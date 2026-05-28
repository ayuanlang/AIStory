import requests
response = requests.get('http://127.0.0.1:8000/api/projects/243/entities', headers={"Authorization": "Bearer 12345"}) # Assuming test env or we can directly query DB? We already queried the DB!
