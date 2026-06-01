import re

with open('c:/AS/AIStory/backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('''        "subjects_json_count": {
            "characters": len(subjects_json.get("characters") or []),
            "props": len(subjects_json.get("props") or []),
            "environments": len(subjects_json.get("environments") or []),
        },''', '''        "subjects_json_count": {
            "characters": len(subjects_json.get("characters") or []),
            "props": len(subjects_json.get("props") or []),
            "environments": len(subjects_json.get("environments") or []),
            "covers": len(subjects_json.get("covers") or []),
            "posters": len(subjects_json.get("posters") or []),
        },''')

with open('c:/AS/AIStory/backend/app/api/endpoints.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Patch applied for subjects_json_count")
