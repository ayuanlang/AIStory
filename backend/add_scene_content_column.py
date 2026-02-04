from app.db.session import SessionLocal, engine
from app.models.all_models import Episode
from sqlalchemy import text

def add_column():
    session = SessionLocal()
    try:
        # Check if column exists
        result = session.execute(text("PRAGMA table_info(episodes)"))
        columns = [row[1] for row in result]
        if "scene_content" not in columns:
            print("Adding scene_content column...")
            session.execute(text("ALTER TABLE episodes ADD COLUMN scene_content TEXT"))
            session.commit()
            print("Done.")
        else:
            print("Column scene_content already exists.")
    except Exception as e:
        print(f"Error: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    add_column()
