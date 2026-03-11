
import requests
import re
from urllib.parse import urljoin
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
from typing import List, Dict, Any, Optional, AsyncGenerator

from app.schemas.agent import AgentRequest, AgentResponse, AgentAction
from app.services.llm_service import llm_service
from app.db.session import SessionLocal
from app.models.all_models import APISetting, SystemAPISetting, Entity, User, Project, ProjectShare, Scene, Shot, Episode, ProviderKeyPool, SystemAPIBillingRule
from app.core.config import settings
from app.services.billing_service import billing_service
from app.services.tool_billing_taxonomy_service import tool_billing_taxonomy_service
from app.services.system_default_api_service import get_task_default_system_setting
from app.core.time_utils import now_bj_iso
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
    _BASE_BILLING_RULE_KIND = "base_pricing"
    _BASE_BILLING_RULE_PRIORITY = -100000
    _RULE_DIMENSION_FIELDS = [
        "generation_mode", "input_format", "output_format", "has_audio",
        "input_tokens_min", "input_tokens_max", "output_tokens_min", "output_tokens_max",
        "total_tokens_min", "total_tokens_max", "image_count_min", "image_count_max",
        "width_min", "width_max", "height_min", "height_max", "pixels_min", "pixels_max",
        "duration_seconds_min", "duration_seconds_max", "fps_min", "fps_max",
    ]
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
        "recommend_model",
        "activate_model",
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
5) For pricing-rule requests, build rule-oriented parameters and upsert billing rules after user confirmation.

Billing semantics and fallback rules (MUST follow):
- System API pricing is always stored in platform credits.
- Platform credit baseline is fixed: 1 credit = CNY 0.01.
- Conversion formula baseline: credits = CNY / 0.01 = CNY * 100.
- Provider/model api_pricing is the primary pricing source.
- Billing rules are stored in system_api_billing_rules. Base pricing is one base rule; granular pricing may have multiple rules.
- Default API pricing map is a fallback by API category (LLM/Vision/Image/Video/Tools).
- Runtime billing uses default fallback only when provider/model pricing is missing, empty, or all of cost/cost_input/cost_output are <= 0.
- Therefore, setting cost/cost_input/cost_output to 0 means "use fallback" (not "free") unless user explicitly asks free.
- For pricing rules: if rule-identifying fields are identical, treat as the same rule and update instead of creating a duplicate.
- API category mapping used by billing:
    - llm_chat -> LLM
    - analysis / analysis_character -> Vision
    - image_gen -> Image
    - video_gen -> Video
    - others -> Tools

Pricing field meanings (for user explanations and writes):
- unit_type: billing unit (per_call/per_second/per_minute/per_token/per_1k_tokens/per_million_tokens)
- cost: base unit price (mainly non-token units)
- cost_input: input token price (token units)
- cost_output: output token price (token units)

How to map natural-language user input to write parameters:
- If user provides supplier prices, map to supplier_price / supplier_price_input / supplier_price_output and apply multiplier (default 1.0).
- If user provides final credit prices (cost/cost_input/cost_output), map them as supplier_price* with multiplier=1.0.
- If user provides RMB prices, convert to credits using 1 credit = CNY 0.01 (i.e., multiplier=100) unless user explicitly provides another confirmed conversion rule.
- If user says prices are in supplier credits/points/tokens (not RMB/USD), DO NOT assume conversion; first ask and confirm exchange ratio to platform credits, then write.
- If user asks to "clear", "reset", "use default", or "兜底", set corresponding cost fields to 0 to trigger fallback.
- If user asks to configure the fallback map itself, explain that this agent can only upsert provider/model api_pricing and should direct user to Billing -> Default API Pricing Map page.

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
- If price unit is ambiguous (RMB/USD/supplier credits): ask unit first.
- If input uses supplier credits/points: ask and confirm conversion ratio (e.g., 1 supplier credit = ? platform credits) before any write.
- If unit_type is missing: infer only when user clearly indicates token/call/time, otherwise ask.
- If operation target is unclear (create vs update): search first, then ask user to confirm create/update.

Update strategy:
- For natural-language requests, first abstract to normalized fields, then map to tool parameters.
- For update requests, preserve unspecified existing fields; only change fields explicitly provided by user.
- For create requests, propose defaults only when safe and explain assumptions in reply.

You may only use these tools:
1) search_system_api_settings
   - Parameters: provider (optional), category (optional), model (optional), modality (optional), limit (optional, max 50)
2) upsert_system_api_pricing
   - Parameters:
     - provider (required)
     - category (required, default LLM)
     - model (required)
     - name (optional)
     - modality (optional)
     - base_url (optional)
     - unit_type (optional: per_call/per_second/per_minute/per_token/per_1k_tokens/per_million_tokens)
     - supplier_price (optional)
     - supplier_price_input (optional)
     - supplier_price_output (optional)
     - multiplier (optional, default 1.0)
     - is_active (optional, default false)
    - rule_name (optional)
    - rule_description (optional)
    - priority (optional)
    - applies_to_text (optional)
    - applies_to_image (optional)
    - applies_to_video (optional)
    - generation_mode (optional)
    - input_format (optional)
    - output_format (optional)
    - has_audio (optional)
    - input_tokens_min/max, output_tokens_min/max, total_tokens_min/max (optional)
    - image_count_min/max, width_min/max, height_min/max, pixels_min/max (optional)
    - duration_seconds_min/max, fps_min/max (optional)
    - extra_conditions (optional JSON object)
3) read_webpage
     - Parameters:
         - url (required)
         - max_chars (optional, default 4000, max 12000)
         - max_pages (optional, default 1, max 5; reads pages sequentially by following next-page links)
4) analyze_model
   - Purpose: Analyze AI models — their characteristics, modality capabilities, strengths, weaknesses, and recommended use-cases. Supports both single-model and batch analysis. Gathers info from system DB and web search, then uses LLM to produce a comprehensive analysis report. Can also write back the inferred modality JSON and tags to the DB for downstream intelligent model selection.
   - Parameters:
     - query (optional): search keyword or model name. Required for single-model analysis. For batch modes, leave empty or use as additional filter.
     - scope (optional, default "auto"): Controls the batch scope:
       - "single" — analyze one specific model (query required)
       - "provider" — analyze all models from a specific provider (provider required)
       - "category" — analyze all models in a category (category required)
       - "all" — analyze ALL system API models
       - "auto" — infer from other params: if query is set, behave like single; if only provider, behave like provider; if only category, behave like category; if nothing specific, behave like all
     - provider (optional): filter by provider (e.g. "volcengine", "kie", "grsai")
     - category (optional): filter by category (LLM/Image/Video/Voice/Music)
     - search_web (optional, default true for single, false for batch): whether to search the web for additional model info
     - update_fields (optional, default false): if true, write the inferred modality JSON and tags back to the matching system settings rows
     - limit (optional, default 50): max number of models to analyze in batch mode
   - When user asks to "分析模型", "模型对比", "模型优缺点", "analyze model", "compare models", "更新模态", "update modality", "补充tags", or similar, use this tool.
   - For batch analysis requests like "分析全部模型", "分析所有Image模型", "分析volcengine的模型", use the appropriate scope.
   - When user explicitly asks to update/write modality or tags, set update_fields=true.
   - This tool calls LLM internally to produce the analysis, so no follow-up LLM call is needed.

Rules:
- Prefer search first, then update.
- Never invent unsupported fields.
- If user asks analysis only, do not write.
- If user asks apply/update/create and fields are complete, call upsert_system_api_pricing.
- If user asks to configure multiple pricing tiers/rules for one provider-model, generate one upsert_system_api_pricing plan item per rule.
- For a "same dimensions" rule (same applies_to flags + same matching fields + same extra_conditions), update that rule.
- If user asks apply/update/create but fields are incomplete, return follow-up questions and keep plan empty.
- Keep replies concise and actionable.
- You will receive Current Runtime Context key `system_api_model_catalog` (authoritative provider/category/model list from DB).
- For pricing analysis from natural language or web content, first fuzzy-match source model names to this catalog, then output matched canonical provider/category/model in plan.
- If multiple catalog entries are plausible for one source model name, ask disambiguation first and keep plan empty for that item.
- IMPORTANT: When the user provides a URL (e.g. a pricing page link), you MUST use the read_webpage tool to fetch and read it. You DO have the ability to browse web pages via this tool. Never refuse a URL read request.
- After reading a webpage, summarize the extracted pricing information and propose updates if the user requested them.

Output must be JSON object with keys: reply, plan.
"""

    _SYSTEM_MANAGEMENT_ALLOWED_TOOLS = {
        "search_system_api_settings",
        "upsert_system_api_pricing",
        "read_webpage",
        "analyze_model",
    }

    _SYSTEM_WRITE_CONFIRM_KEYWORDS = {
        "confirm",
        "confirmed",
        "yes",
        "ok",
        "okay",
        "go ahead",
        "proceed",
        "确认",
        "确认执行",
        "确认应用",
        "好的",
        "可以",
        "继续",
    }

    _SYSTEM_WRITE_CONFIRM_PROMPT_HINTS = {
        "确认",
        "confirm",
        "write confirmation required",
        "confirmation required",
        "请确认后再执行",
        "检测到定价写入操作",
        "确认执行以上更新",
    }

    _PRICING_INTENT_TOKENS = [
        "价格", "定价", "pricing", "价钱",
        "supplier_price", "cost_input", "cost_output",
        "per_call", "per_second", "per_token", "per_million",
        "per_1k", "per_minute",
        "元/", "rmb", "cny", "usd",
        "输入价", "输出价", "单价",
        "积分", "credits",
    ]

    _PRICING_RETRY_PROMPT = """The user provided pricing data in their message, and you already analyzed it.
However, your previous response did not include a structured JSON plan with tool calls.

You MUST now re-analyze the original user message below and produce ONLY a valid JSON object.
Do NOT output any other text. The JSON object must have keys: reply, plan.
The plan array must contain upsert_system_api_pricing tool calls for each model mentioned.
If any required fields are missing, set plan to [] and ask in reply.

Original user message:
{query}

Your previous analysis:
{previous_reply}

Remember the tool signature:
upsert_system_api_pricing(provider, category, model, unit_type, supplier_price, supplier_price_input, supplier_price_output, multiplier, name, base_url, modality, is_active, rule_name, rule_description, priority, applies_to_text, applies_to_image, applies_to_video, generation_mode, input_format, output_format, has_audio, input_tokens_min, input_tokens_max, output_tokens_min, output_tokens_max, total_tokens_min, total_tokens_max, image_count_min, image_count_max, width_min, width_max, height_min, height_max, pixels_min, pixels_max, duration_seconds_min, duration_seconds_max, fps_min, fps_max, extra_conditions)

