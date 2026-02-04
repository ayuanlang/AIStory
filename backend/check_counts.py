import sqlite3
import os

db_path = "aistory.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- Shots Count ---")
cursor.execute("SELECT count(*) FROM shots")
print(cursor.fetchone()[0])

print("--- Scenes Count ---")
cursor.execute("SELECT count(*) FROM scenes")
print(cursor.fetchone()[0])

print("--- First 5 Shots ---")
cursor.execute("SELECT id, scene_id, shot_number, title FROM shots LIMIT 5")
for r in cursor.fetchall():
    print(r)

conn.close()
