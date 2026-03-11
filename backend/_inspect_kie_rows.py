from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting


def main() -> None:
    db = SessionLocal()
    try:
        rows = db.query(SystemAPISetting).filter(SystemAPISetting.provider == "kie").all()
        print("count", len(rows))
        for r in rows[:20]:
            print(r.id, r.category, r.model, isinstance(r.modality, dict), isinstance(r.supplier_info, dict))
    finally:
        db.close()


if __name__ == "__main__":
    main()
