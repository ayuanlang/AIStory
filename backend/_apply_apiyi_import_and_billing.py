import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

from sqlalchemy import func

from app.api.settings import import_system_settings_for_manage, _upsert_base_billing_rule
from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting
from app.schemas.settings import SystemAPISettingImportRequest
from app.services.system_api_runtime_cache import invalidate_system_api_cache


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMPORT_JSON = ROOT / "docs" / "apiyi_system_api_import_bundle.full_catalog.json"
DEFAULT_BILLING_JSON = ROOT / "docs" / "apiyi_system_api_billing_bundle.full_catalog.json"


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_row(db, provider: str, category: str, model: str):
    provider_norm = str(provider or "").strip().lower()
    category_norm = str(category or "").strip().lower()
    model_norm = str(model or "").strip().lower()
    return (
        db.query(SystemAPISetting)
        .filter(func.lower(func.trim(SystemAPISetting.provider)) == provider_norm)
        .filter(func.lower(func.trim(SystemAPISetting.category)) == category_norm)
        .filter(func.lower(func.trim(SystemAPISetting.model)) == model_norm)
        .order_by(SystemAPISetting.id.desc())
        .first()
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply APIYI staging import rows and base billing rules to the local DB")
    parser.add_argument("--import-json", default=str(DEFAULT_IMPORT_JSON), help="APIYI import bundle JSON")
    parser.add_argument("--billing-json", default=str(DEFAULT_BILLING_JSON), help="APIYI billing bundle JSON")
    args = parser.parse_args()

    import_path = Path(args.import_json)
    if not import_path.is_absolute():
        import_path = (ROOT / import_path).resolve()
    billing_path = Path(args.billing_json)
    if not billing_path.is_absolute():
        billing_path = (ROOT / billing_path).resolve()

    import_payload = SystemAPISettingImportRequest(**_read_json(import_path))
    billing_payload = _read_json(billing_path)
    billing_items = billing_payload.get("items") if isinstance(billing_payload.get("items"), list) else []
    admin_user = SimpleNamespace(is_superuser=True)

    with SessionLocal() as db:
        import_result = import_system_settings_for_manage(payload=import_payload, db=db, current_user=admin_user)

    applied_rules = 0
    missing_rows: List[Dict[str, Any]] = []
    with SessionLocal() as db:
        for item in billing_items:
            row = _find_row(db, str(item.get("provider") or "apiyi"), str(item.get("category") or "LLM"), str(item.get("model") or ""))
            if row is None:
                missing_rows.append({
                    "provider": item.get("provider"),
                    "category": item.get("category"),
                    "model": item.get("model"),
                })
                continue
            _upsert_base_billing_rule(
                db,
                int(row.id),
                str(row.category or "LLM"),
                {
                    "billing_unit_type": item.get("billing_unit_type"),
                    "billing_cost": item.get("billing_cost"),
                    "billing_cost_input": item.get("billing_cost_input"),
                    "billing_cost_output": item.get("billing_cost_output"),
                    "charge_multiplier": item.get("charge_multiplier") or 1.0,
                },
                activate=True,
            )
            applied_rules += 1
        db.commit()

    cache_rows = invalidate_system_api_cache(refresh=True)
    with SessionLocal() as db:
        provider_rows = db.query(SystemAPISetting).filter(SystemAPISetting.provider == "apiyi").all()
        active_count = sum(1 for row in provider_rows if bool(getattr(row, "is_active", False)))
        deprecated_count = sum(1 for row in provider_rows if bool(getattr(row, "deprecated", False)))

    print(json.dumps(
        {
            "import_result": import_result,
            "billing_rules_applied": applied_rules,
            "missing_rule_targets": len(missing_rows),
            "provider_rows": len(provider_rows),
            "deprecated_rows": deprecated_count,
            "active_rows": active_count,
            "cache_rows": cache_rows,
        },
        ensure_ascii=False,
    ))
    if missing_rows:
        print(json.dumps({"missing_rule_rows": missing_rows[:20]}, ensure_ascii=False))


if __name__ == "__main__":
    main()