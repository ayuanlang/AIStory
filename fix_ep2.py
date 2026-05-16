with open('c:/AS/AIStory/backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('Depends(get_current_active_superuser)', 'Depends(deps.get_current_active_superuser)')
text = text.replace('current_user: User', 'current_user: Any')
if 'from typing import Any' not in text:
    text = text.replace('from typing import ', 'from typing import Any, ')
with open('c:/AS/AIStory/backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Fixed')
