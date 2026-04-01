import sqlite3
conn = sqlite3.connect('aistory.db')
cur = conn.cursor()
cur.execute('SELECT id, name, type, image_url FROM entities WHERE project_id=67')
rows = cur.fetchall()
for r in rows: print(r)
