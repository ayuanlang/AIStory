from app.main import app
from app.api.endpoints import get_current_user

def mock_get_current_user():
    class MockUser:
        id = 1
        username = "admin"
        is_superuser = True
    return MockUser()

app.dependency_overrides[get_current_user] = mock_get_current_user

from fastapi.testclient import TestClient
client = TestClient(app)

print("GET:")
res = client.get("/api/v1/projects/28/episodes")
print(res.status_code, res.text[:2000])

print("POST:")
res2 = client.post("/api/v1/projects/28/episodes", json={"title": "Test Ep"})
print(res2.status_code, res2.text[:2000])
