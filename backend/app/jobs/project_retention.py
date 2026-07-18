"""Backup then hard-purge projects with no updates for PROJECT_RETENTION_DAYS."""

from __future__ import annotations

import gzip
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time_utils import BEIJING_TZ, now_bj
from app.db.session import SessionLocal
from app.models.all_models import (
    Asset,
    DeletionBatch,
    DeletionBatchItem,
    Entity,
    EntityHistory,
    Episode,
    MarketIntelReport,
    Project,
    ProjectAssetReviewMessage,
    ProjectAssetReviewRound,
    ProjectAssetReviewThread,
    ProjectGroupCreditAllocation,
    ProjectShare,
    Scene,
    ScriptProgressIssue,
    ScriptProgressPipelineNode,
    ScriptProgressSceneUnit,
    ScriptSegment,
    Shot,
    TransactionAction,
    TransactionHistory,
)
from app.services.media_cleanup import cleanup_media_files

logger = logging.getLogger(__name__)

_PROJECT_BACKUP_RE = re.compile(r"^project_(\d+)_(\d{8})(?:_\d{6})?\.json\.gz$")


def _ensure_project_backup_dir() -> Path:
    path = Path(settings.PROJECT_BACKUP_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _parse_iso(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=BEIJING_TZ)
    return dt.astimezone(BEIJING_TZ)


def _model_to_dict(obj: Any) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    table = getattr(obj, "__table__", None)
    if table is None:
        return data
    for column in table.columns:
        val = getattr(obj, column.name, None)
        if isinstance(val, datetime):
            data[column.name] = val.isoformat()
        else:
            try:
                json.dumps(val)
                data[column.name] = val
            except Exception:
                data[column.name] = str(val) if val is not None else None
    return data


def _collect_urls(*values: Any) -> List[str]:
    urls: List[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("http://") or text.startswith("https://") or "/uploads/" in text:
                urls.append(text)
            continue
        if isinstance(value, list):
            for item in value:
                urls.extend(_collect_urls(item))
            continue
        if isinstance(value, dict):
            for item in value.values():
                urls.extend(_collect_urls(item))
    return urls


def _extract_urls_from_jsonish(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, (dict, list)):
        return _collect_urls(raw)
    text = str(raw).strip()
    if not text:
        return []
    if text[0] in "{[":
        try:
            return _collect_urls(json.loads(text))
        except Exception:
            pass
    return _collect_urls(text)


def _project_activity_at(project: Project) -> Optional[datetime]:
    return _parse_iso(getattr(project, "updated_at", None)) or _parse_iso(
        getattr(project, "created_at", None)
    )


def find_stale_projects(
    db: Session,
    *,
    retention_days: int,
    require_soft_deleted: Optional[bool] = None,
) -> List[Project]:
    cutoff = now_bj() - timedelta(days=int(retention_days))
    require_deleted = (
        settings.PROJECT_RETENTION_REQUIRE_SOFT_DELETED
        if require_soft_deleted is None
        else bool(require_soft_deleted)
    )
    projects = db.query(Project).all()
    stale: List[Project] = []
    for project in projects:
        if require_deleted and not bool(getattr(project, "is_deleted", False)):
            continue
        # Prefer deleted_at for soft-deleted rows; otherwise fall back to updated/created.
        activity = _parse_iso(getattr(project, "deleted_at", None)) or _project_activity_at(project)
        if activity is None or activity <= cutoff:
            stale.append(project)
    return stale


def build_project_export(db: Session, project_id: int) -> Dict[str, Any]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ValueError(f"Project {project_id} not found")

    episodes = db.query(Episode).filter(Episode.project_id == project_id).all()
    episode_ids = [int(ep.id) for ep in episodes]
    scenes: List[Scene] = []
    if episode_ids:
        scenes = db.query(Scene).filter(Scene.episode_id.in_(episode_ids)).all()
    scene_ids = [int(sc.id) for sc in scenes]
    shots: List[Shot] = []
    if scene_ids:
        shots = db.query(Shot).filter(Shot.scene_id.in_(scene_ids)).all()
    # Also pick shots keyed by project_id (denormalized)
    shots_by_project = db.query(Shot).filter(Shot.project_id == project_id).all()
    shot_map = {int(s.id): s for s in shots}
    for shot in shots_by_project:
        shot_map[int(shot.id)] = shot
    shots = list(shot_map.values())

    segments: List[ScriptSegment] = []
    if episode_ids:
        segments = db.query(ScriptSegment).filter(ScriptSegment.episode_id.in_(episode_ids)).all()

    entities = db.query(Entity).filter(Entity.project_id == project_id).all()
    entity_ids = [int(e.id) for e in entities]
    entity_histories: List[EntityHistory] = []
    if entity_ids:
        entity_histories = (
            db.query(EntityHistory).filter(EntityHistory.entity_id.in_(entity_ids)).all()
        )

    assets = db.query(Asset).filter(Asset.project_id == project_id).all()
    shares = db.query(ProjectShare).filter(ProjectShare.project_id == project_id).all()
    allocations = (
        db.query(ProjectGroupCreditAllocation)
        .filter(ProjectGroupCreditAllocation.project_id == project_id)
        .all()
    )
    market = (
        db.query(MarketIntelReport).filter(MarketIntelReport.project_id == project_id).all()
    )
    progress_units = (
        db.query(ScriptProgressSceneUnit)
        .filter(ScriptProgressSceneUnit.project_id == project_id)
        .all()
    )
    progress_nodes = (
        db.query(ScriptProgressPipelineNode)
        .filter(ScriptProgressPipelineNode.project_id == project_id)
        .all()
    )
    progress_issues = (
        db.query(ScriptProgressIssue)
        .filter(ScriptProgressIssue.project_id == project_id)
        .all()
    )
    batches = db.query(DeletionBatch).filter(DeletionBatch.project_id == project_id).all()
    batch_ids = [str(b.id) for b in batches]
    batch_items: List[DeletionBatchItem] = []
    if batch_ids:
        batch_items = (
            db.query(DeletionBatchItem).filter(DeletionBatchItem.batch_id.in_(batch_ids)).all()
        )

    threads = (
        db.query(ProjectAssetReviewThread)
        .filter(ProjectAssetReviewThread.project_id == project_id)
        .all()
    )
    thread_ids = [int(t.id) for t in threads]
    rounds: List[ProjectAssetReviewRound] = []
    if thread_ids:
        rounds = (
            db.query(ProjectAssetReviewRound)
            .filter(ProjectAssetReviewRound.thread_id.in_(thread_ids))
            .all()
        )
    round_ids = [int(r.id) for r in rounds]
    messages: List[ProjectAssetReviewMessage] = []
    if round_ids:
        messages = (
            db.query(ProjectAssetReviewMessage)
            .filter(ProjectAssetReviewMessage.round_id.in_(round_ids))
            .all()
        )

    return {
        "type": "aistory_project_backup",
        "created_at": now_bj().isoformat(timespec="seconds"),
        "timezone": "Asia/Shanghai",
        "project_id": project_id,
        "project": _model_to_dict(project),
        "episodes": [_model_to_dict(x) for x in episodes],
        "scenes": [_model_to_dict(x) for x in scenes],
        "shots": [_model_to_dict(x) for x in shots],
        "script_segments": [_model_to_dict(x) for x in segments],
        "entities": [_model_to_dict(x) for x in entities],
        "entity_history": [_model_to_dict(x) for x in entity_histories],
        "assets": [_model_to_dict(x) for x in assets],
        "shares": [_model_to_dict(x) for x in shares],
        "group_credit_allocations": [_model_to_dict(x) for x in allocations],
        "market_intel_reports": [_model_to_dict(x) for x in market],
        "script_progress_scene_units": [_model_to_dict(x) for x in progress_units],
        "script_progress_pipeline_nodes": [_model_to_dict(x) for x in progress_nodes],
        "script_progress_issues": [_model_to_dict(x) for x in progress_issues],
        "deletion_batches": [_model_to_dict(x) for x in batches],
        "deletion_batch_items": [_model_to_dict(x) for x in batch_items],
        "asset_review_threads": [_model_to_dict(x) for x in threads],
        "asset_review_rounds": [_model_to_dict(x) for x in rounds],
        "asset_review_messages": [_model_to_dict(x) for x in messages],
    }


def _collect_project_media_urls(export_payload: Dict[str, Any]) -> List[str]:
    urls: List[str] = []
    for asset in export_payload.get("assets") or []:
        urls.extend(_collect_urls(asset.get("url")))
    for entity in export_payload.get("entities") or []:
        urls.extend(
            _collect_urls(
                entity.get("image_url"),
                entity.get("video_url"),
                entity.get("audio_url"),
            )
        )
    for shot in export_payload.get("shots") or []:
        urls.extend(
            _collect_urls(
                shot.get("image_url"),
                shot.get("video_url"),
            )
        )
        urls.extend(_extract_urls_from_jsonish(shot.get("keyframes")))
        urls.extend(_extract_urls_from_jsonish(shot.get("technical_notes")))
    # de-dupe preserve order
    seen: Set[str] = set()
    unique: List[str] = []
    for url in urls:
        if url and url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def write_project_backup(export_payload: Dict[str, Any]) -> Path:
    backup_dir = _ensure_project_backup_dir()
    project_id = int(export_payload["project_id"])
    stamp = now_bj().strftime("%Y%m%d")
    dest = backup_dir / f"project_{project_id}_{stamp}.json.gz"
    if dest.exists():
        dest = backup_dir / f"project_{project_id}_{now_bj().strftime('%Y%m%d_%H%M%S')}.json.gz"
    with gzip.open(dest, "wt", encoding="utf-8") as fh:
        json.dump(export_payload, fh, ensure_ascii=False, default=str)
    return dest


def hard_purge_project(db: Session, project_id: int) -> Dict[str, Any]:
    """Hard-delete a project and all related creative data. Keeps billing audit rows."""
    episodes = db.query(Episode).filter(Episode.project_id == project_id).all()
    episode_ids = [int(ep.id) for ep in episodes]
    scenes: List[Scene] = []
    if episode_ids:
        scenes = db.query(Scene).filter(Scene.episode_id.in_(episode_ids)).all()
    scene_ids = [int(sc.id) for sc in scenes]

    entities = db.query(Entity).filter(Entity.project_id == project_id).all()
    entity_ids = [int(e.id) for e in entities]

    threads = (
        db.query(ProjectAssetReviewThread)
        .filter(ProjectAssetReviewThread.project_id == project_id)
        .all()
    )
    thread_ids = [int(t.id) for t in threads]
    rounds: List[ProjectAssetReviewRound] = []
    if thread_ids:
        rounds = (
            db.query(ProjectAssetReviewRound)
            .filter(ProjectAssetReviewRound.thread_id.in_(thread_ids))
            .all()
        )
    round_ids = [int(r.id) for r in rounds]

    batches = db.query(DeletionBatch).filter(DeletionBatch.project_id == project_id).all()
    batch_ids = [str(b.id) for b in batches]

    counts: Dict[str, int] = {}

    def _delete_query(label: str, query) -> None:
        counts[label] = int(query.delete(synchronize_session=False) or 0)

    if batch_ids:
        _delete_query(
            "deletion_batch_items",
            db.query(DeletionBatchItem).filter(DeletionBatchItem.batch_id.in_(batch_ids)),
        )
    _delete_query(
        "deletion_batches",
        db.query(DeletionBatch).filter(DeletionBatch.project_id == project_id),
    )

    if round_ids:
        _delete_query(
            "asset_review_messages",
            db.query(ProjectAssetReviewMessage).filter(
                ProjectAssetReviewMessage.round_id.in_(round_ids)
            ),
        )
    if thread_ids:
        _delete_query(
            "asset_review_rounds",
            db.query(ProjectAssetReviewRound).filter(
                ProjectAssetReviewRound.thread_id.in_(thread_ids)
            ),
        )
    _delete_query(
        "asset_review_threads",
        db.query(ProjectAssetReviewThread).filter(
            ProjectAssetReviewThread.project_id == project_id
        ),
    )

    _delete_query(
        "script_progress_issues",
        db.query(ScriptProgressIssue).filter(ScriptProgressIssue.project_id == project_id),
    )
    _delete_query(
        "script_progress_pipeline_nodes",
        db.query(ScriptProgressPipelineNode).filter(
            ScriptProgressPipelineNode.project_id == project_id
        ),
    )
    _delete_query(
        "script_progress_scene_units",
        db.query(ScriptProgressSceneUnit).filter(
            ScriptProgressSceneUnit.project_id == project_id
        ),
    )
    _delete_query(
        "market_intel_reports",
        db.query(MarketIntelReport).filter(MarketIntelReport.project_id == project_id),
    )
    _delete_query(
        "group_credit_allocations",
        db.query(ProjectGroupCreditAllocation).filter(
            ProjectGroupCreditAllocation.project_id == project_id
        ),
    )
    _delete_query(
        "shares",
        db.query(ProjectShare).filter(ProjectShare.project_id == project_id),
    )

    if entity_ids:
        _delete_query(
            "entity_history",
            db.query(EntityHistory).filter(EntityHistory.entity_id.in_(entity_ids)),
        )

    if scene_ids:
        _delete_query("shots", db.query(Shot).filter(Shot.scene_id.in_(scene_ids)))
    # Denormalized project_id shots that may have missed scene cascade
    _delete_query("shots_by_project", db.query(Shot).filter(Shot.project_id == project_id))

    if episode_ids:
        _delete_query("scenes", db.query(Scene).filter(Scene.episode_id.in_(episode_ids)))
        _delete_query(
            "script_segments",
            db.query(ScriptSegment).filter(ScriptSegment.episode_id.in_(episode_ids)),
        )

    _delete_query("assets", db.query(Asset).filter(Asset.project_id == project_id))
    _delete_query("entities", db.query(Entity).filter(Entity.project_id == project_id))

    # Keep billing audit; detach from purged project/episodes.
    counts["transaction_action_detached"] = (
        db.query(TransactionAction)
        .filter(TransactionAction.project_id == project_id)
        .update(
            {TransactionAction.project_id: None, TransactionAction.episode_id: None},
            synchronize_session=False,
        )
        or 0
    )
    counts["transaction_history_detached"] = (
        db.query(TransactionHistory)
        .filter(TransactionHistory.project_id == project_id)
        .update(
            {TransactionHistory.project_id: None, TransactionHistory.episode_id: None},
            synchronize_session=False,
        )
        or 0
    )

    _delete_query("episodes", db.query(Episode).filter(Episode.project_id == project_id))
    _delete_query("projects", db.query(Project).filter(Project.id == project_id))

    db.commit()
    return counts


def prune_old_project_backups(*, keep_days: Optional[int] = None) -> List[str]:
    backup_dir = _ensure_project_backup_dir()
    days = int(keep_days if keep_days is not None else settings.PROJECT_BACKUP_KEEP_DAYS)
    cutoff = now_bj() - timedelta(days=days)
    removed: List[str] = []
    for item in backup_dir.iterdir():
        if not item.is_file():
            continue
        match = _PROJECT_BACKUP_RE.match(item.name)
        if not match:
            continue
        try:
            stamp = datetime.strptime(match.group(2), "%Y%m%d").replace(tzinfo=BEIJING_TZ)
        except Exception:
            stamp = datetime.fromtimestamp(item.stat().st_mtime, tz=BEIJING_TZ)
        if stamp <= cutoff:
            try:
                item.unlink(missing_ok=True)
                removed.append(item.name)
            except Exception as exc:
                logger.warning("Failed to prune project backup %s: %s", item, exc)
    return removed


def backup_and_purge_project(db: Session, project_id: int) -> Dict[str, Any]:
    export_payload = build_project_export(db, project_id)
    media_urls = _collect_project_media_urls(export_payload)
    archive_path = write_project_backup(export_payload)
    counts = hard_purge_project(db, project_id)
    media_result = cleanup_media_files(media_urls)
    return {
        "project_id": project_id,
        "archive": str(archive_path),
        "deleted_counts": counts,
        "media_cleanup": media_result,
    }


def run_stale_project_retention(
    *,
    retention_days: Optional[int] = None,
    keep_backup_days: Optional[int] = None,
    require_soft_deleted: Optional[bool] = None,
) -> Dict[str, Any]:
    days = int(retention_days if retention_days is not None else settings.PROJECT_RETENTION_DAYS)
    require_deleted = (
        settings.PROJECT_RETENTION_REQUIRE_SOFT_DELETED
        if require_soft_deleted is None
        else bool(require_soft_deleted)
    )
    purged: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    with SessionLocal() as db:
        stale = find_stale_projects(
            db,
            retention_days=days,
            require_soft_deleted=require_deleted,
        )
        stale_ids = [int(p.id) for p in stale]
        logger.info(
            "Project retention scan | retention_days=%s require_soft_deleted=%s stale_count=%s",
            days,
            require_deleted,
            len(stale_ids),
        )
        for project_id in stale_ids:
            try:
                # Fresh session per project so one failure does not poison the rest.
                with SessionLocal() as project_db:
                    result = backup_and_purge_project(project_db, project_id)
                purged.append(result)
                logger.info(
                    "Project retention purged | project_id=%s archive=%s",
                    project_id,
                    result.get("archive"),
                )
            except Exception as exc:
                logger.exception("Project retention failed for project_id=%s", project_id)
                errors.append({"project_id": project_id, "error": str(exc)})

    removed_archives = prune_old_project_backups(keep_days=keep_backup_days)
    summary = {
        "ok": len(errors) == 0,
        "retention_days": days,
        "require_soft_deleted": require_deleted,
        "stale_candidates": len(stale_ids) if "stale_ids" in locals() else 0,
        "purged_count": len(purged),
        "purged": purged,
        "errors": errors,
        "removed_archives": removed_archives,
        "created_at": now_bj().isoformat(timespec="seconds"),
    }
    logger.info(
        "Project retention complete | purged=%s errors=%s archives_removed=%s",
        len(purged),
        len(errors),
        len(removed_archives),
    )
    return summary

def summarize_project_candidate(db: Session, project: Project) -> Dict[str, Any]:
    """Build a lightweight admin preview row for a retention candidate."""
    project_id = int(project.id)
    episodes = db.query(Episode).filter(Episode.project_id == project_id).all()
    episode_ids = [int(ep.id) for ep in episodes]
    scene_count = 0
    shot_count = 0
    if episode_ids:
        scenes = db.query(Scene).filter(Scene.episode_id.in_(episode_ids)).all()
        scene_ids = [int(sc.id) for sc in scenes]
        scene_count = len(scene_ids)
        if scene_ids:
            shot_count = (
                db.query(Shot).filter(Shot.scene_id.in_(scene_ids)).count()
            )
    shot_by_project = db.query(Shot).filter(Shot.project_id == project_id).count()
    shot_count = max(int(shot_count), int(shot_by_project or 0))
    entity_count = db.query(Entity).filter(Entity.project_id == project_id).count()
    asset_count = db.query(Asset).filter(Asset.project_id == project_id).count()
    activity = _parse_iso(getattr(project, "deleted_at", None)) or _project_activity_at(project)
    owner = None
    owner_id = getattr(project, "owner_id", None)
    if owner_id is not None:
        from app.models.all_models import User

        owner = db.query(User).filter(User.id == int(owner_id)).first()
    idle_days = None
    if activity is not None:
        idle_days = max(0, int((now_bj() - activity).total_seconds() // 86400))
    return {
        "project_id": project_id,
        "title": str(project.title or f"Project {project_id}"),
        "owner_id": int(owner_id) if owner_id is not None else None,
        "owner_username": str(getattr(owner, "username", "") or "") or None,
        "owner_email": str(getattr(owner, "email", "") or "") or None,
        "is_deleted": bool(getattr(project, "is_deleted", False)),
        "created_at": getattr(project, "created_at", None),
        "updated_at": getattr(project, "updated_at", None),
        "deleted_at": getattr(project, "deleted_at", None),
        "last_activity_at": activity.isoformat(timespec="seconds") if activity else None,
        "idle_days": idle_days,
        "episode_count": len(episode_ids),
        "scene_count": int(scene_count),
        "shot_count": int(shot_count),
        "entity_count": int(entity_count or 0),
        "asset_count": int(asset_count or 0),
    }


def list_stale_project_candidates(
    *,
    retention_days: Optional[int] = None,
    require_soft_deleted: Optional[bool] = None,
) -> Dict[str, Any]:
    days = int(retention_days if retention_days is not None else settings.PROJECT_RETENTION_DAYS)
    require_deleted = (
        settings.PROJECT_RETENTION_REQUIRE_SOFT_DELETED
        if require_soft_deleted is None
        else bool(require_soft_deleted)
    )
    with SessionLocal() as db:
        stale = find_stale_projects(
            db,
            retention_days=days,
            require_soft_deleted=require_deleted,
        )
        projects = [summarize_project_candidate(db, project) for project in stale]
    projects.sort(key=lambda row: (row.get("idle_days") or 0, row.get("project_id") or 0), reverse=True)
    return {
        "ok": True,
        "retention_days": days,
        "require_soft_deleted": require_deleted,
        "cutoff_at": (now_bj() - timedelta(days=days)).isoformat(timespec="seconds"),
        "total_count": len(projects),
        "projects": projects,
        "project_backup_dir": str(Path(settings.PROJECT_BACKUP_DIR)),
    }


def purge_projects_by_ids(
    project_ids: List[int],
    *,
    retention_days: Optional[int] = None,
    require_soft_deleted: Optional[bool] = None,
    allow_non_stale: bool = False,
) -> Dict[str, Any]:
    """Backup then hard-purge selected project IDs (manual admin path)."""
    days = int(retention_days if retention_days is not None else settings.PROJECT_RETENTION_DAYS)
    require_deleted = (
        settings.PROJECT_RETENTION_REQUIRE_SOFT_DELETED
        if require_soft_deleted is None
        else bool(require_soft_deleted)
    )
    requested = []
    seen = set()
    for raw in project_ids or []:
        try:
            pid = int(raw)
        except Exception:
            continue
        if pid <= 0 or pid in seen:
            continue
        seen.add(pid)
        requested.append(pid)

    purged: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    with SessionLocal() as db:
        stale = find_stale_projects(
            db,
            retention_days=days,
            require_soft_deleted=require_deleted,
        )
        stale_ids = {int(p.id) for p in stale}

    for project_id in requested:
        if (not allow_non_stale) and project_id not in stale_ids:
            skipped.append(
                {
                    "project_id": project_id,
                    "reason": "not_in_candidate_list",
                }
            )
            continue
        try:
            with SessionLocal() as project_db:
                if project_db.query(Project).filter(Project.id == project_id).first() is None:
                    skipped.append({"project_id": project_id, "reason": "not_found"})
                    continue
                result = backup_and_purge_project(project_db, project_id)
            purged.append(result)
            logger.info(
                "Manual project retention purged | project_id=%s archive=%s",
                project_id,
                result.get("archive"),
            )
        except Exception as exc:
            logger.exception("Manual project retention failed for project_id=%s", project_id)
            errors.append({"project_id": project_id, "error": str(exc)})

    return {
        "ok": len(errors) == 0,
        "retention_days": days,
        "require_soft_deleted": require_deleted,
        "requested_count": len(requested),
        "purged_count": len(purged),
        "skipped_count": len(skipped),
        "purged": purged,
        "skipped": skipped,
        "errors": errors,
        "created_at": now_bj().isoformat(timespec="seconds"),
    }
