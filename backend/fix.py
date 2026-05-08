import os
path = 'C:/AS/AIStory/backend/app/main.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()
old_part = 'app.mount("/assets", StaticFiles(directory=os.path.join(_FRONTEND_DIST, "assets")), name="frontend-assets")'
new_part = 'os.makedirs(os.path.join(_FRONTEND_DIST, "assets"), exist_ok=True)\n    app.mount("/assets", StaticFiles(directory=os.path.join(_FRONTEND_DIST, "assets")), name="frontend-assets")'
text = text.replace(old_part, new_part)
with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
