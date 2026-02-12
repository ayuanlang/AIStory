import sqlite3
import os

db_path = "aistory.db"
if not os.path.exists(db_path):
    print("DB not found at", db_path)
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get columns for shots table
cursor.execute("PRAGMA table_info(shots)")
columns = [info[1] for info in cursor.fetchall()]
print("Current columns in shots table:", columns)

# Add 'keyframes' if missing
if 'keyframes' not in columns:
    print("Adding column 'keyframes'...")
    try:
        cursor.execute("ALTER TABLE shots ADD COLUMN keyframes TEXT")
        conn.commit()
        print("Column 'keyframes' added successfully.")
    except Exception as e:
        print("Error adding keyframes column:", e)
else:
    print("Column 'keyframes' already exists.")

conn.close()
