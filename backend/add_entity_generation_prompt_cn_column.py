import os
import sqlite3


def add_column() -> None:
    db_path = os.getenv("AISTORY_DB_PATH", "aistory.db")
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(__file__), db_path)

    if not os.path.exists(db_path):
        print(f"DB not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(entities)")
        columns = [row[1] for row in cursor.fetchall()]

        if "generation_prompt_cn" in columns:
            print("entities.generation_prompt_cn already exists")
            return

        cursor.execute("ALTER TABLE entities ADD COLUMN generation_prompt_cn TEXT")
        conn.commit()
        print("Added entities.generation_prompt_cn")
    finally:
        conn.close()


if __name__ == "__main__":
    add_column()
