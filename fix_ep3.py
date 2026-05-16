with open('c:/AS/AIStory/backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('Depends(deps.get_current_active_superuser)', 'Depends(get_current_active_superuser)')
if 'from app.api.deps import' not in text:
    text = text.replace('from app.api.deps import get_db', 'from app.api.deps import get_db, get_current_active_superuser')
with open('c:/AS/AIStory/backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Fixed eps3')
