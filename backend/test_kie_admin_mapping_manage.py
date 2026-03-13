from __future__ import annotations

import time
from types import SimpleNamespace

from fastapi import HTTPException

from app.api import settings as settings_api
from app.db.session import SessionLocal
from app.schemas.settings import KIEDataStandardMappingCreate, KIEDataStandardMappingUpdate


def _assert_forbidden_non_superuser(db):
    non_admin = SimpleNamespace(is_superuser=False)
    try:
        settings_api.list_kie_standard_values_manage(limit=1, db=db, current_user=non_admin)
    except HTTPException as exc:
        assert exc.status_code == 403, f"expected 403 for non-superuser, got {exc.status_code}"
        return
    raise AssertionError("non-superuser request should be rejected")


def main() -> int:
    db = SessionLocal()
    admin = SimpleNamespace(is_superuser=True)
    created_id = None
    marker = f"smoke_{int(time.time())}"

    try:
        _assert_forbidden_non_superuser(db)

        values = settings_api.list_kie_standard_values_manage(limit=5, db=db, current_user=admin)
        assert isinstance(values, list), "list_kie_standard_values_manage should return list"

        mappings = settings_api.list_kie_standard_mappings_manage(limit=5, db=db, current_user=admin)
        assert isinstance(mappings, list), "list_kie_standard_mappings_manage should return list"

        create_payload = KIEDataStandardMappingCreate(
            provider="kie",
            model_key_inferred="__smoke_test_model__",
            model_title="Smoke Test Model",
            model_url="https://example.com/smoke",
            source_field="paths.post.input.mode",
            source_enum_value=marker,
            standard_dimension="MODE",
            standard_value="STANDARD",
            confidence="LOW",
            note="smoke test row",
            is_active=True,
            is_billing_related=False,
        )
        created = settings_api.create_kie_standard_mapping_manage(create_payload, db=db, current_user=admin)
        created_id = int(created.id)

        assert created.source_enum_value == marker, "created row should preserve source_enum_value"
        assert created.is_billing_related is False, "created row billing flag should start false"

        update_payload = KIEDataStandardMappingUpdate(
            note="smoke test row updated",
            is_billing_related=True,
        )
        updated = settings_api.update_kie_standard_mapping_manage(
            created_id,
            update_payload,
            db=db,
            current_user=admin,
        )
        assert updated.note == "smoke test row updated", "update should persist note"
        assert updated.is_billing_related is True, "update should persist billing flag"

        inferred = settings_api.infer_kie_standard_mapping_billing_related_manage(
            provider="kie",
            db=db,
            current_user=admin,
        )
        assert isinstance(inferred.updated_count, int), "inference response must include updated_count"
        assert isinstance(inferred.matched_dimensions, list), "inference response must include matched_dimensions"

        deleted = settings_api.delete_kie_standard_mapping_manage(
            created_id,
            db=db,
            current_user=admin,
        )
        assert deleted.get("ok") is True, "delete should return ok=true"
        deleted_id = int(deleted.get("deleted_id", -1))
        created_id = None

        try:
            settings_api.update_kie_standard_mapping_manage(
                deleted_id,
                KIEDataStandardMappingUpdate(note=f"{marker}_after_delete"),
                db=db,
                current_user=admin,
            )
            raise AssertionError("updating a deleted row should fail")
        except HTTPException as exc:
            assert exc.status_code == 404, f"expected 404 after delete, got {exc.status_code}"

        print("PASS: KIE admin mapping manage smoke test")
        return 0
    finally:
        if created_id is not None:
            try:
                settings_api.delete_kie_standard_mapping_manage(created_id, db=db, current_user=admin)
            except Exception:
                pass
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
