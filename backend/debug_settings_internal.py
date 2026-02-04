
import sys
import os

# Enable importing 'app' from current directory
sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.models.all_models import APISetting

def dump_settings():
    session = SessionLocal()
    try:
        settings = session.query(APISetting).all()
        print(f"Found {len(settings)} settings:")
        for s in settings:
            print(f"ID={s.id} Provider='{s.provider}' Category='{s.category}' Active={s.is_active} Model='{s.model}' Config={s.config} URL='{s.base_url}'")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    dump_settings()
