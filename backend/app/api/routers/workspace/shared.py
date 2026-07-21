# -*- coding: utf-8 -*-
"""Projects / episodes / scenes / shots workspace routes (P6-P8 remainder)."""
from __future__ import annotations
import logging
import os
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.time_utils import BEIJING_TZ, now_bj_iso
from app.db.session import SessionLocal, get_db
from app.models.all_models import *
# Star-import must not shadow the datetime class (all_models used to export the module).
from datetime import datetime, timedelta  # noqa: E402
from app.services.agent_service import agent_service
from app.services.billing_service import billing_service
from app.services.llm_service import llm_service
logger = logging.getLogger("api_logger")
router = APIRouter(tags=["projects-workspace"])

from app.services.soft_delete import (  # noqa: E402
    _active_episode_clause,
    _active_project_clause,
    _active_scene_clause,
    _active_shot_clause,
)


def _bind_endpoint_helpers(*, include_routers: bool = True) -> None:
    # Early call uses include_routers=False to avoid circular facade imports.
    from app.api.routers.helper_bind import bind_shared_helpers
    bind_shared_helpers(globals(), __name__, include_routers=include_routers)

_bind_endpoint_helpers(include_routers=False)

# --- Projects ---
from app.schemas.project import (  # noqa: E402
    ProjectCreate,
    ProjectOut,
    ProjectShareCreate,
    ProjectShareOut,
    ProjectUpdate,
)

from app.schemas.asset_review import (  # noqa: E402,F401
    ProjectAssetReviewMessageCreate,
    ProjectAssetReviewMessageOut,
    ProjectAssetReviewRoundCreate,
    ProjectAssetReviewRoundOut,
    ProjectAssetReviewThreadCreate,
    ProjectAssetReviewThreadOut,
    ProjectAssetReviewThreadReadUpdate,
    ProjectAssetReviewThreadStatusUpdate,
)


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


_PROJECT_LEVEL_GENERATION_DEFAULT_KEYS = (
    "model",
    "quality",
    "style",
    "safety_tolerance",
    "voice",
    "reasoning_effort",
    "aspect_ratio",
    "resolution",
    "size",
    "image_resolution",
    "image_size",
    "horizontal_resolution",
    "vertical_resolution",
    "upscale_factor",
    "character_orientation",
    "duration",
    "n_frames",
    "num_images",
)


# Shared with billing estimate / other light callers (avoid duplicating tables).
from app.services.project_visual_resolution import (
    PROJECT_IMAGE_SIZE_LONG_EDGE_MAP as _PROJECT_IMAGE_SIZE_LONG_EDGE_MAP,
    PROJECT_IMAGE_SIZE_SQUARE_MAP as _PROJECT_IMAGE_SIZE_SQUARE_MAP,
    PROJECT_RESOLUTION_PRESETS as _PROJECT_RESOLUTION_PRESETS,
    infer_dims_from_video_resolution_tier as _infer_dims_from_video_resolution_tier,
    infer_project_resolution as _infer_project_resolution,
    normalize_project_image_size as _normalize_project_image_size,
    normalize_project_video_resolution as _normalize_project_video_resolution,
    parse_aspect_ratio_pair as _parse_aspect_ratio_pair,
    project_video_resolution_label as _project_video_resolution_label,
)


def _to_positive_int_or_none(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except Exception:
        return None
    return parsed if parsed > 0 else None


def _safe_json_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return {}
        try:
            import json as _json
            parsed = _json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _episode_runtime_info_from_episode(episode: Optional[Episode]) -> Dict[str, Any]:
    """Read raw episode_info for runtime status keys even when generic reads are disabled."""
    if not episode:
        return {}
    return _safe_json_dict(getattr(episode, "episode_info", None))


def _extract_episode_number_from_title(title: Any) -> Optional[int]:
    value = str(title or "").strip()
    if not value:
        return None

    match = re.search(r"(?:Episode|EP)\s*[-_#]?\s*(\d+)", value, flags=re.IGNORECASE)
    if match:
        return _to_positive_int_or_none(match.group(1))

    match = re.search(r"第\s*(\d+)\s*集", value)
    if match:
        return _to_positive_int_or_none(match.group(1))

    return None


def _resolve_episode_sort_number(episode: Optional[Episode]) -> Optional[int]:
    if not episode:
        return None

    info = _episode_runtime_info_from_episode(episode)
    for key in (
        "episode_script_episode_number",
        "story_dna_episode_number",
        "episode_number",
        "index",
    ):
        parsed = _to_positive_int_or_none(info.get(key) if isinstance(info, dict) else None)
        if parsed:
            return parsed

    return _extract_episode_number_from_title(getattr(episode, "title", None))


def _sort_project_episodes(episodes: List[Episode]) -> List[Episode]:
    def _sort_key(episode: Episode):
        resolved_number = _resolve_episode_sort_number(episode)
        fallback_id = int(getattr(episode, "id", 0) or 0)
        if resolved_number is not None:
            return (0, int(resolved_number), fallback_id)
        return (1, fallback_id, fallback_id)

    return sorted(list(episodes or []), key=_sort_key)


def _resolve_project_video_sound(global_info: Any, *, default: bool = True) -> bool:
    gi = global_info if isinstance(global_info, dict) else {}
    defaults_raw = gi.get("project_generation_defaults")
    defaults = defaults_raw if isinstance(defaults_raw, dict) else {}
    tech_params = gi.get("tech_params") if isinstance(gi.get("tech_params"), dict) else {}
    visual = tech_params.get("visual_standard") if isinstance(tech_params.get("visual_standard"), dict) else {}
    for candidate in (
        gi.get("video_sound"),
        gi.get("sound"),
        defaults.get("sound"),
        visual.get("sound"),
    ):
        if candidate is None:
            continue
        return _to_bool(candidate)
    return default


def _ensure_project_generation_defaults(global_info: Any) -> Dict[str, Any]:
    gi = dict(global_info) if isinstance(global_info, dict) else {}

    defaults_raw = gi.get("project_generation_defaults")
    defaults = dict(defaults_raw) if isinstance(defaults_raw, dict) else {}
    # Read-only normalization: unify alias keys; video_sound defaults to enabled when unset.
    tech_params = gi.get("tech_params") if isinstance(gi.get("tech_params"), dict) else {}
    visual_standard = tech_params.get("visual_standard") if isinstance(tech_params.get("visual_standard"), dict) else {}

    # Precedence: project_generation_defaults / visual_standard > top-level legacy keys.
    aspect_ratio = str(
        defaults.get("aspect_ratio")
        or defaults.get("aspectRatio")
        or visual_standard.get("aspect_ratio")
        or visual_standard.get("aspectRatio")
        or gi.get("aspect_ratio")
        or gi.get("aspectRatio")
        or ""
    ).strip()
    if aspect_ratio:
        defaults["aspect_ratio"] = aspect_ratio
        visual_standard.setdefault("aspect_ratio", aspect_ratio)

    image_size = _normalize_project_image_size(
        defaults.get("image_size")
        or defaults.get("imageSize")
        or defaults.get("image_resolution")
        or defaults.get("imageResolution")
        or visual_standard.get("image_size")
        or visual_standard.get("imageSize")
        or gi.get("image_size")
        or gi.get("imageSize")
    )
    if image_size:
        defaults["image_size"] = image_size
        visual_standard.setdefault("image_size", image_size)

    video_resolution = _normalize_project_video_resolution(
        defaults.get("video_resolution")
        or visual_standard.get("video_resolution")
        or gi.get("video_resolution")
    ) or "720"
    defaults["video_resolution"] = video_resolution
    visual_standard["video_resolution"] = video_resolution

    current_w = (
        _to_positive_int_or_none(defaults.get("horizontal_resolution"))
        or _to_positive_int_or_none(defaults.get("horizontalResolution"))
        or _to_positive_int_or_none(visual_standard.get("horizontal_resolution"))
        or _to_positive_int_or_none(visual_standard.get("horizontalResolution"))
        or _to_positive_int_or_none(visual_standard.get("h_resolution"))
        or _to_positive_int_or_none(visual_standard.get("width"))
        or _to_positive_int_or_none(gi.get("horizontal_resolution"))
        or _to_positive_int_or_none(gi.get("horizontalResolution"))
        or _to_positive_int_or_none(gi.get("width"))
    )
    current_h = (
        _to_positive_int_or_none(defaults.get("vertical_resolution"))
        or _to_positive_int_or_none(defaults.get("verticalResolution"))
        or _to_positive_int_or_none(visual_standard.get("vertical_resolution"))
        or _to_positive_int_or_none(visual_standard.get("verticalResolution"))
        or _to_positive_int_or_none(visual_standard.get("v_resolution"))
        or _to_positive_int_or_none(visual_standard.get("height"))
        or _to_positive_int_or_none(gi.get("vertical_resolution"))
        or _to_positive_int_or_none(gi.get("verticalResolution"))
        or _to_positive_int_or_none(gi.get("height"))
    )

    if current_w and current_h:
        defaults["horizontal_resolution"] = int(current_w)
        defaults["vertical_resolution"] = int(current_h)
        visual_standard.setdefault("horizontal_resolution", int(current_w))
        visual_standard.setdefault("vertical_resolution", int(current_h))

    # If only logical size tier exists, infer concrete dimensions from aspect ratio.
    if (not current_w or not current_h) and aspect_ratio and image_size:
        inferred_dims = _infer_project_resolution(aspect_ratio, image_size)
        if inferred_dims:
            inferred_w, inferred_h = inferred_dims
            if inferred_w and inferred_h:
                defaults["horizontal_resolution"] = int(inferred_w)
                defaults["vertical_resolution"] = int(inferred_h)
                visual_standard.setdefault("horizontal_resolution", int(inferred_w))
                visual_standard.setdefault("vertical_resolution", int(inferred_h))

    quality = str(
        defaults.get("quality")
        or visual_standard.get("quality")
        or gi.get("quality")
        or ""
    ).strip()
    if quality:
        defaults.setdefault("quality", quality)
        visual_standard.setdefault("quality", quality)

    tech_params["visual_standard"] = visual_standard
    gi["tech_params"] = tech_params
    gi["project_generation_defaults"] = defaults

    resolved_sound = _resolve_project_video_sound(gi, default=True)
    gi["video_sound"] = resolved_sound
    defaults["sound"] = resolved_sound
    visual_standard["sound"] = resolved_sound
    tech_params["visual_standard"] = visual_standard
    gi["tech_params"] = tech_params
    gi["project_generation_defaults"] = defaults
    return gi



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


# _active_project_clause -> soft_delete


# _active_episode_clause -> soft_delete


# _active_scene_clause -> soft_delete


def _scene_no_sort_key(scene) -> tuple:
    scene_no = str(getattr(scene, "scene_no", None) or "").strip()
    if not scene_no:
        return (1, (), "", int(getattr(scene, "id", 0) or 0))
    nums = tuple(int(m) for m in re.findall(r"\d+", scene_no))
    return (0, nums, scene_no.lower(), int(getattr(scene, "id", 0) or 0))


def _sort_scenes_by_scene_no(scenes: list) -> list:
    return sorted(scenes, key=_scene_no_sort_key)


def _canonicalize_scene_no(scene_no: Any, *, scene_id: Any = None) -> str:
    """
    Normalize workspace Scene.scene_no so one episode cannot store aliases
    of the same number (EP01_SC03 / 03 / 3 → "3"). Letter-suffix IDs stay intact.
    """
    raw_id = str(scene_id or "").strip()
    raw_no = str(scene_no or "").strip()
    source = raw_id or raw_no
    if not source:
        return ""

    letter_match = re.fullmatch(r"(EP\d+_SC\d+[A-Za-z]+)", source, flags=re.IGNORECASE)
    if letter_match:
        return letter_match.group(1).upper()

    canonical_match = re.fullmatch(r"EP\d+_SC(\d+)", source, flags=re.IGNORECASE)
    if canonical_match:
        return str(int(canonical_match.group(1)))

    sc_match = re.fullmatch(r"SC?(\d+)", source, flags=re.IGNORECASE)
    if sc_match:
        return str(int(sc_match.group(1)))

    if re.fullmatch(r"\d+", source):
        return str(int(source))

    if raw_no and raw_no != source:
        return _canonicalize_scene_no(raw_no)

    return source


def _scene_no_lookup_keys(scene_no: Any, *, scene_id: Any = None) -> List[str]:
    """Alias keys used when matching an existing active scene in one episode."""
    keys: List[str] = []
    canonical = _canonicalize_scene_no(scene_no, scene_id=scene_id)
    for candidate in (scene_no, scene_id, canonical):
        text = str(candidate or "").strip()
        if text:
            keys.append(text)
    if canonical and re.fullmatch(r"\d+", canonical):
        order = int(canonical)
        keys.append(f"{order:02d}")
        keys.append(f"SC{order:02d}")
        keys.append(f"SC{order}")
    # Preserve order while dropping empties/dupes.
    return list(dict.fromkeys(item for item in keys if item))


def _find_active_scene_by_scene_no(
    db: Session,
    *,
    episode_id: int,
    scene_no: Any,
    scene_id: Any = None,
) -> Optional[Any]:
    keys = _scene_no_lookup_keys(scene_no, scene_id=scene_id)
    if not keys:
        return None
    rows = (
        db.query(Scene)
        .filter(
            Scene.episode_id == int(episode_id),
            Scene.scene_no.in_(keys),
            _active_scene_clause(),
        )
        .order_by(Scene.id.desc())
        .all()
    )
    if not rows:
        return None
    canonical = _canonicalize_scene_no(scene_no, scene_id=scene_id)
    for row in rows:
        if _canonicalize_scene_no(getattr(row, "scene_no", None)) == canonical:
            return row
    return rows[0]


# _active_shot_clause -> soft_delete


def _active_asset_clause():
    return or_(Asset.is_deleted.is_(False), Asset.is_deleted.is_(None))


def _active_entity_clause():
    return or_(Entity.is_deleted.is_(False), Entity.is_deleted.is_(None))


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

def get_project_cover_image(db: Session, project_id: int) -> Optional[str]:
    # 0. 优先使用 named cover 或 type cover 相关的
    poster_entities = db.query(Entity).filter(
        Entity.project_id == project_id,
        _active_entity_clause(),
        or_(
            Entity.name.in_(["封面海报", "海报", "封面", "cover", "poster"]),
            Entity.name.ilike("%海报%"),
            Entity.name.ilike("%封面%"),
            Entity.name.ilike("%cover%"),
            Entity.name.ilike("%poster%"),
            Entity.type.in_(["poster", "posters", "cover", "project_cover", "cover_image"]),
            Entity.type.ilike("%poster%"),
            Entity.type.ilike("%cover%")
        ),
        Entity.image_url != None,
        Entity.image_url != ""
    ).all()
    
    poster_entity = None
    for p in poster_entities:
        if p.name == "封面海报":
            poster_entity = p
            break
        if not poster_entity:
            poster_entity = p

    if poster_entity:
        return _refresh_managed_media_url(poster_entity.image_url, db)

    project = db.query(Project).filter(Project.id == project_id).first()
    if project and isinstance(project.global_info, dict):
        configured_cover = str(project.global_info.get("cover_image") or project.global_info.get("coverImage") or "").strip()
        if configured_cover:
            return _refresh_managed_media_url(configured_cover, db)

    # 1. Try to find first valid image in Shots
    # Check if project_id is populated in shots first (optimization)
    shot = db.query(Shot).filter(Shot.project_id == project_id, Shot.image_url != None, Shot.image_url != "").first()
    if shot:
        return _refresh_managed_media_url(shot.image_url, db)
        
    # If project_id not reliable in shots, try join (fallback)
    shot = db.query(Shot).join(Scene).join(Episode).filter(Episode.project_id == project_id, Shot.image_url != None, Shot.image_url != "").first()
    if shot:
        return _refresh_managed_media_url(shot.image_url, db)

    # 2. Try Scenes? (Scene logic currently undefined as no direct image column, skip to Entities)
    
    # 3. Try Entities (Subjects)
    entity = db.query(Entity).filter(Entity.project_id == project_id, Entity.image_url != None, Entity.image_url != "").first()
    if entity:
        return _refresh_managed_media_url(entity.image_url, db)
        
    # 4. Try Assets? (Maybe, but user said Shots, Scenes, Subjects)
    
    return None


def _extract_md_section(md: str, start_header_regex: str) -> Tuple[str, str]:
    """Return (section_text, remainder) where section_text starts at the first header matching regex.

    Section is from matching header line up to (but not including) the next '## ' header.
    If not found, returns ("", md).
    """
    if not md:
        return "", md
    m = re.search(start_header_regex, md, flags=re.MULTILINE)
    if not m:
        return "", md
    start = m.start()
    after = md[m.end():]
    m2 = re.search(r"^##\s+", after, flags=re.MULTILINE)
    if m2:
        end = m.end() + m2.start()
        return md[start:end].strip(), (md[:start] + md[end:]).strip()
    return md[start:].strip(), md[:start].strip()



# Shared with script_analysis_flow (must not live only in this megamodule).
from app.services.llm_markdown_sanitize import (
    sanitize_llm_markdown_output,
    sanitize_subject_index_text,
)


def _is_provider_moderation_block_response(raw_text: Any, cleaned_text: Optional[str] = None) -> bool:
    """Treat moderation as a hard block only when the payload reduces to the marker itself."""
    raw = str(raw_text or "")
    cleaned = str(cleaned_text if cleaned_text is not None else sanitize_llm_markdown_output(raw)).strip()

    def _normalize_marker(value: str) -> str:
        text = str(value or "").strip()
        text = re.sub(r"^\s*=+\s*", "", text)
        return text.strip().upper()

    if cleaned and _normalize_marker(cleaned) != "PROHIBITED_CONTENT":
        return False

    raw_lines = [str(line or "").strip() for line in raw.splitlines() if str(line or "").strip()]
    if not raw_lines:
        return False

    non_marker_lines = [line for line in raw_lines if _normalize_marker(line) != "PROHIBITED_CONTENT"]
    return len(non_marker_lines) == 0


def _split_markdown_row_escaped(row_line: str) -> List[str]:
    """Split a markdown table row while respecting escaped pipes (\\|)."""
    if not row_line:
        return []

    s = str(row_line).strip()
    if not s:
        return []

    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]

    cells: List[str] = []
    buf: List[str] = []
    escaped = False
    for ch in s:
        if escaped:
            buf.append(ch)
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == "|":
            cells.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)

    if escaped:
        # Preserve trailing backslash if it does not escape any character.
        buf.append("\\")
    cells.append("".join(buf).strip())
    return cells


def _is_markdown_table_separator(line: str) -> bool:
    if not line:
        return False
    stripped = str(line).strip()
    if not stripped or "|" not in stripped:
        return False

    cols = _split_markdown_row_escaped(stripped)
    if not cols:
        return False

    for col in cols:
        token = col.replace(" ", "")
        if not token:
            return False
        token = token.strip(":")
        if len(token) < 3 or not all(ch == "-" for ch in token):
            return False
    return True


def _find_shot_pipe_merge_column_indices(headers: List[str]) -> List[int]:
    """Columns whose cell text may contain unescaped pipe separators."""
    indices: List[int] = []
    preferred_aliases = [
        ["shot logic (cn)", "shot_logic_cn", "镜头逻辑", "镜头逻辑（中文）"],
        ["video content (cn)", "video_prompt_cn", "视频内容（中文）"],
        ["start frame (cn)", "start_frame_cn", "起始帧（中文）"],
        ["keyframes (cn)", "keyframes_cn", "关键帧（中文）"],
        ["end frame (cn)", "end_frame_cn", "结束帧（中文）"],
    ]
    normalized_headers = [_normalize_shot_markdown_col_key(h) for h in headers]
    for aliases in preferred_aliases:
        alias_norms = {_normalize_shot_markdown_col_key(a) for a in aliases}
        for idx, normalized_header in enumerate(normalized_headers):
            if normalized_header in alias_norms:
                if idx not in indices:
                    indices.append(idx)
                break
            if any(
                alias and (alias in normalized_header or normalized_header in alias)
                for alias in alias_norms
            ):
                if idx not in indices:
                    indices.append(idx)
                break
    if not indices:
        indices = [3]
    return indices


def _reconcile_shot_markdown_row_cells(
    cells: List[str],
    header_count: int,
    merge_column_indices: Optional[List[int]] = None,
) -> List[str]:
    """Re-align shot markdown row cells when unescaped pipes inflated the column count."""
    vals = [str(c or "").strip() for c in (cells or [])]
    if header_count <= 0:
        return []
    if len(vals) <= header_count:
        while len(vals) < header_count:
            vals.append("")
        return vals[:header_count]

    # Common LLM artifact: an extra empty cell (spurious `|`) immediately before
    # Video Content (CN). Dropping those empties first avoids merging into Shot Logic,
    # which otherwise shifts Duration into Video Content and blanks Duration (s).
    # Only consider empties from the Start Frame (CN) region onward; never the
    # trailing Associated Entities cell.
    cn_region_start = 9 if header_count >= 14 else max(4, header_count - 5)
    while len(vals) > header_count:
        dropped = False
        for idx in range(cn_region_start, len(vals) - 1):
            if not vals[idx] and vals[idx + 1]:
                vals = vals[:idx] + vals[idx + 1 :]
                dropped = True
                break
        if not dropped:
            break

    merge_indices = list(merge_column_indices or [3])
    while len(vals) > header_count:
        overflow = len(vals) - header_count
        merge_idx = merge_indices[0] if merge_indices else header_count - 1
        merge_idx = max(0, min(int(merge_idx), header_count - 1))
        merge_end = min(len(vals), merge_idx + overflow + 1)
        merged = "|".join(vals[merge_idx:merge_end])
        vals = vals[:merge_idx] + [merged] + vals[merge_end:]
        if len(vals) > header_count:
            if len(merge_indices) > 1:
                merge_indices = merge_indices[1:]
                continue
            tail = " | ".join(vals[header_count - 1 :])
            vals = vals[: header_count - 1] + [tail]

    while len(vals) < header_count:
        vals.append("")
    return vals[:header_count]


