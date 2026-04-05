import os

with open('../backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_code = """                    stream = llm_service._raw_llm_request_stream(
                        base_url=config.get("base_url"),
                        api_key=config.get("api_key"),
                        model=config.get("model"),
                        messages=current_messages,
                        extra_config=config
                    )"""

new_code = """                    extra = dict(config.get("config", {}) or {})
                    extra["__provider"] = config.get("provider")
                    extra["__resolved_category"] = config.get("category", "LLM")
                    stream = llm_service._raw_llm_request_stream(
                        base_url=config.get("base_url"),
                        api_key=config.get("api_key"),
                        model=config.get("model"),
                        messages=current_messages,
                        extra_config=extra
                    )"""

text = text.replace(old_code, new_code)

with open('../backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)