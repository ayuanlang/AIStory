
import os
import sys
from sqlalchemy import create_engine, text, inspect

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings

def migrate():
    print(f"Connecting to database: {settings.DATABASE_URL}")
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        inspector = inspect(engine)
        
        # Check 'shots' table
        if 'shots' in inspector.get_table_names():
            columns = [c['name'] for c in inspector.get_columns('shots')]
            print(f"Existing columns in 'shots': {columns}")
            
            columns_to_add = [
                ("keyframes", "TEXT"),
                ("associated_entities", "TEXT"),
                ("shot_logic_cn", "TEXT"),
                ("scene_code", "VARCHAR"),
                ("project_id", "INTEGER"),
                ("episode_id", "INTEGER"),
                ("technical_notes", "TEXT"),
                ("image_url", "TEXT"),
                ("video_url", "TEXT"),
                ("prompt", "TEXT")
            ]
            
            for col_name, col_type in columns_to_add:
                print(f"Ensuring column '{col_name}' exists in 'shots' table...")
                try:
                    with conn.begin():
                        # Postgres 9.6+ syntax
                        conn.execute(text(f"ALTER TABLE shots ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                    print(f"Verified '{col_name}'")
                except Exception as e:
                    print(f"Error checking/adding '{col_name}': {e}")
                    # Fallback for older DBs if needed
                    if col_name not in columns:
                         try:
                            with conn.begin():
                                conn.execute(text(f"ALTER TABLE shots ADD COLUMN {col_name} {col_type}"))
                            print(f"Fallback add successful for {col_name}")
                         except Exception as e2:
                             print(f"Fallback failed: {e2}")
        else:
            print("Table 'shots' does not exist!")

if __name__ == "__main__":
    migrate()
