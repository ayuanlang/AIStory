from sqlalchemy import inspect, text

from app.db.session import engine, SessionLocal
from app.models.all_models import APISetting


def run() -> None:
    dialect = engine.dialect.name
    is_postgres = dialect == "postgresql"

    inspector = inspect(engine)
    if not inspector.has_table("api_settings"):
        print("[migrate] api_settings table not found, skip")
        return

    existing_cols = {c["name"] for c in inspector.get_columns("api_settings")}

    with engine.begin() as conn:
        if "system_api_id" not in existing_cols:
            if is_postgres:
                conn.execute(text("ALTER TABLE api_settings ADD COLUMN IF NOT EXISTS system_api_id INTEGER"))
            else:
                conn.execute(text("ALTER TABLE api_settings ADD COLUMN system_api_id INTEGER"))
            print("[migrate] added api_settings.system_api_id")

        if "mode" not in existing_cols:
            if is_postgres:
                conn.execute(text("ALTER TABLE api_settings ADD COLUMN IF NOT EXISTS mode VARCHAR"))
            else:
                conn.execute(text("ALTER TABLE api_settings ADD COLUMN mode VARCHAR"))
            print("[migrate] added api_settings.mode")

    updated = 0
    dropped = 0

    with SessionLocal() as session:
        rows = session.query(APISetting).order_by(APISetting.id.desc()).all()
        seen = set()
        for row in rows:
            category = str(getattr(row, "category", "") or "").strip() or "LLM"
            if category != (getattr(row, "category", None) or ""):
                row.category = category
                updated += 1

            mode = str(getattr(row, "mode", "") or "").strip().lower() or None
            if mode != getattr(row, "mode", None):
                row.mode = mode
                updated += 1

            key = (int(getattr(row, "user_id", 0) or 0), category)
            if key in seen:
                session.delete(row)
                dropped += 1
                continue
            seen.add(key)

        session.commit()

    with engine.begin() as conn:
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_api_settings_user_category_idx ON api_settings (user_id, category)"))

        # Drop deprecated overlap columns from user api_settings.
        existing_cols = {c["name"] for c in inspect(engine).get_columns("api_settings")}
        for legacy_col in ["name", "is_active", "provider", "api_key", "base_url", "model", "config"]:
            if legacy_col not in existing_cols:
                continue
            if is_postgres:
                conn.execute(text(f"ALTER TABLE api_settings DROP COLUMN IF EXISTS {legacy_col}"))
            else:
                conn.execute(text(f"ALTER TABLE api_settings DROP COLUMN {legacy_col}"))
            print(f"[migrate] dropped api_settings.{legacy_col}")

    print(f"[migrate] done updated={updated} dropped_duplicates={dropped}")


if __name__ == "__main__":
    run()
