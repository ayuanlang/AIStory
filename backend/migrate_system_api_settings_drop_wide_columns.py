import argparse

from sqlalchemy import create_engine, inspect, text

from app.core.config import settings


DROP_COLUMNS = [
    "generation_modes",
    "input_formats",
    "output_format",
    "supported_resolutions",
    "aspect_ratios",
    "max_images_per_call",
    "reference_image_limit",
    "reference_video_limit",
    "durations_seconds",
    "max_duration",
    "fps_options",
    "image_size_values",
    "quality_values",
    "has_audio",
    "sound_supported",
    "multi_shots_supported",
    "mode_values",
    "text_capabilities",
    "image_capabilities",
    "video_capabilities",
    "digital_human_capabilities",
    "voice_capabilities",
    "music_capabilities",
    "pricing_unit",
    "token_billing_supported",
    "input_token_price",
    "output_token_price",
    "per_resolution_price_map",
    "per_duration_price_map",
    "has_tiered_pricing",
    "free_quota",
    "currency",
]


def migrate(db_url: str | None = None) -> None:
    if db_url is None:
        db_url = settings.DATABASE_URL
    db_url = str(db_url or "").strip()
    if not db_url:
        raise ValueError("DATABASE_URL is empty")

    print(f"[drop-wide-columns] connecting: {db_url}")
    engine = create_engine(db_url)
    inspector = inspect(engine)

    if not inspector.has_table("system_api_settings"):
        print("[drop-wide-columns] system_api_settings table not found, skip")
        return

    is_postgres = engine.dialect.name == "postgresql"
    existing = {c["name"] for c in inspector.get_columns("system_api_settings")}
    dropped = 0
    skipped = 0

    with engine.begin() as conn:
        for col_name in DROP_COLUMNS:
            if col_name not in existing:
                skipped += 1
                continue
            if is_postgres:
                sql = f"ALTER TABLE system_api_settings DROP COLUMN IF EXISTS {col_name}"
            else:
                sql = f"ALTER TABLE system_api_settings DROP COLUMN {col_name}"
            try:
                conn.execute(text(sql))
                dropped += 1
                print(f"[drop-wide-columns] dropped system_api_settings.{col_name}")
            except Exception as exc:
                msg = str(exc).lower()
                # Old SQLite versions may not support DROP COLUMN.
                if not is_postgres and ("syntax error" in msg or "near \"drop\"" in msg):
                    print(
                        "[drop-wide-columns] sqlite does not support DROP COLUMN in this runtime; "
                        f"skip {col_name}"
                    )
                    skipped += 1
                    continue
                raise

    print(f"[drop-wide-columns] done | dropped_columns={dropped} skipped={skipped}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Drop deprecated wide columns on system_api_settings")
    parser.add_argument("--db-url", dest="db_url", default=None, help="Optional SQLAlchemy database URL override")
    args = parser.parse_args()
    migrate(db_url=args.db_url)
