import json
from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting

with SessionLocal() as db:
    settings = db.query(SystemAPISetting).filter(SystemAPISetting.provider == 'zlhub').all()
    for s in settings:
        print(f"id={s.id}, category={s.category}, base_url={s.base_url}, config={s.config}")
