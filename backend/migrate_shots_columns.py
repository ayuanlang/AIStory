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
        cursor.execute("PRAGMA table_info(shots)")
        columns = [info[1] for info in cursor.fetchall()]
        print(f"Current columns: {columns}")
        
        # 0. Check if we already have the old table from a failed run
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shots_old_v2'")
        if cursor.fetchone():
            print("Found 'shots_old_v2' from previous run.")
            
            # Check if 'shots' is empty
            cursor.execute("SELECT count(*) FROM shots")
            count = cursor.fetchone()[0]
            print(f"Current 'shots' table has {count} rows.")
            
            if count == 0:
                print("New 'shots' table is empty. Dropping it to restart migration.")
                cursor.execute("DROP TABLE shots")
                # Also ensure indexes are dropped
                indexes_to_drop = ["ix_shots_id", "ix_shots_project_id", "ix_shots_episode_id"]
                for idx in indexes_to_drop:
                    cursor.execute(f"DROP INDEX IF EXISTS {idx}")
            else:
                if 'shot_id' in columns:
                     print("Table 'shots' has data and new columns. Migration considered complete.")
                     return

        # Double check if shots exists now (it shouldn't if we dropped it)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shots'")
        if not cursor.fetchone():
             # 'shots' does not exist (or we dropped it). But 'shots_old_v2' exists (checked above or will be renamed).
             cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shots_old_v2'")
             if not cursor.fetchone():
                 print("Neither shots nor shots_old_v2 exists. Nothing to migrate.")
                 return
        
        # Logic:
        # If 'shots' exists and has old columns -> Rename to shots_old_v2
        # If 'shots' does not exist and shots_old_v2 exists -> Proceed to create new shots
        
        cursor.execute("PRAGMA table_info(shots)")
        current_columns = [info[1] for info in cursor.fetchall()]

        if 'shot_number' in current_columns:
            print("Renaming old 'shots' table...")
            # Drop indexes on the old table to free up names
            indexes_to_drop = ["ix_shots_id", "ix_shots_project_id", "ix_shots_episode_id"]
            for idx in indexes_to_drop:
                cursor.execute(f"DROP INDEX IF EXISTS {idx}")
                
            cursor.execute("ALTER TABLE shots RENAME TO shots_old_v2")
        
        # 2. Create new table
        # id, scene_id, project_id, episode_id, shot_id, shot_name, scene_code, start_frame, end_frame, video_content, duration, associated_entities, technical_notes, image_url, video_url, prompt
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS shots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id INTEGER,
            project_id INTEGER,
            episode_id INTEGER,
            
            shot_id VARCHAR,
            shot_name VARCHAR,
            scene_code VARCHAR,
            
            start_frame TEXT,
            end_frame TEXT,
            video_content TEXT,
            duration VARCHAR,
            associated_entities TEXT,
            
            technical_notes TEXT,
            image_url VARCHAR,
            video_url VARCHAR,
            prompt TEXT,
            
            FOREIGN KEY(scene_id) REFERENCES scenes(id)
        );
        """
        cursor.execute(create_table_sql)
        
        # Create indexes if not exist
        cursor.execute("DROP INDEX IF EXISTS ix_shots_id")
        cursor.execute("CREATE INDEX ix_shots_id ON shots (id)")
        cursor.execute("DROP INDEX IF EXISTS ix_shots_project_id")
        cursor.execute("CREATE INDEX ix_shots_project_id ON shots (project_id)")
        cursor.execute("DROP INDEX IF EXISTS ix_shots_episode_id")
        cursor.execute("CREATE INDEX ix_shots_episode_id ON shots (episode_id)")
        print("Created new table 'shots'")

        # 3. Copy data
        print("Migrating data from shots_old_v2...")
        insert_sql = """
        INSERT INTO shots (
            id, scene_id, shot_id, shot_name, start_frame, end_frame, video_content, duration, associated_entities, technical_notes, image_url, video_url, prompt
        )
        SELECT 
            id, scene_id, shot_number, title, camera_position, camera_movement, description, duration, associated_entities, technical_notes, image_url, video_url, prompt
        FROM shots_old_v2
        """
        cursor.execute(insert_sql)
        print("Basic data copied.")

        # 4. Backfill project_id and episode_id
        print("Backfilling relational IDs...")
        cursor.execute("""
            UPDATE shots 
            SET episode_id = (SELECT episode_id FROM scenes WHERE scenes.id = shots.scene_id)
        """)
        cursor.execute("""
            UPDATE shots 
            SET project_id = (SELECT project_id FROM episodes WHERE episodes.id = (SELECT episode_id FROM scenes WHERE scenes.id = shots.scene_id))
        """)
        cursor.execute("""
            UPDATE shots
            SET scene_code = (SELECT scene_no FROM scenes WHERE scenes.id = shots.scene_id)
        """)
        print("Backfill complete.")

        # 5. Drop old table
        cursor.execute("DROP TABLE shots_old_v2")
        print("Dropped old table")
        
        conn.commit()
        print("Migration successful")

        # 6. Verify
        cursor.execute("PRAGMA table_info(shots)")
        new_columns = [info[1] for info in cursor.fetchall()]
        print(f"New columns: {new_columns}")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_db()
