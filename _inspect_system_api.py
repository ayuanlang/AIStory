import sqlite3

DB = r"c:/storyboard/AIStory/backend/aistory.db"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute(
    """
    SELECT id, category, provider, model, name,
           generation_modes, input_formats, output_format, has_audio, mode_values
    FROM system_api_settings
    WHERE is_active = 1
    ORDER BY id DESC
    LIMIT 120
    """
)
settings_rows = cur.fetchall()
print("active_settings", len(settings_rows))
for r in settings_rows[:50]:
    print(
        f"{r['id']}|{r['category']}|{r['provider']}|{r['model']}|{r['name']}"
        f"|gm={r['generation_modes']}|in={r['input_formats']}|out={r['output_format']}"
        f"|audio={r['has_audio']}|mode={r['mode_values']}"
    )

cur.execute("SELECT COUNT(1) FROM system_api_billing_rules WHERE is_active = 1")
print("active_rules", cur.fetchone()[0])

cur.execute(
    """
    SELECT id, system_api_id, name, generation_mode, input_format, output_format,
           has_audio, billing_unit_type, billing_cost, charge_multiplier
    FROM system_api_billing_rules
    WHERE is_active = 1
    ORDER BY id DESC
    LIMIT 120
    """
)
rule_rows = cur.fetchall()
print("rule_rows", len(rule_rows))
for r in rule_rows[:40]:
    print(
        f"{r['id']}|api={r['system_api_id']}|{r['name']}"
        f"|gm={r['generation_mode']}|in={r['input_format']}|out={r['output_format']}"
        f"|audio={r['has_audio']}|unit={r['billing_unit_type']}|cost={r['billing_cost']}|x={r['charge_multiplier']}"
    )

conn.close()
