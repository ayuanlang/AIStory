
from app.db.session import engine
from sqlalchemy import text
import sys
import os

# Add backend to sys.path
sys.path.append(os.getcwd())

def check_schema():
    with engine.connect() as connection:
        result = connection.execute(text("PRAGMA table_info(scenes)"))
        columns = [row[1] for row in result]
        print("Scenes Columns:", columns)
        
        result_shots = connection.execute(text("PRAGMA table_info(shots)"))
        columns_shots = [row[1] for row in result_shots]
        print("Shots Columns:", columns_shots)

if __name__ == "__main__":
    check_schema()
