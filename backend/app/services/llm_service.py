

import requests
import httpx
import json
import asyncio
import time
from typing import Dict, Any, List, Optional, AsyncGenerator, Tuple
import logging
import os
import re

from app.core.config import settings
from app.core.prompts.skills_loader import get_skill_prompt_text

logger = logging.getLogger(__name__)

# Some providers (e.g., Ark/Doubao) can take several minutes for large prompts.
# Default timeout set to 300s, with env override support.
DEFAULT_LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "300"))
DEFAULT_LLM_CONNECT_TIMEOUT_SECONDS = int(os.getenv("LLM_CONNECT_TIMEOUT_SECONDS", "15"))
DEFAULT_LLM_NO_PROXY_CONNECT_TIMEOUT_SECONDS = int(os.getenv("LLM_NO_PROXY_CONNECT_TIMEOUT_SECONDS", "10"))
DEFAULT_KIE_LLM_TIMEOUT_SECONDS = max(
    900,
    DEFAULT_LLM_TIMEOUT_SECONDS,
    int(os.getenv("KIE_LLM_TIMEOUT_SECONDS", "900")),
)
LLM_DEBUG_LOG_ENABLED = os.getenv("LLM_DEBUG_LOG", "0") == "1"
LLM_DEBUG_LOG_MAX_CHARS = max(512, int(os.getenv("LLM_DEBUG_LOG_MAX_CHARS", "1800") or 1800))


