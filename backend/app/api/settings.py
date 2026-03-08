from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import cast, String, func
import logging
import json
import os
import ast
import random
import re
from datetime import datetime, timezone
import math
from app.db.session import get_db
from app.models.all_models import (
    APISetting,
    User,
    SystemAPISetting,
    ProviderKeyPool,
    SystemAPIBillingRule,
    TransactionAction,
    SMTPSystemConfig,
    WechatPayConfig,
)
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
    SystemConfigSyncBundleImportRequest,
    AgentToolPolicyUpdate,
    AgentToolPolicyOut,
    SystemAIAssistantRequest,
    SystemAIAssistantResponse,
    SystemAIAssistantSuggestion,
    ExchangeRateRequest,
    ExchangeRateResponse,
    FetchPricingPageRequest,
    FetchPricingPageResponse,
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
)
from app.api.deps import get_current_user
from typing import List, Dict, Tuple, Any, Optional
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

router = APIRouter()
logger = logging.getLogger("settings_api")
logger.setLevel(logging.INFO)

_AGENT_POLICY_CATEGORY = "System_Payment"
_AGENT_POLICY_PROVIDER = "agent_policy"
_AGENT_POLICY_MODEL = "tool_acl"
_BASE_BILLING_RULE_KIND = "base_pricing"
_BASE_BILLING_RULE_PRIORITY = -100000
_KIE_GRANULAR_RULE_KIND = "kie_granular_pricing"
_KIE_HINT_TEMPLATE_LIMIT_PER_MODEL = 6
_KIE_TO_SYSTEM_CREDIT_RATIO = 3.0
_USD_TO_CNY_RATE = 7.0
_SYSTEM_CREDIT_PER_CNY = 100.0


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
    """Convert supplier price (CNY/元) to credits (分).

    Formula: credits = ceil(price_cny * 100 * multiplier)
    100 = 元转分 (1积分 = 1分钱 = 0.01元)
    multiplier = 上浮倍率 (default 2.0, 作为利润)
    """
    base = _safe_non_negative_float(value)
    mul = _safe_non_negative_float(multiplier)
    return max(0, int(math.ceil(base * 100 * (mul if mul > 0 else 1.0))))


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
    if unit in {"cny", "rmb", "yuan", "元", "人民币"}:
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
    rows = db.query(SystemAPISetting).filter(
        SystemAPISetting.category == "LLM",
        SystemAPISetting.is_active == True,
    ).order_by(SystemAPISetting.id.desc()).all()

    for row in rows:
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

        return {
            "provider": row.provider,
            "api_key": runtime_key,
            "base_url": row.base_url or default.get("base_url"),
            "model": row.model or default.get("model"),
            "config": merged_cfg,
        }
    return {}


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
            modality=(item.modality if item.modality else (existing.modality if existing else None)),
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


def _safe_int(value: Any, default: Optional[int] = 0) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return default


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
        }
    return {"keys": [], "strategy": "random", "weights": []}


def _apply_system_provider_key_pool(db: Session, provider: str, keys: List[str]) -> None:
    normalized = _normalize_api_keys(keys)
    provider_name = _normalize_system_provider_name(provider)

    # Upsert provider_key_pool record
    record = db.query(ProviderKeyPool).filter(ProviderKeyPool.provider == provider_name).first()
    if record:
        record.api_keys = normalized
        record.weights = _normalize_key_weights(record.weights, normalized)
        record.updated_at = datetime.utcnow().isoformat()
    else:
        record = ProviderKeyPool(
            provider=provider_name,
            api_keys=normalized,
            strategy="random",
            weights=_normalize_key_weights(None, normalized),
        )
        db.add(record)

    # Sync primary key to all system_api_settings rows for legacy compatibility
    primary_key = normalized[0] if normalized else ""
    rows = db.query(SystemAPISetting).filter(
        _system_provider_case_insensitive_filter(provider_name)
    ).all()
    for row in rows:
        row.provider = provider_name
        row.api_key = primary_key


def _apply_provider_key_bundle_to_rows(db: Session, provider_name: str, keys: List[str], strategy: str, weights: List[float]) -> None:
    """Write full key pool bundle (keys + strategy + weights) to provider_key_pool table and sync api_key on rows."""
    normalized = _normalize_api_keys(keys)
    provider_name = _normalize_system_provider_name(provider_name)

    record = db.query(ProviderKeyPool).filter(ProviderKeyPool.provider == provider_name).first()
    if record:
        record.api_keys = normalized
        record.strategy = strategy
        record.weights = weights
        record.updated_at = datetime.utcnow().isoformat()
    else:
        record = ProviderKeyPool(
            provider=provider_name,
            api_keys=normalized,
            strategy=strategy,
            weights=weights,
        )
        db.add(record)

    primary_key = normalized[0] if normalized else ""
    rows = db.query(SystemAPISetting).filter(
        _system_provider_case_insensitive_filter(provider_name)
    ).all()
    for row in rows:
        row.api_key = primary_key


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
    # Get all active categories the user has configured
    user_active_categories = db.query(APISetting.category).filter(
        APISetting.user_id == user_id,
        APISetting.is_active == True
    ).distinct().all()
    user_active_categories_set = {str(cat[0]).strip() for cat in user_active_categories if cat[0]}

    active_system_rows = db.query(SystemAPISetting).filter(
        SystemAPISetting.is_active == True,
        ~SystemAPISetting.category.like("System_%"),
    ).order_by(SystemAPISetting.category.asc(), SystemAPISetting.id.desc()).all()

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
        marker_config = {
            "selection_source": "system",
            "use_system_setting_id": int(system_setting.id),
        }

        db.add(APISetting(
            user_id=user_id,
            name=f"Use System {system_setting.provider}",
            category=system_setting.category,
            provider=system_setting.provider,
            api_key="",
            base_url="",
            model=system_setting.model,
            config=marker_config,
            is_active=True,
        ))

    db.flush()


