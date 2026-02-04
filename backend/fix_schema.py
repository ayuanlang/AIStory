import sqlite3
import os

db_path = "aistory.db"
if not os.path.exists(db_path):
    print("DB not found at", db_path)
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get columns
cursor.execute("PRAGMA table_info(api_settings)")
columns = [info[1] for info in cursor.fetchall()]
print("Current columns:", columns)

# Add 'name' if missing
if 'name' not in columns:
    print("Adding column 'name'...")
    try:
        cursor.execute("ALTER TABLE api_settings ADD COLUMN name VARCHAR DEFAULT 'Default'")
        conn.commit()
    except Exception as e:
        print("Error adding name:", e)

# Add 'category' if missing (just in case, as user code relies on it)
if 'category' not in columns:
    print("Adding column 'category'...")
    try:
        cursor.execute("ALTER TABLE api_settings ADD COLUMN category VARCHAR DEFAULT 'LLM'")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_api_settings_category ON api_settings (category)")
        conn.commit()
    except Exception as e:
        print("Error adding category:", e)

# Add 'is_active' if missing
if 'is_active' not in columns:
     print("Adding column 'is_active'...")
     try:
         cursor.execute("ALTER TABLE api_settings ADD COLUMN is_active BOOLEAN DEFAULT 0")
         conn.commit()
     except Exception as e:
         print("Error adding is_active:", e)

conn.close()
print("Schema update complete.")
