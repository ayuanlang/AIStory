from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import cast, String, func
import logging
import json
import ast
import random
from datetime import datetime
import math
from app.db.session import get_db
from app.models.all_models import APISetting, User, PricingRule, SystemAPISetting
from app.schemas.settings import (
    APISettingOut,
    APISettingUpdate,
    SystemAPIModelOption,
    SystemAPIProviderModelCatalog,
    SystemAPIProviderSettings,
    SystemAPISettingOut,
    SystemAPISelectionRequest,
    SystemAPISettingManageCreate,
    SystemAPISettingManageUpdate,
    SystemAPISettingToggleDeprecatedRequest,
    SystemAPISettingToggleDeprecatedByKeyRequest,
    SystemAPIProviderBatchDeprecatedRequest,
    SystemAPIProviderKeysUpdateRequest,
    SystemAPISettingImportRequest,
    SystemAPIProviderImportRequest,
    AgentToolPolicyUpdate,
    AgentToolPolicyOut,
    SystemAIAssistantRequest,
    SystemAIAssistantResponse,
    SystemAIAssistantSuggestion,
)
from app.api.deps import get_current_user
from typing import List, Dict, Tuple, Any

router = APIRouter()
logger = logging.getLogger("settings_api")
logger.setLevel(logging.INFO)

_AGENT_POLICY_CATEGORY = "System_Payment"
_AGENT_POLICY_PROVIDER = "agent_policy"
_AGENT_POLICY_MODEL = "tool_acl"


def _default_agent_tool_policy() -> Dict[str, Any]:
    return {
        "default_allow": True,
        "roles": {
            "user": {
                "allow": [],
                "deny": ["internet_search"],
            },
            "authorized": {
                "allow": ["internet_search"],
                "deny": [],
            },
            "superuser": {
                "allow": ["*"],
                "deny": [],
            },
        },
    }


def _normalize_agent_tool_policy(value: Any) -> Dict[str, Any]:
    base = _default_agent_tool_policy()
    payload = _safe_json_dict(value)
    if "agent_tool_policy" in payload and isinstance(payload.get("agent_tool_policy"), dict):
        payload = _safe_json_dict(payload.get("agent_tool_policy"))

    default_allow = payload.get("default_allow")
    if isinstance(default_allow, bool):
        base["default_allow"] = default_allow
    elif default_allow is not None:
        base["default_allow"] = _to_bool(default_allow)

    roles_raw = payload.get("roles") if isinstance(payload.get("roles"), dict) else {}
    normalized_roles: Dict[str, Dict[str, List[str]]] = {}
    for role_name in ["user", "authorized", "superuser"]:
        role_payload = roles_raw.get(role_name) if isinstance(roles_raw.get(role_name), dict) else {}
        allow_list = []
        deny_list = []
        for item in role_payload.get("allow") or []:
            text = str(item or "").strip()
            if text and text not in allow_list:
                allow_list.append(text)
        for item in role_payload.get("deny") or []:
            text = str(item or "").strip()
            if text and text not in deny_list:
                deny_list.append(text)
        normalized_roles[role_name] = {
            "allow": allow_list,
            "deny": deny_list,
        }

    base["roles"] = normalized_roles
    return base


def _get_or_create_agent_policy_row(db: Session) -> SystemAPISetting:
    row = db.query(SystemAPISetting).filter(
        SystemAPISetting.category == _AGENT_POLICY_CATEGORY,
        SystemAPISetting.provider == _AGENT_POLICY_PROVIDER,
        SystemAPISetting.model == _AGENT_POLICY_MODEL,
    ).order_by(SystemAPISetting.id.desc()).first()

    if row:
        normalized = _normalize_agent_tool_policy(_safe_json_dict(row.config).get("agent_tool_policy", {}))
        cfg = _safe_json_dict(row.config)
        cfg["agent_tool_policy"] = normalized
        row.config = cfg
        return row

    row = SystemAPISetting(
        name="Agent Tool Policy",
        category=_AGENT_POLICY_CATEGORY,
        provider=_AGENT_POLICY_PROVIDER,
        api_key="",
        base_url="",
        model=_AGENT_POLICY_MODEL,
        deprecated=False,
        config={"agent_tool_policy": _default_agent_tool_policy()},
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def _normalize_unit_type_for_system_ai(raw: Any) -> str:
    text = str(raw or "per_call").strip() or "per_call"
    allowed = {"per_call", "per_second", "per_minute", "per_token", "per_1k_tokens", "per_million_tokens"}
    return text if text in allowed else "per_call"


def _safe_non_negative_float(value: Any) -> float:
    try:
        parsed = float(value)
        if math.isnan(parsed) or math.isinf(parsed):
            return 0.0
        return max(0.0, parsed)
    except Exception:
        return 0.0


def _multiplied_cost_to_credit(value: Any, multiplier: float) -> int:
    base = _safe_non_negative_float(value)
    mul = _safe_non_negative_float(multiplier)
    return max(0, int(math.ceil(base * (mul if mul > 0 else 1.0))))


def _build_system_ai_suggestions(payload: SystemAIAssistantRequest, db: Session) -> List[SystemAIAssistantSuggestion]:
    provider = str(payload.provider or "").strip()
    if not provider:
        raise HTTPException(status_code=400, detail="provider is required")

    multiplier = _safe_non_negative_float(payload.multiplier)
    if multiplier <= 0:
        multiplier = 1.0

    suggestions: List[SystemAIAssistantSuggestion] = []
    for item in payload.models or []:
        model_name = str(item.model or "").strip()
        if not model_name:
            continue

        category = str(item.category or "LLM").strip() or "LLM"
        unit_type = _normalize_unit_type_for_system_ai(item.unit_type)
        cost = _multiplied_cost_to_credit(item.supplier_price, multiplier)
        cost_input = _multiplied_cost_to_credit(item.supplier_price_input, multiplier)
        cost_output = _multiplied_cost_to_credit(item.supplier_price_output, multiplier)

        existing = _find_system_setting_by_normalized_triplet(db, provider, category, model_name)
        action = "create" if not existing else "update"
        reason = "new model from provider metadata" if not existing else "existing model pricing/API definition will be adjusted"

        suggestions.append(SystemAIAssistantSuggestion(
            action=action,
            setting_id=(existing.id if existing else None),
            provider=provider,
            category=category,
            model=model_name,
            name=(str(item.name or "").strip() or (existing.name if existing else f"{provider} {model_name}")),
            base_url=(str(item.base_url or "").strip() or (existing.base_url if existing else None)),
            unit_type=unit_type,
            supplier_price=(_safe_non_negative_float(item.supplier_price) if item.supplier_price is not None else None),
            supplier_price_input=(_safe_non_negative_float(item.supplier_price_input) if item.supplier_price_input is not None else None),
            supplier_price_output=(_safe_non_negative_float(item.supplier_price_output) if item.supplier_price_output is not None else None),
            multiplier=multiplier,
            cost=cost,
            cost_input=cost_input,
            cost_output=cost_output,
            reason=reason,
        ))

    return suggestions


def _mask_api_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:4]}***{api_key[-4:]}"


def _safe_json_dict(value) -> Dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode("utf-8", errors="ignore")
        except Exception:
            return {}
    if isinstance(value, str):
        raw_obj: Any = value
        for _ in range(3):
            if isinstance(raw_obj, dict):
                return raw_obj
            if not isinstance(raw_obj, str):
                return {}

            raw = raw_obj.strip()
            if not raw:
                return {}

            parsed = None
            try:
                parsed = json.loads(raw)
            except Exception:
                try:
                    parsed = ast.literal_eval(raw)
                except Exception:
                    parsed = None

            if parsed is None:
                return {}
            raw_obj = parsed

        return raw_obj if isinstance(raw_obj, dict) else {}
    return {}


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw in {"1", "true", "yes", "y", "on"}:
            return True
        if raw in {"0", "false", "no", "n", "off", "", "none", "null"}:
            return False
    return bool(value)


def _normalize_api_keys(values) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw_items = values.replace("\r", "\n").replace(",", "\n").split("\n")
    elif isinstance(values, list):
        raw_items = values
    else:
        raw_items = [values]

    result: List[str] = []
    seen = set()
    for item in raw_items:
        key = str(item or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


def _normalize_key_strategy(value: str) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"round_robin", "weighted", "random"}:
        return raw
    return "random"


