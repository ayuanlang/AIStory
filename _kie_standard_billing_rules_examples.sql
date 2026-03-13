-- KIE standard-dimension billing rules examples (idempotent)
--
-- Goal:
-- 1) Demonstrate base pricing rule pattern.
-- 2) Demonstrate fine-grained pricing by extra_conditions.standard_values.
--
-- Usage:
--   Apply this SQL to backend/aistory.db.
--   Existing rules with the same names are deleted first to keep reruns idempotent.

BEGIN TRANSACTION;

DELETE FROM system_api_billing_rules
WHERE name IN (
    'KIE Example Base Pricing',
    'KIE Kling3 Pro P1080',
    'KIE Kling3 Std P720',
    'KIE Sora2 Pro Landscape',
    'KIE Wan Flash ImageToVideo P1080'
);

-- 1) Base pricing rule (fallback)
INSERT INTO system_api_billing_rules (
    system_api_id,
    name,
    description,
    is_active,
    priority,
    applies_to_text,
    applies_to_image,
    applies_to_video,
    billing_unit_type,
    billing_cost,
    billing_cost_input,
    billing_cost_output,
    charge_multiplier,
    extra_conditions,
    created_at,
    updated_at
)
SELECT
    s.id,
    'KIE Example Base Pricing',
    'Base pricing fallback for KIE model when no specific standard_values rule matches',
    1,
    -100000,
    0,
    0,
    1,
    'per_second',
    30,
    0,
    0,
    2.0,
    '{"rule_kind":"base_pricing"}',
    datetime('now'),
    datetime('now')
FROM system_api_settings s
WHERE lower(coalesce(s.provider, '')) = 'kie'
  AND lower(coalesce(s.model, '')) = 'kling-3.0/video';

-- 2) Kling 3.0 pro + 1080p rule via standard dimensions
INSERT INTO system_api_billing_rules (
    system_api_id,
    name,
    description,
    is_active,
    priority,
    applies_to_text,
    applies_to_image,
    applies_to_video,
    billing_unit_type,
    billing_cost,
    billing_cost_input,
    billing_cost_output,
    charge_multiplier,
    extra_conditions,
    created_at,
    updated_at
)
SELECT
    s.id,
    'KIE Kling3 Pro P1080',
    'Higher price when MODE=PRO and RESOLUTION_TIER=P1080',
    1,
    120,
    0,
    0,
    1,
    'per_second',
    55,
    0,
    0,
    2.0,
    '{"standard_values":{"MODE":"PRO","RESOLUTION_TIER":"P1080"}}',
    datetime('now'),
    datetime('now')
FROM system_api_settings s
WHERE lower(coalesce(s.provider, '')) = 'kie'
  AND lower(coalesce(s.model, '')) = 'kling-3.0/video';

-- 3) Kling 3.0 std + 720p rule via standard dimensions
INSERT INTO system_api_billing_rules (
    system_api_id,
    name,
    description,
    is_active,
    priority,
    applies_to_text,
    applies_to_image,
    applies_to_video,
    billing_unit_type,
    billing_cost,
    billing_cost_input,
    billing_cost_output,
    charge_multiplier,
    extra_conditions,
    created_at,
    updated_at
)
SELECT
    s.id,
    'KIE Kling3 Std P720',
    'Lower price when MODE=STANDARD and RESOLUTION_TIER=P720',
    1,
    110,
    0,
    0,
    1,
    'per_second',
    35,
    0,
    0,
    2.0,
    '{"standard_values":{"MODE":"STANDARD","RESOLUTION_TIER":"P720"}}',
    datetime('now'),
    datetime('now')
FROM system_api_settings s
WHERE lower(coalesce(s.provider, '')) = 'kie'
  AND lower(coalesce(s.model, '')) = 'kling-3.0/video';

-- 4) Sora2 Pro Text-to-Video landscape rule
INSERT INTO system_api_billing_rules (
    system_api_id,
    name,
    description,
    is_active,
    priority,
    applies_to_text,
    applies_to_image,
    applies_to_video,
    billing_unit_type,
    billing_cost,
    billing_cost_input,
    billing_cost_output,
    charge_multiplier,
    extra_conditions,
    created_at,
    updated_at
)
SELECT
    s.id,
    'KIE Sora2 Pro Landscape',
    'Sora2 pro text-to-video with landscape aspect ratio (16:9)',
    1,
    100,
    0,
    0,
    1,
    'per_second',
    48,
    0,
    0,
    2.0,
    '{"standard_values":{"ASPECT_RATIO":"16:9"}}',
    datetime('now'),
    datetime('now')
FROM system_api_settings s
WHERE lower(coalesce(s.provider, '')) = 'kie'
  AND lower(coalesce(s.model, '')) = 'sora-2-pro-text-to-video';

-- 5) Wan flash image-to-video 1080p rule
INSERT INTO system_api_billing_rules (
    system_api_id,
    name,
    description,
    is_active,
    priority,
    applies_to_text,
    applies_to_image,
    applies_to_video,
    billing_unit_type,
    billing_cost,
    billing_cost_input,
    billing_cost_output,
    charge_multiplier,
    extra_conditions,
    created_at,
    updated_at
)
SELECT
    s.id,
    'KIE Wan Flash ImageToVideo P1080',
    'Wan 2.6 flash i2v with 1080p tier',
    1,
    95,
    0,
    0,
    1,
    'per_second',
    40,
    0,
    0,
    2.0,
    '{"standard_values":{"RESOLUTION_TIER":"P1080"}}',
    datetime('now'),
    datetime('now')
FROM system_api_settings s
WHERE lower(coalesce(s.provider, '')) = 'kie'
  AND lower(coalesce(s.model, '')) = 'wan/2-6-flash-image-to-video';

COMMIT;
