import re
path = r'C:\AIStory\backend\app\api\endpoints.py'
with open(path, 'r', encoding='utf-8') as f: t = f.read()

t = t.replace('("characters", "props", "environments")', '("characters", "props", "environments", "covers")')
t = t.replace("characters, props, environments, and all three keys", "characters, props, environments, covers, and all keys")
t = t.replace("characters, props, environments, and all 3 keys", "characters, props, environments, covers, and all keys")
t = t.replace("characters, props, environments.\n", "characters, props, environments, covers.\n")
t = t.replace('checked_sections": ["characters", "props", "environments"]', 'checked_sections": ["characters", "props", "environments", "covers"]')
t = t.replace('(characters / props / environments)', '(characters / props / environments / covers)')
t = t.replace('characters/props/environments', 'characters/props/environments/covers')
t = t.replace('characters=%s props=%s environments=%s', 'characters=%s props=%s environments=%s covers=%s')

with open(path, 'w', encoding='utf-8') as f: f.write(t)