def _normalize_user_active_settings(db: Session, user_id: int) -> None:
    rows = db.query(APISetting).filter(
        APISetting.user_id == user_id,
        APISetting.is_active == True,
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
            cfg = _safe_json_dict(item.config)
            selection_source = str((cfg or {}).get("selection_source") or "").strip().lower()
            has_system_setting_id = 1 if _safe_int((cfg or {}).get("use_system_setting_id"), None) else 0
            is_system_selected = 1 if (selection_source == "system" or has_system_setting_id) else 0
            has_model = 1 if str(item.model or "").strip() else 0
            has_provider = 1 if str(item.provider or "").strip() else 0
            return (has_system_setting_id, is_system_selected, has_model, has_provider, int(item.id or 0))

        winner = max(items, key=_score)
        dropped_ids: List[int] = []
        for item in items:
            should_active = (item.id == winner.id)
            if bool(item.is_active) != should_active:
                item.is_active = should_active
                changed = True
            if not should_active:
                dropped_ids.append(item.id)

        logger.warning(
            "Normalize duplicate active api settings | user_id=%s category=%s keep_id=%s drop_ids=%s",
            user_id,
            category,
            winner.id,
            dropped_ids,
        )

    if changed:
        db.flush()


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
    rows = db.query(APISetting).filter(APISetting.user_id == user_id).order_by(APISetting.id.desc()).all()
    if not rows:
        return

    changed = False
    for row in rows:
        normalized_category = _normalize_setting_category_name(row.category)
        if (row.category or "") != normalized_category:
            row.category = normalized_category
            changed = True

        cfg = _safe_json_dict(row.config)
        selection_source = str((cfg or {}).get("selection_source") or "").strip().lower()
        use_system_setting_id = _safe_int((cfg or {}).get("use_system_setting_id"), None)
        is_system_marker = (selection_source == "system") or bool(use_system_setting_id)

        if not is_system_marker:
            continue

        if not use_system_setting_id:
            matched = _find_system_setting_by_normalized_triplet(
                db,
                row.provider,
                normalized_category,
                row.model,
            )
            if matched and not _is_setting_deprecated(matched.config, matched.deprecated):
                use_system_setting_id = int(matched.id)

        next_cfg = {"selection_source": "system"}
        if use_system_setting_id:
            next_cfg["use_system_setting_id"] = int(use_system_setting_id)

        if cfg != next_cfg:
            row.config = next_cfg
            changed = True

        if (row.api_key or "").strip():
            row.api_key = ""
            changed = True
        if (row.base_url or "").strip():
            row.base_url = ""
            changed = True

    if changed:
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
    return db.query(SystemAPISetting).filter(
        func.lower(func.trim(func.coalesce(SystemAPISetting.provider, ""))) == provider_norm,
        func.lower(func.trim(func.coalesce(SystemAPISetting.category, ""))) == category_norm,
        func.lower(func.trim(func.coalesce(SystemAPISetting.model, ""))) == model_norm,
    ).order_by(SystemAPISetting.id.desc()).first()


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


def _collect_kie_system_rule_hints(db: Session, system_rows: List[SystemAPISetting]) -> Dict[int, Dict[str, Any]]:
    ids = [int(getattr(row, "id", 0) or 0) for row in (system_rows or []) if int(getattr(row, "id", 0) or 0) > 0]
    if not ids:
        return {}

    rules = db.query(SystemAPIBillingRule).filter(
        SystemAPIBillingRule.system_api_id.in_(ids),
        SystemAPIBillingRule.is_active == True,
    ).order_by(
        SystemAPIBillingRule.system_api_id.asc(),
        SystemAPIBillingRule.priority.desc(),
        SystemAPIBillingRule.id.desc(),
    ).all()

    hints: Dict[int, Dict[str, Any]] = {int(sid): {
        "has_granular_rules": False,
        "granular_rule_templates": [],
    } for sid in ids}

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
    flags = _category_to_mode_flags(category)
    rule = _get_base_billing_rule(db, system_api_id, include_inactive=True)
    now_iso = datetime.utcnow().isoformat()

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
        rule.charge_multiplier = _normalize_rule_charge_multiplier(getattr(rule, "charge_multiplier", None), default=2.0)
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
        charge_multiplier=2.0,
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
    now_iso = datetime.utcnow().isoformat()
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
    out_cfg = _strip_billing_from_config(row.config)
    modality = row.modality if isinstance(row.modality, dict) else {}
    base_model = str(getattr(row, "base_model", "") or "").strip() or str(modality.get("base_model") or "").strip() or None
    return SystemAPISettingOut(
        id=row.id,
        name=row.name,
        category=row.category,
        provider=row.provider,
        api_key=row.api_key,
        base_url=row.base_url,
        model=row.model,
        base_model=base_model,
        modality=row.modality,
        tags=getattr(row, "tags", None),
        supplier_info=getattr(row, "supplier_info", None),
        config=out_cfg,
        billing_unit_type=billing["unit_type"],
        billing_cost=billing["cost"],
        billing_cost_input=billing["cost_input"],
        billing_cost_output=billing["cost_output"],
        has_granular_billing_rules=_has_granular_billing_rules(db, int(row.id)),
        deprecated=_is_setting_deprecated(out_cfg, row.deprecated),
        is_active=bool(row.is_active),
    )


def _rule_to_out(rule: SystemAPIBillingRule) -> SystemAPIBillingRuleOut:
    if hasattr(SystemAPIBillingRuleOut, "model_validate"):
        return SystemAPIBillingRuleOut.model_validate(rule)
    return SystemAPIBillingRuleOut.from_orm(rule)


def _is_setting_deprecated(config_value, deprecated_flag: Any = None) -> bool:
    if _to_bool(deprecated_flag):
        return True
    cfg = _safe_json_dict(config_value)
    return bool(
        _to_bool(cfg.get("deprecated"))
        or _to_bool(cfg.get("is_deprecated"))
        or _to_bool(cfg.get("disable_api"))
    )


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


def _extract_billing_from_config(config_value: Any) -> Dict[str, Any]:
    """从 config dict 中提取计价信息，返回 {unit_type, cost, cost_input, cost_output}。"""
    cfg = _safe_json_dict(config_value)
    ap = cfg.get("api_pricing") if isinstance(cfg.get("api_pricing"), dict) else {}
    return {
        "unit_type": _normalize_billing_unit_type(ap.get("unit_type") or cfg.get("billing_unit_type") or "per_call"),
        "cost": _non_negative_int(ap.get("cost", cfg.get("billing_cost", 0))),
        "cost_input": _non_negative_int(ap.get("cost_input", cfg.get("billing_cost_input", 0))),
        "cost_output": _non_negative_int(ap.get("cost_output", cfg.get("billing_cost_output", 0))),
    }


def _strip_billing_from_config(config_value: Any) -> Dict[str, Any]:
    """返回去除所有计价键的 config dict。"""
    cfg = _safe_json_dict(config_value)
    for key in _BILLING_CONFIG_KEYS:
        cfg.pop(key, None)
    return cfg


def _normalize_system_api_billing_config(config_value: Any) -> Dict[str, Any]:
    """兼容入口：清理 config 中的计价键，返回干净的 config（不含计价信息）。"""
    return _strip_billing_from_config(config_value)


def _billing_from_payload_or_config(payload, raw_config: dict) -> Dict[str, Any]:
    """优先使用 payload 上的显式计价字段；否则从 config dict 中提取。"""
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
        # continue to normalize existing KIE video rows
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
            deprecated=False,
            config=item["config"],
            is_active=False,
        ))

    # Normalize existing KIE Video rows: clear previous forced deprecation for known KIE video built-ins.
    known_kie_video_models = {
        str(item.get("model") or "").strip().lower()
        for item in builtins
        if str(item.get("provider") or "").strip().lower() == "kie"
        and str(item.get("category") or "").strip().lower() == "video"
    }
    kie_video_rows = db.query(SystemAPISetting).filter(
        _system_provider_case_insensitive_filter("kie"),
        SystemAPISetting.category == "Video",
    ).all()
    for row in kie_video_rows:
        model_text = str(row.model or "").strip().lower()
        cfg = _safe_json_dict(row.config)

        if model_text in known_kie_video_models:
            cfg["deprecated"] = False
            row.deprecated = False
            row.config = cfg

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
        _ensure_default_system_selection_for_user(db, current_user.id)
        _cleanup_user_api_settings_records(db, current_user.id)
        _normalize_user_active_settings(db, current_user.id)
        db.commit()

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
    # Check if we are updating an existing ID
    existing_setting = None
    if setting_in.id:
        existing_setting = db.query(APISetting).filter(
            APISetting.id == setting_in.id,
            APISetting.user_id == current_user.id,
        ).first()
        if not existing_setting:
            raise HTTPException(status_code=404, detail="Setting not found")

    # Identify effective provider/category with existing-row fallback.
    provider = setting_in.provider or (existing_setting.provider if existing_setting else None)
    default_info = DEFAULTS.get(provider, {})
    category = setting_in.category or (existing_setting.category if existing_setting else None) or default_info.get("category", "LLM")

    # If this request is setting item to Active, deactivate others in the same effective category.
    if setting_in.is_active:
        existing_active = db.query(APISetting).filter(
            APISetting.user_id == current_user.id,
            APISetting.category == category,
            APISetting.is_active == True,
        ).all()
        for s in existing_active:
            s.is_active = False

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

    _cleanup_user_api_settings_records(db, current_user.id)
    _normalize_user_active_settings(db, current_user.id)

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
        _cleanup_user_api_settings_records(db, current_user.id)
        _normalize_user_active_settings(db, current_user.id)
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
            SystemAPISetting.modality,
            SystemAPISetting.tags,
            cast(SystemAPISetting.config, String).label("config_raw"),
        ).filter(
            ~SystemAPISetting.category.like("System_%")
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
            row_cfg = _safe_json_dict(getattr(row, "config_raw", None))
            row_data = {
                "id": row.id,
                "category": row.category,
                "provider": row.provider,
                "model": row.model,
                "config": row_cfg,
                "use_system_setting_id": _safe_int(row_cfg.get("use_system_setting_id"), None),
            }
            if cat not in user_active_by_category or (row.id or 0) > (user_active_by_category[cat].get("id") or 0):
                user_active_by_category[cat] = row_data

        grouped: Dict[Tuple[str, str], Dict] = {}
        for item in system_settings:
            provider = item.provider or "unknown"
            category = item.category or "LLM"
            raw_config = getattr(item, "config_raw", None)
            item_config = _safe_json_dict(getattr(item, "config_raw", None))
            if isinstance(raw_config, str) and raw_config.strip() and not _is_json_object_value(raw_config):
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

            key_pool = _get_system_provider_key_pool(db, provider)
            fallback_key = str(item.api_key or "").strip()
            runtime_key = key_pool[0] if key_pool else fallback_key
            has_key = bool(runtime_key)
            grouped[key]["shared_key_configured"] = grouped[key]["shared_key_configured"] or has_key

            user_active = user_active_by_category.get(category)
            user_is_active_for_row = False
            if user_active:
                selected_system_id = _safe_int(user_active.get("use_system_setting_id"), None)
                if selected_system_id:
                    user_is_active_for_row = int(item.id or 0) == int(selected_system_id)
                else:
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
                modality=item.modality,
                tags=getattr(item, "tags", None),
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
    if _is_system_api_auto_billing_sync_enabled():
        _migrate_system_api_pricing_to_base_rules(db)
    db.commit()

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
    system_setting = db.query(SystemAPISetting).filter(
        SystemAPISetting.id == selection.setting_id,
    ).first()
    if not system_setting:
        raise HTTPException(status_code=404, detail="System API setting not found")

    if _is_setting_deprecated(system_setting.config, system_setting.deprecated):
        raise HTTPException(status_code=400, detail="This system API setting is deprecated and cannot be activated")

    _cleanup_user_api_settings_records(db, current_user.id)
    _normalize_user_active_settings(db, current_user.id)

    # Enforce one-active-per-category for current user.
    db.query(APISetting).filter(
        APISetting.user_id == current_user.id,
        APISetting.category == system_setting.category,
        APISetting.is_active == True,
    ).update({"is_active": False})

    # api_settings is a lightweight per-category preference marker only.
    # Keep a single latest row per category, and store selected system setting id.
    user_setting = db.query(APISetting).filter(
        APISetting.user_id == current_user.id,
        APISetting.category == system_setting.category,
    ).order_by(APISetting.id.desc()).first()

    marker_config = {
        "selection_source": "system",
        "use_system_setting_id": int(system_setting.id),
    }

    if user_setting:
        user_setting.name = f"Use System {system_setting.provider}"
        user_setting.provider = system_setting.provider
        user_setting.base_url = ""
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
            base_url="",
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
    migrated_base_count = _migrate_system_api_pricing_to_base_rules(db) if _is_system_api_auto_billing_sync_enabled() else 0
    if migrated_base_count:
        logger.info("[system_api.pricing.base_rule.migrate] migrated_rows=%s", migrated_base_count)
    db.commit()

    rows = db.query(SystemAPISetting).filter(
        ~SystemAPISetting.category.like("System_%"),
    ).order_by(SystemAPISetting.category.asc(), SystemAPISetting.provider.asc(), SystemAPISetting.model.asc(), SystemAPISetting.id.asc()).all()
    return [_setting_to_out(db, row) for row in rows]


@router.get("/settings/system/manage/missing-billing-rules", response_model=List[SystemAPIMissingBillingRuleOut])
def list_system_settings_missing_billing_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    api_rows = db.query(SystemAPISetting).filter(
        ~SystemAPISetting.category.like("System_%"),
    ).order_by(
        SystemAPISetting.category.asc(),
        SystemAPISetting.provider.asc(),
        SystemAPISetting.model.asc(),
        SystemAPISetting.id.asc(),
    ).all()

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
        modality = row.modality if isinstance(row.modality, dict) else {}
        base_model = str(getattr(row, "base_model", "") or "").strip() or str(modality.get("base_model") or "").strip() or None
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

    grouped: Dict[str, List[SystemAPIBillingRuleOut]] = {}
    for row in rows:
        sid = str(int(row.system_api_id))
        grouped.setdefault(sid, []).append(_rule_to_out(row))

    if ids:
        for sid in sorted(set(ids)):
            grouped.setdefault(str(sid), [])

    return grouped


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


@router.get("/settings/system/manage/{system_api_id}/billing-rules", response_model=List[SystemAPIBillingRuleOut])
def list_system_api_billing_rules(
    system_api_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    target = db.query(SystemAPISetting).filter(SystemAPISetting.id == system_api_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="System API setting not found")

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
    if int(payload.system_api_id) != int(system_api_id):
        raise HTTPException(status_code=400, detail="path system_api_id must match payload.system_api_id")

    target = db.query(SystemAPISetting).filter(SystemAPISetting.id == system_api_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="System API setting not found")

    payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    payload_data["charge_multiplier"] = _normalize_rule_charge_multiplier(payload_data.get("charge_multiplier"), default=2.0)
    payload_data["updated_at"] = datetime.utcnow().isoformat()
    rule = SystemAPIBillingRule(**payload_data)
    db.add(rule)
    db.flush()
    _refresh_has_granular_billing_rules_flag(db, system_api_id)
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

    rule = db.query(SystemAPIBillingRule).filter(SystemAPIBillingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Billing rule not found")

    update_data = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    if "charge_multiplier" in update_data:
        update_data["charge_multiplier"] = _normalize_rule_charge_multiplier(update_data.get("charge_multiplier"), default=2.0)
    for key, value in update_data.items():
        setattr(rule, key, value)
    rule.updated_at = datetime.utcnow().isoformat()
    _refresh_has_granular_billing_rules_flag(db, int(rule.system_api_id))
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

    rule = db.query(SystemAPIBillingRule).filter(SystemAPIBillingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Billing rule not found")

    system_api_id = int(rule.system_api_id)
    db.delete(rule)
    db.flush()
    _refresh_has_granular_billing_rules_flag(db, system_api_id)
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

    Algorithm:
    - Build cost score = max(billing_cost, billing_cost_input, billing_cost_output)
    - Map score to multiplier range [min_multiplier, max_multiplier]
    - Higher score => lower multiplier
    """
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    min_multiplier = float(payload.min_multiplier if payload.min_multiplier is not None else 1.1)
    max_multiplier = float(payload.max_multiplier if payload.max_multiplier is not None else 2.0)
    default_multiplier = _normalize_rule_charge_multiplier(payload.default_multiplier, default=2.0)

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
            preview=[],
        )

    scored: List[Tuple[SystemAPIBillingRule, int]] = [(row, _rule_cost_score(row)) for row in rows]
    min_cost = min(score for _, score in scored)
    max_cost = max(score for _, score in scored)

    updated = 0
    now_iso = datetime.utcnow().isoformat()
    preview: List[Dict[str, Any]] = []

    for row, score in scored:
        if score <= 0:
            new_multiplier = float(default_multiplier)
        else:
            new_multiplier = _compute_cost_scaled_multiplier(
                score,
                min_cost,
                max_cost,
                min_multiplier,
                max_multiplier,
            )
        old_multiplier = _normalize_rule_charge_multiplier(getattr(row, "charge_multiplier", None), default=default_multiplier)
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
            "supplier_currency": suggestion.supplier_currency or "CNY",
            "supplier_price_basis": suggestion.supplier_price_basis or "money",
            "source": "provider_input",
            "updated_at": now_iso,
        }
        pricing_scheme = {
            "strategy": "supplier_price_x_multiplier",
            "multiplier": suggestion.multiplier,
            "cny_to_credit_rate": 100,  # 1积分=1分钱=0.01元
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
            "cost": suggestion.cost,
            "cost_input": suggestion.cost_input,
            "cost_output": suggestion.cost_output,
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
    """AI助手工具: 汇率兑换 — 将外币金额转换为人民币(CNY)。"""
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
    """AI助手工具: 定价页面读取 — 抓取供应商定价页面并提取结构化内容。"""
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only superuser can use system AI assistant tools")

    from app.services.pricing_tools import fetch_pricing_page

    url = (payload.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    result = fetch_pricing_page(url, max_length=min(payload.max_length, 50000))
    return FetchPricingPageResponse(**result)


@router.post("/settings/system/manage/kie-pricing/generate", response_model=KIEPricingGenerateResponse)
async def generate_kie_pricing_rules(
    payload: KIEPricingGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """KIE 专项定价助手: 抓取定价页 -> LLM 匹配 system_api(kie) -> 生成规则建议。"""
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
        llm_raw=(llm_raw[:4000] if llm_raw else None),
    )


@router.post("/settings/system/manage/kie-pricing/apply", response_model=KIEPricingApplyResponse)
def apply_kie_pricing_rules(
    payload: KIEPricingApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """KIE 专项定价助手: 直接应用已有建议，不重新执行 LLM 匹配生成。"""
    if not _can_manage_system_settings(current_user):
        raise HTTPException(status_code=403, detail="Only system/admin users can manage system API settings")

    provider_filter = str(payload.provider_filter or "kie").strip() or "kie"
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
    """KIE 专项定价抓取: 支持分页探测，先确认数据再做匹配生成。"""
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
    modality_payload = payload.modality if isinstance(payload.modality, dict) else {}
    base_model = (payload.base_model or "").strip() or str(modality_payload.get("base_model") or "").strip() or None
    existing = _find_system_setting_by_normalized_triplet(db, provider, category, model)
    if existing:
        raw_cfg = payload.config if isinstance(payload.config, dict) else _safe_json_dict(existing.config)
        billing = _billing_from_payload_or_config(payload, raw_cfg)
        target_cfg = _strip_billing_from_config(raw_cfg)
        existing.name = (payload.name or existing.name or "System Setting").strip() or "System Setting"
        existing.base_url = payload.base_url
        existing.model = payload.model
        existing.base_model = base_model
        existing.modality = payload.modality
        existing.tags = getattr(payload, "tags", None)
        existing.supplier_info = getattr(payload, "supplier_info", None) or existing.supplier_info
        existing.config = target_cfg
        existing.is_active = bool(payload.is_active)
        _clear_row_billing_columns(existing)

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

        if _is_system_api_auto_billing_sync_enabled():
            _upsert_base_billing_rule(db, existing.id, existing.category, billing, activate=True)
            _refresh_has_granular_billing_rules_flag(db, existing.id)

        db.commit()
        db.refresh(existing)
        return _setting_to_out(db, existing)

    raw_create_config = payload.config if isinstance(payload.config, dict) else {}
    create_billing = _billing_from_payload_or_config(payload, raw_create_config)
    create_config = _strip_billing_from_config(raw_create_config)
    new_setting = SystemAPISetting(
        name=(payload.name or "System Setting").strip() or "System Setting",
        category=category,
        provider=provider,
        api_key="",
        base_url=payload.base_url,
        model=payload.model,
        base_model=base_model,
        modality=payload.modality,
        tags=getattr(payload, "tags", None),
        supplier_info=getattr(payload, "supplier_info", None),
        deprecated=False,
        config=create_config,
        is_active=bool(payload.is_active),
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

    if new_setting.is_active:
        db.query(SystemAPISetting).filter(
            SystemAPISetting.category == new_setting.category,
            SystemAPISetting.id != new_setting.id,
            SystemAPISetting.is_active == True,
        ).update({"is_active": False})

    db.commit()
    db.refresh(new_setting)
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
    for key, value in update_data.items():
        setattr(target, key, value)

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
    target.config = _strip_billing_from_config(target.config)
    _clear_row_billing_columns(target)

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

    if _is_system_api_auto_billing_sync_enabled():
        _upsert_base_billing_rule(db, target.id, target.category, update_billing, activate=True)
        _refresh_has_granular_billing_rules_flag(db, target.id)

    db.commit()
    db.refresh(target)
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
    if _is_system_api_auto_billing_sync_enabled():
        _migrate_system_api_pricing_to_base_rules(db)
    db.commit()

    rows = db.query(SystemAPISetting).filter(
        ~SystemAPISetting.category.like("System_%"),
    ).order_by(SystemAPISetting.category.asc(), SystemAPISetting.provider.asc(), SystemAPISetting.model.asc(), SystemAPISetting.id.asc()).all()

    items = []
    for row in rows:
        billing = _resolve_system_setting_billing(db, row)
        items.append({
            "name": row.name,
            "category": row.category,
            "provider": row.provider,
            "api_key": row.api_key,
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
            "is_active": bool(row.is_active),
        })

    return {
        "version": 1,
        "exported_at": datetime.utcnow().isoformat(),
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
            "is_active": bool(row.is_active),
        })

    seed_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "system_api_seed.json"))
    os.makedirs(os.path.dirname(seed_path), exist_ok=True)
    with open(seed_path, "w", encoding="utf-8") as f:
        json.dump({
            "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
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

    _ensure_builtin_system_settings(db)
    db.commit()

    rows = db.query(SystemAPISetting).filter(
        ~SystemAPISetting.category.like("System_%"),
    ).order_by(SystemAPISetting.provider.asc(), SystemAPISetting.category.asc(), SystemAPISetting.model.asc(), SystemAPISetting.id.asc()).all()

    grouped: Dict[str, List[SystemAPISetting]] = {}
    for row in rows:
        provider_name = str(row.provider or "").strip()
        if not provider_name:
            continue
        grouped.setdefault(provider_name, []).append(row)

    providers = []
    for provider_name, provider_rows in grouped.items():
        pool_info = _get_system_provider_key_pool_full(db, provider_name)
        models = []
        for row in provider_rows:
            billing = _resolve_system_setting_billing(db, row)
            models.append({
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
                "is_active": bool(row.is_active),
            })
        providers.append({
            "provider": provider_name,
            "api_keys": pool_info["keys"],
            "strategy": pool_info["strategy"],
            "weights": pool_info["weights"],
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
                    target.base_model = (getattr(model_item, "base_model", None) or "").strip() or None
                    target.modality = getattr(model_item, "modality", None)
                    target.tags = getattr(model_item, "tags", None)
                    target.supplier_info = getattr(model_item, "supplier_info", None) or target.supplier_info
                    target.config = clean_model_cfg
                    target.deprecated = _is_setting_deprecated(target.config, model_item.deprecated)
                    target.is_active = bool(model_item.is_active)
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
                        base_model=(getattr(model_item, "base_model", None) or "").strip() or None,
                        modality=getattr(model_item, "modality", None),
                        tags=getattr(model_item, "tags", None),
                        supplier_info=getattr(model_item, "supplier_info", None),
                        deprecated=_is_setting_deprecated(clean_model_cfg, model_item.deprecated),
                        config=clean_model_cfg,
                        is_active=bool(model_item.is_active),
                    )
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

    rule_ids = [
        int(rule_id)
        for rule_id, in db.query(SystemAPIBillingRule.id).filter(
            SystemAPIBillingRule.system_api_id.in_(target_ids),
        ).all()
    ]

    db.query(TransactionAction).filter(
        TransactionAction.system_api_id.in_(target_ids),
    ).update({"system_api_id": None}, synchronize_session=False)

    if rule_ids:
        db.query(TransactionAction).filter(
            TransactionAction.matched_rule_id.in_(rule_ids),
        ).update({"matched_rule_id": None}, synchronize_session=False)

    db.query(SystemAPIBillingRule).filter(
        SystemAPIBillingRule.system_api_id.in_(target_ids),
    ).delete(synchronize_session=False)

    db.query(SystemAPISetting).filter(
        SystemAPISetting.id.in_(target_ids),
    ).delete(synchronize_session=False)

    db.flush()


def _import_provider_bundle_no_commit(db: Session, providers: List[Any], replace_all: bool) -> Dict[str, int]:
    if replace_all:
        _clear_non_system_settings_for_replace_all(db)

    created = 0
    updated = 0
    key_updated_providers = 0
    providers_processed = 0
    skipped_models = 0
    last_active_id_by_category: Dict[str, int] = {}

    for provider_item in providers:
        provider_name = str(getattr(provider_item, "provider", "") or "").strip()
        if not provider_name:
            continue

        providers_processed += 1
        keys = _normalize_api_keys(getattr(provider_item, "api_keys", []) or [])
        strategy = _normalize_key_strategy(getattr(provider_item, "strategy", None))
        weights = _normalize_key_weights(getattr(provider_item, "weights", None), keys)
        models = getattr(provider_item, "models", []) or []

        for model_item in models:
            category = str(getattr(model_item, "category", "LLM") or "LLM").strip() or "LLM"
            if _is_system_reserved_category(category):
                skipped_models += 1
                continue
            model = str(getattr(model_item, "model", "") or "").strip()
            if not model:
                skipped_models += 1
                continue

            target = _find_system_setting_by_normalized_triplet(db, provider_name, category, model)

            raw_model_cfg = getattr(model_item, "config", {}) if isinstance(getattr(model_item, "config", {}), dict) else {}
            model_billing = _billing_from_payload_or_config(model_item, raw_model_cfg)
            clean_model_cfg = _strip_billing_from_config(raw_model_cfg)

            if target:
                target.name = (getattr(model_item, "name", None) or target.name or "System Setting").strip() or "System Setting"
                target.base_url = getattr(model_item, "base_url", None)
                target.model = model
                target.base_model = (getattr(model_item, "base_model", None) or "").strip() or None
                target.modality = getattr(model_item, "modality", None)
                target.tags = getattr(model_item, "tags", None)
                target.supplier_info = getattr(model_item, "supplier_info", None) or target.supplier_info
                target.config = clean_model_cfg
                target.deprecated = _is_setting_deprecated(target.config, getattr(model_item, "deprecated", None))
                target.is_active = bool(getattr(model_item, "is_active", False))
                _clear_row_billing_columns(target)
                if _is_system_api_auto_billing_sync_enabled():
                    _upsert_base_billing_rule(db, target.id, target.category, model_billing, activate=True)
                    _refresh_has_granular_billing_rules_flag(db, target.id)
                updated += 1
            else:
                target = SystemAPISetting(
                    name=(getattr(model_item, "name", None) or "System Setting").strip() or "System Setting",
                    category=category,
                    provider=provider_name,
                    api_key="",
                    base_url=getattr(model_item, "base_url", None),
                    model=model,
                    base_model=(getattr(model_item, "base_model", None) or "").strip() or None,
                    modality=getattr(model_item, "modality", None),
                    tags=getattr(model_item, "tags", None),
                    supplier_info=getattr(model_item, "supplier_info", None),
                    deprecated=_is_setting_deprecated(clean_model_cfg, getattr(model_item, "deprecated", None)),
                    config=clean_model_cfg,
                    is_active=bool(getattr(model_item, "is_active", False)),
                )
                _clear_row_billing_columns(target)
                db.add(target)
                db.flush()
                if _is_system_api_auto_billing_sync_enabled():
                    _upsert_base_billing_rule(db, target.id, target.category, model_billing, activate=True)
                    _refresh_has_granular_billing_rules_flag(db, target.id)
                created += 1

            if bool(getattr(model_item, "is_active", False)):
                last_active_id_by_category[category] = target.id

        provider_rows = db.query(SystemAPISetting).filter(
            SystemAPISetting.provider == provider_name,
            ~SystemAPISetting.category.like("System_%"),
        ).all()
        if provider_rows:
            _apply_provider_key_bundle_to_rows(db, provider_name, keys, strategy, weights)
            key_updated_providers += 1

    for category, keep_id in last_active_id_by_category.items():
        db.query(SystemAPISetting).filter(
            SystemAPISetting.category == category,
            SystemAPISetting.id != keep_id,
            SystemAPISetting.is_active == True,
        ).update({"is_active": False}, synchronize_session=False)

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

    provider_bundle = export_system_provider_bundle_for_manage(db=db, current_user=current_user)

    system_rows = db.query(SystemAPISetting).filter(
        ~SystemAPISetting.category.like("System_%"),
    ).all()
    system_map = {int(row.id): row for row in system_rows}

    billing_rules_payload: List[Dict[str, Any]] = []
    rule_rows = db.query(SystemAPIBillingRule).order_by(
        SystemAPIBillingRule.system_api_id.asc(),
        SystemAPIBillingRule.id.asc(),
    ).all()
    for rule in rule_rows:
        api_row = system_map.get(int(rule.system_api_id))
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

    provider_key_pool_rows = db.query(ProviderKeyPool).order_by(ProviderKeyPool.provider.asc(), ProviderKeyPool.id.asc()).all()
    provider_key_pools_payload = [
        {
            "provider": row.provider,
            "api_keys": _normalize_api_keys(row.api_keys),
            "strategy": _normalize_key_strategy(row.strategy),
            "weights": row.weights if row.weights else [],
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in provider_key_pool_rows
    ]

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
            "is_active": bool(row.is_active),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in smtp_rows
    ]

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

    data = {
        "providers": provider_bundle.get("providers", []),
        "billing_rules": billing_rules_payload,
        "provider_key_pools": provider_key_pools_payload,
        "smtp_configs": smtp_payload,
        "wechat_pay_configs": wechat_payload,
    }

    return {
        "version": 1,
        "format": "system_config_sync_bundle",
        "exported_at": datetime.utcnow().isoformat(),
        "summary": {
            "providers": len(data["providers"]),
            "billing_rules": len(data["billing_rules"]),
            "provider_key_pools": len(data["provider_key_pools"]),
            "smtp_configs": len(data["smtp_configs"]),
            "wechat_pay_configs": len(data["wechat_pay_configs"]),
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

    replace_all = bool(payload.replace_all)
    if replace_all and not bool(getattr(payload, "confirm_clear_existing", False)):
        raise HTTPException(
            status_code=400,
            detail="confirm_clear_existing=true is required when replace_all=true",
        )

    try:
        provider_items = []
        for raw in providers:
            if not isinstance(raw, dict):
                continue
            provider_items.append(raw)
        provider_req = SystemAPIProviderImportRequest(providers=provider_items, replace_all=replace_all)
        provider_result = _import_provider_bundle_no_commit(db, provider_req.providers or [], provider_req.replace_all)

        if replace_all:
            db.query(TransactionAction).filter(
                TransactionAction.matched_rule_id.isnot(None),
            ).update({"matched_rule_id": None}, synchronize_session=False)
            db.query(SystemAPIBillingRule).delete(synchronize_session=False)

        system_rows = db.query(SystemAPISetting).filter(
            ~SystemAPISetting.category.like("System_%"),
        ).all()
        system_index: Dict[Tuple[str, str, str], int] = {}
        for row in system_rows:
            provider_name = _normalize_system_provider_name(row.provider)
            category_name = str(row.category or "").strip()
            model_name = str(row.model or "").strip()
            if provider_name and category_name and model_name:
                system_index[(provider_name, category_name, model_name)] = int(row.id)

        billing_created = 0
        billing_skipped = 0
        now_iso = datetime.utcnow().isoformat()
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
                    setattr(new_rule, field_name, raw_rule.get(field_name))
            new_rule.created_at = str(raw_rule.get("created_at") or now_iso)
            new_rule.updated_at = str(raw_rule.get("updated_at") or now_iso)
            db.add(new_rule)
            billing_created += 1

        provider_pool_created = 0
        provider_pool_updated = 0
        if replace_all:
            db.query(ProviderKeyPool).delete(synchronize_session=False)

        for raw_pool in provider_key_pools:
            if not isinstance(raw_pool, dict):
                continue
            provider_name = _normalize_system_provider_name(raw_pool.get("provider"))
            if not provider_name:
                continue
            keys = _normalize_api_keys(raw_pool.get("api_keys"))
            strategy = _normalize_key_strategy(raw_pool.get("strategy"))
            weights = _normalize_key_weights(raw_pool.get("weights"), keys)
            record = db.query(ProviderKeyPool).filter(ProviderKeyPool.provider == provider_name).first()
            if record:
                record.api_keys = keys
                record.strategy = strategy
                record.weights = weights
                record.updated_at = str(raw_pool.get("updated_at") or datetime.utcnow().isoformat())
                provider_pool_updated += 1
            else:
                created_at = str(raw_pool.get("created_at") or datetime.utcnow().isoformat())
                record = ProviderKeyPool(
                    provider=provider_name,
                    api_keys=keys,
                    strategy=strategy,
                    weights=weights,
                    created_at=created_at,
                    updated_at=str(raw_pool.get("updated_at") or created_at),
                )
                db.add(record)
                provider_pool_created += 1

        smtp_created = 0
        if replace_all:
            db.query(SMTPSystemConfig).delete(synchronize_session=False)
        for raw_smtp in smtp_configs:
            if not isinstance(raw_smtp, dict):
                continue
            created_at = str(raw_smtp.get("created_at") or datetime.utcnow().isoformat())
            row = SMTPSystemConfig(
                host=str(raw_smtp.get("host") or "").strip(),
                port=int(raw_smtp.get("port") or 587),
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

        wechat_created = 0
        if replace_all:
            db.query(WechatPayConfig).delete(synchronize_session=False)
        for raw_wechat in wechat_pay_configs:
            if not isinstance(raw_wechat, dict):
                continue
            created_at = str(raw_wechat.get("created_at") or datetime.utcnow().isoformat())
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

        db.commit()
        return {
            "ok": True,
            "replace_all": replace_all,
            "provider_result": provider_result,
            "billing_rules": {
                "created": billing_created,
                "skipped": billing_skipped,
            },
            "provider_key_pools": {
                "created": provider_pool_created,
                "updated": provider_pool_updated,
            },
            "smtp_configs": {
                "created": smtp_created,
            },
            "wechat_pay_configs": {
                "created": wechat_created,
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
        raise HTTPException(status_code=500, detail=f"sync bundle import failed: {type(exc).__name__}")


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
            target.base_model = (getattr(item, "base_model", None) or "").strip() or None
            target.modality = item.modality
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
            target = SystemAPISetting(
                name=(item.name or "System Setting").strip() or "System Setting",
                category=category,
                provider=provider,
                api_key="",
                base_url=item.base_url,
                model=item.model,
                base_model=(getattr(item, "base_model", None) or "").strip() or None,
                modality=item.modality,
                tags=getattr(item, "tags", None),
                supplier_info=getattr(item, "supplier_info", None),
                deprecated=_is_setting_deprecated(create_raw_cfg, item.deprecated),
                config=_strip_billing_from_config(create_raw_cfg),
                is_active=bool(item.is_active),
            )
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

    db.query(SystemAPIBillingRule).filter(SystemAPIBillingRule.system_api_id == target.id).delete(synchronize_session=False)
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
            api_keys=_normalize_api_keys(row.api_keys),
            strategy=_normalize_key_strategy(row.strategy),
            weights=row.weights if row.weights else [],
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
    now = datetime.utcnow().isoformat()

    record = ProviderKeyPool(
        provider=provider_name,
        api_keys=keys,
        strategy=strategy,
        weights=weights,
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return ProviderKeyPoolOut(
        id=record.id,
        provider=record.provider,
        api_keys=_normalize_api_keys(record.api_keys),
        strategy=_normalize_key_strategy(record.strategy),
        weights=record.weights if record.weights else [],
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
    if payload.strategy is not None:
        record.strategy = _normalize_key_strategy(payload.strategy)
    if payload.weights is not None:
        keys = _normalize_api_keys(record.api_keys)
        record.weights = _normalize_key_weights(payload.weights, keys)
    record.updated_at = datetime.utcnow().isoformat()
    db.commit()
    db.refresh(record)
    return ProviderKeyPoolOut(
        id=record.id,
        provider=record.provider,
        api_keys=_normalize_api_keys(record.api_keys),
        strategy=_normalize_key_strategy(record.strategy),
        weights=record.weights if record.weights else [],
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
    return {"ok": True}


@router.get("/settings/defaults")
def get_defaults():
    return DEFAULTS
