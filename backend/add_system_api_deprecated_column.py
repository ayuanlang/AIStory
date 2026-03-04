from app.db.session import SessionLocal
from sqlalchemy import text
import json


def _to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw in {"1", "true", "yes", "y", "on"}:
            return True
        if raw in {"0", "false", "no", "n", "off", "", "none", "null"}:
            return False
    return bool(value)


def _deprecated_from_config(config_value):
    cfg = {}
    if isinstance(config_value, dict):
        cfg = config_value
    elif isinstance(config_value, str):
        raw = config_value.strip()
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    cfg = parsed
            except Exception:
                cfg = {}
    return bool(
        _to_bool(cfg.get("deprecated"))
        or _to_bool(cfg.get("is_deprecated"))
        or _to_bool(cfg.get("disable_api"))
    )


def _backfill(session):
    rows = session.execute(text("SELECT id, config FROM system_api_settings")).fetchall()
    changed = 0
    for row in rows:
        deprecated = 1 if _deprecated_from_config(row[1]) else 0
        session.execute(
            text("UPDATE system_api_settings SET deprecated = :deprecated WHERE id = :id"),
            {"deprecated": deprecated, "id": row[0]},
        )
        changed += 1
    session.commit()
    print(f"Backfilled deprecated for {changed} rows.")


def add_column():
    session = SessionLocal()
    try:
        dialect = session.bind.dialect.name
        if dialect == "sqlite":
            result = session.execute(text("PRAGMA table_info(system_api_settings)"))
            columns = [row[1] for row in result]
            if "deprecated" in columns:
                print("Column deprecated already exists.")
                return
            print("Adding deprecated column to system_api_settings (sqlite)...")
            session.execute(text("ALTER TABLE system_api_settings ADD COLUMN deprecated BOOLEAN DEFAULT 0"))
            session.execute(text("UPDATE system_api_settings SET deprecated = 0 WHERE deprecated IS NULL"))
            session.commit()
            _backfill(session)
            print("Done.")
            return

        result = session.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='system_api_settings' AND column_name='deprecated'
        """))
        exists = result.first() is not None
        if exists:
            print("Column deprecated already exists.")
            _backfill(session)
            return

        print(f"Adding deprecated column to system_api_settings ({dialect})...")
        session.execute(text("ALTER TABLE system_api_settings ADD COLUMN deprecated BOOLEAN DEFAULT FALSE"))
        session.execute(text("UPDATE system_api_settings SET deprecated = FALSE WHERE deprecated IS NULL"))
        session.commit()
        _backfill(session)
        print("Done.")
    except Exception as e:
        print(f"Error: {e}")
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    add_column()
