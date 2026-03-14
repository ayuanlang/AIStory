import argparse
import os
import sys
from typing import List, Tuple

from sqlalchemy import create_engine, inspect, text

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CURRENT_DIR)

from app.core.config import settings  # noqa: E402


# Minimal, schema-only patch: add missing columns used by ORM queries.
REQUIRED_COLUMNS: List[Tuple[str, str]] = [
    ("generation_modes", "JSON"),
    ("input_formats", "JSON"),
    ("output_format", "VARCHAR"),
    ("supported_resolutions", "JSON"),
    ("aspect_ratios", "JSON"),
    ("max_images_per_call", "INTEGER"),
    ("reference_image_limit", "VARCHAR"),
    ("reference_video_limit", "VARCHAR"),
    ("durations_seconds", "JSON"),
    ("max_duration", "INTEGER"),
    ("fps_options", "JSON"),
    ("image_size_values", "JSON"),
    ("quality_values", "JSON"),
    ("has_audio", "BOOLEAN"),
    ("sound_supported", "BOOLEAN"),
    ("multi_shots_supported", "BOOLEAN"),
    ("mode_values", "JSON"),
    ("text_capabilities", "JSON"),
    ("image_capabilities", "JSON"),
    ("video_capabilities", "JSON"),
    ("digital_human_capabilities", "JSON"),
    ("voice_capabilities", "JSON"),
    ("music_capabilities", "JSON"),
    ("pricing_unit", "VARCHAR"),
    ("token_billing_supported", "BOOLEAN"),
    ("input_token_price", "FLOAT"),
    ("output_token_price", "FLOAT"),
    ("per_resolution_price_map", "JSON"),
    ("per_duration_price_map", "JSON"),
    ("has_tiered_pricing", "BOOLEAN"),
    ("free_quota", "VARCHAR"),
    ("currency", "VARCHAR"),
    ("price_avg_cost", "INTEGER"),
    ("price_source", "VARCHAR"),
    ("price_min_cost", "INTEGER"),
    ("price_max_cost", "INTEGER"),
    ("price_sample_prices", "JSON"),
    ("price_updated_at", "VARCHAR"),
    ("provider_price_avg_cost", "INTEGER"),
    ("provider_price_source", "VARCHAR"),
    ("provider_price_min_cost", "INTEGER"),
    ("provider_price_max_cost", "INTEGER"),
    ("provider_price_sample_prices", "JSON"),
    ("provider_price_updated_at", "VARCHAR"),
]


def migrate(db_url: str | None = None) -> None:
    if db_url is None:
        db_url = settings.DATABASE_URL
    db_url = str(db_url or "").strip()
    if not db_url:
        raise ValueError("DATABASE_URL is empty")

    print(f"[migrate] connecting: {db_url}")
    engine = create_engine(db_url)
    inspector = inspect(engine)
    is_postgres = engine.dialect.name == "postgresql"

    existing = {c["name"] for c in inspector.get_columns("system_api_settings")}
    added = 0

    with engine.begin() as conn:
        for col_name, col_type in REQUIRED_COLUMNS:
            if col_name in existing:
                continue

            if is_postgres:
                sql = f"ALTER TABLE system_api_settings ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
            else:
                # SQLite fallback: no IF NOT EXISTS on some versions.
                sql = f"ALTER TABLE system_api_settings ADD COLUMN {col_name} {col_type}"

            try:
                conn.execute(text(sql))
                added += 1
                print(f"[migrate] added system_api_settings.{col_name}")
            except Exception as exc:
                # For non-Postgres fallback, tolerate 'duplicate column' style errors.
                msg = str(exc).lower()
                if "duplicate" in msg or "already exists" in msg:
                    continue
                raise

    print(f"[migrate] done | added_columns={added}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Patch missing columns on system_api_settings")
    parser.add_argument("--db-url", dest="db_url", default=None, help="Optional SQLAlchemy database URL override")
    args = parser.parse_args()
    migrate(db_url=args.db_url)
