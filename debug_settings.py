
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from backend.app.db.session import SessionLocal
from backend.app.models.all_models import APISetting

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
