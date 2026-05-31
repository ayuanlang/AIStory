import sqlite3
db = sqlite3.connect('c:/AS/AIStory/backend/aistory.db')
cur = db.cursor()
cur.execute('SELECT task_id, status, error, result_json FROM async_tasks ORDER BY id DESC LIMIT 50')
res = cur.fetchall()
for r in res:
    if r[3] and 'Episode ID |' in r[3]:
        print(f"Task: {r[0]}, Status: {r[1]}, Error: {r[2]}")
        print(f"Result length: {len(r[3])}")
        print(f"Sample: {r[3][:200]}")
        print("-" * 50)
