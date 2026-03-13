import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "aistory.db"


MISSING_MODELS = [
    {
        "name": "Kie Seedream 3.0",
        "category": "Image",
        "provider": "kie",
        "model": "seedream/seedream",
    },
    {
        "name": "Kie Seedream 4.0 Edit",
        "category": "Image",
        "provider": "kie",
        "model": "seedream/seedream-v4-edit",
    },
    {
        "name": "Kie Seedream 4.0 Text to Image",
        "category": "Image",
        "provider": "kie",
        "model": "seedream/seedream-v4-text-to-image",
    },
    {
        "name": "Kie Bytedance Seedance 1.5 Pro",
        "category": "Video",
        "provider": "kie",
        "model": "bytedance/seedance-1-5-pro",
    },
    {
        "name": "Kie Kling AI Avatar Pro",
        "category": "Video",
        "provider": "kie",
        "model": "kling/ai-avatar-pro",
    },
    {
        "name": "Kie Kling AI Avatar Standard",
        "category": "Video",
        "provider": "kie",
        "model": "kling/ai-avatar-standard",
    },
]


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"DB not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.isolation_level = None
    try:
        conn.execute("BEGIN")

        inserted = 0
        existed = 0

        for item in MISSING_MODELS:
            found = conn.execute(
                "SELECT id FROM system_api_settings WHERE lower(provider)=lower(?) AND lower(model)=lower(?) LIMIT 1",
                (item["provider"], item["model"]),
            ).fetchone()
            if found:
                existed += 1
                continue

            conn.execute(
                """
                INSERT INTO system_api_settings
                (name, category, provider, model, is_active, deprecated)
                VALUES (?, ?, ?, ?, 1, 0)
                """,
                (item["name"], item["category"], item["provider"], item["model"]),
            )
            inserted += 1

        conn.execute("COMMIT")
        print(f"DB: {DB_PATH}")
        print(f"Inserted: {inserted}")
        print(f"Already existed: {existed}")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
