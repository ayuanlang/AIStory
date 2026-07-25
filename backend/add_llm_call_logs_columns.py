import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import engine
from sqlalchemy import text

def run():
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE llm_call_logs ADD COLUMN user_id INTEGER;"))
            print("Added user_id")
        except Exception as e:
            print("Skipped user_id:", e)
            
        try:
            conn.execute(text("ALTER TABLE llm_call_logs ADD COLUMN user_name VARCHAR;"))
            print("Added user_name")
        except Exception as e:
            print("Skipped user_name:", e)
            
        try:
            conn.execute(text("ALTER TABLE llm_call_logs ADD COLUMN project_id INTEGER;"))
            print("Added project_id")
        except Exception as e:
            print("Skipped project_id:", e)
            
        try:
            conn.execute(text("ALTER TABLE llm_call_logs ADD COLUMN action VARCHAR;"))
            print("Added action")
        except Exception as e:
            print("Skipped action:", e)

if __name__ == "__main__":
    run()