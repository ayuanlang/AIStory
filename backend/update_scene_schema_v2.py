
import sqlite3

def add_columns():
    db_path = "aistory.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    columns = [
        ("title", "TEXT"),
        ("equivalent_duration", "TEXT"),
        ("core_goal", "TEXT"),
        ("core_conflict", "TEXT"),
        ("visual_foreshadowing", "TEXT"),
        ("three_act_structure", "TEXT"),
        ("environment_anchor", "TEXT")
    ]
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(scenes)")
    existing_cols = [info[1] for info in cursor.fetchall()]
    
    for col_name, col_type in columns:
        if col_name not in existing_cols:
            print(f"Adding column {col_name} to scenes table...")
            try:
                cursor.execute(f"ALTER TABLE scenes ADD COLUMN {col_name} {col_type}")
            except Exception as e:
                print(f"Error adding {col_name}: {e}")
        else:
            print(f"Column {col_name} already exists.")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    add_columns()
