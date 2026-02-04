import sqlite3
import os

DB_PATH = "aistory.db"

def add_columns():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    columns = [
        ("atmosphere", "TEXT"),
        ("visual_params", "TEXT"),
        ("narrative_description", "TEXT")
    ]
    
    for col_name, col_type in columns:
        try:
            print(f"Attempting to add {col_name} column to entities table...")
            cursor.execute(f"ALTER TABLE entities ADD COLUMN {col_name} {col_type}")
            conn.commit()
            print(f"Success: Column {col_name} added.")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print(f"Column {col_name} already exists.")
            else:
                print(f"Error adding {col_name}: {e}")

    conn.close()

if __name__ == "__main__":
    add_columns()
