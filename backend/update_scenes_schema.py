import sqlite3
import os

db_path = "aistory.db"
if not os.path.exists(db_path):
    # Try finding it in backend folder if running from root
    if os.path.exists("backend/aistory.db"):
        db_path = "backend/aistory.db"
    else:
        print("DB not found at", db_path)
        # It's possible it doesn't exist yet, but endpoints usually imply it does.
        # If not, create_tables.py works.
        pass

print(f"Checking database at: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get columns for scenes
    cursor.execute("PRAGMA table_info(scenes)")
    columns = [info[1] for info in cursor.fetchall()]
    print("Current scenes columns:", columns)

    columns_to_add = [
        ("linked_characters", "TEXT"),
        ("key_props", "TEXT"),
        ("environment_anchor", "TEXT"),
        ("core_goal", "TEXT"),
        ("equivalent_duration", "VARCHAR"),
        ("scene_number", "VARCHAR"), # Should exist
        ("title", "VARCHAR"),
        ("location", "VARCHAR"),
        ("time_of_day", "VARCHAR"),
        ("description", "TEXT")
    ]

    for col_name, col_type in columns_to_add:
        if col_name not in columns:
            print(f"Adding column '{col_name}'...")
            try:
                cursor.execute(f"ALTER TABLE scenes ADD COLUMN {col_name} {col_type}")
                conn.commit()
                print(f"Added {col_name}")
            except Exception as e:
                print(f"Error adding {col_name}: {e}")

    conn.close()
    print("Scenes schema update complete.")
except Exception as e:
    print(f"Failed to connect or update: {e}")
