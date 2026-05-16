import re

with open('c:/AS/AIStory/backend/app/services/llm_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Line 887: _call_kie_llm (transport error)
text = text.replace('''            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": "kie",
                "category": "LLM",
                "url": url,
                "model": resolved_model,
                "error_kind": "connection",
                "error_text": str(exc),
                "human_summary": human_summary,
            })''', '''            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": "kie",
                "category": "LLM",
                "request": {"url": url, "model": resolved_model, "payload": payload},
                "model": resolved_model,
                "error_kind": "connection",
                "error_text": str(exc),
                "human_summary": human_summary,
            })''')

# Line 909: _call_kie_llm HTTP error
text = text.replace('''            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": "kie",
                "category": "LLM",
                "url": url,
                "model": resolved_model,
                "status_code": resp.status_code,
                "response_text": resp.text[:500],
                "human_summary": human_summary,
            })''', '''            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": "kie",
                "category": "LLM",
                "request": {"url": url, "model": resolved_model, "payload": payload},
                "model": resolved_model,
                "status_code": resp.status_code,
                "response_text": resp.text[:500],
                "human_summary": human_summary,
            })''')

# Line 1769: doubao multimodal
text = text.replace('''            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": "doubao",
                "category": "LLM",
                "url": url,
                "model": model,
                "error_kind": error_kind,
                "error_text": str(e),
                "human_summary": human_summary,
            })''', '''            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": "doubao",
                "category": "LLM",
                "request": {"url": url, "model": model, "payload": payload},
                "model": model,
                "error_kind": error_kind,
                "error_text": str(e),
                "human_summary": human_summary,
            })''')

# Line 2777: _raw_llm_request_full ambiguous_submit_transport
text = text.replace('''                self._safe_log_json("LLM_RESPONSE_ERROR", {
                    "provider": provider,
                    "category": resolved_category,
                    "url": url,
                    "model": model,
                    "error_kind": "ambiguous_submit_transport",
                    "error_text": str(e2),
                    "human_summary": human_summary,
                    "resolved_source": (extra_config or {}).get("__resolved_source"),
                    "resolved_setting_id": (extra_config or {}).get("__resolved_setting_id"),
                })''', '''                self._safe_log_json("LLM_RESPONSE_ERROR", {
                    "provider": provider,
                    "category": resolved_category,
                    "request": {"url": url, "model": model, "messages": messages},
                    "model": model,
                    "error_kind": "ambiguous_submit_transport",
                    "error_text": str(e2),
                    "human_summary": human_summary,
                    "resolved_source": (extra_config or {}).get("__resolved_source"),
                    "resolved_setting_id": (extra_config or {}).get("__resolved_setting_id"),
                })''')

# Line 2798: _raw_llm_request_full connection
text = text.replace('''                self._safe_log_json("LLM_RESPONSE_ERROR", {
                    "provider": provider,
                    "category": resolved_category,
                    "url": url,
                    "model": model,
                    "error_kind": "connection",
                    "error_text": str(e2),
                    "human_summary": human_summary,
                    "resolved_source": (extra_config or {}).get("__resolved_source"),
                    "resolved_setting_id": (extra_config or {}).get("__resolved_setting_id"),
                })''', '''                self._safe_log_json("LLM_RESPONSE_ERROR", {
                    "provider": provider,
                    "category": resolved_category,
                    "request": {"url": url, "model": model, "messages": messages},
                    "model": model,
                    "error_kind": "connection",
                    "error_text": str(e2),
                    "human_summary": human_summary,
                    "resolved_source": (extra_config or {}).get("__resolved_source"),
                    "resolved_setting_id": (extra_config or {}).get("__resolved_setting_id"),
                })''')

# Line 2819: _raw_llm_request_full early ambiguous_submit_transport
text = text.replace('''            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": provider,
                "category": resolved_category,
                "url": url,
                "model": model,
                "error_kind": "ambiguous_submit_transport",
                "error_text": str(e),
                "human_summary": human_summary,
                "resolved_source": (extra_config or {}).get("__resolved_source"),
                "resolved_setting_id": (extra_config or {}).get("__resolved_setting_id"),
            })''', '''            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": provider,
                "category": resolved_category,
                "request": {"url": url, "model": model, "messages": messages},
                "model": model,
                "error_kind": "ambiguous_submit_transport",
                "error_text": str(e),
                "human_summary": human_summary,
                "resolved_source": (extra_config or {}).get("__resolved_source"),
                "resolved_setting_id": (extra_config or {}).get("__resolved_setting_id"),
            })''')

# Line 2869: _raw_llm_request_full invalidate json response
text = text.replace('''            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": provider,
                "category": resolved_category,
                "url": url,
                "model": model,
                "error_kind": "exception",
                "error_text": str(e),
                "human_summary": human_summary,
                "resolved_source": resolved_source,
                "resolved_setting_id": resolved_setting_id,
            })''', '''            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": provider,
                "category": resolved_category,
                "request": {"url": url, "model": model, "messages": messages},
                "model": model,
                "error_kind": "exception",
                "error_text": str(e),
                "human_summary": human_summary,
                "resolved_source": resolved_source,
                "resolved_setting_id": resolved_setting_id,
            })''')

# Line 3404: _raw_llm_request_stream ConnectError
text = text.replace('''            self._safe_log_json("LLM_RESPONSE_ERROR", {
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
            })''', '''            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": provider,
                "category": resolved_category,
                "request": {"url": url, "model": payload.get("model") or model, "messages": messages},
                "model": payload.get("model") or model,
                "error_kind": "connection",
                "error_text": str(exc),
                "human_summary": human_summary,
                "resolved_source": (extra_config or {}).get("__resolved_source"),
                "resolved_setting_id": (extra_config or {}).get("__resolved_setting_id"),
                "stream": True,
            })''')

# Line 3425: _raw_llm_request_stream ReadTimeout
text = text.replace('''            self._safe_log_json("LLM_RESPONSE_ERROR", {
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
            })''', '''            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": provider,
                "category": resolved_category,
                "request": {"url": url, "model": payload.get("model") or model, "messages": messages},
                "model": payload.get("model") or model,
                "error_kind": "ambiguous_submit_transport" if str(provider or "").strip().lower() == "kie" else "timeout",
                "error_text": str(exc),
                "human_summary": human_summary,
                "resolved_source": (extra_config or {}).get("__resolved_source"),
                "resolved_setting_id": (extra_config or {}).get("__resolved_setting_id"),
                "stream": True,
            })''')

# Line 3471: _raw_llm_request_stream Exception
text = text.replace('''            self._safe_log_json("LLM_RESPONSE_ERROR", {
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
            })''', '''            self._safe_log_json("LLM_RESPONSE_ERROR", {
                "provider": provider,
                "category": resolved_category,
                "request": {"url": url, "model": payload.get("model") or model, "messages": messages},
                "model": payload.get("model") or model,
                "error_kind": "exception",
                "error_text": str(exc),
                "human_summary": human_summary,
                "resolved_source": (extra_config or {}).get("__resolved_source"),
                "resolved_setting_id": (extra_config or {}).get("__resolved_setting_id"),
                "stream": True,
            })''')

with open('c:/AS/AIStory/backend/app/services/llm_service.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Replacement complete.")
