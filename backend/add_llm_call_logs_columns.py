import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import engine
from sqlalchemy import inspect, text


def run():
    desired = [
        ("user_id", "INTEGER"),
        ("user_name", "VARCHAR"),
        ("project_id", "INTEGER"),
        ("action", "VARCHAR"),
        ("charged_amount", "INTEGER"),
    ]

    inspector = inspect(engine)
    if "llm_call_logs" not in inspector.get_table_names():
        print("Skip: llm_call_logs table does not exist")
        return

    existing = {c["name"] for c in inspector.get_columns("llm_call_logs")}

    for name, sql_type in desired:
        if name in existing:
            print(f"Skip: column {name} already exists")
            continue
        query = f"ALTER TABLE llm_call_logs ADD COLUMN {name} {sql_type};"
        try:
            with engine.connect() as conn:
                conn.execute(text(query))
                conn.commit()
                print(f"Success: {query}")
        except Exception as e:
            print(f"Skipped {name}: {e}")


if __name__ == "__main__":
    run()
