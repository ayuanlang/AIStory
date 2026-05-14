import re

path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Update sora patch
old_regex = r'cleaned = re.sub\(r\"@\(\?!\(\?:Image\|Video\|Vedie\|Vedio\)\\\\d\+\)\(\?=\[A-Za-z0-9_\\\\u4e00-\\\\u9fff\]\)\", \"\", text, flags=re.IGNORECASE\)'
new_regex = r'cleaned = re.sub(r"@(?!(?:Image|Video|Vedie|Vedio)\s*\d+)(?=[A-Za-z0-9_\u4e00-\u9fff])", "", text, flags=re.IGNORECASE)'
text = re.sub(old_regex, new_regex, text)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Repatched successfully!')
