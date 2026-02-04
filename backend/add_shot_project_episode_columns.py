
import sqlite3
import os

DB_PATH = "backend/aistory.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")

        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Check if columns exist
    cursor.execute("PRAGMA table_info(shots)")
    columns = [info[1] for info in cursor.fetchall()]
    
    print(f"Current columns in shots: {columns}")

    if 'project_id' not in columns:
        print("Adding project_id column...")
        cursor.execute("ALTER TABLE shots ADD COLUMN project_id INTEGER")
    
    if 'episode_id' not in columns:
        print("Adding episode_id column...")
        cursor.execute("ALTER TABLE shots ADD COLUMN episode_id INTEGER")

    # 2. Backfill Data
    print("Backfilling project_id and episode_id from scene relationships...")
    
    # Get all shots
    cursor.execute("SELECT id, scene_id FROM shots")
    shots = cursor.fetchall()
    
    updated_count = 0
    
    for shot_id, scene_id in shots:
        if not scene_id:
            continue
            
        # Get scene -> episode_id
        cursor.execute("SELECT episode_id FROM scenes WHERE id = ?", (scene_id,))
        scene_row = cursor.fetchone()
        
        if scene_row:
            episode_id = scene_row[0]
            
            # Get episode -> project_id
            cursor.execute("SELECT project_id FROM episodes WHERE id = ?", (episode_id,))
            episode_row = cursor.fetchone()
            
            if episode_row:
                project_id = episode_row[0]
                
                # Update Shot
                cursor.execute(
                    "UPDATE shots SET project_id = ?, episode_id = ? WHERE id = ?", 
                    (project_id, episode_id, shot_id)
                )
                updated_count += 1
    
    conn.commit()
    print(f"Migration complete. Updated {updated_count} shots.")
    conn.close()

if __name__ == "__main__":
    migrate()