def _normalize_markdown_table_cells(
    cells: List[str],
    header_count: int,
    *,
    merge_column_indices: Optional[List[int]] = None,
) -> List[str]:
    if header_count <= 0:
        return []
    vals = _reconcile_shot_markdown_row_cells(cells, header_count, merge_column_indices)
    import re
    normalized: List[str] = []
    for c in vals:
        if c:
            c = re.sub(r"(?i)<br\s*/?>", "\n", str(c)).replace("\\n", "\n").strip()
        normalized.append(c or "")
    return normalized


def _looks_like_markdown_table_row_for_shots(line: str) -> bool:
    s = str(line or "").strip()
    if not s:
        return False
    if s.startswith("|"):
        return True
    # Accept markdown rows without leading/trailing pipes.
    return s.count("|") >= 2


def _is_shot_markdown_header_row(line: str) -> bool:
    """True when a table row is a Shot List header (not a data row)."""
    cells = _split_markdown_row_escaped(str(line or "").strip())
    if not cells:
        return False
    first = _normalize_shot_markdown_col_key(cells[0])
    if first in {"shotid", "镜头id"}:
        return True
    normalized_cells = {_normalize_shot_markdown_col_key(cell) for cell in cells}
    return "shotid" in normalized_cells and "sceneid" in normalized_cells


def _is_placeholder_shot_row(row: Dict[str, Any]) -> bool:
    """Reject prompt example / re-emitted header rows mistaken as shot data."""
    if not isinstance(row, dict):
        return True
    shot_id = _pick_shot_cell(row, ["Shot ID", "shot_id", "镜头ID"], "")
    raw_id = str(shot_id or "").strip()
    if not raw_id:
        return True
    if re.fullmatch(r"(shot\s*id|镜头\s*id)", raw_id, flags=re.IGNORECASE):
        return True
    normalized_id = _normalize_shot_business_id(raw_id)
    if not normalized_id:
        return True
    # Header cell "Shot ID" normalizes to "ID" via _normalize_shot_business_id.
    if normalized_id in {"ID", "镜头ID", "{SCENE ID}_SHZZ", "{SCENEID}_SHZZ", "EPXX_SCYY_SHZZ"}:
        return True
    if "{SCENE" in normalized_id or "SHZZ" in normalized_id:
        return True
    if not re.search(r"_SH\d{2}(_\d+)?$", normalized_id, flags=re.IGNORECASE) and (
        "SHZZ" in raw_id.upper() or "{SCENE" in raw_id.upper()
    ):
        return True
    shot_name = _pick_shot_cell(row, ["Shot Name", "shot_name", "镜头名称"], "")
    if shot_name and re.search(r"核心动作简述|^\(正整数", shot_name):
        return True
    scene_id = _pick_shot_cell(
        row,
        ["Scene ID", "scene_id", "Scene Code", "scene_code", "场景ID", "场景编号"],
        "",
    )
    if scene_id and re.search(r"上游\s*Scene\s*ID|原样", scene_id, flags=re.IGNORECASE):
        return True
    return False


_REAL_SHOT_ID_RE = re.compile(
    r"^EP\d{2}_SC\d{2}[A-Za-z]*_SH\d{2}(_\d+)?$",
    re.IGNORECASE,
)


def _shot_id_cell_looks_real(cell: Any) -> bool:
    text = str(cell or "").strip()
    if not text:
        return False
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"(?i)^shot\s*", "", text).strip()
    return bool(_REAL_SHOT_ID_RE.match(text))


def _extract_shot_markdown_table_blocks(lines: List[str]) -> List[List[str]]:
    """Split LLM output into discrete markdown table blocks (header+sep+data)."""
    blocks: List[List[str]] = []
    i = 0
    total = len(lines)
    while i < total - 1:
        header_line = str(lines[i] or "").strip()
        sep_line = str(lines[i + 1] or "").strip()
        if not (
            _looks_like_markdown_table_row_for_shots(header_line)
            and len(_split_markdown_row_escaped(header_line)) >= 2
            and _is_markdown_table_separator(sep_line)
        ):
            i += 1
            continue

        kept_lines: List[str] = [str(lines[i]), str(lines[i + 1])]
        data_row_count = 0
        j = i + 2
        while j < total:
            stripped = str(lines[j] or "").strip()
            if not stripped:
                if data_row_count > 0:
                    break
                j += 1
                continue
            if stripped.startswith("#"):
                break
            if _looks_like_markdown_table_row_for_shots(stripped):
                if _is_markdown_table_separator(stripped):
                    if data_row_count > 0:
                        break
                    j += 1
                    continue
                if data_row_count > 0 and _is_shot_markdown_header_row(stripped):
                    break
                kept_lines.append(stripped)
                data_row_count += 1
                j += 1
                continue
            if data_row_count > 0:
                break
            j += 1

        if data_row_count > 0:
            blocks.append(kept_lines)
        i = max(j, i + 2)

    return blocks


def _score_shot_markdown_table_block(block_lines: List[str]) -> int:
    """Prefer tables with real EP##_SC##_SH## ids over prompt example tables."""
    real_ids = 0
    for line in block_lines[2:]:
        cells = _split_markdown_row_escaped(str(line or "").strip())
        if not cells:
            continue
        if _is_shot_markdown_header_row(line):
            continue
        if _shot_id_cell_looks_real(cells[0]):
            real_ids += 1
    return real_ids


def sanitize_shots_markdown_table_text(text: Any) -> str:
    """Keep one Shot List markdown table from LLM output.

    Stops each table at blank lines / re-headers (no cross-table merge).
    If multiple tables exist, prefer the block with the most real Shot IDs
    so prompt example tables do not displace the actual shot list.
    """
    cleaned = sanitize_llm_markdown_output(str(text or ""))
    if not cleaned:
        return ""

    lines = str(cleaned).splitlines()
    if not lines:
        return ""

    blocks = _extract_shot_markdown_table_blocks(lines)
    if not blocks:
        return ""

    best_block = max(
        blocks,
        key=lambda block: (_score_shot_markdown_table_block(block), len(block)),
    )
    if not best_block:
        return ""

    return "\n".join(str(line) for line in best_block).strip()


def parse_shots_markdown_table(markdown_text: str) -> Tuple[List[str], List[Dict[str, str]], int]:
    """Parse a markdown shot table into headers and rows.

    Returns (headers, rows, table_line_count).
    """
    if not markdown_text:
        return [], [], 0

    lines = str(markdown_text).splitlines()
    header_idx = -1
    separator_idx = -1

    for i in range(len(lines) - 1):
        header_line = lines[i].strip()
        sep_line = lines[i + 1].strip()
        if not _looks_like_markdown_table_row_for_shots(header_line):
            continue
        header_cells_raw = _split_markdown_row_escaped(header_line)
        if len(header_cells_raw) < 2:
            continue
        if _is_markdown_table_separator(sep_line):
            header_idx = i
            separator_idx = i + 1
            break

    raw_headers: List[str] = []
    if header_idx >= 0 and separator_idx >= 0:
        raw_headers = _split_markdown_row_escaped(lines[header_idx].strip())

    # Fallback: some providers occasionally return a markdown table where
    # the header row is missing, but separator/data rows still exist.
    if not raw_headers:
        sep_only_idx = -1
        for i, line in enumerate(lines):
            if _is_markdown_table_separator(str(line or "").strip()):
                sep_only_idx = i
                break

        if sep_only_idx >= 0:
            first_data_cells: List[str] = []
            for line in lines[sep_only_idx + 1 :]:
                stripped = str(line or "").strip()
                if not stripped:
                    continue
                if stripped.startswith("#"):
                    break
                if _looks_like_markdown_table_row_for_shots(stripped) and not _is_markdown_table_separator(stripped):
                    first_data_cells = _split_markdown_row_escaped(stripped)
                    break

            if first_data_cells:
                fallback_headers = [
                    "Shot ID",
                    "Shot Name",
                    "Scene ID",
                    "Shot Logic (CN)",
                    "Start Frame",
                    "Video Content",
                    "Duration (s)",
                    "Keyframes",
                    "End Frame",
                    "Start Frame (CN)",
                    "Video Content (CN)",
                    "Keyframes (CN)",
                    "End Frame (CN)",
                    "Associated Entities",
                ]
                needed = len(first_data_cells)
                if needed > len(fallback_headers):
                    fallback_headers.extend([f"Column {idx}" for idx in range(len(fallback_headers) + 1, needed + 1)])
                raw_headers = fallback_headers[:needed]
                separator_idx = sep_only_idx

    if not raw_headers or separator_idx < 0:
        return [], [], 0

    headers = [h.replace("*", "").replace("_", "").strip() for h in raw_headers]
    header_count = len(headers)
    if header_count <= 0:
        return [], [], 0
    merge_column_indices = _find_shot_pipe_merge_column_indices(headers)

    rows: List[Dict[str, str]] = []
    table_line_count = 0
    row_cells: List[str] = []

    def _flush_row() -> None:
        nonlocal row_cells
        if not row_cells:
            return
        if all(not str(c or "").strip() for c in row_cells):
            row_cells = []
            return
        normalized = _normalize_markdown_table_cells(
            row_cells,
            header_count,
            merge_column_indices=merge_column_indices,
        )
        rows.append({headers[i]: normalized[i] for i in range(header_count)})
        row_cells = []

    for line in lines[separator_idx + 1:]:
        stripped = line.strip()
        # Blank line ends the first table (avoid merging a second example/header table).
        if not stripped:
            if rows or row_cells:
                break
            continue

        # A new markdown heading usually means current table section ended.
        if stripped.startswith("#"):
            break

        if _looks_like_markdown_table_row_for_shots(stripped):
            if _is_markdown_table_separator(stripped):
                if rows or row_cells:
                    break
                continue
            if (rows or row_cells) and _is_shot_markdown_header_row(stripped):
                break

            table_line_count += 1
            cells = _split_markdown_row_escaped(stripped)
            if not cells:
                continue

            if not row_cells:
                row_cells = list(cells)
            elif len(row_cells) >= header_count:
                _flush_row()
                row_cells = list(cells)
            else:
                row_cells.extend(cells)

            if len(row_cells) >= header_count:
                _flush_row()
            continue

        # Non-pipe line inside table area: append as continuation into last cell.
        if row_cells:
            row_cells[-1] = (str(row_cells[-1] or "") + "\n" + stripped).strip()

    _flush_row()

    return headers, rows, table_line_count


# Whitelist mapping for extra shot markdown columns.
# target=shot_field writes into Shot model columns;
# target=tech_field writes into technical_notes JSON keys.
SHOT_MARKDOWN_COLUMN_WHITELIST: Dict[str, Dict[str, str]] = {
    # Camera grammar / cinematography
    "cameraangle": {"target": "tech_field", "field": "camera_angle"},
    "cameramovement": {"target": "tech_field", "field": "camera_movement"},
    "cameralanguage": {"target": "tech_field", "field": "camera_language"},
    "composition": {"target": "tech_field", "field": "composition"},
    "lens": {"target": "tech_field", "field": "lens"},
    "focallength": {"target": "tech_field", "field": "focal_length"},
    "shottype": {"target": "tech_field", "field": "shot_type"},
    "framing": {"target": "tech_field", "field": "framing"},
    # Light / atmosphere / style
    "lighting": {"target": "tech_field", "field": "lighting"},
    "colortone": {"target": "tech_field", "field": "color_tone"},
    "mood": {"target": "tech_field", "field": "mood"},
    "style": {"target": "tech_field", "field": "style"},
    # Audio / performance
    "sounddesign": {"target": "tech_field", "field": "sound_design"},
    "ambientsound": {"target": "tech_field", "field": "ambient_sound"},
    "dialogue": {"target": "tech_field", "field": "dialogue"},
    "voiceover": {"target": "tech_field", "field": "voiceover_text"},
    # Production / edit notes
    "vfxnotes": {"target": "tech_field", "field": "vfx_notes"},
    "reviewnotes": {"target": "tech_field", "field": "review_notes"},
    "editnotes": {"target": "tech_field", "field": "edit_notes"},
    "continuity": {"target": "tech_field", "field": "continuity"},
    "transition": {"target": "tech_field", "field": "transition"},
}


def _normalize_shot_markdown_col_key(key: str) -> str:
    return re.sub(r"[\s_\-./()（）:：]", "", str(key or "").strip().lower())


_SHOT_MARKDOWN_DEFAULT_HEADERS: List[str] = [
    "Shot ID",
    "Shot Name",
    "Scene ID",
    "Shot Logic (CN)",
    "Start Frame",
    "Video Content",
    "Duration (s)",
    "Keyframes",
    "End Frame",
    "Start Frame (CN)",
    "Video Content (CN)",
    "Keyframes (CN)",
    "End Frame (CN)",
    "Associated Entities",
]


_SHOT_REQUIRED_ROW_FIELDS: List[Tuple[str, List[str]]] = [
    ("Shot ID", ["Shot ID", "shot_id", "镜头ID"]),
    ("Shot Name", ["Shot Name", "shot_name", "镜头名称"]),
    ("Scene ID", ["Scene ID", "scene_id", "Scene Code", "scene_code", "场景ID", "场景编号"]),
    ("Shot Logic (CN)", ["Shot Logic (CN)", "shot_logic_cn", "镜头逻辑", "镜头画面逻辑说明"]),
]


def _coerce_shot_row_associated_entities_or_default(row: Dict[str, Any], *, default: str = "none") -> Tuple[bool, Optional[str]]:
    """Normalize Associated Entities in-place when blank (import accepts empty)."""
    if not isinstance(row, dict):
        return False, None
    aliases = ["Associated Entities", "associated_entities", "关联实体"]
    current = _pick_shot_cell(row, aliases, "")
    if current:
        return False, None
    entity_key = "Associated Entities"
    for key in aliases:
        if key in row:
            entity_key = key
            break
    row[entity_key] = default
    return True, f"Associated Entities missing; defaulted to {default}"


_SHOT_REQUIRED_ROW_FIELD_GROUPS: List[Tuple[str, List[str]]] = [
    ("Video Content or Video Content (CN)", [
        "Video Content", "video_content", "视频内容",
        "Video Content (CN)", "video_content_cn", "video_prompt_cn", "视频内容（中文）",
        "中文视频提示词内容", "中文视频提示词", "视频提示词内容", "视频提示词", "中文动态视频提示词",
        "Prompt (CN)", "Prompts (CN)", "Prompt CN", "prompt_cn", "提示词（中文）", "中文提示词",
        "prompt_preview_cn",
    ]),
]


def _shot_row_technical_notes_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    for key in ("technical_notes", "technicalNotes"):
        raw_notes = row.get(key)
        if isinstance(raw_notes, dict):
            return raw_notes
        if isinstance(raw_notes, str) and raw_notes.strip():
            try:
                parsed = json.loads(raw_notes)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue
    return {}


def _pick_shot_cell(row: Dict[str, Any], aliases: List[str], default: str = "") -> str:
    if not isinstance(row, dict):
        return default
    for key in aliases:
        if key in row and row.get(key) is not None:
            return str(row.get(key) or "").strip()
    normalized_aliases = {_normalize_shot_markdown_col_key(key) for key in aliases}
    for raw_key, raw_value in row.items():
        if _normalize_shot_markdown_col_key(raw_key) in normalized_aliases and raw_value is not None:
            return str(raw_value or "").strip()
    notes = _shot_row_technical_notes_dict(row)
    if notes:
        for key in aliases:
            if key in notes and notes.get(key) is not None:
                return str(notes.get(key) or "").strip()
        for raw_key, raw_value in notes.items():
            if _normalize_shot_markdown_col_key(raw_key) in normalized_aliases and raw_value is not None:
                return str(raw_value or "").strip()
    return default


def _pick_shot_video_prompt_cell(row: Dict[str, Any]) -> str:
    direct_value = _pick_shot_cell(row, [
        "Video Content (CN)", "video_content_cn", "video_prompt_cn", "视频内容（中文）",
        "中文视频提示词内容", "中文视频提示词", "视频提示词内容", "视频提示词", "中文动态视频提示词",
        "Prompt (CN)", "Prompts (CN)", "Prompt CN", "prompt_cn", "提示词（中文）", "中文提示词",
        "Video Content", "video_content", "视频内容",
        "prompt_preview_cn",
    ], "")
    if direct_value:
        return direct_value

    for source in (row, _shot_row_technical_notes_dict(row)):
        if not isinstance(source, dict):
            continue
        for raw_key, raw_value in source.items():
            value = str(raw_value or "").strip()
            if not value:
                continue
            key_text = str(raw_key or "").strip().lower()
            normalized_key = _normalize_shot_markdown_col_key(raw_key)
            if (
                ("video" in key_text and "cn" in key_text)
                or "videopromptcn" in normalized_key
                or "videocontentcn" in normalized_key
                or ("视频" in str(raw_key or "") and ("中文" in str(raw_key or "") or "提示词" in str(raw_key or "") or "内容" in str(raw_key or "")))
            ):
                return value
    return ""


def _collect_missing_shot_required_fields(row: Dict[str, Any]) -> List[str]:
    missing_fields: List[str] = []
    for label, aliases in _SHOT_REQUIRED_ROW_FIELDS:
        if not _pick_shot_cell(row, aliases, ""):
            missing_fields.append(label)
    for label, aliases in _SHOT_REQUIRED_ROW_FIELD_GROUPS:
        if label == "Video Content or Video Content (CN)":
            if not _pick_shot_video_prompt_cell(row):
                missing_fields.append(label)
            continue
        if not _pick_shot_cell(row, aliases, ""):
            missing_fields.append(label)
    return missing_fields


def _normalize_shot_business_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"(?i)^shot\s*", "", text)
    return text.strip().upper()


def _extract_shot_row_business_id(row: Dict[str, Any], *, fallback_index: Optional[int] = None) -> str:
    shot_id = _pick_shot_cell(row, ["Shot ID", "shot_id", "镜头ID"], "")
    normalized = _normalize_shot_business_id(shot_id)
    if normalized:
        return normalized
    if fallback_index is not None:
        return f"__row_{int(fallback_index)}"
    return ""


def _shot_record_db_id(shot: Any) -> int:
    if isinstance(shot, dict):
        try:
            return int(shot.get("id") or 0)
        except Exception:
            return 0
    try:
        return int(getattr(shot, "id", 0) or 0)
    except Exception:
        return 0


def _shot_record_scene_id(shot: Any) -> int:
    if isinstance(shot, dict):
        try:
            return int(shot.get("scene_id") or 0)
        except Exception:
            return 0
    try:
        return int(getattr(shot, "scene_id", 0) or 0)
    except Exception:
        return 0


def _shot_record_business_key(shot: Any) -> str:
    scene_id = _shot_record_scene_id(shot)
    if isinstance(shot, dict):
        business_id = _normalize_shot_business_id(shot.get("shot_id"))
    else:
        business_id = _normalize_shot_business_id(getattr(shot, "shot_id", ""))
    if not business_id:
        return f"{scene_id}::__db_{_shot_record_db_id(shot)}"
    return f"{scene_id}::{business_id}"


