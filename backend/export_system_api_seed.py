"""Export local system_api_settings to the seed JSON file.

Run from backend/:
    python export_system_api_seed.py

The exported file (app/data/system_api_seed.json) should be committed to git.
On Render deploy, init_db will auto-import it to sync settings.
"""
import sys, os, json
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting

SEED_PATH = os.path.join(os.path.dirname(__file__), "app", "data", "system_api_seed.json")


def main():
    db = SessionLocal()
    try:
        rows = (
            db.query(SystemAPISetting)
            .filter(SystemAPISetting.category != "System_Payment")
            .order_by(
                SystemAPISetting.category.asc(),
                SystemAPISetting.provider.asc(),
                SystemAPISetting.model.asc(),
                SystemAPISetting.id.asc(),
            )
            .all()
        )

        items = []
        for row in rows:
            config = dict(row.config or {})
            items.append({
                "name": row.name,
                "category": row.category,
                "provider": row.provider,
                "base_url": row.base_url,
                "model": row.model,
                "modality": row.modality,
                "config": config,
                "deprecated": bool(row.deprecated),
                "is_active": bool(row.is_active),
            })

        payload = {
            "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "count": len(items),
            "items": items,
        }

        os.makedirs(os.path.dirname(SEED_PATH), exist_ok=True)
        with open(SEED_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        print(f"Exported {len(items)} system API settings to {SEED_PATH}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
