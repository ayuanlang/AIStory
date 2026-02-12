
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
                ("episode_id", "INTEGER")
            ]
            
            for col_name, col_type in columns_to_add:
                if col_name not in columns:
                    print(f"Adding column '{col_name}' to 'shots' table...")
                    try:
                        with conn.begin():
                            conn.execute(text(f"ALTER TABLE shots ADD COLUMN {col_name} {col_type}"))
                        print(f"Successfully added '{col_name}'")
                    except Exception as e:
                        print(f"Error adding '{col_name}': {e}")
                else:
                    print(f"Column '{col_name}' already exists.")
        else:
            print("Table 'shots' does not exist!")

if __name__ == "__main__":
    migrate()