Output ONLY the JSON object now."""

    def _has_pricing_content(self, text: str) -> bool:
        """Check if text contains pricing-related keywords."""
        lower = str(text or "").lower()
        return sum(1 for token in self._PRICING_INTENT_TOKENS if token in lower) >= 2

    async def _retry_extract_pricing_plan(
        self, query: str, previous_reply: str, llm_config: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Re-call LLM with a focused prompt to extract structured pricing plan
        when the first call returned prose instead of tool calls."""
        retry_prompt = self._PRICING_RETRY_PROMPT.format(
            query=query, previous_reply=previous_reply,
        )
        messages = [
            {"role": "system", "content": self._SYSTEM_MANAGEMENT_PROMPT},
            {"role": "user", "content": retry_prompt},
        ]
        try:
            result = await llm_service._call_openai_compatible(
                llm_config.get("base_url"), llm_config.get("api_key"),
                llm_config.get("model"), messages,
                dict(llm_config.get("config", {}) or {}),
            )
            normalized = self._normalize_llm_result(result)
            plan = normalized.get("plan") or []
            if plan:
                logger.info("[system_management] pricing retry succeeded | plan_count=%d", len(plan))
                return normalized
            logger.info("[system_management] pricing retry returned empty plan")
        except Exception as e:
            logger.warning("[system_management] pricing retry failed: %s", e)
        return None

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
                logger.info("[_normalize_llm_result] plan item type=%s keys=%s", type(item).__name__, list(item.keys()) if isinstance(item, dict) else repr(item)[:100])
                if isinstance(item, dict):
                    tool_name = str(
                        item.get("tool") or item.get("tool_name")
                        or item.get("action") or item.get("function")
                        or item.get("name") or ""
                    ).strip()
                    raw_params = (
                        item.get("parameters") or item.get("tool_params")
                        or item.get("args") or item.get("arguments")
                        or item.get("params") or item.get("input") or {}
                    )
                    params = raw_params if isinstance(raw_params, dict) else {}
                    logger.info("[_normalize_llm_result] resolved tool_name=%s params_keys=%s", tool_name, list(params.keys()))
                    if not tool_name:
                        continue
                    normalized_plan.append({"tool": tool_name, "parameters": params})
                elif isinstance(item, str):
                    parsed = self._parse_function_call_string(item)
                    if parsed:
                        normalized_plan.append(parsed)

        usage = llm_result.get("usage") if isinstance(llm_result.get("usage"), dict) else {}
        return {
            **llm_result,
            "reply": reply_text,
            "plan": normalized_plan,
            "usage": usage,
        }

    @staticmethod
    def _parse_function_call_string(text: str) -> Optional[Dict[str, Any]]:
        """Parse LLM-generated function-call strings like ``tool_name(key='val', key2=123)``
        into ``{"tool": "tool_name", "parameters": {"key": "val", "key2": 123}}``.
        Falls back to bare tool name if no parentheses.
        """
        import re as _re
        text = text.strip()
        if not text:
            return None

        m = _re.match(r'^(\w+)\((.+)\)$', text, _re.DOTALL)
        if not m:
            # bare tool name (no parens)
            if _re.match(r'^\w+$', text):
                return {"tool": text, "parameters": {}}
            return None

        tool_name = m.group(1)
        args_str = m.group(2).strip()
        params: Dict[str, Any] = {}

        # Parse key=value pairs
        for pair_match in _re.finditer(r"""(\w+)\s*=\s*(?:'([^']*)'|"([^"]*)"|(\[.*?\])|(\{.*?\})|([^,]+))""", args_str):
            key = pair_match.group(1)
            value = (
                pair_match.group(2) if pair_match.group(2) is not None
                else pair_match.group(3) if pair_match.group(3) is not None
                else pair_match.group(4) if pair_match.group(4) is not None
                else pair_match.group(5) if pair_match.group(5) is not None
                else pair_match.group(6)
            )
            if value is not None:
                value = str(value).strip()
                # Try to parse booleans / numbers / JSON
                if value.lower() == 'true':
                    params[key] = True
                elif value.lower() == 'false':
                    params[key] = False
                elif value.lower() == 'none' or value.lower() == 'null':
                    params[key] = None
                else:
                    try:
                        import json as _json
                        params[key] = _json.loads(value)
                    except (ValueError, TypeError):
                        params[key] = value

        return {"tool": tool_name, "parameters": params}

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

    def _normalize_upsert_system_api_pricing_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        src = dict(params or {}) if isinstance(params, dict) else {}

        def _pick_text(*keys: str) -> str:
            for key in keys:
                if key not in src:
                    continue
                value = src.get(key)
                if value is None:
                    continue
                text = str(value).strip()
                if text:
                    return text
            return ""

        target = src.get("target") if isinstance(src.get("target"), dict) else {}
        target_list = src.get("targets") if isinstance(src.get("targets"), list) else []
        first_target = target_list[0] if target_list and isinstance(target_list[0], dict) else {}

        provider = _pick_text("provider", "provider_name", "vendor", "supplier")
        model = _pick_text("model", "model_name", "api_model")
        category = _pick_text("category", "task_category", "api_category")

        if not provider:
            provider = str(target.get("provider") or first_target.get("provider") or "").strip()
        if not model:
            model = str(target.get("model") or first_target.get("model") or "").strip()
        if not category:
            category = str(target.get("category") or first_target.get("category") or "").strip()

        if category and category.upper() in {"TEXT", "CHAT"}:
            category = "LLM"

        if provider:
            src["provider"] = provider
        if model:
            src["model"] = model
        if category:
            src["category"] = category

        # Map common price aliases to canonical supplier fields when missing.
        if "supplier_price" not in src:
            for k in ("price_per_call", "price_per_second", "unit_price", "price"):
                if k in src and src.get(k) is not None:
                    src["supplier_price"] = src.get(k)
                    break
        if "supplier_price_input" not in src and "input_price" in src:
            src["supplier_price_input"] = src.get("input_price")
        if "supplier_price_output" not in src and "output_price" in src:
            src["supplier_price_output"] = src.get("output_price")

        return src

    def _hydrate_upsert_system_api_target(
        self,
        db: Session,
        params: Dict[str, Any],
        query_text: str = "",
    ) -> Dict[str, Any]:
        out = self._normalize_upsert_system_api_pricing_params(params)
        provider = str(out.get("provider") or "").strip().lower()
        category = str(out.get("category") or "").strip()
        model = str(out.get("model") or "").strip().lower()

        text_parts = [
            str(query_text or ""),
            str(out.get("query") or ""),
            str(out.get("text") or ""),
            str(out.get("objective") or ""),
            str(out.get("content") or ""),
            str(out.get("raw_text") or ""),
            str(out.get("rule_name") or ""),
            str(out.get("rule_description") or ""),
        ]
        haystack = "\n".join([p for p in text_parts if p]).lower()

        # Infer provider/category from obvious intent tokens.
        if not provider and "kie" in haystack:
            provider = "kie"
        if not category:
            if any(token in haystack for token in ["video", "t2v", "i2v", "veo", "kling", "hailuo", "wan", "sora"]):
                category = "Video"

        # Veo family canonical mapping for KIE rows.
        if not model and any(token in haystack for token in ["veo-3-1", "veo 3 1", "veo3.1", "veo3_1", "veo 3.1"]):
            fast_tokens = ["fast mode", "fast", "极速", "快速"]
            if any(token in haystack for token in fast_tokens):
                model = "veo3_fast"
            else:
                model = "veo3"

        # Generic model extraction: provider/model slug pattern in text.
        if not model:
            m = re.search(r"\b([a-z0-9._-]+/[a-z0-9._-]+)\b", haystack)
            if m:
                model = str(m.group(1) or "").strip().lower()

        # If model still missing, use a fuzzy lookup from existing system rows.
        if not model and haystack:
            rows = db.query(SystemAPISetting).order_by(SystemAPISetting.id.desc()).all()
            for row in rows:
                row_provider = str(getattr(row, "provider", "") or "").strip().lower()
                row_category = str(getattr(row, "category", "") or "").strip().lower()
                row_model = str(getattr(row, "model", "") or "").strip().lower()
                if not row_model:
                    continue
                if provider and row_provider != provider:
                    continue
                if category and row_category != str(category).strip().lower():
                    continue
                if row_model in haystack:
                    model = row_model
                    if not provider:
                        provider = row_provider
                    if not category:
                        category = str(getattr(row, "category", "") or "").strip()
                    break

        if provider:
            out["provider"] = provider
        if category:
            out["category"] = category
        if model:
            out["model"] = model
        return out

    def _normalize_system_upsert_preview(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params = self._normalize_upsert_system_api_pricing_params(params)
        provider = str(params.get("provider") or "").strip()
        provider_alias = str(params.get("provider_alias") or "").strip()
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

        has_rule_dimensions = self._has_rule_dimension_params(params)
        rule_signature = self._extract_rule_signature_from_params(params, category)

        return {
            "provider": provider,
            "provider_alias": provider_alias,
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
            "has_rule_dimensions": has_rule_dimensions,
            "rule_signature": rule_signature,
        }

    def _build_provider_alias_lookup(self, db: Session) -> Dict[str, str]:
        rows = db.query(ProviderKeyPool.provider, ProviderKeyPool.provider_alias).all()
        out: Dict[str, str] = {}
        for provider_name, alias_name in rows:
            provider_text = str(provider_name or "").strip().lower()
            alias_text = str(alias_name or "").strip()
            if provider_text and alias_text and provider_text not in out:
                out[provider_text] = alias_text
        return out

    def _resolve_provider_alias(self, provider_name: Any, alias_lookup: Optional[Dict[str, str]] = None) -> str:
        provider_text = str(provider_name or "").strip().lower()
        if not provider_text:
            return ""
        return str((alias_lookup or {}).get(provider_text) or "").strip()

    def _safe_optional_int(self, value: Any) -> Optional[int]:
        if value is None or str(value).strip() == "":
            return None
        try:
            return int(float(value))
        except Exception:
            return None

    def _safe_optional_float(self, value: Any) -> Optional[float]:
        if value is None or str(value).strip() == "":
            return None
        try:
            return float(value)
        except Exception:
            return None

    def _safe_optional_bool(self, value: Any) -> Optional[bool]:
        if value is None or str(value).strip() == "":
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value).strip().lower()
        if text in {"true", "1", "yes", "y", "on"}:
            return True
        if text in {"false", "0", "no", "n", "off"}:
            return False
        return None

    def _parse_extra_conditions(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return {}
        return {}

    def _has_rule_dimension_params(self, params: Dict[str, Any]) -> bool:
        dimension_keys = set(self._RULE_DIMENSION_FIELDS) | {
            "applies_to_text", "applies_to_image", "applies_to_video",
            "priority", "rule_name", "rule_description", "extra_conditions",
        }
        for key in dimension_keys:
            if key not in params:
                continue
            value = params.get(key)
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            if key == "extra_conditions" and not self._parse_extra_conditions(value):
                continue
            return True
        return False

    def _extract_rule_signature_from_params(self, params: Dict[str, Any], category: str) -> Dict[str, Any]:
        category_text = str(category or "LLM").strip().lower()
        default_applies = {
            "applies_to_text": category_text not in {"image", "video"},
            "applies_to_image": category_text == "image",
            "applies_to_video": category_text == "video",
        }
        applies_to_text = self._safe_optional_bool(params.get("applies_to_text"))
        applies_to_image = self._safe_optional_bool(params.get("applies_to_image"))
        applies_to_video = self._safe_optional_bool(params.get("applies_to_video"))

        signature: Dict[str, Any] = {
            "applies_to_text": default_applies["applies_to_text"] if applies_to_text is None else bool(applies_to_text),
            "applies_to_image": default_applies["applies_to_image"] if applies_to_image is None else bool(applies_to_image),
            "applies_to_video": default_applies["applies_to_video"] if applies_to_video is None else bool(applies_to_video),
        }

        int_fields = {
            "input_tokens_min", "input_tokens_max", "output_tokens_min", "output_tokens_max",
            "total_tokens_min", "total_tokens_max", "image_count_min", "image_count_max",
            "width_min", "width_max", "height_min", "height_max", "pixels_min", "pixels_max",
        }
        float_fields = {"duration_seconds_min", "duration_seconds_max", "fps_min", "fps_max"}

        for field in self._RULE_DIMENSION_FIELDS:
            raw = params.get(field)
            if field == "has_audio":
                signature[field] = self._safe_optional_bool(raw)
            elif field in int_fields:
                signature[field] = self._safe_optional_int(raw)
            elif field in float_fields:
                signature[field] = self._safe_optional_float(raw)
            else:
                value = str(raw or "").strip().lower()
                signature[field] = value or None

        signature["extra_conditions"] = self._parse_extra_conditions(params.get("extra_conditions"))
        return signature

    def _extract_rule_signature_from_row(self, rule: SystemAPIBillingRule) -> Dict[str, Any]:
        signature: Dict[str, Any] = {
            "applies_to_text": bool(getattr(rule, "applies_to_text", False)),
            "applies_to_image": bool(getattr(rule, "applies_to_image", False)),
            "applies_to_video": bool(getattr(rule, "applies_to_video", False)),
        }
        for field in self._RULE_DIMENSION_FIELDS:
            value = getattr(rule, field, None)
            if field in {"generation_mode", "input_format", "output_format"}:
                signature[field] = (str(value or "").strip().lower() or None)
            else:
                signature[field] = value
        signature["extra_conditions"] = self._safe_json_dict(getattr(rule, "extra_conditions", {}))
        return signature

    def _find_matching_granular_rule(
        self,
        session,
        system_api_id: int,
        target_signature: Dict[str, Any],
    ) -> Optional[SystemAPIBillingRule]:
        rows = session.query(SystemAPIBillingRule).filter(
            SystemAPIBillingRule.system_api_id == int(system_api_id),
        ).order_by(SystemAPIBillingRule.id.desc()).all()
        for row in rows:
            if self._is_base_billing_rule(row):
                continue
            if self._extract_rule_signature_from_row(row) == target_signature:
                return row
        return None

    def _annotate_system_upsert_preview_with_rule_action(
        self,
        db: Session,
        params: Dict[str, Any],
        preview: Dict[str, Any],
        existing_row: Optional[SystemAPISetting] = None,
    ) -> Dict[str, Any]:
        out = dict(preview or {})
        row = existing_row
        if row is None:
            row = self._find_existing_system_api_setting(
                db,
                str(params.get("provider") or "").strip(),
                str(params.get("category") or "LLM").strip() or "LLM",
                str(params.get("model") or "").strip(),
            )

        if not row:
            out["preview_action"] = "target_missing"
            out["preview_action_label"] = "目标不存在"
            out["preview_rule_id"] = None
            return out

        if not bool(out.get("has_rule_dimensions")):
            out["preview_action"] = "base_update"
            out["preview_action_label"] = "更新基础规则"
            out["preview_rule_id"] = None
            return out

        signature = out.get("rule_signature") if isinstance(out.get("rule_signature"), dict) else self._extract_rule_signature_from_params(params, str(out.get("category") or "LLM"))
        matched_rule = self._find_matching_granular_rule(db, int(row.id), signature)
        if matched_rule:
            out["preview_action"] = "rule_update"
            out["preview_action_label"] = "更新已有规则"
            out["preview_rule_id"] = int(matched_rule.id)
        else:
            out["preview_action"] = "rule_create"
            out["preview_action_label"] = "新增规则"
            out["preview_rule_id"] = None
        return out

    def _find_existing_system_api_setting(
        self,
        db: Session,
        provider: str,
        category: str,
        model: str,
    ) -> Optional[SystemAPISetting]:
        provider_raw = str(provider or "").strip()
        category_raw = str(category or "LLM").strip() or "LLM"
        model_raw = str(model or "").strip()

        def _norm_provider(text: str) -> str:
            raw = str(text or "").strip().lower()
            if not raw:
                return ""
            # Tolerate LLM extracted noise like "kie provider".
            if "kie" in raw:
                return "kie"
            if "wanxiang" in raw or "wanx" in raw:
                return "wanxiang"
            if "volc" in raw or "doubao" in raw or "ark" in raw:
                return "doubao"
            return raw

        def _norm_model(text: str) -> str:
            raw = str(text or "").strip().lower()
            if not raw:
                return ""
            # Remove common suffix noise from extraction, keep core model slug.
            raw = re.sub(r"\b(model|models|模型)\b", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"\s*/\s*", "/", raw)
            return re.sub(r"\s+", " ", raw).strip()

        def _norm_category(text: str) -> str:
            raw = str(text or "").strip().lower()
            if raw in {"llm", "text", "chat"}:
                return "llm"
            if raw in {"image", "img", "t2i", "i2i"}:
                return "image"
            if raw in {"video", "t2v", "i2v", "v2v"}:
                return "video"
            if raw in {"digital_human", "digital-human", "digitalhuman", "avatar", "s2v", "数字人"}:
                return "digitalhuman"
            if raw in {"voice", "audio", "speech", "tts", "asr"}:
                return "voice"
            if raw in {"music"}:
                return "music"
            if raw in {"tools", "tool"}:
                return "tools"
            return raw

        # 1) exact match first
        exact = db.query(SystemAPISetting).filter(
            SystemAPISetting.provider == provider_raw,
            SystemAPISetting.category == category_raw,
            SystemAPISetting.model == model_raw,
        ).order_by(SystemAPISetting.id.desc()).first()
        if exact:
            return exact

        # 2) case-insensitive exact text match
        provider_lower = _norm_provider(provider_raw)
        category_lower = category_raw.lower()
        category_norm = _norm_category(category_raw)
        model_lower = _norm_model(model_raw)
        rows = db.query(SystemAPISetting).order_by(SystemAPISetting.id.desc()).all()

        for row in rows:
            row_category = str(row.category or "").strip()
            row_category_lower = row_category.lower()
            row_category_norm = _norm_category(row_category)
            if row_category_lower != category_lower and row_category_norm != category_norm:
                continue
            row_provider_lower = _norm_provider(str(row.provider or "").strip())
            row_model_lower = _norm_model(str(row.model or "").strip())
            if row_provider_lower == provider_lower and row_model_lower == model_lower:
                return row

        # 3) relaxed token match (ignore slash/dash/space differences)
        def _tokenize(text: str) -> str:
            return re.sub(r"[^a-z0-9]+", "", str(text or "").strip().lower())

        model_token = _tokenize(model_lower)
        provider_token = _tokenize(provider_lower)

        provider_aliases: Dict[str, List[str]] = {
            "alibaba": ["wan", "tongyi", "aliyun"],
            "wan": ["alibaba", "tongyi", "aliyun"],
            "tongyi": ["wan", "alibaba", "aliyun"],
            "aliyun": ["wan", "alibaba", "tongyi"],
        }
        alias_tokens = {_tokenize(provider_lower)}
        for alias in provider_aliases.get(provider_lower, []):
            alias_tokens.add(_tokenize(alias))

        relaxed_matches: List[SystemAPISetting] = []
        for row in rows:
            row_category = str(row.category or "").strip()
            row_category_lower = row_category.lower()
            row_category_norm = _norm_category(row_category)
            if row_category_lower != category_lower and row_category_norm != category_norm:
                continue
            row_model_token = _tokenize(_norm_model(str(row.model or "")))
            if not row_model_token:
                continue
            # Accept exact token match, or one token containing the other
            # to handle strings like "hailuo / ... model".
            if model_token and not (
                row_model_token == model_token
                or row_model_token in model_token
                or model_token in row_model_token
            ):
                continue
            row_provider_token = _tokenize(_norm_provider(str(row.provider or "")))
            if row_provider_token in alias_tokens or provider_token == row_provider_token:
                relaxed_matches.append(row)

        if relaxed_matches:
            return relaxed_matches[0]

        # 4) last resort: unique model token in same category
        if model_token:
            same_model_rows = []
            for r in rows:
                r_category = str(r.category or "").strip()
                r_category_lower = r_category.lower()
                r_category_norm = _norm_category(r_category)
                if r_category_lower != category_lower and r_category_norm != category_norm:
                    continue
                r_model_token = _tokenize(_norm_model(str(r.model or "")))
                if model_token and (
                    r_model_token == model_token
                    or r_model_token in model_token
                    or model_token in r_model_token
                ):
                    same_model_rows.append(r)
            if len(same_model_rows) == 1:
                return same_model_rows[0]

        return None

    def _ensure_system_api_setting_for_pricing_upsert(
        self,
        db: Session,
        provider: str,
        category: str,
        model: str,
    ) -> Optional[SystemAPISetting]:
        """Find existing system setting for pricing upsert, or create a minimal row."""
        provider_text = str(provider or "").strip()
        category_text = str(category or "LLM").strip() or "LLM"
        model_text = str(model or "").strip()
        if not provider_text or not model_text:
            return None

        existing = self._find_existing_system_api_setting(db, provider_text, category_text, model_text)
        if existing:
            return existing

        default_base_url = None
        try:
            from app.api.settings import DEFAULTS
            default_base_url = (DEFAULTS.get(provider_text) or {}).get("base_url")
        except Exception:
            default_base_url = None

        config_payload: Dict[str, Any] = {"deprecated": False}
        if str(provider_text).strip().lower() == "kie":
            kie_base_url = "https://api.kie.ai"
            config_payload.update({
                "endpoint": f"{kie_base_url}/api/v1/jobs/createTask",
                "query_endpoint": f"{kie_base_url}/api/v1/jobs/recordInfo",
                "credits_endpoint": f"{kie_base_url}/api/v1/user/credits",
                "credits_endpoint_v2": f"{kie_base_url}/api/v1/chat/credit",
            })
            if not default_base_url:
                default_base_url = kie_base_url

        created = SystemAPISetting(
            name=f"{provider_text} {model_text}",
            category=category_text,
            provider=provider_text,
            api_key="",
            base_url=default_base_url,
            model=model_text,
            config=config_payload,
            is_active=False,
            deprecated=False,
        )
        db.add(created)
        db.flush()
        return created

    def _is_system_write_confirmation(self, query: str, history: List[Dict[str, Any]], params: Dict[str, Any]) -> bool:
        if bool(params.get("confirm")):
            return True

        text = str(query or "").strip().lower()
        last_assistant = None
        for item in reversed(history or []):
            if str(item.get("role") or "").strip().lower() == "assistant":
                last_assistant = str(item.get("content") or "")
                break

        # Strict rule: a write can only proceed after the assistant has asked
        # for confirmation in the previous turn (or params.confirm=True).
        asked_for_confirmation = False
        if last_assistant:
            last_assistant_lower = last_assistant.lower()
            asked_for_confirmation = any(
                token in last_assistant_lower for token in self._SYSTEM_WRITE_CONFIRM_PROMPT_HINTS
            )

        if not asked_for_confirmation:
            return False

        if text and any(token in text for token in self._SYSTEM_WRITE_CONFIRM_KEYWORDS):
            return True

        return False

    _ACTIVATE_MODEL_CONFIRM_KEYWORDS = {
        "confirm", "confirmed", "activate", "switch", "use this", "go ahead", "yes",
        "确认", "确认激活", "确认切换", "激活", "切换", "就用这个", "用这个",
        "好的", "可以", "ok", "执行", "应用",
    }

    def _is_activate_model_confirmation(self, query: str, history: List[Dict[str, Any]], params: Dict[str, Any]) -> bool:
        if bool(params.get("confirm")):
            return True

        text = str(query or "").strip().lower()
        if text and any(token in text for token in self._ACTIVATE_MODEL_CONFIRM_KEYWORDS):
            return True

        # Check if the previous assistant message was a confirmation prompt
        last_assistant = None
        for item in reversed(history or []):
            if str(item.get("role") or "").strip().lower() == "assistant":
                last_assistant = str(item.get("content") or "")
                break
        if last_assistant and ("确认" in last_assistant or "激活" in last_assistant or "activate" in last_assistant.lower()):
            if text and any(token in text for token in {"确认", "confirm", "yes", "ok", "好的", "可以", "执行", "激活", "切换"}):
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

    def _extract_model_hint_from_text(self, text: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""

        patterns = [
            r"(?:model|模型)\s*[:：]\s*([A-Za-z0-9._:/-]{2,80})",
            r"(?:model|模型)\s+([A-Za-z0-9._:/-]{2,80})",
        ]
        for pattern in patterns:
            m = re.search(pattern, raw, flags=re.IGNORECASE)
            if m:
                return str(m.group(1) or "").strip()
        return ""

    def _extract_requested_page_count(self, text: str) -> int:
        raw = str(text or "").strip()
        if not raw:
            return 1

        cn_match = re.search(r"(?:读|读取|翻到)?\s*([1-5])\s*页", raw, flags=re.IGNORECASE)
        if cn_match:
            try:
                return max(1, min(5, int(cn_match.group(1))))
            except Exception:
                return 1

        en_match = re.search(r"([1-5])\s*pages?", raw, flags=re.IGNORECASE)
        if en_match:
            try:
                return max(1, min(5, int(en_match.group(1))))
            except Exception:
                return 1

        return 1

    def _extract_next_page_url_from_history(self, history: List[Dict[str, Any]]) -> str:
        if not isinstance(history, list):
            return ""

        for item in reversed(history):
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or "")
            if not content:
                continue

            labeled = re.search(r"下一页\s*[:：]\s*(https?://[^\s)]+)", content, flags=re.IGNORECASE)
            if labeled:
                return str(labeled.group(1) or "").strip()

            urls = re.findall(r"https?://[^\s)]+", content, flags=re.IGNORECASE)
            if urls:
                return str(urls[-1] or "").strip()

        return ""

    def _extract_pricing_candidates_from_webpage(
        self,
        webpage_result: Dict[str, Any],
        query: str,
        history: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not isinstance(webpage_result, dict):
            return []

        url = str(webpage_result.get("url") or "").strip()
        title = str(webpage_result.get("title") or "").strip()
        excerpt = str(webpage_result.get("excerpt") or "").strip()
        combined = " ".join(part for part in [url, title, excerpt] if part).strip()
        if not combined:
            return []

        provider_hint = (
            self._extract_provider_hint_from_text(query)
            or self._infer_provider_hint_from_history(query, history or [])
            or self._extract_provider_hint_from_text(f"{url} {title}")
        )
        model_hint = self._extract_model_hint_from_text(query) or self._extract_model_hint_from_text(combined)

        candidates: List[Dict[str, Any]] = []

        image_patterns = [
            r"(?:\$|usd\s*)?([0-9]+(?:\.[0-9]+)?)\s*(?:/|per\s*)(?:image|img|张|幅|次)",
            r"(?:每\s*张|每\s*幅|单\s*张)\s*(?:\$|usd\s*)?([0-9]+(?:\.[0-9]+)?)",
        ]
        seen_image_prices = set()
        for pattern in image_patterns:
            for m in re.finditer(pattern, combined, flags=re.IGNORECASE):
                raw_price = str(m.group(1) or "").strip()
                if not raw_price or raw_price in seen_image_prices:
                    continue
                seen_image_prices.add(raw_price)
                price = self._safe_non_negative_float(raw_price)
                if price <= 0:
                    continue
                candidates.append({
                    "provider": provider_hint,
                    "category": "Image",
                    "model": model_hint,
                    "unit_type": "per_call",
                    "supplier_price": price,
                    "multiplier": 1.0,
                    "source": "read_webpage",
                })
                if len(candidates) >= 6:
                    break
            if len(candidates) >= 6:
                break

        input_match = re.search(
            r"(?:input|prompt|输入)\D{0,30}(?:\$|usd\s*)?([0-9]+(?:\.[0-9]+)?)",
            combined,
            flags=re.IGNORECASE,
        )
        output_match = re.search(
            r"(?:output|completion|输出)\D{0,30}(?:\$|usd\s*)?([0-9]+(?:\.[0-9]+)?)",
            combined,
            flags=re.IGNORECASE,
        )
        if input_match or output_match:
            in_price = self._safe_non_negative_float(input_match.group(1)) if input_match else 0.0
            out_price = self._safe_non_negative_float(output_match.group(1)) if output_match else 0.0
            if in_price > 0 or out_price > 0:
                candidates.append({
                    "provider": provider_hint,
                    "category": "LLM",
                    "model": model_hint,
                    "unit_type": "per_million_tokens",
                    "supplier_price_input": in_price if in_price > 0 else None,
                    "supplier_price_output": out_price if out_price > 0 else None,
                    "multiplier": 1.0,
                    "source": "read_webpage",
                })

        return candidates[:6]

    def _extract_next_page_url(self, html: str, current_url: str) -> str:
        raw_html = str(html or "")
        if not raw_html:
            return ""

        rel_next = re.search(
            r'<link[^>]*rel=["\']?next["\']?[^>]*href=["\']([^"\']+)["\']',
            raw_html,
            flags=re.IGNORECASE,
        )
        if rel_next:
            href = str(rel_next.group(1) or "").strip()
            return urljoin(current_url, href) if href else ""

        anchor_patterns = [
            r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>\s*(?:下一页|下页|next|next\s*page|›|&gt;|>)\s*</a>',
            r'<a[^>]*>\s*(?:下一页|下页|next|next\s*page|›|&gt;|>)\s*</a>',
        ]

        for pattern in anchor_patterns:
            for match in re.finditer(pattern, raw_html, flags=re.IGNORECASE):
                if match.lastindex and match.lastindex >= 1:
                    href = str(match.group(1) or "").strip()
                    if href:
                        return urljoin(current_url, href)

        generic_next = re.search(
            r'<a[^>]*href=["\']([^"\']+)["\'][^>]*(?:class|id)=["\'][^"\']*(?:next|pagination-next|pager-next)[^"\']*["\'][^>]*>',
            raw_html,
            flags=re.IGNORECASE,
        )
        if generic_next:
            href = str(generic_next.group(1) or "").strip()
            return urljoin(current_url, href) if href else ""

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

            if action.tool == "read_webpage" and isinstance(action.result, dict):
                title = str(action.result.get("title") or "").strip()
                url = str(action.result.get("url") or "").strip()
                excerpt = str(action.result.get("excerpt") or "").strip()
                pages_read = int(action.result.get("pages_read") or 1)
                next_page_url = str(action.result.get("next_page_url") or "").strip()
                lines.append(f"网页读取：{title or url}（已读 {pages_read} 页）")
                if excerpt:
                    lines.append(excerpt[:500])
                if next_page_url:
                    lines.append(f"下一页：{next_page_url}")
                pricing_candidates = action.result.get("pricing_candidates") if isinstance(action.result.get("pricing_candidates"), list) else []
                if pricing_candidates:
                    lines.append(f"识别到价格候选：{len(pricing_candidates)} 条")
                    for idx, item in enumerate(pricing_candidates[:5], start=1):
                        category = str(item.get("category") or "").strip() or "LLM"
                        provider = str(item.get("provider") or "").strip() or "(待补充provider)"
                        model = str(item.get("model") or "").strip() or "(待补充model)"
                        if category.lower() == "image":
                            price = self._safe_non_negative_float(item.get("supplier_price") or 0)
                            lines.append(f"  - {idx}. {provider}/{category}/{model} per_image={price:.2f}")
                        else:
                            in_price = self._safe_non_negative_float(item.get("supplier_price_input") or 0)
                            out_price = self._safe_non_negative_float(item.get("supplier_price_output") or 0)
                            if in_price > 0 or out_price > 0:
                                lines.append(f"  - {idx}. {provider}/{category}/{model} in/out={in_price:.2f}/{out_price:.2f}")
                            else:
                                price = self._safe_non_negative_float(item.get("supplier_price") or 0)
                                lines.append(f"  - {idx}. {provider}/{category}/{model} cost={price:.2f}")

        failed_or_blocked = [a for a in actions if str(a.status or "") in {"failed", "blocked"}]
        if failed_or_blocked:
            lines.append("执行异常项：")
            for idx, action in enumerate(failed_or_blocked[:8], start=1):
                result_text = action.result
                if isinstance(result_text, dict):
                    result_text = json.dumps(result_text, ensure_ascii=False)
                result_short = str(result_text or "").strip().replace("\n", " ")[:220]
                lines.append(f"{idx}. {action.tool} | {action.status} | {result_short}")

        return "\n".join(lines).strip()

    def _extract_plan_item_tool_and_params(self, plan_item: Any) -> Dict[str, Any]:
        """Normalize LLM plan item schema across providers.

        Supported aliases:
        - tool | tool_name
        - parameters | tool_parameters | tool_input
        """
        item = plan_item if isinstance(plan_item, dict) else {}
        tool_name = str(item.get("tool") or item.get("tool_name") or "").strip()
        params = {}
        for key in ("parameters", "tool_parameters", "tool_input"):
            val = item.get(key)
            if isinstance(val, dict):
                params = val
                break
        if not params and item:
            params = {
                k: v for k, v in item.items()
                if k not in {"tool", "tool_name", "parameters", "tool_parameters", "tool_input"}
            }

        if tool_name == "upsert_system_api_pricing":
            params = self._normalize_upsert_system_api_pricing_params(params)
        return {"tool_name": tool_name, "params": params}
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

    def _pick_runtime_api_key(self, config_value: Any, fallback_key: Any = None, session=None, provider_name: str = None) -> str:
        """Pick a runtime API key.
        If session + provider_name given, reads key pool from provider_key_pool table.
        Otherwise falls back to legacy config dict reading (for backward compat).
        """
        # New path: read from provider_key_pool table
        if session and provider_name:
            prov = str(provider_name or "").strip().lower()
            if prov:
                record = session.query(ProviderKeyPool).filter(ProviderKeyPool.provider == prov).first()
                if record and record.api_keys:
                    pooled = self._normalize_api_keys(record.api_keys)
                    if pooled:
                        strategy = str(record.strategy or "random").strip().lower()
                        if strategy == "round_robin":
                            cursor = int(self._provider_key_cursors.get(prov, 0))
                            selected = pooled[cursor % len(pooled)]
                            self._provider_key_cursors[prov] = cursor + 1
                            return selected
                        if strategy == "weighted":
                            raw_weights = record.weights
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

        # Legacy fallback: read from config dict
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
                        "api_key": self._pick_runtime_api_key(setting.config, setting.api_key, session=session, provider_name=setting.provider),
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

                def _resolve_system_default_fallback(selection_source: str) -> Dict[str, Any]:
                    # Prefer task-default system setting in the same category when user setting is missing or unusable.
                    sys_candidates: List[SystemAPISetting] = []
                    default_row = get_task_default_system_setting(session, resolved_category)
                    if default_row:
                        sys_candidates.append(default_row)

                    extra_rows = session.query(SystemAPISetting).filter(
                        SystemAPISetting.category == resolved_category,
                        SystemAPISetting.id != (int(default_row.id) if default_row else -1),
                    ).order_by(SystemAPISetting.id.desc()).all()
                    sys_candidates.extend(extra_rows)

                    sys_fallback = None
                    for cand in sys_candidates:
                        if self._is_deprecated_system_config(cand.config, getattr(cand, "deprecated", None)):
                            continue
                        if not _is_endpoint_compatible(cand.config or {}):
                            continue
                        sys_fallback = cand
                        break

                    if not sys_fallback:
                        logger.warning(
                            "No usable system fallback config found | user_id=%s category=%s source=%s",
                            user_id,
                            resolved_category,
                            selection_source,
                        )
                        return {}

                    from app.api.settings import DEFAULTS
                    default = DEFAULTS.get(sys_fallback.provider, {})
                    merged_config = dict(sys_fallback.config or default.get("config", {}) or {})
                    merged_config["__resolved_setting_id"] = sys_fallback.id
                    merged_config["__resolved_source"] = f"system_fallback:{sys_fallback.provider}/{sys_fallback.model}->{sys_fallback.id}"
                    merged_config["__resolved_category"] = resolved_category
                    merged_config["__selection_source"] = selection_source
                    merged_config["__resolved_user_id"] = user_id

                    logger.info(
                        "Resolved active API config via system fallback | user_id=%s category=%s source=%s setting_id=%s provider=%s model=%s",
                        user_id,
                        resolved_category,
                        selection_source,
                        sys_fallback.id,
                        sys_fallback.provider,
                        sys_fallback.model,
                    )
                    return {
                        "provider": sys_fallback.provider,
                        "api_key": self._pick_runtime_api_key(
                            sys_fallback.config,
                            sys_fallback.api_key,
                            session=session,
                            provider_name=sys_fallback.provider,
                        ),
                        "base_url": sys_fallback.base_url or default.get("base_url"),
                        "model": sys_fallback.model or default.get("model"),
                        "config": merged_config,
                    }

                active_user_setting = session.query(APISetting).filter(
                    APISetting.user_id == user_id,
                    APISetting.category == resolved_category,
                    APISetting.is_active == True
                ).order_by(APISetting.id.desc()).first()

                if not active_user_setting:
                    logger.warning(
                        "No active user api setting found, falling back to system active config | user_id=%s category=%s",
                        user_id,
                        resolved_category,
                    )
                    return _resolve_system_default_fallback("system_fallback_no_user_setting")

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
                        return _resolve_system_default_fallback("system_fallback_selected_deprecated")
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

                if not selected:
                    return _resolve_system_default_fallback("system_fallback_selected_missing_or_incompatible")

                if selected:
                    from app.api.settings import DEFAULTS
                    default = DEFAULTS.get(selected.provider, {})
                    merged_config = dict(selected.config or default.get("config", {}) or {})
                    merged_config["__resolved_setting_id"] = selected.id
                    merged_config["__resolved_source"] = selected_source
                    merged_config["__resolved_category"] = getattr(selected, "category", resolved_category)
                    merged_config["__selection_source"] = "system_only"
                    merged_config["__resolved_user_id"] = user_id
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
                        "api_key": self._pick_runtime_api_key(selected.config, selected.api_key, session=session, provider_name=selected.provider),
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
                    prov = str(provider_name or "").strip().lower()
                    if not prov:
                        return []
                    record = session.query(ProviderKeyPool).filter(ProviderKeyPool.provider == prov).first()
                    if record and record.api_keys:
                        return self._normalize_api_keys(record.api_keys)
                    return []

                default_row = get_task_default_system_setting(session, resolved_category)
                selected = default_row

                def _runtime_key(setting: Optional[SystemAPISetting]) -> str:
                    if not setting:
                        return ""
                    direct = self._pick_runtime_api_key(setting.config, setting.api_key, session=session, provider_name=setting.provider)
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

    def get_fallback_configs(
        self,
        user_id: int,
        category: str = "LLM",
        exclude_setting_id: Optional[int] = None,
        modality: Optional[str] = None,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """Return up to *limit* alternative configs from the same category.

        * Skips the currently-active config (identified by *exclude_setting_id*).
        * Filters by *modality* — a SystemAPISetting with modality=NULL/empty
          is considered compatible with ANY requested modality.
        * Only returns active, non-deprecated rows that have a usable API key.
        * Prioritizes lower estimated average price, then id fallback.
        """
        results: List[Dict[str, Any]] = []
        try:
            with SessionLocal() as session:
                rows = session.query(SystemAPISetting).filter(
                    SystemAPISetting.category == category,
                ).order_by(SystemAPISetting.id.desc()).all()

                from app.api.settings import DEFAULTS
                priced_candidates: List[Dict[str, Any]] = []

                for row in rows:
                    if exclude_setting_id and row.id == exclude_setting_id:
                        continue

                    if self._is_deprecated_system_config(row.config, getattr(row, "deprecated", None)):
                        continue

                    # ── modality check ──
                    if modality:
                        from app.services.modality_utils import modality_matches
                        if not modality_matches(getattr(row, "modality", None), modality):
                            continue

                    # ── endpoint compatibility (LLM) ──
                    endpoint = str((row.config or {}).get("endpoint") or "").strip().lower()
                    if category == "LLM" and endpoint:
                        media_tokens = ["/draw", "/video", "image2video", "video-synthesis", "generations/tasks"]
                        if any(tok in endpoint for tok in media_tokens):
                            continue

                    api_key = self._pick_runtime_api_key(
                        row.config,
                        row.api_key,
                        session=session,
                        provider_name=row.provider,
                    )
                    if not api_key:
                        continue

                    default = DEFAULTS.get(row.provider, {})
                    merged_config = dict(row.config or default.get("config", {}) or {})
                    merged_config["__resolved_setting_id"] = row.id
                    merged_config["__resolved_source"] = f"fallback:{row.provider}/{row.model}->{row.id}"
                    merged_config["__resolved_category"] = category
                    merged_config["__selection_source"] = "fallback_candidate"
                    avg_price_estimate = int((billing_service.estimate_system_api_average_price(session, int(row.id)) or {}).get("average_cost") or 0)
                    merged_config["__avg_price_estimate"] = avg_price_estimate

                    priced_candidates.append({
                        "provider": row.provider,
                        "api_key": api_key,
                        "base_url": row.base_url or default.get("base_url"),
                        "model": row.model or default.get("model"),
                        "config": merged_config,
                        "avg_price_estimate": avg_price_estimate,
                        "_setting_id": int(row.id),
                    })

                priced_candidates.sort(
                    key=lambda x: (
                        int(x.get("avg_price_estimate", 10**9) or 10**9),
                        int(x.get("_setting_id", 10**9) or 10**9),
                    )
                )
                if limit and int(limit) > 0:
                    priced_candidates = priced_candidates[: int(limit)]

                for item in priced_candidates:
                    item.pop("_setting_id", None)
                    results.append(item)

                logger.info(
                    "[fallback_configs] category=%s exclude_id=%s modality=%s found=%d limit=%d order=avg_price_asc",
                    category, exclude_setting_id, modality, len(results), limit,
                )
        except Exception as e:
            logger.error("Error fetching fallback configs: %s", e)
        return results

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
        }

        if tool in project_required_tools:
            if not project_id:
                return "Tool requires project context"
            if not self._has_project_access(db, user.id, int(project_id)):
                return "No permission to access this project"

        system_management_tools = {
            "search_system_api_settings",
            "upsert_system_api_pricing",
            "read_webpage",
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
        """兼容入口：清除 config 中的计价键，计价信息统一从行的宽表列读取。"""
        cfg = self._safe_json_dict(raw_cfg)
        for key in ("api_pricing", "billing_unit_type", "billing_cost", "billing_cost_input", "billing_cost_output"):
            cfg.pop(key, None)
        return cfg

    def _is_base_billing_rule(self, rule: SystemAPIBillingRule) -> bool:
        extra = self._safe_json_dict(getattr(rule, "extra_conditions", {}))
        if str(extra.get("rule_kind", "")).strip().lower() == self._BASE_BILLING_RULE_KIND:
            return True
        return int(getattr(rule, "priority", 0) or 0) <= self._BASE_BILLING_RULE_PRIORITY

    def _get_base_billing_rule(self, session, system_api_id: int) -> Optional[SystemAPIBillingRule]:
        rows = session.query(SystemAPIBillingRule).filter(
            SystemAPIBillingRule.system_api_id == int(system_api_id),
            SystemAPIBillingRule.is_active == True,
        ).order_by(SystemAPIBillingRule.id.desc()).all()
        for row in rows:
            if self._is_base_billing_rule(row):
                return row
        return None

    def _upsert_base_billing_rule(self, session, row: SystemAPISetting, billing: Dict[str, Any]) -> None:
        unit_type = self._normalize_unit_type_for_system_ai((billing or {}).get("unit_type") or "per_call")
        cost = max(0, int((billing or {}).get("cost") or 0))
        cost_input = max(0, int((billing or {}).get("cost_input") or 0))
        cost_output = max(0, int((billing or {}).get("cost_output") or 0))

        category = str(getattr(row, "category", "") or "").strip().lower()
        applies_to_text = category not in {"image", "video"}
        applies_to_image = category == "image"
        applies_to_video = category == "video"

        base_rule = self._get_base_billing_rule(session, int(row.id))
        now_iso = now_bj_iso()
        if base_rule:
            extra = self._safe_json_dict(getattr(base_rule, "extra_conditions", {}))
            extra["rule_kind"] = self._BASE_BILLING_RULE_KIND
            base_rule.name = "Base Pricing"
            base_rule.priority = self._BASE_BILLING_RULE_PRIORITY
            base_rule.applies_to_text = bool(applies_to_text)
            base_rule.applies_to_image = bool(applies_to_image)
            base_rule.applies_to_video = bool(applies_to_video)
            base_rule.billing_unit_type = unit_type
            base_rule.billing_cost = cost
            base_rule.billing_cost_input = cost_input
            base_rule.billing_cost_output = cost_output
            base_rule.extra_conditions = extra
            base_rule.is_active = True
            base_rule.updated_at = now_iso
            return

        session.add(SystemAPIBillingRule(
            system_api_id=int(row.id),
            name="Base Pricing",
            description="Base pricing rule generated by system management agent.",
            is_active=True,
            priority=self._BASE_BILLING_RULE_PRIORITY,
            applies_to_text=bool(applies_to_text),
            applies_to_image=bool(applies_to_image),
            applies_to_video=bool(applies_to_video),
            billing_unit_type=unit_type,
            billing_cost=cost,
            billing_cost_input=cost_input,
            billing_cost_output=cost_output,
            extra_conditions={"rule_kind": self._BASE_BILLING_RULE_KIND},
            created_at=now_iso,
            updated_at=now_iso,
        ))

    def _read_billing_from_row(self, row, session=None) -> Dict[str, Any]:
        """Read pricing from base billing rule (single source of truth)."""
        def _to_int(v: Any) -> int:
            try:
                parsed = int(float(v))
                return parsed if parsed > 0 else 0
            except Exception:
                return 0

        if session is not None:
            base_rule = self._get_base_billing_rule(session, int(getattr(row, "id", 0) or 0))
            if base_rule:
                return {
                    "unit_type": self._normalize_unit_type_for_system_ai(getattr(base_rule, "billing_unit_type", None) or "per_call"),
                    "cost": _to_int(getattr(base_rule, "billing_cost", 0)),
                    "cost_input": _to_int(getattr(base_rule, "billing_cost_input", 0)),
                    "cost_output": _to_int(getattr(base_rule, "billing_cost_output", 0)),
                }
        return {
            "unit_type": "per_call",
            "cost": 0,
            "cost_input": 0,
            "cost_output": 0,
        }

    async def _analyze_intent_with_fallback(
        self,
        user_id: int,
        primary_config: Dict[str, Any],
        call_fn,
        *,
        max_fallbacks: int = 3,
    ) -> tuple:
        """Call *call_fn(config)* with the primary config; on LLM error, retry
        with fallback configs.  Returns ``(result_dict, used_config)``.

        *call_fn* must be an async callable that accepts a single ``config``
        dict and returns the LLM result dict (with optional ``_llm_error`` key).
        """
        result = await call_fn(primary_config)
        if not result.get("_llm_error"):
            return result, primary_config

        primary_setting_id = (primary_config.get("config") or {}).get("__resolved_setting_id")
        logger.warning(
            "[agent.fallback] primary LLM failed | user_id=%s provider=%s model=%s setting_id=%s — trying fallbacks",
            user_id,
            primary_config.get("provider"),
            primary_config.get("model"),
            primary_setting_id,
        )
        fallbacks = self.get_fallback_configs(
            user_id=user_id,
            category="LLM",
            exclude_setting_id=primary_setting_id,
            limit=max_fallbacks,
        )
        for fb in fallbacks:
            fb_result = await call_fn(fb)
            if not fb_result.get("_llm_error"):
                logger.info(
                    "[agent.fallback] succeeded with fallback | provider=%s model=%s setting_id=%s",
                    fb.get("provider"), fb.get("model"),
                    (fb.get("config") or {}).get("__resolved_setting_id"),
                )
                return fb_result, fb
            logger.warning(
                "[agent.fallback] fallback also failed | provider=%s model=%s",
                fb.get("provider"), fb.get("model"),
            )
        # All failed — return original error result
        return result, primary_config

    async def process_system_management_command(self, request: AgentRequest, db: Session, user: User) -> AgentResponse:
        if not bool(getattr(user, "is_superuser", False)):
            raise PermissionError("Only superuser can use system management agent")

        llm_config = self.get_active_llm_config(user_id=user.id, category="LLM")
        if not llm_config or not llm_config.get("api_key"):
            raise ValueError("No active LLM API config found. Please check your LLM settings.")

        merged_context = dict(request.context or {})
        merged_context["agent_mode"] = "system_management"
        merged_context["query"] = request.query
        merged_context["history"] = request.history or []
        merged_context["system_api_model_catalog"] = self._build_system_api_model_catalog_for_llm(db)
        merged_context["auth"] = {
            "user_id": user.id,
            "is_superuser": True,
            "is_authorized": bool(getattr(user, "is_authorized", False)),
            "username": getattr(user, "username", None),
        }

        async def _call_with_config(cfg):
            return await llm_service.analyze_intent_with_system_prompt(
                request.query, merged_context, request.history or [],
                cfg, self._SYSTEM_MANAGEMENT_PROMPT,
            )

        llm_result, llm_config = await self._analyze_intent_with_fallback(
            user.id, llm_config, _call_with_config,
        )
        llm_result = self._normalize_llm_result(llm_result)

        # Debug: trace LLM plan result before fallback
        _plan_from_llm = llm_result.get("plan") or []
        _reply_snippet = str(llm_result.get("reply") or "")[:120]
        logger.info(
            "[system_management] LLM result | plan_count=%d reply_snippet=%s",
            len(_plan_from_llm), _reply_snippet,
        )

        if not (llm_result.get("plan") or []):
            query_text = str(request.query or "").strip().lower()
            requested_pages = self._extract_requested_page_count(request.query)
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
            if any(token in query_text for token in followup_query_tokens) and not (llm_result.get("plan") or []):
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

            # URL detection — always takes priority when a URL is in the query.
            # This ensures read_webpage is called even if the LLM refuses or
            # claims it cannot browse.
            url_match = re.search(r"https?://[^\s)]+", str(request.query or ""), flags=re.IGNORECASE)
            if url_match:
                logger.info("[system_management] URL fallback triggered | url=%s", url_match.group(0))
                llm_result["plan"] = [
                    {
                        "tool": "read_webpage",
                        "parameters": {
                            "url": url_match.group(0),
                            "max_chars": 6000,
                        },
                    }
                ]
                if not str(llm_result.get("reply") or "").strip():
                    llm_result["reply"] = "正在读取并解析您提供的网页内容。"

            continue_page_tokens = [
                "继续读下一页",
                "继续读取下一页",
                "下一页",
                "next page",
                "continue to next",
            ]
            if any(token in query_text for token in continue_page_tokens) and not (llm_result.get("plan") or []):
                next_url = self._extract_next_page_url_from_history(request.history or [])
                if next_url:
                    llm_result["plan"] = [
                        {
                            "tool": "read_webpage",
                            "parameters": {
                                "url": next_url,
                                "max_chars": 6000,
                                "max_pages": requested_pages,
                            },
                        }
                    ]
                    if not str(llm_result.get("reply") or "").strip():
                        llm_result["reply"] = "正在继续逐页读取下一页内容。"

            # Pricing intent retry: if plan is still empty but query contains
            # pricing data, re-call LLM with a focused extraction prompt.
            if not (llm_result.get("plan") or []):
                if self._has_pricing_content(request.query) or self._has_pricing_content(str(llm_result.get("reply") or "")):
                    logger.info("[system_management] pricing retry triggered | query_len=%d reply_len=%d", len(request.query or ""), len(str(llm_result.get("reply") or "")))
                    retry_result = await self._retry_extract_pricing_plan(
                        request.query, str(llm_result.get("reply") or ""), llm_config,
                    )
                    if retry_result and (retry_result.get("plan") or []):
                        llm_result["plan"] = retry_result["plan"]
                        # Merge reply if retry produced a better one
                        retry_reply = str(retry_result.get("reply") or "").strip()
                        if retry_reply:
                            llm_result["reply"] = retry_reply

        actions: List[AgentAction] = []
        updated_data = None
        last_tool_result = None
        pending_write_previews: List[Dict[str, Any]] = []
        provider_alias_lookup = self._build_provider_alias_lookup(db)

        for plan_item in llm_result.get("plan", []):
            normalized = self._extract_plan_item_tool_and_params(plan_item)
            tool_name = normalized["tool_name"]
            params = normalized["params"]
            if tool_name not in self._SYSTEM_MANAGEMENT_ALLOWED_TOOLS:
                actions.append(AgentAction(
                    tool=tool_name or "unknown",
                    parameters=params,
                    status="failed",
                    result=f"Tool '{tool_name}' is not allowed for system management agent",
                ))
                continue

            for k, v in list(params.items()):
                if v == "__LAST_RESULT__" and last_tool_result is not None:
                    params[k] = last_tool_result

            if tool_name == "upsert_system_api_pricing":
                params = self._hydrate_upsert_system_api_target(db, params, request.query)
                existing_row = self._find_existing_system_api_setting(
                    db,
                    str(params.get("provider") or "").strip(),
                    str(params.get("category") or "LLM").strip() or "LLM",
                    str(params.get("model") or "").strip(),
                )
                if not self._is_system_write_confirmation(request.query, request.history or [], params):
                    preview = self._normalize_system_upsert_preview(params)
                    preview["provider_alias"] = self._resolve_provider_alias(preview.get("provider"), provider_alias_lookup)
                    preview = self._annotate_system_upsert_preview_with_rule_action(db, params, preview, existing_row)
                    pending_write_previews.append(preview)
                    pending_msg = "Write confirmation required. Please explicitly confirm before applying pricing updates."
                    if not existing_row:
                        pending_msg = (
                            "Write confirmation required. Target API setting is missing and will be auto-created before applying pricing updates."
                        )
                    actions.append(AgentAction(
                        tool=tool_name,
                        parameters=params,
                        status="blocked",
                        result=pending_msg,
                    ))
                    continue

            action = AgentAction(tool=tool_name, parameters=params)
            logger.info("[system_management] executing tool=%s params_keys=%s", tool_name, list(params.keys()))
            execution_result = await self._execute_tool(action, db, user, None, llm_config, merged_context, tool_policy=None)
            logger.info("[system_management] tool=%s completed status=%s result_len=%d", tool_name, execution_result.get("status"), len(str(execution_result.get("result") or "")))

            action.result = execution_result.get("result")
            action.status = execution_result.get("status", "failed")
            if action.status == "completed":
                last_tool_result = action.result
            if execution_result.get("data_update"):
                updated_data = execution_result.get("data_update")
            actions.append(action)

        write_intent_tokens = ["更新", "应用", "写入", "保存", "创建", "apply", "update", "create", "set", "sync"]
        query_lower = str(request.query or "").strip().lower()
        has_write_intent = any(token in query_lower for token in write_intent_tokens)

        if has_write_intent and not pending_write_previews:
            auto_blocked_actions: List[AgentAction] = []
            for action in actions:
                if action.tool != "read_webpage" or action.status != "completed" or not isinstance(action.result, dict):
                    continue
                candidates = action.result.get("pricing_candidates") if isinstance(action.result.get("pricing_candidates"), list) else []
                for candidate in candidates[:3]:
                    params = {
                        "provider": str(candidate.get("provider") or "").strip(),
                        "category": str(candidate.get("category") or "LLM").strip() or "LLM",
                        "model": str(candidate.get("model") or "").strip(),
                        "unit_type": str(candidate.get("unit_type") or "per_call").strip() or "per_call",
                        "supplier_price": candidate.get("supplier_price"),
                        "supplier_price_input": candidate.get("supplier_price_input"),
                        "supplier_price_output": candidate.get("supplier_price_output"),
                        "multiplier": candidate.get("multiplier") if candidate.get("multiplier") is not None else 1.0,
                    }
                    if not params["provider"] or not params["model"]:
                        continue
                    if (
                        params.get("supplier_price") is None
                        and params.get("supplier_price_input") is None
                        and params.get("supplier_price_output") is None
                    ):
                        continue
                    existing_row = self._find_existing_system_api_setting(
                        db,
                        params["provider"],
                        params["category"],
                        params["model"],
                    )
                    if not existing_row:
                        continue

                    preview = self._normalize_system_upsert_preview(params)
                    preview["provider_alias"] = self._resolve_provider_alias(preview.get("provider"), provider_alias_lookup)
                    preview = self._annotate_system_upsert_preview_with_rule_action(db, params, preview, existing_row)
                    pending_write_previews.append(preview)
                    auto_blocked_actions.append(AgentAction(
                        tool="upsert_system_api_pricing",
                        parameters=params,
                        status="blocked",
                        result="Write confirmation required. Auto-generated from webpage pricing extraction.",
                    ))

            if auto_blocked_actions:
                actions.extend(auto_blocked_actions)

        if pending_write_previews:
            preview_lines = []
            for idx, item in enumerate(pending_write_previews, start=1):
                provider_label = str(item.get("provider_alias") or item.get("provider") or "").strip() or "-"
                action_label = str(item.get("preview_action_label") or "待确认")
                action_suffix = f"action={action_label}"
                if item.get("preview_rule_id") is not None:
                    action_suffix += f"(rule_id={item.get('preview_rule_id')})"
                category_text = str(item.get("category") or "").strip().lower()
                if category_text == "image":
                    preview_lines.append(
                        f"{idx}) provider={provider_label}, category={item.get('category')}, model={item.get('model')}, "
                        f"unit={item.get('unit_type')}, per_image={float(item.get('cost_decimal') or 0):.2f}, multiplier={float(item.get('multiplier_2dp') or 0):.2f}, {action_suffix}"
                    )
                elif str(item.get("unit_type") or "") in {"per_token", "per_1k_tokens", "per_million_tokens"}:
                    preview_lines.append(
                        f"{idx}) provider={provider_label}, category={item.get('category')}, model={item.get('model')}, "
                        f"unit={item.get('unit_type')}, in/out={float(item.get('cost_input_decimal') or 0):.2f}/{float(item.get('cost_output_decimal') or 0):.2f}, multiplier={float(item.get('multiplier_2dp') or 0):.2f}, {action_suffix}"
                    )
                else:
                    preview_lines.append(
                        f"{idx}) provider={provider_label}, category={item.get('category')}, model={item.get('model')}, "
                        f"unit={item.get('unit_type')}, cost={float(item.get('cost_decimal') or 0):.2f}, multiplier={float(item.get('multiplier_2dp') or 0):.2f}, {action_suffix}"
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

        logger.info("[system_management] DONE | actions=%d final_reply_len=%d", len(actions), len(final_reply))
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

    # ── Streaming command processors (SSE) ────────────────────────────────

    async def stream_process_command(
        self, request: AgentRequest, db: Session, user: User
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Streaming version of process_command. Yields SSE event dicts."""
        import asyncio as _asyncio
        print(f"[STREAM-DEBUG] agent_service.stream_process_command entered, query={request.query[:80] if request.query else 'N/A'}")
        user_id = user.id
        project_id = request.project_id or request.context.get("project_id") or request.context.get("projectId")

        # Run synchronous DB work in a thread so it doesn't block the event loop
        llm_config = await _asyncio.to_thread(self.get_active_llm_config, user_id=user_id, category="LLM")

        # Inject user's active API settings into context
        # NOTE: _build_user_active_settings_summary uses the endpoint's db session,
        # so it must run on the event loop thread (not asyncio.to_thread).
        try:
            active_settings = self._build_user_active_settings_summary(db, user_id)
            if active_settings:
                merged_ctx = dict(request.context or {})
                merged_ctx["my_active_api_settings"] = active_settings
                request = request.copy(update={"context": merged_ctx})
        except Exception as e:
            logger.warning("Failed to build user active settings summary: %s", e)

        if request.context.get("is_refinement"):
            # Refinement doesn't call LLM – skip streaming
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
                            "reference_image_url": request.context.get("reference_image_url"),
                        },
                    }
                ],
            }
            yield {"type": "token", "content": llm_result["reply"]}
        else:
            # Stream intent analysis from LLM
            print(f"[STREAM-DEBUG] agent_service: about to call llm_service.stream_analyze_intent, llm_config keys={list(llm_config.keys()) if llm_config else 'None'}")
            llm_result = None
            token_count = 0
            async for event in llm_service.stream_analyze_intent(
                request.query, request.context, request.history, llm_config
            ):
                if event.get("type") == "token":
                    token_count += 1
                    if token_count <= 3:
                        print(f"[STREAM-DEBUG] agent_service: received token #{token_count}: {repr(event.get('content','')[:50])}")
                    yield event
                elif event.get("type") == "result":
                    print(f"[STREAM-DEBUG] agent_service: received result event, reply_len={len(str(event.get('reply','')))}, plan_len={len(event.get('plan',[]))}")
                    llm_result = event

            if llm_result is None:
                yield {"type": "error", "message": "LLM returned no result"}
                return
            if llm_result.get("_llm_error"):
                yield {"type": "error", "message": llm_result.get("reply", "LLM error")}
                return

        llm_result = self._normalize_llm_result(llm_result)

        # Execute tools from plan
        actions: List[AgentAction] = []
        updated_data = None
        last_tool_result = None
        tool_policy = self._get_agent_tool_policy(db)
        merged_context_mode = str((request.context or {}).get("agent_mode") or "project").strip() or "project"

        for plan_item in llm_result.get("plan", []):
            normalized = self._extract_plan_item_tool_and_params(plan_item)
            tool_name = normalized["tool_name"]
            params = normalized["params"]
            if tool_name not in self._PROJECT_AGENT_ALLOWED_TOOLS:
                actions.append(AgentAction(
                    tool=tool_name or "unknown",
                    parameters=params,
                    status="failed",
                    result=f"Tool '{tool_name}' is not allowed for project agent mode ({merged_context_mode})",
                ))
                continue

            for k, v in params.items():
                if v == "__LAST_RESULT__" and last_tool_result:
                    params[k] = last_tool_result

            if tool_name == "activate_model":
                if not self._is_activate_model_confirmation(request.query, request.history or [], params):
                    setting_id = params.get("setting_id")
                    actions.append(AgentAction(tool=tool_name, parameters=params, status="blocked",
                                               result=f"请确认是否要激活此模型 (setting_id={setting_id})？"))
                    yield {"type": "done", "reply": "检测到模型切换操作，请确认是否要激活该模型？回复「确认」即可执行。",
                           "actions": [a.dict() for a in actions], "usage": llm_result.get("usage", {})}
                    return

            yield {"type": "tool_start", "tool": tool_name, "parameters": params}

            action = AgentAction(tool=tool_name, parameters=params)
            execution_result = await self._execute_tool(
                action, db, user, project_id, llm_config, request.context, tool_policy=tool_policy
            )
            action.result = execution_result["result"]
            action.status = execution_result["status"]
            if action.status == "completed":
                last_tool_result = action.result
            if execution_result.get("data_update"):
                updated_data = execution_result["data_update"]
            actions.append(action)

            yield {"type": "tool_result", "tool": tool_name, "status": action.status,
                   "result": action.result}

        final_reply = llm_result.get("reply", "")
        yield {
            "type": "done",
            "reply": final_reply,
            "actions": [a.dict() for a in actions],
            "updated_data": updated_data or {
                "type": "agent_plan_visualization",
                "query": request.query,
                "steps": [{"tool": a.tool, "status": a.status} for a in actions],
            },
            "usage": llm_result.get("usage", {}),
        }

    async def stream_process_system_management_command(
        self, request: AgentRequest, db: Session, user: User
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Streaming version of process_system_management_command. Yields SSE event dicts."""
        import asyncio as _asyncio
        if not bool(getattr(user, "is_superuser", False)):
            yield {"type": "error", "message": "Only superuser can use system management agent"}
            return

        llm_config = await _asyncio.to_thread(self.get_active_llm_config, user_id=user.id, category="LLM")
        if not llm_config or not llm_config.get("api_key"):
            yield {"type": "error", "message": "No active LLM API config found."}
            return

        merged_context = dict(request.context or {})
        merged_context["agent_mode"] = "system_management"
        merged_context["query"] = request.query
        merged_context["history"] = request.history or []
        merged_context["system_api_model_catalog"] = self._build_system_api_model_catalog_for_llm(db)
        merged_context["auth"] = {
            "user_id": user.id,
            "is_superuser": True,
            "is_authorized": bool(getattr(user, "is_authorized", False)),
            "username": getattr(user, "username", None),
        }

        # Stream intent analysis from LLM
        llm_result = None
        async for event in llm_service.stream_analyze_intent_with_system_prompt(
            request.query, merged_context, request.history or [],
            llm_config, self._SYSTEM_MANAGEMENT_PROMPT,
        ):
            if event.get("type") == "token":
                yield event
            elif event.get("type") == "result":
                llm_result = event

        if llm_result is None:
            yield {"type": "error", "message": "LLM returned no result"}
            return
        if llm_result.get("_llm_error"):
            yield {"type": "error", "message": llm_result.get("reply", "LLM error")}
            return

        llm_result = self._normalize_llm_result(llm_result)

        # Fallback plan detection (same as non-streaming version)
        if not (llm_result.get("plan") or []):
            query_text = str(request.query or "").strip().lower()
            list_intent_tokens = ["api设置", "api 設置", "api 设置", "api settings", "settings", "配置", "list api", "有哪些api", "现有哪些api"]
            if any(token in query_text for token in list_intent_tokens):
                llm_result["plan"] = [{"tool": "search_system_api_settings", "parameters": {"limit": 50}}]
                if not str(llm_result.get("reply") or "").strip():
                    llm_result["reply"] = "已为您检索当前系统 API 设置（最多 50 条）。"

            followup_query_tokens = ["查询", "查一下", "查出来", "查到了吗", "结果", "有没有", "现有", "list", "show"]
            if any(token in query_text for token in followup_query_tokens) and not (llm_result.get("plan") or []):
                provider_hint = self._infer_provider_hint_from_history(request.query, request.history or [])
                llm_result["plan"] = [{"tool": "search_system_api_settings", "parameters": {"provider": provider_hint or None, "limit": 50}}]
                if not str(llm_result.get("reply") or "").strip():
                    llm_result["reply"] = "正在为您查询现有系统 API 配置。"

            url_match = re.search(r"https?://[^\s)]+", str(request.query or ""), flags=re.IGNORECASE)
            if url_match:
                logger.info("[system_management_stream] URL fallback triggered | url=%s", url_match.group(0))
                llm_result["plan"] = [{"tool": "read_webpage", "parameters": {"url": url_match.group(0), "max_chars": 6000}}]
                if not str(llm_result.get("reply") or "").strip():
                    llm_result["reply"] = "正在读取并解析您提供的网页内容。"

            continue_page_tokens = ["继续读下一页", "继续读取下一页", "下一页", "next page", "continue to next"]
            if any(token in query_text for token in continue_page_tokens) and not (llm_result.get("plan") or []):
                next_url = self._extract_next_page_url_from_history(request.history or [])
                if next_url:
                    llm_result["plan"] = [{"tool": "read_webpage", "parameters": {"url": next_url, "max_chars": 6000}}]
                    if not str(llm_result.get("reply") or "").strip():
                        llm_result["reply"] = "正在继续逐页读取下一页内容。"

            # Pricing intent retry
            if not (llm_result.get("plan") or []):
                if self._has_pricing_content(request.query) or self._has_pricing_content(str(llm_result.get("reply") or "")):
                    logger.info("[system_management_stream] pricing retry triggered")
                    retry_result = await self._retry_extract_pricing_plan(
                        request.query, str(llm_result.get("reply") or ""), llm_config,
                    )
                    if retry_result and (retry_result.get("plan") or []):
                        llm_result["plan"] = retry_result["plan"]
                        retry_reply = str(retry_result.get("reply") or "").strip()
                        if retry_reply:
                            llm_result["reply"] = retry_reply

        # Execute tools
        actions: List[AgentAction] = []
        updated_data = None
        pending_write_previews: List[Dict[str, Any]] = []
        provider_alias_lookup = self._build_provider_alias_lookup(db)
        tool_policy = self._get_agent_tool_policy(db)

        for plan_item in llm_result.get("plan", []):
            normalized = self._extract_plan_item_tool_and_params(plan_item)
            tool_name = normalized["tool_name"]
            params = normalized["params"]
            if tool_name not in self._SYSTEM_MANAGEMENT_ALLOWED_TOOLS:
                actions.append(AgentAction(
                    tool=tool_name or "unknown",
                    parameters=params,
                    status="failed",
                    result=f"Tool '{tool_name}' is not allowed in system management mode",
                ))
                continue

            if tool_name == "upsert_system_api_pricing":
                params = self._hydrate_upsert_system_api_target(db, params, request.query)
                existing_row = self._find_existing_system_api_setting(
                    db,
                    str(params.get("provider") or "").strip(),
                    str(params.get("category") or "LLM").strip() or "LLM",
                    str(params.get("model") or "").strip(),
                )
                if not self._is_system_write_confirmation(request.query, request.history or [], params):
                    preview = self._normalize_system_upsert_preview(params)
                    preview["provider_alias"] = self._resolve_provider_alias(preview.get("provider"), provider_alias_lookup)
                    preview = self._annotate_system_upsert_preview_with_rule_action(db, params, preview, existing_row)
                    pending_write_previews.append(preview)
                    pending_msg = "Write confirmation required. Please explicitly confirm before applying pricing updates."
                    if not existing_row:
                        pending_msg = (
                            "Write confirmation required. Target API setting is missing and will be auto-created before applying pricing updates."
                        )
                    actions.append(AgentAction(
                        tool=tool_name,
                        parameters=params,
                        status="blocked",
                        result=pending_msg,
                    ))
                    continue

            yield {"type": "tool_start", "tool": tool_name, "parameters": params}

            action = AgentAction(tool=tool_name, parameters=params)
            execution_result = await self._execute_tool(
                action, db, user, None, llm_config, merged_context, tool_policy=tool_policy
            )
            action.result = execution_result["result"]
            action.status = execution_result["status"]
            if execution_result.get("data_update"):
                updated_data = execution_result["data_update"]
            actions.append(action)

            yield {"type": "tool_result", "tool": tool_name, "status": action.status,
                   "result": action.result}

        write_intent_tokens = ["更新", "应用", "写入", "保存", "创建", "apply", "update", "create", "set", "sync"]
        query_lower = str(request.query or "").strip().lower()
        has_write_intent = any(token in query_lower for token in write_intent_tokens)

        if has_write_intent and not pending_write_previews:
            auto_blocked_actions: List[AgentAction] = []
            for action in actions:
                if action.tool != "read_webpage" or action.status != "completed" or not isinstance(action.result, dict):
                    continue
                candidates = action.result.get("pricing_candidates") if isinstance(action.result.get("pricing_candidates"), list) else []
                for candidate in candidates[:3]:
                    params = {
                        "provider": str(candidate.get("provider") or "").strip(),
                        "category": str(candidate.get("category") or "LLM").strip() or "LLM",
                        "model": str(candidate.get("model") or "").strip(),
                        "unit_type": str(candidate.get("unit_type") or "per_call").strip() or "per_call",
                        "supplier_price": candidate.get("supplier_price"),
                        "supplier_price_input": candidate.get("supplier_price_input"),
                        "supplier_price_output": candidate.get("supplier_price_output"),
                        "multiplier": candidate.get("multiplier") if candidate.get("multiplier") is not None else 1.0,
                    }
                    if not params["provider"] or not params["model"]:
                        continue
                    if (
                        params.get("supplier_price") is None
                        and params.get("supplier_price_input") is None
                        and params.get("supplier_price_output") is None
                    ):
                        continue
                    existing_row = self._find_existing_system_api_setting(
                        db,
                        params["provider"],
                        params["category"],
                        params["model"],
                    )
                    if not existing_row:
                        continue

                    preview = self._normalize_system_upsert_preview(params)
                    preview["provider_alias"] = self._resolve_provider_alias(preview.get("provider"), provider_alias_lookup)
                    preview = self._annotate_system_upsert_preview_with_rule_action(db, params, preview, existing_row)
                    pending_write_previews.append(preview)
                    auto_blocked_actions.append(AgentAction(
                        tool="upsert_system_api_pricing",
                        parameters=params,
                        status="blocked",
                        result="Write confirmation required. Auto-generated from webpage pricing extraction.",
                    ))

            if auto_blocked_actions:
                actions.extend(auto_blocked_actions)

        if pending_write_previews:
            preview_lines = []
            for idx, item in enumerate(pending_write_previews, start=1):
                provider_label = str(item.get("provider_alias") or item.get("provider") or "").strip() or "-"
                action_label = str(item.get("preview_action_label") or "待确认")
                action_suffix = f"action={action_label}"
                if item.get("preview_rule_id") is not None:
                    action_suffix += f"(rule_id={item.get('preview_rule_id')})"
                category_text = str(item.get("category") or "").strip().lower()
                if category_text == "image":
                    preview_lines.append(
                        f"{idx}) provider={provider_label}, category={item.get('category')}, model={item.get('model')}, "
                        f"unit={item.get('unit_type')}, per_image={float(item.get('cost_decimal') or 0):.2f}, multiplier={float(item.get('multiplier_2dp') or 0):.2f}, {action_suffix}"
                    )
                elif str(item.get("unit_type") or "") in {"per_token", "per_1k_tokens", "per_million_tokens"}:
                    preview_lines.append(
                        f"{idx}) provider={provider_label}, category={item.get('category')}, model={item.get('model')}, "
                        f"unit={item.get('unit_type')}, in/out={float(item.get('cost_input_decimal') or 0):.2f}/{float(item.get('cost_output_decimal') or 0):.2f}, multiplier={float(item.get('multiplier_2dp') or 0):.2f}, {action_suffix}"
                    )
                else:
                    preview_lines.append(
                        f"{idx}) provider={provider_label}, category={item.get('category')}, model={item.get('model')}, "
                        f"unit={item.get('unit_type')}, cost={float(item.get('cost_decimal') or 0):.2f}, multiplier={float(item.get('multiplier_2dp') or 0):.2f}, {action_suffix}"
                    )

            confirm_tip = (
                "检测到定价写入操作。请确认后再执行：\n"
                + "\n".join(preview_lines)
                + "\n\n如确认，请回复：确认执行以上更新"
            )

            yield {
                "type": "done",
                "reply": confirm_tip,
                "actions": [a.dict() for a in actions],
                "updated_data": {
                    "type": "system_management_write_confirmation_required",
                    "items": pending_write_previews,
                },
                "usage": llm_result.get("usage", {}),
            }
            return

        action_summary = self._build_system_management_action_summary(actions)
        final_reply = str(llm_result.get("reply", "") or "").strip()
        if action_summary:
            final_reply = (final_reply + "\n\n" + action_summary).strip()

        yield {
            "type": "done",
            "reply": final_reply,
            "actions": [a.dict() for a in actions],
            "updated_data": updated_data or {
                "type": "system_management_agent_plan",
                "query": request.query,
                "steps": [{"tool": a.tool, "status": a.status} for a in actions],
            },
            "usage": llm_result.get("usage", {}),
        }

    def _build_user_active_settings_summary(self, db: Session, user_id: int) -> List[Dict[str, Any]]:
        """Build a summary of the user's active API settings with model details & pricing."""
        rows = db.query(APISetting).filter(
            APISetting.user_id == user_id,
            APISetting.is_active == True,
        ).order_by(APISetting.category, APISetting.id.desc()).all()

        items = []
        for row in rows:
            provider = str(row.provider or "").strip()
            model = str(row.model or "").strip()
            category = str(row.category or "").strip()
            if not provider or not model:
                continue

            sys_setting = db.query(SystemAPISetting).filter(
                SystemAPISetting.provider == provider,
                SystemAPISetting.model == model,
                SystemAPISetting.category == category,
            ).first()
            if not sys_setting:
                sys_setting = db.query(SystemAPISetting).filter(
                    SystemAPISetting.provider == provider,
                    SystemAPISetting.model == model,
                ).first()

            item: Dict[str, Any] = {
                "category": category,
                "provider": provider,
                "model": model,
            }
            if sys_setting:
                api_pricing = self._read_billing_from_row(sys_setting, session=db)
                item["name"] = sys_setting.name
                item["api_pricing"] = api_pricing
            items.append(item)
        return items

    def _build_system_api_model_catalog_for_llm(self, db: Session, limit: int = 200) -> List[Dict[str, Any]]:
        """Build a compact model catalog for LLM-side fuzzy model-name matching.

        This mirrors the KIE pricing helper pattern where system model names are
        provided explicitly so the LLM can map source model labels to canonical
        provider/category/model targets before pricing analysis.
        """
        safe_limit = max(20, min(int(limit or 200), 400))
        rows = db.query(SystemAPISetting).filter(
            ~SystemAPISetting.category.like("System_%")
        ).order_by(SystemAPISetting.id.desc()).limit(safe_limit).all()

        catalog: List[Dict[str, Any]] = []
        for row in rows:
            provider = str(getattr(row, "provider", "") or "").strip()
            category = str(getattr(row, "category", "") or "").strip()
            model = str(getattr(row, "model", "") or "").strip()
            if not provider or not model:
                continue

            modality = row.modality if isinstance(getattr(row, "modality", None), dict) else {}
            base_model = str(getattr(row, "base_model", "") or "").strip() or str(modality.get("base_model") or "").strip()
            tags = getattr(row, "tags", None)
            tags_out = [str(t).strip() for t in (tags if isinstance(tags, list) else []) if str(t).strip()][:8]

            catalog.append({
                "system_api_id": int(getattr(row, "id", 0) or 0),
                "provider": provider,
                "category": category,
                "model": model,
                "name": str(getattr(row, "name", "") or "").strip(),
                "base_model": base_model or None,
                "tags": tags_out,
            })

        return catalog

    async def process_command(self, request: AgentRequest, db: Session, user: User) -> AgentResponse:
        user_id = user.id
        project_id = request.project_id or request.context.get("project_id") or request.context.get("projectId")
        
        # Resolve LLM Config from user's active setting (falls back to system default).
        llm_config = self.get_active_llm_config(user_id=user_id, category="LLM")

        # Inject user's active API settings into context for the LLM
        try:
            active_settings = self._build_user_active_settings_summary(db, user_id)
            if active_settings:
                merged_ctx = dict(request.context or {})
                merged_ctx["my_active_api_settings"] = active_settings
                request = request.copy(update={"context": merged_ctx})
        except Exception as e:
            logger.warning("Failed to build user active settings summary: %s", e)

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
            async def _call_with_config(cfg):
                return await llm_service.analyze_intent(request.query, request.context, request.history, cfg)

            llm_result, llm_config = await self._analyze_intent_with_fallback(
                user_id, llm_config, _call_with_config,
            )
        llm_result = self._normalize_llm_result(llm_result)

        actions: List[AgentAction] = []
        updated_data = None
        last_tool_result = None

        tool_policy = self._get_agent_tool_policy(db)
        merged_context_mode = str((request.context or {}).get("agent_mode") or "project").strip() or "project"

        for plan_item in llm_result.get("plan", []):
            normalized = self._extract_plan_item_tool_and_params(plan_item)
            tool_name = normalized["tool_name"]
            params = normalized["params"]
            if tool_name not in self._PROJECT_AGENT_ALLOWED_TOOLS:
                actions.append(AgentAction(
                    tool=tool_name or "unknown",
                    parameters=params,
                    status="failed",
                    result=f"Tool '{tool_name}' is not allowed for project agent mode ({merged_context_mode})",
                ))
                continue

            for k, v in params.items():
                if v == "__LAST_RESULT__" and last_tool_result:
                    params[k] = last_tool_result

            # Gate: activate_model requires explicit user confirmation
            if tool_name == "activate_model":
                if not self._is_activate_model_confirmation(request.query, request.history or [], params):
                    setting_id = params.get("setting_id")
                    actions.append(AgentAction(
                        tool=tool_name,
                        parameters=params,
                        status="blocked",
                        result=f"请确认是否要激活此模型 (setting_id={setting_id})？回复「确认」或「activate」即可执行。",
                    ))
                    # Return early with confirmation prompt
                    return AgentResponse(
                        reply=f"检测到模型切换操作，请确认是否要激活该模型？回复「确认」即可执行。",
                        actions=actions,
                        updated_data={"type": "model_activation_confirmation_required", "setting_id": setting_id},
                        usage=llm_result.get("usage"),
                    )

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
            modality = str(params.get("modality") or "").strip()
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

            # Post-fetch modality filter (JSON column)
            if modality:
                from app.services.modality_utils import modality_matches
                rows = [r for r in rows if modality_matches(getattr(r, "modality", None), modality)]

            alias_lookup = self._build_provider_alias_lookup(db)
            items = []
            for row in rows:
                api_pricing = self._read_billing_from_row(row, session=db)
                items.append({
                    "id": row.id,
                    "name": row.name,
                    "provider": row.provider,
                    "provider_alias": self._resolve_provider_alias(row.provider, alias_lookup),
                    "category": row.category,
                    "model": row.model,
                    "modality": row.modality,
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
            params = self._normalize_upsert_system_api_pricing_params(params)
            params = self._hydrate_upsert_system_api_target(
                db,
                params,
                str((context or {}).get("query") or ""),
            )
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

            row = self._find_existing_system_api_setting(db, provider, category, model)
            if not row:
                row = self._ensure_system_api_setting_for_pricing_upsert(db, provider, category, model)
            if not row:
                return {
                    "status": "failed",
                    "result": (
                        "Target API setting does not exist and auto-create failed "
                        f"({provider}/{category}/{model}). Please create it first in System API settings CRUD."
                    ),
                }

            now_iso = now_bj_iso()
            billing = {
                "unit_type": unit_type,
                "cost": cost,
                "cost_input": cost_input,
                "cost_output": cost_output,
            }
            patch_cfg = {
                "supplier_pricing": {
                    "unit_type": unit_type,
                    "supplier_price": supplier_price,
                    "supplier_price_input": supplier_price_input,
                    "supplier_price_output": supplier_price_output,
                    "source": "system_management_agent",
                    "updated_at": now_iso,
                },
                "pricing_scheme": {
                    "strategy": "supplier_price_x_multiplier",
                    "multiplier": multiplier,
                    "updated_at": now_iso,
                },
            }

            action = "update"
            cfg = self._safe_json_dict(row.config)
            for key in ("api_pricing", "billing_unit_type", "billing_cost", "billing_cost_input", "billing_cost_output"):
                cfg.pop(key, None)
            row.config = {**cfg, **patch_cfg}
            has_rule_dimensions = self._has_rule_dimension_params(params)
            rule_id = None
            rule_action = "base_update"
            if has_rule_dimensions:
                signature = self._extract_rule_signature_from_params(params, category)
                matched_rule = self._find_matching_granular_rule(db, int(row.id), signature)
                rule_name = str(params.get("rule_name") or params.get("name") or "Granular Pricing Rule").strip()
                rule_description = str(params.get("rule_description") or "").strip() or None
                priority_val = self._safe_optional_int(params.get("priority"))
                priority = priority_val if priority_val is not None else 0
                is_rule_active = self._safe_optional_bool(params.get("is_active"))
                now_rule_iso = now_bj_iso()

                if matched_rule:
                    matched_rule.name = rule_name
                    matched_rule.description = rule_description
                    matched_rule.priority = int(priority)
                    matched_rule.applies_to_text = bool(signature.get("applies_to_text", False))
                    matched_rule.applies_to_image = bool(signature.get("applies_to_image", False))
                    matched_rule.applies_to_video = bool(signature.get("applies_to_video", False))
                    for field in self._RULE_DIMENSION_FIELDS:
                        setattr(matched_rule, field, signature.get(field))
                    matched_rule.billing_unit_type = unit_type
                    matched_rule.billing_cost = cost
                    matched_rule.billing_cost_input = cost_input
                    matched_rule.billing_cost_output = cost_output
                    matched_rule.extra_conditions = signature.get("extra_conditions") or {}
                    matched_rule.is_active = True if is_rule_active is None else bool(is_rule_active)
                    matched_rule.updated_at = now_rule_iso
                    rule_id = int(matched_rule.id)
                    rule_action = "rule_update"
                else:
                    new_rule = SystemAPIBillingRule(
                        system_api_id=int(row.id),
                        name=rule_name,
                        description=rule_description,
                        is_active=True if is_rule_active is None else bool(is_rule_active),
                        priority=int(priority),
                        applies_to_text=bool(signature.get("applies_to_text", False)),
                        applies_to_image=bool(signature.get("applies_to_image", False)),
                        applies_to_video=bool(signature.get("applies_to_video", False)),
                        billing_unit_type=unit_type,
                        billing_cost=cost,
                        billing_cost_input=cost_input,
                        billing_cost_output=cost_output,
                        extra_conditions=signature.get("extra_conditions") or {},
                        created_at=now_rule_iso,
                        updated_at=now_rule_iso,
                    )
                    for field in self._RULE_DIMENSION_FIELDS:
                        setattr(new_rule, field, signature.get(field))
                    db.add(new_rule)
                    db.flush()
                    rule_id = int(new_rule.id)
                    rule_action = "rule_create"
            else:
                self._upsert_base_billing_rule(db, row, billing)
            if params.get("base_url"):
                row.base_url = str(params.get("base_url") or "").strip()
            if params.get("name"):
                row.name = str(params.get("name") or "").strip()
            if params.get("modality"):
                raw_modality = params.get("modality")
                if isinstance(raw_modality, dict):
                    row.modality = raw_modality
                elif isinstance(raw_modality, str) and raw_modality.strip():
                    from app.services.modality_utils import migrate_legacy_modality_string
                    row.modality = migrate_legacy_modality_string(raw_modality) or row.modality
            if params.get("tags"):
                raw_tags = params.get("tags")
                if isinstance(raw_tags, list):
                    row.tags = raw_tags
            if params.get("is_active") is not None:
                row.is_active = bool(params.get("is_active"))

            db.commit()

            payload = {
                "action": action,
                "setting_id": row.id,
                "provider": provider,
                "category": category,
                "model": model,
                "modality": getattr(row, "modality", None),
                "api_pricing": billing,
                "multiplier": multiplier,
                "rule_action": rule_action,
                "rule_id": rule_id,
                "has_rule_dimensions": has_rule_dimensions,
            }
            return {
                "status": "completed",
                "result": payload,
                "data_update": {
                    "type": "system_ai_pricing_updated",
                    "payload": payload,
                },
            }

        if tool == "read_webpage":
            url = str(params.get("url") or "").strip()
            if not url:
                return {"status": "failed", "result": "url is required"}

            if not re.match(r"^https?://", url, flags=re.IGNORECASE):
                return {"status": "failed", "result": "url must start with http:// or https://"}

            try:
                max_chars = int(params.get("max_chars") or 4000)
            except Exception:
                max_chars = 4000
            max_chars = max(500, min(12000, max_chars))

            try:
                max_pages = int(params.get("max_pages") or 1)
            except Exception:
                max_pages = 1
            max_pages = max(1, min(5, max_pages))

            pages: List[Dict[str, Any]] = []
            visited = set()
            current_url = url
            final_next_page_url = ""

            for _ in range(max_pages):
                if not current_url or current_url in visited:
                    break
                visited.add(current_url)

                try:
                    resp = await asyncio.to_thread(
                        lambda u=current_url: requests.get(
                            u,
                            timeout=25,
                            headers={
                                "User-Agent": "Mozilla/5.0 (compatible; AIStory-SystemAgent/1.0)",
                                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                            },
                        )
                    )
                except Exception as e:
                    if not pages:
                        return {"status": "failed", "result": f"read_webpage request failed: {e}"}
                    break

                if resp.status_code >= 400:
                    if not pages:
                        return {"status": "failed", "result": f"read_webpage HTTP {resp.status_code}"}
                    break

                html = str(resp.text or "")
                title_match = re.search(r"<title[^>]*>([\s\S]*?)</title>", html, flags=re.IGNORECASE)
                title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""

                cleaned = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
                cleaned = re.sub(r"<style[\s\S]*?</style>", " ", cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(r"<[^>]+>", " ", cleaned)
                cleaned = re.sub(r"\s+", " ", cleaned).strip()

                # ---------- JS-rendered SPA fallback (Jina Reader) ----------
                # If direct fetch returned very little text (< 200 chars) but
                # the raw HTML was large, the page is likely JS-rendered (SPA).
                # Fall back to Jina Reader API which renders JS and returns
                # clean Markdown/text.
                _MIN_USEFUL_TEXT_LEN = 200
                if len(cleaned) < _MIN_USEFUL_TEXT_LEN and len(html) > 2000:
                    try:
                        jina_resp = await asyncio.to_thread(
                            lambda u=current_url: requests.get(
                                f"https://r.jina.ai/{u}",
                                timeout=30,
                                headers={
                                    "Accept": "text/plain",
                                    "X-Return-Format": "text",
                                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                                },
                            )
                        )
                        if jina_resp.status_code == 200 and len(jina_resp.text.strip()) > len(cleaned):
                            cleaned = jina_resp.text.strip()
                            if not title:
                                # Try to extract title from first non-empty line
                                for _line in cleaned.split("\n"):
                                    _line = _line.strip().lstrip("# ").strip()
                                    if _line:
                                        title = _line[:120]
                                        break
                    except Exception:
                        pass  # keep whatever we got from direct fetch
                # ---------- end SPA fallback ----------

                excerpt = cleaned[:max_chars]

                next_page_url = self._extract_next_page_url(html, current_url)
                pages.append({
                    "url": current_url,
                    "title": title,
                    "excerpt": excerpt,
                    "content_length": len(cleaned),
                    "next_page_url": next_page_url,
                })

                if not next_page_url:
                    final_next_page_url = ""
                    break
                final_next_page_url = next_page_url
                current_url = next_page_url

            if not pages:
                return {"status": "failed", "result": "read_webpage returned no content"}

            first = pages[0]
            merged_excerpt = "\n\n".join(
                [
                    f"[Page {idx + 1}] {item.get('title') or item.get('url')}\n{str(item.get('excerpt') or '')}"
                    for idx, item in enumerate(pages)
                ]
            )[: max_chars * max_pages]

            result = {
                "url": first.get("url"),
                "title": first.get("title"),
                "excerpt": merged_excerpt,
                "content_length": sum(int(item.get("content_length") or 0) for item in pages),
                "pages_read": len(pages),
                "pages": pages,
                "next_page_url": final_next_page_url,
                "pricing_candidates": self._extract_pricing_candidates_from_webpage(
                    {
                        "url": first.get("url"),
                        "title": first.get("title"),
                        "excerpt": merged_excerpt,
                    },
                    str((context or {}).get("query") or ""),
                    (context or {}).get("history") if isinstance((context or {}).get("history"), list) else [],
                ),
            }
            return {
                "status": "completed",
                "result": result,
                "data_update": {
                    "type": "webpage_read_result",
                    "result": result,
                },
            }

        if tool == "analyze_model":
            query = str(params.get("query") or "").strip()
            provider_filter = params.get("provider")
            category_filter = params.get("category")
            scope = str(params.get("scope") or "auto").strip().lower()
            search_web = params.get("search_web")
            update_fields = params.get("update_fields", False) or params.get("update_modality", False)
            batch_limit = min(int(params.get("limit") or 50), 200)

            # Resolve scope
            if scope == "auto":
                if query and not provider_filter and not category_filter:
                    scope = "single"
                elif provider_filter and not query:
                    scope = "provider"
                elif category_filter and not query:
                    scope = "category"
                elif not query and not provider_filter and not category_filter:
                    scope = "all"
                else:
                    scope = "single"  # query + filters = refined single search

            is_batch = scope in ("all", "provider", "category")

            # Default search_web: true for single, false for batch
            if search_web is None:
                search_web = not is_batch

            if scope == "single" and not query:
                return {"status": "failed", "result": "query is required for single-model analysis. Use scope=all/provider/category for batch."}

            # ── 1. Gather existing DB info ──
            db_items = []
            try:
                with SessionLocal() as session:
                    q = session.query(SystemAPISetting)
                    if provider_filter:
                        q = q.filter(SystemAPISetting.provider.ilike(f"%{provider_filter}%"))
                    if category_filter:
                        q = q.filter(SystemAPISetting.category.ilike(f"%{category_filter}%"))
                    if query:
                        q = q.filter(
                            (SystemAPISetting.model.ilike(f"%{query}%"))
                            | (SystemAPISetting.name.ilike(f"%{query}%"))
                            | (SystemAPISetting.provider.ilike(f"%{query}%"))
                        )
                    rows = q.limit(batch_limit).all()
                    for r in rows:
                        cfg = r.config if isinstance(r.config, dict) else {}
                        db_items.append({
                            "id": r.id,
                            "provider": r.provider,
                            "category": r.category,
                            "model": r.model,
                            "name": r.name,
                            "modality": r.modality,
                            "tags": r.tags,
                            "unit_type": getattr(r, "billing_unit_type", None) or "per_call",
                            "is_active": r.is_active,
                        })
            except Exception as e:
                logger.warning(f"[analyze_model] DB query error: {e}")

            if not db_items:
                return {"status": "completed", "result": {"query": query, "scope": scope, "models_found": 0, "analysis": "No matching models found.", "models": []}}

            # ── 2. Web search for additional info (single/small batch only) ──
            web_info = ""
            if search_web and query:
                try:
                    search_query = f"{query} AI model capabilities features"
                    response = await asyncio.to_thread(
                        lambda: requests.get(
                            "https://api.duckduckgo.com/",
                            params={
                                "q": search_query,
                                "format": "json",
                                "no_redirect": 1,
                                "no_html": 1,
                                "skip_disambig": 1,
                            },
                            timeout=20,
                            headers={"User-Agent": "AIStory-Agent/1.0"},
                        )
                    )
                    if response.status_code == 200:
                        data = response.json()
                        parts = []
                        abstract = data.get("AbstractText") or ""
                        if abstract:
                            parts.append(f"Summary: {abstract}")
                        for item in (data.get("RelatedTopics") or [])[:8]:
                            if isinstance(item, dict) and item.get("Text"):
                                parts.append(item["Text"])
                        web_info = "\n".join(parts)
                except Exception as e:
                    logger.warning(f"[analyze_model] Web search error: {e}")

            # ── 3. Resolve LLM config ──
            if not llm_config or not llm_config.get("api_key"):
                _fallback_config = self.get_system_default_llm_config(
                    user_id=(context or {}).get("auth", {}).get("user_id"), category="LLM"
                )
                if _fallback_config and _fallback_config.get("api_key"):
                    llm_config = _fallback_config

            if not llm_config or not llm_config.get("api_key"):
                return {"status": "failed", "result": "No LLM config available for analysis"}

            # Build analysis prompt — concise for batch, detailed for single
            if is_batch:
                analysis_prompt = (
                    "You are an AI model analyst. Analyze the listed models CONCISELY.\n"
                    "Do NOT use <think> tags or internal reasoning blocks. Output the analysis directly.\n\n"
                    "For EACH model, output under a heading `### <provider>/<model>`:\n"
                    "- **Overview**: 1-2 sentences on what it does\n"
                    "- **Capabilities**: generation modes, resolution, audio, duration, formats (brief)\n"
                    "- **Pros/Cons**: 1-2 bullet points each\n"
                    "- **Modality JSON**:\n"
                    "```modality\n"
                    '{"generation_modes": [...], "max_resolution": "...", "aspect_ratios": [...], '
                    '"has_audio": false, "max_duration": null, "base_model": "...", '
                    '"model_version": "...", "model_type": "...", "input_formats": [...], "output_format": "..."}\n'
                    "```\n"
                    "- **Tags**:\n"
                    "```tags\n"
                    '["tag1", "tag2", ...]\n'
                    "```\n\n"
                    "generation_modes: t2i/i2i/t2v/i2v/v2v/t2a/a2t/a2a/s2v/i2t/t2m/t2s\n"
                    "Tags: style(写实/动漫/3D), capability(高清/快速/超分), use-case(电商/短视频), tier(旗舰/经济)\n\n"
                    "CRITICAL: The NUMBER of `modality` and `tags` blocks MUST equal the number of models.\n"
                    "Be brief and structured. Respond in the same language as the user query.\n"
                )
            else:
                analysis_prompt = (
                    "You are an AI model analyst. Analyze the following model(s) and provide a comprehensive report.\n"
                    "Do NOT use <think> tags or internal reasoning blocks. Output the analysis directly.\n\n"
                    "For EACH model, include these sections:\n"
                    "1. **Model Overview** — what the model does, its provider, and category\n"
                    "2. **Key Capabilities / Modality** — generation modes, supported resolutions, aspect ratios, "
                    "audio support, duration limits, input/output formats\n"
                    "3. **Strengths** — what it excels at\n"
                    "4. **Weaknesses / Limitations** — known shortcomings\n"
                    "5. **Recommended Use Cases** — best scenarios for this model\n"
                    "6. **Modality JSON** — output a fenced JSON block with label `modality` following this schema:\n"
                    '   ```modality\n'
                    '   {"generation_modes": ["t2i","i2i"], "max_resolution": "2048x2048", '
                    '"aspect_ratios": ["1:1","16:9"], "has_audio": false, "max_duration": null, '
                    '"base_model": "...", "model_version": "...", "model_type": "diffusion", '
                    '"input_formats": ["text","image"], "output_format": "image"}\n'
                    '   ```\n'
                    "   generation_modes abbreviations: t2i(text-to-image) i2i(image-to-image) t2v(text-to-video) "
                    "i2v(image-to-video) v2v(video-to-video) t2a(text-to-audio) a2t(speech-recognition) "
                    "a2a(audio-to-audio) s2v(speech-driven-video/digital-human) i2t(image-understanding) "
                    "t2m(text-to-music) t2s(text-to-speech)\n"
                    "7. **Tags** — output a fenced JSON array with label `tags`, listing descriptive tags for this model. "
                    "Tags should cover: style (e.g. 写实/动漫/3D), capability (e.g. 高清/快速/局部重绘/超分), "
                    "use-case (e.g. 电商/短视频/广告), quality tier (e.g. 旗舰/经济), and any other relevant labels.\n"
                    '   ```tags\n'
                    '   ["写实", "高清", "文生图", "图生图"]\n'
                    '   ```\n\n'
                    "CRITICAL: Each model MUST have its own separate `modality` and `tags` fenced blocks "
                    "under a heading like `### <provider>/<model>`. "
                    "The NUMBER of `modality` blocks and `tags` blocks MUST equal the NUMBER of models you are analyzing.\n\n"
                    "Respond in the same language as the user query.\n"
                )

            # ── 4. Call LLM — single call or chunked batch ──
            # Larger chunks for batch (fewer LLM roundtrips), smaller for single (deeper analysis)
            CHUNK_SIZE = 25 if is_batch else 10
            all_analysis_texts = []

            chunks = [db_items[i:i + CHUNK_SIZE] for i in range(0, len(db_items), CHUNK_SIZE)]
            logger.info("[analyze_model] scope=%s models=%d chunks=%d", scope, len(db_items), len(chunks))

            for chunk_idx, chunk in enumerate(chunks):
                db_context = json.dumps(chunk, ensure_ascii=False, default=str)
                chunk_label = f" (batch {chunk_idx + 1}/{len(chunks)})" if len(chunks) > 1 else ""
                user_msg = (
                    f"User query: {query or f'Batch analysis — scope={scope}'}{chunk_label}\n\n"
                    f"Database records ({len(chunk)} models):\n{db_context}\n\n"
                    f"Web search results:\n{web_info or 'No web results available.'}"
                )

                try:
                    analysis_result = await llm_service.analyze_intent_with_system_prompt(
                        user_msg, {}, [], llm_config, analysis_prompt,
                    )
                    chunk_text = analysis_result.get("reply") or analysis_result.get("content") or str(analysis_result)
                    all_analysis_texts.append(chunk_text)
                except Exception as e:
                    logger.error(f"[analyze_model] LLM analysis error (chunk {chunk_idx}): {e}")
                    all_analysis_texts.append(f"[Analysis failed for batch {chunk_idx + 1}: {e}]")

            analysis_text = "\n\n---\n\n".join(all_analysis_texts)

            # ── 5. Optionally update modality & tags ──
            modality_updated = []
            tags_updated = []
            if update_fields and db_items:
                try:
                    import re as _re
                    # Extract all modality and tags blocks from merged analysis text
                    modality_blocks = _re.findall(r'```modality\s*([\s\S]*?)```', analysis_text)
                    if not modality_blocks:
                        modality_blocks = _re.findall(r'```(?:json)?\s*(\{[^`]*"generation_modes"[^`]*\})\s*```', analysis_text, _re.DOTALL)
                    tags_blocks = _re.findall(r'```tags\s*([\s\S]*?)```', analysis_text)

                    parsed_modalities = []
                    for block in modality_blocks:
                        try:
                            parsed_modalities.append(json.loads(block.strip()))
                        except Exception:
                            pass
                    parsed_tags_list = []
                    for block in tags_blocks:
                        try:
                            t = json.loads(block.strip())
                            if isinstance(t, list):
                                parsed_tags_list.append(t)
                        except Exception:
                            pass

                    with SessionLocal() as session:
                        for idx, item in enumerate(db_items):
                            row = session.query(SystemAPISetting).filter(SystemAPISetting.id == item["id"]).first()
                            if not row:
                                continue
                            m_obj = None
                            if idx < len(parsed_modalities):
                                m_obj = parsed_modalities[idx]
                            elif len(parsed_modalities) == 1:
                                m_obj = parsed_modalities[0]
                            if m_obj and isinstance(m_obj, dict):
                                row.modality = m_obj
                                modality_updated.append(row.model)
                            t_arr = None
                            if idx < len(parsed_tags_list):
                                t_arr = parsed_tags_list[idx]
                            elif len(parsed_tags_list) == 1:
                                t_arr = parsed_tags_list[0]
                            if t_arr and isinstance(t_arr, list):
                                row.tags = t_arr
                                tags_updated.append(row.model)
                        session.commit()
                except Exception as e:
                    logger.warning(f"[analyze_model] Modality/tags update error: {e}")

            result = {
                "query": query or f"batch ({scope})",
                "scope": scope,
                "models_found": len(db_items),
                "models": [{"provider": i["provider"], "model": i["model"], "category": i["category"]} for i in db_items],
                "analysis": analysis_text,
                "web_search_used": bool(web_info),
                "modality_updated": modality_updated,
                "tags_updated": tags_updated,
                "chunks_processed": len(chunks),
            }
            return {
                "status": "completed",
                "result": result,
                "data_update": {
                    "type": "model_analysis_result",
                    "result": result,
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

                billing_details = {"item": "video_from_tool"}
                if billing_service.is_token_pricing(db, video_task_type, gen_provider, gen_model):
                    raw_resp = (gen_result.get("metadata") or {}).get("raw") or {}
                    usage = raw_resp.get("usage") or {}
                    actual_tokens = int(usage.get("total_tokens") or usage.get("output_tokens") or 0)
                    if actual_tokens <= 0:
                        vtc = billing_service.resolve_video_token_config(db, gen_provider, gen_model)
                        actual_tokens = billing_service.estimate_video_output_tokens(
                            width=vtc.get("default_width", 1280), height=vtc.get("default_height", 720),
                            fps=vtc.get("default_fps", 24), duration_seconds=5,
                            draft_token_coefficient=vtc.get("draft_token_coefficient", 1.0),
                        )
                    billing_details.update({"output_tokens": actual_tokens, "total_tokens": actual_tokens})
                billing_service.deduct_credits(db, user_id, video_task_type, gen_provider, gen_model, billing_details)

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
                
                billing_details = {"item": "i2v_from_tool"}
                if billing_service.is_token_pricing(db, video_task_type, gen_provider, gen_model):
                    raw_resp = (gen_result.get("metadata") or {}).get("raw") or {}
                    usage = raw_resp.get("usage") or {}
                    actual_tokens = int(usage.get("total_tokens") or usage.get("output_tokens") or 0)
                    if actual_tokens <= 0:
                        vtc = billing_service.resolve_video_token_config(db, gen_provider, gen_model)
                        actual_tokens = billing_service.estimate_video_output_tokens(
                            width=vtc.get("default_width", 1280), height=vtc.get("default_height", 720),
                            fps=vtc.get("default_fps", 24), duration_seconds=5,
                            draft_token_coefficient=vtc.get("draft_token_coefficient", 1.0),
                        )
                    billing_details.update({"output_tokens": actual_tokens, "total_tokens": actual_tokens})
                billing_service.deduct_credits(db, user_id, video_task_type, gen_provider, gen_model, billing_details)
                
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
                project.updated_at = now_bj_iso()
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

        elif tool == "recommend_model":
            requirement = str(params.get("requirement") or params.get("query") or "").strip()
            if not requirement:
                return {"status": "failed", "result": "requirement is required"}

            category_filter = params.get("category")
            generation_mode = params.get("generation_mode")

            # ── 1. Query available system models ──
            candidates = []
            try:
                with SessionLocal() as session:
                    q = session.query(SystemAPISetting).filter(
                        SystemAPISetting.deprecated != True,
                        ~SystemAPISetting.category.like("System_%"),
                    )
                    if category_filter:
                        q = q.filter(SystemAPISetting.category.ilike(f"%{category_filter}%"))
                    rows = q.all()
                    for r in rows:
                        # Filter by generation_mode if specified
                        if generation_mode:
                            from app.services.modality_utils import modality_matches
                            if not modality_matches(r.modality, generation_mode):
                                continue
                        r_cfg = r.config if isinstance(r.config, dict) else {}
                        candidates.append({
                            "setting_id": r.id,
                            "provider": r.provider,
                            "category": r.category,
                            "model": r.model,
                            "name": r.name,
                            "modality": r.modality,
                            "tags": r.tags,
                            "unit_type": getattr(r, "billing_unit_type", None) or "per_call",
                        })
            except Exception as e:
                logger.warning(f"[recommend_model] DB query error: {e}")
                return {"status": "failed", "result": f"Failed to query models: {e}"}

            if not candidates:
                return {
                    "status": "completed",
                    "result": {
                        "requirement": requirement,
                        "recommendations": [],
                        "message": "No matching models found in system. Please contact admin to add models.",
                    },
                }

            # ── 2. Build user's current active settings for context ──
            current_settings = []
            try:
                current_settings = self._build_user_active_settings_summary(db, user_id)
            except Exception:
                pass

            # ── 3. Call LLM to rank and recommend ──
            recommend_prompt = (
                "You are an AI model recommendation assistant. Based on the user's requirement, "
                "rank the available models and recommend the best options.\n\n"
                "For each recommended model, provide:\n"
                "1. **setting_id** — the ID to activate this model\n"
                "2. **model** — model identifier\n"
                "3. **provider** — provider name\n"
                "4. **reason** — why this model fits the user's needs\n"
                "5. **score** — 1-10 rating of fit\n\n"
                "Return a JSON object with:\n"
                '- "recommendations": [{"setting_id": ..., "model": ..., "provider": ..., '
                '"category": ..., "reason": ..., "score": ...}]\n'
                '- "summary": a brief natural-language summary of your recommendation\n\n'
                "Respond in the same language as the user requirement.\n"
                "Rank by relevance to the user's needs. Limit to top 5 recommendations.\n"
            )

            user_msg = (
                f"User requirement: {requirement}\n\n"
                f"User's current active settings:\n{json.dumps(current_settings, ensure_ascii=False, default=str)}\n\n"
                f"Available system models ({len(candidates)} total):\n"
                f"{json.dumps(candidates, ensure_ascii=False, default=str)}"
            )

            try:
                llm_result_rec = await llm_service.analyze_intent_with_system_prompt(
                    user_msg, {}, [], llm_config, recommend_prompt,
                )
                rec_text = llm_result_rec.get("reply") or llm_result_rec.get("content") or str(llm_result_rec)
            except Exception as e:
                logger.error(f"[recommend_model] LLM error: {e}")
                # Fallback: return raw candidates without LLM ranking
                rec_text = None

            # ── 4. Parse LLM recommendations or return raw candidates ──
            recommendations = []
            summary = ""
            if rec_text:
                try:
                    # Try to extract JSON from LLM response
                    import re as _re
                    json_match = _re.search(r'\{[\s\S]*"recommendations"[\s\S]*\}', rec_text)
                    if json_match:
                        parsed = json.loads(json_match.group(0))
                        recommendations = parsed.get("recommendations") or []
                        summary = parsed.get("summary") or ""
                except Exception:
                    summary = rec_text

            if not recommendations:
                # Fallback: return top candidates as-is
                recommendations = [
                    {
                        "setting_id": c["setting_id"],
                        "model": c["model"],
                        "provider": c["provider"],
                        "category": c["category"],
                        "reason": ", ".join(c["tags"]) if c.get("tags") else c.get("name") or "",
                        "score": 5,
                    }
                    for c in candidates[:5]
                ]
                if not summary:
                    summary = f"Found {len(candidates)} available models. Here are the top candidates."

            result = {
                "requirement": requirement,
                "recommendations": recommendations[:5],
                "summary": summary,
                "total_candidates": len(candidates),
            }
            return {
                "status": "completed",
                "result": result,
                "data_update": {
                    "type": "model_recommendation_result",
                    "result": result,
                },
            }

        elif tool == "activate_model":
            setting_id = params.get("setting_id")
            if not setting_id:
                return {"status": "failed", "result": "setting_id is required"}

            try:
                setting_id = int(setting_id)
            except (ValueError, TypeError):
                return {"status": "failed", "result": "setting_id must be a valid integer"}

            try:
                with SessionLocal() as session:
                    system_setting = session.query(SystemAPISetting).filter(
                        SystemAPISetting.id == setting_id,
                    ).first()
                    if not system_setting:
                        return {"status": "failed", "result": f"System API setting {setting_id} not found"}

                    if system_setting.deprecated:
                        return {"status": "failed", "result": f"Model {system_setting.model} is deprecated and cannot be activated"}

                    if not system_setting.is_active:
                        return {"status": "failed", "result": f"Model {system_setting.model} is not enabled by admin"}

                    # Deactivate all current user settings in same category
                    session.query(APISetting).filter(
                        APISetting.user_id == user_id,
                        APISetting.category == system_setting.category,
                        APISetting.is_active == True,
                    ).update({"is_active": False})

                    # Find or create user setting
                    user_setting = session.query(APISetting).filter(
                        APISetting.user_id == user_id,
                        APISetting.provider == system_setting.provider,
                        APISetting.category == system_setting.category,
                        APISetting.model == system_setting.model,
                    ).first()

                    marker_config = dict(system_setting.config or {})
                    marker_config["selection_source"] = "agent_recommendation"

                    if user_setting:
                        user_setting.name = user_setting.name or f"Use System {system_setting.provider}"
                        user_setting.base_url = system_setting.base_url
                        user_setting.model = system_setting.model
                        user_setting.config = marker_config
                        user_setting.is_active = True
                        user_setting.api_key = ""
                    else:
                        user_setting = APISetting(
                            user_id=user_id,
                            name=f"Use System {system_setting.provider}",
                            category=system_setting.category,
                            provider=system_setting.provider,
                            api_key="",
                            base_url=system_setting.base_url,
                            model=system_setting.model,
                            config=marker_config,
                            is_active=True,
                        )
                        session.add(user_setting)

                    session.commit()

                    result = {
                        "activated": True,
                        "category": system_setting.category,
                        "provider": system_setting.provider,
                        "model": system_setting.model,
                        "name": system_setting.name,
                        "setting_id": setting_id,
                    }
                    return {
                        "status": "completed",
                        "result": result,
                        "data_update": {
                            "type": "model_activated",
                            "result": result,
                        },
                    }
            except Exception as e:
                logger.error(f"[activate_model] Error: {e}")
                return {"status": "failed", "result": f"Failed to activate model: {e}"}

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
