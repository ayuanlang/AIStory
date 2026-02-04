import sqlite3
import os

def check_and_add_column(db_path, table_name, column_name, column_type):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [info[1] for info in cursor.fetchall()]
    
    if column_name not in columns:
        print(f"Adding column {column_name} to table {table_name}...")
        try:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            conn.commit()
            print("Column added successfully.")
        except Exception as e:
            print(f"Error adding column: {e}")
    else:
        print(f"Column {column_name} already exists in {table_name}.")

    conn.close()

if __name__ == "__main__":
    db_path = "backend/aistory.db"
    check_and_add_column(db_path, "shots", "shot_logic_cn", "TEXT")
