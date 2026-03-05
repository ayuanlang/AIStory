from sqlalchemy.orm import Session
from app.models.all_models import User, TransactionHistory, SystemAPISetting
from fastapi import HTTPException
import logging
import math
import re
import json
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class BillingService:
    TOKEN_UNIT_TYPES = {'per_token', 'per_1k_tokens', 'per_million_tokens'}
    FEATURE_PRICING_PROVIDER = "feature_pricing"
    FEATURE_PRICING_MODEL = "global"
    DEFAULT_API_PRICING_PROVIDER = "default_api_pricing"
    DEFAULT_API_PRICING_MODEL = "global"
    DEFAULT_API_PRICING_BY_CATEGORY = {
        "LLM": {"unit_type": "per_million_tokens", "cost": 90, "cost_input": 90, "cost_output": 700},
        "Vision": {"unit_type": "per_million_tokens", "cost": 120, "cost_input": 120, "cost_output": 800},
        "Image": {"unit_type": "per_call", "cost": 10, "cost_input": 0, "cost_output": 0},
        "Video": {"unit_type": "per_second", "cost": 30, "cost_input": 0, "cost_output": 0},
        "Tools": {"unit_type": "per_call", "cost": 5, "cost_input": 0, "cost_output": 0},
    }

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            if value is None:
                return int(default)
            return int(float(value))
        except Exception:
            return int(default)

    @staticmethod
    def _safe_json_dict(value: Any) -> Dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    @staticmethod
    def _task_type_to_category(task_type: str) -> str:
        normalized = str(task_type or "").strip().lower()
        if normalized == "image_gen":
            return "Image"
        if normalized == "video_gen":
            return "Video"
        if normalized == "analysis_character":
            return "Vision"
        if normalized == "analysis":
            return "Vision"
        if normalized == "llm_chat":
            return "LLM"
        return "Tools"

    @staticmethod
    def _normalize_api_pricing_config(raw_config: Dict[str, Any]) -> Dict[str, Any]:
        config = dict(raw_config or {})
        unit_type = str(config.get("unit_type", "per_call") or "per_call").strip()
        allowed_unit_types = {"per_call", "per_second", "per_minute", *BillingService.TOKEN_UNIT_TYPES}
        if unit_type not in allowed_unit_types:
            unit_type = "per_call"

        return {
            "unit_type": unit_type,
            "cost": max(0, BillingService._to_int(config.get("cost", 0), 0)),
            "cost_input": max(0, BillingService._to_int(config.get("cost_input", 0), 0)),
            "cost_output": max(0, BillingService._to_int(config.get("cost_output", 0), 0)),
        }

    @staticmethod
    def _has_effective_api_pricing(config: Dict[str, Any]) -> bool:
        normalized = BillingService._normalize_api_pricing_config(config)
        return any(normalized.get(key, 0) > 0 for key in ("cost", "cost_input", "cost_output"))

    @staticmethod
    def _normalize_default_api_pricing_map(pricing_map: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        normalized: Dict[str, Dict[str, Any]] = {}
        source = pricing_map if isinstance(pricing_map, dict) else {}
        for category, fallback_cfg in BillingService.DEFAULT_API_PRICING_BY_CATEGORY.items():
            raw = source.get(category)
            if isinstance(raw, dict):
                normalized[category] = BillingService._normalize_api_pricing_config(raw)
                continue
            if raw is not None:
                normalized[category] = BillingService._normalize_api_pricing_config({
                    "unit_type": "per_call",
                    "cost": raw,
                    "cost_input": 0,
                    "cost_output": 0,
                })
                continue
            normalized[category] = BillingService._normalize_api_pricing_config(fallback_cfg)
        return normalized

    @staticmethod
    def get_recommended_default_api_pricing_map() -> Dict[str, Dict[str, Any]]:
        return BillingService._normalize_default_api_pricing_map(BillingService.DEFAULT_API_PRICING_BY_CATEGORY)

    @staticmethod
    def get_default_api_pricing_map(db: Session) -> Dict[str, Dict[str, Any]]:
        row = db.query(SystemAPISetting).filter(
            SystemAPISetting.category == "System_Payment",
            SystemAPISetting.provider == BillingService.DEFAULT_API_PRICING_PROVIDER,
            SystemAPISetting.model == BillingService.DEFAULT_API_PRICING_MODEL,
        ).order_by(SystemAPISetting.id.desc()).first()

        if not row:
            return BillingService.get_recommended_default_api_pricing_map()

        cfg = BillingService._safe_json_dict(row.config)
        raw_map = cfg.get("default_api_pricing") if isinstance(cfg.get("default_api_pricing"), dict) else {}
        return BillingService._normalize_default_api_pricing_map(raw_map)

    @staticmethod
    def set_default_api_pricing_map(db: Session, pricing_map: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        normalized = BillingService._normalize_default_api_pricing_map(pricing_map)

        row = db.query(SystemAPISetting).filter(
            SystemAPISetting.category == "System_Payment",
            SystemAPISetting.provider == BillingService.DEFAULT_API_PRICING_PROVIDER,
            SystemAPISetting.model == BillingService.DEFAULT_API_PRICING_MODEL,
        ).order_by(SystemAPISetting.id.desc()).first()

        if not row:
            row = SystemAPISetting(
                name="Default API Pricing",
                category="System_Payment",
                provider=BillingService.DEFAULT_API_PRICING_PROVIDER,
                api_key="",
                base_url="",
                model=BillingService.DEFAULT_API_PRICING_MODEL,
                deprecated=False,
                config={"default_api_pricing": normalized},
                is_active=True,
            )
            db.add(row)
            db.commit()
            return normalized

        cfg = BillingService._safe_json_dict(row.config)
        cfg["default_api_pricing"] = normalized
        row.config = cfg
        db.commit()
        return normalized

    @staticmethod
    def _default_api_pricing_config(db: Session, task_type: str) -> Dict[str, Any]:
        pricing_map = BillingService.get_default_api_pricing_map(db)
        category = BillingService._task_type_to_category(task_type)
        default_cfg = pricing_map.get(
            category,
            pricing_map.get("Tools") or BillingService.DEFAULT_API_PRICING_BY_CATEGORY["Tools"],
        )
        return BillingService._normalize_api_pricing_config(default_cfg)

    @staticmethod
    def get_feature_pricing_map(db: Session) -> Dict[str, int]:
        row = db.query(SystemAPISetting).filter(
            SystemAPISetting.category == "System_Payment",
            SystemAPISetting.provider == BillingService.FEATURE_PRICING_PROVIDER,
            SystemAPISetting.model == BillingService.FEATURE_PRICING_MODEL,
        ).order_by(SystemAPISetting.id.desc()).first()

        if not row:
            return {}

        cfg = BillingService._safe_json_dict(row.config)
        raw_map = cfg.get("feature_pricing") if isinstance(cfg.get("feature_pricing"), dict) else {}
        out: Dict[str, int] = {}
        for key, value in raw_map.items():
            text_key = str(key or "").strip()
            if not text_key:
                continue
            out[text_key] = max(0, BillingService._to_int(value, 0))
        return out

    @staticmethod
    def set_feature_pricing_map(db: Session, pricing: Dict[str, Any]) -> Dict[str, int]:
        normalized: Dict[str, int] = {}
        for key, value in (pricing or {}).items():
            text_key = str(key or "").strip()
            if not text_key:
                continue
            normalized[text_key] = max(0, BillingService._to_int(value, 0))

        row = db.query(SystemAPISetting).filter(
            SystemAPISetting.category == "System_Payment",
            SystemAPISetting.provider == BillingService.FEATURE_PRICING_PROVIDER,
            SystemAPISetting.model == BillingService.FEATURE_PRICING_MODEL,
        ).order_by(SystemAPISetting.id.desc()).first()

        if not row:
            row = SystemAPISetting(
                name="Feature Pricing",
                category="System_Payment",
                provider=BillingService.FEATURE_PRICING_PROVIDER,
                api_key="",
                base_url="",
                model=BillingService.FEATURE_PRICING_MODEL,
                deprecated=False,
                config={"feature_pricing": normalized},
                is_active=True,
            )
            db.add(row)
            db.commit()
            return normalized

        cfg = BillingService._safe_json_dict(row.config)
        cfg["feature_pricing"] = normalized
        row.config = cfg
        db.commit()
        return normalized

    @staticmethod
    def _resolve_feature_cost(db: Session, task_type: str, details: dict = None) -> int:
        pricing_map = BillingService.get_feature_pricing_map(db)
        if not pricing_map:
            return 0

        payload = dict(details or {})
        candidates: List[str] = []
        for key in ["billing_feature", "feature", "item"]:
            value = payload.get(key)
            if value is not None:
                text = str(value).strip()
                if text:
                    candidates.append(text)
        task_text = str(task_type or "").strip()
        if task_text:
            candidates.append(task_text)

        for candidate in candidates:
            if candidate in pricing_map:
                return max(0, BillingService._to_int(pricing_map[candidate], 0))
        return 0

    @staticmethod
    def _resolve_api_pricing_config(db: Session, task_type: str, provider: str = None, model: str = None) -> Dict[str, Any]:
        provider_text = str(provider or "").strip()
        model_text = str(model or "").strip()
        category = BillingService._task_type_to_category(task_type)
        default_pricing = BillingService._default_api_pricing_config(db, task_type)

        query = db.query(SystemAPISetting).filter(
            SystemAPISetting.category == category,
            SystemAPISetting.provider == provider_text,
        )
        if model_text:
            query = query.filter(SystemAPISetting.model == model_text)
        row = query.order_by(SystemAPISetting.id.desc()).first()

        if not row and provider_text and model_text:
            row = db.query(SystemAPISetting).filter(
                SystemAPISetting.category == category,
                SystemAPISetting.provider == provider_text,
                SystemAPISetting.model == None,
            ).order_by(SystemAPISetting.id.desc()).first()

        if not row and provider_text:
            query_any_category = db.query(SystemAPISetting).filter(
                SystemAPISetting.provider == provider_text,
            )
            if model_text:
                query_any_category = query_any_category.filter(SystemAPISetting.model == model_text)
            else:
                query_any_category = query_any_category.filter(SystemAPISetting.model == None)
            row = query_any_category.order_by(SystemAPISetting.id.desc()).first()

        if not row:
            return default_pricing

        cfg = BillingService._safe_json_dict(row.config)
        api_pricing = cfg.get("api_pricing") if isinstance(cfg.get("api_pricing"), dict) else {}
        resolved = api_pricing if api_pricing else {
            "unit_type": cfg.get("billing_unit_type", "per_call"),
            "cost": cfg.get("billing_cost", 0),
            "cost_input": cfg.get("billing_cost_input", 0),
            "cost_output": cfg.get("billing_cost_output", 0),
        }
        resolved = BillingService._normalize_api_pricing_config(resolved)

        if not BillingService._has_effective_api_pricing(resolved):
            return default_pricing
        return resolved

    @staticmethod
    def _estimate_api_cost_from_config(config: Dict[str, Any], details: dict = None) -> int:
        if not config:
            return 0

        unit_type = str(config.get("unit_type", "per_call") or "per_call").strip()
        base_cost = max(0, BillingService._to_int(config.get("cost", 0), 0))
        cost_input = max(0, BillingService._to_int(config.get("cost_input", 0), 0))
        cost_output = max(0, BillingService._to_int(config.get("cost_output", 0), 0))

        payload = dict(details or {})
        if unit_type in BillingService.TOKEN_UNIT_TYPES:
            input_tokens = BillingService._to_int(payload.get("input_tokens", payload.get("prompt_tokens", 0)), 0)
            output_tokens = BillingService._to_int(payload.get("output_tokens", payload.get("completion_tokens", 0)), 0)
            total_tokens = BillingService._to_int(payload.get("total_tokens", 0), 0)
            if input_tokens == 0 and output_tokens == 0 and total_tokens > 0:
                input_tokens = total_tokens

            divisor = 1_000_000.0 if unit_type == 'per_million_tokens' else 1_000.0 if unit_type == 'per_1k_tokens' else 1.0
            token_cost = ((float(input_tokens) * float(cost_input)) + (float(output_tokens) * float(cost_output))) / divisor
            if cost_input == 0 and cost_output == 0 and base_cost > 0:
                token_cost = (float(max(total_tokens, input_tokens + output_tokens)) * float(base_cost)) / divisor
            return max(0, int(round(token_cost)))

        quantity = 1.0
        if unit_type == 'per_second':
            quantity = float(payload.get('duration_seconds', payload.get('duration', 0)) or 0)
        elif unit_type == 'per_minute':
            quantity = float(payload.get('duration_seconds', payload.get('duration', 0)) or 0) / 60.0

        if quantity <= 0 and unit_type in {'per_second', 'per_minute'}:
            return 0
        return max(0, int(round(float(base_cost) * float(quantity))))

    @staticmethod
    def _estimate_tokens_from_text(text: str) -> int:
        if not text:
            return 0

        # Normalize whitespace; bytes-based heuristic works reasonably across CJK/EN.
        normalized = re.sub(r"\s+", " ", str(text)).strip()
        if not normalized:
            return 0

        # Heuristic: ~4 bytes per token on average.
        return max(1, int(math.ceil(len(normalized.encode("utf-8")) / 4.0)))

    @staticmethod
    def estimate_input_output_tokens_from_messages(
        messages: List[Dict[str, Any]],
        output_ratio: float = 1.5
    ) -> Dict[str, int]:
        """
        Estimates token usage based on the *actual system/user prompts* we send.
        Output tokens are estimated as input_tokens * output_ratio.

        Notes:
        - Counts only textual parts for multimodal messages.
        - Adds a small per-message overhead to reduce underestimation.
        """
        input_tokens = 0
        overhead_per_message = 4

        for msg in messages or []:
            input_tokens += overhead_per_message
            content = msg.get("content")

            if isinstance(content, str):
                input_tokens += BillingService._estimate_tokens_from_text(content)
                continue

            # Multimodal / structured content
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    # OpenAI: {type: text, text: "..."}
                    if part.get("type") == "text" and "text" in part:
                        input_tokens += BillingService._estimate_tokens_from_text(part.get("text"))
                    # Ark/Doubao style: {type: input_text, text: "..."}
                    if part.get("type") == "input_text" and "text" in part:
                        input_tokens += BillingService._estimate_tokens_from_text(part.get("text"))
                continue

        output_tokens = int(math.ceil(float(input_tokens) * float(output_ratio))) if input_tokens > 0 else 0
        return {
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
            "total_tokens": int(input_tokens + output_tokens)
        }

    @staticmethod
    def is_token_pricing(db: Session, task_type: str, provider: str = None, model: str = None) -> bool:
        api_cfg = BillingService._resolve_api_pricing_config(db, task_type, provider, model)
        if api_cfg:
            unit_type = str(api_cfg.get("unit_type", "per_call") or "per_call").strip()
            if unit_type in BillingService.TOKEN_UNIT_TYPES:
                return True
        return False

    @staticmethod
    def reserve_credits(
        db: Session,
        user_id: int,
        task_type: str,
        provider: str = None,
        model: str = None,
        details: dict = None
    ) -> TransactionHistory:
        """Pre-deduct (freeze) estimated credits and create a RESERVED transaction."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        reserve_details = dict(details or {})
        reserve_details.setdefault("status", "RESERVED")
        reserve_details.setdefault("billing_mode", "RESERVE")

        reserved_cost = BillingService.estimate_cost(db, task_type, provider, model, details=reserve_details)
        BillingService.check_can_proceed(user, reserved_cost)

        user.credits -= reserved_cost

        tx = TransactionHistory(
            user_id=user_id,
            amount=-reserved_cost,
            balance_after=user.credits or 0,
            task_type=task_type,
            provider=provider,
            model=model,
            details=reserve_details
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        logger.info(
            f"Reserved {reserved_cost} credits from user {user_id} for {task_type}. New Balance: {user.credits}"
        )
        return tx

    @staticmethod
    def cancel_reservation(db: Session, reservation_tx_id: int, error_msg: str = None) -> Optional[TransactionHistory]:
        """Refunds a reservation when an upstream call fails."""
        tx = db.query(TransactionHistory).filter(TransactionHistory.id == reservation_tx_id).first()
        if not tx:
            return None

        if tx.amount >= 0:
            return tx

        user = db.query(User).filter(User.id == tx.user_id).first()
        if not user:
            return tx

        reserved_cost = int(abs(tx.amount))
        user.credits = (user.credits or 0) + reserved_cost

        refund_details = {
            "status": "REFUND",
            "reason": "RESERVATION_CANCELED",
            "reservation_tx_id": tx.id,
        }
        if error_msg:
            refund_details["error"] = str(error_msg)[:500]

        refund_tx = TransactionHistory(
            user_id=tx.user_id,
            amount=reserved_cost,
            balance_after=user.credits or 0,
            task_type=tx.task_type,
            provider=tx.provider,
            model=tx.model,
            details=refund_details,
        )
        db.add(refund_tx)

        tx_details = dict(tx.details or {})
        tx_details["status"] = "CANCELED"
        tx_details["refund_tx_id"] = refund_tx.id  # may be None until commit
        if error_msg:
            tx_details["error"] = str(error_msg)[:500]
        tx.details = tx_details

        db.commit()
        db.refresh(refund_tx)

        # Backfill link after we know refund id
        tx_details = dict(tx.details or {})
        tx_details["refund_tx_id"] = refund_tx.id
        tx.details = tx_details
        db.commit()

        return refund_tx

    @staticmethod
    def settle_reservation(
        db: Session,
        reservation_tx_id: int,
        actual_details: dict = None
    ) -> Dict[str, Any]:
        """
        Reconciles a RESERVED transaction using actual token usage.
        Creates a settlement transaction if refund/extra charge is needed.
        Updates the reservation transaction's details with actual usage and settlement refs.
        """
        reservation_tx = db.query(TransactionHistory).filter(TransactionHistory.id == reservation_tx_id).first()
        if not reservation_tx:
            raise HTTPException(status_code=404, detail="Reservation transaction not found")

        user = db.query(User).filter(User.id == reservation_tx.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        reserved_cost = int(abs(reservation_tx.amount or 0))
        details = dict(actual_details or {})
        details.setdefault("billing_mode", "ACTUAL")

        # Normalize usage keys
        if "input_tokens" not in details and "prompt_tokens" in details:
            details["input_tokens"] = details.get("prompt_tokens", 0)
        if "output_tokens" not in details and "completion_tokens" in details:
            details["output_tokens"] = details.get("completion_tokens", 0)

        actual_cost = BillingService.estimate_cost(
            db,
            reservation_tx.task_type,
            reservation_tx.provider,
            reservation_tx.model,
            details=details
        )

        delta = int(actual_cost - reserved_cost)
        settlement_tx = None
        outstanding = 0

        if delta < 0:
            refund = -delta
            user.credits = (user.credits or 0) + refund
            settlement_tx = TransactionHistory(
                user_id=user.id,
                amount=refund,
                balance_after=user.credits or 0,
                task_type=reservation_tx.task_type,
                provider=reservation_tx.provider,
                model=reservation_tx.model,
                details={
                    "status": "REFUND",
                    "reason": "RESERVATION_SETTLEMENT",
                    "reservation_tx_id": reservation_tx.id,
                    "reserved_cost": reserved_cost,
                    "actual_cost": actual_cost,
                }
            )
            db.add(settlement_tx)
        elif delta > 0:
            extra = delta
            can_deduct = min(int(user.credits or 0), extra)
            if can_deduct > 0:
                user.credits -= can_deduct
                settlement_tx = TransactionHistory(
                    user_id=user.id,
                    amount=-can_deduct,
                    balance_after=user.credits or 0,
                    task_type=reservation_tx.task_type,
                    provider=reservation_tx.provider,
                    model=reservation_tx.model,
                    details={
                        "status": "CHARGE",
                        "reason": "RESERVATION_SETTLEMENT",
                        "reservation_tx_id": reservation_tx.id,
                        "reserved_cost": reserved_cost,
                        "actual_cost": actual_cost,
                        "delta": delta,
                    }
                )
                db.add(settlement_tx)

            outstanding = extra - can_deduct
            if outstanding > 0:
                logger.warning(
                    f"User {user.id} could not cover settlement delta={extra}. outstanding={outstanding}"
                )

        # Update reservation details for audit
        res_details = dict(reservation_tx.details or {})
        res_details["status"] = "SETTLED"
        res_details["reserved_cost"] = reserved_cost
        res_details["actual_cost"] = actual_cost
        res_details["delta"] = delta
        if outstanding > 0:
            res_details["outstanding_delta"] = outstanding

        if settlement_tx is not None:
            # Will be populated after commit/refresh, but keep placeholder for clarity.
            res_details["settlement_tx_id"] = None

        # Add actual usage details (token counts, etc)
        res_details.update({
            "actual_input_tokens": int(details.get("input_tokens", 0) or 0),
            "actual_output_tokens": int(details.get("output_tokens", 0) or 0),
            "actual_total_tokens": int(details.get("total_tokens", 0) or 0),
        })
        reservation_tx.details = res_details

        db.commit()
        if settlement_tx:
            db.refresh(settlement_tx)

            # Backfill settlement id into reservation details
            res_details = dict(reservation_tx.details or {})
            res_details["settlement_tx_id"] = settlement_tx.id
            reservation_tx.details = res_details
            db.commit()

        return {
            "reserved_cost": reserved_cost,
            "actual_cost": actual_cost,
            "delta": delta,
            "settlement_tx_id": settlement_tx.id if settlement_tx else None,
            "outstanding_delta": outstanding,
        }
    @staticmethod
    def estimate_cost(db: Session, task_type: str, provider: str = None, model: str = None, details: dict = None) -> int:
        feature_cost = BillingService._resolve_feature_cost(db, task_type, details)
        api_pricing_cfg = BillingService._resolve_api_pricing_config(db, task_type, provider, model)
        if api_pricing_cfg:
            api_cost = BillingService._estimate_api_cost_from_config(api_pricing_cfg, details)
            return max(0, int(feature_cost) + int(api_cost))
        return max(0, int(feature_cost))


    @staticmethod
    def check_balance(db: Session, user_id: int, task_type: str, provider: str = None, model: str = None):
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
             raise HTTPException(status_code=404, detail="User not found")
        
        # Estimate base cost
        cost = BillingService.estimate_cost(db, task_type, provider, model)
        # Check
        BillingService.check_can_proceed(user, cost)

    @staticmethod
    def check_can_proceed(user: User, cost: int):
        """
        Raises HTTPException if user doesn't have enough credits.
        """
        if user.credits is None:
            user.credits = 0
            
        if user.credits < cost:
            raise HTTPException(
                status_code=402, 
                detail=f"Insufficient credits. Required: {cost}, Available: {user.credits}. Please top up."
            )
        return True

    @staticmethod
    def deduct_credits(
        db: Session, 
        user_id: int, 
        task_type: str, 
        provider: str = None, 
        model: str = None, 
        details: dict = None
    ) -> TransactionHistory:
        """
        Deducts credits from user and logs transaction.
        """
        # Re-fetch user to lock/ensure latest state
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        final_cost = BillingService.estimate_cost(db, task_type, provider, model, details=details)
        
        if user.credits < final_cost:
             raise HTTPException(status_code=402, detail="Insufficient credits during deduction.")
             
        user.credits -= final_cost
        
        # Log Transaction
        transaction = TransactionHistory(
            user_id=user_id,
            amount=-final_cost,
            balance_after=user.credits,
            task_type=task_type,
            provider=provider,
            model=model,
            details=details or {}
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        logger.info(f"Deducted {final_cost} credits from user {user_id} for {task_type}. New Balance: {user.credits}")
        return transaction

    @staticmethod
    def log_failed_transaction(
        db: Session, 
        user_id: int, 
        task_type: str, 
        provider: str = None, 
        model: str = None, 
        error_msg: str = None,
        details: dict = None
    ):
        """
        Logs a failed transaction for visibility in recent transactions.
        """
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.error(f"Cannot log failure for non-existent user {user_id}")
                return

            fail_details = details or {}
            fail_details["status"] = "FAILED"
            fail_details["error"] = str(error_msg)[:500] # Truncate error

            transaction = TransactionHistory(
                user_id=user_id,
                amount=0,
                balance_after=user.credits or 0,
                task_type=task_type,
                provider=provider,
                model=model,
                details=fail_details
            )
            db.add(transaction)
            db.commit()
            logger.info(f"Logged failed transaction for user {user_id}: {error_msg}")
        except Exception as e:
            logger.error(f"Failed to log transaction failure: {e}")
            db.rollback()

billing_service = BillingService()
