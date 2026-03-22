from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, load_only
from sqlalchemy import cast, String, func, inspect, or_, and_, text, Table, MetaData, bindparam
from sqlalchemy.exc import OperationalError
import logging
import csv
import io
import json
import asyncio
import os
import ast
import random
import re
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import math
from types import SimpleNamespace
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from app.db.session import get_db
from app.core.time_utils import now_bj_iso
from app.core.prompts.supplier_feature_analysis_prompt import get_supplier_feature_analysis_system_prompt
from app.models.all_models import (
    APISetting,
    User,
    TransactionHistory,
    SystemAPISetting,
    TaskDefaultSystemAPI,
    ProviderKeyPool,
    SystemAPIBillingRule,
    TransactionAction,
    SMTPSystemConfig,
    WechatPayConfig,
)
from app.services.system_default_api_service import (
    get_task_default_system_setting,
    is_task_default_system_setting,
    upsert_task_default_system_setting,
    clear_task_default_for_category,
    clear_task_defaults_for_system_api_ids,
    normalize_task_category,
)
from app.services.system_api_runtime_cache import invalidate_system_api_cache
from app.schemas.settings import (
    APISettingOut,
    APISettingUpdate,
    UserPreferencesOut,
    UserPreferencesUpdate,
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
    SystemConfigSyncBundleImportRequest,
    TaskDefaultSystemAPIManageCreate,
    TaskDefaultSystemAPIManageUpdate,
    TaskDefaultSystemAPIManageOut,
    AgentToolPolicyUpdate,
    AgentToolPolicyOut,
    BillingRuleResetConfigOut,
    BillingRuleResetConfigUpdate,
    SoraMentionConfigOut,
    SoraMentionConfigUpdate,
    SystemAIAssistantRequest,
    SystemAIAssistantResponse,
    SystemAIAssistantSuggestion,
    ExchangeRateRequest,
    ExchangeRateResponse,
    FetchPricingPageRequest,
    FetchPricingPageResponse,
    SupplierApiFeatureAnalyzeRequest,
    SupplierApiFeatureAnalyzeResponse,
    SupplierApiFeatureApplyRequest,
    SupplierApiFeatureApplyResponse,
    SupplierApiFeatureModel,
    KIEPricingGenerateRequest,
    KIEPricingApplyRequest,
    KIEPricingFetchRequest,
    KIEPricingFetchResponse,
    KIEPricingFetchPage,
    KIEPricingGenerateResponse,
    KIEPricingApplyResponse,
    KIEPricingRuleSuggestion,
    KIEPricingApplyReceipt,
    ProviderKeyPoolCreate,
    ProviderKeyPoolUpdate,
    ProviderKeyPoolOut,
    SystemAPIBillingRuleCreate,
    SystemAPIBillingRuleUpdate,
    SystemAPIBillingRuleOut,
    SystemAPIMissingBillingRuleOut,
    SystemAPIBillingRuleMultiplierResetRequest,
    SystemAPIBillingRuleMultiplierResetResponse,
    KIEDataStandardValueOut,
    KIEDataStandardValueCreate,
    KIEDataStandardValueExportResponse,
    KIEDataStandardValueImportRequest,
    KIEDataStandardValueImportResponse,
    KIEDataStandardMappingCreate,
    KIEDataStandardMappingUpdate,
    KIEDataStandardMappingOut,
    KIEDataStandardBillingInferenceResponse,
    KIEDataStandardMappingExportResponse,
    KIEDataStandardMappingImportRequest,
    KIEDataStandardMappingImportResponse,
    KIEDataDictionaryBundleExportResponse,
    KIEDataDictionaryBundleImportRequest,
    KIEDataDictionaryBundleImportResponse,
    KIEDataStandardValueMappingImportRequest,
)
from app.api.deps import get_current_user
from app.services.billing_service import BillingService

HAS_TASK_DEFAULT_SYSTEM_API_MODEL = True

router = APIRouter()
logger = logging.getLogger("settings_api")
logger.setLevel(logging.INFO)
api_logger = logging.getLogger("api_logger")

_PROVIDER_POOL_CACHE_TTL_SECONDS = 10.0
_provider_pool_cache = {
    "ts": 0.0,
    "runtime_key_map": {},
    "alias_map": {},
}
_settings_system_indexes_ensured = False
_api_settings_binding_columns_ensured = False

_AGENT_POLICY_CATEGORY = "System_Payment"
_AGENT_POLICY_PROVIDER = "agent_policy"
_AGENT_POLICY_MODEL = "tool_acl"
_BILLING_RESET_CONFIG_KEY = "billing_rule_reset_config"
_SORA_MENTION_CONFIG_KEY = "sora_mention_config"
_BILLING_RESET_MAX_INCREASE_DEFAULT = 50
_BILLING_RESET_MIN_MULTIPLIER_DEFAULT = 1.1
_BILLING_RESET_MAX_MULTIPLIER_DEFAULT = 2.0
_BILLING_RESET_DEFAULT_MULTIPLIER_DEFAULT = 2.0
_BILLING_RESET_BIN_SIZE_CREDITS_DEFAULT = 10
_BILLING_RESET_BIN_DROP_MULTIPLIER_DEFAULT = 0.1
_BASE_BILLING_RULE_KIND = "base_pricing"
_BASE_BILLING_RULE_PRIORITY = -100000
_KIE_GRANULAR_RULE_KIND = "kie_granular_pricing"
_KIE_HINT_TEMPLATE_LIMIT_PER_MODEL = 6
_KIE_TO_SYSTEM_CREDIT_RATIO = 3.0
_USD_TO_CNY_RATE = 7.0
_SYSTEM_CREDIT_PER_CNY = 100.0
_USER_API_STRATEGIES = {"fixed", "smart_default", "low_price_replace"}
_MODEL_MODE_DEFAULTS_KEY = "model_mode_defaults"
_MODEL_MODE_DEFAULTS_ALIASES = (
    "model_mode_defaults",
    "mode_by_model",
    "default_mode_by_model",
    "model_mode_bindings",
)


def _invalidate_provider_pool_cache() -> None:
    _provider_pool_cache["ts"] = 0.0
    _provider_pool_cache["runtime_key_map"] = {}
    _provider_pool_cache["alias_map"] = {}
    _provider_pool_cache["row_count"] = 0


def _invalidate_system_api_runtime_cache(refresh: bool = False) -> None:
    try:
        invalidate_system_api_cache(refresh=refresh)
    except Exception as exc:
        logger.warning("settings.system.runtime_cache_invalidate skipped: %s", str(exc)[:300])

_USER_PREF_ALLOWED_PROMPT_SUBMIT_LANGUAGE = {"en", "cn", "auto"}
_USER_PREF_ALLOWED_REASONING_EFFORT = {"low", "medium", "high"}
_USER_PREF_DEFAULTS: Dict[str, Any] = {
    "prompt_submit_language": "en",
    "auto_download_local": False,
    "generation": {},
    "advanced_model": {
        "temperature": 0.7,
        "seed": None,
        "cfg": None,
        "reasoning_effort": "high",
    },
}

def _normalize_prompt_submit_language(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"zh", "zh-cn"}:
        raw = "cn"
    return raw if raw in _USER_PREF_ALLOWED_PROMPT_SUBMIT_LANGUAGE else "en"


def _normalize_reasoning_effort(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return raw if raw in _USER_PREF_ALLOWED_REASONING_EFFORT else "high"


def _normalize_user_preferences(payload: Any) -> Dict[str, Any]:
    raw = _safe_json_dict(payload)
    defaults = dict(_USER_PREF_DEFAULTS)

    generation = raw.get("generation") if isinstance(raw.get("generation"), dict) else {}
    advanced_raw = raw.get("advanced_model") if isinstance(raw.get("advanced_model"), dict) else {}

    advanced_defaults = defaults.get("advanced_model") if isinstance(defaults.get("advanced_model"), dict) else {}
    advanced_model: Dict[str, Any] = {
        **advanced_defaults,
        **advanced_raw,
    }

    try:
        temp = float(advanced_model.get("temperature"))
        if not math.isfinite(temp):
            raise ValueError("not finite")
        advanced_model["temperature"] = max(0.0, min(2.0, temp))
    except Exception:
        advanced_model["temperature"] = float(advanced_defaults.get("temperature", 0.7))

    try:
        seed = advanced_model.get("seed")
        if seed is None or str(seed).strip() == "":
            advanced_model["seed"] = None
        else:
            parsed_seed = int(seed)
            advanced_model["seed"] = parsed_seed if parsed_seed > 0 else None
    except Exception:
        advanced_model["seed"] = None

    try:
        cfg = advanced_model.get("cfg")
        if cfg is None or str(cfg).strip() == "":
            advanced_model["cfg"] = None
        else:
            parsed_cfg = float(cfg)
            advanced_model["cfg"] = parsed_cfg if math.isfinite(parsed_cfg) and parsed_cfg > 0 else None
    except Exception:
        advanced_model["cfg"] = None

    advanced_model["reasoning_effort"] = _normalize_reasoning_effort(advanced_model.get("reasoning_effort"))

    return {
        "prompt_submit_language": _normalize_prompt_submit_language(raw.get("prompt_submit_language")),
        "auto_download_local": bool(raw.get("auto_download_local", False)),
        "generation": generation,
        "advanced_model": advanced_model,
    }


def _merge_user_preferences(current: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(current or {})
    for key in ("prompt_submit_language", "auto_download_local"):
        if key in patch:
            merged[key] = patch.get(key)

    if "generation" in patch and isinstance(patch.get("generation"), dict):
        current_generation = merged.get("generation") if isinstance(merged.get("generation"), dict) else {}
        merged["generation"] = {**current_generation, **patch.get("generation")}

    if "advanced_model" in patch and isinstance(patch.get("advanced_model"), dict):
        current_adv = merged.get("advanced_model") if isinstance(merged.get("advanced_model"), dict) else {}
        merged["advanced_model"] = {**current_adv, **patch.get("advanced_model")}

    return _normalize_user_preferences(merged)


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


def _get_or_create_agent_policy_row(db: Session) -> SimpleNamespace:
    row = db.execute(text("""
        SELECT id, config
        FROM system_api_settings
        WHERE category = :category
          AND provider = :provider
          AND model = :model
        ORDER BY id DESC
        LIMIT 1
    """), {
        "category": _AGENT_POLICY_CATEGORY,
        "provider": _AGENT_POLICY_PROVIDER,
        "model": _AGENT_POLICY_MODEL,
    }).mappings().first()

    if row and row.get("id") is not None:
        cfg = _safe_json_dict(row.get("config"))
        cfg["agent_tool_policy"] = _normalize_agent_tool_policy(cfg.get("agent_tool_policy", {}))
        return SimpleNamespace(id=int(row["id"]), config=cfg)

    cfg = {"agent_tool_policy": _default_agent_tool_policy()}
    db.execute(text("""
        INSERT INTO system_api_settings (
            name,
            category,
            provider,
            api_key,
            base_url,
            model,
            deprecated,
            config,
            is_active
        ) VALUES (
            :name,
            :category,
            :provider,
            :api_key,
            :base_url,
            :model,
            :deprecated,
            :config,
            :is_active
        )
    """), {
        "name": "Agent Tool Policy",
        "category": _AGENT_POLICY_CATEGORY,
        "provider": _AGENT_POLICY_PROVIDER,
        "api_key": "",
        "base_url": "",
        "model": _AGENT_POLICY_MODEL,
        "deprecated": False,
        "config": _safe_json_text(cfg),
        "is_active": True,
    })

    inserted = db.execute(text("""
        SELECT id
        FROM system_api_settings
        WHERE category = :category
          AND provider = :provider
          AND model = :model
        ORDER BY id DESC
        LIMIT 1
    """), {
        "category": _AGENT_POLICY_CATEGORY,
        "provider": _AGENT_POLICY_PROVIDER,
        "model": _AGENT_POLICY_MODEL,
    }).mappings().first()

    return SimpleNamespace(id=int(inserted["id"]), config=cfg)


def _persist_agent_policy_row_config(db: Session, row_id: int, config: Dict[str, Any]) -> None:
    db.execute(text("""
        UPDATE system_api_settings
        SET config = :config
        WHERE id = :id
    """), {
        "id": int(row_id),
        "config": _safe_json_text(config),
    })


def _default_billing_rule_reset_config() -> Dict[str, Any]:
    return {
        "min_multiplier": float(_BILLING_RESET_MIN_MULTIPLIER_DEFAULT),
        "max_multiplier": float(_BILLING_RESET_MAX_MULTIPLIER_DEFAULT),
        "default_multiplier": float(_BILLING_RESET_DEFAULT_MULTIPLIER_DEFAULT),
        "bin_size_credits": int(_BILLING_RESET_BIN_SIZE_CREDITS_DEFAULT),
        "bin_drop_multiplier": float(_BILLING_RESET_BIN_DROP_MULTIPLIER_DEFAULT),
        "max_total_increase_credits": int(_BILLING_RESET_MAX_INCREASE_DEFAULT),
    }


def _default_sora_mention_config() -> Dict[str, Any]:
    return {
        "auto_use_sora_mention": False,
        "auto_upload_character": False,
    }


def _normalize_sora_mention_config(value: Any) -> Dict[str, Any]:
    base = _default_sora_mention_config()
    payload = _safe_json_dict(value)

    auto_use = payload.get("auto_use_sora_mention")
    if auto_use is not None:
        base["auto_use_sora_mention"] = _to_bool(auto_use)

    auto_upload = payload.get("auto_upload_character")
    if auto_upload is not None:
        base["auto_upload_character"] = _to_bool(auto_upload)

    # Upload depends on mention mode.
    if not base["auto_use_sora_mention"]:
        base["auto_upload_character"] = False

    return base


def _normalize_billing_rule_reset_config(value: Any) -> Dict[str, Any]:
    base = _default_billing_rule_reset_config()
    payload = _safe_json_dict(value)
    min_multiplier = _safe_non_negative_float(payload.get("min_multiplier")) or _BILLING_RESET_MIN_MULTIPLIER_DEFAULT
    max_multiplier = _safe_non_negative_float(payload.get("max_multiplier")) or _BILLING_RESET_MAX_MULTIPLIER_DEFAULT
    if min_multiplier > max_multiplier:
        min_multiplier, max_multiplier = max_multiplier, min_multiplier
    min_multiplier = max(1.1, min(2.0, float(min_multiplier)))
    max_multiplier = max(1.1, min(2.0, float(max_multiplier)))
    if min_multiplier > max_multiplier:
        min_multiplier, max_multiplier = max_multiplier, min_multiplier

    default_multiplier = _normalize_rule_charge_multiplier(payload.get("default_multiplier"), default=_BILLING_RESET_DEFAULT_MULTIPLIER_DEFAULT)
    default_multiplier = max(1.0, min(float(max_multiplier), float(default_multiplier)))

    bin_size_credits = max(1, _non_negative_int(payload.get("bin_size_credits"), _BILLING_RESET_BIN_SIZE_CREDITS_DEFAULT))
    bin_drop_multiplier = _safe_non_negative_float(payload.get("bin_drop_multiplier")) or _BILLING_RESET_BIN_DROP_MULTIPLIER_DEFAULT

    base["min_multiplier"] = float(round(min_multiplier, 4))
    base["max_multiplier"] = float(round(max_multiplier, 4))
    base["default_multiplier"] = float(round(default_multiplier, 4))
    base["bin_size_credits"] = int(bin_size_credits)
    base["bin_drop_multiplier"] = float(round(bin_drop_multiplier, 6))

    max_total = _non_negative_int(payload.get("max_total_increase_credits"), _BILLING_RESET_MAX_INCREASE_DEFAULT)
    base["max_total_increase_credits"] = int(max_total)
    return base


def _compute_binned_multiplier(score: int, min_multiplier: float, max_multiplier: float, bin_size_credits: int, bin_drop_multiplier: float) -> float:
    if score <= 0:
        return float(max_multiplier)

    # Use absolute credit bins (0..bin-1, bin..2*bin-1, ...) so the distribution
    # remains stable regardless of the current dataset's minimum score.
    span_from_zero = max(0.0, float(score))
    safe_bin = max(1.0, float(bin_size_credits))
    bin_index = math.floor(span_from_zero / safe_bin)
    within_bin = (span_from_zero % safe_bin) / safe_bin
    drop = (float(bin_index) + float(within_bin)) * float(bin_drop_multiplier)
    raw = float(max_multiplier) - drop
    return float(max(float(min_multiplier), min(float(max_multiplier), raw)))


def _get_billing_rule_reset_config(db: Session) -> Dict[str, Any]:
    row = _get_or_create_agent_policy_row(db)
    cfg = _safe_json_dict(row.config)
    normalized = _normalize_billing_rule_reset_config(cfg.get(_BILLING_RESET_CONFIG_KEY, {}))
    cfg[_BILLING_RESET_CONFIG_KEY] = normalized
    row.config = cfg
    _persist_agent_policy_row_config(db, row.id, row.config)
    return normalized


def _get_sora_mention_config(db: Session) -> Dict[str, Any]:
    row = _get_or_create_agent_policy_row(db)
    cfg = _safe_json_dict(row.config)
    normalized = _normalize_sora_mention_config(cfg.get(_SORA_MENTION_CONFIG_KEY, {}))
    cfg[_SORA_MENTION_CONFIG_KEY] = normalized
    row.config = cfg
    _persist_agent_policy_row_config(db, row.id, row.config)
    return normalized


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


def _base_cost_to_credit(value: Any) -> int:
    """Convert supplier price (CNY) to raw system credits before markup."""
    base = _safe_non_negative_float(value)
    return max(0, int(math.ceil(base * 100)))


def _apply_charge_multiplier_to_credit(base_cost: Any, multiplier: float) -> int:
    raw_cost = _safe_non_negative_int(base_cost)
    mul = _safe_non_negative_float(multiplier)
    return max(0, int(round(raw_cost * (mul if mul > 0 else 1.0))))


def _multiplied_cost_to_credit(value: Any, multiplier: float) -> int:
    """Convert supplier price (CNY) to final charged credits after markup."""
    return _apply_charge_multiplier_to_credit(_base_cost_to_credit(value), multiplier)


def _normalize_currency_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return "CNY"
    aliases = {
        "RMB": "CNY",
        "CNH": "CNY",
    }
    return aliases.get(text, text)


def _normalize_price_basis(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "money"
    aliases = {
        "amount": "money",
        "cash": "money",
        "currency": "money",
        "point": "points",
        "credit": "points",
        "credits": "points",
        "score": "points",
        "积分": "points",
        "点数": "points",
    }
    return aliases.get(text, text)


def _assert_supplier_pricing_convertible(item: Any) -> Tuple[str, str]:
    raw_info = item.supplier_raw_info if isinstance(getattr(item, "supplier_raw_info", None), dict) else {}
    basis = _normalize_price_basis(
        getattr(item, "supplier_price_basis", None)
        or raw_info.get("price_basis")
        or raw_info.get("pricing_basis")
        or "money"
    )
    currency = _normalize_currency_code(
        getattr(item, "supplier_currency", None)
        or raw_info.get("currency")
        or raw_info.get("pricing_currency")
        or "CNY"
    )

    has_supplier_price = any(
        getattr(item, field, None) is not None
        for field in ["supplier_price", "supplier_price_input", "supplier_price_output"]
    )

    if basis != "money" and has_supplier_price:
        raise HTTPException(
            status_code=400,
            detail=(
                "supplier_price_basis must be 'money'. Provider points/credits cannot be converted directly to system credits. "
                "Please provide absolute monetary price first."
            ),
        )

    if currency != "CNY" and has_supplier_price:
        raise HTTPException(
            status_code=400,
            detail=(
                f"supplier_currency={currency} is not supported for direct conversion. "
                "Use /settings/system/ai-assistant/tools/exchange-rate to convert to CNY first, then submit CNY prices."
            ),
        )

    return basis, currency


def _safe_non_negative_int(value: Any) -> int:
    try:
        parsed = int(float(value))
        return parsed if parsed > 0 else 0
    except Exception:
        return 0


def _safe_non_negative_number(value: Any) -> float:
    try:
        parsed = float(value)
        if math.isnan(parsed) or math.isinf(parsed):
            return 0.0
        return parsed if parsed > 0 else 0.0
    except Exception:
        return 0.0


def _convert_supplier_value_to_system_credit(value: Any, source_unit: str) -> int:
    base = _safe_non_negative_number(value)
    unit = str(source_unit or "kie_credit").strip().lower()
    if base <= 0:
        return 0

    # Business rule:
    # 1 KIE credit = 3 system credits
    # 1 USD = 7 CNY
    # 1 system credit = 0.01 CNY  => 100 credits per CNY
    if unit in {"kie", "kie_credit", "kie_credits", "credit", "credits", "point", "points", "积分"}:
        return int(math.ceil(base * _KIE_TO_SYSTEM_CREDIT_RATIO))
    if unit in {"usd", "$", "us_dollar", "dollar", "dollars"}:
        cny = base * _USD_TO_CNY_RATE
        return int(math.ceil(cny * _SYSTEM_CREDIT_PER_CNY))
    if unit in {"cny", "rmb", "yuan", "¥", "人民币"}:
        return int(math.ceil(base * _SYSTEM_CREDIT_PER_CNY))
    if unit in {"system_credit", "system_credits", "credit_system", "credits_system"}:
        return int(math.ceil(base))

    # Unknown unit: fallback as KIE credit to avoid silent underbilling.
    return int(math.ceil(base * _KIE_TO_SYSTEM_CREDIT_RATIO))


def _normalize_rule_costs_with_source(rule: Dict[str, Any], source_unit: str) -> Dict[str, Any]:
    item = dict(rule or {})
    item["billing_cost"] = _convert_supplier_value_to_system_credit(item.get("billing_cost"), source_unit)
    item["billing_cost_input"] = _convert_supplier_value_to_system_credit(item.get("billing_cost_input"), source_unit)
    item["billing_cost_output"] = _convert_supplier_value_to_system_credit(item.get("billing_cost_output"), source_unit)
    return item


def _is_kie_system_setting(row: SystemAPISetting, provider_filter: str = "kie") -> bool:
    provider = str(getattr(row, "provider", "") or "").strip().lower()
    base_url = str(getattr(row, "base_url", "") or "").strip().lower()
    model = str(getattr(row, "model", "") or "").strip().lower()
    cfg = _safe_json_dict(getattr(row, "config", {}) or {})
    endpoint = str(cfg.get("endpoint") or "").strip().lower()
    target = str(provider_filter or "kie").strip().lower() or "kie"

    if provider == target or provider.startswith(f"{target}/"):
        return True
    if target == "kie" and (
        "kie.ai" in base_url
        or "kie.ai" in endpoint
        or model.startswith("kie/")
        or provider.startswith("kie")
    ):
        return True
    return False


def _extract_json_from_llm_text(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {}

    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw, re.IGNORECASE)
    if fenced:
        raw = fenced.group(1).strip()

    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass

    obj_match = re.search(r"\{[\s\S]*\}", raw)
    if not obj_match:
        return {}
    candidate = obj_match.group(0)
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _parse_confirmed_pricing_tables(payload: KIEPricingGenerateRequest) -> Tuple[List[Any], str, Optional[str]]:
    """Normalize optional pricing tables from array input or raw JSON text.

    Returns: (tables, parse_status, warning)
    parse_status: provided_array | parsed_json_array | parsed_json_tables_field | empty | invalid_json | invalid_shape
    """
    if isinstance(payload.confirmed_tables, list):
        return payload.confirmed_tables, "provided_array", None

    raw_text = str(payload.confirmed_pricing_tables_text or "").strip()
    if not raw_text:
        return [], "empty", None

    try:
        parsed = json.loads(raw_text)
    except Exception:
        return [], "invalid_json", "confirmed_pricing_tables_text is not valid JSON; ignored"

    if isinstance(parsed, list):
        return parsed, "parsed_json_array", None
    if isinstance(parsed, dict):
        nested_tables = parsed.get("tables")
        if isinstance(nested_tables, list):
            return nested_tables, "parsed_json_tables_field", None
    return [], "invalid_shape", "tables JSON must be an array or an object containing a tables array"


def _resolve_system_llm_runtime_config(db: Session) -> Dict[str, Any]:
    configs = _resolve_system_llm_runtime_configs(db, max_candidates=1)
    return configs[0] if configs else {}


def _resolve_system_llm_runtime_configs(db: Session, max_candidates: int = 4) -> List[Dict[str, Any]]:
    default_row = get_task_default_system_setting(db, "LLM")
    rows: List[SystemAPISetting] = []
    if default_row is not None:
        rows.append(default_row)

    # Fallback candidates: all available LLM providers/models, prefer active rows first.
    fallback_rows = db.query(SystemAPISetting).filter(
        SystemAPISetting.category == "LLM",
        ~SystemAPISetting.category.like("System_%"),
    ).order_by(
        SystemAPISetting.is_active.desc(),
        SystemAPISetting.id.asc(),
    ).all()
    rows.extend(fallback_rows)

    out: List[Dict[str, Any]] = []
    seen_setting_ids = set()

    for row in rows:
        if row is None:
            continue
        row_id = int(getattr(row, "id", 0) or 0)
        if row_id > 0 and row_id in seen_setting_ids:
            continue

        cfg = _safe_json_dict(getattr(row, "config", {}) or {})
        if bool(getattr(row, "deprecated", False)):
            continue

        runtime_key = _pick_provider_runtime_key(db, str(row.provider or ""), row.api_key or "")
        if not str(runtime_key or "").strip():
            continue

        default = DEFAULTS.get(str(row.provider or "").strip(), {})
        merged_cfg = dict(cfg or default.get("config", {}) or {})
        merged_cfg["__selection_source"] = "system_kie_pricing_assistant"
        merged_cfg["__resolved_setting_id"] = row.id

        out.append({
            "provider": row.provider,
            "api_key": runtime_key,
            "base_url": row.base_url or default.get("base_url"),
            "model": row.model or default.get("model"),
            "config": merged_cfg,
        })
        if row_id > 0:
            seen_setting_ids.add(row_id)

        if len(out) >= max(1, int(max_candidates or 1)):
            break

    return out


def _build_kie_pagination_urls(url: str, max_pages: int) -> List[str]:
    base = str(url or "").strip()
    if not base:
        return []
    parsed = urlparse(base)
    existing_qs = dict(parse_qsl(parsed.query or "", keep_blank_values=True))
    out: List[str] = []
    for idx in range(2, max(2, int(max_pages) + 1)):
        for key in ["page", "p", "current", "pageNo"]:
            query = dict(existing_qs)
            query[key] = str(idx)
            next_url = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                urlencode(query, doseq=True),
                parsed.fragment,
            ))
            if next_url not in out:
                out.append(next_url)
    return out


def _fetch_kie_pricing_paginated(url: str, max_length: int, max_pages: int) -> Dict[str, Any]:
    from app.services.pricing_tools import fetch_pricing_page

    first = fetch_pricing_page(url, max_length=max_length)
    if first.get("error"):
        return {
            "url": url,
            "page_count": 0,
            "has_pagination": False,
            "pages": [],
            "combined_text": "",
            "combined_tables": [],
            "warnings": [str(first.get("error"))],
            "error": str(first.get("error")),
        }

    pages_payload: List[Dict[str, Any]] = [first]
    seen_text_hash = {hash(str(first.get("text_content") or ""))}
    warnings: List[str] = []

    # Heuristic probing for pagination query parameters.
    for page_url in _build_kie_pagination_urls(url, max_pages=max_pages):
        resp = fetch_pricing_page(page_url, max_length=max_length)
        if resp.get("error"):
            continue
        text = str(resp.get("text_content") or "")
        if not text.strip():
            continue
        text_hash = hash(text)
        if text_hash in seen_text_hash:
            continue
        seen_text_hash.add(text_hash)
        pages_payload.append(resp)
        if len(pages_payload) >= max(1, int(max_pages)):
            break

    combined_text_parts: List[str] = []
    combined_tables: List[Any] = []
    pages: List[KIEPricingFetchPage] = []

    for page in pages_payload:
        page_url = str(page.get("url") or "")
        title = str(page.get("title") or "").strip() or None
        text = str(page.get("text_content") or "")
        tables = page.get("tables") if isinstance(page.get("tables"), list) else []
        content_length = int(page.get("content_length") or len(text))
        pages.append(KIEPricingFetchPage(
            url=page_url,
            title=title,
            content_length=content_length,
            table_count=len(tables),
        ))
        if text.strip():
            combined_text_parts.append(f"### page: {page_url}\n{text}")
        if tables:
            combined_tables.extend(tables)

    combined_text = "\n\n".join(combined_text_parts)
    if len(pages_payload) == 1:
        warnings.append("Pagination probing did not find additional distinct pages; first-page content may already include all data.")

    return {
        "url": url,
        "page_count": len(pages),
        "has_pagination": len(pages) > 1,
        "pages": pages,
        "combined_text": combined_text[:max(5000, min(max_length * max(1, len(pages)), 300000))],
        "combined_tables": combined_tables[:200],
        "warnings": warnings,
        "error": None,
    }


def _normalize_generation_modes(values: Any) -> List[str]:
    if isinstance(values, str):
        raw_items = [x.strip() for x in values.replace(";", ",").split(",")]
    elif isinstance(values, list):
        raw_items = [str(x or "").strip() for x in values]
    else:
        raw_items = []

    alias = {
        "text2image": "t2i",
        "txt2img": "t2i",
        "image2image": "i2i",
        "img2img": "i2i",
        "image2video": "i2v",
        "img2video": "i2v",
        "text2video": "t2v",
        "txt2video": "t2v",
        "digital_human": "s2v",
        "avatar": "s2v",
        "image_edit": "i2i",
    }
    out: List[str] = []
    seen = set()
    for item in raw_items:
        k = item.strip().lower()
        if not k:
            continue
        normalized = alias.get(k, k)
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _clean_feature_dict(value: Any) -> Dict[str, Any]:
    data = _safe_json_dict(value)
    out: Dict[str, Any] = {}
    for key, raw in data.items():
        name = str(key or "").strip()
        if not name:
            continue
        if isinstance(raw, list):
            cleaned = []
            seen = set()
            for item in raw:
                token = str(item or "").strip()
                if not token or token in seen:
                    continue
                seen.add(token)
                cleaned.append(token)
            out[name] = cleaned
        elif isinstance(raw, (int, float, bool)) or raw is None:
            out[name] = raw
        else:
            out[name] = str(raw or "").strip()
    return out


def _build_modality_from_feature_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    generation_modes = _normalize_generation_modes(profile.get("generation_modes"))
    capability_flags = _clean_feature_dict(profile.get("capability_flags"))
    text_caps = _clean_feature_dict(profile.get("text_capabilities"))
    image_caps = _clean_feature_dict(profile.get("image_capabilities"))
    video_caps = _clean_feature_dict(profile.get("video_capabilities"))
    digital_caps = _clean_feature_dict(profile.get("digital_human_capabilities"))
    voice_caps = _clean_feature_dict(profile.get("voice_capabilities"))
    music_caps = _clean_feature_dict(profile.get("music_capabilities"))

    out: Dict[str, Any] = {
        "generation_modes": generation_modes,
    }

    if profile.get("base_model"):
        out["base_model"] = str(profile.get("base_model") or "").strip()
    if capability_flags:
        out["capability_flags"] = capability_flags

    if text_caps:
        out["text_capabilities"] = text_caps
        if text_caps.get("input_formats") and not out.get("input_formats"):
            out["input_formats"] = text_caps.get("input_formats")
        if text_caps.get("output_format") and not out.get("output_format"):
            out["output_format"] = text_caps.get("output_format")

    if image_caps.get("supported_resolutions"):
        out["supported_resolutions"] = image_caps.get("supported_resolutions")
    if image_caps.get("aspect_ratios"):
        out["aspect_ratios"] = image_caps.get("aspect_ratios")
    if image_caps.get("max_images_per_call") is not None:
        out["max_images_per_call"] = image_caps.get("max_images_per_call")
    if image_caps.get("reference_image_limit") is not None:
        out["reference_image_limit"] = image_caps.get("reference_image_limit")
    if image_caps.get("image_size_values"):
        out["image_size_values"] = image_caps.get("image_size_values")
    if image_caps.get("quality_values"):
        out["quality_values"] = image_caps.get("quality_values")

    if video_caps.get("supported_resolutions") and not out.get("supported_resolutions"):
        out["supported_resolutions"] = video_caps.get("supported_resolutions")
    if video_caps.get("aspect_ratios") and not out.get("aspect_ratios"):
        out["aspect_ratios"] = video_caps.get("aspect_ratios")
    if video_caps.get("durations_seconds"):
        out["durations_seconds"] = video_caps.get("durations_seconds")
        durations = []
        for val in video_caps.get("durations_seconds") or []:
            try:
                durations.append(float(val))
            except Exception:
                continue
        if durations:
            out["max_duration"] = max(durations)
    if video_caps.get("fps_options"):
        out["fps_options"] = video_caps.get("fps_options")
    if video_caps.get("reference_image_limit") is not None and out.get("reference_image_limit") is None:
        out["reference_image_limit"] = video_caps.get("reference_image_limit")
    if video_caps.get("reference_video_limit") is not None:
        out["reference_video_limit"] = video_caps.get("reference_video_limit")
    if video_caps.get("quality_values") and not out.get("quality_values"):
        out["quality_values"] = video_caps.get("quality_values")
    if video_caps.get("image_size_values") and not out.get("image_size_values"):
        out["image_size_values"] = video_caps.get("image_size_values")
    if video_caps.get("sound_supported") is not None:
        out["sound_supported"] = bool(video_caps.get("sound_supported"))
    elif video_caps.get("has_audio") is not None:
        out["sound_supported"] = bool(video_caps.get("has_audio"))
    if video_caps.get("multi_shots_supported") is not None:
        out["multi_shots_supported"] = bool(video_caps.get("multi_shots_supported"))

    if bool(digital_caps.get("supported")):
        out["has_digital_human"] = True

    if voice_caps:
        out["voice_capabilities"] = voice_caps
        if voice_caps.get("has_audio") is not None:
            out["has_audio"] = bool(voice_caps.get("has_audio"))
        if voice_caps.get("input_formats") and not out.get("input_formats"):
            out["input_formats"] = voice_caps.get("input_formats")
        if voice_caps.get("output_format") and not out.get("output_format"):
            out["output_format"] = voice_caps.get("output_format")

    if music_caps:
        out["music_capabilities"] = music_caps
        if music_caps.get("has_audio") is not None:
            out["has_audio"] = bool(music_caps.get("has_audio"))
        if music_caps.get("input_formats") and not out.get("input_formats"):
            out["input_formats"] = music_caps.get("input_formats")
        if music_caps.get("output_format") and not out.get("output_format"):
            out["output_format"] = music_caps.get("output_format")

    return out


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
        supplier_price_basis, supplier_currency = _assert_supplier_pricing_convertible(item)
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
            tags=(item.tags if item.tags else (getattr(existing, "tags", None) if existing else None)),
            name=(str(item.name or "").strip() or (existing.name if existing else f"{provider} {model_name}")),
            base_url=(str(item.base_url or "").strip() or (existing.base_url if existing else None)),
            unit_type=unit_type,
            supplier_price=(_safe_non_negative_float(item.supplier_price) if item.supplier_price is not None else None),
            supplier_price_input=(_safe_non_negative_float(item.supplier_price_input) if item.supplier_price_input is not None else None),
            supplier_price_output=(_safe_non_negative_float(item.supplier_price_output) if item.supplier_price_output is not None else None),
            supplier_currency=supplier_currency,
            supplier_price_basis=supplier_price_basis,
            supplier_raw_info=(item.supplier_raw_info if item.supplier_raw_info else None),
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


def _safe_json_text(value: Any) -> str:
    try:
        return json.dumps(_safe_json_dict(value), ensure_ascii=False)
    except Exception:
        return "{}"


def _assign_wide_modality_fields(target: SystemAPISetting, source: Any) -> None:
    # Wide dimension fields were removed from system_api_settings.
    # Keep this as a no-op to preserve import compatibility with historical payloads.
    return


def _build_modality_payload_from_item(source: Any) -> Optional[Dict[str, Any]]:
    raw_modality = _safe_json_dict(getattr(source, "modality", None))
    if raw_modality:
        return raw_modality

    profile = {
        "base_model": getattr(source, "base_model", None),
        "generation_modes": getattr(source, "generation_modes", None),
        "capability_flags": getattr(source, "capability_flags", None),
        "text_capabilities": getattr(source, "text_capabilities", None),
        "image_capabilities": getattr(source, "image_capabilities", None),
        "video_capabilities": getattr(source, "video_capabilities", None),
        "digital_human_capabilities": getattr(source, "digital_human_capabilities", None),
        "voice_capabilities": getattr(source, "voice_capabilities", None),
        "music_capabilities": getattr(source, "music_capabilities", None),
    }
    modality = _build_modality_from_feature_profile(profile)

    # Keep compatibility with older import payloads where these values were top-level fields.
    top_level_keys = [
        "input_formats",
        "output_format",
        "supported_resolutions",
        "aspect_ratios",
        "max_images_per_call",
        "reference_image_limit",
        "reference_video_limit",
        "durations_seconds",
        "max_duration",
        "fps_options",
        "image_size_values",
        "quality_values",
        "has_audio",
        "sound_supported",
        "multi_shots_supported",
        "mode_values",
        "capability_flags",
        "pricing_unit",
        "token_billing_supported",
        "input_token_price",
        "output_token_price",
        "per_resolution_price_map",
        "per_duration_price_map",
        "has_tiered_pricing",
        "free_quota",
        "currency",
    ]
    for key in top_level_keys:
        value = getattr(source, key, None)
        if value is not None:
            modality[key] = value

    return modality or None


def _extract_modality_manage_fields(modality_value: Any) -> Dict[str, Any]:
    modality = _safe_json_dict(modality_value)
    extracted: Dict[str, Any] = {}
    for name in [
        "generation_modes",
        "input_formats",
        "output_format",
        "supported_resolutions",
        "aspect_ratios",
        "max_images_per_call",
        "reference_image_limit",
        "reference_video_limit",
        "durations_seconds",
        "max_duration",
        "fps_options",
        "image_size_values",
        "quality_values",
        "has_audio",
        "sound_supported",
        "multi_shots_supported",
        "mode_values",
        "capability_flags",
        "pricing_unit",
        "token_billing_supported",
        "input_token_price",
        "output_token_price",
        "per_resolution_price_map",
        "per_duration_price_map",
        "has_tiered_pricing",
        "free_quota",
        "currency",
        "text_capabilities",
        "image_capabilities",
        "video_capabilities",
        "digital_human_capabilities",
        "voice_capabilities",
        "music_capabilities",
    ]:
        value = modality.get(name)
        if value is not None:
            extracted[name] = value
    return extracted


def _primary_generation_mode_from_wide(generation_modes: Any) -> Optional[str]:
    if isinstance(generation_modes, list):
        for mode in generation_modes:
            text = str(mode or "").strip()
            if text:
                return text
    return None


def _safe_int(value: Any, default: Optional[int] = 0) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return default


def _normalize_user_api_strategy(value: Any, default: str = "smart_default") -> str:
    raw = str(value or "").strip().lower()
    return raw if raw in _USER_API_STRATEGIES else default


def _normalize_user_mode(value: Any) -> Optional[str]:
    text = str(value or "").strip().lower()
    return text or None


def _is_json_object_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, dict):
        return True
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode("utf-8", errors="ignore")
        except Exception:
            return False
    if isinstance(value, str):
        raw_obj: Any = value
        for _ in range(3):
            if isinstance(raw_obj, dict):
                return True
            if not isinstance(raw_obj, str):
                return False

            raw = raw_obj.strip()
            if not raw:
                return True

            parsed = None
            try:
                parsed = json.loads(raw)
            except Exception:
                try:
                    parsed = ast.literal_eval(raw)
                except Exception:
                    parsed = None

            if parsed is None:
                return False
            raw_obj = parsed

        return isinstance(raw_obj, dict)
    return False


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


