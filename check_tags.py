import re
data = open('C:/AS/AIStory/backend/app/services/llm_service.py', encoding='utf-8').read()
tags = set(re.findall(r'_safe_log_json\([\'"]([^\'"]+)[\'"]', data))
print(tags)