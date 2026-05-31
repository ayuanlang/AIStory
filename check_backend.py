import sys
path = 'c:/AS/AIStory/backend/app/api/endpoints.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')

for i, line in enumerate(lines):
    if 'environments' in line and ('covers' in line or 'posters' in line):
        print(f"Line {i+1}: {line.strip()}")
