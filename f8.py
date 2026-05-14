import re
with open(r'c:\AS\AIStory\backend\app\services\media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('def _handle_kie_generation')
matches = re.finditer(r'(_video|video[Uu]rl)', text)
for m in matches:
    if m.start() > idx:
        start_idx = max(idx, m.start() - 30)
        print('Match at', m.start())
        print(text[start_idx:m.start()+100])
