import requests 
from jose import jwt 
from app.core.config import settings 
token = jwt.encode({'sub': '4'}, settings.SECRET_KEY, algorithm=settings.ALGORITHM) 
r=requests.get('http://localhost:8000/api/v1/projects/?skip=0&limit=20', headers={'Authorization': 'Bearer ' + token}) 
print(r.status_code, r.text[:2000]) 
