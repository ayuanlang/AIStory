import re
path = r'C:\AIStory\backend\app\api\endpoints.py'
with open(path, 'r', encoding='utf-8') as f: t = f.read()

t = t.replace('characters/props/environments/covers/covers.', 'characters/props/environments/covers.')
t = t.replace('characters=%s props=%s environments=%s covers=%s covers=%s', 'characters=%s props=%s environments=%s covers=%s')
t = t.replace('keys: characters, props, environments.\\n', 'keys: characters, props, environments, covers.\\n')
t = t.replace('extraction principles for characters / props / environments.\\n', 'extraction principles for characters / props / environments / covers.\\n')

with open(path, 'w', encoding='utf-8') as f: f.write(t)
