import sqlite3
import json

db_path = 'C:/AIStory/backend/aistory.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute('SELECT id, supplier_info FROM system_api_settings')
rows = c.fetchall()

updated = 0
for row_id, supplier_info_str in rows:
    if supplier_info_str and 'doc_extracted' in supplier_info_str:
        try:
            info = json.loads(supplier_info_str)
            if 'llms_txt_preupdate' in info and 'doc_extracted' in info['llms_txt_preupdate']:
                print(row_id, info['llms_txt_preupdate']['doc_extracted'].keys())
                updated += 1
        except Exception as e:
            print("Error parsing row_id", row_id)

print(f"Rows with doc_extracted: {updated}")