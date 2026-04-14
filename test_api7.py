import sys; sys.path.append('backend')
from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting
db = SessionLocal()
rows = db.query(SystemAPISetting).filter(SystemAPISetting.category=='Image', SystemAPISetting.deprecated==False).all()
print(f'Total image APIs: {len(rows)}')
