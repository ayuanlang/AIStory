import sqlite3
import os

DB_PATH = "aistory.db"

def migrate_db():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check current columns
        cursor.execute("PRAGMA table_info(scenes)")
        columns = [info[1] for info in cursor.fetchall()]
        print(f"Current columns: {columns}")
        
        # 1. Rename existing table
        cursor.execute("ALTER TABLE scenes RENAME TO scenes_old_v3")
        
        # 2. Create new table with updated column names
        create_table_sql = """
        CREATE TABLE scenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            episode_id INTEGER,
            scene_no VARCHAR,
            scene_name VARCHAR,
            original_script_text TEXT,
            equivalent_duration VARCHAR,
            core_scene_info TEXT,
            environment_name TEXT,
            linked_characters TEXT,
            key_props TEXT,
            FOREIGN KEY(episode_id) REFERENCES episodes(id)
        );
        """
        cursor.execute(create_table_sql)
        print("Created new table 'scenes' with renamed columns")

        # 3. Copy data
        # Mapping:
        # scene_number -> scene_no
        # title -> scene_name
        # description -> original_script_text
        # equivalent_duration -> equivalent_duration
        # core_goal -> core_scene_info
        # environment_anchor -> environment_name
        # linked_characters -> linked_characters
        # key_props -> key_props
        
        insert_sql = """
        INSERT INTO scenes (id, episode_id, scene_no, scene_name, original_script_text, equivalent_duration, core_scene_info, environment_name, linked_characters, key_props)
        SELECT id, episode_id, scene_number, title, description, equivalent_duration, core_goal, environment_anchor, linked_characters, key_props
        FROM scenes_old_v3
        """
        
        cursor.execute(insert_sql)
        print("Copied data to new columns")

        # 4. Drop old table
        cursor.execute("DROP TABLE scenes_old_v3")
        print("Dropped old table")
        
        conn.commit()
        print("Migration successful")

        # 5. Verify
        cursor.execute("PRAGMA table_info(scenes)")
        new_columns = [info[1] for info in cursor.fetchall()]
        print(f"New columns: {new_columns}")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_db()
