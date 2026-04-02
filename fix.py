path = r'C:\AIStory\backend\app\api\endpoints.py'
with open(path, 'r', encoding='utf-8') as f: t = f.read()

t = t.replace('"characters": [], "covers": [], "covers": [],', '"characters": [], "covers": [],')

with open(path, 'w', encoding='utf-8') as f: f.write(t)
