import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DICT_CSV = ROOT / "_kie_system_data_standard_dictionary.csv"
MAP_CSV = ROOT / "_kie_system_to_model_enum_mapping.csv"

OUT_SCHEMA = ROOT / "_kie_system_data_standard_schema.sql"
OUT_SEED = ROOT / "_kie_system_data_standard_seed.sql"


def esc(v: str) -> str:
    return str(v or "").replace("'", "''")


def main() -> None:
    if not DICT_CSV.exists():
        raise FileNotFoundError(f"Missing input: {DICT_CSV}")
    if not MAP_CSV.exists():
        raise FileNotFoundError(f"Missing input: {MAP_CSV}")

    schema_sql = """-- KIE system data standard schema (SQLite)
PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS kie_system_data_standard_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_dimension TEXT NOT NULL,
    standard_value TEXT NOT NULL,
    value_type TEXT NOT NULL,
    definition TEXT,
    alias_values TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(standard_dimension, standard_value)
);

CREATE TABLE IF NOT EXISTS kie_system_data_standard_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    model_key_inferred TEXT,
    model_title TEXT,
    model_url TEXT,
    source_field TEXT NOT NULL,
    source_enum_value TEXT NOT NULL,
    standard_dimension TEXT NOT NULL,
    standard_value TEXT NOT NULL,
    confidence TEXT,
    note TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(provider, model_key_inferred, source_field, source_enum_value, standard_dimension, standard_value)
);

CREATE INDEX IF NOT EXISTS ix_kie_std_values_dim
ON kie_system_data_standard_values(standard_dimension, is_active);

CREATE INDEX IF NOT EXISTS ix_kie_std_mappings_lookup
ON kie_system_data_standard_mappings(provider, model_key_inferred, standard_dimension, source_field, is_active);

COMMIT;
"""
    OUT_SCHEMA.write_text(schema_sql, encoding="utf-8")

    lines = []
    lines.append("-- Generated seed SQL for KIE data standard tables")
    lines.append("BEGIN TRANSACTION;")

    dict_count = 0
    with DICT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        for r in rd:
            lines.append(
                "INSERT INTO kie_system_data_standard_values "
                "(standard_dimension, standard_value, value_type, definition, alias_values, is_active, updated_at) VALUES "
                f"('{esc(r.get('standard_dimension'))}', '{esc(r.get('standard_value'))}', '{esc(r.get('value_type'))}', "
                f"'{esc(r.get('definition'))}', '{esc(r.get('alias_values'))}', 1, datetime('now')) "
                "ON CONFLICT(standard_dimension, standard_value) DO UPDATE SET "
                "value_type=excluded.value_type, definition=excluded.definition, alias_values=excluded.alias_values, "
                "is_active=excluded.is_active, updated_at=datetime('now');"
            )
            dict_count += 1

    map_count = 0
    with MAP_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        for r in rd:
            lines.append(
                "INSERT INTO kie_system_data_standard_mappings "
                "(provider, model_key_inferred, model_title, model_url, source_field, source_enum_value, "
                "standard_dimension, standard_value, confidence, note, is_active, updated_at) VALUES "
                f"('{esc(r.get('provider'))}', '{esc(r.get('model_key_inferred'))}', '{esc(r.get('model_title'))}', "
                f"'{esc(r.get('model_url'))}', '{esc(r.get('source_field'))}', '{esc(r.get('source_enum_value'))}', "
                f"'{esc(r.get('standard_dimension'))}', '{esc(r.get('standard_value'))}', '{esc(r.get('confidence'))}', "
                f"'{esc(r.get('note'))}', 1, datetime('now')) "
                "ON CONFLICT(provider, model_key_inferred, source_field, source_enum_value, standard_dimension, standard_value) "
                "DO UPDATE SET model_title=excluded.model_title, model_url=excluded.model_url, confidence=excluded.confidence, "
                "note=excluded.note, is_active=excluded.is_active, updated_at=datetime('now');"
            )
            map_count += 1

    lines.append("COMMIT;")
    OUT_SEED.write_text("\n".join(lines), encoding="utf-8")

    print(f"Generated: {OUT_SCHEMA}")
    print(f"Generated: {OUT_SEED}")
    print(f"standard_values_rows={dict_count}")
    print(f"mapping_rows={map_count}")


if __name__ == "__main__":
    main()
