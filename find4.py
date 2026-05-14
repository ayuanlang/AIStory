with open(r'c:\AS\AIStory\backend\app\services\media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re
matches = re.finditer(r'await asyncio\.to_thread\(_post_submit, submit_payload\)', text)
for m in matches:
    idx = m.start()
    print('Match at', idx)
    print(text[max(0, idx-500):min(len(text), idx+200)])
