import sys
import os

# Add the parent directory to sys.path so we can import app modules
# Assuming this script is run from backend/ directory
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from sqlalchemy import create_engine, text, inspect
from app.core.config import settings

def add_credits_column():
    # Allow overriding database via command line argument
    db_url = settings.DATABASE_URL
    if len(sys.argv) > 1:
        db_url = sys.argv[1]

    print(f"Connecting to database: {db_url}")
    
    # Create engine for the target database
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        try:
            # Use SQLAlchemy Inspector for reliable column check
            inspector = inspect(engine)
            existing_columns = [c['name'] for c in inspector.get_columns('users')]
            print(f"Existing columns in 'users': {existing_columns}")

            # Check database type
            db_url_str = str(engine.url)
            
            if 'credits' in existing_columns:
                print("Column 'credits' already exists in users table.")
                return

            print("Adding 'credits' column to users table...")
            
            if 'postgresql' in db_url_str or 'postgres' in db_url_str:
                # Postgres requires commit for ALTER
                trans = conn.begin()
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN credits INTEGER DEFAULT 0;"))
                    trans.commit()
                    print("Successfully added 'credits' column (Postgres).")
                except Exception as e:
                    trans.rollback()
                    raise e
            else:
                # SQLite
                conn.execute(text("ALTER TABLE users ADD COLUMN credits INTEGER DEFAULT 0;"))
                # conn.commit() # SQLite autocommits DDL usually, but some drivers separate it
                print("Successfully added 'credits' column (SQLite).")

        except Exception as e:
            print(f"Error during migration: {e}")

if __name__ == "__main__":
    add_credits_column()
