import sys, os
sys.path.append(os.getcwd())
from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting
from sqlalchemy import text

TO_DELETE = [
    # Image
    "grok-imagine", "flux-2", "imagen4-fast", "imagen4-ultra", "ideogram", "qwen-image", "recraft", "topaz",
    # Video
    "kling-v2.1", "kling-v2.5", "sora2", "bytedance-v1-pro", "bytedance-v1-lite", "hailuo", "wan-turbo", "grok-imagine-video"
]

with SessionLocal() as db:
    rows = db.query(SystemAPISetting).filter(SystemAPISetting.provider == 'kie', SystemAPISetting.model.in_(TO_DELETE)).all()
    count = len(rows)
    for r in rows:
        db.delete(r)
    db.commit()
    print(f"Deleted {count} legacy duplicate KIE models.")
