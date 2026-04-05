with open('../backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()
text = text.replace('extra_config=config', 'extra_config=dict(config.get(\"config\", {}) or {})')
with open('../backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
