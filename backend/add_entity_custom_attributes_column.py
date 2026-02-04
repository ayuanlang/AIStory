
import sqlite3
import os

DB_PATH = "aistory.db"

def add_column():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        print("Attempting to add custom_attributes column to entities table...")
        cursor.execute("ALTER TABLE entities ADD COLUMN custom_attributes JSON DEFAULT '{}'")
        conn.commit()
        print("Success: Column custom_attributes added.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("Info: Column custom_attributes already exists.")
        else:
            print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_column()
