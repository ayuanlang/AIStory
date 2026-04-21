from app.services.auth_service import create_access_token 
from datetime import timedelta 
token = create_access_token(data={'sub': '4'}, expires_delta=timedelta(minutes=15)) 
print(token) 
