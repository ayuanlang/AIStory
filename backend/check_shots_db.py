
import sqlite3
import os

# Database file path
DB_FILE = os.path.join(os.path.dirname(__file__), "aistory.db")

def check_structure():
    if not os.path.exists(DB_FILE):
        print(f"Database not found at {DB_FILE}")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        print("--- Checking 'shots' table schema ---")
        cursor.execute("PRAGMA table_info(shots)")
        columns = cursor.fetchall()
        
        col_names = [col[1] for col in columns]
        for name in col_names:
            print(f" - {name}")

        if "shot_logic_cn" in col_names:
            print("\n[OK] 'shot_logic_cn' column exists.")
        else:
            print("\n[FAIL] 'shot_logic_cn' column MISSING.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_structure()
