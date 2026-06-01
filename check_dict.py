import re

with open('c:/AS/AIStory/backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.split('\n')
for i, line in enumerate(lines):
    if '"environments":' in line or "'environments':" in line:
        context = '\n'.join(lines[i-4:i+5])
        if 'posters' not in context:
            print(f'Possible missing posters near line {i+1}:\n{context}\n')