def _dedupe_shot_rows_for_import(
    rows: List[Dict[str, Any]],
    *,
    scene_id: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    deduped: List[Dict[str, Any]] = []
    index_by_key: Dict[str, int] = {}
    warnings: List[str] = []
    stable_scene_id = int(scene_id or 0)

    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        business_id = _extract_shot_row_business_id(row, fallback_index=idx)
        dedup_key = f"{stable_scene_id}::{business_id}"
        if dedup_key in index_by_key:
            prev_idx = index_by_key[dedup_key]
            warnings.append(
                f"duplicate Shot ID '{business_id}' at rows {prev_idx} and {idx}; kept row {idx}"
            )
            deduped[index_by_key[dedup_key] - 1] = row
            continue
        index_by_key[dedup_key] = len(deduped) + 1
        deduped.append(row)

    return deduped, warnings


def _dedupe_active_shot_records_for_display(shots: List[Any]) -> List[Any]:
    if not shots:
        return []
    ordered_keys: List[str] = []
    best_by_key: Dict[str, Any] = {}
    for shot in shots:
        key = _shot_record_business_key(shot)
        if key not in best_by_key:
            ordered_keys.append(key)
        existing = best_by_key.get(key)
        if existing is None or _shot_record_db_id(shot) >= _shot_record_db_id(existing):
            best_by_key[key] = shot
    return [best_by_key[key] for key in ordered_keys if key in best_by_key]


def _soft_delete_duplicate_active_shots_in_db(
    db: Session,
    *,
    scene_id: Optional[int] = None,
    episode_id: Optional[int] = None,
    project_id: Optional[int] = None,
    scope: str = "scene",
) -> int:
    """Soft-delete duplicate active shots.

    scope=scene: key = scene_id::shot_id (legacy per-scene dedupe)
    scope=episode: key = project_id::episode_id::shot_id (matches unique index)
    """
    filters = [_active_shot_clause()]
    if scene_id is not None:
        filters.append(Shot.scene_id == int(scene_id))
    if episode_id is not None:
        filters.append(Shot.episode_id == int(episode_id))
    if project_id is not None:
        filters.append(Shot.project_id == int(project_id))

    shots = db.query(Shot).filter(*filters).order_by(Shot.id.asc()).all()
    if not shots:
        return 0

    use_episode_scope = str(scope or "scene").strip().lower() == "episode"
    grouped: Dict[str, List[Shot]] = {}
    for shot in shots:
        business_id = _normalize_shot_business_id(getattr(shot, "shot_id", ""))
        if not business_id:
            continue
        if use_episode_scope:
            key = (
                f"{int(getattr(shot, 'project_id', 0) or 0)}::"
                f"{int(getattr(shot, 'episode_id', 0) or 0)}::{business_id}"
            )
        else:
            key = f"{int(getattr(shot, 'scene_id', 0) or 0)}::{business_id}"
        grouped.setdefault(key, []).append(shot)

    duplicate_ids: List[int] = []
    for group in grouped.values():
        if len(group) <= 1:
            continue
        group.sort(key=lambda item: int(getattr(item, "id", 0) or 0))
        duplicate_ids.extend(int(item.id) for item in group[:-1])

    if not duplicate_ids:
        return 0

    now = now_bj_iso()
    db.query(Shot).filter(Shot.id.in_(duplicate_ids)).update(
        {Shot.is_deleted: True, Shot.deleted_at: now},
        synchronize_session=False,
    )
    logger.info(
        "[shot_import.dedup] soft_deleted duplicate active shots count=%s scene_id=%s episode_id=%s project_id=%s scope=%s",
        len(duplicate_ids),
        scene_id,
        episode_id,
        project_id,
        "episode" if use_episode_scope else "scene",
    )
    return len(duplicate_ids)


def _find_active_shot_by_business_id(
    db: Session,
    *,
    project_id: int,
    episode_id: int,
    shot_id: Any,
    exclude_scene_id: Optional[int] = None,
) -> Optional[Shot]:
    business_id = _normalize_shot_business_id(shot_id)
    if not business_id:
        return None
    rows = (
        db.query(Shot)
        .filter(
            Shot.project_id == int(project_id),
            Shot.episode_id == int(episode_id),
            _active_shot_clause(),
        )
        .all()
    )
    for row in rows:
        if exclude_scene_id is not None and int(getattr(row, "scene_id", 0) or 0) == int(exclude_scene_id):
            continue
        if _normalize_shot_business_id(getattr(row, "shot_id", "")) == business_id:
            return row
    return None


def _escape_shot_markdown_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("|", "\\|")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    return text


def _collect_shot_markdown_headers(rows: List[Dict[str, Any]]) -> List[str]:
    discovered_headers: List[str] = []
    discovered_set = set()
    for item in rows:
        if not isinstance(item, dict):
            continue
        for key in item.keys():
            normalized_key = str(key or "").strip()
            if not normalized_key or normalized_key in discovered_set:
                continue
            discovered_set.add(normalized_key)
            discovered_headers.append(normalized_key)

    if not discovered_headers:
        return list(_SHOT_MARKDOWN_DEFAULT_HEADERS)

    headers: List[str] = [h for h in _SHOT_MARKDOWN_DEFAULT_HEADERS if h in discovered_set]
    headers.extend([h for h in discovered_headers if h not in headers])
    return headers


def _serialize_shot_rows_to_markdown(rows: List[Dict[str, Any]]) -> str:
    headers = _collect_shot_markdown_headers(rows)
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join([":---"] * len(headers)) + " |"
    body_lines = []
    for item in rows:
        row_values = [_escape_shot_markdown_cell(item.get(header, "")) for header in headers]
        body_lines.append("| " + " | ".join(row_values) + " |")
    return "\n".join([header_line, separator_line] + body_lines)


def _coerce_shot_row_duration_or_default(row: Dict[str, Any], *, default: float = 2.0) -> Tuple[bool, Optional[str]]:
    """Normalize Duration (s) in-place.

    Import already defaults missing/invalid duration to 2.0; validation must match
    that behavior so apply does not reject rows the importer would accept.
    Returns (changed, warning_or_none).
    """
    if not isinstance(row, dict):
        return False, None
    raw_duration = _pick_shot_cell(row, ["Duration (s)", "Duration", "duration", "时长", "时长(s)"], "")
    duration_ok = False
    parsed: Optional[float] = None
    if raw_duration:
        match = re.search(r"[\d\.]+", str(raw_duration))
        if match:
            try:
                parsed = float(match.group())
                duration_ok = parsed > 0
            except Exception:
                duration_ok = False
    if duration_ok and parsed is not None:
        # Keep original cell text when already valid.
        return False, None

    # Prefer writing the canonical English header used by the shot table schema.
    duration_key = "Duration (s)"
    for key in ("Duration (s)", "Duration", "duration", "时长", "时长(s)"):
        if key in row:
            duration_key = key
            break
    row[duration_key] = str(default)
    warning = (
        f"Duration (s) missing/invalid ({raw_duration or 'empty'}); defaulted to {default}"
        if raw_duration
        else f"Duration (s) missing; defaulted to {default}"
    )
    return True, warning


def _validate_shot_rows_or_raise(
    content: Any,
    *,
    source_label: str,
    status_code: int = 400,
) -> List[Dict[str, Any]]:
    if not isinstance(content, list):
        raise HTTPException(status_code=status_code, detail=f"{source_label} must be a non-empty shot row list")

    normalized_rows: List[Dict[str, Any]] = []
    for idx, item in enumerate(content, start=1):
        if not isinstance(item, dict):
            raise HTTPException(status_code=status_code, detail=f"{source_label} row {idx} is not an object")
        if not any(str(val or "").strip() for val in item.values()):
            continue
        normalized_rows.append(item)

    if not normalized_rows:
        raise HTTPException(status_code=status_code, detail=f"{source_label} did not contain any non-empty shot rows")

    row_errors: List[str] = []
    for idx, row in enumerate(normalized_rows, start=1):
        _coerce_shot_row_duration_or_default(row)
        _coerce_shot_row_associated_entities_or_default(row)
        missing_fields = _collect_missing_shot_required_fields(row)

        if missing_fields:
            row_errors.append(f"row {idx} missing/invalid: {', '.join(missing_fields)}")

    if row_errors:
        detail = "; ".join(row_errors[:5])
        if len(row_errors) > 5:
            detail += f"; and {len(row_errors) - 5} more rows"
        raise HTTPException(status_code=status_code, detail=f"{source_label} failed structural validation: {detail}")

    deduped_rows, _ = _dedupe_shot_rows_for_import(normalized_rows)
    return deduped_rows


def _validate_shot_rows_for_apply_with_tolerance(
    content: Any,
    *,
    source_label: str,
    status_code: int = 400,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    if not isinstance(content, list):
        raise HTTPException(status_code=status_code, detail=f"{source_label} must be a non-empty shot row list")

    normalized_rows: List[Dict[str, Any]] = []
    skipped_errors: List[str] = []
    for idx, item in enumerate(content, start=1):
        if not isinstance(item, dict):
            skipped_errors.append(f"row {idx} is not an object")
            continue
        if not any(str(val or "").strip() for val in item.values()):
            continue

        if _is_placeholder_shot_row(item):
            shot_id = _pick_shot_cell(item, ["Shot ID", "shot_id", "镜头ID"], "") or "(blank)"
            skipped_errors.append(
                f"row {idx}: skipped placeholder/template Shot ID '{shot_id}'"
            )
            continue

        _, duration_warning = _coerce_shot_row_duration_or_default(item)
        if duration_warning:
            skipped_errors.append(f"row {idx}: {duration_warning}")
        _, entities_warning = _coerce_shot_row_associated_entities_or_default(item)
        if entities_warning:
            skipped_errors.append(f"row {idx}: {entities_warning}")

        missing_fields = _collect_missing_shot_required_fields(item)

        if missing_fields:
            skipped_errors.append(f"row {idx} missing/invalid: {', '.join(missing_fields)}")
            continue

        normalized_rows.append(item)

    if not normalized_rows:
        detail = "; ".join(skipped_errors[:5]) if skipped_errors else "no non-empty shot rows"
        if len(skipped_errors) > 5:
            detail += f"; and {len(skipped_errors) - 5} more rows"
        raise HTTPException(status_code=status_code, detail=f"{source_label} failed structural validation: {detail}")

    deduped_rows, dedupe_warnings = _dedupe_shot_rows_for_import(normalized_rows)
    for warning in dedupe_warnings:
        skipped_errors.append(f"dedupe: {warning}")

    return deduped_rows, skipped_errors


def _resolve_shots_data_for_apply(
    scene: Scene,
    provided_content: Any,
    *,
    source_label: str,
    status_code: int = 400,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Prefer freshly parsed stored markdown over stale provided staging rows."""
    markdown_rows: List[Dict[str, Any]] = []
    markdown_skipped: List[str] = []
    markdown_error: Optional[str] = None
    raw_value = str(getattr(scene, "ai_shots_result", None) or "").strip()

    if raw_value.startswith("{"):
        try:
            legacy = json.loads(raw_value)
            if isinstance(legacy, dict) and legacy.get("raw_text"):
                raw_value = str(legacy.get("raw_text") or "").strip()
        except Exception:
            pass

    if raw_value:
        try:
            _, parsed_rows, _ = _parse_shot_markdown_or_raise(
                raw_value,
                source_label=f"{source_label} (stored markdown)",
                status_code=status_code,
            )
            markdown_rows, markdown_skipped = _validate_shot_rows_for_apply_with_tolerance(
                parsed_rows,
                source_label=f"{source_label} (stored markdown)",
                status_code=status_code,
            )
        except HTTPException as exc:
            markdown_rows = []
            markdown_skipped = []
            markdown_error = str(getattr(exc, "detail", None) or exc)

    provided_rows: List[Dict[str, Any]] = []
    provided_skipped: List[str] = []
    provided_error: Optional[str] = None
    if provided_content is not None:
        try:
            provided_rows, provided_skipped = _validate_shot_rows_for_apply_with_tolerance(
                provided_content,
                source_label=f"{source_label} (provided content)",
                status_code=status_code,
            )
        except HTTPException as exc:
            provided_rows = []
            provided_skipped = []
            provided_error = str(getattr(exc, "detail", None) or exc)

    if markdown_rows and not provided_rows:
        return markdown_rows, markdown_skipped
    if provided_rows and not markdown_rows:
        return provided_rows, provided_skipped
    if len(markdown_rows) > len(provided_rows):
        logger.info(
            "[apply_scene_ai_result] prefer stored markdown rows over provided content | markdown=%s provided=%s",
            len(markdown_rows),
            len(provided_rows),
        )
        return markdown_rows, markdown_skipped
    if len(provided_rows) > len(markdown_rows):
        return provided_rows, provided_skipped
    if markdown_rows:
        return markdown_rows, markdown_skipped

    # Both sources empty: surface the real structural validation failure instead of
    # collapsing into a generic "No shot rows" message.
    error_parts = [part for part in (markdown_error, provided_error) if part]
    if error_parts:
        detail = " | ".join(dict.fromkeys(error_parts))
        logger.warning(
            "[apply_scene_ai_result] no valid rows after validation | source=%s detail=%s",
            source_label,
            detail[:800],
        )
        raise HTTPException(status_code=status_code, detail=detail)

    return provided_rows, provided_skipped


def _parse_shot_markdown_or_raise(
    markdown_text: str,
    *,
    source_label: str,
    status_code: int = 400,
) -> Tuple[List[str], List[Dict[str, str]], int]:
    headers, rows, table_line_count = parse_shots_markdown_table(markdown_text or "")
    if not rows:
        raise HTTPException(status_code=status_code, detail=f"{source_label} did not produce a parseable markdown table")
    if table_line_count >= 4 and len(rows) > 0 and (len(rows) * 2) <= table_line_count:
        raise HTTPException(
            status_code=status_code,
            detail=f"{source_label} lost rows during markdown parsing; fix the table before continuing",
        )
    return headers, rows, table_line_count


def _validate_shot_rows_roundtrip_or_raise(
    content: Any,
    *,
    source_label: str,
    status_code: int = 400,
) -> Tuple[List[Dict[str, Any]], str]:
    rows = _validate_shot_rows_or_raise(content, source_label=source_label, status_code=status_code)
    markdown_text = _serialize_shot_rows_to_markdown(rows)
    _, reparsed_rows, _ = _parse_shot_markdown_or_raise(markdown_text, source_label=source_label, status_code=status_code)
    if len(reparsed_rows) != len(rows):
        raise HTTPException(
            status_code=status_code,
            detail=(
                f"{source_label} changed row count after markdown round-trip "
                f"({len(rows)} -> {len(reparsed_rows)}); fix pipe escaping or multiline cells before continuing"
            ),
        )
    return rows, markdown_text


def is_valid_markdown_output(text: str, require_h1: bool = True) -> bool:
    if not text:
        return False

    content = str(text).strip()
    if not content:
        return False

    lower = content.lower()
    if "<think>" in lower or "```" in content:
        return False

    lines = [ln for ln in content.splitlines() if ln.strip()]
    if not lines:
        return False

    first = lines[0].lstrip()
    # Story DNA contract: machine title marker may lead the deliverable block.
    has_script_title_marker = bool(re.match(r"^\[\s*SCRIPT_TITLE\s*[：:]", first, flags=re.IGNORECASE))
    if require_h1 and not first.startswith("#") and not has_script_title_marker:
        return False

    # Basic markdown structure presence
    has_md_structure = any(
        ln.lstrip().startswith(("#", "- ", "* ", "|", ">", "1. ", "2. ", "3. "))
        or bool(re.match(r"^\[\s*SCRIPT_TITLE\s*[：:]", ln.lstrip(), flags=re.IGNORECASE))
        or bool(re.match(r"^\[\s*EPISODE_BLOCK_START", ln.lstrip(), flags=re.IGNORECASE))
        for ln in lines
    )
    return has_md_structure


def _parse_episode_heading_from_markdown(text: str) -> Dict[str, Any]:
    content = str(text or "").strip()
    if not content:
        return {}

    non_empty_lines: List[str] = []
    first_line = ""
    for line in content.splitlines():
        candidate = str(line or "").strip()
        if candidate:
            non_empty_lines.append(candidate)
            if not first_line:
                first_line = candidate

    if not first_line:
        return {}

    has_markdown_h1 = first_line.startswith("#")
    second_line = non_empty_lines[1] if len(non_empty_lines) > 1 else ""
    looks_like_episode_heading = bool(
        re.match(r"^(?:#\s*)?(?:(?:EP(?:ISODE)?\s*)?0*\d+|第\s*\d+\s*[集话章回]|0*\d+)(?:\s*[-:：|｜]\s*|\s+).+$", first_line, flags=re.IGNORECASE)
    )
    looks_like_script_structure = bool(
        second_line and re.match(r"^(?:##\s*)?-?1\)|^##\s+Logline\b|^##\s+Scenes\b|^##\s+Ending Hook\b", second_line, flags=re.IGNORECASE)
    )
    if not has_markdown_h1 and not (looks_like_episode_heading and looks_like_script_structure):
        return {}

    heading = first_line.lstrip("#").strip()
    if not heading:
        return {"raw_heading": first_line}

    heading = re.sub(r"^[`*_~\s]+|[`*_~\s]+$", "", heading).strip()

    patterns = (
        r"^(?:EP(?:ISODE)?\s*)?0*(\d+)\s*[-:：|｜]\s*(.+)$",
        r"^第\s*(\d+)\s*[集话章回]\s*[-:：|｜]\s*(.+)$",
        r"^(?:EP(?:ISODE)?\s*)?0*(\d+)\s+(.+)$",
        r"^第\s*(\d+)\s*[集话章回]\s+(.+)$",
        r"^0*(\d+)\s*[-:：|｜]\s*(.+)$",
        r"^0*(\d+)\s+(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, heading, flags=re.IGNORECASE)
        if not match:
            continue
        try:
            episode_number = int(match.group(1))
        except Exception:
            episode_number = None
        episode_title = str(match.group(2) or "").strip().strip("-:： ")
        return {
            "raw_heading": first_line,
            "episode_number": episode_number,
            "episode_title": episode_title,
        }

    return {
        "raw_heading": first_line,
        "episode_title": heading,
    }


async def generate_markdown_with_retry(
    user_prompt: str,
    sys_prompt: str,
    llm_config: Optional[Dict[str, Any]],
    strict_markdown: bool = True,
    require_h1: bool = True,
    return_meta: bool = False,
) -> Any:
    def _is_prohibited_marker(text: str) -> bool:
        if not text:
            return False
        t = text.strip().upper()
        t = t.lstrip("=").strip()
        return t == "PROHIBITED_CONTENT"

    def _looks_like_error_text(text: str) -> bool:
        if not text:
            return False
        t = text.strip().lower()
        return (
            t.startswith("error:")
            or "api error" in t
            or "no llm configuration" in t
            or "please configure your llm api key" in t
            or "prohibited_content" in t
        )

    async def _call_once(tag: str, up: str, sp: str) -> Tuple[str, str, Dict[str, Any]]:
        resp = await llm_service.generate_content_with_fallback(up, sp, llm_config)
        raw = str(resp.get("content") or "")
        cleaned = sanitize_llm_markdown_output(raw)
        finish_reason = str(resp.get("finish_reason") or "")
        usage = resp.get("usage") or {}
        routing_meta = _extract_llm_routing_metadata(resp)
        logger.info(
            f"[generate_markdown_with_retry] tag={tag} raw_len={len(raw)} clean_len={len(cleaned)} "
            f"finish_reason={finish_reason or '-'} usage={usage} is_error_like={_looks_like_error_text(cleaned)}"
        )
        return raw, cleaned, {
            "tag": tag,
            "finish_reason": finish_reason,
            "usage": usage,
            "routing_metadata": routing_meta,
            "raw_len": len(raw),
            "clean_len": len(cleaned),
        }

    def _result_payload(content: str, meta: Optional[Dict[str, Any]]) -> Any:
        if not return_meta:
            return content
        return {
            "content": content,
            "usage": ((meta or {}).get("usage") if isinstance(meta, dict) else {}) or {},
            "routing_metadata": ((meta or {}).get("routing_metadata") if isinstance(meta, dict) else {}) or {},
            "finish_reason": ((meta or {}).get("finish_reason") if isinstance(meta, dict) else None),
        }

    def _is_truncated(meta: Optional[Dict[str, Any]]) -> bool:
        reason = str((meta or {}).get("finish_reason") or "").strip().lower()
        return reason == "length"

    def _validation_view(content: str, tag: str) -> str:
        """Prefer STORY_DNA_OUTPUT (truncate THINKING) so reasoning cannot fail validation."""
        info = extract_story_dna_output_for_validation(content)
        view = str(info.get("content") or content or "").strip()
        if info.get("had_output_markers") or info.get("truncated_thinking") or info.get("output_source"):
            logger.info(
                "[generate_markdown_with_retry] story_dna_truncate tag=%s "
                "had_output=%s had_thinking=%s truncated_thinking=%s "
                "output_source=%s output_score=%s "
                "full_len=%s validate_len=%s thinking_len=%s",
                tag,
                bool(info.get("had_output_markers")),
                bool(info.get("had_thinking_markers")),
                bool(info.get("truncated_thinking")),
                info.get("output_source"),
                info.get("output_score"),
                len(str(info.get("full") or "")),
                len(view),
                len(str(info.get("thinking") or "")),
            )
        return view

    def _passes_markdown(content: str, tag: str) -> bool:
        if not content or _looks_like_error_text(content):
            return False
        # Story DNA hard rule: both OUTPUT_START and OUTPUT_END → middle slice passes.
        if is_acceptable_story_dna_markdown(content):
            view = _validation_view(content, tag)
            logger.info(
                "[generate_markdown_with_retry] story_dna_output_markers_accept tag=%s "
                "view_len=%s full_len=%s",
                tag,
                len(view),
                len(content),
            )
            return True
        view = _validation_view(content, tag)
        if is_valid_markdown_output(view, require_h1=require_h1):
            return True
        if is_acceptable_story_dna_markdown(view):
            logger.info(
                "[generate_markdown_with_retry] story_dna_lenient_accept tag=%s "
                "view_len=%s full_len=%s require_h1=%s",
                tag,
                len(view),
                len(content),
                require_h1,
            )
            return True
        return False

    raw_1, content_1, meta_1 = await _call_once("initial", user_prompt, sys_prompt)
    if _is_prohibited_marker(raw_1) or _is_prohibited_marker(content_1):
        logger.error("[generate_markdown_with_retry] provider returned PROHIBITED_CONTENT on initial attempt")
        raise RuntimeError("LLM content blocked by provider (PROHIBITED_CONTENT)")
    if _looks_like_error_text(content_1):
        lowered = (content_1 or "").strip().lower()
        if "please configure your llm api key" in lowered or "no llm configuration" in lowered:
            raise RuntimeError("No valid LLM API key configured in active settings")

    if not strict_markdown:
        if _is_truncated(meta_1):
            raise RuntimeError("LLM output appears truncated (finish_reason=length) in non-strict mode")
        if content_1 and not _looks_like_error_text(content_1):
            return _result_payload(content_1, meta_1)
        raise RuntimeError("LLM returned empty/error content in non-strict mode")

    if content_1 and _passes_markdown(content_1, "initial") and not _is_truncated(meta_1):
        return _result_payload(content_1, meta_1)

    retry_sys_prompt = (
        f"{sys_prompt}\n\n"
        "[FORMAT RETRY - STRICT]\n"
        "Return ONLY final valid Markdown.\n"
        "Do NOT output reasoning, preface text, or chain-of-thought outside truncatable markers.\n"
        "Do NOT output code fences.\n"
        "If this is Story DNA: wrap Part 1 in [STORY_DNA_THINKING_START]/[STORY_DNA_THINKING_END], "
        "and wrap §0–§9 (including [SCRIPT_TITLE:…]) in [STORY_DNA_OUTPUT_START]/[STORY_DNA_OUTPUT_END]. "
        "OUTPUT block first non-empty line must be [SCRIPT_TITLE:…] or a markdown header starting with '# '.\n"
        "Otherwise: the first non-empty line must be an H1 markdown header starting with '# '."
    )
    retry_user_prompt = (
        f"{user_prompt}\n\n"
        "[RETRY INSTRUCTION]\n"
        "Only return corrected final markdown now. Put any reasoning inside THINKING markers; "
        "formal deliverable must be inside OUTPUT markers when Story DNA applies."
    )
    raw_2, content_2, meta_2 = await _call_once("strict_retry", retry_user_prompt, retry_sys_prompt)
    if _is_prohibited_marker(raw_2) or _is_prohibited_marker(content_2):
        logger.error("[generate_markdown_with_retry] provider returned PROHIBITED_CONTENT on strict retry")
        raise RuntimeError("LLM content blocked by provider (PROHIBITED_CONTENT)")
    if content_2 and _passes_markdown(content_2, "strict_retry") and not _is_truncated(meta_2):
        return _result_payload(content_2, meta_2)

    final_retry_sys_prompt = (
        f"{sys_prompt}\n\n"
        "[FINAL RETRY - STRICT MARKDOWN ONLY]\n"
        "Return ONLY complete final markdown that fully satisfies the requested structure.\n"
        "Do NOT output a partial draft.\n"
        "Do NOT output placeholder sections.\n"
        "Do NOT output reasoning, analysis text, or code fences outside truncatable markers.\n"
        "If this is Story DNA: include [STORY_DNA_THINKING_START]/[STORY_DNA_THINKING_END] and "
        "[STORY_DNA_OUTPUT_START]/[STORY_DNA_OUTPUT_END]; OUTPUT must begin with [SCRIPT_TITLE:…] "
        "or a markdown header starting with '# '.\n"
        "Otherwise: the first non-empty line must be an H1 markdown header starting with '# '."
    )
    final_retry_user_prompt = (
        f"{user_prompt}\n\n"
        "[FINAL STRICT RETRY]\n"
        "Return only the fully valid final markdown now. If you cannot satisfy the required structure, do not emit a partial draft."
    )
    raw_3, content_3, meta_3 = await _call_once("final_strict_retry", final_retry_user_prompt, final_retry_sys_prompt)
    if _is_prohibited_marker(raw_3) or _is_prohibited_marker(content_3):
        logger.error("[generate_markdown_with_retry] provider returned PROHIBITED_CONTENT on final strict retry")
        raise RuntimeError("LLM content blocked by provider (PROHIBITED_CONTENT)")
    if content_3 and _passes_markdown(content_3, "final_strict_retry") and not _is_truncated(meta_3):
        return _result_payload(content_3, meta_3)

    diagnostics = {
        "initial_finish_reason": meta_1.get("finish_reason"),
        "strict_retry_finish_reason": meta_2.get("finish_reason"),
        "final_strict_retry_finish_reason": meta_3.get("finish_reason"),
        "initial_usage": meta_1.get("usage"),
        "strict_retry_usage": meta_2.get("usage"),
        "final_strict_retry_usage": meta_3.get("usage"),
        "initial_clean_len": len(content_1 or ""),
        "strict_retry_clean_len": len(content_2 or ""),
        "final_strict_retry_clean_len": len(content_3 or ""),
        "initial_error_like": _looks_like_error_text(content_1),
        "strict_retry_error_like": _looks_like_error_text(content_2),
        "final_strict_retry_error_like": _looks_like_error_text(content_3),
        "initial_raw_sample": (raw_1 or "")[:120],
        "strict_retry_raw_sample": (raw_2 or "")[:120],
        "final_strict_retry_raw_sample": (raw_3 or "")[:120],
    }
    logger.error(f"[generate_markdown_with_retry] exhausted retries. {json.dumps(diagnostics, ensure_ascii=False)}")
    if _is_truncated(meta_1) or _is_truncated(meta_2) or _is_truncated(meta_3):
        raise RuntimeError("LLM output appears truncated (finish_reason=length). Check model max_tokens/context and retry.")
    raise RuntimeError("LLM returned empty/invalid content after retries")

@router.post("/projects/", response_model=ProjectOut)
def create_project(
    project: ProjectCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not project.global_info:
        project.global_info = {}

    description = (project.description or "").strip()
    if description:
        project.global_info["notes"] = description

    # If aspectRatio is provided, merge it into global_info
    if project.aspectRatio:
        project.global_info['aspectRatio'] = project.aspectRatio

    project.global_info = _ensure_project_generation_defaults(project.global_info)
        
    db_project = Project(title=project.title, global_info=project.global_info, owner_id=current_user.id) 
    try:
        db.add(db_project)
        db.flush()
        _sync_project_managed_shares(
            db,
            db_project,
            current_user,
            share_users=project.share_users,
            reviewer_users=project.reviewer_users,
        )
        try:
            _recompute_and_persist_project_cost_estimation(db, int(db_project.id))
        except Exception as cost_exc:
            logger.warning("create_project cost recompute skipped | project_id=%s err=%s", getattr(db_project, "id", None), cost_exc)
        db.commit()
    except SQLAlchemyTimeoutError:
        db.rollback()
        logger.warning(
            "create_project DB pool timeout | user_id=%s title=%s",
            current_user.id,
            (project.title or "")[:80],
        )
        raise HTTPException(
            status_code=503,
            detail="数据库连接繁忙，请稍后重试",
        )
    db.refresh(db_project)
    # New project has no images
    db_project.cover_image = None
    # Extract aspectRatio for response from global_info
    db_project.aspectRatio = db_project.global_info.get('aspectRatio') if db_project.global_info else None
    db_project.description = (db_project.global_info or {}).get("notes")
    db_project.is_owner = True
    return db_project


@router.get("/projects/{project_id}/shares", response_model=List[ProjectShareOut])
def list_project_shares(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user, owner_only=True)
    rows = _run_with_schema_self_heal(
        db,
        lambda: (
            db.query(ProjectShare, User)
            .join(User, User.id == ProjectShare.user_id)
            .filter(ProjectShare.project_id == project_id)
            .order_by(ProjectShare.id.desc())
            .all()
        ),
        context="project_share.list",
    )
    return [
        _serialize_project_share(share, user)
        for share, user in rows
    ]


@router.post("/projects/{project_id}/shares", response_model=ProjectShareOut)
def create_project_share(
    project_id: int,
    payload: ProjectShareCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user, owner_only=True)
    target = str(payload.target_user or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="target_user is required")

    role = _normalize_project_share_role(payload.role, strict=True)
    permissions = _normalize_project_share_permissions(payload.permissions)

    target_user = db.query(User).filter(or_(User.username == target, User.email == target)).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    project = db.query(Project).filter(Project.id == project_id).first()
    if project and project.owner_id == target_user.id:
        raise HTTPException(status_code=400, detail="Project owner already has access")

    existing = _get_project_share_record(db, project_id, target_user.id)
    if existing:
        _apply_project_share_access_fields(existing, role, permissions)
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return _serialize_project_share(existing, target_user)

    share = _build_project_share(project_id, target_user.id, role, permissions)
    db.add(share)
    db.commit()
    db.refresh(share)
    return _serialize_project_share(share, target_user)


@router.delete("/projects/{project_id}/shares/{shared_user_id}", status_code=204)
def delete_project_share(
    project_id: int,
    shared_user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user, owner_only=True)
    share = _get_project_share_record(db, project_id, shared_user_id)
    if not share:
        raise HTTPException(status_code=404, detail="Share record not found")
    db.delete(share)
    db.commit()
    return None


@router.get("/projects/{project_id}/review_threads", response_model=List[ProjectAssetReviewThreadOut])
def list_project_review_threads(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    _require_project_access(db, project_id, current_user)
    threads = _run_with_schema_self_heal(
        db,
        lambda: (
            db.query(ProjectAssetReviewThread)
            .filter(ProjectAssetReviewThread.project_id == project_id)
            .order_by(ProjectAssetReviewThread.latest_activity_at.desc(), ProjectAssetReviewThread.id.desc())
            .all()
        ),
        context="review_thread.list_project",
    )
    user_ids = {thread.requester_user_id for thread in threads} | {thread.reviewer_user_id for thread in threads}
    users = {user.id: user for user in db.query(User).filter(User.id.in_(list(user_ids))).all()} if user_ids else {}
    return [
        _serialize_review_thread(thread, requester=users.get(thread.requester_user_id), reviewer=users.get(thread.reviewer_user_id), current_user=current_user)
        for thread in threads
    ]


@router.get("/projects/review_threads/inbox", response_model=List[ProjectAssetReviewThreadOut])
def list_review_inbox_threads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    threads = _run_with_schema_self_heal(
        db,
        lambda: (
            db.query(ProjectAssetReviewThread)
            .filter(ProjectAssetReviewThread.reviewer_user_id == current_user.id)
            .order_by(ProjectAssetReviewThread.latest_activity_at.desc(), ProjectAssetReviewThread.id.desc())
            .all()
        ),
        context="review_thread.list_inbox",
    )
    user_ids = {thread.requester_user_id for thread in threads} | {thread.reviewer_user_id for thread in threads}
    users = {user.id: user for user in db.query(User).filter(User.id.in_(list(user_ids))).all()} if user_ids else {}
    return [
        _serialize_review_thread(thread, requester=users.get(thread.requester_user_id), reviewer=users.get(thread.reviewer_user_id), current_user=current_user)
        for thread in threads
    ]


@router.get("/projects/review_threads/outbox", response_model=List[ProjectAssetReviewThreadOut])
def list_review_outbox_threads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    threads = _run_with_schema_self_heal(
        db,
        lambda: (
            db.query(ProjectAssetReviewThread)
            .filter(ProjectAssetReviewThread.requester_user_id == current_user.id)
            .order_by(ProjectAssetReviewThread.latest_activity_at.desc(), ProjectAssetReviewThread.id.desc())
            .all()
        ),
        context="review_thread.list_outbox",
    )
    user_ids = {thread.requester_user_id for thread in threads} | {thread.reviewer_user_id for thread in threads}
    users = {user.id: user for user in db.query(User).filter(User.id.in_(list(user_ids))).all()} if user_ids else {}
    return [
        _serialize_review_thread(thread, requester=users.get(thread.requester_user_id), reviewer=users.get(thread.reviewer_user_id), current_user=current_user)
        for thread in threads
    ]


@router.post("/projects/{project_id}/review_threads", response_model=ProjectAssetReviewThreadOut)
def create_project_review_thread(
    project_id: int,
    payload: ProjectAssetReviewThreadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    project = _require_project_access(db, project_id, current_user)
    share = _get_project_share_record(db, project_id, current_user.id)
    if share and _normalize_project_share_role(getattr(share, "role", None)) == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot initiate asset reviews")

    reviewer = _resolve_review_reviewer(
        db,
        project,
        current_user,
        payload.reviewer_user_id,
        payload.reviewer_user,
    )
    scope_type = _normalize_asset_review_scope_type(payload.scope_type)
    entity_required = bool(payload.entity_required)
    shot_required = bool(payload.shot_required)
    _ensure_review_scope_has_dimension(entity_required, shot_required)
    entity_ids, shot_ids = _validate_review_target_ids_for_project(
        db,
        project.id,
        payload.entity_ids or [],
        payload.shot_ids or [],
        scope_type=scope_type,
    )
    now_iso = now_bj_iso()
    thread = ProjectAssetReviewThread(
        project_id=project.id,
        requester_user_id=current_user.id,
        reviewer_user_id=reviewer.id,
        title=(str(payload.title or "").strip() or f"{project.title or 'Project'} 资产审核"),
        status="open",
        latest_round_no=1,
        latest_activity_at=now_iso,
        requester_last_read_at=now_iso,
        reviewer_last_read_at=None,
        updated_at=now_iso,
    )
    db.add(thread)
    db.flush()

    round_row = ProjectAssetReviewRound(
        thread_id=thread.id,
        round_no=1,
        initiated_by_user_id=current_user.id,
        request_message=(str(payload.request_message or "").strip() or None),
        scope_type=scope_type,
        entity_required=entity_required,
        shot_required=shot_required,
        entity_decision="pending",
        shot_decision="pending",
        overall_status="pending_reviewer",
        due_at=(str(payload.due_at or "").strip() or None),
        selected_entity_ids=entity_ids,
        selected_shot_ids=shot_ids,
        updated_at=now_iso,
    )
    db.add(round_row)
    db.flush()

    initial_message = ProjectAssetReviewMessage(
        round_id=round_row.id,
        sender_user_id=current_user.id,
        sender_role="requester",
        message_type="request",
        message_text=(str(payload.request_message or "").strip() or None),
        created_at=now_iso,
    )
    db.add(initial_message)
    db.commit()
    db.refresh(thread)
    return _serialize_review_thread(thread, requester=current_user, reviewer=reviewer, current_user=current_user)


@router.get("/review_threads/{thread_id}", response_model=ProjectAssetReviewThreadOut)
def get_review_thread(
    thread_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    thread, _project = _require_review_thread_access(db, thread_id, current_user)
    users = {
        user.id: user
        for user in db.query(User).filter(User.id.in_([thread.requester_user_id, thread.reviewer_user_id])).all()
    }
    return _serialize_review_thread(thread, requester=users.get(thread.requester_user_id), reviewer=users.get(thread.reviewer_user_id), current_user=current_user)


@router.post("/review_threads/{thread_id}/read", response_model=ProjectAssetReviewThreadOut)
def mark_review_thread_read(
    thread_id: int,
    payload: ProjectAssetReviewThreadReadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    thread, _project = _require_review_thread_access(db, thread_id, current_user)
    if payload.read:
        _mark_review_thread_read_for_user(thread, current_user)
        thread.updated_at = now_bj_iso()
        db.add(thread)
        db.commit()
        db.refresh(thread)
    users = {
        user.id: user
        for user in db.query(User).filter(User.id.in_([thread.requester_user_id, thread.reviewer_user_id])).all()
    }
    return _serialize_review_thread(thread, requester=users.get(thread.requester_user_id), reviewer=users.get(thread.reviewer_user_id), current_user=current_user)


@router.patch("/review_threads/{thread_id}/status", response_model=ProjectAssetReviewThreadOut)
def update_review_thread_status(
    thread_id: int,
    payload: ProjectAssetReviewThreadStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    thread, project = _require_review_thread_access(db, thread_id, current_user)
    next_status = str(payload.status or "").strip().lower()
    if next_status not in _ASSET_REVIEW_THREAD_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid review thread status: {next_status}")
    can_archive = int(current_user.id or 0) in {int(thread.requester_user_id or 0), int(project.owner_id or 0)}
    if next_status == "archived" and not can_archive:
        raise HTTPException(status_code=403, detail="Only requester side can archive review threads")

    now_iso = now_bj_iso()
    thread.status = next_status
    thread.updated_at = now_iso
    thread.latest_activity_at = now_iso
    db.add(thread)

    if next_status == "closed":
        db.query(ProjectAssetReviewRound).filter(
            ProjectAssetReviewRound.thread_id == thread.id,
            ProjectAssetReviewRound.closed_at.is_(None),
        ).update(
            {
                ProjectAssetReviewRound.overall_status: "closed",
                ProjectAssetReviewRound.closed_at: now_iso,
                ProjectAssetReviewRound.updated_at: now_iso,
            },
            synchronize_session=False,
        )

    requester = db.query(User).filter(User.id == thread.requester_user_id).first()
    reviewer = db.query(User).filter(User.id == thread.reviewer_user_id).first()
    db.commit()
    db.refresh(thread)
    return _serialize_review_thread(thread, requester=requester, reviewer=reviewer)


@router.get("/review_threads/{thread_id}/rounds", response_model=List[ProjectAssetReviewRoundOut])
def list_review_thread_rounds(
    thread_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    thread, _project = _require_review_thread_access(db, thread_id, current_user)
    rounds = (
        db.query(ProjectAssetReviewRound)
        .filter(ProjectAssetReviewRound.thread_id == thread.id)
        .order_by(ProjectAssetReviewRound.round_no.asc(), ProjectAssetReviewRound.id.asc())
        .all()
    )
    user_ids = {row.initiated_by_user_id for row in rounds}
    users = {user.id: user for user in db.query(User).filter(User.id.in_(list(user_ids))).all()} if user_ids else {}
    return [_serialize_review_round(row, initiator=users.get(row.initiated_by_user_id)) for row in rounds]


@router.post("/review_threads/{thread_id}/rounds", response_model=ProjectAssetReviewRoundOut)
def create_review_thread_round(
    thread_id: int,
    payload: ProjectAssetReviewRoundCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    thread, project = _require_review_thread_access(db, thread_id, current_user)
    sender_role = _resolve_thread_sender_role(db, thread, current_user, project)
    if sender_role != "requester":
        raise HTTPException(status_code=403, detail="Only requester side can initiate a new review round")

    scope_type = _normalize_asset_review_scope_type(payload.scope_type)
    entity_required = bool(payload.entity_required)
    shot_required = bool(payload.shot_required)
    _ensure_review_scope_has_dimension(entity_required, shot_required)
    entity_ids, shot_ids = _validate_review_target_ids_for_project(
        db,
        project.id,
        payload.entity_ids or [],
        payload.shot_ids or [],
        scope_type=scope_type,
    )
    next_round_no = int(thread.latest_round_no or 0) + 1
    now_iso = now_bj_iso()
    round_row = ProjectAssetReviewRound(
        thread_id=thread.id,
        round_no=next_round_no,
        initiated_by_user_id=current_user.id,
        request_message=(str(payload.request_message or "").strip() or None),
        scope_type=scope_type,
        entity_required=entity_required,
        shot_required=shot_required,
        entity_decision="pending",
        shot_decision="pending",
        overall_status="pending_reviewer",
        due_at=(str(payload.due_at or "").strip() or None),
        selected_entity_ids=entity_ids,
        selected_shot_ids=shot_ids,
        updated_at=now_iso,
    )
    db.add(round_row)
    db.flush()
    db.add(ProjectAssetReviewMessage(
        round_id=round_row.id,
        sender_user_id=current_user.id,
        sender_role="requester",
        message_type="request",
        message_text=(str(payload.request_message or "").strip() or None),
        created_at=now_iso,
    ))
    thread.latest_round_no = next_round_no
    thread.latest_activity_at = now_iso
    _mark_review_thread_read_for_user(thread, current_user, read_at=now_iso)
    thread.updated_at = now_iso
    thread.status = "open"
    db.add(thread)
    db.commit()
    db.refresh(round_row)
    return _serialize_review_round(round_row, initiator=current_user)


@router.get("/review_rounds/{round_id}/messages", response_model=List[ProjectAssetReviewMessageOut])
def list_review_round_messages(
    round_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    round_row, _thread, _project = _require_review_round_access(db, round_id, current_user)
    messages = (
        db.query(ProjectAssetReviewMessage)
        .filter(ProjectAssetReviewMessage.round_id == round_row.id)
        .order_by(ProjectAssetReviewMessage.id.asc())
        .all()
    )
    user_ids = {message.sender_user_id for message in messages}
    users = {user.id: user for user in db.query(User).filter(User.id.in_(list(user_ids))).all()} if user_ids else {}
    return [_serialize_review_message(message, sender=users.get(message.sender_user_id)) for message in messages]


@router.post("/review_rounds/{round_id}/messages", response_model=ProjectAssetReviewMessageOut)
def create_review_round_message(
    round_id: int,
    payload: ProjectAssetReviewMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_review_models()
    round_row, thread, project = _require_review_round_access(db, round_id, current_user)
    sender_role = _resolve_thread_sender_role(db, thread, current_user, project)
    message_type = _normalize_asset_review_message_type(payload.message_type)
    message_text = (str(payload.message_text or "").strip() or None)
    entity_feedback = (str(payload.entity_feedback or "").strip() or None)
    shot_feedback = (str(payload.shot_feedback or "").strip() or None)
    entity_decision = _normalize_asset_review_decision(payload.entity_decision)
    shot_decision = _normalize_asset_review_decision(payload.shot_decision)

    if sender_role != "reviewer" and (entity_decision or shot_decision):
        raise HTTPException(status_code=403, detail="Only reviewer can submit review decisions")
    if sender_role == "reviewer" and message_type == "message" and (entity_decision or shot_decision):
        message_type = "reply"
    if sender_role == "requester" and message_type == "message":
        message_type = "followup"
    if not any([message_text, entity_feedback, shot_feedback, entity_decision, shot_decision]):
        raise HTTPException(status_code=400, detail="Message body or review feedback is required")

    now_iso = now_bj_iso()
    if sender_role == "reviewer":
        if round_row.entity_required and entity_decision:
            round_row.entity_decision = entity_decision
        if round_row.shot_required and shot_decision:
            round_row.shot_decision = shot_decision
        if entity_feedback is not None:
            round_row.entity_feedback = entity_feedback
        if shot_feedback is not None:
            round_row.shot_feedback = shot_feedback
        round_row.overall_status = "replied"
        round_row.closed_at = now_iso if (
            (not round_row.entity_required or round_row.entity_decision != "pending")
            and (not round_row.shot_required or round_row.shot_decision != "pending")
        ) else None
        _mark_review_thread_read_for_user(thread, current_user, read_at=now_iso)
    else:
        round_row.overall_status = "in_discussion" if round_row.overall_status != "pending_reviewer" else round_row.overall_status
        _mark_review_thread_read_for_user(thread, current_user, read_at=now_iso)

    round_row.updated_at = now_iso
    thread.latest_activity_at = now_iso
    thread.updated_at = now_iso
    thread.status = "open"

    message = ProjectAssetReviewMessage(
        round_id=round_row.id,
        sender_user_id=current_user.id,
        sender_role=sender_role,
        message_type=message_type,
        message_text=message_text,
        entity_decision=entity_decision,
        shot_decision=shot_decision,
        entity_feedback=entity_feedback,
        shot_feedback=shot_feedback,
        created_at=now_iso,
    )
    db.add(round_row)
    db.add(thread)
    db.add(message)
    db.commit()
    db.refresh(message)
    return _serialize_review_message(message, sender=current_user)


@router.post("/projects/{project_id}/story_generator/global", response_model=ProjectOut)
async def generate_project_story_dna_global(
    project_id: int,
    req: "StoryGeneratorRequest",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(generate_project_story_dna_global, user_id=current_user.id,
                            kind="story_dna_global", project_id=project_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    project = _require_project_access(db, project_id, current_user)

    gi_existing = dict(project.global_info or {})

    # Force global mode for this endpoint
    episodes_count = req.episodes_count
    if not episodes_count or int(episodes_count) <= 0:
        raise HTTPException(status_code=400, detail="episodes_count is required")

    # Prefer request payload (latest UI state), fall back to saved global_info.
    script_title = (req.script_title or gi_existing.get("script_title") or "").strip()
    project_type = (getattr(req, "type", None) or gi_existing.get("type") or "").strip()
    language = (req.language or gi_existing.get("language") or "").strip()
    base_positioning = (req.base_positioning or gi_existing.get("base_positioning") or "").strip()
    global_style = (req.Global_Style or gi_existing.get("Global_Style") or gi_existing.get("global_style") or "").strip()
    generator_kind = _normalize_generator_kind(req.generator_kind) or "story"

    if generator_kind == "promo":
        prompt_filename = "promo_generator_global.txt"
    else:
        prompt_filename = "master_story_architect.md"

    try:
        sys_prompt = _resolve_prompt_text(prompt_filename)
    except FileNotFoundError:
        logger.error("Story generator prompt not found: %s", prompt_filename)
        raise HTTPException(status_code=404, detail=f"Prompt file '{prompt_filename}' not found.")

    user_id = int(current_user.id)
    project_title = str(project.title or "").strip()
    literal_input_title = script_title or project_title

    title_policy_block = (
        "Script Title Generation Policy (Hard Constraint):\n"
        f"- Project title (reference only, do NOT copy literally): {project_title}\n"
        f"- Input script title hint (reference only): {script_title or '(empty)'}\n"
        "- You MUST create a story-fitting script title based on genre, conflict, and tone.\n"
        "- The final Script Title MUST NOT be identical to the project title or the input hint above.\n"
        "- Avoid generic placeholders like 'Untitled', 'Project Title', or 'Episode N'.\n"
        "- Inside [STORY_DNA_OUTPUT_START]…[STORY_DNA_OUTPUT_END], output a dedicated machine-parseable line: [SCRIPT_TITLE:{title}]\n"
        "- Then also keep the human label: Script Title:{title} · Type:… · Language:…\n"
        "- Do NOT append production-format words (实拍/真人剧/Live Action/Type labels) to the title.\n"
        "- Truncatable markers (hard): wrap Part 1 in [STORY_DNA_THINKING_START]…[STORY_DNA_THINKING_END]; "
        "wrap §0–§9 formal Story DNA in [STORY_DNA_OUTPUT_START]…[STORY_DNA_OUTPUT_END]. "
        "Do not echo the INPUT block into OUTPUT.\n\n"
    )

    user_prompt = wrap_story_dna_input_block(
        f"Mode: global\n"
        f"Project Title: {project_title}\n"
        f"Note: Project Overview / Basic Information and Character Canon may be empty; do not fail, infer sensible defaults and continue.\n"
        f"\n"
        f"{title_policy_block}"
        f"[Project Overview / Basic Information]\n"
        f"Script Title: {script_title}\n"
        f"Type: {project_type}\n"
        f"Language: {language}\n"
        f"Base Positioning: {base_positioning}\n"
        f"Global Style: {global_style}\n"
        f"\n"
        f"Episodes Count: {int(episodes_count)}\n"
        f"Episode Duration (minutes): {_resolve_episode_duration_minutes(getattr(req, 'episode_duration_minutes', None))}\n"
        f"Script Mode: {(getattr(req, 'script_mode', None) or '').strip()}\n"
        f"Target Audience: {(getattr(req, 'target_audience', None) or '').strip()}\n"
        f"\n"
        f"[Creative Input — Standard Structure (脑洞标准输入)]\n"
        f"I1 Logline / 高概念: {(getattr(req, 'logline', None) or '').strip()}\n"
        f"I2 Theme / 主题与主控思想: {(getattr(req, 'theme', None) or '').strip()}\n"
        f"I3 Core Conflict / 核心矛盾·赌注·Gap: {(getattr(req, 'core_conflict', None) or '').strip()}\n"
        f"I4 World & Background / 世界与背景: {(req.background or '').strip()}\n"
        f"I5 Characters & Relationships / 核心人物: {(getattr(req, 'characters', None) or '').strip()}\n"
        f"I6a Opening & Inciting / 开局与激励: {(req.setup or '').strip()}\n"
        f"I6b Mid Arc Escalation / 中段升级: {(req.development or '').strip()}\n"
        f"I6c Turning Points / 转折与中点: {(req.turning_points or '').strip()}\n"
        f"I7a Climax & Must-Have Scenes / 高潮与名场面: {(req.climax or '').strip()}\n"
        f"I7b Ending & Resolution / 结局与收尾: {(req.resolution or '').strip()}\n"
        f"I8a Core Suspense / 核心悬念: {(req.suspense or '').strip()}\n"
        f"I8b Foreshadowing & Must-Keep / 伏笔与必留元素: {(req.foreshadowing or '').strip()}\n"
        f"I9 Raw Fragments / 自由脑洞补充: {(req.extra_notes or '').strip()}\n"
        f"Wild Creative Notes (天马行空原文，保留溯源): {(getattr(req, 'wild_creative_notes', None) or '').strip()}\n"
    )

    llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        user_id,
        function_name=(getattr(req, "function_name", None) or "script_analysis"),
        system_api_id=getattr(req, "system_api_id", None),
        context="generate_project_story_dna_global",
        project_global_info=project.global_info,
    )
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured in active settings")
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None
    reservation_tx = None
    if billing_service.is_token_pricing(db, "llm_chat", provider, model):
        est = billing_service.estimate_reserve_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        reservation_tx = billing_service.reserve_credits(
            db,
            user_id,
            "llm_chat",
            provider,
            model,
            {
                "item": "story_generator_global",
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            },
        )
    else:
        billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

    _release_db_connection(db, "generate_project_story_dna_global_llm_call")

    try:
        # Story DNA: do not strict-retry on H1/marker shape — recover markers on persist instead.
        generated_payload = await generate_markdown_with_retry(
            user_prompt=user_prompt,
            sys_prompt=sys_prompt,
            llm_config=llm_config,
            strict_markdown=False,
            require_h1=False,
            return_meta=True,
        )
    except Exception as e:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(e))
        raise

    generated_md = str((generated_payload or {}).get("content") or "").strip()
    usage = (generated_payload or {}).get("usage") if isinstance(generated_payload, dict) else {}
    if not generated_md:
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    dna_view = extract_story_dna_output_for_validation(generated_md)
    generated_md = normalize_story_dna_markdown_for_persist(generated_md)
    logger.info(
        "[generate_project_story_dna_global] story_dna_markers had_output=%s had_thinking=%s "
        "truncated_thinking=%s persist_len=%s output_len=%s thinking_len=%s",
        bool(dna_view.get("had_output_markers")),
        bool(dna_view.get("had_thinking_markers")),
        bool(dna_view.get("truncated_thinking")),
        len(generated_md),
        len(str(dna_view.get("content") or "")),
        len(str(dna_view.get("thinking") or "")),
    )

    generated_script_title = _strip_stacked_production_title_suffixes(
        _extract_script_title_from_story_dna_markdown(
            str(dna_view.get("content") or generated_md)
        )
    )
    if not generated_script_title:
        generated_script_title = _build_non_literal_script_title(
            seed_title=literal_input_title,
            project_type=project_type,
            global_style=global_style,
            base_positioning=base_positioning,
        )
    literal_input_title_clean = _strip_stacked_production_title_suffixes(literal_input_title)
    if _normalize_title_for_compare(generated_script_title) == _normalize_title_for_compare(literal_input_title_clean):
        generated_script_title = _build_non_literal_script_title(
            seed_title=generated_script_title,
            project_type=project_type,
            global_style=global_style,
            base_positioning=base_positioning,
        )
    generated_script_title = _strip_stacked_production_title_suffixes(generated_script_title)

    if not usage:
        usage = billing_service.estimate_input_output_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": generated_md},
            ],
            output_ratio=1.0,
        )
    settle_details = {
        "item": "promo_generator_global" if generator_kind == "promo" else "story_generator_global",
        "prompt_tokens": int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0),
        "completion_tokens": int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
        "total_tokens": int(
            usage.get(
                "total_tokens",
                int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
                + int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
            )
            or 0
        ),
    }
    settle_details["input_tokens"] = settle_details["prompt_tokens"]
    settle_details["output_tokens"] = settle_details["completion_tokens"]
    _apply_llm_routing_to_billing_details(settle_details, generated_payload)

    if reservation_tx:
        billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), settle_details)
    else:
        billing_service.deduct_credits(db, current_user.id, "llm_chat", provider, model, settle_details)

    # Persist both output and the inputs that produced it.
    # This ensures a successful generation is durable across refresh even
    # if the user doesn't click the separate "Save Changes" button.
    try:
        story_input = req.model_dump()
    except AttributeError:
        story_input = req.dict()
    story_input["mode"] = "global"
    generator_kind = _normalize_generator_kind(story_input.get("generator_kind") or req.generator_kind) or "story"
    story_input["generator_kind"] = generator_kind
    generator_kind = _normalize_generator_kind(story_input.get("generator_kind") or req.generator_kind) or "story"
    story_input["generator_kind"] = generator_kind
    story_input["generator_kind"] = generator_kind

    now_iso = now_bj_iso()
    project = db.merge(project)
    gi = dict(project.global_info or {})
    if generator_kind == "promo":
        gi["promo_generator_input"] = story_input
        gi["promo_generator_input_updated_at"] = now_iso
        gi["promo_dna_global_md"] = generated_md
        gi["promo_dna_global_updated_at"] = now_iso
    else:
        gi["story_generator_global_input"] = story_input
        gi["story_dna_global_md"] = generated_md
        gi["story_dna_global_updated_at"] = now_iso
    if generated_script_title:
        gi["script_title"] = generated_script_title
        basic_info = gi.get("basic_information") if isinstance(gi.get("basic_information"), dict) else {}
        basic_info = dict(basic_info)
        basic_info["script_title"] = generated_script_title
        gi["basic_information"] = basic_info
    project.global_info = gi

    db.add(project)
    db.commit()
    db.refresh(project)

    # Populate response aliases to match other endpoints
    try:
        project.cover_image = get_project_cover_image(db, project.id)
    except Exception:
        project.cover_image = None
    try:
        project.aspectRatio = project.global_info.get('aspectRatio') if project.global_info else None
    except Exception:
        project.aspectRatio = None
    return project


@router.put("/projects/{project_id}/story_generator/global/input", response_model=ProjectOut)
def save_project_story_generator_global_input(
    project_id: int,
    req: "StoryGeneratorRequest",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist Story Generator (Global/Project) draft inputs without calling the LLM."""
    project = _require_project_access(db, project_id, current_user)

    try:
        story_input = req.model_dump()
    except AttributeError:
        story_input = req.dict()
    story_input["mode"] = "global"
    generator_kind = _normalize_generator_kind(story_input.get("generator_kind") or req.generator_kind) or "story"
    story_input["generator_kind"] = generator_kind

    now_iso = now_bj_iso()
    gi = dict(project.global_info or {})
    if generator_kind == "promo":
        gi["promo_generator_input"] = story_input
        gi["promo_generator_input_updated_at"] = now_iso
    else:
        gi["story_generator_global_input"] = story_input
        gi["story_generator_global_input_updated_at"] = now_iso
    project.global_info = gi

    db.add(project)
    db.commit()
    db.refresh(project)

    # Populate response aliases to match other endpoints
    try:
        project.cover_image = get_project_cover_image(db, project.id)
    except Exception:
        project.cover_image = None
    try:
        project.aspectRatio = project.global_info.get('aspectRatio') if project.global_info else None
    except Exception:
        project.aspectRatio = None
    return project


class StoryGeneratorGlobalImportRequest(BaseModel):
    project_overview: Optional[Dict[str, Any]] = None
    basic_information: Optional[Dict[str, Any]] = None
    character_canon_project: Optional[Dict[str, Any]] = None
    story_generator_global_project: Optional[Dict[str, Any]] = None
    story_generator_global_structured: Optional[Dict[str, Any]] = None
    story_generator_global_input: Optional[Dict[str, Any]] = None
    story_dna_global_md: Optional[str] = None


@router.get("/projects/{project_id}/story_generator/global/export", response_model=Dict[str, Any])
def export_project_story_generator_global_package(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)

    gi = dict(project.global_info or {})
    basic_info_nested = gi.get("basic_information") if isinstance(gi.get("basic_information"), dict) else {}
    e_global_info = gi.get("e_global_info") if isinstance(gi.get("e_global_info"), dict) else {}
    story_input = gi.get("story_generator_global_input") if isinstance(gi.get("story_generator_global_input"), dict) else {}

    def _pick_text(*values):
        for v in values:
            if v is None:
                continue
            s = str(v).strip()
            if s:
                return s
        return ""

    def _pick_dict(*values):
        for v in values:
            if isinstance(v, dict) and len(v) > 0:
                return v
        return {}

    def _pick_list(*values):
        for v in values:
            if isinstance(v, list) and len(v) > 0:
                return v
        return []

    basic_information = {
        "script_title": _pick_text(
            gi.get("script_title"),
            basic_info_nested.get("script_title"),
            e_global_info.get("script_title"),
            story_input.get("script_title"),
            _extract_script_title_from_story_dna_markdown(gi.get("story_dna_global_md") or ""),
        ),
        "series_episode": _pick_text(gi.get("series_episode"), basic_info_nested.get("series_episode"), e_global_info.get("series_episode")),
        "type": _pick_text(gi.get("type"), basic_info_nested.get("type"), e_global_info.get("type"), story_input.get("type")),
        "country_region": _pick_text(gi.get("country_region"), basic_info_nested.get("country_region"), e_global_info.get("country_region"), story_input.get("country_region")),
        "language": _pick_text(gi.get("language"), basic_info_nested.get("language"), e_global_info.get("language"), story_input.get("language")),
        "base_positioning": _pick_text(gi.get("base_positioning"), basic_info_nested.get("base_positioning"), e_global_info.get("base_positioning"), story_input.get("base_positioning")),
        "Global_Style": _pick_text(gi.get("Global_Style"), gi.get("global_style"), basic_info_nested.get("Global_Style"), e_global_info.get("Global_Style"), story_input.get("Global_Style")),
        "tech_params": _pick_dict(gi.get("tech_params"), basic_info_nested.get("tech_params"), e_global_info.get("tech_params")),
        "tone": _pick_text(gi.get("tone"), basic_info_nested.get("tone"), e_global_info.get("tone")),
        "lighting": _pick_text(gi.get("lighting"), basic_info_nested.get("lighting"), e_global_info.get("lighting")),
        "borrowed_films": _pick_list(gi.get("borrowed_films"), basic_info_nested.get("borrowed_films"), e_global_info.get("borrowed_films")),
        "character_relationships": _pick_text(gi.get("character_relationships"), basic_info_nested.get("character_relationships")),
        "notes": _pick_text(gi.get("notes"), basic_info_nested.get("notes"), e_global_info.get("notes")),
    }

    character_canon_project = {
        "character_canon_input": gi.get("character_canon_input") or {},
        "character_canon_md": gi.get("character_canon_md") or "",
        "character_profiles": gi.get("character_profiles") or [],
        "character_canon_tag_categories": gi.get("character_canon_tag_categories") or [],
        "character_canon_identity_categories": gi.get("character_canon_identity_categories") or [],
    }

    def _extract_between(text: str, start_pat: str, end_pat: str) -> str:
        try:
            pattern = rf"{start_pat}(.*?){end_pat}"
            m = re.search(pattern, text, flags=re.S)
            return (m.group(1).strip() if m else "")
        except Exception:
            return ""

    def _extract_story_structured(md: str) -> Dict[str, Any]:
        raw = str(md or "")
        if not raw.strip():
            return {}

        def _first_non_empty(*pairs: tuple[str, str]) -> str:
            for start_pat, end_pat in pairs:
                block = _extract_between(raw, start_pat, end_pat)
                if block:
                    return block
            return ""

        setup_block = _extract_between(raw, r"###\s*A\)", r"###\s*B\)")
        development_block = _first_non_empty(
            (r"###\s*B\)\s*发展", r"###\s*C\)\s*转折"),
            (r"###\s*B\)", r"###\s*C\)"),
        )
        turning_block = _first_non_empty(
            (r"###\s*C\)\s*转折", r"###\s*D\)\s*高潮"),
            (r"###\s*C\)", r"###\s*D\)"),
        )
        climax_block = _first_non_empty(
            (r"###\s*D\)\s*高潮", r"###\s*E\)\s*定局"),
            (r"###\s*D\)", r"###\s*E\)"),
        )
        resolution_block = _first_non_empty(
            (r"###\s*E\)\s*定局", r"##\s*5\)\s*[^\n]*悬念"),
            (r"###\s*E\)", r"##\s*6\)"),
            (r"###\s*E\)", r"##\s*5\)\s*[^\n]*悬念"),
        )
        suspense_block = _first_non_empty(
            (r"##\s*6\)\s*[^\n]*悬念", r"##\s*7\)"),
            (r"##\s*5\)\s*[^\n]*悬念", r"##\s*6\)"),
            (r"##\s*5\)", r"##\s*6\)"),
        )
        foreshadowing_block = _first_non_empty(
            (r"##\s*7\)\s*[^\n]*伏笔", r"##\s*8\)"),
            (r"##\s*6\)\s*[^\n]*伏笔", r"##\s*7\)"),
            (r"##\s*6\)", r"##\s*7\)"),
        )
        background_block = _first_non_empty(
            (r"##\s*2\)\s*[^\n]*核心设定", r"##\s*3\)"),
            (r"##\s*1\)", r"##\s*2\)"),
        )

        hook = ""
        inciting = ""
        point_of_no_return = ""
        hook_keys = ("开场钩子", "开场画面", "Opening Image")
        inciting_keys = ("触发事件", "激励事件", "Inciting Incident", "催化剂", "Catalyst")
        ponr_keys = ("不可回头", "立场选择", "越过边界", "Break into Two")
        for line in (setup_block or "").splitlines():
            s = line.strip()
            if (not hook) and any(k in s for k in hook_keys):
                hook = s
            elif (not inciting) and any(k in s for k in inciting_keys):
                inciting = s
            elif (not point_of_no_return) and any(k in s for k in ponr_keys):
                point_of_no_return = s

        return {
            "script_title": _extract_script_title_from_story_dna_markdown(raw),
            "background": background_block,
            "setup": setup_block,
            "hook": hook,
            "inciting_incident": inciting,
            "point_of_no_return": point_of_no_return,
            "development": development_block,
            "turning_points": turning_block,
            "climax": climax_block,
            "resolution": resolution_block,
            "suspense": suspense_block,
            "foreshadowing": foreshadowing_block,
        }

    story_structured = _extract_story_structured(gi.get("story_dna_global_md") or "")

    def _coalesce_story_input(stored_input: Dict[str, Any], structured: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(stored_input or {})
        for key in ["background", "setup", "development", "turning_points", "climax", "resolution", "suspense", "foreshadowing"]:
            current = str(merged.get(key) or "").strip()
            if not current:
                merged[key] = structured.get(key) or ""
        return merged

    story_input_export = _coalesce_story_input(story_input, story_structured)

    # Export complete Story Generator (Global/Project) related payload,
    # including draft inputs, outputs and metadata timestamps.
    story_generator_global_project = {
        key: value
        for key, value in gi.items()
        if (
            str(key).startswith("story_generator_global")
            or str(key).startswith("story_dna_global")
        )
    }

    return {
        "schema_version": 1,
        "export_type": "story_generator_global_project",
        "exported_at": now_bj_iso(),
        "source_project": {
            "id": project.id,
            "title": project.title,
        },
        "project_overview": {
            "script_title": basic_information.get("script_title") or "",
            "type": basic_information.get("type") or "",
            "language": basic_information.get("language") or "",
            "base_positioning": basic_information.get("base_positioning") or "",
            "Global_Style": basic_information.get("Global_Style") or "",
        },
        "basic_information": basic_information,
        "character_canon_project": character_canon_project,
        "story_generator_global_project": story_generator_global_project,
        "story_generator_global_structured": story_structured,
        "story_generator_global_input": story_input_export,
        "story_dna_global_md": gi.get("story_dna_global_md") or "",
    }


@router.put("/projects/{project_id}/story_generator/global/import", response_model=ProjectOut)
def import_project_story_generator_global_package(
    project_id: int,
    req: StoryGeneratorGlobalImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)

    now_iso = now_bj_iso()
    gi = dict(project.global_info or {})

    basic_information = req.basic_information or req.project_overview or {}
    if isinstance(basic_information, dict):
        text_fields = [
            "script_title",
            "series_episode",
            "type",
            "language",
            "base_positioning",
            "Global_Style",
            "tone",
            "lighting",
            "character_relationships",
            "notes",
        ]
        for key in text_fields:
            if key in basic_information:
                val = basic_information.get(key)
                gi[key] = "" if val is None else str(val)

        if "tech_params" in basic_information and isinstance(basic_information.get("tech_params"), dict):
            gi["tech_params"] = basic_information.get("tech_params") or {}

        if "borrowed_films" in basic_information:
            borrowed = basic_information.get("borrowed_films")
            gi["borrowed_films"] = borrowed if isinstance(borrowed, list) else []

    canon_payload = req.character_canon_project or {}
    if isinstance(canon_payload, dict):
        if "character_canon_input" in canon_payload and isinstance(canon_payload.get("character_canon_input"), dict):
            gi["character_canon_input"] = canon_payload.get("character_canon_input") or {}
            gi["character_canon_input_updated_at"] = now_iso

        if "character_canon_md" in canon_payload:
            gi["character_canon_md"] = canon_payload.get("character_canon_md") or ""

        if "character_profiles" in canon_payload:
            profiles = canon_payload.get("character_profiles")
            gi["character_profiles"] = profiles if isinstance(profiles, list) else []
            gi["character_profiles_updated_at"] = now_iso

        if "character_canon_tag_categories" in canon_payload:
            tags = canon_payload.get("character_canon_tag_categories")
            gi["character_canon_tag_categories"] = tags if isinstance(tags, list) else []

        if "character_canon_identity_categories" in canon_payload:
            identities = canon_payload.get("character_canon_identity_categories")
            gi["character_canon_identity_categories"] = identities if isinstance(identities, list) else []

    # Full Story Generator (Global/Project) package import (preferred path)
    # Accept all recognized story-global keys and merge into global_info.
    full_story_pkg = req.story_generator_global_project or {}
    if isinstance(full_story_pkg, dict):
        for key, value in full_story_pkg.items():
            k = str(key)
            if (
                k.startswith("story_generator_global")
                or k.startswith("story_dna_global")
            ):
                gi[k] = value

    imported_input = req.story_generator_global_input or {}
    if isinstance(imported_input, dict) and len(imported_input) > 0:
        normalized_input = dict(imported_input)
        normalized_input["mode"] = "global"
        if "episodes_count" in normalized_input:
            try:
                normalized_input["episodes_count"] = int(normalized_input.get("episodes_count") or 0)
            except Exception:
                normalized_input["episodes_count"] = 0
        if "episode_duration_minutes" in normalized_input:
            normalized_input["episode_duration_minutes"] = _resolve_episode_duration_minutes(
                normalized_input.get("episode_duration_minutes")
            )

        structured_input = req.story_generator_global_structured or {}
        if isinstance(structured_input, dict):
            for key in ["background", "setup", "development", "turning_points", "climax", "resolution", "suspense", "foreshadowing"]:
                if not str(normalized_input.get(key) or "").strip() and str(structured_input.get(key) or "").strip():
                    normalized_input[key] = structured_input.get(key)

        gi["story_generator_global_input"] = normalized_input
        gi["story_generator_global_input_updated_at"] = now_iso

    if req.story_dna_global_md is not None:
        gi["story_dna_global_md"] = req.story_dna_global_md or ""
        gi["story_dna_global_updated_at"] = now_iso


    project.global_info = gi
    db.add(project)
    db.commit()
    db.refresh(project)

    # Populate response aliases to match other endpoints
    try:
        project.cover_image = get_project_cover_image(db, project.id)
    except Exception:
        project.cover_image = None
    try:
        project.aspectRatio = project.global_info.get('aspectRatio') if project.global_info else None
    except Exception:
        project.aspectRatio = None
    return project


class AnalyzeNovelRequest(BaseModel):
    novel_text: str
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None


class StructureCreativeInputRequest(BaseModel):
    creative_text: str
    script_mode: Optional[str] = None
    target_audience: Optional[str] = None
    type: Optional[str] = None
    language: Optional[str] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None


_CREATIVE_INPUT_STRUCTURE_KEYS = [
    "logline",
    "theme",
    "core_conflict",
    "background",
    "characters",
    "setup",
    "development",
    "turning_points",
    "climax",
    "resolution",
    "suspense",
    "foreshadowing",
    "extra_notes",
]


def _sanitize_llm_json_text(raw: str) -> str:
    content = re.sub(r"<think>.*?</think>", "", str(raw or ""), flags=re.DOTALL | re.IGNORECASE).strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content, re.IGNORECASE)
    if fenced:
        content = fenced.group(1).strip()
    content = content.replace("```json", "").replace("```", "").strip()
    # Keep Unicode curly quotes inside JSON string values; converting them to ASCII "
    # breaks valid payloads like: "core_conflict": "隐藏"穿越者"身份".
    content = re.sub(r",\s*}", "}", content)
    content = re.sub(r",\s*]", "]", content)
    return content


def _extract_llm_json_object_from_text(raw: str) -> Optional[Dict[str, Any]]:
    text = _sanitize_llm_json_text(raw)
    if not text:
        return None

    json5_obj = _loads_json5_if_available(text)
    if isinstance(json5_obj, dict):
        return json5_obj

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        candidate = text[start_idx:end_idx + 1]
        json5_obj = _loads_json5_if_available(candidate)
        if isinstance(json5_obj, dict):
            return json5_obj
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            parsed, _end = decoder.raw_decode(text[idx:])
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


def _normalize_llm_json_object(raw: str, *, context: str) -> Dict[str, Any]:
    data = _extract_llm_json_object_from_text(raw)
    if not isinstance(data, dict):
        logger.error("[%s] JSON parse failed. Raw len=%s", context, len(raw or ""))
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM JSON for {context}")
    return data


async def _normalize_llm_json_object_with_repair(
    raw: str,
    *,
    context: str,
    llm_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data = _extract_llm_json_object_from_text(raw)
    if isinstance(data, dict):
        return data

    content = _sanitize_llm_json_text(raw)
    if not content or not llm_config:
        logger.error("[%s] JSON parse failed and repair unavailable. Raw len=%s", context, len(raw or ""))
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM JSON for {context}")

    repair_system = (
        "You are a strict JSON formatter. "
        "Convert the user's text into one valid JSON object only. "
        "The first character must be '{' and the last character must be '}'. "
        "Escape internal double quotes inside strings as \\\". "
        "No markdown fences, no explanation, no extra text."
    )
    repair_user = (
        "Fix the following content into valid JSON while preserving fields and values as much as possible.\n\n"
        f"{content}"
    )
    try:
        repair_response = await llm_service.chat_completion_with_fallback(
            [
                {"role": "system", "content": repair_system},
                {"role": "user", "content": repair_user},
            ],
            llm_config,
        )
        repair_raw = str((repair_response or {}).get("content") or "").strip()
        repaired = _extract_llm_json_object_from_text(repair_raw)
        if isinstance(repaired, dict):
            logger.warning("[%s] JSON parse recovered via repair pass", context)
            return repaired
    except Exception as exc:
        logger.warning("[%s] JSON repair pass failed: %s", context, exc)

    logger.error("[%s] JSON parse failed after repair. Raw len=%s", context, len(raw or ""))
    raise HTTPException(status_code=500, detail=f"Failed to parse LLM JSON for {context}")


def _normalize_story_field_map(data: Dict[str, Any], keys: List[str]) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    for key in keys:
        val = data.get(key, "")
        if val is None:
            normalized[key] = ""
        elif isinstance(val, str):
            normalized[key] = val.strip()
        else:
            normalized[key] = str(val).strip()
    return normalized


async def _run_structure_llm_call(
    *,
    db: Session,
    user_id: int,
    project_global_info: Optional[Dict[str, Any]],
    req: "StructureCreativeInputRequest",
    sys_prompt: str,
    user_prompt: str,
    billing_item: str,
    llm_context: str,
) -> str:
    function_name = (getattr(req, "function_name", None) if req else None) or "script_analysis"
    system_api_id = getattr(req, "system_api_id", None) if req else None
    llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        user_id,
        function_name=function_name,
        system_api_id=system_api_id,
        context=llm_context,
        project_global_info=project_global_info,
    )
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured in active settings")
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None
    reservation_tx = None
    if billing_service.is_token_pricing(db, "llm_chat", provider, model):
        est = billing_service.estimate_reserve_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        reservation_tx = billing_service.reserve_credits(
            db,
            user_id,
            "llm_chat",
            provider,
            model,
            {
                "item": billing_item,
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            },
        )
    else:
        billing_service.check_balance(db, user_id, "llm_chat", provider, model)

    try:
        _release_db_connection(db, f"{llm_context}_llm_call")
        resp = await llm_service.generate_content_with_fallback(user_prompt, sys_prompt, llm_config)
    except Exception as e:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(e))
        raise

    raw = (resp.get("content") or "").strip()
    if not raw:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), "LLM returned empty content")
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    usage = resp.get("usage") or {}
    if not usage:
        usage = billing_service.estimate_input_output_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": raw},
            ],
            output_ratio=1.0,
        )
    billing_details = {
        "item": billing_item,
        "prompt_tokens": int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0),
        "completion_tokens": int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
        "total_tokens": int(
            usage.get(
                "total_tokens",
                int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
                + int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
            )
            or 0
        ),
    }
    billing_details["input_tokens"] = billing_details["prompt_tokens"]
    billing_details["output_tokens"] = billing_details["completion_tokens"]
    _apply_llm_routing_to_billing_details(billing_details, resp)

    if reservation_tx:
        billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), billing_details)
    else:
        billing_service.deduct_credits(db, user_id, "llm_chat", provider, model, billing_details)

    return raw


