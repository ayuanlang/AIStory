import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from sqlalchemy import create_engine, text, inspect
from app.core.config import settings

def add_column():
    db_url = settings.DATABASE_URL
    if len(sys.argv) > 1:
        db_url = sys.argv[1]

    print(f"Connecting to database: {db_url}")
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        try:
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns('episodes')]
            
            if "ai_scene_analysis_subject_index" not in columns:
                print("Adding ai_scene_analysis_subject_index column...")
                conn.execute(text(
                    "ALTER TABLE episodes ADD COLUMN ai_scene_analysis_subject_index TEXT"
                ))
                conn.commit()
                print("✓ Column added successfully")
            else:
                print("✓ Column already exists")
        except Exception as e:
            print(f"✗ Error: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    add_column()
