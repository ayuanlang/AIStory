import codecs

with codecs.open('C:/AS/AIStory/backend/app/services/llm_service.py', 'r', 'utf-8') as f:
    data = f.read()

target = """        content = self._sanitize_response_content(raw_content)
        logger.info(
            "[COLLECT] parts=%d raw_len=%d content_len=%d finish_reason=%s snippet=%r",
            parts_count, len(raw_content), len(content or ""), finish_reason, (content or "")[:120],
        )
        return {
            "raw_content": raw_content,
            "content": content,
            "usage": usage,
            "finish_reason": finish_reason,
        }"""
if target in data:
    replacement = """        content = self._sanitize_response_content(raw_content)
        logger.info(
            "[COLLECT] parts=%d raw_len=%d content_len=%d finish_reason=%s snippet=%r",
            parts_count, len(raw_content), len(content or ""), finish_reason, (content or "")[:120],
        )

        provider = (extra_config or {}).get("__provider") or self._infer_provider(base_url, model)
        self._safe_log_json("LLM_RESPONSE", {
            "provider": provider,
            "category": str((extra_config or {}).get("__resolved_category") or "LLM").strip().upper(),
            "model": model,
            "response": {
                "content": content,
                "finish_reason": finish_reason,
            }
        })

        return {
            "raw_content": raw_content,
            "content": content,
            "usage": usage,
            "finish_reason": finish_reason,
        }"""
    
    data = data.replace(target, replacement)
    with codecs.open('C:/AS/AIStory/backend/app/services/llm_service.py', 'w', 'utf-8') as f:
        f.write(data)
    print("success replace in _collect_openai...")
else:
    print("Not found in _collect_openai...")

target2 = """            raw_content = self._extract_text_from_response(full_response)
            content = self._sanitize_response_content(raw_content)
            finish_reason = self._extract_finish_reason_from_response(full_response)
            usage = full_response.get("usage", {})
            token_limit_hints = full_response.get("_token_limit_hints", []) if isinstance(full_response, dict) else []
            extraction_diagnostics = self._build_extraction_diagnostics(full_response)
            return {"""

if target2 in data:
    replacement2 = """            raw_content = self._extract_text_from_response(full_response)
            content = self._sanitize_response_content(raw_content)
            finish_reason = self._extract_finish_reason_from_response(full_response)
            usage = full_response.get("usage", {})
            token_limit_hints = full_response.get("_token_limit_hints", []) if isinstance(full_response, dict) else []
            extraction_diagnostics = self._build_extraction_diagnostics(full_response)
            
            self._safe_log_json("LLM_RESPONSE", {
                "provider": provider,
                "model": model,
                "response": {
                    "content": content,
                    "finish_reason": finish_reason,
                }
            })
            
            return {"""
    data = data.replace(target2, replacement2)
    with codecs.open('C:/AS/AIStory/backend/app/services/llm_service.py', 'w', 'utf-8') as f:
        f.write(data)
    print("success replace in chat_completion...")
else:
    print("Not found in chat_completion...")
