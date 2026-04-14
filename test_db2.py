import sys
import os
import json
sys.path.append('backend')
from app.db.session import SessionLocal
from app.models.all_models import FunctionAPIConfig

db = SessionLocal()
conf = db.query(FunctionAPIConfig).all()
for c in conf:
    print(c.function_name, json.dumps(c.api_settings))
