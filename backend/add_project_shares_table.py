import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from sqlalchemy import create_engine, text, inspect
from app.core.config import settings


def add_project_shares_table():
    db_url = settings.DATABASE_URL
    if len(sys.argv) > 1:
        db_url = sys.argv[1]

    print(f"Connecting to database: {db_url}")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        try:
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            if "project_shares" in tables:
                print("Table 'project_shares' already exists.")
                return

            db_url_str = str(engine.url)
            ddl = """
            CREATE TABLE project_shares (
                id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at VARCHAR,
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """

            if 'postgresql' in db_url_str or 'postgres' in db_url_str:
                trans = conn.begin()
                try:
                    conn.execute(text("""
                        CREATE TABLE project_shares (
                            id SERIAL PRIMARY KEY,
                            project_id INTEGER NOT NULL REFERENCES projects(id),
                            user_id INTEGER NOT NULL REFERENCES users(id),
                            created_at VARCHAR
                        );
                    """))
                    conn.execute(text("CREATE INDEX idx_project_shares_project_id ON project_shares(project_id);"))
                    conn.execute(text("CREATE INDEX idx_project_shares_user_id ON project_shares(user_id);"))
                    conn.execute(text("CREATE UNIQUE INDEX uq_project_shares_project_user ON project_shares(project_id, user_id);"))
                    trans.commit()
                    print("Successfully created 'project_shares' table (Postgres).")
                except Exception:
                    trans.rollback()
                    raise
            else:
                conn.execute(text(ddl))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_project_shares_project_id ON project_shares(project_id);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_project_shares_user_id ON project_shares(user_id);"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_project_shares_project_user ON project_shares(project_id, user_id);"))
                print("Successfully created 'project_shares' table (SQLite).")
        except Exception as e:
            print(f"Error during migration: {e}")


if __name__ == "__main__":
    add_project_shares_table()
