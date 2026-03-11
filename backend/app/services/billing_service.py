from sqlalchemy.orm import Session
from app.models.all_models import (
    User,
    TransactionHistory,
    SystemAPISetting,
    SystemAPIBillingRule,
    TransactionAction,
)
from fastapi import HTTPException
import logging
import math
import re
import json
from typing import Any, Dict, List, Optional
from app.services.system_default_api_service import list_task_default_system_settings

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
    MINIMUM_CHARGE_BY_TASK = {
        "llm_chat": 1,
    }

    @staticmethod
    def _task_type_for_category(category: str) -> str:
        normalized = str(category or "").strip().lower()
        if normalized == "image":
            return "image_gen"
        if normalized == "video":
            return "video_gen"
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
            return {"average_cost": 0, "source": "invalid_system_api_id", "samples": 0}

        system_row = db.query(SystemAPISetting).filter(SystemAPISetting.id == api_id).first()
        if not system_row:
            return {"average_cost": 0, "source": "system_api_not_found", "samples": 0}

        category = str(getattr(system_row, "category", "") or "").strip()

        # Media categories: prefer averaging this API's own active rule prices.
        media_avg = BillingService._estimate_media_average_price_from_rules(db, api_id, category)
        if media_avg is not None:
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

        if not costs:
            return {"average_cost": 0, "source": "no_profiles", "samples": 0}

        avg_cost = int(round(sum(costs) / float(len(costs))))
        source = sources[0] if sources and all(s == sources[0] for s in sources) else "mixed"
        return {
            "average_cost": max(0, avg_cost),
            "source": source,
            "samples": len(costs),
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

        costs: List[int] = []
        for row in rows:
            if cat == "image" and not bool(getattr(row, "applies_to_image", False)):
                continue
            if cat == "video" and not bool(getattr(row, "applies_to_video", False)):
                continue

            cost = max(0, BillingService._to_int(getattr(row, "billing_cost", 0), 0))
            if cost <= 0:
                continue
            costs.append(int(cost))

        if not costs:
            return None

        avg_cost = int(round(sum(costs) / float(len(costs))))
        return {
            "average_cost": max(0, avg_cost),
            "source": "system_api_rule_price_average",
            "samples": len(costs),
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
    def _is_base_billing_rule(rule: SystemAPIBillingRule) -> bool:
        extra = BillingService._rule_extra_conditions(rule)
        if str(extra.get("rule_kind", "")).strip().lower() == BillingService.BASE_BILLING_RULE_KIND:
            return True
        if int(getattr(rule, "priority", 0) or 0) <= BillingService.BASE_BILLING_RULE_PRIORITY and not BillingService._rule_has_matching_dimensions(rule):
            return True
        return False

    @staticmethod
    def _billing_from_rule(rule: Optional[SystemAPIBillingRule]) -> Dict[str, Any]:
        if not rule:
            return {"unit_type": "per_call", "cost": 0, "cost_input": 0, "cost_output": 0}
        return BillingService._normalize_api_pricing_config({
            "unit_type": getattr(rule, "billing_unit_type", "per_call"),
            "cost": getattr(rule, "billing_cost", 0),
            "cost_input": getattr(rule, "billing_cost_input", 0),
            "cost_output": getattr(rule, "billing_cost_output", 0),
        })

    @staticmethod
    def _get_base_billing_rule(db: Session, system_api_id: int) -> Optional[SystemAPIBillingRule]:
        rows = db.query(SystemAPIBillingRule).filter(
            SystemAPIBillingRule.system_api_id == system_api_id,
            SystemAPIBillingRule.is_active == True,
        ).order_by(SystemAPIBillingRule.id.desc()).all()
        for row in rows:
            if BillingService._is_base_billing_rule(row):
                return row
        return None

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
        row = db.query(SystemAPISetting).filter(
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

        base_rule = BillingService._get_base_billing_rule(db, int(row.id))
        if base_rule:
            resolved = BillingService._billing_from_rule(base_rule)
            if BillingService._has_effective_api_pricing(resolved):
                return resolved

        return default_pricing

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

        quantity = float(BillingService._safe_non_negative_float(payload.get("billing_quantity", 1), 1.0))
        if unit_type == 'per_call':
            success_output_count = BillingService._to_int(payload.get("success_output_count", payload.get("successful_outputs", 0)), 0)
            if success_output_count > 0:
                quantity = float(success_output_count)
            return max(0, int(round(float(base_cost) * float(max(quantity, 1.0)))))

        if unit_type == 'per_second':
            quantity = float(payload.get('duration_seconds', payload.get('duration', 0)) or 0)
        elif unit_type == 'per_minute':
            quantity = float(payload.get('duration_seconds', payload.get('duration', 0)) or 0) / 60.0

        if quantity <= 0 and unit_type in {'per_second', 'per_minute'}:
            return 0
        return max(0, int(round(float(base_cost) * float(quantity))))

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
    def _resolve_system_api_row(db: Session, task_type: str, provider: str = None, model: str = None) -> Optional[SystemAPISetting]:
        provider_text = str(provider or "").strip()
        model_text = str(model or "").strip()
        category = BillingService._task_type_to_category(task_type)

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
            query_any_category = db.query(SystemAPISetting).filter(SystemAPISetting.provider == provider_text)
            if model_text:
                query_any_category = query_any_category.filter(SystemAPISetting.model == model_text)
            row = query_any_category.order_by(SystemAPISetting.id.desc()).first()
        return row

    @staticmethod
    def _extract_usage_metadata(details: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        payload = dict(details or {})

        input_tokens = BillingService._to_int(payload.get("input_tokens", payload.get("prompt_tokens", 0)), 0)
        output_tokens = BillingService._to_int(payload.get("output_tokens", payload.get("completion_tokens", 0)), 0)
        total_tokens = BillingService._to_int(payload.get("total_tokens", input_tokens + output_tokens), 0)
        cache_hit_tokens = BillingService._to_int(payload.get("cache_hit_tokens", payload.get("cached_tokens", 0)), 0)
        cache_miss_tokens = BillingService._to_int(payload.get("cache_miss_tokens", 0), 0)

        if cache_hit_tokens > 0 and cache_miss_tokens == 0 and total_tokens > cache_hit_tokens:
            cache_miss_tokens = total_tokens - cache_hit_tokens

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

        return {
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
        }

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

        required_keys = extra.get("required_keys")
        if isinstance(required_keys, list):
            score += max(0, len([k for k in required_keys if str(k or "").strip()])) * 2

        return int(score)

    @staticmethod
    def _rule_matches_usage(rule: SystemAPIBillingRule, usage: Dict[str, Any], mode: str) -> bool:
        if not bool(getattr(rule, "is_active", False)):
            return False

        if mode == "text" and not bool(getattr(rule, "applies_to_text", False)):
            return False
        if mode == "image" and not bool(getattr(rule, "applies_to_image", False)):
            return False
        if mode == "video" and not bool(getattr(rule, "applies_to_video", False)):
            return False

        gm = BillingService._to_lower_text(getattr(rule, "generation_mode", ""))
        if gm and gm != BillingService._to_lower_text(usage.get("generation_mode")):
            return False

        inf = BillingService._to_lower_text(getattr(rule, "input_format", ""))
        if inf and inf != BillingService._to_lower_text(usage.get("input_format")):
            return False

        outf = BillingService._to_lower_text(getattr(rule, "output_format", ""))
        if outf and outf != BillingService._to_lower_text(usage.get("output_format")):
            return False

        rule_has_audio = getattr(rule, "has_audio", None)
        if rule_has_audio is not None:
            usage_has_audio = usage.get("has_audio", None)
            if usage_has_audio is None or bool(rule_has_audio) != bool(usage_has_audio):
                return False

        if not BillingService._in_range_int(usage.get("input_tokens", 0), getattr(rule, "input_tokens_min", None), getattr(rule, "input_tokens_max", None)):
            return False
        if not BillingService._in_range_int(usage.get("output_tokens", 0), getattr(rule, "output_tokens_min", None), getattr(rule, "output_tokens_max", None)):
            return False
        if not BillingService._in_range_int(usage.get("total_tokens", 0), getattr(rule, "total_tokens_min", None), getattr(rule, "total_tokens_max", None)):
            return False

        if not BillingService._in_range_int(usage.get("image_count", 1), getattr(rule, "image_count_min", None), getattr(rule, "image_count_max", None)):
            return False
        if not BillingService._in_range_int(usage.get("width", 0), getattr(rule, "width_min", None), getattr(rule, "width_max", None)):
            return False
        if not BillingService._in_range_int(usage.get("height", 0), getattr(rule, "height_min", None), getattr(rule, "height_max", None)):
            return False
        if not BillingService._in_range_int(usage.get("pixels", 0), getattr(rule, "pixels_min", None), getattr(rule, "pixels_max", None)):
            return False

        if not BillingService._in_range_float(usage.get("duration_seconds", 0.0), getattr(rule, "duration_seconds_min", None), getattr(rule, "duration_seconds_max", None)):
            return False
        if not BillingService._in_range_float(usage.get("fps", 0.0), getattr(rule, "fps_min", None), getattr(rule, "fps_max", None)):
            return False

        extra = BillingService._rule_extra_conditions(rule)
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
        cfg = {
            "unit_type": str(getattr(rule, "billing_unit_type", "per_call") or "per_call"),
            "cost": max(0, BillingService._to_int(getattr(rule, "billing_cost", 0), 0)),
            "cost_input": max(0, BillingService._to_int(getattr(rule, "billing_cost_input", 0), 0)),
            "cost_output": max(0, BillingService._to_int(getattr(rule, "billing_cost_output", 0), 0)),
        }
        extra = BillingService._rule_extra_conditions(rule)
        cache_hit_input_cost = BillingService._to_int(extra.get("cache_hit_cost_input", 0), 0)
        cache_hit_output_cost = BillingService._to_int(extra.get("cache_hit_cost_output", 0), 0)
        cache_miss_input_cost = BillingService._to_int(extra.get("cache_miss_cost_input", 0), 0)
        cache_miss_output_cost = BillingService._to_int(extra.get("cache_miss_cost_output", 0), 0)

        if cfg["unit_type"] in BillingService.TOKEN_UNIT_TYPES and any(
            value > 0 for value in [cache_hit_input_cost, cache_hit_output_cost, cache_miss_input_cost, cache_miss_output_cost]
        ):
            divisor = 1_000_000.0 if cfg["unit_type"] == "per_million_tokens" else 1_000.0 if cfg["unit_type"] == "per_1k_tokens" else 1.0
            cache_hit_tokens = max(0, BillingService._to_int(usage.get("cache_hit_tokens", 0), 0))
            cache_miss_tokens = max(0, BillingService._to_int(usage.get("cache_miss_tokens", 0), 0))
            input_tokens = max(0, BillingService._to_int(usage.get("input_tokens", 0), 0))
            output_tokens = max(0, BillingService._to_int(usage.get("output_tokens", 0), 0))
            if cache_miss_tokens == 0:
                cache_miss_tokens = max(0, input_tokens - cache_hit_tokens)

            miss_input_rate = cache_miss_input_cost if cache_miss_input_cost > 0 else cfg["cost_input"]
            output_rate = cache_miss_output_cost if cache_miss_output_cost > 0 else cache_hit_output_cost if cache_hit_output_cost > 0 else cfg["cost_output"]

            computed = (
                (float(cache_hit_tokens) * float(cache_hit_input_cost))
                + (float(cache_miss_tokens) * float(miss_input_rate))
                + (float(output_tokens) * float(output_rate))
            ) / divisor
            amount = max(0, int(round(computed)))
        else:
            amount = BillingService._estimate_api_cost_from_config(cfg, usage)

        raw_multiplier = getattr(rule, "charge_multiplier", None)
        try:
            parsed_multiplier = float(raw_multiplier) if raw_multiplier is not None else 2.0
        except Exception:
            parsed_multiplier = 2.0
        # Requirement: null/negative multiplier falls back to 2.0
        charge_multiplier = 2.0 if parsed_multiplier < 0 else parsed_multiplier

        base_cost = int(max(0, amount))
        charged_cost = int(max(0, round(float(base_cost) * float(charge_multiplier))))
        return {
            "cost": charged_cost,
            "base_cost": base_cost,
            "charge_multiplier": float(charge_multiplier),
            "config": cfg,
        }

    @staticmethod
    def _select_best_matching_rule(
        db: Session,
        system_api_id: int,
        usage: Dict[str, Any],
        mode: str,
    ) -> Dict[str, Any]:
        rows = db.query(SystemAPIBillingRule).filter(
            SystemAPIBillingRule.system_api_id == system_api_id,
            SystemAPIBillingRule.is_active == True,
        ).order_by(SystemAPIBillingRule.priority.desc(), SystemAPIBillingRule.id.desc()).all()

        if not rows:
            return {"matched": [], "best": None}

        matched = []
        for row in rows:
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

        return {
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
            "computed_base_cost": int((pricing_payload or {}).get("base_cost", 0) or 0),
            "computed_cost": int((pricing_payload or {}).get("cost", 0) or 0),
            "specificity_score": int(specificity or 0),
        }

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
            system_row = db.query(SystemAPISetting).filter(SystemAPISetting.id == forced_system_api_id).first()
        if not system_row:
            system_row = BillingService._resolve_system_api_row(db, task_type, provider_text, model_text)
        if system_row:
            provider_text = str(getattr(system_row, "provider", "") or provider_text).strip()
            model_text = str(getattr(system_row, "model", "") or model_text).strip()

        # Billing order: system API billing rules -> system API base rule -> generic default pricing.
        if system_row:
            base_rule = BillingService._get_base_billing_rule(db, int(system_row.id))
            if base_rule:
                api_cfg = BillingService._billing_from_rule(base_rule)
                api_pricing_source = "system_api_base_rule"
                api_pricing_source_detail = {
                    "base_rule_id": int(getattr(base_rule, "id", 0) or 0),
                    "base_rule_name": str(getattr(base_rule, "name", "") or ""),
                }
            else:
                api_cfg = BillingService._resolve_api_pricing_config(db, task_type, provider_text, model_text)
                api_pricing_source = "default_api_pricing"
                api_pricing_source_detail = {"reason": "system_api_has_no_base_rule"}
        else:
            api_cfg = BillingService._resolve_api_pricing_config(db, task_type, provider_text, model_text)
            api_pricing_source = "default_api_pricing"
            api_pricing_source_detail = {"reason": "system_api_not_resolved"}

        api_cost_fallback = BillingService._estimate_api_cost_from_config(api_cfg, usage)

        matched_rule_ids: List[int] = []
        selected_rule_id = None
        selected_rule_name = None
        selected_rule_detail = None
        matched_rule_details: List[Dict[str, Any]] = []
        selected_api_cfg = api_cfg
        selected_api_cost = api_cost_fallback
        rule_match_count = 0

        if system_row:
            matched_info = BillingService._select_best_matching_rule(db, int(system_row.id), usage, mode)
            matched_rows = matched_info.get("matched") or []
            rule_match_count = len(matched_rows)
            matched_rule_ids = [int(item["rule"].id) for item in matched_rows]
            matched_rule_details = [
                BillingService._serialize_rule_for_audit(
                    item.get("rule"),
                    pricing=item.get("pricing"),
                    specificity=item.get("specificity"),
                )
                for item in matched_rows[:20]
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
            elif phase == "settle" and reserved_cost_fallback is not None:
                selected_api_cost = int(max(0, reserved_cost_fallback))
                api_pricing_source = "settlement_reserved_cost_fallback"
                api_pricing_source_detail = {"reason": "no_rule_matched_use_reserved_cost"}

        used_reserved_fallback = bool(
            phase == "settle"
            and reserved_cost_fallback is not None
            and selected_rule_id is None
            and rule_match_count == 0
            and system_row is not None
        )

        if used_reserved_fallback and reserved_cost_fallback is not None:
            total_cost = max(0, int(reserved_cost_fallback))
        else:
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

        return {
            "task_type": task_type,
            "provider": provider_text,
            "model": model_text,
            "resolved_provider": resolved_provider,
            "resolved_model": resolved_model,
            "phase": phase,
            "feature_cost": int(feature_cost),
            "api_cost": int(selected_api_cost),
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
            "usage_metadata": usage,
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

    @staticmethod
    def _build_billing_trace(breakdown: Dict[str, Any], *, task_type: str, provider: Optional[str], model: Optional[str], phase: str) -> Dict[str, Any]:
        resolved_provider = str(
            breakdown.get("resolved_provider")
            or breakdown.get("provider")
            or provider
            or ""
        ).strip() or None
        resolved_model = str(
            breakdown.get("resolved_model")
            or breakdown.get("model")
            or model
            or ""
        ).strip() or None
        return {
            "task_type": str(task_type or "").strip(),
            "provider": resolved_provider,
            "model": resolved_model,
            "phase": str(phase or "").strip() or None,
            "system_api_ref": breakdown.get("system_api_ref") or {},
            "system_api_id": breakdown.get("system_api_id"),
            "api_pricing_source": breakdown.get("api_pricing_source"),
            "api_pricing_source_detail": breakdown.get("api_pricing_source_detail") or {},
            "matched_rule_id": breakdown.get("matched_rule_id"),
            "matched_rule_name": breakdown.get("matched_rule_name"),
            "matched_rule_ids": breakdown.get("matched_rule_ids") or [],
            "rule_match_count": int(breakdown.get("rule_match_count") or 0),
            "rule_selection_status": breakdown.get("rule_selection_status"),
            "rule_selection_reason": breakdown.get("rule_selection_reason"),
            "selected_rule_detail": breakdown.get("selected_rule_detail"),
            "matched_rule_details": breakdown.get("matched_rule_details") or [],
            "usage_metadata": breakdown.get("usage_metadata") or {},
            "minimum_charge": breakdown.get("minimum_charge") or {},
            "audit_summary": breakdown.get("audit_summary") or {},
        }

    @staticmethod
    def _log_transaction_action(
        db: Session,
        *,
        user_id: int,
        stage: str,
        task_type: str,
        provider: Optional[str],
        model: Optional[str],
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
    ) -> None:
        action = TransactionAction(
            user_id=int(user_id),
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
            usage_metadata=dict(usage_metadata or {}),
            billing_metadata=dict(billing_metadata or {}),
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
    def is_token_pricing(db: Session, task_type: str, provider: str = None, model: str = None) -> bool:
        api_cfg = BillingService._resolve_api_pricing_config(db, task_type, provider, model)
        if api_cfg:
            unit_type = str(api_cfg.get("unit_type", "per_call") or "per_call").strip()
            if unit_type in BillingService.TOKEN_UNIT_TYPES:
                return True
        return False

    # ── Video token estimation ──────────────────────────────────────

    @staticmethod
    def estimate_video_output_tokens(
        width: int = 1280,
        height: int = 720,
        fps: int = 24,
        duration_seconds: float = 5.0,
        draft_token_coefficient: float = 1.0,
    ) -> int:
        """
        Estimate video output tokens.
        Normal:  ceil(width × height × fps × duration / 1024)
        Draft:   above × draft_token_coefficient  (< 1.0 means fewer tokens)
        """
        w = max(1, int(width))
        h = max(1, int(height))
        f = max(1, int(fps))
        d = max(0.0, float(duration_seconds))
        if d <= 0:
            return 0
        raw = (w * h * f * d) / 1024.0
        coeff = float(draft_token_coefficient)
        if 0 < coeff < 1.0:
            raw *= coeff
        return max(1, int(math.ceil(raw)))

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
            row = db.query(SystemAPISetting).filter(
                SystemAPISetting.category == "Video",
                SystemAPISetting.provider == provider_text,
                SystemAPISetting.model == model_text,
            ).order_by(SystemAPISetting.id.desc()).first()
        if not row and provider_text:
            row = db.query(SystemAPISetting).filter(
                SystemAPISetting.category == "Video",
                SystemAPISetting.provider == provider_text,
            ).order_by(SystemAPISetting.id.desc()).first()

        defaults = {"default_width": 1280, "default_height": 720, "default_fps": 24, "draft_token_coefficient": 1.0}
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
        try:
            defaults["draft_token_coefficient"] = max(0.0, float(vtd.get("draft_token_coefficient", 1.0)))
        except Exception:
            pass
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
        BillingService.check_can_proceed(user, reserved_cost)
        resolved_provider = reserve_breakdown.get("resolved_provider") or provider
        resolved_model = reserve_breakdown.get("resolved_model") or model

        reserve_details.update({
            "resolved_provider": reserve_breakdown.get("resolved_provider"),
            "resolved_model": reserve_breakdown.get("resolved_model"),
            "billing_breakdown": {
                "feature_cost": int(reserve_breakdown.get("feature_cost") or 0),
                "api_cost": int(reserve_breakdown.get("api_cost") or 0),
                "total_cost": int(reserve_breakdown.get("total_cost") or 0),
                "resolved_provider": reserve_breakdown.get("resolved_provider"),
                "resolved_model": reserve_breakdown.get("resolved_model"),
                "api_pricing_source": reserve_breakdown.get("api_pricing_source"),
                "api_pricing_source_detail": reserve_breakdown.get("api_pricing_source_detail") or {},
                "system_api_id": reserve_breakdown.get("system_api_id"),
                "matched_rule_id": reserve_breakdown.get("matched_rule_id"),
                "matched_rule_name": reserve_breakdown.get("matched_rule_name"),
                "matched_rule_ids": reserve_breakdown.get("matched_rule_ids") or [],
                "matched_rule_details": reserve_breakdown.get("matched_rule_details") or [],
                "selected_rule_detail": reserve_breakdown.get("selected_rule_detail"),
                "rule_match_count": int(reserve_breakdown.get("rule_match_count") or 0),
                "rule_selection_status": reserve_breakdown.get("rule_selection_status"),
                "rule_selection_reason": reserve_breakdown.get("rule_selection_reason"),
                "minimum_charge": reserve_breakdown.get("minimum_charge") or {},
                "phase": "reserve",
                "system_api_ref": reserve_breakdown.get("system_api_ref") or {},
                "audit_summary": reserve_breakdown.get("audit_summary") or {},
            },
            "usage_metadata": reserve_breakdown.get("usage_metadata") or {},
            "billing_trace": BillingService._build_billing_trace(
                reserve_breakdown,
                task_type=task_type,
                provider=resolved_provider,
                model=resolved_model,
                phase="reserve",
            ),
        })

        user.credits -= reserved_cost

        tx = TransactionHistory(
            user_id=user_id,
            amount=-reserved_cost,
            balance_after=user.credits or 0,
            task_type=task_type,
            provider=resolved_provider,
            model=resolved_model,
            details=reserve_details
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
            billing_metadata={
                "phase": "reserve",
                "breakdown": reserve_details.get("billing_breakdown") or {},
            },
        )
        db.commit()
        db.refresh(tx)
        logger.info(
            "billing.reserve.audit %s",
            json.dumps({
                "tx_id": tx.id,
                "user_id": user_id,
                "task_type": task_type,
                "provider": provider,
                "model": model,
                "reserved_cost": reserved_cost,
                "billing_breakdown": reserve_details.get("billing_breakdown") or {},
                "usage_metadata": reserve_breakdown.get("usage_metadata") or {},
            }, ensure_ascii=False),
        )
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
            "reservation_billing_breakdown": ((tx.details or {}).get("billing_breakdown") if isinstance(tx.details, dict) else {}),
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
        db.flush()

        BillingService._log_transaction_action(
            db,
            user_id=tx.user_id,
            stage="CANCELED",
            task_type=tx.task_type,
            provider=tx.provider,
            model=tx.model,
            transaction_id=tx.id,
            reservation_tx_id=tx.id,
            settlement_tx_id=refund_tx.id,
            system_api_id=None,
            matched_rule_id=None,
            reserved_cost=reserved_cost,
            actual_cost=0,
            delta=-reserved_cost,
            charged_amount=0,
            refunded_amount=reserved_cost,
            outstanding_amount=0,
            matched_rule_ids=[],
            usage_metadata={},
            billing_metadata=refund_details,
        )

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

        logger.info(
            "billing.cancel.audit %s",
            json.dumps({
                "reservation_tx_id": tx.id,
                "refund_tx_id": refund_tx.id,
                "user_id": tx.user_id,
                "task_type": tx.task_type,
                "provider": tx.provider,
                "model": tx.model,
                "reserved_cost": reserved_cost,
                "error": str(error_msg or "")[:500] if error_msg else "",
                "reservation_billing_breakdown": refund_details.get("reservation_billing_breakdown") or {},
            }, ensure_ascii=False),
        )

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
        smart_routing = details.get("smart_routing") if isinstance(details.get("smart_routing"), dict) else {}
        settle_provider = str(
            details.get("provider")
            or details.get("resolved_provider")
            or smart_routing.get("provider")
            or reservation_tx.provider
            or ""
        ).strip() or None
        settle_model = str(
            details.get("model")
            or details.get("resolved_model")
            or smart_routing.get("model")
            or reservation_tx.model
            or ""
        ).strip() or None

        # Normalize usage keys
        if "input_tokens" not in details and "prompt_tokens" in details:
            details["input_tokens"] = details.get("prompt_tokens", 0)
        if "output_tokens" not in details and "completion_tokens" in details:
            details["output_tokens"] = details.get("completion_tokens", 0)

        breakdown = BillingService.estimate_cost_breakdown(
            db,
            reservation_tx.task_type,
            settle_provider,
            settle_model,
            details=details,
            phase="settle",
            reserved_cost_fallback=reserved_cost,
        )
        settle_provider = str(breakdown.get("provider") or settle_provider or reservation_tx.provider or "").strip() or None
        settle_model = str(breakdown.get("model") or settle_model or reservation_tx.model or "").strip() or None
        actual_cost = int(breakdown.get("total_cost") or 0)

        delta = int(actual_cost - reserved_cost)
        settlement_tx = None
        outstanding = 0
        charged_amount = 0
        refunded_amount = 0

        if delta < 0:
            refund = -delta
            user.credits = (user.credits or 0) + refund
            settlement_tx = TransactionHistory(
                user_id=user.id,
                amount=refund,
                balance_after=user.credits or 0,
                task_type=reservation_tx.task_type,
                provider=settle_provider,
                model=settle_model,
                details={
                    "status": "REFUND",
                    "reason": "RESERVATION_SETTLEMENT",
                    "reservation_tx_id": reservation_tx.id,
                    "reserved_cost": reserved_cost,
                    "actual_cost": actual_cost,
                }
            )
            db.add(settlement_tx)
            refunded_amount = refund
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
                    provider=settle_provider,
                    model=settle_model,
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
                charged_amount = can_deduct

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
            "resolved_provider": settle_provider,
            "resolved_model": settle_model,
            "actual_input_tokens": int(details.get("input_tokens", 0) or 0),
            "actual_output_tokens": int(details.get("output_tokens", 0) or 0),
            "actual_total_tokens": int(details.get("total_tokens", 0) or 0),
            "billing_breakdown": {
                "feature_cost": int(breakdown.get("feature_cost") or 0),
                "api_cost": int(breakdown.get("api_cost") or 0),
                "fallback_api_cost": int(breakdown.get("fallback_api_cost") or 0),
                "resolved_provider": breakdown.get("resolved_provider"),
                "resolved_model": breakdown.get("resolved_model"),
                "api_pricing_source": breakdown.get("api_pricing_source"),
                "api_pricing_source_detail": breakdown.get("api_pricing_source_detail") or {},
                "system_api_id": breakdown.get("system_api_id"),
                "matched_rule_id": breakdown.get("matched_rule_id"),
                "matched_rule_name": breakdown.get("matched_rule_name"),
                "matched_rule_ids": breakdown.get("matched_rule_ids") or [],
                "matched_rule_details": breakdown.get("matched_rule_details") or [],
                "selected_rule_detail": breakdown.get("selected_rule_detail"),
                "rule_match_count": int(breakdown.get("rule_match_count") or 0),
                "rule_selection_status": breakdown.get("rule_selection_status"),
                "rule_selection_reason": breakdown.get("rule_selection_reason"),
                "minimum_charge": breakdown.get("minimum_charge") or {},
                "used_reserved_fallback": bool(breakdown.get("used_reserved_fallback")),
                "settlement_fallback_reason": breakdown.get("settlement_fallback_reason"),
                "system_api_ref": breakdown.get("system_api_ref") or {},
                "phase": "settle",
                "audit_summary": breakdown.get("audit_summary") or {},
            },
            "usage_metadata": breakdown.get("usage_metadata") or {},
            "billing_trace": BillingService._build_billing_trace(
                breakdown,
                task_type=reservation_tx.task_type,
                provider=settle_provider,
                model=settle_model,
                phase="settle",
            ),
        })
        reservation_tx.details = res_details
        reservation_tx.provider = settle_provider
        reservation_tx.model = settle_model

        if settlement_tx is not None:
            db.flush()

        BillingService._log_transaction_action(
            db,
            user_id=user.id,
            stage="SETTLED",
            task_type=reservation_tx.task_type,
            provider=settle_provider,
            model=settle_model,
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
            billing_metadata={
                "phase": "settle",
                "breakdown": res_details.get("billing_breakdown") or {},
            },
        )

        db.commit()
        if settlement_tx:
            db.refresh(settlement_tx)

            # Backfill settlement id into reservation details
            res_details = dict(reservation_tx.details or {})
            res_details["settlement_tx_id"] = settlement_tx.id
            reservation_tx.details = res_details
            db.commit()

        logger.info(
            "billing.settle.audit %s",
            json.dumps({
                "reservation_tx_id": reservation_tx.id,
                "settlement_tx_id": settlement_tx.id if settlement_tx else None,
                "user_id": user.id,
                "task_type": reservation_tx.task_type,
                "provider": settle_provider,
                "model": settle_model,
                "reserved_cost": reserved_cost,
                "actual_cost": actual_cost,
                "delta": delta,
                "charged_amount": charged_amount,
                "refunded_amount": refunded_amount,
                "outstanding": outstanding,
                "billing_breakdown": res_details.get("billing_breakdown") or {},
                "usage_metadata": breakdown.get("usage_metadata") or {},
            }, ensure_ascii=False),
        )

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
            
        breakdown = BillingService.estimate_cost_breakdown(
            db,
            task_type,
            provider,
            model,
            details=details,
            phase="reserve",
        )
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
        
        if user.credits < final_cost:
             raise HTTPException(status_code=402, detail="Insufficient credits during deduction.")
             
        user.credits -= final_cost
        
        # Log Transaction
        tx_details = dict(details or {})
        tx_details["billing_breakdown"] = {
            "feature_cost": int(breakdown.get("feature_cost") or 0),
            "api_cost": int(breakdown.get("api_cost") or 0),
            "fallback_api_cost": int(breakdown.get("fallback_api_cost") or 0),
            "total_cost": int(breakdown.get("total_cost") or 0),
            "resolved_provider": breakdown.get("resolved_provider"),
            "resolved_model": breakdown.get("resolved_model"),
            "api_pricing_source": breakdown.get("api_pricing_source"),
            "api_pricing_source_detail": breakdown.get("api_pricing_source_detail") or {},
            "system_api_id": breakdown.get("system_api_id"),
            "matched_rule_id": breakdown.get("matched_rule_id"),
            "matched_rule_name": breakdown.get("matched_rule_name"),
            "matched_rule_ids": breakdown.get("matched_rule_ids") or [],
            "matched_rule_details": breakdown.get("matched_rule_details") or [],
            "selected_rule_detail": breakdown.get("selected_rule_detail"),
            "rule_match_count": int(breakdown.get("rule_match_count") or 0),
            "rule_selection_status": breakdown.get("rule_selection_status"),
            "rule_selection_reason": breakdown.get("rule_selection_reason"),
            "minimum_charge": breakdown.get("minimum_charge") or {},
            "phase": "direct_deduct",
            "system_api_ref": breakdown.get("system_api_ref") or {},
            "audit_summary": breakdown.get("audit_summary") or {},
        }
        tx_details["usage_metadata"] = breakdown.get("usage_metadata") or {}
        tx_details["billing_trace"] = BillingService._build_billing_trace(
            breakdown,
            task_type=task_type,
            provider=resolved_provider,
            model=resolved_model,
            phase="direct_deduct",
        )

        transaction = TransactionHistory(
            user_id=user_id,
            amount=-final_cost,
            balance_after=user.credits,
            task_type=task_type,
            provider=resolved_provider,
            model=resolved_model,
            details=tx_details
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
            billing_metadata={
                "phase": "direct_deduct",
                "breakdown": tx_details.get("billing_breakdown") or {},
            },
        )
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
