

import requests
import json
import asyncio
from typing import Dict, Any, List
import logging
import os
import re
from pathlib import Path
from logging.handlers import RotatingFileHandler

from app.core.config import settings

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
DEFAULT_LLM_TIMEOUT_SECONDS = 600

SYSTEM_PROMPT = """
You are an AI assistant for a Storyboard Editor application.
Your goal is to help the user edit, create, and manage storyboard projects.

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
    def _safe_log_json(self, tag: str, payload: Dict[str, Any]) -> None:
        try:
            _llm_call_logger.info("%s %s", tag, json.dumps(payload, ensure_ascii=False, default=str))
        except Exception as e:
            logger.warning(f"Failed to write llm call audit log ({tag}): {e}")

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
        cleaned = re.sub(r"<think\b[^>]*>[\s\S]*?</think>", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<think\b[^>]*>[\s\S]*$", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"</think>", "", cleaned, flags=re.IGNORECASE)

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
            chunks = []
            for item in content:
                if isinstance(item, dict):
                    txt = item.get("text")
                    if isinstance(txt, str) and txt.strip():
                        chunks.append(txt)
                elif isinstance(item, str) and item.strip():
                    chunks.append(item)
            return "\n".join(chunks).strip()
        return ""

    def _extract_text_from_response(self, full_response: Dict[str, Any]) -> str:
        choices = full_response.get("choices") or []
        first = choices[0] if choices else {}
        if isinstance(first, dict):
            message = first.get("message") or {}
            if isinstance(message, dict):
                text = self._extract_text_from_content(message.get("content"))
                if text:
                    return text
                reasoning_text = self._extract_text_from_content(message.get("reasoning_content"))
                if reasoning_text:
                    return reasoning_text
                refusal = message.get("refusal")
                if isinstance(refusal, str) and refusal.strip():
                    return refusal

            choice_text = first.get("text")
            if isinstance(choice_text, str) and choice_text.strip():
                return choice_text

        return ""

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
        
        logger.info(f"Calling Doubao Multimodal: {url} model={model}")

        def _request():
            return requests.post(url, headers=headers, json=payload, timeout=DEFAULT_LLM_TIMEOUT_SECONDS)

        try:
            response = await asyncio.to_thread(_request)
            
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
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        
        # Add context summary to system message or valid context message
        context_str = f"Current Project Context: {json.dumps(context, default=str)}"
        messages.append({"role": "system", "content": context_str})

        # Add history
        for msg in history[-5:]: # Keep last 5 turns
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        
        # Add current query
        messages.append({"role": "user", "content": query})

        extra_config = dict(config.get("config", {}) or {})
        extra_config.setdefault("__provider", config.get("provider") or self._infer_provider(base_url, model))

        try:
            return await self._call_openai_compatible(base_url, api_key, model, messages, extra_config)
        except Exception as e:
            logger.error(f"LLM Call failed: {e}")
            return {
                "reply": f"Sorry, I encountered an error communicating with the AI provider: {str(e)}",
                "plan": []
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
            content = self._extract_text_from_response(full_response)
            content = self._sanitize_response_content(content)
            finish_reason = full_response.get("choices", [{}])[0].get("finish_reason")
            usage = full_response.get("usage", {})
            return {"content": content, "usage": usage, "finish_reason": finish_reason}
        except Exception as e:
            logger.error(f"LLM Raw Completion failed: {e}")
            raise e

    async def _call_openai_compatible(self, base_url: str, api_key: str, model: str, messages: List[Dict], extra_config: Dict[str, Any] = None) -> Dict[str, Any]:
        full_response = await self._raw_llm_request_full(base_url, api_key, model, messages, extra_config)
        content = self._extract_text_from_response(full_response)
        content = self._sanitize_response_content(content)
        usage = full_response.get("usage", {})
        finish_reason = None
        try:
            choices = full_response.get("choices") or []
            first = choices[0] if choices else {}
            finish_reason = first.get("finish_reason") if isinstance(first, dict) else None
        except Exception:
            finish_reason = None
        
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
            
        try:
            result = json.loads(clean_content)
            # Validate keys
            if "reply" not in result:
                result["reply"] = clean_content
            if "plan" not in result:
                result["plan"] = []
            
            # Inject Usage
            result["usage"] = usage
            result["finish_reason"] = finish_reason
            return result

        except json.JSONDecodeError:
            # Fallback if not valid JSON
            return {
                "reply": clean_content,
                "plan": [],
                "usage": usage,
                "finish_reason": finish_reason,
            }


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
             return {"content": f"Error: {e}", "usage": {}, "finish_reason": None}

    async def _raw_llm_request(self, base_url: str, api_key: str, model: str, messages: List[Dict], extra_config: Dict[str, Any] = None) -> str:
        data = await self._raw_llm_request_full(base_url, api_key, model, messages, extra_config)
        return data["choices"][0]["message"]["content"]

    async def _raw_llm_request_full(self, base_url: str, api_key: str, model: str, messages: List[Dict], extra_config: Dict[str, Any] = None) -> Dict[str, Any]:
        # Ensure base_url ends with correct chat endpoint if not specific
        if not base_url:
            base_url = "https://api.openai.com/v1"  # Default to OpenAI if not set

        resolved_category = str((extra_config or {}).get("__resolved_category") or "LLM").strip().upper()
        provider = (extra_config or {}).get("__provider") or self._infer_provider(base_url, model)
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

        def _request(bypass_proxy=False):
            kwargs = {
                "json": payload,
                "headers": headers,
                "timeout": DEFAULT_LLM_TIMEOUT_SECONDS
            }
            if bypass_proxy:
                kwargs["proxies"] = {"http": None, "https": None}
            return requests.post(url, **kwargs)

        try:
            response = await asyncio.to_thread(_request, False)
        except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
            logger.warning(f"Connection failed ({str(e)}). Retrying without proxy...")
            response = await asyncio.to_thread(_request, True)
        
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
            raise Exception(
                f"API Error {response.status_code} [provider={provider}, model={model}, endpoint={url}, setting_id={resolved_setting_id}, source={resolved_source}]: {response.text}"
            )

        data = response.json()
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
            finish_reason = first.get("finish_reason") if isinstance(first, dict) else None
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
            if str(finish_reason).lower() == "length":
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
        except Exception:
            logger.info("LLM Response received (summary unavailable)")

        # Optional deep debug (disabled by default). This may include large content.
        if os.getenv("LLM_DEBUG_LOG_CONTENT") == "1":
            logging.getLogger("app").debug("LLM Payload (debug): %s", json.dumps(payload, ensure_ascii=False))
            logging.getLogger("app").debug("LLM Response (debug): %s", json.dumps(data, ensure_ascii=False))
        
        if "choices" in data and len(data["choices"]) > 0:
            return data
        else:
             raise Exception(f"Invalid API Response: {data}")

    def _mock_fallback(self, query: str) -> Dict[str, Any]:
        if "analyze" in query.lower():
            return {
                "reply": "I will analyze the script (Mock).",
                "plan": [{"tool": "analyze_script", "parameters": {"text": "..."}}]
            }
        return {"reply": f"Mock reply to: {query}", "plan": []}

llm_service = LLMService()