async def _prepare_episode_script_reference_block(
    *,
    user_id: int,
    project_global_info: Optional[Dict[str, Any]],
    llm_config: Dict[str, Any],
    global_md: str,
    episode_number: int,
    project_title: str = "",
    language: str = "",
) -> str:
    """Extract current-episode framework block, LLM key elements, web search (10 snippets), format for user prompt."""
    episode_block = extract_episode_block_from_global_framework(global_md, episode_number)
    if not episode_block.strip():
        logger.info(
            "[generate_episode_scripts] REFERENCE_SEARCH_SKIP episode_number=%s reason=empty_episode_block",
            episode_number,
        )
        return ""

    try:
        extract_prompt_template = _resolve_prompt_text("story_generator_episode_extract_key_elements.txt")
    except FileNotFoundError:
        logger.warning(
            "[generate_episode_scripts] REFERENCE_SEARCH_SKIP episode_number=%s reason=missing_extract_prompt",
            episode_number,
        )
        return ""

    try:
        extract_sys_prompt = extract_prompt_template.format(episode_block=episode_block)
    except Exception:
        extract_sys_prompt = extract_prompt_template

    extract_user_prompt = (
        f"Project Title: {project_title or '(none)'}\n"
        f"Episode Number: {episode_number}\n"
        f"Preferred Language: {language or 'zh'}\n\n"
        "Extract searchable key elements from this episode's framework block, with emphasis on climax moments, iconic scenes, golden quotes, and trope patterns."
    )

    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None
    reservation_tx = None
    key_elements: Dict[str, Any] = {}

    ref_db = SessionLocal()
    try:
        if billing_service.is_token_pricing(ref_db, "llm_chat", provider, model):
            est = billing_service.estimate_reserve_tokens_from_messages(
                [
                    {"role": "system", "content": extract_sys_prompt},
                    {"role": "user", "content": extract_user_prompt},
                ],
            )
            reservation_tx = billing_service.reserve_credits(
                ref_db,
                user_id,
                "llm_chat",
                provider,
                model,
                {
                    "item": "episode_extract_key_elements",
                    "episode_number": episode_number,
                    "estimation_method": "prompt_tokens_ratio",
                    "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                    "input_tokens": est.get("input_tokens", 0),
                    "output_tokens": est.get("output_tokens", 0),
                    "total_tokens": est.get("total_tokens", 0),
                },
            )
        else:
            billing_service.check_balance(ref_db, user_id, "llm_chat", provider, model)

        _release_db_connection(ref_db, f"episode_extract_key_elements_ep{episode_number}_llm_call")
        ref_db = None
        resp = await llm_service.generate_content_with_fallback(extract_user_prompt, extract_sys_prompt, llm_config)
        raw = (resp.get("content") or "").strip()
        if not raw:
            raise RuntimeError("LLM returned empty content for episode key-element extraction")

        usage = resp.get("usage") or {}
        if not usage:
            usage = billing_service.estimate_input_output_tokens_from_messages(
                [
                    {"role": "system", "content": extract_sys_prompt},
                    {"role": "user", "content": extract_user_prompt},
                    {"role": "assistant", "content": raw},
                ],
                output_ratio=1.0,
            )
        billing_details = {
            "item": "episode_extract_key_elements",
            "episode_number": episode_number,
            "prompt_tokens": int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0),
            "completion_tokens": int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
            "total_tokens": int(
                usage.get(
                    "total_tokens",
                    int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
                    + int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
                )
                or 0
            ),
        }
        billing_details["input_tokens"] = billing_details["prompt_tokens"]
        billing_details["output_tokens"] = billing_details["completion_tokens"]
        _apply_llm_routing_to_billing_details(billing_details, resp)

        settle_db = SessionLocal()
        try:
            if reservation_tx:
                billing_service.settle_reservation(settle_db, _reservation_tx_id(reservation_tx), billing_details)
            else:
                billing_service.deduct_credits(settle_db, user_id, "llm_chat", provider, model, billing_details)
        finally:
            settle_db.close()

        key_elements = _normalize_llm_json_object(raw, context="episode_extract_key_elements")
    except Exception as exc:
        if reservation_tx:
            cancel_db = SessionLocal()
            try:
                billing_service.cancel_reservation(cancel_db, _reservation_tx_id(reservation_tx), str(exc))
            finally:
                cancel_db.close()
        if ref_db is not None:
            try:
                ref_db.close()
            except Exception:
                pass
        logger.warning(
            "[generate_episode_scripts] REFERENCE_SEARCH_KEY_EXTRACT_FAILED episode_number=%s err=%s",
            episode_number,
            exc,
        )
        key_elements = {
            "conflict_hooks": [episode_block[:240]],
            "iconic_scene_search_terms": [f"第{episode_number}集 短剧 名场面"],
            "climax_search_terms": [f"第{episode_number}集 高潮 反转"],
        }
    finally:
        if ref_db is not None:
            try:
                ref_db.close()
            except Exception:
                pass

    try:
        search_bundle = await collect_episode_script_reference_snippets(
            key_elements,
            episode_number=episode_number,
        )
    except Exception as exc:
        logger.warning(
            "[generate_episode_scripts] REFERENCE_SEARCH_FAILED episode_number=%s err=%s",
            episode_number,
            exc,
        )
        return ""

    snippet_count = len(search_bundle.get("snippets") or [])
    rendered_snippet_count = int(search_bundle.get("rendered_snippet_count") or 0)
    reference_text = build_episode_script_reference_user_prompt(
        search_bundle,
        key_elements,
        episode_number=episode_number,
        episode_block=episode_block,
        project_title=project_title,
        language=language,
    )
    rendered_snippet_count = int(search_bundle.get("rendered_snippet_count") or rendered_snippet_count)
    logger.info(
        "[generate_episode_scripts] REFERENCE_SEARCH_OK episode_number=%s episode_block_len=%s query_count=%s snippet_count=%s rendered_snippet_count=%s reference_block_len=%s",
        episode_number,
        len(episode_block),
        len(search_bundle.get("queries") or []),
        snippet_count,
        rendered_snippet_count,
        len(reference_text),
    )
    if not reference_text.strip():
        return ""

    return reference_text + "\n\n"


