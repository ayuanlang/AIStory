import sqlite3
import os

# Adjust path to your database file
DB_PATH = "c:\\storyboard\\AIStory\\backend\\aistory.db" 

# If you configure differently in .env, you might need to read it. 
# But usually it's storyboard.db in backend root or similar. 
# Let's try to find it or just assume standard.
# If not found, the script will just print error, which is fine for now.

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}. Skipping migration.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    columns = [
        ("is_active", "BOOLEAN DEFAULT 1"),
        ("is_superuser", "BOOLEAN DEFAULT 0"),
        ("is_authorized", "BOOLEAN DEFAULT 0"),
        ("is_system", "BOOLEAN DEFAULT 0")
    ]
    
    for col_name, col_def in columns:
        try:
            print(f"Adding column {col_name}...")
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
            print(f"Added {col_name}.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column {col_name} already exists.")
            else:
                print(f"Error adding {col_name}: {e}")
                
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