def _get_provider_pool_runtime_maps(db: Session) -> Tuple[Dict[str, str], Dict[str, Optional[str]], int]:
    now_ts = time.time()
    cached_ts = float(_provider_pool_cache.get("ts") or 0.0)
    if (now_ts - cached_ts) < _PROVIDER_POOL_CACHE_TTL_SECONDS:
        return (
            dict(_provider_pool_cache.get("runtime_key_map") or {}),
            dict(_provider_pool_cache.get("alias_map") or {}),
            int(_provider_pool_cache.get("row_count") or 0),
        )

    provider_pool_rows = db.query(
        ProviderKeyPool.provider,
        ProviderKeyPool.provider_alias,
        ProviderKeyPool.api_keys,
    ).all()

    runtime_key_map: Dict[str, str] = {}
    alias_map: Dict[str, Optional[str]] = {}
    for row in provider_pool_rows:
        provider_key = str(getattr(row, "provider", "") or "").strip().lower()
        if not provider_key:
            continue
        keys = _normalize_api_keys(getattr(row, "api_keys", None))
        runtime_key_map[provider_key] = keys[0] if keys else ""
        alias = str(getattr(row, "provider_alias", "") or "").strip()
        alias_map[provider_key] = alias or None

    _provider_pool_cache["ts"] = now_ts
    _provider_pool_cache["runtime_key_map"] = dict(runtime_key_map)
    _provider_pool_cache["alias_map"] = dict(alias_map)
    _provider_pool_cache["row_count"] = len(provider_pool_rows)

    return runtime_key_map, alias_map, len(provider_pool_rows)


def _ensure_settings_system_indexes(db: Session) -> None:
    global _settings_system_indexes_ensured
    if _settings_system_indexes_ensured:
        return
    try:
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_system_api_settings_cat_depr ON system_api_settings(category, deprecated)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_system_api_settings_provider_cat_model ON system_api_settings(provider, category, model)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_api_settings_user_category ON api_settings(user_id, category)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_provider_key_pool_provider ON provider_key_pool(provider)"))
        db.commit()
        _settings_system_indexes_ensured = True
        logger.info("settings.system.indexes ensured")
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("settings.system.index ensure skipped: %s", str(exc)[:300])


def _ensure_api_settings_binding_columns(db: Session) -> None:
    global _api_settings_binding_columns_ensured
    if _api_settings_binding_columns_ensured:
        return

    try:
        conn = db.connection()
        inspector = inspect(conn)
        if not inspector.has_table("api_settings"):
            return

        existing_cols = {str(c.get("name") or "").strip().lower() for c in inspector.get_columns("api_settings")}
        dialect_name = str(conn.dialect.name or "").lower()
        added_cols: List[str] = []

        if "system_api_id" not in existing_cols:
            if dialect_name == "postgresql":
                db.execute(text("ALTER TABLE api_settings ADD COLUMN IF NOT EXISTS system_api_id INTEGER"))
            else:
                db.execute(text("ALTER TABLE api_settings ADD COLUMN system_api_id INTEGER"))
            added_cols.append("system_api_id")

        if "mode" not in existing_cols:
            if dialect_name == "postgresql":
                db.execute(text("ALTER TABLE api_settings ADD COLUMN IF NOT EXISTS mode VARCHAR"))
            else:
                db.execute(text("ALTER TABLE api_settings ADD COLUMN mode VARCHAR"))
            added_cols.append("mode")

        if "api_strategy" not in existing_cols:
            if dialect_name == "postgresql":
                db.execute(text("ALTER TABLE api_settings ADD COLUMN IF NOT EXISTS api_strategy VARCHAR"))
            else:
                db.execute(text("ALTER TABLE api_settings ADD COLUMN api_strategy VARCHAR"))
            added_cols.append("api_strategy")

        if added_cols:
            logger.warning("api_settings runtime migration applied: added columns %s", ",".join(added_cols))

        _api_settings_binding_columns_ensured = True
    except Exception as exc:
        logger.warning("api_settings runtime migration skipped: %s", str(exc)[:300])


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


def _validate_provider_bundle_payload(providers: List[Any]) -> Dict[str, Any]:
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    provider_count = 0
    model_count = 0

    seen_triplets = set()

    for p_idx, provider_item in enumerate(providers or []):
        provider_name = str(getattr(provider_item, "provider", "") or "").strip()
        if not provider_name:
            errors.append({
                "type": "provider_missing",
                "provider_index": p_idx,
                "message": "provider is required",
            })
            continue

        provider_count += 1
        keys = _normalize_api_keys(getattr(provider_item, "api_keys", []))
        strategy = _normalize_key_strategy(getattr(provider_item, "strategy", None))
        weights = _normalize_key_weights(getattr(provider_item, "weights", None), keys)
        if strategy == "weighted" and keys and len(weights) != len(keys):
            warnings.append({
                "type": "weights_normalized",
                "provider": provider_name,
                "message": "weights length adjusted to match api_keys",
            })

        models = getattr(provider_item, "models", []) or []
        if not models:
            warnings.append({
                "type": "provider_without_models",
                "provider": provider_name,
                "message": "provider has no models",
            })

        for m_idx, model_item in enumerate(models):
            category = str(getattr(model_item, "category", "LLM") or "LLM").strip() or "LLM"
            model = str(getattr(model_item, "model", "") or "").strip()
            model_count += 1

            if not model:
                errors.append({
                    "type": "model_missing",
                    "provider": provider_name,
                    "provider_index": p_idx,
                    "model_index": m_idx,
                    "message": "model is required",
                })
                continue

            triplet = (provider_name.lower(), category.lower(), model.lower())
            if triplet in seen_triplets:
                warnings.append({
                    "type": "duplicate_triplet",
                    "provider": provider_name,
                    "category": category,
                    "model": model,
                    "message": "duplicate provider/category/model found; later item may overwrite earlier one",
                })
            else:
                seen_triplets.add(triplet)

            cfg = getattr(model_item, "config", None)
            if cfg is not None and not isinstance(cfg, dict):
                warnings.append({
                    "type": "config_not_object",
                    "provider": provider_name,
                    "category": category,
                    "model": model,
                    "message": "config is not an object; will be normalized to {}",
                })

    return {
        "ok": len(errors) == 0,
        "providers": provider_count,
        "models": model_count,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def _extract_provider_key_pool_from_row(row: SystemAPISetting) -> List[str]:
    """Legacy fallback: extract keys from api_key column only (key pool is now in provider_key_pool table)."""
    single = str(row.api_key or "").strip()
    return [single] if single else []


def _normalize_system_provider_name(provider: Any) -> str:
    return str(provider or "").strip().lower()


def _system_provider_case_insensitive_filter(provider: Any):
    provider_norm = _normalize_system_provider_name(provider)
    return func.lower(func.trim(func.coalesce(SystemAPISetting.provider, ""))) == provider_norm


def _get_provider_key_pool_record(db: Session, provider: str):
    """Return the ProviderKeyPool row for the given provider, or None."""
    provider_name = _normalize_system_provider_name(provider)
    if not provider_name:
        return None
    if not _db_has_table(db, "provider_key_pool"):
        return None
    return db.query(ProviderKeyPool).filter(ProviderKeyPool.provider == provider_name).first()


def _get_system_provider_key_pool(db: Session, provider: str) -> List[str]:
    record = _get_provider_key_pool_record(db, provider)
    if record and record.api_keys:
        return _normalize_api_keys(record.api_keys)
    return []


def _get_system_provider_key_pool_full(db: Session, provider: str) -> dict:
    """Return full key pool info (keys, strategy, weights) from provider_key_pool table."""
    record = _get_provider_key_pool_record(db, provider)
    if record:
        keys = _normalize_api_keys(record.api_keys)
        return {
            "keys": keys,
            "strategy": _normalize_key_strategy(record.strategy),
            "weights": _normalize_key_weights(record.weights, keys),
            "provider_alias": str(getattr(record, "provider_alias", "") or "").strip() or None,
            "intro_url": str(getattr(record, "intro_url", "") or "").strip() or None,
        }
    return {"keys": [], "strategy": "random", "weights": [], "provider_alias": None, "intro_url": None}


def _apply_system_provider_key_pool(db: Session, provider: str, keys: List[str]) -> None:
    normalized = _normalize_api_keys(keys)
    provider_name = _normalize_system_provider_name(provider)

    # SQL-level upsert avoids stale ORM row state after bulk-delete flows.
    now_iso = now_bj_iso()
    target_weights = _normalize_key_weights(None, normalized)
    updated_rows = db.query(ProviderKeyPool).filter(
        ProviderKeyPool.provider == provider_name,
    ).update(
        {
            "api_keys": normalized,
            "weights": target_weights,
            "updated_at": now_iso,
        },
        synchronize_session=False,
    )
    if int(updated_rows or 0) == 0:
        db.add(ProviderKeyPool(
            provider=provider_name,
            api_keys=normalized,
            strategy="random",
            weights=target_weights,
            created_at=now_iso,
            updated_at=now_iso,
        ))

    # Sync primary key to all system_api_settings rows for legacy compatibility
    primary_key = normalized[0] if normalized else ""
    rows = db.query(SystemAPISetting).filter(
        _system_provider_case_insensitive_filter(provider_name)
    ).all()
    for row in rows:
        row.provider = provider_name
        row.api_key = primary_key


def _apply_provider_key_bundle_to_rows(
    db: Session,
    provider_name: str,
    keys: List[str],
    strategy: str,
    weights: List[float],
    *,
    provider_alias: Optional[str] = None,
    intro_url: Optional[str] = None,
    created_at: Optional[str] = None,
    updated_at: Optional[str] = None,
) -> None:
    """Write full key pool bundle to provider_key_pool and sync api_key on system_api_settings rows."""
    normalized = _normalize_api_keys(keys)
    provider_name = _normalize_system_provider_name(provider_name)

    if _db_has_table(db, "provider_key_pool"):
        # SQL-level upsert avoids StaleDataError in replace_all transaction scopes.
        now_iso = str(updated_at or now_bj_iso())
        updated_rows = db.query(ProviderKeyPool).filter(
            ProviderKeyPool.provider == provider_name,
        ).update(
            {
                "api_keys": normalized,
                "strategy": strategy,
                "weights": weights,
                "provider_alias": str(provider_alias or "").strip() or None,
                "intro_url": _normalize_optional_http_url(intro_url),
                "updated_at": now_iso,
            },
            synchronize_session=False,
        )
        if int(updated_rows or 0) == 0:
            db.add(ProviderKeyPool(
                provider=provider_name,
                api_keys=normalized,
                strategy=strategy,
                weights=weights,
                provider_alias=str(provider_alias or "").strip() or None,
                intro_url=_normalize_optional_http_url(intro_url),
                created_at=str(created_at or now_iso),
                updated_at=now_iso,
            ))
    else:
        logger.warning("Skip provider_key_pool sync for provider=%s: table provider_key_pool not found", provider_name)

    primary_key = normalized[0] if normalized else ""
    rows = db.query(SystemAPISetting).filter(
        _system_provider_case_insensitive_filter(provider_name)
    ).all()
    for row in rows:
        row.api_key = primary_key


def _normalize_optional_http_url(value: Any) -> Optional[str]:
    text_value = str(value or "").strip()
    if not text_value:
        return None
    if not text_value.startswith(("http://", "https://")):
        return None
    return text_value


def _derive_base_model_from_model(model_value: Any) -> Optional[str]:
    model_text = str(model_value or "").strip()
    if not model_text:
        return None
    normalized = model_text.replace("\\", "/").strip("/")
    if not normalized:
        return None
    if "/" in normalized:
        head = normalized.split("/", 1)[0].strip()
        if head:
            return head
    return normalized


def _resolve_base_model(explicit_base_model: Any, model_value: Any) -> Optional[str]:
    explicit_text = str(explicit_base_model or "").strip()
    if explicit_text:
        return explicit_text
    return _derive_base_model_from_model(model_value)


def _pick_provider_runtime_key(db: Session, provider: str, fallback_key: str = "") -> str:
    """Pick a runtime key from the provider_key_pool table (simple random)."""
    record = _get_provider_key_pool_record(db, provider)
    if record and record.api_keys:
        pooled = _normalize_api_keys(record.api_keys)
        if pooled:
            return random.choice(pooled)
    return str(fallback_key or "").strip()


def _can_use_system_settings(user: User) -> bool:
    return bool(user and user.is_active)


def _can_manage_system_settings(user: User) -> bool:
    return bool(user.is_superuser)


def _ensure_default_system_selection_for_user(db: Session, user_id: int) -> None:
    _ensure_api_settings_binding_columns(db)

    # Get all categories the user has configured
    user_active_categories = db.query(APISetting.category).filter(
        APISetting.user_id == user_id,
    ).distinct().all()
    user_active_categories_set = {str(cat[0]).strip() for cat in user_active_categories if cat[0]}

    active_system_rows: List[SystemAPISetting] = []
    for category in ["LLM", "Image", "Video", "DigitalHuman", "Voice", "Music"]:
        row = get_task_default_system_setting(db, category)
        if not row:
            continue
        cat = str(row.category or "").strip()
        if not cat or cat.startswith("System_"):
            continue
        active_system_rows.append(row)

    if not active_system_rows:
        return

    selected_by_category: Dict[str, SystemAPISetting] = {}
    for row in active_system_rows:
        category = str(row.category or "").strip()
        if not category or category in selected_by_category:
            continue
        # Only add default if user doesn't already have an active setting for this category
        if category not in user_active_categories_set:
            selected_by_category[category] = row

    for _, system_setting in selected_by_category.items():
        db.add(APISetting(
            user_id=user_id,
            category=system_setting.category,
            system_api_id=int(system_setting.id),
            api_strategy=_normalize_user_api_strategy(None),
            mode=None,
        ))

    db.flush()


def _normalize_user_active_settings(db: Session, user_id: int) -> None:
    _ensure_api_settings_binding_columns(db)

    rows = db.query(APISetting).filter(
        APISetting.user_id == user_id,
    ).order_by(APISetting.category.asc(), APISetting.id.desc()).all()

    grouped: Dict[str, List[APISetting]] = {}
    for row in rows:
        category = str(row.category or "LLM").strip() or "LLM"
        grouped.setdefault(category, []).append(row)

    changed = False
    for category, items in grouped.items():
        if len(items) <= 1:
            continue

        def _score(item: APISetting):
            has_system_setting_id = 1 if _safe_int(getattr(item, "system_api_id", None), None) else 0
            has_strategy = 1 if str(getattr(item, "api_strategy", "") or "").strip() else 0
            has_mode = 1 if str(getattr(item, "mode", "") or "").strip() else 0
            return (has_system_setting_id, has_strategy, has_mode, int(item.id or 0))

        winner = max(items, key=_score)
        dropped_ids: List[int] = [item.id for item in items if item.id != winner.id]
        for item in items:
            if item.id == winner.id:
                continue
            db.delete(item)
            changed = True

        logger.warning(
            "Normalize duplicate active api settings | user_id=%s category=%s keep_id=%s drop_ids=%s",
            user_id,
            category,
            winner.id,
            dropped_ids,
        )

    if changed:
        db.flush()


def _keep_only_active_setting_row_for_category(db: Session, user_id: int, category: str, keep_id: int) -> None:
    """Delete all other rows in the same category and keep only one binding row."""
    if not keep_id:
        return
    db.query(APISetting).filter(
        APISetting.user_id == user_id,
        APISetting.category == category,
        APISetting.id != int(keep_id),
    ).delete(synchronize_session=False)


def _normalize_setting_category_name(category: Any) -> str:
    raw = str(category or "").strip()
    lower = raw.lower()
    mapped = {
        "llm": "LLM",
        "image": "Image",
        "video": "Video",
        "vision": "Vision",
        "tools": "Tools",
        "voice": "Voice",
        "music": "Music",
        "llm_chat": "LLM",
        "image_gen": "Image",
        "video_gen": "Video",
        "analysis": "Vision",
        "analysis_character": "Vision",
    }.get(lower)
    if mapped:
        return mapped
    return raw or "LLM"


def _cleanup_user_api_settings_records(db: Session, user_id: int) -> None:
    _ensure_api_settings_binding_columns(db)

    rows = db.query(APISetting).filter(APISetting.user_id == user_id).order_by(APISetting.id.desc()).all()
    if not rows:
        return

    changed = False
    for row in rows:
        normalized_category = _normalize_setting_category_name(row.category)
        if (row.category or "") != normalized_category:
            row.category = normalized_category
            changed = True

        normalized_mode = _normalize_user_mode(getattr(row, "mode", None))
        if normalized_mode != getattr(row, "mode", None):
            row.mode = normalized_mode
            changed = True

        normalized_strategy = _normalize_user_api_strategy(getattr(row, "api_strategy", None))
        if normalized_strategy != getattr(row, "api_strategy", None):
            row.api_strategy = normalized_strategy
            changed = True

    if changed:
        db.flush()


def _sync_system_provider_shared_key(db: Session, provider: str, current_setting_id: int, incoming_api_key: str = None) -> str:
    if not provider:
        return incoming_api_key or ""

    provider = _normalize_system_provider_name(provider)

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

    query = db.query(SystemAPISetting)
    try:
        existing_cols = {
            str(col.get("name") or "").strip()
            for col in inspect(db.bind).get_columns("system_api_settings")
            if isinstance(col, dict)
        }
        mapper = inspect(SystemAPISetting)
        attrs = []
        for attr in mapper.column_attrs:
            cols = getattr(attr, "columns", None) or []
            if not cols:
                continue
            col_name = str(getattr(cols[0], "name", "") or "").strip()
            if col_name and col_name in existing_cols:
                attrs.append(getattr(SystemAPISetting, attr.key))
        if attrs:
            query = query.options(load_only(*attrs))
    except Exception:
        # Fallback to default ORM behavior if reflection fails.
        pass

    return query.filter(
        func.lower(func.trim(func.coalesce(SystemAPISetting.provider, ""))) == provider_norm,
        func.lower(func.trim(func.coalesce(SystemAPISetting.category, ""))) == category_norm,
        func.lower(func.trim(func.coalesce(SystemAPISetting.model, ""))) == model_norm,
    ).order_by(SystemAPISetting.id.desc()).first()


def _insert_system_setting_schema_safe(
    db: Session,
    payload: Dict[str, Any],
    *,
    provider: str,
    category: str,
    model: str,
) -> Optional[SystemAPISetting]:
    """Insert system_api_settings row using only columns that exist in current DB schema."""
    try:
        table = Table("system_api_settings", MetaData(), autoload_with=db.bind)
        existing_cols = set(table.columns.keys())
    except Exception as e:
        logger.warning("[_insert_system_setting_schema_safe] table reflection failed: %s", e)
        return None

    safe_payload = {
        k: v
        for k, v in (payload or {}).items()
        if str(k or "").strip() in existing_cols
    }

    # Keep a safe default for legacy schemas.
    if "is_active" in existing_cols and "is_active" not in safe_payload:
        safe_payload["is_active"] = False

    db.execute(table.insert().values(**safe_payload))
    db.flush()

    return _find_system_setting_by_normalized_triplet(db, provider, category, model)


def _refresh_has_granular_billing_rules_flag(db: Session, system_api_id: int) -> None:
    # Deprecated no-op: granular state is derived dynamically from rules table.
    return


def _has_granular_billing_rules(db: Session, system_api_id: int) -> bool:
    rows = db.query(SystemAPIBillingRule).filter(
        SystemAPIBillingRule.system_api_id == system_api_id,
        SystemAPIBillingRule.is_active == True,
    ).all()
    return any(not _is_base_billing_rule(row) for row in rows)


def _category_to_mode_flags(category: Any) -> Dict[str, bool]:
    normalized = str(category or "").strip().lower()
    if normalized in {"llm", "vision", "tools", "voice", "music"}:
        return {"text": True, "image": False, "video": False}
    if normalized == "image":
        return {"text": False, "image": True, "video": False}
    if normalized == "video":
        return {"text": False, "image": False, "video": True}
    return {"text": True, "image": False, "video": False}


def _rule_extra_conditions(rule: SystemAPIBillingRule) -> Dict[str, Any]:
    return _safe_json_dict(getattr(rule, "extra_conditions", {}))


def _rule_has_matching_dimensions(rule: SystemAPIBillingRule) -> bool:
    text_fields = [
        "generation_mode", "input_format", "output_format", "has_audio",
        "input_tokens_min", "input_tokens_max", "output_tokens_min", "output_tokens_max",
        "total_tokens_min", "total_tokens_max", "image_count_min", "image_count_max",
        "width_min", "width_max", "height_min", "height_max", "pixels_min", "pixels_max",
        "duration_seconds_min", "duration_seconds_max", "fps_min", "fps_max",
    ]
    for field in text_fields:
        value = getattr(rule, field, None)
        if value is not None and str(value).strip() != "":
            return True
    return False


def _is_base_billing_rule(rule: SystemAPIBillingRule) -> bool:
    extra = _rule_extra_conditions(rule)
    if str(extra.get("rule_kind", "")).strip().lower() == _BASE_BILLING_RULE_KIND:
        return True
    priority = int(getattr(rule, "priority", 0) or 0)
    if priority <= _BASE_BILLING_RULE_PRIORITY and not _rule_has_matching_dimensions(rule):
        return True
    return False


def _rule_to_billing(rule: Optional[SystemAPIBillingRule]) -> Dict[str, Any]:
    if not rule:
        return {"unit_type": "per_call", "cost": 0, "cost_input": 0, "cost_output": 0}
    return {
        "unit_type": _normalize_billing_unit_type(getattr(rule, "billing_unit_type", None) or "per_call"),
        "cost": _non_negative_int(getattr(rule, "billing_cost", 0), 0),
        "cost_input": _non_negative_int(getattr(rule, "billing_cost_input", 0), 0),
        "cost_output": _non_negative_int(getattr(rule, "billing_cost_output", 0), 0),
    }


def _extract_rule_match_signature(rule: SystemAPIBillingRule) -> Dict[str, Any]:
    fields = [
        "generation_mode", "input_format", "output_format", "has_audio",
        "input_tokens_min", "input_tokens_max", "output_tokens_min", "output_tokens_max",
        "total_tokens_min", "total_tokens_max", "image_count_min", "image_count_max",
        "width_min", "width_max", "height_min", "height_max", "pixels_min", "pixels_max",
        "duration_seconds_min", "duration_seconds_max", "fps_min", "fps_max",
    ]

    out: Dict[str, Any] = {}
    for field in fields:
        value = getattr(rule, field, None)
        if value is None:
            continue
        if isinstance(value, str):
            text = value.strip()
            if not text:
                continue
            out[field] = text
        else:
            out[field] = value

    out["billing_unit_type"] = _normalize_billing_unit_type(getattr(rule, "billing_unit_type", None) or "per_call")
    out["applies_to_text"] = bool(getattr(rule, "applies_to_text", False))
    out["applies_to_image"] = bool(getattr(rule, "applies_to_image", False))
    out["applies_to_video"] = bool(getattr(rule, "applies_to_video", False))

    extra = _rule_extra_conditions(rule)
    if isinstance(extra, dict):
        extra_copy = dict(extra)
        extra_copy.pop("rule_kind", None)
        if extra_copy:
            out["extra_conditions"] = extra_copy
    return out


def _ensure_kie_standard_tables_for_admin(db: Session) -> None:
    dialect_name = str(getattr(getattr(db, "bind", None), "dialect", None).name if getattr(getattr(db, "bind", None), "dialect", None) else "").lower()

    if dialect_name == "postgresql":
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS kie_system_data_standard_values (
                id BIGSERIAL PRIMARY KEY,
                standard_dimension TEXT NOT NULL,
                standard_value TEXT NOT NULL,
                value_type TEXT NOT NULL,
                definition TEXT,
                alias_values TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (now()::text),
                updated_at TEXT NOT NULL DEFAULT (now()::text),
                UNIQUE(standard_dimension, standard_value)
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS kie_system_data_standard_mappings (
                id BIGSERIAL PRIMARY KEY,
                provider TEXT NOT NULL,
                model_key_inferred TEXT,
                model_title TEXT,
                model_url TEXT,
                source_field TEXT NOT NULL,
                source_enum_value TEXT NOT NULL,
                standard_dimension TEXT NOT NULL,
                standard_value TEXT NOT NULL,
                confidence TEXT,
                note TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_billing_related INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (now()::text),
                updated_at TEXT NOT NULL DEFAULT (now()::text),
                UNIQUE(provider, model_key_inferred, source_field, source_enum_value, standard_dimension, standard_value)
            )
        """))
    else:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS kie_system_data_standard_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                standard_dimension TEXT NOT NULL,
                standard_value TEXT NOT NULL,
                value_type TEXT NOT NULL,
                definition TEXT,
                alias_values TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(standard_dimension, standard_value)
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS kie_system_data_standard_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                model_key_inferred TEXT,
                model_title TEXT,
                model_url TEXT,
                source_field TEXT NOT NULL,
                source_enum_value TEXT NOT NULL,
                standard_dimension TEXT NOT NULL,
                standard_value TEXT NOT NULL,
                confidence TEXT,
                note TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_billing_related INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(provider, model_key_inferred, source_field, source_enum_value, standard_dimension, standard_value)
            )
        """))

    if dialect_name == "postgresql":
        db.execute(text("""
            ALTER TABLE kie_system_data_standard_mappings
            ADD COLUMN IF NOT EXISTS is_billing_related INTEGER NOT NULL DEFAULT 0
        """))
    else:
        # Reflect on the current transactional connection so newly created tables are visible.
        cols = {
            str(col.get("name") or "").strip().lower()
            for col in inspect(db.connection()).get_columns("kie_system_data_standard_mappings")
        }
        if "is_billing_related" not in cols:
            db.execute(text("ALTER TABLE kie_system_data_standard_mappings ADD COLUMN is_billing_related INTEGER NOT NULL DEFAULT 0"))

    db.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_kie_std_values_dim
        ON kie_system_data_standard_values(standard_dimension, is_active)
    """))
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_kie_std_mappings_lookup
        ON kie_system_data_standard_mappings(provider, model_key_inferred, standard_dimension, source_field, is_active)
    """))


_KIE_ENUM_FACT_CSV = Path(__file__).resolve().parents[3] / "_kie_input_param_enum_values_for_db.csv"
_KIE_ENUM_FACT_CACHE: Dict[str, Any] = {
    "mtime": None,
    "by_model_field": set(),
    "by_field": set(),
}


def _normalize_kie_enum_token(value: Any) -> str:
    return str(value or "").strip().lower()


def _load_kie_enum_fact_index() -> Dict[str, Any]:
    try:
        stat = _KIE_ENUM_FACT_CSV.stat()
        mtime = float(stat.st_mtime)
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="KIE enum catalog is unavailable; cannot validate source_enum_value",
        )

    cached_mtime = _KIE_ENUM_FACT_CACHE.get("mtime")
    if cached_mtime is not None and abs(float(cached_mtime) - mtime) < 1e-9:
        return _KIE_ENUM_FACT_CACHE

    by_model_field: set = set()
    by_field: set = set()
    try:
        with _KIE_ENUM_FACT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                model_key = _normalize_kie_enum_token(row.get("model_key_inferred"))
                field_path = _normalize_kie_enum_token(row.get("field_path"))
                enum_value = _normalize_kie_enum_token(row.get("enum_value"))
                if not field_path or not enum_value:
                    continue
                by_field.add((field_path, enum_value))
                if model_key:
                    by_model_field.add((model_key, field_path, enum_value))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Failed to load KIE enum catalog; cannot validate source_enum_value",
        )

    _KIE_ENUM_FACT_CACHE["mtime"] = mtime
    _KIE_ENUM_FACT_CACHE["by_model_field"] = by_model_field
    _KIE_ENUM_FACT_CACHE["by_field"] = by_field
    return _KIE_ENUM_FACT_CACHE


def _validate_kie_mapping_source_enum_allowed(
    *,
    provider: Any,
    model_key_inferred: Any,
    source_field: Any,
    source_enum_value: Any,
) -> None:
    provider_norm = _normalize_kie_enum_token(provider)
    if provider_norm != "kie":
        return

    field_norm = _normalize_kie_enum_token(source_field)
    value_norm = _normalize_kie_enum_token(source_enum_value)
    model_norm = _normalize_kie_enum_token(model_key_inferred)

    if not field_norm or not value_norm:
        raise HTTPException(status_code=400, detail="source_field and source_enum_value are required")

    # Strictly enforce API-side enum values. Non-API synthetic fields (e.g. matrix booleans)
    # are handled by separate pipelines and are excluded from this guard.
    if not field_norm.startswith("paths."):
        return

    idx = _load_kie_enum_fact_index()
    by_model_field = idx.get("by_model_field") if isinstance(idx.get("by_model_field"), set) else set()
    by_field = idx.get("by_field") if isinstance(idx.get("by_field"), set) else set()

    if model_norm:
        if (model_norm, field_norm, value_norm) in by_model_field:
            return
        raise HTTPException(
            status_code=400,
            detail=(
                "source_enum_value is not allowed by API enum catalog for this model/field: "
                f"model={model_norm}, field={field_norm}, value={value_norm}"
            ),
        )

    if (field_norm, value_norm) not in by_field:
        raise HTTPException(
            status_code=400,
            detail=(
                "source_enum_value is not allowed by API enum catalog for this field: "
                f"field={field_norm}, value={value_norm}"
            ),
        )


