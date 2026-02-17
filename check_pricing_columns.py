import sqlite3
import os

db_path = "backend/aistory.db"
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
try:
    cursor.execute("PRAGMA table_info(pricing_rules)")
    columns = cursor.fetchall()
    print("Columns in pricing_rules:")
    for col in columns:
        print(col)
except Exception as e:
    print(e)
conn.close()
