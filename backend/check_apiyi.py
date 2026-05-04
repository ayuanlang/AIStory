from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting

with SessionLocal() as db:
    settings = db.query(SystemAPISetting).filter(SystemAPISetting.provider.like('%apiyi%'), SystemAPISetting.category == 'LLM').all()
    for s in settings[:5]:
        print(f"prov={s.provider}, base={s.base_url}, config={s.config}")
