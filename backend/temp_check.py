import sys, os, re
sys.path.append(os.getcwd())

with open('app/db/init_db.py', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('kie_models = [')
idx2 = text.find(']', idx)
chunk = text[idx:idx2+1]

valid_models = set()
for m in re.finditer(r'"([^"]+)"', chunk):
    val = m.group(1)
    if val and val not in ['Image', 'Video', 'LLM', 'Tools'] and not val.startswith('Kie ') and '(' not in val and '\n' not in val:
        valid_models.add(val)

from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting

with SessionLocal() as db:
    rows = db.query(SystemAPISetting).filter(SystemAPISetting.provider == 'kie').all()
    to_delete = []
    to_keep = []
    
    for r in rows:
        if r.model in valid_models:
            to_keep.append(r)
        else:
            to_delete.append(r)
            
    print(f'Keep: {len(to_keep)}, Delete: {len(to_delete)}')
    for r in to_delete[:20]:
        print(f'  DELETE: {r.id} | {r.model} | {r.name}')
