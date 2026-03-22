import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

from sqlalchemy import func

from app.api.settings import import_system_settings_for_manage
from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting
from app.schemas.settings import SystemAPISettingImportRequest
from app.services.system_api_runtime_cache import invalidate_system_api_cache


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMPORT_JSON = ROOT / "docs" / "n1n_system_api_import_bundle.protocol_baseline.json"


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalized_triplet_counts(db, provider: str) -> List[Dict[str, Any]]:
    provider_norm = str(provider or "").strip().lower()
    rows = (
        db.query(
            func.lower(func.trim(func.coalesce(SystemAPISetting.provider, ""))).label("provider_norm"),
            func.lower(func.trim(func.coalesce(SystemAPISetting.category, ""))).label("category_norm"),
            func.lower(func.trim(func.coalesce(SystemAPISetting.model, ""))).label("model_norm"),
            func.count(SystemAPISetting.id).label("row_count"),
        )
        .filter(func.lower(func.trim(func.coalesce(SystemAPISetting.provider, ""))) == provider_norm)
        .group_by(
            func.lower(func.trim(func.coalesce(SystemAPISetting.provider, ""))),
            func.lower(func.trim(func.coalesce(SystemAPISetting.category, ""))),
            func.lower(func.trim(func.coalesce(SystemAPISetting.model, ""))),
        )
        .having(func.count(SystemAPISetting.id) > 1)
        .all()
    )
    return [
        {
            "provider": row.provider_norm,
            "category": row.category_norm,
            "model": row.model_norm,
            "row_count": int(row.row_count or 0),
        }
        for row in rows
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply n1n staging import rows to the local DB")
    parser.add_argument("--import-json", default=str(DEFAULT_IMPORT_JSON), help="n1n import bundle JSON")
    args = parser.parse_args()

    import_path = Path(args.import_json)
    if not import_path.is_absolute():
        import_path = (ROOT / import_path).resolve()

    payload = SystemAPISettingImportRequest(**_read_json(import_path))
    admin_user = SimpleNamespace(is_superuser=True)

    with SessionLocal() as db:
        import_result = import_system_settings_for_manage(payload=payload, db=db, current_user=admin_user)

    cache_rows = invalidate_system_api_cache(refresh=True)

    with SessionLocal() as db:
        provider_rows = db.query(SystemAPISetting).filter(SystemAPISetting.provider == "n1n").all()
        active_count = sum(1 for row in provider_rows if bool(getattr(row, "is_active", False)))
        deprecated_count = sum(1 for row in provider_rows if bool(getattr(row, "deprecated", False)))
        category_counts: Dict[str, int] = {}
        for row in provider_rows:
            category = str(getattr(row, "category", "") or "").strip() or "Unknown"
            category_counts[category] = category_counts.get(category, 0) + 1
        duplicate_triplets = _normalized_triplet_counts(db, "n1n")

    print(json.dumps(
        {
            "import_result": import_result,
            "provider_rows": len(provider_rows),
            "deprecated_rows": deprecated_count,
            "active_rows": active_count,
            "category_counts": category_counts,
            "duplicate_triplets": len(duplicate_triplets),
            "cache_rows": cache_rows,
        },
        ensure_ascii=False,
    ))
    if duplicate_triplets:
        print(json.dumps({"duplicate_triplet_rows": duplicate_triplets[:20]}, ensure_ascii=False))


if __name__ == "__main__":
    main()