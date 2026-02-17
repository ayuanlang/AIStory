
import sqlite3
import os

db_path = "backend/aistory.db"

if not os.path.exists(db_path):
    print(f"Error: {db_path} not found.")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE pricing_rules ADD COLUMN cost_input INTEGER DEFAULT 0")
    print("Added cost_input column")
except Exception as e:
    print(f"Warning: cost_input exist? {e}")

try:
    cursor.execute("ALTER TABLE pricing_rules ADD COLUMN cost_output INTEGER DEFAULT 0")
    print("Added cost_output column")
except Exception as e:
    print(f"Warning: cost_output exist? {e}")
    
conn.commit()
conn.close()
