"""Ensure assets.meta_info and related columns exist (SQLite + PostgreSQL)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

from sqlalchemy import create_engine, inspect, text

from app.core.config import settings
from app.models import all_models as models


def _compile_column_type(column, dialect) -> str:
    try:
        return column.type.compile(dialect=dialect)
    except Exception:
        return str(column.type)


def _count_meta_coverage(conn, is_postgres: bool) -> dict:
    if is_postgres:
        sql = text(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE meta_info IS NOT NULL
                      AND (
                        COALESCE(meta_info->>'width', '') <> ''
                        OR COALESCE(meta_info->>'resolution', '') <> ''
                      )
                ) AS with_resolution
            FROM assets
            """
        )
    else:
        sql = text(
            """
            SELECT
                COUNT(*) AS total,
                SUM(
                    CASE
                        WHEN meta_info IS NOT NULL
                         AND (
                            instr(meta_info, '"width"') > 0
                            OR instr(meta_info, '"resolution"') > 0
                         )
                        THEN 1 ELSE 0
                    END
                ) AS with_resolution
            FROM assets
            """
        )
    row = conn.execute(sql).mappings().first()
    total = int(row["total"] or 0) if row else 0
    with_resolution = int(row["with_resolution"] or 0) if row else 0
    return {
        "total": total,
        "with_resolution": with_resolution,
        "missing_resolution": max(0, total - with_resolution),
    }


def ensure_assets_columns(db_url: str | None = None) -> int:
    db_url = db_url or settings.DATABASE_URL
    print(f"[assets-meta] connecting to {db_url}")
    engine = create_engine(db_url)
    is_postgres = engine.dialect.name == "postgresql"
    inspector = inspect(engine)

    if not inspector.has_table("assets"):
        print("[assets-meta] assets table missing; create_all should create it on boot")
        return 0

    existing_cols = {col["name"] for col in inspector.get_columns("assets")}
    print(f"[assets-meta] existing columns: {sorted(existing_cols)}")

    missing_columns = [
        column
        for column in models.Asset.__table__.columns
        if not column.primary_key and column.name not in existing_cols
    ]

    if missing_columns:
        with engine.begin() as conn:
            for column in missing_columns:
                column_type_sql = _compile_column_type(column, engine.dialect)
                if is_postgres:
                    ddl = f"ALTER TABLE assets ADD COLUMN IF NOT EXISTS {column.name} {column_type_sql}"
                else:
                    ddl = f"ALTER TABLE assets ADD COLUMN {column.name} {column_type_sql}"
                print(f"[assets-meta] applying: {ddl}")
                conn.execute(text(ddl))
        print(
            "[assets-meta] added columns:",
            ", ".join(column.name for column in missing_columns),
        )
    else:
        print("[assets-meta] all model columns already present")

    with engine.connect() as conn:
        coverage = _count_meta_coverage(conn, is_postgres)
        print(
            "[assets-meta] coverage:",
            json.dumps(coverage, ensure_ascii=False),
        )
        if coverage["missing_resolution"] > 0:
            print(
                "[assets-meta] hint: run `python backfill_assets_metadata.py --limit 200` "
                "or use Assets Library -> Backfill Metadata in the UI"
            )

    return len(missing_columns)


if __name__ == "__main__":
    override_url = sys.argv[1] if len(sys.argv) > 1 else None
    added = ensure_assets_columns(override_url)
    sys.exit(0 if added >= 0 else 1)
