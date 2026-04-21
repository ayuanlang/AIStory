import traceback 
from app.db.session import SessionLocal 
from app.api.endpoints import read_projects 
from app.models.all_models import User 
try: 
    db = SessionLocal() 
    u = db.query(User).first() 
    read_projects(skip=0, limit=20, db=db, current_user=u) 
    print('Success!') 
except Exception as e: 
    traceback.print_exc() 
