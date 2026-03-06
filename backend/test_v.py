with open('app/db/init_db.py', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('kie_models = [')
idx2 = text.find(']', idx)
chunk = text[idx:idx2+1]

import re
matches = re.finditer(r'"([^"]+)",\s*"Video",\s*"([^"]+)"', chunk)
for m in matches:
    print(m.group(1).ljust(40), m.group(2))
