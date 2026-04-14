import sys
sys.path.insert(0, "C:\\AIStory\\backend")
from app.db.session import SessionLocal
from app.models.user import User
from app.api.endpoints import read_entities
db = SessionLocal()
try:
    u = db.query(User).first()
    print("User", u)
    read_entities(275, None, db, u)
except Exception as e:
    import traceback; traceback.print_exc()
