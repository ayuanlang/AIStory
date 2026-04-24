"""Migration: add project_id and episode_id columns to transaction_history table."""
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from sqlalchemy import create_engine, text, inspect
from app.core.config import settings


def add_columns():
    db_url = settings.DATABASE_URL
    if len(sys.argv) > 1:
        db_url = sys.argv[1]

    print(f"Connecting to database: {db_url}")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        inspector = inspect(engine)
        existing_columns = [c['name'] for c in inspector.get_columns('transaction_history')]
        print(f"Existing columns in 'transaction_history': {existing_columns}")

        db_url_str = str(engine.url)
        is_postgres = 'postgresql' in db_url_str or 'postgres' in db_url_str

        columns_to_add = [
            ("project_id", "INTEGER"),
            ("episode_id", "INTEGER"),
        ]

        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                print(f"Adding '{col_name}' to 'transaction_history'...")
                if is_postgres:
                    trans = conn.begin()
                    try:
                        conn.execute(text(f"ALTER TABLE transaction_history ADD COLUMN {col_name} {col_type}"))
                        conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_transaction_history_{col_name} ON transaction_history ({col_name})"))
                        trans.commit()
                        print(f"Added {col_name} (Postgres).")
                    except Exception as e:
                        trans.rollback()
                        print(f"Error adding {col_name} (Postgres): {e}")
                else:
                    try:
                        conn.execute(text(f"ALTER TABLE transaction_history ADD COLUMN {col_name} {col_type}"))
                        print(f"Added {col_name} (SQLite).")
                    except Exception as e:
                        print(f"Error adding {col_name} (SQLite): {e}")
            else:
                print(f"Column '{col_name}' already exists, skipping.")

    print("Migration complete.")


if __name__ == "__main__":
    add_columns()
