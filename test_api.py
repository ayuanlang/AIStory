import sys; sys.path.append('backend')
from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting
db = SessionLocal()
cfg = db.query(SystemAPISetting).filter(SystemAPISetting.id==1083).first()
print(f'{cfg.id} {cfg.provider} {cfg.model}' if cfg else 'None')
