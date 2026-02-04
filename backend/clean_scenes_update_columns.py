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
        cursor.execute("ALTER TABLE scenes RENAME TO scenes_old_v2")
        
        # 2. Create new table
        # id, episode_id, scene_number, title, description, equivalent_duration, core_goal, environment_anchor, linked_characters, key_props
        create_table_sql = """
        CREATE TABLE scenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            episode_id INTEGER,
            scene_number VARCHAR,
            title VARCHAR,
            description TEXT,
            equivalent_duration VARCHAR,
            core_goal TEXT,
            environment_anchor TEXT,
            linked_characters TEXT,
            key_props TEXT,
            FOREIGN KEY(episode_id) REFERENCES episodes(id)
        );
        """
        cursor.execute(create_table_sql)
        print("Created new table 'scenes'")

        # 3. Copy data
        # We select only the columns that exist in the old table and match the new table
        # excluding location, time_of_day
        # equivalent_duration is new, so it stays default (NULL)
        
        # Identify common columns based on what we know existed
        # We assume id, episode_id, scene_number, title, description, core_goal, environment_anchor, linked_characters, key_props exist
        # But we must be safe.
        
        common_cols = []
        target_cols = ['id', 'episode_id', 'scene_number', 'title', 'description', 'core_goal', 'environment_anchor', 'linked_characters', 'key_props']
        
        # Verify which target cols exist in source (columns list)
        for col in target_cols:
            if col in columns:
                common_cols.append(col)
            else:
                print(f"Warning: Column {col} missing in source table, skipping copy for this column.")
        
        cols_str = ", ".join(common_cols)
        
        insert_sql = f"INSERT INTO scenes ({cols_str}) SELECT {cols_str} FROM scenes_old_v2"
        cursor.execute(insert_sql)
        print(f"Copied data using columns: {cols_str}")

        # 4. Drop old table
        cursor.execute("DROP TABLE scenes_old_v2")
        print("Dropped old table")
        
        conn.commit()
        print("Migration successful: Added equivalent_duration, Removed location/time_of_day")

        # 5. Verify
        cursor.execute("PRAGMA table_info(scenes)")
        new_columns = [info[1] for info in cursor.fetchall()]
        print(f"New columns: {new_columns}")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        # Restore if failed (basic attempt)
        try:
            cursor.execute("DROP TABLE IF EXISTS scenes")
            cursor.execute("ALTER TABLE scenes_old_v2 RENAME TO scenes")
            print("Restored original table due to error.")
            conn.commit()
        except:
            pass
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_db()
