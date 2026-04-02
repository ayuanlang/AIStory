import re

with open('c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

def inject_function_name(match):
    prefix = match.group(1)
    body = match.group(2)
    # Don't double inject
    if 'function_name:' not in body:
        return prefix + "\n                    function_name: '" + match.group(3) + "'," + body + "}"
    return match.group(0)

# Regex for generateImage(..., { 
text = re.sub(r'(generateImage\([^)]*,\s*\{)([^}]*)\}', lambda m: inject_function_name(re.match(r'(generateImage\([^)]*,\s*\{)([^}]*)\}', m.group(0)) and type('obj', (object,), {'group': lambda self, i: ['generate_shot_images' if i==3 else m.group(i) for _ in range(1)][0]})()), text)

old_text = text
parts = text.split('generateImage(')

new_parts = [parts[0]]
for part in parts[1:]:
    if ', {' in part:
        # find the '{' and insert function_name: 'generate_shot_images',
        idx = part.find('{') + 1
        if 'function_name:' not in part:
            part = part[:idx] + " function_name: 'generate_shot_images', " + part[idx:]
    new_parts.append('generateImage(' + part)
text = ''.join(new_parts)

parts = text.split('generateVideo(')
new_parts = [parts[0]]
for part in parts[1:]:
    if ', {' in part:
        # find the '{' and insert function_name: 'generate_videos',
        idx = part.find('{') + 1
        if 'function_name:' not in part:
            part = part[:idx] + " function_name: 'generate_videos', " + part[idx:]
    new_parts.append('generateVideo(' + part)
text = ''.join(new_parts)

with open('c:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

print("patched shotsview")
