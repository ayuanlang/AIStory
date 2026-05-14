with open(r'c:\AS\AIStory\backend\app\services\media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re
matches = re.finditer(r'imageUrls', text)
for m in matches:
    idx = m.start()
    if 570000 < idx < 580000:
        print('Match at', idx)
        print(text[max(0, idx-100):min(len(text), idx+300)])
