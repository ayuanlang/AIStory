import sys
path = 'c:/AS/AIStory/backend/app/api/endpoints.py'
with open(path, 'r', encoding='utf-8') as f:
    txt = f.read()

txt = txt.replace('{"characters": [], "props": [], "environments": [], "covers": []}', '{"characters": [], "props": [], "environments": [], "covers": [], "posters": []}')
txt = txt.replace('{"characters": set(), "props": set(), "environments": set(), "covers": set()}', '{"characters": set(), "props": set(), "environments": set(), "covers": set(), "posters": set()}')
txt = txt.replace('("props", "environments", "covers")', '("props", "environments", "covers", "posters")')
txt = txt.replace('["characters", "props", "environments", "posters"]', '["characters", "props", "environments", "covers", "posters"]')

with open(path, 'w', encoding='utf-8') as f:
    f.write(txt)
print("Done dictionaries")