def _normalize_key_weights(values, keys: List[str]) -> List[float]:
    if not keys:
        return []
    if values is None:
        return [1.0] * len(keys)
    raw_values = values if isinstance(values, list) else [values]
    parsed: List[float] = []
    for item in raw_values:
        try:
            val = float(item)
        except Exception:
            val = 1.0
        if val <= 0:
            val = 1.0
        parsed.append(val)

    if not parsed:
        parsed = [1.0]
    if len(parsed) < len(keys):
        parsed.extend([1.0] * (len(keys) - len(parsed)))
    return parsed[:len(keys)]


def _extract_provider_key_pool_from_row(row: SystemAPISetting) -> List[str]:
    cfg = _safe_json_dict(row.config)
    pooled = _normalize_api_keys(cfg.get("provider_api_keys"))
    if pooled:
        return pooled
    single = str(row.api_key or "").strip()
    return [single] if single else []


def _get_system_provider_key_pool(db: Session, provider: str) -> List[str]:
    rows = db.query(SystemAPISetting).filter(SystemAPISetting.provider == provider).order_by(SystemAPISetting.id.asc()).all()
    merged: List[str] = []
    seen = set()
    for row in rows:
        for key in _extract_provider_key_pool_from_row(row):
            if key in seen:
                continue
            seen.add(key)
            merged.append(key)
    return merged


def _apply_system_provider_key_pool(db: Session, provider: str, keys: List[str]) -> None:
    normalized = _normalize_api_keys(keys)
    rows = db.query(SystemAPISetting).filter(SystemAPISetting.provider == provider).all()
    primary_key = normalized[0] if normalized else ""
    for row in rows:
        cfg = _safe_json_dict(row.config)
        cfg["provider_api_keys"] = normalized
        strategy = _normalize_key_strategy(cfg.get("provider_api_key_strategy"))
        cfg["provider_api_key_strategy"] = strategy
        cfg["provider_api_key_weights"] = _normalize_key_weights(cfg.get("provider_api_key_weights"), normalized)
        row.config = cfg
        row.api_key = primary_key


def _apply_provider_key_bundle_to_rows(rows: List[SystemAPISetting], keys: List[str], strategy: str, weights: List[float]) -> None:
    primary_key = keys[0] if keys else ""
    for row in rows:
        cfg = _safe_json_dict(row.config)
        cfg["provider_api_keys"] = keys
        cfg["provider_api_key_strategy"] = strategy
        cfg["provider_api_key_weights"] = weights
        row.config = cfg
        row.api_key = primary_key


def _pick_provider_runtime_key(config_value, fallback_key: str = "") -> str:
    cfg = _safe_json_dict(config_value)
    pooled = _normalize_api_keys(cfg.get("provider_api_keys"))
    if pooled:
        return random.choice(pooled)
    return str(fallback_key or "").strip()


def _can_use_system_settings(user: User) -> bool:
    return bool(user and user.is_active)


def _can_manage_system_settings(user: User) -> bool:
    return bool(user.is_superuser)


def _ensure_default_system_selection_for_user(db: Session, user_id: int) -> None:
    existing_count = db.query(APISetting).filter(APISetting.user_id == user_id).count()
    if existing_count > 0:
        return

    active_system_rows = db.query(SystemAPISetting).filter(
        SystemAPISetting.is_active == True,
        SystemAPISetting.category != "System_Payment",
    ).order_by(SystemAPISetting.category.asc(), SystemAPISetting.id.desc()).all()

    if not active_system_rows:
        return

    selected_by_category: Dict[str, SystemAPISetting] = {}
    for row in active_system_rows:
        category = str(row.category or "").strip()
        if not category or category in selected_by_category:
            continue
        selected_by_category[category] = row

    for _, system_setting in selected_by_category.items():
        marker_config = dict(system_setting.config or {})
        marker_config["selection_source"] = "system"

        db.add(APISetting(
            user_id=user_id,
            name=f"Use System {system_setting.provider}",
            category=system_setting.category,
            provider=system_setting.provider,
            api_key="",
            base_url=system_setting.base_url,
            model=system_setting.model,
            config=marker_config,
            is_active=True,
        ))

    db.flush()


def _sync_provider_shared_key(db: Session, user_id: int, provider: str, current_setting_id: int, incoming_api_key: str = None) -> str:
    if not provider:
        return incoming_api_key or ""

    key = (incoming_api_key or "").strip()
    provider_settings = db.query(APISetting).filter(
        APISetting.user_id == user_id,
        APISetting.provider == provider,
    ).all()

    if key:
        for item in provider_settings:
            if item.id != current_setting_id:
                item.api_key = key
        return key

    # No incoming key: inherit existing provider key (shared by provider)
    for item in provider_settings:
        if item.id != current_setting_id and (item.api_key or "").strip():
            return item.api_key
    return ""


def _sync_system_provider_shared_key(db: Session, provider: str, current_setting_id: int, incoming_api_key: str = None) -> str:
    if not provider:
        return incoming_api_key or ""

    key = (incoming_api_key or "").strip()
    pool = _get_system_provider_key_pool(db, provider)
    if key and key not in pool:
        pool = [key, *pool]

    _apply_system_provider_key_pool(db, provider, pool)
    return pool[0] if pool else ""


def _task_type_to_category(task_type: str) -> str:
    task = (task_type or "").strip().lower()
    if task == "image_gen":
        return "Image"
    if task == "video_gen":
        return "Video"
    if task == "analysis":
        return "Vision"
    if task == "llm_chat":
        return "LLM"
    return "Tools"


def _find_system_setting_by_normalized_triplet(db: Session, provider: str, category: str, model: str):
    provider_norm = str(provider or "").strip().lower()
    category_norm = str(category or "").strip().lower()
    model_norm = str(model or "").strip().lower()
    return db.query(SystemAPISetting).filter(
        func.lower(func.trim(func.coalesce(SystemAPISetting.provider, ""))) == provider_norm,
        func.lower(func.trim(func.coalesce(SystemAPISetting.category, ""))) == category_norm,
        func.lower(func.trim(func.coalesce(SystemAPISetting.model, ""))) == model_norm,
    ).order_by(SystemAPISetting.id.desc()).first()


def _is_setting_deprecated(config_value, deprecated_flag: Any = None) -> bool:
    if _to_bool(deprecated_flag):
        return True
    cfg = _safe_json_dict(config_value)
    return bool(
        _to_bool(cfg.get("deprecated"))
        or _to_bool(cfg.get("is_deprecated"))
        or _to_bool(cfg.get("disable_api"))
    )


def _normalize_system_api_billing_config(config_value: Any) -> Dict[str, Any]:
    cfg = _safe_json_dict(config_value)
    api_pricing_raw = cfg.get("api_pricing") if isinstance(cfg.get("api_pricing"), dict) else {}

    unit_type = str(api_pricing_raw.get("unit_type", cfg.get("billing_unit_type", "per_call")) or "per_call").strip() or "per_call"
    token_unit_types = {"per_token", "per_1k_tokens", "per_million_tokens"}
    if unit_type not in {"per_call", "per_second", "per_minute", *token_unit_types}:
        unit_type = "per_call"

    def _non_negative_int(value: Any, default: int = 0) -> int:
        try:
            parsed = int(float(value))
            return parsed if parsed >= 0 else 0
        except Exception:
            return default

    cost = _non_negative_int(api_pricing_raw.get("cost", cfg.get("billing_cost", 0)), 0)
    cost_input = _non_negative_int(api_pricing_raw.get("cost_input", cfg.get("billing_cost_input", 0)), 0)
    cost_output = _non_negative_int(api_pricing_raw.get("cost_output", cfg.get("billing_cost_output", 0)), 0)

    normalized_api_pricing = {
        "unit_type": unit_type,
        "cost": cost,
        "cost_input": cost_input,
        "cost_output": cost_output,
    }

    cfg["api_pricing"] = normalized_api_pricing
    cfg["billing_unit_type"] = unit_type
    cfg["billing_cost"] = cost
    cfg["billing_cost_input"] = cost_input
    cfg["billing_cost_output"] = cost_output
    return cfg


