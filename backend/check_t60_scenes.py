import sqlite3
conn = sqlite3.connect('aistory.db')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM scenes WHERE project_id=67')
print('Scenes:', cur.fetchone()[0])
cur.execute('SELECT COUNT(*) FROM episodes WHERE project_id=67')
print('Episodes:', cur.fetchone()[0])