@router.post("/projects/{project_id}/story_generator/structure_creative_input", response_model=Dict[str, Any])
async def structure_project_creative_input_to_story_fields(
    project_id: int,
    req: StructureCreativeInputRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(
            structure_project_creative_input_to_story_fields,
            user_id=current_user.id,
            kind="structure_creative_input",
            project_id=project_id,
            req=req,
            async_mode="0",
        )
        return JSONResponse({"task_id": tid, "async": True})
    project = _require_project_access(db, project_id, current_user)

    creative_text = (req.creative_text or "").strip()
    if not creative_text:
        raise HTTPException(status_code=400, detail="creative_text is required")

    gi_existing = dict(project.global_info or {})
    user_id = int(current_user.id)
    project_global_info = gi_existing
    project_title_str = str(project.title or "")
    project_type = (getattr(req, "type", None) or gi_existing.get("type") or "").strip()
    language = (getattr(req, "language", None) or gi_existing.get("language") or "").strip()
    script_mode = (getattr(req, "script_mode", None) or "").strip()
    target_audience = (getattr(req, "target_audience", None) or "").strip()

    project_context = (
        f"Project Title: {project_title_str}\n"
        f"Type: {project_type}\n"
        f"Language: {language}\n"
        f"Script Mode: {script_mode}\n"
        f"Target Audience: {target_audience}\n"
    )

    try:
        extract_prompt_template = _resolve_prompt_text("story_generator_structure_extract_key_elements.txt")
    except FileNotFoundError:
        logger.error("Structure extract key elements prompt not found")
        raise HTTPException(
            status_code=404,
            detail="Prompt file 'story_generator_structure_extract_key_elements.txt' not found.",
        )

    try:
        extract_sys_prompt = extract_prompt_template.format(creative_text=creative_text)
    except Exception:
        extract_sys_prompt = extract_prompt_template

    extract_user_prompt = (
        f"{project_context}\n"
        f"Wild Creative Brainstorm:\n{creative_text}\n\n"
        "Extract searchable key elements from the brainstorm, with emphasis on climax moments and iconic scenes."
    )
    extract_raw = await _run_structure_llm_call(
        db=db,
        user_id=user_id,
        project_global_info=project_global_info,
        req=req,
        sys_prompt=extract_sys_prompt,
        user_prompt=extract_user_prompt,
        billing_item="structure_extract_key_elements",
        llm_context="structure_extract_key_elements",
    )
    key_elements = _normalize_llm_json_object(extract_raw, context="structure_extract_key_elements")

    search_bundle = await collect_creative_structure_search_snippets(key_elements)
    search_context = build_creative_structure_search_user_prompt(
        search_bundle,
        key_elements,
        project_title=project_title_str,
        language=language,
    )

    try:
        sys_prompt_template = _resolve_prompt_text("story_generator_structure_creative_input.txt")
    except FileNotFoundError:
        logger.error("Structure creative input prompt not found: story_generator_structure_creative_input.txt")
        raise HTTPException(
            status_code=404,
            detail="Prompt file 'story_generator_structure_creative_input.txt' not found.",
        )

    try:
        sys_prompt = sys_prompt_template.format(creative_text=creative_text, search_context=search_context)
    except Exception:
        sys_prompt = f"{sys_prompt_template}\n\n{creative_text}\n\n{search_context}"

    user_prompt = (
        f"{project_context}\n"
        f"Wild Creative Brainstorm:\n{creative_text}\n\n"
        "Use the extracted key elements and reference search snippets to structure I1-I9. Prioritize climax and iconic scenes (I7a) using visual, dialogue, and action reference angles."
    )
    raw = await _run_structure_llm_call(
        db=db,
        user_id=user_id,
        project_global_info=project_global_info,
        req=req,
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        billing_item="structure_creative_input",
        llm_context="structure_creative_input",
    )

    structure_llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        user_id,
        function_name=(getattr(req, "function_name", None) or "script_analysis"),
        system_api_id=getattr(req, "system_api_id", None),
        context="structure_creative_input",
        project_global_info=project_global_info,
    )
    data = await _normalize_llm_json_object_with_repair(
        raw,
        context="structure_creative_input",
        llm_config=structure_llm_config,
    )
    normalized = _normalize_story_field_map(data, _CREATIVE_INPUT_STRUCTURE_KEYS)
    normalized["prefill_meta"] = {
        "pipeline": "extract_key_elements -> reference_search -> structure_fill",
        "key_elements": key_elements,
        "search_meta": {
            "query_count": len(search_bundle.get("queries") or []),
            "snippet_count": len(search_bundle.get("snippets") or []),
            "instant_note_count": len(search_bundle.get("instant_notes") or []),
            "source_stats": search_bundle.get("source_stats") or {},
        },
    }
    return normalized


