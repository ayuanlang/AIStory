import argparse

from sqlalchemy import create_engine, inspect, text

from app.core.config import mask_database_url, settings


REQUIRED_COLUMNS = [
    ("system_api_id", "INTEGER"),
    ("mode", "VARCHAR"),
]


def migrate(db_url: str | None = None) -> None:
    if db_url is None:
        db_url = settings.DATABASE_URL
    db_url = str(db_url or "").strip()
    if not db_url:
        raise ValueError("DATABASE_URL is empty")

    print(f"[migrate-api-settings] connecting: {mask_database_url(db_url)}")
    engine = create_engine(db_url)
    inspector = inspect(engine)
    if not inspector.has_table("api_settings"):
        print("[migrate-api-settings] api_settings table not found, skip")
        return

    is_postgres = engine.dialect.name == "postgresql"
    existing = {c["name"] for c in inspector.get_columns("api_settings")}
    added = 0

    with engine.begin() as conn:
        for col_name, col_type in REQUIRED_COLUMNS:
            if col_name in existing:
                continue
            if is_postgres:
                sql = f"ALTER TABLE api_settings ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
            else:
                sql = f"ALTER TABLE api_settings ADD COLUMN {col_name} {col_type}"
            try:
                conn.execute(text(sql))
                added += 1
                print(f"[migrate-api-settings] added api_settings.{col_name}")
            except Exception as exc:
                msg = str(exc).lower()
                if "duplicate" in msg or "already exists" in msg:
                    continue
                raise

    print(f"[migrate-api-settings] done | added_columns={added}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Patch missing columns on api_settings")
    parser.add_argument("--db-url", dest="db_url", default=None, help="Optional SQLAlchemy database URL override")
    args = parser.parse_args()
    migrate(db_url=args.db_url)
