from sqlalchemy.orm import Session, load_only
from app.models.all_models import (
    User,
    TransactionHistory,
    SystemAPISetting,
    SystemAPIBillingRule,
    TransactionAction,
    UserGroup,
    ProjectGroupCreditAllocation,
    FunctionAPIConfig,
)
from fastapi import HTTPException
import logging
import math
import re
import json
from typing import Any, Dict, List, Optional
from app.services.system_default_api_service import list_task_default_system_settings
from sqlalchemy import text

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
    CONTENT_FALLBACK_CONTENT_TYPES = ["text", "image", "video"]
    CONTENT_FALLBACK_STRATEGIES = {"manual", "average", "highest"}
    CONTENT_FALLBACK_CATEGORY_MAP = {
        "text": ["LLM", "Vision", "Tools", "Voice", "Music"],
        "image": ["Image"],
        "video": ["Video"],
    }
    BASE_BILLING_RULE_KIND = "base_pricing"
    BASE_BILLING_RULE_PRIORITY = -100000
    _USAGE_POSITIVE_KEYS = {
        "input_tokens", "output_tokens", "total_tokens", "cache_hit_tokens", "cache_miss_tokens",
        "width", "height", "pixels", "image_count", "duration_seconds", "fps", "success_output_count",
        "billing_quantity",
    }
    _AUDIT_USAGE_DROP_ZERO_KEYS = {
        "input_tokens", "output_tokens", "total_tokens", "cache_hit_tokens", "cache_miss_tokens",
        "success_output_count", "billing_quantity", "duration_seconds", "fps",
    }
    _AUDIT_BREAKDOWN_DROP_ZERO_KEYS = {
        "feature_cost", "api_cost", "fallback_api_cost", "total_cost",
    }
    MINIMUM_CHARGE_BY_TASK = {
        "llm_chat": 1,
    }
    # LLM pre-reserve: output is typically shorter than input.
    # Legacy reserve used 1.5x input for output; pre-deduct at ~30% of that (0.45x).
    RESERVE_OUTPUT_RATIO = 0.45
    KIE_STANDARD_PROVIDER = "kie"
    # Legacy Seedance runtime odds (draft 0.7 / continuation 1.5) are retired.
    # Draft bills via 480p (or native token dims); continuation via with-video rates / input duration.
    DEFAULT_SEEDANCE_DRAFT_PRICE_MULTIPLIER = 1.0
    DEFAULT_SEEDANCE_CONTINUATION_PRICE_MULTIPLIER = 1.0

    @staticmethod
    def _system_setting_query(db: Session):
        # Keep SystemAPISetting reads compatible with environments where legacy
        # price_* columns were dropped from the physical table.
        return db.query(SystemAPISetting).options(
            load_only(
                SystemAPISetting.id,
                SystemAPISetting.name,
                SystemAPISetting.category,
                SystemAPISetting.provider,
                SystemAPISetting.api_key,
                SystemAPISetting.base_url,
                SystemAPISetting.model,
                SystemAPISetting.base_model,
                SystemAPISetting.modality,
                SystemAPISetting.tags,
                SystemAPISetting.supplier_info,
                SystemAPISetting.deprecated,
                SystemAPISetting.config,
                SystemAPISetting.is_active,
            )
        )

    @staticmethod
    def _task_type_for_category(category: str) -> str:
        normalized = str(category or "").strip().lower()
        if normalized == "image":
            return "image_gen"
        if normalized == "video":
            return "video_gen"
        if normalized == "voice":
            return "voice_gen"
        if normalized == "music":
            return "music_gen"
        if normalized == "vision":
            return "analysis"
        if normalized == "llm":
            return "llm_chat"
        return "llm_chat"

    @staticmethod
    def _default_usage_profiles_for_category(category: str, generation_mode: Optional[str] = None) -> List[Dict[str, Any]]:
        cat = str(category or "").strip().lower()
        gm = str(generation_mode or "").strip().lower()

        if cat == "image":
            if gm in {"i2i", "image-to-image", "image2image", "img2img"}:
                return [{"image_count": 1, "width": 1024, "height": 1024, "generation_mode": "i2i"}]
            return [{"image_count": 1, "width": 1024, "height": 1024, "generation_mode": "t2i"}]

        if cat == "video":
            if gm in {"i2v", "image-to-video", "image2video", "img2video"}:
                return [{"duration_seconds": 5, "width": 1280, "height": 720, "fps": 24, "generation_mode": "i2v"}]
            return [{"duration_seconds": 5, "width": 1280, "height": 720, "fps": 24, "generation_mode": "t2v"}]

        if cat == "vision":
            return [{"input_tokens": 1000, "output_tokens": 300, "total_tokens": 1300}]

        if cat == "llm":
            # LLM average estimation baseline: 1M total tokens with input:output = 3:1.
            return [{"input_tokens": 750000, "output_tokens": 250000, "total_tokens": 1000000}]

        return [{"input_tokens": 1500, "output_tokens": 700, "total_tokens": 2200}]

    @staticmethod
    def estimate_system_api_average_price(
        db: Session,
        system_api_id: int,
        generation_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            api_id = int(system_api_id or 0)
        except Exception:
            api_id = 0
        if api_id <= 0:
            return {
                "average_cost": 0,
                "source": "invalid_system_api_id",
                "samples": 0,
                "min_cost": 0,
                "max_cost": 0,
                "sample_prices": [],
            }

        system_row = BillingService._system_setting_query(db).filter(SystemAPISetting.id == api_id).first()
        if not system_row:
            return {
                "average_cost": 0,
                "source": "system_api_not_found",
                "samples": 0,
                "min_cost": 0,
                "max_cost": 0,
                "sample_prices": [],
            }

        category = str(getattr(system_row, "category", "") or "").strip()
        rule_range = BillingService._estimate_price_range_from_billing_rules(
            db,
            api_id,
            category,
        )

        # Preferred source: real billing audit records from transaction_action.
        audit_avg = BillingService._estimate_average_price_from_audit_records(db, api_id)
        if audit_avg is not None:
            if rule_range is not None:
                audit_avg["min_cost"] = int(rule_range.get("min_cost") or 0)
                audit_avg["max_cost"] = int(rule_range.get("max_cost") or 0)
            return audit_avg

        # Fallback source: paid transaction history rows when action audit rows are missing.
        history_avg = BillingService._estimate_average_price_from_transaction_history(
            db,
            api_id,
            provider=str(getattr(system_row, "provider", "") or "").strip(),
            model=str(getattr(system_row, "model", "") or "").strip(),
        )
        if history_avg is not None:
            if rule_range is not None:
                history_avg["min_cost"] = int(rule_range.get("min_cost") or 0)
                history_avg["max_cost"] = int(rule_range.get("max_cost") or 0)
            return history_avg

        # Media categories: prefer averaging this API's own active rule prices.
        media_avg = BillingService._estimate_media_average_price_from_rules(db, api_id, category)
        if media_avg is not None:
            if rule_range is not None:
                media_avg["min_cost"] = int(rule_range.get("min_cost") or 0)
                media_avg["max_cost"] = int(rule_range.get("max_cost") or 0)
            return media_avg

        task_type = BillingService._task_type_for_category(category)
        profiles = BillingService._default_usage_profiles_for_category(category, generation_mode=generation_mode)

        costs: List[int] = []
        sources: List[str] = []
        for usage in profiles:
            breakdown = BillingService.estimate_cost_breakdown(
                db,
                task_type=task_type,
                provider=str(getattr(system_row, "provider", "") or "").strip(),
                model=str(getattr(system_row, "model", "") or "").strip(),
                details={**dict(usage or {}), "system_api_id": api_id},
                phase="reserve",
            )
            costs.append(int(breakdown.get("api_cost") or 0))
            sources.append(str(breakdown.get("api_pricing_source") or "").strip() or "unknown")

        # Exclude zero-cost values to avoid misleading ranges/samples in UI.
        non_zero_costs = [int(c) for c in costs if int(c) > 0]
        if not non_zero_costs:
            # Fallback 1: if billing-rule range exists, derive a display average from range midpoint.
            if rule_range is not None:
                range_min = int(rule_range.get("min_cost") or 0)
                range_max = int(rule_range.get("max_cost") or 0)
                if range_min > 0 or range_max > 0:
                    if range_min <= 0:
                        range_min = range_max
                    if range_max <= 0:
                        range_max = range_min
                    avg_from_range = int(round((float(range_min) + float(range_max)) / 2.0))
                    return {
                        "average_cost": max(0, avg_from_range),
                        "source": "billing_rule_range_midpoint",
                        "samples": 1,
                        "min_cost": int(range_min),
                        "max_cost": int(range_max),
                        "sample_prices": [],
                    }

            # Fallback 2: use default pricing map representative cost for this task category.
            default_cfg = BillingService._default_api_pricing_config(db, task_type)
            default_cost = max(
                0,
                BillingService._to_int(default_cfg.get("cost"), 0),
                BillingService._to_int(default_cfg.get("cost_input"), 0),
                BillingService._to_int(default_cfg.get("cost_output"), 0),
            )
            if default_cost > 0:
                return {
                    "average_cost": int(default_cost),
                    "source": "default_api_pricing_fallback",
                    "samples": 1,
                    "min_cost": int(default_cost),
                    "max_cost": int(default_cost),
                    "sample_prices": [],
                }

            return {
                "average_cost": 0,
                "source": "no_profiles",
                "samples": 0,
                "min_cost": 0,
                "max_cost": 0,
                "sample_prices": [],
            }

        avg_cost = int(round(sum(non_zero_costs) / float(len(non_zero_costs))))
        source = sources[0] if sources and all(s == sources[0] for s in sources) else "mixed"
        sample_prices = sorted(set(non_zero_costs))[:5]
        return {
            "average_cost": max(0, avg_cost),
            "source": source,
            "samples": len(non_zero_costs),
            "min_cost": int((rule_range or {}).get("min_cost") or min(non_zero_costs)),
            "max_cost": int((rule_range or {}).get("max_cost") or max(non_zero_costs)),
            "sample_prices": [],
        }

    @staticmethod
    def _estimate_price_range_from_billing_rules(
        db: Session,
        system_api_id: int,
        category: str,
    ) -> Optional[Dict[str, int]]:
        rows = db.query(SystemAPIBillingRule).filter(
            SystemAPIBillingRule.system_api_id == int(system_api_id),
            SystemAPIBillingRule.is_active == True,
        ).order_by(SystemAPIBillingRule.priority.desc(), SystemAPIBillingRule.id.desc()).all()

        if not rows:
            return None

        def _rule_effective_cost(rule: SystemAPIBillingRule) -> int:
            # billing_cost columns store raw rule values; UI-facing ranges should reflect
            # the final billed price after the rule multiplier is applied once.
            pricing = BillingService._billing_from_rule(rule)
            return max(
                0,
                BillingService._to_int(pricing.get("cost", 0), 0),
                BillingService._to_int(pricing.get("cost_input", 0), 0),
                BillingService._to_int(pricing.get("cost_output", 0), 0),
            )

        # Price range for settings page is sourced directly from billing rules table
        # by system_api_id, without any key/category/runtime gating.
        costs: List[int] = []
        for row in rows:
            cost = _rule_effective_cost(row)
            if cost <= 0:
                continue
            costs.append(int(cost))

        if not costs:
            return None

        return {
            "min_cost": int(min(costs)),
            "max_cost": int(max(costs)),
        }

    @staticmethod
    def _estimate_media_average_price_from_rules(
        db: Session,
        system_api_id: int,
        category: str,
    ) -> Optional[Dict[str, Any]]:
        cat = str(category or "").strip().lower()
        if cat not in {"image", "video"}:
            return None

        rows = db.query(SystemAPIBillingRule).filter(
            SystemAPIBillingRule.system_api_id == int(system_api_id),
            SystemAPIBillingRule.is_active == True,
        ).order_by(SystemAPIBillingRule.priority.desc(), SystemAPIBillingRule.id.desc()).all()

        if not rows:
            return None

        strict_costs: List[int] = []
        all_costs: List[int] = []
        for row in rows:
            pricing = BillingService._billing_from_rule(row)
            cost = max(
                0,
                BillingService._to_int(pricing.get("cost", 0), 0),
                BillingService._to_int(pricing.get("cost_input", 0), 0),
                BillingService._to_int(pricing.get("cost_output", 0), 0),
            )
            if cost <= 0:
                continue
            all_costs.append(int(cost))

            if cat == "image" and bool(getattr(row, "applies_to_image", False)):
                strict_costs.append(int(cost))
            elif cat == "video" and bool(getattr(row, "applies_to_video", False)):
                strict_costs.append(int(cost))

        # Keep category-aware preference, but support legacy rows without applies flags.
        costs = strict_costs or all_costs

        if not costs:
            return None

        avg_cost = int(round(sum(costs) / float(len(costs))))
        sample_prices = sorted(set(costs))[:5]
        return {
            "average_cost": max(0, avg_cost),
            "source": "system_api_rule_price_average",
            "samples": len(costs),
            "min_cost": min(costs),
            "max_cost": max(costs),
            "sample_prices": [],
        }

    @staticmethod
    def _estimate_average_price_from_audit_records(
        db: Session,
        system_api_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Estimate prices from real transaction audit rows for one system API.

        Uses settled/direct-deduct stages and actual_cost to reflect real billed costs.
        """
        try:
            rows = db.query(TransactionAction).filter(
                TransactionAction.system_api_id == int(system_api_id),
                TransactionAction.stage.in_(["SETTLED", "DEDUCTED"]),
            ).order_by(TransactionAction.id.desc()).limit(200).all()
        except Exception:
            return None

        costs: List[int] = []
        for row in rows or []:
            cost = max(0, BillingService._to_int(getattr(row, "actual_cost", 0), 0))
            if cost <= 0:
                continue
            costs.append(int(cost))

        if not costs:
            return None

        avg_cost = int(round(sum(costs) / float(len(costs))))
        sample_prices = sorted(set(costs))[:5]
        return {
            "average_cost": max(0, avg_cost),
            "source": "transaction_action_audit",
            "samples": len(costs),
            "min_cost": min(costs),
            "max_cost": max(costs),
            "sample_prices": sample_prices,
        }

    @staticmethod
    def _estimate_average_price_from_transaction_history(
        db: Session,
        system_api_id: int,
        provider: str,
        model: str,
    ) -> Optional[Dict[str, Any]]:
        """Fallback average from paid transaction history rows.

        Uses negative (cost) records and prefers rows explicitly linked to this
        system_api_id in billing details. This helps when transaction_action rows
        are missing in older data.
        """
        provider_text = str(provider or "").strip()
        model_text = str(model or "").strip()

        try:
            query = db.query(TransactionHistory).filter(TransactionHistory.amount < 0)
            if provider_text:
                query = query.filter(TransactionHistory.provider == provider_text)
            if model_text:
                query = query.filter(TransactionHistory.model == model_text)
            rows = query.order_by(TransactionHistory.id.desc()).limit(400).all()
        except Exception:
            return None

        costs: List[int] = []
        for row in rows or []:
            details = BillingService._safe_json_dict(getattr(row, "details", {}))
            # Prefer lean history fields; fall back to legacy fat billing_breakdown.
            billing_breakdown = details.get("billing_breakdown") if isinstance(details.get("billing_breakdown"), dict) else {}
            phase = str(
                details.get("phase")
                or billing_breakdown.get("phase")
                or ""
            ).strip().lower()
            status = str(details.get("status") or "").strip().upper()
            reason = str(details.get("reason") or "").strip().upper()

            # Skip reserve hold rows; keep direct deduction and settlement charges.
            if phase == "reserve" or status == "RESERVED":
                continue
            if reason == "RESERVATION_SETTLEMENT" and status not in {"CHARGE"}:
                continue

            row_system_api_id = (
                BillingService._to_int(details.get("system_api_id"), 0)
                or BillingService._to_int(billing_breakdown.get("system_api_id"), 0)
            )
            if row_system_api_id > 0 and row_system_api_id != int(system_api_id):
                continue

            total_cost = BillingService._to_int(billing_breakdown.get("total_cost"), 0)
            actual_cost = BillingService._to_int(details.get("actual_cost"), 0)
            amount_cost = abs(BillingService._to_int(getattr(row, "amount", 0), 0))
            cost = max(0, total_cost, actual_cost, amount_cost)
            if cost <= 0:
                continue
            costs.append(int(cost))

        if not costs:
            return None

        avg_cost = int(round(sum(costs) / float(len(costs))))
        return {
            "average_cost": max(0, avg_cost),
            "source": "transaction_history_paid_average",
            "samples": len(costs),
            "min_cost": min(costs),
            "max_cost": max(costs),
            "sample_prices": [],
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
    def _group_allows_credit_billing(group: Optional[UserGroup]) -> bool:
        """Group pool billing is opt-in; default / missing flag means personal-only."""
        if group is None:
            return False
        return bool(getattr(group, "allow_group_credit_billing", False))

    @staticmethod
    def _attach_balance_snapshots(
        details: Optional[dict],
        *,
        user: Optional[User] = None,
        group: Optional[UserGroup] = None,
        db: Optional[Session] = None,
    ) -> dict:
        """Snapshot personal/group balances after a billing mutation for history UI."""
        payload = dict(details or {}) if isinstance(details, dict) else {}
        if user is not None:
            personal = int(user.credits or 0)
            payload["personal_balance_after"] = personal
            payload["balance_after"] = personal
        if group is not None:
            payload["group_id"] = payload.get("group_id") or group.id
            payload["group_balance_after"] = int(group.credits or 0)
        elif db is not None and payload.get("group_id"):
            gid = BillingService._to_int(payload.get("group_id"), 0)
            if gid > 0:
                g = db.query(UserGroup).filter(UserGroup.id == gid).first()
                if g is not None:
                    payload["group_balance_after"] = int(g.credits or 0)
        return payload

    @staticmethod
    def _reserve_wallet_split(details: Optional[dict], reserved_cost: int) -> Dict[str, int]:
        """Return how a reservation was split across group vs personal wallets."""
        payload = details if isinstance(details, dict) else {}
        billed_group = max(0, BillingService._to_int(payload.get("billed_group_credits", 0), 0))
        billed_personal = max(0, BillingService._to_int(payload.get("billed_personal_credits", 0), 0))
        reserved = max(0, int(reserved_cost or 0))
        if billed_group + billed_personal <= 0 and reserved > 0:
            # Legacy rows without split metadata: treat as personal-only.
            billed_personal = reserved
            billed_group = 0
        elif billed_group + billed_personal != reserved and reserved > 0:
            # Prefer recorded group share; put remainder on personal.
            billed_group = min(billed_group, reserved)
            billed_personal = max(0, reserved - billed_group)
        return {
            "billed_group_credits": billed_group,
            "billed_personal_credits": billed_personal,
        }

    @staticmethod
    def _settle_refund_split(
        *,
        refund: int,
        billed_group_credits: int,
        billed_personal_credits: int,
        actual_cost: int,
    ) -> Dict[str, int]:
        """
        Refund settle over-reserve using the same priority as reserve (group first).

        Final charge stays on group first, then personal; leftover reserved amounts
        are returned to their original wallets.
        """
        refund = max(0, int(refund or 0))
        billed_group = max(0, int(billed_group_credits or 0))
        billed_personal = max(0, int(billed_personal_credits or 0))
        actual = max(0, int(actual_cost or 0))

        group_final = min(actual, billed_group)
        personal_final = max(0, actual - group_final)
        refund_group = max(0, billed_group - group_final)
        refund_personal = max(0, billed_personal - personal_final)

        # Guard against rounding / legacy mismatch: distribute remainder by original priority.
        assigned = refund_group + refund_personal
        if assigned < refund:
            leftover = refund - assigned
            # Prefer returning leftover to group when any group was billed.
            if billed_group > 0:
                refund_group += leftover
            else:
                refund_personal += leftover
        elif assigned > refund:
            overflow = assigned - refund
            take_personal = min(overflow, refund_personal)
            refund_personal -= take_personal
            overflow -= take_personal
            refund_group = max(0, refund_group - overflow)

        return {
            "refund_group_credits": max(0, refund_group),
            "refund_personal_credits": max(0, refund_personal),
            "final_group_credits": max(0, group_final),
            "final_personal_credits": max(0, personal_final),
        }

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
    def _rule_extra_conditions(rule: Optional[SystemAPIBillingRule]) -> Dict[str, Any]:
        if not rule:
            return {}
        return BillingService._safe_json_dict(getattr(rule, "extra_conditions", {}))

    @staticmethod
    def _rule_has_matching_dimensions(rule: SystemAPIBillingRule) -> bool:
        fields = [
            "generation_mode", "input_format", "output_format", "has_audio",
            "input_tokens_min", "input_tokens_max", "output_tokens_min", "output_tokens_max",
            "total_tokens_min", "total_tokens_max", "image_count_min", "image_count_max",
            "width_min", "width_max", "height_min", "height_max", "pixels_min", "pixels_max",
            "duration_seconds_min", "duration_seconds_max", "fps_min", "fps_max",
        ]
        for field in fields:
            value = getattr(rule, field, None)
            if value is not None and str(value).strip() != "":
                return True
        return False

    @staticmethod
    def _rule_has_extra_match_constraints(rule: SystemAPIBillingRule) -> bool:
        """True when extra_conditions encode usage match filters (not pricing matrices)."""
        extra = BillingService._rule_extra_conditions(rule)
        if not extra:
            return False
        if extra.get("has_video_input") is not None:
            return True
        if extra.get("require_success_output") is True:
            return True
        required_keys = extra.get("required_keys")
        if isinstance(required_keys, list) and any(str(k or "").strip() for k in required_keys):
            return True
        for key in (
            "cache_hit_tokens_min",
            "cache_hit_tokens_max",
            "cache_miss_tokens_min",
            "cache_miss_tokens_max",
        ):
            if extra.get(key) is not None and str(extra.get(key)).strip() != "":
                return True
        if isinstance(extra.get("standard_values"), dict) and extra.get("standard_values"):
            return True
        for key in extra.keys():
            if str(key or "").strip().lower().startswith("standard."):
                return True
        return False

    @staticmethod
    def _rule_is_dimensional_matcher(rule: SystemAPIBillingRule) -> bool:
        """Dimensional / constrained override rules (not undimensioned base-tier pricing)."""
        if BillingService._is_base_billing_rule(rule):
            return False
        return bool(
            BillingService._rule_has_matching_dimensions(rule)
            or BillingService._rule_has_extra_match_constraints(rule)
        )

    @staticmethod
    def _is_base_billing_rule(rule: SystemAPIBillingRule) -> bool:
        extra = BillingService._rule_extra_conditions(rule)
        if str(extra.get("rule_kind", "")).strip().lower() == BillingService.BASE_BILLING_RULE_KIND:
            return True
        if int(getattr(rule, "priority", 0) or 0) <= BillingService.BASE_BILLING_RULE_PRIORITY and not BillingService._rule_has_matching_dimensions(rule):
            return True
        return False

    @staticmethod
    def _pick_undimensioned_base_fallback(
        rows: List[SystemAPIBillingRule],
        *,
        prefer_token_unit: bool = False,
        prefer_per_second_unit: bool = False,
    ) -> Optional[SystemAPIBillingRule]:
        """Prefer explicit base_pricing; else undimensioned active rule (legacy orphans)."""
        if not rows:
            return None
        base_rows = [row for row in rows if BillingService._is_base_billing_rule(row)]
        if base_rows:
            if prefer_token_unit:
                token_bases = [
                    row for row in base_rows
                    if str(getattr(row, "billing_unit_type", "") or "").strip().lower()
                    in BillingService.TOKEN_UNIT_TYPES
                ]
                if token_bases:
                    token_bases.sort(
                        key=lambda row: (
                            int(getattr(row, "priority", 0) or 0),
                            -int(getattr(row, "id", 0) or 0),
                        )
                    )
                    return token_bases[0]
            if prefer_per_second_unit:
                second_bases = [
                    row for row in base_rows
                    if str(getattr(row, "billing_unit_type", "") or "").strip().lower() == "per_second"
                ]
                if second_bases:
                    second_bases.sort(
                        key=lambda row: (
                            int(getattr(row, "priority", 0) or 0),
                            -int(getattr(row, "id", 0) or 0),
                        )
                    )
                    return second_bases[0]
            base_rows.sort(
                key=lambda row: (
                    int(getattr(row, "priority", 0) or 0),
                    -int(getattr(row, "id", 0) or 0),
                )
            )
            return base_rows[0]
        undim = [
            row for row in rows
            if not BillingService._rule_is_dimensional_matcher(row)
        ]
        if not undim:
            return None
        undim.sort(
            key=lambda row: (
                int(getattr(row, "priority", 0) or 0),
                -int(getattr(row, "id", 0) or 0),
            )
        )
        return undim[0]

    @staticmethod
    def _billing_from_rule(rule: Optional[SystemAPIBillingRule]) -> Dict[str, Any]:
        if not rule:
            return {"unit_type": "per_call", "cost": 0, "cost_input": 0, "cost_output": 0}
        from app.services.billing_pricing import apply_odds_to_credits, normalize_charge_multiplier, resolve_rule_base_credits
        resolved = resolve_rule_base_credits(rule)
        charge_multiplier = normalize_charge_multiplier(getattr(rule, "charge_multiplier", None), default=2.0)
        return BillingService._normalize_api_pricing_config({
            "unit_type": resolved.get("unit_type") or "per_call",
            "cost": apply_odds_to_credits(resolved.get("cost") or 0, charge_multiplier),
            "cost_input": apply_odds_to_credits(resolved.get("cost_input") or 0, charge_multiplier),
            "cost_output": apply_odds_to_credits(resolved.get("cost_output") or 0, charge_multiplier),
        })

    @staticmethod
    def _get_base_billing_rule(
        db: Session,
        system_api_id: int,
        *,
        prefer_token_unit: bool = False,
        prefer_per_second_unit: bool = False,
    ) -> Optional[SystemAPIBillingRule]:
        rows = db.query(SystemAPIBillingRule).filter(
            SystemAPIBillingRule.system_api_id == system_api_id,
            SystemAPIBillingRule.is_active == True,
        ).order_by(SystemAPIBillingRule.id.desc()).all()
        return BillingService._pick_undimensioned_base_fallback(
            rows,
            prefer_token_unit=prefer_token_unit,
            prefer_per_second_unit=prefer_per_second_unit,
        )

    @staticmethod
    def _categories_for_mode(mode: Optional[str]) -> List[str]:
        normalized = str(mode or "").strip().lower()
        if not normalized:
            return []
        if normalized == "video":
            return ["Video"]
        if normalized == "image":
            return ["Image"]
        if normalized == "text":
            return ["LLM", "Vision", "Tools", "Voice", "Music"]
        return []

    @staticmethod
    def _normalize_model_identity(model: Any) -> str:
        text = str(model or "").strip().lower()
        if not text:
            return ""
        text = text.replace("_", "-").replace(".", "-")
        text = re.sub(r"\s+", "", text)
        text = re.sub(r"-+", "-", text)
        return text.strip("-")

    @staticmethod
    def _query_active_rules_by_identity(
        db: Session,
        provider: str,
        model: str,
        mode: Optional[str],
    ) -> List[SystemAPIBillingRule]:
        provider_text = str(provider or "").strip()
        model_text = str(model or "").strip()
        normalized_model_text = BillingService._normalize_model_identity(model_text)
        if not provider_text or not normalized_model_text:
            return []

        query = db.query(SystemAPIBillingRule, SystemAPISetting.model).join(
            SystemAPISetting,
            SystemAPIBillingRule.system_api_id == SystemAPISetting.id,
        ).filter(
            SystemAPIBillingRule.is_active == True,
            SystemAPISetting.provider == provider_text,
        )

        categories = BillingService._categories_for_mode(mode)
        if categories:
            query = query.filter(SystemAPISetting.category.in_(categories))

        rows = query.order_by(SystemAPIBillingRule.priority.desc(), SystemAPIBillingRule.id.desc()).all()
        matched_rows: List[SystemAPIBillingRule] = []
        for rule_row, setting_model in rows:
            if BillingService._normalize_model_identity(setting_model) != normalized_model_text:
                continue
            matched_rows.append(rule_row)
        return matched_rows

    @staticmethod
    def _get_base_billing_rule_by_identity(
        db: Session,
        provider: str,
        model: str,
        mode: Optional[str],
        *,
        prefer_token_unit: bool = False,
        prefer_per_second_unit: bool = False,
    ) -> Optional[SystemAPIBillingRule]:
        rows = BillingService._query_active_rules_by_identity(db, provider, model, mode)
        return BillingService._pick_undimensioned_base_fallback(
            rows,
            prefer_token_unit=prefer_token_unit,
            prefer_per_second_unit=prefer_per_second_unit,
        )

    @staticmethod
    def _task_type_to_category(task_type: str) -> str:
        normalized = str(task_type or "").strip().lower()
        if normalized == "image_gen":
            return "Image"
        if normalized == "video_gen":
            return "Video"
        if normalized == "voice_gen":
            return "Voice"
        if normalized == "music_gen":
            return "Music"
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
        row = BillingService._system_setting_query(db).filter(
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
    def _normalize_content_fallback_pricing(raw_config: Dict[str, Any]) -> Dict[str, Any]:
        source = raw_config if isinstance(raw_config, dict) else {}
        strategy = str(source.get("strategy", "manual") or "manual").strip().lower()
        if strategy not in BillingService.CONTENT_FALLBACK_STRATEGIES:
            strategy = "manual"

        out_map: Dict[str, Dict[str, Any]] = {}
        raw_map = source.get("content_pricing") if isinstance(source.get("content_pricing"), dict) else {}
        for content_type in BillingService.CONTENT_FALLBACK_CONTENT_TYPES:
            candidate = raw_map.get(content_type)
            if not isinstance(candidate, dict):
                candidate = {}
            default_unit = "per_second" if content_type == "video" else "per_call"
            out_map[content_type] = BillingService._normalize_api_pricing_config({
                "unit_type": candidate.get("unit_type", default_unit),
                "cost": candidate.get("cost", 0),
                "cost_input": candidate.get("cost_input", 0),
                "cost_output": candidate.get("cost_output", 0),
            })

        return {
            "enabled": bool(source.get("enabled", False)),
            "strategy": strategy,
            "content_pricing": out_map,
        }

    @staticmethod
    def get_content_fallback_pricing(db: Session) -> Dict[str, Any]:
        row = BillingService._system_setting_query(db).filter(
            SystemAPISetting.category == "System_Payment",
            SystemAPISetting.provider == BillingService.DEFAULT_API_PRICING_PROVIDER,
            SystemAPISetting.model == BillingService.DEFAULT_API_PRICING_MODEL,
        ).order_by(SystemAPISetting.id.desc()).first()

        if not row:
            return BillingService._normalize_content_fallback_pricing({})

        cfg = BillingService._safe_json_dict(row.config)
        raw = cfg.get("content_fallback_pricing") if isinstance(cfg.get("content_fallback_pricing"), dict) else {}
        return BillingService._normalize_content_fallback_pricing(raw)

    @staticmethod
    def set_content_fallback_pricing(db: Session, fallback_pricing: Dict[str, Any]) -> Dict[str, Any]:
        normalized = BillingService._normalize_content_fallback_pricing(fallback_pricing)
        row = BillingService._system_setting_query(db).filter(
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
                config={
                    "default_api_pricing": BillingService.get_recommended_default_api_pricing_map(),
                    "content_fallback_pricing": normalized,
                },
                is_active=True,
            )
            db.add(row)
            db.commit()
            return normalized

        cfg = BillingService._safe_json_dict(row.config)
        cfg["content_fallback_pricing"] = normalized
        row.config = cfg
        db.commit()
        return normalized

    @staticmethod
    def _extract_api_pricing_from_setting_config(config_value: Any) -> Dict[str, Any]:
        cfg = BillingService._safe_json_dict(config_value)
        api_pricing = cfg.get("api_pricing") if isinstance(cfg.get("api_pricing"), dict) else {}
        if isinstance(api_pricing, dict) and api_pricing:
            return BillingService._normalize_api_pricing_config(api_pricing)
        return BillingService._normalize_api_pricing_config({
            "unit_type": cfg.get("billing_unit_type", "per_call"),
            "cost": cfg.get("billing_cost", 0),
            "cost_input": cfg.get("billing_cost_input", 0),
            "cost_output": cfg.get("billing_cost_output", 0),
        })

    @staticmethod
    def _pricing_score(config: Dict[str, Any]) -> int:
        normalized = BillingService._normalize_api_pricing_config(config)
        return int(max(
            normalized.get("cost", 0),
            normalized.get("cost_input", 0),
            normalized.get("cost_output", 0),
        ))

    @staticmethod
    def _collect_content_mode_pricing_candidates(db: Session, mode: str) -> List[Dict[str, Any]]:
        categories = BillingService.CONTENT_FALLBACK_CATEGORY_MAP.get(mode, [])
        if not categories:
            return []

        default_rows_map = list_task_default_system_settings(db)
        rows: List[SystemAPISetting] = []
        for cat in categories:
            normalized = str(cat or "").strip().upper()
            row = default_rows_map.get(normalized)
            if row:
                rows.append(row)

        out: List[Dict[str, Any]] = []
        for row in rows:
            base_rule = BillingService._get_base_billing_rule(db, int(row.id))
            if base_rule:
                pricing = BillingService._billing_from_rule(base_rule)
            else:
                pricing = BillingService._extract_api_pricing_from_setting_config(row.config)
            if BillingService._has_effective_api_pricing(pricing):
                out.append(pricing)
        return out

    @staticmethod
    def _aggregate_content_mode_pricing(candidates: List[Dict[str, Any]], strategy: str) -> Dict[str, Any]:
        if not candidates:
            return BillingService._normalize_api_pricing_config({})

        if strategy == "highest":
            selected = max(candidates, key=lambda c: BillingService._pricing_score(c))
            return BillingService._normalize_api_pricing_config(selected)

        # average strategy
        unit_counts: Dict[str, int] = {}
        for candidate in candidates:
            unit = str(candidate.get("unit_type", "per_call") or "per_call").strip()
            unit_counts[unit] = unit_counts.get(unit, 0) + 1

        dominant_unit = max(unit_counts.items(), key=lambda item: (item[1], item[0]))[0]
        filtered = [
            BillingService._normalize_api_pricing_config(c)
            for c in candidates
            if str(c.get("unit_type", "per_call") or "per_call").strip() == dominant_unit
        ]
        if not filtered:
            filtered = [BillingService._normalize_api_pricing_config(c) for c in candidates]

        count = float(len(filtered))
        return BillingService._normalize_api_pricing_config({
            "unit_type": dominant_unit,
            "cost": int(round(sum(c.get("cost", 0) for c in filtered) / count)),
            "cost_input": int(round(sum(c.get("cost_input", 0) for c in filtered) / count)),
            "cost_output": int(round(sum(c.get("cost_output", 0) for c in filtered) / count)),
        })

    @staticmethod
    def _resolve_content_fallback_pricing(db: Session, task_type: str, fallback_config: Dict[str, Any]) -> Dict[str, Any]:
        normalized = BillingService._normalize_content_fallback_pricing(fallback_config)
        if not normalized.get("enabled", False):
            return BillingService._normalize_api_pricing_config({})

        mode = BillingService._task_type_to_mode(task_type)
        if mode not in BillingService.CONTENT_FALLBACK_CONTENT_TYPES:
            mode = "text"

        strategy = str(normalized.get("strategy", "manual") or "manual").strip().lower()
        manual_map = normalized.get("content_pricing") if isinstance(normalized.get("content_pricing"), dict) else {}
        manual_cfg = BillingService._normalize_api_pricing_config(manual_map.get(mode) if isinstance(manual_map.get(mode), dict) else {})

        if strategy == "manual":
            return manual_cfg

        candidates = BillingService._collect_content_mode_pricing_candidates(db, mode)
        derived = BillingService._aggregate_content_mode_pricing(candidates, strategy)
        if BillingService._has_effective_api_pricing(derived):
            return derived
        return manual_cfg

    @staticmethod
    def set_default_api_pricing_map(db: Session, pricing_map: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        normalized = BillingService._normalize_default_api_pricing_map(pricing_map)

        row = BillingService._system_setting_query(db).filter(
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
                config={
                    "default_api_pricing": normalized,
                    "content_fallback_pricing": BillingService._normalize_content_fallback_pricing({}),
                },
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
        content_fallback = BillingService.get_content_fallback_pricing(db)
        content_cfg = BillingService._resolve_content_fallback_pricing(db, task_type, content_fallback)
        if BillingService._has_effective_api_pricing(content_cfg):
            return content_cfg

        pricing_map = BillingService.get_default_api_pricing_map(db)
        category = BillingService._task_type_to_category(task_type)
        default_cfg = pricing_map.get(
            category,
            pricing_map.get("Tools") or BillingService.DEFAULT_API_PRICING_BY_CATEGORY["Tools"],
        )
        return BillingService._normalize_api_pricing_config(default_cfg)

    @staticmethod
    def get_feature_pricing_map(db: Session) -> Dict[str, int]:
        row = BillingService._system_setting_query(db).filter(
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

        row = BillingService._system_setting_query(db).filter(
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


    ITEM_TO_FUNCTION_NAME = {
        "generate_subjects": "generate_subjects",
        "generate_subjects_t2i": "generate_subjects_t2i",
        "generate_subjects_i2i": "generate_subjects_i2i",
        "generate_cover": "generate_cover",
        "generate_shot_images": "generate_shot_images",
        "generate_videos": "generate_videos",
        "generate_entity_reference_audio": "generate_entity_reference_audio",
        "generate_entity_reference_audio_audio": "generate_entity_reference_audio_audio",
        "generate_entity_reference_audio_video": "generate_entity_reference_audio_video",
        "script_analysis": "script_analysis",
        "scene_analysis": "script_analysis",
        "ai_assistant": "ai_assistant",
        "ai_shot": "ai_shot",
        "generate_shots": "ai_shot",
    }

    @staticmethod
    def _resolve_billing_function_name(details: Optional[dict] = None, system_api_id: Optional[int] = None, db: Session = None) -> Optional[str]:
        payload = dict(details or {})
        for key in ("function_name", "billing_function_name", "function"):
            text = str(payload.get(key) or "").strip()
            if text:
                return text
        for key in ("billing_feature", "feature", "item"):
            raw = str(payload.get(key) or "").strip()
            if not raw:
                continue
            mapped = BillingService.ITEM_TO_FUNCTION_NAME.get(raw) or BillingService.ITEM_TO_FUNCTION_NAME.get(raw.lower())
            if mapped:
                return mapped
            if raw in BillingService.ITEM_TO_FUNCTION_NAME.values():
                return raw
        sid = BillingService._to_int(system_api_id or payload.get("system_api_id"), 0)
        if sid > 0 and db is not None:
            try:
                rows = db.query(FunctionAPIConfig).all()
            except Exception:
                rows = []
            matches = []
            for row in rows:
                for item in (row.api_settings or []):
                    if not isinstance(item, dict):
                        continue
                    if BillingService._to_int(item.get("system_api_id"), 0) == sid:
                        name = str(getattr(row, "function_name", "") or "").strip()
                        if name:
                            matches.append(name)
                        break
            # Only auto-bind when uniquely mapped to one function.
            uniq = sorted(set(matches))
            if len(uniq) == 1:
                return uniq[0]
        return None

    @staticmethod
    def _resolve_function_billing_adjustment(db: Session, details: Optional[dict] = None, system_api_id: Optional[int] = None) -> Dict[str, Any]:
        function_name = BillingService._resolve_billing_function_name(details, system_api_id=system_api_id, db=db)
        multiplier = 1.0
        add_credits = 0
        source = "default"
        if function_name:
            try:
                row = db.query(FunctionAPIConfig).filter(FunctionAPIConfig.function_name == function_name).first()
            except Exception:
                row = None
            if row is not None:
                source = "function_api_config"
                try:
                    raw_mult = getattr(row, "billing_multiplier", None)
                    if raw_mult is None or raw_mult == "":
                        multiplier = 1.0
                    else:
                        multiplier = float(raw_mult)
                        if not math.isfinite(multiplier) or multiplier < 0:
                            multiplier = 1.0
                except Exception:
                    multiplier = 1.0
                add_credits = max(0, BillingService._to_int(getattr(row, "billing_add_credits", 0), 0))
        return {
            "function_name": function_name,
            "function_multiplier": float(multiplier),
            "function_add_credits": int(add_credits),
            "source": source,
        }

    @staticmethod
    def _resolve_api_pricing_config(db: Session, task_type: str, provider: str = None, model: str = None) -> Dict[str, Any]:
        provider_text = str(provider or "").strip()
        model_text = str(model or "").strip()
        category = BillingService._task_type_to_category(task_type)
        default_pricing = BillingService._default_api_pricing_config(db, task_type)

        query = BillingService._system_setting_query(db).filter(
            SystemAPISetting.category == category,
            SystemAPISetting.provider == provider_text,
        )
        if model_text:
            query = query.filter(SystemAPISetting.model == model_text)
        row = query.order_by(SystemAPISetting.id.desc()).first()

        if not row and provider_text and model_text:
            row = BillingService._system_setting_query(db).filter(
                SystemAPISetting.category == category,
                SystemAPISetting.provider == provider_text,
                SystemAPISetting.model == None,
            ).order_by(SystemAPISetting.id.desc()).first()

        if not row and provider_text:
            query_any_category = BillingService._system_setting_query(db).filter(
                SystemAPISetting.provider == provider_text,
            )
            if model_text:
                query_any_category = query_any_category.filter(SystemAPISetting.model == model_text)
            else:
                query_any_category = query_any_category.filter(SystemAPISetting.model == None)
            row = query_any_category.order_by(SystemAPISetting.id.desc()).first()

        if not row:
            return default_pricing

        base_rule = BillingService._get_base_billing_rule(db, int(row.id))
        if base_rule:
            resolved = BillingService._billing_from_rule(base_rule)
            if BillingService._has_effective_api_pricing(resolved):
                return resolved

        return default_pricing

    @staticmethod
    def _estimate_api_cost_from_config(config: Dict[str, Any], details: dict = None, return_float: bool = False) -> float:
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

            # Backward-compatibility guard:
            # legacy data may store unit_type=per_token while costs are actually per-million-token rates.
            # By default, treat per_token as per_million_tokens unless explicitly overridden.
            divisor = 1_000_000.0 if unit_type == 'per_million_tokens' else 1_000.0 if unit_type == 'per_1k_tokens' else 1.0
            if unit_type == 'per_token':
                raw_divisor = config.get("per_token_divisor")
                if raw_divisor is None:
                    raw_divisor = payload.get("per_token_divisor")
                parsed_divisor = BillingService._safe_float(raw_divisor, 1_000_000.0)
                divisor = parsed_divisor if parsed_divisor > 0 else 1_000_000.0

            from app.services.billing_pricing import (
                is_video_token_usage,
                resolve_video_token_unit_rate,
            )
            if is_video_token_usage(payload):
                tokens = max(total_tokens, output_tokens, input_tokens)
                if tokens <= 0:
                    estimate = payload.get("video_token_estimate")
                    if isinstance(estimate, dict):
                        tokens = BillingService._to_int(estimate.get("tokens", 0), 0)
                has_video_input = bool(payload.get("has_video_input"))
                if not has_video_input and isinstance(payload.get("video_token_estimate"), dict):
                    has_video_input = bool(payload["video_token_estimate"].get("has_video_input"))
                selected = resolve_video_token_unit_rate(
                    cost=float(base_cost),
                    cost_input=float(cost_input),
                    cost_output=float(cost_output),
                    has_video_input=has_video_input,
                )
                token_cost = (float(tokens) * float(selected["rate"])) / divisor
            else:
                token_cost = ((float(input_tokens) * float(cost_input)) + (float(output_tokens) * float(cost_output))) / divisor
                if cost_input == 0 and cost_output == 0 and base_cost > 0:
                    token_cost = (float(max(total_tokens, input_tokens + output_tokens)) * float(base_cost)) / divisor
            if return_float: return float(max(0.0, token_cost))
            
            import math
            return max(0, int(math.ceil(token_cost))) if token_cost > 0 else 0

        quantity = float(BillingService._safe_non_negative_float(payload.get("billing_quantity", 1), 1.0))
        if unit_type == 'per_call':
            success_output_count = BillingService._to_int(payload.get("success_output_count", payload.get("successful_outputs", 0)), 0)
            if success_output_count > 0:
                quantity = float(success_output_count)
            cost_val = float(base_cost) * float(max(quantity, 1.0))
            if return_float: return cost_val
            
            import math
            return max(0, int(math.ceil(cost_val))) if cost_val > 0 else 0

        if unit_type in {"per_second", "per_minute"}:
            # Includes KIE Seedance / SparkVideo resolution matrices (CNY/s or KIE/s).
            from app.services.billing_pricing import estimate_base_amount_by_unit
            amount = float(
                estimate_base_amount_by_unit(
                    {
                        "unit_type": unit_type,
                        "cost": base_cost,
                        "cost_input": cost_input,
                        "cost_output": cost_output,
                        "video_second_cny_resolution_rates": (
                            payload.get("video_second_cny_resolution_rates")
                            or config.get("video_second_cny_resolution_rates")
                        ),
                        "video_second_resolution_rates": (
                            payload.get("video_second_resolution_rates")
                            or config.get("video_second_resolution_rates")
                        ),
                        "video_second_min_billable_by_output": (
                            payload.get("video_second_min_billable_by_output")
                            or config.get("video_second_min_billable_by_output")
                        ),
                    },
                    payload,
                )
            )
            if return_float:
                return float(max(0.0, amount))
            import math
            return max(0, int(math.ceil(amount))) if amount > 0 else 0

        cost_val = float(base_cost) * float(quantity)
        if return_float: return cost_val
        
        import math
        return max(0, int(math.ceil(cost_val))) if cost_val > 0 else 0

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return float(default)
            return float(value)
        except Exception:
            return float(default)

    @staticmethod
    def _safe_non_negative_float(value: Any, default: float = 0.0) -> float:
        parsed = BillingService._safe_float(value, default)
        return parsed if parsed >= 0 else float(default)

    @staticmethod
    def _to_lower_text(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _normalize_bool_value(value: Any) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        raw = str(value or "").strip().lower()
        if not raw:
            return None
        if raw in {"1", "true", "yes", "y", "on", "supported"}:
            return True
        if raw in {"0", "false", "no", "n", "off", "unsupported"}:
            return False
        return None

    @staticmethod
    def _normalize_kie_standard_value(dimension: str, raw_value: Any) -> Optional[str]:
        dim = str(dimension or "").strip().upper()
        value = "" if raw_value is None else str(raw_value).strip()
        if not dim or not value:
            return None

        lower = value.lower()
        if dim == "ASPECT_RATIO":
            if lower == "portrait":
                return "9:16"
            if lower == "landscape":
                return "16:9"
            if lower == "auto":
                return "AUTO"
            return value

        if dim == "RESOLUTION_TIER":
            mapping = {
                "1k": "K1",
                "2k": "K2",
                "4k": "K4",
                "480p": "P480",
                "512p": "P512",
                "580p": "P580",
                "720p": "P720",
                "768p": "P768",
                "1080p": "P1080",
            }
            return mapping.get(lower.replace(" ", ""), value.upper())

        if dim == "DURATION_SECONDS":
            try:
                num = float(value)
                if abs(num - int(num)) < 1e-9:
                    return str(int(num))
                return str(num)
            except Exception:
                return value

        if dim == "MODE":
            mode_map = {
                "std": "STANDARD",
                "standard": "STANDARD",
                "pro": "PRO",
                "fast": "FAST",
                "turbo": "TURBO",
                "master": "MASTER",
                "fun": "FUN",
                "normal": "NORMAL",
                "spicy": "SPICY",
            }
            return mode_map.get(lower, value.upper())

        if dim == "QUALITY_LEVEL":
            quality_map = {
                "basic": "BASIC",
                "medium": "MEDIUM",
                "high": "HIGH",
                "std": "STANDARD",
                "standard": "STANDARD",
            }
            return quality_map.get(lower, value.upper())

        if dim in {"OUTPUT_FORMAT", "STYLE", "REASONING_EFFORT", "CHARACTER_ORIENTATION", "IMAGE_SIZE_CLASS"}:
            return value.upper()

        if dim in {"SOUND_SUPPORTED", "MULTI_SHOTS_SUPPORTED"}:
            b = BillingService._normalize_bool_value(value)
            if b is None:
                return None
            return "TRUE" if b else "FALSE"

        return value

    @staticmethod
    def _get_kie_standard_forward_mapping(
        db: Session,
        model_key: str,
        standard_dimension: str,
        source_field: str,
        source_enum_value: Any,
    ) -> Optional[Dict[str, Any]]:
        model = str(model_key or "").strip()
        dim = str(standard_dimension or "").strip().upper()
        field = str(source_field or "").strip()
        value = "" if source_enum_value is None else str(source_enum_value).strip()
        if not dim or not field or not value:
            return None

        row = db.execute(
            text(
                """
                SELECT standard_value, standard_dimension, source_field, source_enum_value, confidence
                FROM kie_system_data_standard_mappings
                WHERE provider = 'kie'
                  AND is_active = 1
                  AND standard_dimension = :dim
                  AND lower(coalesce(source_field, '')) = lower(:field)
                  AND lower(trim(coalesce(source_enum_value, ''))) = lower(trim(:val))
                  AND (
                    lower(coalesce(model_key_inferred, '')) = lower(:model)
                    OR coalesce(model_key_inferred, '') = ''
                  )
                ORDER BY CASE
                    WHEN lower(coalesce(model_key_inferred, '')) = lower(:model) THEN 0
                    ELSE 1
                  END,
                  CASE upper(coalesce(confidence, ''))
                    WHEN 'HIGH' THEN 0
                    WHEN 'MEDIUM' THEN 1
                    WHEN 'LOW' THEN 2
                    ELSE 3
                  END,
                  id ASC
                LIMIT 1
                """
            ),
            {
                "model": model,
                "dim": dim,
                "field": field,
                "val": value,
            },
        ).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def _resolve_kie_standard_usage(
        db: Session,
        model_key: str,
        usage: Dict[str, Any],
        details: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        payload = dict(details or {})
        out_values: Dict[str, str] = {}
        out_trace: Dict[str, Any] = {}

        preferred: Dict[str, List[str]] = {
            "ASPECT_RATIO": ["paths.post.input.aspect_ratio", "paths.post.input.size"],
            "RESOLUTION_TIER": ["paths.post.input.resolution", "paths.post.input.image_resolution"],
            "DURATION_SECONDS": ["paths.post.input.duration", "paths.post.input.n_frames"],
            "MODE": ["paths.post.input.mode"],
            "QUALITY_LEVEL": ["paths.post.input.quality"],
            "OUTPUT_FORMAT": ["paths.post.input.output_format"],
            "IMAGE_SIZE_CLASS": ["paths.post.input.image_size"],
            "SOUND_SUPPORTED": ["sound"],
            "MULTI_SHOTS_SUPPORTED": ["multi_shots"],
        }

        raw_candidates: Dict[str, List[Any]] = {
            "ASPECT_RATIO": [payload.get("aspect_ratio"), payload.get("size")],
            "RESOLUTION_TIER": [payload.get("resolution"), payload.get("image_resolution")],
            "DURATION_SECONDS": [payload.get("duration_seconds"), payload.get("duration"), usage.get("duration_seconds")],
            "MODE": [payload.get("mode")],
            "QUALITY_LEVEL": [payload.get("quality")],
            "OUTPUT_FORMAT": [payload.get("output_format"), payload.get("outputFormat"), usage.get("output_format")],
            "IMAGE_SIZE_CLASS": [payload.get("image_size")],
            "SOUND_SUPPORTED": [payload.get("sound"), payload.get("has_audio"), usage.get("has_audio")],
            "MULTI_SHOTS_SUPPORTED": [payload.get("multi_shots")],
        }

        for dim, candidates in raw_candidates.items():
            picked = None
            source_field = None
            source_value = None

            for raw in candidates:
                raw_text = "" if raw is None else str(raw).strip()
                if not raw_text:
                    continue
                for field in preferred.get(dim, []):
                    mapped = BillingService._get_kie_standard_forward_mapping(
                        db=db,
                        model_key=model_key,
                        standard_dimension=dim,
                        source_field=field,
                        source_enum_value=raw_text,
                    )
                    if not mapped:
                        continue
                    mapped_val = str(mapped.get("standard_value") or "").strip()
                    if not mapped_val:
                        continue
                    picked = mapped_val
                    source_field = str(mapped.get("source_field") or field)
                    source_value = str(mapped.get("source_enum_value") or raw_text)
                    break
                if picked:
                    break

            if not picked:
                for raw in candidates:
                    norm_val = BillingService._normalize_kie_standard_value(dim, raw)
                    if norm_val:
                        picked = norm_val
                        source_value = str(raw)
                        break

            if not picked:
                continue

            out_values[dim] = picked
            out_trace[dim] = {
                "standard_value": picked,
                "source_field": source_field,
                "source_value": source_value,
            }

        return {
            "standard_values": out_values,
            "standard_trace": out_trace,
        }

    @staticmethod
    def _resolve_system_api_row(db: Session, task_type: str, provider: str = None, model: str = None) -> Optional[SystemAPISetting]:
        provider_text = str(provider or "").strip()
        model_text = str(model or "").strip()
        category = BillingService._task_type_to_category(task_type)

        query = BillingService._system_setting_query(db).filter(
            SystemAPISetting.category == category,
            SystemAPISetting.provider == provider_text,
        )
        if model_text:
            query = query.filter(SystemAPISetting.model == model_text)
        row = query.order_by(SystemAPISetting.id.desc()).first()

        if not row and provider_text and model_text:
            row = BillingService._system_setting_query(db).filter(
                SystemAPISetting.category == category,
                SystemAPISetting.provider == provider_text,
                SystemAPISetting.model == None,
            ).order_by(SystemAPISetting.id.desc()).first()

        if not row and provider_text:
            query_any_category = BillingService._system_setting_query(db).filter(SystemAPISetting.provider == provider_text)
            if model_text:
                query_any_category = query_any_category.filter(SystemAPISetting.model == model_text)
            row = query_any_category.order_by(SystemAPISetting.id.desc()).first()
        return row


    @staticmethod
    def _extract_provider_task_ref(*payloads: Any) -> Dict[str, str]:
        """Pull provider taskId / query endpoint from settle details or nested provider payloads."""
        task_id = ""
        query_endpoint = ""

        def _scan(obj: Any, *, depth: int = 0) -> None:
            nonlocal task_id, query_endpoint
            if depth > 3 or not isinstance(obj, dict):
                return
            if not task_id:
                for key in ("provider_task_id", "task_id", "taskId", "job_task_id"):
                    val = str(obj.get(key) or "").strip()
                    if val:
                        task_id = val
                        break
            if not query_endpoint:
                for key in ("query_endpoint", "queryEndpoint"):
                    val = str(obj.get(key) or "").strip()
                    if val:
                        query_endpoint = val
                        break
            if task_id and query_endpoint:
                return
            for nest_key in ("provider_usage", "raw", "submit_raw", "metadata", "data", "output"):
                nested = obj.get(nest_key)
                if isinstance(nested, dict):
                    _scan(nested, depth=depth + 1)
                    if task_id and query_endpoint:
                        return

        for payload in payloads:
            _scan(payload)
            if task_id and query_endpoint:
                break

        out: Dict[str, str] = {}
        if task_id:
            out["provider_task_id"] = task_id
            out["task_id"] = task_id
            out["taskId"] = task_id
        if query_endpoint:
            out["query_endpoint"] = query_endpoint
        return out

    @staticmethod
    def ensure_provider_task_ids(details: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Normalize provider taskId fields onto a settle/deduct details dict."""
        payload = dict(details or {}) if isinstance(details, dict) else {}
        ref = BillingService._extract_provider_task_ref(payload)
        if ref:
            payload.update(ref)
        return payload

    @staticmethod
    def attach_provider_task_id_to_reservation(
        db: Session,
        reservation_tx_id: int,
        task_id: str,
        *,
        query_endpoint: Optional[str] = None,
    ) -> bool:
        """Persist provider taskId onto an open reservation as soon as API submit returns it."""
        stable_task_id = str(task_id or "").strip()
        if not stable_task_id:
            return False
        try:
            tx_id = int(reservation_tx_id)
        except Exception:
            return False
        if tx_id <= 0:
            return False

        reservation_tx = db.query(TransactionHistory).filter(TransactionHistory.id == tx_id).first()
        if reservation_tx is None:
            return False

        details = dict(reservation_tx.details or {}) if isinstance(reservation_tx.details, dict) else {}
        status = str(details.get("status") or "").strip().upper()
        changed = False
        for key in ("provider_task_id", "task_id", "taskId"):
            if str(details.get(key) or "").strip() != stable_task_id:
                details[key] = stable_task_id
                changed = True
        qe = str(query_endpoint or "").strip()
        if qe and str(details.get("query_endpoint") or "").strip() != qe:
            details["query_endpoint"] = qe
            changed = True
        if changed:
            reservation_tx.details = details
            db.add(reservation_tx)

        # Also stamp the latest RESERVED action usage_metadata when still open.
        action = (
            db.query(TransactionAction)
            .filter(TransactionAction.reservation_tx_id == tx_id)
            .order_by(TransactionAction.id.desc())
            .first()
        )
        if action is not None and str(getattr(action, "stage", "") or "").upper() in {"RESERVED", "RESERVE", ""}:
            usage = dict(action.usage_metadata or {}) if isinstance(action.usage_metadata, dict) else {}
            usage_changed = False
            for key in ("provider_task_id", "task_id", "taskId"):
                if str(usage.get(key) or "").strip() != stable_task_id:
                    usage[key] = stable_task_id
                    usage_changed = True
            if qe and str(usage.get("query_endpoint") or "").strip() != qe:
                usage["query_endpoint"] = qe
                usage_changed = True
            if usage_changed:
                action.usage_metadata = BillingService._slim_usage_metadata_for_storage(usage)
                db.add(action)
                changed = True

        if changed:
            db.commit()
        return changed

    @staticmethod
    def _extract_usage_metadata(details: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        payload = dict(details or {})

        input_tokens = BillingService._to_int(payload.get("input_tokens", payload.get("prompt_tokens", 0)), 0)
        output_tokens = BillingService._to_int(payload.get("output_tokens", payload.get("completion_tokens", 0)), 0)
        total_tokens = BillingService._to_int(payload.get("total_tokens", input_tokens + output_tokens), 0)
        cache_hit_tokens = BillingService._to_int(payload.get("cache_hit_tokens", payload.get("cached_tokens", 0)), 0)
        cache_miss_tokens = BillingService._to_int(payload.get("cache_miss_tokens", 0), 0)

        if cache_hit_tokens > 0 and cache_miss_tokens == 0:
            if input_tokens > cache_hit_tokens:
                cache_miss_tokens = input_tokens - cache_hit_tokens
            elif total_tokens > cache_hit_tokens:
                cache_miss_tokens = max(0, total_tokens - cache_hit_tokens - output_tokens)

        width = BillingService._to_int(payload.get("width", payload.get("output_width", 0)), 0)
        height = BillingService._to_int(payload.get("height", payload.get("output_height", 0)), 0)
        image_count = BillingService._to_int(payload.get("image_count", payload.get("n", 1)), 1)
        success_output_count = BillingService._to_int(payload.get("success_output_count", payload.get("successful_outputs", 0)), 0)
        billing_quantity = BillingService._to_int(payload.get("billing_quantity", 0), 0)
        duration_seconds = BillingService._safe_non_negative_float(payload.get("duration_seconds", payload.get("duration", 0)), 0.0)
        fps = BillingService._safe_non_negative_float(payload.get("fps", 0), 0.0)

        generation_mode = BillingService._to_lower_text(payload.get("generation_mode", payload.get("mode", "")))
        input_format = BillingService._to_lower_text(payload.get("input_format", payload.get("input_type", "")))
        output_format = BillingService._to_lower_text(payload.get("output_format", payload.get("output_type", "")))

        has_audio_raw = payload.get("has_audio")
        has_audio = None if has_audio_raw is None else bool(has_audio_raw)
        draft_mode = bool(
            BillingService._normalize_bool_value(payload.get("draft_mode"))
            or BillingService._normalize_bool_value(payload.get("draft"))
        )
        use_prev_video = bool(
            BillingService._normalize_bool_value(payload.get("use_prev_video"))
            or BillingService._normalize_bool_value(payload.get("shot_continuation"))
            or BillingService._normalize_bool_value(payload.get("continuation_mode"))
        )

        # KIE callback actual consumption (data.creditsConsumed).
        kie_credits_consumed = 0.0
        try:
            from app.services.billing_pricing import resolve_provider_kie_credits

            kie_credits_consumed = float(resolve_provider_kie_credits(payload) or 0.0)
        except Exception:
            kie_credits_consumed = BillingService._safe_non_negative_float(
                payload.get("kie_credits_consumed")
                or payload.get("credits_consumed")
                or payload.get("creditsConsumed")
                , 0.0,
            )

        usage_out = {
            "input_tokens": max(0, input_tokens),
            "output_tokens": max(0, output_tokens),
            "total_tokens": max(0, total_tokens),
            "cache_hit_tokens": max(0, cache_hit_tokens),
            "cache_miss_tokens": max(0, cache_miss_tokens),
            "width": max(0, width),
            "height": max(0, height),
            "pixels": max(0, width * height) if width > 0 and height > 0 else 0,
            "image_count": max(1, image_count),
            "success_output_count": max(0, success_output_count),
            "billing_quantity": max(0, billing_quantity),
            "duration_seconds": max(0.0, duration_seconds),
            "fps": max(0.0, fps),
            "generation_mode": generation_mode,
            "input_format": input_format,
            "output_format": output_format,
            "has_audio": has_audio,
            "draft_mode": draft_mode,
            "use_prev_video": use_prev_video,
        }
        if kie_credits_consumed > 0:
            usage_out["kie_credits_consumed"] = float(kie_credits_consumed)
            usage_out["credits_consumed"] = float(kie_credits_consumed)
            usage_out["creditsConsumed"] = float(kie_credits_consumed)
            usage_out["billing_basis"] = str(payload.get("billing_basis") or "provider_kie_credits")
        if payload.get("provider_usage") and isinstance(payload.get("provider_usage"), dict):
            usage_out["provider_usage"] = dict(payload.get("provider_usage") or {})
        if payload.get("usage_source"):
            usage_out["usage_source"] = str(payload.get("usage_source") or "").strip()
        token_source = str(payload.get("token_source") or "").strip().lower()
        if not token_source and isinstance(usage_out.get("provider_usage"), dict):
            token_source = str(usage_out["provider_usage"].get("token_source") or "").strip().lower()
        if token_source:
            usage_out["token_source"] = token_source
        if payload.get("billing_basis") and not usage_out.get("billing_basis"):
            usage_out["billing_basis"] = str(payload.get("billing_basis") or "").strip()
        elif token_source == "api_usage" and total_tokens > 0 and not usage_out.get("billing_basis"):
            usage_out["billing_basis"] = "provider_tokens"
        # Keep OpenAI-style aliases for LLM provider usage audits (Grsai etc.).
        if input_tokens > 0:
            usage_out.setdefault("prompt_tokens", input_tokens)
        if output_tokens > 0:
            usage_out.setdefault("completion_tokens", output_tokens)
        if payload.get("resolution"):
            usage_out["resolution"] = payload.get("resolution")
        if payload.get("resolution_tier"):
            usage_out["resolution_tier"] = payload.get("resolution_tier")
        if payload.get("has_video_input") is not None:
            usage_out["has_video_input"] = bool(payload.get("has_video_input"))
        aspect_ratio = payload.get("aspect_ratio") or payload.get("aspectRatio")
        if aspect_ratio not in (None, ""):
            usage_out["aspect_ratio"] = str(aspect_ratio).strip()
        input_duration = BillingService._safe_non_negative_float(
            payload.get("input_duration_seconds", payload.get("input_duration", 0)),
            0.0,
        )
        if input_duration > 0:
            usage_out["input_duration_seconds"] = float(input_duration)
        # Persist provider task ids for later supplier usage reconcile.
        usage_out.update(
            BillingService._extract_provider_task_ref(
                payload,
                payload.get("provider_usage") if isinstance(payload.get("provider_usage"), dict) else None,
            )
        )
        return usage_out

    @staticmethod
    def _in_range_int(value: int, min_v: Any, max_v: Any) -> bool:
        if min_v is not None and int(value) < int(min_v):
            return False
        if max_v is not None and int(value) > int(max_v):
            return False
        return True

    @staticmethod
    def _in_range_float(value: float, min_v: Any, max_v: Any) -> bool:
        if min_v is not None and float(value) < float(min_v):
            return False
        if max_v is not None and float(value) > float(max_v):
            return False
        return True

    @staticmethod
    def _usage_key_present(usage: Dict[str, Any], key: str) -> bool:
        if key not in usage:
            return False
        value = usage.get(key)
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, bool):
            return True
        if key in BillingService._USAGE_POSITIVE_KEYS:
            return BillingService._safe_non_negative_float(value, 0.0) > 0
        return True

    @staticmethod
    def _compact_audit_payload(value: Any, *, drop_zero_keys: Optional[set] = None) -> Any:
        zero_keys = set(drop_zero_keys or set())

        def _walk(node: Any, key_name: Optional[str] = None) -> Any:
            if node is None:
                return None

            if isinstance(node, bool):
                return node

            if isinstance(node, (int, float)):
                if isinstance(node, float) and not math.isfinite(node):
                    return None
                if key_name in zero_keys and float(node) == 0.0:
                    return None
                return node

            if isinstance(node, str):
                text = node.strip()
                return text if text else None

            if isinstance(node, dict):
                out: Dict[str, Any] = {}
                for k, v in node.items():
                    key_text = str(k)
                    compacted = _walk(v, key_text)
                    if compacted is None:
                        continue
                    if isinstance(compacted, (dict, list)) and len(compacted) == 0:
                        continue
                    out[key_text] = compacted
                return out

            if isinstance(node, (list, tuple, set)):
                out_list = []
                for item in node:
                    compacted = _walk(item, key_name)
                    if compacted is None:
                        continue
                    if isinstance(compacted, (dict, list)) and len(compacted) == 0:
                        continue
                    out_list.append(compacted)
                return out_list

            return node

        compacted_root = _walk(value)
        if compacted_root is None:
            return {}
        return compacted_root

    @staticmethod
    def _compact_usage_metadata_for_audit(usage: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        payload = dict(usage or {})
        compacted = BillingService._compact_audit_payload(
            payload,
            drop_zero_keys=BillingService._AUDIT_USAGE_DROP_ZERO_KEYS,
        )
        return compacted if isinstance(compacted, dict) else {}

    # Heavy nested blobs belong in TransactionAction / process logs, not history UI details.
    _HISTORY_DETAILS_DROP_KEYS = {
        "billing_breakdown",
        "billing_trace",
        "billing_process",
        "usage_metadata",
        "provider_usage",
        "video_token_estimate",
        "selected_rule_detail",
        "matched_rule_details",
        "matched_rule_ids",
        "audit_summary",
        "system_api_ref",
        "reservation_billing_breakdown",
        "runtime_price_adjustments",
        "standard_resolution_trace",
        "function_billing",
        "supplier_pricing",
        "api_pricing_source_detail",
    }

    @staticmethod
    def _slim_pricing_program_for_history(
        *,
        breakdown: Optional[Dict[str, Any]] = None,
        selected_rule_detail: Optional[Dict[str, Any]] = None,
        existing: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        breakdown = breakdown if isinstance(breakdown, dict) else {}
        rule = selected_rule_detail if isinstance(selected_rule_detail, dict) else {}
        prev = existing if isinstance(existing, dict) else {}
        user_cost = breakdown.get("api_cost")
        if user_cost is None:
            user_cost = rule.get("computed_cost", prev.get("user_cost"))
        return BillingService._compact_audit_payload(
            {
                "base_cost": rule.get("computed_base_cost", prev.get("base_cost")),
                "charge_multiplier": rule.get("rule_charge_multiplier", prev.get("charge_multiplier")),
                "runtime_price_multiplier": rule.get("runtime_price_multiplier", prev.get("runtime_price_multiplier")),
                "user_cost": user_cost,
                "billing_unit_type": (
                    ((rule.get("pricing") or {}) if isinstance(rule.get("pricing"), dict) else {}).get("unit_type")
                    or prev.get("billing_unit_type")
                ),
                "base_credit_source": rule.get("base_credit_source", prev.get("base_credit_source")),
            }
        )

    @staticmethod
    def _promote_media_context_for_history(
        details: Optional[dict],
        *,
        usage: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """Lift video/image generation scalars onto history details before dropping nested trees."""
        payload = dict(details or {}) if isinstance(details, dict) else {}
        sources: List[Dict[str, Any]] = []
        if isinstance(usage, dict) and usage:
            sources.append(usage)
        nested_usage = payload.get("usage_metadata")
        if isinstance(nested_usage, dict) and nested_usage:
            sources.append(nested_usage)
        process = payload.get("billing_process")
        if isinstance(process, dict):
            process_usage = process.get("usage")
            if isinstance(process_usage, dict) and process_usage:
                sources.append(process_usage)
        sources.append(payload)

        def _first(*keys: str) -> Any:
            for source in sources:
                for key in keys:
                    value = source.get(key)
                    if value not in (None, ""):
                        return value
            return None

        duration = _first("duration_seconds", "duration")
        if duration not in (None, ""):
            payload["duration_seconds"] = duration
            payload["duration"] = duration

        input_duration = _first("input_duration_seconds", "input_duration", "reference_duration_seconds")
        if input_duration not in (None, ""):
            payload["input_duration_seconds"] = input_duration

        aspect_ratio = _first("aspect_ratio", "aspectRatio", "size")
        if aspect_ratio not in (None, ""):
            # Prefer explicit ratios like 16:9 over raw size enums when both exist.
            explicit = _first("aspect_ratio", "aspectRatio")
            payload["aspect_ratio"] = explicit if explicit not in (None, "") else aspect_ratio

        resolution = _first("resolution", "resolution_tier", "video_resolution", "image_resolution")
        if resolution not in (None, ""):
            payload["resolution"] = resolution
        resolution_tier = _first("resolution_tier")
        if resolution_tier not in (None, ""):
            payload["resolution_tier"] = resolution_tier

        for key in ("width", "height", "fps", "image_count", "generation_mode"):
            value = _first(key)
            if value not in (None, ""):
                payload[key] = value

        for key in ("has_video_input", "use_prev_video", "draft_mode"):
            for source in sources:
                if key in source and source.get(key) is not None:
                    payload[key] = bool(source.get(key))
                    break

        # RunningHub callback usage (coins / money / task runtime).
        for key in (
            "consumeCoins",
            "consumeMoney",
            "thirdPartyConsumeMoney",
            "taskCostTime",
            "provider_cost_time_seconds",
            "cost_time",
        ):
            value = _first(key)
            if value not in (None, ""):
                payload[key] = value
        if payload.get("taskCostTime") not in (None, "") and payload.get("provider_cost_time_seconds") in (None, ""):
            payload["provider_cost_time_seconds"] = payload.get("taskCostTime")

        return payload

    @staticmethod
    def _compact_history_ledger_details(details: Optional[dict]) -> dict:
        """Keep history-row details short; drop duplicated stage audit trees."""
        payload = BillingService._promote_media_context_for_history(details)
        for key in BillingService._HISTORY_DETAILS_DROP_KEYS:
            payload.pop(key, None)
        # Keep only a slim pricing_program for UI columns.
        program = payload.get("pricing_program")
        if isinstance(program, dict):
            payload["pricing_program"] = BillingService._slim_pricing_program_for_history(existing=program)
        compacted = BillingService._compact_audit_payload(payload)
        return compacted if isinstance(compacted, dict) else payload

    @staticmethod
    def _rule_specificity_score(rule: SystemAPIBillingRule) -> int:
        score = 0

        def _filled(value: Any) -> bool:
            return value is not None and str(value).strip() != ""

        weighted_fields = [
            ("generation_mode", 3),
            ("input_format", 2),
            ("output_format", 2),
            ("has_audio", 2),
        ]
        for field_name, weight in weighted_fields:
            if _filled(getattr(rule, field_name, None)):
                score += weight

        range_fields = [
            ("input_tokens_min", "input_tokens_max"),
            ("output_tokens_min", "output_tokens_max"),
            ("total_tokens_min", "total_tokens_max"),
            ("image_count_min", "image_count_max"),
            ("width_min", "width_max"),
            ("height_min", "height_max"),
            ("pixels_min", "pixels_max"),
            ("duration_seconds_min", "duration_seconds_max"),
            ("fps_min", "fps_max"),
        ]
        for min_field, max_field in range_fields:
            if _filled(getattr(rule, min_field, None)) or _filled(getattr(rule, max_field, None)):
                score += 2

        extra = BillingService._rule_extra_conditions(rule)
        if any(extra.get(key) is not None for key in ["cache_hit_tokens_min", "cache_hit_tokens_max"]):
            score += 2
        if any(extra.get(key) is not None for key in ["cache_miss_tokens_min", "cache_miss_tokens_max"]):
            score += 2
        if extra.get("require_success_output") is True:
            score += 2
        if extra.get("has_video_input") is not None:
            score += 2

        required_keys = extra.get("required_keys")
        if isinstance(required_keys, list):
            score += max(0, len([k for k in required_keys if str(k or "").strip()])) * 2

        return int(score)

    @staticmethod
    def _rule_matches_usage(rule: SystemAPIBillingRule, usage: Dict[str, Any], mode: str) -> bool:
        if not bool(getattr(rule, "is_active", False)):
            return False

        gm = BillingService._to_lower_text(getattr(rule, "generation_mode", ""))
        usage_gm = BillingService._to_lower_text(usage.get("generation_mode"))
        if gm and usage_gm and gm != usage_gm:
            return False

        inf = BillingService._to_lower_text(getattr(rule, "input_format", ""))
        usage_inf = BillingService._to_lower_text(usage.get("input_format"))
        if inf and usage_inf and inf != usage_inf:
            return False

        outf = BillingService._to_lower_text(getattr(rule, "output_format", ""))
        usage_outf = BillingService._to_lower_text(usage.get("output_format"))
        if outf and usage_outf and outf != usage_outf:
            return False

        rule_has_audio = getattr(rule, "has_audio", None)
        if rule_has_audio is not None:
            usage_has_audio = usage.get("has_audio", None)
            if usage_has_audio is not None and bool(rule_has_audio) != bool(usage_has_audio):
                return False

        if not BillingService._in_range_int(usage.get("input_tokens", 0), getattr(rule, "input_tokens_min", None), getattr(rule, "input_tokens_max", None)):
            return False
        if not BillingService._in_range_int(usage.get("output_tokens", 0), getattr(rule, "output_tokens_min", None), getattr(rule, "output_tokens_max", None)):
            return False
        if not BillingService._in_range_int(usage.get("total_tokens", 0), getattr(rule, "total_tokens_min", None), getattr(rule, "total_tokens_max", None)):
            return False

        if not BillingService._in_range_int(usage.get("image_count", 1), getattr(rule, "image_count_min", None), getattr(rule, "image_count_max", None)):
            return False
        width_min = getattr(rule, "width_min", None)
        width_max = getattr(rule, "width_max", None)
        height_min = getattr(rule, "height_min", None)
        height_max = getattr(rule, "height_max", None)

        width_ok = BillingService._in_range_int(usage.get("width", 0), width_min, width_max)
        height_ok = BillingService._in_range_int(usage.get("height", 0), height_min, height_max)

        if (not width_ok or not height_ok) and mode in {"image", "video"}:
            usage_w = BillingService._to_int(usage.get("width", 0), 0)
            usage_h = BillingService._to_int(usage.get("height", 0), 0)

            def _has_bound(v: Any) -> bool:
                return v is not None and str(v).strip() != ""

            has_width_bound = _has_bound(width_min) or _has_bound(width_max)
            has_height_bound = _has_bound(height_min) or _has_bound(height_max)

            if usage_w > 0 and usage_h > 0:
                # Fallback: allow portrait/landscape equivalent matching.
                # Rules are often authored with landscape assumptions (e.g. height<=1080).
                short_edge = min(usage_w, usage_h)
                swapped_width_ok = BillingService._in_range_int(usage_h, width_min, width_max)
                swapped_height_ok = BillingService._in_range_int(usage_w, height_min, height_max)

                if has_width_bound and has_height_bound:
                    if swapped_width_ok and swapped_height_ok:
                        width_ok = True
                        height_ok = True
                elif has_width_bound and not has_height_bound:
                    if BillingService._in_range_int(short_edge, width_min, width_max):
                        width_ok = True
                elif has_height_bound and not has_width_bound:
                    if BillingService._in_range_int(short_edge, height_min, height_max):
                        height_ok = True

        if not width_ok:
            return False
        if not height_ok:
            return False
        if not BillingService._in_range_int(usage.get("pixels", 0), getattr(rule, "pixels_min", None), getattr(rule, "pixels_max", None)):
            return False

        if not BillingService._in_range_float(usage.get("duration_seconds", 0.0), getattr(rule, "duration_seconds_min", None), getattr(rule, "duration_seconds_max", None)):
            return False
        if not BillingService._in_range_float(usage.get("fps", 0.0), getattr(rule, "fps_min", None), getattr(rule, "fps_max", None)):
            return False

        extra = BillingService._rule_extra_conditions(rule)
        rule_has_video_input = extra.get("has_video_input")
        if rule_has_video_input is not None:
            usage_has_video_input = usage.get("has_video_input")
            if usage_has_video_input is None and isinstance(usage.get("video_token_estimate"), dict):
                usage_has_video_input = usage["video_token_estimate"].get("has_video_input")
            if usage_has_video_input is not None and bool(rule_has_video_input) != bool(usage_has_video_input):
                return False

        if not BillingService._in_range_int(
            usage.get("cache_hit_tokens", 0),
            extra.get("cache_hit_tokens_min"),
            extra.get("cache_hit_tokens_max"),
        ):
            return False
        if not BillingService._in_range_int(
            usage.get("cache_miss_tokens", 0),
            extra.get("cache_miss_tokens_min"),
            extra.get("cache_miss_tokens_max"),
        ):
            return False

        require_success_output = extra.get("require_success_output")
        if require_success_output is True and int(usage.get("success_output_count", 0) or 0) <= 0:
            return False

        required_keys = extra.get("required_keys")
        if isinstance(required_keys, list):
            for key in required_keys:
                key_text = str(key or "").strip()
                if not key_text:
                    continue
                if not BillingService._usage_key_present(usage, key_text):
                    return False

        usage_standard_values = usage.get("standard_values") if isinstance(usage.get("standard_values"), dict) else {}
        expected_standard_values: Dict[str, Any] = {}
        explicit_standard = extra.get("standard_values")
        if isinstance(explicit_standard, dict):
            for key, value in explicit_standard.items():
                dim = str(key or "").strip().upper()
                if dim:
                    expected_standard_values[dim] = value
        for key, value in (extra or {}).items():
            key_text = str(key or "").strip()
            if not key_text.lower().startswith("standard."):
                continue
            dim = key_text.split(".", 1)[1].strip().upper()
            if dim:
                expected_standard_values[dim] = value

        for dim, expected in expected_standard_values.items():
            expected_norm = BillingService._normalize_kie_standard_value(dim, expected)
            actual_norm = BillingService._normalize_kie_standard_value(dim, usage_standard_values.get(dim))
            if not expected_norm:
                continue
            if not actual_norm or expected_norm != actual_norm:
                return False

        return True

    @staticmethod
    def _task_type_to_mode(task_type: str) -> str:
        normalized = str(task_type or "").strip().lower()
        if normalized in {"llm_chat", "analysis", "analysis_character"}:
            return "text"
        if normalized in {"image_gen"}:
            return "image"
        if normalized in {"video_gen"}:
            return "video"
        return "text"

    @staticmethod
    def _estimate_rule_cost(rule: SystemAPIBillingRule, usage: Dict[str, Any]) -> Dict[str, Any]:
        from app.services.billing_pricing import (
            compute_user_charge,
            estimate_base_amount_by_unit,
            resolve_rule_base_credits,
        )

        resolved = resolve_rule_base_credits(rule)
        raw_cfg = {
            "unit_type": str(resolved.get("unit_type") or "per_call"),
            "cost": max(0, int(resolved.get("cost") or 0)),
            "cost_input": max(0, int(resolved.get("cost_input") or 0)),
            "cost_output": max(0, int(resolved.get("cost_output") or 0)),
        }
        supplier = resolved.get("supplier") if isinstance(resolved.get("supplier"), dict) else {}
        extra = BillingService._rule_extra_conditions(rule)
        cache_hit_input_cost = BillingService._to_int(extra.get("cache_hit_cost_input", 0), 0)
        cache_hit_output_cost = BillingService._to_int(extra.get("cache_hit_cost_output", 0), 0)
        cache_miss_input_cost = BillingService._to_int(extra.get("cache_miss_cost_input", 0), 0)
        cache_miss_output_cost = BillingService._to_int(extra.get("cache_miss_cost_output", 0), 0)

        if raw_cfg["unit_type"] in BillingService.TOKEN_UNIT_TYPES and any(
            value > 0 for value in [cache_hit_input_cost, cache_hit_output_cost, cache_miss_input_cost, cache_miss_output_cost]
        ):
            divisor = 1_000_000.0 if raw_cfg["unit_type"] == "per_million_tokens" else 1_000.0 if raw_cfg["unit_type"] == "per_1k_tokens" else 1.0
            cache_hit_tokens = max(0, BillingService._to_int(usage.get("cache_hit_tokens", 0), 0))
            cache_miss_tokens = max(0, BillingService._to_int(usage.get("cache_miss_tokens", 0), 0))
            input_tokens = max(0, BillingService._to_int(usage.get("input_tokens", 0), 0))
            output_tokens = max(0, BillingService._to_int(usage.get("output_tokens", 0), 0))
            if cache_miss_tokens == 0:
                cache_miss_tokens = max(0, input_tokens - cache_hit_tokens)

            miss_input_rate = cache_miss_input_cost if cache_miss_input_cost > 0 else raw_cfg["cost_input"]
            output_rate = cache_miss_output_cost if cache_miss_output_cost > 0 else cache_hit_output_cost if cache_hit_output_cost > 0 else raw_cfg["cost_output"]

            computed = (
                (float(cache_hit_tokens) * float(cache_hit_input_cost))
                + (float(cache_miss_tokens) * float(miss_input_rate))
                + (float(output_tokens) * float(output_rate))
            ) / divisor
            amount = max(0.0, float(computed))
        else:
            usage_for_cost = dict(usage or {})
            rates = extra.get("video_token_resolution_rates")
            if isinstance(rates, dict) and rates:
                usage_for_cost["video_token_resolution_rates"] = rates
            second_rates = extra.get("video_second_resolution_rates")
            if not (isinstance(second_rates, dict) and second_rates):
                second_rates = usage_for_cost.get("video_second_resolution_rates")
            if isinstance(second_rates, dict) and second_rates:
                usage_for_cost["video_second_resolution_rates"] = second_rates
                # Per-second resolution matrix wins over Ark video-token flags.
                usage_for_cost.pop("video_token_estimate", None)
                if str(usage_for_cost.get("estimation_method") or "").startswith(
                    ("video_token", "seedance2_video_token")
                ):
                    usage_for_cost["estimation_method"] = "video_second_resolution"
                usage_for_cost.pop("video_token_branch", None)
            cny_rates = extra.get("video_second_cny_resolution_rates")
            if not (isinstance(cny_rates, dict) and cny_rates):
                cny_rates = usage_for_cost.get("video_second_cny_resolution_rates")
            if isinstance(cny_rates, dict) and cny_rates:
                usage_for_cost["video_second_cny_resolution_rates"] = cny_rates
                usage_for_cost.pop("video_token_estimate", None)
                usage_for_cost.pop("video_token_branch", None)
                min_table_probe = (
                    extra.get("video_second_min_billable_by_output")
                    or usage_for_cost.get("video_second_min_billable_by_output")
                )
                has_upscale_probe = any(
                    isinstance(row, dict)
                    and (
                        row.get("with_video_base") is not None
                        or row.get("with_video_addon") is not None
                        or str(row.get("pricing_kind") or "").lower() == "upscale"
                    )
                    for row in cny_rates.values()
                )
                if (isinstance(min_table_probe, dict) and min_table_probe) or has_upscale_probe:
                    usage_for_cost["estimation_method"] = "video_second_cny_sparkvideo"
                else:
                    usage_for_cost["estimation_method"] = "video_second_cny_kie"
            min_table = extra.get("video_second_min_billable_by_output")
            if not (isinstance(min_table, dict) and min_table):
                min_table = usage_for_cost.get("video_second_min_billable_by_output")
            if isinstance(min_table, dict) and min_table:
                usage_for_cost["video_second_min_billable_by_output"] = min_table
            if usage_for_cost.get("video_second_cny_resolution_rates"):
                from app.services.billing_pricing import resolve_sparkvideo_resolution_tier as _resolve_tier_cost
            else:
                from app.services.billing_pricing import resolve_video_resolution_tier as _resolve_tier_cost
            tier = _resolve_tier_cost(
                usage_for_cost.get("width"),
                usage_for_cost.get("height"),
                usage_for_cost.get("resolution_tier") or usage_for_cost.get("resolution"),
            )
            if tier:
                usage_for_cost["resolution_tier"] = tier
            amount = float(estimate_base_amount_by_unit(raw_cfg, usage_for_cost))

        runtime_multiplier = 1.0
        runtime_adjustments: Dict[str, Any] = {}
        is_seedance_video = bool(usage.get("is_seedance_video"))
        is_seedance_2 = bool(usage.get("is_seedance_2"))
        uses_video_token_formula = bool(
            usage.get("video_token_estimate")
            or str(usage.get("estimation_method") or "").startswith("video_token")
            or str(usage.get("estimation_method") or "").startswith("seedance2_video_token")
        )
        runtime_enabled = extra.get("seedance_runtime_price_adjustment_enabled")
        runtime_enabled = True if runtime_enabled is None else bool(BillingService._normalize_bool_value(runtime_enabled))
        cny_rates_audit = extra.get("video_second_cny_resolution_rates")
        if not (isinstance(cny_rates_audit, dict) and cny_rates_audit):
            cny_rates_audit = (usage or {}).get("video_second_cny_resolution_rates")
        if isinstance(cny_rates_audit, dict) and cny_rates_audit and raw_cfg["unit_type"] == "per_second":
            from app.services.billing_pricing import (
                estimate_sparkvideo_second_cny_amount,
                resolve_sparkvideo_resolution_tier as _resolve_sv_tier,
            )
            has_video_input_sv = bool(usage.get("has_video_input"))
            est = estimate_sparkvideo_second_cny_amount(
                rates=cny_rates_audit,
                resolution_tier=_resolve_sv_tier(
                    usage.get("width"),
                    usage.get("height"),
                    usage.get("resolution_tier") or usage.get("resolution"),
                ),
                has_video_input=has_video_input_sv,
                output_duration=usage.get("duration_seconds", usage.get("duration", 0)),
                input_duration=usage.get("input_duration_seconds", usage.get("input_duration", 0)),
                min_billable_table=extra.get("video_second_min_billable_by_output"),
            )
            runtime_adjustments["sparkvideo_rate_branch"] = est.get("rate_branch")
            runtime_adjustments["sparkvideo_cny_amount"] = est.get("cny_amount")
            runtime_adjustments["has_video_input"] = bool(has_video_input_sv)
            if est.get("resolution_tier"):
                runtime_adjustments["resolution_tier"] = est.get("resolution_tier")
            if est.get("billable_seconds") is not None:
                runtime_adjustments["sparkvideo_billable_seconds"] = est.get("billable_seconds")
            if est.get("min_billable_seconds") is not None:
                runtime_adjustments["sparkvideo_min_billable_seconds"] = est.get("min_billable_seconds")
            if est.get("unit_rate_cny") is not None:
                runtime_adjustments["sparkvideo_unit_rate_cny"] = est.get("unit_rate_cny")
            if est.get("with_video_base_cny") is not None:
                runtime_adjustments["sparkvideo_with_video_base_cny"] = est.get("with_video_base_cny")
            if est.get("with_video_addon_cny") is not None:
                runtime_adjustments["sparkvideo_with_video_addon_cny"] = est.get("with_video_addon_cny")
        if is_seedance_video and runtime_enabled:
            # Draft / continuation runtime odds removed: no 0.7 draft or 1.5 continuation markup.
            second_rates = extra.get("video_second_resolution_rates")
            if isinstance(second_rates, dict) and second_rates and raw_cfg["unit_type"] == "per_second":
                from app.services.billing_pricing import (
                    resolve_video_resolution_tier as _resolve_tier_s,
                    resolve_video_second_unit_rate,
                )
                has_video_input_s = bool(usage.get("has_video_input"))
                rate_meta_s = resolve_video_second_unit_rate(
                    cost=float(raw_cfg["cost"]),
                    cost_input=float(raw_cfg["cost_input"]),
                    cost_output=float(raw_cfg["cost_output"]),
                    has_video_input=has_video_input_s,
                    resolution_tier=_resolve_tier_s(
                        usage.get("width"),
                        usage.get("height"),
                        usage.get("resolution_tier") or usage.get("resolution"),
                    ),
                    resolution_rates_kie=second_rates,
                )
                runtime_adjustments["video_second_rate_branch"] = rate_meta_s.get("rate_branch")
                runtime_adjustments["video_second_unit_rate"] = rate_meta_s.get("rate")
                runtime_adjustments["has_video_input"] = bool(has_video_input_s)
                if rate_meta_s.get("resolution_tier"):
                    runtime_adjustments["resolution_tier"] = rate_meta_s.get("resolution_tier")
                if rate_meta_s.get("rate_source"):
                    runtime_adjustments["video_second_rate_source"] = rate_meta_s.get("rate_source")
                if rate_meta_s.get("rate_kie_credits_per_second") is not None:
                    runtime_adjustments["video_second_rate_kie_credits_per_second"] = rate_meta_s.get(
                        "rate_kie_credits_per_second"
                    )
            if uses_video_token_formula:
                runtime_adjustments["video_token_branch"] = "seedance2" if is_seedance_2 else "fallback"
                runtime_adjustments["video_token_formula"] = (
                    (usage.get("video_token_estimate") or {}).get("formula")
                    if isinstance(usage.get("video_token_estimate"), dict)
                    else None
                )
                from app.services.billing_pricing import resolve_video_token_unit_rate
                has_video_input = bool(usage.get("has_video_input"))
                if not has_video_input and isinstance(usage.get("video_token_estimate"), dict):
                    has_video_input = bool(usage["video_token_estimate"].get("has_video_input"))
                from app.services.billing_pricing import resolve_video_resolution_tier as _resolve_tier
                rate_meta = resolve_video_token_unit_rate(
                    cost=float(raw_cfg["cost"]),
                    cost_input=float(raw_cfg["cost_input"]),
                    cost_output=float(raw_cfg["cost_output"]),
                    has_video_input=has_video_input,
                    resolution_tier=_resolve_tier(
                        usage.get("width"),
                        usage.get("height"),
                        usage.get("resolution_tier") or usage.get("resolution"),
                    ),
                    resolution_rates_cny=extra.get("video_token_resolution_rates"),
                )
                runtime_adjustments["video_token_rate_branch"] = rate_meta.get("rate_branch")
                runtime_adjustments["video_token_unit_rate"] = rate_meta.get("rate")
                runtime_adjustments["has_video_input"] = bool(has_video_input)
                if rate_meta.get("resolution_tier"):
                    runtime_adjustments["resolution_tier"] = rate_meta.get("resolution_tier")
                if rate_meta.get("rate_source"):
                    runtime_adjustments["video_token_rate_source"] = rate_meta.get("rate_source")
                if rate_meta.get("rate_cny_per_mtok") is not None:
                    runtime_adjustments["video_token_rate_cny_per_mtok"] = rate_meta.get("rate_cny_per_mtok")

        charged = compute_user_charge(
            unit_type=raw_cfg["unit_type"],
            base_cost=raw_cfg["cost"],
            base_cost_input=raw_cfg["cost_input"],
            base_cost_output=raw_cfg["cost_output"],
            charge_multiplier=getattr(rule, "charge_multiplier", 2.0),
            usage={"billing_quantity": 1},
            runtime_multiplier=1.0,
        )
        # Reuse unit calc amount (incl. cache path) then apply odds via pricing program.
        from app.services.billing_pricing import apply_odds_to_credits, normalize_charge_multiplier
        charge_multiplier = normalize_charge_multiplier(getattr(rule, "charge_multiplier", None), default=2.0)
        base_cost = int(max(0, math.ceil(amount))) if amount > 0 else 0
        charged_cost = apply_odds_to_credits(amount, charge_multiplier, runtime_multiplier)
        effective_cfg = BillingService._normalize_api_pricing_config({
            "unit_type": raw_cfg["unit_type"],
            "cost": int(charged.get("unit_user_cost") or 0),
            "cost_input": int(charged.get("unit_user_cost_input") or 0),
            "cost_output": int(charged.get("unit_user_cost_output") or 0),
        })
        if runtime_multiplier != 1.0:
            effective_cfg = BillingService._normalize_api_pricing_config({
                "unit_type": raw_cfg["unit_type"],
                "cost": apply_odds_to_credits(raw_cfg["cost"], charge_multiplier, runtime_multiplier),
                "cost_input": apply_odds_to_credits(raw_cfg["cost_input"], charge_multiplier, runtime_multiplier),
                "cost_output": apply_odds_to_credits(raw_cfg["cost_output"], charge_multiplier, runtime_multiplier),
            })
        return {
            "cost": charged_cost,
            "base_cost": base_cost,
            "charge_multiplier": float(charge_multiplier),
            "runtime_price_multiplier": float(runtime_multiplier),
            "runtime_price_adjustments": runtime_adjustments,
            "supplier_pricing": supplier,
            "base_credit_source": resolved.get("source"),
            "config": effective_cfg,
        }

    @staticmethod
    def _first_positive_float(source: Dict[str, Any], keys: List[str], default: float) -> float:
        for key in keys:
            if key not in source:
                continue
            parsed = BillingService._safe_float(source.get(key), default)
            if parsed > 0:
                return float(parsed)
        return float(default)

    @staticmethod
    def _select_best_matching_rule(
        db: Session,
        provider: str,
        model: str,
        usage: Dict[str, Any],
        mode: Optional[str],
    ) -> Dict[str, Any]:
        rows = BillingService._query_active_rules_by_identity(db, provider, model, mode)

        if not rows:
            return {"matched": [], "best": None}

        matched = []
        for row in rows:
            # Undimensioned / base-tier rules are priced via base-rule fallback, not here.
            # Otherwise orphan per_second rows (priority 0) steal from real base_pricing.
            if not BillingService._rule_is_dimensional_matcher(row):
                continue
            if not BillingService._rule_matches_usage(row, usage, mode):
                continue
            pricing = BillingService._estimate_rule_cost(row, usage)
            specificity = BillingService._rule_specificity_score(row)
            matched.append({"rule": row, "pricing": pricing, "specificity": int(specificity)})

        if not matched:
            return {"matched": [], "best": None}

        matched.sort(
            key=lambda x: (
                int(getattr(x["rule"], "priority", 0) or 0),
                int(x.get("specificity", 0) or 0),
                int(x["pricing"]["cost"]),
                int(getattr(x["rule"], "id", 0) or 0),
            ),
            reverse=True,
        )
        return {"matched": matched, "best": matched[0]}

    @staticmethod
    def _serialize_rule_for_audit(
        rule: Optional[SystemAPIBillingRule],
        *,
        pricing: Optional[Dict[str, Any]] = None,
        specificity: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        if not rule:
            return None

        ranges: Dict[str, Any] = {
            "input_tokens_min": getattr(rule, "input_tokens_min", None),
            "input_tokens_max": getattr(rule, "input_tokens_max", None),
            "output_tokens_min": getattr(rule, "output_tokens_min", None),
            "output_tokens_max": getattr(rule, "output_tokens_max", None),
            "total_tokens_min": getattr(rule, "total_tokens_min", None),
            "total_tokens_max": getattr(rule, "total_tokens_max", None),
            "image_count_min": getattr(rule, "image_count_min", None),
            "image_count_max": getattr(rule, "image_count_max", None),
            "width_min": getattr(rule, "width_min", None),
            "width_max": getattr(rule, "width_max", None),
            "height_min": getattr(rule, "height_min", None),
            "height_max": getattr(rule, "height_max", None),
            "pixels_min": getattr(rule, "pixels_min", None),
            "pixels_max": getattr(rule, "pixels_max", None),
            "duration_seconds_min": getattr(rule, "duration_seconds_min", None),
            "duration_seconds_max": getattr(rule, "duration_seconds_max", None),
            "fps_min": getattr(rule, "fps_min", None),
            "fps_max": getattr(rule, "fps_max", None),
        }

        pricing_payload = dict(pricing or {})
        pricing_config = pricing_payload.get("config") if isinstance(pricing_payload.get("config"), dict) else None
        if pricing_config is None:
            pricing_config = BillingService._billing_from_rule(rule)

        payload = {
            "id": int(getattr(rule, "id", 0) or 0),
            "name": str(getattr(rule, "name", "") or ""),
            "priority": int(getattr(rule, "priority", 0) or 0),
            "is_base_pricing": BillingService._is_base_billing_rule(rule),
            "is_active": bool(getattr(rule, "is_active", False)),
            "applies_to": {
                "text": bool(getattr(rule, "applies_to_text", False)),
                "image": bool(getattr(rule, "applies_to_image", False)),
                "video": bool(getattr(rule, "applies_to_video", False)),
            },
            "match_dimensions": {
                "generation_mode": getattr(rule, "generation_mode", None),
                "input_format": getattr(rule, "input_format", None),
                "output_format": getattr(rule, "output_format", None),
                "has_audio": getattr(rule, "has_audio", None),
                "ranges": ranges,
                "extra_conditions": BillingService._rule_extra_conditions(rule),
            },
            "pricing": dict(pricing_config or {}),
            "rule_charge_multiplier": float((pricing_payload or {}).get("charge_multiplier", getattr(rule, "charge_multiplier", 2.0)) or 0.0),
            "runtime_price_multiplier": float((pricing_payload or {}).get("runtime_price_multiplier", 1.0) or 1.0),
            "runtime_price_adjustments": (pricing_payload or {}).get("runtime_price_adjustments") or {},
            "supplier_pricing": (pricing_payload or {}).get("supplier_pricing") or {},
            "base_credit_source": (pricing_payload or {}).get("base_credit_source"),
            "computed_base_cost": int((pricing_payload or {}).get("base_cost", 0) or 0),
            "computed_cost": int((pricing_payload or {}).get("cost", 0) or 0),
            "specificity_score": int(specificity or 0),
        }
        compacted = BillingService._compact_audit_payload(payload)
        return compacted if isinstance(compacted, dict) else None

    @staticmethod
    @staticmethod
    def _derive_billing_logic_branch(
        *,
        unit_type: Any = None,
        usage: Optional[Dict[str, Any]] = None,
        selected_rule_detail: Optional[Dict[str, Any]] = None,
        runtime_adjustments: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Human-readable billing logic branch for logs / UI diagnostics."""
        usage_payload = dict(usage or {})
        adj = dict(runtime_adjustments or {})
        if not adj and isinstance(selected_rule_detail, dict):
            adj = dict(selected_rule_detail.get("runtime_price_adjustments") or {})
        unit = str(unit_type or "").strip().lower()
        if not unit and isinstance(selected_rule_detail, dict):
            pricing = selected_rule_detail.get("pricing") if isinstance(selected_rule_detail.get("pricing"), dict) else {}
            unit = str(pricing.get("unit_type") or "").strip().lower()

        extra = {}
        if isinstance(selected_rule_detail, dict):
            match_dims = selected_rule_detail.get("match_dimensions") if isinstance(selected_rule_detail.get("match_dimensions"), dict) else {}
            extra = match_dims.get("extra_conditions") if isinstance(match_dims.get("extra_conditions"), dict) else {}

        has_cny_matrix = bool(
            (isinstance(extra.get("video_second_cny_resolution_rates"), dict) and extra.get("video_second_cny_resolution_rates"))
            or (isinstance(usage_payload.get("video_second_cny_resolution_rates"), dict) and usage_payload.get("video_second_cny_resolution_rates"))
            or adj.get("sparkvideo_unit_rate_cny") is not None
            or adj.get("sparkvideo_cny_amount") is not None
            or str(usage_payload.get("estimation_method") or "").startswith("sparkvideo_second_cny")
            or str(usage_payload.get("estimation_method") or "").startswith("video_second_cny")
        )
        has_kie_matrix = bool(
            (isinstance(extra.get("video_second_resolution_rates"), dict) and extra.get("video_second_resolution_rates"))
            or (isinstance(usage_payload.get("video_second_resolution_rates"), dict) and usage_payload.get("video_second_resolution_rates"))
        )
        has_token_matrix = bool(
            (isinstance(extra.get("video_token_resolution_rates"), dict) and extra.get("video_token_resolution_rates"))
            or (isinstance(usage_payload.get("video_token_resolution_rates"), dict) and usage_payload.get("video_token_resolution_rates"))
        )
        has_min_table = bool(
            (
                isinstance(extra.get("video_second_min_billable_by_output"), dict)
                and extra.get("video_second_min_billable_by_output")
            )
            or (
                isinstance(usage_payload.get("video_second_min_billable_by_output"), dict)
                and usage_payload.get("video_second_min_billable_by_output")
            )
        )
        has_upscale = bool(
            adj.get("sparkvideo_with_video_base_cny") is not None
            or adj.get("sparkvideo_with_video_addon_cny") is not None
            or str(adj.get("sparkvideo_rate_branch") or "").endswith("upscale")
        )
        uses_token_formula = bool(
            usage_payload.get("video_token_estimate")
            or str(usage_payload.get("estimation_method") or "").startswith("video_token")
            or str(usage_payload.get("estimation_method") or "").startswith("seedance2_video_token")
            or adj.get("video_token_rate_branch")
        )

        if unit == "per_second" and has_cny_matrix:
            if has_upscale or has_min_table:
                return "video_second_cny_sparkvideo"
            return "video_second_cny_kie_or_flat"
        if unit == "per_second" and has_kie_matrix:
            return "video_second_kie_credits"
        if unit in BillingService.TOKEN_UNIT_TYPES and (has_token_matrix or uses_token_formula):
            return "video_token_resolution" if has_token_matrix else "video_token_formula"
        if unit == "per_second":
            return "video_per_second_flat"
        if unit in BillingService.TOKEN_UNIT_TYPES:
            return "token_unit"
        if unit:
            return f"unit:{unit}"
        return "unknown"

    @staticmethod
    def _slim_runtime_adjustments_for_process(adj: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Keep tier/multiplier scalars; drop resolution rate matrices from process snapshots/logs."""
        if not isinstance(adj, dict) or not adj:
            return {}
        out: Dict[str, Any] = {}
        for key in (
            "resolution_tier",
            "runtime_price_multiplier",
            "price_multiplier",
            "draft_mode",
            "has_video_input",
            "has_audio",
            "reason",
        ):
            if adj.get(key) not in (None, ""):
                out[key] = adj.get(key)
        return out

    @staticmethod
    def _build_billing_process_snapshot(breakdown: Dict[str, Any], *, phase: str = "reserve") -> Dict[str, Any]:
        usage = breakdown.get("usage_metadata") if isinstance(breakdown.get("usage_metadata"), dict) else {}
        selected = breakdown.get("selected_rule_detail") if isinstance(breakdown.get("selected_rule_detail"), dict) else {}
        adj = selected.get("runtime_price_adjustments") if isinstance(selected.get("runtime_price_adjustments"), dict) else {}
        pricing = selected.get("pricing") if isinstance(selected.get("pricing"), dict) else {}
        function_billing = breakdown.get("function_billing") if isinstance(breakdown.get("function_billing"), dict) else {}
        api_pricing = breakdown.get("api_pricing") if isinstance(breakdown.get("api_pricing"), dict) else {}
        source_detail = breakdown.get("api_pricing_source_detail") if isinstance(breakdown.get("api_pricing_source_detail"), dict) else {}
        if not adj and isinstance(source_detail.get("runtime_price_adjustments"), dict):
            adj = dict(source_detail.get("runtime_price_adjustments") or {})
        unit_type = (
            pricing.get("unit_type")
            or api_pricing.get("unit_type")
            or usage.get("billing_unit_type")
        )
        # Prefer matrix markers from usage/source_detail when rule detail was compacted away.
        usage_for_logic = dict(usage or {})
        for key in (
            "video_second_cny_resolution_rates",
            "video_second_resolution_rates",
            "video_token_resolution_rates",
            "video_second_min_billable_by_output",
        ):
            if not usage_for_logic.get(key) and isinstance(api_pricing.get(key), dict):
                usage_for_logic[key] = api_pricing.get(key)
        logic = BillingService._derive_billing_logic_branch(
            unit_type=unit_type,
            usage=usage_for_logic,
            selected_rule_detail=selected,
            runtime_adjustments=adj,
        )
        matched_rule_id = breakdown.get("matched_rule_id")
        if matched_rule_id is None:
            matched_rule_id = source_detail.get("base_rule_id") or source_detail.get("rule_id")
        matched_rule_name = breakdown.get("matched_rule_name")
        if not matched_rule_name:
            matched_rule_name = source_detail.get("base_rule_name") or source_detail.get("rule_name")
        # Compact snapshot for API/logs — no rate maps / nested estimate trees.
        return {
            "phase": str(phase or "").strip() or None,
            "logic_branch": logic,
            "total_cost": int(breakdown.get("total_cost") or 0),
            "feature_cost": int(breakdown.get("feature_cost") or 0),
            "api_cost": int(breakdown.get("api_cost") or 0),
            "api_cost_before_function": int(breakdown.get("api_cost_before_function") or breakdown.get("api_cost") or 0),
            "provider": breakdown.get("resolved_provider") or breakdown.get("provider"),
            "model": breakdown.get("resolved_model") or breakdown.get("model"),
            "system_api_id": breakdown.get("system_api_id"),
            "api_pricing_source": breakdown.get("api_pricing_source"),
            "matched_rule_id": matched_rule_id,
            "matched_rule_name": matched_rule_name,
            "unit_type": unit_type,
            "charge_multiplier": selected.get("rule_charge_multiplier"),
            "base_cost": selected.get("computed_base_cost"),
            "runtime_price_multiplier": selected.get("runtime_price_multiplier"),
            "runtime_price_adjustments": BillingService._slim_runtime_adjustments_for_process(adj),
            "function_billing": {
                "applied": bool(function_billing.get("applied")),
                "multiplier": function_billing.get("function_multiplier"),
                "add_credits": function_billing.get("function_add_credits"),
            },
            "usage": {
                "duration_seconds": usage.get("duration_seconds", usage.get("duration")),
                "input_duration_seconds": usage.get("input_duration_seconds", usage.get("input_duration")),
                "aspect_ratio": usage.get("aspect_ratio"),
                "width": usage.get("width"),
                "height": usage.get("height"),
                "resolution": usage.get("resolution"),
                "resolution_tier": usage.get("resolution_tier") or adj.get("resolution_tier"),
                "has_video_input": usage.get("has_video_input"),
                "use_prev_video": usage.get("use_prev_video"),
                "draft_mode": usage.get("draft_mode"),
                "estimation_method": usage.get("estimation_method"),
                "output_tokens": usage.get("output_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "kie_credits_consumed": usage.get("kie_credits_consumed") or usage.get("creditsConsumed"),
            },
            "new_logic": logic in {
                "video_second_cny_sparkvideo",
                "video_second_cny_kie_or_flat",
                "video_second_kie_credits",
                "video_token_resolution",
                "video_token_formula",
            },
        }

    @staticmethod
    def _log_billing_process(snapshot: Dict[str, Any], *, context: str = "billing") -> None:
        """One short line to the billing logger — no JSON dump, no multi-logger fan-out."""
        try:
            usage = snapshot.get("usage") if isinstance(snapshot.get("usage"), dict) else {}
            logger.info(
                "[BillingProcess] %s phase=%s logic=%s total=%s api=%s rule=%s unit=%s "
                "x%s %s/%s api_id=%s tier=%s dur=%s draft=%s v_in=%s src=%s%s",
                context,
                snapshot.get("phase"),
                snapshot.get("logic_branch") or "unknown",
                snapshot.get("total_cost"),
                snapshot.get("api_cost"),
                snapshot.get("matched_rule_id"),
                snapshot.get("unit_type"),
                snapshot.get("charge_multiplier"),
                snapshot.get("provider"),
                snapshot.get("model"),
                snapshot.get("system_api_id"),
                usage.get("resolution_tier"),
                usage.get("duration_seconds"),
                usage.get("draft_mode"),
                usage.get("has_video_input"),
                snapshot.get("api_pricing_source"),
                (
                    f" user={snapshot.get('user_id')} tx={snapshot.get('reservation_tx_id')}"
                    if snapshot.get("user_id") or snapshot.get("reservation_tx_id")
                    else ""
                ),
            )
        except Exception as exc:
            logger.warning("[BillingProcess] log failed ctx=%s err=%s", context, exc)

    @staticmethod
    def estimate_cost_breakdown(
        db: Session,
        task_type: str,
        provider: str = None,
        model: str = None,
        details: dict = None,
        phase: str = "reserve",
        reserved_cost_fallback: Optional[int] = None,
    ) -> Dict[str, Any]:
        payload_details = dict(details or {})
        usage = BillingService._extract_usage_metadata(payload_details)

        provider_text = str(provider or "").strip()
        model_text = str(model or "").strip()
        smart_routing = payload_details.get("smart_routing") if isinstance(payload_details.get("smart_routing"), dict) else {}
        details_provider = str(
            payload_details.get("provider")
            or payload_details.get("resolved_provider")
            or smart_routing.get("provider")
            or ""
        ).strip()
        details_model = str(
            payload_details.get("model")
            or payload_details.get("resolved_model")
            or smart_routing.get("model")
            or ""
        ).strip()
        if details_provider:
            provider_text = details_provider
        if details_model:
            model_text = details_model

        forced_system_api_id = payload_details.get("system_api_id")
        if forced_system_api_id is None:
            forced_system_api_id = payload_details.get("resolved_system_api_id")
        if forced_system_api_id is None and smart_routing:
            forced_system_api_id = smart_routing.get("system_api_id")
        try:
            forced_system_api_id = int(forced_system_api_id) if forced_system_api_id is not None else None
        except Exception:
            forced_system_api_id = None

        feature_cost = BillingService._resolve_feature_cost(db, task_type, details)
        api_pricing_source = "default_api_pricing"
        api_pricing_source_detail: Dict[str, Any] = {}

        mode = BillingService._task_type_to_mode(task_type)
        system_row = None
        if forced_system_api_id is not None:
            system_row = BillingService._system_setting_query(db).filter(SystemAPISetting.id == forced_system_api_id).first()
        if not system_row:
            system_row = BillingService._resolve_system_api_row(db, task_type, provider_text, model_text)
        if system_row:
            provider_text = str(getattr(system_row, "provider", "") or provider_text).strip()
            model_text = str(getattr(system_row, "model", "") or model_text).strip()

        if mode == "video":
            identity_parts = [
                provider_text,
                model_text,
                getattr(system_row, "name", "") if system_row else "",
            ]
            identity_text = " ".join(str(part or "") for part in identity_parts).lower()
            usage["is_seedance_video"] = "seedance" in identity_text
            usage["is_seedance_2"] = BillingService.is_seedance_2_model(*identity_parts)
            usage["has_video_input"] = BillingService.resolve_has_video_input(usage)
            if usage.get("is_seedance_video"):
                usage["seedance_billing_adjustable"] = True
            identity_lower = " ".join(str(p or "") for p in identity_parts).lower()
            if "sparkvideo" in identity_lower or "runninghub" in str(provider_text or "").lower():
                from app.services.billing_pricing import resolve_sparkvideo_resolution_tier as _tier_fn_early
            else:
                from app.services.billing_pricing import resolve_video_resolution_tier as _tier_fn_early
            usage["resolution_tier"] = _tier_fn_early(
                usage.get("width"),
                usage.get("height"),
                usage.get("resolution") or usage.get("resolution_tier"),
            )
            # Video token fallback / Seedance 2.0 branch: derive tokens when missing.
            # KIE Seedance 2 bills per-second by resolution (not Ark token formula).
            is_kie_provider = BillingService._is_kie_provider(provider_text)
            usage["is_kie_provider"] = bool(is_kie_provider)
            usage["provider"] = provider_text
            # Inject published KIE Seedance 2 CNY/s matrix when rule extras are empty.
            # Seedance 1.5 keeps dimensional per_call rules; do not force the 2.0 matrix there.
            if is_kie_provider and (
                usage.get("is_seedance_2")
                or "seedance-2" in identity_text
                or "seedance2" in identity_text.replace("-", "").replace("_", "").replace(" ", "")
            ):
                usage["is_seedance_video"] = True
                usage = BillingService._ensure_kie_seedance_second_matrix(usage)
            provider_lower = str(provider_text or "").strip().lower()
            is_runninghub_provider = (
                provider_lower == "runninghub"
                or provider_lower.startswith("runninghub/")
                or "runninghub" in provider_lower
            )
            if (not is_kie_provider) and (not is_runninghub_provider) and (
                usage.get("is_seedance_2")
                or str(usage.get("estimation_method") or "").startswith("video_token")
                or str(usage.get("estimation_method") or "").startswith("seedance2_video_token")
                or (
                    BillingService._to_int(usage.get("output_tokens", 0), 0) <= 0
                    and BillingService._to_int(usage.get("total_tokens", 0), 0) <= 0
                    and (
                        BillingService._to_int(usage.get("width", 0), 0) > 0
                        or BillingService._to_int(usage.get("height", 0), 0) > 0
                    )
                )
            ):
                out_duration = BillingService._safe_float(
                    usage.get("duration_seconds", usage.get("duration", usage.get("estimated_duration", 0))),
                    0.0,
                )
                if out_duration > 0:
                    token_estimate = BillingService.estimate_video_token_usage(
                        width=BillingService._to_int(usage.get("width"), 1280) or 1280,
                        height=BillingService._to_int(usage.get("height"), 720) or 720,
                        fps=BillingService._to_int(usage.get("fps"), 24) or 24,
                        output_duration_seconds=out_duration,
                        has_video_input=bool(usage.get("has_video_input")),
                        input_duration_seconds=usage.get("input_duration_seconds"),
                        draft_token_coefficient=BillingService._safe_float(
                            usage.get("draft_token_coefficient"),
                            1.0,
                        ),
                        method=("seedance2_video_token_formula" if usage.get("is_seedance_2") else "video_token_formula"),
                    )
                    tokens = int(token_estimate.get("tokens") or 0)
                    if tokens > 0 and BillingService._to_int(usage.get("output_tokens", 0), 0) <= 0:
                        usage["output_tokens"] = tokens
                        usage["total_tokens"] = tokens
                    usage["video_token_estimate"] = token_estimate
                    usage["estimation_method"] = token_estimate.get("estimation_method")
                    usage["video_token_branch"] = "seedance2" if usage.get("is_seedance_2") else "fallback"
                    from app.services.billing_pricing import resolve_video_resolution_tier as _tier_fn
                    usage["resolution_tier"] = _tier_fn(
                        usage.get("width"),
                        usage.get("height"),
                        usage.get("resolution") or usage.get("resolution_tier"),
                    )

        if (
            system_row
            and str(getattr(system_row, "provider", "") or "").strip().lower() == BillingService.KIE_STANDARD_PROVIDER
        ):
            std_usage = BillingService._resolve_kie_standard_usage(
                db=db,
                model_key=model_text,
                usage=usage,
                details=payload_details,
            )
            if isinstance(std_usage.get("standard_values"), dict) and std_usage.get("standard_values"):
                usage["standard_values"] = dict(std_usage.get("standard_values") or {})
            if isinstance(std_usage.get("standard_trace"), dict) and std_usage.get("standard_trace"):
                usage["standard_trace"] = dict(std_usage.get("standard_trace") or {})

        # Billing order:
        # 1) system_api_id base rule (with resolution matrices via _estimate_rule_cost)
        # 2) provider/model identity base rule
        # 3) dimensional matching rules
        # 4) generic default pricing
        prefer_token_unit = bool(
            usage.get("video_token_estimate")
            or str(usage.get("estimation_method") or "").startswith("video_token")
            or str(usage.get("estimation_method") or "").startswith("seedance2_video_token")
        )
        # KIE Seedance 2: always prefer per_second base (never Ark token base).
        prefer_per_second_unit = bool(
            usage.get("is_kie_provider")
            and (
                usage.get("is_seedance_2")
                or str(usage.get("estimation_method") or "").startswith("video_second_cny")
                or usage.get("kie_seedance_default_matrix")
            )
        )
        if prefer_per_second_unit:
            prefer_token_unit = False
        base_rule: Optional[SystemAPIBillingRule] = None
        base_rule_pricing: Optional[Dict[str, Any]] = None
        if system_row is not None:
            base_rule = BillingService._get_base_billing_rule(
                db,
                int(system_row.id),
                prefer_token_unit=prefer_token_unit,
                prefer_per_second_unit=prefer_per_second_unit,
            )
        if base_rule is None and provider_text and model_text:
            base_rule = BillingService._get_base_billing_rule_by_identity(
                db,
                provider_text,
                model_text,
                mode,
                prefer_token_unit=prefer_token_unit,
                prefer_per_second_unit=prefer_per_second_unit,
            )

        if base_rule is not None:
            # Critical: use _estimate_rule_cost so video_second_cny / token resolution matrices apply.
            base_rule_pricing = BillingService._estimate_rule_cost(base_rule, usage)
            api_cfg = dict((base_rule_pricing or {}).get("config") or BillingService._billing_from_rule(base_rule) or {})
            # Keep matrix extras on cfg so flat fallback helpers can also see them.
            extra_for_cfg = BillingService._rule_extra_conditions(base_rule)
            for key in (
                "video_second_cny_resolution_rates",
                "video_second_resolution_rates",
                "video_token_resolution_rates",
                "video_second_min_billable_by_output",
            ):
                if isinstance(extra_for_cfg.get(key), dict) and extra_for_cfg.get(key):
                    api_cfg[key] = extra_for_cfg.get(key)
                    usage[key] = extra_for_cfg.get(key)
                elif isinstance(usage.get(key), dict) and usage.get(key):
                    # Preserve KIE Seedance injected defaults when rule extras are empty.
                    api_cfg[key] = usage.get(key)
            api_pricing_source = "system_api_base_rule"
            api_pricing_source_detail = {
                "base_rule_id": int(getattr(base_rule, "id", 0) or 0),
                "base_rule_name": str(getattr(base_rule, "name", "") or ""),
                "base_cost": int((base_rule_pricing or {}).get("base_cost") or 0),
                "runtime_price_adjustments": (base_rule_pricing or {}).get("runtime_price_adjustments") or {},
            }
            api_cost_fallback = int((base_rule_pricing or {}).get("cost") or 0)
        elif provider_text and model_text:
            api_cfg = dict(BillingService._resolve_api_pricing_config(db, task_type, provider_text, model_text) or {})
            # No base rule: still apply injected KIE Seedance CNY/s matrix via unit estimator.
            for key in (
                "video_second_cny_resolution_rates",
                "video_second_resolution_rates",
                "video_second_min_billable_by_output",
            ):
                if isinstance(usage.get(key), dict) and usage.get(key):
                    api_cfg[key] = usage.get(key)
            if usage.get("is_kie_provider") and (
                usage.get("kie_seedance_default_matrix")
                or isinstance(usage.get("video_second_cny_resolution_rates"), dict)
                and usage.get("video_second_cny_resolution_rates")
            ):
                api_cfg["unit_type"] = "per_second"
                if not api_cfg.get("cost"):
                    api_cfg["cost"] = 0
            api_pricing_source = "default_api_pricing"
            api_pricing_source_detail = {"reason": "system_api_has_no_base_rule"}
            api_cost_fallback = BillingService._estimate_api_cost_from_config(api_cfg, usage)
        else:
            api_cfg = dict(BillingService._resolve_api_pricing_config(db, task_type, provider_text, model_text) or {})
            for key in (
                "video_second_cny_resolution_rates",
                "video_second_resolution_rates",
                "video_second_min_billable_by_output",
            ):
                if isinstance(usage.get(key), dict) and usage.get(key):
                    api_cfg[key] = usage.get(key)
            api_pricing_source = "default_api_pricing"
            api_pricing_source_detail = {"reason": "system_api_not_resolved"}
            api_cost_fallback = BillingService._estimate_api_cost_from_config(api_cfg, usage)

        matched_rule_ids: List[int] = []
        selected_rule_id = None
        selected_rule_name = None
        selected_rule_detail = None
        matched_rule_details: List[Dict[str, Any]] = []
        selected_api_cfg = api_cfg
        selected_api_cost = int(api_cost_fallback or 0)
        rule_match_count = 0

        if provider_text and model_text:
            matched_info = BillingService._select_best_matching_rule(db, provider_text, model_text, usage, mode)
            matched_rows = matched_info.get("matched") or []
            rule_match_count = len(matched_rows)
            matched_rule_ids = [int(item["rule"].id) for item in matched_rows]
            matched_rule_details = [
                BillingService._serialize_rule_for_audit(
                    item.get("rule"),
                    pricing=item.get("pricing"),
                    specificity=item.get("specificity"),
                )
                for item in matched_rows[:5]
            ]
            matched_rule_details = [item for item in matched_rule_details if item]
            best = matched_info.get("best")
            if best:
                selected_rule = best["rule"]
                selected_rule_id = int(selected_rule.id)
                selected_rule_name = str(getattr(selected_rule, "name", "") or "")
                selected_api_cfg = dict(best["pricing"].get("config") or api_cfg)
                selected_api_cost = int(best["pricing"].get("cost") or 0)
                api_pricing_source = "system_api_billing_rule"
                api_pricing_source_detail = {
                    "rule_id": int(selected_rule_id),
                    "rule_name": selected_rule_name,
                    "priority": int(getattr(selected_rule, "priority", 0) or 0),
                }
                selected_rule_detail = BillingService._serialize_rule_for_audit(
                    selected_rule,
                    pricing=best.get("pricing"),
                    specificity=best.get("specificity"),
                )
            elif base_rule is not None and base_rule_pricing is not None:
                # No dimensional match: still charge/display via base rule + resolution matrices.
                selected_rule_id = int(getattr(base_rule, "id", 0) or 0) or None
                selected_rule_name = str(getattr(base_rule, "name", "") or "") or None
                selected_api_cfg = dict(api_cfg or {})
                selected_api_cost = int((base_rule_pricing or {}).get("cost") or 0)
                api_pricing_source = "system_api_base_rule"
                api_pricing_source_detail = {
                    "base_rule_id": int(getattr(base_rule, "id", 0) or 0),
                    "base_rule_name": str(getattr(base_rule, "name", "") or ""),
                    "reason": "no_dimensional_rule_matched_use_base_rule",
                }
                selected_rule_detail = BillingService._serialize_rule_for_audit(
                    base_rule,
                    pricing=base_rule_pricing,
                    specificity=0,
                )
            elif phase == "settle" and reserved_cost_fallback is not None:
                selected_api_cost = int(max(0, reserved_cost_fallback))
                api_pricing_source = "settlement_reserved_cost_fallback"
                api_pricing_source_detail = {"reason": "no_rule_matched_use_reserved_cost"}
        elif base_rule is not None and base_rule_pricing is not None:
            selected_rule_id = int(getattr(base_rule, "id", 0) or 0) or None
            selected_rule_name = str(getattr(base_rule, "name", "") or "") or None
            selected_api_cfg = dict(api_cfg or {})
            selected_api_cost = int((base_rule_pricing or {}).get("cost") or 0)
            selected_rule_detail = BillingService._serialize_rule_for_audit(
                base_rule,
                pricing=base_rule_pricing,
                specificity=0,
            )

        used_reserved_fallback = bool(
            phase == "settle"
            and reserved_cost_fallback is not None
            and selected_rule_id is None
            and rule_match_count == 0
            and system_row is not None
        )

        function_billing = BillingService._resolve_function_billing_adjustment(
            db,
            details=payload_details,
            system_api_id=(int(system_row.id) if system_row else None),
        )
        api_cost_before_function = int(selected_api_cost)
        if used_reserved_fallback and reserved_cost_fallback is not None:
            # Reserved fallback already includes prior function markup from reserve phase.
            total_cost = max(0, int(reserved_cost_fallback))
            function_billing = {
                **function_billing,
                "applied": False,
                "reason": "settlement_reserved_cost_fallback",
                "api_cost_before": api_cost_before_function,
                "api_cost_after": int(reserved_cost_fallback),
            }
        else:
            from app.services.billing_pricing import apply_function_billing_adjustment
            adjusted = apply_function_billing_adjustment(
                selected_api_cost,
                multiplier=function_billing.get("function_multiplier", 1.0),
                add_credits=function_billing.get("function_add_credits", 0),
            )
            selected_api_cost = int(adjusted.get("api_cost_after") or 0)
            function_billing = {
                **function_billing,
                "applied": True,
                "api_cost_before": int(adjusted.get("api_cost_before") or api_cost_before_function),
                "api_cost_after": int(selected_api_cost),
            }
            total_cost = max(0, int(feature_cost) + int(selected_api_cost))

        normalized_task = str(task_type or "").strip().lower()
        min_charge = int(BillingService.MINIMUM_CHARGE_BY_TASK.get(normalized_task, 0) or 0)
        minimum_charge_applied = bool(min_charge > 0 and total_cost < min_charge)
        minimum_charge_delta = 0
        if minimum_charge_applied:
            minimum_charge_delta = int(min_charge - total_cost)
            total_cost = int(min_charge)

        resolved_provider = str(provider_text or "").strip() or None
        resolved_model = str(model_text or "").strip() or None
        rule_selection_status = "matched" if selected_rule_id is not None else "not_matched"
        if selected_rule_id is not None:
            rule_selection_reason = "matched_active_rule"
        elif system_row is None:
            rule_selection_reason = "system_api_not_resolved"
        elif rule_match_count <= 0:
            rule_selection_reason = "no_rule_matched"
        else:
            rule_selection_reason = "rule_not_selected"

        audit_summary = {
            "api": {
                "system_api_id": int(system_row.id) if system_row else None,
                "provider": resolved_provider,
                "model": resolved_model,
                "pricing_source": api_pricing_source,
            },
            "rule": {
                "matched_rule_id": selected_rule_id,
                "matched_rule_name": selected_rule_name,
                "match_count": int(rule_match_count),
                "status": rule_selection_status,
                "reason": rule_selection_reason,
            },
        }

        payload = {
            "task_type": task_type,
            "provider": provider_text,
            "model": model_text,
            "resolved_provider": resolved_provider,
            "resolved_model": resolved_model,
            "phase": phase,
            "feature_cost": int(feature_cost),
            "api_cost": int(selected_api_cost),
            "api_cost_before_function": int(function_billing.get("api_cost_before") or selected_api_cost),
            "function_billing": function_billing,
            "total_cost": int(total_cost),
            "api_pricing": selected_api_cfg,
            "fallback_api_cost": int(api_cost_fallback),
            "api_pricing_source": api_pricing_source,
            "api_pricing_source_detail": api_pricing_source_detail,
            "system_api_id": int(system_row.id) if system_row else None,
            "matched_rule_id": selected_rule_id,
            "matched_rule_name": selected_rule_name,
            "matched_rule_ids": matched_rule_ids,
            "matched_rule_details": matched_rule_details,
            "selected_rule_detail": selected_rule_detail,
            "rule_match_count": int(rule_match_count),
            "rule_selection_status": rule_selection_status,
            "rule_selection_reason": rule_selection_reason,
            "audit_summary": audit_summary,
            "usage_metadata": BillingService._compact_usage_metadata_for_audit(usage),
            "minimum_charge": {
                "enabled": min_charge > 0,
                "required": int(min_charge),
                "applied": minimum_charge_applied,
                "delta": int(max(0, minimum_charge_delta)),
            },
            "used_reserved_fallback": used_reserved_fallback,
            "settlement_fallback_reason": (
                "reserved_cost_fallback"
                if used_reserved_fallback
                else ("no_rule_matched" if phase == "settle" and system_row is not None and selected_rule_id is None else None)
            ),
            "system_api_ref": {
                "id": int(system_row.id) if system_row else None,
                "category": str(getattr(system_row, "category", "") or "") if system_row else "",
                "provider": str(getattr(system_row, "provider", "") or "") if system_row else "",
                "model": str(getattr(system_row, "model", "") or "") if system_row else "",
            },
        }
        billing_process = BillingService._build_billing_process_snapshot(payload, phase=phase)
        payload["billing_process"] = billing_process
        compacted = BillingService._compact_audit_payload(payload)
        if isinstance(compacted, dict):
            # Keep slim process snapshot for estimate API responses.
            # Money-moving stages (reserve/settle/deduct) log once at their boundary —
            # do not log every estimate_cost_breakdown call (UI preview spam).
            compacted["billing_process"] = billing_process
            return compacted
        return {}

    _USAGE_STORAGE_KEEP_KEYS = {
        "input_tokens", "output_tokens", "total_tokens", "prompt_tokens", "completion_tokens",
        "width", "height", "pixels", "image_count", "duration_seconds", "duration", "fps",
        "input_duration_seconds", "input_duration", "aspect_ratio",
        "resolution", "resolution_tier", "has_video_input", "has_audio", "draft_mode",
        "use_prev_video", "estimation_method", "token_source", "billing_basis", "usage_source",
        "kie_credits_consumed", "credits_consumed", "creditsConsumed", "credits",
        "is_seedance_2", "is_seedance_video", "is_kie_provider", "generation_mode",
        "provider_task_id", "task_id", "taskId", "query_endpoint",
        "consumeMoney", "consumeCoins", "thirdPartyConsumeMoney",
        "taskCostTime", "provider_cost_time_seconds", "cost_time",
    }

    @staticmethod
    def _slim_usage_metadata_for_storage(usage: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Persist only billable usage scalars — no rate maps / nested estimate trees."""
        payload = usage if isinstance(usage, dict) else {}
        out: Dict[str, Any] = {}
        for key in BillingService._USAGE_STORAGE_KEEP_KEYS:
            if key not in payload or payload.get(key) in (None, ""):
                continue
            out[key] = payload.get(key)
        # Flatten nested provider_usage token/credit scalars once (no deep copy of raw task).
        nested = payload.get("provider_usage")
        if isinstance(nested, dict):
            for key in (
                "input_tokens", "output_tokens", "total_tokens", "completion_tokens",
                "creditsConsumed", "credits_consumed", "kie_credits_consumed", "credits",
                "consumeMoney", "consumeCoins", "thirdPartyConsumeMoney",
                "taskCostTime", "provider_cost_time_seconds", "cost_time",
                "provider_task_id", "task_id", "taskId", "query_endpoint",
            ):
                if out.get(key) in (None, "") and nested.get(key) not in (None, ""):
                    out[key] = nested.get(key)
                elif (
                    key in {"input_tokens", "output_tokens", "total_tokens", "completion_tokens",
                            "creditsConsumed", "credits_consumed", "kie_credits_consumed", "credits"}
                    and out.get(key) in (0, 0.0)
                    and nested.get(key) not in (None, "", 0, 0.0)
                ):
                    out[key] = nested.get(key)
        compacted = BillingService._compact_audit_payload(
            out,
            drop_zero_keys=BillingService._AUDIT_USAGE_DROP_ZERO_KEYS,
        )
        return compacted if isinstance(compacted, dict) else out

    @staticmethod
    def _slim_selected_rule_for_storage(rule: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Keep rule identity + pricing numbers; drop match_dimensions / rate matrices."""
        if not isinstance(rule, dict) or not rule:
            return {}
        pricing = rule.get("pricing") if isinstance(rule.get("pricing"), dict) else {}
        return BillingService._compact_audit_payload(
            {
                "id": rule.get("id"),
                "name": rule.get("name"),
                "priority": rule.get("priority"),
                "is_base_pricing": rule.get("is_base_pricing"),
                "pricing": {
                    "unit_type": pricing.get("unit_type"),
                    "cost": pricing.get("cost"),
                    "cost_input": pricing.get("cost_input"),
                    "cost_output": pricing.get("cost_output"),
                },
                "rule_charge_multiplier": rule.get("rule_charge_multiplier"),
                "runtime_price_multiplier": rule.get("runtime_price_multiplier"),
                "base_credit_source": rule.get("base_credit_source"),
                "computed_base_cost": rule.get("computed_base_cost"),
                "computed_cost": rule.get("computed_cost"),
            }
        )

    @staticmethod
    def _slim_source_detail_for_storage(detail: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(detail, dict) or not detail:
            return {}
        # Keep identifiers/reason only — drop embedded rate maps / adjustments trees.
        return BillingService._compact_audit_payload(
            {
                "rule_id": detail.get("rule_id") or detail.get("base_rule_id"),
                "rule_name": detail.get("rule_name") or detail.get("base_rule_name"),
                "base_rule_id": detail.get("base_rule_id"),
                "base_rule_name": detail.get("base_rule_name"),
                "reason": detail.get("reason"),
                "priority": detail.get("priority"),
            }
        )

    @staticmethod
    def _build_billing_audit_for_storage(
        breakdown: Optional[Dict[str, Any]],
        *,
        phase: str,
        task_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Single compact audit blob for TransactionAction.billing_metadata.

        Replaces the old duplicated trio: billing_breakdown + billing_trace + nested
        billing_process/usage/audit_summary copies.
        """
        breakdown = breakdown if isinstance(breakdown, dict) else {}
        selected = breakdown.get("selected_rule_detail") if isinstance(breakdown.get("selected_rule_detail"), dict) else {}
        function_billing = breakdown.get("function_billing") if isinstance(breakdown.get("function_billing"), dict) else {}
        process = breakdown.get("billing_process") if isinstance(breakdown.get("billing_process"), dict) else {}
        pricing = selected.get("pricing") if isinstance(selected.get("pricing"), dict) else {}
        minimum_charge = breakdown.get("minimum_charge") if isinstance(breakdown.get("minimum_charge"), dict) else {}

        minimum_payload = None
        if (
            bool(minimum_charge.get("applied"))
            or bool(minimum_charge.get("enabled"))
            or BillingService._to_int(minimum_charge.get("required"), 0) > 0
            or BillingService._to_int(minimum_charge.get("delta"), 0) > 0
        ):
            minimum_payload = {
                "enabled": bool(minimum_charge.get("enabled")),
                "required": BillingService._to_int(minimum_charge.get("required"), 0),
                "applied": bool(minimum_charge.get("applied")),
                "delta": max(0, BillingService._to_int(minimum_charge.get("delta"), 0)),
            }

        payload = {
            "phase": str(phase or "").strip() or None,
            "task_type": str(task_type or breakdown.get("task_type") or "").strip() or None,
            "logic_branch": process.get("logic_branch"),
            "provider": breakdown.get("resolved_provider") or breakdown.get("provider"),
            "model": breakdown.get("resolved_model") or breakdown.get("model"),
            "system_api_id": breakdown.get("system_api_id"),
            "matched_rule_id": breakdown.get("matched_rule_id"),
            "matched_rule_name": breakdown.get("matched_rule_name"),
            "rule_selection_status": breakdown.get("rule_selection_status"),
            "rule_selection_reason": breakdown.get("rule_selection_reason"),
            "api_pricing_source": breakdown.get("api_pricing_source"),
            "api_pricing_source_detail": BillingService._slim_source_detail_for_storage(
                breakdown.get("api_pricing_source_detail")
            ),
            "unit_type": pricing.get("unit_type") or process.get("unit_type"),
            "base_cost": selected.get("computed_base_cost") or process.get("base_cost"),
            "charge_multiplier": selected.get("rule_charge_multiplier") or process.get("charge_multiplier"),
            "runtime_price_multiplier": selected.get("runtime_price_multiplier") or process.get("runtime_price_multiplier"),
            "feature_cost": int(breakdown.get("feature_cost") or 0),
            "api_cost": int(breakdown.get("api_cost") or 0),
            "api_cost_before_function": int(
                breakdown.get("api_cost_before_function") or breakdown.get("api_cost") or 0
            ),
            "total_cost": int(breakdown.get("total_cost") or 0),
            "function_billing": {
                "applied": bool(function_billing.get("applied")),
                "multiplier": function_billing.get("function_multiplier"),
                "add_credits": function_billing.get("function_add_credits"),
                "source": function_billing.get("source"),
                "function_name": function_billing.get("function_name"),
            },
            "selected_rule": BillingService._slim_selected_rule_for_storage(selected),
            "minimum_charge": minimum_payload,
            "used_reserved_fallback": bool(breakdown.get("used_reserved_fallback")) or None,
            "settlement_fallback_reason": breakdown.get("settlement_fallback_reason"),
        }
        return BillingService._compact_audit_payload(
            payload,
            drop_zero_keys=BillingService._AUDIT_BREAKDOWN_DROP_ZERO_KEYS,
        )

    @staticmethod
    def _build_billing_breakdown_for_audit(breakdown: Dict[str, Any], *, phase: str) -> Dict[str, Any]:
        """Backward-compatible alias — storage now uses the slim unified audit."""
        return BillingService._build_billing_audit_for_storage(breakdown, phase=phase)

    @staticmethod
    def _build_billing_trace(
        breakdown: Dict[str, Any],
        *,
        task_type: str,
        provider: Optional[str],
        model: Optional[str],
        phase: str,
    ) -> Dict[str, Any]:
        """Deprecated duplicate of audit identity fields — return slim pointer only."""
        audit = BillingService._build_billing_audit_for_storage(
            breakdown,
            phase=phase,
            task_type=task_type,
        )
        return BillingService._compact_audit_payload(
            {
                "phase": audit.get("phase"),
                "task_type": audit.get("task_type") or str(task_type or "").strip() or None,
                "provider": audit.get("provider") or provider,
                "model": audit.get("model") or model,
                "system_api_id": audit.get("system_api_id"),
                "matched_rule_id": audit.get("matched_rule_id"),
                "matched_rule_name": audit.get("matched_rule_name"),
                "api_pricing_source": audit.get("api_pricing_source"),
            }
        )

    @staticmethod
    def _log_transaction_action(
        db: Session,
        *,
        user_id: int,
        stage: str,
        task_type: str,
        provider: Optional[str],
        model: Optional[str],
        project_id: Optional[int] = None,
        episode_id: Optional[int] = None,
        transaction_id: Optional[int] = None,
        reservation_tx_id: Optional[int] = None,
        settlement_tx_id: Optional[int] = None,
        system_api_id: Optional[int] = None,
        matched_rule_id: Optional[int] = None,
        reserved_cost: int = 0,
        actual_cost: int = 0,
        delta: int = 0,
        charged_amount: int = 0,
        refunded_amount: int = 0,
        outstanding_amount: int = 0,
        matched_rule_ids: Optional[List[int]] = None,
        usage_metadata: Optional[Dict[str, Any]] = None,
        billing_metadata: Optional[Dict[str, Any]] = None,
        breakdown: Optional[Dict[str, Any]] = None,
        phase: Optional[str] = None,
    ) -> None:
        # Prefer a single slim audit blob. If callers still pass nested
        # {"phase","breakdown":...}, unwrap and re-slim.
        meta_in = dict(billing_metadata or {}) if isinstance(billing_metadata, dict) else {}
        nested_breakdown = meta_in.get("breakdown") if isinstance(meta_in.get("breakdown"), dict) else None
        source_breakdown = breakdown if isinstance(breakdown, dict) else nested_breakdown
        stage_phase = str(phase or meta_in.get("phase") or "").strip() or None
        if source_breakdown is not None:
            slim_meta = BillingService._build_billing_audit_for_storage(
                source_breakdown,
                phase=stage_phase or str(stage or "").strip().lower() or "audit",
                task_type=task_type,
            )
        else:
            # Already a compact payload (cancel/refund) — strip known heavy nests.
            slim_meta = dict(meta_in)
            for heavy in (
                "breakdown", "billing_breakdown", "billing_trace", "billing_process",
                "usage_metadata", "matched_rule_details", "selected_rule_detail",
                "audit_summary", "reservation_billing_breakdown",
            ):
                slim_meta.pop(heavy, None)
            slim_meta = BillingService._compact_audit_payload(slim_meta)

        slim_usage = BillingService._slim_usage_metadata_for_storage(usage_metadata)
        # Avoid duplicating usage inside billing_metadata.
        if isinstance(slim_meta, dict):
            slim_meta.pop("usage", None)
            slim_meta.pop("usage_metadata", None)

        action = TransactionAction(
            user_id=int(user_id),
            project_id=project_id,
            episode_id=episode_id,
            transaction_id=transaction_id,
            reservation_tx_id=reservation_tx_id,
            settlement_tx_id=settlement_tx_id,
            stage=str(stage or "").strip().upper() or "UNKNOWN",
            task_type=str(task_type or "").strip(),
            provider=str(provider or "").strip() or None,
            model=str(model or "").strip() or None,
            system_api_id=system_api_id,
            matched_rule_id=matched_rule_id,
            reserved_cost=max(0, int(reserved_cost or 0)),
            actual_cost=max(0, int(actual_cost or 0)),
            delta=int(delta or 0),
            charged_amount=max(0, int(charged_amount or 0)),
            refunded_amount=max(0, int(refunded_amount or 0)),
            outstanding_amount=max(0, int(outstanding_amount or 0)),
            matched_rule_ids=list(matched_rule_ids or []),
            usage_metadata=slim_usage if isinstance(slim_usage, dict) else {},
            billing_metadata=slim_meta if isinstance(slim_meta, dict) else {},
        )
        db.add(action)

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
    def estimate_reserve_tokens_from_messages(
        messages: List[Dict[str, Any]],
        output_ratio: Optional[float] = None,
    ) -> Dict[str, int]:
        """Token estimate for LLM credit reservation (output assumed < input)."""
        ratio = (
            BillingService.RESERVE_OUTPUT_RATIO
            if output_ratio is None
            else float(output_ratio)
        )
        return BillingService.estimate_input_output_tokens_from_messages(
            messages,
            output_ratio=ratio,
        )

    @staticmethod
    def is_token_pricing(db: Session, task_type: str, provider: str = None, model: str = None) -> bool:
        api_cfg = BillingService._resolve_api_pricing_config(db, task_type, provider, model)
        if api_cfg:
            unit_type = str(api_cfg.get("unit_type", "per_call") or "per_call").strip()
            if unit_type in BillingService.TOKEN_UNIT_TYPES:
                return True
        return False

    # ── Video token estimation ──────────────────────────────────────
    # Ark Seedance 2.0 / video-token fallback:
    #   tokens = (W × H × fps × billable_duration) / 1024
    #   without video input: billable_duration = output_duration
    #   with video input:    billable_duration = input_duration + output_duration
    #   cost = token_unit_price × tokens

    @staticmethod
    def is_seedance_2_model(*identity_parts: Any) -> bool:
        """True when identity contains both 'seedance' and a '2' version marker."""
        text = " ".join(str(part or "") for part in identity_parts).strip().lower()
        if "seedance" not in text:
            return False
        if any(marker in text for marker in ("seedance-2", "seedance_2", "seedance2", "2.0", "2-0", "2_0")):
            return True
        # Loose fallback: seedance + standalone digit 2 (e.g. "seedance 2 pro")
        return bool(re.search(r"(^|[^0-9])2([^0-9]|$)", text))

    @staticmethod
    def _is_kie_provider(provider: Any) -> bool:
        provider_lower = str(provider or "").strip().lower()
        if not provider_lower:
            return False
        return (
            provider_lower == BillingService.KIE_STANDARD_PROVIDER
            or provider_lower.startswith(f"{BillingService.KIE_STANDARD_PROVIDER}/")
            or "kie.ai" in provider_lower
        )

    @staticmethod
    def _ensure_kie_seedance_second_matrix(usage: Dict[str, Any]) -> Dict[str, Any]:
        """
        KIE Seedance bills per-second by resolution matrix (CNY/s).
        When the selected rule has not persisted matrix extras yet, inject published defaults
        so estimate/reserve hit video_second_cny_kie instead of flat per_second / zero base cost.
        """
        payload = dict(usage or {})
        if not payload.get("is_seedance_video"):
            return payload
        if not (
            payload.get("is_kie_provider")
            or BillingService._is_kie_provider(payload.get("provider") or payload.get("resolved_provider"))
        ):
            return payload
        has_cny = isinstance(payload.get("video_second_cny_resolution_rates"), dict) and payload.get(
            "video_second_cny_resolution_rates"
        )
        has_kie = isinstance(payload.get("video_second_resolution_rates"), dict) and payload.get(
            "video_second_resolution_rates"
        )
        if has_cny or has_kie:
            return payload
        from app.services.billing_pricing import (
            DEFAULT_KIE_SEEDANCE_SECOND_CNY_RATES,
            normalize_sparkvideo_second_cny_rates,
        )
        injected = normalize_sparkvideo_second_cny_rates(DEFAULT_KIE_SEEDANCE_SECOND_CNY_RATES)
        if not injected:
            injected = dict(DEFAULT_KIE_SEEDANCE_SECOND_CNY_RATES)
        payload["video_second_cny_resolution_rates"] = injected
        payload["estimation_method"] = "video_second_cny_kie"
        payload["kie_seedance_default_matrix"] = True
        # Never let Ark token formula tags leak into KIE Seedance second billing.
        payload.pop("video_token_estimate", None)
        payload.pop("video_token_branch", None)
        return payload

    @staticmethod
    def resolve_has_video_input(usage: Optional[Dict[str, Any]] = None) -> bool:
        payload = dict(usage or {})
        if payload.get("has_video_input") is True:
            return True
        if payload.get("has_video_input") is False:
            return False
        if bool(payload.get("use_prev_video") or payload.get("shot_continuation")):
            return True
        for key in ("reference_video_count", "resolved_reference_video_count", "ref_video_count"):
            if BillingService._to_int(payload.get(key), 0) > 0:
                return True
        for key in ("reference_video_urls", "ref_video_urls"):
            value = payload.get(key)
            if isinstance(value, (list, tuple)) and len(value) > 0:
                return True
        if BillingService._safe_float(payload.get("input_duration_seconds"), 0.0) > 0:
            return True
        return False

    @staticmethod
    def estimate_video_token_usage(
        width: int = 1280,
        height: int = 720,
        fps: int = 24,
        output_duration_seconds: float = 5.0,
        *,
        has_video_input: bool = False,
        input_duration_seconds: Optional[float] = None,
        draft_token_coefficient: float = 1.0,
        method: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Estimate video tokens via Ark Seedance 2.0 / video-token fallback formula.

        draft_token_coefficient is ignored (always 1.0); draft no longer discounts tokens.
        """
        _ = draft_token_coefficient  # retired discount; callers may still pass legacy values
        w = max(1, int(width or 1))
        h = max(1, int(height or 1))
        f = max(1, int(fps or 1))
        out_d = max(0.0, float(output_duration_seconds or 0.0))
        in_d = 0.0
        if has_video_input:
            parsed_in = BillingService._safe_float(input_duration_seconds, 0.0)
            # When input duration is unknown, use output duration as reserve proxy.
            in_d = parsed_in if parsed_in > 0 else out_d
        billable_duration = (out_d + in_d) if has_video_input else out_d
        if billable_duration <= 0:
            return {
                "tokens": 0,
                "width": w,
                "height": h,
                "fps": f,
                "output_duration_seconds": out_d,
                "input_duration_seconds": in_d,
                "billable_duration_seconds": 0.0,
                "has_video_input": bool(has_video_input),
                "estimation_method": method or "video_token_formula",
                "formula": "(width * height * fps * billable_duration) / 1024",
            }

        raw = (float(w) * float(h) * float(f) * float(billable_duration)) / 1024.0
        tokens = max(1, int(math.ceil(raw))) if raw > 0 else 0
        return {
            "tokens": tokens,
            "width": w,
            "height": h,
            "fps": f,
            "output_duration_seconds": out_d,
            "input_duration_seconds": in_d,
            "billable_duration_seconds": float(billable_duration),
            "has_video_input": bool(has_video_input),
            "draft_token_coefficient": 1.0,
            "estimation_method": method or ("seedance2_video_token_formula" if has_video_input else "video_token_formula"),
            "formula": "(width * height * fps * (input+output duration)) / 1024" if has_video_input else "(width * height * fps * output_duration) / 1024",
        }

    @staticmethod
    def estimate_video_output_tokens(
        width: int = 1280,
        height: int = 720,
        fps: int = 24,
        duration_seconds: float = 5.0,
        draft_token_coefficient: float = 1.0,
        *,
        has_video_input: bool = False,
        input_duration_seconds: Optional[float] = None,
        method: Optional[str] = None,
    ) -> int:
        """
        Estimate video tokens (Seedance 2.0 / video-token fallback).

        Without video input:
          ceil(width × height × fps × output_duration / 1024)
        With video input:
          ceil(width × height × fps × (input_duration + output_duration) / 1024)
        """
        estimated = BillingService.estimate_video_token_usage(
            width=width,
            height=height,
            fps=fps,
            output_duration_seconds=duration_seconds,
            has_video_input=has_video_input,
            input_duration_seconds=input_duration_seconds,
            draft_token_coefficient=draft_token_coefficient,
            method=method,
        )
        return int(estimated.get("tokens") or 0)

    @staticmethod
    def resolve_video_token_config(
        db: Session,
        provider: str,
        model: str,
    ) -> Dict[str, Any]:
        """
        Resolve video-token estimation parameters from SystemAPISetting.config.video_token_defaults.
        Returns dict with keys: default_width, default_height, default_fps, draft_token_coefficient.
        """
        provider_text = str(provider or "").strip()
        model_text = str(model or "").strip()
        row = None
        if provider_text and model_text:
            row = BillingService._system_setting_query(db).filter(
                SystemAPISetting.category == "Video",
                SystemAPISetting.provider == provider_text,
                SystemAPISetting.model == model_text,
            ).order_by(SystemAPISetting.id.desc()).first()
        if not row and provider_text:
            row = BillingService._system_setting_query(db).filter(
                SystemAPISetting.category == "Video",
                SystemAPISetting.provider == provider_text,
            ).order_by(SystemAPISetting.id.desc()).first()

        defaults = {
            "default_width": 1280,
            "default_height": 720,
            "default_fps": 24,
            "draft_token_coefficient": 1.0,
            "is_seedance_2": BillingService.is_seedance_2_model(provider_text, model_text, getattr(row, "name", "") if row else ""),
            "video_token_branch": "seedance2" if BillingService.is_seedance_2_model(provider_text, model_text, getattr(row, "name", "") if row else "") else "fallback",
        }
        if row:
            defaults["is_seedance_2"] = BillingService.is_seedance_2_model(
                provider_text, model_text, getattr(row, "name", "")
            )
            defaults["video_token_branch"] = "seedance2" if defaults["is_seedance_2"] else "fallback"

        if not row:
            return defaults

        cfg = BillingService._safe_json_dict(row.config)
        vtd = cfg.get("video_token_defaults")
        if not isinstance(vtd, dict):
            return defaults

        try:
            defaults["default_width"] = max(1, int(vtd.get("width", 1280)))
        except Exception:
            pass
        try:
            defaults["default_height"] = max(1, int(vtd.get("height", 720)))
        except Exception:
            pass
        try:
            defaults["default_fps"] = max(1, int(vtd.get("fps", 24)))
        except Exception:
            pass
        # Draft token discount retired; keep key for callers but always 1.0.
        defaults["draft_token_coefficient"] = 1.0
        return defaults

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

        reserve_breakdown = BillingService.estimate_cost_breakdown(
            db,
            task_type,
            provider,
            model,
            details=reserve_details,
            phase="reserve",
        )
        reserved_cost = int(reserve_breakdown.get("total_cost") or 0)
        BillingService.check_can_proceed(user, reserved_cost, db=db, project_id=details.get("project_id") if details else None)
        resolved_provider = reserve_breakdown.get("resolved_provider") or provider
        resolved_model = reserve_breakdown.get("resolved_model") or model

        selected_rule_detail = reserve_breakdown.get("selected_rule_detail") if isinstance(reserve_breakdown.get("selected_rule_detail"), dict) else {}
        reserve_details.update({
            "resolved_provider": reserve_breakdown.get("resolved_provider"),
            "resolved_model": reserve_breakdown.get("resolved_model"),
            "matched_rule_id": reserve_breakdown.get("matched_rule_id"),
            "matched_rule_name": reserve_breakdown.get("matched_rule_name"),
            "system_api_id": reserve_breakdown.get("system_api_id"),
            "pricing_program": BillingService._slim_pricing_program_for_history(
                breakdown=reserve_breakdown,
                selected_rule_detail=selected_rule_detail,
            ),
        })
        reserve_details = BillingService._promote_media_context_for_history(
            reserve_details,
            usage=reserve_breakdown.get("usage_metadata") if isinstance(reserve_breakdown.get("usage_metadata"), dict) else None,
        )

        project_id = reserve_details.get("project_id")
        group = None
        allocation = None
        billed_group_credits = 0
        billed_personal_credits = 0
        can_use_group_credits = False

        if user.current_group_id:
            group = db.query(UserGroup).filter(UserGroup.id == user.current_group_id).first()
            can_use_group_credits = BillingService._group_allows_credit_billing(group)
            if can_use_group_credits and project_id:
                allocation = db.query(ProjectGroupCreditAllocation).filter(
                    ProjectGroupCreditAllocation.group_id == group.id,
                    ProjectGroupCreditAllocation.project_id == project_id
                ).first()
                if allocation and allocation.credit_limit != -1:
                    if (allocation.used_credits or 0) + reserved_cost > allocation.credit_limit:
                        raise HTTPException(status_code=402, detail="Project group credit allocation exceeded.")
                        
        remaining_cost = reserved_cost
        if can_use_group_credits and group and (group.credits or 0) > 0 and remaining_cost > 0:
            if group.credits >= remaining_cost:
                billed_group_credits = remaining_cost
                group.credits -= remaining_cost
                remaining_cost = 0
            else:
                billed_group_credits = group.credits
                remaining_cost -= group.credits
                group.credits = 0

        if remaining_cost > 0:
            if (user.credits or 0) < remaining_cost:
                 raise HTTPException(status_code=402, detail="Insufficient personal credits.")
            billed_personal_credits = remaining_cost
            user.credits -= remaining_cost

        if allocation and reserved_cost > 0:
            allocation.used_credits = (allocation.used_credits or 0) + reserved_cost

        reserve_details["billed_group_credits"] = billed_group_credits
        reserve_details["billed_personal_credits"] = billed_personal_credits
        reserve_details["reserved_cost"] = reserved_cost
        if group:
            reserve_details["group_id"] = group.id
            reserve_details["allow_group_credit_billing"] = can_use_group_credits
        reserve_details = BillingService._attach_balance_snapshots(
            reserve_details, user=user, group=group if can_use_group_credits else None
        )
        reserve_details = BillingService._compact_history_ledger_details(reserve_details)

        tx = TransactionHistory(
            user_id=user_id,
            amount=-reserved_cost,
            balance_after=user.credits or 0,
            description=reserve_details.get("description", task_type),
            details=reserve_details,
            project_id=reserve_details.get("project_id"),
            episode_id=reserve_details.get("episode_id"),
        )
        db.add(tx)
        db.flush()
        BillingService._log_transaction_action(
            db,
            user_id=user_id,
            stage="RESERVED",
            task_type=task_type,
            provider=resolved_provider,
            model=resolved_model,
            project_id=reserve_details.get("project_id"),
            episode_id=reserve_details.get("episode_id"),
            transaction_id=tx.id,
            reservation_tx_id=tx.id,
            system_api_id=reserve_breakdown.get("system_api_id"),
            matched_rule_id=reserve_breakdown.get("matched_rule_id"),
            reserved_cost=reserved_cost,
            actual_cost=0,
            delta=0,
            charged_amount=reserved_cost,
            refunded_amount=0,
            outstanding_amount=0,
            matched_rule_ids=reserve_breakdown.get("matched_rule_ids") or [],
            usage_metadata=reserve_breakdown.get("usage_metadata") or {},
            breakdown=reserve_breakdown,
            phase="reserve",
        )
        db.commit()
        db.refresh(tx)
        process_snapshot = reserve_breakdown.get("billing_process") if isinstance(reserve_breakdown.get("billing_process"), dict) else {}
        if not process_snapshot:
            process_snapshot = BillingService._build_billing_process_snapshot(reserve_breakdown, phase="reserve")
        BillingService._log_billing_process(
            {
                **process_snapshot,
                "user_id": user_id,
                "reservation_tx_id": int(getattr(tx, "id", 0) or 0) or None,
            },
            context=f"reserve:{task_type}",
        )
        return tx

    @staticmethod
    def cancel_reservation(
        db: Session,
        reservation_tx_id: int,
        error_msg: str = None,
        usage_metadata: Optional[Dict[str, Any]] = None,
        extra_details: Optional[Dict[str, Any]] = None,
    ) -> Optional[TransactionHistory]:
        """Refunds a reservation when an upstream call fails."""
        tx = db.query(TransactionHistory).filter(TransactionHistory.id == reservation_tx_id).first()
        if not tx:
            return None

        if tx.amount >= 0:
            return tx

        user = db.query(User).filter(User.id == tx.user_id).first()
        if not user:
            return tx

        tx_action = db.query(TransactionAction).filter(TransactionAction.transaction_id == tx.id).order_by(TransactionAction.id.desc()).first()
        tx_task_type = tx_action.task_type if tx_action else ""
        tx_provider = tx_action.provider if tx_action else ""
        tx_model = tx_action.model if tx_action else ""

        reserved_cost = int(abs(tx.amount))
        tx_details_dict = dict(tx.details or {}) if isinstance(tx.details, dict) else {}
        billed_group_credits = max(0, BillingService._to_int(tx_details_dict.get("billed_group_credits", 0), 0))
        billed_personal_credits = max(0, BillingService._to_int(tx_details_dict.get("billed_personal_credits", 0), 0))
        group_id = BillingService._to_int(tx_details_dict.get("group_id", 0), 0)
        project_id = tx_details_dict.get("project_id") or (tx_action.project_id if tx_action else None)
        slim_usage = BillingService._slim_usage_metadata_for_storage(usage_metadata)
        cancel_extra = dict(extra_details or {}) if isinstance(extra_details, dict) else {}

        # Restore group/personal split using reserve-time metadata when available.
        restored_group = 0
        restored_personal = 0
        if billed_group_credits > 0 or billed_personal_credits > 0:
            if billed_group_credits > 0 and group_id > 0:
                group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
                if group:
                    group.credits = (group.credits or 0) + billed_group_credits
                    restored_group = billed_group_credits
            if billed_personal_credits > 0:
                user.credits = (user.credits or 0) + billed_personal_credits
                restored_personal = billed_personal_credits
            # Fallback remainder (legacy reservations without split metadata).
            remainder = reserved_cost - restored_group - restored_personal
            if remainder > 0:
                user.credits = (user.credits or 0) + remainder
                restored_personal += remainder
        else:
            user.credits = (user.credits or 0) + reserved_cost
            restored_personal = reserved_cost

        if project_id and group_id > 0 and reserved_cost > 0:
            allocation = db.query(ProjectGroupCreditAllocation).filter(
                ProjectGroupCreditAllocation.group_id == group_id,
                ProjectGroupCreditAllocation.project_id == project_id,
            ).first()
            if allocation:
                allocation.used_credits = max(0, (allocation.used_credits or 0) - reserved_cost)

        refund_group = None
        if group_id > 0:
            refund_group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
        refund_details = {
            "status": "REFUND",
            "reason": "RESERVATION_CANCELED",
            "reservation_tx_id": tx.id,
            "refunded_group_credits": restored_group,
            "refunded_personal_credits": restored_personal,
            "group_id": group_id or None,
            "system_api_id": tx_details_dict.get("system_api_id"),
            "matched_rule_id": tx_details_dict.get("matched_rule_id"),
            "matched_rule_name": tx_details_dict.get("matched_rule_name"),
        }
        if error_msg:
            refund_details["error"] = str(error_msg)[:500]
        for copy_key in (
            "consumeCoins",
            "consumeMoney",
            "thirdPartyConsumeMoney",
            "taskCostTime",
            "provider_cost_time_seconds",
            "cost_time",
            "usage_source",
        ):
            value = cancel_extra.get(copy_key)
            if value in (None, ""):
                value = slim_usage.get(copy_key) if isinstance(slim_usage, dict) else None
            if value not in (None, ""):
                refund_details[copy_key] = value
        refund_details = BillingService._promote_media_context_for_history(
            refund_details,
            usage=slim_usage if isinstance(slim_usage, dict) else None,
        )
        refund_details = BillingService._attach_balance_snapshots(
            refund_details, user=user, group=refund_group
        )
        refund_details = BillingService._compact_history_ledger_details(refund_details)

        refund_tx = TransactionHistory(
            user_id=tx.user_id,
            amount=reserved_cost,
            balance_after=user.credits or 0,
            description=f"Refund for {tx.description or 'task'}",
            details=refund_details,
            project_id=tx_action.project_id if tx_action else None,
            episode_id=tx_action.episode_id if tx_action else None,
        )
        db.add(refund_tx)
        db.flush()

        BillingService._log_transaction_action(
            db,
            user_id=tx.user_id,
            stage="CANCELED",
            task_type=tx_task_type,
            provider=tx_provider,
            model=tx_model,
            project_id=tx_action.project_id if tx_action else None,
            episode_id=tx_action.episode_id if tx_action else None,
            transaction_id=tx.id,
            reservation_tx_id=tx.id,
            settlement_tx_id=refund_tx.id,
            system_api_id=BillingService._to_int(tx_details_dict.get("system_api_id"), 0) or None,
            matched_rule_id=BillingService._to_int(tx_details_dict.get("matched_rule_id"), 0) or None,
            reserved_cost=reserved_cost,
            actual_cost=0,
            delta=-reserved_cost,
            charged_amount=0,
            refunded_amount=reserved_cost,
            outstanding_amount=0,
            matched_rule_ids=[],
            usage_metadata=slim_usage if isinstance(slim_usage, dict) else {},
            billing_metadata={
                "phase": "cancel",
                "reason": "RESERVATION_CANCELED",
                "refunded_group_credits": restored_group,
                "refunded_personal_credits": restored_personal,
                "system_api_id": tx_details_dict.get("system_api_id"),
                "matched_rule_id": tx_details_dict.get("matched_rule_id"),
                "matched_rule_name": tx_details_dict.get("matched_rule_name"),
                **{
                    k: cancel_extra.get(k)
                    for k in (
                        "consumeCoins",
                        "consumeMoney",
                        "thirdPartyConsumeMoney",
                        "taskCostTime",
                        "provider_cost_time_seconds",
                        "usage_source",
                    )
                    if cancel_extra.get(k) not in (None, "")
                },
            },
            phase="cancel",
        )

        tx_details = dict(tx.details or {})
        tx_details["status"] = "CANCELED"
        tx_details["refund_tx_id"] = refund_tx.id  # may be None until commit
        if error_msg:
            tx_details["error"] = str(error_msg)[:500]
        for copy_key in (
            "consumeCoins",
            "consumeMoney",
            "thirdPartyConsumeMoney",
            "taskCostTime",
            "provider_cost_time_seconds",
            "cost_time",
            "usage_source",
        ):
            value = cancel_extra.get(copy_key)
            if value in (None, ""):
                value = slim_usage.get(copy_key) if isinstance(slim_usage, dict) else None
            if value not in (None, ""):
                tx_details[copy_key] = value
        tx_details = BillingService._promote_media_context_for_history(
            tx_details,
            usage=slim_usage if isinstance(slim_usage, dict) else None,
        )
        tx.details = BillingService._compact_history_ledger_details(tx_details)

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

        res_action = db.query(TransactionAction).filter(TransactionAction.transaction_id == reservation_tx.id).order_by(TransactionAction.id.desc()).first()
        res_task_type = res_action.task_type if res_action else ""
        res_provider = res_action.provider if res_action else ""
        res_model = res_action.model if res_action else ""
        res_details_dict = dict(reservation_tx.details or {}) if isinstance(reservation_tx.details, dict) else {}

        # Prefer original reserved_cost from details/action — amount may already be rewritten to actual.
        reserved_cost = BillingService._to_int(res_details_dict.get("reserved_cost"), 0)
        if reserved_cost <= 0 and res_action is not None:
            reserved_cost = BillingService._to_int(getattr(res_action, "reserved_cost", 0), 0)
        if reserved_cost <= 0:
            reserved_cost = int(abs(reservation_tx.amount or 0))
        if str(res_details_dict.get("status") or "").strip().upper() == "SETTLED":
            return {
                "reserved_cost": reserved_cost,
                "actual_cost": BillingService._to_int(res_details_dict.get("actual_cost"), reserved_cost),
                "delta": BillingService._to_int(res_details_dict.get("delta"), 0),
                "reservation_tx_id": reservation_tx.id,
                "settlement_tx_id": res_details_dict.get("settlement_tx_id"),
                "already_settled": True,
            }

        details = BillingService.ensure_provider_task_ids(dict(actual_details or {}))
        details.setdefault("billing_mode", "ACTUAL")
        smart_routing = details.get("smart_routing") if isinstance(details.get("smart_routing"), dict) else {}
        settle_provider = str(
            details.get("provider")
            or details.get("resolved_provider")
            or smart_routing.get("provider")
            or res_provider
            or ""
        ).strip() or None
        settle_model = str(
            details.get("model")
            or details.get("resolved_model")
            or smart_routing.get("model")
            or res_model
            or ""
        ).strip() or None

        # Normalize usage keys
        if "input_tokens" not in details and "prompt_tokens" in details:
            details["input_tokens"] = details.get("prompt_tokens", 0)
        if "output_tokens" not in details and "completion_tokens" in details:
            details["output_tokens"] = details.get("completion_tokens", 0)

        # Fallback input_tokens from reservation if missing
        # res_details_dict already loaded above
        missing_input = BillingService._to_int(details.get("input_tokens", 0), 0) <= 0
        missing_output = BillingService._to_int(details.get("output_tokens", 0), 0) <= 0

        if missing_input:
            reserved_input = BillingService._to_int(res_details_dict.get("input_tokens", 0), 0)
            if reserved_input > 0:
                details["input_tokens"] = reserved_input

        # Infer output_tokens: if we have total_tokens but no output_tokens
        total_toks = BillingService._to_int(details.get("total_tokens", 0), 0)
        in_toks = BillingService._to_int(details.get("input_tokens", 0), 0)
        
        if missing_output and total_toks > 0 and in_toks > 0:
            if total_toks >= in_toks:
                details["output_tokens"] = total_toks - in_toks
            else:
                # Proxy anomalous case: total_tokens < input_tokens
                details["input_tokens"] = total_toks
                details["output_tokens"] = 0

        breakdown = BillingService.estimate_cost_breakdown(
            db,
            res_task_type,
            settle_provider,
            settle_model,
            details=details,
            phase="settle",
            reserved_cost_fallback=reserved_cost,
        )
        usage_meta = dict(breakdown.get("usage_metadata") or {}) if isinstance(breakdown.get("usage_metadata"), dict) else {}
        usage_meta = BillingService.ensure_provider_task_ids({**usage_meta, **details})
        breakdown["usage_metadata"] = usage_meta
        settle_provider = str(breakdown.get("provider") or settle_provider or res_provider or "").strip() or None
        settle_model = str(breakdown.get("model") or settle_model or res_model or "").strip() or None
        actual_cost = int(breakdown.get("total_cost") or 0)

        delta = int(actual_cost - reserved_cost)
        settlement_tx = None
        outstanding = 0
        charged_amount = 0
        refunded_amount = 0

        settle_group = None
        settle_group_id = BillingService._to_int(res_details_dict.get("group_id"), 0)
        if settle_group_id > 0:
            settle_group = db.query(UserGroup).filter(UserGroup.id == settle_group_id).first()

        wallet_split = BillingService._reserve_wallet_split(res_details_dict, reserved_cost)
        billed_group_credits = wallet_split["billed_group_credits"]
        billed_personal_credits = wallet_split["billed_personal_credits"]
        refunded_group_credits = 0
        refunded_personal_credits = 0
        charged_group_credits = 0
        charged_personal_credits = 0
        final_group_credits = min(actual_cost, billed_group_credits) if delta <= 0 else billed_group_credits
        final_personal_credits = max(0, actual_cost - final_group_credits) if delta <= 0 else billed_personal_credits

        project_id_for_alloc = (
            res_details_dict.get("project_id")
            or (res_action.project_id if res_action else None)
            or getattr(reservation_tx, "project_id", None)
        )

        if delta < 0:
            refund = -delta
            refund_split = BillingService._settle_refund_split(
                refund=refund,
                billed_group_credits=billed_group_credits,
                billed_personal_credits=billed_personal_credits,
                actual_cost=actual_cost,
            )
            refunded_group_credits = refund_split["refund_group_credits"]
            refunded_personal_credits = refund_split["refund_personal_credits"]
            final_group_credits = refund_split["final_group_credits"]
            final_personal_credits = refund_split["final_personal_credits"]

            if refunded_group_credits > 0:
                if settle_group is None and settle_group_id > 0:
                    settle_group = db.query(UserGroup).filter(UserGroup.id == settle_group_id).first()
                if settle_group is not None:
                    settle_group.credits = (settle_group.credits or 0) + refunded_group_credits
                else:
                    # Group missing: fall back to personal so credits are not lost.
                    logger.warning(
                        "Settlement refund group_id=%s missing; returning %s credits to personal",
                        settle_group_id,
                        refunded_group_credits,
                    )
                    refunded_personal_credits += refunded_group_credits
                    refunded_group_credits = 0

            if refunded_personal_credits > 0:
                user.credits = (user.credits or 0) + refunded_personal_credits

            if project_id_for_alloc and settle_group_id > 0 and refund > 0:
                allocation = db.query(ProjectGroupCreditAllocation).filter(
                    ProjectGroupCreditAllocation.group_id == settle_group_id,
                    ProjectGroupCreditAllocation.project_id == project_id_for_alloc,
                ).first()
                if allocation:
                    allocation.used_credits = max(0, (allocation.used_credits or 0) - refund)

            settlement_tx = TransactionHistory(
                user_id=user.id,
                # Net cost is rewritten onto the reservation row; keep adjustment amount=0
                # so ledger SUM(amount) is not double-counted.
                amount=0,
                balance_after=user.credits or 0,
                description=f"Partial refund for {reservation_tx.description or 'task'}",
                details=BillingService._attach_balance_snapshots(
                    {
                        "status": "REFUND",
                        "reason": "RESERVATION_SETTLEMENT",
                        "ledger_role": "settlement_adjustment",
                        "hide_in_history": True,
                        "wallet_delta": refund,
                        "reservation_tx_id": reservation_tx.id,
                        "reserved_cost": reserved_cost,
                        "actual_cost": actual_cost,
                        "group_id": settle_group_id or None,
                        "refunded_group_credits": refunded_group_credits,
                        "refunded_personal_credits": refunded_personal_credits,
                        "final_group_credits": final_group_credits,
                        "final_personal_credits": final_personal_credits,
                    },
                    user=user,
                    group=settle_group,
                ),
                project_id=res_action.project_id if res_action else None,
                episode_id=res_action.episode_id if res_action else None,
            )
            db.add(settlement_tx)
            refunded_amount = refund
        elif delta > 0:
            extra = delta
            remaining_extra = extra
            # Extra settle charge follows reserve priority when group billing was used / allowed.
            can_use_group = (
                settle_group is not None
                and (
                    billed_group_credits > 0
                    or BillingService._group_allows_credit_billing(settle_group)
                )
            )
            if can_use_group and remaining_extra > 0 and (settle_group.credits or 0) > 0:
                take_group = min(int(settle_group.credits or 0), remaining_extra)
                settle_group.credits = int(settle_group.credits or 0) - take_group
                charged_group_credits = take_group
                remaining_extra -= take_group

            take_personal = min(int(user.credits or 0), remaining_extra)
            if take_personal > 0:
                user.credits = int(user.credits or 0) - take_personal
                charged_personal_credits = take_personal
                remaining_extra -= take_personal

            charged_amount = charged_group_credits + charged_personal_credits
            final_group_credits = billed_group_credits + charged_group_credits
            final_personal_credits = billed_personal_credits + charged_personal_credits

            if charged_amount > 0:
                if project_id_for_alloc and settle_group_id > 0 and charged_group_credits > 0:
                    allocation = db.query(ProjectGroupCreditAllocation).filter(
                        ProjectGroupCreditAllocation.group_id == settle_group_id,
                        ProjectGroupCreditAllocation.project_id == project_id_for_alloc,
                    ).first()
                    if allocation and allocation.credit_limit != -1:
                        # Soft-track usage; do not block settle mid-flight.
                        allocation.used_credits = (allocation.used_credits or 0) + charged_group_credits
                    elif allocation:
                        allocation.used_credits = (allocation.used_credits or 0) + charged_group_credits

                settlement_tx = TransactionHistory(
                    user_id=user.id,
                    # Net cost is rewritten onto the reservation row; keep adjustment amount=0
                    # so ledger SUM(amount) is not double-counted.
                    amount=0,
                    balance_after=user.credits or 0,
                    description=f"Extra charge for {reservation_tx.description or 'task'}",
                    details=BillingService._attach_balance_snapshots(
                        {
                            "status": "CHARGE",
                            "reason": "RESERVATION_SETTLEMENT",
                            "ledger_role": "settlement_adjustment",
                            "hide_in_history": True,
                            "wallet_delta": -charged_amount,
                            "reservation_tx_id": reservation_tx.id,
                            "reserved_cost": reserved_cost,
                            "actual_cost": actual_cost,
                            "delta": delta,
                            "group_id": settle_group_id or None,
                            "billed_group_credits": charged_group_credits,
                            "billed_personal_credits": charged_personal_credits,
                            "final_group_credits": final_group_credits,
                            "final_personal_credits": final_personal_credits,
                        },
                        user=user,
                        group=settle_group,
                    ),
                    project_id=res_action.project_id if res_action else None,
                    episode_id=res_action.episode_id if res_action else None,
                )
                db.add(settlement_tx)

            outstanding = remaining_extra
            if outstanding > 0:
                logger.warning(
                    f"User {user.id} could not cover settlement delta={extra}. outstanding={outstanding}"
                )

        # Update reservation details for audit
        res_details = dict(reservation_tx.details or {})
        res_details["status"] = "SETTLED"
        # Always flip billing_mode off RESERVE so UI/history don't look "unsettled".
        settle_billing_mode = str(details.get("billing_mode") or "").strip().upper()
        if settle_billing_mode in {"", "RESERVE", "RESERVED"}:
            settle_billing_mode = "ACTUAL"
        res_details["billing_mode"] = settle_billing_mode
        res_details["reserved_cost"] = reserved_cost
        res_details["actual_cost"] = actual_cost
        res_details["delta"] = delta
        res_details["billed_group_credits"] = billed_group_credits
        res_details["billed_personal_credits"] = billed_personal_credits
        res_details["final_group_credits"] = final_group_credits
        res_details["final_personal_credits"] = final_personal_credits
        if refunded_group_credits or refunded_personal_credits:
            res_details["refunded_group_credits"] = refunded_group_credits
            res_details["refunded_personal_credits"] = refunded_personal_credits
        if charged_group_credits or charged_personal_credits:
            res_details["settlement_charged_group_credits"] = charged_group_credits
            res_details["settlement_charged_personal_credits"] = charged_personal_credits
        if outstanding > 0:
            res_details["outstanding_delta"] = outstanding

        if settlement_tx is not None:
            # Will be populated after commit/refresh, but keep placeholder for clarity.
            res_details["settlement_tx_id"] = None

        # Add actual usage details — keep history row lean (full audit lives on TransactionAction).
        selected_rule_detail = breakdown.get("selected_rule_detail") if isinstance(breakdown.get("selected_rule_detail"), dict) else {}
        res_details.update({
            "resolved_provider": settle_provider,
            "resolved_model": settle_model,
            "matched_rule_id": breakdown.get("matched_rule_id"),
            "matched_rule_name": breakdown.get("matched_rule_name"),
            "system_api_id": breakdown.get("system_api_id"),
            "actual_input_tokens": int(details.get("input_tokens", 0) or 0),
            "actual_output_tokens": int(details.get("output_tokens", 0) or 0),
            "actual_total_tokens": int(details.get("total_tokens", 0) or 0),
            "pricing_program": BillingService._slim_pricing_program_for_history(
                breakdown=breakdown,
                selected_rule_detail=selected_rule_detail,
            ),
        })
        # Persist settle-time quantity markers used by UI / audits (scalars only).
        for copy_key in (
            "item",
            "image_count",
            "token_source",
            "billing_basis",
            "kie_credits_consumed",
            "credits_consumed",
            "creditsConsumed",
            "completion_tokens",
            "width",
            "height",
            "fps",
            "resolution",
            "resolution_tier",
            "aspect_ratio",
            "duration",
            "duration_seconds",
            "input_duration_seconds",
            "input_duration",
            "has_video_input",
            "use_prev_video",
            "draft_mode",
            "generation_mode",
            "usage_source",
            "provider_task_id",
            "task_id",
            "taskId",
            "query_endpoint",
            "provider_cost_time_seconds",
            "cost_time",
            "taskCostTime",
            "consumeCoins",
            "consumeMoney",
            "thirdPartyConsumeMoney",
            "provider_create_time_ms",
            "provider_complete_time_ms",
        ):
            if details.get(copy_key) not in (None, ""):
                res_details[copy_key] = details.get(copy_key)
        res_details = BillingService._promote_media_context_for_history(
            res_details,
            usage=breakdown.get("usage_metadata") if isinstance(breakdown.get("usage_metadata"), dict) else None,
        )
        # Do not store provider_usage / usage_metadata trees on history — they live on TransactionAction.
        # Rewrite ledger amount to actual user charge (supplier × multiplier), not reserve estimate.
        reservation_tx.amount = -int(max(0, actual_cost))
        res_details = BillingService._attach_balance_snapshots(
            res_details, user=user, group=settle_group
        )
        res_details = BillingService._compact_history_ledger_details(res_details)
        reservation_tx.details = res_details
        reservation_tx.balance_after = user.credits or 0
        res_provider = settle_provider
        res_model = settle_model

        if settlement_tx is not None:
            db.flush()

        BillingService._log_transaction_action(
            db,
            user_id=user.id,
            stage="SETTLED",
            task_type=res_task_type,
            provider=settle_provider,
            model=settle_model,
            project_id=res_action.project_id if res_action else None,
            episode_id=res_action.episode_id if res_action else None,
            transaction_id=reservation_tx.id,
            reservation_tx_id=reservation_tx.id,
            settlement_tx_id=settlement_tx.id if settlement_tx else None,
            system_api_id=breakdown.get("system_api_id"),
            matched_rule_id=breakdown.get("matched_rule_id"),
            reserved_cost=reserved_cost,
            actual_cost=actual_cost,
            delta=delta,
            charged_amount=charged_amount,
            refunded_amount=refunded_amount,
            outstanding_amount=outstanding,
            matched_rule_ids=breakdown.get("matched_rule_ids") or [],
            usage_metadata=breakdown.get("usage_metadata") or {},
            breakdown=breakdown,
            phase="settle",
        )

        process_snapshot = breakdown.get("billing_process") if isinstance(breakdown.get("billing_process"), dict) else {}
        if not process_snapshot:
            process_snapshot = BillingService._build_billing_process_snapshot(breakdown, phase="settle")
        BillingService._log_billing_process(
            {
                **process_snapshot,
                "total_cost": actual_cost,
                "user_id": user.id,
                "reservation_tx_id": reservation_tx.id,
            },
            context=f"settle:{res_task_type}:delta={delta}",
        )

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
        breakdown = BillingService.estimate_cost_breakdown(
            db,
            task_type,
            provider,
            model,
            details=details,
            phase="reserve",
        )
        return int(max(0, breakdown.get("total_cost") or 0))


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
    def check_can_proceed(user: User, cost: int, db: Session = None, project_id: int = None):
        """
        Raises HTTPException if user doesn't have enough credits, considering groups if db provided.
        """
        if user.credits is None:
            user.credits = 0

        # Optimization: fast path if user has enough purely on their own.
        if user.credits >= cost:
            return True

        if db and user.current_group_id:
            group = db.query(UserGroup).filter(UserGroup.id == user.current_group_id).first()
            if BillingService._group_allows_credit_billing(group) and (group.credits or 0) > 0:
                # Need to also check allocation if project_id is provided
                if project_id:
                    allocation = db.query(ProjectGroupCreditAllocation).filter(
                        ProjectGroupCreditAllocation.group_id == group.id,
                        ProjectGroupCreditAllocation.project_id == project_id
                    ).first()
                    if allocation and allocation.credit_limit != -1:
                        if (allocation.used_credits or 0) + cost > allocation.credit_limit:
                            # Not allowed to use group credits because of allocation, default back to personal failure
                            pass
                        elif (group.credits or 0) + user.credits >= cost:
                            return True
                    elif (group.credits or 0) + user.credits >= cost:
                        return True
                elif (group.credits or 0) + user.credits >= cost:
                    return True
            
        if user.credits < cost:
            raise HTTPException(
                status_code=402, 
                detail=f"Insufficient credits. Required: {cost}. Please top up or ask your group admin."
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
            
        details = BillingService.ensure_provider_task_ids(details if isinstance(details, dict) else {})
        breakdown = BillingService.estimate_cost_breakdown(
            db,
            task_type,
            provider,
            model,
            details=details,
            phase="reserve",
        )
        usage_meta = dict(breakdown.get("usage_metadata") or {}) if isinstance(breakdown.get("usage_metadata"), dict) else {}
        usage_meta = BillingService.ensure_provider_task_ids({**usage_meta, **details})
        breakdown["usage_metadata"] = usage_meta
        final_cost = int(max(0, breakdown.get("total_cost") or 0))

        resolved_provider = str(
            breakdown.get("resolved_provider")
            or provider
            or ""
        ).strip() or None
        resolved_model = str(
            breakdown.get("resolved_model")
            or model
            or ""
        ).strip() or None
        
        # Credit deduction logic with Multi-tenant support
        project_id = details.get("project_id") if details else None
        
        group = None
        allocation = None
        billed_group_credits = 0
        billed_personal_credits = 0
        can_use_group_credits = False

        if user.current_group_id:
            group = db.query(UserGroup).filter(UserGroup.id == user.current_group_id).first()
            can_use_group_credits = BillingService._group_allows_credit_billing(group)
            if can_use_group_credits and project_id:
                allocation = db.query(ProjectGroupCreditAllocation).filter(
                    ProjectGroupCreditAllocation.group_id == group.id,
                    ProjectGroupCreditAllocation.project_id == project_id
                ).first()
                if allocation and allocation.credit_limit != -1:
                    if allocation.used_credits + final_cost > allocation.credit_limit:
                        raise HTTPException(status_code=402, detail="Project group credit allocation exceeded.")
        
        remaining_cost = final_cost
        if can_use_group_credits and group and (group.credits or 0) > 0 and remaining_cost > 0:
            if group.credits >= remaining_cost:
                billed_group_credits = remaining_cost
                group.credits -= remaining_cost
                remaining_cost = 0
            else:
                billed_group_credits = group.credits
                remaining_cost -= group.credits
                group.credits = 0

        if remaining_cost > 0:
            if (user.credits or 0) < remaining_cost:
                 raise HTTPException(status_code=402, detail="Insufficient personal credits.")
            billed_personal_credits = remaining_cost
            user.credits -= remaining_cost
            
        if allocation and final_cost > 0:
            allocation.used_credits = (allocation.used_credits or 0) + final_cost
        
        # Log Transaction (lean history details; full audit on TransactionAction)
        selected_rule_detail = breakdown.get("selected_rule_detail") if isinstance(breakdown.get("selected_rule_detail"), dict) else {}
        tx_details = dict(details or {})
        tx_details["matched_rule_id"] = breakdown.get("matched_rule_id")
        tx_details["matched_rule_name"] = breakdown.get("matched_rule_name")
        tx_details["system_api_id"] = breakdown.get("system_api_id")
        tx_details["pricing_program"] = BillingService._slim_pricing_program_for_history(
            breakdown=breakdown,
            selected_rule_detail=selected_rule_detail,
        )
        tx_details["billed_group_credits"] = billed_group_credits
        tx_details["billed_personal_credits"] = billed_personal_credits
        tx_details["reserved_cost"] = final_cost
        tx_details["actual_cost"] = final_cost
        tx_details["status"] = "SETTLED"
        tx_details["billing_mode"] = "ACTUAL"
        if group:
            tx_details["group_id"] = group.id
            tx_details["allow_group_credit_billing"] = can_use_group_credits
        tx_details = BillingService._promote_media_context_for_history(
            tx_details,
            usage=breakdown.get("usage_metadata") if isinstance(breakdown.get("usage_metadata"), dict) else None,
        )
        tx_details = BillingService._attach_balance_snapshots(
            tx_details, user=user, group=group if can_use_group_credits else None
        )
        tx_details = BillingService._compact_history_ledger_details(tx_details)

        transaction = TransactionHistory(
            user_id=user_id,
            amount=-final_cost,
            balance_after=user.credits,
            description=tx_details.get("description", task_type),
            details=tx_details,
            project_id=tx_details.get("project_id"),
            episode_id=tx_details.get("episode_id"),
        )
        db.add(transaction)
        db.flush()

        BillingService._log_transaction_action(
            db,
            user_id=user_id,
            stage="DEDUCTED",
            task_type=task_type,
            provider=resolved_provider,
            model=resolved_model,
            project_id=tx_details.get("project_id"),
            episode_id=tx_details.get("episode_id"),
            transaction_id=transaction.id,
            system_api_id=breakdown.get("system_api_id"),
            matched_rule_id=breakdown.get("matched_rule_id"),
            reserved_cost=final_cost,
            actual_cost=final_cost,
            delta=0,
            charged_amount=final_cost,
            refunded_amount=0,
            outstanding_amount=0,
            matched_rule_ids=breakdown.get("matched_rule_ids") or [],
            usage_metadata=breakdown.get("usage_metadata") or {},
            breakdown=breakdown,
            phase="direct_deduct",
        )
        process_snapshot = breakdown.get("billing_process") if isinstance(breakdown.get("billing_process"), dict) else {}
        if not process_snapshot:
            process_snapshot = BillingService._build_billing_process_snapshot(breakdown, phase="direct_deduct")
        BillingService._log_billing_process(
            {
                **process_snapshot,
                "user_id": user_id,
                "reservation_tx_id": transaction.id,
            },
            context=f"deduct:{task_type}",
        )
        db.commit()
        db.refresh(transaction)
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
                description=fail_details.get("description", task_type),
                details=fail_details
            )
            db.add(transaction)
            db.commit()
            logger.info(f"Logged failed transaction for user {user_id}: {error_msg}")
        except Exception as e:
            logger.error(f"Failed to log transaction failure: {e}")
            db.rollback()

billing_service = BillingService()
