import re
with open('c:/AS/AIStory/backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('Depends(deps.get_current_active_superuser)', 'Depends(get_current_user)')
with open('c:/AS/AIStory/backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Fixed eps6')
