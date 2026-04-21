import traceback 
from app.db.session import SessionLocal 
from app.api.endpoints import read_projects, ProjectOut 
from app.models.all_models import User 
try: 
    db = SessionLocal() 
    users = db.query(User).all() 
    for u in users: 
        projects = read_projects(skip=0, limit=20, db=db, current_user=u) 
        for p in projects: 
            ProjectOut.from_orm(p) 
    print('Serialization Success on all users!') 
except Exception as e: 
    traceback.print_exc() 
