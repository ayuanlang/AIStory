from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy.orm import Session, load_only

from app.models.all_models import SystemAPISetting, TaskDefaultSystemAPI
from app.core.time_utils import now_bj_iso


def normalize_task_category(value: Optional[str]) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"llm", "text", "chat"}:
        return "LLM"
    if raw in {"image", "img", "t2i", "i2i"}:
        return "IMAGE"
    if raw in {"video", "t2v", "i2v", "v2v"}:
        return "VIDEO"
    if raw in {"digital_human", "digital-human", "avatar", "s2v", "数字人"}:
        return "DIGITAL_HUMAN"
    if raw in {"voice", "audio", "speech", "tts", "asr"}:
        return "VOICE"
    if raw in {"music"}:
        return "MUSIC"
    if raw:
        return raw.upper()
    return "LLM"


def _candidate_system_categories(task_category: str) -> List[str]:
    normalized = normalize_task_category(task_category)
    if normalized == "LLM":
        return ["LLM"]
    if normalized == "IMAGE":
        return ["Image"]
    if normalized == "VIDEO":
        return ["Video"]
    if normalized == "DIGITAL_HUMAN":
        return ["DigitalHuman", "Avatar", "Video"]
    if normalized == "VOICE":
        return ["Voice"]
    if normalized == "MUSIC":
        return ["Music"]
    return [normalized.title()]


def upsert_task_default_system_setting(db: Session, task_category: str, system_api_id: int) -> None:
    normalized = normalize_task_category(task_category)
    record = db.query(TaskDefaultSystemAPI).filter(TaskDefaultSystemAPI.task_category == normalized).first()
    now = now_bj_iso()
    if record:
        record.system_api_id = int(system_api_id)
        record.updated_at = now
        return
    db.add(TaskDefaultSystemAPI(
        task_category=normalized,
        system_api_id=int(system_api_id),
        created_at=now,
        updated_at=now,
    ))


def clear_task_default_for_category(db: Session, task_category: str) -> None:
    normalized = normalize_task_category(task_category)
    db.query(TaskDefaultSystemAPI).filter(TaskDefaultSystemAPI.task_category == normalized).delete(synchronize_session=False)


def clear_task_defaults_for_system_api_ids(db: Session, system_api_ids: List[int]) -> None:
    ids = [int(x) for x in (system_api_ids or []) if x is not None]
    if not ids:
        return
    db.query(TaskDefaultSystemAPI).filter(TaskDefaultSystemAPI.system_api_id.in_(ids)).delete(synchronize_session=False)


def list_task_default_system_setting_ids(db: Session) -> Dict[str, int]:
    rows = db.query(TaskDefaultSystemAPI).all()
    out: Dict[str, int] = {}
    for row in rows:
        key = normalize_task_category(getattr(row, "task_category", None))
        sid = int(getattr(row, "system_api_id", 0) or 0)
        if sid > 0:
            out[key] = sid
    return out


def _system_setting_query(db: Session):
    return db.query(SystemAPISetting).options(
        load_only(
            SystemAPISetting.id,
            SystemAPISetting.name,
            SystemAPISetting.category,
            SystemAPISetting.provider,
            SystemAPISetting.api_key,
            SystemAPISetting.base_url,
            SystemAPISetting.model,
            SystemAPISetting.base_model,
            SystemAPISetting.modality,
            SystemAPISetting.tags,
            SystemAPISetting.supplier_info,
            SystemAPISetting.deprecated,
            SystemAPISetting.config,
            SystemAPISetting.is_active,
        )
    )


def is_task_default_system_setting(db: Session, system_api_id: int, category: Optional[str] = None) -> bool:
    sid = int(system_api_id or 0)
    if sid <= 0:
        return False
    if category:
        record = db.query(TaskDefaultSystemAPI).filter(
            TaskDefaultSystemAPI.task_category == normalize_task_category(category),
        ).first()
        if record and int(getattr(record, "system_api_id", 0) or 0) == sid:
            return True
    else:
        record = db.query(TaskDefaultSystemAPI).filter(TaskDefaultSystemAPI.system_api_id == sid).first()
        if record:
            return True
    return False


def get_task_default_system_setting(db: Session, task_category: str) -> Optional[SystemAPISetting]:
    normalized = normalize_task_category(task_category)
    record = db.query(TaskDefaultSystemAPI).filter(TaskDefaultSystemAPI.task_category == normalized).first()
    if record:
        row = _system_setting_query(db).filter(SystemAPISetting.id == int(record.system_api_id)).first()
        if row:
            return row
    return None


def list_task_default_system_settings(db: Session) -> Dict[str, SystemAPISetting]:
    out: Dict[str, SystemAPISetting] = {}
    id_map = list_task_default_system_setting_ids(db)
    if id_map:
        rows = _system_setting_query(db).filter(SystemAPISetting.id.in_(list(id_map.values()))).all()
        by_id = {int(r.id): r for r in rows}
        for category, sid in id_map.items():
            row = by_id.get(int(sid))
            if row:
                out[category] = row
    return out

