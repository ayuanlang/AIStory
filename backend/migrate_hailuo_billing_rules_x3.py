import json

from app.db.session import SessionLocal
from app.models.all_models import SystemAPIBillingRule, SystemAPISetting


MIGRATION_MARKER_KEY = "hailuo_price_x3_applied"
MIGRATION_MARKER_VERSION = "2026-03-14"


def _safe_json_dict(value):
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _is_hailuo_setting(setting: SystemAPISetting) -> bool:
    provider = str(getattr(setting, "provider", "") or "").strip().lower()
    model = str(getattr(setting, "model", "") or "").strip().lower()
    if provider != "kie":
        return False
    return "hailuo" in model


def run() -> None:
    touched = 0
    skipped_marked = 0

    with SessionLocal() as session:
        setting_rows = session.query(SystemAPISetting.id, SystemAPISetting.provider, SystemAPISetting.model).all()
        hailuo_setting_ids = {
            int(row.id)
            for row in setting_rows
            if _is_hailuo_setting(row)
        }

        if not hailuo_setting_ids:
            print("[migrate] no hailuo system_api_settings found, skip")
            return

        rules = (
            session.query(SystemAPIBillingRule)
            .filter(SystemAPIBillingRule.system_api_id.in_(hailuo_setting_ids))
            .all()
        )

        for rule in rules:
            extra = _safe_json_dict(getattr(rule, "extra_conditions", None))
            marker = str(extra.get(MIGRATION_MARKER_KEY) or "").strip().lower()
            if marker in {"1", "true", "yes", "applied"}:
                skipped_marked += 1
                continue

            changed = False
            for col in ("billing_cost", "billing_cost_input", "billing_cost_output"):
                raw = getattr(rule, col, 0)
                try:
                    value = int(raw or 0)
                except Exception:
                    value = 0
                if value > 0:
                    setattr(rule, col, int(value * 3))
                    changed = True

            if not changed:
                # Mark zero-price rows as processed to keep migration idempotent.
                extra[MIGRATION_MARKER_KEY] = "applied"
                extra["hailuo_price_x3_version"] = MIGRATION_MARKER_VERSION
                rule.extra_conditions = extra
                touched += 1
                continue

            extra[MIGRATION_MARKER_KEY] = "applied"
            extra["hailuo_price_x3_version"] = MIGRATION_MARKER_VERSION
            rule.extra_conditions = extra
            touched += 1

        session.commit()

    print(f"[migrate] hailuo billing rules x3 done | updated={touched} skipped_marked={skipped_marked}")


if __name__ == "__main__":
    run()
