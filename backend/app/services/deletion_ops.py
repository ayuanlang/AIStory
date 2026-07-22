# -*- coding: utf-8 -*-
"""Soft-delete / deletion-batch helpers for workspace resources."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.time_utils import now_bj_iso
from app.models.all_models import (
    Asset,
    DeletionBatch,
    DeletionBatchItem,
    Entity,
    Episode,
    Project,
    Scene,
    Shot,
    ScriptProgressPipelineNode,
    ScriptProgressSceneUnit,
    User,
)
from app.services.soft_delete import (
    _active_asset_clause,
    _active_entity_clause,
    _active_episode_clause,
    _active_project_clause,
    _active_scene_clause,
    _active_shot_clause,
)

logger = logging.getLogger("api_logger")

def _resolve_record_episode_id(record) -> Optional[int]:
    episode_id = getattr(record, "episode_id", None)
    if episode_id is not None:
        try:
            parsed = int(episode_id)
            if parsed > 0:
                return parsed
        except Exception:
            pass
    meta = getattr(record, "meta_info", None)
    if isinstance(meta, dict):
        try:
            meta_episode_id = meta.get("episode_id")
            if meta_episode_id is not None:
                parsed = int(meta_episode_id)
                if parsed > 0:
                    return parsed
        except Exception:
            pass
    return None


def _assert_episode_scoped_delete(record, *, label: str = "Record") -> int:
    episode_id = _resolve_record_episode_id(record)
    if episode_id is None:
        raise HTTPException(
            status_code=403,
            detail=f"{label} is project-scoped and can only be removed when deleting the entire project",
        )
    return episode_id


def _is_soft_deleted(record) -> bool:
    return bool(getattr(record, "is_deleted", False))


def _restore_soft_deleted_record(record) -> bool:
    if record is None or not _is_soft_deleted(record):
        return False
    record.is_deleted = False
    record.deleted_at = None
    return True


_DELETION_RESOURCE_MODELS: Dict[str, Any] = {
    "project": Project,
    "episode": Episode,
    "scene": Scene,
    "shot": Shot,
    "entity": Entity,
    "asset": Asset,
}

_DELETION_RESTORE_ORDER = ("project", "episode", "scene", "shot", "entity", "asset")


def _start_deletion_batch(
    db: Session,
    *,
    user_id: int,
    project_id: int,
    action_type: str,
    episode_id: Optional[int] = None,
    label: Optional[str] = None,
) -> str:
    if DeletionBatch is None or DeletionBatchItem is None:
        return ""
    batch_id = str(uuid.uuid4())
    db.add(
        DeletionBatch(
            id=batch_id,
            user_id=int(user_id),
            project_id=int(project_id),
            episode_id=int(episode_id) if episode_id is not None else None,
            action_type=str(action_type or "delete").strip() or "delete",
            label=str(label or "").strip() or None,
            item_count=0,
        )
    )
    db.flush()
    return batch_id


def _track_deletion_batch_items(
    db: Session,
    batch_id: Optional[str],
    resource_type: str,
    resource_ids: Iterable[Any],
) -> int:
    if not batch_id or DeletionBatchItem is None:
        return 0
    tracked = 0
    seen: Set[int] = set()
    for raw_id in resource_ids:
        try:
            resource_id = int(raw_id)
        except Exception:
            continue
        if resource_id <= 0 or resource_id in seen:
            continue
        seen.add(resource_id)
        db.add(
            DeletionBatchItem(
                batch_id=batch_id,
                resource_type=str(resource_type),
                resource_id=resource_id,
            )
        )
        tracked += 1
    return tracked


def _finalize_deletion_batch(db: Session, batch_id: Optional[str]) -> int:
    if not batch_id or DeletionBatch is None or DeletionBatchItem is None:
        return 0
    count = int(
        db.query(DeletionBatchItem)
        .filter(DeletionBatchItem.batch_id == batch_id)
        .count()
    )
    batch = db.query(DeletionBatch).filter(DeletionBatch.id == batch_id).first()
    if batch is not None:
        batch.item_count = count
    return count


def _require_project_owner_any_state(
    db: Session,
    project_id: int,
    current_user: User,
) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.owner_id != current_user.id:
        is_root_super_system_user = (
            bool(getattr(current_user, "is_superuser", False))
            and str(getattr(current_user, "username", "")).strip().lower() == "ylsystem"
        )
        if not is_root_super_system_user:
            raise HTTPException(status_code=403, detail="Not authorized")
    return project


def _serialize_deletion_batch(batch: DeletionBatch, db: Session) -> Dict[str, Any]:
    counts_by_type: Dict[str, int] = {}
    if DeletionBatchItem is not None:
        rows = (
            db.query(DeletionBatchItem.resource_type, func.count(DeletionBatchItem.id))
            .filter(DeletionBatchItem.batch_id == batch.id)
            .group_by(DeletionBatchItem.resource_type)
            .all()
        )
        counts_by_type = {str(rtype or "unknown"): int(count or 0) for rtype, count in rows}
    project_title = ""
    project_row = db.query(Project.id, Project.title).filter(Project.id == batch.project_id).first()
    if project_row:
        project_title = str(project_row[1] or "")
    episode_title = ""
    if batch.episode_id is not None:
        episode_row = db.query(Episode.id, Episode.title).filter(Episode.id == batch.episode_id).first()
        if episode_row:
            episode_title = str(episode_row[1] or "")
    return {
        "id": batch.id,
        "project_id": int(batch.project_id),
        "project_title": project_title,
        "episode_id": int(batch.episode_id) if batch.episode_id is not None else None,
        "episode_title": episode_title or None,
        "action_type": batch.action_type,
        "label": batch.label,
        "item_count": int(batch.item_count or 0),
        "created_at": batch.created_at,
        "restored_at": batch.restored_at,
        "counts_by_type": counts_by_type,
        "is_restored": bool(batch.restored_at),
    }


def _restore_deletion_batch(db: Session, batch_id: str, current_user: User) -> Dict[str, Any]:
    if DeletionBatch is None or DeletionBatchItem is None:
        raise HTTPException(status_code=503, detail="Deletion batch restore is unavailable")
    batch = db.query(DeletionBatch).filter(DeletionBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Deletion batch not found")
    if batch.restored_at:
        raise HTTPException(status_code=409, detail="Deletion batch already restored")
    _require_project_owner_any_state(db, int(batch.project_id), current_user)

    items = db.query(DeletionBatchItem).filter(DeletionBatchItem.batch_id == batch_id).all()
    ids_by_type: Dict[str, List[int]] = {}
    for item in items:
        ids_by_type.setdefault(str(item.resource_type), []).append(int(item.resource_id))

    restored_counts: Dict[str, int] = {}
    for resource_type in _DELETION_RESTORE_ORDER:
        model = _DELETION_RESOURCE_MODELS.get(resource_type)
        resource_ids = ids_by_type.get(resource_type) or []
        if not model or not resource_ids:
            continue
        updated = int(
            db.query(model)
            .filter(model.id.in_(resource_ids), model.is_deleted.is_(True))
            .update({model.is_deleted: False, model.deleted_at: None}, synchronize_session=False)
            or 0
        )
        if updated:
            restored_counts[resource_type] = updated

    batch.restored_at = now_bj_iso()
    return {
        "status": "restored",
        "batch_id": batch_id,
        "restored_counts": restored_counts,
        "restored_at": batch.restored_at,
    }


def _soft_delete_shots(
    db: Session,
    *,
    scene_id: Optional[int] = None,
    scene_ids: Optional[List[int]] = None,
    shot_id: Optional[int] = None,
    now: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> int:
    now = now or now_bj_iso()
    filters = [_active_shot_clause()]
    if scene_id is not None:
        filters.append(Shot.scene_id == scene_id)
    if scene_ids:
        filters.append(Shot.scene_id.in_(scene_ids))
    if shot_id is not None:
        filters.append(Shot.id == shot_id)
    shot_ids = [row[0] for row in db.query(Shot.id).filter(*filters).all()]
    if not shot_ids:
        return 0
    db.query(Shot).filter(Shot.id.in_(shot_ids)).update(
        {Shot.is_deleted: True, Shot.deleted_at: now},
        synchronize_session=False,
    )
    _track_deletion_batch_items(db, batch_id, "shot", shot_ids)
    return len(shot_ids)


def _hard_purge_episode_scenes(db: Session, episode_id: int) -> int:
    scene_ids = [
        int(row[0])
        for row in db.query(Scene.id).filter(Scene.episode_id == int(episode_id)).all()
        if row and row[0] is not None
    ]
    if not scene_ids:
        return 0
    db.query(Shot).filter(Shot.scene_id.in_(scene_ids)).delete(synchronize_session=False)
    deleted = db.query(Scene).filter(Scene.id.in_(scene_ids)).delete(synchronize_session=False)
    return int(deleted or 0)


def _purge_episode_scene_progress(db: Session, *, project_id: int, episode_id: int) -> int:
    removed = 0
    if ScriptProgressSceneUnit is not None:
        removed += int(
            db.query(ScriptProgressSceneUnit)
            .filter(
                ScriptProgressSceneUnit.project_id == int(project_id),
                ScriptProgressSceneUnit.episode_id == int(episode_id),
            )
            .delete(synchronize_session=False)
            or 0
        )
    if ScriptProgressPipelineNode is not None:
        db.query(ScriptProgressPipelineNode).filter(
            ScriptProgressPipelineNode.project_id == int(project_id),
            ScriptProgressPipelineNode.episode_id == int(episode_id),
            ScriptProgressPipelineNode.node_name.in_(["scene_markdown", "scene_planning", "scene_import"]),
        ).delete(synchronize_session=False)
    return removed


def _soft_delete_scenes(
    db: Session,
    *,
    episode_id: Optional[int] = None,
    scene_id: Optional[int] = None,
    now: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> int:
    now = now or now_bj_iso()
    scene_filters = [_active_scene_clause()]
    if episode_id is not None:
        scene_filters.append(Scene.episode_id == episode_id)
    if scene_id is not None:
        scene_filters.append(Scene.id == scene_id)

    scene_ids = [row[0] for row in db.query(Scene.id).filter(*scene_filters).all()]
    if scene_ids:
        _soft_delete_shots(db, scene_ids=scene_ids, now=now, batch_id=batch_id)

    if not scene_ids:
        return 0
    db.query(Scene).filter(Scene.id.in_(scene_ids)).update(
        {Scene.is_deleted: True, Scene.deleted_at: now},
        synchronize_session=False,
    )
    _track_deletion_batch_items(db, batch_id, "scene", scene_ids)
    return len(scene_ids)


def _soft_delete_assets(
    db: Session,
    *,
    asset_id: Optional[int] = None,
    asset_ids: Optional[List[int]] = None,
    project_id: Optional[int] = None,
    episode_id: Optional[int] = None,
    user_id: Optional[int] = None,
    now: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> int:
    now = now or now_bj_iso()
    filters = [_active_asset_clause()]
    if asset_id is not None:
        filters.append(Asset.id == asset_id)
    if asset_ids:
        filters.append(Asset.id.in_(asset_ids))
    if project_id is not None:
        filters.append(Asset.project_id == project_id)
    if episode_id is not None:
        filters.append(Asset.episode_id == episode_id)
    if user_id is not None:
        filters.append(Asset.user_id == user_id)
    matched_ids = [row[0] for row in db.query(Asset.id).filter(*filters).all()]
    if not matched_ids:
        return 0
    db.query(Asset).filter(Asset.id.in_(matched_ids)).update(
        {Asset.is_deleted: True, Asset.deleted_at: now},
        synchronize_session=False,
    )
    _track_deletion_batch_items(db, batch_id, "asset", matched_ids)
    return len(matched_ids)


def _soft_delete_entities(
    db: Session,
    *,
    entity_id: Optional[int] = None,
    entity_ids: Optional[List[int]] = None,
    project_id: Optional[int] = None,
    episode_id: Optional[int] = None,
    now: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> int:
    now = now or now_bj_iso()
    filters = [_active_entity_clause()]
    if entity_id is not None:
        filters.append(Entity.id == entity_id)
    if entity_ids:
        filters.append(Entity.id.in_(entity_ids))
    if project_id is not None:
        filters.append(Entity.project_id == project_id)
    if episode_id is not None:
        filters.append(Entity.episode_id == episode_id)
    matched_ids = [row[0] for row in db.query(Entity.id).filter(*filters).all()]
    if not matched_ids:
        return 0
    db.query(Entity).filter(Entity.id.in_(matched_ids)).update(
        {Entity.is_deleted: True, Entity.deleted_at: now},
        synchronize_session=False,
    )
    _track_deletion_batch_items(db, batch_id, "entity", matched_ids)
    return len(matched_ids)


def _soft_delete_episode_children(
    db: Session,
    episode_id: int,
    now: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> None:
    now = now or now_bj_iso()
    _soft_delete_scenes(db, episode_id=episode_id, now=now, batch_id=batch_id)
    _soft_delete_assets(db, episode_id=episode_id, now=now, batch_id=batch_id)
    _soft_delete_entities(db, episode_id=episode_id, now=now, batch_id=batch_id)


def _soft_delete_project_children(
    db: Session,
    project_id: int,
    now: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> None:
    now = now or now_bj_iso()
    episode_ids = [
        row[0]
        for row in db.query(Episode.id).filter(
            Episode.project_id == project_id,
            _active_episode_clause(),
        ).all()
    ]
    for ep_id in episode_ids:
        _soft_delete_scenes(db, episode_id=ep_id, now=now, batch_id=batch_id)
    _soft_delete_assets(db, project_id=project_id, now=now, batch_id=batch_id)
    _soft_delete_entities(db, project_id=project_id, now=now, batch_id=batch_id)

