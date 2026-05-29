
from app.db.session import engine
from sqlalchemy import text

with engine.begin() as conn:
    try:
        conn.execute(text('ALTER TABLE llm_call_logs ADD COLUMN request_id VARCHAR'))
        print('Added request_id column using VARCHAR')
    except Exception as e:
        print('Error:', e)
