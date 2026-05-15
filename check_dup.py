import sqlite3

conn = sqlite3.connect('backend/aistory.db')
c = conn.cursor()
c.execute('SELECT url, COUNT(*) FROM assets GROUP BY url HAVING COUNT(*) > 1 LIMIT 10')
rows = c.fetchall()
for r in rows:
    print(f"Dup URL: {r[0]} Output count: {r[1]}")
