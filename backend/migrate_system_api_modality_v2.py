"""
Migration script: Convert system_api_settings.modality from VARCHAR to JSON.
Also adds the new 'tags' column (JSON).

Run from the backend directory:
    python migrate_system_api_modality_v2.py

This script:
1. Reads all existing system_api_settings rows
2. Converts legacy string modality values (e.g. "text-to-image,image-to-image")
   to the new JSON format: {"generation_modes": ["t2i", "i2i"]}
3. Adds the 'tags' column if missing
4. Handles both PostgreSQL and SQLite

The new modality JSON schema:
{
    "generation_modes": ["t2i", "i2i"],       // 生成方式
    "max_resolution": "2048x2048",             // 最高分辨率
    "aspect_ratios": ["1:1", "16:9", "9:16"], // 支持的画幅比
    "has_audio": false,                        // 是否有声
    "max_duration": null,                      // 最大时长(秒)
    "base_model": "seedream-4.5",             // 基础模型
    "model_version": "v4.5",                  // 模型版本
    "model_type": "diffusion",                // 模型类型
    "input_formats": ["text", "image"],       // 输入格式
    "output_format": "image"                  // 输出格式
}

The new tags JSON schema (separate column):
["真人写实", "局部重绘", "高清", "快速生成"]
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))

from app.db.session import SessionLocal, engine
from app.models.all_models import SystemAPISetting
from app.services.modality_utils import migrate_legacy_modality_string
from sqlalchemy import inspect, text


def run_migration():
    inspector = inspect(engine)
    is_postgres = engine.dialect.name == 'postgresql'

    if not inspector.has_table("system_api_settings"):
        print("Table system_api_settings does not exist. Nothing to migrate.")
        return

    existing_cols = {c['name'] for c in inspector.get_columns('system_api_settings')}

    # Step 1: Add tags column if missing
    if 'tags' not in existing_cols:
        with engine.begin() as conn:
            if is_postgres:
                conn.execute(text("ALTER TABLE system_api_settings ADD COLUMN IF NOT EXISTS tags JSON"))
            else:
                conn.execute(text("ALTER TABLE system_api_settings ADD COLUMN tags JSON"))
        print("Added 'tags' column.")

    # Step 2: Check if modality column type needs migration
    modality_col_info = None
    for col in inspector.get_columns('system_api_settings'):
        if col['name'] == 'modality':
            modality_col_info = col
            break

    need_type_migration = False
    if modality_col_info:
        col_type_str = str(modality_col_info.get('type', '')).upper()
        if 'VARCHAR' in col_type_str or 'TEXT' in col_type_str or 'CHAR' in col_type_str:
            need_type_migration = True

    if need_type_migration:
        print("Detected VARCHAR modality column. Migrating to JSON...")

        # Read existing values before schema change
        with SessionLocal() as session:
            rows = session.execute(
                text("SELECT id, modality FROM system_api_settings WHERE modality IS NOT NULL AND modality != ''")
            ).fetchall()
            legacy_values = {row[0]: row[1] for row in rows}
            print(f"  Found {len(legacy_values)} rows with non-null modality string values.")

        # Alter column type
        with engine.begin() as conn:
            if is_postgres:
                # PostgreSQL: use USING to cast, then backfill
                conn.execute(text(
                    "ALTER TABLE system_api_settings "
                    "ALTER COLUMN modality TYPE JSON USING NULL::json"
                ))
                print("  Altered column type to JSON (PostgreSQL).")
            else:
                # SQLite: rename + recreate
                conn.execute(text("ALTER TABLE system_api_settings RENAME COLUMN modality TO modality_legacy"))
                conn.execute(text("ALTER TABLE system_api_settings ADD COLUMN modality JSON"))
                conn.execute(text("ALTER TABLE system_api_settings DROP COLUMN modality_legacy"))
                print("  Altered column type to JSON (SQLite).")

        # Backfill converted JSON values
        with SessionLocal() as session:
            migrated = 0
            for row_id, old_val in legacy_values.items():
                new_val = migrate_legacy_modality_string(old_val)
                if new_val:
                    row = session.query(SystemAPISetting).filter(SystemAPISetting.id == row_id).first()
                    if row:
                        row.modality = new_val
                        migrated += 1
            session.commit()
            print(f"  Backfilled {migrated} rows with converted JSON modality values.")
    else:
        if modality_col_info:
            print("Modality column is already JSON type. Skipping type migration.")
        else:
            print("Modality column doesn't exist. It will be created as JSON on next startup.")

    # Step 3: Convert any remaining string modality values in the DB (safety net)
    with SessionLocal() as session:
        all_rows = session.query(SystemAPISetting).all()
        converted = 0
        for row in all_rows:
            if isinstance(row.modality, str):
                new_val = migrate_legacy_modality_string(row.modality)
                row.modality = new_val
                converted += 1
        if converted:
            session.commit()
            print(f"Converted {converted} additional string modality values to JSON.")

    print("\nMigration complete!")
    print("New modality JSON format: {\"generation_modes\": [\"t2i\", \"i2i\"], ...}")
    print("New tags column: [\"真人写实\", \"局部重绘\", ...]")


if __name__ == "__main__":
    run_migration()
