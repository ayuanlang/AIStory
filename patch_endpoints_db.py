import os
import re

endpoints_path = r"c:\AS\AIStory\backend\app\api\endpoints.py"

with open(endpoints_path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix 1: db.commit() in _find_existing_asset_for_registration
target_str = """def _find_existing_asset_for_registration(
    db: Session,
    user_id: int,
    *,
    url: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    meta_info: Optional[Dict[str, Any]] = None,
) -> Optional[Asset]:
    normalized_key = _normalize_asset_idempotency_key(idempotency_key)"""

replacement_str = """def _find_existing_asset_for_registration(
    db: Session,
    user_id: int,
    *,
    url: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    meta_info: Optional[Dict[str, Any]] = None,
) -> Optional[Asset]:
    # Flush session to see commits from other background threads/callbacks
    try:
        db.commit()
    except Exception:
        db.rollback()
        
    normalized_key = _normalize_asset_idempotency_key(idempotency_key)"""

content = content.replace(target_str, replacement_str)

with open(endpoints_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Endpoints patched!")
