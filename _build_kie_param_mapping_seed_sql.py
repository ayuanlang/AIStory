import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROFILE_CSV = ROOT / "_kie_model_capability_profiles_template.csv"
RULES_CSV = ROOT / "_kie_param_auto_mapping_rules_template.csv"
OUT_SQL = ROOT / "_kie_param_mapping_seed.sql"


def q(val: str) -> str:
    if val is None:
        return "NULL"
    s = str(val)
    if s == "":
        return "NULL"
    return "'" + s.replace("'", "''") + "'"


def main() -> None:
    profile_rows = list(csv.DictReader(PROFILE_CSV.open("r", encoding="utf-8-sig", newline="")))
    rule_rows = list(csv.DictReader(RULES_CSV.open("r", encoding="utf-8-sig", newline="")))

    out = []
    out.append("-- Generated seed SQL for KIE param mapping tables")
    out.append("BEGIN TRANSACTION;")

    for r in profile_rows:
        out.append(
            "INSERT INTO kie_model_capability_profiles ("
            "profile_code, profile_name, supported_ratio_field, supported_quality_field, "
            "supported_secondary_field, requires_square_only, notes, is_active, updated_at"
            ") VALUES ("
            f"{q(r.get('profile_code'))}, {q(r.get('profile_name'))}, {q(r.get('supported_ratio_field'))}, "
            f"{q(r.get('supported_quality_field'))}, {q(r.get('supported_secondary_field'))}, "
            f"{q(r.get('requires_square_only') or '0')}, {q(r.get('notes'))}, {q(r.get('is_active') or '1')}, datetime('now')"
            ") "
            "ON CONFLICT(profile_code) DO UPDATE SET "
            "profile_name=excluded.profile_name, "
            "supported_ratio_field=excluded.supported_ratio_field, "
            "supported_quality_field=excluded.supported_quality_field, "
            "supported_secondary_field=excluded.supported_secondary_field, "
            "requires_square_only=excluded.requires_square_only, "
            "notes=excluded.notes, "
            "is_active=excluded.is_active, "
            "updated_at=datetime('now');"
        )

    for r in rule_rows:
        out.append(
            "INSERT INTO kie_param_auto_mapping_rules ("
            "rule_id, profile_code, source_ratio, source_quality, target_field, target_value, "
            "priority, fallback_action, description, is_active, updated_at"
            ") VALUES ("
            f"{q(r.get('rule_id'))}, {q(r.get('profile_code'))}, {q(r.get('source_ratio'))}, "
            f"{q(r.get('source_quality'))}, {q(r.get('target_field'))}, {q(r.get('target_value'))}, "
            f"{q(r.get('priority') or '100')}, {q(r.get('fallback_action') or 'use_model_default')}, "
            f"{q(r.get('description'))}, {q(r.get('is_active') or '1')}, datetime('now')"
            ") "
            "ON CONFLICT(rule_id) DO UPDATE SET "
            "profile_code=excluded.profile_code, "
            "source_ratio=excluded.source_ratio, "
            "source_quality=excluded.source_quality, "
            "target_field=excluded.target_field, "
            "target_value=excluded.target_value, "
            "priority=excluded.priority, "
            "fallback_action=excluded.fallback_action, "
            "description=excluded.description, "
            "is_active=excluded.is_active, "
            "updated_at=datetime('now');"
        )

    out.append("COMMIT;")

    OUT_SQL.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"WROTE {OUT_SQL}")
    print(f"PROFILES {len(profile_rows)}")
    print(f"RULES {len(rule_rows)}")


if __name__ == "__main__":
    main()
