import sqlite3
import os

db_path = "aistory.db"
if not os.path.exists(db_path):
    print("DB not found at", db_path)
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def table_exists(table_name):
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    return cursor.fetchone() is not None

def remove_columns():
    print("Starting schema cleanup for 'scenes' table...")
    
    has_scenes = table_exists("scenes")
    has_backup = table_exists("scenes_old")

    if has_backup:
        print("Found existing backup table 'scenes_old'.")
        if has_scenes:
            print("Found existing 'scenes' table. Assuming it is incomplete/new. Dropping it to recreate.")
            cursor.execute("DROP TABLE scenes")
            conn.commit()
    else:
        if has_scenes:
            print("Renaming 'scenes' to 'scenes_old'...")
            cursor.execute("ALTER TABLE scenes RENAME TO scenes_old")
            conn.commit()
        else:
            print("Error: No 'scenes' table found to migrate!")
            return

    # Now we are sure 'scenes_old' exists and 'scenes' does not.
    
    # 2. Create new table without unwanted columns
    print("Creating new table...")
    create_sql = """
    CREATE TABLE scenes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        episode_id INTEGER,
        scene_number VARCHAR,
        title VARCHAR,
        location VARCHAR,
        time_of_day VARCHAR,
        description TEXT,
        core_goal TEXT,
        environment_anchor TEXT,
        linked_characters TEXT,
        key_props TEXT,
        FOREIGN KEY(episode_id) REFERENCES episodes(id)
    )
    """
    cursor.execute(create_sql)
    
    # 3. Create Index
    print("Creating index...")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_scenes_id ON scenes (id)")
    
    # 4. Copy data
    print("Copying data...")
    cols = "id, episode_id, scene_number, title, location, time_of_day, description, core_goal, environment_anchor, linked_characters, key_props"
    
    try:
        cursor.execute(f"INSERT INTO scenes ({cols}) SELECT {cols} FROM scenes_old")
        count = cursor.rowcount
        print(f"Data copied successfully. Rows impacted: {count}")
        
        # 5. Drop old table
        print("Dropping old table...")
        cursor.execute("DROP TABLE scenes_old")
        
        conn.commit()
        print("Schema cleanup complete!")
        
    except Exception as e:
        print("Error during migration:", e)
        # conn.rollback() # Don't rollback immediately so we can inspect if needed, or just let it fail
        print("Aborted.")

remove_columns()
conn.close()
