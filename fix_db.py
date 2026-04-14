import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))
from app.db.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    db.execute(text('ALTER TABLE "episodes" ADD COLUMN "ai_entity_design_result" TEXT;'))
    db.commit()
    print("Column added.")
except Exception as e:
    print(e)
finally:
    db.close()
