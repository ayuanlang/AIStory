from app.db.session import SessionLocal
from app.models.all_models import Asset
import json

db = SessionLocal()
assets = db.query(Asset).all()

print(f"Total Assets: {len(assets)}")
for a in assets[:10]:
    print(f"ID: {a.id}, Meta: {a.meta_info}")

db.close()
