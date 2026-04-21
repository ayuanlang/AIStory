import traceback, requests 
from datetime import timedelta 
from app.core.security import create_access_token 
token = create_access_token(4, expires_delta=timedelta(minutes=15)) 
try: 
  r = requests.get('http://localhost:8000/api/v1/projects/?skip=0&limit=20', headers={'Authorization': 'Bearer ' + token}) 
  print(r.status_code) 
  print(r.text[:1000]) 
except Exception as e: 
  traceback.print_exc() 
