import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend'))) 

from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting

def main():
    db = SessionLocal()
    existing = db.query(SystemAPISetting).filter(SystemAPISetting.provider == 'runninghub', SystemAPISetting.model == "sparkvideo-2.0").first()
    if existing:
        print(f"ID: {existing.id}")
        print(f"Name: {existing.name}")
        print(f"Config: {existing.config}")
    else:
        print("Not found")

if __name__ == '__main__':
    main()
