import traceback, requests 
from datetime import timedelta 
from app.db.session import SessionLocal 
from app.models.all_models import User 
from app.core.config import settings 
from jose import jwt 
try: 
    db = SessionLocal() 
    u=db.query(User).filter(User.username=='admin').first() 
    uid=u.id if u else  
    token = jwt.encode({'sub': str(uid)}, settings.SECRET_KEY, algorithm=settings.ALGORITHM) 
    r=requests.get('http://localhost:8000/api/v1/projects/?skip=0&limit=20', headers={'Authorization': 'Bearer ' + token}) 
    print(r.status_code, r.text[:2000]) 
except Exception as e: 
    traceback.print_exc() 