class TrendingAiShortDramasRequest(BaseModel):
    month_label: Optional[str] = None
    limit: Optional[int] = 12
    language: Optional[str] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None


def _require_market_intel_model():
    if MarketIntelReport is None:
        raise HTTPException(status_code=503, detail="Market intel persistence is unavailable on this deployment")
    return MarketIntelReport


def _market_intel_report_to_dict(row, *, include_payload: bool = True) -> Dict[str, Any]:
    payload = dict(getattr(row, "payload_json", None) or {}) if include_payload else {}
    base = {
        "id": int(getattr(row, "id", 0) or 0),
        "project_id": int(getattr(row, "project_id", 0) or 0),
        "report_kind": str(getattr(row, "report_kind", "") or "").strip(),
        "report_month": str(getattr(row, "report_month", "") or "").strip(),
        "report_period": str(getattr(row, "report_period", "") or "").strip(),
        "fetched_at": str(getattr(row, "fetched_at", "") or "").strip(),
        "summary": str(getattr(row, "summary", "") or "").strip(),
        "markdown": str(getattr(row, "markdown", "") or "").strip() if include_payload else None,
        "created_at": str(getattr(row, "created_at", "") or "").strip(),
    }
    if include_payload:
        # Prefer full stored snapshot; fall back to row fields.
        merged = {
            **payload,
            **{k: v for k, v in base.items() if v is not None and v != ""},
            "id": base["id"],
            "project_id": base["project_id"],
            "report_kind": base["report_kind"],
            "created_at": base["created_at"],
        }
        if not merged.get("markdown"):
            merged["markdown"] = base.get("markdown") or ""
        if not merged.get("summary"):
            merged["summary"] = base.get("summary") or ""
        return merged
    return {k: v for k, v in base.items() if k != "markdown"}


