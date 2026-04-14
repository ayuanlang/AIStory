from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting

db = SessionLocal()
setting = db.query(SystemAPISetting).filter(SystemAPISetting.id == 1062).first()
if setting:
    print("Found! ID:", setting.id, "Category:", setting.category, "Provider:", setting.provider)
else:
    print("Not found!")