def _migrate_legacy_pricing_rules_to_system_api_pricing(db: Session) -> int:
    rows = db.query(SystemAPISetting).filter(
        SystemAPISetting.category != "System_Payment",
    ).all()
    if not rows:
        return 0

    rules = db.query(PricingRule).filter(PricingRule.is_active == True).order_by(PricingRule.id.asc()).all()
    if not rules:
        return 0

    def _norm(value: Any) -> str:
        return str(value or "").strip().lower()

    def _nn_int(value: Any) -> int:
        try:
            parsed = int(float(value))
            return parsed if parsed >= 0 else 0
        except Exception:
            return 0

    def _rule_api_pricing(rule: PricingRule) -> Dict[str, Any]:
        unit_type = str(rule.unit_type or "per_call").strip() or "per_call"
        allowed_unit_types = {"per_call", "per_second", "per_minute", "per_token", "per_1k_tokens", "per_million_tokens"}
        if unit_type not in allowed_unit_types:
            unit_type = "per_call"
        return {
            "unit_type": unit_type,
            "cost": _nn_int(getattr(rule, "cost", 0)),
            "cost_input": _nn_int(getattr(rule, "cost_input", 0)),
            "cost_output": _nn_int(getattr(rule, "cost_output", 0)),
        }

    def _config_has_non_zero_pricing(cfg: Dict[str, Any]) -> bool:
        pricing = cfg.get("api_pricing") if isinstance(cfg.get("api_pricing"), dict) else {}
        return any(
            _nn_int(pricing.get(k, 0)) > 0
            for k in ("cost", "cost_input", "cost_output")
        )

    by_exact: Dict[Tuple[str, str, str], List[SystemAPISetting]] = {}
    by_provider_category: Dict[Tuple[str, str], List[SystemAPISetting]] = {}
    by_category_model: Dict[Tuple[str, str], List[SystemAPISetting]] = {}
    by_category: Dict[str, List[SystemAPISetting]] = {}
    active_by_category: Dict[str, List[SystemAPISetting]] = {}

    for row in rows:
        provider_key = _norm(row.provider)
        category_key = _norm(row.category)
        model_key = _norm(row.model)

        by_exact.setdefault((provider_key, category_key, model_key), []).append(row)
        by_provider_category.setdefault((provider_key, category_key), []).append(row)
        by_category_model.setdefault((category_key, model_key), []).append(row)
        by_category.setdefault(category_key, []).append(row)
        if bool(row.is_active):
            active_by_category.setdefault(category_key, []).append(row)

    updated = 0

    for rule in rules:
        category_key = _norm(_task_type_to_category(str(rule.task_type or "")))
        provider_key = _norm(rule.provider)
        model_key = _norm(rule.model)

        candidate_rows: List[SystemAPISetting] = []
        if provider_key and model_key:
            candidate_rows.extend(by_exact.get((provider_key, category_key, model_key), []))
        elif provider_key:
            candidate_rows.extend(by_provider_category.get((provider_key, category_key), []))
        elif model_key:
            candidate_rows.extend(by_category_model.get((category_key, model_key), []))
        else:
            candidate_rows.extend(active_by_category.get(category_key, []))
            if not candidate_rows:
                candidate_rows.extend(by_category.get(category_key, []))

        if not candidate_rows:
            fallback_rows = active_by_category.get(category_key, [])
            if fallback_rows:
                candidate_rows.extend(fallback_rows)

        if not candidate_rows:
            continue

        target_pricing = _rule_api_pricing(rule)

        seen_ids = set()
        for row in candidate_rows:
            if row.id in seen_ids:
                continue
            seen_ids.add(row.id)

            cfg = _normalize_system_api_billing_config(row.config)
            if _config_has_non_zero_pricing(cfg):
                continue

            cfg["api_pricing"] = {
                "unit_type": target_pricing["unit_type"],
                "cost": target_pricing["cost"],
                "cost_input": target_pricing["cost_input"],
                "cost_output": target_pricing["cost_output"],
            }
            cfg["billing_unit_type"] = target_pricing["unit_type"]
            cfg["billing_cost"] = target_pricing["cost"]
            cfg["billing_cost_input"] = target_pricing["cost_input"]
            cfg["billing_cost_output"] = target_pricing["cost_output"]

            row.config = cfg
            updated += 1

    return updated


def _ensure_builtin_system_settings(db: Session) -> None:
    kie_base_url = "https://api.kie.ai"

    def _kie_item(name: str, category: str, model: str) -> Dict[str, Any]:
        return {
            "name": name,
            "category": category,
            "provider": "kie",
            "base_url": kie_base_url,
            "model": model,
            "config": {
                "endpoint": f"{kie_base_url}/api/v1/jobs/createTask",
                "query_endpoint": f"{kie_base_url}/api/v1/jobs/recordInfo",
                "credits_endpoint": f"{kie_base_url}/api/v1/user/credits",
                "deprecated": False,
            },
        }

    builtins = [
        _kie_item("Kie Z-image v4.0", "Image", "z-image-v4.0"),
        _kie_item("Kie Z-image v4.5", "Image", "z-image-v4.5"),
        _kie_item("Kie Grok Imagine", "Image", "grok-imagine"),
        _kie_item("Kie Flux-2", "Image", "flux-2"),
        _kie_item("Kie Google Imagen4 Fast", "Image", "imagen4-fast"),
        _kie_item("Kie Google Imagen4 Ultra", "Image", "imagen4-ultra"),
        _kie_item("Kie Ideogram", "Image", "ideogram"),
        _kie_item("Kie Qwen Image", "Image", "qwen-image"),
        _kie_item("Kie Recraft", "Image", "recraft"),
        _kie_item("Kie Topaz", "Image", "topaz"),

        _kie_item("Kie Kling v2.1", "Video", "kling-v2.1"),
        _kie_item("Kie Kling v2.5", "Video", "kling-v2.5"),
        _kie_item("Kie Sora2", "Video", "sora2"),
        _kie_item("Kie Bytedance v1 Pro", "Video", "bytedance-v1-pro"),
        _kie_item("Kie Bytedance v1 Lite", "Video", "bytedance-v1-lite"),
        _kie_item("Kie Hailuo", "Video", "hailuo"),
        _kie_item("Kie Wan Turbo", "Video", "wan-turbo"),
        _kie_item("Kie Grok Imagine Video", "Video", "grok-imagine-video"),

        _kie_item("Kie ElevenLabs", "Tools", "elevenlabs"),

        _kie_item("Kie Gemini 2.5 Flash", "LLM", "gemini-2.5-flash"),
        _kie_item("Kie Gemini 2.5 Pro", "LLM", "gemini-2.5-pro"),
    ]

    existing = db.query(SystemAPISetting.category, SystemAPISetting.provider, SystemAPISetting.model).filter(
        SystemAPISetting.provider == "kie"
    ).all()
    existing_keys = {
        ((c or "").strip().lower(), (p or "").strip().lower(), (m or "").strip().lower())
        for c, p, m in existing
    }

    to_create = []
    for item in builtins:
        key = (
            item["category"].strip().lower(),
            item["provider"].strip().lower(),
            item["model"].strip().lower(),
        )
        if key in existing_keys:
            continue
        to_create.append(item)

    if not to_create:
        return

    shared_key = ""
    key_row = db.query(SystemAPISetting.api_key).filter(
        SystemAPISetting.provider == "kie",
        SystemAPISetting.api_key.isnot(None),
        SystemAPISetting.api_key != "",
    ).order_by(SystemAPISetting.id.desc()).first()
    if key_row and (key_row[0] or "").strip():
        shared_key = key_row[0].strip()

    for item in to_create:
        db.add(SystemAPISetting(
            name=item["name"],
            category=item["category"],
            provider=item["provider"],
            api_key=shared_key,
            base_url=item["base_url"],
            model=item["model"],
            deprecated=False,
            config=item["config"],
            is_active=False,
        ))

    db.flush()

