from sqlalchemy.orm import Session
from app.models.all_models import User, PricingRule, TransactionHistory
from fastapi import HTTPException
import logging
import math
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class BillingService:
    TOKEN_UNIT_TYPES = {'per_token', 'per_1k_tokens', 'per_million_tokens'}

    @staticmethod
    def _task_type_candidates(task_type: str) -> List[str]:
        """Return ordered task_type candidates for pricing lookup fallback."""
        primary = str(task_type or "").strip()
        if not primary:
            return []

        alias_map = {
            # Vision/entity analysis historically billed as analysis_character,
            # but many deployments only have analysis or llm_chat rules.
            "analysis_character": ["analysis", "llm_chat"],
            "analysis": ["llm_chat"],
        }

        out = [primary]
        for candidate in alias_map.get(primary, []):
            if candidate not in out:
                out.append(candidate)
        return out

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
        rule = BillingService.get_pricing_rule(db, task_type, provider, model)
        return bool(rule and rule.unit_type in BillingService.TOKEN_UNIT_TYPES)

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
    def get_pricing_rule(db: Session, task_type: str, provider: str = None, model: str = None) -> PricingRule:
        """
        Finds the pricing rule for the given parameters.
        Matching priority:
        1) Exact match on (task_type, provider, model)
        2) Fallback on (task_type, provider, model=None) if model-specific not found
        3) Fallback on generic (task_type, provider=None, model=None) if provider-specific not found
        """
        for candidate_task in BillingService._task_type_candidates(task_type):
            base = db.query(PricingRule).filter(
                PricingRule.task_type == candidate_task,
                PricingRule.is_active == True
            )

            # 1) Exact
            if provider is not None:
                q = base.filter(PricingRule.provider == provider)
            else:
                q = base.filter(PricingRule.provider == None)

            if model is not None:
                q = q.filter(PricingRule.model == model)
            else:
                q = q.filter(PricingRule.model == None)

            rule = q.first()
            if rule:
                if candidate_task != task_type:
                    logger.warning(
                        "Pricing rule fallback hit: requested_task=%s fallback_task=%s provider=%s model=%s rule_id=%s",
                        task_type,
                        candidate_task,
                        provider,
                        model,
                        rule.id,
                    )
                return rule

            # 2) Provider-level fallback (model=None)
            if provider is not None and model is not None:
                rule = base.filter(
                    PricingRule.provider == provider,
                    PricingRule.model == None
                ).first()
                if rule:
                    if candidate_task != task_type:
                        logger.warning(
                            "Pricing rule fallback hit (provider-level): requested_task=%s fallback_task=%s provider=%s model=%s rule_id=%s",
                            task_type,
                            candidate_task,
                            provider,
                            model,
                            rule.id,
                        )
                    return rule

            # 3) Generic fallback
            if provider is not None or model is not None:
                rule = base.filter(
                    PricingRule.provider == None,
                    PricingRule.model == None
                ).first()
                if rule:
                    if candidate_task != task_type:
                        logger.warning(
                            "Pricing rule fallback hit (generic): requested_task=%s fallback_task=%s provider=%s model=%s rule_id=%s",
                            task_type,
                            candidate_task,
                            provider,
                            model,
                            rule.id,
                        )
                    return rule

        return None

    @staticmethod
    def estimate_cost(db: Session, task_type: str, provider: str = None, model: str = None, details: dict = None) -> int:
        rule = BillingService.get_pricing_rule(db, task_type, provider, model)
        if not rule:
            error_msg = f"No pricing rule found for task: {task_type}, provider: {provider}, model: {model}"
            logger.error(error_msg)
            raise HTTPException(
                status_code=500,
                detail=f"Pricing configuration error: missing pricing rule for task={task_type}, provider={provider}, model={model}."
            )

        # Advanced Calculation Logic
        try:
            # Token-unit dual pricing (Input/Output) is driven by unit_type, not task_type.
            if details and rule.unit_type in BillingService.TOKEN_UNIT_TYPES and (
                'input_tokens' in details or 'output_tokens' in details or 'total_tokens' in details
            ):
                input_tokens = details.get('input_tokens', None)
                output_tokens = details.get('output_tokens', None)

                # Back-compat: if caller only provides total_tokens, treat as input.
                if input_tokens is None and output_tokens is None:
                    input_tokens = details.get('total_tokens', 0)
                    output_tokens = 0
                else:
                    input_tokens = input_tokens or 0
                    output_tokens = output_tokens or 0

                if rule.cost_input is None or rule.cost_output is None or rule.cost_input <= 0 or rule.cost_output <= 0:
                    raise HTTPException(
                        status_code=500,
                        detail="Pricing configuration error: token unit type requires positive cost_input and cost_output."
                    )

                divisor = 1_000_000.0 if rule.unit_type == 'per_million_tokens' else \
                          1_000.0 if rule.unit_type == 'per_1k_tokens' else 1.0

                cost_in = (float(input_tokens) / divisor) * float(rule.cost_input)
                cost_out = (float(output_tokens) / divisor) * float(rule.cost_output)

                total_calculated = cost_in + cost_out
                return int(max(1, round(total_calculated)))

            # Standard Unit Multipliers
            quantity = 1.0
            if details:
                if rule.unit_type == 'per_second':
                    quantity = float(details.get('duration_seconds', 0))
                elif rule.unit_type == 'per_minute':
                    quantity = float(details.get('duration_seconds', 0)) / 60.0
                elif rule.unit_type == 'per_token':
                    quantity = float(details.get('total_tokens', 0))
                elif rule.unit_type == 'per_1k_tokens':
                    quantity = float(details.get('total_tokens', 0)) / 1000.0
                elif rule.unit_type == 'per_million_tokens':
                    quantity = float(details.get('total_tokens', 0)) / 1_000_000.0
            
            total = float(rule.cost) * quantity
            return int(max(1, round(total))) if total > 0 else 0

        except Exception as e:
            logger.error(f"Error calculating cost: {e}")
            return rule.cost


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
