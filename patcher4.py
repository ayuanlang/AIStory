import os
import re

file_path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

matches = re.finditer(r'elif effective_provider == "doubao"[\s\S]{0,300}', text)
count = 0
for m in matches:
    count += 1
    if count > 2: break
    print("Match found:")
    print("-------------------")
    print(repr(m.group(0)))
    print("-------------------")

print("\n\nNow searching for grsai")
matches = re.finditer(r'if effective_provider == "grsai":[\s\S]{0,400}', text)
count = 0
for m in matches:
    count += 1
    if count > 2: break
    print("Match found:")
    print("-------------------")
    print(repr(m.group(0)))
    print("-------------------")
