import re

def main():
    path = "backend/app/db/init_db.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    migration_func = """
def _ensure_transaction_schema(is_postgres: bool = False):
    from sqlalchemy import inspect, text
    from .session import engine
    from ..models.all_models import TransactionHistory, TransactionAction
    import logging
    logger = logging.getLogger(__name__)

    try:
        inspector = inspect(engine)

        # Ensure transaction_history columns
        if inspector.has_table("transaction_history"):
            cols = {c['name'] for c in inspector.get_columns("transaction_history")}
            with engine.begin() as conn:
                if "description" not in cols:
                    if is_postgres:
                        conn.execute(text("ALTER TABLE transaction_history ADD COLUMN description VARCHAR"))
                    else:
                        conn.execute(text("ALTER TABLE transaction_history ADD COLUMN description VARCHAR"))
                    logger.info("Added description to transaction_history")

        # Ensure transaction_action columns
        if inspector.has_table("transaction_action"):
            cols = {c['name'] for c in inspector.get_columns("transaction_action")}
            with engine.begin() as conn:
                if "project_id" not in cols:
                    if is_postgres:
                        conn.execute(text("ALTER TABLE transaction_action ADD COLUMN project_id INTEGER REFERENCES projects(id)"))
                    else:
                        conn.execute(text("ALTER TABLE transaction_action ADD COLUMN project_id INTEGER REFERENCES projects(id)"))
                        
                if "episode_id" not in cols:
                    if is_postgres:
                        conn.execute(text("ALTER TABLE transaction_action ADD COLUMN episode_id INTEGER REFERENCES episodes(id)"))
                    else:
                        conn.execute(text("ALTER TABLE transaction_action ADD COLUMN episode_id INTEGER REFERENCES episodes(id)"))
                    logger.info("Added project_id and episode_id to transaction_action")
                    
    except Exception as e:
        logger.error(f"Failed to migrate transaction tables: {e}")

def check_and_migrate_tables"""

    if "_ensure_transaction_schema" not in content:
        content = content.replace("def check_and_migrate_tables", migration_func)
        
        # Inject call
        call_statement = """
        _ensure_minimum_runtime_schema(is_postgres=is_postgres)
        _ensure_transaction_schema(is_postgres=is_postgres)
"""
        content = content.replace("_ensure_minimum_runtime_schema(is_postgres=is_postgres)", call_statement.strip())
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("Patched init_db.py")
    else:
        print("Already patched")

if __name__ == "__main__":
    main()
