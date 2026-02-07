
from app.db.session import engine
from sqlalchemy import inspect

inspector = inspect(engine)
columns = [c['name'] for c in inspector.get_columns('users')]
print(f"Columns in users table: {columns}")

required_columns = ['is_authorized', 'is_system']
missing = [c for c in required_columns if c not in columns]
print(f"Missing columns: {missing}")
