import codecs

with codecs.open('C:/AS/AIStory/backend/app/api/endpoints.py', 'r', 'utf-8') as f:
    data = f.read()

target = """            llm_service._safe_log_json("LLM_STREAM_INCOMPLETE_REJECTED", {
                "provider": (config or {}).get("provider", ""),
                "model": (config or {}).get("model", ""),
                "episode_id": getattr(request, "episode_id", None),
                "error": f"LLM connection dropped prematurely (reason: {finish_reason}).",
                "response": {
                    "partial_content_len": len(result_content or ""),
                    "partial_content": result_content
                }
            })
            
            raise HTTPException(status_code=502, detail=f"LLM connection dropped prematurely (reason: {finish_reason}). Please retry.")"""

replacement = target + """

        llm_service._safe_log_json("LLM_RESPONSE", {
            "provider": (config or {}).get("provider", ""),
            "model": (config or {}).get("model", ""),
            "episode_id": getattr(request, "episode_id", None),
            "response": {
                "content": result_content,
                "finish_reason": finish_reason,
            }
        })
"""

assert target in data, "Target not found!"

data = data.replace(target, replacement)

with codecs.open('C:/AS/AIStory/backend/app/api/endpoints.py', 'w', 'utf-8') as f:
    f.write(data)

print("Replacement successful")