class AmbiguousLLMTransportError(Exception):
    pass

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
    """Bounded debug logger for optional verbose traces.

    Info-level debug traces are disabled by default and only enabled with
    LLM_DEBUG_LOG=1. Warning/error logs still flow for diagnostics.
    """
    method = getattr(logger, level, logger.info)
    if level not in {"warning", "error", "critical"} and not LLM_DEBUG_LOG_ENABLED:
        return
    text = str(msg or "")
    if len(text) > LLM_DEBUG_LOG_MAX_CHARS:
        text = f"{text[:LLM_DEBUG_LOG_MAX_CHARS]}...<TRUNCATED len={len(text)}>"
    method(text)


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

    def _flatten_transport_error_text(self, error: Any) -> str:
        if error is None:
            return ""
        try:
            if isinstance(error, BaseException):
                parts = [str(error)]
                for arg in getattr(error, "args", ()) or ():
                    try:
                        parts.append(str(arg))
                    except Exception:
                        continue
                return " | ".join(part for part in parts if part)
        except Exception:
            pass
        return str(error)

    def _is_retryable_proxy_fallback_error(self, error: Any) -> bool:
        if isinstance(error, requests.exceptions.ProxyError):
            return True

        text = self._flatten_transport_error_text(error).lower()
        proxy_markers = [
            "proxyerror",
            "cannot connect to proxy",
            "proxy authentication",
            "tunnel connection failed",
            "407 proxy",
            "https proxy",
            "http proxy",
        ]
        if any(marker in text for marker in proxy_markers):
            return True

        if isinstance(error, requests.exceptions.SSLError):
            ssl_proxy_markers = [
                "wrong version number",
                "tlsv1 alert",
                "certificate verify failed",
            ]
            return any(marker in text for marker in ssl_proxy_markers)

        return False

    def _is_runtime_shutdown_text(self, text: Any) -> bool:
        stable = str(text or "").strip().lower()
        if not stable:
            return False
        markers = [
            "cannot schedule new futures after shutdown",
            "executor shutdown has been called",
            "event loop is closed",
            "cannot schedule new futures",
        ]
        return any(marker in stable for marker in markers)

    def _is_runtime_shutdown_error(self, error: Any) -> bool:
        if isinstance(error, RuntimeError) and self._is_runtime_shutdown_text(str(error)):
            return True
        return self._is_runtime_shutdown_text(self._flatten_transport_error_text(error))

    def _is_ambiguous_submit_transport_error(self, error: Any) -> bool:
        if error is None or self._is_retryable_proxy_fallback_error(error):
            return False

        text = self._flatten_transport_error_text(error).lower()
        markers = [
            "remotedisconnected",
            "remote end closed connection without response",
            "unexpected_eof_while_reading",
            "ssleoferror",
            "connection reset by peer",
            "connection aborted",
            "connection closed",
            "broken pipe",
            "read timed out",
            "readtimeout",
            "timed out",
            "10054",
            "unexpected eof",
        ]
        if isinstance(error, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
            return True
        if isinstance(error, requests.exceptions.SSLError):
            return any(marker in text for marker in markers)
        return any(marker in text for marker in markers)

    def _get_provider_read_timeout_seconds(self, provider: Any) -> int:
        normalized = str(provider or "").strip().lower()
        if normalized == "kie":
            return DEFAULT_KIE_LLM_TIMEOUT_SECONDS
        return DEFAULT_LLM_TIMEOUT_SECONDS

    def _raise_ambiguous_submit_error(self, provider: Any, model: Any, error: Any, url: str) -> None:
        detail = str(error or "unknown transport error").strip()
        vendor = self._vendor_label(provider)
        endpoint = str(url or "").strip()
        model_text = str(model or "").strip() or "unknown"
        message = (
            f"{vendor} 上游连接在响应前中断，无法确认请求是否已被受理；系统已停止自动重试以避免重复生成或重复扣费。"
            f" model={model_text} endpoint={endpoint} 原始错误: {detail}"
        )
        raise AmbiguousLLMTransportError(message)

    def _safe_log_json(self, tag: str, payload: Dict[str, Any]) -> None:
        # Disabled by design: stop persisting raw/returned LLM payload logs.
        return None

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
        if "kie.ai" in url:
            return "kie"
        if "ark.cn-" in url or "doubao" in model_lower:
            return "doubao"
        if "claude" in model_lower:
            return "claude"
        if "openai" in url:
            return "openai"
        if "anthropic" in url:
            return "claude"
        if "grsai" in url:
            return "grsai"
        if "volces" in url:
            return "volcengine"
        if "localhost" in url or "127.0.0.1" in url:
            return "local"
        return "unknown"

    def _is_claude_provider(self, provider: Any) -> bool:
        normalized = str(provider or "").strip().lower()
        return normalized in {"claude", "anthropic"}

    def _should_use_claude_api(self, provider: Any, model: Any) -> bool:
        normalized_provider = str(provider or "").strip().lower()
        model_lower = str(model or "").strip().lower()
        return self._is_claude_provider(provider) or ("claude" in model_lower)

    def _resolve_claude_llm_url(self, base_url: str, endpoint_hint: str = "") -> str:
        hinted = str(endpoint_hint or "").strip()
        if hinted:
            if hinted.startswith("http"):
                hinted_root = hinted.rstrip("/")
                hinted_lower = hinted_root.lower()

                if "kie.ai" in hinted_lower:
                    clean_root = re.sub(
                        r"(/claude/v1/messages|/api/v1/jobs/createTask|/[^/]+/v1/chat/completions|/v1/chat/completions|/chat/completions|/v1)+/?$",
                        "",
                        hinted_root,
                        flags=re.IGNORECASE,
                    ).rstrip("/")
                    return f"{clean_root}/claude/v1/messages"

                if hinted_lower.endswith("/chat/completions"):
                    if "apiyi.com" in hinted_lower:
                        return hinted_root
                    return re.sub(r"/chat/completions/?$", "/messages", hinted_root, flags=re.IGNORECASE)

                if hinted_lower.endswith("/v1"):
                    if "apiyi.com" in hinted_lower:
                        return f"{hinted_root}/chat/completions"
                    return f"{hinted_root}/messages"

                return hinted_root
            return f"{str(base_url or '').rstrip('/')}/{hinted.lstrip('/')}".rstrip("/")

        root = (base_url or "").strip().rstrip("/")
        lower_root = root.lower()

        if lower_root.endswith("/v1/messages") or lower_root.endswith("/openapi/v1/messages"):
            return root
        if "anthropic.com" in lower_root:
            if lower_root.endswith("/v1"):
                return f"{root}/messages"
            return f"{root}/v1/messages"
        
        if "kie.ai" in lower_root:
            # Drop trailing /v1 or /claude if accidentally provided, enforce canonical
            clean_root = re.sub(r"(/v1|/claude)+/?$", "", lower_root, flags=re.IGNORECASE)
            return f"{root[:len(clean_root)]}/claude/v1/messages"

        if lower_root.endswith("/v1"):
            if "apiyi.com" in lower_root:
                return f"{root}/chat/completions"
            return f"{root}/messages"
        if lower_root.endswith("/chat/completions"):
            if "apiyi.com" in lower_root:
                return root
            return re.sub(r"/chat/completions/?$", "/messages", root, flags=re.IGNORECASE)
        if lower_root.endswith("/model") or "zimaocloud" in lower_root:
            return f"{root}/openApi/v1/messages"
        return f"{root}/messages"

    def _build_claude_payload_from_messages(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        stream: bool,
        extra_config: Optional[Dict[str, Any]] = None,
        provider: Any = None,
    ) -> Dict[str, Any]:
        cfg = dict(extra_config or {})
        system_chunks: List[str] = []
        converted_messages: List[Dict[str, Any]] = []

        for msg in messages or []:
            if not isinstance(msg, dict):
                continue
            role = str(msg.get("role") or "user").strip().lower() or "user"
            content_text = self._extract_text_from_content(msg.get("content"))

            if role == "system":
                if content_text:
                    system_chunks.append(content_text)
                continue

            if role not in {"user", "assistant"}:
                role = "user"

            converted_messages.append({
                "role": role,
                "content": content_text or "",
            })

        payload: Dict[str, Any] = {
            "model": model,
            "messages": converted_messages,
            "stream": bool(stream),
        }

        if system_chunks:
            payload["system"] = "\n\n".join(chunk for chunk in system_chunks if chunk).strip()

        allowed_keys = {
            "temperature",
            "top_p",
            "top_k",
            "max_tokens",
            "stop_sequences",
            "tools",
            "tool_choice",
            "system",
        }
        for key, value in cfg.items():
            if str(key).startswith("__"):
                continue
            if key in {"model", "messages", "stream"}:
                continue
            if key in allowed_keys:
                payload[key] = value

        def _to_positive_int(value: Any) -> Optional[int]:
            try:
                parsed = int(value)
                return parsed if parsed > 0 else None
            except Exception:
                return None

        resolved_cap = (
            _to_positive_int(payload.get("max_tokens"))
            or _to_positive_int(cfg.get("max_completion_tokens"))
            or _to_positive_int(cfg.get("max_output_tokens"))
        )
        if resolved_cap:
            payload["max_tokens"] = resolved_cap
        elif str(provider or "").strip().lower() == "aiclub":
            # aiclub Claude endpoint rejects empty max_tokens; keep this provider-local.
            fallback_cap = _to_positive_int(os.getenv("AICLUB_CLAUDE_DEFAULT_MAX_TOKENS", "81920")) or 81920
            payload["max_tokens"] = fallback_cap

        return payload

    def _extract_stream_chunk_text_and_finish(self, chunk: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        choices = chunk.get("choices") or []
        if isinstance(choices, list) and choices:
            first = choices[0] if isinstance(choices[0], dict) else {}
            finish_reason = first.get("finish_reason")
            delta = first.get("delta") if isinstance(first.get("delta"), dict) else {}
            content = ""
            if isinstance(delta, dict):
                content = str(delta.get("content") or "")
                if not content:
                    content = str(delta.get("reasoning_content") or "")
            if content or finish_reason:
                return content, finish_reason

        event_type = str(chunk.get("type") or "").strip().lower()
        if event_type == "content_block_start":
            cb = chunk.get("content_block") if isinstance(chunk.get("content_block"), dict) else {}
            if cb.get("type") == "tool_use":
                return f"[TOOL_USE_START: {cb.get('name')}]", None
            return str(cb.get("text") or cb.get("content") or ""), None
        if event_type == "content_block_delta":
            delta = chunk.get("delta") if isinstance(chunk.get("delta"), dict) else {}
            content = str(delta.get("text") or "")
            if not content:
                content = str(delta.get("content") or "")
            if not content:
                content = str(delta.get("partial_json") or "")
            return content, None
        if event_type == "message_delta":
            delta = chunk.get("delta") if isinstance(chunk.get("delta"), dict) else {}
            finish_reason = delta.get("stop_reason") or chunk.get("stop_reason")
            return "", finish_reason
        if event_type in {"message_stop", "content_block_stop"}:
            return "", chunk.get("stop_reason")

        # OpenAI responses-style SSE events (also used by some gateways):
        # - response.output_text.delta {"delta":"..."}
        # - response.output_text.done {"text":"..."}
        # - response.output_item.done {"item": {"type":"message", "content":[{"type":"output_text","text":"..."}]}}
        # - response.completed {"response": {...}}
        if event_type == "response.output_text.delta":
            return str(chunk.get("delta") or ""), None
        if event_type == "response.output_text.done":
            return str(chunk.get("text") or ""), None
        if event_type == "response.output_item.done":
            item = chunk.get("item") if isinstance(chunk.get("item"), dict) else {}
            item_text = self._extract_text_from_content(item.get("content"))
            return item_text, None
        if event_type == "response.completed":
            response_obj = chunk.get("response") if isinstance(chunk.get("response"), dict) else {}
            full_text = self._extract_text_from_response(response_obj) if response_obj else ""
            finish_reason = self._extract_finish_reason_from_response(response_obj) if response_obj else None
            return full_text, finish_reason

        text = self._extract_text_from_content(chunk.get("content"))
        if text:
            return text, chunk.get("stop_reason")

        return "", None

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
            if content.get("type") == "tool_use":
                import json as _json
                return f"[TOOL_USE: {content.get('name')}] {_json.dumps(content.get('input', {}), ensure_ascii=False)}"

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

        # KIE responses may return input/output token fields directly.
        if provider_prompt <= 0:
            provider_prompt = _to_int(normalized.get("input_tokens"))
            if provider_prompt > 0:
                normalized["prompt_tokens"] = provider_prompt
        if provider_completion <= 0:
            provider_completion = _to_int(normalized.get("output_tokens"))
            if provider_completion > 0:
                normalized["completion_tokens"] = provider_completion

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
        """KIE LLM request supporting both chat/completions and responses transports."""
        cfg = dict(extra_config or {})

        _, resolved_model, url, transport_kind = self._resolve_kie_llm_url(base_url, model)
        endpoint_label = "responses" if transport_kind == "responses" else "chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        if transport_kind == "responses":
            instructions, response_input = self._build_kie_responses_input(messages)
            payload = {
                "model": resolved_model,
                "input": response_input,
                "stream": False,
            }
            if instructions:
                payload["instructions"] = instructions
            payload.update(self._extract_kie_responses_options(cfg))
        else:
            payload = {
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
            f"provider=kie model={resolved_model} endpoint={endpoint_label} url={url} messages={len(messages or [])} "
            f"prompt_chars={prompt_chars} max_tokens={payload.get('max_tokens')} "
            f"max_completion_tokens={payload.get('max_completion_tokens')} "
            f"max_output_tokens={payload.get('max_output_tokens')} "
            f"cap_source={cap_source} "
            f"has_tools={bool(payload.get('tools'))} has_response_format={bool(payload.get('response_format'))} "
            f"include_thoughts={payload.get('include_thoughts')}"
        )

        timeout = max(90, self._get_provider_read_timeout_seconds("kie"))

        def _do_post():
            return requests.post(url, json=payload, headers=headers, timeout=timeout)

        try:
            resp = await asyncio.to_thread(_do_post)
        except requests.exceptions.Timeout as exc:
            human_summary = self._build_human_readable_transport_error_summary(
                provider="kie",
                model=resolved_model,
                error_kind="ambiguous_submit_transport",
                error_text=exc,
            )
            _debug_log(f"[DEBUG][LLM][KIE] Timeout before response: {exc}", "error")
            logger.error("%s", human_summary)
            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": "kie",
                "category": "LLM",
                "url": url,
                "model": resolved_model,
                "error_kind": "ambiguous_submit_transport",
                "error_text": str(exc),
                "human_summary": human_summary,
            })
            self._raise_ambiguous_submit_error("kie", resolved_model, exc, url)
        except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError) as exc:
            human_summary = self._build_human_readable_transport_error_summary(
                provider="kie",
                model=resolved_model,
                error_kind="connection",
                error_text=exc,
            )
            _debug_log(f"[DEBUG][LLM][KIE] Connection failed before response: {exc}", "error")
            logger.error("%s", human_summary)
            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": "kie",
                "category": "LLM",
                "url": url,
                "model": resolved_model,
                "error_kind": "connection",
                "error_text": str(exc),
                "human_summary": human_summary,
            })
            raise Exception(self._vendor_failed_message("kie", f"Connection failed before response: {exc}"))
        _debug_log(
            f"[DEBUG][LLM][KIE] Response | status={resp.status_code} body_preview_len=800 body_preview={_strip_base64_from_log(resp.text[:800])}"
        )

        if resp.status_code != 200:
            human_summary = self._build_human_readable_http_error_summary(
                provider="kie",
                model=resolved_model,
                status_code=resp.status_code,
                response_text=resp.text[:500],
            )
            logger.warning("%s", human_summary)
            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": "kie",
                "category": "LLM",
                "url": url,
                "model": resolved_model,
                "status_code": resp.status_code,
                "response_text": resp.text[:500],
                "human_summary": human_summary,
            })
            raise Exception(f"KIE {endpoint_label} failed {resp.status_code}: {resp.text[:500]}")

        data = resp.json()

        # KIE may return HTTP 200 with an error payload like {"code":500,"msg":"..."}
        kie_code = data.get("code")
        if kie_code is not None and str(kie_code) != "200" and "choices" not in data:
            err_msg = data.get("msg") or data.get("message") or data.get("error") or str(data)
            raise Exception(f"KIE {endpoint_label} error code={kie_code}: {err_msg}")

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

    def _extract_kie_responses_options(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Whitelist and normalize KIE responses API options."""
        safe_cfg = dict(cfg or {})

        out: Dict[str, Any] = {}
        direct_keys = {
            "temperature",
            "top_p",
            "max_output_tokens",
            "tools",
            "tool_choice",
            "metadata",
            "reasoning",
            "stop",
            "seed",
        }

        for key, value in safe_cfg.items():
            if str(key).startswith("__"):
                continue
            if key in {"model", "messages", "stream", "input"}:
                continue
            if key in direct_keys:
                out[key] = value

        if "max_output_tokens" not in out:
            for candidate in ("max_tokens", "max_completion_tokens"):
                value = safe_cfg.get(candidate)
                try:
                    parsed = int(value)
                except Exception:
                    parsed = 0
                if parsed > 0:
                    out["max_output_tokens"] = parsed
                    break

        if "reasoning" not in out:
            effort = str(safe_cfg.get("reasoning_effort") or "").strip().lower()
            if effort in {"low", "medium", "high"}:
                out["reasoning"] = {"effort": effort}

        tools = out.get("tools")
        if isinstance(tools, list):
            normalized_tools: List[Dict[str, Any]] = []
            for item in tools:
                if isinstance(item, dict) and item.get("type"):
                    normalized_tools.append(item)
                elif isinstance(item, str) and item.strip():
                    normalized_tools.append({"type": item.strip()})
            out["tools"] = normalized_tools

        return out

    def _extract_n1n_responses_options(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Whitelist and normalize n1n responses API options."""
        safe_cfg = dict(cfg or {})
        out: Dict[str, Any] = {}
        direct_keys = {
            "temperature",
            "top_p",
            "max_output_tokens",
            "tools",
            "tool_choice",
            "metadata",
            "reasoning",
            "stop",
            "seed",
        }

        for key, value in safe_cfg.items():
            if str(key).startswith("__"):
                continue
            if key in {"model", "messages", "stream", "input"}:
                continue
            if key in direct_keys:
                out[key] = value

        if "max_output_tokens" not in out:
            for candidate in ("max_tokens", "max_completion_tokens"):
                value = safe_cfg.get(candidate)
                try:
                    parsed = int(value)
                except Exception:
                    parsed = 0
                if parsed > 0:
                    out["max_output_tokens"] = parsed
                    break

        return out

    def _build_n1n_responses_input(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert chat-style messages to n1n /responses input schema."""
        response_input: List[Dict[str, Any]] = []
        for message in messages or []:
            if not isinstance(message, dict):
                continue
            role = str(message.get("role") or "user").strip().lower() or "user"
            if role not in {"system", "user", "assistant"}:
                role = "user"
            content_text = self._extract_text_from_content(message.get("content"))
            response_input.append({
                "role": role,
                "content": content_text or "",
            })
        return response_input

    def _resolve_n1n_llm_url(self, base_url: str, endpoint_hint: str = "") -> str:
        """Resolve canonical n1n responses URL, preferring /v1/responses."""
        hinted = str(endpoint_hint or "").strip()
        if hinted:
            if hinted.startswith("http"):
                normalized_hint = hinted.rstrip("/")
                hint_lower = normalized_hint.lower()
                if hint_lower.endswith("/chat/completions"):
                    return re.sub(r"/chat/completions/?$", "/responses", normalized_hint, flags=re.IGNORECASE)
                if hint_lower.endswith("/responses"):
                    return normalized_hint
                if hint_lower.endswith("/v1"):
                    return f"{normalized_hint}/responses"
                return f"{normalized_hint}/responses"
            root_from_base = (base_url or "https://api.n1n.ai").rstrip("/")
            return f"{root_from_base}/{hinted.lstrip('/')}".rstrip("/")

        root = (base_url or "https://api.n1n.ai").strip().rstrip("/")
        lower_root = root.lower()
        if lower_root.endswith("/chat/completions"):
            return re.sub(r"/chat/completions/?$", "/responses", root, flags=re.IGNORECASE)
        if lower_root.endswith("/responses"):
            return root
        if lower_root.endswith("/v1"):
            return f"{root}/responses"
        return f"{root}/v1/responses"

    def _build_kie_responses_input(self, messages: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
        """Convert chat messages into KIE responses API input format."""
        instructions_parts: List[str] = []
        response_input: List[Dict[str, Any]] = []

        for message in messages or []:
            if not isinstance(message, dict):
                continue

            role = str(message.get("role") or "user").strip().lower() or "user"
            raw_content = message.get("content")

            if role == "system":
                text = self._extract_text_from_content(raw_content)
                if text:
                    instructions_parts.append(text)
                continue

            if role not in {"user", "assistant"}:
                role = "user"

            content_parts: List[Dict[str, Any]] = []

            if isinstance(raw_content, list):
                for part in raw_content:
                    if isinstance(part, dict):
                        part_type = str(part.get("type") or "").strip().lower()
                        if part_type in {"text", "input_text"}:
                            text = str(part.get("text") or "").strip()
                            if text:
                                content_parts.append({"type": "input_text", "text": text})
                            continue

                        if part_type == "image_url":
                            image_value = part.get("image_url")
                            if isinstance(image_value, dict):
                                image_url = str(image_value.get("url") or "").strip()
                            else:
                                image_url = str(image_value or "").strip()
                            if image_url:
                                content_parts.append({"type": "input_image", "image_url": image_url})
                            continue

                    fallback_text = self._extract_text_from_content(part)
                    if fallback_text:
                        content_parts.append({"type": "input_text", "text": fallback_text})
            else:
                text = self._extract_text_from_content(raw_content)
                if text:
                    content_parts.append({"type": "input_text", "text": text})

            if not content_parts:
                content_parts.append({"type": "input_text", "text": ""})

            response_input.append({
                "role": role,
                "content": content_parts,
            })

        instructions = "\n\n".join(chunk for chunk in instructions_parts if chunk).strip()
        return instructions, response_input

    def _resolve_kie_llm_url(self, base_url: str, model: str) -> Tuple[str, str, str, str]:
        """Normalize KIE URL and resolve transport endpoint.

        Returns: (root, resolved_model, url, transport_kind)
        transport_kind is either "chat_completions" or "responses".
        """
        root = (base_url or "https://api.kie.ai").strip().rstrip("/")
        lower_root = root.lower()

        # Normalize model aliases first.
        kie_llm_alias = {
            "claude-opus-4.5": "claude-opus-4-5",
            "claude-sonnet-4.5": "claude-sonnet-4-5",
        }
        resolved_model = kie_llm_alias.get(model, model)
        if resolved_model != model:
            logger.info("KIE LLM model remapped | from=%s to=%s", model, resolved_model)

        # Responses transport (e.g. https://api.kie.ai/codex/v1/responses)
        responses_match = re.search(r"/(?:codex/)?v1/responses(?:/|$)", lower_root)
        if responses_match:
            match_end = responses_match.end()
            canonical_endpoint = root[:match_end].rstrip("/")
            canonical_root = root[:responses_match.start()].rstrip("/")
            if not canonical_root:
                canonical_root = "https://api.kie.ai"

            return canonical_root, resolved_model, canonical_endpoint, "responses"

        # If a full endpoint was saved (including model path), collapse back to provider root.
        root = re.sub(r"/[^/]+/v1/chat/completions/?$", "", root, flags=re.IGNORECASE)

        # Strip other legacy fragments if present.
        for suffix in ("/api/v1/jobs", "/v1/chat/completions", "/v1", "/responses"):
            if root.endswith(suffix):
                root = root[: -len(suffix)].rstrip("/")

        # For KIE GPT family, prefer canonical responses endpoint by default.
        if str(resolved_model or "").strip().lower().startswith("gpt-"):
            url = f"{root}/codex/v1/responses"
            return root, resolved_model, url, "responses"

        url = f"{root}/{resolved_model}/v1/chat/completions"
        return root, resolved_model, url, "chat_completions"

    def _extract_finish_reason_from_response(self, full_response: Dict[str, Any]) -> Any:
        choices = full_response.get("choices") or []
        if not isinstance(choices, list):
            stop_reason = full_response.get("stop_reason")
            if stop_reason is not None and str(stop_reason).strip() != "":
                return stop_reason
            return None

        for choice in choices:
            if not isinstance(choice, dict):
                continue
            reason = choice.get("finish_reason")
            if reason is not None and str(reason).strip() != "":
                return reason

        # KIE responses API often reports terminal status at top-level.
        status = full_response.get("status")
        if status is not None and str(status).strip() != "":
            return status

        stop_reason = full_response.get("stop_reason")
        if stop_reason is not None and str(stop_reason).strip() != "":
            return stop_reason
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
        # KIE responses API shape:
        # {"output":[{"type":"message","content":[{"type":"output_text","text":"..."}]}], ...}
        output_items = full_response.get("output") or []
        if isinstance(output_items, list) and output_items:
            output_chunks: List[str] = []
            for item in output_items:
                if not isinstance(item, dict):
                    continue
                if str(item.get("type") or "").strip().lower() != "message":
                    continue
                content_text = self._extract_text_from_content(item.get("content"))
                if content_text:
                    output_chunks.append(content_text)
            if output_chunks:
                return "\n".join(output_chunks).strip()

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

    def _build_human_readable_response_summary(
        self,
        full_response: Dict[str, Any],
        *,
        provider: Any,
        model: Any,
        status_code: Any,
    ) -> str:
        finish_reason = self._extract_finish_reason_from_response(full_response)
        finish_reason_norm = str(finish_reason or "").strip().lower().replace("-", "_")
        usage = full_response.get("usage") or {}
        content = self._extract_text_from_response(full_response)
        output_chars = len(content) if isinstance(content, str) else len(str(content or ""))
        extraction = self._build_extraction_diagnostics(full_response)
        choices = full_response.get("choices") or []
        first_choice = choices[0] if isinstance(choices, list) and choices else {}
        first_keys = list(first_choice.keys()) if isinstance(first_choice, dict) else []

        prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        completion_tokens = usage.get("completion_tokens") or usage.get("output_tokens") or 0
        total_tokens = usage.get("total_tokens") or 0
        try:
            prompt_tokens = int(prompt_tokens or 0)
        except Exception:
            prompt_tokens = 0
        try:
            completion_tokens = int(completion_tokens or 0)
        except Exception:
            completion_tokens = 0
        try:
            total_tokens = int(total_tokens or 0)
        except Exception:
            total_tokens = 0

        parts: List[str] = []
        parts.append(
            f"LLM 返回摘要：供应商={self._vendor_label(provider)}，模型={str(model or full_response.get('model') or 'unknown')}，HTTP={status_code}。"
        )

        if status_code == 200:
            parts.append("接口调用成功。")
        else:
            parts.append("接口返回异常状态。")

        if self._is_blocked_response(full_response):
            parts.append("本次返回被内容安全策略拦截。")
        elif self._is_length_limited_finish_reason(finish_reason):
            parts.append("本次响应因长度上限停止，当前分段可能不完整；是否形成最终缺失，需要结合后续续写或业务完整性校验判断。")
        elif finish_reason_norm in {"stop", "completed", "complete", "end_turn"}:
            parts.append("模型正常结束返回。")
        elif finish_reason_norm:
            parts.append(f"结束原因={finish_reason_norm}。")
        else:
            parts.append("未返回明确的结束原因。")

        if output_chars > 0:
            parts.append(f"已提取到正文，长度约 {output_chars} 个字符。")
        else:
            parts.append("未提取到可用正文。")
            if first_keys:
                parts.append(f"首个 choice 字段={first_keys}。")

        if total_tokens == 0 and prompt_tokens == 0 and completion_tokens == 0:
            parts.append("token 统计全部为 0，这通常表示供应商没有正确回传 usage，不能据此判断真实消耗。")
        else:
            parts.append(
                f"token 统计：输入={prompt_tokens}，输出={completion_tokens}，合计={total_tokens or (prompt_tokens + completion_tokens)}。"
            )

        if extraction.get("choices_count") and output_chars == 0:
            parts.append(
                f"本次返回包含 {extraction.get('choices_count')} 个 choice，但正文抽取结果为空，建议检查供应商响应结构或日志截断。"
            )

        return " ".join(parts)

    def _build_human_readable_http_error_summary(
        self,
        *,
        provider: Any,
        model: Any,
        status_code: Any,
        response_text: Any,
    ) -> str:
        vendor = self._vendor_label(provider)
        model_text = str(model or "unknown")
        body = str(response_text or "").strip()
        body_lower = body.lower()

        try:
            status = int(status_code)
        except Exception:
            status = 0

        reason = "上游接口返回异常。"
        if status == 400:
            reason = "请求参数不符合供应商要求，供应商拒绝处理。"
        elif status == 401:
            reason = "供应商鉴权失败，通常是 API Key 无效、缺失或已失效。"
        elif status == 402:
            reason = "供应商侧余额不足或当前账号无权调用该模型。"
        elif status == 403:
            reason = "供应商拒绝访问，通常是权限、地域或模型白名单限制。"
        elif status == 404:
            reason = "供应商接口地址或模型路径不存在，可能是路由或模型名配置错误。"
        elif status == 408:
            reason = "供应商处理超时，本次请求没有在时限内完成。"
        elif status == 409:
            reason = "供应商返回冲突状态，通常表示任务状态或参数组合不被接受。"
        elif status == 413:
            reason = "请求内容过大，超出了供应商允许的输入限制。"
        elif status == 422:
            reason = "请求结构可解析，但字段值不符合供应商要求。"
        elif status == 429:
            reason = "供应商限流或并发超限，需要稍后重试。"
        elif status == 500:
            reason = "供应商服务内部报错，不是当前业务参数可以直接修复的问题。"
        elif status == 502:
            reason = "供应商网关或上游链路异常，本次调用未得到有效结果。"
        elif status == 503:
            reason = "供应商服务暂时不可用，通常是维护、过载或短时故障。"
        elif status == 504:
            reason = "供应商网关等待上游超时，本次调用未在时限内完成。"
        elif status == 524:
            reason = "供应商前置网关等待上游响应超时（常见于 Cloudflare 524），无法确认任务是否已被受理。"

        body_hint = ""
        if body:
            if "insufficient" in body_lower or "余额" in body or "quota" in body_lower:
                body_hint = "返回内容提示额度、余额或配额不足。"
            elif "invalid api key" in body_lower or "unauthorized" in body_lower or "authentication" in body_lower:
                body_hint = "返回内容提示鉴权失败。"
            elif "rate limit" in body_lower or "too many requests" in body_lower:
                body_hint = "返回内容提示触发了限流。"
            elif "model" in body_lower and ("not found" in body_lower or "does not exist" in body_lower):
                body_hint = "返回内容提示模型不存在或当前账号不可用。"

        summary = f"LLM 异常摘要：供应商={vendor}，模型={model_text}，HTTP={status or status_code}。{reason}"
        if body_hint:
            summary += f" {body_hint}"
        summary += " 建议先检查供应商配置、模型名、额度和限流状态。"
        return summary

    def _build_human_readable_transport_error_summary(
        self,
        *,
        provider: Any,
        model: Any,
        error_kind: str,
        error_text: Any,
    ) -> str:
        vendor = self._vendor_label(provider)
        model_text = str(model or "unknown")
        kind = str(error_kind or "unknown").strip().lower()
        detail = str(error_text or "").strip()

        if kind == "timeout":
            reason = "请求已经发出，但在等待供应商返回时超时，没有拿到有效响应。"
        elif kind == "proxy_retry_timeout":
            reason = "代理链路失败后已切换直连重试，但直连仍然超时，没有拿到有效响应。"
        elif kind == "connection":
            reason = "请求未能稳定连接到供应商，可能是网络、证书、代理或上游服务不稳定。"
        else:
            reason = "请求在拿到 HTTP 响应之前就失败了，未形成可解析的返回结果。"

        summary = f"LLM 异常摘要：供应商={vendor}，模型={model_text}。{reason}"
        if detail:
            summary += f" 原始异常={detail[:180]}。"
        summary += " 建议检查网络连通性、代理配置、供应商服务状态与超时设置。"
        return summary

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
                 human_summary = self._build_human_readable_http_error_summary(
                     provider="doubao",
                     model=model,
                     status_code=response.status_code,
                     response_text=response.text[:500],
                 )
                 logger.warning("%s", human_summary)
                 self._safe_log_json("LLM_RESPONSE_ERROR", {
                     "provider": "doubao",
                     "category": "LLM",
                     "url": url,
                     "model": model,
                     "status_code": response.status_code,
                     "response_text": response.text[:500],
                     "human_summary": human_summary,
                 })
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
            if self._is_runtime_shutdown_error(e):
                logger.error(
                    "LLM multimodal request aborted: runtime executor/event loop is shutting down | provider=doubao model=%s err=%s",
                    model,
                    str(e)[:200],
                )
                return {"content": "Error: 服务正在关闭或重启，线程池暂不可用，请稍后重试。", "usage": {}}
            error_kind = "exception"
            if isinstance(e, requests.exceptions.Timeout):
                error_kind = "timeout"
            elif isinstance(e, (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError)):
                error_kind = "connection"
            human_summary = self._build_human_readable_transport_error_summary(
                provider="doubao",
                model=model,
                error_kind=error_kind,
                error_text=e,
            )
            logger.error(f"Doubao Multimodal failed: {e}")
            logger.error("%s", human_summary)
            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": "doubao",
                "category": "LLM",
                "url": url,
                "model": model,
                "error_kind": error_kind,
                "error_text": str(e),
                "human_summary": human_summary,
            })
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
                __override_fallback_candidates = active_cfg_obj.get('__override_fallback_candidates')
                if __override_fallback_candidates is not None:
                    override_ids = [int(x) for x in __override_fallback_candidates]
                    fallback_candidates = agent_service.get_fallback_configs_by_ids(override_ids)
                else:
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
                if self._is_runtime_shutdown_error(exc):
                    logger.warning(
                        "[llm_fallback] intent aborted: runtime is shutting down, skip fallback chain | provider=%s model=%s",
                        attempt_provider,
                        attempt_model,
                    )
                    raise
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

        if not api_key and config.get("provider") != "apiyi2":
             raise ValueError("API Key missing in config")

        extra_config = dict(config.get("config", {}) or {})
        extra_config.setdefault("__provider", config.get("provider") or self._infer_provider(base_url, model))
        provider = extra_config.get("__provider") or config.get("provider") or self._infer_provider(base_url, model)

        try:
            if str(provider or "").strip().lower() in {"kie", "n1n"}:
                logger.info(
                    "chat_completion routing: provider=%s model=%s mode=stream_aggregate",
                    provider,
                    model,
                )
                return await self._collect_openai_compatible_text_response(
                    base_url,
                    api_key,
                    model,
                    messages,
                    extra_config,
                )

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
        except AmbiguousLLMTransportError:
            raise
        except Exception as e:
            if str(provider or "").strip().lower() in {"kie", "n1n"} and self._is_ambiguous_submit_transport_error(e):
                self._raise_ambiguous_submit_error(provider, model, e, base_url)
            logger.error(f"LLM Raw Completion failed: {e}")
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

    async def _collect_openai_compatible_text_response(
        self,
        base_url: str,
        api_key: str,
        model: str,
        messages: List[Dict],
        extra_config: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Collect streamed OpenAI-compatible output and expose generic text response fields."""
        content_parts: List[str] = []
        usage: Dict[str, Any] = {}
        finish_reason = "stop"

        async for event in self._raw_llm_request_stream(base_url, api_key, model, messages, extra_config):
            if event.get("type") == "token":
                content_parts.append(event.get("content", ""))
            elif event.get("type") == "done":
                if event.get("usage"):
                    usage = event["usage"]
                if event.get("finish_reason"):
                    finish_reason = event["finish_reason"]

        raw_content = "".join(content_parts)
        content = self._sanitize_response_content(raw_content)
        logger.info(
            "[_collect_openai_compatible_text_response] content length=%d finish_reason=%s",
            len(content or ""),
            finish_reason,
        )
        return {
            "raw_content": raw_content,
            "content": content,
            "usage": usage,
            "finish_reason": finish_reason,
            "token_limit_hints": [],
            "extraction_diagnostics": {
                "stream_aggregated": True,
                "provider": (extra_config or {}).get("__provider") or self._infer_provider(base_url, model),
            },
        }

    async def _call_openai_compatible(self, base_url: str, api_key: str, model: str, messages: List[Dict], extra_config: Dict[str, Any] = None) -> Dict[str, Any]:
        # Internally use streaming to bypass gateway 60s/300s idle timeouts
        aggregated = await self._collect_openai_compatible_text_response(
            base_url,
            api_key,
            model,
            messages,
            extra_config,
        )
        content = str(aggregated.get("content") or "")
        usage = aggregated.get("usage") or {}
        finish_reason = aggregated.get("finish_reason") or "stop"
        
        logger.info("[_call_openai_compatible] extracted content length=%d snippet=%s", len(content or ""), (content or "")[:200])
        logger.info("[_call_openai_compatible] sanitized content length=%d snippet=%s", len(content or ""), (content or "")[:200])
        
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
        original_base_url = base_url
        if not base_url:
            base_url = "https://api.openai.com/v1"  # Default to OpenAI if not set

        resolved_category = str((extra_config or {}).get("__resolved_category") or "LLM").strip().upper()
        provider = (extra_config or {}).get("__provider") or self._infer_provider(base_url, model)

        if provider == "kie":
            model = {
                "claude-opus-4.5": "claude-opus-4-5",
                "claude-sonnet-4.5": "claude-sonnet-4-5",
                "claude-opus-4.6": "claude-opus-4-6",
                "claude-sonnet-4.6": "claude-sonnet-4-6",
            }.get(model, model)

        use_claude_api = self._should_use_claude_api(provider, model)
        logger.info(
            "LLM route decision (full): provider=%s model=%s use_claude_api=%s category=%s",
            provider,
            model,
            use_claude_api,
            resolved_category,
        )

        if not original_base_url and use_claude_api:
            base_url = "https://api.anthropic.com"
        
        if provider == "apiyi" or provider == "apiyi2":
            if not original_base_url or original_base_url == "https://api.apiyi.com":
                base_url = "https://api.apiyi.com/v1"
            else:
                base_url = original_base_url.rstrip("/")
                if not base_url.endswith("/v1"):
                     base_url = f"{base_url}/v1"
            
        if provider == "kie" and resolved_category == "LLM" and not use_claude_api:
            return await self._raw_kie_llm_request_full(base_url, api_key, model, messages, extra_config)
        if provider == "grsai" and resolved_category == "LLM":
            base_url = self._normalize_grsai_llm_base_url(base_url)

        configured_endpoint = ((extra_config or {}).get("endpoint") or "").strip()
        if provider == "zlhub":
            configured_endpoint = "" 

        if configured_endpoint and not configured_endpoint.startswith("http"):
            configured_endpoint = f"{base_url.rstrip('/')}/{configured_endpoint.lstrip('/')}"
            # De-duplicate /v1/v1/ that can occur when base_url already ends with /v1
            # and the endpoint_hint also starts with /v1/ (e.g. apiyi2 base_url normalization)
            import re as _re
            configured_endpoint = _re.sub(r'(/v1)/v1(?=/|$)', r'\1', configured_endpoint)

        n1n_use_responses = provider == "n1n" and resolved_category == "LLM" and not use_claude_api

        if use_claude_api and resolved_category == "LLM":
            url = self._resolve_claude_llm_url(base_url, configured_endpoint)
            url_source = "claude.messages"
        elif n1n_use_responses:
            url = self._resolve_n1n_llm_url(base_url, configured_endpoint)
            url_source = "n1n.responses"
        elif configured_endpoint and resolved_category == "LLM":
            endpoint_lower = configured_endpoint.lower()
            if "/chat/completions" in endpoint_lower or provider == "zlhub" or "createtask" in endpoint_lower:
                url = configured_endpoint.rstrip("/")
            else:
                url = f"{configured_endpoint.rstrip('/')}/chat/completions"
            url_source = "config.endpoint"
        elif configured_endpoint and resolved_category != "LLM":
            url = configured_endpoint.rstrip("/")
            url_source = "config.endpoint(non-llm)"
        else:
            url = base_url.rstrip("/")
            if resolved_category == "LLM" and not url.endswith("/chat/completions") and provider != "zlhub" and "createtask" not in url.lower():
                url = f"{url}/chat/completions"
            url_source = "base_url"

        logger.info(
            "LLM route target (full): provider=%s model=%s use_claude_api=%s category=%s url_source=%s url=%s",
            provider,
            model,
            use_claude_api,
            resolved_category,
            url_source,
            url,
        )
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        if use_claude_api:
            headers.setdefault("x-api-key", api_key)
            headers.setdefault("anthropic-version", "2023-06-01")
        
        if use_claude_api and resolved_category == "LLM":
            payload = self._build_claude_payload_from_messages(
                model=model,
                messages=messages,
                stream=False,
                extra_config=extra_config,
                provider=provider,
            )
        elif n1n_use_responses:
            payload = {
                "model": model,
                "input": self._build_n1n_responses_input(messages),
                "stream": False,
            }
            payload.update(self._extract_n1n_responses_options(extra_config or {}))
        else:
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "temperature": 0.7
            }

        if extra_config and not (use_claude_api and resolved_category == "LLM") and not n1n_use_responses:
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
                with requests.Session() as session:
                    session.trust_env = False
                    return session.post(url, **kwargs)
            return requests.post(url, **kwargs)

        try:
            response = await asyncio.to_thread(_request, False)
        except RuntimeError as e:
            if self._is_runtime_shutdown_error(e):
                logger.error(
                    "LLM request aborted: runtime executor/event loop is shutting down | provider=%s model=%s url=%s err=%s",
                    provider,
                    model,
                    url,
                    str(e)[:200],
                )
                raise Exception(self._vendor_failed_message(provider, "服务正在关闭或重启，线程池暂不可用，请稍后重试"))
            raise
        except (requests.exceptions.ProxyError, requests.exceptions.SSLError) as e:
            _debug_log(f"[DEBUG][LLM][{provider}] Connection failed ({str(e)[:120]}), retrying without proxy...", "warning")
            logger.warning(f"Connection failed ({str(e)}). Retrying without proxy (connect_timeout={DEFAULT_LLM_NO_PROXY_CONNECT_TIMEOUT_SECONDS}s)...")
            try:
                response = await asyncio.to_thread(_request, True, max(3, DEFAULT_LLM_NO_PROXY_CONNECT_TIMEOUT_SECONDS))
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e2:
                human_summary = self._build_human_readable_transport_error_summary(
                    provider=provider,
                    model=model,
                    error_kind="ambiguous_submit_transport",
                    error_text=e2,
                )
                _debug_log(f"[DEBUG][LLM][{provider}] No-proxy retry ended with ambiguous transport failure: {e2}", "error")
                logger.error("%s", human_summary)
                self._safe_log_json("LLM_RESPONSE_ERROR", {
                    "provider": provider,
                    "category": resolved_category,
                    "url": url,
                    "model": model,
                    "error_kind": "ambiguous_submit_transport",
                    "error_text": str(e2),
                    "human_summary": human_summary,
                    "resolved_source": (extra_config or {}).get("__resolved_source"),
                    "resolved_setting_id": (extra_config or {}).get("__resolved_setting_id"),
                })
                self._raise_ambiguous_submit_error(provider, model, e2, url)
            except Exception as e2:
                human_summary = self._build_human_readable_transport_error_summary(
                    provider=provider,
                    model=model,
                    error_kind="connection",
                    error_text=e2,
                )
                logger.error(f"No-proxy retry also failed: {e2}")
                logger.error("%s", human_summary)
                self._safe_log_json("LLM_RESPONSE_ERROR", {
                    "provider": provider,
                    "category": resolved_category,
                    "url": url,
                    "model": model,
                    "error_kind": "connection",
                    "error_text": str(e2),
                    "human_summary": human_summary,
                    "resolved_source": (extra_config or {}).get("__resolved_source"),
                    "resolved_setting_id": (extra_config or {}).get("__resolved_setting_id"),
                })
                raise Exception(self._vendor_failed_message(provider, e2))
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            human_summary = self._build_human_readable_transport_error_summary(
                provider=provider,
                model=model,
                error_kind="ambiguous_submit_transport",
                error_text=e,
            )
            _debug_log(f"[DEBUG][LLM][{provider}] Ambiguous transport failure before response; automatic retry disabled: {e}", "error")
            logger.error("%s", human_summary)
            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": provider,
                "category": resolved_category,
                "url": url,
                "model": model,
                "error_kind": "ambiguous_submit_transport",
                "error_text": str(e),
                "human_summary": human_summary,
                "resolved_source": (extra_config or {}).get("__resolved_source"),
                "resolved_setting_id": (extra_config or {}).get("__resolved_setting_id"),
            })
            self._raise_ambiguous_submit_error(provider, model, e, url)
        
        _debug_log(f"[DEBUG][LLM][{provider}] Response | status={response.status_code} model={model} url={url} body={_strip_base64_from_log(response.text[:500])}")

        if response.status_code != 200:
            provider = (extra_config or {}).get("__provider") or (extra_config or {}).get("provider") or self._infer_provider(base_url, model)
            resolved_setting_id = (extra_config or {}).get("__resolved_setting_id")
            resolved_source = (extra_config or {}).get("__resolved_source")
            if str(provider or "").strip().lower() in {"n1n", "kie"} and int(response.status_code or 0) == 524:
                self._raise_ambiguous_submit_error(provider, model, f"HTTP 524: {response.text[:300]}", url)
            human_summary = self._build_human_readable_http_error_summary(
                provider=provider,
                model=model,
                status_code=response.status_code,
                response_text=response.text,
            )
            logger.warning("%s", human_summary)
            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": provider,
                "category": resolved_category,
                "url": url,
                "model": model,
                "status_code": response.status_code,
                "response_text": response.text,
                "human_summary": human_summary,
                "resolved_source": resolved_source,
                "resolved_setting_id": resolved_setting_id,
            })
            raw_reason = f"API Error {response.status_code} [provider={provider}, model={model}, endpoint={url}, setting_id={resolved_setting_id}, source={resolved_source}]: {response.text}"
            raise Exception(self._vendor_failed_message(provider, raw_reason))

        try:
            data = response.json()
        except Exception as e:
            provider = (extra_config or {}).get("__provider") or (extra_config or {}).get("provider") or self._infer_provider(base_url, model)
            resolved_setting_id = (extra_config or {}).get("__resolved_setting_id")
            resolved_source = (extra_config or {}).get("__resolved_source")
            human_summary = f"LLM provider '{provider}' returned an invalid JSON response (Status {response.status_code})."
            logger.warning("%s | Exception: %s | Raw body snippet: %s", human_summary, e, response.text[:200])
            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": provider,
                "category": resolved_category,
                "url": url,
                "model": model,
                "status_code": response.status_code,
                "response_text": response.text[:2000],
                "human_summary": human_summary,
                "resolved_source": resolved_source,
                "resolved_setting_id": resolved_setting_id,
                "exception": str(e),
            })
            raw_reason = f"Invalid JSON response [provider={provider}, model={model}, status={response.status_code}]: {response.text[:200]}"
            raise Exception(self._vendor_failed_message(provider, raw_reason))

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
            human_summary = self._build_human_readable_response_summary(
                data,
                provider=provider,
                model=data.get("model") or model,
                status_code=response.status_code,
            )
            logger.info(
                "LLM Response: model=%s finish_reason=%s output_chars=%s usage=%s",
                data.get("model") or model,
                finish_reason,
                output_chars,
                usage,
            )
            logger.info("%s", human_summary)
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
                "human_summary": human_summary,
            })
            if self._is_length_limited_finish_reason(finish_reason):
                logger.warning(
                    "LLM segment stopped by length limit (finish_reason=length); current segment may be partial until continuation/integrity checks complete. prompt_chars=%s output_chars=%s max_tokens=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s usage=%s",
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
                    "segment_only": True,
                    "final_result_unknown": True,
                    "human_summary": "Current segment stopped by length limit; final completeness must be determined after continuation or business-level integrity checks.",
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
        
        if ("choices" in data and len(data["choices"]) > 0) or (use_claude_api and data.get("type") == "message"):
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
        original_base_url = base_url
        if not base_url:
            base_url = "https://api.openai.com/v1"

        resolved_category = str((extra_config or {}).get("__resolved_category") or "LLM").strip().upper()
        provider = (extra_config or {}).get("__provider") or self._infer_provider(base_url, model)

        if provider == "kie":
            model = {
                "claude-opus-4.5": "claude-opus-4-5",
                "claude-sonnet-4.5": "claude-sonnet-4-5",
                "claude-opus-4.6": "claude-opus-4-6",
                "claude-sonnet-4.6": "claude-sonnet-4-6",
            }.get(model, model)

        use_claude_api = self._should_use_claude_api(provider, model)
        logger.info(
            "LLM route decision (stream): provider=%s model=%s use_claude_api=%s category=%s",
            provider,
            model,
            use_claude_api,
            resolved_category,
        )

        if not original_base_url and use_claude_api:
            base_url = "https://api.anthropic.com"

        if not original_base_url and provider == "apiyi":
            base_url = "https://api.apiyi.com"

        if provider == "grsai" and resolved_category == "LLM":
            base_url = self._normalize_grsai_llm_base_url(base_url)

        # ── Build URL (same logic as _raw_llm_request_full) ──
        configured_endpoint = ((extra_config or {}).get("endpoint") or "").strip()
        if provider == "zlhub":
            configured_endpoint = "" 

        if configured_endpoint and not configured_endpoint.startswith("http"):
            configured_endpoint = f"{base_url.rstrip('/')}/{configured_endpoint.lstrip('/')}"
            import re as _re
            configured_endpoint = _re.sub(r'(/v1)/v1(?=/|$)', r'\1', configured_endpoint)

        resolved_model = model
        kie_transport_kind = "chat_completions"
        n1n_use_responses = provider == "n1n" and resolved_category == "LLM" and not use_claude_api
        
        if provider == "kie" and resolved_category == "LLM" and not use_claude_api:
            _, resolved_model, url, kie_transport_kind = self._resolve_kie_llm_url(base_url, model)
            url_source = "kie.model_path"
        elif n1n_use_responses:
            url = self._resolve_n1n_llm_url(base_url, configured_endpoint)
            url_source = "n1n.responses"
        elif use_claude_api and resolved_category == "LLM":
            url = self._resolve_claude_llm_url(base_url, configured_endpoint)
            url_source = "claude.messages"
        elif configured_endpoint and resolved_category == "LLM":
            endpoint_lower = configured_endpoint.lower()
            if "/chat/completions" in endpoint_lower or provider == "zlhub" or "createtask" in endpoint_lower:
                url = configured_endpoint.rstrip("/")
            else:
                url = f"{configured_endpoint.rstrip('/')}/chat/completions"
        elif configured_endpoint and resolved_category != "LLM":
            url = configured_endpoint.rstrip("/")
            url_source = "config.endpoint(non-llm)"
        else:
            url = base_url.rstrip("/")
            if resolved_category == "LLM" and not url.endswith("/chat/completions") and provider != "zlhub" and "createtask" not in url.lower():
                url = f"{url}/chat/completions"
            url_source = "base_url"

        if configured_endpoint and resolved_category == "LLM" and not use_claude_api and provider not in {"kie", "n1n"}:
            endpoint_lower = configured_endpoint.lower()
            if "/chat/completions" in endpoint_lower:
                url_source = "config.endpoint"
            else:
                url_source = "config.endpoint"

        logger.info(
            "LLM route target (stream): provider=%s model=%s use_claude_api=%s category=%s url_source=%s url=%s",
            provider,
            model,
            use_claude_api,
            resolved_category,
            url_source,
            url,
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if use_claude_api:
            headers.setdefault("x-api-key", api_key)
            headers.setdefault("anthropic-version", "2023-06-01")

        if use_claude_api and resolved_category == "LLM":
            payload = self._build_claude_payload_from_messages(
                model=model,
                messages=messages,
                stream=True,
                extra_config=extra_config,
                provider=provider,
            )
        elif n1n_use_responses:
            payload = {
                "model": model,
                "input": self._build_n1n_responses_input(messages),
                # n1n responses can return non-SSE JSON; force JSON mode for stable parsing.
                "stream": False,
            }
            payload.update(self._extract_n1n_responses_options(extra_config or {}))
        elif provider == "kie" and resolved_category == "LLM" and kie_transport_kind == "responses":
            instructions, response_input = self._build_kie_responses_input(messages)
            payload = {
                "model": resolved_model,
                "input": response_input,
                # KIE responses endpoint is more reliable in non-stream JSON mode.
                "stream": False,
            }
            if instructions:
                payload["instructions"] = instructions
        else:
            payload = {
                "model": resolved_model if (provider == "kie" and resolved_category == "LLM") else model,
                "messages": messages,
                "stream": True,
                "temperature": 0.7,
            }

        if provider == "kie" and resolved_category == "LLM":
            if kie_transport_kind == "responses":
                payload.update(self._extract_kie_responses_options(extra_config or {}))
            else:
                payload.update(self._extract_kie_chat_options(extra_config or {}))
        elif n1n_use_responses:
            pass
        elif extra_config and not (use_claude_api and resolved_category == "LLM"):
            for k, v in extra_config.items():
                if k not in ["model", "messages", "stream"] and not str(k).startswith("__"):
                    payload[k] = v

        self._safe_log_json("LLM_REQUEST", {
            "provider": provider,
            "category": resolved_category,
            "url": url,
            "url_source": url_source,
            "model": payload.get("model") or model,
            "headers": {
                **headers,
                "Authorization": "Bearer ***REDACTED***",
            },
            "payload": payload,
            "message_count": len(messages or []),
            "stream": True,
            "resolved_source": (extra_config or {}).get("__resolved_source"),
            "resolved_setting_id": (extra_config or {}).get("__resolved_setting_id"),
        })
        logger.info(
            "Calling LLM (stream): provider=%s model=%s url=%s messages=%d",
            provider, model, url, len(messages or []),
        )

        usage: Dict[str, Any] = {}
        finish_reason: Optional[str] = None
        token_batch_buf = ""

        timeout = httpx.Timeout(
            connect=30.0,
            read=float(self._get_provider_read_timeout_seconds(provider)),
            write=30.0,
            pool=30.0,
        )

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        error_text = error_body.decode("utf-8", errors="replace")[:500]
                        provider_lower = str(provider or "").strip().lower()
                        if provider_lower in {"n1n", "kie"} and int(response.status_code or 0) == 524:
                            self._raise_ambiguous_submit_error(
                                provider,
                                payload.get("model") or model,
                                f"HTTP 524: {error_text}",
                                url,
                            )
                        human_summary = self._build_human_readable_http_error_summary(
                            provider=provider,
                            model=payload.get("model") or model,
                            status_code=response.status_code,
                            response_text=error_text,
                        )
                        logger.warning("%s", human_summary)
                        self._safe_log_json("LLM_RESPONSE_ERROR", {
                            "provider": provider,
                            "category": resolved_category,
                            "url": url,
                            "model": payload.get("model") or model,
                            "status_code": response.status_code,
                            "response_text": error_text,
                            "human_summary": human_summary,
                            "resolved_source": (extra_config or {}).get("__resolved_source"),
                            "resolved_setting_id": (extra_config or {}).get("__resolved_setting_id"),
                            "stream": True,
                        })
                        raise Exception(
                            self._vendor_failed_message(
                                provider,
                                f"API Error {response.status_code}: {error_text}",
                            )
                        )

                    content_type = response.headers.get("content-type", "").lower()
                    if "application/json" in content_type and "event-stream" not in content_type:
                        body_bytes = await response.aread()
                        try:
                            import json as _json
                            full_json = _json.loads(body_bytes)
                        except Exception:
                            logger.error(f"Failed to parse JSON response on stream endpoint: {body_bytes[:200]}")
                            full_json = {}
                        text = self._extract_text_from_response(full_json)
                        if text:
                            yield {"type": "token", "content": text}
                        usage_res = full_json.get("usage", {})
                        if use_claude_api and not usage_res:
                            usage_res = full_json.get("usage", {})
                        finish_res = self._extract_finish_reason_from_response(full_json) or "stop"
                        yield {"type": "done", "usage": usage_res, "finish_reason": finish_res}
                        return

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
                        else:
                            response_obj = chunk.get("response") if isinstance(chunk.get("response"), dict) else {}
                            if response_obj.get("usage"):
                                usage = response_obj.get("usage")

                        content, chunk_finish_reason = self._extract_stream_chunk_text_and_finish(chunk)
                        if chunk_finish_reason:
                            finish_reason = chunk_finish_reason
                        if content:
                            if use_claude_api:
                                token_batch_buf += content
                                if len(token_batch_buf) >= 32 or "\n" in token_batch_buf:
                                    yield {"type": "token", "content": token_batch_buf}
                                    token_batch_buf = ""
                                    _last_yield_time = _asyncio.get_event_loop().time()
                            else:
                                yield {"type": "token", "content": content}
                                _last_yield_time = _asyncio.get_event_loop().time()

        except httpx.ConnectError as exc:
            human_summary = self._build_human_readable_transport_error_summary(
                provider=provider,
                model=payload.get("model") or model,
                error_kind="connection",
                error_text=exc,
            )
            logger.error("%s", human_summary)
            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": provider,
                "category": resolved_category,
                "url": url,
                "model": payload.get("model") or model,
                "error_kind": "connection",
                "error_text": str(exc),
                "human_summary": human_summary,
                "resolved_source": (extra_config or {}).get("__resolved_source"),
                "resolved_setting_id": (extra_config or {}).get("__resolved_setting_id"),
                "stream": True,
            })
            raise Exception(self._vendor_failed_message(provider, f"Connection failed: {exc}"))
        except httpx.ReadTimeout as exc:
            human_summary = self._build_human_readable_transport_error_summary(
                provider=provider,
                model=payload.get("model") or model,
                error_kind="ambiguous_submit_transport" if str(provider or "").strip().lower() == "kie" else "timeout",
                error_text=exc,
            )
            logger.error("%s", human_summary)
            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": provider,
                "category": resolved_category,
                "url": url,
                "model": payload.get("model") or model,
                "error_kind": "ambiguous_submit_transport" if str(provider or "").strip().lower() == "kie" else "timeout",
                "error_text": str(exc),
                "human_summary": human_summary,
                "resolved_source": (extra_config or {}).get("__resolved_source"),
                "resolved_setting_id": (extra_config or {}).get("__resolved_setting_id"),
                "stream": True,
            })
            if str(provider or "").strip().lower() == "kie":
                self._raise_ambiguous_submit_error(provider, payload.get("model") or model, exc, url)
            raise Exception(self._vendor_failed_message(provider, f"Read timeout: {exc}"))
        except Exception as exc:
            human_summary = self._build_human_readable_transport_error_summary(
                provider=provider,
                model=payload.get("model") or model,
                error_kind="exception",
                error_text=exc,
            )
            logger.error("%s", human_summary)
            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": provider,
                "category": resolved_category,
                "url": url,
                "model": payload.get("model") or model,
                "error_kind": "exception",
                "error_text": str(exc),
                "human_summary": human_summary,
                "resolved_source": (extra_config or {}).get("__resolved_source"),
                "resolved_setting_id": (extra_config or {}).get("__resolved_setting_id"),
                "stream": True,
            })
            raise

        if token_batch_buf:
            yield {"type": "token", "content": token_batch_buf}
        yield {"type": "done", "usage": usage, "finish_reason": finish_reason}

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
            if self._is_runtime_shutdown_text(content):
                logger.warning(
                    "[llm_fallback] active attempt %d/2 aborted: runtime shutting down, skip fallback chain | provider=%s model=%s",
                    attempt, config.get("provider"), config.get("model"),
                )
                return self._attach_routing_metadata({"content": last_err, "usage": {}, "finish_reason": None}, config)
            logger.warning(
                "[llm_fallback] active attempt %d/2 failed | provider=%s model=%s err=%s",
                attempt, config.get("provider"), config.get("model"), content[:200],
            )

        # ── fallback candidates: up to 3 ──
        active_cfg_obj = dict((config.get('config') or {}))
        __override_fallback_candidates = active_cfg_obj.get('__override_fallback_candidates')
        if __override_fallback_candidates is not None:
            override_ids = [int(x) for x in __override_fallback_candidates]
            fallbacks = agent_service.get_fallback_configs_by_ids(override_ids)
        else:
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
            if self._is_runtime_shutdown_text(content):
                logger.warning(
                    "[llm_fallback] fallback %d/%d aborted: runtime shutting down | provider=%s model=%s",
                    idx, len(fallbacks), fb_cfg.get("provider"), fb_cfg.get("model"),
                )
                return self._attach_routing_metadata({"content": last_err, "usage": {}, "finish_reason": None}, fb_cfg)
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
            except AmbiguousLLMTransportError:
                raise
            except Exception as e:
                last_exc = e
                if self._is_runtime_shutdown_error(e):
                    logger.warning(
                        "[llm_fallback] chat_completion active attempt %d/2 aborted: runtime shutting down, skip fallback chain | provider=%s model=%s",
                        attempt,
                        config.get("provider"),
                        config.get("model"),
                    )
                    raise
                _record_failed_attempt(config.get("provider"), config.get("model"), "active", attempt, e)
                logger.warning(
                    "[llm_fallback] chat_completion active attempt %d/2 failed | provider=%s model=%s err=%s",
                    attempt, config.get("provider"), config.get("model"), str(e)[:200],
                )

        # ── fallback candidates: up to 3 ──
        active_cfg_obj = dict((config.get('config') or {}))
        __override_fallback_candidates = active_cfg_obj.get('__override_fallback_candidates')
        if __override_fallback_candidates is not None:
            override_ids = [int(x) for x in __override_fallback_candidates]
            fallbacks = agent_service.get_fallback_configs_by_ids(override_ids)
        else:
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
            except AmbiguousLLMTransportError:
                raise
            except Exception as e:
                last_exc = e
                if self._is_runtime_shutdown_error(e):
                    logger.warning(
                        "[llm_fallback] chat_completion fallback %d/%d aborted: runtime shutting down | provider=%s model=%s",
                        idx,
                        len(fallbacks),
                        fb_cfg.get("provider"),
                        fb_cfg.get("model"),
                    )
                    raise
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