DEFAULTS = {
    "openai": {
        "category": "LLM",
        "name": "OpenAI Default",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4-turbo-preview",
        "config": {"temperature": 0.7}
    },
    "anthropic": {
        "category": "LLM",
        "name": "Anthropic Default",
        "base_url": "https://api.anthropic.com",
        "model": "claude-3-opus-20240229",
        "config": {"max_tokens": 1024}
    },
    "baidu": {
        "category": "LLM",
        "name": "Baidu Ernie",
        "base_url": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat",
        "model": "completions_pro",
        "config": {}
    },
    "stability": {
        "category": "Image",
        "name": "Stability Core",
        "base_url": "https://api.stability.ai",
        "model": "stable-diffusion-xl-1024-v1-0",
        "config": {"steps": 30}
    },
    "runway": {
        "category": "Video",
        "name": "Runway Gen-2",
        "base_url": "https://api.runwayml.com",
        "model": "gen-2",
        "config": {}
    },
    "elevenlabs": {
        "category": "Voice",
        "name": "ElevenLabs v1",
        "base_url": "https://api.elevenlabs.io/v1",
        "model": "premade/Adam",
        "config": {}
    },
    "ark": {
        "category": "LLM", 
        "name": "Volcengine Ark", 
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-pro-32k",
        "config": {}
    },
    "grsai": {
        "category": "Video",
        "name": "Grsai (Sora)",
        "base_url": "https://grsai.dakka.com.cn",
        "model": "sora-image", 
        "config": {}
    },
    "tencent": {
        "category": "Image",
        "name": "Tencent Hunyuan",
        "base_url": "https://aiart.tencentcloudapi.com",
        "model": "hunyuan-vision",
        "config": {}
    },
    "wanxiang": {
        "category": "Video",
        "name": "Aliyun Wanxiang",
        "base_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis",
        "model": "wanx2.1-kf2v-plus",
        "config": {}
    },
    "kie": {
        "category": "Video",
        "name": "KIE AI",
        "base_url": "https://api.kie.ai",
        "model": "veo3-fast",
        "config": {
            "endpoint": "https://api.kie.ai/api/v1/jobs/createTask",
            "query_endpoint": "https://api.kie.ai/api/v1/jobs/recordInfo"
        }
    }
}

@router.get("/settings", response_model=List[APISettingOut])
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        _ensure_default_system_selection_for_user(db, current_user.id)

        rows = db.query(APISetting).filter(APISetting.user_id == current_user.id).all()
        result: List[APISettingOut] = []
        for row in rows:
            result.append(APISettingOut(
                id=row.id,
                user_id=row.user_id,
                name=row.name,
                provider=row.provider,
                category=row.category,
                api_key=row.api_key,
                base_url=row.base_url,
                model=row.model,
                config=_safe_json_dict(row.config),
                is_active=bool(row.is_active),
            ))
        return result
    except Exception as exc:
        logger.exception("Failed to get settings for user_id=%s: %s", getattr(current_user, "id", None), exc)
        try:
            db.rollback()
        except Exception:
            pass
        return []

@router.post("/settings", response_model=APISettingOut)
def update_setting(
    setting_in: APISettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    
    # Identify Category
    provider = setting_in.provider
    default_info = DEFAULTS.get(provider, {})
    category = setting_in.category or default_info.get("category", "LLM")
    
    # If this request is setting item to Active, we must deactivate others in same category
    if setting_in.is_active:
        existing_active = db.query(APISetting).filter(
            APISetting.user_id == current_user.id,
            APISetting.category == category,
            APISetting.is_active == True
        ).all()
        for s in existing_active:
            s.is_active = False
            
    # Check if we are updating an existing ID
    if setting_in.id:
        db_setting = db.query(APISetting).filter(APISetting.id == setting_in.id, APISetting.user_id == current_user.id).first()
        if not db_setting:
            raise HTTPException(status_code=404, detail="Setting not found")
            
        # Update fields
        # Loop through fields in schema but skip None
        update_data = setting_in.dict(exclude_unset=True)
        for key, value in update_data.items():
            if key != 'id':
                setattr(db_setting, key, value)
                
        # Ensure category is set if missing
        if not db_setting.category:
            db_setting.category = category

        if not db_setting.provider and provider:
            db_setting.provider = provider
            
    else:
        # Create New
        if not provider:
            raise HTTPException(status_code=400, detail="provider is required when creating a setting")

        new_setting = APISetting(
            user_id=current_user.id,
            name=setting_in.name or default_info.get("name", provider),
            category=category,
            provider=provider,
            api_key=setting_in.api_key or "",
            base_url=setting_in.base_url or default_info.get("base_url"),
            model=setting_in.model or default_info.get("model"),
            config=setting_in.config or default_info.get("config"),
            is_active=setting_in.is_active
        )
        db.add(new_setting)
        db_setting = new_setting

    # Provider-level shared key strategy:
    # Same user + same provider should share one API key across multiple model rows.
    effective_provider = db_setting.provider
    effective_key = _sync_provider_shared_key(
        db,
        current_user.id,
        effective_provider,
        db_setting.id or -1,
        setting_in.api_key,
    )
    db_setting.api_key = effective_key

    db.commit()
    db.refresh(db_setting)
    return db_setting


@router.get("/settings/system", response_model=List[SystemAPIProviderSettings])
def get_system_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_use_system_settings(current_user):
        return []

    try:
        _ensure_builtin_system_settings(db)

        _ensure_default_system_selection_for_user(db, current_user.id)
        db.commit()

        system_settings = db.query(
            SystemAPISetting.id,
            SystemAPISetting.name,
            SystemAPISetting.provider,
            SystemAPISetting.category,
            SystemAPISetting.model,
            SystemAPISetting.base_url,
            SystemAPISetting.api_key,
            SystemAPISetting.deprecated.label("deprecated_flag"),
            cast(SystemAPISetting.config, String).label("config_raw"),
        ).filter(
            SystemAPISetting.category != "System_Payment"
        ).all()

        user_active_by_category: Dict[str, Dict] = {}
        user_active_rows = db.query(
            APISetting.id,
            APISetting.category,
            APISetting.provider,
            APISetting.model,
            cast(APISetting.config, String).label("config_raw"),
        ).filter(
            APISetting.user_id == current_user.id,
            APISetting.is_active == True,
        ).all()
        for row in user_active_rows:
            cat = row.category or "LLM"
            row_data = {
                "id": row.id,
                "category": row.category,
                "provider": row.provider,
                "model": row.model,
                "config": _safe_json_dict(getattr(row, "config_raw", None)),
            }
            if cat not in user_active_by_category or (row.id or 0) > (user_active_by_category[cat].get("id") or 0):
                user_active_by_category[cat] = row_data

        grouped: Dict[Tuple[str, str], Dict] = {}
        for item in system_settings:
            provider = item.provider or "unknown"
            category = item.category or "LLM"
            item_config = _safe_json_dict(getattr(item, "config_raw", None))
            if getattr(item, "config_raw", None) and not item_config:
                logger.warning(
                    "Invalid JSON in system setting config, fallback to empty dict | setting_id=%s provider=%s category=%s",
                    item.id,
                    provider,
                    category,
                )
            key = (provider, category)
            if key not in grouped:
                grouped[key] = {
                    "provider": provider,
                    "category": category,
                    "shared_key_configured": False,
                    "models_map": {},
                }

            key_pool = _normalize_api_keys((item_config or {}).get("provider_api_keys"))
            fallback_key = str(item.api_key or "").strip()
            runtime_key = key_pool[0] if key_pool else fallback_key
            has_key = bool(runtime_key)
            grouped[key]["shared_key_configured"] = grouped[key]["shared_key_configured"] or has_key

            user_active = user_active_by_category.get(category)
            user_is_active_for_row = False
            if user_active:
                user_is_active_for_row = (
                    (user_active.get("provider") == item.provider)
                    and ((user_active.get("model") or "") == (item.model or ""))
                )

            option = SystemAPIModelOption(
                id=item.id,
                name=item.name,
                provider=provider,
                category=category,
                model=item.model,
                base_url=item.base_url,
                webhook_url=(item_config or {}).get("webHook"),
                deprecated=_is_setting_deprecated(item_config, getattr(item, "deprecated_flag", None)),
                is_active=bool(user_is_active_for_row),
                has_api_key=has_key,
                api_key_masked=_mask_api_key(runtime_key) if has_key else "",
            )

            if option.deprecated:
                continue

            model_key = str(item.model or "").strip().lower()
            existing_option = grouped[key]["models_map"].get(model_key)
            if existing_option is None or (option.id or 0) >= (existing_option.id or 0):
                grouped[key]["models_map"][model_key] = option

        result = []
        for _, row in grouped.items():
            row["models"] = sorted(list(row.get("models_map", {}).values()), key=lambda m: (m.model or "", m.id))
            row.pop("models_map", None)
            if not row["models"]:
                continue
            result.append(SystemAPIProviderSettings(**row))

        return sorted(result, key=lambda r: (r.category, r.provider))
    except Exception as exc:
        logger.exception("Failed to load system settings for user_id=%s: %s", getattr(current_user, "id", None), exc)
        try:
            db.rollback()
        except Exception:
            pass
        return []


@router.get("/settings/system/catalog", response_model=List[SystemAPIProviderModelCatalog])
def get_system_settings_catalog(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_use_system_settings(current_user) and not _can_manage_system_settings(current_user):
        return []

    _ensure_builtin_system_settings(db)
    db.commit()

    grouped: Dict[Tuple[str, str], set] = {}

    pricing_rows = db.query(PricingRule.provider, PricingRule.model, PricingRule.task_type).all()
    for provider, model, task_type in pricing_rows:
        provider_name = (provider or "").strip()
        if not provider_name:
            continue
        category = _task_type_to_category(task_type)
        key = (category, provider_name)
        if key not in grouped:
            grouped[key] = set()
        if (model or "").strip():
            grouped[key].add(model.strip())

    setting_rows = db.query(SystemAPISetting.provider, SystemAPISetting.model, SystemAPISetting.category).filter(
        SystemAPISetting.provider.isnot(None)
    ).all()
    for provider, model, category in setting_rows:
        provider_name = (provider or "").strip()
        if not provider_name:
            continue
        cat = (category or "Tools").strip() or "Tools"
        key = (cat, provider_name)
        if key not in grouped:
            grouped[key] = set()
        if (model or "").strip():
            grouped[key].add(model.strip())

    result = [
        SystemAPIProviderModelCatalog(
            category=category,
            provider=provider,
            models=sorted(models),
        )
        for (category, provider), models in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1]))
    ]
    return result


