import os
import re

file_path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

matches = re.finditer(r'elif effective_provider == "doubao":[\s\S]{0,300}\)', text)
for m in matches:
    print("Match found:")
    print("-------------------")
    print(repr(m.group(0)))
    print("-------------------")
