import sys
path = 'c:/AS/AIStory/backend/app/api/endpoints.py'
with open(path, 'r', encoding='utf-8') as f:
    txt = f.read()

txt = txt.replace(
'''            "environments": len(subjects_json.get("environments") or []),
            "covers": len(subjects_json.get("covers") or []),''',
'''            "environments": len(subjects_json.get("environments") or []),
            "covers": len(subjects_json.get("covers") or []),
            "posters": len(subjects_json.get("posters") or []),'''
)
with open(path, 'w', encoding='utf-8') as f:
    f.write(txt)
print("Done padding subjects_json_count")