import sys
import os

# Add the parent directory to sys.path so we can import app modules
# Assuming this script is run from backend/ directory
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from sqlalchemy import create_engine, text, inspect
from app.core.config import settings

def add_columns():
    # Allow overriding database via command line argument
    db_url = settings.DATABASE_URL
    if len(sys.argv) > 1:
        db_url = sys.argv[1]

    print(f"Connecting to database: {db_url}")
    
    # Create engine for the target database
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        try:
            inspector = inspect(engine)
            existing_columns = [c['name'] for c in inspector.get_columns('scenes')]
            print(f"Existing columns in 'scenes': {existing_columns}")

            # Check database type
            db_url_str = str(engine.url)
            is_postgres = 'postgresql' in db_url_str or 'postgres' in db_url_str

            if 'ai_shots_result' not in existing_columns:
                print("Adding 'ai_shots_result' to 'scenes' table...")
                if is_postgres:
                    trans = conn.begin()
                    try:
                        conn.execute(text("ALTER TABLE scenes ADD COLUMN ai_shots_result TEXT;")) # or JSONB if supported
                        trans.commit()
                        print("Added ai_shots_result (Postgres).")
                    except Exception as e:
                        trans.rollback()
                        print(f"Error adding ai_shots_result (Postgres): {e}")
                else:
                    try:
                        conn.execute(text("ALTER TABLE scenes ADD COLUMN ai_shots_result TEXT;"))
                        print("Added ai_shots_result (SQLite).")
                    except Exception as e:
                        print(f"Error adding ai_shots_result (SQLite): {e}")
            else:
                print("'ai_shots_result' already exists.")

        except Exception as e:
            print(f"Error checking/migrating schema: {e}")

if __name__ == "__main__":
    add_columns()
