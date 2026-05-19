import codecs
import re

with codecs.open('C:/AS/AIStory/backend/app/services/llm_service.py', 'r', 'utf-8') as f:
    data = f.read()

# Pattern for chat_completion
patt1 = re.compile(
    r'(extraction_diagnostics = self\._build_extraction_diagnostics\(full_response\)\s+)(return \{)',
    re.DOTALL
)

def repl1(m):
    return m.group(1) + """self._safe_log_json("LLM_RESPONSE", {
                "provider": provider,
                "model": model,
                "response": {
                    "content": content,
                    "finish_reason": finish_reason,
                }
            })
            """ + m.group(2)

data, c1 = patt1.subn(repl1, data)
print(f"chat_completion replacements: {c1}")

# Pattern for _collect_openai
patt2 = re.compile(
    r'(finish_reason, \(content or ""\)\[:120\],\s+\)\s+)(return \{)',
    re.DOTALL
)

def repl2(m):
    return m.group(1) + """provider = (extra_config or {}).get("__provider") or self._infer_provider(base_url, model)
        self._safe_log_json("LLM_RESPONSE", {
            "provider": provider,
            "category": str((extra_config or {}).get("__resolved_category") or "LLM").strip().upper(),
            "model": model,
            "response": {
                "content": content,
                "finish_reason": finish_reason,
            }
        })
        """ + m.group(2)

data, c2 = patt2.subn(repl2, data)
print(f"_collect_openai replacements: {c2}")

with codecs.open('C:/AS/AIStory/backend/app/services/llm_service.py', 'w', 'utf-8') as f:
    f.write(data)
