import sqlite3
import os

db_path = "aistory.db"
# Should handle abs path if needed but working dir is usually root
if not os.path.exists(db_path):
    # Try finding it in backend/aistory.db if running from root
    db_path = "backend/aistory.db"

if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

print(f"Updating DB at {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(entities)")
minfos = cursor.fetchall()
columns = [m[1] for m in minfos]

if "generation_prompt_en" not in columns:
    print("Adding generation_prompt_en...")
    cursor.execute("ALTER TABLE entities ADD COLUMN generation_prompt_en TEXT")

if "anchor_description" not in columns:
    print("Adding anchor_description...")
    cursor.execute("ALTER TABLE entities ADD COLUMN anchor_description TEXT")

conn.commit()
conn.close()
print("Done.")
