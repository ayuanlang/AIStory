import codecs
import re

with codecs.open('C:/AS/AIStory/backend/app/api/endpoints.py', 'r', 'utf-8') as f:
    data = f.read()

target = "raise HTTPException(status_code=502, detail=f\"LLM connection dropped prematurely (reason: {finish_reason}). Please retry.\")"
if target in data:
    idx = data.find(target) + len(target)
    
    replacement = """

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
    # Just insert it right after the exact string
    new_data = data[:idx] + replacement + data[idx:]
    with codecs.open('C:/AS/AIStory/backend/app/api/endpoints.py', 'w', 'utf-8') as f:
        f.write(new_data)
    print("Injected successfully at idx", idx)
else:
    print("Target not found")
