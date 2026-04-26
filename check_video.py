import os

path = 'backend/app/api/endpoints.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')

for i, line in enumerate(lines):
    if 'await asyncio.to_thread(_register_asset_helper, bg_db, bg_user.id, final_url, req_obj, final_meta)' in line:
        for idx in range(i-5, i+5):
            print(f'{idx+1}: {lines[idx]}')
        print('-'*20)
