import sys
import os

# Add the parent directory to sys.path so we can import app modules
# Assuming this script is run from backend/ directory
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from sqlalchemy import create_engine, text
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
            # Check database type
            db_url_str = str(engine.url)
            
            if 'postgresql' in db_url_str or 'postgres' in db_url_str:
                # Postgres check
                check_sql = text("SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='credits';")
                result = conn.execute(check_sql).fetchone()
                
                if result:
                    print("Column 'credits' already exists in users table (Postgres).")
                else:
                    print("Adding 'credits' column to users table (Postgres instruction)...")
                    # Postgres requires commit for ALTER
                    trans = conn.begin()
                    try:
                        conn.execute(text("ALTER TABLE users ADD COLUMN credits INTEGER DEFAULT 0;"))
                        trans.commit()
                        print("Successfully added 'credits' column.")
                    except Exception as e:
                        trans.rollback()
                        raise e
                    
            else:
                # SQLite check
                check_sql = text("PRAGMA table_info(users);")
                columns = conn.execute(check_sql).fetchall()
                # columns result format: (cid, name, type, notnull, dflt_value, pk)
                column_names = [col[1] for col in columns]
                
                if 'credits' in column_names:
                    print("Column 'credits' already exists in users table (SQLite).")
                else:
                    print("Adding 'credits' column to users table (SQLite)...")
                    conn.execute(text("ALTER TABLE users ADD COLUMN credits INTEGER DEFAULT 0;"))
                    conn.commit()
                    print("Successfully added 'credits' column.")

        except Exception as e:
            print(f"Error during migration: {e}")

if __name__ == "__main__":
    add_credits_column()