def _persist_market_intel_report(
    db: Session,
    *,
    project: Project,
    report_kind: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    model = _require_market_intel_model()
    kind = str(report_kind or "").strip()
    report_month = str((payload or {}).get("report_month") or "").strip() or current_report_month_label()
    report_period = str((payload or {}).get("report_period") or "").strip() or current_report_period_label(report_month)
    fetched_at = str((payload or {}).get("fetched_at") or "").strip() or now_bj_iso()
    summary = str((payload or {}).get("summary") or "").strip()
    markdown = str((payload or {}).get("markdown") or "").strip()
    row = model(
        project_id=int(project.id),
        report_kind=kind,
        report_month=report_month,
        report_period=report_period,
        fetched_at=fetched_at,
        summary=summary,
        markdown=markdown,
        payload_json=dict(payload or {}),
        created_at=now_bj_iso(),
    )
    db.add(row)

    # Keep latest snapshot on story_generator_global_input for backward compatibility.
    gi = dict(project.global_info or {})
    draft = dict(gi.get("story_generator_global_input") or {})
    if kind == "industry_analysis":
        draft["ai_short_drama_industry_report"] = dict(payload or {})
    elif kind == "trending_dramas":
        draft["trending_ai_short_dramas_report"] = dict(payload or {})
    gi["story_generator_global_input"] = draft
    gi["story_generator_global_input_updated_at"] = now_bj_iso()
    project.global_info = gi
    flag_modified(project, "global_info")

    db.commit()
    db.refresh(row)
    return _market_intel_report_to_dict(row, include_payload=True)


def _seed_market_intel_from_global_info(db: Session, project: Project) -> int:
    """One-time seed: copy latest global_info reports into history table when empty."""
    model = _require_market_intel_model()
    existing = (
        db.query(model.id)
        .filter(model.project_id == int(project.id))
        .limit(1)
        .first()
    )
    if existing:
        return 0
    gi = dict(project.global_info or {})
    draft = dict(gi.get("story_generator_global_input") or {})
    seeded = 0
    industry = draft.get("ai_short_drama_industry_report")
    if isinstance(industry, dict) and (industry.get("markdown") or industry.get("summary")):
        payload = dict(industry)
        payload.setdefault("report_month", current_report_month_label())
        payload.setdefault("report_period", current_report_period_label(payload["report_month"]))
        payload.setdefault("fetched_at", gi.get("story_generator_global_input_updated_at") or now_bj_iso())
        row = model(
            project_id=int(project.id),
            report_kind="industry_analysis",
            report_month=str(payload.get("report_month") or ""),
            report_period=str(payload.get("report_period") or ""),
            fetched_at=str(payload.get("fetched_at") or ""),
            summary=str(payload.get("summary") or ""),
            markdown=str(payload.get("markdown") or ""),
            payload_json=payload,
            created_at=str(payload.get("fetched_at") or now_bj_iso()),
        )
        db.add(row)
        seeded += 1
    trending = draft.get("trending_ai_short_dramas_report")
    if isinstance(trending, dict) and (trending.get("markdown") or trending.get("summary") or trending.get("dramas")):
        # Skip legacy combined blob that only holds industry_analysis.
        if trending.get("industry_analysis") and not (trending.get("markdown") or trending.get("dramas")):
            pass
        else:
            payload = dict(trending)
            payload.pop("industry_analysis", None)
            payload.setdefault("report_month", current_report_month_label())
            payload.setdefault("report_period", current_report_period_label(payload["report_month"]))
            payload.setdefault("fetched_at", gi.get("story_generator_global_input_updated_at") or now_bj_iso())
            row = model(
                project_id=int(project.id),
                report_kind="trending_dramas",
                report_month=str(payload.get("report_month") or ""),
                report_period=str(payload.get("report_period") or ""),
                fetched_at=str(payload.get("fetched_at") or ""),
                summary=str(payload.get("summary") or ""),
                markdown=str(payload.get("markdown") or ""),
                payload_json=payload,
                created_at=str(payload.get("fetched_at") or now_bj_iso()),
            )
            db.add(row)
            seeded += 1
    if seeded:
        db.commit()
    return seeded


async def _run_ai_short_drama_market_llm(
    *,
    db: Session,
    current_user: User,
    project,
    req: TrendingAiShortDramasRequest,
    sys_prompt: str,
    user_prompt: str,
    billing_item: str,
    llm_context: str,
) -> Dict[str, Any]:
    function_name = (getattr(req, "function_name", None) if req else None) or "script_analysis"
    system_api_id = getattr(req, "system_api_id", None) if req else None
    llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        int(current_user.id),
        function_name=function_name,
        system_api_id=system_api_id,
        context=llm_context,
        project_global_info=project.global_info,
    )
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured in active settings")
    cfg = dict(llm_config.get("config") or {})
    cfg.setdefault("response_format", {"type": "json_object"})
    llm_config = {**llm_config, "config": cfg}
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None

    reservation_tx = None
    if billing_service.is_token_pricing(db, "llm_chat", provider, model):
        est = billing_service.estimate_reserve_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        reservation_tx = billing_service.reserve_credits(
            db,
            current_user.id,
            "llm_chat",
            provider,
            model,
            {
                "item": billing_item,
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            },
        )
    else:
        billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

    try:
        _release_db_connection(db, f"{llm_context}_llm_call")
        resp = await llm_service.generate_content_with_fallback(user_prompt, sys_prompt, llm_config)
    except Exception as e:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(e))
        raise

    raw = (resp.get("content") or "").strip()
    if not raw:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), "LLM returned empty content")
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    usage = resp.get("usage") or {}
    if not usage:
        usage = billing_service.estimate_input_output_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": raw},
            ],
            output_ratio=1.0,
        )
    billing_details = {
        "item": billing_item,
        "prompt_tokens": int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0),
        "completion_tokens": int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
        "total_tokens": int(
            usage.get(
                "total_tokens",
                int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
                + int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
            )
            or 0
        ),
    }
    billing_details["input_tokens"] = billing_details["prompt_tokens"]
    billing_details["output_tokens"] = billing_details["completion_tokens"]
    _apply_llm_routing_to_billing_details(billing_details, resp)

    if reservation_tx:
        billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), billing_details)
    else:
        billing_service.deduct_credits(db, current_user.id, "llm_chat", provider, model, billing_details)

    return {"raw": raw, "llm_config": llm_config}


def _industry_analysis_section_map() -> List[Tuple[str, str]]:
    return [
        ("hot_list_overview", "热榜整体变化"),
        ("genre_theme_shifts", "题材变化（核心）"),
        ("rising_genres", "上升/新热题材"),
        ("declining_genres", "降温/退潮题材"),
        ("hook_and_trope_shifts", "钩子与桥段变化"),
        ("platform_hot_list_diff", "平台热榜差异"),
        ("audience_drivers", "受众驱动因素"),
        ("creator_opportunities", "创作者选材建议"),
    ]


def _build_industry_analysis_markdown(report_period: str, summary: str, industry_analysis: Dict[str, Any]) -> str:
    lines = [f"## {report_period} AI短剧热榜与题材变化分析", "", summary.strip(), "", "## 热榜与题材变化", ""]
    for key, title in _industry_analysis_section_map():
        value = str(industry_analysis.get(key) or "").strip()
        if value:
            lines.extend([f"### {title}", value, ""])
    return "\n".join(lines).strip()


def _build_trending_dramas_markdown(report_period: str, summary: str, dramas: List[Dict[str, Any]]) -> str:
    lines = [f"## {report_period} AI短剧热榜", "", summary.strip(), "", "## 热榜作品（高潮与名场面）", ""]
    for item in dramas:
        if not isinstance(item, dict):
            continue
        lines.append(f"### {item.get('rank', '')}. {item.get('title', '')}")
        lines.append(f"- 平台：{item.get('platform', '')}")
        lines.append(f"- 新上榜：{'是' if item.get('is_new_entry') else '否'}")
        lines.append(f"- 热度：{item.get('heat_signal', '')}")
        lines.append(f"- 简介：{item.get('synopsis', '')}")
        climax = str(item.get("climax_iconic_scenes") or "").strip()
        if climax:
            lines.append(f"- 高潮/名场面：{climax}")
        dialogue = str(item.get("classic_dialogue") or "").strip()
        if dialogue:
            lines.append(f"- 经典对白：{dialogue}")
        visual_action = str(item.get("visual_action_beats") or "").strip()
        if visual_action:
            lines.append(f"- 画面/动作：{visual_action}")
        lines.append(f"- 看点：{item.get('hook_points', '')}")
        lines.append("")
    return "\n".join(lines).strip()


@router.post("/projects/{project_id}/story_generator/industry_analysis_ai_short_dramas", response_model=Dict[str, Any])
async def fetch_industry_analysis_ai_short_dramas_report(
    project_id: int,
    req: TrendingAiShortDramasRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(
            fetch_industry_analysis_ai_short_dramas_report,
            user_id=current_user.id,
            kind="industry_analysis_ai_short_dramas",
            project_id=project_id,
            req=req,
            async_mode="0",
        )
        return JSONResponse({"task_id": tid, "async": True})
    project = _require_project_access(db, project_id, current_user)

    month_label = (req.month_label or current_report_month_label()).strip()
    report_period = current_report_period_label(month_label)

    search_bundle = await collect_industry_analysis_search_snippets(month_label=month_label)
    if not (search_bundle.get("snippets") or search_bundle.get("instant_notes")):
        raise HTTPException(status_code=502, detail="Web search returned no snippets for AI short drama industry analysis")

    try:
        sys_prompt_template = _resolve_prompt_text("story_generator_industry_analysis_ai_short_dramas.txt")
    except FileNotFoundError:
        logger.error("Industry analysis AI short dramas prompt not found")
        raise HTTPException(status_code=404, detail="Prompt file 'story_generator_industry_analysis_ai_short_dramas.txt' not found.")

    gi_existing = dict(project.global_info or {})
    language = (req.language or gi_existing.get("language") or "").strip()
    search_context = build_industry_analysis_user_prompt(
        search_bundle,
        project_title=str(project.title or ""),
        language=language,
    )
    try:
        sys_prompt = sys_prompt_template.format(search_context=search_context)
    except Exception:
        sys_prompt = f"{sys_prompt_template}\n\n{search_context}"

    user_prompt = (
        f"Compile the {report_period} AI short drama industry analysis from the search snippets below.\n"
        f"Focus on industry-wide trends only; do not rank individual dramas.\n\n"
        f"{search_context}"
    )
    llm_result = await _run_ai_short_drama_market_llm(
        db=db,
        current_user=current_user,
        project=project,
        req=req,
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        billing_item="industry_analysis_ai_short_dramas",
        llm_context="industry_analysis_ai_short_dramas",
    )
    raw = str((llm_result or {}).get("raw") or "").strip()
    data = await _normalize_llm_json_object_with_repair(
        raw,
        context="industry_analysis_ai_short_dramas",
        llm_config=(llm_result or {}).get("llm_config"),
    )
    industry_analysis = data.get("industry_analysis") if isinstance(data.get("industry_analysis"), dict) else {}
    markdown = str(data.get("markdown") or "").strip()
    summary = str(data.get("summary") or "").strip()
    if not markdown and industry_analysis:
        markdown = _build_industry_analysis_markdown(report_period, summary, industry_analysis)

    result = {
        "report_month": str(data.get("report_month") or month_label),
        "report_period": str(data.get("report_period") or report_period),
        "fetched_at": search_bundle.get("fetched_at"),
        "summary": summary,
        "industry_analysis": industry_analysis,
        "markdown": markdown,
        "disclaimer": str(data.get("disclaimer") or "").strip(),
        "search_meta": {
            "report_kind": "industry_analysis",
            "report_months": search_bundle.get("report_months") or [],
            "query_count": len(search_bundle.get("queries") or []),
            "snippet_count": len(search_bundle.get("snippets") or []),
            "instant_note_count": len(search_bundle.get("instant_notes") or []),
            "source_stats": search_bundle.get("source_stats") or {},
        },
    }
    try:
        return _persist_market_intel_report(
            db,
            project=project,
            report_kind="industry_analysis",
            payload=result,
        )
    except HTTPException:
        raise
    except Exception as persist_err:
        logger.warning("Failed to persist industry analysis report: %s", persist_err)
        return result


@router.post("/projects/{project_id}/story_generator/trending_ai_short_dramas", response_model=Dict[str, Any])
async def fetch_trending_ai_short_dramas_report(
    project_id: int,
    req: TrendingAiShortDramasRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(
            fetch_trending_ai_short_dramas_report,
            user_id=current_user.id,
            kind="trending_ai_short_dramas",
            project_id=project_id,
            req=req,
            async_mode="0",
        )
        return JSONResponse({"task_id": tid, "async": True})
    project = _require_project_access(db, project_id, current_user)

    month_label = (req.month_label or current_report_month_label()).strip()
    report_period = current_report_period_label(month_label)
    list_limit = 12
    try:
        list_limit = max(3, min(20, int(req.limit or 12)))
    except Exception:
        list_limit = 12

    search_bundle = await collect_trending_dramas_search_snippets(month_label=month_label)
    if not (search_bundle.get("snippets") or search_bundle.get("instant_notes")):
        raise HTTPException(status_code=502, detail="Web search returned no snippets for trending AI short dramas")

    try:
        sys_prompt_template = _resolve_prompt_text("story_generator_trending_ai_short_dramas.txt")
    except FileNotFoundError:
        logger.error("Trending AI short dramas prompt not found")
        raise HTTPException(status_code=404, detail="Prompt file 'story_generator_trending_ai_short_dramas.txt' not found.")

    gi_existing = dict(project.global_info or {})
    language = (req.language or gi_existing.get("language") or "").strip()
    search_context = build_trending_ai_short_dramas_user_prompt(
        search_bundle,
        project_title=str(project.title or ""),
        language=language,
        limit=list_limit,
    )
    try:
        sys_prompt = sys_prompt_template.format(search_context=search_context)
    except Exception:
        sys_prompt = f"{sys_prompt_template}\n\n{search_context}"

    user_prompt = (
        f"Compile the {report_period} AI short drama hot-list from the search snippets below.\n"
        f"Return up to {list_limit} hot/new dramas only.\n"
        f"For each drama, analyze climax and iconic scenes from visual, dialogue, and action angles.\n\n"
        f"{search_context}"
    )
    llm_result = await _run_ai_short_drama_market_llm(
        db=db,
        current_user=current_user,
        project=project,
        req=req,
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        billing_item="trending_ai_short_dramas",
        llm_context="trending_ai_short_dramas",
    )
    raw = str((llm_result or {}).get("raw") or "").strip()
    data = await _normalize_llm_json_object_with_repair(
        raw,
        context="trending_ai_short_dramas",
        llm_config=(llm_result or {}).get("llm_config"),
    )
    dramas = data.get("dramas") if isinstance(data.get("dramas"), list) else []
    markdown = str(data.get("markdown") or "").strip()
    summary = str(data.get("summary") or "").strip()
    if not markdown and dramas:
        markdown = _build_trending_dramas_markdown(report_period, summary, dramas)

    result = {
        "report_month": str(data.get("report_month") or month_label),
        "report_period": str(data.get("report_period") or report_period),
        "fetched_at": search_bundle.get("fetched_at"),
        "summary": summary,
        "markdown": markdown,
        "dramas": dramas,
        "disclaimer": str(data.get("disclaimer") or "").strip(),
        "search_meta": {
            "report_kind": "trending_dramas",
            "report_months": search_bundle.get("report_months") or [],
            "query_count": len(search_bundle.get("queries") or []),
            "snippet_count": len(search_bundle.get("snippets") or []),
            "instant_note_count": len(search_bundle.get("instant_notes") or []),
            "source_stats": search_bundle.get("source_stats") or {},
        },
    }
    try:
        return _persist_market_intel_report(
            db,
            project=project,
            report_kind="trending_dramas",
            payload=result,
        )
    except HTTPException:
        raise
    except Exception as persist_err:
        logger.warning("Failed to persist trending dramas report: %s", persist_err)
        return result


@router.get("/projects/{project_id}/market_intel/reports", response_model=Dict[str, Any])
async def list_market_intel_reports(
    project_id: int,
    kind: Optional[str] = Query(None, description="industry_analysis | trending_dramas"),
    month: Optional[str] = Query(None, description="YYYY-MM time index"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)
    model = _require_market_intel_model()
    try:
        _seed_market_intel_from_global_info(db, project)
    except Exception as seed_err:
        logger.warning("market intel seed skipped: %s", seed_err)

    q = db.query(model).filter(model.project_id == int(project_id))
    kind_norm = str(kind or "").strip()
    if kind_norm:
        q = q.filter(model.report_kind == kind_norm)
    month_norm = str(month or "").strip()
    if month_norm:
        q = q.filter(model.report_month == month_norm)
    rows = q.order_by(model.created_at.desc(), model.id.desc()).limit(int(limit)).all()
    items = [_market_intel_report_to_dict(row, include_payload=False) for row in rows]
    return {"items": items, "total": len(items)}


@router.get("/projects/{project_id}/market_intel/reports/{report_id}", response_model=Dict[str, Any])
async def get_market_intel_report(
    project_id: int,
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user)
    model = _require_market_intel_model()
    row = (
        db.query(model)
        .filter(model.id == int(report_id), model.project_id == int(project_id))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Market intel report not found")
    return _market_intel_report_to_dict(row, include_payload=True)


@router.post("/projects/{project_id}/story_generator/analyze_novel", response_model=Dict[str, Any])
async def analyze_project_novel_to_story_generator_fields(
    project_id: int,
    req: AnalyzeNovelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(analyze_project_novel_to_story_generator_fields, user_id=current_user.id,
                            kind="analyze_novel", project_id=project_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    project = _require_project_access(db, project_id, current_user)

    novel_text = (req.novel_text or "").strip()
    if not novel_text:
        raise HTTPException(status_code=400, detail="novel_text is required")

    try:
        sys_prompt_template = _resolve_prompt_text("story_generator_analyze_novel.txt")
    except FileNotFoundError:
        logger.error("Analyze novel prompt not found: story_generator_analyze_novel.txt")
        raise HTTPException(status_code=404, detail="Prompt file 'story_generator_analyze_novel.txt' not found.")

    project_title_str = str(project.title or "")
    user_prompt = f"Project Title: {project_title_str}\n\nNovel/Script Text:\n{novel_text}"

    function_name = (getattr(req, "function_name", None) if req else None) or "script_analysis"
    system_api_id = getattr(req, "system_api_id", None) if req else None

    llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        int(current_user.id),
        function_name=function_name,
        system_api_id=system_api_id,
        context="analyze_project_novel",
        project_global_info=project.global_info,
    )
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured in active settings")
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None
    resolved_id = ((llm_config or {}).get("config") or {}).get("__resolved_setting_id")
    resolved_source = ((llm_config or {}).get("config") or {}).get("__resolved_source")
    logger.info(
        "[analyze_novel] Using LLM config | provider=%s model=%s base_url=%s setting_id=%s source=%s",
        provider,
        model,
        (llm_config or {}).get("base_url"),
        resolved_id,
        resolved_source,
    )
    reservation_tx = None
    if billing_service.is_token_pricing(db, "llm_chat", provider, model):
        est = billing_service.estimate_reserve_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt_template},
                {"role": "user", "content": user_prompt},
            ],
        )
        reservation_tx = billing_service.reserve_credits(
            db,
            current_user.id,
            "llm_chat",
            provider,
            model,
            {
                "item": "analyze_novel",
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            },
        )
    else:
        billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

    # Keep compatibility with prompt template variable while still passing text in user prompt.
    try:
        sys_prompt = sys_prompt_template.format(novel_text=novel_text)
    except Exception:
        sys_prompt = sys_prompt_template

    try:
        _release_db_connection(db, "analyze_novel_llm_call")
        resp = await llm_service.generate_content_with_fallback(user_prompt, sys_prompt, llm_config)
    except Exception as e:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(e))
        raise

    raw = (resp.get("content") or "").strip()
    if not raw:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), "LLM returned empty content")
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    usage = resp.get("usage") or {}
    if not usage:
        usage = billing_service.estimate_input_output_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": raw},
            ],
            output_ratio=1.0,
        )
    billing_details = {
        "item": "analyze_novel",
        "prompt_tokens": int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0),
        "completion_tokens": int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
        "total_tokens": int(
            usage.get(
                "total_tokens",
                int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
                + int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
            )
            or 0
        ),
    }
    billing_details["input_tokens"] = billing_details["prompt_tokens"]
    billing_details["output_tokens"] = billing_details["completion_tokens"]
    _apply_llm_routing_to_billing_details(billing_details, resp)

    if reservation_tx:
        billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), billing_details)
    else:
        billing_service.deduct_credits(db, current_user.id, "llm_chat", provider, model, billing_details)

    content = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    content = content.replace("```json", "").replace("```", "").strip()
    start_idx = content.find("{")
    end_idx = content.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        content = content[start_idx:end_idx + 1]

    try:
        data = json.loads(content)
    except Exception as e:
        logger.error(f"[analyze_novel] JSON parse failed: {e}. Raw len={len(raw)}")
        raise HTTPException(status_code=500, detail="Failed to parse LLM JSON for novel analysis")

    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="LLM JSON must be an object")

    required_keys = [
        "background",
        "setup",
        "development",
        "turning_points",
        "climax",
        "resolution",
        "suspense",
        "foreshadowing",
    ]

    normalized: Dict[str, Any] = {}
    for key in required_keys:
        val = data.get(key, "")
        if val is None:
            normalized[key] = ""
        elif isinstance(val, str):
            normalized[key] = val.strip()
        else:
            normalized[key] = str(val).strip()

    return normalized


