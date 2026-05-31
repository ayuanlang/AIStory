import sys
path = 'c:/AS/AIStory/backend/app/api/endpoints.py'
with open(path, 'r', encoding='utf-8') as f:
    txt = f.read()

txt = txt.replace(
    '                        "characters": [], "props": [], "environments": [], "covers": []',
    '                        "characters": [], "props": [], "environments": [], "covers": [], "posters": []'
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(txt)
print("Done line 5263")