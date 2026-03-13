

import requests
import httpx
import json
import asyncio
import time
from typing import Dict, Any, List, Optional, AsyncGenerator, Tuple
import logging
import os
import re
from pathlib import Path
from logging.handlers import RotatingFileHandler

from app.core.config import settings
from app.core.prompts.skills_loader import get_skill_prompt_text

logger = logging.getLogger(__name__)

_llm_call_logger = logging.getLogger("llm_call_audit")
if not _llm_call_logger.handlers:
    try:
        log_dir = Path(settings.BASE_DIR) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "llm_calls.log"
        max_bytes = int(os.getenv("LLM_CALL_LOG_MAX_BYTES", str(20 * 1024 * 1024)))
        backup_count = int(os.getenv("LLM_CALL_LOG_BACKUP_COUNT", "5"))
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s'))
        _llm_call_logger.addHandler(file_handler)
        _llm_call_logger.setLevel(logging.INFO)
        _llm_call_logger.propagate = False
    except Exception as e:
        logger.warning(f"Failed to initialize llm_call_audit logger: {e}")

# Some providers (e.g., Ark/Doubao) can take several minutes for large prompts.
# Default timeout set to 300s, with env override support.
DEFAULT_LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "300"))
DEFAULT_LLM_CONNECT_TIMEOUT_SECONDS = int(os.getenv("LLM_CONNECT_TIMEOUT_SECONDS", "15"))
DEFAULT_LLM_NO_PROXY_CONNECT_TIMEOUT_SECONDS = int(os.getenv("LLM_NO_PROXY_CONNECT_TIMEOUT_SECONDS", "10"))

_BASE64_PATTERN = re.compile(r'(data:[\w/+.-]+;base64,)[A-Za-z0-9+/=]{64,}')

def _strip_base64_from_log(obj):
    """Recursively strip base64 content from data structures before logging."""
    if isinstance(obj, str):
        if obj.startswith("data:") and ";base64," in obj[:64]:
            prefix = obj[:obj.index(";base64,") + 8]
            return f"{prefix}<BASE64_STRIPPED len={len(obj)}>"
        if len(obj) > 500 and _BASE64_PATTERN.search(obj[:500]):
            return _BASE64_PATTERN.sub(r'\1<BASE64_STRIPPED>', obj)
        return obj
    if isinstance(obj, dict):
        return {k: _strip_base64_from_log(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_strip_base64_from_log(item) for item in obj]
    return obj

def _debug_log(msg, level="info"):
    """Print to console and write to logger."""
    print(msg)
    getattr(logger, level, logger.info)(msg)


def _safe_json_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}

# ---------------------------------------------------------------------------
# Token-aware history trimming
# ---------------------------------------------------------------------------
# Rough chars-per-token ratio (conservative; works for CJK & English mixed text).
_CHARS_PER_TOKEN = 3
_DEFAULT_HISTORY_TOKEN_BUDGET = 6000   # tokens reserved for history messages
_MIN_HISTORY_MESSAGES = 2             # always keep at least last 2 messages
_MAX_HISTORY_MESSAGES = 20            # hard upper bound

