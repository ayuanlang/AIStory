
import requests
import re
import urllib3
import time
import base64
import json
import hashlib
import hmac
import asyncio
import uuid
import os
import random
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.schemas.agent import AgentRequest, AgentResponse, AgentAction
from app.services.llm_service import llm_service
from app.db.session import SessionLocal
from app.models.all_models import APISetting, SystemAPISetting, Entity, User, Project, ProjectShare, Scene, Shot, Episode
from app.core.config import settings
from app.services.billing_service import billing_service
from app.services.tool_billing_taxonomy_service import tool_billing_taxonomy_service
from sqlalchemy.orm import Session
from sqlalchemy import cast, String
# from app.db.session import db as legacy_db 
# Mock legacy_db to prevent import error during refactor
class MockLegacyDB:
    projects = {}
    def save(self): pass
legacy_db = MockLegacyDB()

# Suppress InsecureRequestWarning from urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class AgentService:
    _provider_key_cursors: Dict[str, int] = {}
    _PROJECT_AGENT_ALLOWED_TOOLS = {
        "generate_project_asset",
        "analyze_script",
        "update_project_metadata",
        "search_project_data",
        "internet_search",
        "visualize_user_requirement",
        "generate_image_text_to_image",
        "generate_image_image_to_image",
        "generate_video_text_to_video",
        "generate_video_image_to_video",
    }
    _SYSTEM_MANAGEMENT_PROMPT = """
You are a System Management AI Agent for platform operators.
Your job is to analyze provider/model pricing inputs and execute safe updates to system API definitions and api_pricing.

Core workflow:
1) Understand user intent and classify it as one of:
    - list/query existing settings
    - create new provider/model pricing definition
    - update existing provider/model pricing definition
2) Extract structured pricing facts from user text (provider, model, category, base_url, unit_type, supplier price input/output, multiplier, active flag).
3) If user asks create/update but required fields are incomplete, DO NOT write. Ask concise follow-up questions for missing fields.
4) Only call write tool when required information is sufficient.

Category-specific pricing elements:
- Image: return and write per-image price (single-price path). Prefer fields: supplier_price / price_per_image / supplier_price_per_image / our_price_usd.
- Video/Audio: return and write single-unit price (per call or per second/minute depending on user input).
- LLM/Text: return and write input/output token prices when available (supplier_price_input/supplier_price_output).

Required fields for write:
- provider
- model
- category (default LLM if not explicitly specified)
- pricing basis: at least one of supplier_price / supplier_price_input / supplier_price_output (or category aliases like price_per_image)

Missing-info policy:
- If provider or model is missing: ask user to provide.
- If pricing basis is missing: ask supplier price basis and billing unit.
- If unit_type is missing: infer only when user clearly indicates token/call/time, otherwise ask.
- If operation target is unclear (create vs update): search first, then ask user to confirm create/update.

Update strategy:
- For natural-language requests, first abstract to normalized fields, then map to tool parameters.
- For update requests, preserve unspecified existing fields; only change fields explicitly provided by user.
- For create requests, propose defaults only when safe and explain assumptions in reply.

You may only use these tools:
1) search_system_api_settings
   - Parameters: provider (optional), category (optional), model (optional), limit (optional, max 50)
2) upsert_system_api_pricing
   - Parameters:
     - provider (required)
     - category (required, default LLM)
     - model (required)
     - name (optional)
     - base_url (optional)
     - unit_type (optional: per_call/per_second/per_minute/per_token/per_1k_tokens/per_million_tokens)
     - supplier_price (optional)
     - supplier_price_input (optional)
     - supplier_price_output (optional)
     - multiplier (optional, default 1.0)
     - is_active (optional, default false)

Rules:
- Prefer search first, then update.
- Never invent unsupported fields.
- If user asks analysis only, do not write.
- If user asks apply/update/create and fields are complete, call upsert_system_api_pricing.
- If user asks apply/update/create but fields are incomplete, return follow-up questions and keep plan empty.
- Keep replies concise and actionable.

Output must be JSON object with keys: reply, plan.
"""

    _SYSTEM_MANAGEMENT_ALLOWED_TOOLS = {
        "search_system_api_settings",
        "upsert_system_api_pricing",
    }

    _SYSTEM_WRITE_CONFIRM_KEYWORDS = {
        "confirm",
        "confirmed",
        "apply now",
        "go ahead",
        "proceed",
        "yes apply",
        "确认",
        "请确认",
        "确认执行",
        "确认应用",
        "执行",
        "应用",
        "提交",
        "继续",
    }

    def _normalize_llm_result(self, llm_result: Any) -> Dict[str, Any]:
        if isinstance(llm_result, str):
            return {"reply": llm_result, "plan": [], "usage": {}}

        if not isinstance(llm_result, dict):
            return {"reply": str(llm_result or ""), "plan": [], "usage": {}}

        reply = llm_result.get("reply")
        reply_text = reply if isinstance(reply, str) else str(reply or "")

        raw_plan = llm_result.get("plan")
        normalized_plan: List[Dict[str, Any]] = []
        if isinstance(raw_plan, list):
            for item in raw_plan:
                if isinstance(item, dict):
                    tool_name = str(item.get("tool") or "").strip()
                    params = item.get("parameters") if isinstance(item.get("parameters"), dict) else {}
                    if not tool_name:
                        continue
                    normalized_plan.append({"tool": tool_name, "parameters": params})
                elif isinstance(item, str):
                    tool_name = item.strip()
                    if tool_name:
                        normalized_plan.append({"tool": tool_name, "parameters": {}})

        usage = llm_result.get("usage") if isinstance(llm_result.get("usage"), dict) else {}
        return {
            **llm_result,
            "reply": reply_text,
            "plan": normalized_plan,
            "usage": usage,
        }

    def _first_non_negative_float_from_keys(self, params: Dict[str, Any], keys: List[str]) -> Optional[float]:
        for key in keys:
            if key not in params:
                continue
            value = params.get(key)
            if value is None:
                continue
            parsed = self._safe_non_negative_float(value)
            return parsed
        return None

    def _normalize_system_upsert_preview(self, params: Dict[str, Any]) -> Dict[str, Any]:
        provider = str(params.get("provider") or "").strip()
        category = str(params.get("category") or "LLM").strip() or "LLM"
        category_lower = category.lower()
        model = str(params.get("model") or "").strip()
        unit_type = self._normalize_unit_type_for_system_ai(params.get("unit_type") or "per_call")
        multiplier = self._safe_non_negative_float(params.get("multiplier") or 1.0)
        if multiplier <= 0:
            multiplier = 1.0

        supplier_price = self._first_non_negative_float_from_keys(params, [
            "supplier_price", "price_per_image", "supplier_price_per_image", "our_price_usd", "price_usd", "price",
        ])
        supplier_price_input = self._first_non_negative_float_from_keys(params, [
            "supplier_price_input", "price_input", "input_price", "our_price_input_usd",
        ])
        supplier_price_output = self._first_non_negative_float_from_keys(params, [
            "supplier_price_output", "price_output", "output_price", "our_price_output_usd",
        ])

        if category_lower == "image" and supplier_price is None:
            supplier_price = self._first_non_negative_float_from_keys(params, ["cost", "cost_per_image", "image_cost"]) 

        def _to_2dp(value: Optional[float]) -> Optional[float]:
            if value is None:
                return None
            return round(float(value), 2)

        computed_cost = self._multiplied_cost_to_credit(supplier_price, multiplier)
        computed_cost_input = self._multiplied_cost_to_credit(supplier_price_input, multiplier)
        computed_cost_output = self._multiplied_cost_to_credit(supplier_price_output, multiplier)

        computed_cost_decimal = _to_2dp((supplier_price or 0.0) * multiplier if supplier_price is not None else None)
        computed_cost_input_decimal = _to_2dp((supplier_price_input or 0.0) * multiplier if supplier_price_input is not None else None)
        computed_cost_output_decimal = _to_2dp((supplier_price_output or 0.0) * multiplier if supplier_price_output is not None else None)

        return {
            "provider": provider,
            "category": category,
            "model": model,
            "name": (str(params.get("name") or "").strip() or None),
            "base_url": (str(params.get("base_url") or "").strip() or None),
            "unit_type": unit_type,
            "multiplier": multiplier,
            "multiplier_2dp": round(multiplier, 2),
            "supplier_price": supplier_price,
            "supplier_price_input": supplier_price_input,
            "supplier_price_output": supplier_price_output,
            "supplier_price_2dp": _to_2dp(supplier_price),
            "supplier_price_input_2dp": _to_2dp(supplier_price_input),
            "supplier_price_output_2dp": _to_2dp(supplier_price_output),
            "cost": computed_cost,
            "cost_input": computed_cost_input,
            "cost_output": computed_cost_output,
            "cost_decimal": computed_cost_decimal,
            "cost_input_decimal": computed_cost_input_decimal,
            "cost_output_decimal": computed_cost_output_decimal,
            "price_display": (
                f"{computed_cost_decimal:.2f} per image"
                if (category_lower == "image" and computed_cost_decimal is not None)
                else None
            ),
            "is_active": bool(params.get("is_active")) if params.get("is_active") is not None else False,
        }

    def _is_system_write_confirmation(self, query: str, history: List[Dict[str, Any]], params: Dict[str, Any]) -> bool:
        if bool(params.get("confirm")):
            return True

        text = str(query or "").strip().lower()
        if text and any(token in text for token in self._SYSTEM_WRITE_CONFIRM_KEYWORDS):
            return True

        last_assistant = None
        for item in reversed(history or []):
            if str(item.get("role") or "").strip().lower() == "assistant":
                last_assistant = str(item.get("content") or "")
                break
        if last_assistant and ("确认" in last_assistant or "confirm" in last_assistant.lower()):
            if text and any(token in text for token in {"确认", "confirm", "继续", "执行", "应用", "yes", "ok", "好的"}):
                return True

        return False

    def _extract_provider_hint_from_text(self, text: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""

        lowered = raw.lower()
        provider_aliases = [
            "kie", "kei", "openai", "anthropic", "google", "gemini", "doubao", "ark", "grsai", "stability", "runway", "tencent",
        ]
        for alias in provider_aliases:
            if alias in lowered:
                return alias
        return ""

    def _infer_provider_hint_from_history(self, query: str, history: List[Dict[str, Any]]) -> str:
        direct = self._extract_provider_hint_from_text(query)
        if direct:
            return direct

        for msg in reversed(history or []):
            role = str(msg.get("role") or "").strip().lower()
            if role != "user":
                continue
            hint = self._extract_provider_hint_from_text(str(msg.get("content") or ""))
            if hint:
                return hint
        return ""

    def _build_system_management_action_summary(self, actions: List[AgentAction]) -> str:
        if not actions:
            return ""

        lines: List[str] = []
        for action in actions:
            if action.status != "completed":
                continue

            if action.tool == "search_system_api_settings" and isinstance(action.result, dict):
                count = int(action.result.get("count") or 0)
                items = action.result.get("items") if isinstance(action.result.get("items"), list) else []
                lines.append(f"查询结果：共 {count} 条。")
                for idx, row in enumerate(items[:8], start=1):
                    provider = row.get("provider") or "-"
                    category = row.get("category") or "-"
                    model = row.get("model") or "-"
                    pricing = row.get("api_pricing") if isinstance(row.get("api_pricing"), dict) else {}
                    unit_type = pricing.get("unit_type") or "per_call"
                    cost_input = pricing.get("cost_input", 0)
                    cost_output = pricing.get("cost_output", 0)
                    cost = pricing.get("cost", 0)
                    if unit_type in {"per_token", "per_1k_tokens", "per_million_tokens"}:
                        price_text = f"{unit_type} in/out={cost_input}/{cost_output}"
                    elif str(category).strip().lower() == "image":
                        price_text = f"per_image={cost}"
                    else:
                        price_text = f"{unit_type} cost={cost}"
                    lines.append(f"{idx}. {provider} | {category} | {model} | {price_text}")

            if action.tool == "upsert_system_api_pricing" and isinstance(action.result, dict):
                lines.append(
                    "写入结果："
                    f"{action.result.get('action')} | "
                    f"{action.result.get('provider')}/{action.result.get('category')}/{action.result.get('model')}"
                )

        return "\n".join(lines).strip()
    def _safe_json_dict_or_none(self, value: Any) -> Optional[Dict[str, Any]]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            try:
                parsed = json.loads(raw)
            except Exception:
                return None
            return parsed if isinstance(parsed, dict) else None
        return None

    def _repair_invalid_user_config_rows(
        self,
        session: Session,
        user_id: int,
        category: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> None:
        q = session.query(
            APISetting.id,
            cast(APISetting.config, String).label("config_raw"),
        ).filter(APISetting.user_id == user_id)
        if category:
            q = q.filter(APISetting.category == category)
        if provider:
            q = q.filter(APISetting.provider == provider)

        bad_ids: List[int] = []
        for row in q.all():
            if self._safe_json_dict_or_none(row.config_raw) is None:
                bad_ids.append(row.id)

        if bad_ids:
            logger.warning(
                "Repair invalid api_settings.config rows | user_id=%s category=%s provider=%s ids=%s",
                user_id,
                category,
                provider,
                bad_ids,
            )
            session.query(APISetting).filter(APISetting.id.in_(bad_ids)).update(
                {APISetting.config: {}},
                synchronize_session=False,
            )
            session.commit()

    def _repair_invalid_system_config_rows(self, session: Session, category: Optional[str] = None) -> None:
        q = session.query(
            SystemAPISetting.id,
            cast(SystemAPISetting.config, String).label("config_raw"),
        )
        if category:
            q = q.filter(SystemAPISetting.category == category)

        bad_ids: List[int] = []
        for row in q.all():
            if self._safe_json_dict_or_none(row.config_raw) is None:
                bad_ids.append(row.id)

        if bad_ids:
            logger.warning(
                "Repair invalid system_api_settings.config rows | category=%s ids=%s",
                category,
                bad_ids,
            )
            session.query(SystemAPISetting).filter(SystemAPISetting.id.in_(bad_ids)).update(
                {SystemAPISetting.config: {}},
                synchronize_session=False,
            )
            session.commit()

    def _is_deprecated_system_config(self, config_value: Any, deprecated_flag: Any = None) -> bool:
        if isinstance(deprecated_flag, bool):
            if deprecated_flag:
                return True
        elif deprecated_flag is not None and str(deprecated_flag).strip().lower() in {"1", "true", "yes", "y", "on"}:
            return True
        cfg = self._safe_json_dict_or_none(config_value) or {}
        return bool(
            cfg.get("deprecated")
            or cfg.get("is_deprecated")
            or cfg.get("disable_api")
        )

    def _normalize_api_keys(self, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            raw_items = value.replace("\r", "\n").replace(",", "\n").split("\n")
        elif isinstance(value, list):
            raw_items = value
        else:
            raw_items = [value]

        result: List[str] = []
        seen = set()
        for item in raw_items:
            key = str(item or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(key)
        return result

    def _pick_runtime_api_key(self, config_value: Any, fallback_key: Any = None) -> str:
        cfg = self._safe_json_dict_or_none(config_value) or {}
        pooled = self._normalize_api_keys(cfg.get("provider_api_keys"))
        if pooled:
            strategy = str(cfg.get("provider_api_key_strategy") or "random").strip().lower()
            if strategy == "round_robin":
                cursor_key = str(cfg.get("provider") or cfg.get("__provider") or "default")
                cursor = int(self._provider_key_cursors.get(cursor_key, 0))
                selected = pooled[cursor % len(pooled)]
                self._provider_key_cursors[cursor_key] = cursor + 1
                return selected
            if strategy == "weighted":
                raw_weights = cfg.get("provider_api_key_weights")
                if isinstance(raw_weights, list) and raw_weights:
                    weights = []
                    for i in range(len(pooled)):
                        try:
                            w = float(raw_weights[i]) if i < len(raw_weights) else 1.0
                        except Exception:
                            w = 1.0
                        weights.append(w if w > 0 else 1.0)
                    return random.choices(pooled, weights=weights, k=1)[0]
            return random.choice(pooled)
        return str(fallback_key or "").strip()

    def get_api_config(self, provider: str, user_id: int = 1, category: Optional[str] = None) -> Dict[str, Any]:
        """
        Resolves API configuration by:
        1) finding user's active api_settings row in the given category,
        2) using that row's provider+model to match system_api_settings.
        """
        defaults = {
            "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4-turbo-preview"},
            "anthropic": {"base_url": "https://api.anthropic.com", "model": "claude-3-opus-20240229"},
            "stability": {"base_url": "https://api.stability.ai", "model": "stable-diffusion-xl-1024-v1-0"},
            "runway": {"base_url": "https://api.runwayml.com", "model": "gen-2"},
            "elevenlabs": {"base_url": "https://api.elevenlabs.io/v1", "model": "premade/Adam"},
            "ark": {"base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "deepseek-v3-2-251201"},
            "doubao": {"base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "doubao-seedream-4-5-251128"},
            "grsai": {"base_url": "https://api.grsai.com/v1", "model": "g-image-v1"},
            "tencent": {"base_url": "https://hunyuan.tencentcloudapi.com", "model": "hunyuan-vision"},
        }

        try:
            with SessionLocal() as session:
                resolved_category = str(category or "").strip()
                if not resolved_category:
                    logger.warning("Missing category when resolving API config | user_id=%s", user_id)
                    return {}

                self._repair_invalid_user_config_rows(session, user_id, category=resolved_category)
                self._repair_invalid_system_config_rows(session, category=resolved_category)

                active_user_setting = session.query(APISetting).filter(
                    APISetting.user_id == user_id,
                    APISetting.category == resolved_category,
                    APISetting.is_active == True,
                ).order_by(APISetting.id.desc()).first()

                if not active_user_setting:
                    logger.warning(
                        "No active user api setting found | user_id=%s category=%s",
                        user_id,
                        resolved_category,
                    )
                    return {}

                target_provider = str(active_user_setting.provider or "").strip()
                target_model = str(active_user_setting.model or "").strip()
                if not target_provider or not target_model:
                    logger.warning(
                        "Active user setting missing provider/model | user_id=%s category=%s setting_id=%s provider=%s model=%s",
                        user_id,
                        resolved_category,
                        active_user_setting.id,
                        active_user_setting.provider,
                        active_user_setting.model,
                    )
                    return {}

                setting = session.query(SystemAPISetting).filter(
                    SystemAPISetting.category == resolved_category,
                    SystemAPISetting.provider == target_provider,
                    SystemAPISetting.model == target_model,
                ).order_by(SystemAPISetting.id.desc()).first()

                if setting:
                    if self._is_deprecated_system_config(setting.config, getattr(setting, "deprecated", None)):
                        logger.warning(
                            "Blocked deprecated system api setting | user_id=%s category=%s provider=%s model=%s setting_id=%s",
                            user_id,
                            resolved_category,
                            target_provider,
                            target_model,
                            setting.id,
                        )
                        return {}
                    return {
                        "provider": setting.provider,
                        "api_key": self._pick_runtime_api_key({**(setting.config or {}), "provider": setting.provider}, setting.api_key),
                        "base_url": setting.base_url or defaults.get(target_provider, {}).get("base_url"),
                        "model": setting.model or defaults.get(target_provider, {}).get("model"),
                        "config": setting.config or {}
                    }
                logger.warning(
                    "No matching system api setting by provider+model | user_id=%s category=%s provider=%s model=%s",
                    user_id,
                    resolved_category,
                    target_provider,
                    target_model,
                )
        except Exception as e:
            logger.error(f"Error fetching system settings for {provider}: {e}")

        return {}

    def get_active_llm_config(self, user_id: int = 1, category: str = "LLM") -> Dict[str, Any]:
        """
        Retrieves active API configuration by category by matching
        active user api_settings(provider+model) -> system_api_settings.
        """
        try:
            with SessionLocal() as session:
                resolved_category = str(category or "LLM").strip() or "LLM"

                self._repair_invalid_user_config_rows(session, user_id, category=resolved_category)
                self._repair_invalid_system_config_rows(session, category=resolved_category)

                def _is_endpoint_compatible(cfg: Dict[str, Any]) -> bool:
                    endpoint = str((cfg or {}).get("endpoint") or "").strip().lower()
                    if not endpoint:
                        return True
                    if resolved_category != "LLM":
                        return True
                    if "/chat/completions" in endpoint:
                        return True
                    media_tokens = ["/draw", "/video", "image2video", "video-synthesis", "generations/tasks"]
                    return not any(token in endpoint for token in media_tokens)

                active_user_setting = session.query(APISetting).filter(
                    APISetting.user_id == user_id,
                    APISetting.category == resolved_category,
                    APISetting.is_active == True
                ).order_by(APISetting.id.desc()).first()

                if not active_user_setting:
                    logger.warning(
                        "No active user api setting found | user_id=%s category=%s",
                        user_id,
                        resolved_category,
                    )
                    return {}

                selected: Optional[SystemAPISetting] = None
                selected_source = "none"

                target_provider = active_user_setting.provider if active_user_setting else None
                target_model = active_user_setting.model if active_user_setting else None

                if target_provider and target_model:
                    selected = session.query(SystemAPISetting).filter(
                        SystemAPISetting.category == resolved_category,
                        SystemAPISetting.provider == target_provider,
                        SystemAPISetting.model == target_model,
                    ).order_by(SystemAPISetting.id.desc()).first()
                    if selected:
                        selected_source = f"system_by_user_provider_model:{target_provider}/{target_model}->{selected.id}"

                if not selected and active_user_setting:
                    logger.warning(
                        "No matching system api setting by provider+model | user_id=%s category=%s user_setting_id=%s provider=%s model=%s",
                        user_id,
                        resolved_category,
                        active_user_setting.id,
                        target_provider,
                        target_model,
                    )

                if selected:
                    if self._is_deprecated_system_config(selected.config, getattr(selected, "deprecated", None)):
                        logger.warning(
                            "Blocked deprecated active system api config | user_id=%s category=%s provider=%s model=%s setting_id=%s",
                            user_id,
                            resolved_category,
                            selected.provider,
                            selected.model,
                            selected.id,
                        )
                        return {}
                    if not _is_endpoint_compatible(selected.config or {}):
                        logger.warning(
                            "Skipping incompatible %s setting | user_id=%s setting_id=%s provider=%s model=%s endpoint=%s",
                            resolved_category,
                            user_id,
                            selected.id,
                            selected.provider,
                            selected.model,
                            (selected.config or {}).get("endpoint"),
                        )
                        selected = None

                if selected:
                    from app.api.settings import DEFAULTS
                    default = DEFAULTS.get(selected.provider, {})
                    merged_config = dict(selected.config or default.get("config", {}) or {})
                    merged_config["__resolved_setting_id"] = selected.id
                    merged_config["__resolved_source"] = selected_source
                    merged_config["__resolved_category"] = getattr(selected, "category", resolved_category)
                    merged_config["__selection_source"] = "system_only"
                    if active_user_setting:
                        merged_config["__resolved_user_setting_id"] = active_user_setting.id

                    logger.info(
                        "Resolved active API config | user_id=%s category=%s source=%s selection_source=system_only setting_id=%s provider=%s model=%s endpoint=%s",
                        user_id,
                        resolved_category,
                        selected_source,
                        selected.id,
                        selected.provider,
                        selected.model,
                        selected.base_url or default.get("base_url"),
                    )

                    return {
                        "provider": selected.provider,
                        "api_key": self._pick_runtime_api_key({**(selected.config or {}), "provider": selected.provider}, selected.api_key),
                        "base_url": selected.base_url or default.get("base_url"),
                        "model": selected.model or default.get("model"),
                        "config": merged_config
                    }
        except Exception as e:
            logger.error(f"Error fetching active API config ({category}): {e}")

        return {}

    def get_system_default_llm_config(self, user_id: int = 1, category: str = "LLM") -> Dict[str, Any]:
        resolved_category = "LLM"

        try:
            with SessionLocal() as session:
                def _provider_key_pool(provider_name: str) -> List[str]:
                    rows = session.query(SystemAPISetting).filter(
                        SystemAPISetting.provider == provider_name,
                    ).order_by(SystemAPISetting.id.asc()).all()
                    merged: List[str] = []
                    seen = set()
                    for item in rows:
                        cfg = self._safe_json_dict_or_none(item.config) or {}
                        pooled = self._normalize_api_keys(cfg.get("provider_api_keys"))
                        if not pooled:
                            single = str(item.api_key or "").strip()
                            pooled = [single] if single else []
                        for key in pooled:
                            if key in seen:
                                continue
                            seen.add(key)
                            merged.append(key)
                    return merged

                selected = session.query(SystemAPISetting).filter(
                    SystemAPISetting.category == resolved_category,
                    SystemAPISetting.is_active == True,
                ).order_by(SystemAPISetting.id.desc()).first()

                def _runtime_key(setting: Optional[SystemAPISetting]) -> str:
                    if not setting:
                        return ""
                    cfg = self._safe_json_dict_or_none(setting.config) or {}
                    direct = self._pick_runtime_api_key({**cfg, "provider": setting.provider}, setting.api_key)
                    if str(direct or "").strip():
                        return str(direct or "").strip()
                    pooled = _provider_key_pool(str(setting.provider or "").strip())
                    return pooled[0] if pooled else ""

                def _is_usable(setting: Optional[SystemAPISetting]) -> bool:
                    if not setting:
                        return False
                    if self._is_deprecated_system_config(setting.config, getattr(setting, "deprecated", None)):
                        return False
                    picked_key = _runtime_key(setting)
                    return bool(str(picked_key or "").strip())

                def _reject_reason(setting: Optional[SystemAPISetting]) -> str:
                    if not setting:
                        return "missing"
                    if self._is_deprecated_system_config(setting.config, getattr(setting, "deprecated", None)):
                        return "deprecated"
                    if not _runtime_key(setting):
                        return "no_runtime_key"
                    return "ok"

                if not _is_usable(selected):
                    candidates = session.query(SystemAPISetting).filter(
                        SystemAPISetting.category == resolved_category,
                        SystemAPISetting.is_active == True,
                    ).order_by(SystemAPISetting.id.desc()).all()

                    for cand in candidates[:10]:
                        logger.info(
                            "[agent.config.resolve] candidate_check category=%s setting_id=%s provider=%s model=%s active=%s reason=%s",
                            resolved_category,
                            cand.id,
                            cand.provider,
                            cand.model,
                            cand.is_active,
                            _reject_reason(cand),
                        )
                    selected = next((row for row in candidates if _is_usable(row)), None)

                if not selected:
                    logger.warning("[agent.config.resolve] no usable active system LLM setting found | category=%s", resolved_category)
                    return {}

                from app.api.settings import DEFAULTS
                default = DEFAULTS.get(selected.provider, {})
                merged_config = dict(selected.config or default.get("config", {}) or {})
                merged_config["__selection_source"] = "system_default_llm"
                merged_config["__resolved_setting_id"] = selected.id
                merged_config["__resolved_category"] = resolved_category

                return {
                    "provider": selected.provider,
                    "api_key": _runtime_key(selected),
                    "base_url": selected.base_url or default.get("base_url"),
                    "model": selected.model or default.get("model"),
                    "config": merged_config,
                }
        except Exception as e:
            logger.error("Error fetching default system LLM config: %s", e)
        return {}

    def _has_project_access(self, db: Session, user_id: int, project_id: int) -> bool:
        owned = db.query(Project.id).filter(Project.id == project_id, Project.owner_id == user_id).first()
        if owned:
            return True
        shared = db.query(ProjectShare.id).filter(ProjectShare.project_id == project_id, ProjectShare.user_id == user_id).first()
        return bool(shared)

    def _default_agent_tool_policy(self) -> Dict[str, Any]:
        return {
            "default_allow": True,
            "roles": {
                "user": {"allow": [], "deny": ["internet_search"]},
                "authorized": {"allow": ["internet_search"], "deny": []},
                "superuser": {"allow": ["*"], "deny": []},
            },
        }

    def _normalize_agent_tool_policy(self, value: Any) -> Dict[str, Any]:
        base = self._default_agent_tool_policy()
        payload = self._safe_json_dict_or_none(value) or {}
        if isinstance(payload.get("agent_tool_policy"), dict):
            payload = payload.get("agent_tool_policy") or {}

        if "default_allow" in payload:
            base["default_allow"] = bool(payload.get("default_allow"))

        roles_raw = payload.get("roles") if isinstance(payload.get("roles"), dict) else {}
        normalized_roles: Dict[str, Dict[str, List[str]]] = {}
        for role_name in ["user", "authorized", "superuser"]:
            role_cfg = roles_raw.get(role_name) if isinstance(roles_raw.get(role_name), dict) else {}
            allow = [str(item).strip() for item in (role_cfg.get("allow") or []) if str(item).strip()]
            deny = [str(item).strip() for item in (role_cfg.get("deny") or []) if str(item).strip()]
            normalized_roles[role_name] = {
                "allow": list(dict.fromkeys(allow)),
                "deny": list(dict.fromkeys(deny)),
            }
        base["roles"] = normalized_roles
        return base

    def _get_agent_tool_policy(self, db: Session) -> Dict[str, Any]:
        row = db.query(SystemAPISetting).filter(
            SystemAPISetting.category == "System_Payment",
            SystemAPISetting.provider == "agent_policy",
            SystemAPISetting.model == "tool_acl",
        ).order_by(SystemAPISetting.id.desc()).first()
        if not row:
            return self._default_agent_tool_policy()
        return self._normalize_agent_tool_policy(row.config)

    def _resolve_agent_role(self, user: User) -> str:
        if bool(getattr(user, "is_superuser", False)):
            return "superuser"
        if bool(getattr(user, "is_authorized", False)):
            return "authorized"
        return "user"

    def _is_tool_allowed_by_policy(self, tool: str, role: str, policy: Dict[str, Any]) -> bool:
        roles = policy.get("roles") if isinstance(policy.get("roles"), dict) else {}
        role_cfg = roles.get(role) if isinstance(roles.get(role), dict) else {}
        allow_list = {str(item).strip() for item in (role_cfg.get("allow") or []) if str(item).strip()}
        deny_list = {str(item).strip() for item in (role_cfg.get("deny") or []) if str(item).strip()}

        if "*" in allow_list:
            return True
        if tool in deny_list:
            return False
        if tool in allow_list:
            return True
        return bool(policy.get("default_allow", True))

    def _check_tool_permission(
        self,
        db: Session,
        user: User,
        tool: str,
        project_id: Optional[int],
        policy: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if not user or not bool(getattr(user, "is_active", False)):
            return "User is not active"

        resolved_policy = policy or self._default_agent_tool_policy()
        role = self._resolve_agent_role(user)
        if not self._is_tool_allowed_by_policy(tool, role, resolved_policy):
            return f"Tool '{tool}' blocked by role policy ({role})"

        project_required_tools = {
            "generate_project_asset",
            "generate_image_text_to_image",
            "generate_image_image_to_image",
            "generate_video_text_to_video",
            "generate_video_image_to_video",
            "analyze_script",
            "update_project_metadata",
            "search_project_data",
            "visualize_user_requirement",
        }

        if tool in project_required_tools:
            if not project_id:
                return "Tool requires project context"
            if not self._has_project_access(db, user.id, int(project_id)):
                return "No permission to access this project"

        system_management_tools = {
            "search_system_api_settings",
            "upsert_system_api_pricing",
        }
        if tool in system_management_tools and not bool(getattr(user, "is_superuser", False)):
            return "Only superuser can use system management tools"

        return None

    def _normalize_unit_type_for_system_ai(self, raw: Any) -> str:
        text = str(raw or "per_call").strip() or "per_call"
        allowed = {"per_call", "per_second", "per_minute", "per_token", "per_1k_tokens", "per_million_tokens"}
        return text if text in allowed else "per_call"

    def _safe_non_negative_float(self, value: Any) -> float:
        try:
            parsed = float(value)
            if parsed < 0:
                return 0.0
            return parsed
        except Exception:
            return 0.0

    def _multiplied_cost_to_credit(self, value: Any, multiplier: float) -> int:
        base = self._safe_non_negative_float(value)
        mul = self._safe_non_negative_float(multiplier)
        use_mul = mul if mul > 0 else 1.0
        return max(0, int((base * use_mul) + 0.999999))

    def _safe_json_dict(self, value: Any) -> Dict[str, Any]:
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
            except Exception:
                return {}
            if isinstance(parsed, dict):
                return parsed
            return {}
        return {}

    def _normalize_system_api_billing_config(self, raw_cfg: Any) -> Dict[str, Any]:
        cfg = self._safe_json_dict(raw_cfg)
        pricing = cfg.get("api_pricing") if isinstance(cfg.get("api_pricing"), dict) else {}
        unit_type = self._normalize_unit_type_for_system_ai(pricing.get("unit_type") or cfg.get("billing_unit_type") or "per_call")

        def _to_int(v: Any) -> int:
            try:
                parsed = int(float(v))
                return parsed if parsed > 0 else 0
            except Exception:
                return 0

        return {
            **cfg,
            "api_pricing": {
                "unit_type": unit_type,
                "cost": _to_int(pricing.get("cost") if pricing else cfg.get("billing_cost")),
                "cost_input": _to_int(pricing.get("cost_input") if pricing else cfg.get("billing_cost_input")),
                "cost_output": _to_int(pricing.get("cost_output") if pricing else cfg.get("billing_cost_output")),
            },
        }

    async def process_system_management_command(self, request: AgentRequest, db: Session, user: User) -> AgentResponse:
        if not bool(getattr(user, "is_superuser", False)):
            raise PermissionError("Only superuser can use system management agent")

        llm_config = self.get_system_default_llm_config(user_id=user.id, category="LLM")
        if not llm_config or not llm_config.get("api_key"):
            raise ValueError("No active system default LLM API config found in Settings (System API / category=LLM).")

        merged_context = dict(request.context or {})
        merged_context["agent_mode"] = "system_management"
        merged_context["auth"] = {
            "user_id": user.id,
            "is_superuser": True,
            "is_authorized": bool(getattr(user, "is_authorized", False)),
            "username": getattr(user, "username", None),
        }

        llm_result = await llm_service.analyze_intent_with_system_prompt(
            request.query,
            merged_context,
            request.history or [],
            llm_config,
            self._SYSTEM_MANAGEMENT_PROMPT,
        )
        llm_result = self._normalize_llm_result(llm_result)

        if not (llm_result.get("plan") or []):
            query_text = str(request.query or "").strip().lower()
            list_intent_tokens = [
                "api设置",
                "api 設置",
                "api 设置",
                "api settings",
                "settings",
                "配置",
                "list api",
                "有哪些api",
                "现有哪些api",
            ]
            if any(token in query_text for token in list_intent_tokens):
                llm_result["plan"] = [
                    {
                        "tool": "search_system_api_settings",
                        "parameters": {
                            "limit": 50,
                        },
                    }
                ]
                if not str(llm_result.get("reply") or "").strip():
                    llm_result["reply"] = "已为您检索当前系统 API 设置（最多 50 条）。"

            followup_query_tokens = ["查询", "查一下", "查出来", "查到了吗", "结果", "有没有", "现有", "list", "show"]
            if any(token in query_text for token in followup_query_tokens):
                provider_hint = self._infer_provider_hint_from_history(request.query, request.history or [])
                llm_result["plan"] = [
                    {
                        "tool": "search_system_api_settings",
                        "parameters": {
                            "provider": provider_hint or None,
                            "limit": 50,
                        },
                    }
                ]
                if not str(llm_result.get("reply") or "").strip():
                    llm_result["reply"] = "正在为您查询现有系统 API 配置。"

        actions: List[AgentAction] = []
        updated_data = None
        last_tool_result = None
        pending_write_previews: List[Dict[str, Any]] = []

        for plan_item in llm_result.get("plan", []):
            tool_name = str(plan_item.get("tool") or "").strip()
            if tool_name not in self._SYSTEM_MANAGEMENT_ALLOWED_TOOLS:
                actions.append(AgentAction(
                    tool=tool_name or "unknown",
                    parameters=plan_item.get("parameters") if isinstance(plan_item.get("parameters"), dict) else {},
                    status="failed",
                    result=f"Tool '{tool_name}' is not allowed for system management agent",
                ))
                continue

            params = plan_item.get("parameters") if isinstance(plan_item.get("parameters"), dict) else {}
            for k, v in list(params.items()):
                if v == "__LAST_RESULT__" and last_tool_result is not None:
                    params[k] = last_tool_result

            if tool_name == "upsert_system_api_pricing":
                if not self._is_system_write_confirmation(request.query, request.history or [], params):
                    preview = self._normalize_system_upsert_preview(params)
                    pending_write_previews.append(preview)
                    actions.append(AgentAction(
                        tool=tool_name,
                        parameters=params,
                        status="blocked",
                        result="Write confirmation required. Please explicitly confirm before applying pricing updates.",
                    ))
                    continue

            action = AgentAction(tool=tool_name, parameters=params)
            execution_result = await self._execute_tool(action, db, user, None, llm_config, merged_context, tool_policy=None)

            action.result = execution_result.get("result")
            action.status = execution_result.get("status", "failed")
            if action.status == "completed":
                last_tool_result = action.result
            if execution_result.get("data_update"):
                updated_data = execution_result.get("data_update")
            actions.append(action)

        if pending_write_previews:
            preview_lines = []
            for idx, item in enumerate(pending_write_previews, start=1):
                category_text = str(item.get("category") or "").strip().lower()
                if category_text == "image":
                    preview_lines.append(
                        f"{idx}) provider={item.get('provider')}, category={item.get('category')}, model={item.get('model')}, "
                        f"unit={item.get('unit_type')}, per_image={float(item.get('cost_decimal') or 0):.2f}, multiplier={float(item.get('multiplier_2dp') or 0):.2f}"
                    )
                elif str(item.get("unit_type") or "") in {"per_token", "per_1k_tokens", "per_million_tokens"}:
                    preview_lines.append(
                        f"{idx}) provider={item.get('provider')}, category={item.get('category')}, model={item.get('model')}, "
                        f"unit={item.get('unit_type')}, in/out={float(item.get('cost_input_decimal') or 0):.2f}/{float(item.get('cost_output_decimal') or 0):.2f}, multiplier={float(item.get('multiplier_2dp') or 0):.2f}"
                    )
                else:
                    preview_lines.append(
                        f"{idx}) provider={item.get('provider')}, category={item.get('category')}, model={item.get('model')}, "
                        f"unit={item.get('unit_type')}, cost={float(item.get('cost_decimal') or 0):.2f}, multiplier={float(item.get('multiplier_2dp') or 0):.2f}"
                    )

            confirm_tip = (
                "检测到定价写入操作。请确认后再执行：\n"
                + "\n".join(preview_lines)
                + "\n\n如确认，请回复：确认执行以上更新"
            )

            return AgentResponse(
                reply=confirm_tip,
                actions=actions,
                updated_data={
                    "type": "system_management_write_confirmation_required",
                    "items": pending_write_previews,
                },
                usage=llm_result.get("usage"),
            )

        action_summary = self._build_system_management_action_summary(actions)
        final_reply = str(llm_result.get("reply", "") or "").strip()
        if action_summary:
            final_reply = (final_reply + "\n\n" + action_summary).strip()

        return AgentResponse(
            reply=final_reply,
            actions=actions,
            updated_data=updated_data or {
                "type": "system_management_agent_plan",
                "query": request.query,
                "steps": [{"tool": item.tool, "status": item.status} for item in actions],
            },
            usage=llm_result.get("usage"),
        )

    async def process_command(self, request: AgentRequest, db: Session, user: User) -> AgentResponse:
        user_id = user.id
        project_id = request.project_id or request.context.get("project_id") or request.context.get("projectId")
        
        # Resolve LLM Config from system default/active configuration only (category=LLM).
        llm_config = self.get_system_default_llm_config(user_id=user_id, category="LLM")

        if request.context.get("is_refinement"):
            llm_result = {
                "reply": "Refining asset based on your instructions...",
                "plan": [
                    {
                        "tool": "generate_project_asset",
                        "parameters": {
                            "prompt": request.query,
                            "target_id": request.context.get("target_id") or "",
                            "target_type": request.context.get("target_type"),
                            "target_field": request.context.get("target_field"),
                            "reference_image_url": request.context.get("reference_image_url") 
                        }
                    }
                ]
            }
        else:
            llm_result = await llm_service.analyze_intent(request.query, request.context, request.history, llm_config)
        llm_result = self._normalize_llm_result(llm_result)

        actions: List[AgentAction] = []
        updated_data = None
        last_tool_result = None

        tool_policy = self._get_agent_tool_policy(db)
        merged_context_mode = str((request.context or {}).get("agent_mode") or "project").strip() or "project"

        for plan_item in llm_result.get("plan", []):
            tool_name = str(plan_item.get("tool") or "").strip()
            if tool_name not in self._PROJECT_AGENT_ALLOWED_TOOLS:
                actions.append(AgentAction(
                    tool=tool_name or "unknown",
                    parameters=plan_item.get("parameters") if isinstance(plan_item.get("parameters"), dict) else {},
                    status="failed",
                    result=f"Tool '{tool_name}' is not allowed for project agent mode ({merged_context_mode})",
                ))
                continue

            params = plan_item["parameters"]
            for k, v in params.items():
                if v == "__LAST_RESULT__" and last_tool_result:
                    params[k] = last_tool_result

            action = AgentAction(
                tool=tool_name,
                parameters=params
            )
            
            execution_result = await self._execute_tool(action, db, user, project_id, llm_config, request.context, tool_policy=tool_policy)
            
            action.result = execution_result["result"]
            action.status = execution_result["status"]
            
            if action.status == "completed":
                last_tool_result = action.result
            
            if execution_result.get("data_update"):
                updated_data = execution_result["data_update"]
                
            actions.append(action)

        final_reply = llm_result.get("reply", "")
        # ... logic to append images ...
            
        return AgentResponse(
            reply=final_reply,
            actions=actions,
            updated_data=updated_data or {
                "type": "agent_plan_visualization",
                "query": request.query,
                "steps": [
                    {
                        "tool": item.tool,
                        "status": item.status,
                    }
                    for item in actions
                ],
            },
            usage=llm_result.get("usage")
        )

    async def _execute_tool(self, action: AgentAction, db: Session, user: User, project_id: str = None, llm_config: Any = None, context: Dict[str, Any] = None, tool_policy: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        tool = action.tool
        params = action.parameters
        user_id = user.id
        if context is None: context = {}
        agent_mode = str((context or {}).get("agent_mode") or "project").strip() or "project"

        if agent_mode == "system_management":
            if tool not in self._SYSTEM_MANAGEMENT_ALLOWED_TOOLS:
                return {"status": "failed", "result": f"Tool '{tool}' is not allowed in system management mode"}
        else:
            if tool in self._SYSTEM_MANAGEMENT_ALLOWED_TOOLS:
                return {"status": "failed", "result": f"Tool '{tool}' is only allowed in system management mode"}

        try:
            normalized_project_id = int(project_id) if project_id is not None else None
        except Exception:
            normalized_project_id = None

        denied_reason = self._check_tool_permission(db, user, tool, normalized_project_id, policy=tool_policy)
        if denied_reason:
            return {"status": "failed", "result": f"Permission denied: {denied_reason}"}
        
        # Helper for billing checks
        def check_and_deduct_callback(task_type, details, operation):
            provider = llm_config.get("provider") if llm_config else None
            model = llm_config.get("model") if llm_config else None
            # 1. Check Balance
            billing_service.check_balance(db, user_id, task_type, provider, model)
            # 2. Execute
            result = operation()
            # 3. Deduct
            billing_service.deduct_credits(db, user_id, task_type, provider, model, details)
            return result

        if tool == "search_system_api_settings":
            provider = str(params.get("provider") or "").strip()
            category = str(params.get("category") or "").strip()
            model = str(params.get("model") or "").strip()
            try:
                limit = int(params.get("limit") or 20)
            except Exception:
                limit = 20
            limit = max(1, min(50, limit))

            query = db.query(SystemAPISetting)
            if provider:
                query = query.filter(SystemAPISetting.provider == provider)
            if category:
                query = query.filter(SystemAPISetting.category == category)
            if model:
                query = query.filter(SystemAPISetting.model.ilike(f"%{model}%"))

            rows = query.order_by(SystemAPISetting.id.desc()).limit(limit).all()
            items = []
            for row in rows:
                cfg = self._safe_json_dict(row.config)
                api_pricing = self._normalize_system_api_billing_config(cfg).get("api_pricing") or {}
                items.append({
                    "id": row.id,
                    "name": row.name,
                    "provider": row.provider,
                    "category": row.category,
                    "model": row.model,
                    "base_url": row.base_url,
                    "is_active": bool(row.is_active),
                    "api_pricing": api_pricing,
                })

            providers = sorted({str(item.get("provider") or "").strip() for item in items if str(item.get("provider") or "").strip()})
            categories = sorted({str(item.get("category") or "").strip() for item in items if str(item.get("category") or "").strip()})
            summary = {
                "count": len(items),
                "providers": providers,
                "categories": categories,
            }

            return {
                "status": "completed",
                "result": {
                    "count": len(items),
                    "items": items,
                    "summary": summary,
                },
                "data_update": {
                    "type": "system_api_search_result",
                    "result": {
                        "count": len(items),
                        "items": items,
                        "summary": summary,
                    },
                },
            }

        if tool == "upsert_system_api_pricing":
            provider = str(params.get("provider") or "").strip()
            category = str(params.get("category") or "LLM").strip() or "LLM"
            category_lower = category.lower()
            model = str(params.get("model") or "").strip()
            if not provider or not model:
                return {"status": "failed", "result": "provider and model are required"}

            unit_type = self._normalize_unit_type_for_system_ai(params.get("unit_type") or "per_call")
            multiplier = self._safe_non_negative_float(params.get("multiplier") or 1.0)
            if multiplier <= 0:
                multiplier = 1.0

            supplier_price = self._first_non_negative_float_from_keys(params, [
                "supplier_price", "price_per_image", "supplier_price_per_image", "our_price_usd", "price_usd", "price",
            ])
            supplier_price_input = self._first_non_negative_float_from_keys(params, [
                "supplier_price_input", "price_input", "input_price", "our_price_input_usd",
            ])
            supplier_price_output = self._first_non_negative_float_from_keys(params, [
                "supplier_price_output", "price_output", "output_price", "our_price_output_usd",
            ])

            if category_lower == "image" and supplier_price is None:
                supplier_price = self._first_non_negative_float_from_keys(params, ["cost", "cost_per_image", "image_cost"])

            cost = self._multiplied_cost_to_credit(supplier_price, multiplier)
            cost_input = self._multiplied_cost_to_credit(supplier_price_input, multiplier)
            cost_output = self._multiplied_cost_to_credit(supplier_price_output, multiplier)

            row = db.query(SystemAPISetting).filter(
                SystemAPISetting.provider == provider,
                SystemAPISetting.category == category,
                SystemAPISetting.model == model,
            ).order_by(SystemAPISetting.id.desc()).first()

            now_iso = datetime.utcnow().isoformat()
            patch_cfg = self._normalize_system_api_billing_config({
                "api_pricing": {
                    "unit_type": unit_type,
                    "cost": cost,
                    "cost_input": cost_input,
                    "cost_output": cost_output,
                }
            })
            patch_cfg["supplier_pricing"] = {
                "unit_type": unit_type,
                "supplier_price": supplier_price,
                "supplier_price_input": supplier_price_input,
                "supplier_price_output": supplier_price_output,
                "source": "system_management_agent",
                "updated_at": now_iso,
            }
            patch_cfg["pricing_scheme"] = {
                "strategy": "supplier_price_x_multiplier",
                "multiplier": multiplier,
                "updated_at": now_iso,
            }

            action = "update"
            if row:
                cfg = self._safe_json_dict(row.config)
                row.config = {**cfg, **patch_cfg}
                if params.get("base_url"):
                    row.base_url = str(params.get("base_url") or "").strip()
                if params.get("name"):
                    row.name = str(params.get("name") or "").strip()
                if params.get("is_active") is not None:
                    row.is_active = bool(params.get("is_active"))
            else:
                action = "create"
                row = SystemAPISetting(
                    name=str(params.get("name") or f"{provider} {model}").strip(),
                    category=category,
                    provider=provider,
                    api_key="",
                    base_url=str(params.get("base_url") or "").strip() or None,
                    model=model,
                    deprecated=False,
                    config=patch_cfg,
                    is_active=bool(params.get("is_active")) if params.get("is_active") is not None else False,
                )
                db.add(row)

            db.commit()

            payload = {
                "action": action,
                "setting_id": row.id,
                "provider": provider,
                "category": category,
                "model": model,
                "api_pricing": patch_cfg.get("api_pricing") or {},
                "multiplier": multiplier,
            }
            return {
                "status": "completed",
                "result": payload,
                "data_update": {
                    "type": "system_ai_pricing_updated",
                    "payload": payload,
                },
            }

        if tool == "generate_project_asset":
            print(f"DEBUG: Executing generate_project_asset. ProjectID: {project_id}, Target: {params.get('target_id')}")
            prompt = params.get("prompt", "")
            target_type = params.get("target_type")
            target_id = str(params.get("target_id") or "").strip().strip('"').strip("'")
            prompt = self._enrich_prompt_if_possible(prompt, project_id, target_id=target_id)
            target_field = params.get("target_field")
            reference_image_url = params.get("reference_image_url")

            # Resolve Visual Dependencies if Entity
            if (target_type == "entity" or target_type == "subject") and target_id:
                try:
                     with SessionLocal() as session:
                         # Try to find entity by ID
                         # Assuming target_id is the numeric ID
                         e_id = int(target_id) if target_id.isdigit() else None
                         entity = None
                         if e_id:
                             entity = session.query(Entity).filter(Entity.id == e_id).first()
                         
                         if entity and entity.visual_dependencies:
                             # If reference_image_url is None, init as list
                             if reference_image_url is None: reference_image_url = []
                             elif isinstance(reference_image_url, str): reference_image_url = [reference_image_url]
                             
                             deps = entity.visual_dependencies # List of names
                             if isinstance(deps, list):
                                 for dep_name in deps:
                                     # Try match by name or ID
                                     dep_entity = session.query(Entity).filter(
                                         Entity.project_id == int(project_id), 
                                         Entity.name == str(dep_name)
                                     ).first()
                                     if not dep_entity and str(dep_name).isdigit():
                                          dep_entity = session.query(Entity).filter(Entity.id == int(dep_name)).first()

                                     if dep_entity and dep_entity.image_url:
                                         print(f"DEBUG: Found dependency image for {dep_name}: {dep_entity.image_url}")
                                         if dep_entity.image_url not in reference_image_url:
                                             reference_image_url.append(dep_entity.image_url)
                except Exception as e:
                    print(f"Error resolving dependencies: {e}")

            if isinstance(reference_image_url, list):
                 if len(reference_image_url) == 0:
                     reference_image_url = None
            
            print(f"DEBUG: Cleaned Target ID: '{target_id}'")
            
            # --- Billing Injection ---
            # Determine provider/model used in internal generator
            # This is tricky because _generate_image_with_metadata resolves provider internally
            # We will use the main llm_config provider as a proxy OR default to 'stability' to be safe
            # But wait, _generate_image_with_metadata uses llm_config to pick provider
            gen_provider = llm_config.get("provider", "stability") if llm_config else "stability"
            gen_model = llm_config.get("model", "") if llm_config else ""
            image_task_type = tool_billing_taxonomy_service.resolve_agent_tool_task_type(tool, fallback="image_gen")
            
            # 1. Check Balance
            billing_service.check_balance(db, user_id, image_task_type, gen_provider, gen_model)
            
            try:
                gen_result = await self._generate_image_with_metadata(prompt, llm_config, user_id=user_id, reference_image_url=reference_image_url)
                
                # 2. Deduct Credits
                # Only if successful
                billing_service.deduct_credits(db, user_id, image_task_type, gen_provider, gen_model, {"item": "image_from_chat"})
                
                generated_url = gen_result["url"]
                gen_meta = gen_result["metadata"]
                
                return self._save_and_bind_asset(
                    project_id, generated_url, "image", prompt, 
                    {**gen_meta, "target_id": target_id, "target_type": target_type},
                    target_id, target_type, target_field
                )
            except Exception as e:
                # No Charge on Failure
                return {"status": "failed", "result": f"Failed to generate asset: {str(e)}"}
            
        elif tool == "generate_image_text_to_image":
            gen_provider = llm_config.get("provider", "stability") if llm_config else "stability"
            gen_model = llm_config.get("model", "") if llm_config else ""
            image_task_type = tool_billing_taxonomy_service.resolve_agent_tool_task_type(tool, fallback="image_gen")
            billing_service.check_balance(db, user_id, image_task_type, gen_provider, gen_model)
            
            try:
                prompt = params.get("prompt", "")
                prompt = self._enrich_prompt_if_possible(prompt, project_id)
                gen_result = await self._generate_image_with_metadata(prompt, llm_config, user_id=user_id)
                
                billing_service.deduct_credits(db, user_id, image_task_type, gen_provider, gen_model, {"item": "image_from_tool"})

                return self._save_and_bind_asset(
                    project_id, gen_result["url"], "image", prompt, 
                    gen_result["metadata"], 
                    None, "generic"
                )
            except Exception as e:
                return {"status": "failed", "result": f"Failed: {str(e)}"}

        elif tool == "generate_image_image_to_image":
            gen_provider = llm_config.get("provider", "stability") if llm_config else "stability"
            gen_model = llm_config.get("model", "") if llm_config else ""
            image_task_type = tool_billing_taxonomy_service.resolve_agent_tool_task_type(tool, fallback="image_gen")
            billing_service.check_balance(db, user_id, image_task_type, gen_provider, gen_model)
            
            try:
                prompt = params.get("prompt", "")
                prompt = self._enrich_prompt_if_possible(prompt, project_id)
                image_url = params.get("image_url", "")
                gen_result = await self._generate_image_with_metadata(prompt, llm_config, user_id=user_id, reference_image_url=image_url)
                
                billing_service.deduct_credits(db, user_id, image_task_type, gen_provider, gen_model, {"item": "i2i_from_tool"})
                
                return self._save_and_bind_asset(
                    project_id, gen_result["url"], "image", prompt, 
                    gen_result["metadata"], 
                    None, "generic"
                )
            except Exception as e:
                return {"status": "failed", "result": f"Failed: {str(e)}"}

        elif tool == "generate_video_text_to_video":
            gen_provider = llm_config.get("provider", "runway") if llm_config else "runway"
            gen_model = llm_config.get("model", "") if llm_config else ""
            video_task_type = tool_billing_taxonomy_service.resolve_agent_tool_task_type(tool, fallback="video_gen")
            billing_service.check_balance(db, user_id, video_task_type, gen_provider, gen_model)

            try:
                prompt = params.get("prompt", "")
                prompt = self._enrich_prompt_if_possible(prompt, project_id)
                target_id = context.get("target_id")
                target_type = context.get("target_type", "scene_item")
                duration = -1

                gen_result = await self._generate_video_with_metadata(prompt, llm_config, user_id=user_id, duration=duration)

                billing_service.deduct_credits(db, user_id, video_task_type, gen_provider, gen_model, {"item": "video_from_tool"})

                return self._save_and_bind_asset(
                    project_id, gen_result["url"], "video", prompt,
                    {**gen_result["metadata"], "target_id": target_id, "target_type": target_type},
                    target_id, target_type
                )
            except Exception as e:
                return {"status": "failed", "result": f"Failed: {str(e)}"}

        elif tool == "generate_video_image_to_video":
            gen_provider = llm_config.get("provider", "runway") if llm_config else "runway"
            gen_model = llm_config.get("model", "") if llm_config else ""
            video_task_type = tool_billing_taxonomy_service.resolve_agent_tool_task_type(tool, fallback="video_gen")
            billing_service.check_balance(db, user_id, video_task_type, gen_provider, gen_model)
            
            try:
                prompt = params.get("prompt", "")
                prompt = self._enrich_prompt_if_possible(prompt, project_id)
                
                image_candidate = params.get("image_url")
                if not image_candidate:
                    image_candidate = context.get("start_frame") or context.get("reference_image_url")
                
                last_frame_candidate = params.get("last_frame_url")
                if not last_frame_candidate:
                    last_frame_candidate = context.get("end_frame")
                    
                target_id = context.get("target_id")
                video_mode = context.get("video_mode", "default")
                
                if video_mode == "cross_scene" and target_id:
                    pass # logic placeholder
                elif video_mode == "first_frame":
                    last_frame_candidate = None
                    
                image_url = None
                last_frame_url = last_frame_candidate
                
                if isinstance(image_candidate, list):
                    if len(image_candidate) > 0:
                        image_url = image_candidate[0]
                        if len(image_candidate) > 1 and not last_frame_url:
                            last_frame_url = image_candidate[1]
                else:
                    image_url = image_candidate

                if isinstance(last_frame_url, list):
                    last_frame_url = last_frame_url[0] if len(last_frame_url) > 0 else None

                target_type = context.get("target_type", "scene_item")
                duration = -1

                gen_result = await self._generate_video_with_metadata(
                    prompt, 
                    llm_config, 
                    user_id=user_id,
                    reference_image_url=image_url, 
                    last_frame_url=last_frame_url,
                    duration=duration
                )
                
                billing_service.deduct_credits(db, user_id, video_task_type, gen_provider, gen_model, {"item": "i2v_from_tool"})
                
                return self._save_and_bind_asset(
                    project_id, gen_result["url"], "video", prompt, 
                    {**gen_result["metadata"], "target_id": target_id, "target_type": target_type},
                    target_id, target_type
                )
            except Exception as e:
                return {"status": "failed", "result": f"Failed: {str(e)}"}
            
        elif tool == "create_project":
            new_id = f"proj_{uuid.uuid4().hex[:8]}"
            legacy_db.projects[new_id] = {
                "id": new_id,
                "title": params.get("title", "New Project"),
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "subprojects": []
            }
            legacy_db.save()
            return {
                "status": "completed",
                "result": f"Project created: {new_id}",
                "data_update": {"type": "project_list_refresh"}
            }
        
        elif tool == "analyze_script":
             return {
                 "status": "completed",
                 "result": {
                     "screenplay_analysis": {
                        "genre": "Sci-Fi",
                        "logline": "A futuristic journey.",
                        "characters": ["Hero", "Villain"],
                        "scenes": [{"id": 1, "slug": "INT. LAB - DAY"}]
                     },
                     "visual_style_guide": {
                         "color_palette": ["#000000", "#FFFFFF"],
                         "lighting": "High Contrast"
                     }
                 },
                 "data_update": {"type": "analysis_result", "projectId": project_id}
             }

        elif tool == "update_project_metadata":
            if not normalized_project_id:
                return {"status": "failed", "result": "project_id is required"}

            project = db.query(Project).filter(Project.id == normalized_project_id).first()
            if not project:
                return {"status": "failed", "result": "Project not found"}

            title = params.get("title")
            description = params.get("description")
            updated = False

            if title is not None:
                title_text = str(title).strip()
                if title_text:
                    project.title = title_text
                    updated = True

            if description is not None:
                global_info = dict(project.global_info or {})
                global_info["description"] = str(description)
                project.global_info = global_info
                updated = True

            if updated:
                project.updated_at = datetime.utcnow().isoformat()
                db.add(project)
                db.commit()
                db.refresh(project)

            return {
                "status": "completed",
                "result": {
                    "project_id": project.id,
                    "title": project.title,
                    "description": (project.global_info or {}).get("description"),
                },
                "data_update": {
                    "type": "project_updated",
                    "projectId": project.id,
                },
            }

        elif tool == "search_project_data":
            keyword = str(params.get("keyword") or params.get("query") or "").strip()
            if not keyword:
                return {"status": "failed", "result": "keyword is required"}
            if not normalized_project_id:
                return {"status": "failed", "result": "project_id is required"}

            limit = 10
            try:
                limit = max(1, min(20, int(params.get("limit", 10))))
            except Exception:
                limit = 10

            pattern = f"%{keyword}%"
            entities = db.query(Entity).filter(
                Entity.project_id == normalized_project_id,
                (Entity.name.ilike(pattern)) | (Entity.description.ilike(pattern))
            ).limit(limit).all()

            scenes = db.query(Scene).filter(
                Scene.episode_id.in_(
                    db.query(Episode.id).filter(Episode.project_id == normalized_project_id)
                ),
                Scene.scene_name.ilike(pattern) | Scene.original_script_text.ilike(pattern)
            ).limit(limit).all()

            shots = db.query(Shot).filter(
                Shot.project_id == normalized_project_id,
                (Shot.shot_name.ilike(pattern)) | (Shot.video_content.ilike(pattern))
            ).limit(limit).all()

            result = {
                "keyword": keyword,
                "entities": [{"id": item.id, "name": item.name, "type": item.type} for item in entities],
                "scenes": [{"id": item.id, "scene_no": item.scene_no, "scene_name": item.scene_name} for item in scenes],
                "shots": [{"id": item.id, "shot_id": item.shot_id, "shot_name": item.shot_name} for item in shots],
            }
            return {
                "status": "completed",
                "result": result,
                "data_update": {
                    "type": "search_result",
                    "projectId": normalized_project_id,
                    "keyword": keyword,
                    "result": result,
                },
            }

        elif tool == "internet_search":
            query = str(params.get("query") or params.get("keyword") or "").strip()
            if not query:
                return {"status": "failed", "result": "query is required"}

            try:
                response = await asyncio.to_thread(
                    lambda: requests.get(
                        "https://api.duckduckgo.com/",
                        params={
                            "q": query,
                            "format": "json",
                            "no_redirect": 1,
                            "no_html": 1,
                            "skip_disambig": 1,
                        },
                        timeout=20,
                        headers={"User-Agent": "AIStory-Agent/1.0"},
                    )
                )
                data = response.json() if response.status_code == 200 else {}
            except Exception as e:
                return {"status": "failed", "result": f"Internet search failed: {e}"}

            related = []
            for item in data.get("RelatedTopics") or []:
                if isinstance(item, dict) and item.get("Text"):
                    related.append({"text": item.get("Text"), "url": item.get("FirstURL")})
                if len(related) >= 5:
                    break

            result = {
                "query": query,
                "abstract": data.get("AbstractText") or "",
                "abstract_url": data.get("AbstractURL") or "",
                "related": related,
            }
            return {
                "status": "completed",
                "result": result,
                "data_update": {
                    "type": "internet_search_result",
                    "query": query,
                    "result": result,
                },
            }

        elif tool == "visualize_user_requirement":
            objective = str(params.get("objective") or params.get("query") or "").strip()
            tasks = params.get("tasks") if isinstance(params.get("tasks"), list) else []
            normalized_tasks = [str(item).strip() for item in tasks if str(item).strip()]
            if not normalized_tasks and objective:
                normalized_tasks = [objective]

            result = {
                "objective": objective,
                "tasks": normalized_tasks,
            }
            return {
                "status": "completed",
                "result": result,
                "data_update": {
                    "type": "requirements_visualization",
                    "projectId": normalized_project_id,
                    "payload": result,
                },
            }

        return {"status": "failed", "result": f"Unknown tool: {tool}"}

    def _enrich_prompt_if_possible(self, prompt, project_id, target_id=None):
        if not project_id: return prompt
        # Future: Lookup scene context or character details to append to prompt
        return prompt

    def _find_previous_scene_end_frame(self, project_id, current_scene_id):
        # Implementation to find the end frame of the logically preceding scene
        # 1. Get project
        project = legacy_db.projects.get(project_id)
        if not project: return None
        # 2. Find index of current scene
        # (Simplified) Just return None for now as we don't have full scene graph traversal here
        return None

    def _save_and_bind_asset(self, project_id, url, asset_type, prompt, metadata, target_id, target_type, target_field=None):
        asset_id = f"asset_{uuid.uuid4().hex[:8]}"
        asset_data = {
            "id": asset_id,
            "url": url,
            "type": asset_type,
            "prompt": prompt,
            "metadata": metadata,
            "created_at": datetime.now()
        }
        
        # Save to Project Library
        if project_id:
             project = legacy_db.projects.get(project_id)
             if project:
                 if "assets" not in project: project["assets"] = []
                 project["assets"].append(asset_data)
                 
                 # Bind to Target if specified
                 if target_id:
                     # For now, just save to library. 
                     # Binding logic would go here (updating scene items)
                     pass 
                 
                 legacy_db.save()
        
        return {
            "status": "completed", 
            "result": url,
            "data_update": {
                "type": "asset_created", 
                "asset": asset_data,
                "projectId": project_id,
                "targetId": target_id
            }
        }

    async def _generate_image_with_metadata(self, prompt, llm_config, user_id: int, reference_image_url=None):
        provider = "stability"
        if llm_config and "provider" in llm_config:
            provider = llm_config["provider"]
        
        api_config = self.get_api_config(provider, user_id, category="Image")
        
        if provider == "doubao":
             return await self._handle_doubao_generation("image", prompt, api_config, reference_image_url)
        elif provider == "grsai":
             return await self._handle_grsai_generation("image", prompt, api_config, reference_image_url)
        elif provider == "tencent":
             return await self._handle_tencent_generation("image", prompt, api_config, reference_image_url)
        
        print(f"Mocking Image Gen for {provider}")
        return {
            "url": "https://pub-8415848529ba47329437b600ab383416.r2.dev/generated_image.png",
            "metadata": {"provider": provider, "model": api_config.get("model", "default")}
        }

    async def _generate_video_with_metadata(self, prompt, llm_config, user_id: int, reference_image_url=None, last_frame_url=None, duration=5):
        provider = "runway"
        if llm_config and "provider" in llm_config:
            provider = llm_config["provider"]
            
        api_config = self.get_api_config(provider, user_id, category="Video")

        if provider == "doubao":
             return await self._handle_doubao_generation("video", prompt, api_config, reference_image_url)
        elif provider == "grsai":
             return await self._handle_grsai_generation("video", prompt, api_config, reference_image_url, last_frame_url=last_frame_url)
        elif provider == "tencent":
             return await self._handle_tencent_generation("video", prompt, api_config, reference_image_url)

        print(f"Mocking Video Gen for {provider}")
        return {
            "url": "https://pub-8415848529ba47329437b600ab383416.r2.dev/generated_video.mp4",
            "metadata": {"provider": provider, "duration": duration}
        }
    
    # --- Provider Implementations ---
    
    async def _handle_doubao_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None):
        return {
            "url": "https://pub-8415848529ba47329437b600ab383416.r2.dev/doubao_gen.png" if gen_type == "image" else "https://pub-8415848529ba47329437b600ab383416.r2.dev/doubao_gen.mp4",
            "metadata": {"provider": "doubao", "ref": ref_image}
        }

    async def _handle_grsai_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None):
         return {
            "url": "https://pub-8415848529ba47329437b600ab383416.r2.dev/grsai_gen.png" if gen_type == "image" else "https://pub-8415848529ba47329437b600ab383416.r2.dev/grsai_gen.mp4",
            "metadata": {"provider": "grsai"}
        }

    async def _handle_tencent_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None):
        return {
            "url": "https://pub-8415848529ba47329437b600ab383416.r2.dev/tencent_gen.png" if gen_type == "image" else "https://pub-8415848529ba47329437b600ab383416.r2.dev/tencent_gen.mp4",
            "metadata": {"provider": "tencent"}
        }
    
    def _log_generation(self, provider, prompt, status, result):
        print(f"[{provider.upper()}] {prompt[:30]}... -> {status}")

agent_service = AgentService()
