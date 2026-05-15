import sqlite3
import json

conn = sqlite3.connect('backend/aistory.db')
c = conn.cursor()
c.execute('SELECT id, type, meta_info FROM assets ORDER BY id DESC LIMIT 20')
rows = c.fetchall()
for r in rows:
    meta = json.loads(r[2]) if r[2] else {}
    print(f"id={r[0]}, type={r[1]}, meta_type={meta.get('asset_type')}, shot_id={meta.get('shot_id')}, entity_id={meta.get('entity_id')}, frame_type={meta.get('frame_type')}, url_end={r[2][-20:]}")
