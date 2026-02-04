
import sqlite3

def add_columns():
    db_path = "aistory.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    columns = [
        ("title", "TEXT"),
        ("shot_type", "TEXT"),
        ("camera_position", "TEXT"),
        ("lens", "TEXT"),
        ("duration", "TEXT"),
        ("framing", "TEXT"),
        ("action", "TEXT"),
        ("dialogue", "TEXT"),
        ("technical_notes", "TEXT"),
        ("associated_entities", "TEXT")
    ]
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(shots)")
    existing_cols = [info[1] for info in cursor.fetchall()]
    
    print(f"Existing columns in 'shots': {existing_cols}")

    for col_name, col_type in columns:
        if col_name not in existing_cols:
            print(f"Adding column {col_name} to shots table...")
            try:
                cursor.execute(f"ALTER TABLE shots ADD COLUMN {col_name} {col_type}")
            except Exception as e:
                print(f"Error adding {col_name}: {e}")
        else:
            print(f"Column {col_name} already exists.")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    add_columns()
