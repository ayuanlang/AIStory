import re

path = r'c:\AS\AIStory\backend\app\services\media_service.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Patch KIE
def repl_kie(m):
    return '''        def _repl(match):
            name = match.group(1)
            lower_name = name.strip().lower()
            if lower_name.startswith("image") or lower_name.startswith("video") or lower_name.startswith("vedie") or lower_name.startswith("vedio"):
                return match.group(0)
            if name.strip() in valid_element_names or name in valid_element_names:
                return match.group(0)
            return name
'''
text = re.sub(r'        def _repl\(match\):.*?(?:return name\n)', repl_kie, text, flags=re.DOTALL)

# Patch Sora
target = 'cleaned = re.sub(r"@(?!(?:Image\\\\d+\\\\b))(?=[A-Za-z0-9_\\\\u4e00-\\\\u9fff])", "", text)'
replacement = 'cleaned = re.sub(r"@(?!(?:Image|Video|Vedie|Vedio)\\\\d+)(?=[A-Za-z0-9_\\\\u4e00-\\\\u9fff])", "", text, flags=re.IGNORECASE)'
text = text.replace(target, replacement)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Patched successfully!')
