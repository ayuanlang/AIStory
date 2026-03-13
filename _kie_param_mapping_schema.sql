-- KIE parameter mapping rule engine schema (SQLite)
-- Goal: user picks ratio + quality, system resolves API payload fields by model profile.

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS kie_model_capability_profiles (
    profile_code TEXT PRIMARY KEY,
    profile_name TEXT NOT NULL,
    supported_ratio_field TEXT,
    supported_quality_field TEXT,
    supported_secondary_field TEXT,
    requires_square_only INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS kie_model_profile_bindings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL DEFAULT 'kie',
    model_key TEXT NOT NULL,
    profile_code TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (profile_code) REFERENCES kie_model_capability_profiles(profile_code)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_kie_model_profile_bindings_model
ON kie_model_profile_bindings(provider, model_key);

CREATE INDEX IF NOT EXISTS ix_kie_model_profile_bindings_profile
ON kie_model_profile_bindings(profile_code, is_active);

CREATE TABLE IF NOT EXISTS kie_param_auto_mapping_rules (
    rule_id TEXT PRIMARY KEY,
    profile_code TEXT NOT NULL,
    source_ratio TEXT,
    source_quality TEXT,
    target_field TEXT NOT NULL,
    target_value TEXT,
    priority INTEGER NOT NULL DEFAULT 100,
    fallback_action TEXT NOT NULL DEFAULT 'use_model_default',
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (profile_code) REFERENCES kie_model_capability_profiles(profile_code)
);

CREATE INDEX IF NOT EXISTS ix_kie_param_auto_mapping_rules_lookup
ON kie_param_auto_mapping_rules(profile_code, source_ratio, source_quality, is_active, priority);

CREATE TABLE IF NOT EXISTS kie_param_resolution_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL DEFAULT 'kie',
    model_key TEXT NOT NULL,
    profile_code TEXT,
    source_ratio TEXT,
    source_quality TEXT,
    resolved_payload_json TEXT NOT NULL,
    fallback_events_json TEXT,
    status TEXT NOT NULL, -- resolved | degraded | conflict | failed
    message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

COMMIT;

-- =============================
-- Query 1: resolve active profile
-- =============================
-- SELECT profile_code
-- FROM kie_model_profile_bindings
-- WHERE provider = 'kie' AND model_key = :model_key AND is_active = 1
-- LIMIT 1;

-- ===========================================
-- Query 2: resolve rules for ratio + quality
-- ===========================================
-- SELECT rule_id, target_field, target_value, fallback_action, priority
-- FROM kie_param_auto_mapping_rules
-- WHERE profile_code = :profile_code
--   AND is_active = 1
--   AND (source_ratio = :source_ratio OR source_ratio IS NULL OR source_ratio = '')
--   AND (source_quality = :source_quality OR source_quality IS NULL OR source_quality = '')
-- ORDER BY priority ASC, rule_id ASC;

-- ==========================================================
-- Query 3: inspect current effective payload per model choice
-- ==========================================================
-- WITH p AS (
--   SELECT profile_code
--   FROM kie_model_profile_bindings
--   WHERE provider='kie' AND model_key=:model_key AND is_active=1
--   LIMIT 1
-- )
-- SELECT r.target_field, r.target_value, r.fallback_action, r.priority
-- FROM kie_param_auto_mapping_rules r
-- JOIN p ON p.profile_code = r.profile_code
-- WHERE r.is_active = 1
--   AND (r.source_ratio = :source_ratio OR r.source_ratio IS NULL OR r.source_ratio = '')
--   AND (r.source_quality = :source_quality OR r.source_quality IS NULL OR r.source_quality = '')
-- ORDER BY r.priority ASC, r.rule_id ASC;