def _estimate_tokens(text: str) -> int:
    """Fast approximate token count."""
    return max(1, len(text) // _CHARS_PER_TOKEN)

def _trim_history_by_token_budget(
    history: List[Dict[str, str]],
    budget: int = _DEFAULT_HISTORY_TOKEN_BUDGET,
) -> List[Dict[str, str]]:
    """
    Select the most recent history messages that fit within *budget* tokens.
    Always keeps at least _MIN_HISTORY_MESSAGES (even if over budget) and
    never more than _MAX_HISTORY_MESSAGES.
    """
    if not history:
        return []
    # Take at most _MAX_HISTORY_MESSAGES from the tail
    candidates = list(history[-_MAX_HISTORY_MESSAGES:])
    # Walk backwards, accumulating tokens
    selected: list = []
    used = 0
    for msg in reversed(candidates):
        cost = _estimate_tokens(msg.get("content", ""))
        if used + cost > budget and len(selected) >= _MIN_HISTORY_MESSAGES:
            break
        selected.append(msg)
        used += cost
    selected.reverse()
    return selected

_DEFAULT_AGENT_SYSTEM_PROMPT = """
You are an AI assistant for a Storyboard Editor application.
Your goal is to help the user edit, create, and manage storyboard projects.

Always do reasoning/scheduling with the system default LLM config provided by backend.
You must only call tools listed below and should prefer read-first, then write.
Respect permissions: if project context is missing or user appears unauthorized for a tool, ask for confirmation/context instead of writing.

You have access to the following tools:
1. `generate_project_asset`
   - Use this to generate images or videos.
   - Parameters:
     - `prompt`: (string) Description of the image/video.
     - `target_type`: (string) "shot" or "character".
     - `target_id`: (string, optional) ID of the shot/character if modifying an existing one.

2. `analyze_script`
   - Use this to analyze a script text.
   - Parameters:
     - `text`: (string) The script content.

3. `update_project_metadata`
   - Use this to change project title vs description.
   - Parameters:
     - `title`: (string, optional)
     - `description`: (string, optional)

4. `search_project_data`
     - Use this to search entities/scenes/shots in the current project.
     - Parameters:
         - `query`: (string) keyword to search.
         - `limit`: (integer, optional, default 10, max 20)

5. `internet_search`
     - Use this for basic web search when project data is insufficient.
     - Parameters:
         - `query`: (string)

6. `visualize_user_requirement`
     - Use this to structure user requirements into a visualizable task list.
     - Parameters:
         - `objective`: (string)
         - `tasks`: (array of strings, optional)

7. `recommend_model`
     - Use this when the user describes requirements for a model (e.g. "I need a fast video model", "推荐一个高清图片模型", "哪个模型适合生成动漫风格").
     - Searches available system API models by category, modality, and tags, then uses LLM to rank and recommend.
     - Parameters:
         - `requirement`: (string, required) User's description of what they need.
         - `category`: (string, optional) Filter by category: LLM / Image / Video / Voice / Music.
         - `generation_mode`: (string, optional) Filter by generation mode: t2i / i2i / t2v / i2v / v2v / t2a / a2t / t2m / t2s.
     - Returns a ranked list of recommended models with reasons. Each recommendation includes a `setting_id` for activation.

8. `activate_model`
     - Use this to activate a recommended system API model for the user.
     - MUST only be called after user explicitly confirms a recommendation from `recommend_model`.
     - Parameters:
         - `setting_id`: (integer, required) The system API setting ID to activate.
     - This replaces the user's current active model in the same category.

CONTEXT DATA:
The `Current Project Context` system message contains a field `my_active_api_settings` — an array of the user's currently activated API settings across all categories (LLM, Image, Video, etc.).
Each item includes: category, provider, model, name, and api_pricing (unit_type, cost, cost_input, cost_output in platform credits where 1 credit = CNY 0.01).
When the user asks about their current models, API settings, or pricing, answer directly from this context data — no tool call is needed.
When the user asks to recommend, switch, or change models, use `recommend_model` first, then `activate_model` after user confirmation.

RESPONSE FORMAT:
You must respond with a JSON object. Do not include markdown formatting (like ```json).
The JSON object must have exactly these keys:
- `reply`: (string) A conversational response to the user explaining what you are doing.
- `plan`: (array) A list of tool calls to execute.

Example Response:
{
    "reply": "I'll generate a cinematic shot of a rainy street.",
    "plan": [
        {
            "tool": "generate_project_asset",
            "parameters": {
                "prompt": "Cinematic wide angle shot of rainy street at night, cyberpunk style",
                "target_type": "shot"
            }
        }
    ]
}

If the user's request is not clear or does not require a tool, return an empty plan.
"""

class LLMService:
    def _get_agent_system_prompt(self) -> str:
        try:
            resolved = get_skill_prompt_text("agent_orchestrator", "system_prompt.txt")
            if isinstance(resolved, str) and resolved.strip():
                return resolved
        except Exception as e:
            logger.warning("Failed to load agent skill prompt, fallback to default: %s", e)
        return _DEFAULT_AGENT_SYSTEM_PROMPT

    def _vendor_label(self, provider: Any) -> str:
        raw = str(provider or "").strip()
        return raw or "unknown"

    def _vendor_failed_message(self, provider: Any, reason: Any) -> str:
        vendor = self._vendor_label(provider)
        detail = str(reason or "unknown error").strip()
        if "供应商调用失败" in detail:
            return detail
        return f"{vendor}供应商调用失败: {detail}"

    def _safe_log_json(self, tag: str, payload: Dict[str, Any]) -> None:
        try:
            cleaned = _strip_base64_from_log(payload)
            _llm_call_logger.info("%s %s", tag, json.dumps(cleaned, ensure_ascii=False, default=str))
        except Exception as e:
            logger.warning(f"Failed to write llm call audit log ({tag}): {e}")

    def log_audit(self, tag: str, payload: Dict[str, Any]) -> None:
        self._safe_log_json(tag, payload)

    def _normalize_grsai_llm_base_url(self, base_url: str) -> str:
        url = (base_url or "").strip()
        if not url:
            return url

        normalized = url.replace("grsaiapi.com", "grsai.dakka.com.cn")
        normalized = normalized.rstrip("/")

        # Preserve explicit endpoint if already configured.
        if normalized.endswith("/chat/completions"):
            return normalized

        if normalized.endswith("/v1"):
            return normalized

        return f"{normalized}/v1"

    def _infer_provider(self, base_url: str, model: str = "") -> str:
        url = (base_url or "").lower()
        model_lower = (model or "").lower()
        if "kie.ai" in url or model_lower.startswith("gemini-2.5"):
            return "kie"
        if "ark.cn-" in url or "doubao" in model_lower:
            return "doubao"
        if "openai" in url:
            return "openai"
        if "anthropic" in url:
            return "anthropic"
        if "grsai" in url:
            return "grsai"
        if "volces" in url:
            return "volcengine"
        if "localhost" in url or "127.0.0.1" in url:
            return "local"
        return "unknown"

    def sanitize_text_output(self, text: str) -> str:
        if not isinstance(text, str) or not text:
            return text

        cleaned = text
        # Strip closed <think>...</think> blocks
        cleaned = re.sub(r"<think\b[^>]*>[\s\S]*?</think>", "", cleaned, flags=re.IGNORECASE)
        # Strip orphan </think> tags
        cleaned = re.sub(r"</think>", "", cleaned, flags=re.IGNORECASE)
        # Strip unclosed <think> blocks — consume content up to JSON ({) or markdown (```) boundary, or end of string
        cleaned = re.sub(r"<think\b[^>]*>(?:(?!\{|```)[\s\S])*", "", cleaned, flags=re.IGNORECASE)

        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def _sanitize_response_content(self, content: Any) -> Any:
        if isinstance(content, str):
            return self.sanitize_text_output(content)
        if isinstance(content, list):
            normalized = []
            for item in content:
                if isinstance(item, dict):
                    updated = dict(item)
                    if isinstance(updated.get("text"), str):
                        updated["text"] = self.sanitize_text_output(updated.get("text"))
                    normalized.append(updated)
                else:
                    normalized.append(item)
            return normalized
        return content

    def _extract_text_from_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            chunks: List[str] = []
            for item in content:
                item_text = self._extract_text_from_content(item)
                if isinstance(item_text, str) and item_text.strip():
                    chunks.append(item_text)
            return "\n".join(chunks).strip()

        if isinstance(content, dict):
            direct_text_candidates: List[str] = []
            for key in ["text", "output_text", "value", "content", "parts", "delta"]:
                value = content.get(key)
                extracted = self._extract_text_from_content(value)
                if isinstance(extracted, str) and extracted.strip():
                    direct_text_candidates.append(extracted)

            if direct_text_candidates:
                return "\n".join(direct_text_candidates).strip()

            nested_chunks: List[str] = []
            for value in content.values():
                extracted = self._extract_text_from_content(value)
                if isinstance(extracted, str) and extracted.strip():
                    nested_chunks.append(extracted)
            return "\n".join(nested_chunks).strip()

        return ""

    def _extract_text_from_kie_result(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return ""
            if raw.startswith("{") or raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    return self._extract_text_from_kie_result(parsed)
                except Exception:
                    return raw
            return raw
        if isinstance(value, list):
            chunks = [self._extract_text_from_kie_result(item) for item in value]
            return "\n".join([chunk for chunk in chunks if chunk]).strip()
        if isinstance(value, dict):
            direct_keys = [
                "text", "content", "output", "response", "answer", "message", "result", "resultText", "result_text"
            ]
            for key in direct_keys:
                if key in value:
                    text = self._extract_text_from_kie_result(value.get(key))
                    if text:
                        return text
            chunks = []
            for nested in value.values():
                text = self._extract_text_from_kie_result(nested)
                if text:
                    chunks.append(text)
            return "\n".join(chunks).strip()
        return str(value)

    def _estimate_tokens_rough_from_text(self, text: Any) -> int:
        raw = str(text or "")
        if not raw:
            return 0
        # Keep a conservative upper-bound style estimate for mixed CJK/EN payloads.
        char_est = int(len(raw) / 1.2)
        byte_est = int(len(raw.encode("utf-8", errors="ignore")) / 3.2)
        return max(1, char_est, byte_est)

    def _estimate_prompt_tokens_rough_from_messages(self, messages: List[Dict[str, Any]]) -> int:
        try:
            # Include structural overhead so estimate is not underestimated.
            serialized = json.dumps(messages or [], ensure_ascii=False, separators=(",", ":"))
        except Exception:
            serialized = str(messages or "")
        return self._estimate_tokens_rough_from_text(serialized)

    def _normalize_kie_usage(self, usage: Any, messages: List[Dict[str, Any]], output_text: str) -> Dict[str, Any]:
        normalized = dict(usage or {}) if isinstance(usage, dict) else {}

        def _to_int(v: Any) -> int:
            try:
                return max(0, int(v))
            except Exception:
                return 0

        provider_prompt = _to_int(normalized.get("prompt_tokens"))
        provider_completion = _to_int(normalized.get("completion_tokens"))

        est_prompt = self._estimate_prompt_tokens_rough_from_messages(messages)
        est_completion = self._estimate_tokens_rough_from_text(output_text)

        prompt_suspicious = provider_prompt > 0 and est_prompt >= 1000 and provider_prompt < int(est_prompt * 0.35)
        completion_suspicious = (
            (provider_completion == 0 and est_completion >= 50)
            or (provider_completion > 0 and est_completion >= 200 and provider_completion < int(est_completion * 0.35))
        )

        usage_normalized = False
        if prompt_suspicious:
            normalized["provider_prompt_tokens_raw"] = provider_prompt
            normalized["prompt_tokens"] = max(provider_prompt, int(est_prompt * 0.8))
            usage_normalized = True

        if completion_suspicious:
            normalized["provider_completion_tokens_raw"] = provider_completion
            normalized["completion_tokens"] = max(provider_completion, int(est_completion * 0.8))
            usage_normalized = True

        prompt_tokens = _to_int(normalized.get("prompt_tokens"))
        completion_tokens = _to_int(normalized.get("completion_tokens"))
        normalized["total_tokens"] = max(_to_int(normalized.get("total_tokens")), prompt_tokens + completion_tokens)

        # Keep cross-provider keys aligned for downstream billing.
        normalized.setdefault("input_tokens", prompt_tokens)
        normalized.setdefault("output_tokens", completion_tokens)

        normalized["prompt_tokens_estimated_local"] = est_prompt
        normalized["completion_tokens_estimated_local"] = est_completion
        normalized["usage_normalized_by_local_estimate"] = usage_normalized
        return normalized

    async def _raw_kie_llm_request_full(self, base_url: str, api_key: str, model: str, messages: List[Dict], extra_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """KIE LLM — OpenAI-compatible chat/completions with model in URL path."""
        cfg = dict(extra_config or {})

        root, resolved_model, url = self._resolve_kie_llm_url(base_url, model)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": resolved_model,
            "messages": messages,
            "stream": False,
        }

        # KIE LLM: only forward known-safe chat/completions keys.
        payload.update(self._extract_kie_chat_options(cfg))

        cap_source = "provider_default"
        if any(
            payload.get(k) not in (None, "", 0)
            for k in ("max_tokens", "max_completion_tokens", "max_output_tokens")
        ):
            cap_source = "user_configured"

        prompt_chars = sum(len(str(m.get("content", ""))) for m in (messages or []))
        _debug_log(
            "[DEBUG][LLM][KIE] Request | "
            f"provider=kie model={resolved_model} url={url} messages={len(messages or [])} "
            f"prompt_chars={prompt_chars} max_tokens={payload.get('max_tokens')} "
            f"max_completion_tokens={payload.get('max_completion_tokens')} "
            f"max_output_tokens={payload.get('max_output_tokens')} "
            f"cap_source={cap_source} "
            f"has_tools={bool(payload.get('tools'))} has_response_format={bool(payload.get('response_format'))} "
            f"include_thoughts={payload.get('include_thoughts')}"
        )

        timeout = max(90, DEFAULT_LLM_TIMEOUT_SECONDS)

        def _do_post():
            return requests.post(url, json=payload, headers=headers, timeout=timeout)

        resp = await asyncio.to_thread(_do_post)
        _debug_log(
            f"[DEBUG][LLM][KIE] Response | status={resp.status_code} body_preview_len=800 body_preview={_strip_base64_from_log(resp.text[:800])}"
        )

        if resp.status_code != 200:
            raise Exception(f"KIE chat/completions failed {resp.status_code}: {resp.text[:500]}")

        data = resp.json()

        # KIE may return HTTP 200 with an error payload like {"code":500,"msg":"..."}
        kie_code = data.get("code")
        if kie_code is not None and str(kie_code) != "200" and "choices" not in data:
            err_msg = data.get("msg") or data.get("message") or data.get("error") or str(data)
            raise Exception(f"KIE chat/completions error code={kie_code}: {err_msg}")

        # KIE usage occasionally under-reports token counts for large prompts.
        # Normalize with local rough estimates to keep diagnostics/billing consistent.
        try:
            extracted_text = self._extract_text_from_response(data)
            normalized_usage = self._normalize_kie_usage(data.get("usage", {}), messages, extracted_text)
            data["usage"] = normalized_usage
            if normalized_usage.get("usage_normalized_by_local_estimate"):
                logger.warning(
                    "[KIE usage normalized] model=%s prompt_raw=%s completion_raw=%s prompt_est=%s completion_est=%s prompt_used=%s completion_used=%s",
                    resolved_model,
                    normalized_usage.get("provider_prompt_tokens_raw", normalized_usage.get("prompt_tokens")),
                    normalized_usage.get("provider_completion_tokens_raw", normalized_usage.get("completion_tokens")),
                    normalized_usage.get("prompt_tokens_estimated_local"),
                    normalized_usage.get("completion_tokens_estimated_local"),
                    normalized_usage.get("prompt_tokens"),
                    normalized_usage.get("completion_tokens"),
                )
        except Exception:
            pass

        # Standard OpenAI-compatible response — return as-is
        _debug_log(f"[DEBUG][LLM][KIE] Done | model={resolved_model} usage={data.get('usage', {})}")
        return data

    def _extract_kie_chat_options(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Whitelist and normalize KIE chat/completions options.

        KIE system setting configs may include non-chat keys (endpoint/query/credits/etc.).
        Passing those through can lead to provider-specific undefined behavior.
        """
        safe_cfg = dict(cfg or {})
        allowed_keys = {
            "temperature",
            "max_tokens",
            "max_completion_tokens",
            "max_output_tokens",
            "top_p",
            "presence_penalty",
            "frequency_penalty",
            "n",
            "tools",
            "tool_choice",
            "response_format",
            "include_thoughts",
            "reasoning_effort",
            "stop",
            "seed",
        }

        out: Dict[str, Any] = {}
        for key, value in safe_cfg.items():
            if str(key).startswith("__"):
                continue
            if key in {"model", "messages", "stream"}:
                continue
            if key in allowed_keys:
                out[key] = value

        return out

    def _resolve_kie_llm_url(self, base_url: str, model: str) -> Tuple[str, str, str]:
        """Normalize KIE root URL and produce model-in-path chat/completions endpoint."""
        root = (base_url or "https://api.kie.ai").strip().rstrip("/")

        # If a full endpoint was saved (including model path), collapse back to provider root.
        root = re.sub(r"/[^/]+/v1/chat/completions/?$", "", root, flags=re.IGNORECASE)

        # Strip other legacy fragments if present.
        for suffix in ("/api/v1/jobs", "/v1/chat/completions", "/v1"):
            if root.endswith(suffix):
                root = root[: -len(suffix)].rstrip("/")

        # KIE uses hyphens in version numbers, not dots (e.g. claude-opus-4-5, not claude-opus-4.5)
        kie_llm_alias = {
            "claude-opus-4.5": "claude-opus-4-5",
            "claude-sonnet-4.5": "claude-sonnet-4-5",
        }
        resolved_model = kie_llm_alias.get(model, model)
        if resolved_model != model:
            logger.info("KIE LLM model remapped | from=%s to=%s", model, resolved_model)

        url = f"{root}/{resolved_model}/v1/chat/completions"
        return root, resolved_model, url

    def _extract_finish_reason_from_response(self, full_response: Dict[str, Any]) -> Any:
        choices = full_response.get("choices") or []
        if not isinstance(choices, list):
            return None

        for choice in choices:
            if not isinstance(choice, dict):
                continue
            reason = choice.get("finish_reason")
            if reason is not None and str(reason).strip() != "":
                return reason
        return None

    def _build_extraction_diagnostics(self, full_response: Dict[str, Any]) -> Dict[str, Any]:
        choices = full_response.get("choices") or []
        if not isinstance(choices, list):
            choices = []

        combined_text = self._extract_text_from_response(full_response)
        choice_items: List[Dict[str, Any]] = []

        for idx, choice in enumerate(choices):
            if not isinstance(choice, dict):
                choice_items.append({
                    "index": idx,
                    "type": type(choice).__name__,
                    "selected_source": "invalid_choice",
                    "selected_chars": 0,
                })
                continue

            finish_reason = choice.get("finish_reason")
            message = choice.get("message") if isinstance(choice.get("message"), dict) else {}

            content_text = self._extract_text_from_content(message.get("content")) if message else ""
            reasoning_text = self._extract_text_from_content(message.get("reasoning_content")) if message else ""

            refusal_val = message.get("refusal") if message else None
            refusal_text = refusal_val if isinstance(refusal_val, str) else ""

            choice_text = self._extract_text_from_content(choice.get("text"))

            selected_source = "none"
            selected_text = ""
            if content_text:
                selected_source = "message.content"
                selected_text = content_text
            elif reasoning_text:
                selected_source = "message.reasoning_content"
                selected_text = reasoning_text
            elif refusal_text:
                selected_source = "message.refusal"
                selected_text = refusal_text
            elif choice_text:
                selected_source = "choice.text"
                selected_text = choice_text

            choice_items.append({
                "index": idx,
                "finish_reason": finish_reason,
                "selected_source": selected_source,
                "selected_chars": len(selected_text or ""),
                "message_content_chars": len(content_text or ""),
                "message_reasoning_chars": len(reasoning_text or ""),
                "message_refusal_chars": len(refusal_text or ""),
                "choice_text_chars": len(choice_text or ""),
            })

        return {
            "choices_count": len(choices),
            "combined_output_chars": len(combined_text or ""),
            "choices": choice_items,
        }

    def _extract_text_from_response(self, full_response: Dict[str, Any]) -> str:
        choices = full_response.get("choices") or []
        if isinstance(choices, list):
            all_choice_chunks: List[str] = []
            for choice in choices:
                if not isinstance(choice, dict):
                    continue

                message = choice.get("message") or {}
                if isinstance(message, dict):
                    text = self._extract_text_from_content(message.get("content"))
                    if text:
                        all_choice_chunks.append(text)
                        continue

                    reasoning_text = self._extract_text_from_content(message.get("reasoning_content"))
                    if reasoning_text:
                        all_choice_chunks.append(reasoning_text)
                        continue

                    refusal = message.get("refusal")
                    if isinstance(refusal, str) and refusal.strip():
                        all_choice_chunks.append(refusal)
                        continue

                choice_text = self._extract_text_from_content(choice.get("text"))
                if choice_text:
                    all_choice_chunks.append(choice_text)

            if all_choice_chunks:
                return "\n".join(all_choice_chunks).strip()

        for key in ["output_text", "content", "text", "response"]:
            extracted = self._extract_text_from_content(full_response.get(key))
            if extracted:
                return extracted

        return ""

    def _is_length_limited_finish_reason(self, reason: Any) -> bool:
        r = str(reason or "").strip().lower().replace("-", "_")
        return r in {
            "length",
            "max_tokens",
            "max_token",
            "max_output_tokens",
            "output_token_limit",
            "token_limit",
        }

    def _extract_provider_limit_hints(self, response_data: Dict[str, Any], response_headers: Any) -> List[str]:
        hints: List[str] = []
        data = response_data if isinstance(response_data, dict) else {}

        # Body-level common fields from various OpenAI-compatible gateways
        for key in ["max_output_tokens", "max_tokens", "max_completion_tokens", "context_window", "context_length"]:
            value = data.get(key)
            if value is not None:
                hints.append(f"body.{key}={value}")

        # Header-level hints (case-insensitive in requests headers)
        header_keys = [
            "x-ratelimit-limit-tokens",
            "x-ratelimit-remaining-tokens",
            "x-ratelimit-limit-requests",
            "x-ratelimit-remaining-requests",
            "x-ratelimit-limit-output-tokens",
            "x-ratelimit-remaining-output-tokens",
        ]
        try:
            for key in header_keys:
                value = response_headers.get(key)
                if value is not None:
                    hints.append(f"header.{key}={value}")
        except Exception:
            pass

        deduped: List[str] = []
        seen = set()
        for item in hints:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            deduped.append(text)
        return deduped

    def _is_prohibited_marker(self, text: str) -> bool:
        if not isinstance(text, str):
            return False
        normalized = text.strip().upper().lstrip("=").strip()
        return normalized == "PROHIBITED_CONTENT"

    def _has_content_filter_block(self, content_filter_results: Any) -> bool:
        if not isinstance(content_filter_results, dict):
            return False
        for value in content_filter_results.values():
            if not isinstance(value, dict):
                continue
            if value.get("filtered") is True:
                return True
        return False

    def _is_blocked_response(self, full_response: Dict[str, Any]) -> bool:
        if not isinstance(full_response, dict):
            return False

        choices = full_response.get("choices") or []
        if not isinstance(choices, list):
            return False

        for choice in choices:
            if not isinstance(choice, dict):
                continue

            finish_reason = str(choice.get("finish_reason") or "").strip().lower()
            if finish_reason in {"content_filter", "safety", "blocked"}:
                return True

            if self._has_content_filter_block(choice.get("content_filter_results")):
                return True

            message = choice.get("message")
            if isinstance(message, dict):
                content_text = self._extract_text_from_content(message.get("content"))
                if self._is_prohibited_marker(content_text):
                    return True

                refusal_text = message.get("refusal")
                if self._is_prohibited_marker(refusal_text):
                    return True

            choice_text = choice.get("text")
            if self._is_prohibited_marker(choice_text):
                return True

        extracted_text = self._extract_text_from_response(full_response)
        return self._is_prohibited_marker(extracted_text)

    async def analyze_multimodal(self, prompt: str, image_url: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyzes an image with a prompt using multimodal LLM capabilities.
        Returns Dict with 'content' and 'usage'.
        Supports:
        1. Doubao/Ark format (if 'doubao' in model name or 'responses' endpoint used)
        2. Standard OpenAI Vision format (fallback)
        """
        if not config:
            return {"content": "Error: No LLM configuration found.", "usage": {}}

        api_key = config.get("api_key")
        base_url = config.get("base_url")
        model = config.get("model")

        if not api_key:
             return {"content": "Error: Please configure your LLM API Key in Settings.", "usage": {}}

        # Detect Doubao / Ark specific mode based on user instruction
        is_doubao = "doubao" in (model or "").lower() or "ark.cn-" in (base_url or "").lower()

        if is_doubao:
            return await self._call_doubao_prop(base_url, api_key, model, prompt, image_url)
        else:
            return await self._call_openai_vision(base_url, api_key, model, prompt, image_url)

    async def _call_doubao_prop(self, base_url: str, api_key: str, model: str, prompt: str, image_url: str) -> Dict[str, Any]:
        """
        Specific implementation for Doubao/Ark /api/v3/responses endpoint
        Structure:
        {
            "model": "...",
            "input": [ { "role": "user", "content": [ { "type": "input_image", ... }, { "type": "input_text", ... } ] } ]
        }
        """
        # Construct specific Doubao URL
        # base_url usually: https://ark.cn-beijing.volces.com/api/v3
        url = base_url.rstrip("/")
        if url.endswith("/chat/completions"):
            url = url.replace("/chat/completions", "/responses")
        elif not url.endswith("/responses"):
             url = f"{url}/responses"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_image",
                            "image_url": image_url
                        },
                        {
                            "type": "input_text",
                            "text": prompt
                        }
                    ]
                }
            ]
        }
        
        _debug_log(f"[DEBUG][LLM][Doubao] Request | provider=doubao model={model} url={url} prompt_len={len(prompt)} has_image={bool(image_url)}")

        def _request():
            return requests.post(url, headers=headers, json=payload, timeout=DEFAULT_LLM_TIMEOUT_SECONDS)

        try:
            response = await asyncio.to_thread(_request)
            _debug_log(f"[DEBUG][LLM][Doubao] Response | status={response.status_code} body={_strip_base64_from_log(response.text[:500])}")
            
            if response.status_code != 200:
                 # Try fallback to standard OpenAI format if 404/400, in case it's a standard model
                 logger.warning(f"Doubao proprietary call failed: {response.text}. Attempting OpenAI standard format...")
                 return await self._call_openai_vision(base_url, api_key, model, prompt, image_url)
                 
            data = response.json()
            # Doubao responses format might differ?
            # Usually Ark /responses returns similar to /chat/completions but 'choices' key exists
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                content = self._sanitize_response_content(content)
                usage = data.get("usage", {})
                return {"content": content, "usage": usage}
            else:
                 return {"content": f"Error: Unexpected response format from Doubao: {data}", "usage": {}}
                 
        except Exception as e:
            logger.error(f"Doubao Multimodal failed: {e}")
            return {"content": f"Error: {e}", "usage": {}}

    async def _call_openai_vision(self, base_url: str, api_key: str, model: str, prompt: str, image_url: str) -> Dict[str, Any]:
        """Standard OpenAI Vision Format"""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text", 
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }
                ]
            }
        ]
        
        # Reuse existing raw request logic but we need to ensure it processes the list content correctly
        # The existing _raw_llm_request takes `messages` list and sends it as JSON.
        # So it should simply work if we call it.
        try:
             # Use _raw_llm_request_full to get usage
             full_response = await self._raw_llm_request_full(base_url, api_key, model, messages)
             content = full_response["choices"][0]["message"]["content"]
             usage = full_response.get("usage", {})
             return {"content": content, "usage": usage}
        except Exception as e:
             logger.error(f"OpenAI Vision call failed: {e}")
             return {"content": f"Error: {e}", "usage": {}}

    async def _call_intent_with_failover(
        self,
        messages: List[Dict[str, Any]],
        config: Dict[str, Any],
        extra_config: Optional[Dict[str, Any]] = None,
        *,
        category: str = "LLM",
        modality: Optional[str] = None,
    ) -> Dict[str, Any]:
        base_attempt_cfg = dict(config or {})
        attempts: List[Dict[str, Any]] = [base_attempt_cfg]
        active_cfg_obj = _safe_json_dict((base_attempt_cfg.get("config") or {}))
        active_setting_id = active_cfg_obj.get("__resolved_setting_id")
        resolved_user_id = active_cfg_obj.get("__resolved_user_id")

        if resolved_user_id:
            try:
                from app.services.agent_service import agent_service
                fallback_candidates = agent_service.get_fallback_configs(
                    int(resolved_user_id),
                    category=category,
                    exclude_setting_id=int(active_setting_id) if str(active_setting_id or "").isdigit() else None,
                    modality=modality,
                    limit=3,
                )
                if isinstance(fallback_candidates, list) and fallback_candidates:
                    attempts.extend([item for item in fallback_candidates if isinstance(item, dict)])
            except Exception as exc:
                logger.warning("[llm_fallback] failed loading fallback configs: %s", exc)

        last_error: Optional[Exception] = None
        total_attempts = len(attempts)

        for idx, attempt_cfg in enumerate(attempts, start=1):
            attempt_provider = attempt_cfg.get("provider") or self._infer_provider(attempt_cfg.get("base_url"), attempt_cfg.get("model"))
            attempt_base_url = attempt_cfg.get("base_url")
            attempt_model = attempt_cfg.get("model")
            attempt_api_key = attempt_cfg.get("api_key")

            if not str(attempt_api_key or "").strip():
                last_error = Exception(self._vendor_failed_message(attempt_provider, "missing api_key"))
                continue

            runtime_extra = dict(_safe_json_dict(attempt_cfg.get("config") or {}))
            for k, v in dict(extra_config or {}).items():
                if not str(k).startswith("__"):
                    runtime_extra[k] = v
            runtime_extra["__provider"] = attempt_provider

            logger.info(
                "[llm_fallback] intent attempt %s/%s | provider=%s model=%s",
                idx,
                total_attempts,
                attempt_provider,
                attempt_model,
            )

            try:
                return await self._call_openai_compatible(
                    attempt_base_url,
                    attempt_api_key,
                    attempt_model,
                    messages,
                    runtime_extra,
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "[llm_fallback] intent attempt %s/%s failed | provider=%s model=%s err=%s",
                    idx,
                    total_attempts,
                    attempt_provider,
                    attempt_model,
                    str(exc)[:200],
                )
                continue

        raise last_error or Exception("All LLM attempts exhausted")

    async def analyze_intent(self, query: str, context: Dict[str, Any], history: List[Dict[str, str]], config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyzes user query and returns a plan (list of tool calls).
        """
        if not config:
            # Fallback mock if no config
            logger.warning("No LLM config provided, using mock fallback.")
            return self._mock_fallback(query)

        api_key = config.get("api_key")
        base_url = config.get("base_url")
        model = config.get("model")

        if not api_key:
             return {"reply": "Please configure your LLM API Key in Settings.", "plan": []}

        messages = [
            {"role": "system", "content": self._get_agent_system_prompt()},
        ]
        
        # Add context summary to system message or valid context message
        context_str = f"Current Project Context: {json.dumps(context, default=str)}"
        messages.append({"role": "system", "content": context_str})

        # Add history
        for msg in _trim_history_by_token_budget(history or []):
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        
        # Add current query
        messages.append({"role": "user", "content": query})

        extra_config = dict(config.get("config", {}) or {})
        # System-management/project-agent planning expects JSON plan text,
        # not provider-side function-calling. Strip tool-calling knobs to
        # avoid upstream errors like "function ... not found in declarations".
        for key in (
            "tools",
            "tool_choice",
            "parallel_tool_calls",
            "functions",
            "function_call",
            "function_declarations",
        ):
            extra_config.pop(key, None)
        extra_config.setdefault("__provider", config.get("provider") or self._infer_provider(base_url, model))

        try:
            return await self._call_intent_with_failover(
                messages,
                config,
                extra_config,
                category="LLM",
            )
        except Exception as e:
            logger.error(f"LLM Call failed: {e}")
            provider = (extra_config or {}).get("__provider") or config.get("provider") or self._infer_provider(base_url, model)
            err_msg = self._vendor_failed_message(provider, e)
            return {
                "reply": f"Sorry, I encountered an error communicating with the AI provider: {err_msg}",
                "plan": [],
                "_llm_error": True,
            }

    async def analyze_intent_with_system_prompt(
        self,
        query: str,
        context: Dict[str, Any],
        history: List[Dict[str, str]],
        config: Dict[str, Any],
        system_prompt: str,
    ) -> Dict[str, Any]:
        if not config:
            logger.warning("No LLM config provided for custom prompt intent analysis, using mock fallback.")
            return self._mock_fallback(query)

        api_key = config.get("api_key")
        base_url = config.get("base_url")
        model = config.get("model")

        if not api_key:
            return {"reply": "Please configure your LLM API Key in Settings.", "plan": []}

        resolved_prompt = str(system_prompt or "").strip() or self._get_agent_system_prompt()
        messages = [
            {"role": "system", "content": resolved_prompt},
            {"role": "system", "content": f"Current Runtime Context: {json.dumps(context or {}, default=str)}"},
        ]

        for msg in _trim_history_by_token_budget(history or []):
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        messages.append({"role": "user", "content": query})

        extra_config = dict(config.get("config", {}) or {})
        # Intent analysis uses JSON plan parsing, not provider-native function calling.
        # Strip function-calling keys to avoid upstream "function declaration not found" errors.
        for key in (
            "tools",
            "tool_choice",
            "parallel_tool_calls",
            "functions",
            "function_call",
            "function_declarations",
        ):
            extra_config.pop(key, None)
        extra_config.setdefault("response_format", {"type": "json_object"})
        extra_config.setdefault("__provider", config.get("provider") or self._infer_provider(base_url, model))

        try:
            return await self._call_intent_with_failover(
                messages,
                config,
                extra_config,
                category="LLM",
            )
        except Exception as e:
            logger.error(f"LLM custom-prompt intent call failed: {e}")
            provider = (extra_config or {}).get("__provider") or config.get("provider") or self._infer_provider(base_url, model)
            err_msg = self._vendor_failed_message(provider, e)
            return {
                "reply": f"Sorry, I encountered an error communicating with the AI provider: {err_msg}",
                "plan": [],
                "_llm_error": True,
            }


    async def chat_completion(self, messages: List[Dict], config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Direct chat completion that returns Dict with 'content' and 'usage'.
        """
        if not config:
            raise ValueError("No LLM config provided")

        api_key = config.get("api_key")
        base_url = config.get("base_url")
        model = config.get("model")

        if not api_key:
             raise ValueError("API Key missing in config")

        extra_config = dict(config.get("config", {}) or {})
        extra_config.setdefault("__provider", config.get("provider") or self._infer_provider(base_url, model))

        try:
            full_response = await self._raw_llm_request_full(base_url, api_key, model, messages, extra_config)
            raw_content = self._extract_text_from_response(full_response)
            content = self._sanitize_response_content(raw_content)
            finish_reason = self._extract_finish_reason_from_response(full_response)
            usage = full_response.get("usage", {})
            token_limit_hints = full_response.get("_token_limit_hints", []) if isinstance(full_response, dict) else []
            extraction_diagnostics = self._build_extraction_diagnostics(full_response)
            return {
                "raw_content": raw_content,
                "content": content,
                "usage": usage,
                "finish_reason": finish_reason,
                "token_limit_hints": token_limit_hints,
                "extraction_diagnostics": extraction_diagnostics,
            }
        except Exception as e:
            logger.error(f"LLM Raw Completion failed: {e}")
            provider = (extra_config or {}).get("__provider") or config.get("provider") or self._infer_provider(base_url, model)
            raise Exception(self._vendor_failed_message(provider, e))

    def _to_positive_int(self, value: Any, default: int = 0) -> int:
        try:
            parsed = int(value)
            return parsed if parsed > 0 else int(default)
        except Exception:
            return int(default)

    def _merge_usage_dict(self, total: Dict[str, Any], part: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(total or {})
        incoming = dict(part or {})

        def _add(key: str, value: Any) -> None:
            if value is None:
                return
            try:
                iv = int(value)
            except Exception:
                return
            merged[key] = int(merged.get(key) or 0) + iv

        for k in ["prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens"]:
            _add(k, incoming.get(k))

        for k, v in incoming.items():
            if k in merged:
                continue
            if isinstance(v, (int, float, str)):
                merged[k] = v

        return merged

    def _dedupe_continuation_overlap(self, existing: str, incoming: str) -> str:
        if not existing or not incoming:
            return incoming

        for size in (200, 400, 800):
            suffix = existing[-size:]
            if suffix and incoming.startswith(suffix):
                return incoming[len(suffix):]

        incoming_lstrip = incoming.lstrip()
        for size in (200, 400, 800):
            suffix = existing[-size:]
            if suffix and incoming_lstrip.startswith(suffix):
                return incoming_lstrip[len(suffix):]

        return incoming

    async def _auto_continue_chat_completion_on_length(
        self,
        messages: List[Dict],
        config: Dict[str, Any],
        first_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        cfg = (config or {}).get("config") or {}
        auto_continue = str(cfg.get("auto_continue_on_length", "1")).strip().lower() not in {"0", "false", "no", "off"}
        if not auto_continue:
            return first_result

        max_segments = min(20, max(1, self._to_positive_int(cfg.get("continuation_max_segments"), 4)))
        if max_segments <= 1:
            return first_result

        tail_chars = min(3000, max(400, self._to_positive_int(cfg.get("continuation_tail_chars"), 1600)))
        continuation_instruction_tpl = (
            "Continue exactly where you left off, immediately after the suffix below. "
            "Do NOT repeat any suffix text. "
            "Return ONLY the continuation in the same format.\n\n"
            "SUFFIX (do not repeat):\n{suffix}"
        )

        first_raw = first_result.get("raw_content")
        if not isinstance(first_raw, str):
            first_raw = str(first_result.get("content") or "")
        first_finish_reason = first_result.get("finish_reason")
        if not self._is_length_limited_finish_reason(first_finish_reason):
            return first_result
        if not first_raw.strip():
            return first_result

        accumulated_raw = first_raw
        usage_total = self._merge_usage_dict({}, first_result.get("usage") or {})
        finish_reason = first_finish_reason
        token_limit_hints: List[str] = []
        for hint in (first_result.get("token_limit_hints") or []):
            hint_text = str(hint or "").strip()
            if hint_text and hint_text not in token_limit_hints:
                token_limit_hints.append(hint_text)

        segments: List[Dict[str, Any]] = [{
            "index": 1,
            "finish_reason": first_finish_reason,
            "output_chars": len(first_raw),
            "usage": first_result.get("usage") or {},
        }]
        continuation_stopped_by_max_segments = False

        system_only_messages: List[Dict[str, Any]] = []
        try:
            if messages and isinstance(messages[0], dict) and messages[0].get("role") == "system":
                system_only_messages = [messages[0]]
        except Exception:
            system_only_messages = []

        current_messages = list(messages)
        for seg_idx in range(2, max_segments + 1):
            if not self._is_length_limited_finish_reason(finish_reason):
                break

            suffix = accumulated_raw[-tail_chars:] if len(accumulated_raw) > tail_chars else accumulated_raw
            continuation_instruction = continuation_instruction_tpl.format(suffix=suffix)
            base_messages = system_only_messages or list(messages)
            current_messages = list(base_messages) + [
                {"role": "assistant", "content": suffix},
                {"role": "user", "content": continuation_instruction},
            ]

            next_result = await self.chat_completion(current_messages, config)
            next_raw = next_result.get("raw_content")
            if not isinstance(next_raw, str):
                next_raw = str(next_result.get("content") or "")
            if not next_raw.strip():
                finish_reason = next_result.get("finish_reason")
                break

            deduped_next_raw = self._dedupe_continuation_overlap(accumulated_raw, next_raw)
            accumulated_raw += deduped_next_raw

            usage_total = self._merge_usage_dict(usage_total, next_result.get("usage") or {})
            finish_reason = next_result.get("finish_reason")
            for hint in (next_result.get("token_limit_hints") or []):
                hint_text = str(hint or "").strip()
                if hint_text and hint_text not in token_limit_hints:
                    token_limit_hints.append(hint_text)

            segments.append({
                "index": seg_idx,
                "finish_reason": finish_reason,
                "output_chars": len(next_raw),
                "deduped_chars": len(deduped_next_raw),
                "usage": next_result.get("usage") or {},
            })

        if self._is_length_limited_finish_reason(finish_reason) and len(segments) >= max_segments:
            continuation_stopped_by_max_segments = True

        if len(segments) <= 1:
            return first_result

        logger.warning(
            "LLM auto-continuation applied | provider=%s model=%s segments=%s final_finish_reason=%s output_chars=%s stopped_by_max_segments=%s",
            config.get("provider"),
            config.get("model"),
            len(segments),
            finish_reason,
            len(accumulated_raw),
            continuation_stopped_by_max_segments,
        )

        return {
            "raw_content": accumulated_raw,
            "content": self._sanitize_response_content(accumulated_raw),
            "usage": usage_total,
            "finish_reason": finish_reason,
            "token_limit_hints": token_limit_hints,
            "extraction_diagnostics": {
                "auto_continuation_applied": True,
                "segments": segments,
                "max_segments": max_segments,
                "continuation_stopped_by_max_segments": continuation_stopped_by_max_segments,
            },
            "auto_continuation_applied": True,
            "continuation_segments": len(segments),
            "continuation_stopped_by_max_segments": continuation_stopped_by_max_segments,
        }

    async def _call_openai_compatible(self, base_url: str, api_key: str, model: str, messages: List[Dict], extra_config: Dict[str, Any] = None) -> Dict[str, Any]:
        full_response = await self._raw_llm_request_full(base_url, api_key, model, messages, extra_config)
        content = self._extract_text_from_response(full_response)
        logger.info("[_call_openai_compatible] extracted content length=%d snippet=%s", len(content or ""), (content or "")[:200])
        content = self._sanitize_response_content(content)
        logger.info("[_call_openai_compatible] sanitized content length=%d snippet=%s", len(content or ""), (content or "")[:200])
        usage = full_response.get("usage", {})
        finish_reason = self._extract_finish_reason_from_response(full_response)
        
        # Parse JSON from content
        # LLM might wrap in ```json ... ```
        clean_content = content.strip()
        if clean_content.startswith("```"):
            # Remove marked block
            lines = clean_content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_content = "\n".join(lines)

        # Try direct parse first
        result = self._try_parse_json_plan(clean_content)
        if result is not None:
            logger.info("[_call_openai_compatible] parsed JSON plan | plan_count=%d reply_len=%d", len(result.get("plan") or []), len(str(result.get("reply") or "")))
            if "reply" not in result:
                result["reply"] = clean_content
            if "plan" not in result:
                result["plan"] = []
            result["usage"] = usage
            result["finish_reason"] = finish_reason
            return result

        logger.info("[_call_openai_compatible] no JSON plan found, returning as plain reply | content_len=%d", len(clean_content))
        # Fallback if not valid JSON
        return {
            "reply": clean_content,
            "plan": [],
            "usage": usage,
            "finish_reason": finish_reason,
        }

    def _try_parse_json_plan(self, text: str) -> Optional[Dict[str, Any]]:
        """Try to extract a JSON object with 'reply'/'plan' from text.

        Handles cases where the LLM returns JSON surrounded by prose,
        leftover think-tag fragments, or other non-JSON text.
        """
        if not text or not text.strip():
            return None
        text = text.strip()

        # 1) Direct parse
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

        # 2) Find the first top-level { ... } block via brace matching
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        in_string = False
        escape_next = False
        end = -1
        for i in range(start, len(text)):
            ch = text[i]
            if escape_next:
                escape_next = False
                continue
            if ch == "\\":
                if in_string:
                    escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end == -1:
            return None
        try:
            obj = json.loads(text[start:end + 1])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        return None

    async def generate_content(self, user_prompt: str, system_prompt: str, config: Dict[str, Any], image_urls: List[str] = None, video_urls: List[str] = None) -> Dict[str, Any]:
        """
        Generates content (Text or structured) based on prompts and optional multimedia context.
        """
        if not config:
            return {"content": "Error: No LLM configuration found.", "usage": {}}
        
        # Backwards compatibility if called with positional args as (prompt, system_prompt, config)
        # Note: 'prompt' named argument in old signature maps to 'user_prompt' here if passed positional
        
        api_key = config.get("api_key")
        base_url = config.get("base_url")
        model = config.get("model")

        if not api_key:
             return {"content": "Error: Please configure your LLM API Key in Settings.", "usage": {}}

        messages = []
        if system_prompt:
             messages.append({"role": "system", "content": system_prompt})
             
        user_content = []
        if user_prompt:
             user_content.append({"type": "text", "text": user_prompt})
        
        if image_urls:
            for url in image_urls:
                if url:
                    user_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": url
                        }
                    })
        
        # Note: Video URLs support varies by provider (Gemini 1.5, GPT-4o typically don't take video URL directly in standard Chat completions yet, 
        # but specialized endpoints do. We append them as text or specific block if supported)
        if video_urls:
             for url in video_urls:
                  if url:
                       # Fallback: Just mention the URL or use specific provider logic
                       # For now, append as text context
                       user_content.append({
                           "type": "text", 
                           "text": f"Reference Video URL: {url}"
                       })
        
        # Compress if single text item (Standard format)
        if len(user_content) == 1 and user_content[0]["type"] == "text":
             messages.append({"role": "user", "content": user_content[0]["text"]})
        else:
             messages.append({"role": "user", "content": user_content})

        extra_config = dict(config.get("config", {}) or {})
        extra_config.setdefault("__provider", config.get("provider") or self._infer_provider(base_url, model))
        
        # Handle specialized "sora-create-character" if detected in system prompt
        if system_prompt == "sora-create-character":
             # This is where we would call the specialized library or endpoint
             # For now, we pass it to the generic LLM hoping it understands or we mock it
             # If provider is Doubao/Grsai Video, we might need specific payload.
             pass

        try:
             # Using the generic call which handles standard messages
             response = await self._call_openai_compatible(base_url, api_key, model, messages, extra_config)
             
             # Unpack
             content = response.get("reply", "")
             usage = response.get("usage", {})
             finish_reason = response.get("finish_reason")
             if not content and "content" in response:
                 content = response["content"] # fallback if _call_openai_compatible returns typical dict
             
             return {"content": content, "usage": usage, "finish_reason": finish_reason}

        except Exception as e:
             logger.error(f"Generate Content Error: {e}")
             provider = (extra_config or {}).get("__provider") or config.get("provider") or self._infer_provider(base_url, model)
             return {"content": f"Error: {self._vendor_failed_message(provider, e)}", "usage": {}, "finish_reason": None}

    async def _raw_llm_request(self, base_url: str, api_key: str, model: str, messages: List[Dict], extra_config: Dict[str, Any] = None) -> str:
        data = await self._raw_llm_request_full(base_url, api_key, model, messages, extra_config)
        return self._extract_text_from_response(data)

    async def _raw_llm_request_full(self, base_url: str, api_key: str, model: str, messages: List[Dict], extra_config: Dict[str, Any] = None) -> Dict[str, Any]:
        # Ensure base_url ends with correct chat endpoint if not specific
        if not base_url:
            base_url = "https://api.openai.com/v1"  # Default to OpenAI if not set

        resolved_category = str((extra_config or {}).get("__resolved_category") or "LLM").strip().upper()
        provider = (extra_config or {}).get("__provider") or self._infer_provider(base_url, model)
        if provider == "kie" and resolved_category == "LLM":
            return await self._raw_kie_llm_request_full(base_url, api_key, model, messages, extra_config)
        if provider == "grsai" and resolved_category == "LLM":
            base_url = self._normalize_grsai_llm_base_url(base_url)

        configured_endpoint = ((extra_config or {}).get("endpoint") or "").strip()
        if configured_endpoint and resolved_category == "LLM":
            endpoint_lower = configured_endpoint.lower()
            if "/chat/completions" in endpoint_lower:
                url = configured_endpoint.rstrip("/")
            else:
                url = f"{configured_endpoint.rstrip('/')}/chat/completions"
            url_source = "config.endpoint"
        elif configured_endpoint and resolved_category != "LLM":
            url = configured_endpoint.rstrip("/")
            url_source = "config.endpoint(non-llm)"
        else:
            url = base_url.rstrip("/")
            if resolved_category == "LLM" and not url.endswith("/chat/completions"):
                url = f"{url}/chat/completions"
            url_source = "base_url"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": 0.7
        }

        if extra_config:
            # Merge extra config, but don't overwrite critical fields if not intended
            # For now, just update, but maybe exclude 'model' or 'messages'
            for k, v in extra_config.items():
                if k not in ["model", "messages", "stream"] and not str(k).startswith("__"):
                    payload[k] = v

        def _to_positive_int(value: Any) -> Optional[int]:
            try:
                parsed = int(value)
                return parsed if parsed > 0 else None
            except Exception:
                return None

        resolved_output_cap = (
            _to_positive_int(payload.get("max_tokens"))
            or _to_positive_int(payload.get("max_completion_tokens"))
            or _to_positive_int(payload.get("max_output_tokens"))
        )
        if resolved_output_cap and _to_positive_int(payload.get("max_tokens")) is None:
            payload["max_tokens"] = resolved_output_cap

        def _message_chars(msg: Dict[str, Any]) -> int:
            content = msg.get("content")
            if isinstance(content, str):
                return len(content)
            if isinstance(content, list):
                total = 0
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            total += len(part.get("text") or "")
                        elif part.get("type") == "image_url":
                            url_val = (part.get("image_url") or {}).get("url") or ""
                            total += len(url_val)
                        else:
                            total += len(json.dumps(part, ensure_ascii=False))
                    else:
                        total += len(str(part))
                return total
            return len(str(content))

        roles = {}
        prompt_chars = 0
        for m in (messages or []):
            try:
                role = m.get("role", "unknown")
                roles[role] = roles.get(role, 0) + 1
                prompt_chars += _message_chars(m)
            except Exception:
                continue

        effective_max_tokens = payload.get("max_tokens")
        if effective_max_tokens is None:
            effective_max_tokens = payload.get("max_completion_tokens")
        if effective_max_tokens is None:
            effective_max_tokens = payload.get("max_output_tokens")

        _debug_log(f"[DEBUG][LLM][{provider}] Request | provider={provider} category={resolved_category} model={model} url={url} (source={url_source}) messages={len(messages or [])} prompt_chars={prompt_chars} max_tokens={effective_max_tokens}")
        logger.info(
            "Calling LLM: category=%s url=%s (source=%s) model=%s messages=%s roles=%s prompt_chars=%s max_tokens=%s",
            resolved_category,
            url,
            url_source,
            model,
            len(messages or []),
            roles,
            prompt_chars,
            effective_max_tokens,
        )

        redacted_headers = {
            **headers,
            "Authorization": "Bearer ***REDACTED***",
        }
        self._safe_log_json("LLM_REQUEST", {
            "provider": provider,
            "category": resolved_category,
            "url": url,
            "url_source": url_source,
            "model": model,
            "headers": redacted_headers,
            "payload": payload,
            "message_count": len(messages or []),
            "prompt_chars": prompt_chars,
            "max_tokens": effective_max_tokens,
            "resolved_source": (extra_config or {}).get("__resolved_source"),
            "resolved_setting_id": (extra_config or {}).get("__resolved_setting_id"),
        })

        def _request(bypass_proxy=False, connect_timeout=None):
            read_timeout = DEFAULT_LLM_TIMEOUT_SECONDS
            c_timeout = connect_timeout or max(3, DEFAULT_LLM_CONNECT_TIMEOUT_SECONDS)
            kwargs = {
                "json": payload,
                "headers": headers,
                "timeout": (c_timeout, read_timeout),
            }
            if bypass_proxy:
                kwargs["proxies"] = {"http": None, "https": None}
            return requests.post(url, **kwargs)

        try:
            response = await asyncio.to_thread(_request, False)
        except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            _debug_log(f"[DEBUG][LLM][{provider}] Connection failed ({str(e)[:120]}), retrying without proxy...", "warning")
            logger.warning(f"Connection failed ({str(e)}). Retrying without proxy (connect_timeout={DEFAULT_LLM_NO_PROXY_CONNECT_TIMEOUT_SECONDS}s)...")
            try:
                response = await asyncio.to_thread(_request, True, max(3, DEFAULT_LLM_NO_PROXY_CONNECT_TIMEOUT_SECONDS))
            except requests.exceptions.Timeout as e2:
                _debug_log(f"[DEBUG][LLM][{provider}] No-proxy retry also timed out: {e2}", "error")
                logger.error(f"No-proxy retry also timed out: {e2}")
                raise Exception(self._vendor_failed_message(provider, f"Upstream timeout (proxy failed, direct also timed out): {e2}"))
            except Exception as e2:
                logger.error(f"No-proxy retry also failed: {e2}")
                raise Exception(self._vendor_failed_message(provider, e2))
        
        _debug_log(f"[DEBUG][LLM][{provider}] Response | status={response.status_code} model={model} url={url} body={_strip_base64_from_log(response.text[:500])}")

        if response.status_code != 200:
            provider = (extra_config or {}).get("__provider") or (extra_config or {}).get("provider") or self._infer_provider(base_url, model)
            resolved_setting_id = (extra_config or {}).get("__resolved_setting_id")
            resolved_source = (extra_config or {}).get("__resolved_source")
            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": provider,
                "category": resolved_category,
                "url": url,
                "model": model,
                "status_code": response.status_code,
                "response_text": response.text,
                "resolved_source": resolved_source,
                "resolved_setting_id": resolved_setting_id,
            })
            raw_reason = f"API Error {response.status_code} [provider={provider}, model={model}, endpoint={url}, setting_id={resolved_setting_id}, source={resolved_source}]: {response.text}"
            raise Exception(self._vendor_failed_message(provider, raw_reason))

        data = response.json()
        try:
            data["_token_limit_hints"] = self._extract_provider_limit_hints(data, response.headers)
        except Exception:
            data["_token_limit_hints"] = []
        self._safe_log_json("LLM_RESPONSE", {
            "provider": provider,
            "category": resolved_category,
            "url": url,
            "model": model,
            "status_code": response.status_code,
            "response": data,
            "resolved_source": (extra_config or {}).get("__resolved_source"),
            "resolved_setting_id": (extra_config or {}).get("__resolved_setting_id"),
        })

        # Normalize assistant text output across all text-LLM calls.
        if isinstance(data.get("choices"), list):
            for choice in data.get("choices"):
                if not isinstance(choice, dict):
                    continue
                message = choice.get("message")
                if isinstance(message, dict) and "content" in message:
                    message["content"] = self._sanitize_response_content(message.get("content"))

        # Summarize response without dumping content.
        try:
            choices = data.get("choices") or []
            first = choices[0] if choices else {}
            finish_reason = self._extract_finish_reason_from_response(data)
            content = self._extract_text_from_response(data)
            usage = data.get("usage") or {}
            output_chars = len(content) if isinstance(content, str) else len(str(content))
            logger.info(
                "LLM Response: model=%s finish_reason=%s output_chars=%s usage=%s",
                data.get("model") or model,
                finish_reason,
                output_chars,
                usage,
            )
            self._safe_log_json("LLM_RESPONSE_SUMMARY", {
                "provider": provider,
                "category": resolved_category,
                "url": url,
                "model": data.get("model") or model,
                "finish_reason": finish_reason,
                "output_chars": output_chars,
                "usage": usage,
                "prompt_chars": prompt_chars,
                "max_tokens": effective_max_tokens,
            })
            if self._is_length_limited_finish_reason(finish_reason):
                logger.warning(
                    "LLM output appears truncated (finish_reason=length). prompt_chars=%s output_chars=%s max_tokens=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s usage=%s",
                    prompt_chars,
                    output_chars,
                    effective_max_tokens,
                    usage.get("prompt_tokens") or usage.get("input_tokens"),
                    usage.get("completion_tokens") or usage.get("output_tokens"),
                    usage.get("total_tokens"),
                    usage,
                )
                self._safe_log_json("LLM_RESPONSE_TRUNCATED", {
                    "provider": provider,
                    "category": resolved_category,
                    "url": url,
                    "model": data.get("model") or model,
                    "finish_reason": finish_reason,
                    "prompt_chars": prompt_chars,
                    "output_chars": output_chars,
                    "max_tokens": effective_max_tokens,
                    "prompt_tokens": usage.get("prompt_tokens") or usage.get("input_tokens"),
                    "completion_tokens": usage.get("completion_tokens") or usage.get("output_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                    "usage": usage,
                })
            if output_chars == 0:
                first_choice_keys = list(first.keys()) if isinstance(first, dict) else []
                logger.warning(
                    "LLM empty output detected: provider=%s model=%s finish_reason=%s first_choice_keys=%s usage=%s",
                    provider,
                    model,
                    finish_reason,
                    first_choice_keys,
                    usage,
                )
                self._safe_log_json("LLM_EMPTY_OUTPUT", {
                    "provider": provider,
                    "category": resolved_category,
                    "url": url,
                    "model": data.get("model") or model,
                    "finish_reason": finish_reason,
                    "first_choice_keys": first_choice_keys,
                    "usage": usage,
                })
        except Exception:
            logger.info("LLM Response received (summary unavailable)")

        # Optional deep debug (disabled by default). This may include large content.
        if os.getenv("LLM_DEBUG_LOG_CONTENT") == "1":
            logging.getLogger("app").debug("LLM Payload (debug): %s", json.dumps(payload, ensure_ascii=False))
            logging.getLogger("app").debug("LLM Response (debug): %s", json.dumps(data, ensure_ascii=False))

        if self._is_blocked_response(data):
            logger.warning(
                "LLM blocked by provider moderation: provider=%s model=%s url=%s finish_reason=%s",
                provider,
                model,
                url,
                ((data.get("choices") or [{}])[0] or {}).get("finish_reason"),
            )
            raise RuntimeError(self._vendor_failed_message(provider, "LLM content blocked by provider (PROHIBITED_CONTENT)"))
        
        if "choices" in data and len(data["choices"]) > 0:
            return data
        else:
             raise Exception(self._vendor_failed_message(provider, f"Invalid API Response: {data}"))

    # ── Streaming LLM request ──────────────────────────────────────────────

    async def _raw_llm_request_stream(
        self,
        base_url: str,
        api_key: str,
        model: str,
        messages: List[Dict],
        extra_config: Dict[str, Any] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Async generator yielding streaming events from an OpenAI-compatible API.

        Yields dicts:
            {"type": "token", "content": "..."}   – text delta
            {"type": "done",  "usage": {...}}      – stream finished
        """
        if not base_url:
            base_url = "https://api.openai.com/v1"

        resolved_category = str((extra_config or {}).get("__resolved_category") or "LLM").strip().upper()
        provider = (extra_config or {}).get("__provider") or self._infer_provider(base_url, model)

        if provider == "grsai" and resolved_category == "LLM":
            base_url = self._normalize_grsai_llm_base_url(base_url)

        # ── Build URL (same logic as _raw_llm_request_full) ──
        configured_endpoint = ((extra_config or {}).get("endpoint") or "").strip()
        if provider == "kie" and resolved_category == "LLM":
            _, resolved_model, url = self._resolve_kie_llm_url(base_url, model)
        elif configured_endpoint and resolved_category == "LLM":
            endpoint_lower = configured_endpoint.lower()
            if "/chat/completions" in endpoint_lower:
                url = configured_endpoint.rstrip("/")
            else:
                url = f"{configured_endpoint.rstrip('/')}/chat/completions"
        elif configured_endpoint and resolved_category != "LLM":
            url = configured_endpoint.rstrip("/")
        else:
            url = base_url.rstrip("/")
            if resolved_category == "LLM" and not url.endswith("/chat/completions"):
                url = f"{url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": resolved_model if (provider == "kie" and resolved_category == "LLM") else model,
            "messages": messages,
            "stream": True,
            "temperature": 0.7,
        }

        if provider == "kie" and resolved_category == "LLM":
            payload.update(self._extract_kie_chat_options(extra_config or {}))
        elif extra_config:
            for k, v in extra_config.items():
                if k not in ["model", "messages", "stream"] and not str(k).startswith("__"):
                    payload[k] = v

        print(f"[STREAM-DEBUG] _raw_llm_request_stream: url={url}, model={model}, provider={provider}, payload_keys={list(payload.keys())}, stream={payload.get('stream')}")
        logger.info(
            "Calling LLM (stream): provider=%s model=%s url=%s messages=%d",
            provider, model, url, len(messages or []),
        )

        usage: Dict[str, Any] = {}
        timeout = httpx.Timeout(connect=30.0, read=float(DEFAULT_LLM_TIMEOUT_SECONDS), write=30.0, pool=30.0)

        try:
            print(f"[STREAM-DEBUG] _raw_llm_request_stream: opening httpx connection to {url}...")
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    print(f"[STREAM-DEBUG] _raw_llm_request_stream: got response status={response.status_code}")
                    if response.status_code != 200:
                        error_body = await response.aread()
                        raise Exception(
                            self._vendor_failed_message(
                                provider,
                                f"API Error {response.status_code}: {error_body.decode('utf-8', errors='replace')[:500]}",
                            )
                        )

                    import asyncio as _asyncio
                    _heartbeat_interval = 15  # seconds
                    _last_yield_time = _asyncio.get_event_loop().time()

                    async for raw_line in response.aiter_lines():
                        line = raw_line.strip()
                        if not line:
                            # Send heartbeat if no data for a while (keeps SSE alive)
                            now = _asyncio.get_event_loop().time()
                            if now - _last_yield_time > _heartbeat_interval:
                                yield {"type": "heartbeat", "content": ""}
                                _last_yield_time = now
                            continue
                        if not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        # Capture usage if the provider includes it in a chunk
                        if chunk.get("usage"):
                            usage = chunk["usage"]

                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        content = delta.get("content") or ""
                        if not content:
                            content = delta.get("reasoning_content") or ""
                        if content:
                            yield {"type": "token", "content": content}
                            _last_yield_time = _asyncio.get_event_loop().time()

        except httpx.ConnectError as exc:
            raise Exception(self._vendor_failed_message(provider, f"Connection failed: {exc}"))
        except httpx.ReadTimeout as exc:
            raise Exception(self._vendor_failed_message(provider, f"Read timeout: {exc}"))

        yield {"type": "done", "usage": usage}

    async def stream_analyze_intent(
        self,
        query: str,
        context: Dict[str, Any],
        history: List[Dict[str, str]],
        config: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Streaming version of analyze_intent.

        Yields:
            {"type": "token", "content": "..."}  – text deltas from the LLM
            {"type": "result", "reply": "...", "plan": [...], "usage": {...}}  – final parsed result
        """
        if not config:
            yield {"type": "result", "reply": "No LLM config provided.", "plan": [], "usage": {}}
            return
        api_key = config.get("api_key")
        base_url = config.get("base_url")
        model = config.get("model")
        if not api_key:
            yield {"type": "result", "reply": "Please configure your LLM API Key in Settings.", "plan": [], "usage": {}}
            return

        messages = [
            {"role": "system", "content": self._get_agent_system_prompt()},
            {"role": "system", "content": f"Current Project Context: {json.dumps(context or {}, default=str)}"},
        ]
        for msg in _trim_history_by_token_budget(history or []):
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        messages.append({"role": "user", "content": query})

        extra_config = dict(config.get("config", {}) or {})
        extra_config.setdefault("__provider", config.get("provider") or self._infer_provider(base_url, model))

        print(f"[STREAM-DEBUG] llm_service.stream_analyze_intent: calling _raw_llm_request_stream, base_url={base_url}, model={model}, messages_count={len(messages)}")
        accumulated = ""
        usage: Dict[str, Any] = {}
        try:
            async for event in self._raw_llm_request_stream(base_url, api_key, model, messages, extra_config):
                if event["type"] == "token":
                    accumulated += event["content"]
                    if len(accumulated) <= 100:
                        print(f"[STREAM-DEBUG] llm_service.stream_analyze_intent: accumulated so far: {repr(accumulated[:100])}")
                    yield event
                elif event["type"] == "done":
                    print(f"[STREAM-DEBUG] llm_service.stream_analyze_intent: done event, usage={usage}, accumulated_len={len(accumulated)}")
                    usage = event.get("usage", {})
        except Exception as e:
            print(f"[STREAM-DEBUG] llm_service.stream_analyze_intent ERROR: {e}")
            logger.error("stream_analyze_intent error: %s", e)
            provider = extra_config.get("__provider") or config.get("provider") or self._infer_provider(base_url, model)
            yield {"type": "result", "reply": f"Error: {self._vendor_failed_message(provider, e)}", "plan": [], "usage": {}, "_llm_error": True}
            return

        # Parse the accumulated response
        content = self._sanitize_response_content(accumulated)
        clean = content.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean = "\n".join(lines)

        result = self._try_parse_json_plan(clean)
        if result is not None:
            if "reply" not in result:
                result["reply"] = clean
            if "plan" not in result:
                result["plan"] = []
        else:
            result = {"reply": clean, "plan": []}
        result["usage"] = usage
        yield {"type": "result", **result}

    async def stream_analyze_intent_with_system_prompt(
        self,
        query: str,
        context: Dict[str, Any],
        history: List[Dict[str, str]],
        config: Dict[str, Any],
        system_prompt: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Streaming version of analyze_intent_with_system_prompt."""
        if not config:
            yield {"type": "result", "reply": "No LLM config provided.", "plan": [], "usage": {}}
            return
        api_key = config.get("api_key")
        base_url = config.get("base_url")
        model = config.get("model")
        if not api_key:
            yield {"type": "result", "reply": "Please configure your LLM API Key in Settings.", "plan": [], "usage": {}}
            return

        resolved_prompt = str(system_prompt or "").strip() or self._get_agent_system_prompt()
        messages = [
            {"role": "system", "content": resolved_prompt},
            {"role": "system", "content": f"Current Runtime Context: {json.dumps(context or {}, default=str)}"},
        ]
        for msg in _trim_history_by_token_budget(history or []):
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        messages.append({"role": "user", "content": query})

        extra_config = dict(config.get("config", {}) or {})
        # Keep streaming intent-analysis aligned with non-streaming behavior.
        for key in (
            "tools",
            "tool_choice",
            "parallel_tool_calls",
            "functions",
            "function_call",
            "function_declarations",
        ):
            extra_config.pop(key, None)
        extra_config.setdefault("response_format", {"type": "json_object"})
        extra_config.setdefault("__provider", config.get("provider") or self._infer_provider(base_url, model))

        accumulated = ""
        usage: Dict[str, Any] = {}
        try:
            async for event in self._raw_llm_request_stream(base_url, api_key, model, messages, extra_config):
                if event["type"] == "token":
                    accumulated += event["content"]
                    yield event
                elif event["type"] == "done":
                    usage = event.get("usage", {})
        except Exception as e:
            logger.error("stream_analyze_intent_with_system_prompt error: %s", e)
            provider = extra_config.get("__provider") or config.get("provider") or self._infer_provider(base_url, model)
            yield {"type": "result", "reply": f"Error: {self._vendor_failed_message(provider, e)}", "plan": [], "usage": {}, "_llm_error": True}
            return

        content = self._sanitize_response_content(accumulated)
        clean = content.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean = "\n".join(lines)

        result = self._try_parse_json_plan(clean)
        if result is not None:
            if "reply" not in result:
                result["reply"] = clean
            if "plan" not in result:
                result["plan"] = []
        else:
            result = {"reply": clean, "plan": []}
        result["usage"] = usage
        yield {"type": "result", **result}

    # ── Retry-with-fallback wrappers ──────────────────────────────────────

    @staticmethod
    def _build_routing_metadata_from_config(config: Dict[str, Any]) -> Dict[str, Any]:
        cfg = config or {}
        cfg_extra = cfg.get("config") or {}
        system_api_id = cfg_extra.get("__resolved_setting_id")
        try:
            system_api_id = int(system_api_id) if system_api_id is not None else None
        except Exception:
            system_api_id = None

        provider = str(cfg.get("provider") or "").strip() or None
        model = str(cfg.get("model") or "").strip() or None
        resolved_source = str(cfg_extra.get("__resolved_source") or "").strip() or None
        return {
            "provider": provider,
            "model": model,
            "system_api_id": system_api_id,
            "resolved_source": resolved_source,
        }

    def _attach_routing_metadata(self, result: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(result, dict):
            return result

        routing = self._build_routing_metadata_from_config(config)
        provider = routing.get("provider")
        model = routing.get("model")
        system_api_id = routing.get("system_api_id")

        if provider:
            result["provider"] = provider
        if model:
            result["model"] = model
        if system_api_id is not None:
            result["system_api_id"] = system_api_id

        result["routing_metadata"] = {
            "provider": provider,
            "model": model,
            "system_api_id": system_api_id,
            "resolved_source": routing.get("resolved_source"),
        }
        return result

    async def generate_content_with_fallback(
        self,
        user_prompt: str,
        system_prompt: str,
        config: Dict[str, Any],
        image_urls: List[str] = None,
        video_urls: List[str] = None,
        *,
        user_id: int = None,
        category: str = "LLM",
        modality: Optional[str] = None,
    ) -> Dict[str, Any]:
        """generate_content with active-config×2 retry + 3 fallback candidates."""
        from app.services.agent_service import agent_service

        active_setting_id = (config.get("config") or {}).get("__resolved_setting_id")
        if user_id is None:
            user_id = (config.get("config") or {}).get("__resolved_user_id") or 1
        last_err = ""

        # ── active config: 2 attempts ──
        for attempt in range(1, 3):
            result = await self.generate_content(user_prompt, system_prompt, config, image_urls, video_urls)
            content = str(result.get("content") or "")
            if not content.startswith("Error:"):
                return self._attach_routing_metadata(result, config)
            last_err = content
            logger.warning(
                "[llm_fallback] active attempt %d/2 failed | provider=%s model=%s err=%s",
                attempt, config.get("provider"), config.get("model"), content[:200],
            )

        # ── fallback candidates: up to 3 ──
        fallbacks = agent_service.get_fallback_configs(
            user_id, category=category, exclude_setting_id=active_setting_id,
            modality=modality, limit=3,
        )
        for idx, fb_cfg in enumerate(fallbacks, 1):
            logger.info(
                "[llm_fallback] trying fallback %d/%d | provider=%s model=%s",
                idx, len(fallbacks), fb_cfg.get("provider"), fb_cfg.get("model"),
            )
            result = await self.generate_content(user_prompt, system_prompt, fb_cfg, image_urls, video_urls)
            content = str(result.get("content") or "")
            if not content.startswith("Error:"):
                return self._attach_routing_metadata(result, fb_cfg)
            last_err = content
            logger.warning(
                "[llm_fallback] fallback %d/%d failed | provider=%s model=%s err=%s",
                idx, len(fallbacks), fb_cfg.get("provider"), fb_cfg.get("model"), content[:200],
            )

        return self._attach_routing_metadata({"content": last_err, "usage": {}, "finish_reason": None}, config)

    async def chat_completion_with_fallback(
        self,
        messages: List[Dict],
        config: Dict[str, Any],
        *,
        user_id: int = None,
        category: str = "LLM",
        modality: Optional[str] = None,
    ) -> Dict[str, Any]:
        """chat_completion with active-config×2 retry + 3 fallback candidates."""
        from app.services.agent_service import agent_service

        active_setting_id = (config.get("config") or {}).get("__resolved_setting_id")
        if user_id is None:
            user_id = (config.get("config") or {}).get("__resolved_user_id") or 1
        last_exc: Optional[Exception] = None
        failed_attempts: List[str] = []

        def _record_failed_attempt(provider: Any, model: Any, stage: str, attempt_no: int, err: Exception) -> None:
            provider_text = str(provider or "unknown").strip() or "unknown"
            model_text = str(model or "unknown").strip() or "unknown"
            detail = str(err or "unknown error").strip()
            failed_attempts.append(
                f"{stage} attempt {attempt_no} failed ({provider_text}/{model_text}): {detail}"
            )

        def _attach_fallback_warnings(result: Dict[str, Any]) -> Dict[str, Any]:
            if not isinstance(result, dict):
                return result
            if not failed_attempts:
                return result
            # Keep payload bounded to avoid oversized meta and UI spam.
            result["fallback_warnings"] = failed_attempts[:8]
            result["fallback_warning_codes"] = ["LLM_CALL_FAILED_RETRIED"]
            return result

        # ── active config: 2 attempts ──
        for attempt in range(1, 3):
            try:
                result = await self.chat_completion(messages, config)
                result = await self._auto_continue_chat_completion_on_length(messages, config, result)
                result = self._attach_routing_metadata(result, config)
                return _attach_fallback_warnings(result)
            except Exception as e:
                last_exc = e
                _record_failed_attempt(config.get("provider"), config.get("model"), "active", attempt, e)
                logger.warning(
                    "[llm_fallback] chat_completion active attempt %d/2 failed | provider=%s model=%s err=%s",
                    attempt, config.get("provider"), config.get("model"), str(e)[:200],
                )

        # ── fallback candidates: up to 3 ──
        fallbacks = agent_service.get_fallback_configs(
            user_id, category=category, exclude_setting_id=active_setting_id,
            modality=modality, limit=3,
        )
        for idx, fb_cfg in enumerate(fallbacks, 1):
            try:
                logger.info(
                    "[llm_fallback] chat_completion fallback %d/%d | provider=%s model=%s",
                    idx, len(fallbacks), fb_cfg.get("provider"), fb_cfg.get("model"),
                )
                result = await self.chat_completion(messages, fb_cfg)
                result = await self._auto_continue_chat_completion_on_length(messages, fb_cfg, result)
                result = self._attach_routing_metadata(result, fb_cfg)
                return _attach_fallback_warnings(result)
            except Exception as e:
                last_exc = e
                _record_failed_attempt(fb_cfg.get("provider"), fb_cfg.get("model"), "fallback", idx, e)
                logger.warning(
                    "[llm_fallback] chat_completion fallback %d/%d failed | provider=%s model=%s err=%s",
                    idx, len(fallbacks), fb_cfg.get("provider"), fb_cfg.get("model"), str(e)[:200],
                )

        raise last_exc or Exception("All LLM attempts exhausted")

    def _mock_fallback(self, query: str) -> Dict[str, Any]:
        if "analyze" in query.lower():
            return {
                "reply": "I will analyze the script (Mock).",
                "plan": [{"tool": "analyze_script", "parameters": {"text": "..."}}]
            }
        return {"reply": f"Mock reply to: {query}", "plan": []}

llm_service = LLMService()
