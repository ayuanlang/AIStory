import re
from collections import defaultdict
with open('app/db/init_db.py', 'r', encoding='utf-8') as f:
    text = f.read()

matches = re.finditer(r'_kie_item\([^)]+\)', text)
items = []
for m in matches:
    inner = m.group(0)
    args = re.findall(r'"([^"]+)"', inner)
    if len(args) >= 3:
        items.append(args[:3])

grouped = defaultdict(list)
for item in items:
    name, cat, mod = item
    prefix = name.split(' ')[1].lower() if len(name.split(' ')) > 1 else name.lower()
    grouped[prefix].append(item)

for prefix, grouped_items in grouped.items():
    if len(grouped_items) > 1:
        print(f'=== {prefix} ===')
        for i in grouped_items:
            print('  ', i)
