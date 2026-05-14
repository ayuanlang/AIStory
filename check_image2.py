import re
with open(r'c:\AS\AIStory\backend\app\services\media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

for i, line in enumerate(text.split('\n')):
    if 'replace' in line and ('@' in line or 'Image' in line):
        print(f'{i}: {line.strip()}')
