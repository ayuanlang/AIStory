# -*- coding: utf-8 -*-
"""Project share, asset-review access, and project authorization helpers."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.time_utils import now_bj_iso
from app.models import all_models as models
from app.models.all_models import (
    Entity,
    Episode,
    Project,
    ProjectShare,
    Scene,
    Shot,
    User,
)
from app.schemas.asset_review import (
    ProjectAssetReviewMessageOut,
    ProjectAssetReviewRoundOut,
    ProjectAssetReviewThreadOut,
)
from app.schemas.project import ProjectShareOut
from app.services.endpoint_misc import _require_review_models, _run_with_schema_self_heal
from app.services.soft_delete import _active_project_clause


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    """Lightweight ISO parse for review unread checks (avoid job_store import cycle)."""
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        return datetime.fromisoformat(normalized)
    except Exception:
        return None

ProjectAssetReviewThread = getattr(models, "ProjectAssetReviewThread", None)
ProjectAssetReviewRound = getattr(models, "ProjectAssetReviewRound", None)
ProjectAssetReviewMessage = getattr(models, "ProjectAssetReviewMessage", None)
ProjectAssetReviewThreadModel = ProjectAssetReviewThread
ProjectAssetReviewRoundModel = ProjectAssetReviewRound
ProjectAssetReviewMessageModel = ProjectAssetReviewMessage

_PROJECT_SHARE_ROLES = {"editor", "reviewer", "viewer"}
_PROJECT_SHARE_PERMISSION_KEYS = {
    "can_review_assets",
    "can_reply_review",
    "can_edit_entities",
    "can_edit_shots",
}
_ASSET_REVIEW_THREAD_STATUSES = {"open", "closed", "archived"}
_ASSET_REVIEW_SCOPE_TYPES = {"all_current", "selected_only"}
_ASSET_REVIEW_DECISIONS = {"pending", "approved", "rejected", "conditional"}
_ASSET_REVIEW_ROUND_STATUSES = {"pending_reviewer", "replied", "in_discussion", "closed", "cancelled"}
_ASSET_REVIEW_MESSAGE_TYPES = {"request", "reply", "followup", "message", "status_change"}

def _is_project_shared_with_user(db: Session, project_id: int, user_id: int) -> bool:
    share = _run_with_schema_self_heal(
        db,
        lambda: db.query(ProjectShare).filter(
            ProjectShare.project_id == project_id,
            ProjectShare.user_id == user_id,
        ).first(),
        context="project_share.lookup_shared",
    )
    return share is not None


def _get_project_share_record(db: Session, project_id: int, user_id: int) -> Optional[ProjectShare]:
    return _run_with_schema_self_heal(
        db,
        lambda: db.query(ProjectShare).filter(
            ProjectShare.project_id == project_id,
            ProjectShare.user_id == user_id,
        ).first(),
        context="project_share.lookup_record",
    )


def _normalize_project_share_role(value: Any, *, strict: bool = False) -> str:
    raw = str(value or "").strip().lower()
    if raw in _PROJECT_SHARE_ROLES:
        return raw
    if strict and raw:
        raise HTTPException(status_code=400, detail=f"Invalid project share role: {raw}")
    return "editor"


def _normalize_project_share_permissions(value: Any) -> Dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    normalized: Dict[str, Any] = {}
    for key in _PROJECT_SHARE_PERMISSION_KEYS:
        if key in payload:
            normalized[key] = bool(payload.get(key))
    return normalized


def _project_share_supports_mapped_field(field_name: str) -> bool:
    mapper = getattr(ProjectShare, "__mapper__", None)
    attrs = getattr(mapper, "attrs", None)
    if attrs is None:
        return False
    try:
        return field_name in attrs.keys()
    except Exception:
        return False


def _apply_project_share_access_fields(share: ProjectShare, role: Any, permissions: Any) -> ProjectShare:
    normalized_role = _normalize_project_share_role(role)
    normalized_permissions = _normalize_project_share_permissions(permissions)

    if _project_share_supports_mapped_field("role") or not hasattr(share, "role"):
        share.role = normalized_role
    if _project_share_supports_mapped_field("permissions") or not hasattr(share, "permissions"):
        share.permissions = normalized_permissions
    return share


def _build_project_share(project_id: int, user_id: int, role: Any, permissions: Any) -> ProjectShare:
    share = ProjectShare(project_id=project_id, user_id=user_id)
    return _apply_project_share_access_fields(share, role, permissions)


def _project_share_has_permission(share: Optional[ProjectShare], permission_key: str) -> bool:
    if not share:
        return False
    permissions = _normalize_project_share_permissions(getattr(share, "permissions", None))
    return bool(permissions.get(permission_key))


def _project_share_can_review_assets(share: Optional[ProjectShare]) -> bool:
    if not share:
        return False
    role = _normalize_project_share_role(getattr(share, "role", None))
    if role in {"editor", "reviewer"}:
        return True
    return _project_share_has_permission(share, "can_review_assets")


def _normalize_asset_review_scope_type(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return raw if raw in _ASSET_REVIEW_SCOPE_TYPES else "all_current"


def _normalize_asset_review_decision(value: Any, *, allow_empty: bool = True) -> Optional[str]:
    raw = str(value or "").strip().lower()
    if not raw:
        return None if allow_empty else "pending"
    if raw not in _ASSET_REVIEW_DECISIONS:
        raise HTTPException(status_code=400, detail=f"Invalid review decision: {raw}")
    return raw


def _normalize_asset_review_message_type(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return raw if raw in _ASSET_REVIEW_MESSAGE_TYPES else "message"


def _normalize_int_list(values: Any) -> List[int]:
    if not isinstance(values, list):
        return []
    normalized: List[int] = []
    seen = set()
    for item in values:
        try:
            parsed = int(item)
        except Exception:
            continue
        if parsed <= 0 or parsed in seen:
            continue
        seen.add(parsed)
        normalized.append(parsed)
    return normalized


_PROJECT_GLOBAL_INFO_SHARE_USERS_KEY = "project_share_users"
_PROJECT_GLOBAL_INFO_REVIEWER_USERS_KEY = "project_reviewer_users"


def _normalize_user_identifier_list(values: Any) -> List[str]:
    if values is None:
        return []
    raw_items = values if isinstance(values, list) else re.split(r"[,;\n\r]+", str(values or ""))
    normalized: List[str] = []
    seen = set()
    for item in raw_items:
        value = str(item or "").strip()
        if not value:
            continue
        dedupe_key = value.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized.append(value)
    return normalized


def _resolve_project_share_users(
    db: Session,
    identifiers: Any,
    *,
    field_name: str,
    allow_missing: bool = False,
) -> Tuple[List[User], List[str]]:
    normalized = _normalize_user_identifier_list(identifiers)
    resolved_users: List[User] = []
    canonical_usernames: List[str] = []
    seen_user_ids = set()
    missing: List[str] = []

    for identifier in normalized:
        user = db.query(User).filter(or_(User.username == identifier, User.email == identifier)).first()
        if not user:
            missing.append(identifier)
            continue
        if int(user.id or 0) in seen_user_ids:
            continue
        seen_user_ids.add(int(user.id or 0))
        resolved_users.append(user)
        canonical_usernames.append(str(user.username or identifier).strip())

    if missing and not allow_missing:
        joined = "、".join([str(item).strip() for item in missing if str(item).strip()])
        if field_name == "share_users":
            message = f"以下分享人不存在: {joined}"
        elif field_name == "reviewer_users":
            message = f"以下审核人不存在: {joined}"
        else:
            message = f"以下用户不存在: {joined}"
        raise HTTPException(status_code=404, detail=message)

    return resolved_users, canonical_usernames


def _sync_project_managed_shares(
    db: Session,
    project: Project,
    current_user: User,
    *,
    share_users: Optional[Any] = None,
    reviewer_users: Optional[Any] = None,
) -> None:
    if share_users is None and reviewer_users is None:
        return

    if int(project.owner_id or 0) != int(current_user.id or 0):
        raise HTTPException(status_code=403, detail="Only project owner can manage share users or reviewer users")

    current_info = dict(project.global_info) if isinstance(project.global_info, dict) else {}
    existing_share_identifiers = current_info.get(_PROJECT_GLOBAL_INFO_SHARE_USERS_KEY, [])
    existing_reviewer_identifiers = current_info.get(_PROJECT_GLOBAL_INFO_REVIEWER_USERS_KEY, [])

    effective_share_identifiers = existing_share_identifiers if share_users is None else share_users
    effective_reviewer_identifiers = existing_reviewer_identifiers if reviewer_users is None else reviewer_users

    share_members, share_canonical_usernames = _resolve_project_share_users(
        db,
        effective_share_identifiers,
        field_name="share_users",
    )
    reviewer_members, reviewer_canonical_usernames = _resolve_project_share_users(
        db,
        effective_reviewer_identifiers,
        field_name="reviewer_users",
    )

    desired_by_user_id: Dict[int, Dict[str, Any]] = {}
    for user in reviewer_members:
        if int(project.owner_id or 0) == int(user.id or 0):
            continue
        desired_by_user_id[int(user.id)] = {
            "role": "reviewer",
            "can_review_assets": True,
        }
    for user in share_members:
        if int(project.owner_id or 0) == int(user.id or 0):
            continue
        existing = desired_by_user_id.get(int(user.id), {})
        desired_by_user_id[int(user.id)] = {
            "role": "editor",
            "can_review_assets": bool(existing.get("can_review_assets")),
        }

    existing_managed_users, _ = _resolve_project_share_users(
        db,
        list(existing_share_identifiers) + list(existing_reviewer_identifiers),
        field_name="managed_project_users",
        allow_missing=True,
    )
    existing_managed_ids = {
        int(user.id)
        for user in existing_managed_users
        if int(project.owner_id or 0) != int(user.id or 0)
    }

    for user_id in existing_managed_ids | set(desired_by_user_id.keys()):
        share = _get_project_share_record(db, project.id, user_id)
        desired = desired_by_user_id.get(user_id)
        if not desired:
            if share:
                db.delete(share)
            continue

        permissions = _normalize_project_share_permissions(getattr(share, "permissions", None) if share else None)
        permissions["can_review_assets"] = bool(desired.get("can_review_assets"))
        next_role = "editor" if desired.get("role") == "editor" else "reviewer"

        if not share:
            share = _build_project_share(project.id, user_id, next_role, permissions)
            db.add(share)
            continue

        _apply_project_share_access_fields(share, next_role, permissions)
        db.add(share)

    current_info[_PROJECT_GLOBAL_INFO_SHARE_USERS_KEY] = [
        username
        for user, username in zip(share_members, share_canonical_usernames)
        if int(project.owner_id or 0) != int(user.id or 0)
    ]
    current_info[_PROJECT_GLOBAL_INFO_REVIEWER_USERS_KEY] = [
        username
        for user, username in zip(reviewer_members, reviewer_canonical_usernames)
        if int(project.owner_id or 0) != int(user.id or 0)
    ]
    project.global_info = current_info


def _serialize_project_share(share: ProjectShare, user: User) -> ProjectShareOut:
    return ProjectShareOut(
        id=share.id,
        project_id=share.project_id,
        user_id=share.user_id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=_normalize_project_share_role(getattr(share, "role", None)),
        permissions=_normalize_project_share_permissions(getattr(share, "permissions", None)),
        created_at=share.created_at,
    )


def _review_thread_has_unread(thread: ProjectAssetReviewThreadModel, current_user: Optional[User]) -> bool:
    if not current_user:
        return False
    latest_dt = _parse_iso_datetime(getattr(thread, "latest_activity_at", None))
    if not latest_dt:
        return False
    last_read_raw = None
    if int(getattr(current_user, "id", 0) or 0) == int(getattr(thread, "requester_user_id", 0) or 0):
        last_read_raw = getattr(thread, "requester_last_read_at", None)
    elif int(getattr(current_user, "id", 0) or 0) == int(getattr(thread, "reviewer_user_id", 0) or 0):
        last_read_raw = getattr(thread, "reviewer_last_read_at", None)
    else:
        return False
    last_read_dt = _parse_iso_datetime(last_read_raw)
    if not last_read_dt:
        return True
    return latest_dt > last_read_dt


def _mark_review_thread_read_for_user(thread: ProjectAssetReviewThreadModel, current_user: User, *, read_at: Optional[str] = None) -> None:
    now_iso = str(read_at or now_bj_iso())
    if int(current_user.id or 0) == int(thread.requester_user_id or 0):
        thread.requester_last_read_at = now_iso
    elif int(current_user.id or 0) == int(thread.reviewer_user_id or 0):
        thread.reviewer_last_read_at = now_iso


def _serialize_review_thread(thread: ProjectAssetReviewThreadModel, requester: Optional[User] = None, reviewer: Optional[User] = None, current_user: Optional[User] = None) -> ProjectAssetReviewThreadOut:
    return ProjectAssetReviewThreadOut(
        id=thread.id,
        project_id=thread.project_id,
        requester_user_id=thread.requester_user_id,
        requester_username=getattr(requester, "username", None),
        reviewer_user_id=thread.reviewer_user_id,
        reviewer_username=getattr(reviewer, "username", None),
        title=thread.title,
        status=str(thread.status or "open"),
        latest_round_no=int(thread.latest_round_no or 0),
        latest_activity_at=thread.latest_activity_at,
        has_unread=_review_thread_has_unread(thread, current_user),
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


def _serialize_review_round(round_row: ProjectAssetReviewRoundModel, initiator: Optional[User] = None) -> ProjectAssetReviewRoundOut:
    return ProjectAssetReviewRoundOut(
        id=round_row.id,
        thread_id=round_row.thread_id,
        round_no=int(round_row.round_no or 1),
        initiated_by_user_id=round_row.initiated_by_user_id,
        initiated_by_username=getattr(initiator, "username", None),
        request_message=round_row.request_message,
        scope_type=str(round_row.scope_type or "all_current"),
        entity_required=bool(round_row.entity_required),
        shot_required=bool(round_row.shot_required),
        entity_decision=str(round_row.entity_decision or "pending"),
        shot_decision=str(round_row.shot_decision or "pending"),
        overall_status=str(round_row.overall_status or "pending_reviewer"),
        entity_feedback=round_row.entity_feedback,
        shot_feedback=round_row.shot_feedback,
        due_at=round_row.due_at,
        selected_entity_ids=_normalize_int_list(getattr(round_row, "selected_entity_ids", None)),
        selected_shot_ids=_normalize_int_list(getattr(round_row, "selected_shot_ids", None)),
        created_at=round_row.created_at,
        updated_at=round_row.updated_at,
        closed_at=round_row.closed_at,
    )


def _serialize_review_message(message: ProjectAssetReviewMessageModel, sender: Optional[User] = None) -> ProjectAssetReviewMessageOut:
    return ProjectAssetReviewMessageOut(
        id=message.id,
        round_id=message.round_id,
        sender_user_id=message.sender_user_id,
        sender_username=getattr(sender, "username", None),
        sender_role=str(message.sender_role or "requester"),
        message_type=str(message.message_type or "message"),
        message_text=message.message_text,
        entity_decision=message.entity_decision,
        shot_decision=message.shot_decision,
        entity_feedback=message.entity_feedback,
        shot_feedback=message.shot_feedback,
        created_at=message.created_at,
    )


def _ensure_review_scope_has_dimension(entity_required: bool, shot_required: bool) -> None:
    if not entity_required and not shot_required:
        raise HTTPException(status_code=400, detail="At least one of entity_required or shot_required must be true")


def _validate_review_target_ids_for_project(
    db: Session,
    project_id: int,
    entity_ids: List[int],
    shot_ids: List[int],
    *,
    scope_type: str,
) -> Tuple[List[int], List[int]]:
    normalized_entity_ids = _normalize_int_list(entity_ids)
    normalized_shot_ids = _normalize_int_list(shot_ids)

    if scope_type == "selected_only" and not normalized_entity_ids and not normalized_shot_ids:
        raise HTTPException(status_code=400, detail="selected_only scope requires at least one entity or shot id")

    if normalized_entity_ids:
        existing_entity_ids = {
            int(row_id)
            for row_id, in db.query(Entity.id).filter(
                Entity.project_id == project_id,
                Entity.id.in_(normalized_entity_ids),
            ).all()
        }
        missing_entity_ids = [item for item in normalized_entity_ids if item not in existing_entity_ids]
        if missing_entity_ids:
            raise HTTPException(status_code=400, detail=f"Entity ids not found in project: {missing_entity_ids}")

    if normalized_shot_ids:
        existing_shot_ids = {
            int(row_id)
            for row_id, in db.query(Shot.id)
            .join(Scene, Scene.id == Shot.scene_id)
            .join(Episode, Episode.id == Scene.episode_id)
            .filter(
                Episode.project_id == project_id,
                Shot.id.in_(normalized_shot_ids),
            ).all()
        }
        missing_shot_ids = [item for item in normalized_shot_ids if item not in existing_shot_ids]
        if missing_shot_ids:
            raise HTTPException(status_code=400, detail=f"Shot ids not found in project: {missing_shot_ids}")

    return normalized_entity_ids, normalized_shot_ids


def _resolve_thread_sender_role(db: Session, thread: ProjectAssetReviewThreadModel, current_user: User, project: Project) -> str:
    if current_user.id == thread.reviewer_user_id:
        return "reviewer"
    if current_user.id == thread.requester_user_id:
        return "requester"
    raise HTTPException(status_code=403, detail="Not authorized to reply in this review thread")


def _resolve_review_reviewer(
    db: Session,
    project: Project,
    current_user: User,
    reviewer_user_id: Optional[int],
    reviewer_user: Optional[str],
) -> User:
    resolved_user: Optional[User] = None
    parsed_user_id = int(reviewer_user_id or 0)
    if parsed_user_id > 0:
        resolved_user = db.query(User).filter(User.id == parsed_user_id).first()
    if not resolved_user:
        target = str(reviewer_user or "").strip()
        if target:
            resolved_user = db.query(User).filter(or_(User.username == target, User.email == target)).first()
    reviewer = resolved_user
    if not reviewer:
        raise HTTPException(status_code=404, detail="Reviewer user not found")
    if int(project.owner_id or 0) == int(reviewer.id or 0):
        return reviewer
    share = _get_project_share_record(db, project.id, reviewer.id)
    if not share:
        if int(project.owner_id or 0) != int(current_user.id or 0):
            raise HTTPException(status_code=400, detail="Reviewer must already have project access")
        share = ProjectShare(
            project_id=project.id,
            user_id=reviewer.id,
            role="reviewer",
            permissions={"can_review_assets": True},
        )
        db.add(share)
        db.flush()
        return reviewer
    if int(project.owner_id or 0) == int(current_user.id or 0):
        next_role = _normalize_project_share_role(getattr(share, "role", None))
        if next_role == "viewer":
            share.role = "reviewer"
        permissions = _normalize_project_share_permissions(getattr(share, "permissions", None))
        permissions["can_review_assets"] = True
        share.permissions = permissions
        db.add(share)
    if not _project_share_can_review_assets(share):
        if int(project.owner_id or 0) != int(current_user.id or 0):
            raise HTTPException(status_code=400, detail="Reviewer must have reviewer or editor access")
    return reviewer


def _require_review_thread_access(db: Session, thread_id: int, current_user: User) -> Tuple[ProjectAssetReviewThreadModel, Project]:
    _require_review_models()
    thread = _run_with_schema_self_heal(
        db,
        lambda: db.query(ProjectAssetReviewThread).filter(ProjectAssetReviewThread.id == thread_id).first(),
        context="review_thread.require_access",
    )
    if not thread:
        raise HTTPException(status_code=404, detail="Review thread not found")
    project = _require_project_access(db, int(thread.project_id), current_user)
    if current_user.id in {thread.requester_user_id, thread.reviewer_user_id, project.owner_id}:
        return thread, project
    share = _get_project_share_record(db, project.id, current_user.id)
    if share and _normalize_project_share_role(getattr(share, "role", None)) == "editor":
        return thread, project
    raise HTTPException(status_code=403, detail="Not authorized to access this review thread")


def _require_review_round_access(db: Session, round_id: int, current_user: User) -> Tuple[ProjectAssetReviewRoundModel, ProjectAssetReviewThreadModel, Project]:
    _require_review_models()
    round_row = db.query(ProjectAssetReviewRound).filter(ProjectAssetReviewRound.id == round_id).first()
    if not round_row:
        raise HTTPException(status_code=404, detail="Review round not found")
    thread, project = _require_review_thread_access(db, int(round_row.thread_id), current_user)
    return round_row, thread, project

def _require_project_access(
    db: Session,
    project_id: int,
    current_user: User,
    owner_only: bool = False,
) -> Project:
    from app.api.deps import is_current_http_mutating

    project = db.query(Project).filter(Project.id == project_id, _active_project_clause()).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    is_owner = project.owner_id == current_user.id
    if is_owner:
        return project

    is_superuser = bool(getattr(current_user, "is_superuser", False))
    is_root_super_system_user = (
        is_superuser
        and str(getattr(current_user, "username", "")).strip().lower() == "ylsystem"
    )
    # Root system account keeps full admin access (including mutations).
    if is_root_super_system_user:
        return project

    if owner_only:
        raise HTTPException(status_code=403, detail="This action is restricted to project owner")

    if _is_project_shared_with_user(db, project.id, current_user.id):
        return project

    # Any other superuser may temporarily peek any project (read-only).
    if is_superuser:
        if is_current_http_mutating():
            raise HTTPException(
                status_code=403,
                detail="Superuser temporary project view is read-only",
            )
        return project

    raise HTTPException(status_code=403, detail="Not authorized")


def _attach_project_flags(project: Project, current_user: User, db: Session = None) -> Project:
    is_owner = project.owner_id == current_user.id
    project.is_owner = is_owner
    is_shared = False
    if not is_owner and db is not None:
        try:
            is_shared = bool(_is_project_shared_with_user(db, int(project.id), int(current_user.id)))
        except Exception:
            is_shared = False
    is_superuser = bool(getattr(current_user, "is_superuser", False))
    is_root_super_system_user = (
        is_superuser
        and str(getattr(current_user, "username", "")).strip().lower() == "ylsystem"
    )
    # Non-root superuser without ownership/share → temporary view-only.
    # Root system account is not marked temp-view unless the peek endpoint forces it.
    is_temp_view = bool(is_superuser and not is_owner and not is_shared and not is_root_super_system_user)
    project.is_temp_view = is_temp_view
    project.can_edit = bool(is_owner or is_shared or is_root_super_system_user)
    return project
