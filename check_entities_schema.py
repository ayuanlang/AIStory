import sqlite3
import os

# Adjust DB path if needed. Assuming it's in backend/ or root.
# Usually backend/app.db or similar.
# Let's search for .db files first, but standard is often local.

db_path = "backend/aistory.db" # Guessing default
if not os.path.exists(db_path):
    # Try looking in current dir if script is run from backend
    db_path = "sql_app.db"

if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
try:
    cursor.execute("PRAGMA table_info(entities)")
    columns = [row[1] for row in cursor.fetchall()]
    print("Entities columns:", columns)
    
    needed = ['name_en', 'gender', 'role', 'archetype', 'appearance_cn', 'clothing', 'action_characteristics', 'visual_dependencies', 'dependency_strategy', 'generation_prompt_en', 'anchor_description']
    missing = [c for c in needed if c not in columns]
    if missing:
        print("Missing columns:", missing)
    else:
        print("All columns present.")
except Exception as e:
    print("Error:", e)
finally:
    conn.close()
