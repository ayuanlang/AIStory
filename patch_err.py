import os

file_path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

target = 'return {"error": "Generation Failed", "details": p_data.get("error") or p_data}'
replacement = 'return {"error": f"Generation Failed: {p_data.get(\'error\') or p_data}", "details": p_data.get("error") or p_data}'

if target in text:
    new_text = text.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("Patched!")
else:
    print("Not found")