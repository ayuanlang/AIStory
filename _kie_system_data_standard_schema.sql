-- KIE system data standard schema (SQLite)
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

CREATE TABLE IF NOT EXISTS kie_system_data_standard_mapping_rules (
    rule_code TEXT PRIMARY KEY,
    rule_name TEXT,
    rule_description TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS ix_kie_std_values_dim
ON kie_system_data_standard_values(standard_dimension, is_active);

CREATE INDEX IF NOT EXISTS ix_kie_std_mappings_lookup
ON kie_system_data_standard_mappings(provider, model_key_inferred, standard_dimension, source_field, is_active);

COMMIT;
