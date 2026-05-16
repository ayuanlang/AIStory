import re
with open('c:/AS/AIStory/backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'from app\.api\.deps import\s+?([A-Za-z0-linejoin_\s,]+)', lambda m: 'from app.api.deps import ' + ('get_current_active_superuser, ' if 'get_current_active_superuser' not in m.group(1) else '') + m.group(1), text, count=1)
with open('c:/AS/AIStory/backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Fixed eps4')
