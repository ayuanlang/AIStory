import re
from collections import defaultdict
with open('app/db/init_db.py', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('kie_models = [')
idx2 = text.find(']', idx)
chunk = text[idx:idx2+1]

matches = re.finditer(r'_kie_item\(([^)]+)\)', chunk)
items = []
for m in matches:
    inner = m.group(1)
    parts = []
    for p in inner.split(','):
        p = p.strip()
        if len(p) >= 2 and p[0] in ('"', "'") and p[-1] in ('"', "'"):
            p = p[1:-1]
        parts.append(p)
    if len(parts) >= 3:
        items.append(parts[:3])
        
grouped = defaultdict(list)
for item in items:
    name, cat, mod = item
    parts = name.split(' ')
    prefix = parts[1].lower() if len(parts) > 1 else name.lower()
    grouped[prefix].append(item)

for prefix, grouped_items in grouped.items():
    if len(grouped_items) > 1:
        print('=== ' + prefix + ' ===')
        for i in grouped_items:
            print('  ', i)
