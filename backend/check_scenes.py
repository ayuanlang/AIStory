import sqlite3

db_path = "aistory.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- First 10 Scenes ---")
cursor.execute("SELECT id, scene_number, title FROM scenes LIMIT 10")
for r in cursor.fetchall():
    print(r)

conn.close()
