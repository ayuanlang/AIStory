import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import engine
from sqlalchemy import text

def run():
    queries = [
        "ALTER TABLE llm_call_logs ADD COLUMN user_id INTEGER;",
        "ALTER TABLE llm_call_logs ADD COLUMN user_name VARCHAR;",
        "ALTER TABLE llm_call_logs ADD COLUMN project_id INTEGER;",
        "ALTER TABLE llm_call_logs ADD COLUMN action VARCHAR;"
    ]
    
    for query in queries:
        try:
            with engine.connect() as conn:
                # In SQLAlchemy 2.0+, we must explicitly commit for connect()
                conn.execute(text(query))
                conn.commit()
                print(f"Success: {query}")
        except Exception as e:
            print(f"Skipped {query.split('ADD COLUMN ')[-1].split(' ')[0]}: {e}")

if __name__ == "__main__":
    run()