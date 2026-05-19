data=open('C:/AS/AIStory/backend/app/services/llm_service.py', encoding='utf-8').read(); import re; res=re.finditer(r'_safe_log_json\(([^,]+).*?\)', data); print([m.group(1) for m in res])
