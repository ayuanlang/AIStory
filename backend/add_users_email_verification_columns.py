import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from sqlalchemy import create_engine, text, inspect
from app.core.config import settings


def add_users_email_verification_columns():
    db_url = settings.DATABASE_URL
    if len(sys.argv) > 1:
        db_url = sys.argv[1]

    print(f"Connecting to database: {db_url}")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        inspector = inspect(engine)
        existing_columns = [c['name'] for c in inspector.get_columns('users')]
        print(f"Existing columns in 'users': {existing_columns}")

        columns_to_add = [
            ("account_status", "INTEGER DEFAULT 1"),
            ("email_verified", "BOOLEAN DEFAULT FALSE"),
            ("email_verification_code", "VARCHAR"),
            ("email_verification_expires_at", "VARCHAR"),
        ]

        for col_name, col_type in columns_to_add:
            if col_name in existing_columns:
                print(f"Column '{col_name}' already exists.")
                continue
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
                print(f"Added '{col_name}'.")
            except Exception as e:
                print(f"Failed to add '{col_name}': {e}")


if __name__ == "__main__":
    add_users_email_verification_columns()
