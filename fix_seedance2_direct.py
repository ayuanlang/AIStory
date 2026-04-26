import os

file_path = 'c:/AS/AIStory/backend/app/services/media_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

target = '"role": "first_frame" if idx == 0 else "reference_image",'
replacement = '"role": "reference_image",'

text = text.replace(target, replacement)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)
