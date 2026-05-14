import re
with open(r'c:\AS\AIStory\backend\app\services\media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()
import ast
lines = text.split('\n')
for i, line in enumerate(lines):
    if 'def _merge_negative_prompt' in line:
        for idx in range(i, i+15):
             print(lines[idx].strip())
        break
