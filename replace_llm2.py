import codecs

with codecs.open('C:/AS/AIStory/backend/app/services/llm_service.py', 'r', 'utf-8') as f:
    data = f.read()

target = """        logger.info(
            "[COLLECT] parts=%d raw_len=%d content_len=%d finish_reason=%s snippet=%r",
            parts_count, len(raw_content), len(content or ""), finish_reason, (content or "")[:120],
        )
        return {"""

replacement = """        logger.info(
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
        
        return {"""

assert target in data, "Target not found"
data = data.replace(target, replacement)

with codecs.open('C:/AS/AIStory/backend/app/services/llm_service.py', 'w', 'utf-8') as f:
    f.write(data)

print("success code patched")
