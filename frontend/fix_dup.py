import re

with open('c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'''\{\s*function_name:\s*'[^']+',\s*function_name:\s*'[^']+',''', r"{ function_name: 'generate_shot_images',", text)

with open('c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

