import sqlite3
import os
import sys

def migrate_logic(db_path):
    print(f"Connecting to: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Add credits column to users
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN credits INTEGER DEFAULT 100")
        print("Added 'credits' column to 'users' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("'credits' column already exists.")
        else:
            print(f"Error adding credits column: {e}")

    # 2. Create pricing_rules table
    try:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pricing_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider VARCHAR,
            model VARCHAR,
            task_type VARCHAR NOT NULL,
            cost INTEGER DEFAULT 1,
            unit_type VARCHAR DEFAULT 'per_call',
            description VARCHAR,
            is_active BOOLEAN DEFAULT 1
        )
        """)
        # Index
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_pricing_rules_provider ON pricing_rules (provider)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_pricing_rules_task_type ON pricing_rules (task_type)")
        print("Created 'pricing_rules' table.")
    except Exception as e:
        print(f"Error creating pricing_rules: {e}")

    # 3. Create transaction_history table
    try:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS transaction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            task_type VARCHAR,
            provider VARCHAR,
            model VARCHAR,
            details JSON,
            created_at VARCHAR,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_transaction_history_user_id ON transaction_history (user_id)")
        print("Created 'transaction_history' table.")
    except Exception as e:
        print(f"Error creating transaction_history: {e}")
    
    # 4. Seed basic pricing rules
    try:
        cursor.execute("SELECT count(*) FROM pricing_rules")
        count = cursor.fetchone()[0]
        if count == 0:
            seed_data = [
                ('openai', 'gpt-4', 'llm_chat', 10, 'per_call', 'Expensive GPT4 call'),
                ('openai', 'gpt-3.5-turbo', 'llm_chat', 1, 'per_call', 'Cheap chat'),
                (None, None, 'image_gen', 5, 'per_call', 'Generic Image Gen'),
                (None, None, 'video_gen', 20, 'per_call', 'Generic Video Gen'),
                (None, None, 'analysis', 2, 'per_call', 'Image Analysis'),
                (None, None, 'analysis_character', 3, 'per_call', 'Character Analysis'),
            ]
            cursor.executemany("INSERT INTO pricing_rules (provider, model, task_type, cost, unit_type, description) VALUES (?, ?, ?, ?, ?, ?)", seed_data)
            print("Seeded default pricing rules.")
    except Exception as e:
        print(f"Seeding failed: {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")

def migrate():
    print("Starting billing migration...")
    
    # Path resolution logic
    candidates = [
        "backend/aistory.db",
        "aistory.db",
        "../aistory.db"
    ]
    
    db_path = None
    for c in candidates:
        if os.path.exists(c):
            db_path = c
            break
            
    if not db_path:
        print("Error: Could not find aistory.db in: " + ", ".join(candidates))
        return

    migrate_logic(db_path)

if __name__ == "__main__":
    migrate()