@router.post("/settings/system/select", response_model=APISettingOut)
def select_system_setting(
    selection: SystemAPISelectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    system_setting = db.query(SystemAPISetting).filter(
        SystemAPISetting.id == selection.setting_id,
    ).first()
    if not system_setting:
        raise HTTPException(status_code=404, detail="System API setting not found")

    if _is_setting_deprecated(system_setting.config, system_setting.deprecated):
        raise HTTPException(status_code=400, detail="This system API setting is deprecated and cannot be activated")

    # Enforce one-active-per-category for current user.
    db.query(APISetting).filter(
        APISetting.user_id == current_user.id,
        APISetting.category == system_setting.category,
        APISetting.is_active == True,
    ).update({"is_active": False})

    user_setting = db.query(APISetting).filter(
        APISetting.user_id == current_user.id,
        APISetting.provider == system_setting.provider,
        APISetting.category == system_setting.category,
        APISetting.model == system_setting.model,
    ).first()

    marker_config = dict(system_setting.config or {})
    marker_config["selection_source"] = "system"

    if user_setting:
        user_setting.name = user_setting.name or f"Use System {system_setting.provider}"
        user_setting.base_url = system_setting.base_url
        user_setting.model = system_setting.model
        user_setting.config = marker_config
        user_setting.is_active = True
        # Keep API key empty to force runtime lookup from system-side key.
        user_setting.api_key = ""
        selected = user_setting
    else:
        selected = APISetting(
            user_id=current_user.id,
            name=f"Use System {system_setting.provider}",
            category=system_setting.category,
            provider=system_setting.provider,
            api_key="",
            base_url=system_setting.base_url,
            model=system_setting.model,
            config=marker_config,
            is_active=True,
        )
        db.add(selected)

    db.commit()
    db.refresh(selected)
    return selected


@router.get("/settings/system/manage", response_model=List[SystemAPISettingOut])
def list_system_settings_for_manage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    _ensure_builtin_system_settings(db)
    migrated_count = _migrate_legacy_pricing_rules_to_system_api_pricing(db)
    if migrated_count:
        logger.info("[system_api.pricing.migrate] migrated_rows=%s", migrated_count)
    db.commit()

    rows = db.query(SystemAPISetting).filter(
        SystemAPISetting.category != "System_Payment",
    ).order_by(SystemAPISetting.category.asc(), SystemAPISetting.provider.asc(), SystemAPISetting.model.asc(), SystemAPISetting.id.asc()).all()
    return [
        SystemAPISettingOut(
            id=row.id,
            name=row.name,
            category=row.category,
            provider=row.provider,
            api_key=row.api_key,
            base_url=row.base_url,
            model=row.model,
            config=_normalize_system_api_billing_config(row.config),
            deprecated=_is_setting_deprecated(row.config, row.deprecated),
            is_active=bool(row.is_active),
        )
        for row in rows
    ]


@router.get("/settings/system/agent/tools-policy", response_model=AgentToolPolicyOut)
def get_agent_tool_policy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage agent tool policy")

    row = _get_or_create_agent_policy_row(db)
    db.commit()
    db.refresh(row)
    cfg = _safe_json_dict(row.config)
    normalized = _normalize_agent_tool_policy(cfg.get("agent_tool_policy", {}))
    return AgentToolPolicyOut(**normalized)


@router.put("/settings/system/agent/tools-policy", response_model=AgentToolPolicyOut)
def update_agent_tool_policy(
    payload: AgentToolPolicyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage agent tool policy")

    row = _get_or_create_agent_policy_row(db)
    cfg = _safe_json_dict(row.config)
    cfg["agent_tool_policy"] = _normalize_agent_tool_policy(payload.dict())
    row.config = cfg
    db.commit()
    db.refresh(row)

    normalized = _normalize_agent_tool_policy(_safe_json_dict(row.config).get("agent_tool_policy", {}))
    return AgentToolPolicyOut(**normalized)


@router.post("/settings/system/ai-assistant/analyze", response_model=SystemAIAssistantResponse)
def analyze_system_ai_assistant(
    payload: SystemAIAssistantRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only superuser can use system AI assistant")

    suggestions = _build_system_ai_suggestions(payload, db)
    return SystemAIAssistantResponse(
        provider=str(payload.provider or "").strip(),
        multiplier=(_safe_non_negative_float(payload.multiplier) or 1.0),
        suggestions=suggestions,
        applied_count=0,
    )


@router.post("/settings/system/ai-assistant/apply", response_model=SystemAIAssistantResponse)
def apply_system_ai_assistant(
    payload: SystemAIAssistantRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only superuser can use system AI assistant")

    suggestions = _build_system_ai_suggestions(payload, db)
    applied_count = 0
    now_iso = datetime.utcnow().isoformat()

    for suggestion in suggestions:
        existing = _find_system_setting_by_normalized_triplet(db, suggestion.provider, suggestion.category, suggestion.model)

        supplier_pricing = {
            "unit_type": suggestion.unit_type,
            "supplier_price": suggestion.supplier_price,
            "supplier_price_input": suggestion.supplier_price_input,
            "supplier_price_output": suggestion.supplier_price_output,
            "source": "provider_input",
            "updated_at": now_iso,
        }
        pricing_scheme = {
            "strategy": "supplier_price_x_multiplier",
            "multiplier": suggestion.multiplier,
            "computed_at": now_iso,
        }
        normalized_cfg = _normalize_system_api_billing_config({
            "api_pricing": {
                "unit_type": suggestion.unit_type,
                "cost": suggestion.cost,
                "cost_input": suggestion.cost_input,
                "cost_output": suggestion.cost_output,
            }
        })
        normalized_cfg["supplier_pricing"] = supplier_pricing
        normalized_cfg["pricing_scheme"] = pricing_scheme

        if existing:
            existing.name = suggestion.name or existing.name
            if suggestion.base_url:
                existing.base_url = suggestion.base_url
            existing.config = {**_safe_json_dict(existing.config), **normalized_cfg}
            existing.is_active = bool(existing.is_active)
        else:
            existing = SystemAPISetting(
                name=suggestion.name or f"{suggestion.provider} {suggestion.model}",
                category=suggestion.category,
                provider=suggestion.provider,
                api_key="",
                base_url=suggestion.base_url,
                model=suggestion.model,
                deprecated=False,
                config=normalized_cfg,
                is_active=False,
            )
            db.add(existing)

        applied_count += 1

    db.commit()
    return SystemAIAssistantResponse(
        provider=str(payload.provider or "").strip(),
        multiplier=(_safe_non_negative_float(payload.multiplier) or 1.0),
        suggestions=suggestions,
        applied_count=applied_count,
    )


@router.post("/settings/system/manage", response_model=SystemAPISettingOut)
def create_system_setting_for_manage(
    payload: SystemAPISettingManageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    provider = (payload.provider or "").strip()
    if not provider:
        raise HTTPException(status_code=400, detail="provider is required")

    category = (payload.category or "LLM").strip() or "LLM"
    model = (payload.model or "").strip()
    existing = _find_system_setting_by_normalized_triplet(db, provider, category, model)
    if existing:
        target_cfg = payload.config if isinstance(payload.config, dict) else _safe_json_dict(existing.config)
        target_cfg = _normalize_system_api_billing_config(target_cfg)
        existing.name = (payload.name or existing.name or "System Setting").strip() or "System Setting"
        existing.base_url = payload.base_url
        existing.model = payload.model
        existing.config = target_cfg
        existing.is_active = bool(payload.is_active)

        effective_key = _sync_system_provider_shared_key(
            db,
            existing.provider,
            existing.id,
            payload.api_key,
        )
        existing.api_key = effective_key

        if existing.is_active:
            db.query(SystemAPISetting).filter(
                SystemAPISetting.category == existing.category,
                SystemAPISetting.id != existing.id,
                SystemAPISetting.is_active == True,
            ).update({"is_active": False})

        db.commit()
        db.refresh(existing)
        out_cfg = _safe_json_dict(existing.config)
        return SystemAPISettingOut(
            id=existing.id,
            name=existing.name,
            category=existing.category,
            provider=existing.provider,
            api_key=existing.api_key,
            base_url=existing.base_url,
            model=existing.model,
            config=out_cfg,
            deprecated=_is_setting_deprecated(out_cfg, existing.deprecated),
            is_active=bool(existing.is_active),
        )

    create_config = payload.config if isinstance(payload.config, dict) else {}
    create_config = _normalize_system_api_billing_config(create_config)
    new_setting = SystemAPISetting(
        name=(payload.name or "System Setting").strip() or "System Setting",
        category=category,
        provider=provider,
        api_key="",
        base_url=payload.base_url,
        model=payload.model,
        deprecated=False,
        config=create_config,
        is_active=bool(payload.is_active),
    )
    db.add(new_setting)
    db.flush()

    # Keep provider-level key shared across all system rows for the same provider.
    effective_key = _sync_system_provider_shared_key(
        db,
        new_setting.provider,
        new_setting.id,
        payload.api_key,
    )
    new_setting.api_key = effective_key

    if new_setting.is_active:
        db.query(SystemAPISetting).filter(
            SystemAPISetting.category == new_setting.category,
            SystemAPISetting.id != new_setting.id,
            SystemAPISetting.is_active == True,
        ).update({"is_active": False})

    db.commit()
    db.refresh(new_setting)
    out_cfg = _safe_json_dict(new_setting.config)
    return SystemAPISettingOut(
        id=new_setting.id,
        name=new_setting.name,
        category=new_setting.category,
        provider=new_setting.provider,
        api_key=new_setting.api_key,
        base_url=new_setting.base_url,
        model=new_setting.model,
        config=out_cfg,
        deprecated=_is_setting_deprecated(out_cfg, new_setting.deprecated),
        is_active=bool(new_setting.is_active),
    )


@router.post("/settings/system/manage/{setting_id}", response_model=SystemAPISettingOut)
def update_system_setting_for_manage(
    setting_id: int,
    payload: SystemAPISettingManageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    target = db.query(SystemAPISetting).filter(
        SystemAPISetting.id == setting_id,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="System API setting not found")

    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(target, key, value)

    target.config = _normalize_system_api_billing_config(target.config)

    if payload.is_active:
        db.query(SystemAPISetting).filter(
            SystemAPISetting.category == target.category,
            SystemAPISetting.id != target.id,
            SystemAPISetting.is_active == True,
        ).update({"is_active": False})

    # Keep provider-level key shared among system rows as well.
    effective_key = _sync_system_provider_shared_key(
        db,
        target.provider,
        target.id,
        payload.api_key,
    )
    target.api_key = effective_key

    db.commit()
    db.refresh(target)
    out_cfg = _safe_json_dict(target.config)
    return SystemAPISettingOut(
        id=target.id,
        name=target.name,
        category=target.category,
        provider=target.provider,
        api_key=target.api_key,
        base_url=target.base_url,
        model=target.model,
        config=out_cfg,
        deprecated=_is_setting_deprecated(out_cfg, target.deprecated),
        is_active=bool(target.is_active),
    )


@router.post("/settings/system/manage/{setting_id}/deprecated", response_model=SystemAPISettingOut)
def toggle_system_setting_deprecated_for_manage(
    setting_id: int,
    payload: SystemAPISettingToggleDeprecatedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    target = db.query(SystemAPISetting).filter(
        SystemAPISetting.id == setting_id,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="System API setting not found")

    logger.warning(
        "[system_api.deprecated.toggle_by_id] request user_id=%s setting_id=%s provider=%s category=%s model=%s payload_deprecated=%s before_deprecated_col=%s before_config=%s",
        getattr(current_user, "id", None),
        target.id,
        target.provider,
        target.category,
        target.model,
        payload.deprecated,
        target.deprecated,
        target.config,
    )
    print(f"[DBG toggle_by_id request] setting_id={target.id} provider={target.provider} category={target.category} model={target.model} payload_deprecated={payload.deprecated} before_col={target.deprecated} before_cfg={target.config}")

    cfg = dict(_safe_json_dict(target.config))
    current = _is_setting_deprecated(cfg, target.deprecated)
    next_value = (not current) if payload.deprecated is None else bool(payload.deprecated)

    cfg["deprecated"] = bool(next_value)
    # Keep legacy aliases aligned for compatibility.
    cfg["is_deprecated"] = bool(next_value)
    cfg["disable_api"] = bool(next_value)

    # Always force-update the requested row id first.
    db.query(SystemAPISetting).filter(SystemAPISetting.id == target.id).update(
        {"config": cfg, "deprecated": bool(next_value)},
        synchronize_session=False,
    )

    provider_norm = str(target.provider or "").strip().lower()
    category_norm = str(target.category or "").strip().lower()
    model_norm = str(target.model or "").strip().lower()

    duplicate_query = db.query(SystemAPISetting).filter(
        func.lower(func.trim(func.coalesce(SystemAPISetting.provider, ""))) == provider_norm,
        func.lower(func.trim(func.coalesce(SystemAPISetting.category, ""))) == category_norm,
        func.lower(func.trim(func.coalesce(SystemAPISetting.model, ""))) == model_norm,
    )

    duplicate_rows = duplicate_query.all()
    if not duplicate_rows:
        duplicate_rows = [target]

    logger.warning(
        "[system_api.deprecated.toggle_by_id] matched_rows setting_id=%s matched_ids=%s normalized_key=(%s,%s,%s) next_value=%s",
        target.id,
        [row.id for row in duplicate_rows],
        provider_norm,
        category_norm,
        model_norm,
        next_value,
    )
    print(f"[DBG toggle_by_id matched] setting_id={target.id} matched_ids={[row.id for row in duplicate_rows]} normalized_key=({provider_norm},{category_norm},{model_norm}) next_value={next_value}")

    for row in duplicate_rows:
        if row.id == target.id:
            continue
        row_cfg = dict(_safe_json_dict(row.config))
        row_cfg["deprecated"] = bool(next_value)
        row_cfg["is_deprecated"] = bool(next_value)
        row_cfg["disable_api"] = bool(next_value)
        db.query(SystemAPISetting).filter(SystemAPISetting.id == row.id).update(
            {"config": row_cfg, "deprecated": bool(next_value)},
            synchronize_session=False,
        )

    db.commit()
    db.refresh(target)
    logger.warning(
        "[system_api.deprecated.toggle_by_id] committed setting_id=%s target_deprecated_col=%s target_config=%s",
        target.id,
        target.deprecated,
        target.config,
    )
    print(f"[DBG toggle_by_id committed] setting_id={target.id} after_col={target.deprecated} after_cfg={target.config}")
    if bool(target.deprecated) != bool(next_value):
        logger.error(
            "[system_api.deprecated.toggle_by_id] persistence_mismatch setting_id=%s expected=%s actual_col=%s actual_config=%s",
            target.id,
            next_value,
            target.deprecated,
            target.config,
        )
        raise HTTPException(status_code=500, detail=f"Deprecated persistence mismatch for setting_id={target.id}")
    out_cfg = _safe_json_dict(target.config)
    return SystemAPISettingOut(
        id=target.id,
        name=target.name,
        category=target.category,
        provider=target.provider,
        api_key=target.api_key,
        base_url=target.base_url,
        model=target.model,
        config=out_cfg,
        deprecated=_is_setting_deprecated(out_cfg, target.deprecated),
        is_active=bool(target.is_active),
    )


@router.post("/settings/system/manage/deprecated/by-key", response_model=SystemAPISettingOut)
def toggle_system_setting_deprecated_by_key_for_manage(
    payload: SystemAPISettingToggleDeprecatedByKeyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    provider_norm = str(payload.provider or "").strip().lower()
    category_norm = str(payload.category or "").strip().lower()
    model_norm = str(payload.model or "").strip().lower()
    if not provider_norm or not category_norm:
        raise HTTPException(status_code=400, detail="provider and category are required")

    logger.warning(
        "[system_api.deprecated.toggle_by_key] request user_id=%s provider=%s category=%s model=%s setting_id=%s payload_deprecated=%s",
        getattr(current_user, "id", None),
        payload.provider,
        payload.category,
        payload.model,
        payload.setting_id,
        payload.deprecated,
    )
    print(f"[DBG toggle_by_key request] provider={payload.provider} category={payload.category} model={payload.model} setting_id={payload.setting_id} payload_deprecated={payload.deprecated}")

    query = db.query(SystemAPISetting).filter(
        func.lower(func.trim(func.coalesce(SystemAPISetting.provider, ""))) == provider_norm,
        func.lower(func.trim(func.coalesce(SystemAPISetting.category, ""))) == category_norm,
        func.lower(func.trim(func.coalesce(SystemAPISetting.model, ""))) == model_norm,
    )
    rows = query.order_by(SystemAPISetting.id.asc()).all()
    if not rows and payload.setting_id:
        fallback = db.query(SystemAPISetting).filter(SystemAPISetting.id == int(payload.setting_id)).first()
        if fallback:
            rows = [fallback]
            logger.warning(
                "[system_api.deprecated.toggle_by_key] fallback_to_id matched setting_id=%s provider=%s category=%s model=%s",
                fallback.id,
                fallback.provider,
                fallback.category,
                fallback.model,
            )
            print(f"[DBG toggle_by_key fallback] fallback_id={fallback.id} provider={fallback.provider} category={fallback.category} model={fallback.model}")
    if not rows:
        raise HTTPException(status_code=404, detail="System API setting not found for provider/category/model")

    latest = sorted(rows, key=lambda r: r.id, reverse=True)[0]
    current = _is_setting_deprecated(latest.config, latest.deprecated)
    next_value = (not current) if payload.deprecated is None else bool(payload.deprecated)

    logger.warning(
        "[system_api.deprecated.toggle_by_key] matched_rows ids=%s latest_id=%s current=%s next=%s",
        [row.id for row in rows],
        latest.id,
        current,
        next_value,
    )
    print(f"[DBG toggle_by_key matched] ids={[row.id for row in rows]} latest_id={latest.id} current={current} next={next_value}")

    for row in rows:
        row_cfg = dict(_safe_json_dict(row.config))
        row_cfg["deprecated"] = bool(next_value)
        row_cfg["is_deprecated"] = bool(next_value)
        row_cfg["disable_api"] = bool(next_value)
        db.query(SystemAPISetting).filter(SystemAPISetting.id == row.id).update(
            {"config": row_cfg, "deprecated": bool(next_value)},
            synchronize_session=False,
        )

    db.commit()
    db.refresh(latest)
    logger.warning(
        "[system_api.deprecated.toggle_by_key] committed latest_id=%s latest_deprecated_col=%s latest_config=%s",
        latest.id,
        latest.deprecated,
        latest.config,
    )
    print(f"[DBG toggle_by_key committed] latest_id={latest.id} after_col={latest.deprecated} after_cfg={latest.config}")

    out_cfg = _safe_json_dict(latest.config)
    return SystemAPISettingOut(
        id=latest.id,
        name=latest.name,
        category=latest.category,
        provider=latest.provider,
        api_key=latest.api_key,
        base_url=latest.base_url,
        model=latest.model,
        config=out_cfg,
        deprecated=_is_setting_deprecated(out_cfg, latest.deprecated),
        is_active=bool(latest.is_active),
    )


@router.post("/settings/system/manage/provider/{provider}/deprecated")
def batch_toggle_system_provider_deprecated_for_manage(
    provider: str,
    payload: SystemAPIProviderBatchDeprecatedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    provider_name = str(provider or "").strip()
    if not provider_name:
        raise HTTPException(status_code=400, detail="provider is required")

    query = db.query(SystemAPISetting).filter(SystemAPISetting.provider == provider_name)
    category = str(payload.category or "").strip()
    if category:
        query = query.filter(SystemAPISetting.category == category)

    rows = query.order_by(SystemAPISetting.id.asc()).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No system API settings found for provider")

    changed = 0
    next_value = bool(payload.deprecated)
    for row in rows:
        cfg = dict(_safe_json_dict(row.config))
        current = _is_setting_deprecated(cfg, row.deprecated)
        if current != next_value:
            changed += 1
        cfg["deprecated"] = next_value
        cfg["is_deprecated"] = next_value
        cfg["disable_api"] = next_value
        db.query(SystemAPISetting).filter(SystemAPISetting.id == row.id).update(
            {"config": cfg, "deprecated": next_value},
            synchronize_session=False,
        )

    db.commit()

    return {
        "ok": True,
        "provider": provider_name,
        "category": category or None,
        "deprecated": next_value,
        "matched": len(rows),
        "changed": changed,
    }


@router.get("/settings/system/manage/provider/{provider}/keys")
def get_system_provider_keys_for_manage(
    provider: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    provider_name = str(provider or "").strip()
    if not provider_name:
        raise HTTPException(status_code=400, detail="provider is required")

    pool = _get_system_provider_key_pool(db, provider_name)
    first_row = db.query(SystemAPISetting).filter(SystemAPISetting.provider == provider_name).order_by(SystemAPISetting.id.asc()).first()
    cfg = _safe_json_dict(first_row.config if first_row else {})
    strategy = _normalize_key_strategy(cfg.get("provider_api_key_strategy"))
    weights = _normalize_key_weights(cfg.get("provider_api_key_weights"), pool)
    return {
        "provider": provider_name,
        "key_count": len(pool),
        "keys": pool,
        "keys_masked": [_mask_api_key(k) for k in pool],
        "strategy": strategy,
        "weights": weights,
    }


@router.post("/settings/system/manage/provider/{provider}/keys")
def set_system_provider_keys_for_manage(
    provider: str,
    payload: SystemAPIProviderKeysUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    provider_name = str(provider or "").strip()
    if not provider_name:
        raise HTTPException(status_code=400, detail="provider is required")

    rows = db.query(SystemAPISetting).filter(SystemAPISetting.provider == provider_name).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No system API settings found for provider")

    pool = _normalize_api_keys(payload.keys)
    strategy = _normalize_key_strategy(payload.strategy)
    weights = _normalize_key_weights(payload.weights, pool)

    rows = db.query(SystemAPISetting).filter(SystemAPISetting.provider == provider_name).all()
    primary_key = pool[0] if pool else ""
    for row in rows:
        cfg = _safe_json_dict(row.config)
        cfg["provider_api_keys"] = pool
        cfg["provider_api_key_strategy"] = strategy
        cfg["provider_api_key_weights"] = weights
        row.config = cfg
        row.api_key = primary_key
    db.commit()

    return {
        "ok": True,
        "provider": provider_name,
        "key_count": len(pool),
        "keys_masked": [_mask_api_key(k) for k in pool],
        "strategy": strategy,
        "weights": weights,
    }


@router.get("/settings/system/manage/export")
def export_system_settings_for_manage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    _ensure_builtin_system_settings(db)
    db.commit()

    rows = db.query(SystemAPISetting).filter(
        SystemAPISetting.category != "System_Payment",
    ).order_by(SystemAPISetting.category.asc(), SystemAPISetting.provider.asc(), SystemAPISetting.model.asc(), SystemAPISetting.id.asc()).all()

    return {
        "version": 1,
        "exported_at": datetime.utcnow().isoformat(),
        "count": len(rows),
        "items": [
            {
                "name": row.name,
                "category": row.category,
                "provider": row.provider,
                "api_key": row.api_key,
                "base_url": row.base_url,
                "model": row.model,
                "config": row.config or {},
                "deprecated": bool(row.deprecated),
                "is_active": bool(row.is_active),
            }
            for row in rows
        ],
    }


@router.get("/settings/system/manage/provider-bundle/export")
def export_system_provider_bundle_for_manage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    _ensure_builtin_system_settings(db)
    db.commit()

    rows = db.query(SystemAPISetting).filter(
        SystemAPISetting.category != "System_Payment",
    ).order_by(SystemAPISetting.provider.asc(), SystemAPISetting.category.asc(), SystemAPISetting.model.asc(), SystemAPISetting.id.asc()).all()

    grouped: Dict[str, List[SystemAPISetting]] = {}
    for row in rows:
        provider_name = str(row.provider or "").strip()
        if not provider_name:
            continue
        grouped.setdefault(provider_name, []).append(row)

    providers = []
    for provider_name, provider_rows in grouped.items():
        first_cfg = _safe_json_dict(provider_rows[0].config if provider_rows else {})
        keys = _get_system_provider_key_pool(db, provider_name)
        strategy = _normalize_key_strategy(first_cfg.get("provider_api_key_strategy"))
        weights = _normalize_key_weights(first_cfg.get("provider_api_key_weights"), keys)
        models = [
            {
                "name": row.name,
                "category": row.category,
                "base_url": row.base_url,
                "model": row.model,
                "config": row.config or {},
                "deprecated": bool(row.deprecated),
                "is_active": bool(row.is_active),
            }
            for row in provider_rows
        ]
        providers.append({
            "provider": provider_name,
            "api_keys": keys,
            "strategy": strategy,
            "weights": weights,
            "model_count": len(models),
            "models": models,
        })

    return {
        "version": 1,
        "format": "provider_bundle",
        "exported_at": datetime.utcnow().isoformat(),
        "provider_count": len(providers),
        "providers": providers,
    }


@router.post("/settings/system/manage/provider-bundle/import")
def import_system_provider_bundle_for_manage(
    payload: SystemAPIProviderImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    try:
        providers = payload.providers or []
        if not providers:
            return {"ok": True, "providers": 0, "created": 0, "updated": 0, "key_updated_providers": 0, "total": 0}

        if payload.replace_all:
            db.query(SystemAPISetting).filter(
                SystemAPISetting.category != "System_Payment",
            ).delete(synchronize_session=False)
            db.flush()

        created = 0
        updated = 0
        key_updated_providers = 0
        providers_processed = 0
        skipped_models = 0
        last_active_id_by_category: Dict[str, int] = {}

        for provider_item in providers:
            provider_name = str(provider_item.provider or "").strip()
            if not provider_name:
                continue

            providers_processed += 1
            keys = _normalize_api_keys(provider_item.api_keys)
            strategy = _normalize_key_strategy(provider_item.strategy)
            weights = _normalize_key_weights(provider_item.weights, keys)
            models = provider_item.models or []

            for model_item in models:
                category = str(model_item.category or "LLM").strip() or "LLM"
                model = str(model_item.model or "").strip()
                if not model:
                    skipped_models += 1
                    continue

                target = _find_system_setting_by_normalized_triplet(db, provider_name, category, model)

                normalized_cfg = _normalize_system_api_billing_config(
                    model_item.config if isinstance(model_item.config, dict) else {}
                )

                if target:
                    target.name = (model_item.name or target.name or "System Setting").strip() or "System Setting"
                    target.base_url = model_item.base_url
                    target.model = model
                    target.config = normalized_cfg
                    target.deprecated = _is_setting_deprecated(target.config, model_item.deprecated)
                    target.is_active = bool(model_item.is_active)
                    updated += 1
                else:
                    target = SystemAPISetting(
                        name=(model_item.name or "System Setting").strip() or "System Setting",
                        category=category,
                        provider=provider_name,
                        api_key="",
                        base_url=model_item.base_url,
                        model=model,
                        deprecated=_is_setting_deprecated(normalized_cfg, model_item.deprecated),
                        config=normalized_cfg,
                        is_active=bool(model_item.is_active),
                    )
                    db.add(target)
                    db.flush()
                    created += 1

                if bool(model_item.is_active):
                    last_active_id_by_category[category] = target.id

            provider_rows = db.query(SystemAPISetting).filter(
                SystemAPISetting.provider == provider_name,
                SystemAPISetting.category != "System_Payment",
            ).all()
            if provider_rows:
                _apply_provider_key_bundle_to_rows(provider_rows, keys, strategy, weights)
                key_updated_providers += 1

        for category, keep_id in last_active_id_by_category.items():
            db.query(SystemAPISetting).filter(
                SystemAPISetting.category == category,
                SystemAPISetting.id != keep_id,
                SystemAPISetting.is_active == True,
            ).update({"is_active": False}, synchronize_session=False)

        db.commit()
        return {
            "ok": True,
            "providers": providers_processed,
            "created": created,
            "updated": updated,
            "key_updated_providers": key_updated_providers,
            "skipped_models": skipped_models,
            "total": created + updated,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to import provider bundle: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"provider bundle import failed: {type(exc).__name__}")


@router.post("/settings/system/manage/import")
def import_system_settings_for_manage(
    payload: SystemAPISettingImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    items = payload.items or []
    if not items:
        return {"ok": True, "created": 0, "updated": 0, "total": 0}

    if payload.replace_all:
        db.query(SystemAPISetting).filter(
            SystemAPISetting.category != "System_Payment",
        ).delete(synchronize_session=False)
        db.flush()

    created = 0
    updated = 0
    last_active_id_by_category: Dict[str, int] = {}

    for item in items:
        provider = (item.provider or "").strip()
        category = (item.category or "LLM").strip() or "LLM"
        model = (item.model or "").strip()
        if not provider:
            continue

        target = _find_system_setting_by_normalized_triplet(db, provider, category, model)

        if target:
            target.name = (item.name or target.name or "System Setting").strip() or "System Setting"
            target.base_url = item.base_url
            target.model = item.model
            target.config = _normalize_system_api_billing_config(item.config if isinstance(item.config, dict) else {})
            target.deprecated = _is_setting_deprecated(target.config, item.deprecated)
            target.is_active = bool(item.is_active)
            updated += 1
        else:
            target = SystemAPISetting(
                name=(item.name or "System Setting").strip() or "System Setting",
                category=category,
                provider=provider,
                api_key="",
                base_url=item.base_url,
                model=item.model,
                deprecated=_is_setting_deprecated(item.config if isinstance(item.config, dict) else {}, item.deprecated),
                config=_normalize_system_api_billing_config(item.config if isinstance(item.config, dict) else {}),
                is_active=bool(item.is_active),
            )
            db.add(target)
            db.flush()
            created += 1

        effective_key = _sync_system_provider_shared_key(
            db,
            target.provider,
            target.id,
            item.api_key,
        )
        target.api_key = effective_key

        if bool(item.is_active):
            last_active_id_by_category[category] = target.id

    for category, keep_id in last_active_id_by_category.items():
        db.query(SystemAPISetting).filter(
            SystemAPISetting.category == category,
            SystemAPISetting.id != keep_id,
            SystemAPISetting.is_active == True,
        ).update({"is_active": False}, synchronize_session=False)

    db.commit()
    return {
        "ok": True,
        "created": created,
        "updated": updated,
        "total": created + updated,
    }


@router.delete("/settings/system/manage/{setting_id}")
def delete_system_setting_for_manage(
    setting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    target = db.query(SystemAPISetting).filter(
        SystemAPISetting.id == setting_id,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="System API setting not found")

    db.delete(target)
    db.commit()
    return {"ok": True}

@router.delete("/settings/{setting_id}")
def delete_setting(
    setting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    setting = db.query(APISetting).filter(APISetting.id == setting_id, APISetting.user_id == current_user.id).first()
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
        
    db.delete(setting)
    db.commit()
    return {"ok": True}

@router.get("/settings/defaults")
def get_defaults():
    return DEFAULTS
