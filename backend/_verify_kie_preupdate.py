from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting


def main() -> None:
    db = SessionLocal()
    try:
        rows = (
            db.query(SystemAPISetting)
            .filter(SystemAPISetting.provider == "kie")
            .filter(~SystemAPISetting.category.like("System_%"))
            .all()
        )
        has_meta = 0
        matched = 0
        unmatched = 0
        for r in rows:
            supplier_info = r.supplier_info if isinstance(r.supplier_info, dict) else {}
            pre = supplier_info.get("llms_txt_preupdate") if isinstance(supplier_info.get("llms_txt_preupdate"), dict) else None
            if pre is None:
                continue
            has_meta += 1
            if int(pre.get("match_count") or 0) > 0:
                matched += 1
            else:
                unmatched += 1

        print("=== VERIFY_KIE_PREUPDATE ===")
        print(f"total={len(rows)}")
        print(f"has_meta={has_meta}")
        print(f"matched={matched}")
        print(f"unmatched={unmatched}")

        print("sample:")
        shown = 0
        for r in rows:
            if shown >= 8:
                break
            supplier_info = r.supplier_info if isinstance(r.supplier_info, dict) else {}
            pre = supplier_info.get("llms_txt_preupdate") if isinstance(supplier_info.get("llms_txt_preupdate"), dict) else None
            if not pre:
                continue
            print(r.id, r.category, r.model, int(pre.get("match_count") or 0))
            shown += 1
    finally:
        db.close()


if __name__ == "__main__":
    main()