def _row_to_kie_standard_value_out(row: Dict[str, Any]) -> KIEDataStandardValueOut:
    return KIEDataStandardValueOut(
        id=int(row.get("id") or 0),
        standard_dimension=str(row.get("standard_dimension") or ""),
        standard_value=str(row.get("standard_value") or ""),
        value_type=str(row.get("value_type") or ""),
        definition=row.get("definition"),
        alias_values=row.get("alias_values"),
        is_active=bool(_to_bool(row.get("is_active"))),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _row_to_kie_mapping_out(row: Dict[str, Any]) -> KIEDataStandardMappingOut:
    return KIEDataStandardMappingOut(
        id=int(row.get("id") or 0),
        provider=str(row.get("provider") or ""),
        model_key_inferred=row.get("model_key_inferred"),
        model_title=row.get("model_title"),
        model_url=row.get("model_url"),
        source_field=str(row.get("source_field") or ""),
        source_enum_value=str(row.get("source_enum_value") or ""),
        standard_dimension=str(row.get("standard_dimension") or ""),
        standard_value=str(row.get("standard_value") or ""),
        confidence=row.get("confidence"),
        note=row.get("note"),
        is_active=bool(_to_bool(row.get("is_active"))),
        is_billing_related=bool(_to_bool(row.get("is_billing_related"))),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _extract_billing_related_dimensions(rule: SystemAPIBillingRule) -> set:
    out = set()
    if str(getattr(rule, "generation_mode", "") or "").strip():
        out.add("MODE")
    if str(getattr(rule, "output_format", "") or "").strip():
        out.add("OUTPUT_FORMAT")
    if getattr(rule, "has_audio", None) is not None:
        out.add("SOUND_SUPPORTED")
    if getattr(rule, "duration_seconds_min", None) is not None or getattr(rule, "duration_seconds_max", None) is not None:
        out.add("DURATION_SECONDS")

    extra = _rule_extra_conditions(rule)
    standard_values = extra.get("standard_values") if isinstance(extra.get("standard_values"), dict) else {}
    for key in standard_values.keys():
        dim = str(key or "").strip().upper()
        if dim:
            out.add(dim)

    for key in extra.keys():
        k = str(key or "").strip()
        if not k:
            continue
        low = k.lower()
        if low.startswith("standard."):
            dim = k.split(".", 1)[1].strip().upper()
            if dim:
                out.add(dim)
        elif low.startswith("standard_values."):
            dim = k.split(".", 1)[1].strip().upper()
            if dim:
                out.add(dim)

    return out


def _collect_kie_system_rule_hints(db: Session, system_rows: List[SystemAPISetting]) -> Dict[int, Dict[str, Any]]:
    ids = [int(getattr(row, "id", 0) or 0) for row in (system_rows or []) if int(getattr(row, "id", 0) or 0) > 0]
    if not ids:
        return {}

    hints: Dict[int, Dict[str, Any]] = {int(sid): {
        "has_granular_rules": False,
        "granular_rule_templates": [],
    } for sid in ids}

    if not _db_has_table(db, "system_api_billing_rules"):
        logger.warning("[_collect_kie_system_rule_hints] table missing: system_api_billing_rules")
        return hints

    try:
        rules = db.query(SystemAPIBillingRule).filter(
            SystemAPIBillingRule.system_api_id.in_(ids),
            SystemAPIBillingRule.is_active == True,
        ).order_by(
            SystemAPIBillingRule.system_api_id.asc(),
            SystemAPIBillingRule.priority.desc(),
            SystemAPIBillingRule.id.desc(),
        ).all()
    except Exception as e:
        logger.warning("[_collect_kie_system_rule_hints] failed to query billing rules: %s", e)
        return hints

    for rule in rules:
        sid = int(getattr(rule, "system_api_id", 0) or 0)
        if sid <= 0 or sid not in hints:
            continue
        if _is_base_billing_rule(rule):
            continue

        entry = hints[sid]
        entry["has_granular_rules"] = True
        templates = entry["granular_rule_templates"]
        if len(templates) >= _KIE_HINT_TEMPLATE_LIMIT_PER_MODEL:
            continue

        signature = _extract_rule_match_signature(rule)
        if signature:
            templates.append(signature)

    return hints


def _clear_row_billing_columns(row: SystemAPISetting) -> None:
    return


def _get_base_billing_rule(db: Session, system_api_id: int, include_inactive: bool = False) -> Optional[SystemAPIBillingRule]:
    query = db.query(SystemAPIBillingRule).filter(SystemAPIBillingRule.system_api_id == system_api_id)
    if not include_inactive:
        query = query.filter(SystemAPIBillingRule.is_active == True)
    rows = query.order_by(SystemAPIBillingRule.id.desc()).all()
    for row in rows:
        if _is_base_billing_rule(row):
            return row
    return None


def _upsert_base_billing_rule(
    db: Session,
    system_api_id: int,
    category: str,
    billing: Dict[str, Any],
    *,
    activate: bool = True,
) -> SystemAPIBillingRule:
    def _pick_cost_value(payload: Dict[str, Any], plain_key: str, billing_key: str) -> Any:
        if plain_key in payload and payload.get(plain_key) is not None:
            return payload.get(plain_key)
        return payload.get(billing_key)

    raw_billing = billing or {}
    normalized = {
        # Accept both internal keys (unit_type/cost) and suggestion keys (billing_unit_type/billing_cost).
        "unit_type": _normalize_billing_unit_type(
            raw_billing.get("unit_type")
            or raw_billing.get("billing_unit_type")
            or "per_call"
        ),
        "cost": _non_negative_int(_pick_cost_value(raw_billing, "cost", "billing_cost"), 0),
        "cost_input": _non_negative_int(_pick_cost_value(raw_billing, "cost_input", "billing_cost_input"), 0),
        "cost_output": _non_negative_int(_pick_cost_value(raw_billing, "cost_output", "billing_cost_output"), 0),
    }
    charge_multiplier = _normalize_rule_charge_multiplier(raw_billing.get("charge_multiplier"), default=2.0)
    flags = _category_to_mode_flags(category)
    rule = _get_base_billing_rule(db, system_api_id, include_inactive=True)
    now_iso = now_bj_iso()

    if rule:
        extra = _rule_extra_conditions(rule)
        extra["rule_kind"] = _BASE_BILLING_RULE_KIND
        rule.name = "Base Pricing"
        rule.description = "Base pricing rule generated from system API setting."
        rule.priority = _BASE_BILLING_RULE_PRIORITY
        rule.applies_to_text = bool(flags["text"])
        rule.applies_to_image = bool(flags["image"])
        rule.applies_to_video = bool(flags["video"])
        rule.generation_mode = None
        rule.input_format = None
        rule.output_format = None
        rule.has_audio = None
        rule.input_tokens_min = None
        rule.input_tokens_max = None
        rule.output_tokens_min = None
        rule.output_tokens_max = None
        rule.total_tokens_min = None
        rule.total_tokens_max = None
        rule.image_count_min = None
        rule.image_count_max = None
        rule.width_min = None
        rule.width_max = None
        rule.height_min = None
        rule.height_max = None
        rule.pixels_min = None
        rule.pixels_max = None
        rule.duration_seconds_min = None
        rule.duration_seconds_max = None
        rule.fps_min = None
        rule.fps_max = None
        rule.billing_unit_type = normalized["unit_type"]
        rule.billing_cost = normalized["cost"]
        rule.billing_cost_input = normalized["cost_input"]
        rule.billing_cost_output = normalized["cost_output"]
        rule.charge_multiplier = charge_multiplier
        rule.extra_conditions = extra
        if activate:
            rule.is_active = True
        rule.updated_at = now_iso
        return rule

    rule = SystemAPIBillingRule(
        system_api_id=system_api_id,
        name="Base Pricing",
        description="Base pricing rule generated from system API setting.",
        is_active=bool(activate),
        priority=_BASE_BILLING_RULE_PRIORITY,
        applies_to_text=bool(flags["text"]),
        applies_to_image=bool(flags["image"]),
        applies_to_video=bool(flags["video"]),
        generation_mode=None,
        input_format=None,
        output_format=None,
        has_audio=None,
        billing_unit_type=normalized["unit_type"],
        billing_cost=normalized["cost"],
        billing_cost_input=normalized["cost_input"],
        billing_cost_output=normalized["cost_output"],
        charge_multiplier=charge_multiplier,
        extra_conditions={"rule_kind": _BASE_BILLING_RULE_KIND},
        created_at=now_iso,
        updated_at=now_iso,
    )
    db.add(rule)
    db.flush()
    return rule


def _build_kie_resolution_granular_rules_from_note(
    raw_price_note: str,
    *,
    base_unit_type: str,
    source_unit: str,
) -> List[Dict[str, Any]]:
    """Fallback parser for multi-resolution notes like: 1K: 8, 2K: 12, 4K: 18."""
    text = str(raw_price_note or "").strip()
    if not text:
        return []

    pairs = re.findall(r"(\d+(?:\.\d+)?)\s*[kK]\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)", text)
    if not pairs:
        return []

    granular: List[Dict[str, Any]] = []
    seen_px: set = set()
    for res_text, cost_text in pairs:
        try:
            px = int(round(float(res_text) * 1024.0))
        except Exception:
            continue
        if px <= 0 or px in seen_px:
            continue
        seen_px.add(px)

        raw_cost = _safe_non_negative_number(cost_text)
        converted_cost = _convert_supplier_value_to_system_credit(raw_cost, source_unit)
        rule_label = f"{res_text}K"
        granular.append({
            "name": f"KIE Resolution {rule_label}",
            "description": f"Auto-generated KIE granular price for {rule_label}.",
            "billing_unit_type": _normalize_unit_type_for_system_ai(base_unit_type or "per_call"),
            "billing_cost": int(converted_cost),
            "billing_cost_input": 0,
            "billing_cost_output": 0,
            "applies_to_image": True,
            "image_count_min": 1,
            "image_count_max": 1,
            "width_min": int(px),
            "width_max": int(px),
            "height_min": int(px),
            "height_max": int(px),
            "pixels_min": int(px * px),
            "pixels_max": int(px * px),
            "priority": 2000 + int(px),
            "extra_conditions": {
                "rule_kind": _KIE_GRANULAR_RULE_KIND,
                "resolution_label": rule_label,
            },
        })

    granular.sort(key=lambda item: int(item.get("pixels_min") or 0))
    return granular


def _replace_kie_granular_billing_rules(
    db: Session,
    system_api_id: int,
    category: str,
    granular_rules: List[Dict[str, Any]],
    *,
    activate: bool = True,
) -> List[SystemAPIBillingRule]:
    """Replace KIE-managed granular rules for one system_api_id, keep non-KIE user rules untouched."""
    existing_rows = db.query(SystemAPIBillingRule).filter(
        SystemAPIBillingRule.system_api_id == int(system_api_id)
    ).all()

    for row in existing_rows:
        extra = _rule_extra_conditions(row)
        if str(extra.get("rule_kind") or "").strip().lower() == _KIE_GRANULAR_RULE_KIND:
            db.delete(row)

    if not granular_rules:
        db.flush()
        return []

    flags = _category_to_mode_flags(category)
    now_iso = now_bj_iso()
    created_rows: List[SystemAPIBillingRule] = []

    for idx, item in enumerate(granular_rules):
        if not isinstance(item, dict):
            continue
        normalized_unit = _normalize_unit_type_for_system_ai(item.get("billing_unit_type") or item.get("unit_type") or "per_call")
        billing_cost = _non_negative_int(item.get("billing_cost") if item.get("billing_cost") is not None else item.get("cost"), 0)
        billing_cost_input = _non_negative_int(item.get("billing_cost_input") if item.get("billing_cost_input") is not None else item.get("cost_input"), 0)
        billing_cost_output = _non_negative_int(item.get("billing_cost_output") if item.get("billing_cost_output") is not None else item.get("cost_output"), 0)

        item_extra = _safe_json_dict(item.get("extra_conditions") or {})
        item_extra["rule_kind"] = _KIE_GRANULAR_RULE_KIND

        row = SystemAPIBillingRule(
            system_api_id=int(system_api_id),
            name=str(item.get("name") or f"KIE Granular Rule #{idx + 1}").strip() or f"KIE Granular Rule #{idx + 1}",
            description=str(item.get("description") or "Auto-generated granular rule from KIE pricing suggestion.").strip(),
            is_active=bool(activate),
            priority=_non_negative_int(item.get("priority"), 1000),
            applies_to_text=bool(item.get("applies_to_text") if item.get("applies_to_text") is not None else flags["text"]),
            applies_to_image=bool(item.get("applies_to_image") if item.get("applies_to_image") is not None else flags["image"]),
            applies_to_video=bool(item.get("applies_to_video") if item.get("applies_to_video") is not None else flags["video"]),
            generation_mode=str(item.get("generation_mode") or "").strip() or None,
            input_format=str(item.get("input_format") or "").strip() or None,
            output_format=str(item.get("output_format") or "").strip() or None,
            has_audio=(None if item.get("has_audio") is None else bool(item.get("has_audio"))),
            input_tokens_min=(_safe_non_negative_int(item.get("input_tokens_min")) or None),
            input_tokens_max=(_safe_non_negative_int(item.get("input_tokens_max")) or None),
            output_tokens_min=(_safe_non_negative_int(item.get("output_tokens_min")) or None),
            output_tokens_max=(_safe_non_negative_int(item.get("output_tokens_max")) or None),
            total_tokens_min=(_safe_non_negative_int(item.get("total_tokens_min")) or None),
            total_tokens_max=(_safe_non_negative_int(item.get("total_tokens_max")) or None),
            image_count_min=(_safe_non_negative_int(item.get("image_count_min")) or None),
            image_count_max=(_safe_non_negative_int(item.get("image_count_max")) or None),
            width_min=(_safe_non_negative_int(item.get("width_min")) or None),
            width_max=(_safe_non_negative_int(item.get("width_max")) or None),
            height_min=(_safe_non_negative_int(item.get("height_min")) or None),
            height_max=(_safe_non_negative_int(item.get("height_max")) or None),
            pixels_min=(_safe_non_negative_int(item.get("pixels_min")) or None),
            pixels_max=(_safe_non_negative_int(item.get("pixels_max")) or None),
            duration_seconds_min=(_safe_non_negative_number(item.get("duration_seconds_min")) or None),
            duration_seconds_max=(_safe_non_negative_number(item.get("duration_seconds_max")) or None),
            fps_min=(_safe_non_negative_number(item.get("fps_min")) or None),
            fps_max=(_safe_non_negative_number(item.get("fps_max")) or None),
            billing_unit_type=normalized_unit,
            billing_cost=billing_cost,
            billing_cost_input=billing_cost_input,
            billing_cost_output=billing_cost_output,
            charge_multiplier=_normalize_rule_charge_multiplier(item.get("charge_multiplier"), default=2.0),
            extra_conditions=item_extra,
            created_at=now_iso,
            updated_at=now_iso,
        )
        db.add(row)
        created_rows.append(row)

    db.flush()
    return created_rows


def _resolve_system_setting_billing(db: Session, row: SystemAPISetting) -> Dict[str, Any]:
    base_rule = _get_base_billing_rule(db, int(row.id))
    if base_rule:
        return _rule_to_billing(base_rule)
    return _extract_billing_from_config(row.config)


def _setting_to_out(db: Session, row: SystemAPISetting) -> SystemAPISettingOut:
    billing = _resolve_system_setting_billing(db, row)
    out_cfg = _sync_model_mode_defaults_config(_strip_billing_from_config(row.config))
    model_mode_defaults = _extract_model_mode_defaults(out_cfg)
    base_model = _resolve_base_model(getattr(row, "base_model", None), getattr(row, "model", None))
    modality_fields = _extract_modality_manage_fields(getattr(row, "modality", None))
    return SystemAPISettingOut(
        id=row.id,
        name=row.name,
        category=row.category,
        provider=row.provider,
        api_key=row.api_key,
        base_url=row.base_url,
        model=row.model,
        base_model=base_model,
        modality=getattr(row, "modality", None),
        tags=getattr(row, "tags", None),
        supplier_info=getattr(row, "supplier_info", None),
        model_mode_defaults=(model_mode_defaults or None),
        config=out_cfg,
        billing_unit_type=billing["unit_type"],
        billing_cost=billing["cost"],
        billing_cost_input=billing["cost_input"],
        billing_cost_output=billing["cost_output"],
        has_granular_billing_rules=_has_granular_billing_rules(db, int(row.id)),
        deprecated=_is_setting_deprecated(out_cfg, row.deprecated),
        is_active=is_task_default_system_setting(db, int(row.id), row.category),
        **modality_fields,
    )


def _query_system_settings_manage_rows(db: Session):
    return db.query(
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
    ).filter(
        ~SystemAPISetting.category.like("System_%"),
    ).order_by(
        SystemAPISetting.category.asc(),
        SystemAPISetting.provider.asc(),
        SystemAPISetting.model.asc(),
        SystemAPISetting.id.asc(),
    ).all()


def _rule_to_out(rule: SystemAPIBillingRule) -> SystemAPIBillingRuleOut:
    if hasattr(SystemAPIBillingRuleOut, "model_validate"):
        return SystemAPIBillingRuleOut.model_validate(rule)
    return SystemAPIBillingRuleOut.from_orm(rule)


def _task_default_row_to_out(row: TaskDefaultSystemAPI, system_row: Optional[SystemAPISetting]) -> TaskDefaultSystemAPIManageOut:
    return TaskDefaultSystemAPIManageOut(
        task_category=normalize_task_category(getattr(row, "task_category", None)),
        system_api_id=int(getattr(row, "system_api_id", 0) or 0),
        system_api_category=str(getattr(system_row, "category", "") or "").strip() or None,
        system_api_provider=str(getattr(system_row, "provider", "") or "").strip() or None,
        system_api_model=str(getattr(system_row, "model", "") or "").strip() or None,
        system_api_name=str(getattr(system_row, "name", "") or "").strip() or None,
        created_at=str(getattr(row, "created_at", "") or "").strip() or None,
        updated_at=str(getattr(row, "updated_at", "") or "").strip() or None,
    )


def _assert_task_default_target_row(db: Session, system_api_id: int) -> SystemAPISetting:
    sid = _safe_non_negative_int(system_api_id)
    if sid <= 0:
        raise HTTPException(status_code=400, detail="system_api_id must be a positive integer")
    row = db.query(
        SystemAPISetting.id,
        SystemAPISetting.category,
        SystemAPISetting.provider,
        SystemAPISetting.model,
        SystemAPISetting.name,
    ).filter(SystemAPISetting.id == sid).first()
    if not row:
        raise HTTPException(status_code=404, detail="system_api_id not found")
    if _is_system_reserved_category(str(getattr(row, "category", "") or "")):
        raise HTTPException(status_code=400, detail="system_api_id cannot reference System_* infrastructure categories")
    return row


@router.get("/settings/system/manage/task-default-apis", response_model=List[TaskDefaultSystemAPIManageOut])
def list_task_default_apis_for_manage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    if HAS_TASK_DEFAULT_SYSTEM_API_MODEL:
        rows = db.query(TaskDefaultSystemAPI).order_by(TaskDefaultSystemAPI.task_category.asc()).all()
        system_rows = db.query(
            SystemAPISetting.id,
            SystemAPISetting.category,
            SystemAPISetting.provider,
            SystemAPISetting.model,
            SystemAPISetting.name,
        ).filter(
            SystemAPISetting.id.in_([int(getattr(row, "system_api_id", 0) or 0) for row in rows])
        ).all() if rows else []
        by_id = {int(item.id): item for item in system_rows}
        return [_task_default_row_to_out(row, by_id.get(int(getattr(row, "system_api_id", 0) or 0))) for row in rows]

    # Legacy fallback: infer defaults from active rows when mapping table/model is unavailable.
    active_rows = db.query(
        SystemAPISetting.id,
        SystemAPISetting.category,
        SystemAPISetting.provider,
        SystemAPISetting.model,
        SystemAPISetting.name,
        SystemAPISetting.is_active,
    ).filter(
        SystemAPISetting.is_active == True,
        ~SystemAPISetting.category.like("System_%"),
    ).order_by(SystemAPISetting.id.desc()).all()
    out = []
    seen = set()
    for row in active_rows:
        task_category = normalize_task_category(getattr(row, "category", None))
        if task_category in seen:
            continue
        seen.add(task_category)
        out.append(TaskDefaultSystemAPIManageOut(
            task_category=task_category,
            system_api_id=int(getattr(row, "id", 0) or 0),
            system_api_category=str(getattr(row, "category", "") or "").strip() or None,
            system_api_provider=str(getattr(row, "provider", "") or "").strip() or None,
            system_api_model=str(getattr(row, "model", "") or "").strip() or None,
            system_api_name=str(getattr(row, "name", "") or "").strip() or None,
            created_at=None,
            updated_at=None,
        ))
    return out


@router.post("/settings/system/manage/task-default-apis", response_model=TaskDefaultSystemAPIManageOut)
def create_task_default_api_for_manage(
    payload: TaskDefaultSystemAPIManageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    category = normalize_task_category(payload.task_category)
    target = _assert_task_default_target_row(db, payload.system_api_id)
    upsert_task_default_system_setting(db, category, int(target.id))
    db.commit()

    if HAS_TASK_DEFAULT_SYSTEM_API_MODEL:
        record = db.query(TaskDefaultSystemAPI).filter(TaskDefaultSystemAPI.task_category == category).first()
        if not record:
            raise HTTPException(status_code=500, detail="failed to create task default mapping")
        db.refresh(record)
        return _task_default_row_to_out(record, target)

    return TaskDefaultSystemAPIManageOut(
        task_category=category,
        system_api_id=int(target.id),
        system_api_category=str(getattr(target, "category", "") or "").strip() or None,
        system_api_provider=str(getattr(target, "provider", "") or "").strip() or None,
        system_api_model=str(getattr(target, "model", "") or "").strip() or None,
        system_api_name=str(getattr(target, "name", "") or "").strip() or None,
        created_at=None,
        updated_at=None,
    )


@router.post("/settings/system/manage/task-default-apis/{task_category}", response_model=TaskDefaultSystemAPIManageOut)
def update_task_default_api_for_manage(
    task_category: str,
    payload: TaskDefaultSystemAPIManageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    category = normalize_task_category(task_category)
    target = _assert_task_default_target_row(db, payload.system_api_id)
    upsert_task_default_system_setting(db, category, int(target.id))
    db.commit()

    if HAS_TASK_DEFAULT_SYSTEM_API_MODEL:
        record = db.query(TaskDefaultSystemAPI).filter(TaskDefaultSystemAPI.task_category == category).first()
        if not record:
            raise HTTPException(status_code=404, detail="task default mapping not found")
        db.refresh(record)
        return _task_default_row_to_out(record, target)

    return TaskDefaultSystemAPIManageOut(
        task_category=category,
        system_api_id=int(target.id),
        system_api_category=str(getattr(target, "category", "") or "").strip() or None,
        system_api_provider=str(getattr(target, "provider", "") or "").strip() or None,
        system_api_model=str(getattr(target, "model", "") or "").strip() or None,
        system_api_name=str(getattr(target, "name", "") or "").strip() or None,
        created_at=None,
        updated_at=None,
    )


@router.delete("/settings/system/manage/task-default-apis/{task_category}")
def delete_task_default_api_for_manage(
    task_category: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    category = normalize_task_category(task_category)
    if HAS_TASK_DEFAULT_SYSTEM_API_MODEL:
        existing = db.query(TaskDefaultSystemAPI).filter(TaskDefaultSystemAPI.task_category == category).first()
        if not existing:
            raise HTTPException(status_code=404, detail="task default mapping not found")
    clear_task_default_for_category(db, category)
    db.commit()
    return {"ok": True, "task_category": category}


def _is_setting_deprecated(config_value, deprecated_flag: Any = None) -> bool:
    return _to_bool(deprecated_flag)


def _non_negative_int(value: Any, default: int = 0) -> int:
    try:
        parsed = int(float(value))
        return parsed if parsed >= 0 else 0
    except Exception:
        return default


def _normalize_billing_unit_type(raw: Any) -> str:
    text = str(raw or "per_call").strip() or "per_call"
    allowed = {"per_call", "per_second", "per_minute", "per_token", "per_1k_tokens", "per_million_tokens"}
    return text if text in allowed else "per_call"


def _normalize_rule_charge_multiplier(raw: Any, default: float = 2.0) -> float:
    try:
        parsed = float(raw) if raw is not None else float(default)
    except Exception:
        parsed = float(default)
    if parsed < 0:
        parsed = float(default)
    return float(round(parsed, 4))


def _rule_cost_score(rule: SystemAPIBillingRule) -> int:
    # Use the largest effective per-unit cost as rule "cost level" for scaling.
    cost = _non_negative_int(getattr(rule, "billing_cost", 0), 0)
    cost_input = _non_negative_int(getattr(rule, "billing_cost_input", 0), 0)
    cost_output = _non_negative_int(getattr(rule, "billing_cost_output", 0), 0)
    return int(max(cost, cost_input, cost_output))


def _rule_multiplier_score_x100(rule: SystemAPIBillingRule) -> int:
    multiplier = _safe_non_negative_float(getattr(rule, "charge_multiplier", None))
    if multiplier <= 0:
        multiplier = 2.0
    return int(round(multiplier * 100.0))


def _rule_effective_cost_score(rule: SystemAPIBillingRule) -> int:
    cost = _non_negative_int(getattr(rule, "billing_cost", 0), 0)
    cost_input = _non_negative_int(getattr(rule, "billing_cost_input", 0), 0)
    cost_output = _non_negative_int(getattr(rule, "billing_cost_output", 0), 0)
    multiplier = _normalize_rule_charge_multiplier(getattr(rule, "charge_multiplier", None), default=2.0)
    return int(max(
        _apply_charge_multiplier_to_credit(cost, multiplier),
        _apply_charge_multiplier_to_credit(cost_input, multiplier),
        _apply_charge_multiplier_to_credit(cost_output, multiplier),
    ))


def _system_api_pricing_from_rules_and_audit(
    db: Session,
    system_api_id: int,
) -> Dict[str, Any]:
    """Settings pricing summary from rules + audit only.

    - price range: system_api_billing_rules by system_api_id
    - sample/average: transaction_action audit by system_api_id
    """
    sid = _safe_int(system_api_id, 0)
    if sid <= 0:
        return {
            "average_cost": 0,
            "source": "rules_and_audit_only",
            "min_cost": 0,
            "max_cost": 0,
            "sample_prices": [],
        }

    rule_rows = db.query(SystemAPIBillingRule).filter(
        SystemAPIBillingRule.system_api_id == sid,
        or_(SystemAPIBillingRule.is_active == True, SystemAPIBillingRule.is_active.is_(None)),
    ).all()
    rule_scores: List[int] = []
    for row in rule_rows:
        c = _rule_effective_cost_score(row)
        if c > 0:
            rule_scores.append(int(c))

    range_min = int(min(rule_scores)) if rule_scores else 0
    range_max = int(max(rule_scores)) if rule_scores else 0

    rule_ids = [int(getattr(row, "id", 0) or 0) for row in rule_rows if int(getattr(row, "id", 0) or 0) > 0]

    avg_cost = int(round(sum(rule_scores) / float(len(rule_scores)))) if rule_scores else 0
    sample_prices: List[int] = []

    return {
        "average_cost": max(0, int(avg_cost)),
        "source": "billing_cost_x_multiplier",
        "min_cost": max(0, int(range_min)),
        "max_cost": max(0, int(range_max)),
        "sample_prices": sample_prices,
    }


def _batch_system_api_pricing_from_rules_and_audit(
    db: Session,
    system_api_ids: List[int],
    include_audit: bool = True,
) -> Dict[int, Dict[str, Any]]:
    normalized_ids = sorted({_safe_int(sid, 0) for sid in (system_api_ids or []) if _safe_int(sid, 0) > 0})
    if not normalized_ids:
        return {}

    id_set = set(normalized_ids)
    default_value = {
        "average_cost": 0,
        "source": "billing_cost_x_multiplier",
        "min_cost": 0,
        "max_cost": 0,
        "sample_prices": [],
    }
    result: Dict[int, Dict[str, Any]] = {sid: dict(default_value) for sid in normalized_ids}

    rule_rows = db.query(
        SystemAPIBillingRule.id,
        SystemAPIBillingRule.system_api_id,
        SystemAPIBillingRule.billing_cost,
        SystemAPIBillingRule.billing_cost_input,
        SystemAPIBillingRule.billing_cost_output,
        SystemAPIBillingRule.charge_multiplier,
    ).filter(
        SystemAPIBillingRule.system_api_id.in_(normalized_ids),
        or_(SystemAPIBillingRule.is_active == True, SystemAPIBillingRule.is_active.is_(None)),
    ).all()

    rule_ids: List[int] = []
    rule_id_to_sid: Dict[int, int] = {}
    rule_costs_by_sid: Dict[int, List[int]] = defaultdict(list)
    for row in rule_rows:
        sid = _safe_int(getattr(row, "system_api_id", 0), 0)
        rid = _safe_int(getattr(row, "id", 0), 0)
        if sid <= 0:
            continue
        if rid > 0:
            rule_ids.append(rid)
            rule_id_to_sid[rid] = sid
        cost = _non_negative_int(getattr(row, "billing_cost", 0), 0)
        cost_input = _non_negative_int(getattr(row, "billing_cost_input", 0), 0)
        cost_output = _non_negative_int(getattr(row, "billing_cost_output", 0), 0)
        multiplier = _normalize_rule_charge_multiplier(getattr(row, "charge_multiplier", None), default=2.0)
        c = int(max(
            _apply_charge_multiplier_to_credit(cost, multiplier),
            _apply_charge_multiplier_to_credit(cost_input, multiplier),
            _apply_charge_multiplier_to_credit(cost_output, multiplier),
        ))
        if c > 0:
            rule_costs_by_sid[sid].append(int(c))

    for sid, costs in rule_costs_by_sid.items():
        if sid not in result or not costs:
            continue
        result[sid]["min_cost"] = int(min(costs))
        result[sid]["max_cost"] = int(max(costs))

    # Fast path for settings page: avoid scanning large audit tables.
    if not include_audit:
        for sid in normalized_ids:
            costs = rule_costs_by_sid.get(sid) or []
            if costs:
                result[sid]["average_cost"] = int(round(sum(costs) / float(len(costs))))
                result[sid]["sample_prices"] = []
            result[sid]["source"] = "billing_cost_x_multiplier"
        return result

    for sid in normalized_ids:
        costs = rule_costs_by_sid.get(sid) or []
        avg_cost = int(round(sum(costs) / float(len(costs)))) if costs else 0
        result[sid]["average_cost"] = max(0, int(avg_cost))
        result[sid]["sample_prices"] = []
        result[sid]["source"] = "billing_cost_x_multiplier"

    return result


def _batch_system_api_primary_billing_unit_type(
    db: Session,
    system_api_ids: List[int],
) -> Dict[int, str]:
    normalized_ids = sorted({_safe_int(sid, 0) for sid in (system_api_ids or []) if _safe_int(sid, 0) > 0})
    if not normalized_ids:
        return {}

    rows = db.query(
        SystemAPIBillingRule.system_api_id,
        SystemAPIBillingRule.billing_unit_type,
        SystemAPIBillingRule.priority,
        SystemAPIBillingRule.id,
    ).filter(
        SystemAPIBillingRule.system_api_id.in_(normalized_ids),
        or_(SystemAPIBillingRule.is_active == True, SystemAPIBillingRule.is_active.is_(None)),
    ).order_by(
        SystemAPIBillingRule.system_api_id.asc(),
        SystemAPIBillingRule.priority.desc(),
        SystemAPIBillingRule.id.desc(),
    ).all()

    result: Dict[int, str] = {}
    for row in rows or []:
        sid = _safe_int(getattr(row, "system_api_id", 0), 0)
        if sid <= 0 or sid in result:
            continue
        unit = _normalize_billing_unit_type(getattr(row, "billing_unit_type", None))
        result[sid] = unit

    return result


_SETTINGS_PRICE_CACHE_KEY = "settings_price_summary"
_SETTINGS_PROVIDER_PRICE_CACHE_KEY = "settings_provider_price_summary"


def _read_settings_price_cache(config_value: Any) -> Dict[str, Any]:
    cfg = _safe_json_dict(config_value)
    raw = cfg.get(_SETTINGS_PRICE_CACHE_KEY) if isinstance(cfg.get(_SETTINGS_PRICE_CACHE_KEY), dict) else {}
    return {
        "average_cost": _safe_int(raw.get("average_cost"), 0),
        "source": str(raw.get("source") or "") or None,
        "min_cost": _safe_int(raw.get("min_cost"), 0),
        "max_cost": _safe_int(raw.get("max_cost"), 0),
        "sample_prices": [
            int(v)
            for v in (raw.get("sample_prices") or [])
            if _safe_int(v, 0) > 0
        ],
    }


def _read_settings_provider_price_cache(config_value: Any) -> Dict[str, Any]:
    cfg = _safe_json_dict(config_value)
    raw = cfg.get(_SETTINGS_PROVIDER_PRICE_CACHE_KEY) if isinstance(cfg.get(_SETTINGS_PROVIDER_PRICE_CACHE_KEY), dict) else {}
    return {
        "average_cost": _safe_int(raw.get("average_cost"), 0),
        "source": str(raw.get("source") or "") or None,
        "min_cost": _safe_int(raw.get("min_cost"), 0),
        "max_cost": _safe_int(raw.get("max_cost"), 0),
        "sample_prices": [
            int(v)
            for v in (raw.get("sample_prices") or [])
            if _safe_int(v, 0) > 0
        ],
        "updated_at": str(raw.get("updated_at") or "").strip() or None,
    }


def _read_settings_price_cache_from_row(row: Any) -> Dict[str, Any]:
    if row is None:
        return {
            "average_cost": 0,
            "source": None,
            "min_cost": 0,
            "max_cost": 0,
            "sample_prices": [],
            "updated_at": None,
        }

    col_avg = _safe_int(getattr(row, "price_avg_cost", None), 0)
    col_min = _safe_int(getattr(row, "price_min_cost", None), 0)
    col_max = _safe_int(getattr(row, "price_max_cost", None), 0)
    col_source = str(getattr(row, "price_source", "") or "").strip() or None
    col_updated = str(getattr(row, "price_updated_at", "") or "").strip() or None
    raw_samples = getattr(row, "price_sample_prices", None)
    col_samples = [
        int(v)
        for v in (raw_samples if isinstance(raw_samples, list) else [])
        if _safe_int(v, 0) > 0
    ]

    has_col_payload = bool(col_avg or col_min or col_max or col_source or col_samples or col_updated)
    if has_col_payload:
        return {
            "average_cost": col_avg,
            "source": col_source,
            "min_cost": col_min,
            "max_cost": col_max,
            "sample_prices": col_samples,
            "updated_at": col_updated,
        }

    return _read_settings_price_cache(getattr(row, "config", None))


def _read_settings_provider_price_cache_from_row(row: Any) -> Dict[str, Any]:
    if row is None:
        return {
            "average_cost": 0,
            "source": None,
            "min_cost": 0,
            "max_cost": 0,
            "sample_prices": [],
            "updated_at": None,
        }

    col_avg = _safe_int(getattr(row, "provider_price_avg_cost", None), 0)
    col_min = _safe_int(getattr(row, "provider_price_min_cost", None), 0)
    col_max = _safe_int(getattr(row, "provider_price_max_cost", None), 0)
    col_source = str(getattr(row, "provider_price_source", "") or "").strip() or None
    col_updated = str(getattr(row, "provider_price_updated_at", "") or "").strip() or None
    raw_samples = getattr(row, "provider_price_sample_prices", None)
    col_samples = [
        int(v)
        for v in (raw_samples if isinstance(raw_samples, list) else [])
        if _safe_int(v, 0) > 0
    ]

    has_col_payload = bool(col_avg or col_min or col_max or col_source or col_samples or col_updated)
    if has_col_payload:
        return {
            "average_cost": col_avg,
            "source": col_source,
            "min_cost": col_min,
            "max_cost": col_max,
            "sample_prices": col_samples,
            "updated_at": col_updated,
        }

    return _read_settings_provider_price_cache(getattr(row, "config", None))


def _extract_webhook_and_price_cache(config_value: Any) -> Tuple[Optional[str], Dict[str, Any]]:
    if isinstance(config_value, dict):
        webhook = str(config_value.get("webHook") or "").strip() or None
        return webhook, _read_settings_price_cache(config_value)

    if isinstance(config_value, str):
        raw = config_value
        has_webhook_hint = '"webHook"' in raw
        has_price_hint = _SETTINGS_PRICE_CACHE_KEY in raw
        if not has_webhook_hint and not has_price_hint:
            return None, {
                "average_cost": 0,
                "source": None,
                "min_cost": 0,
                "max_cost": 0,
                "sample_prices": [],
            }

        cfg = _safe_json_dict(raw)
        webhook = str(cfg.get("webHook") or "").strip() or None
        return webhook, _read_settings_price_cache(cfg)

    return None, {
        "average_cost": 0,
        "source": None,
        "min_cost": 0,
        "max_cost": 0,
        "sample_prices": [],
    }


def _settings_price_cache_is_legacy(config_value: Any) -> bool:
    price_cache = _read_settings_price_cache(config_value)
    provider_cache = _read_settings_provider_price_cache(config_value)
    return (
        str(price_cache.get("source") or "").strip().lower() == "charge_multiplier_x100"
        or str(provider_cache.get("source") or "").strip().lower() == "provider_range_from_rules_sample_from_audit"
    )


def _refresh_settings_price_cache_for_system_apis(db: Session, system_api_ids: List[int]) -> int:
    ids = sorted({_safe_int(sid, 0) for sid in (system_api_ids or []) if _safe_int(sid, 0) > 0})
    if not ids:
        return 0

    pricing_map = _batch_system_api_pricing_from_rules_and_audit(db, ids, include_audit=True)
    rows = db.execute(text("""
        SELECT id, config
        FROM system_api_settings
        WHERE id IN :ids
    """).bindparams(bindparam("ids", expanding=True)), {"ids": ids}).mappings().all()
    changed = 0
    now_iso = now_bj_iso()

    for row in rows:
        sid = int(row.get("id") or 0)
        next_price = pricing_map.get(sid, {
            "average_cost": 0,
            "source": "range_from_rules_sample_from_audit",
            "min_cost": 0,
            "max_cost": 0,
            "sample_prices": [],
        })

        cfg = _safe_json_dict(row.get("config"))
        current_cfg = _read_settings_price_cache(cfg)
        current_cfg_cmp = {
            "average_cost": int(current_cfg.get("average_cost") or 0),
            "source": str(current_cfg.get("source") or "") or None,
            "min_cost": int(current_cfg.get("min_cost") or 0),
            "max_cost": int(current_cfg.get("max_cost") or 0),
            "sample_prices": [int(v) for v in (current_cfg.get("sample_prices") or []) if int(v or 0) > 0],
        }
        next_cmp = {
            "average_cost": int(next_price.get("average_cost") or 0),
            "source": str(next_price.get("source") or "") or None,
            "min_cost": int(next_price.get("min_cost") or 0),
            "max_cost": int(next_price.get("max_cost") or 0),
            "sample_prices": [int(v) for v in (next_price.get("sample_prices") or []) if int(v or 0) > 0],
        }

        if current_cfg_cmp == next_cmp:
            continue

        cfg[_SETTINGS_PRICE_CACHE_KEY] = {
            **next_cmp,
            "updated_at": now_iso,
        }
        db.execute(text("""
            UPDATE system_api_settings
            SET config = :config
            WHERE id = :id
        """), {
            "id": sid,
            "config": _safe_json_text(cfg),
        })
        changed += 1

    return changed


def _refresh_settings_provider_price_cache_for_system_apis(db: Session, system_api_ids: List[int]) -> int:
    ids = sorted({_safe_int(sid, 0) for sid in (system_api_ids or []) if _safe_int(sid, 0) > 0})
    if not ids:
        return 0

    touched_rows = db.execute(text("""
        SELECT id, provider, category
        FROM system_api_settings
        WHERE id IN :ids
    """).bindparams(bindparam("ids", expanding=True)), {"ids": ids}).mappings().all()

    touched_keys: set = set()
    for row in touched_rows:
        provider_key = str(row.get("provider") or "").strip().lower()
        category_key = str(row.get("category") or "").strip().lower()
        if provider_key and category_key:
            touched_keys.add((provider_key, category_key))

    if not touched_keys:
        return 0

    candidate_rows = db.execute(text("""
        SELECT id, provider, category, config, deprecated
        FROM system_api_settings
        WHERE lower(coalesce(category, '')) NOT LIKE 'system_%'
    """)).mappings().all()

    grouped_rows: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for row in candidate_rows:
        provider_key = str(row.get("provider") or "").strip().lower()
        category_key = str(row.get("category") or "").strip().lower()
        if not provider_key or not category_key:
            continue
        key = (provider_key, category_key)
        if key not in touched_keys:
            continue
        grouped_rows.setdefault(key, []).append(row)

    if not grouped_rows:
        return 0

    all_group_ids: List[int] = []
    for rows in grouped_rows.values():
        for row in rows:
            sid = _safe_int(row.get("id"), 0)
            if sid > 0:
                all_group_ids.append(sid)

    pricing_map = _batch_system_api_pricing_from_rules_and_audit(db, all_group_ids, include_audit=True)
    changed = 0
    now_iso = now_bj_iso()

    for _, rows in grouped_rows.items():
        active_rows = [
            row
            for row in rows
            if not _is_setting_deprecated(row.get("config"), row.get("deprecated"))
        ]

        min_candidates: List[int] = []
        max_candidates: List[int] = []
        sample_candidates: List[int] = []

        for row in active_rows:
            sid = _safe_int(row.get("id"), 0)
            if sid <= 0:
                continue
            p = pricing_map.get(sid) or {}
            min_cost = _safe_int(p.get("min_cost"), 0)
            max_cost = _safe_int(p.get("max_cost"), 0)
            avg_cost = _safe_int(p.get("average_cost"), 0)
            if min_cost > 0:
                min_candidates.append(min_cost)
            if max_cost > 0:
                max_candidates.append(max_cost)
            for v in (p.get("sample_prices") or []):
                iv = _safe_int(v, 0)
                if iv > 0:
                    sample_candidates.append(iv)

        sample_prices = sorted(set(sample_candidates))[:5] if sample_candidates else []
        avg_cost = int(round(sum(sample_candidates) / float(len(sample_candidates)))) if sample_candidates else 0
        min_cost = int(min(min_candidates)) if min_candidates else 0
        max_cost = int(max(max_candidates)) if max_candidates else 0

        next_cmp = {
            "average_cost": max(0, int(avg_cost)),
            "source": "effective_provider_range_from_rules",
            "min_cost": max(0, int(min_cost)),
            "max_cost": max(0, int(max_cost)),
            "sample_prices": [int(v) for v in sample_prices if int(v) > 0],
        }

        for row in rows:
            sid = _safe_int(row.get("id"), 0)
            if sid <= 0:
                continue

            cfg = _safe_json_dict(row.get("config"))
            current_cfg = _read_settings_provider_price_cache(cfg)
            current_cfg_cmp = {
                "average_cost": int(current_cfg.get("average_cost") or 0),
                "source": str(current_cfg.get("source") or "") or None,
                "min_cost": int(current_cfg.get("min_cost") or 0),
                "max_cost": int(current_cfg.get("max_cost") or 0),
                "sample_prices": [int(v) for v in (current_cfg.get("sample_prices") or []) if int(v or 0) > 0],
            }
            if current_cfg_cmp == next_cmp:
                continue

            cfg[_SETTINGS_PROVIDER_PRICE_CACHE_KEY] = {
                **next_cmp,
                "updated_at": now_iso,
            }
            db.execute(text("""
                UPDATE system_api_settings
                SET config = :config
                WHERE id = :id
            """), {
                "id": sid,
                "config": _safe_json_text(cfg),
            })
            changed += 1

    return changed


def _compute_cost_scaled_multiplier(cost_score: int, min_cost: int, max_cost: int, min_multiplier: float, max_multiplier: float) -> float:
    if max_cost <= min_cost:
        return float(round((float(min_multiplier) + float(max_multiplier)) / 2.0, 4))
    normalized = (float(cost_score) - float(min_cost)) / (float(max_cost) - float(min_cost))
    normalized = max(0.0, min(1.0, normalized))
    # Higher score => lower multiplier.
    multiplier = float(max_multiplier) - (float(max_multiplier) - float(min_multiplier)) * normalized
    multiplier = max(float(min_multiplier), min(float(max_multiplier), multiplier))
    return float(round(multiplier, 4))


_BILLING_CONFIG_KEYS = {"api_pricing", "billing_unit_type", "billing_cost", "billing_cost_input", "billing_cost_output"}


def _normalize_model_mode_defaults(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: Dict[str, str] = {}
    for raw_model, raw_mode in value.items():
        model_name = str(raw_model or "").strip()
        mode_name = str(raw_mode or "").strip()
        if not model_name or not mode_name:
            continue
        normalized[model_name] = mode_name
    return normalized


def _extract_model_mode_defaults(config_value: Any) -> Dict[str, str]:
    cfg = _safe_json_dict(config_value)
    for key in _MODEL_MODE_DEFAULTS_ALIASES:
        normalized = _normalize_model_mode_defaults(cfg.get(key))
        if normalized:
            return normalized
    return {}


def _sync_model_mode_defaults_config(config_value: Any, model_mode_defaults: Any = None, provided: bool = False) -> Dict[str, Any]:
    cfg = _safe_json_dict(config_value)
    existing_defaults = _extract_model_mode_defaults(cfg)

    for key in _MODEL_MODE_DEFAULTS_ALIASES:
        cfg.pop(key, None)

    if provided:
        next_defaults = _normalize_model_mode_defaults(model_mode_defaults)
        if next_defaults:
            cfg[_MODEL_MODE_DEFAULTS_KEY] = next_defaults
        return cfg

    if existing_defaults:
        cfg[_MODEL_MODE_DEFAULTS_KEY] = existing_defaults
    return cfg


def _extract_billing_from_config(config_value: Any) -> Dict[str, Any]:
    """Extract billing fields from a config dict."""
    cfg = _safe_json_dict(config_value)
    ap = cfg.get("api_pricing") if isinstance(cfg.get("api_pricing"), dict) else {}
    return {
        "unit_type": _normalize_billing_unit_type(ap.get("unit_type") or cfg.get("billing_unit_type") or "per_call"),
        "cost": _non_negative_int(ap.get("cost", cfg.get("billing_cost", 0))),
        "cost_input": _non_negative_int(ap.get("cost_input", cfg.get("billing_cost_input", 0))),
        "cost_output": _non_negative_int(ap.get("cost_output", cfg.get("billing_cost_output", 0))),
    }


def _strip_billing_from_config(config_value: Any) -> Dict[str, Any]:
    """Return config dict without billing-related keys."""
    cfg = _safe_json_dict(config_value)
    for key in _BILLING_CONFIG_KEYS:
        cfg.pop(key, None)
    return cfg


def _normalize_system_api_billing_config(config_value: Any) -> Dict[str, Any]:
    """Compatibility wrapper to strip billing fields from config."""
    return _strip_billing_from_config(config_value)


def _billing_from_payload_or_config(payload, raw_config: dict) -> Dict[str, Any]:
    """Prefer explicit billing fields from payload, else read from config."""
    ut = getattr(payload, "billing_unit_type", None)
    c = getattr(payload, "billing_cost", None)
    ci = getattr(payload, "billing_cost_input", None)
    co = getattr(payload, "billing_cost_output", None)
    if ut is not None or c is not None or ci is not None or co is not None:
        return {
            "unit_type": _normalize_billing_unit_type(ut or "per_call"),
            "cost": _non_negative_int(c if c is not None else 0),
            "cost_input": _non_negative_int(ci if ci is not None else 0),
            "cost_output": _non_negative_int(co if co is not None else 0),
        }
    return _extract_billing_from_config(raw_config)


def _sync_row_billing_columns(row: SystemAPISetting, billing: Dict[str, Any] = None, config_value: Any = None) -> None:
    return


def _is_system_reserved_category(category: Any) -> bool:
    return str(category or "").strip().lower().startswith("system_")


def _migrate_system_api_pricing_to_base_rules(db: Session) -> int:
    rows = db.query(SystemAPISetting).filter(
        ~SystemAPISetting.category.like("System_%"),
    ).all()
    if not rows:
        return 0

    migrated = 0
    for row in rows:
        billing = _resolve_system_setting_billing(db, row)
        has_pricing = any(_non_negative_int(billing.get(k, 0), 0) > 0 for k in ("cost", "cost_input", "cost_output"))
        if not has_pricing:
            continue

        existing_base = _get_base_billing_rule(db, int(row.id), include_inactive=True)
        if existing_base:
            _clear_row_billing_columns(row)
            row.config = _strip_billing_from_config(row.config)
            continue

        _upsert_base_billing_rule(db, int(row.id), row.category, billing, activate=True)
        _clear_row_billing_columns(row)
        row.config = _strip_billing_from_config(row.config)
        _refresh_has_granular_billing_rules_flag(db, int(row.id))
        migrated += 1

    return migrated


def _is_system_api_auto_billing_sync_enabled() -> bool:
    """Global switch for legacy auto-sync from system_api_settings -> billing rules.

    Keep disabled so billing rules are only changed by explicit billing-rule actions.
    """
    return False


def _ensure_builtin_system_settings(db: Session) -> None:
    kie_base_url = "https://api.kie.ai"

    def _kie_item(name: str, category: str, model: str, extra_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        config = {
            "endpoint": f"{kie_base_url}/api/v1/jobs/createTask",
            "query_endpoint": f"{kie_base_url}/api/v1/jobs/recordInfo",
            "credits_endpoint": f"{kie_base_url}/api/v1/user/credits",
            "credits_endpoint_v2": f"{kie_base_url}/api/v1/chat/credit",
            "deprecated": False,
        }
        if isinstance(extra_config, dict) and extra_config:
            config.update(extra_config)
        return {
            "name": name,
            "category": category,
            "provider": "kie",
            "base_url": kie_base_url,
            "model": model,
            "config": config,
        }

    builtins = [
        _kie_item("Kie Seedream 4.5", "Image", "seedream/4.5-text-to-image"),
        _kie_item("Kie Seedream 4.5 Edit", "Image", "seedream/4.5-edit"),
        _kie_item("Kie Google Imagen4 Fast (Canonical)", "Image", "google/imagen4-fast"),
        _kie_item("Kie Google Imagen4 Ultra (Canonical)", "Image", "google/imagen4-ultra"),
        _kie_item("Kie Google Imagen4", "Image", "google/imagen4"),
        _kie_item("Kie Google Nano Banana", "Image", "google/nano-banana"),
        _kie_item("Kie Google Nano Banana Edit", "Image", "google/nano-banana-edit"),
        _kie_item("Kie Google Nano Banana 2", "Image", "google/nanobanana2"),
        _kie_item("Kie Google Pro Image-to-Image", "Image", "google/pro-image-to-image"),
        _kie_item("Kie Grok Imagine T2I (Canonical)", "Image", "grok-imagine/text-to-image"),
        _kie_item("Kie Grok Imagine I2I (Canonical)", "Image", "grok-imagine/image-to-image"),
        _kie_item("Kie Grok Imagine Upscale (Canonical)", "Image", "grok-imagine/upscale"),
        _kie_item("Kie Qwen T2I (Canonical)", "Image", "qwen/text-to-image"),
        _kie_item("Kie Qwen I2I (Canonical)", "Image", "qwen/image-to-image"),
        _kie_item("Kie Qwen Edit (Canonical)", "Image", "qwen/image-edit"),
        _kie_item("Kie Flux2 Pro T2I (Canonical)", "Image", "flux-2/pro-text-to-image"),
        _kie_item("Kie Flux2 Pro I2I (Canonical)", "Image", "flux-2/pro-image-to-image"),
        _kie_item("Kie Flux2 Flex T2I (Canonical)", "Image", "flux-2/flex-text-to-image"),
        _kie_item("Kie Flux2 Flex I2I (Canonical)", "Image", "flux-2/flex-image-to-image"),
        _kie_item("Kie GPT Image 1.5 T2I", "Image", "gpt-image/1-5-text-to-image"),
        _kie_item("Kie GPT Image 1.5 I2I", "Image", "gpt-image/1-5-image-to-image"),
        _kie_item("Kie Topaz Image Upscale", "Image", "topaz/image-upscale"),
        _kie_item("Kie Recraft Remove BG", "Image", "recraft/remove-background"),
        _kie_item("Kie Recraft Crisp Upscale", "Image", "recraft/crisp-upscale"),
        _kie_item("Kie Ideogram V3 Reframe", "Image", "ideogram/v3-reframe"),
        _kie_item("Kie Ideogram Character", "Image", "ideogram/character"),
        _kie_item("Kie Ideogram Character Edit", "Image", "ideogram/character-edit"),
        _kie_item("Kie Ideogram Character Remix", "Image", "ideogram/character-remix"),

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

        _kie_item("Kie Kling 3.0", "Video", "kling-3.0/video"),
        _kie_item("Kie Kling 2.6 T2V", "Video", "kling-2.6/text-to-video"),
        _kie_item("Kie Kling 2.6 I2V", "Video", "kling-2.6/image-to-video"),
        _kie_item("Kie Kling 2.6 Motion Control", "Video", "kling-2.6/motion-control"),
        _kie_item("Kie Kling 2.5 Turbo T2V Pro", "Video", "kling/v2-5-turbo-text-to-video-pro"),
        _kie_item("Kie Kling 2.5 Turbo I2V Pro", "Video", "kling/v2-5-turbo-image-to-video-pro"),
        _kie_item("Kie Kling V2.1 Pro", "Video", "kling/v2-1-pro"),
        _kie_item("Kie Kling V2.1 Standard", "Video", "kling/v2-1-standard"),
        _kie_item("Kie Kling V2.1 Master T2V", "Video", "kling/v2-1-master-text-to-video"),
        _kie_item("Kie Kling V2.1 Master I2V", "Video", "kling/v2-1-master-image-to-video"),
        _kie_item("Kie Bytedance V1 Pro T2V (Canonical)", "Video", "bytedance/v1-pro-text-to-video"),
        _kie_item("Kie Bytedance V1 Pro I2V (Canonical)", "Video", "bytedance/v1-pro-image-to-video"),
        _kie_item("Kie Bytedance V1 Pro Fast I2V (Canonical)", "Video", "bytedance/v1-pro-fast-image-to-video"),
        _kie_item("Kie Bytedance V1 Lite T2V (Canonical)", "Video", "bytedance/v1-lite-text-to-video"),
        _kie_item("Kie Bytedance V1 Lite I2V (Canonical)", "Video", "bytedance/v1-lite-image-to-video"),
        _kie_item("Kie Hailuo Pro T2V (Canonical)", "Video", "hailuo/02-text-to-video-pro"),
        _kie_item("Kie Hailuo Pro I2V (Canonical)", "Video", "hailuo/02-image-to-video-pro"),
        _kie_item("Kie Hailuo Standard T2V (Canonical)", "Video", "hailuo/02-text-to-video-standard"),
        _kie_item("Kie Hailuo Standard I2V (Canonical)", "Video", "hailuo/02-image-to-video-standard"),
        _kie_item("Kie Hailuo 2.3 Pro I2V", "Video", "hailuo/2-3-image-to-video-pro"),
        _kie_item("Kie Hailuo 2.3 Standard I2V", "Video", "hailuo/2-3-image-to-video-standard"),
        _kie_item("Kie Wan 2.6 T2V (Canonical)", "Video", "wan/2-6-text-to-video"),
        _kie_item("Kie Wan 2.6 I2V (Canonical)", "Video", "wan/2-6-image-to-video"),
        _kie_item("Kie Wan 2.6 V2V (Canonical)", "Video", "wan/2-6-video-to-video"),
        _kie_item("Kie Wan 2.2 A14B T2V Turbo", "Video", "wan/2-2-a14b-text-to-video-turbo"),
        _kie_item("Kie Wan 2.2 A14B I2V Turbo", "Video", "wan/2-2-a14b-image-to-video-turbo"),
        _kie_item("Kie Wan 2.2 A14B Speech2Video", "Video", "wan/2-2-a14b-speech-to-video-turbo"),
        _kie_item("Kie Wan Animate Move", "Video", "wan/2-2-animate-move"),
        _kie_item("Kie Wan Animate Replace", "Video", "wan/2-2-animate-replace"),
        _kie_item("Kie Wan 2.6 Flash I2V", "Video", "wan/2-6-flash-image-to-video"),
        _kie_item("Kie Wan 2.6 Flash V2V", "Video", "wan/2-6-flash-video-to-video"),
        _kie_item("Kie Sora2 T2V (Canonical)", "Video", "sora-2-text-to-video"),
        _kie_item("Kie Sora2 I2V (Canonical)", "Video", "sora-2-image-to-video"),
        _kie_item("Kie Sora2 Pro T2V (Canonical)", "Video", "sora-2-pro-text-to-video"),
        _kie_item("Kie Sora2 Pro I2V (Canonical)", "Video", "sora-2-pro-image-to-video"),
        _kie_item("Kie Sora2 Watermark Remover", "Video", "sora-watermark-remover"),
        _kie_item("Kie Sora2 Pro Storyboard", "Video", "sora-2-pro-storyboard"),
        _kie_item("Kie Sora2 Characters", "Video", "sora-2-characters"),
        _kie_item("Kie Sora2 Characters Pro", "Video", "sora-2-characters-pro"),
        _kie_item("Kie Grok Imagine T2V (Canonical)", "Video", "grok-imagine/text-to-video"),
        _kie_item("Kie Grok Imagine I2V (Canonical)", "Video", "grok-imagine/image-to-video"),
        _kie_item("Kie Topaz Video Upscale", "Video", "topaz/video-upscale"),
        _kie_item("Kie Infinitalk From Audio", "Video", "infinitalk/from-audio"),

        _kie_item("Kie Veo 3.1 Quality", "Video", "veo3"),
        _kie_item("Kie Veo 3.1 Fast", "Video", "veo3_fast"),
        _kie_item("Kie Kling v2.1", "Video", "kling-v2.1"),
        _kie_item("Kie Kling v2.5", "Video", "kling-v2.5"),
        _kie_item("Kie Sora2", "Video", "sora2"),
        _kie_item("Kie Bytedance v1 Pro", "Video", "bytedance-v1-pro"),
        _kie_item("Kie Bytedance v1 Lite", "Video", "bytedance-v1-lite"),
        _kie_item("Kie Hailuo", "Video", "hailuo"),
        _kie_item("Kie Wan Turbo", "Video", "wan-turbo"),
        _kie_item("Kie Grok Imagine Video", "Video", "grok-imagine-video"),

        _kie_item("Kie ElevenLabs", "Tools", "elevenlabs"),
        _kie_item("Kie ElevenLabs Text to Dialogue v3", "Tools", "elevenlabs/text-to-dialogue-v3"),
        _kie_item("Kie ElevenLabs TTS Turbo 2.5", "Tools", "elevenlabs/text-to-speech-turbo-2-5"),
        _kie_item("Kie ElevenLabs TTS Multilingual v2", "Tools", "elevenlabs/text-to-speech-multilingual-v2"),
        _kie_item("Kie ElevenLabs Speech-to-Text", "Tools", "elevenlabs/speech-to-text"),
        _kie_item("Kie ElevenLabs Sound Effect v2", "Tools", "elevenlabs/sound-effect-v2"),
        _kie_item("Kie ElevenLabs Audio Isolation", "Tools", "elevenlabs/audio-isolation"),

        _kie_item("Kie Gemini 2.5 Flash", "LLM", "gemini-2.5-flash"),
        _kie_item("Kie Gemini 2.5 Pro", "LLM", "gemini-2.5-pro"),
        _kie_item("Kie Gemini 3 Pro", "LLM", "gemini-3-pro"),
        _kie_item("Kie GPT-5-2", "LLM", "gpt-5-2"),
        _kie_item("Kie Claude Sonnet 4.5", "LLM", "claude-sonnet-4.5"),
        _kie_item("Kie Claude Opus 4.5", "LLM", "claude-opus-4.5"),
    ]

    # Merge provider aliases by case (e.g. "KIE" -> "kie") before builtin upsert.
    kie_case_rows = db.query(SystemAPISetting).filter(
        _system_provider_case_insensitive_filter("kie")
    ).all()
    for row in kie_case_rows:
        row.provider = "kie"

    kie_pool = _get_system_provider_key_pool(db, "kie")
    if kie_pool:
        _apply_system_provider_key_pool(db, "kie", kie_pool)

    existing = db.query(SystemAPISetting.category, SystemAPISetting.provider, SystemAPISetting.model).filter(
        _system_provider_case_insensitive_filter("kie")
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
        pass

    shared_key = ""
    key_row = db.query(SystemAPISetting.api_key).filter(
        _system_provider_case_insensitive_filter("kie"),
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
            base_model=_derive_base_model_from_model(item["model"]),
            deprecated=False,
            config=item["config"],
            is_active=False,
        ))

    # Keep existing deprecation decisions intact.
    # Built-in sync should only create missing rows, not mutate admin-maintained deprecated flags.

    db.flush()

    # Ensure Vidu built-ins exist as first-class system settings.
    vidu_base_url = "https://api.vidu.studio/open/v1/creation/video"
    vidu_builtins = [
        {
            "name": "Vidu 2.0",
            "category": "Video",
            "provider": "vidu",
            "base_url": vidu_base_url,
            "model": "vidu2.0",
            "config": {"provider_api_key_strategy": "random"},
        },
        {
            "name": "Vidu Q2 Pro",
            "category": "Video",
            "provider": "vidu",
            "base_url": vidu_base_url,
            "model": "viduq2-pro",
            "config": {"provider_api_key_strategy": "random"},
        },
    ]

    existing_vidu = db.query(SystemAPISetting.category, SystemAPISetting.provider, SystemAPISetting.model).filter(
        _system_provider_case_insensitive_filter("vidu")
    ).all()
    existing_vidu_keys = {
        ((c or "").strip().lower(), (p or "").strip().lower(), (m or "").strip().lower())
        for c, p, m in existing_vidu
    }

    vidu_key_row = db.query(SystemAPISetting.api_key).filter(
        _system_provider_case_insensitive_filter("vidu"),
        SystemAPISetting.api_key.isnot(None),
        SystemAPISetting.api_key != "",
    ).order_by(SystemAPISetting.id.desc()).first()
    vidu_shared_key = vidu_key_row[0].strip() if vidu_key_row and (vidu_key_row[0] or "").strip() else ""

    for item in vidu_builtins:
        key = (
            item["category"].strip().lower(),
            item["provider"].strip().lower(),
            item["model"].strip().lower(),
        )
        if key in existing_vidu_keys:
            continue

        db.add(SystemAPISetting(
            name=item["name"],
            category=item["category"],
            provider=item["provider"],
            api_key=vidu_shared_key,
            base_url=item["base_url"],
            model=item["model"],
            base_model=_derive_base_model_from_model(item["model"]),
            deprecated=False,
            config=item["config"],
            is_active=False,
        ))
        existing_vidu_keys.add(key)

    db.flush()

    # Ensure default Vidu has-audio granular billing rules exist.
    vidu_rows = db.query(SystemAPISetting).filter(
        _system_provider_case_insensitive_filter("vidu"),
        SystemAPISetting.category == "Video",
    ).all()

    now_iso = now_bj_iso()
    for row in vidu_rows:
        existing_rule_names = {
            str(rule.name or "").strip().lower()
            for rule in db.query(SystemAPIBillingRule).filter(
                SystemAPIBillingRule.system_api_id == int(row.id)
            ).all()
        }

        specs = [
            {
                "name": "Vidu Sound On",
                "description": "Vidu pricing rule when generated video has audio.",
                "has_audio": True,
                "priority": 20,
            },
            {
                "name": "Vidu Sound Off",
                "description": "Vidu pricing rule when generated video has no audio.",
                "has_audio": False,
                "priority": 19,
            },
        ]

        for spec in specs:
            normalized = str(spec["name"]).strip().lower()
            if normalized in existing_rule_names:
                continue

            db.add(SystemAPIBillingRule(
                system_api_id=int(row.id),
                name=str(spec["name"]),
                description=str(spec["description"]),
                is_active=True,
                priority=int(spec["priority"]),
                applies_to_text=False,
                applies_to_image=False,
                applies_to_video=True,
                has_audio=bool(spec["has_audio"]),
                billing_unit_type="per_second",
                billing_cost=30,
                billing_cost_input=0,
                billing_cost_output=0,
                charge_multiplier=2.0,
                extra_conditions={"provider": "vidu"},
                created_at=now_iso,
                updated_at=now_iso,
            ))

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
        "model": "veo3_fast",
        "config": {
            "endpoint": "https://api.kie.ai/api/v1/jobs/createTask",
            "query_endpoint": "https://api.kie.ai/api/v1/jobs/recordInfo",
            "credits_endpoint": "https://api.kie.ai/api/v1/user/credits",
            "credits_endpoint_v2": "https://api.kie.ai/api/v1/chat/credit",
            "veo_endpoint": "https://api.kie.ai/api/v1/veo/generate",
            "veo_query_endpoint": "https://api.kie.ai/api/v1/veo/record-info"
        }
    }
}

@router.get("/settings", response_model=List[APISettingOut])
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        rows = db.query(APISetting).filter(APISetting.user_id == current_user.id).all()
        result: List[APISettingOut] = []
        for row in rows:
            normalized_strategy = _normalize_user_api_strategy(getattr(row, "api_strategy", None))
            result.append(APISettingOut(
                id=row.id,
                user_id=row.user_id,
                category=row.category,
                system_api_id=_safe_int(getattr(row, "system_api_id", None), None),
                api_strategy=normalized_strategy,
                mode=_normalize_user_mode(getattr(row, "mode", None)),
                config={"api_strategy": normalized_strategy},
            ))
        return result
    except Exception as exc:
        logger.exception("Failed to get settings for user_id=%s: %s", getattr(current_user, "id", None), exc)
        try:
            db.rollback()
        except Exception:
            pass
        return []


@router.get("/settings/preferences", response_model=UserPreferencesOut)
def get_user_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        user_row = db.query(User).filter(User.id == current_user.id).first()
        if not user_row:
            raise HTTPException(status_code=404, detail="User not found")
        normalized = _normalize_user_preferences(getattr(user_row, "preferences", {}) or {})
        return UserPreferencesOut(**normalized)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get user preferences | user_id=%s err=%s", getattr(current_user, "id", None), exc)
        return UserPreferencesOut(**_normalize_user_preferences({}))


@router.put("/settings/preferences", response_model=UserPreferencesOut)
def update_user_preferences(
    payload: UserPreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_row = db.query(User).filter(User.id == current_user.id).first()
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    current_normalized = _normalize_user_preferences(getattr(user_row, "preferences", {}) or {})
    patch = payload.dict(exclude_unset=True)
    merged = _merge_user_preferences(current_normalized, patch)

    user_row.preferences = merged
    db.add(user_row)
    db.commit()
    db.refresh(user_row)
    return UserPreferencesOut(**merged)

@router.post("/settings", response_model=APISettingOut)
def update_setting(
    setting_in: APISettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if we are updating an existing ID
    existing_setting = None
    if setting_in.id:
        existing_setting = db.query(APISetting).filter(
            APISetting.id == setting_in.id,
            APISetting.user_id == current_user.id,
        ).first()
        if not existing_setting:
            raise HTTPException(status_code=404, detail="Setting not found")

    category = _normalize_setting_category_name(
        setting_in.category or (existing_setting.category if existing_setting else None) or "LLM"
    )

    target_system_api_id = _safe_int(getattr(setting_in, "system_api_id", None), None)
    if target_system_api_id is None and existing_setting is not None:
        target_system_api_id = _safe_int(getattr(existing_setting, "system_api_id", None), None)

    if target_system_api_id is not None:
        target_system_row = db.query(SystemAPISetting).filter(SystemAPISetting.id == int(target_system_api_id)).first()
        if not target_system_row:
            raise HTTPException(status_code=404, detail="System API setting not found")
        target_category = _normalize_setting_category_name(getattr(target_system_row, "category", None))
        if target_category != category:
            raise HTTPException(status_code=400, detail="system_api_id category mismatch")

    if setting_in.id:
        db_setting = existing_setting
            
        # Update fields
        # Loop through fields in schema but skip None
        update_data = setting_in.dict(exclude_unset=True)
        for key, value in update_data.items():
            if key != 'id':
                setattr(db_setting, key, value)
                
        # Ensure category is set if missing
        if not db_setting.category:
            db_setting.category = category

        db_setting.category = category
        if hasattr(setting_in, "mode") and setting_in.mode is not None:
            db_setting.mode = _normalize_user_mode(setting_in.mode)
        if hasattr(setting_in, "api_strategy") and setting_in.api_strategy is not None:
            db_setting.api_strategy = _normalize_user_api_strategy(setting_in.api_strategy)
        if hasattr(setting_in, "system_api_id"):
            db_setting.system_api_id = _safe_int(setting_in.system_api_id, None)

        # Merge collision if another row already owns this (user_id, category).
        conflict_row = db.query(APISetting).filter(
            APISetting.user_id == current_user.id,
            APISetting.category == db_setting.category,
            APISetting.id != db_setting.id,
        ).order_by(APISetting.id.desc()).first()
        if conflict_row:
            conflict_row.system_api_id = db_setting.system_api_id
            conflict_row.api_strategy = _normalize_user_api_strategy(getattr(db_setting, "api_strategy", None))
            conflict_row.mode = _normalize_user_mode(db_setting.mode)
            db.delete(db_setting)
            db_setting = conflict_row
            
    else:
        # Create/Upsert by (user_id, category)
        existing_by_category = db.query(APISetting).filter(
            APISetting.user_id == current_user.id,
            APISetting.category == category,
        ).order_by(APISetting.id.desc()).first()

        if existing_by_category:
            existing_by_category.system_api_id = _safe_int(getattr(setting_in, "system_api_id", None), None) if setting_in.system_api_id is not None else existing_by_category.system_api_id
            existing_by_category.api_strategy = _normalize_user_api_strategy(getattr(setting_in, "api_strategy", None), _normalize_user_api_strategy(getattr(existing_by_category, "api_strategy", None))) if setting_in.api_strategy is not None else _normalize_user_api_strategy(getattr(existing_by_category, "api_strategy", None))
            existing_by_category.mode = _normalize_user_mode(getattr(setting_in, "mode", None)) if setting_in.mode is not None else _normalize_user_mode(existing_by_category.mode)
            db_setting = existing_by_category
        else:
            new_setting = APISetting(
                user_id=current_user.id,
                category=category,
                system_api_id=_safe_int(getattr(setting_in, "system_api_id", None), None),
                api_strategy=_normalize_user_api_strategy(getattr(setting_in, "api_strategy", None)),
                mode=_normalize_user_mode(getattr(setting_in, "mode", None)),
            )
            db.add(new_setting)
            db_setting = new_setting

    _cleanup_user_api_settings_records(db, current_user.id)
    _normalize_user_active_settings(db, current_user.id)
    db.flush()
    _keep_only_active_setting_row_for_category(
        db,
        current_user.id,
        str(db_setting.category or category or "LLM"),
        int(db_setting.id or 0),
    )

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
        _ensure_api_settings_binding_columns(db)
        _ensure_settings_system_indexes(db)
        can_view_pricing = bool(getattr(current_user, "is_superuser", False))
        t0 = time.perf_counter()
        t_prev = t0
        visible_categories = ("LLM", "Image", "Video", "Vision")
        def _query_system_settings_rows():
            return db.query(
                SystemAPISetting.id,
                SystemAPISetting.name,
                SystemAPISetting.provider,
                SystemAPISetting.category,
                SystemAPISetting.model,
                SystemAPISetting.base_url,
                SystemAPISetting.api_key,
                SystemAPISetting.deprecated.label("deprecated_flag"),
                SystemAPISetting.tags,
                SystemAPISetting.config,
            ).filter(
                ~SystemAPISetting.category.like("System_%"),
                SystemAPISetting.category.in_(visible_categories),
                or_(SystemAPISetting.deprecated.is_(False), SystemAPISetting.deprecated.is_(None)),
            ).all()

        system_settings = _query_system_settings_rows()
        stale_price_ids = [
            int(getattr(item, "id", 0) or 0)
            for item in system_settings
            if int(getattr(item, "id", 0) or 0) > 0 and _settings_price_cache_is_legacy(getattr(item, "config", None))
        ]
        if stale_price_ids:
            _refresh_settings_price_cache_for_system_apis(db, stale_price_ids)
            _refresh_settings_provider_price_cache_for_system_apis(db, stale_price_ids)
            db.commit()
            system_settings = _query_system_settings_rows()
        t_query_system_settings_ms = int((time.perf_counter() - t_prev) * 1000)
        t_prev = time.perf_counter()

        system_api_ids_for_units = [int(getattr(item, "id", 0) or 0) for item in system_settings if int(getattr(item, "id", 0) or 0) > 0]
        billing_unit_type_by_system_api_id = _batch_system_api_primary_billing_unit_type(db, system_api_ids_for_units)
        t_query_billing_unit_ms = int((time.perf_counter() - t_prev) * 1000)
        t_prev = time.perf_counter()

        user_active_by_category: Dict[str, Dict] = {}
        user_active_rows = db.query(
            APISetting.id,
            APISetting.category,
            APISetting.system_api_id,
            APISetting.mode,
        ).filter(
            APISetting.user_id == current_user.id,
        ).all()
        for row in user_active_rows:
            cat = row.category or "LLM"
            row_data = {
                "id": row.id,
                "category": row.category,
                "system_api_id": _safe_int(getattr(row, "system_api_id", None), None),
                "mode": _normalize_user_mode(getattr(row, "mode", None)),
            }
            if cat not in user_active_by_category or (row.id or 0) > (user_active_by_category[cat].get("id") or 0):
                user_active_by_category[cat] = row_data
        t_query_user_active_ms = int((time.perf_counter() - t_prev) * 1000)
        t_prev = time.perf_counter()

        provider_runtime_key_map, provider_alias_map, provider_pool_row_count = _get_provider_pool_runtime_maps(db)
        t_query_provider_pool_ms = int((time.perf_counter() - t_prev) * 1000)
        t_prev = time.perf_counter()

        grouped: Dict[Tuple[str, str], Dict] = {}
        for item in system_settings:
            provider = item.provider or "unknown"
            category = item.category or "LLM"
            webhook_url, _avg_pricing_from_cfg = _extract_webhook_and_price_cache(getattr(item, "config", None))
            avg_pricing = _read_settings_price_cache_from_row(item) if can_view_pricing else {}
            key = (provider, category)
            if key not in grouped:
                provider_pricing = _read_settings_provider_price_cache_from_row(item) if can_view_pricing else {}
                grouped[key] = {
                    "provider": provider,
                    "provider_alias": provider_alias_map.get(str(provider or "").strip().lower()),
                    "category": category,
                    "shared_key_configured": False,
                    "provider_avg_price_estimate": (int(provider_pricing.get("average_cost") or 0) if can_view_pricing else None),
                    "provider_price_source": (str(provider_pricing.get("source") or "") or None) if can_view_pricing else None,
                    "provider_price_range_min": (int(provider_pricing.get("min_cost") or 0) if can_view_pricing else None),
                    "provider_price_range_max": (int(provider_pricing.get("max_cost") or 0) if can_view_pricing else None),
                    "provider_sample_prices": ([
                        int(v)
                        for v in (provider_pricing.get("sample_prices") or [])
                        if int(v or 0) > 0
                    ] if can_view_pricing else None),
                    "models_map": {},
                }

            provider_key = str(provider or "").strip().lower()
            key_pool_first = provider_runtime_key_map.get(provider_key, "")
            fallback_key = str(item.api_key or "").strip()
            runtime_key = key_pool_first or fallback_key
            has_key = bool(runtime_key)
            grouped[key]["shared_key_configured"] = grouped[key]["shared_key_configured"] or has_key

            user_active = user_active_by_category.get(category)
            user_is_active_for_row = False
            if user_active:
                selected_system_id = _safe_int(user_active.get("system_api_id"), None)
                user_is_active_for_row = bool(selected_system_id and int(item.id or 0) == int(selected_system_id))

            option = SystemAPIModelOption(
                id=item.id,
                name=item.name,
                provider=provider,
                category=category,
                model=item.model,
                modality=getattr(item, "modality", None),
                tags=getattr(item, "tags", None),
                base_url=item.base_url,
                webhook_url=webhook_url,
                deprecated=bool(getattr(item, "deprecated_flag", False)),
                is_active=bool(user_is_active_for_row),
                has_api_key=has_key,
                api_key_masked=_mask_api_key(runtime_key) if has_key else "",
            )

            option.avg_price_estimate = int(avg_pricing.get("average_cost") or 0) if can_view_pricing else None
            option.avg_price_source = (str(avg_pricing.get("source") or "") or None) if can_view_pricing else None
            option.price_range_min = int(avg_pricing.get("min_cost") or 0) if can_view_pricing else None
            option.price_range_max = int(avg_pricing.get("max_cost") or 0) if can_view_pricing else None
            option.sample_prices = [
                int(v)
                for v in (avg_pricing.get("sample_prices") or [])
                if int(v or 0) > 0
            ] if can_view_pricing else None
            option.billing_unit_type = billing_unit_type_by_system_api_id.get(int(item.id or 0))

            if option.deprecated:
                continue

            model_key = str(item.model or "").strip().lower()
            existing_option = grouped[key]["models_map"].get(model_key)
            if existing_option is None or (option.id or 0) >= (existing_option.id or 0):
                grouped[key]["models_map"][model_key] = option
        t_group_build_ms = int((time.perf_counter() - t_prev) * 1000)
        t_prev = time.perf_counter()

        result = []
        for _, row in grouped.items():
            row["models"] = sorted(list(row.get("models_map", {}).values()), key=lambda m: (m.model or "", m.id))
            row.pop("models_map", None)
            if not row["models"]:
                continue
            result.append(SystemAPIProviderSettings(**row))

        t_result_build_ms = int((time.perf_counter() - t_prev) * 1000)
        total_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(
            "settings.system.timing user_id=%s total_ms=%s query_system_ms=%s query_billing_unit_ms=%s query_user_active_ms=%s query_provider_pool_ms=%s group_build_ms=%s result_build_ms=%s system_rows=%s user_rows=%s provider_rows=%s provider_groups=%s result_groups=%s",
            getattr(current_user, "id", None),
            total_ms,
            t_query_system_settings_ms,
            t_query_billing_unit_ms,
            t_query_user_active_ms,
            t_query_provider_pool_ms,
            t_group_build_ms,
            t_result_build_ms,
            len(system_settings),
            len(user_active_rows),
            provider_pool_row_count,
            len(grouped),
            len(result),
        )
        api_logger.info(
            "settings.system.timing user_id=%s total_ms=%s query_system_ms=%s query_billing_unit_ms=%s query_user_active_ms=%s query_provider_pool_ms=%s group_build_ms=%s result_build_ms=%s system_rows=%s user_rows=%s provider_rows=%s provider_groups=%s result_groups=%s",
            getattr(current_user, "id", None),
            total_ms,
            t_query_system_settings_ms,
            t_query_billing_unit_ms,
            t_query_user_active_ms,
            t_query_provider_pool_ms,
            t_group_build_ms,
            t_result_build_ms,
            len(system_settings),
            len(user_active_rows),
            provider_pool_row_count,
            len(grouped),
            len(result),
        )

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

    grouped: Dict[Tuple[str, str], set] = {}

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
    system_setting = db.query(
        SystemAPISetting.id,
        SystemAPISetting.category,
        SystemAPISetting.config,
        SystemAPISetting.deprecated,
    ).filter(
        SystemAPISetting.id == selection.setting_id,
    ).first()
    if not system_setting:
        raise HTTPException(status_code=404, detail="System API setting not found")

    if _is_setting_deprecated(system_setting.config, system_setting.deprecated):
        raise HTTPException(status_code=400, detail="This system API setting is deprecated and cannot be activated")

    _ensure_api_settings_binding_columns(db)
    _cleanup_user_api_settings_records(db, current_user.id)
    _normalize_user_active_settings(db, current_user.id)

    # api_settings is a lightweight per-category preference marker only.
    # Keep a single latest row per category, and store selected system setting id.
    user_setting = db.query(APISetting).filter(
        APISetting.user_id == current_user.id,
        APISetting.category == system_setting.category,
    ).order_by(APISetting.id.desc()).first()

    selection_mode = _normalize_user_mode(getattr(selection, "mode", None))

    if user_setting:
        user_setting.system_api_id = int(system_setting.id)
        user_setting.api_strategy = _normalize_user_api_strategy(getattr(selection, "api_strategy", None), _normalize_user_api_strategy(getattr(user_setting, "api_strategy", None)))
        user_setting.mode = selection_mode
        selected = user_setting
    else:
        selected = APISetting(
            user_id=current_user.id,
            category=system_setting.category,
            system_api_id=int(system_setting.id),
            api_strategy=_normalize_user_api_strategy(getattr(selection, "api_strategy", None)),
            mode=selection_mode,
        )
        db.add(selected)

    db.flush()
    _keep_only_active_setting_row_for_category(
        db,
        current_user.id,
        str(system_setting.category or "LLM"),
        int(selected.id or 0),
    )

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

    rows = _query_system_settings_manage_rows(db)
    return [_setting_to_out(db, row) for row in rows]


@router.get("/settings/system/manage/missing-billing-rules", response_model=List[SystemAPIMissingBillingRuleOut])
def list_system_settings_missing_billing_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    api_rows = _query_system_settings_manage_rows(db)

    billed_api_ids = {
        int(api_id)
        for (api_id,) in db.query(SystemAPIBillingRule.system_api_id).distinct().all()
        if api_id is not None
    }

    out_rows: List[SystemAPIMissingBillingRuleOut] = []
    for row in api_rows:
        if _is_setting_deprecated(row.config, row.deprecated):
            continue
        if not bool(row.is_active):
            continue
        if int(row.id) in billed_api_ids:
            continue
        base_model = _resolve_base_model(getattr(row, "base_model", None), getattr(row, "model", None))
        out_rows.append(
            SystemAPIMissingBillingRuleOut(
                id=int(row.id),
                name=row.name,
                category=str(row.category or ""),
                provider=str(row.provider or ""),
                model=row.model,
                base_model=base_model,
                deprecated=False,
                is_active=bool(row.is_active),
            )
        )

    return out_rows


@router.post("/settings/system/manage/missing-billing-rules", response_model=List[SystemAPIMissingBillingRuleOut])
def list_system_settings_missing_billing_rules_post_compat(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Backward-compatible alias for environments that still call POST.
    return list_system_settings_missing_billing_rules(db=db, current_user=current_user)


@router.get("/settings/system/manage/billing-rules", response_model=Dict[str, List[SystemAPIBillingRuleOut]])
def list_system_api_billing_rules_batch(
    system_api_ids: Optional[str] = Query(default=None, description="Comma-separated system_api_ids"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    if not _require_billing_rules_table(db, allow_missing=True):
        grouped: Dict[str, List[SystemAPIBillingRuleOut]] = {}
        if system_api_ids:
            for token in str(system_api_ids).split(","):
                text = str(token or "").strip()
                if text.isdigit() and int(text) > 0:
                    grouped.setdefault(str(int(text)), [])
        return grouped

    ids: List[int] = []
    if system_api_ids:
        for token in str(system_api_ids).split(","):
            text = str(token or "").strip()
            if not text:
                continue
            try:
                parsed = int(text)
            except Exception:
                continue
            if parsed > 0:
                ids.append(parsed)

    query = db.query(SystemAPIBillingRule)
    if ids:
        query = query.filter(SystemAPIBillingRule.system_api_id.in_(sorted(set(ids))))

    rows = query.order_by(
        SystemAPIBillingRule.system_api_id.asc(),
        SystemAPIBillingRule.is_active.desc(),
        SystemAPIBillingRule.priority.desc(),
        SystemAPIBillingRule.id.desc(),
    ).all()

    touched_ids = sorted(set(ids)) if ids else sorted({int(getattr(row, "system_api_id", 0) or 0) for row in rows if int(getattr(row, "system_api_id", 0) or 0) > 0})
    if touched_ids:
        changed_model = _refresh_settings_price_cache_for_system_apis(db, touched_ids)
        changed_provider = _refresh_settings_provider_price_cache_for_system_apis(db, touched_ids)
        if changed_model or changed_provider:
            db.commit()

    grouped: Dict[str, List[SystemAPIBillingRuleOut]] = {}
    for row in rows:
        sid = str(int(row.system_api_id))
        grouped.setdefault(sid, []).append(_rule_to_out(row))

    if ids:
        for sid in sorted(set(ids)):
            grouped.setdefault(str(sid), [])

    return grouped


@router.post("/settings/system/manage/price-cache/recompute")
def recompute_system_api_price_cache_manage(
    system_api_ids: Optional[str] = Query(default=None, description="Comma-separated system_api_ids"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    ids: List[int] = []
    if system_api_ids:
        for token in str(system_api_ids).split(","):
            text_token = str(token or "").strip()
            if not text_token:
                continue
            try:
                parsed = int(text_token)
            except Exception:
                continue
            if parsed > 0:
                ids.append(parsed)

    target_ids = sorted(set(ids))
    if not target_ids:
        target_ids = [
            int(row_id)
            for row_id, in db.query(SystemAPISetting.id).filter(
                ~SystemAPISetting.category.like("System_%"),
            ).all()
            if int(row_id or 0) > 0
        ]

    if not target_ids:
        return {
            "ok": True,
            "target_count": 0,
            "changed_model": 0,
            "changed_provider": 0,
            "changed_total": 0,
        }

    changed_model = _refresh_settings_price_cache_for_system_apis(db, target_ids)
    changed_provider = _refresh_settings_provider_price_cache_for_system_apis(db, target_ids)
    if changed_model or changed_provider:
        db.commit()

    return {
        "ok": True,
        "target_count": len(target_ids),
        "changed_model": int(changed_model or 0),
        "changed_provider": int(changed_provider or 0),
        "changed_total": int(changed_model or 0) + int(changed_provider or 0),
    }


@router.get("/settings/system/manage/kie-standard-values", response_model=List[KIEDataStandardValueOut])
def list_kie_standard_values_manage(
    standard_dimension: Optional[str] = Query(default=None),
    active_only: bool = Query(default=True),
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    _ensure_kie_standard_tables_for_admin(db)

    where = ["1=1"]
    params: Dict[str, Any] = {"limit": int(limit)}
    if standard_dimension:
        where.append("upper(standard_dimension) = upper(:standard_dimension)")
        params["standard_dimension"] = str(standard_dimension).strip()
    if active_only:
        where.append("coalesce(is_active, 1) = 1")

    rows = db.execute(text(f"""
        SELECT id, standard_dimension, standard_value, value_type, definition, alias_values, is_active, created_at, updated_at
        FROM kie_system_data_standard_values
        WHERE {' AND '.join(where)}
        ORDER BY standard_dimension ASC, standard_value ASC, id ASC
        LIMIT :limit
    """), params).mappings().all()
    return [_row_to_kie_standard_value_out(dict(row)) for row in rows]


@router.get("/settings/system/manage/kie-standard-values/export", response_model=KIEDataStandardValueExportResponse)
@router.get("/kie/data-dictionary/values/export", response_model=KIEDataStandardValueExportResponse)
def export_kie_standard_values_manage(
    standard_dimension: Optional[str] = Query(default=None),
    active_only: bool = Query(default=False),
    include_csv: bool = Query(default=True),
    limit: int = Query(default=10000, ge=1, le=50000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    _ensure_kie_standard_tables_for_admin(db)

    where = ["1=1"]
    params: Dict[str, Any] = {"limit": int(limit)}
    if standard_dimension:
        where.append("upper(standard_dimension) = upper(:standard_dimension)")
        params["standard_dimension"] = str(standard_dimension).strip()
    if active_only:
        where.append("coalesce(is_active, 1) = 1")

    rows = db.execute(text(f"""
        SELECT id, standard_dimension, standard_value, value_type, definition, alias_values, is_active, created_at, updated_at
        FROM kie_system_data_standard_values
        WHERE {' AND '.join(where)}
        ORDER BY standard_dimension ASC, standard_value ASC, id ASC
        LIMIT :limit
    """), params).mappings().all()

    items = [_row_to_kie_standard_value_out(dict(row)) for row in rows]
    csv_text: Optional[str] = None
    if include_csv:
        csv_headers = [
            "id", "standard_dimension", "standard_value", "value_type", "definition", "alias_values", "is_active", "created_at", "updated_at",
        ]
        sio = io.StringIO()
        writer = csv.DictWriter(sio, fieldnames=csv_headers)
        writer.writeheader()
        for item in items:
            payload = item.model_dump() if hasattr(item, "model_dump") else item.dict()
            writer.writerow({k: payload.get(k) for k in csv_headers})
        csv_text = sio.getvalue()

    return KIEDataStandardValueExportResponse(
        total=len(items),
        items=items,
        csv=csv_text,
    )


@router.post("/settings/system/manage/kie-standard-values/import", response_model=KIEDataStandardValueImportResponse)
@router.post("/kie/data-dictionary/values/import", response_model=KIEDataStandardValueImportResponse)
def import_kie_standard_values_manage(
    payload: KIEDataStandardValueImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    _ensure_kie_standard_tables_for_admin(db)

    items = payload.items or []
    received = len(items)
    created = 0
    updated = 0
    skipped = 0

    # Dictionary import is clear-import mode by design.
    clear_import = True
    if clear_import:
        db.execute(text("DELETE FROM kie_system_data_standard_values"))

    for item in items:
        values = item.model_dump() if hasattr(item, "model_dump") else item.dict()
        standard_dimension_value = str(values.get("standard_dimension") or "").strip().upper()
        standard_value_value = str(values.get("standard_value") or "").strip()
        if not standard_dimension_value or not standard_value_value:
            skipped += 1
            continue

        value_type_value = str(values.get("value_type") or "enum").strip() or "enum"
        definition_value = str(values.get("definition") or "").strip() or None
        alias_values_value = str(values.get("alias_values") or "").strip() or None
        is_active_value = 1 if _to_bool(values.get("is_active")) else 0
        now_iso = now_bj_iso()

        if payload.upsert_by_natural_key:
            existing = db.execute(text("""
                SELECT id
                FROM kie_system_data_standard_values
                WHERE standard_dimension = :standard_dimension
                  AND standard_value = :standard_value
                ORDER BY id DESC
                LIMIT 1
            """), {
                "standard_dimension": standard_dimension_value,
                "standard_value": standard_value_value,
            }).mappings().first()

            if existing:
                db.execute(text("""
                    UPDATE kie_system_data_standard_values
                    SET value_type = :value_type,
                        definition = :definition,
                        alias_values = :alias_values,
                        is_active = :is_active,
                        updated_at = :updated_at
                    WHERE id = :id
                """), {
                    "id": int(existing.get("id") or 0),
                    "value_type": value_type_value,
                    "definition": definition_value,
                    "alias_values": alias_values_value,
                    "is_active": is_active_value,
                    "updated_at": now_iso,
                })
                updated += 1
                continue

        db.execute(text("""
            INSERT INTO kie_system_data_standard_values (
                standard_dimension, standard_value, value_type, definition,
                alias_values, is_active, created_at, updated_at
            ) VALUES (
                :standard_dimension, :standard_value, :value_type, :definition,
                :alias_values, :is_active, :created_at, :updated_at
            )
        """), {
            "standard_dimension": standard_dimension_value,
            "standard_value": standard_value_value,
            "value_type": value_type_value,
            "definition": definition_value,
            "alias_values": alias_values_value,
            "is_active": is_active_value,
            "created_at": now_iso,
            "updated_at": now_iso,
        })
        created += 1

    db.commit()
    return KIEDataStandardValueImportResponse(
        ok=True,
        received=received,
        created=created,
        updated=updated,
        skipped=skipped,
    )


@router.get("/settings/system/kie-standard-values/options", response_model=Dict[str, List[str]])
def get_kie_standard_value_options(
    dimensions: Optional[str] = Query(default="type,language,base_positioning,aspect_ratio,image_size"),
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Any authenticated user can read dictionary options used by project-creation forms.
    _ = current_user
    _ensure_kie_standard_tables_for_admin(db)

    raw_dimensions = [str(x or "").strip() for x in str(dimensions or "").split(",")]
    target_dimensions = [x for x in raw_dimensions if x]
    if not target_dimensions:
        target_dimensions = ["type", "language", "base_positioning", "aspect_ratio", "image_size"]

    where = ["1=1"]
    params: Dict[str, Any] = {}
    if active_only:
        where.append("coalesce(is_active, 1) = 1")

    dim_placeholders: List[str] = []
    for idx, dim in enumerate(target_dimensions):
        key = f"dim_{idx}"
        dim_placeholders.append(f":{key}")
        params[key] = dim
    where.append(f"standard_dimension IN ({', '.join(dim_placeholders)})")

    rows = db.execute(text(f"""
        SELECT standard_dimension, standard_value
        FROM kie_system_data_standard_values
        WHERE {' AND '.join(where)}
        ORDER BY standard_dimension ASC, standard_value ASC, id ASC
    """), params).mappings().all()

    grouped: Dict[str, List[str]] = {dim: [] for dim in target_dimensions}
    seen: Dict[str, set] = {dim: set() for dim in target_dimensions}

    for row in rows:
        dim = str(row.get("standard_dimension") or "").strip()
        val = str(row.get("standard_value") or "").strip()
        if not dim or not val or dim not in grouped:
            continue
        if val in seen[dim]:
            continue
        seen[dim].add(val)
        grouped[dim].append(val)

    return grouped


@router.get("/settings/system/manage/kie-standard-mappings", response_model=List[KIEDataStandardMappingOut])
def list_kie_standard_mappings_manage(
    provider: Optional[str] = Query(default="kie"),
    standard_dimension: Optional[str] = Query(default=None),
    model_key_inferred: Optional[str] = Query(default=None),
    source_field: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    active_only: bool = Query(default=False),
    billing_related_only: bool = Query(default=False),
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    _ensure_kie_standard_tables_for_admin(db)

    where = ["1=1"]
    params: Dict[str, Any] = {"limit": int(limit)}

    if provider is not None and str(provider).strip():
        where.append("lower(coalesce(provider, '')) = lower(:provider)")
        params["provider"] = str(provider).strip()
    if standard_dimension:
        where.append("upper(standard_dimension) = upper(:standard_dimension)")
        params["standard_dimension"] = str(standard_dimension).strip()
    if model_key_inferred:
        where.append("lower(coalesce(model_key_inferred, '')) = lower(:model_key_inferred)")
        params["model_key_inferred"] = str(model_key_inferred).strip()
    if source_field:
        where.append("lower(coalesce(source_field, '')) = lower(:source_field)")
        params["source_field"] = str(source_field).strip()
    if q:
        where.append("(" 
                     "lower(coalesce(model_key_inferred, '')) LIKE :q OR "
                     "lower(coalesce(model_title, '')) LIKE :q OR "
                     "lower(coalesce(source_field, '')) LIKE :q OR "
                     "lower(coalesce(source_enum_value, '')) LIKE :q OR "
                     "lower(coalesce(standard_dimension, '')) LIKE :q OR "
                     "lower(coalesce(standard_value, '')) LIKE :q"
                     ")")
        params["q"] = f"%{str(q).strip().lower()}%"
    if active_only:
        where.append("coalesce(is_active, 1) = 1")
    if billing_related_only:
        where.append("coalesce(is_billing_related, 0) = 1")

    rows = db.execute(text(f"""
        SELECT id, provider, model_key_inferred, model_title, model_url,
               source_field, source_enum_value, standard_dimension, standard_value,
               confidence, note, is_active, is_billing_related, created_at, updated_at
        FROM kie_system_data_standard_mappings
        WHERE {' AND '.join(where)}
        ORDER BY standard_dimension ASC, model_key_inferred ASC, source_field ASC, source_enum_value ASC, id ASC
        LIMIT :limit
    """), params).mappings().all()
    return [_row_to_kie_mapping_out(dict(row)) for row in rows]


@router.get("/settings/system/manage/kie-standard-mappings/export", response_model=KIEDataStandardMappingExportResponse)
@router.get("/kie/data-dictionary/mappings/export", response_model=KIEDataStandardMappingExportResponse)
def export_kie_standard_mappings_manage(
    provider: Optional[str] = Query(default="kie"),
    standard_dimension: Optional[str] = Query(default=None),
    model_key_inferred: Optional[str] = Query(default=None),
    source_field: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    active_only: bool = Query(default=False),
    billing_related_only: bool = Query(default=False),
    include_csv: bool = Query(default=True),
    limit: int = Query(default=10000, ge=1, le=50000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    _ensure_kie_standard_tables_for_admin(db)

    where = ["1=1"]
    params: Dict[str, Any] = {"limit": int(limit)}

    if provider is not None and str(provider).strip():
        where.append("lower(coalesce(provider, '')) = lower(:provider)")
        params["provider"] = str(provider).strip()
    if standard_dimension:
        where.append("upper(standard_dimension) = upper(:standard_dimension)")
        params["standard_dimension"] = str(standard_dimension).strip()
    if model_key_inferred:
        where.append("lower(coalesce(model_key_inferred, '')) = lower(:model_key_inferred)")
        params["model_key_inferred"] = str(model_key_inferred).strip()
    if source_field:
        where.append("lower(coalesce(source_field, '')) = lower(:source_field)")
        params["source_field"] = str(source_field).strip()
    if q:
        where.append("(" 
                     "lower(coalesce(model_key_inferred, '')) LIKE :q OR "
                     "lower(coalesce(model_title, '')) LIKE :q OR "
                     "lower(coalesce(source_field, '')) LIKE :q OR "
                     "lower(coalesce(source_enum_value, '')) LIKE :q OR "
                     "lower(coalesce(standard_dimension, '')) LIKE :q OR "
                     "lower(coalesce(standard_value, '')) LIKE :q"
                     ")")
        params["q"] = f"%{str(q).strip().lower()}%"
    if active_only:
        where.append("coalesce(is_active, 1) = 1")
    if billing_related_only:
        where.append("coalesce(is_billing_related, 0) = 1")

    rows = db.execute(text(f"""
        SELECT id, provider, model_key_inferred, model_title, model_url,
               source_field, source_enum_value, standard_dimension, standard_value,
               confidence, note, is_active, is_billing_related, created_at, updated_at
        FROM kie_system_data_standard_mappings
        WHERE {' AND '.join(where)}
        ORDER BY standard_dimension ASC, model_key_inferred ASC, source_field ASC, source_enum_value ASC, id ASC
        LIMIT :limit
    """), params).mappings().all()

    items = [_row_to_kie_mapping_out(dict(row)) for row in rows]
    csv_text: Optional[str] = None
    if include_csv:
        csv_headers = [
            "id", "provider", "model_key_inferred", "model_title", "model_url",
            "source_field", "source_enum_value", "standard_dimension", "standard_value",
            "confidence", "note", "is_active", "is_billing_related", "created_at", "updated_at",
        ]
        sio = io.StringIO()
        writer = csv.DictWriter(sio, fieldnames=csv_headers)
        writer.writeheader()
        for item in items:
            payload = item.model_dump() if hasattr(item, "model_dump") else item.dict()
            writer.writerow({k: payload.get(k) for k in csv_headers})
        csv_text = sio.getvalue()

    return KIEDataStandardMappingExportResponse(
        provider=str(provider or "kie").strip() or "kie",
        total=len(items),
        items=items,
        csv=csv_text,
    )


@router.post("/settings/system/manage/kie-standard-mappings/import", response_model=KIEDataStandardMappingImportResponse)
@router.post("/kie/data-dictionary/mappings/import", response_model=KIEDataStandardMappingImportResponse)
def import_kie_standard_mappings_manage(
    payload: KIEDataStandardMappingImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    _ensure_kie_standard_tables_for_admin(db)

    items = payload.items or []
    received = len(items)
    created = 0
    updated = 0
    skipped = 0

    # KIE mapping feature import is designed as clear-import mode.
    clear_import = True
    if clear_import:
        providers_to_clear = {"kie"}
        for item in items:
            provider_value = str(getattr(item, "provider", "kie") or "kie").strip() or "kie"
            providers_to_clear.add(provider_value)
        for provider_value in providers_to_clear:
            db.execute(
                text("DELETE FROM kie_system_data_standard_mappings WHERE lower(coalesce(provider, '')) = lower(:provider)"),
                {"provider": provider_value},
            )

    for item in items:
        values = item.model_dump() if hasattr(item, "model_dump") else item.dict()

        provider_value = str(values.get("provider") or "kie").strip() or "kie"
        model_key_value = str(values.get("model_key_inferred") or "").strip() or None
        source_field_value = str(values.get("source_field") or "").strip()
        source_enum_value_value = str(values.get("source_enum_value") or "").strip()
        standard_dimension_value = str(values.get("standard_dimension") or "").strip().upper()
        standard_value_value = str(values.get("standard_value") or "").strip()

        if not source_field_value or not source_enum_value_value or not standard_dimension_value or not standard_value_value:
            skipped += 1
            continue

        _validate_kie_mapping_source_enum_allowed(
            provider=provider_value,
            model_key_inferred=model_key_value,
            source_field=source_field_value,
            source_enum_value=source_enum_value_value,
        )

        now_iso = now_bj_iso()
        if payload.upsert_by_natural_key:
            existing = db.execute(text("""
                SELECT id
                FROM kie_system_data_standard_mappings
                WHERE lower(coalesce(provider, '')) = lower(:provider)
                  AND coalesce(model_key_inferred, '') = coalesce(:model_key_inferred, '')
                  AND source_field = :source_field
                  AND source_enum_value = :source_enum_value
                  AND standard_dimension = :standard_dimension
                  AND standard_value = :standard_value
                ORDER BY id DESC
                LIMIT 1
            """), {
                "provider": provider_value,
                "model_key_inferred": model_key_value,
                "source_field": source_field_value,
                "source_enum_value": source_enum_value_value,
                "standard_dimension": standard_dimension_value,
                "standard_value": standard_value_value,
            }).mappings().first()

            if existing:
                db.execute(text("""
                    UPDATE kie_system_data_standard_mappings
                    SET model_title = :model_title,
                        model_url = :model_url,
                        confidence = :confidence,
                        note = :note,
                        is_active = :is_active,
                        is_billing_related = :is_billing_related,
                        updated_at = :updated_at
                    WHERE id = :id
                """), {
                    "id": int(existing.get("id") or 0),
                    "model_title": values.get("model_title"),
                    "model_url": values.get("model_url"),
                    "confidence": values.get("confidence"),
                    "note": values.get("note"),
                    "is_active": 1 if _to_bool(values.get("is_active")) else 0,
                    "is_billing_related": 1 if _to_bool(values.get("is_billing_related")) else 0,
                    "updated_at": now_iso,
                })
                updated += 1
                continue

        db.execute(text("""
            INSERT INTO kie_system_data_standard_mappings (
                provider, model_key_inferred, model_title, model_url,
                source_field, source_enum_value, standard_dimension, standard_value,
                confidence, note, is_active, is_billing_related, created_at, updated_at
            ) VALUES (
                :provider, :model_key_inferred, :model_title, :model_url,
                :source_field, :source_enum_value, :standard_dimension, :standard_value,
                :confidence, :note, :is_active, :is_billing_related, :created_at, :updated_at
            )
        """), {
            "provider": provider_value,
            "model_key_inferred": model_key_value,
            "model_title": values.get("model_title"),
            "model_url": values.get("model_url"),
            "source_field": source_field_value,
            "source_enum_value": source_enum_value_value,
            "standard_dimension": standard_dimension_value,
            "standard_value": standard_value_value,
            "confidence": values.get("confidence"),
            "note": values.get("note"),
            "is_active": 1 if _to_bool(values.get("is_active")) else 0,
            "is_billing_related": 1 if _to_bool(values.get("is_billing_related")) else 0,
            "created_at": now_iso,
            "updated_at": now_iso,
        })
        created += 1

    db.commit()
    return KIEDataStandardMappingImportResponse(
        ok=True,
        received=received,
        created=created,
        updated=updated,
        skipped=skipped,
    )


@router.get("/settings/system/manage/kie-data-dictionary/export", response_model=KIEDataDictionaryBundleExportResponse)
@router.get("/kie/data-dictionary/bundle/export", response_model=KIEDataDictionaryBundleExportResponse)
def export_kie_data_dictionary_bundle_manage(
    include_csv: bool = Query(default=True),
    values_limit: int = Query(default=10000, ge=1, le=50000),
    mappings_limit: int = Query(default=10000, ge=1, le=50000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    _ensure_kie_standard_tables_for_admin(db)

    value_rows = db.execute(text("""
        SELECT id, standard_dimension, standard_value, value_type, definition, alias_values, is_active, created_at, updated_at
        FROM kie_system_data_standard_values
        ORDER BY standard_dimension ASC, standard_value ASC, id ASC
        LIMIT :limit
    """), {"limit": int(values_limit)}).mappings().all()
    mapping_rows = db.execute(text("""
        SELECT id, provider, model_key_inferred, model_title, model_url,
               source_field, source_enum_value, standard_dimension, standard_value,
               confidence, note, is_active, is_billing_related, created_at, updated_at
        FROM kie_system_data_standard_mappings
        ORDER BY standard_dimension ASC, model_key_inferred ASC, source_field ASC, source_enum_value ASC, id ASC
        LIMIT :limit
    """), {"limit": int(mappings_limit)}).mappings().all()

    values = [_row_to_kie_standard_value_out(dict(row)) for row in value_rows]
    mappings = [_row_to_kie_mapping_out(dict(row)) for row in mapping_rows]

    values_csv: Optional[str] = None
    mappings_csv: Optional[str] = None
    if include_csv:
        value_headers = ["id", "standard_dimension", "standard_value", "value_type", "definition", "alias_values", "is_active", "created_at", "updated_at"]
        sio_values = io.StringIO()
        writer_values = csv.DictWriter(sio_values, fieldnames=value_headers)
        writer_values.writeheader()
        for item in values:
            payload = item.model_dump() if hasattr(item, "model_dump") else item.dict()
            writer_values.writerow({k: payload.get(k) for k in value_headers})
        values_csv = sio_values.getvalue()

        mapping_headers = [
            "id", "provider", "model_key_inferred", "model_title", "model_url",
            "source_field", "source_enum_value", "standard_dimension", "standard_value",
            "confidence", "note", "is_active", "is_billing_related", "created_at", "updated_at",
        ]
        sio_mappings = io.StringIO()
        writer_mappings = csv.DictWriter(sio_mappings, fieldnames=mapping_headers)
        writer_mappings.writeheader()
        for item in mappings:
            payload = item.model_dump() if hasattr(item, "model_dump") else item.dict()
            writer_mappings.writerow({k: payload.get(k) for k in mapping_headers})
        mappings_csv = sio_mappings.getvalue()

    return KIEDataDictionaryBundleExportResponse(
        total_values=len(values),
        total_mappings=len(mappings),
        values=values,
        mappings=mappings,
        values_csv=values_csv,
        mappings_csv=mappings_csv,
    )


@router.post("/settings/system/manage/kie-data-dictionary/import", response_model=KIEDataDictionaryBundleImportResponse)
@router.post("/kie/data-dictionary/bundle/import", response_model=KIEDataDictionaryBundleImportResponse)
def import_kie_data_dictionary_bundle_manage(
    payload: KIEDataDictionaryBundleImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    _ensure_kie_standard_tables_for_admin(db)

    values = payload.values or []
    mappings = payload.mappings or []
    received_values = len(values)
    received_mappings = len(mappings)
    created_values = 0
    skipped_values = 0
    created_mappings = 0
    skipped_mappings = 0

    # Bundle import is always clear-import mode to keep dictionary and mapping fully aligned.
    clear_import = True
    if clear_import:
        db.execute(text("DELETE FROM kie_system_data_standard_mappings"))
        db.execute(text("DELETE FROM kie_system_data_standard_values"))

    for item in values:
        row = item.model_dump() if hasattr(item, "model_dump") else item.dict()
        standard_dimension = str(row.get("standard_dimension") or "").strip().upper()
        standard_value = str(row.get("standard_value") or "").strip()
        if not standard_dimension or not standard_value:
            skipped_values += 1
            continue
        now_iso = now_bj_iso()
        db.execute(text("""
            INSERT INTO kie_system_data_standard_values (
                standard_dimension, standard_value, value_type, definition,
                alias_values, is_active, created_at, updated_at
            ) VALUES (
                :standard_dimension, :standard_value, :value_type, :definition,
                :alias_values, :is_active, :created_at, :updated_at
            )
        """), {
            "standard_dimension": standard_dimension,
            "standard_value": standard_value,
            "value_type": str(row.get("value_type") or "enum").strip() or "enum",
            "definition": str(row.get("definition") or "").strip() or None,
            "alias_values": str(row.get("alias_values") or "").strip() or None,
            "is_active": 1 if _to_bool(row.get("is_active")) else 0,
            "created_at": now_iso,
            "updated_at": now_iso,
        })
        created_values += 1

    for item in mappings:
        row = item.model_dump() if hasattr(item, "model_dump") else item.dict()
        provider_value = str(row.get("provider") or "kie").strip() or "kie"
        model_key_value = str(row.get("model_key_inferred") or "").strip() or None
        source_field_value = str(row.get("source_field") or "").strip()
        source_enum_value_value = str(row.get("source_enum_value") or "").strip()
        standard_dimension_value = str(row.get("standard_dimension") or "").strip().upper()
        standard_value_value = str(row.get("standard_value") or "").strip()

        if not source_field_value or not source_enum_value_value or not standard_dimension_value or not standard_value_value:
            skipped_mappings += 1
            continue

        try:
            _validate_kie_mapping_source_enum_allowed(
                provider=provider_value,
                model_key_inferred=model_key_value,
                source_field=source_field_value,
                source_enum_value=source_enum_value_value,
            )
        except HTTPException:
            if payload.strict_mapping_validation:
                raise
            skipped_mappings += 1
            continue

        now_iso = now_bj_iso()
        db.execute(text("""
            INSERT INTO kie_system_data_standard_mappings (
                provider, model_key_inferred, model_title, model_url,
                source_field, source_enum_value, standard_dimension, standard_value,
                confidence, note, is_active, is_billing_related, created_at, updated_at
            ) VALUES (
                :provider, :model_key_inferred, :model_title, :model_url,
                :source_field, :source_enum_value, :standard_dimension, :standard_value,
                :confidence, :note, :is_active, :is_billing_related, :created_at, :updated_at
            )
        """), {
            "provider": provider_value,
            "model_key_inferred": model_key_value,
            "model_title": str(row.get("model_title") or "").strip() or None,
            "model_url": str(row.get("model_url") or "").strip() or None,
            "source_field": source_field_value,
            "source_enum_value": source_enum_value_value,
            "standard_dimension": standard_dimension_value,
            "standard_value": standard_value_value,
            "confidence": str(row.get("confidence") or "").strip() or None,
            "note": str(row.get("note") or "").strip() or None,
            "is_active": 1 if _to_bool(row.get("is_active")) else 0,
            "is_billing_related": 1 if _to_bool(row.get("is_billing_related")) else 0,
            "created_at": now_iso,
            "updated_at": now_iso,
        })
        created_mappings += 1

    db.commit()
    return KIEDataDictionaryBundleImportResponse(
        ok=True,
        received_values=received_values,
        created_values=created_values,
        skipped_values=skipped_values,
        received_mappings=received_mappings,
        created_mappings=created_mappings,
        skipped_mappings=skipped_mappings,
    )


@router.post("/settings/system/manage/kie-standard-mappings", response_model=KIEDataStandardMappingOut)
def create_kie_standard_mapping_manage(
    payload: KIEDataStandardMappingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    _ensure_kie_standard_tables_for_admin(db)

    values = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    _validate_kie_mapping_source_enum_allowed(
        provider=values.get("provider") or "kie",
        model_key_inferred=values.get("model_key_inferred"),
        source_field=values.get("source_field"),
        source_enum_value=values.get("source_enum_value"),
    )
    now_iso = now_bj_iso()
    db.execute(text("""
        INSERT INTO kie_system_data_standard_mappings (
            provider, model_key_inferred, model_title, model_url,
            source_field, source_enum_value, standard_dimension, standard_value,
            confidence, note, is_active, is_billing_related, created_at, updated_at
        ) VALUES (
            :provider, :model_key_inferred, :model_title, :model_url,
            :source_field, :source_enum_value, :standard_dimension, :standard_value,
            :confidence, :note, :is_active, :is_billing_related, :created_at, :updated_at
        )
    """), {
        "provider": str(values.get("provider") or "kie").strip() or "kie",
        "model_key_inferred": str(values.get("model_key_inferred") or "").strip() or None,
        "model_title": values.get("model_title"),
        "model_url": values.get("model_url"),
        "source_field": str(values.get("source_field") or "").strip(),
        "source_enum_value": str(values.get("source_enum_value") or "").strip(),
        "standard_dimension": str(values.get("standard_dimension") or "").strip().upper(),
        "standard_value": str(values.get("standard_value") or "").strip(),
        "confidence": values.get("confidence"),
        "note": values.get("note"),
        "is_active": 1 if _to_bool(values.get("is_active")) else 0,
        "is_billing_related": 1 if _to_bool(values.get("is_billing_related")) else 0,
        "created_at": now_iso,
        "updated_at": now_iso,
    })

    row = db.execute(text("""
        SELECT id, provider, model_key_inferred, model_title, model_url,
               source_field, source_enum_value, standard_dimension, standard_value,
               confidence, note, is_active, is_billing_related, created_at, updated_at
        FROM kie_system_data_standard_mappings
        WHERE provider = :provider
          AND coalesce(model_key_inferred, '') = coalesce(:model_key_inferred, '')
          AND source_field = :source_field
          AND source_enum_value = :source_enum_value
          AND standard_dimension = :standard_dimension
          AND standard_value = :standard_value
        ORDER BY id DESC
        LIMIT 1
    """), {
        "provider": str(values.get("provider") or "kie").strip() or "kie",
        "model_key_inferred": str(values.get("model_key_inferred") or "").strip() or None,
        "source_field": str(values.get("source_field") or "").strip(),
        "source_enum_value": str(values.get("source_enum_value") or "").strip(),
        "standard_dimension": str(values.get("standard_dimension") or "").strip().upper(),
        "standard_value": str(values.get("standard_value") or "").strip(),
    }).mappings().first()

    db.commit()
    if not row:
        raise HTTPException(status_code=500, detail="Failed to create mapping")
    return _row_to_kie_mapping_out(dict(row))


@router.post("/settings/system/manage/kie-standard-mappings/{mapping_id:int}", response_model=KIEDataStandardMappingOut)
def update_kie_standard_mapping_manage(
    mapping_id: int,
    payload: KIEDataStandardMappingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    _ensure_kie_standard_tables_for_admin(db)
    existing_row = db.execute(text("""
        SELECT id, provider, model_key_inferred, source_field, source_enum_value
        FROM kie_system_data_standard_mappings
        WHERE id = :id
        LIMIT 1
    """), {"id": int(mapping_id)}).mappings().first()
    existing = dict(existing_row) if existing_row else None
    if not existing:
        raise HTTPException(status_code=404, detail="KIE mapping not found")

    patch = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    if not patch:
        row = db.execute(text("""
            SELECT id, provider, model_key_inferred, model_title, model_url,
                   source_field, source_enum_value, standard_dimension, standard_value,
                   confidence, note, is_active, is_billing_related, created_at, updated_at
            FROM kie_system_data_standard_mappings
            WHERE id = :id
            LIMIT 1
        """), {"id": int(mapping_id)}).mappings().first()
        return _row_to_kie_mapping_out(dict(row))

    allowed = {
        "provider", "model_key_inferred", "model_title", "model_url",
        "source_field", "source_enum_value", "standard_dimension", "standard_value",
        "confidence", "note", "is_active", "is_billing_related",
    }
    assignments = []
    params: Dict[str, Any] = {"id": int(mapping_id), "updated_at": now_bj_iso()}
    for key, value in patch.items():
        if key not in allowed:
            continue
        if key == "standard_dimension" and value is not None:
            value = str(value).strip().upper()
        elif key in {"provider", "source_field", "source_enum_value"} and value is not None:
            value = str(value).strip()
        elif key == "model_key_inferred" and value is not None:
            value = str(value).strip() or None
        elif key in {"is_active", "is_billing_related"}:
            value = 1 if _to_bool(value) else 0
        assignments.append(f"{key} = :{key}")
        params[key] = value

    effective_provider = params.get("provider", existing.get("provider"))
    effective_model_key = params.get("model_key_inferred", existing.get("model_key_inferred"))
    effective_source_field = params.get("source_field", existing.get("source_field"))
    effective_source_enum_value = params.get("source_enum_value", existing.get("source_enum_value"))
    _validate_kie_mapping_source_enum_allowed(
        provider=effective_provider,
        model_key_inferred=effective_model_key,
        source_field=effective_source_field,
        source_enum_value=effective_source_enum_value,
    )

    if assignments:
        assignments.append("updated_at = :updated_at")
        db.execute(text(f"UPDATE kie_system_data_standard_mappings SET {', '.join(assignments)} WHERE id = :id"), params)

    row = db.execute(text("""
        SELECT id, provider, model_key_inferred, model_title, model_url,
               source_field, source_enum_value, standard_dimension, standard_value,
               confidence, note, is_active, is_billing_related, created_at, updated_at
        FROM kie_system_data_standard_mappings
        WHERE id = :id
        LIMIT 1
    """), {"id": int(mapping_id)}).mappings().first()

    db.commit()
    return _row_to_kie_mapping_out(dict(row))


@router.delete("/settings/system/manage/kie-standard-mappings/{mapping_id:int}")
def delete_kie_standard_mapping_manage(
    mapping_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    _ensure_kie_standard_tables_for_admin(db)
    result = db.execute(text("DELETE FROM kie_system_data_standard_mappings WHERE id = :id"), {"id": int(mapping_id)})
    db.commit()
    if int(result.rowcount or 0) <= 0:
        raise HTTPException(status_code=404, detail="KIE mapping not found")
    return {"ok": True, "deleted_id": int(mapping_id)}


@router.post("/settings/system/manage/kie-standard-mappings/infer-billing-related", response_model=KIEDataStandardBillingInferenceResponse)
def infer_kie_standard_mapping_billing_related_manage(
    provider: str = Query(default="kie"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    provider_norm = str(provider or "kie").strip().lower() or "kie"
    _ensure_kie_standard_tables_for_admin(db)

    rows = db.query(SystemAPIBillingRule, SystemAPISetting).join(
        SystemAPISetting,
        SystemAPISetting.id == SystemAPIBillingRule.system_api_id,
    ).filter(
        SystemAPIBillingRule.is_active == True,
        func.lower(func.trim(func.coalesce(SystemAPISetting.provider, ""))) == provider_norm,
    ).all()

    dimensions_global: set = set()
    dimensions_by_model: Dict[str, set] = {}
    for rule, system_api in rows:
        dims = _extract_billing_related_dimensions(rule)
        if not dims:
            continue
        dimensions_global.update(dims)
        model_key = str(getattr(system_api, "model", "") or "").strip().lower()
        if model_key:
            bucket = dimensions_by_model.setdefault(model_key, set())
            bucket.update(dims)

    updated_count = 0
    reset_result = db.execute(text("""
        UPDATE kie_system_data_standard_mappings
        SET is_billing_related = 0,
            updated_at = datetime('now')
        WHERE lower(coalesce(provider, '')) = :provider
          AND coalesce(is_billing_related, 0) <> 0
    """), {"provider": provider_norm})
    updated_count += int(reset_result.rowcount or 0)

    if dimensions_global:
        for dim in sorted(dimensions_global):
            global_result = db.execute(text("""
                UPDATE kie_system_data_standard_mappings
                SET is_billing_related = 1,
                    updated_at = datetime('now')
                WHERE lower(coalesce(provider, '')) = :provider
                  AND upper(coalesce(standard_dimension, '')) = :dim
                  AND (coalesce(model_key_inferred, '') = '')
            """), {
                "provider": provider_norm,
                "dim": dim,
            })
            updated_count += int(global_result.rowcount or 0)

    for model_key, dims in dimensions_by_model.items():
        if not dims:
            continue
        for dim in sorted(dims):
            result = db.execute(text("""
                UPDATE kie_system_data_standard_mappings
                SET is_billing_related = 1,
                    updated_at = datetime('now')
                WHERE lower(coalesce(provider, '')) = :provider
                  AND lower(coalesce(model_key_inferred, '')) = :model_key
                  AND upper(coalesce(standard_dimension, '')) = :dim
            """), {
                "provider": provider_norm,
                "model_key": model_key,
                "dim": dim,
            })
            updated_count += int(result.rowcount or 0)

    db.commit()
    return KIEDataStandardBillingInferenceResponse(
        ok=True,
        updated_count=updated_count,
        matched_dimension_count=len(dimensions_global),
        matched_dimensions=sorted(dimensions_global),
    )


@router.get("/settings/system/agent/tools-policy", response_model=AgentToolPolicyOut)
def get_agent_tool_policy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage agent tool policy")

    row = _get_or_create_agent_policy_row(db)
    db.commit()
    cfg = _safe_json_dict(row.config)
    normalized = _normalize_agent_tool_policy(cfg.get("agent_tool_policy", {}))
    return AgentToolPolicyOut(**normalized)


@router.get("/settings/system/manage/billing-rules/reset-config", response_model=BillingRuleResetConfigOut)
def get_billing_rule_reset_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage billing reset config")

    cfg = _get_billing_rule_reset_config(db)
    db.commit()
    return BillingRuleResetConfigOut(**cfg)


@router.get("/settings/system/manage/sora-mention-config", response_model=SoraMentionConfigOut)
def get_sora_mention_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage Sora mention config")

    cfg = _get_sora_mention_config(db)
    db.commit()
    return SoraMentionConfigOut(**cfg)


@router.put("/settings/system/manage/billing-rules/reset-config", response_model=BillingRuleResetConfigOut)
def update_billing_rule_reset_config(
    payload: BillingRuleResetConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage billing reset config")

    row = _get_or_create_agent_policy_row(db)
    cfg = _safe_json_dict(row.config)
    current_cfg = _normalize_billing_rule_reset_config(cfg.get(_BILLING_RESET_CONFIG_KEY, {}))
    patch = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    merged_cfg = {**current_cfg, **_safe_json_dict(patch)}
    cfg[_BILLING_RESET_CONFIG_KEY] = _normalize_billing_rule_reset_config(merged_cfg)
    row.config = cfg
    _persist_agent_policy_row_config(db, row.id, row.config)
    db.commit()

    normalized = _normalize_billing_rule_reset_config(_safe_json_dict(row.config).get(_BILLING_RESET_CONFIG_KEY, {}))
    return BillingRuleResetConfigOut(**normalized)


@router.put("/settings/system/manage/sora-mention-config", response_model=SoraMentionConfigOut)
def update_sora_mention_config(
    payload: SoraMentionConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage Sora mention config")

    row = _get_or_create_agent_policy_row(db)
    cfg = _safe_json_dict(row.config)
    current_cfg = _normalize_sora_mention_config(cfg.get(_SORA_MENTION_CONFIG_KEY, {}))
    patch = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    merged_cfg = {**current_cfg, **_safe_json_dict(patch)}
    cfg[_SORA_MENTION_CONFIG_KEY] = _normalize_sora_mention_config(merged_cfg)
    row.config = cfg
    _persist_agent_policy_row_config(db, row.id, row.config)
    db.commit()

    normalized = _normalize_sora_mention_config(_safe_json_dict(row.config).get(_SORA_MENTION_CONFIG_KEY, {}))
    return SoraMentionConfigOut(**normalized)


@router.get("/settings/system/manage/{system_api_id}/billing-rules", response_model=List[SystemAPIBillingRuleOut])
def list_system_api_billing_rules(
    system_api_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    target = db.query(SystemAPISetting.id).filter(SystemAPISetting.id == system_api_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="System API setting not found")

    if not _require_billing_rules_table(db, allow_missing=True):
        return []

    rows = db.query(SystemAPIBillingRule).filter(
        SystemAPIBillingRule.system_api_id == system_api_id,
    ).order_by(SystemAPIBillingRule.is_active.desc(), SystemAPIBillingRule.priority.desc(), SystemAPIBillingRule.id.desc()).all()
    return [_rule_to_out(row) for row in rows]


@router.post("/settings/system/manage/{system_api_id}/billing-rules", response_model=SystemAPIBillingRuleOut)
def create_system_api_billing_rule(
    system_api_id: int,
    payload: SystemAPIBillingRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")
    _require_billing_rules_table(db)
    if int(payload.system_api_id) != int(system_api_id):
        raise HTTPException(status_code=400, detail="path system_api_id must match payload.system_api_id")

    target = db.query(SystemAPISetting.id).filter(SystemAPISetting.id == system_api_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="System API setting not found")

    payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    payload_data["charge_multiplier"] = _normalize_rule_charge_multiplier(payload_data.get("charge_multiplier"), default=2.0)
    payload_data["updated_at"] = now_bj_iso()
    rule = SystemAPIBillingRule(**payload_data)
    db.add(rule)
    db.flush()
    _refresh_has_granular_billing_rules_flag(db, system_api_id)
    _refresh_settings_price_cache_for_system_apis(db, [system_api_id])
    _refresh_settings_provider_price_cache_for_system_apis(db, [system_api_id])
    db.commit()
    db.refresh(rule)
    return _rule_to_out(rule)


@router.post("/settings/system/manage/billing-rules/{rule_id:int}", response_model=SystemAPIBillingRuleOut)
def update_system_api_billing_rule(
    rule_id: int,
    payload: SystemAPIBillingRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")
    _require_billing_rules_table(db)

    rule = db.query(SystemAPIBillingRule).filter(SystemAPIBillingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Billing rule not found")

    update_data = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    if "is_active" in update_data:
        # Preserve explicit disable requests (false) and avoid accidental truthy coercion.
        update_data["is_active"] = bool(update_data.get("is_active"))
    if "charge_multiplier" in update_data:
        update_data["charge_multiplier"] = _normalize_rule_charge_multiplier(update_data.get("charge_multiplier"), default=2.0)
    for key, value in update_data.items():
        setattr(rule, key, value)
    rule.updated_at = now_bj_iso()
    db.flush()
    _refresh_has_granular_billing_rules_flag(db, int(rule.system_api_id))
    _refresh_settings_price_cache_for_system_apis(db, [int(rule.system_api_id)])
    _refresh_settings_provider_price_cache_for_system_apis(db, [int(rule.system_api_id)])
    db.commit()
    db.refresh(rule)
    return _rule_to_out(rule)


@router.delete("/settings/system/manage/billing-rules/{rule_id:int}")
def delete_system_api_billing_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")
    _require_billing_rules_table(db)

    rule = db.query(SystemAPIBillingRule).filter(SystemAPIBillingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Billing rule not found")

    system_api_id = int(rule.system_api_id)
    db.delete(rule)
    db.flush()
    _refresh_has_granular_billing_rules_flag(db, system_api_id)
    _refresh_settings_price_cache_for_system_apis(db, [system_api_id])
    _refresh_settings_provider_price_cache_for_system_apis(db, [system_api_id])
    db.commit()
    return {"ok": True, "deleted_id": rule_id}


@router.delete("/settings/system/manage/billing-rules")
def batch_delete_system_api_billing_rules(
    rule_ids: str = Query("", description="Comma separated billing rule ids"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")
    _require_billing_rules_table(db)

    raw_ids = [token.strip() for token in str(rule_ids or "").split(",") if token.strip()]
    parsed_ids: List[int] = []
    for token in raw_ids:
        try:
            value = int(token)
        except Exception:
            continue
        if value > 0 and value not in parsed_ids:
            parsed_ids.append(value)

    if not parsed_ids:
        raise HTTPException(status_code=400, detail="No valid rule_ids provided")

    rows = db.query(SystemAPIBillingRule).filter(SystemAPIBillingRule.id.in_(parsed_ids)).all()
    found_ids = {int(row.id) for row in rows}
    missing_ids = [rid for rid in parsed_ids if rid not in found_ids]

    if not rows:
        raise HTTPException(status_code=404, detail="Billing rules not found")

    touched_system_api_ids = {int(row.system_api_id) for row in rows}
    for row in rows:
        db.delete(row)

    db.flush()
    for system_api_id in touched_system_api_ids:
        _refresh_has_granular_billing_rules_flag(db, system_api_id)
    _refresh_settings_price_cache_for_system_apis(db, list(touched_system_api_ids))
    _refresh_settings_provider_price_cache_for_system_apis(db, list(touched_system_api_ids))
    db.commit()

    return {
        "ok": True,
        "deleted_count": len(rows),
        "deleted_ids": sorted(found_ids),
        "missing_ids": missing_ids,
    }


@router.post("/settings/system/manage/billing-rules/reset-charge-multiplier", response_model=SystemAPIBillingRuleMultiplierResetResponse)
def reset_system_api_billing_rule_charge_multipliers(
    payload: SystemAPIBillingRuleMultiplierResetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Batch reset charge_multiplier by rule cost level.

    Rules:
    - Multiplier target range is [1.1, 2.0].
    - Lower base score => higher multiplier (absolute-score binned linear decay).
    - Per-rule increase cap: score * multiplier - score <= configured cap.
    """
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    reset_cfg = _get_billing_rule_reset_config(db)
    min_multiplier = float(payload.min_multiplier if payload.min_multiplier is not None else reset_cfg.get("min_multiplier", _BILLING_RESET_MIN_MULTIPLIER_DEFAULT))
    max_multiplier = float(payload.max_multiplier if payload.max_multiplier is not None else reset_cfg.get("max_multiplier", _BILLING_RESET_MAX_MULTIPLIER_DEFAULT))
    default_multiplier = _normalize_rule_charge_multiplier(
        payload.default_multiplier if payload.default_multiplier is not None else reset_cfg.get("default_multiplier", _BILLING_RESET_DEFAULT_MULTIPLIER_DEFAULT),
        default=_BILLING_RESET_DEFAULT_MULTIPLIER_DEFAULT,
    )
    bin_size_credits = max(1, _non_negative_int(
        payload.bin_size_credits if payload.bin_size_credits is not None else reset_cfg.get("bin_size_credits", _BILLING_RESET_BIN_SIZE_CREDITS_DEFAULT),
        _BILLING_RESET_BIN_SIZE_CREDITS_DEFAULT,
    ))
    bin_drop_multiplier = _safe_non_negative_float(
        payload.bin_drop_multiplier if payload.bin_drop_multiplier is not None else reset_cfg.get("bin_drop_multiplier", _BILLING_RESET_BIN_DROP_MULTIPLIER_DEFAULT)
    )
    if bin_drop_multiplier <= 0:
        bin_drop_multiplier = float(_BILLING_RESET_BIN_DROP_MULTIPLIER_DEFAULT)

    configured_cap = _non_negative_int(reset_cfg.get("max_total_increase_credits"), _BILLING_RESET_MAX_INCREASE_DEFAULT)
    max_total_increase_credits = _non_negative_int(getattr(payload, "max_total_increase_credits", None), configured_cap)

    if min_multiplier <= 0 or max_multiplier <= 0:
        raise HTTPException(status_code=400, detail="Multiplier bounds must be positive")
    if min_multiplier > max_multiplier:
        min_multiplier, max_multiplier = max_multiplier, min_multiplier

    min_multiplier = max(1.1, min(2.0, min_multiplier))
    max_multiplier = max(1.1, min(2.0, max_multiplier))
    if min_multiplier > max_multiplier:
        min_multiplier, max_multiplier = max_multiplier, min_multiplier

    requested_ids = sorted({int(x) for x in (payload.system_api_ids or []) if _safe_non_negative_int(x) > 0})

    query = db.query(SystemAPIBillingRule)
    if requested_ids:
        query = query.filter(SystemAPIBillingRule.system_api_id.in_(requested_ids))
    rows = query.order_by(SystemAPIBillingRule.system_api_id.asc(), SystemAPIBillingRule.id.asc()).all()

    if not rows:
        return SystemAPIBillingRuleMultiplierResetResponse(
            requested_system_api_count=len(requested_ids),
            total_rules=0,
            updated_rules=0,
            min_cost=0,
            max_cost=0,
            min_multiplier=min_multiplier,
            max_multiplier=max_multiplier,
            default_multiplier=default_multiplier,
            bin_size_credits=int(bin_size_credits),
            bin_drop_multiplier=float(round(bin_drop_multiplier, 6)),
            max_total_increase_credits=int(max_total_increase_credits),
            total_increase_credits=0.0,
            max_rule_increase_credits=0.0,
            increase_cap_applied=False,
            preview=[],
        )

    scored: List[Tuple[SystemAPIBillingRule, int]] = [(row, _rule_cost_score(row)) for row in rows]
    min_cost = min(score for _, score in scored)
    max_cost = max(score for _, score in scored)

    planned_rows: List[Dict[str, Any]] = []
    per_rule_cap_applied = False

    for row, score in scored:
        if score <= 0:
            target_multiplier = float(default_multiplier)
        else:
            target_multiplier = _compute_binned_multiplier(
                score,
                min_multiplier,
                max_multiplier,
                bin_size_credits,
                bin_drop_multiplier,
            )

        old_multiplier = _normalize_rule_charge_multiplier(getattr(row, "charge_multiplier", None), default=default_multiplier)

        # 1) Keep base mapping in configured multiplier band.
        target_multiplier = max(float(min_multiplier), min(float(max_multiplier), float(target_multiplier)))

        # 2) Per-rule cap against original score baseline:
        #    score * multiplier - score <= cap  => multiplier <= 1 + cap/score
        if score > 0 and max_total_increase_credits >= 0:
            cap_upper = 1.0 + (float(max_total_increase_credits) / float(score))
            capped_multiplier = min(float(target_multiplier), float(cap_upper))
            if capped_multiplier < float(target_multiplier) - 1e-9:
                per_rule_cap_applied = True
            target_multiplier = capped_multiplier

        # Final safe clamp.
        target_multiplier = max(0.0, min(float(max_multiplier), float(target_multiplier)))

        baseline_increase_credits = float(score) * max(0.0, float(target_multiplier) - 1.0) if score > 0 else 0.0

        delta_multiplier = float(target_multiplier) - float(old_multiplier)

        planned_rows.append({
            "row": row,
            "score": int(score),
            "old_multiplier": float(old_multiplier),
            "new_multiplier": float(target_multiplier),
            "delta_multiplier": float(delta_multiplier),
            "increase_credits": max(0.0, float(baseline_increase_credits)),
        })

    increase_cap_applied = bool(per_rule_cap_applied)

    total_increase_credits = 0.0
    max_rule_increase_credits = 0.0
    updated = 0
    now_iso = now_bj_iso()
    preview: List[Dict[str, Any]] = []

    for item in planned_rows:
        row = item["row"]
        score = int(item["score"])
        old_multiplier = float(item["old_multiplier"])
        new_multiplier = _normalize_rule_charge_multiplier(item["new_multiplier"], default=default_multiplier)

        if score > 0:
            rule_inc = float(score) * max(0.0, float(new_multiplier) - 1.0)
            total_increase_credits += rule_inc
            if rule_inc > max_rule_increase_credits:
                max_rule_increase_credits = rule_inc

        if abs(float(old_multiplier) - float(new_multiplier)) > 1e-9:
            updated += 1
            row.charge_multiplier = float(new_multiplier)
            row.updated_at = now_iso

        if len(preview) < 50:
            preview.append({
                "rule_id": int(row.id),
                "system_api_id": int(row.system_api_id),
                "cost_score": int(score),
                "old_multiplier": float(old_multiplier),
                "new_multiplier": float(new_multiplier),
            })

    touched_system_api_ids = sorted({int(getattr(item.get("row"), "system_api_id", 0) or 0) for item in planned_rows if item.get("row") is not None})
    if touched_system_api_ids:
        _refresh_settings_price_cache_for_system_apis(db, touched_system_api_ids)
        _refresh_settings_provider_price_cache_for_system_apis(db, touched_system_api_ids)
    db.commit()

    return SystemAPIBillingRuleMultiplierResetResponse(
        requested_system_api_count=len(requested_ids),
        total_rules=len(rows),
        updated_rules=updated,
        min_cost=int(min_cost),
        max_cost=int(max_cost),
        min_multiplier=float(min_multiplier),
        max_multiplier=float(max_multiplier),
        default_multiplier=float(default_multiplier),
        bin_size_credits=int(bin_size_credits),
        bin_drop_multiplier=float(round(bin_drop_multiplier, 6)),
        max_total_increase_credits=int(max_total_increase_credits),
        total_increase_credits=float(round(total_increase_credits, 4)),
        max_rule_increase_credits=float(round(max_rule_increase_credits, 4)),
        increase_cap_applied=bool(increase_cap_applied),
        preview=preview,
    )


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
    _persist_agent_policy_row_config(db, row.id, row.config)
    db.commit()

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
    now_iso = now_bj_iso()

    for suggestion in suggestions:
        existing = _find_system_setting_by_normalized_triplet(db, suggestion.provider, suggestion.category, suggestion.model)

        supplier_pricing = {
            "unit_type": suggestion.unit_type,
            "supplier_price": suggestion.supplier_price,
            "supplier_price_input": suggestion.supplier_price_input,
            "supplier_price_output": suggestion.supplier_price_output,
            "supplier_currency": suggestion.supplier_currency or "CNY",
            "supplier_price_basis": suggestion.supplier_price_basis or "money",
            "source": "provider_input",
            "updated_at": now_iso,
        }
        pricing_scheme = {
            "strategy": "supplier_price_x_multiplier",
            "multiplier": suggestion.multiplier,
            "cny_to_credit_rate": 100,  # 1积分=1分钱=0.01�?
            "supplier_currency": suggestion.supplier_currency or "CNY",
            "supplier_price_basis": suggestion.supplier_price_basis or "money",
            "conversion_note": "Only CNY monetary prices are accepted. Non-CNY must be converted via exchange-rate tool first.",
            "computed_at": now_iso,
        }
        normalized_cfg = _strip_billing_from_config({})
        normalized_cfg["supplier_pricing"] = supplier_pricing
        normalized_cfg["pricing_scheme"] = pricing_scheme

        billing = {
            "unit_type": suggestion.unit_type,
            "cost": _base_cost_to_credit(suggestion.supplier_price),
            "cost_input": _base_cost_to_credit(suggestion.supplier_price_input),
            "cost_output": _base_cost_to_credit(suggestion.supplier_price_output),
            "charge_multiplier": suggestion.multiplier,
        }

        # 构建 supplier_info: 存储原供应商API定价信息用于审计对照
        raw_info = suggestion.supplier_raw_info or {}
        supplier_info_data = {
            "supplier_pricing_snapshot": supplier_pricing,
            "pricing_scheme_snapshot": pricing_scheme,
            "raw_info": raw_info,
            "recorded_at": now_iso,
        }

        if existing:
            existing.name = suggestion.name or existing.name
            if suggestion.base_url:
                existing.base_url = suggestion.base_url
            existing.config = _strip_billing_from_config({**_safe_json_dict(existing.config), **normalized_cfg})
            existing.supplier_info = supplier_info_data
            existing.is_active = bool(existing.is_active)
            _clear_row_billing_columns(existing)
            _upsert_base_billing_rule(db, existing.id, existing.category, billing, activate=True)
            _refresh_has_granular_billing_rules_flag(db, existing.id)
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
                supplier_info=supplier_info_data,
                is_active=False,
            )
            _clear_row_billing_columns(existing)
            db.add(existing)
            db.flush()
            _upsert_base_billing_rule(db, existing.id, existing.category, billing, activate=True)
            _refresh_has_granular_billing_rules_flag(db, existing.id)

        applied_count += 1

    db.commit()
    return SystemAIAssistantResponse(
        provider=str(payload.provider or "").strip(),
        multiplier=(_safe_non_negative_float(payload.multiplier) or 1.0),
        suggestions=suggestions,
        applied_count=applied_count,
    )


# ── AI助手 MCP 工具端点 ────────────────────────────────────────

@router.post("/settings/system/ai-assistant/tools/exchange-rate", response_model=ExchangeRateResponse)
def ai_assistant_exchange_rate(
    payload: ExchangeRateRequest,
    current_user: User = Depends(get_current_user),
):
    """AI assistant tool: convert currency amounts to CNY."""
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only superuser can use system AI assistant tools")

    from app.services.pricing_tools import convert_currency, fetch_exchange_rate

    from_cur = (payload.from_currency or "USD").strip().upper()
    to_cur = (payload.to_currency or "CNY").strip().upper()

    if payload.amount is not None:
        result = convert_currency(payload.amount, from_cur, to_cur)
        return ExchangeRateResponse(**result)
    else:
        rate_info = fetch_exchange_rate(from_cur, to_cur)
        return ExchangeRateResponse(
            from_currency=rate_info["from"],
            to_currency=rate_info["to"],
            rate=rate_info.get("rate"),
            source=rate_info.get("source"),
            error=rate_info.get("error"),
        )


@router.post("/settings/system/ai-assistant/tools/fetch-pricing", response_model=FetchPricingPageResponse)
def ai_assistant_fetch_pricing(
    payload: FetchPricingPageRequest,
    current_user: User = Depends(get_current_user),
):
    """AI assistant tool: fetch pricing page and extract structured content."""
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only superuser can use system AI assistant tools")

    from app.services.pricing_tools import fetch_pricing_page

    url = (payload.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    result = fetch_pricing_page(url, max_length=min(payload.max_length, 50000))
    return FetchPricingPageResponse(**result)


@router.post("/settings/system/ai-assistant/tools/analyze-supplier-features", response_model=SupplierApiFeatureAnalyzeResponse)
async def ai_assistant_analyze_supplier_features(
    payload: SupplierApiFeatureAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Analyze supplier API feature profiles from docs pages and persist to system_api_settings."""
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only superuser can use system AI assistant tools")

    from app.services.llm_service import llm_service
    from app.services.pricing_tools import fetch_pricing_page

    selected_api_ids = {
        int(x) for x in (payload.selected_system_api_ids or [])
        if _safe_non_negative_int(x) > 0
    }
    selected_rows: List[SystemAPISetting] = []
    if selected_api_ids:
        selected_rows = db.query(SystemAPISetting).filter(
            SystemAPISetting.id.in_(selected_api_ids),
            ~SystemAPISetting.category.like("System_%"),
        ).all()

    provider = _normalize_system_provider_name(payload.provider)
    if not provider and selected_rows:
        provider = _normalize_system_provider_name(getattr(selected_rows[0], "provider", ""))
    if not provider:
        raise HTTPException(status_code=400, detail="provider is required")

    logger.info("supplier_feature_analysis.start provider=%s selected_api_ids=%s", provider, sorted(selected_api_ids))

    urls: List[str] = []
    for item in payload.source_urls or []:
        u = str(item or "").strip()
        if not u:
            continue
        if not u.startswith(("http://", "https://")):
            continue
        if u not in urls:
            urls.append(u)
    def _append_unique_http_url(raw: Any):
        normalized = _normalize_optional_http_url(raw)
        if normalized and normalized not in urls:
            urls.append(normalized)

    if bool(payload.include_provider_intro_url):
        pool_record = _get_provider_key_pool_record(db, provider)
        _append_unique_http_url(getattr(pool_record, "intro_url", None) if pool_record else None)

    selected_api_context: List[Dict[str, Any]] = []
    for row in selected_rows:
        row_provider = _normalize_system_provider_name(getattr(row, "provider", ""))
        if row_provider and provider and row_provider != provider:
            continue
        supplier_info = _safe_json_dict(getattr(row, "supplier_info", {}))
        selected_api_context.append({
            "id": int(row.id),
            "provider": row_provider,
            "category": str(row.category or "").strip(),
            "model": str(row.model or "").strip(),
            "base_model": str(row.base_model or "").strip(),
            "generation_modes": getattr(row, "generation_modes", None),
            "input_formats": getattr(row, "input_formats", None),
            "output_format": getattr(row, "output_format", None),
            "supported_resolutions": getattr(row, "supported_resolutions", None),
            "aspect_ratios": getattr(row, "aspect_ratios", None),
            "max_duration": getattr(row, "max_duration", None),
            "has_audio": getattr(row, "has_audio", None),
            "mode_values": getattr(row, "mode_values", None),
            "supplier_info": supplier_info,
        })
        for key_name in ["intro_url", "docs_url", "doc_url", "pricing_url", "official_url", "api_doc_url"]:
            _append_unique_http_url(supplier_info.get(key_name))
        for list_name in ["source_urls", "urls", "references"]:
            values = supplier_info.get(list_name)
            if isinstance(values, list):
                for item in values:
                    _append_unique_http_url(item)
        _append_unique_http_url(getattr(row, "base_url", None))

    max_len = min(max(int(payload.max_length or 40000), 2000), 50000)
    max_pages = min(max(int(payload.max_pages or 6), 1), 12)
    # Bound page fetching time to avoid long stalls when candidate URLs are slow/unreachable.
    fetch_timeout_seconds = min(120.0, max(35.0, float(max_pages * 8)))
    fetch_deadline = time.monotonic() + fetch_timeout_seconds

    page_summaries: List[Dict[str, Any]] = []
    combined_parts: List[str] = []
    warnings: List[str] = []

    if not urls:
        logger.info("supplier_feature_analysis.skip_fetch provider=%s reason=no_source_urls", provider)
    else:
        for base_url in urls:
            if time.monotonic() >= fetch_deadline:
                warnings.append(f"fetch_timeout_reached:{int(fetch_timeout_seconds)}s")
                logger.warning("supplier_feature_analysis.fetch_timeout provider=%s timeout_seconds=%s", provider, fetch_timeout_seconds)
                break
            page_urls = [base_url]
            page_urls.extend(_build_kie_pagination_urls(base_url, max_pages=max_pages))
            seen_hash = set()
            collected = 0
            for page_url in page_urls:
                if time.monotonic() >= fetch_deadline:
                    warnings.append(f"fetch_timeout_reached:{int(fetch_timeout_seconds)}s")
                    logger.warning("supplier_feature_analysis.fetch_timeout_during_pages provider=%s url=%s", provider, base_url)
                    break
                if collected >= max_pages:
                    break
                result = fetch_pricing_page(page_url, max_length=max_len)
                if result.get("error"):
                    warnings.append(f"fetch_failed:{page_url}:{result.get('error')}")
                    continue

                text_content = str(result.get("text_content") or "")
                if not text_content.strip():
                    continue
                text_hash = hash(text_content)
                if text_hash in seen_hash:
                    continue
                seen_hash.add(text_hash)
                collected += 1

                tables = result.get("tables") if isinstance(result.get("tables"), list) else []
                page_summaries.append({
                    "url": page_url,
                    "title": str(result.get("title") or "").strip() or None,
                    "text_length": len(text_content),
                    "table_count": len(tables),
                })
                combined_parts.append(f"### {page_url}\n{text_content}")
                if tables:
                    try:
                        combined_parts.append(f"TABLES: {json.dumps(tables, ensure_ascii=False)[:12000]}")
                    except Exception:
                        pass

    logger.info(
        "supplier_feature_analysis.fetch_done provider=%s urls=%s pages=%s warnings=%s",
        provider,
        len(urls),
        len(page_summaries),
        len(warnings),
    )

    combined_text = "\n\n".join(combined_parts)
    if not combined_text.strip() and selected_api_context:
        combined_text = f"SELECTED_SYSTEM_APIS: {json.dumps(selected_api_context, ensure_ascii=False)}"
    auto_research_mode = not combined_text.strip()
    if auto_research_mode:
        warnings.append("no_readable_source_content_fallback_to_llm_self_research")

    keyword_candidates = [
        "resolution", "aspect ratio", "duration", "reference image", "base model",
        "t2i", "i2i", "i2v", "t2v", "digital human", "image edit",
        "pricing", "price", "cost", "billing", "token", "input token", "output token",
        "fps", "audio", "webhook", "queue", "concurrency", "rate limit",
        "llm", "chat", "completion", "context window", "input tokens", "output tokens", "reasoning",
        "voice", "tts", "asr", "speech", "speaker", "emotion", "tone", "voice clone", "sample rate", "bitrate",
        "music", "bgm", "instrumental", "vocal", "genre", "tempo", "bpm", "key", "style",
        "分辨率", "画幅", "时长", "参考图", "基础模型", "数字人", "图像修改",
        "计费", "价格", "成本", "输入token", "输出token", "并发", "限流", "队列",
        "配音", "语音", "音色", "语速", "情感", "采样率", "码率", "克隆",
        "音乐", "背景音乐", "曲风", "节奏", "调式", "乐器",
        "文本", "对话", "推理", "上下文", "上下文长度", "输入长度", "输出长度",
    ]
    for kw in payload.search_keywords or []:
        token = str(kw or "").strip()
        if token and token not in keyword_candidates:
            keyword_candidates.append(token)

    keyword_hits: Dict[str, int] = {}
    lower_text = combined_text.lower()
    for kw in keyword_candidates:
        k = str(kw or "").strip().lower()
        if not k:
            continue
        keyword_hits[k] = lower_text.count(k)

    llm_configs = _resolve_system_llm_runtime_configs(db, max_candidates=4)
    if not llm_configs:
        raise HTTPException(status_code=400, detail="No system default LLM configured for analysis")

    user_supplement = str(payload.user_supplement or "").strip()

    system_prompt = get_supplier_feature_analysis_system_prompt()

    query_payload = {
        "provider": provider,
        "user_supplement": user_supplement or None,
        "keyword_hits": keyword_hits,
        "pages": page_summaries,
        "auto_research_mode": auto_research_mode,
        "selected_system_apis": selected_api_context,
        "target_mapping": {
            "system_api_modality_fields": [
                "generation_modes", "supported_resolutions", "aspect_ratios", "max_duration", "has_audio", "base_model", "input_formats", "output_format",
                "text_capabilities", "voice_capabilities", "music_capabilities"
            ],
            "billing_rule_matching_fields": [
                "generation_mode", "input_format", "output_format", "has_audio",
                "input_tokens_min", "input_tokens_max", "output_tokens_min", "output_tokens_max", "total_tokens_min", "total_tokens_max",
                "width_min", "width_max", "height_min", "height_max", "duration_seconds_min", "duration_seconds_max", "fps_min", "fps_max",
                "sample_rate_min", "sample_rate_max", "bitrate_min", "bitrate_max"
            ]
        },
        # Keep input conservative to reduce upstream truncation/empty responses.
        "content": combined_text[:60000],
    }
    query = json.dumps(query_payload, ensure_ascii=False)

    async def _run_supplier_feature_analysis_llm(input_query: str, prompt_text: str, llm_runtime_config: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        llm_result_local = await llm_service.analyze_intent_with_system_prompt(
            input_query,
            {},
            [],
            llm_runtime_config,
            prompt_text,
        )
        if bool(llm_result_local.get("_llm_error")):
            raise RuntimeError(str(llm_result_local.get("reply") or "llm_error"))
        llm_raw_local = str(llm_result_local.get("reply") or llm_result_local.get("content") or llm_result_local)
        parsed_local = _extract_json_from_llm_text(llm_raw_local)
        return llm_raw_local, parsed_local

    llm_raw: str = ""
    parsed: Dict[str, Any] = {}
    llm_attempt_timeout_seconds = 40
    attempt_errors: List[str] = []

    for idx, llm_config in enumerate(llm_configs, start=1):
        provider_name = str(llm_config.get("provider") or "").strip() or "unknown"
        model_name = str(llm_config.get("model") or "").strip() or "-"
        logger.info(
            "supplier_feature_analysis.llm_attempt_start provider=%s attempt=%s/%s target=%s/%s timeout=%ss",
            provider,
            idx,
            len(llm_configs),
            provider_name,
            model_name,
            llm_attempt_timeout_seconds,
        )
        try:
            llm_raw, parsed = await asyncio.wait_for(
                _run_supplier_feature_analysis_llm(query, system_prompt, llm_config),
                timeout=llm_attempt_timeout_seconds,
            )
            initial_models = parsed.get("models") if isinstance(parsed.get("models"), list) else []
            if len(initial_models) == 0:
                retry_prompt = (
                    system_prompt
                    + " STRICT MODE: return JSON object only. "
                    + "If no model can be extracted, set models=[] and explain why in warnings."
                )
                retry_query = json.dumps({
                    "provider": provider,
                    "pages": page_summaries,
                    "selected_system_apis": selected_api_context,
                    "content_excerpt": combined_text[:30000],
                    "instruction": "extract model capabilities",
                }, ensure_ascii=False)
                retry_raw, retry_parsed = await asyncio.wait_for(
                    _run_supplier_feature_analysis_llm(retry_query, retry_prompt, llm_config),
                    timeout=llm_attempt_timeout_seconds,
                )
                retry_models = retry_parsed.get("models") if isinstance(retry_parsed.get("models"), list) else []
                if len(retry_models) > 0:
                    llm_raw, parsed = retry_raw, retry_parsed
                else:
                    warnings.append("llm_empty_models_after_retry")

            current_models = parsed.get("models") if isinstance(parsed.get("models"), list) else []
            if current_models or idx >= len(llm_configs):
                break

            attempt_errors.append(f"attempt_{idx}:{provider_name}/{model_name}:empty_models")
            warnings.append(f"llm_attempt_empty_models:{provider_name}:{model_name}")
        except asyncio.TimeoutError:
            attempt_errors.append(f"attempt_{idx}:{provider_name}/{model_name}:timeout")
            warnings.append(f"llm_attempt_timeout:{provider_name}:{model_name}")
            continue
        except Exception as exc:
            attempt_errors.append(f"attempt_{idx}:{provider_name}/{model_name}:{str(exc)[:200]}")
            warnings.append(f"llm_attempt_failed:{provider_name}:{model_name}")
            continue

    if attempt_errors:
        logger.warning("supplier_feature_analysis.llm_attempt_errors provider=%s details=%s", provider, attempt_errors)

    logger.info(
        "supplier_feature_analysis.llm_done provider=%s models=%s warnings=%s",
        provider,
        len(parsed.get("models") if isinstance(parsed.get("models"), list) else []),
        len(warnings),
    )

    raw_models = parsed.get("models") if isinstance(parsed.get("models"), list) else []
    if not raw_models:
        warnings.append("llm_no_parsed_models")
    normalized_models: List[SupplierApiFeatureModel] = []
    for item in raw_models:
        if not isinstance(item, dict):
            continue
        model_name = str(item.get("model") or "").strip()
        if not model_name:
            continue
        category = str(item.get("category") or "").strip() or "Image"
        if category.lower() == "digitalhuman":
            category = "DigitalHuman"
        if category.lower() == "digital_human":
            category = "DigitalHuman"
        generation_modes = _normalize_generation_modes(item.get("generation_modes"))
        confidence = 0.0
        try:
            confidence = float(item.get("confidence") or 0.0)
        except Exception:
            confidence = 0.0
        confidence = max(0.0, min(confidence, 1.0))

        normalized_models.append(SupplierApiFeatureModel(
            provider=provider,
            category=category,
            model=model_name,
            base_model=(str(item.get("base_model") or "").strip() or None),
            generation_modes=generation_modes,
            text_capabilities=_clean_feature_dict(item.get("text_capabilities")),
            image_capabilities=_clean_feature_dict(item.get("image_capabilities")),
            video_capabilities=_clean_feature_dict(item.get("video_capabilities")),
            digital_human_capabilities=_clean_feature_dict(item.get("digital_human_capabilities")),
            voice_capabilities=_clean_feature_dict(item.get("voice_capabilities")),
            music_capabilities=_clean_feature_dict(item.get("music_capabilities")),
            notes=(str(item.get("notes") or "").strip() or None),
            confidence=confidence,
        ))

    saved_created = 0
    saved_updated = 0
    if payload.save_to_db and normalized_models:
        apply_result = _apply_supplier_feature_models_to_db(
            db=db,
            provider=provider,
            models=normalized_models,
            source_urls=urls,
            create_missing_models=bool(payload.create_missing_models),
        )
        saved_created = int(apply_result.get("saved_created") or 0)
        saved_updated = int(apply_result.get("saved_updated") or 0)
        warnings.extend(apply_result.get("warnings") or [])

    parsed_warnings = parsed.get("warnings") if isinstance(parsed.get("warnings"), list) else []
    for w in parsed_warnings:
        wt = str(w or "").strip()
        if wt:
            warnings.append(wt)

    return SupplierApiFeatureAnalyzeResponse(
        provider=provider,
        analyzed_url_count=len(page_summaries),
        selected_system_api_count=len(selected_api_context),
        selected_system_api_ids=[int(item.get("id")) for item in selected_api_context if _safe_non_negative_int(item.get("id")) > 0],
        source_urls_used=urls,
        models=normalized_models,
        saved_created=saved_created,
        saved_updated=saved_updated,
        warnings=warnings,
        provider_summary=(str(parsed.get("provider_summary") or "").strip() or None),
        llm_input=query,
        llm_output=llm_raw,
        llm_raw=llm_raw,
    )


def _apply_supplier_feature_models_to_db(
    db: Session,
    provider: str,
    models: List[SupplierApiFeatureModel],
    source_urls: Optional[List[str]] = None,
    create_missing_models: bool = True,
) -> Dict[str, Any]:
    saved_created = 0
    saved_updated = 0
    skipped_count = 0
    warnings: List[str] = []
    now_iso = now_bj_iso()
    normalized_provider = _normalize_system_provider_name(provider)

    for item in models or []:
        if not isinstance(item, SupplierApiFeatureModel):
            continue
        model_name = str(item.model or "").strip()
        category = str(item.category or "").strip() or "Image"
        if not model_name:
            skipped_count += 1
            warnings.append("skip_empty_model")
            continue

        existing = _find_system_setting_by_normalized_triplet(db, normalized_provider, category, model_name)
        profile_dict = {
            "provider": normalized_provider,
            "category": category,
            "model": model_name,
            "base_model": item.base_model,
            "generation_modes": item.generation_modes,
            "text_capabilities": item.text_capabilities,
            "image_capabilities": item.image_capabilities,
            "video_capabilities": item.video_capabilities,
            "digital_human_capabilities": item.digital_human_capabilities,
            "voice_capabilities": item.voice_capabilities,
            "music_capabilities": item.music_capabilities,
            "notes": item.notes,
            "confidence": item.confidence,
            "source_urls": source_urls or [],
            "updated_at": now_iso,
        }
        feature_payload = _build_modality_from_feature_profile(profile_dict)

        wide_payload = {
            "generation_modes": feature_payload.get("generation_modes"),
            "input_formats": feature_payload.get("input_formats"),
            "output_format": feature_payload.get("output_format"),
            "supported_resolutions": feature_payload.get("supported_resolutions"),
            "aspect_ratios": feature_payload.get("aspect_ratios"),
            "max_images_per_call": feature_payload.get("max_images_per_call"),
            "reference_image_limit": feature_payload.get("reference_image_limit"),
            "reference_video_limit": feature_payload.get("reference_video_limit"),
            "durations_seconds": feature_payload.get("durations_seconds"),
            "max_duration": feature_payload.get("max_duration"),
            "fps_options": feature_payload.get("fps_options"),
            "image_size_values": feature_payload.get("image_size_values"),
            "quality_values": feature_payload.get("quality_values"),
            "has_audio": feature_payload.get("has_audio"),
            "sound_supported": feature_payload.get("sound_supported"),
            "multi_shots_supported": feature_payload.get("multi_shots_supported"),
            "mode_values": feature_payload.get("mode_values"),
            "text_capabilities": feature_payload.get("text_capabilities"),
            "image_capabilities": feature_payload.get("image_capabilities"),
            "video_capabilities": feature_payload.get("video_capabilities"),
            "digital_human_capabilities": feature_payload.get("digital_human_capabilities"),
            "voice_capabilities": feature_payload.get("voice_capabilities"),
            "music_capabilities": feature_payload.get("music_capabilities"),
        }

        if existing:
            existing.base_model = _resolve_base_model(item.base_model, existing.model or model_name)
            existing.modality = feature_payload
            supplier_info = _safe_json_dict(existing.supplier_info)
            supplier_info.setdefault("feature_profiles", {})
            supplier_info["feature_profiles"][model_name] = profile_dict
            existing.supplier_info = supplier_info
            saved_updated += 1
            continue

        if create_missing_models:
            supplier_info = {
                "feature_profiles": {
                    model_name: profile_dict,
                }
            }
            row = SystemAPISetting(
                name=f"{normalized_provider} {model_name}",
                category=category,
                provider=normalized_provider,
                api_key="",
                base_url=None,
                model=model_name,
                base_model=_resolve_base_model(item.base_model, model_name),
                modality=feature_payload,
                tags=[],
                supplier_info=supplier_info,
                deprecated=False,
                config={},
                is_active=False,
            )
            db.add(row)
            saved_created += 1
            continue

        skipped_count += 1

    if saved_created > 0 or saved_updated > 0:
        db.commit()

    return {
        "saved_created": saved_created,
        "saved_updated": saved_updated,
        "skipped_count": skipped_count,
        "warnings": warnings,
    }


@router.post("/settings/system/ai-assistant/tools/apply-supplier-features", response_model=SupplierApiFeatureApplyResponse)
async def ai_assistant_apply_supplier_features(
    payload: SupplierApiFeatureApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist selected supplier feature models into system_api_settings."""
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only superuser can use system AI assistant tools")

    provider = _normalize_system_provider_name(payload.provider)
    if not provider:
        raise HTTPException(status_code=400, detail="provider is required")
    if not payload.models:
        raise HTTPException(status_code=400, detail="models is required")

    normalized_models: List[SupplierApiFeatureModel] = []
    for item in payload.models:
        model_name = str(item.model or "").strip()
        if not model_name:
            continue
        category = str(item.category or "").strip() or "Image"
        if category.lower() == "digitalhuman":
            category = "DigitalHuman"
        if category.lower() == "digital_human":
            category = "DigitalHuman"
        normalized_models.append(SupplierApiFeatureModel(
            provider=provider,
            category=category,
            model=model_name,
            base_model=(str(item.base_model or "").strip() or None),
            generation_modes=_normalize_generation_modes(item.generation_modes),
            text_capabilities=_clean_feature_dict(item.text_capabilities),
            image_capabilities=_clean_feature_dict(item.image_capabilities),
            video_capabilities=_clean_feature_dict(item.video_capabilities),
            digital_human_capabilities=_clean_feature_dict(item.digital_human_capabilities),
            voice_capabilities=_clean_feature_dict(item.voice_capabilities),
            music_capabilities=_clean_feature_dict(item.music_capabilities),
            notes=(str(item.notes or "").strip() or None),
            confidence=max(0.0, min(float(item.confidence or 0.0), 1.0)),
        ))

    if not normalized_models:
        raise HTTPException(status_code=400, detail="No valid models to apply")

    apply_result = _apply_supplier_feature_models_to_db(
        db=db,
        provider=provider,
        models=normalized_models,
        source_urls=[],
        create_missing_models=bool(payload.create_missing_models),
    )

    return SupplierApiFeatureApplyResponse(
        provider=provider,
        requested_count=len(payload.models),
        saved_created=int(apply_result.get("saved_created") or 0),
        saved_updated=int(apply_result.get("saved_updated") or 0),
        skipped_count=int(apply_result.get("skipped_count") or 0),
        warnings=[str(w) for w in (apply_result.get("warnings") or []) if str(w).strip()],
    )


@router.post("/settings/system/manage/kie-pricing/generate", response_model=KIEPricingGenerateResponse)
async def generate_kie_pricing_rules(
    payload: KIEPricingGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """KIE pricing helper: fetch pricing, map to system_api(kie), generate rule suggestions."""
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    from app.services.llm_service import llm_service

    url = str(payload.url or "").strip() or "https://kie.ai/zh-CN/pricing"
    provider_filter = str(payload.provider_filter or "kie").strip() or "kie"
    selected_apply_ids = {
        int(x) for x in (payload.selected_system_api_ids or [])
        if _safe_non_negative_int(x) > 0
    }
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail="Please confirm fetched KIE pricing data before generating rules")

    text_content = str(payload.confirmed_pricing_text or "").strip()
    if not text_content:
        raise HTTPException(status_code=400, detail="confirmed_pricing_text is required after confirmation")

    system_rows = db.query(SystemAPISetting).filter(
        ~SystemAPISetting.category.like("System_%")
    ).order_by(SystemAPISetting.id.desc()).all()

    filtered_rows: List[SystemAPISetting] = []
    for row in system_rows:
        if not payload.include_deprecated and bool(getattr(row, "deprecated", False)):
            continue
        if _is_kie_system_setting(row, provider_filter=provider_filter):
            filtered_rows.append(row)

    if not filtered_rows:
        raise HTTPException(status_code=404, detail=f"No system_api_settings found for provider filter: {provider_filter}")

    llm_config = _resolve_system_llm_runtime_config(db)
    if not llm_config:
        raise HTTPException(status_code=400, detail="No usable active system LLM config found")

    system_model_payload = [
        {
            "system_api_id": int(row.id),
            "provider": str(row.provider or ""),
            "category": str(row.category or ""),
            "model": str(row.model or ""),
            "name": str(row.name or ""),
            "base_url": str(row.base_url or ""),
            "tags": (row.tags if isinstance(row.tags, list) else []),
        }
        for row in filtered_rows
    ]
    system_rule_hints = _collect_kie_system_rule_hints(db, filtered_rows)

    for item in system_model_payload:
        sid = int(item.get("system_api_id") or 0)
        hint = system_rule_hints.get(sid) or {}
        item["has_granular_rules"] = bool(hint.get("has_granular_rules", False))
        item["granular_rule_templates"] = list(hint.get("granular_rule_templates") or [])

    pricing_tables, tables_parse_status, tables_parse_warning = _parse_confirmed_pricing_tables(payload)
    table_sample = pricing_tables[:8]
    text_sample = text_content[:18000]

    system_prompt = (
        "You are a pricing-rule planner for a backend billing system. "
        "Given KIE pricing page content and system API model list, match model names and generate billing rule suggestions. "
        "Return STRICT JSON only. No markdown.\n"
        "Rules:\n"
        "1) Only match to provided system_api_id values.\n"
        "2) If uncertain, keep confidence low and put reason.\n"
        "3) Output source costs in numeric form. They may come from KIE credits or USD/CNY.\n"
        "4) unit_type must be one of per_call/per_second/per_minute/per_token/per_1k_tokens/per_million_tokens.\n"
        "5) For token models prefer per_million_tokens with input/output split when available.\n"
        "6) Include source_pricing_unit for each match: one of kie_credit|usd|cny.\n"
        "7) If one model has multiple prices by resolution/quality/variant (e.g. 1K/2K/4K), you MUST fill granular_rules with one rule per tier.\n"
        "8) For image-resolution tiers, set width_min/width_max/height_min/height_max/pixels_min/pixels_max so each tier can be matched independently.\n"
        "9) Respect system pricing rule metadata patterns from granular_rule_templates: when present, align granular_rules dimensions/extra_conditions with those templates (generation_mode, input/output format, token/image/video ranges, extra_conditions).\n"
        "10) If no granular template exists, infer necessary dimensions from source pricing note/table and still output structured granular_rules.\n"
        "JSON schema:\n"
        "{\n"
        "  \"matches\": [\n"
        "    {\n"
        "      \"system_api_id\": 123,\n"
        "      \"source_model_name\": \"...\",\n"
        "      \"confidence\": 0.0,\n"
        "      \"reason\": \"...\",\n"
        "      \"raw_price_note\": \"...\",\n"
        "      \"source_pricing_unit\": \"kie_credit\",\n"
        "      \"base_rule\": {\n"
        "        \"billing_unit_type\": \"per_call\",\n"
        "        \"billing_cost\": 0,\n"
        "        \"billing_cost_input\": 0,\n"
        "        \"billing_cost_output\": 0\n"
        "      },\n"
        "      \"granular_rules\": [\n"
        "        {\n"
        "          \"name\": \"...\",\n"
        "          \"description\": \"...\",\n"
        "          \"billing_unit_type\": \"per_call\",\n"
        "          \"billing_cost\": 0,\n"
        "          \"billing_cost_input\": 0,\n"
        "          \"billing_cost_output\": 0,\n"
        "          \"applies_to_text\": false,\n"
        "          \"applies_to_image\": true,\n"
        "          \"applies_to_video\": false,\n"
        "          \"generation_mode\": null,\n"
        "          \"input_format\": null,\n"
        "          \"output_format\": null,\n"
        "          \"has_audio\": null,\n"
        "          \"input_tokens_min\": null,\n"
        "          \"input_tokens_max\": null,\n"
        "          \"output_tokens_min\": null,\n"
        "          \"output_tokens_max\": null,\n"
        "          \"total_tokens_min\": null,\n"
        "          \"total_tokens_max\": null,\n"
        "          \"image_count_min\": null,\n"
        "          \"image_count_max\": null,\n"
        "          \"width_min\": null,\n"
        "          \"width_max\": null,\n"
        "          \"height_min\": null,\n"
        "          \"height_max\": null,\n"
        "          \"pixels_min\": null,\n"
        "          \"pixels_max\": null,\n"
        "          \"duration_seconds_min\": null,\n"
        "          \"duration_seconds_max\": null,\n"
        "          \"fps_min\": null,\n"
        "          \"fps_max\": null,\n"
        "          \"priority\": 0,\n"
        "          \"extra_conditions\": {}\n"
        "        }\n"
        "      ]\n"
        "    }\n"
        "  ],\n"
        "  \"unmatched_source_models\": [\"...\"],\n"
        "  \"unmatched_system_models\": [\"...\"],\n"
        "  \"warnings\": [\"...\"]\n"
        "}"
    )

    llm_query = (
        f"pricing_url={url}\n"
        f"provider_filter={provider_filter}\n"
        f"system_models={json.dumps(system_model_payload, ensure_ascii=False)}\n"
        f"system_pricing_rule_hints={json.dumps(system_rule_hints, ensure_ascii=False)}\n"
        f"pricing_text={text_sample}\n"
        f"pricing_tables={json.dumps(table_sample, ensure_ascii=False)}"
    )

    llm_result = await llm_service.analyze_intent_with_system_prompt(
        llm_query,
        context={},
        history=[],
        config=llm_config,
        system_prompt=system_prompt,
    )

    llm_raw = (
        llm_result.get("content")
        or llm_result.get("reply")
        or llm_result.get("raw_content")
        or json.dumps(llm_result, ensure_ascii=False)
    )
    parsed = _extract_json_from_llm_text(llm_raw)

    raw_matches = parsed.get("matches") if isinstance(parsed.get("matches"), list) else []
    allowed_ids = {int(row.id): row for row in filtered_rows}
    suggestions: List[KIEPricingRuleSuggestion] = []
    touched_ids: set = set()
    applied_count = 0
    applied_system_api_ids: List[int] = []
    apply_receipts: List[KIEPricingApplyReceipt] = []
    applied_id_set: set = set()
    has_billing_rules_table = _db_has_table(db, "system_api_billing_rules")

    for item in raw_matches:
        if not isinstance(item, dict):
            continue
        system_api_id = _safe_non_negative_int(item.get("system_api_id"))
        if system_api_id <= 0 or system_api_id not in allowed_ids:
            continue

        row = allowed_ids[system_api_id]
        source_pricing_unit = str(item.get("source_pricing_unit") or "kie_credit").strip().lower() or "kie_credit"
        base_rule_raw = item.get("base_rule") if isinstance(item.get("base_rule"), dict) else {}
        base_rule_unconverted = {
            "billing_unit_type": _normalize_unit_type_for_system_ai(base_rule_raw.get("billing_unit_type") or "per_call"),
            "billing_cost": _safe_non_negative_number(base_rule_raw.get("billing_cost")),
            "billing_cost_input": _safe_non_negative_number(base_rule_raw.get("billing_cost_input")),
            "billing_cost_output": _safe_non_negative_number(base_rule_raw.get("billing_cost_output")),
        }
        base_rule = _normalize_rule_costs_with_source(base_rule_unconverted, source_pricing_unit)

        granular_rules = item.get("granular_rules") if isinstance(item.get("granular_rules"), list) else []
        normalized_granular_rules: List[Dict[str, Any]] = []
        for rule_item in granular_rules:
            if not isinstance(rule_item, dict):
                continue
            converted_rule = _normalize_rule_costs_with_source(rule_item, source_pricing_unit)
            converted_rule["billing_unit_type"] = _normalize_unit_type_for_system_ai(converted_rule.get("billing_unit_type") or base_rule.get("billing_unit_type") or "per_call")
            normalized_granular_rules.append(converted_rule)

        if not normalized_granular_rules:
            normalized_granular_rules = _build_kie_resolution_granular_rules_from_note(
                str(item.get("raw_price_note") or ""),
                base_unit_type=str(base_rule.get("billing_unit_type") or "per_call"),
                source_unit=source_pricing_unit,
            )

        suggestion = KIEPricingRuleSuggestion(
            system_api_id=system_api_id,
            provider=str(row.provider or ""),
            category=str(row.category or ""),
            model=str(row.model or ""),
            source_model_name=str(item.get("source_model_name") or "").strip() or None,
            confidence=float(item.get("confidence") or 0.0),
            reason=str(item.get("reason") or "").strip() or None,
            base_rule=base_rule,
            granular_rules=normalized_granular_rules,
            raw_price_note=(
                (str(item.get("raw_price_note") or "").strip() or "")
                + f" | source_pricing_unit={source_pricing_unit}; conversion: kie*3, usd*7*100, cny*100"
            ).strip(" |"),
        )
        suggestions.append(suggestion)
        touched_ids.add(system_api_id)

        should_apply = bool(payload.apply_base_rules) and (
            not selected_apply_ids or system_api_id in selected_apply_ids
        )
        if should_apply:
            if not has_billing_rules_table:
                continue
            if system_api_id in applied_id_set:
                continue
            existed_before = _get_base_billing_rule(db, system_api_id, include_inactive=True) is not None
            upserted_rule = _upsert_base_billing_rule(db, system_api_id, str(row.category or "LLM"), base_rule, activate=True)
            _replace_kie_granular_billing_rules(db, system_api_id, str(row.category or "LLM"), normalized_granular_rules, activate=True)
            _refresh_has_granular_billing_rules_flag(db, system_api_id)
            applied_count += 1
            applied_system_api_ids.append(int(system_api_id))
            applied_id_set.add(system_api_id)
            apply_receipts.append(KIEPricingApplyReceipt(
                system_api_id=int(system_api_id),
                base_rule_id=int(upserted_rule.id),
                action=("updated" if existed_before else "created"),
            ))

    if payload.apply_base_rules and applied_count > 0:
        db.commit()

    unmatched_system_models = parsed.get("unmatched_system_models") if isinstance(parsed.get("unmatched_system_models"), list) else []
    if not unmatched_system_models:
        unmatched_system_models = [
            str(row.model or "")
            for row in filtered_rows
            if int(row.id) not in touched_ids and str(row.model or "").strip()
        ]

    warnings = parsed.get("warnings") if isinstance(parsed.get("warnings"), list) else []
    if payload.apply_base_rules and not has_billing_rules_table:
        warnings.append("system_api_billing_rules table missing; skipped apply_base_rules")
    unmatched_source_models = parsed.get("unmatched_source_models") if isinstance(parsed.get("unmatched_source_models"), list) else []

    apply_requested = bool(payload.apply_base_rules)
    apply_status = "not_requested"
    apply_message = None
    if apply_requested:
        if len(suggestions) <= 0:
            apply_status = "no_matches"
            apply_message = "Apply requested but no matched suggestions were generated."
        elif applied_count <= 0:
            apply_status = "no_selected_match"
            apply_message = "Apply requested but none of the matched suggestions were selected for apply."
        else:
            apply_status = "applied"
            apply_message = f"Applied base pricing to {applied_count} system API settings."

    return KIEPricingGenerateResponse(
        url=url,
        title=None,
        provider_filter=provider_filter,
        system_model_count=len(filtered_rows),
        suggestion_count=len(suggestions),
        apply_requested=apply_requested,
        apply_status=apply_status,
        apply_message=apply_message,
        applied_count=applied_count,
        applied_system_api_ids=[int(x) for x in applied_system_api_ids],
        apply_receipts=apply_receipts,
        matches=suggestions,
        unmatched_source_models=[str(x) for x in unmatched_source_models if str(x).strip()],
        unmatched_system_models=[str(x) for x in unmatched_system_models if str(x).strip()],
        warnings=[str(x) for x in warnings if str(x).strip()],
        tables_parse_status=tables_parse_status,
        tables_parse_warning=tables_parse_warning,
        llm_input=(llm_query[:4000] if llm_query else None),
        llm_output=(llm_raw[:4000] if llm_raw else None),
        llm_raw=(llm_raw[:4000] if llm_raw else None),
    )


@router.post("/settings/system/manage/kie-pricing/apply", response_model=KIEPricingApplyResponse)
def apply_kie_pricing_rules(
    payload: KIEPricingApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """KIE pricing helper: apply existing suggestions without re-running LLM matching."""
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    provider_filter = str(payload.provider_filter or "kie").strip() or "kie"
    has_billing_rules_table = _db_has_table(db, "system_api_billing_rules")
    if not has_billing_rules_table:
        return KIEPricingApplyResponse(
            provider_filter=provider_filter,
            requested_count=len(payload.matches or []),
            applied_count=0,
            apply_status="table_missing",
            apply_message="system_api_billing_rules table missing; apply skipped.",
            applied_system_api_ids=[],
            apply_receipts=[],
        )

    selected_apply_ids = {
        int(x) for x in (payload.selected_system_api_ids or [])
        if _safe_non_negative_int(x) > 0
    }
    matches = payload.matches if isinstance(payload.matches, list) else []
    requested_count = len(matches)
    if requested_count <= 0:
        return KIEPricingApplyResponse(
            provider_filter=provider_filter,
            requested_count=0,
            applied_count=0,
            apply_status="no_matches",
            apply_message="No existing suggestions to apply.",
            applied_system_api_ids=[],
            apply_receipts=[],
        )

    system_rows = db.query(SystemAPISetting).filter(
        ~SystemAPISetting.category.like("System_%")
    ).order_by(SystemAPISetting.id.desc()).all()

    filtered_rows: List[SystemAPISetting] = []
    for row in system_rows:
        if not payload.include_deprecated and bool(getattr(row, "deprecated", False)):
            continue
        if _is_kie_system_setting(row, provider_filter=provider_filter):
            filtered_rows.append(row)

    allowed_ids = {int(row.id): row for row in filtered_rows}
    applied_count = 0
    applied_system_api_ids: List[int] = []
    apply_receipts: List[KIEPricingApplyReceipt] = []
    applied_id_set: set = set()

    for item in matches:
        if not isinstance(item, dict):
            continue
        system_api_id = _safe_non_negative_int(item.get("system_api_id"))
        if system_api_id <= 0 or system_api_id not in allowed_ids:
            continue
        if selected_apply_ids and system_api_id not in selected_apply_ids:
            continue
        if system_api_id in applied_id_set:
            continue

        row = allowed_ids[system_api_id]
        base_rule_raw = item.get("base_rule") if isinstance(item.get("base_rule"), dict) else {}
        base_rule = {
            "unit_type": _normalize_unit_type_for_system_ai(base_rule_raw.get("billing_unit_type") or "per_call"),
            "cost": _safe_non_negative_number(base_rule_raw.get("billing_cost")),
            "cost_input": _safe_non_negative_number(base_rule_raw.get("billing_cost_input")),
            "cost_output": _safe_non_negative_number(base_rule_raw.get("billing_cost_output")),
        }

        granular_rules = item.get("granular_rules") if isinstance(item.get("granular_rules"), list) else []
        normalized_granular_rules: List[Dict[str, Any]] = []
        for rule_item in granular_rules:
            if not isinstance(rule_item, dict):
                continue
            converted_rule = dict(rule_item)
            converted_rule["billing_unit_type"] = _normalize_unit_type_for_system_ai(
                converted_rule.get("billing_unit_type") or base_rule.get("unit_type") or "per_call"
            )
            converted_rule["billing_cost"] = _safe_non_negative_int(converted_rule.get("billing_cost") if converted_rule.get("billing_cost") is not None else converted_rule.get("cost"))
            converted_rule["billing_cost_input"] = _safe_non_negative_int(converted_rule.get("billing_cost_input") if converted_rule.get("billing_cost_input") is not None else converted_rule.get("cost_input"))
            converted_rule["billing_cost_output"] = _safe_non_negative_int(converted_rule.get("billing_cost_output") if converted_rule.get("billing_cost_output") is not None else converted_rule.get("cost_output"))
            normalized_granular_rules.append(converted_rule)

        existed_before = _get_base_billing_rule(db, system_api_id, include_inactive=True) is not None
        upserted_rule = _upsert_base_billing_rule(db, system_api_id, str(row.category or "LLM"), base_rule, activate=True)
        _replace_kie_granular_billing_rules(db, system_api_id, str(row.category or "LLM"), normalized_granular_rules, activate=True)
        _refresh_has_granular_billing_rules_flag(db, system_api_id)

        applied_count += 1
        applied_system_api_ids.append(int(system_api_id))
        applied_id_set.add(system_api_id)
        apply_receipts.append(KIEPricingApplyReceipt(
            system_api_id=int(system_api_id),
            base_rule_id=int(upserted_rule.id),
            action=("updated" if existed_before else "created"),
        ))

    if applied_count > 0:
        db.commit()

    apply_status = "applied" if applied_count > 0 else "no_selected_match"
    apply_message = (
        f"Applied base pricing to {applied_count} system API settings."
        if applied_count > 0
        else "None of the existing suggestions matched selected/allowed system_api_id targets."
    )
    return KIEPricingApplyResponse(
        provider_filter=provider_filter,
        requested_count=requested_count,
        applied_count=applied_count,
        apply_status=apply_status,
        apply_message=apply_message,
        applied_system_api_ids=[int(x) for x in applied_system_api_ids],
        apply_receipts=apply_receipts,
    )


@router.post("/settings/system/manage/kie-pricing/fetch", response_model=KIEPricingFetchResponse)
def fetch_kie_pricing_data(
    payload: KIEPricingFetchRequest,
    current_user: User = Depends(get_current_user),
):
    """KIE pricing fetch helper: probe pages and confirm data before matching generation."""
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    url = str(payload.url or "").strip() or "https://kie.ai/zh-CN/pricing"
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="url must start with http:// or https://")

    result = _fetch_kie_pricing_paginated(
        url=url,
        max_length=min(max(int(payload.max_length or 40000), 5000), 60000),
        max_pages=min(max(int(payload.max_pages or 8), 1), 20),
    )
    return KIEPricingFetchResponse(**result)


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
    if _is_system_reserved_category(category):
        raise HTTPException(status_code=400, detail="System_* categories are reserved for infrastructure settings and cannot be managed as AIGC System API")
    model = (payload.model or "").strip()
    base_model = _resolve_base_model(payload.base_model, payload.model)
    existing = _find_system_setting_by_normalized_triplet(db, provider, category, model)
    if existing:
        raw_cfg = payload.config if isinstance(payload.config, dict) else _safe_json_dict(existing.config)
        billing = _billing_from_payload_or_config(payload, raw_cfg)
        target_cfg = _strip_billing_from_config(raw_cfg)
        target_cfg = _sync_model_mode_defaults_config(
            target_cfg,
            getattr(payload, "model_mode_defaults", None),
            provided=getattr(payload, "model_mode_defaults", None) is not None,
        )
        existing.name = (payload.name or existing.name or "System Setting").strip() or "System Setting"
        existing.base_url = payload.base_url
        existing.model = payload.model
        existing.base_model = base_model
        existing.modality = _build_modality_payload_from_item(payload)
        existing.tags = getattr(payload, "tags", None)
        existing.supplier_info = getattr(payload, "supplier_info", None) or existing.supplier_info
        existing.config = target_cfg
        existing.is_active = bool(existing.is_active)
        _clear_row_billing_columns(existing)

        effective_key = _sync_system_provider_shared_key(
            db,
            existing.provider,
            existing.id,
            payload.api_key,
        )
        existing.api_key = effective_key

        if bool(payload.is_active):
            upsert_task_default_system_setting(db, existing.category, int(existing.id))
        else:
            clear_task_default_for_category(db, existing.category)

        if _is_system_api_auto_billing_sync_enabled():
            _upsert_base_billing_rule(db, existing.id, existing.category, billing, activate=True)
            _refresh_has_granular_billing_rules_flag(db, existing.id)

        db.commit()
        db.refresh(existing)
        _invalidate_system_api_runtime_cache(refresh=True)
        return _setting_to_out(db, existing)

    raw_create_config = payload.config if isinstance(payload.config, dict) else {}
    create_billing = _billing_from_payload_or_config(payload, raw_create_config)
    create_config = _strip_billing_from_config(raw_create_config)
    create_config = _sync_model_mode_defaults_config(
        create_config,
        getattr(payload, "model_mode_defaults", None),
        provided=getattr(payload, "model_mode_defaults", None) is not None,
    )
    new_setting = SystemAPISetting(
        name=(payload.name or "System Setting").strip() or "System Setting",
        category=category,
        provider=provider,
        api_key="",
        base_url=payload.base_url,
        model=payload.model,
        base_model=base_model,
        tags=getattr(payload, "tags", None),
        supplier_info=getattr(payload, "supplier_info", None),
        modality=_build_modality_payload_from_item(payload),
        deprecated=False,
        config=create_config,
        is_active=False,
    )
    _clear_row_billing_columns(new_setting)
    db.add(new_setting)
    db.flush()

    if _is_system_api_auto_billing_sync_enabled():
        _upsert_base_billing_rule(db, new_setting.id, new_setting.category, create_billing, activate=True)
        _refresh_has_granular_billing_rules_flag(db, new_setting.id)

    # Keep provider-level key shared across all system rows for the same provider.
    effective_key = _sync_system_provider_shared_key(
        db,
        new_setting.provider,
        new_setting.id,
        payload.api_key,
    )
    new_setting.api_key = effective_key

    if bool(payload.is_active):
        upsert_task_default_system_setting(db, new_setting.category, int(new_setting.id))

    db.commit()
    db.refresh(new_setting)
    _invalidate_system_api_runtime_cache(refresh=True)
    return _setting_to_out(db, new_setting)


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

    next_category = payload.category if payload.category is not None else target.category
    if _is_system_reserved_category(next_category):
        raise HTTPException(status_code=400, detail="System_* categories are reserved for infrastructure settings and cannot be managed as AIGC System API")

    update_data = payload.dict(exclude_unset=True)
    billing_keys = ("billing_unit_type", "billing_cost", "billing_cost_input", "billing_cost_output")
    payload_billing = {k: update_data.pop(k) for k in billing_keys if k in update_data}
    has_model_mode_defaults = "model_mode_defaults" in update_data
    payload_model_mode_defaults = update_data.pop("model_mode_defaults", None)
    for key, value in update_data.items():
        setattr(target, key, value)
    target.base_model = _resolve_base_model(getattr(target, "base_model", None), getattr(target, "model", None))

    existing_billing = _resolve_system_setting_billing(db, target)
    if payload_billing:
        update_billing = {
            "unit_type": _normalize_billing_unit_type(payload_billing.get("billing_unit_type") or existing_billing.get("unit_type") or "per_call"),
            "cost": _non_negative_int(payload_billing["billing_cost"]) if "billing_cost" in payload_billing else _non_negative_int(existing_billing.get("cost", 0)),
            "cost_input": _non_negative_int(payload_billing["billing_cost_input"]) if "billing_cost_input" in payload_billing else _non_negative_int(existing_billing.get("cost_input", 0)),
            "cost_output": _non_negative_int(payload_billing["billing_cost_output"]) if "billing_cost_output" in payload_billing else _non_negative_int(existing_billing.get("cost_output", 0)),
        }
    else:
        update_billing = existing_billing
    target.config = _sync_model_mode_defaults_config(
        _strip_billing_from_config(target.config),
        payload_model_mode_defaults,
        provided=has_model_mode_defaults,
    )
    _clear_row_billing_columns(target)

    if payload.is_active is True:
        upsert_task_default_system_setting(db, target.category, int(target.id))
    elif payload.is_active is False:
        clear_task_default_for_category(db, target.category)

    # Keep provider-level key shared among system rows as well.
    effective_key = _sync_system_provider_shared_key(
        db,
        target.provider,
        target.id,
        payload.api_key,
    )
    target.api_key = effective_key

    if _is_system_api_auto_billing_sync_enabled():
        _upsert_base_billing_rule(db, target.id, target.category, update_billing, activate=True)
        _refresh_has_granular_billing_rules_flag(db, target.id)

    db.commit()
    db.refresh(target)
    _invalidate_system_api_runtime_cache(refresh=True)
    return _setting_to_out(db, target)


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
    _invalidate_system_api_runtime_cache(refresh=True)
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
    return _setting_to_out(db, target)


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
    _invalidate_system_api_runtime_cache(refresh=True)
    logger.warning(
        "[system_api.deprecated.toggle_by_key] committed latest_id=%s latest_deprecated_col=%s latest_config=%s",
        latest.id,
        latest.deprecated,
        latest.config,
    )
    print(f"[DBG toggle_by_key committed] latest_id={latest.id} after_col={latest.deprecated} after_cfg={latest.config}")

    return _setting_to_out(db, latest)


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

    provider_name = _normalize_system_provider_name(provider_name)

    query = db.query(SystemAPISetting).filter(
        _system_provider_case_insensitive_filter(provider_name)
    )
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
    _invalidate_system_api_runtime_cache(refresh=True)

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

    provider_name = _normalize_system_provider_name(provider_name)

    pool_info = _get_system_provider_key_pool_full(db, provider_name)
    return {
        "provider": provider_name,
        "key_count": len(pool_info["keys"]),
        "keys": pool_info["keys"],
        "keys_masked": [_mask_api_key(k) for k in pool_info["keys"]],
        "strategy": pool_info["strategy"],
        "weights": pool_info["weights"],
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

    provider_name = _normalize_system_provider_name(provider_name)

    pool = _normalize_api_keys(payload.keys)
    strategy = _normalize_key_strategy(payload.strategy)
    weights = _normalize_key_weights(payload.weights, pool)

    _apply_provider_key_bundle_to_rows(db, provider_name, pool, strategy, weights)
    db.commit()
    _invalidate_system_api_runtime_cache(refresh=True)
    _invalidate_provider_pool_cache()

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

    rows = _query_system_settings_manage_rows(db)

    items = []
    for row in rows:
        billing = _resolve_system_setting_billing(db, row)
        modality_fields = _extract_modality_manage_fields(getattr(row, "modality", None))
        items.append({
            "name": row.name,
            "category": row.category,
            "provider": row.provider,
            "api_key": row.api_key,
            "base_url": row.base_url,
            "model": row.model,
            "base_model": row.base_model,
            "tags": getattr(row, "tags", None),
            "supplier_info": getattr(row, "supplier_info", None),
            "config": _strip_billing_from_config(row.config),
            "billing_unit_type": billing.get("unit_type", "per_call"),
            "billing_cost": billing.get("cost", 0),
            "billing_cost_input": billing.get("cost_input", 0),
            "billing_cost_output": billing.get("cost_output", 0),
            "deprecated": bool(row.deprecated),
            "is_active": is_task_default_system_setting(db, int(row.id), row.category),
            **modality_fields,
        })

    return {
        "version": 1,
        "exported_at": now_bj_iso(),
        "count": len(rows),
        "items": items,
    }


@router.post("/settings/system/manage/export-seed")
def export_system_settings_to_seed_file(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Write current system_api_settings to the seed JSON file (for deploy sync)."""
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    _ensure_builtin_system_settings(db)
    if _is_system_api_auto_billing_sync_enabled():
        _migrate_system_api_pricing_to_base_rules(db)
    db.commit()

    rows = db.query(SystemAPISetting).filter(
        ~SystemAPISetting.category.like("System_%"),
    ).order_by(
        SystemAPISetting.category.asc(),
        SystemAPISetting.provider.asc(),
        SystemAPISetting.model.asc(),
        SystemAPISetting.id.asc(),
    ).all()

    items = []
    for row in rows:
        config = _strip_billing_from_config(row.config)
        billing = _resolve_system_setting_billing(db, row)
        modality_fields = _extract_modality_manage_fields(getattr(row, "modality", None))
        items.append({
            "name": row.name,
            "category": row.category,
            "provider": row.provider,
            "base_url": row.base_url,
            "model": row.model,
            "base_model": row.base_model,
            "modality": row.modality,
            "tags": getattr(row, "tags", None),
            "supplier_info": getattr(row, "supplier_info", None),
            "config": config,
            "billing_unit_type": billing.get("unit_type", "per_call"),
            "billing_cost": billing.get("cost", 0),
            "billing_cost_input": billing.get("cost_input", 0),
            "billing_cost_output": billing.get("cost_output", 0),
            "deprecated": bool(row.deprecated),
            "is_active": is_task_default_system_setting(db, int(row.id), row.category),
            **modality_fields,
        })

    seed_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "system_api_seed.json"))
    os.makedirs(os.path.dirname(seed_path), exist_ok=True)
    with open(seed_path, "w", encoding="utf-8") as f:
        json.dump({
            "version": 1,
            "exported_at": now_bj_iso(),
            "count": len(items),
            "items": items,
        }, f, ensure_ascii=False, indent=2)

    return {"ok": True, "count": len(items), "path": seed_path}


@router.get("/settings/system/manage/provider-bundle/export")
def export_system_provider_bundle_for_manage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    rows = db.query(SystemAPISetting).filter(
        ~SystemAPISetting.category.like("System_%"),
    ).order_by(SystemAPISetting.provider.asc(), SystemAPISetting.category.asc(), SystemAPISetting.model.asc(), SystemAPISetting.id.asc()).all()
    providers = _build_provider_bundle_export_payload(db, rows)

    return {
        "version": 1,
        "format": "provider_bundle",
        "exported_at": now_bj_iso(),
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
                ~SystemAPISetting.category.like("System_%"),
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
                if _is_system_reserved_category(category):
                    skipped_models += 1
                    continue
                model = str(model_item.model or "").strip()
                if not model:
                    skipped_models += 1
                    continue

                target = _find_system_setting_by_normalized_triplet(db, provider_name, category, model)

                raw_model_cfg = model_item.config if isinstance(model_item.config, dict) else {}
                model_billing = _billing_from_payload_or_config(model_item, raw_model_cfg)
                clean_model_cfg = _strip_billing_from_config(raw_model_cfg)

                if target:
                    target.name = (model_item.name or target.name or "System Setting").strip() or "System Setting"
                    target.base_url = model_item.base_url
                    target.model = model
                    target.base_model = _resolve_base_model(getattr(model_item, "base_model", None), model)
                    _assign_wide_modality_fields(target, model_item)
                    target.modality = _build_modality_payload_from_item(model_item)
                    target.tags = getattr(model_item, "tags", None)
                    target.supplier_info = getattr(model_item, "supplier_info", None) or target.supplier_info
                    target.config = clean_model_cfg
                    target.deprecated = _is_setting_deprecated(target.config, model_item.deprecated)
                    target.is_active = bool(target.is_active)
                    _clear_row_billing_columns(target)
                    if _is_system_api_auto_billing_sync_enabled():
                        _upsert_base_billing_rule(db, target.id, target.category, model_billing, activate=True)
                        _refresh_has_granular_billing_rules_flag(db, target.id)
                    updated += 1
                else:
                    target = SystemAPISetting(
                        name=(model_item.name or "System Setting").strip() or "System Setting",
                        category=category,
                        provider=provider_name,
                        api_key="",
                        base_url=model_item.base_url,
                        model=model,
                        base_model=_resolve_base_model(getattr(model_item, "base_model", None), model),
                        modality=_build_modality_payload_from_item(model_item),
                        tags=getattr(model_item, "tags", None),
                        supplier_info=getattr(model_item, "supplier_info", None),
                        deprecated=_is_setting_deprecated(clean_model_cfg, model_item.deprecated),
                        config=clean_model_cfg,
                        is_active=False,
                    )
                    _assign_wide_modality_fields(target, model_item)
                    _clear_row_billing_columns(target)
                    db.add(target)
                    db.flush()
                    if _is_system_api_auto_billing_sync_enabled():
                        _upsert_base_billing_rule(db, target.id, target.category, model_billing, activate=True)
                        _refresh_has_granular_billing_rules_flag(db, target.id)
                    created += 1

                if bool(model_item.is_active):
                    last_active_id_by_category[category] = target.id

            provider_rows = db.query(SystemAPISetting).filter(
                SystemAPISetting.provider == provider_name,
                ~SystemAPISetting.category.like("System_%"),
            ).all()
            if provider_rows:
                _apply_provider_key_bundle_to_rows(db, provider_name, keys, strategy, weights)
                key_updated_providers += 1

        for category, keep_id in last_active_id_by_category.items():
            upsert_task_default_system_setting(db, category, int(keep_id))

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


@router.post("/settings/system/manage/provider-bundle/validate")
def validate_system_provider_bundle_for_manage(
    payload: SystemAPIProviderImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    providers = payload.providers or []
    return _validate_provider_bundle_payload(providers)


_SYNC_BILLING_RULE_FIELDS = [
    "name",
    "description",
    "is_active",
    "priority",
    "applies_to_text",
    "applies_to_image",
    "applies_to_video",
    "generation_mode",
    "input_format",
    "output_format",
    "has_audio",
    "input_tokens_min",
    "input_tokens_max",
    "output_tokens_min",
    "output_tokens_max",
    "total_tokens_min",
    "total_tokens_max",
    "image_count_min",
    "image_count_max",
    "width_min",
    "width_max",
    "height_min",
    "height_max",
    "pixels_min",
    "pixels_max",
    "duration_seconds_min",
    "duration_seconds_max",
    "fps_min",
    "fps_max",
    "billing_unit_type",
    "billing_cost",
    "billing_cost_input",
    "billing_cost_output",
    "charge_multiplier",
    "extra_conditions",
]

_SYNC_BILLING_RULE_BOOL_FIELDS = {
    "is_active",
    "applies_to_text",
    "applies_to_image",
    "applies_to_video",
}
_SYNC_BILLING_RULE_INT_FIELDS = {
    "priority",
    "input_tokens_min",
    "input_tokens_max",
    "output_tokens_min",
    "output_tokens_max",
    "total_tokens_min",
    "total_tokens_max",
    "image_count_min",
    "image_count_max",
    "width_min",
    "width_max",
    "height_min",
    "height_max",
    "pixels_min",
    "pixels_max",
    "billing_cost",
    "billing_cost_input",
    "billing_cost_output",
}
_SYNC_BILLING_RULE_FLOAT_FIELDS = {
    "duration_seconds_min",
    "duration_seconds_max",
    "fps_min",
    "fps_max",
    "charge_multiplier",
}


def _list_config_sync_exportable_system_rows(db: Session) -> Tuple[List[SystemAPISetting], int]:
    rows = db.query(SystemAPISetting).filter(
        ~SystemAPISetting.category.like("System_%"),
    ).order_by(
        SystemAPISetting.provider.asc(),
        SystemAPISetting.category.asc(),
        SystemAPISetting.model.asc(),
        SystemAPISetting.id.asc(),
    ).all()

    exportable_rows: List[SystemAPISetting] = []
    excluded_deprecated = 0
    for row in rows:
        if _is_setting_deprecated(getattr(row, "config", None), getattr(row, "deprecated", None)):
            excluded_deprecated += 1
            continue
        exportable_rows.append(row)

    return exportable_rows, excluded_deprecated


def _build_provider_bundle_export_payload(db: Session, rows: List[SystemAPISetting]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[SystemAPISetting]] = {}
    for row in rows:
        provider_name = str(getattr(row, "provider", "") or "").strip()
        if not provider_name:
            continue
        grouped.setdefault(provider_name, []).append(row)

    providers: List[Dict[str, Any]] = []
    for provider_name, provider_rows in grouped.items():
        pool_info = _get_system_provider_key_pool_full(db, provider_name)
        models = []
        for row in provider_rows:
            billing = _resolve_system_setting_billing(db, row)
            models.append({
                "fixed_id": int(row.id),
                "id": int(row.id),
                "name": row.name,
                "category": row.category,
                "base_url": row.base_url,
                "model": row.model,
                "base_model": row.base_model,
                "modality": row.modality,
                "tags": getattr(row, "tags", None),
                "supplier_info": getattr(row, "supplier_info", None),
                "config": _strip_billing_from_config(row.config),
                "billing_unit_type": billing.get("unit_type", "per_call"),
                "billing_cost": billing.get("cost", 0),
                "billing_cost_input": billing.get("cost_input", 0),
                "billing_cost_output": billing.get("cost_output", 0),
                "deprecated": bool(row.deprecated),
                "is_active": is_task_default_system_setting(db, int(row.id), row.category),
            })
        providers.append({
            "provider": provider_name,
            "api_keys": pool_info["keys"],
            "strategy": pool_info["strategy"],
            "weights": pool_info["weights"],
            "model_count": len(models),
            "models": models,
        })

    return providers


def _db_has_table(db: Session, table_name: str) -> bool:
    try:
        # Isolate metadata probe errors so failed reflection does not poison
        # the caller transaction (InFailedSqlTransaction on PostgreSQL).
        with db.begin_nested():
            conn = db.connection()
            return bool(inspect(conn).has_table(table_name))
    except Exception:
        return False


_SQLITE_LOCK_RETRY_DELAYS = (0.35, 0.8, 1.5)


def _is_sqlite_locked_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    return "sqlite" in text and "database is locked" in text


def _run_sqlite_lock_retry(db: Session, label: str, operation):
    for attempt, delay in enumerate((0.0, *_SQLITE_LOCK_RETRY_DELAYS), start=1):
        try:
            with db.begin_nested():
                return operation()
        except OperationalError as exc:
            if not _is_sqlite_locked_error(exc) or attempt > len(_SQLITE_LOCK_RETRY_DELAYS):
                raise
            logger.warning(
                "Retrying %s after SQLite lock (%s/%s) in %.2fs",
                label,
                attempt,
                len(_SQLITE_LOCK_RETRY_DELAYS) + 1,
                delay,
            )
            time.sleep(delay)


def _require_billing_rules_table(db: Session, *, allow_missing: bool = False) -> bool:
    has_table = _db_has_table(db, "system_api_billing_rules")
    if has_table:
        return True
    if allow_missing:
        return False
    raise HTTPException(status_code=409, detail="system_api_billing_rules table not found in current database schema")


def _rebuild_sync_config_tables_for_replace_all(db: Session) -> Dict[str, bool]:
    """Drop and recreate sync-config tables to enforce strict schema/data consistency."""
    rebuilt = {
        "system_api_settings": False,
        "system_api_billing_rules": False,
        "provider_key_pool": False,
        "smtp_system_configs": False,
        "wechat_pay_configs": False,
        "system_task_default_apis": False,
    }

    drop_table_specs = [
        ("system_api_billing_rules", SystemAPIBillingRule),
        ("system_task_default_apis", TaskDefaultSystemAPI),
        ("system_api_settings", SystemAPISetting),
        ("provider_key_pool", ProviderKeyPool),
        ("smtp_system_configs", SMTPSystemConfig),
        ("wechat_pay_configs", WechatPayConfig),
    ]

    create_table_specs = [
        ("system_api_settings", SystemAPISetting),
        ("system_api_billing_rules", SystemAPIBillingRule),
        ("provider_key_pool", ProviderKeyPool),
        ("smtp_system_configs", SMTPSystemConfig),
        ("wechat_pay_configs", WechatPayConfig),
    ]
    if HAS_TASK_DEFAULT_SYSTEM_API_MODEL:
        drop_table_specs = [spec for spec in drop_table_specs if spec[0] != "system_task_default_apis"] + [("system_task_default_apis", TaskDefaultSystemAPI)]
        create_table_specs.append(("system_task_default_apis", TaskDefaultSystemAPI))
    else:
        drop_table_specs = [spec for spec in drop_table_specs if spec[0] != "system_task_default_apis"]

    bind = db.get_bind()
    dialect_name = str(getattr(getattr(bind, "dialect", None), "name", "") or "").lower()
    use_cascade = dialect_name == "postgresql"

    with bind.begin() as conn:
        inspector = inspect(conn)

        for table_name, _model_cls in drop_table_specs:
            try:
                if inspector.has_table(table_name):
                    drop_sql = f"DROP TABLE IF EXISTS {table_name} CASCADE" if use_cascade else f"DROP TABLE IF EXISTS {table_name}"
                    conn.execute(text(drop_sql))
            except Exception as exc:
                logger.warning("Failed to rebuild table %s during sync replace_all: %s", table_name, exc)

        for table_name, model_cls in create_table_specs:
            try:
                model_cls.__table__.create(bind=conn, checkfirst=True)
            except Exception as exc:
                logger.warning("Failed to rebuild table %s during sync replace_all: %s", table_name, exc)

        inspector = inspect(conn)
        for table_name, _model_cls in create_table_specs:
            rebuilt[table_name] = bool(inspector.has_table(table_name))

    db.expire_all()

    if not rebuilt.get("system_api_settings"):
        raise RuntimeError("replace_all rebuild failed: system_api_settings table was not recreated")

    return rebuilt


def _safe_clear_transaction_action_rule_links(db: Session, *, clear_system_api_ids: Optional[List[int]] = None, clear_rule_ids: Optional[List[int]] = None) -> None:
    # Older deployments may not have the transaction_action table or newer columns.
    if not _db_has_table(db, "transaction_action"):
        return
    try:
        def _cleanup() -> None:
            if clear_system_api_ids:
                db.query(TransactionAction).filter(
                    TransactionAction.system_api_id.in_(clear_system_api_ids),
                ).update({"system_api_id": None}, synchronize_session=False)
            if clear_rule_ids:
                db.query(TransactionAction).filter(
                    TransactionAction.matched_rule_id.in_(clear_rule_ids),
                ).update({"matched_rule_id": None}, synchronize_session=False)
        # Isolate legacy-schema failures so PostgreSQL transactions are not left
        # in aborted state (InFailedSqlTransaction) for subsequent queries.
        _run_sqlite_lock_retry(db, "transaction_action cleanup", _cleanup)
    except Exception as exc:
        logger.warning("Skip transaction_action cleanup due to schema mismatch: %s", exc)


def _normalize_sync_billing_rule_field(field_name: str, raw_value: Any) -> Any:
    if field_name == "name":
        text = str(raw_value or "").strip()
        return text or "Rule"
    if field_name == "description":
        text = str(raw_value or "").strip()
        return text or None
    if field_name == "billing_unit_type":
        text = str(raw_value or "").strip()
        return text or "per_call"
    if field_name == "has_audio":
        if raw_value is None:
            return None
        if isinstance(raw_value, str) and raw_value.strip().lower() in {"", "none", "null"}:
            return None
        return _to_bool(raw_value)
    if field_name == "extra_conditions":
        return _safe_json_dict(raw_value)
    if field_name in _SYNC_BILLING_RULE_BOOL_FIELDS:
        return _to_bool(raw_value)
    if field_name in _SYNC_BILLING_RULE_INT_FIELDS:
        if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
            return 0 if field_name in {"priority", "billing_cost", "billing_cost_input", "billing_cost_output"} else None
        try:
            return int(float(raw_value))
        except Exception:
            return 0 if field_name in {"priority", "billing_cost", "billing_cost_input", "billing_cost_output"} else None
    if field_name in _SYNC_BILLING_RULE_FLOAT_FIELDS:
        if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
            return 2.0 if field_name == "charge_multiplier" else None
        try:
            return float(raw_value)
        except Exception:
            return 2.0 if field_name == "charge_multiplier" else None

    text = str(raw_value or "").strip()
    return text or None


def _clear_non_system_settings_for_replace_all(db: Session) -> None:
    # Delete non-System API settings in FK-safe order.
    target_ids = [
        int(row_id)
        for row_id, in db.query(SystemAPISetting.id).filter(
            ~SystemAPISetting.category.like("System_%"),
        ).all()
    ]
    if not target_ids:
        return

    if _db_has_table(db, "system_task_default_apis"):
        clear_task_defaults_for_system_api_ids(db, target_ids)

    has_billing_rules_table = _db_has_table(db, "system_api_billing_rules")
    rule_ids: List[int] = []
    if has_billing_rules_table:
        rule_ids = [
            int(rule_id)
            for rule_id, in db.query(SystemAPIBillingRule.id).filter(
                SystemAPIBillingRule.system_api_id.in_(target_ids),
            ).all()
        ]

    _safe_clear_transaction_action_rule_links(
        db,
        clear_system_api_ids=target_ids,
        clear_rule_ids=rule_ids,
    )

    if has_billing_rules_table:
        _run_sqlite_lock_retry(
            db,
            "replace_all delete billing rules",
            lambda: db.query(SystemAPIBillingRule).filter(
                SystemAPIBillingRule.system_api_id.in_(target_ids),
            ).delete(synchronize_session=False),
        )

    _run_sqlite_lock_retry(
        db,
        "replace_all delete system_api_settings",
        lambda: db.query(SystemAPISetting).filter(
            SystemAPISetting.id.in_(target_ids),
        ).delete(synchronize_session=False),
    )

    _run_sqlite_lock_retry(db, "replace_all flush non-system settings", db.flush)


def _prepare_sync_replace_all_state(db: Session) -> Dict[str, bool]:
    target_ids = [
        int(row_id)
        for row_id, in db.query(SystemAPISetting.id).all()
    ]

    if target_ids:
        rule_ids: List[int] = []
        if _db_has_table(db, "system_api_billing_rules"):
            rule_ids = [
                int(rule_id)
                for rule_id, in db.query(SystemAPIBillingRule.id).filter(
                    SystemAPIBillingRule.system_api_id.in_(target_ids),
                ).all()
            ]

        _safe_clear_transaction_action_rule_links(
            db,
            clear_system_api_ids=target_ids,
            clear_rule_ids=rule_ids,
        )

    db.commit()

    return _rebuild_sync_config_tables_for_replace_all(db)


def _import_provider_bundle_no_commit(
    db: Session,
    providers: List[Any],
    replace_all: bool,
    *,
    sync_base_billing_rules: bool = True,
    sync_provider_keys: bool = True,
) -> Dict[str, int]:
    if replace_all:
        _clear_non_system_settings_for_replace_all(db)

    created = 0
    updated = 0
    key_updated_providers = 0
    providers_processed = 0
    skipped_models = 0

    def _as_object(item: Any) -> Any:
        if isinstance(item, dict):
            return SimpleNamespace(**item)
        return item

    for provider_item_raw in providers:
        provider_item = _as_object(provider_item_raw)
        provider_name = str(getattr(provider_item, "provider", "") or "").strip()
        if not provider_name:
            continue

        providers_processed += 1
        keys = _normalize_api_keys(getattr(provider_item, "api_keys", []) or [])
        strategy = _normalize_key_strategy(getattr(provider_item, "strategy", None))
        weights = _normalize_key_weights(getattr(provider_item, "weights", None), keys)
        models = getattr(provider_item, "models", []) or []
        if isinstance(models, dict):
            models = [models]

        for model_item_raw in models:
            model_item = _as_object(model_item_raw)
            category = str(getattr(model_item, "category", "LLM") or "LLM").strip() or "LLM"
            if _is_system_reserved_category(category):
                skipped_models += 1
                continue
            model = str(getattr(model_item, "model", "") or "").strip()
            if not model:
                skipped_models += 1
                continue

            fixed_id_raw = getattr(model_item, "fixed_id", None)
            if fixed_id_raw in (None, ""):
                fixed_id_raw = getattr(model_item, "id", None)
            fixed_id = _safe_int(fixed_id_raw, None)
            if isinstance(fixed_id, int) and fixed_id <= 0:
                fixed_id = None

            target = _find_system_setting_by_normalized_triplet(db, provider_name, category, model)

            raw_model_cfg = getattr(model_item, "config", {}) if isinstance(getattr(model_item, "config", {}), dict) else {}
            model_billing = _billing_from_payload_or_config(model_item, raw_model_cfg)
            clean_model_cfg = _strip_billing_from_config(raw_model_cfg)

            if target:
                target.name = (getattr(model_item, "name", None) or target.name or "System Setting").strip() or "System Setting"
                target.base_url = getattr(model_item, "base_url", None)
                target.model = model
                target.base_model = _resolve_base_model(getattr(model_item, "base_model", None), model)
                _assign_wide_modality_fields(target, model_item)
                target.modality = _build_modality_payload_from_item(model_item)
                target.tags = getattr(model_item, "tags", None)
                target.supplier_info = getattr(model_item, "supplier_info", None) or target.supplier_info
                target.config = clean_model_cfg
                target.deprecated = _is_setting_deprecated(target.config, getattr(model_item, "deprecated", None))
                target.is_active = bool(target.is_active)
                _clear_row_billing_columns(target)
                if sync_base_billing_rules and _is_system_api_auto_billing_sync_enabled():
                    _upsert_base_billing_rule(db, target.id, target.category, model_billing, activate=True)
                    _refresh_has_granular_billing_rules_flag(db, target.id)
                updated += 1
            else:
                insert_payload = {
                    "name": (getattr(model_item, "name", None) or "System Setting").strip() or "System Setting",
                    "category": category,
                    "provider": provider_name,
                    "api_key": "",
                    "base_url": getattr(model_item, "base_url", None),
                    "model": model,
                    "base_model": _resolve_base_model(getattr(model_item, "base_model", None), model),
                    "modality": _build_modality_payload_from_item(model_item),
                    "tags": getattr(model_item, "tags", None),
                    "supplier_info": getattr(model_item, "supplier_info", None),
                    "deprecated": _is_setting_deprecated(clean_model_cfg, getattr(model_item, "deprecated", None)),
                    "config": clean_model_cfg,
                    "is_active": False,
                }
                if fixed_id is not None:
                    insert_payload["id"] = int(fixed_id)
                target = _insert_system_setting_schema_safe(
                    db,
                    insert_payload,
                    provider=provider_name,
                    category=category,
                    model=model,
                )
                if not target:
                    # Fallback to ORM path if schema-safe path could not produce row.
                    target = SystemAPISetting(**insert_payload)
                    _assign_wide_modality_fields(target, model_item)
                    _clear_row_billing_columns(target)
                    db.add(target)
                    db.flush()
                if sync_base_billing_rules and _is_system_api_auto_billing_sync_enabled():
                    _upsert_base_billing_rule(db, target.id, target.category, model_billing, activate=True)
                    _refresh_has_granular_billing_rules_flag(db, target.id)
                created += 1

        provider_query = db.query(SystemAPISetting)
        try:
            existing_cols = {
                str(col.get("name") or "").strip()
                for col in inspect(db.bind).get_columns("system_api_settings")
                if isinstance(col, dict)
            }
            mapper = inspect(SystemAPISetting)
            attrs = []
            for attr in mapper.column_attrs:
                cols = getattr(attr, "columns", None) or []
                if not cols:
                    continue
                col_name = str(getattr(cols[0], "name", "") or "").strip()
                if col_name and col_name in existing_cols:
                    attrs.append(getattr(SystemAPISetting, attr.key))
            if attrs:
                provider_query = provider_query.options(load_only(*attrs))
        except Exception:
            pass

        provider_rows = provider_query.filter(
            SystemAPISetting.provider == provider_name,
            ~SystemAPISetting.category.like("System_%"),
        ).all()
        if sync_provider_keys and provider_rows:
            _apply_provider_key_bundle_to_rows(db, provider_name, keys, strategy, weights)
            key_updated_providers += 1

    return {
        "providers": providers_processed,
        "created": created,
        "updated": updated,
        "key_updated_providers": key_updated_providers,
        "skipped_models": skipped_models,
    }


@router.get("/settings/system/manage/sync/export")
def export_system_config_sync_bundle_for_manage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    system_rows, excluded_deprecated_system_apis = _list_config_sync_exportable_system_rows(db)
    provider_bundle = {
        "providers": _build_provider_bundle_export_payload(db, system_rows),
    }
    system_map = {int(row.id): row for row in system_rows}

    billing_rules_payload: List[Dict[str, Any]] = []
    if _db_has_table(db, "system_api_billing_rules"):
        rule_rows = db.query(SystemAPIBillingRule).order_by(
            SystemAPIBillingRule.system_api_id.asc(),
            SystemAPIBillingRule.id.asc(),
        ).all()
        for rule in rule_rows:
            api_row = system_map.get(int(rule.system_api_id))
            if not api_row:
                continue
            entry = {
                "system_api_ref": {
                    "provider": api_row.provider if api_row else None,
                    "category": api_row.category if api_row else None,
                    "model": api_row.model if api_row else None,
                },
                "created_at": rule.created_at,
                "updated_at": rule.updated_at,
            }
            for field_name in _SYNC_BILLING_RULE_FIELDS:
                entry[field_name] = getattr(rule, field_name)
            billing_rules_payload.append(entry)
    else:
        logger.warning("Skip sync export billing rules: table system_api_billing_rules not found")

    provider_key_pools_payload = []
    if _db_has_table(db, "provider_key_pool"):
        provider_key_pool_rows = db.query(ProviderKeyPool).order_by(ProviderKeyPool.provider.asc(), ProviderKeyPool.id.asc()).all()
        provider_key_pools_payload = [
            {
                "provider": row.provider,
                "provider_alias": str(getattr(row, "provider_alias", "") or "").strip() or None,
                "api_keys": _normalize_api_keys(row.api_keys),
                "strategy": _normalize_key_strategy(row.strategy),
                "weights": row.weights if row.weights else [],
                "intro_url": _normalize_optional_http_url(getattr(row, "intro_url", None)),
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            for row in provider_key_pool_rows
        ]
    else:
        logger.warning("Skip sync export provider key pools: table provider_key_pool not found")

    smtp_payload = []
    if _db_has_table(db, "smtp_system_configs"):
        smtp_rows = db.query(SMTPSystemConfig).order_by(SMTPSystemConfig.id.asc()).all()
        smtp_payload = [
            {
                "host": str(row.host or "").strip(),
                "port": int(row.port or 587),
                "username": str(row.username or "").strip(),
                "password": str(row.password or ""),
                "use_ssl": bool(row.use_ssl),
                "use_tls": bool(row.use_tls),
                "from_email": str(row.from_email or "").strip(),
                "frontend_base_url": str(row.frontend_base_url or "").strip(),
                "is_active": bool(getattr(row, "is_active", True)),
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            for row in smtp_rows
        ]
    else:
        logger.warning("Skip sync export SMTP configs: table smtp_system_configs not found")

    wechat_payload = []
    if _db_has_table(db, "wechat_pay_configs"):
        wechat_rows = db.query(WechatPayConfig).order_by(WechatPayConfig.id.asc()).all()
        wechat_payload = [
            {
                "mchid": str(row.mchid or "").strip(),
                "appid": str(row.appid or "").strip(),
                "api_v3_key": str(row.api_v3_key or "").strip(),
                "cert_serial_no": str(row.cert_serial_no or "").strip(),
                "private_key": str(row.private_key or ""),
                "notify_url": str(row.notify_url or "").strip(),
                "use_mock": bool(row.use_mock),
                "is_active": bool(row.is_active),
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            for row in wechat_rows
        ]
    else:
        logger.warning("Skip sync export WeChat pay configs: table wechat_pay_configs not found")

    task_default_payload: List[Dict[str, Any]] = []
    if HAS_TASK_DEFAULT_SYSTEM_API_MODEL and _db_has_table(db, "system_task_default_apis"):
        task_default_rows = db.query(TaskDefaultSystemAPI).order_by(TaskDefaultSystemAPI.task_category.asc()).all()
        for row in task_default_rows:
            api_row = system_map.get(int(getattr(row, "system_api_id", 0) or 0))
            if not api_row:
                continue
            task_default_payload.append({
                "task_category": normalize_task_category(getattr(row, "task_category", None)),
                "system_api_id": int(getattr(row, "system_api_id", 0) or 0),
                "system_api_ref": {
                    "provider": str(getattr(api_row, "provider", "") or "").strip() or None,
                    "category": str(getattr(api_row, "category", "") or "").strip() or None,
                    "model": str(getattr(api_row, "model", "") or "").strip() or None,
                },
                "created_at": getattr(row, "created_at", None),
                "updated_at": getattr(row, "updated_at", None),
            })
    else:
        if HAS_TASK_DEFAULT_SYSTEM_API_MODEL:
            logger.warning("Skip sync export dedicated task defaults table: table system_task_default_apis not found, fallback to SystemAPISetting.is_active")
        # Legacy fallback: export inferred defaults from active settings.
        active_rows = db.query(SystemAPISetting).filter(
            SystemAPISetting.is_active == True,
            ~SystemAPISetting.category.like("System_%"),
        ).order_by(SystemAPISetting.id.desc()).all()
        seen = set()
        for row in active_rows:
            if _is_setting_deprecated(getattr(row, "config", None), getattr(row, "deprecated", None)):
                continue
            task_category = normalize_task_category(getattr(row, "category", None))
            if task_category in seen:
                continue
            seen.add(task_category)
            task_default_payload.append({
                "task_category": task_category,
                "system_api_id": int(getattr(row, "id", 0) or 0),
                "system_api_ref": {
                    "provider": str(getattr(row, "provider", "") or "").strip() or None,
                    "category": str(getattr(row, "category", "") or "").strip() or None,
                    "model": str(getattr(row, "model", "") or "").strip() or None,
                },
                "created_at": None,
                "updated_at": None,
            })

    data = {
        "providers": provider_bundle.get("providers", []),
        "billing_rules": billing_rules_payload,
        "provider_key_pools": provider_key_pools_payload,
        "smtp_configs": smtp_payload,
        "wechat_pay_configs": wechat_payload,
        "task_default_apis": task_default_payload,
    }

    return {
        "version": 1,
        "format": "system_config_sync_bundle",
        "exported_at": now_bj_iso(),
        "summary": {
            "providers": len(data["providers"]),
            "billing_rules": len(data["billing_rules"]),
            "provider_key_pools": len(data["provider_key_pools"]),
            "smtp_configs": len(data["smtp_configs"]),
            "wechat_pay_configs": len(data["wechat_pay_configs"]),
            "task_default_apis": len(data["task_default_apis"]),
            "excluded_deprecated_system_apis": excluded_deprecated_system_apis,
        },
        "data": data,
    }


@router.post("/settings/system/manage/sync/import")
def import_system_config_sync_bundle_for_manage(
    payload: SystemConfigSyncBundleImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    data = payload.data or {}
    providers = data.get("providers") if isinstance(data.get("providers"), list) else []
    billing_rules = data.get("billing_rules") if isinstance(data.get("billing_rules"), list) else []
    provider_key_pools = data.get("provider_key_pools") if isinstance(data.get("provider_key_pools"), list) else []
    smtp_configs = data.get("smtp_configs") if isinstance(data.get("smtp_configs"), list) else []
    wechat_pay_configs = data.get("wechat_pay_configs") if isinstance(data.get("wechat_pay_configs"), list) else []
    task_default_apis = data.get("task_default_apis") if isinstance(data.get("task_default_apis"), list) else []
    kie_standard_values_ignored = len(data.get("kie_standard_values") or []) if isinstance(data.get("kie_standard_values"), list) else 0
    kie_standard_mappings_ignored = len(data.get("kie_standard_mappings") or []) if isinstance(data.get("kie_standard_mappings"), list) else 0

    replace_all = bool(payload.replace_all)
    if replace_all and not bool(getattr(payload, "confirm_clear_existing", False)):
        raise HTTPException(
            status_code=400,
            detail="confirm_clear_existing=true is required when replace_all=true",
        )

    try:
        def _safe_int(raw_value: Any, default_value: int) -> int:
            try:
                return int(float(raw_value))
            except Exception:
                return int(default_value)

        has_billing_rules_table = _db_has_table(db, "system_api_billing_rules")
        has_provider_key_pool_table = _db_has_table(db, "provider_key_pool")
        has_smtp_table = _db_has_table(db, "smtp_system_configs")
        has_wechat_table = _db_has_table(db, "wechat_pay_configs")
        has_task_default_table = HAS_TASK_DEFAULT_SYSTEM_API_MODEL and _db_has_table(db, "system_task_default_apis")
        rebuilt_tables: Dict[str, bool] = {}

        if replace_all:
            rebuilt_tables = _prepare_sync_replace_all_state(db)
            _ensure_builtin_system_settings(db)
            _ensure_settings_system_indexes(db)
            has_billing_rules_table = _db_has_table(db, "system_api_billing_rules")
            has_provider_key_pool_table = _db_has_table(db, "provider_key_pool")
            has_smtp_table = _db_has_table(db, "smtp_system_configs")
            has_wechat_table = _db_has_table(db, "wechat_pay_configs")
            has_task_default_table = HAS_TASK_DEFAULT_SYSTEM_API_MODEL and _db_has_table(db, "system_task_default_apis")

        tx_ctx = db.begin_nested() if db.in_transaction() else db.begin()
        with tx_ctx:

            provider_items = []
            for raw in providers:
                if not isinstance(raw, dict):
                    continue
                provider_items.append(raw)
            provider_import_items: List[Any] = provider_items
            try:
                provider_req = SystemAPIProviderImportRequest(providers=provider_items, replace_all=replace_all)
                provider_import_items = provider_req.providers or []
            except Exception as parse_exc:
                logger.warning("Provider bundle parse warning, fallback to permissive import: %s", parse_exc)
            provider_result = None
            try:
                provider_result = _import_provider_bundle_no_commit(
                    db,
                    provider_import_items,
                    False,
                    sync_base_billing_rules=not replace_all,
                    sync_provider_keys=False,
                )
            except Exception:
                raise

            system_index: Dict[Tuple[str, str, str], int] = {}
            system_rows = db.execute(text("""
                SELECT id, provider, category, model
                FROM system_api_settings
                WHERE category NOT LIKE 'System_%'
            """)).mappings().all()
            for row in system_rows:
                provider_name = _normalize_system_provider_name(row.get("provider"))
                category_name = str(row.get("category") or "").strip()
                model_name = str(row.get("model") or "").strip()
                if provider_name and category_name and model_name:
                    system_index[(provider_name, category_name, model_name)] = int(row.get("id") or 0)

            billing_created = 0
            billing_skipped = 0
            default_created = 0
            default_skipped = 0
            now_iso = now_bj_iso()
            if has_billing_rules_table:
                for raw_rule in billing_rules:
                    if not isinstance(raw_rule, dict):
                        billing_skipped += 1
                        continue

                    ref = raw_rule.get("system_api_ref") if isinstance(raw_rule.get("system_api_ref"), dict) else {}
                    provider_name = _normalize_system_provider_name(ref.get("provider"))
                    category_name = str(ref.get("category") or "").strip()
                    model_name = str(ref.get("model") or "").strip()

                    target_api_id = None
                    if provider_name and category_name and model_name:
                        target_api_id = system_index.get((provider_name, category_name, model_name))

                    if not target_api_id:
                        billing_skipped += 1
                        continue

                    new_rule = SystemAPIBillingRule(system_api_id=int(target_api_id))
                    for field_name in _SYNC_BILLING_RULE_FIELDS:
                        if field_name in raw_rule:
                            setattr(new_rule, field_name, _normalize_sync_billing_rule_field(field_name, raw_rule.get(field_name)))
                    new_rule.created_at = str(raw_rule.get("created_at") or now_iso)
                    new_rule.updated_at = str(raw_rule.get("updated_at") or now_iso)
                    db.add(new_rule)
                    billing_created += 1
            else:
                billing_skipped += len(billing_rules)
                if billing_rules:
                    logger.warning("Skip billing rules import: table system_api_billing_rules not found")

            # KIE standard data is intentionally excluded from sync bundle import.
            # Use CLI loader instead (backend/apply_kie_system_data_standard_seed.py).

            provider_pool_created = 0
            provider_pool_updated = 0
            for raw_pool in provider_key_pools:
                if not isinstance(raw_pool, dict):
                    continue
                provider_name = _normalize_system_provider_name(raw_pool.get("provider"))
                if not provider_name:
                    continue
                keys = _normalize_api_keys(raw_pool.get("api_keys"))
                strategy = _normalize_key_strategy(raw_pool.get("strategy"))
                weights = _normalize_key_weights(raw_pool.get("weights"), keys)
                provider_alias = str(raw_pool.get("provider_alias") or "").strip() or None
                intro_url = _normalize_optional_http_url(raw_pool.get("intro_url"))
                updated_at = str(raw_pool.get("updated_at") or now_bj_iso())
                created_at = str(raw_pool.get("created_at") or updated_at)
                existed_before = bool(_get_provider_key_pool_record(db, provider_name)) if has_provider_key_pool_table else False

                _apply_provider_key_bundle_to_rows(
                    db,
                    provider_name,
                    keys,
                    strategy,
                    weights,
                    provider_alias=provider_alias,
                    intro_url=intro_url,
                    created_at=created_at,
                    updated_at=updated_at,
                )

                if has_provider_key_pool_table:
                    if existed_before:
                        provider_pool_updated += 1
                    else:
                        provider_pool_created += 1
            if not has_provider_key_pool_table and provider_key_pools:
                logger.warning("provider_key_pool table not found during sync import; applied primary api_key fallback to system_api_settings only")

            smtp_created = 0
            if has_smtp_table:
                for raw_smtp in smtp_configs:
                    if not isinstance(raw_smtp, dict):
                        continue
                    created_at = str(raw_smtp.get("created_at") or now_bj_iso())
                    row = SMTPSystemConfig(
                        host=str(raw_smtp.get("host") or "").strip(),
                        port=_safe_int(raw_smtp.get("port"), 587),
                        username=str(raw_smtp.get("username") or "").strip(),
                        password=str(raw_smtp.get("password") or ""),
                        use_ssl=bool(raw_smtp.get("use_ssl")),
                        use_tls=bool(raw_smtp.get("use_tls", True)),
                        from_email=str(raw_smtp.get("from_email") or "").strip(),
                        frontend_base_url=str(raw_smtp.get("frontend_base_url") or "").strip(),
                        is_active=bool(raw_smtp.get("is_active", True)),
                        created_at=created_at,
                        updated_at=str(raw_smtp.get("updated_at") or created_at),
                    )
                    db.add(row)
                    smtp_created += 1
            elif smtp_configs:
                logger.warning("Skip SMTP import: table smtp_system_configs not found")

            wechat_created = 0
            if has_wechat_table:
                for raw_wechat in wechat_pay_configs:
                    if not isinstance(raw_wechat, dict):
                        continue
                    created_at = str(raw_wechat.get("created_at") or now_bj_iso())
                    row = WechatPayConfig(
                        mchid=str(raw_wechat.get("mchid") or "").strip(),
                        appid=str(raw_wechat.get("appid") or "").strip(),
                        api_v3_key=str(raw_wechat.get("api_v3_key") or "").strip(),
                        cert_serial_no=str(raw_wechat.get("cert_serial_no") or "").strip(),
                        private_key=str(raw_wechat.get("private_key") or ""),
                        notify_url=str(raw_wechat.get("notify_url") or "").strip(),
                        use_mock=bool(raw_wechat.get("use_mock", True)),
                        is_active=bool(raw_wechat.get("is_active", True)),
                        created_at=created_at,
                        updated_at=str(raw_wechat.get("updated_at") or created_at),
                    )
                    db.add(row)
                    wechat_created += 1
            elif wechat_pay_configs:
                logger.warning("Skip WeChat pay import: table wechat_pay_configs not found")

            resolved_task_default_targets: Dict[str, int] = {}
            for raw_default in task_default_apis:
                if not isinstance(raw_default, dict):
                    default_skipped += 1
                    continue
                task_category = normalize_task_category(raw_default.get("task_category"))
                ref = raw_default.get("system_api_ref") if isinstance(raw_default.get("system_api_ref"), dict) else {}
                provider_name = _normalize_system_provider_name(ref.get("provider"))
                category_name = str(ref.get("category") or "").strip()
                model_name = str(ref.get("model") or "").strip()
                target_api_id = None
                if provider_name and category_name and model_name:
                    target_api_id = system_index.get((provider_name, category_name, model_name))
                if not target_api_id:
                    raw_system_api_id = int(raw_default.get("system_api_id") or 0)
                    if raw_system_api_id > 0:
                        exists = db.query(SystemAPISetting.id).filter(
                            SystemAPISetting.id == raw_system_api_id,
                            ~SystemAPISetting.category.like("System_%"),
                        ).first()
                        if exists:
                            target_api_id = raw_system_api_id
                if not target_api_id:
                    default_skipped += 1
                    continue
                # Keep the latest mapping for each task category to avoid duplicate
                # inserts against unique(task_category) when bundle contains repeats.
                resolved_task_default_targets[task_category] = int(target_api_id)

            for task_category, target_api_id in resolved_task_default_targets.items():
                upsert_task_default_system_setting(db, task_category, int(target_api_id))
                default_created += 1

        # Ensure changes are durably committed for this request scope.
        db.commit()
        _invalidate_system_api_runtime_cache(refresh=True)
        _invalidate_provider_pool_cache()
        return {
            "ok": True,
            "replace_all": replace_all,
            "rebuild_tables": rebuilt_tables,
            "provider_result": provider_result,
            "billing_rules": {
                "created": billing_created,
                "skipped": billing_skipped,
                "skipped_reason": None if has_billing_rules_table else "missing table system_api_billing_rules",
            },
            "provider_key_pools": {
                "created": provider_pool_created,
                "updated": provider_pool_updated,
                "skipped": 0 if has_provider_key_pool_table else len(provider_key_pools),
                "skipped_reason": None if has_provider_key_pool_table else "missing table provider_key_pool",
            },
            "smtp_configs": {
                "created": smtp_created,
                "skipped": 0 if has_smtp_table else len(smtp_configs),
                "skipped_reason": None if has_smtp_table else "missing table smtp_system_configs",
            },
            "wechat_pay_configs": {
                "created": wechat_created,
                "skipped": 0 if has_wechat_table else len(wechat_pay_configs),
                "skipped_reason": None if has_wechat_table else "missing table wechat_pay_configs",
            },
            "task_default_apis": {
                "created_or_updated": default_created,
                "skipped": default_skipped,
                "storage": "system_task_default_apis" if has_task_default_table else "system_api_settings.is_active",
            },
            "kie_standard_data": {
                "imported": 0,
                "ignored_values": kie_standard_values_ignored,
                "ignored_mappings": kie_standard_mappings_ignored,
                "note": "KIE standard data import via sync bundle is disabled; use CLI loader",
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to import system config sync bundle: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
        err_text = str(exc or "").strip()
        if len(err_text) > 240:
            err_text = f"{err_text[:240]}..."
        detail = f"sync bundle import failed: {type(exc).__name__}"
        if err_text:
            detail = f"{detail}: {err_text}"
        raise HTTPException(status_code=500, detail=detail)


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
        _clear_non_system_settings_for_replace_all(db)

    created = 0
    updated = 0
    last_active_id_by_category: Dict[str, int] = {}

    for item in items:
        provider = (item.provider or "").strip()
        category = (item.category or "LLM").strip() or "LLM"
        if _is_system_reserved_category(category):
            continue
        model = (item.model or "").strip()
        if not provider:
            continue

        target = _find_system_setting_by_normalized_triplet(db, provider, category, model)

        if target:
            target.name = (item.name or target.name or "System Setting").strip() or "System Setting"
            target.base_url = item.base_url
            target.model = item.model
            target.base_model = _resolve_base_model(getattr(item, "base_model", None), item.model)
            _assign_wide_modality_fields(target, item)
            target.modality = _build_modality_payload_from_item(item)
            target.tags = getattr(item, "tags", None)
            target.supplier_info = getattr(item, "supplier_info", None) or target.supplier_info
            import_raw_cfg = item.config if isinstance(item.config, dict) else {}
            import_billing = _billing_from_payload_or_config(item, import_raw_cfg)
            target.config = _strip_billing_from_config(import_raw_cfg)
            target.deprecated = _is_setting_deprecated(target.config, item.deprecated)
            target.is_active = bool(item.is_active)
            _clear_row_billing_columns(target)
            if _is_system_api_auto_billing_sync_enabled():
                _upsert_base_billing_rule(db, target.id, target.category, import_billing, activate=True)
                _refresh_has_granular_billing_rules_flag(db, target.id)
            updated += 1
        else:
            create_raw_cfg = item.config if isinstance(item.config, dict) else {}
            create_billing = _billing_from_payload_or_config(item, create_raw_cfg)
            fixed_id_raw = getattr(item, "fixed_id", None)
            if fixed_id_raw in (None, ""):
                fixed_id_raw = getattr(item, "id", None)
            fixed_id = _safe_int(fixed_id_raw, None)
            if isinstance(fixed_id, int) and fixed_id <= 0:
                fixed_id = None
            target = SystemAPISetting(
                name=(item.name or "System Setting").strip() or "System Setting",
                category=category,
                provider=provider,
                api_key="",
                base_url=item.base_url,
                model=item.model,
                base_model=_resolve_base_model(getattr(item, "base_model", None), item.model),
                modality=_build_modality_payload_from_item(item),
                tags=getattr(item, "tags", None),
                supplier_info=getattr(item, "supplier_info", None),
                deprecated=_is_setting_deprecated(create_raw_cfg, item.deprecated),
                config=_strip_billing_from_config(create_raw_cfg),
                is_active=bool(item.is_active),
            )
            if fixed_id is not None:
                target.id = int(fixed_id)
            _assign_wide_modality_fields(target, item)
            _clear_row_billing_columns(target)
            db.add(target)
            db.flush()
            if _is_system_api_auto_billing_sync_enabled():
                _upsert_base_billing_rule(db, target.id, target.category, create_billing, activate=True)
                _refresh_has_granular_billing_rules_flag(db, target.id)
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
        upsert_task_default_system_setting(db, category, int(keep_id))

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

    clear_task_defaults_for_system_api_ids(db, [int(target.id)])
    db.query(SystemAPIBillingRule).filter(SystemAPIBillingRule.system_api_id == target.id).delete(synchronize_session=False)
    db.delete(target)
    db.commit()
    _invalidate_system_api_runtime_cache(refresh=True)
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


# ─── provider_key_pool CRUD ───

@router.get("/settings/system/manage/provider-key-pools", response_model=List[ProviderKeyPoolOut])
def list_provider_key_pools(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    rows = db.query(ProviderKeyPool).order_by(ProviderKeyPool.provider.asc()).all()
    return [
        ProviderKeyPoolOut(
            id=row.id,
            provider=row.provider,
            provider_alias=str(getattr(row, "provider_alias", "") or "").strip() or None,
            api_keys=_normalize_api_keys(row.api_keys),
            strategy=_normalize_key_strategy(row.strategy),
            weights=row.weights if row.weights else [],
            intro_url=_normalize_optional_http_url(getattr(row, "intro_url", None)),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@router.post("/settings/system/manage/provider-key-pools", response_model=ProviderKeyPoolOut)
def create_provider_key_pool(
    payload: ProviderKeyPoolCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    provider_name = _normalize_system_provider_name(payload.provider)
    if not provider_name:
        raise HTTPException(status_code=400, detail="provider is required")

    existing = db.query(ProviderKeyPool).filter(ProviderKeyPool.provider == provider_name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Provider '{provider_name}' already exists in key pool")

    keys = _normalize_api_keys(payload.api_keys)
    strategy = _normalize_key_strategy(payload.strategy)
    weights = _normalize_key_weights(payload.weights, keys)
    now = now_bj_iso()

    record = ProviderKeyPool(
        provider=provider_name,
        provider_alias=str(payload.provider_alias or "").strip() or None,
        api_keys=keys,
        strategy=strategy,
        weights=weights,
        intro_url=_normalize_optional_http_url(payload.intro_url),
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    _invalidate_provider_pool_cache()
    return ProviderKeyPoolOut(
        id=record.id,
        provider=record.provider,
        provider_alias=str(getattr(record, "provider_alias", "") or "").strip() or None,
        api_keys=_normalize_api_keys(record.api_keys),
        strategy=_normalize_key_strategy(record.strategy),
        weights=record.weights if record.weights else [],
        intro_url=_normalize_optional_http_url(getattr(record, "intro_url", None)),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post("/settings/system/manage/provider-key-pools/{pool_id}", response_model=ProviderKeyPoolOut)
def update_provider_key_pool(
    pool_id: int,
    payload: ProviderKeyPoolUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    record = db.query(ProviderKeyPool).filter(ProviderKeyPool.id == pool_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Provider key pool entry not found")

    if payload.provider is not None:
        new_provider = _normalize_system_provider_name(payload.provider)
        if not new_provider:
            raise HTTPException(status_code=400, detail="provider cannot be empty")
        if new_provider != record.provider:
            dup = db.query(ProviderKeyPool).filter(ProviderKeyPool.provider == new_provider).first()
            if dup:
                raise HTTPException(status_code=409, detail=f"Provider '{new_provider}' already exists in key pool")
            record.provider = new_provider
    if payload.api_keys is not None:
        record.api_keys = _normalize_api_keys(payload.api_keys)
    if payload.provider_alias is not None:
        record.provider_alias = str(payload.provider_alias or "").strip() or None
    if payload.strategy is not None:
        record.strategy = _normalize_key_strategy(payload.strategy)
    if payload.weights is not None:
        keys = _normalize_api_keys(record.api_keys)
        record.weights = _normalize_key_weights(payload.weights, keys)
    if payload.intro_url is not None:
        record.intro_url = _normalize_optional_http_url(payload.intro_url)
    record.updated_at = now_bj_iso()
    db.commit()
    db.refresh(record)
    _invalidate_provider_pool_cache()
    return ProviderKeyPoolOut(
        id=record.id,
        provider=record.provider,
        provider_alias=str(getattr(record, "provider_alias", "") or "").strip() or None,
        api_keys=_normalize_api_keys(record.api_keys),
        strategy=_normalize_key_strategy(record.strategy),
        weights=record.weights if record.weights else [],
        intro_url=_normalize_optional_http_url(getattr(record, "intro_url", None)),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.delete("/settings/system/manage/provider-key-pools/{pool_id}")
def delete_provider_key_pool(
    pool_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    record = db.query(ProviderKeyPool).filter(ProviderKeyPool.id == pool_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Provider key pool entry not found")

    db.delete(record)
    db.commit()
    _invalidate_provider_pool_cache()
    return {"ok": True}


@router.get("/settings/defaults")
def get_defaults():
    return DEFAULTS

