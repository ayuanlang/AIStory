import codecs

with codecs.open('C:/AS/AIStory/backend/app/services/llm_service.py', 'r', 'utf-8') as f:
    data = f.read()

target = "        content = self._sanitize_response_content(raw_content)\n        logger.info(\n            \"[COLLECT] parts=%d raw_len=%d content_len=%d finish_reason=%s snippet=%r\",\n            parts_count, len(raw_content), len(content or \"\"), finish_reason, (content or \"\")[:120],\n        )\n        return {\n            \"raw_content\": raw_content,\n            \"content\": content,\n            \"usage\": usage,\n            \"finish_reason\": finish_reason,\n        }"
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
    print("success replace")
else:
    print("Not found")