@router.get("/projects/", response_model=List[ProjectOut])
def read_projects(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    def _query_with(session: Session) -> List[Project]:
        shared_project_ids = [
            row[0]
            for row in session.query(ProjectShare.project_id).filter(ProjectShare.user_id == current_user.id).all()
        ]
        result = (
            session.query(Project.id, Project, func.count(ProjectShare.id).label("share_count"))
            .outerjoin(ProjectShare, Project.id == ProjectShare.project_id)
            .filter(
                _active_project_clause(),
                or_(
                    Project.owner_id == current_user.id,
                    Project.id.in_(shared_project_ids),
                )
            )
            .group_by(Project.id)
            .order_by(Project.updated_at.desc(), Project.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        if not result:
            return []
        
        # Batch preload cover images for the retrieved projects
        p_ids = [row[0] for row in result]
        
        poster_map, cover_images_map, shot_map, entity_map = {}, {}, {}, {}
        # Poster entities (project-level + per-episode covers)
        posters = session.query(
            Entity.project_id, Entity.episode_id, Entity.image_url, Entity.name
        ).filter(
            Entity.project_id.in_(p_ids),
            _active_entity_clause(),
            or_(
                Entity.name.in_(["封面海报", "海报", "封面", "cover", "poster"]),
                Entity.name.ilike("%海报%"),
                Entity.name.ilike("%封面%"),
                Entity.name.ilike("%cover%"),
                Entity.name.ilike("%poster%"),
                Entity.type.in_(["poster", "posters", "cover", "project_cover", "cover_image"]),
                Entity.type.ilike("%poster%"),
                Entity.type.ilike("%cover%")
            ),
            Entity.image_url != None,
            Entity.image_url != ""
        ).all()
        
        _temp_poster_map = {}
        _temp_episode_poster_map = {}
        for p_id, episode_id, image_url, name in posters:
            is_exact = (name == "封面海报")
            if p_id not in _temp_poster_map:
                _temp_poster_map[p_id] = {"url": image_url, "exact": is_exact}
            elif is_exact and not _temp_poster_map[p_id]["exact"]:
                _temp_poster_map[p_id] = {"url": image_url, "exact": is_exact}

            ep_key = (p_id, episode_id)
            if ep_key not in _temp_episode_poster_map:
                _temp_episode_poster_map[ep_key] = {"url": image_url, "exact": is_exact}
            elif is_exact and not _temp_episode_poster_map[ep_key]["exact"]:
                _temp_episode_poster_map[ep_key] = {"url": image_url, "exact": is_exact}
                
        for p_id, data in _temp_poster_map.items():
            poster_map[p_id] = _refresh_managed_media_url(data["url"], session)

        # Prefer exact「封面海报」per episode; order by episode_id (nulls last).
        for p_id, episode_id in sorted(
            _temp_episode_poster_map.keys(),
            key=lambda item: (item[1] is None, item[1] or 0, item[0]),
        ):
            refreshed = _refresh_managed_media_url(
                _temp_episode_poster_map[(p_id, episode_id)]["url"], session
            )
            if not refreshed:
                continue
            bucket = cover_images_map.setdefault(p_id, [])
            if refreshed not in bucket:
                bucket.append(refreshed)
            
        # First valid shot images (optimized using first() equivalent query or just aggregating)
        shot_subq = session.query(
            Shot.project_id,
            func.min(Shot.id).label("min_img_shot_id")
        ).filter(
            Shot.project_id.in_(p_ids),
            Shot.image_url != None,
            Shot.image_url != ""
        ).group_by(Shot.project_id).subquery()

        shots = session.query(Shot.project_id, Shot.image_url).join(
            shot_subq, (Shot.id == shot_subq.c.min_img_shot_id)
        ).all()
        for p_id, image_url in shots:
            if p_id not in shot_map:
                shot_map[p_id] = _refresh_managed_media_url(image_url, session)
                
        # First valid entities
        entity_subq = session.query(
            Entity.project_id,
            func.min(Entity.id).label("min_img_entity_id")
        ).filter(
            Entity.project_id.in_(p_ids),
            Entity.image_url != None,
            Entity.image_url != ""
        ).group_by(Entity.project_id).subquery()

        entities = session.query(Entity.project_id, Entity.image_url).join(
            entity_subq, (Entity.id == entity_subq.c.min_img_entity_id)
        ).all()
        for p_id, image_url in entities:
            if p_id not in entity_map:
                entity_map[p_id] = _refresh_managed_media_url(image_url, session)

        ret = []
        for row in result:
            p = row[1]
            p.share_count = row[2]
            
            # Determine cover image
            cover_image = poster_map.get(p.id)
            if not cover_image and isinstance(p.global_info, dict):
                configured_cover = str(p.global_info.get("cover_image") or p.global_info.get("coverImage") or "").strip()
                if configured_cover:
                    cover_image = configured_cover
            if not cover_image:
                cover_image = shot_map.get(p.id)
            if not cover_image:
                cover_image = entity_map.get(p.id)

            cover_images = list(cover_images_map.get(p.id) or [])
            if cover_image and cover_image not in cover_images:
                # Keep configured/fallback cover in the rotation pool when no per-ep posters.
                cover_images.insert(0, cover_image)
                
            p.cover_image = cover_image
            p.cover_images = cover_images
            _attach_project_flags(p, current_user, session)
            if p.global_info:
                p.aspectRatio = p.global_info.get('aspectRatio')
            p.description = (p.global_info or {}).get("notes")
            ret.append(p)
            
        return ret

    try:
        return _query_with(db)
    except OperationalError as e:
        logger.warning("[read_projects] transient db OperationalError, retrying once: %s", e)
        try:
            db.rollback()
        except Exception:
            pass

        retry_db = SessionLocal()
        try:
            return _query_with(retry_db)
        finally:
            retry_db.close()


@router.get("/projects/{project_id}", response_model=ProjectOut)
def read_project(
    project_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = _require_project_access(db, project_id, current_user)

    raw_info = project.global_info
    if isinstance(raw_info, dict):
        global_info = dict(raw_info)
    elif isinstance(raw_info, str):
        try:
            parsed = json.loads(raw_info)
            global_info = parsed if isinstance(parsed, dict) else {}
        except Exception:
            global_info = {}
    else:
        global_info = {}

    existing_seed = _normalize_seed_value(
        global_info.get("generation_seed")
        or global_info.get("seed")
        or ((global_info.get("generation") or {}).get("seed") if isinstance(global_info.get("generation"), dict) else None)
    )
    resolved_seed = _ensure_project_generation_seed(db, project_id, current_user)
    seed_initialized = bool(resolved_seed and not existing_seed)

    basic_info = global_info.get("basic_info") if isinstance(global_info.get("basic_info"), dict) else {}
    e_global_info = global_info.get("e_global_info") if isinstance(global_info.get("e_global_info"), dict) else {}
    story_input = global_info.get("story_generator_global_input") if isinstance(global_info.get("story_generator_global_input"), dict) else {}

    def _pick_non_empty_text(*values: Any) -> str:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return ""

    type_value = _pick_non_empty_text(
        global_info.get("type"),
        basic_info.get("type"),
        e_global_info.get("type"),
        story_input.get("type"),
    )
    country_region_value = _pick_non_empty_text(
        global_info.get("country_region"),
        basic_info.get("country_region"),
        e_global_info.get("country_region"),
        story_input.get("country_region"),
    )
    language_value = _pick_non_empty_text(
        global_info.get("language"),
        basic_info.get("language"),
        e_global_info.get("language"),
        story_input.get("language"),
    )

    missing_basic_fields: List[str] = []
    if not type_value:
        missing_basic_fields.append("type")
    if not country_region_value:
        missing_basic_fields.append("country_region")
    if not language_value:
        missing_basic_fields.append("language")
    
    project.cover_image = get_project_cover_image(db, project.id)
    if project.global_info:
        project.global_info = _ensure_project_generation_defaults(
            dict(project.global_info) if isinstance(project.global_info, dict) else {}
        )
        project.aspectRatio = project.global_info.get('aspectRatio')
    project.description = (project.global_info or {}).get("notes")
    project.generation_seed = resolved_seed
    project.seed_initialized = seed_initialized
    project.missing_basic_fields = missing_basic_fields
    project.has_missing_basic_info = bool(missing_basic_fields)
    _attach_project_flags(project, current_user, db)
    return project


@router.get("/projects/{project_id}/superuser-peek", response_model=ProjectOut)
def superuser_peek_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Superuser-only: load a project by id for temporary read-only viewing on the project cards page."""
    if not bool(getattr(current_user, "is_superuser", False)):
        raise HTTPException(status_code=403, detail="Only superuser can peek projects")

    project = db.query(Project).filter(Project.id == project_id, _active_project_clause()).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Owners / existing shares should open via normal membership, not temp peek.
    is_owner = project.owner_id == current_user.id
    is_shared = (not is_owner) and _is_project_shared_with_user(db, project.id, current_user.id)
    if is_owner or is_shared:
        project.cover_image = get_project_cover_image(db, project.id)
        if project.global_info:
            project.aspectRatio = (project.global_info or {}).get("aspectRatio")
        project.description = (project.global_info or {}).get("notes")
        _attach_project_flags(project, current_user, db)
        return project

    project.cover_image = get_project_cover_image(db, project.id)
    cover_images = []
    if project.cover_image:
        cover_images.append(project.cover_image)
    project.cover_images = cover_images
    if project.global_info:
        project.aspectRatio = (project.global_info or {}).get("aspectRatio")
    project.description = (project.global_info or {}).get("notes")
    project.share_count = int(
        db.query(func.count(ProjectShare.id)).filter(ProjectShare.project_id == project.id).scalar() or 0
    )
    _attach_project_flags(project, current_user, db)
    # Force temp-view markers for peek entry even if flags change later.
    project.is_temp_view = True
    project.can_edit = False
    project.is_owner = False
    return project


@router.put("/projects/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int, 
    project_in: ProjectUpdate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    project = _require_project_access(db, project_id, current_user)
    
    if project_in.title is not None:
        project.title = project_in.title

    # Merge global_info updates - handle aspectRatio specially if provided separately
    new_global_info = project_in.global_info # dict or None
    if new_global_info is None:
         # If generic global_info not provided, maybe we init with existing?
         # But usually PUT overwrites or PATCH updates partial. 
         # Assuming logic: "if provided, update".
         # However, we also have project_in.aspectRatio now.
         if project_in.aspectRatio is not None:
              # We need to update just that key in the existing JSON
              current_info = dict(project.global_info) if project.global_info else {}
              current_info['aspectRatio'] = project_in.aspectRatio
              project.global_info = current_info
    else:
         # global_info IS provided. Check if aspectRatio is also provided separately
         if project_in.aspectRatio is not None:
             new_global_info['aspectRatio'] = project_in.aspectRatio
         project.global_info = new_global_info

    if project_in.description is not None:
        current_info = dict(project.global_info) if project.global_info else {}
        current_info['notes'] = project_in.description
        project.global_info = current_info

    if project_in.cover_image is not None:
        current_info = dict(project.global_info) if project.global_info else {}
        cover_image = str(project_in.cover_image or "").strip()
        if cover_image:
            current_info['cover_image'] = cover_image
        else:
            current_info.pop('cover_image', None)
            current_info.pop('coverImage', None)
        project.global_info = current_info

    _sync_project_managed_shares(
        db,
        project,
        current_user,
        share_users=project_in.share_users,
        reviewer_users=project_in.reviewer_users,
    )

    # Normalize and persist generation defaults for consistent downstream billing inputs.
    project.global_info = _ensure_project_generation_defaults(project.global_info)
    try:
        _recompute_and_persist_project_cost_estimation(db, int(project.id))
    except Exception as cost_exc:
        logger.warning("update_project cost recompute skipped | project_id=%s err=%s", project.id, cost_exc)
    
    db.commit()
    db.refresh(project)
    project.cover_image = get_project_cover_image(db, project.id)
    if project.global_info:
        project.aspectRatio = project.global_info.get('aspectRatio')
    project.description = (project.global_info or {}).get("notes")
    _attach_project_flags(project, current_user, db)
    return project


@router.get("/projects/{project_id}/cost_estimation", response_model=Dict[str, Any])
def get_project_cost_estimation(
    project_id: int,
    refresh: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user)
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    existing = (project.global_info or {}).get("cost_estimation") if isinstance(project.global_info, dict) else None
    if refresh or not isinstance(existing, dict):
        snapshot = _recompute_and_persist_project_cost_estimation(db, project_id)
        db.commit()
        return snapshot
    return existing


@router.post("/projects/{project_id}/cost_estimation/recompute", response_model=Dict[str, Any])
def recompute_project_cost_estimation(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user)
    snapshot = _recompute_and_persist_project_cost_estimation(db, project_id)
    db.commit()
    return snapshot


@router.post("/projects/{project_id}/episodes/{episode_id}/cost_estimation/recompute", response_model=Dict[str, Any])
def recompute_episode_cost_estimation(
    project_id: int,
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recompute cost estimation scoped to a single episode, then persist full project snapshot."""
    _require_project_access(db, project_id, current_user)
    episode = db.query(Episode).filter(
        Episode.id == episode_id,
        Episode.project_id == project_id,
        _active_episode_clause(),
    ).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    snapshot = _recompute_and_persist_project_cost_estimation(db, project_id)
    db.commit()
    # Extract episode-specific slice from snapshot for a focused response
    ep_costs = [ep for ep in (snapshot.get("episode_costs") or []) if ep.get("episode_id") == episode_id]
    sc_costs = [sc for sc in (snapshot.get("scene_costs") or []) if sc.get("episode_id") == episode_id]
    return {
        "project_id": project_id,
        "episode_id": episode_id,
        "episode_cost": ep_costs[0] if ep_costs else None,
        "scene_costs": sc_costs,
        "summary": snapshot.get("summary"),
        "computed_at": snapshot.get("computed_at"),
    }


@router.post("/projects/{project_id}/scenes/{scene_id}/cost_estimation/recompute", response_model=Dict[str, Any])
def recompute_scene_cost_estimation(
    project_id: int,
    scene_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recompute cost estimation for a specific scene, persist full project snapshot, return scene slice."""
    _require_project_access(db, project_id, current_user)
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    # Verify scene belongs to this project via episode
    episode = db.query(Episode).filter(
        Episode.id == scene.episode_id,
        Episode.project_id == project_id,
        _active_episode_clause(),
    ).first()
    if not episode:
        raise HTTPException(status_code=403, detail="Scene does not belong to this project")
    snapshot = _recompute_and_persist_project_cost_estimation(db, project_id)
    db.commit()
    # Return the scene-level slice
    scene_cost = next((sc for sc in (snapshot.get("scene_costs") or []) if sc.get("scene_id") == scene_id), None)
    return {
        "project_id": project_id,
        "scene_id": scene_id,
        "episode_id": int(scene.episode_id),
        "scene_cost": scene_cost,
        "summary": snapshot.get("summary"),
        "computed_at": snapshot.get("computed_at"),
    }


@router.get("/deletion-batches")
def list_deletion_batches(
    project_id: Optional[int] = None,
    include_restored: bool = False,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if DeletionBatch is None:
        return []
    if project_id is not None:
        _require_project_owner_any_state(db, int(project_id), current_user)
    query = db.query(DeletionBatch).filter(DeletionBatch.user_id == current_user.id)
    if project_id is not None:
        query = query.filter(DeletionBatch.project_id == int(project_id))
    if not include_restored:
        query = query.filter(DeletionBatch.restored_at.is_(None))
    safe_skip = max(int(skip or 0), 0)
    safe_limit = max(1, min(int(limit or 50), 200))
    batches = (
        query.order_by(DeletionBatch.created_at.desc(), DeletionBatch.id.desc())
        .offset(safe_skip)
        .limit(safe_limit)
        .all()
    )
    return [_serialize_deletion_batch(batch, db) for batch in batches]


@router.get("/deletion-batches/{batch_id}")
def get_deletion_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if DeletionBatch is None:
        raise HTTPException(status_code=503, detail="Deletion batch is unavailable")
    batch = db.query(DeletionBatch).filter(DeletionBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Deletion batch not found")
    if int(batch.user_id) != int(current_user.id):
        _require_project_owner_any_state(db, int(batch.project_id), current_user)
    return _serialize_deletion_batch(batch, db)


@router.post("/deletion-batches/{batch_id}/restore")
def restore_deletion_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = _restore_deletion_batch(db, batch_id, current_user)
    db.commit()
    return result


@router.delete("/projects/{project_id}", status_code=200)
def delete_project(
    project_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = _require_project_access(db, project_id, current_user, owner_only=True)
    if _is_soft_deleted(project):
        return {"status": "deleted", "batch_id": None}

    now = now_bj_iso()
    batch_id = _start_deletion_batch(
        db,
        user_id=current_user.id,
        project_id=project_id,
        action_type="project",
        label=str(project.title or f"Project {project_id}"),
    )
    episode_ids = [
        row[0]
        for row in db.query(Episode.id).filter(
            Episode.project_id == project_id,
            _active_episode_clause(),
        ).all()
    ]
    _track_deletion_batch_items(db, batch_id, "project", [project_id])
    _track_deletion_batch_items(db, batch_id, "episode", episode_ids)

    project.is_deleted = True
    project.deleted_at = now
    project.updated_at = now
    if episode_ids:
        db.query(Episode).filter(Episode.id.in_(episode_ids)).update(
            {Episode.is_deleted: True, Episode.deleted_at: now},
            synchronize_session=False,
        )
    _soft_delete_project_children(db, project_id, now=now, batch_id=batch_id)
    _finalize_deletion_batch(db, batch_id)
    db.add(project)
    db.commit()
    return {"status": "deleted", "batch_id": batch_id}

