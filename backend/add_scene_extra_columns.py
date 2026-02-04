import sqlite3
import os

db_path = "aistory.db"
if not os.path.exists(db_path):
    print("DB not found at", db_path)
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get columns
cursor.execute("PRAGMA table_info(scenes)")
columns = [info[1] for info in cursor.fetchall()]
print("Current columns in scenes:", columns)

if 'linked_characters' not in columns:
    print("Adding column 'linked_characters'...")
    try:
        cursor.execute("ALTER TABLE scenes ADD COLUMN linked_characters TEXT")
        conn.commit()
        print("Success.")
    except Exception as e:
        print("Error adding linked_characters:", e)

if 'key_props' not in columns:
    print("Adding column 'key_props'...")
    try:
        cursor.execute("ALTER TABLE scenes ADD COLUMN key_props TEXT")
        conn.commit()
        print("Success.")
    except Exception as e:
        print("Error adding key_props:", e)

conn.close()
