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

def _bind_endpoint_helpers() -> None:
    from app.api.routers.helper_bind import bind_shared_helpers
    bind_shared_helpers(globals(), __name__)

_bind_endpoint_helpers()

# --- Projects ---
class ProjectCreate(BaseModel):
    title: str
    description: Optional[str] = None
    global_info: dict = {}
    aspectRatio: Optional[str] = None
    share_users: Optional[List[str]] = None
    reviewer_users: Optional[List[str]] = None

class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    global_info: Optional[dict] = None
    aspectRatio: Optional[str] = None
    cover_image: Optional[str] = None
    share_users: Optional[List[str]] = None
    reviewer_users: Optional[List[str]] = None

class ProjectOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    owner_id: int
    global_info: dict
    aspectRatio: Optional[str] = None
    cover_image: Optional[str] = None
    # Per-episode cover poster URLs (ordered by episode_id) for project-card rotation.
    cover_images: Optional[List[str]] = None
    is_owner: Optional[bool] = True
    # Superuser temporary peek (not owner / not shared): view-only card in project list.
    is_temp_view: Optional[bool] = False
    can_edit: Optional[bool] = True
    generation_seed: Optional[int] = None
    seed_initialized: Optional[bool] = False
    missing_basic_fields: Optional[List[str]] = None
    has_missing_basic_info: Optional[bool] = False
    share_count: Optional[int] = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    class Config:
        from_attributes = True


class ProjectShareCreate(BaseModel):
    target_user: str
    role: Optional[str] = "editor"
    permissions: Optional[Dict[str, Any]] = None


class ProjectShareOut(BaseModel):
    id: int
    project_id: int
    user_id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str = "editor"
    permissions: Dict[str, Any] = {}
    created_at: Optional[str] = None


class ProjectAssetReviewThreadCreate(BaseModel):
    reviewer_user_id: Optional[int] = None
    reviewer_user: Optional[str] = None
    title: Optional[str] = None
    request_message: Optional[str] = None
    scope_type: Optional[str] = "all_current"
    entity_required: Optional[bool] = True
    shot_required: Optional[bool] = True
    entity_ids: Optional[List[int]] = None
    shot_ids: Optional[List[int]] = None
    due_at: Optional[str] = None


class ProjectAssetReviewThreadOut(BaseModel):
    id: int
    project_id: int
    requester_user_id: int
    requester_username: Optional[str] = None
    reviewer_user_id: int
    reviewer_username: Optional[str] = None
    title: Optional[str] = None
    status: str
    latest_round_no: int
    latest_activity_at: Optional[str] = None
    has_unread: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProjectAssetReviewThreadStatusUpdate(BaseModel):
    status: str


class ProjectAssetReviewThreadReadUpdate(BaseModel):
    read: bool = True


class ProjectAssetReviewRoundCreate(BaseModel):
    request_message: Optional[str] = None
    scope_type: Optional[str] = "all_current"
    entity_required: Optional[bool] = True
    shot_required: Optional[bool] = True
    entity_ids: Optional[List[int]] = None
    shot_ids: Optional[List[int]] = None
    due_at: Optional[str] = None


class ProjectAssetReviewRoundOut(BaseModel):
    id: int
    thread_id: int
    round_no: int
    initiated_by_user_id: int
    initiated_by_username: Optional[str] = None
    request_message: Optional[str] = None
    scope_type: str
    entity_required: bool
    shot_required: bool
    entity_decision: str
    shot_decision: str
    overall_status: str
    entity_feedback: Optional[str] = None
    shot_feedback: Optional[str] = None
    due_at: Optional[str] = None
    selected_entity_ids: List[int] = []
    selected_shot_ids: List[int] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    closed_at: Optional[str] = None


class ProjectAssetReviewMessageCreate(BaseModel):
    message_text: Optional[str] = None
    message_type: Optional[str] = "message"
    entity_decision: Optional[str] = None
    shot_decision: Optional[str] = None
    entity_feedback: Optional[str] = None
    shot_feedback: Optional[str] = None


class ProjectAssetReviewMessageOut(BaseModel):
    id: int
    round_id: int
    sender_user_id: int
    sender_username: Optional[str] = None
    sender_role: str
    message_type: str
    message_text: Optional[str] = None
    entity_decision: Optional[str] = None
    shot_decision: Optional[str] = None
    entity_feedback: Optional[str] = None
    shot_feedback: Optional[str] = None
    created_at: Optional[str] = None


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


def _active_project_clause():
    return or_(Project.is_deleted.is_(False), Project.is_deleted.is_(None))


def _active_episode_clause():
    return or_(Episode.is_deleted.is_(False), Episode.is_deleted.is_(None))


def _active_scene_clause():
    return or_(Scene.is_deleted.is_(False), Scene.is_deleted.is_(None))


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


def _active_shot_clause():
    return or_(Shot.is_deleted.is_(False), Shot.is_deleted.is_(None))


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

# --- Episodes (Script) ---

class ScriptSegmentBase(BaseModel):
    pid: str
    title: str
    content_revised: str
    content_original: str
    narrative_function: str
    analysis: str

class ScriptSegmentOut(ScriptSegmentBase):
    id: int
    class Config:
        from_attributes = True

class EpisodeCreate(BaseModel):
    title: str = "Episode 1"
    script_content: Optional[str] = ""
    episode_info: Optional[Dict] = {}
    ai_scene_analysis_result: Optional[str] = None
    ai_scene_analysis_scene_markdown: Optional[str] = None
    ai_entity_design_result: Optional[str] = None
    character_profiles: Optional[List[Dict[str, Any]]] = None
    ai_entity_design_result: Optional[str] = None
    ai_stage_outputs: Optional[str] = None

class EpisodeUpdate(BaseModel):
    title: Optional[str] = None
    script_content: Optional[str] = None
    episode_info: Optional[Dict] = None
    ai_scene_analysis_result: Optional[str] = None
    ai_scene_analysis_scene_markdown: Optional[str] = None
    ai_scene_analysis_subject_index: Optional[str] = None
    ai_scene_analysis_adaptation: Optional[str] = None
    character_profiles: Optional[List[Dict[str, Any]]] = None
    ai_entity_design_result: Optional[str] = None
    ai_stage_outputs: Optional[str] = None

class EpisodeListOut(BaseModel):
    id: int
    project_id: int
    title: str
    episode_info: Optional[Dict] = {}
    class Config:
        from_attributes = True

class EpisodeOut(BaseModel):
    id: int
    project_id: int
    title: str
    script_content: Optional[str]
    episode_info: Optional[Dict] = {}
    ai_scene_analysis_result: Optional[str] = None
    ai_scene_analysis_scene_markdown: Optional[str] = None
    ai_scene_analysis_subject_index: Optional[str] = None
    ai_scene_analysis_adaptation: Optional[str] = None
    ai_entity_design_result: Optional[str] = None
    ai_stage_outputs: Optional[str] = None
    character_profiles: Optional[List[Dict[str, Any]]] = []
    script_segments: List[ScriptSegmentOut] = []
    class Config:
        from_attributes = True


class ProjectEpisodeScriptsGenerateRequest(BaseModel):
    generator_kind: Optional[str] = None  # promo | story
    episodes_count: Optional[int] = None
    episode_duration_minutes: Optional[int] = None
    episode_id: Optional[int] = None  # Optional. Generate a specific episode only
    episode_number: Optional[int] = None  # Optional alias for single-episode generation
    script_mode: Optional[str] = None
    target_audience: Optional[str] = None
    script_title: Optional[str] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None
    overwrite_existing: bool = True
    retry_failed_only: bool = False
    extra_notes: Optional[str] = None
    strict_markdown: bool = True

@router.get("/projects/{project_id}/episodes", response_model=List[EpisodeListOut])
def read_episodes(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify access
    _require_project_access(db, project_id, current_user)
    
    from sqlalchemy.orm import selectinload, defer, noload
    episodes = (
        db.query(Episode)
        .options(
            defer(Episode.script_content),
            defer(Episode.ai_scene_analysis_result),
            defer(Episode.ai_scene_analysis_scene_markdown),
            defer(Episode.ai_scene_analysis_subject_index),
            defer(Episode.ai_scene_analysis_adaptation),
            defer(Episode.ai_entity_design_result),
            defer(Episode.ai_stage_outputs),
            defer(Episode.character_profiles),
            noload(Episode.script_segments)
        )
        .filter(
            Episode.project_id == project_id,
            _active_episode_clause(),
        )
        .all()
    )
    return _sort_project_episodes(episodes)

@router.get("/episodes/{episode_id}", response_model=EpisodeOut)
def read_episode(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from sqlalchemy.orm import noload
    episode = db.query(Episode).options(noload(Episode.script_segments)).filter(
        Episode.id == episode_id,
        _active_episode_clause(),
    ).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    return episode

@router.put("/episodes/{episode_id}/segments", response_model=List[ScriptSegmentOut])
def update_episode_segments(
    episode_id: int,
    segments: List[ScriptSegmentBase],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(
        Episode.id == episode_id,
        _active_episode_clause(),
    ).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    _require_project_access(db, episode.project_id, current_user)

    # Clear existing
    db.query(ScriptSegment).filter(ScriptSegment.episode_id == episode_id).delete()
    
    # Add new
    new_segments = []
    for s in segments:
        seg = ScriptSegment(
            episode_id=episode_id,
            pid=s.pid,
            title=s.title,
            content_revised=s.content_revised,
            content_original=s.content_original,
            narrative_function=s.narrative_function,
            analysis=s.analysis
        )
        db.add(seg)
        new_segments.append(seg)
    
    db.commit()
    # Refresh logic is tricky for lists, but querying clearly works
    return db.query(ScriptSegment).filter(ScriptSegment.episode_id == episode_id).all()

@router.post("/projects/{project_id}/episodes", response_model=EpisodeOut)
def create_episode(
    project_id: int,
    episode: EpisodeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_project_access(db, project_id, current_user)

    existing_episodes = db.query(Episode).filter(
        Episode.project_id == project_id,
        _active_episode_clause(),
    ).all()
    existing_numbers = {
        int(num)
        for num in (_resolve_episode_sort_number(item) for item in existing_episodes)
        if num is not None
    }
    requested_number = _extract_episode_number_from_title(getattr(episode, "title", None))
    if requested_number is not None and requested_number in existing_numbers:
        raise HTTPException(status_code=409, detail=f"episode_number={requested_number} already exists")

    assigned_number = requested_number
    if assigned_number is None:
        assigned_number = max(existing_numbers) + 1 if existing_numbers else 1

    episode_info = {"episode_script_episode_number": int(assigned_number)}
        
    db_episode = Episode(
        project_id=project_id, 
        title=episode.title, 
        script_content=episode.script_content,
        episode_info=episode_info,
        ai_scene_analysis_result=episode.ai_scene_analysis_result,
        ai_scene_analysis_scene_markdown=episode.ai_scene_analysis_scene_markdown,
        character_profiles=episode.character_profiles or []
    )
    db.add(db_episode)
    try:
        _recompute_and_persist_project_cost_estimation(db, int(project_id))
    except Exception as cost_exc:
        logger.warning("create_episode cost recompute skipped | project_id=%s err=%s", project_id, cost_exc)
    db.commit()
    db.refresh(db_episode)
    return db_episode

@router.put("/episodes/{episode_id}", response_model=EpisodeOut)
def update_episode(
    episode_id: int,
    episode_in: EpisodeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(
        Episode.id == episode_id,
        _active_episode_clause(),
    ).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    # Check access via project
    _require_project_access(db, episode.project_id, current_user)

    if episode_in.title is not None:
        episode.title = episode_in.title
    if episode_in.script_content is not None:
        episode.script_content = episode_in.script_content
    # episode_info is deprecated and intentionally ignored.

    if episode_in.ai_scene_analysis_result is not None:
        episode.ai_scene_analysis_result = episode_in.ai_scene_analysis_result
    if hasattr(episode_in, 'ai_scene_analysis_scene_markdown') and episode_in.ai_scene_analysis_scene_markdown is not None:
        episode.ai_scene_analysis_scene_markdown = episode_in.ai_scene_analysis_scene_markdown
    # Apply stage_outputs BEFORE subject_index heal so intentional clears
    # (empty subject_index + empty stage_outputs in one PUT) do not resurrect
    # the pre-update stage_outputs Subject Index.
    if hasattr(episode_in, 'ai_stage_outputs') and episode_in.ai_stage_outputs is not None:
        episode.ai_stage_outputs = episode_in.ai_stage_outputs
    if hasattr(episode_in, 'ai_scene_analysis_subject_index') and episode_in.ai_scene_analysis_subject_index is not None:
        sanitized_subject_index = sanitize_subject_index_text(episode_in.ai_scene_analysis_subject_index)
        if _subject_index_has_usable_content(sanitized_subject_index):
            episode.ai_scene_analysis_subject_index = sanitized_subject_index
        else:
            # Prefer Stage 2 panel Subject Index over empty/contaminated writes.
            # episode.ai_stage_outputs already reflects this request when provided.
            stage_candidate = _extract_subject_index_from_stage_outputs(episode.ai_stage_outputs)
            if _subject_index_has_usable_content(stage_candidate):
                episode.ai_scene_analysis_subject_index = stage_candidate
                logger.info(
                    "[update_episode] recovered subject index from stage_outputs episode_id=%s chars=%s",
                    episode_id,
                    len(stage_candidate),
                )
            else:
                episode.ai_scene_analysis_subject_index = sanitized_subject_index
    if hasattr(episode_in, 'ai_scene_analysis_adaptation') and episode_in.ai_scene_analysis_adaptation is not None:
        episode.ai_scene_analysis_adaptation = episode_in.ai_scene_analysis_adaptation
    if hasattr(episode_in, 'ai_entity_design_result') and episode_in.ai_entity_design_result is not None:
        episode.ai_entity_design_result = episode_in.ai_entity_design_result
    if episode_in.character_profiles is not None:
        episode.character_profiles = episode_in.character_profiles
    try:
        _recompute_and_persist_project_cost_estimation(db, int(episode.project_id))
    except Exception as cost_exc:
        logger.warning("update_episode cost recompute skipped | project_id=%s err=%s", episode.project_id, cost_exc)
    
    db.commit()
    db.refresh(episode)
    return episode


class CharacterProfileGenerateRequest(BaseModel):
    name: str
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None
    identity: Optional[str] = None
    body_features: Optional[str] = None
    style_tags: Optional[List[str]] = []
    extra_notes: Optional[str] = None


class CharacterProfilesUpdateRequest(BaseModel):
    character_profiles: List[Dict[str, Any]]


class CharacterCanonInputRequest(BaseModel):
    name: Optional[str] = None
    selected_tag_ids: Optional[List[str]] = None
    selected_identity_ids: Optional[List[str]] = None
    custom_identity: Optional[str] = None
    body_features: Optional[str] = None
    custom_style_tags: Optional[str] = None
    extra_notes: Optional[str] = None


class CharacterCanonCategoriesRequest(BaseModel):
    tag_categories: Optional[List[Dict[str, Any]]] = None
    identity_categories: Optional[List[Dict[str, Any]]] = None


@router.get("/projects/{project_id}/character_profiles", response_model=List[Dict[str, Any]])
def get_project_character_profiles(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)
    gi = project.global_info or {}
    if not isinstance(gi, dict):
        return []
    profiles = gi.get("character_profiles")
    return profiles if isinstance(profiles, list) else []


@router.put("/projects/{project_id}/character_profiles", response_model=List[Dict[str, Any]])
def update_project_character_profiles(
    project_id: int,
    req: CharacterProfilesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)

    def _render_canon_md(items: List[Dict[str, Any]]) -> str:
        blocks: List[str] = []
        for it in items or []:
            if not isinstance(it, dict):
                continue
            nm = (it.get("name") or "").strip()
            if not nm:
                continue
            md = (it.get("description_md") or "").strip()
            if md:
                blocks.append(md)
            else:
                blocks.append(f"### {nm} (Canonical)\n- Identity: {it.get('identity') or ''}\n")
        return "\n\n".join(blocks).strip()

    gi = dict(project.global_info or {})
    profiles = req.character_profiles or []
    gi["character_profiles"] = profiles
    gi["character_profiles_updated_at"] = now_bj_iso()
    gi["character_canon_md"] = _render_canon_md(profiles)
    project.global_info = gi

    db.add(project)
    db.commit()
    db.refresh(project)

    profiles = gi.get("character_profiles")
    return profiles if isinstance(profiles, list) else []


@router.put("/projects/{project_id}/character_canon/input", response_model=ProjectOut)
def save_project_character_canon_input(
    project_id: int,
    req: CharacterCanonInputRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist Project Character Canon draft inputs without calling the LLM."""
    project = _require_project_access(db, project_id, current_user)

    now_iso = now_bj_iso()
    gi = dict(project.global_info or {})
    gi["character_canon_input"] = {
        "name": req.name or "",
        "selected_tag_ids": req.selected_tag_ids or [],
        "selected_identity_ids": req.selected_identity_ids or [],
        "custom_identity": req.custom_identity or "",
        "body_features": req.body_features or "",
        "custom_style_tags": req.custom_style_tags or "",
        "extra_notes": req.extra_notes or "",
    }
    gi["character_canon_input_updated_at"] = now_iso
    project.global_info = gi

    db.add(project)
    db.commit()
    db.refresh(project)

    # Populate response aliases
    try:
        project.cover_image = get_project_cover_image(db, project.id)
    except Exception:
        project.cover_image = None
    try:
        project.aspectRatio = project.global_info.get('aspectRatio') if project.global_info else None
    except Exception:
        project.aspectRatio = None
    return project


@router.put("/projects/{project_id}/character_canon/categories", response_model=ProjectOut)
def save_project_character_canon_categories(
    project_id: int,
    req: CharacterCanonCategoriesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist Project Character Canon tag/identity category configuration."""
    project = _require_project_access(db, project_id, current_user)

    now_iso = now_bj_iso()
    gi = dict(project.global_info or {})
    if req.tag_categories is not None:
        gi["character_canon_tag_categories"] = req.tag_categories
    if req.identity_categories is not None:
        gi["character_canon_identity_categories"] = req.identity_categories
    gi["character_canon_categories_updated_at"] = now_iso
    project.global_info = gi

    db.add(project)
    db.commit()
    db.refresh(project)

    # Populate response aliases
    try:
        project.cover_image = get_project_cover_image(db, project.id)
    except Exception:
        project.cover_image = None
    try:
        project.aspectRatio = project.global_info.get('aspectRatio') if project.global_info else None
    except Exception:
        project.aspectRatio = None
    return project


@router.post("/projects/{project_id}/character_profiles/generate", response_model=ProjectOut)
async def generate_project_character_profile(
    project_id: int,
    req: CharacterProfileGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(generate_project_character_profile, user_id=current_user.id,
                            kind="char_profile_project", project_id=project_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    project = _require_project_access(db, project_id, current_user)

    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Character name is required")

    tags = [t.strip() for t in (req.style_tags or []) if isinstance(t, str) and t.strip()]
    tags_str = ", ".join(tags)

    sys_prompt = (
        "You are a professional character bible writer for film storyboarding. "
        "Write a CANONICAL character profile that will be treated as the single source of truth for this project. "
        "Return ONLY Markdown (no JSON, no code fences). "
        "Keep it concise but specific. Avoid NSFW/explicit sexual content; if the user requests 'sexy', express it in non-explicit, cinematic terms. "
        "Do not invent backstory not implied by inputs; focus on identity, silhouette/body proportions, face/hair, clothing, signature mannerisms, and on-screen presence."
    )

    user_prompt = (
        f"Character Name: {name}\n"
        f"Identity/Role: {req.identity or ''}\n"
        f"Body Features: {req.body_features or ''}\n"
        f"Style Tags: {tags_str}\n"
        f"Extra Notes: {req.extra_notes or ''}\n\n"
        "Output format (Markdown):\n"
        f"### {name} (Canonical)\n"
        "- Identity: ...\n"
        "- Body & silhouette: ...\n"
        "- Face & hair: ...\n"
        "- Outfit & materials: ...\n"
        "- Screen presence (cinematic, non-explicit): ...\n"
        "- Do/Don't (hard constraints): ...\n"
    )

    function_name = (getattr(req, "function_name", None) if req else None) or "script_analysis"
    system_api_id = getattr(req, "system_api_id", None) if req else None
    llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        int(current_user.id),
        function_name=function_name,
        system_api_id=system_api_id,
        context="generate_project_character_profile",
        project_global_info=project.global_info,
    )
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
                "item": "character_profile_project_generate",
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
        _release_db_connection(db, "character_profile_project_llm_call")
        resp = await llm_service.generate_content_with_fallback(user_prompt, sys_prompt, llm_config)
    except Exception as e:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(e))
        raise

    description_md = (resp.get("content") or "").strip()
    if not description_md:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), "LLM returned empty content")
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    usage = resp.get("usage") or {}
    if not usage:
        usage = billing_service.estimate_input_output_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": description_md},
            ],
            output_ratio=1.0,
        )
    details = {
        "item": "character_profile_project_generate",
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
    details["input_tokens"] = details["prompt_tokens"]
    details["output_tokens"] = details["completion_tokens"]
    _apply_llm_routing_to_billing_details(details, resp)
    if reservation_tx:
        billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), details)
    else:
        billing_service.deduct_credits(db, current_user.id, "llm_chat", provider, model, details)

    now_iso = now_bj_iso()
    gi = dict(project.global_info or {})
    profiles = gi.get("character_profiles")
    profiles = list(profiles) if isinstance(profiles, list) else []

    updated = False
    for p in profiles:
        if isinstance(p, dict) and (p.get("name") == name):
            p.update({
                "name": name,
                "identity": req.identity,
                "body_features": req.body_features,
                "style_tags": tags,
                "extra_notes": req.extra_notes,
                "description_md": description_md,
                "updated_at": now_iso,
            })
            updated = True
            break
    if not updated:
        profiles.append({
            "name": name,
            "identity": req.identity,
            "body_features": req.body_features,
            "style_tags": tags,
            "extra_notes": req.extra_notes,
            "description_md": description_md,
            "updated_at": now_iso,
        })

    def _render_canon_md(items: List[Dict[str, Any]]) -> str:
        blocks = []
        for it in items:
            if not isinstance(it, dict):
                continue
            nm = (it.get("name") or "").strip()
            if not nm:
                continue
            md = (it.get("description_md") or "").strip()
            if md:
                blocks.append(md)
            else:
                blocks.append(f"### {nm} (Canonical)\n- Identity: {it.get('identity') or ''}\n")
        return "\n\n".join(blocks).strip()

    gi["character_profiles"] = profiles
    gi["character_profiles_updated_at"] = now_iso
    gi["character_canon_md"] = _render_canon_md(profiles)
    project.global_info = gi

    db.add(project)
    db.commit()
    db.refresh(project)

    # Populate response aliases
    try:
        project.cover_image = get_project_cover_image(db, project.id)
    except Exception:
        project.cover_image = None
    try:
        project.aspectRatio = project.global_info.get('aspectRatio') if project.global_info else None
    except Exception:
        project.aspectRatio = None
    return project


class StoryGeneratorRequest(BaseModel):
    mode: str  # 'global' | 'episode'
    generator_kind: Optional[str] = None  # promo | story
    episodes_count: Optional[int] = None
    episode_duration_minutes: Optional[int] = 1
    episode_number: Optional[int] = None
    script_mode: Optional[str] = None
    target_audience: Optional[str] = None
    # Project Overview / Basic Information (optional but should be forwarded to LLM when provided)
    script_title: Optional[str] = None
    type: Optional[str] = None
    language: Optional[str] = None
    base_positioning: Optional[str] = None
    Global_Style: Optional[str] = None
    foreshadowing: Optional[str] = None
    logline: Optional[str] = None
    theme: Optional[str] = None
    core_conflict: Optional[str] = None
    characters: Optional[str] = None
    background: Optional[str] = None
    setup: Optional[str] = None
    development: Optional[str] = None
    turning_points: Optional[str] = None
    climax: Optional[str] = None
    resolution: Optional[str] = None
    suspense: Optional[str] = None
    wild_creative_notes: Optional[str] = None
    extra_notes: Optional[str] = None
    trending_ai_short_dramas_report: Optional[Dict[str, Any]] = None
    ai_short_drama_industry_report: Optional[Dict[str, Any]] = None
    strict_markdown: bool = True
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None


class ScriptScenesGenerateRequest(BaseModel):
    scene_count: Optional[int] = None
    background: Optional[str] = None
    setup: Optional[str] = None
    development: Optional[str] = None
    turning_points: Optional[str] = None
    climax: Optional[str] = None
    resolution: Optional[str] = None
    suspense: Optional[str] = None
    foreshadowing: Optional[str] = None
    extra_notes: Optional[str] = None
    replace_existing_scenes: Optional[bool] = True


EPISODE_SCENE_GEN_STATUS_KEY = "episode_scene_generation_status"


def _read_episode_scene_generation_status(episode: Episode) -> Dict[str, Any]:
    try:
        info = _episode_runtime_info_from_episode(episode)
        payload = info.get(EPISODE_SCENE_GEN_STATUS_KEY)
        if isinstance(payload, dict):
            return dict(payload)
    except Exception:
        pass
    return {
        "running": False,
        "status": "idle",
        "message": "",
        "scenes_created": 0,
        "stop_requested": False,
    }


def _persist_episode_scene_generation_status(db: Session, episode: Episode, status_payload: Dict[str, Any]) -> None:
    latest_episode = (
        db.query(Episode)
        .execution_options(populate_existing=True)
        .filter(Episode.id == int(episode.id))
        .first()
    )
    target_episode = latest_episode or episode

    info = _episode_runtime_info_from_episode(target_episode)
    existing_status = info.get(EPISODE_SCENE_GEN_STATUS_KEY)
    merged_status = dict(status_payload or {})
    has_incoming_force_flag = "force_stopped" in merged_status

    if isinstance(existing_status, dict) and bool(existing_status.get("force_stopped")) and not has_incoming_force_flag:
        merged_status["force_stopped"] = True

    if bool(merged_status.get("force_stopped")):
        now_iso = now_bj_iso()
        merged_status["running"] = False
        merged_status["status"] = "canceled"
        merged_status["stopped_by_user"] = True
        merged_status["finished_at"] = merged_status.get("finished_at") or now_iso
        merged_status["updated_at"] = now_iso

    info[EPISODE_SCENE_GEN_STATUS_KEY] = merged_status
    target_episode.episode_info = info
    db.add(target_episode)
    db.commit()


def _run_episode_scene_generation_job(episode_id: int, req_payload: Dict[str, Any], user_id: int) -> None:
    db = SessionLocal()
    try:
        episode = db.query(Episode).filter(Episode.id == episode_id).first()
        user = db.query(User).filter(User.id == user_id).first()
        if not episode or not user:
            return
        user_principal = _snapshot_user_principal(user)

        job_id = f"episode-scenes:{int(episode_id)}"
        user_name = str(user_principal.username or f"user_{user_id}")

        latest = _read_episode_scene_generation_status(episode)
        if bool(latest.get("stop_requested")):
            latest["running"] = False
            latest["status"] = "stopped"
            latest["message"] = "Stopped before generation started"
            latest["finished_at"] = now_bj_iso()
            latest["updated_at"] = latest["finished_at"]
            _persist_episode_scene_generation_status(db, episode, latest)
            _log_batch_sys_event(
                kind="episode-scenes",
                phase="end",
                user_id=user_id,
                user_name=user_name,
                project_id=episode.project_id,
                episode_id=episode_id,
                job_id=job_id,
                result="canceled",
                message="Stopped before generation started",
            )
            return

        req = ScriptScenesGenerateRequest(**(req_payload or {}))
        _release_db_connection(db, "episode_scene_generation_job")
        result = asyncio.run(
            generate_episode_scenes_from_story(
                episode_id=episode_id,
                req=req,
                db=db,
                current_user=user_principal,
            )
        )

        episode = db.query(Episode).filter(Episode.id == episode_id).first()
        if episode:
            status_payload = _read_episode_scene_generation_status(episode)
            status_payload["running"] = False
            status_payload["status"] = "completed"
            status_payload["message"] = "Scene generation completed"
            status_payload["scenes_created"] = int((result or {}).get("scenes_created") or 0)
            status_payload["result"] = result
            status_payload["updated_at"] = now_bj_iso()
            status_payload["finished_at"] = status_payload["updated_at"]
            _persist_episode_scene_generation_status(db, episode, status_payload)
            _log_batch_sys_event(
                kind="episode-scenes",
                phase="end",
                user_id=user_id,
                user_name=user_name,
                project_id=episode.project_id,
                episode_id=episode_id,
                job_id=job_id,
                result="completed",
                message="Scene generation completed",
                extra={
                    "scenes_created": int(status_payload.get("scenes_created") or 0),
                    "status": status_payload.get("status"),
                },
            )
    except Exception as e:
        try:
            episode = db.query(Episode).filter(Episode.id == episode_id).first()
            if episode:
                status_payload = _read_episode_scene_generation_status(episode)
                status_payload["running"] = False
                status_payload["status"] = "failed"
                status_payload["message"] = str(e)
                status_payload["updated_at"] = now_bj_iso()
                status_payload["finished_at"] = status_payload["updated_at"]
                _persist_episode_scene_generation_status(db, episode, status_payload)
                _log_batch_sys_event(
                    kind="episode-scenes",
                    phase="end",
                    user_id=user_id,
                    user_name=str((user.username if 'user' in locals() and user else "") or f"user_{user_id}"),
                    project_id=episode.project_id,
                    episode_id=episode_id,
                    job_id=f"episode-scenes:{int(episode_id)}",
                    result="failed",
                    message=str(e),
                )
        except Exception:
            pass
    finally:
        _clear_episode_worker(EPISODE_SCENE_JOB_THREADS, EPISODE_SCENE_JOB_THREADS_LOCK, int(episode_id))
        db.close()


@router.get("/episodes/{episode_id}/character_profiles", response_model=List[Dict[str, Any]])
def get_episode_character_profiles(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    return episode.character_profiles or []


@router.put("/episodes/{episode_id}/character_profiles", response_model=List[Dict[str, Any]])
def update_episode_character_profiles(
    episode_id: int,
    req: CharacterProfilesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    episode.character_profiles = req.character_profiles or []
    db.commit()
    db.refresh(episode)
    return episode.character_profiles or []


@router.post("/episodes/{episode_id}/character_profiles/generate", response_model=EpisodeOut)
async def generate_episode_character_profile(
    episode_id: int,
    req: CharacterProfileGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(generate_episode_character_profile, user_id=current_user.id,
                            kind="char_profile_episode", episode_id=episode_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Character name is required")

    # Build a strict, safe prompt: canonical character sheet used as ground truth.
    tags = [t.strip() for t in (req.style_tags or []) if isinstance(t, str) and t.strip()]
    tags_str = ", ".join(tags)

    sys_prompt = (
        "You are a professional character bible writer for film storyboarding. "
        "Write a CANONICAL character profile that will be treated as the single source of truth for this script. "
        "Return ONLY Markdown (no JSON, no code fences). "
        "Keep it concise but specific. Avoid NSFW/explicit sexual content; if the user requests 'sexy', express it in non-explicit, cinematic terms. "
        "Do not invent backstory not implied by inputs; focus on identity, silhouette/body proportions, face/hair, clothing, signature mannerisms, and on-screen presence."
    )

    user_prompt = (
        f"Character Name: {name}\n"
        f"Identity/Role: {req.identity or ''}\n"
        f"Body Features: {req.body_features or ''}\n"
        f"Style Tags: {tags_str}\n"
        f"Extra Notes: {req.extra_notes or ''}\n\n"
        "Output format (Markdown):\n"
        f"### {name} (Canonical)\n"
        "- Identity: ...\n"
        "- Body & silhouette: ...\n"
        "- Face & hair: ...\n"
        "- Outfit & materials: ...\n"
        "- Screen presence (cinematic, non-explicit): ...\n"
        "- Do/Don't (hard constraints): ...\n"
    )

    llm_config = agent_service.get_active_llm_config(current_user.id, function_name=getattr(req, "function_name", None), system_api_id=getattr(req, "system_api_id", None))
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
                "item": "character_profile_episode_generate",
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
        _release_db_connection(db, "character_profile_episode_llm_call")
        resp = await llm_service.generate_content_with_fallback(user_prompt, sys_prompt, llm_config)
    except Exception as e:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(e))
        raise

    description_md = (resp.get("content") or "").strip()
    if not description_md:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), "LLM returned empty content")
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    usage = resp.get("usage") or {}
    if not usage:
        usage = billing_service.estimate_input_output_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": description_md},
            ],
            output_ratio=1.0,
        )
    details = {
        "item": "character_profile_episode_generate",
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
    details["input_tokens"] = details["prompt_tokens"]
    details["output_tokens"] = details["completion_tokens"]
    _apply_llm_routing_to_billing_details(details, resp)
    if reservation_tx:
        billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), details)
    else:
        billing_service.deduct_credits(db, current_user.id, "llm_chat", provider, model, details)

    now_iso = now_bj_iso()
    profiles = list(episode.character_profiles or [])
    updated = False
    for p in profiles:
        if isinstance(p, dict) and (p.get("name") == name):
            p.update({
                "name": name,
                "identity": req.identity,
                "body_features": req.body_features,
                "style_tags": tags,
                "extra_notes": req.extra_notes,
                "description_md": description_md,
                "updated_at": now_iso,
            })
            updated = True
            break
    if not updated:
        profiles.append({
            "name": name,
            "identity": req.identity,
            "body_features": req.body_features,
            "style_tags": tags,
            "extra_notes": req.extra_notes,
            "description_md": description_md,
            "updated_at": now_iso,
        })

    def _render_canon_md(items: List[Dict[str, Any]]) -> str:
        blocks = []
        for it in items:
            if not isinstance(it, dict):
                continue
            nm = (it.get("name") or "").strip()
            if not nm:
                continue
            md = (it.get("description_md") or "").strip()
            if md:
                blocks.append(md)
            else:
                blocks.append(f"### {nm} (Canonical)\n- Identity: {it.get('identity') or ''}\n")
        return "\n\n".join(blocks).strip()

    canon_body = _render_canon_md(profiles)
    canon_section = (
        "## Character Canon (Authoritative)\n"
        "\n"
        "<!-- CHARACTER_CANON_START -->\n"
        "The following character profiles are AUTHORITATIVE for this script. Scene analysis and downstream generation MUST use these descriptions as ground truth and IGNORE conflicting character info elsewhere in the script.\n\n"
        f"{canon_body}\n"
        "<!-- CHARACTER_CANON_END -->\n"
    )

    script = episode.script_content or ""
    if "<!-- CHARACTER_CANON_START -->" in script and "<!-- CHARACTER_CANON_END -->" in script:
        script = re.sub(
            r"## Character Canon \(Authoritative\)[\s\S]*?<!-- CHARACTER_CANON_END -->\n?",
            canon_section + "\n",
            script,
            count=1,
        )
    else:
        script = canon_section + "\n\n" + script

    episode.character_profiles = profiles
    episode.script_content = script
    db.commit()
    db.refresh(episode)
    return episode


@router.post("/episodes/{episode_id}/story_generator", response_model=EpisodeOut)
async def generate_episode_story_dna(
    episode_id: int,
    req: "StoryGeneratorRequest",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(generate_episode_story_dna, user_id=current_user.id,
                            kind="story_dna_episode", episode_id=episode_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    project = _require_project_access(db, episode.project_id, current_user)

    mode = (req.mode or "").strip().lower()
    if mode not in ("global", "episode"):
        raise HTTPException(status_code=400, detail="mode must be 'global' or 'episode'")

    if mode == "global":
        # Backward compatible: allow generating global from any episode, but store to project.global_info
        if not req.episodes_count or int(req.episodes_count) <= 0:
            raise HTTPException(status_code=400, detail="episodes_count is required for global mode")
        generator_kind = _normalize_generator_kind(req.generator_kind) or "story"
        if generator_kind == "promo":
            prompt_filename = "promo_generator_global.txt"
        else:
            prompt_filename = "master_story_architect.md"
    else:
        if not req.episode_number or int(req.episode_number) <= 0:
            raise HTTPException(status_code=400, detail="episode_number is required for episode mode")
        prompt_filename = "story_generator_episode.txt"

    try:
        sys_prompt = _resolve_prompt_text(prompt_filename)
    except FileNotFoundError:
        logger.error("Story generator prompt not found: %s", prompt_filename)
        raise HTTPException(status_code=404, detail=f"Prompt file '{prompt_filename}' not found.")

    user_prompt_body = (
        f"Mode: {mode}\n"
        f"Episodes Count: {req.episodes_count or ''}\n"
        f"Episode Duration (minutes): {_resolve_episode_duration_minutes(getattr(req, 'episode_duration_minutes', None))}\n"
        f"Episode Number: {req.episode_number or ''}\n"
        f"Foreshadowing: {req.foreshadowing or ''}\n"
        f"Background: {req.background or ''}\n"
        f"Setup: {req.setup or ''}\n"
        f"Development: {req.development or ''}\n"
        f"Turning Points: {req.turning_points or ''}\n"
        f"Climax: {req.climax or ''}\n"
        f"Resolution: {req.resolution or ''}\n"
        f"Suspense: {req.suspense or ''}\n"
        f"Extra Notes: {req.extra_notes or ''}\n"
    )
    if mode == "global" and prompt_filename == "master_story_architect.md":
        user_prompt_body += (
            "\nTruncatable markers (hard): wrap Part 1 in [STORY_DNA_THINKING_START]…[STORY_DNA_THINKING_END]; "
            "wrap §0–§9 (including [SCRIPT_TITLE:…]) in [STORY_DNA_OUTPUT_START]…[STORY_DNA_OUTPUT_END]. "
            "Do not echo the INPUT block into OUTPUT.\n"
        )
        user_prompt = wrap_story_dna_input_block(user_prompt_body)
    else:
        user_prompt = user_prompt_body

    llm_config = agent_service.get_active_llm_config(current_user.id, function_name=getattr(req, "function_name", None), system_api_id=getattr(req, "system_api_id", None))
    llm_config = _inject_project_creativity_temperature(
        llm_config,
        project.global_info,
        context="generate_episode_story_dna",
    )
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None
    reservation_tx = None
    item_name = f"story_generator_{mode}"
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
                "item": item_name,
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            },
        )
    else:
        billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

    _release_db_connection(db, f"generate_episode_story_dna_{mode}_llm_call")

    try:
        generated_payload = await generate_markdown_with_retry(
            user_prompt=user_prompt,
            sys_prompt=sys_prompt,
            llm_config=llm_config,
            strict_markdown=False if (mode == "global" and prompt_filename == "master_story_architect.md") else (req.strict_markdown is not False),
            require_h1=False if (mode == "global" and prompt_filename == "master_story_architect.md") else True,
            return_meta=True,
        )
    except Exception as e:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(e))
        raise

    generated_md = str((generated_payload or {}).get("content") or "").strip()
    if not generated_md:
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    if mode == "global" and prompt_filename == "master_story_architect.md":
        dna_view = extract_story_dna_output_for_validation(generated_md)
        generated_md = normalize_story_dna_markdown_for_persist(generated_md)
        logger.info(
            "[generate_episode_story_dna] story_dna_markers mode=global had_output=%s had_thinking=%s "
            "truncated_thinking=%s persist_len=%s output_len=%s thinking_len=%s",
            bool(dna_view.get("had_output_markers")),
            bool(dna_view.get("had_thinking_markers")),
            bool(dna_view.get("truncated_thinking")),
            len(generated_md),
            len(str(dna_view.get("content") or "")),
            len(str(dna_view.get("thinking") or "")),
        )

    usage = (generated_payload or {}).get("usage") if isinstance(generated_payload, dict) else {}
    if not usage:
        usage = billing_service.estimate_input_output_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": generated_md},
            ],
            output_ratio=1.0,
        )
    billing_details = {
        "item": item_name,
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
    _apply_llm_routing_to_billing_details(billing_details, generated_payload)

    if reservation_tx:
        billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), billing_details)
    else:
        billing_service.deduct_credits(db, current_user.id, "llm_chat", provider, model, billing_details)

    # Persist both output and the inputs that produced it.
    try:
        story_input = req.model_dump()
    except AttributeError:
        story_input = req.dict()
    story_input["mode"] = mode
    story_input["generator_kind"] = _normalize_generator_kind(story_input.get("generator_kind") or req.generator_kind) or "story"
    story_input["generator_kind"] = _normalize_generator_kind(story_input.get("generator_kind") or req.generator_kind) or "story"

    now_iso = now_bj_iso()
    if mode == "global":
        project = db.merge(project)
        global_kind = _normalize_generator_kind(story_input.get("generator_kind")) or "story"
        gi = dict(project.global_info or {})
        if global_kind == "promo":
            gi["promo_generator_input"] = story_input
            gi["promo_generator_input_updated_at"] = now_iso
            gi["promo_dna_global_md"] = generated_md
            gi["promo_dna_global_updated_at"] = now_iso
        else:
            gi["story_generator_global_input"] = story_input
            gi["story_dna_global_md"] = generated_md
            gi["story_dna_global_updated_at"] = now_iso
        project.global_info = gi
        db.add(project)
    else:
        episode = db.merge(episode)
        ei = _episode_info_from_episode(episode)
        ei["story_generator_episode_input"] = story_input
        ei["story_generator_episode_input_updated_at"] = now_iso
        ei["story_dna_episode_md"] = generated_md
        ei["story_dna_episode_updated_at"] = now_iso
        # Also store the episode_number used to generate
        ei["story_dna_episode_number"] = int(req.episode_number)
        episode.episode_info = ei
        db.add(episode)

    db.commit()
    db.refresh(episode)
    return episode


@router.put("/episodes/{episode_id}/story_generator/input", response_model=EpisodeOut)
def save_episode_story_generator_input(
    episode_id: int,
    req: "StoryGeneratorRequest",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist Story Generator draft inputs without calling the LLM.

    This is used to avoid losing in-progress inputs before the user clicks Generate.
    """
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    project = _require_project_access(db, episode.project_id, current_user)

    mode = (req.mode or "").strip().lower()
    if mode not in ("global", "episode"):
        raise HTTPException(status_code=400, detail="mode must be 'global' or 'episode'")

    try:
        story_input = req.model_dump()
    except AttributeError:
        story_input = req.dict()
    story_input["mode"] = mode

    now_iso = now_bj_iso()
    if mode == "global":
        global_kind = _normalize_generator_kind(story_input.get("generator_kind")) or "story"
        gi = dict(project.global_info or {})
        if global_kind == "promo":
            gi["promo_generator_input"] = story_input
            gi["promo_generator_input_updated_at"] = now_iso
        else:
            gi["story_generator_global_input"] = story_input
            gi["story_generator_global_input_updated_at"] = now_iso
        project.global_info = gi
        db.add(project)
    else:
        ei = _episode_info_from_episode(episode)
        ei["story_generator_episode_input"] = story_input
        ei["story_generator_episode_input_updated_at"] = now_iso
        episode.episode_info = ei
        db.add(episode)

    db.commit()
    db.refresh(episode)
    return episode


@router.post("/episodes/{episode_id}/script_generator/scenes", response_model=Dict[str, Any])
async def generate_episode_scenes_from_story(
    episode_id: int,
    req: ScriptScenesGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(generate_episode_scenes_from_story, user_id=current_user.id,
                            kind="episode_scenes", episode_id=episode_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    project = _require_project_access(db, episode.project_id, current_user)

    try:
        sys_prompt = _resolve_prompt_text("script_generator_scenes.txt")
    except FileNotFoundError:
        logger.error("Script generator prompt not found: script_generator_scenes.txt")
        raise HTTPException(status_code=404, detail="Prompt file 'script_generator_scenes.txt' not found.")

    global_md = ""
    try:
        global_md = (project.global_info or {}).get("story_dna_global_md") or ""
    except Exception:
        global_md = ""
    episode_md = ""
    try:
        episode_md = _episode_info_from_episode(episode).get("story_dna_episode_md") or ""
    except Exception:
        episode_md = ""

    project_title_str = str(project.title or "")
    episode_title_str = str(episode.title or "")

    user_prompt = (
        f"Project Title: {project_title_str}\n"
        f"Episode Title: {episode_title_str}\n"
        f"Scene Count Target: {req.scene_count or ''}\n"
        f"Background: {req.background or ''}\n"
        f"Setup: {req.setup or ''}\n"
        f"Development: {req.development or ''}\n"
        f"Turning Points: {req.turning_points or ''}\n"
        f"Climax: {req.climax or ''}\n"
        f"Resolution: {req.resolution or ''}\n"
        f"Suspense: {req.suspense or ''}\n"
        f"Foreshadowing: {req.foreshadowing or ''}\n"
        f"Extra Notes: {req.extra_notes or ''}\n\n"
        f"Global Story DNA (if any):\n{global_md}\n\n"
        f"Episode Story DNA (if any):\n{episode_md}\n"
    )

    llm_config = agent_service.get_active_llm_config(current_user.id, function_name=getattr(req, "function_name", None), system_api_id=getattr(req, "system_api_id", None))
    llm_config = _inject_project_creativity_temperature(
        llm_config,
        project.global_info,
        context="generate_episode_scenes_from_story",
    )
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
                "item": "script_generator_scenes",
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
        _release_db_connection(db, "generate_episode_scenes_llm_call")
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
        "item": "script_generator_scenes",
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

    # Parse strict JSON (strip fences if model ignored instruction)
    content = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    content = content.replace("```json", "").replace("```", "").strip()
    start_idx = content.find("{")
    end_idx = content.rfind("}")
    if start_idx != -1 and end_idx != -1:
        content = content[start_idx:end_idx + 1]
    try:
        data = json.loads(content)
    except Exception as e:
        logger.error(f"[script_generator] JSON parse failed: {e}. Raw len={len(raw)}")
        raise HTTPException(status_code=500, detail="Failed to parse LLM JSON for scenes")

    scenes = data.get("scenes") if isinstance(data, dict) else None
    if not isinstance(scenes, list) or len(scenes) == 0:
        raise HTTPException(status_code=500, detail="LLM JSON did not include a non-empty 'scenes' list")

    if req.replace_existing_scenes:
        _soft_delete_scenes(db, episode_id=episode_id)

    created = []
    for i, s in enumerate(scenes, start=1):
        if not isinstance(s, dict):
            continue
        scene_no = str(s.get("scene_no") or i)
        original_script_text = str(s.get("original_script_text") or "").strip()
        if not original_script_text:
            continue
        db_scene = Scene(
            episode_id=episode_id,
            scene_no=scene_no,
            scene_name=(s.get("scene_name") or None),
            original_script_text=original_script_text,
            equivalent_duration=(s.get("equivalent_duration") or None),
            core_scene_info=(s.get("core_scene_info") or None),
            environment_name=(s.get("environment_name") or None),
            linked_characters=(s.get("linked_characters") or None),
            key_props=(s.get("key_props") or None),
        )
        db.add(db_scene)
        created.append(db_scene)

    db.commit()
    for sc in created:
        db.refresh(sc)

    # Non-blocking cost recompute after scenes are imported
    try:
        _recompute_and_persist_project_cost_estimation(db, int(episode.project_id))
        db.commit()
    except Exception:
        pass

    return {
        "episode_id": episode_id,
        "scenes_created": len(created),
        "scenes": [
            {
                "id": sc.id,
                "scene_no": sc.scene_no,
                "scene_name": sc.scene_name,
                "original_script_text": sc.original_script_text,
                "equivalent_duration": sc.equivalent_duration,
                "core_scene_info": sc.core_scene_info,
                "environment_name": sc.environment_name,
                "linked_characters": sc.linked_characters,
                "key_props": sc.key_props,
            }
            for sc in created
        ],
    }


@router.post("/episodes/{episode_id}/script_generator/scenes/start", response_model=Dict[str, Any])
def start_episode_scenes_generation_job(
    episode_id: int,
    req: ScriptScenesGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    latest = _read_episode_scene_generation_status(episode)
    if bool(latest.get("running")):
        raise HTTPException(status_code=409, detail="Scene generation is already running")

    now_iso = now_bj_iso()
    status_payload = {
        "running": True,
        "status": "running",
        "message": "Scene generation started",
        "episode_id": episode_id,
        "project_id": episode.project_id,
        "request": req.model_dump(),
        "scenes_created": 0,
        "result": None,
        "stop_requested": False,
        "stop_requested_at": None,
        "force_stopped": False,
        "started_at": now_iso,
        "updated_at": now_iso,
        "finished_at": None,
    }
    _persist_episode_scene_generation_status(db, episode, status_payload)
    _log_batch_sys_event(
        kind="episode-scenes",
        phase="start",
        user_id=current_user.id,
        user_name=current_user.username,
        project_id=episode.project_id,
        episode_id=episode_id,
        job_id=f"episode-scenes:{int(episode_id)}",
        result="running",
        message="Batch task started",
        extra={
            "request": req.model_dump(),
        },
    )

    worker = threading.Thread(
        target=_run_episode_scene_generation_job,
        args=(episode_id, req.model_dump(), current_user.id),
        daemon=True,
    )
    worker.start()
    _register_episode_worker(EPISODE_SCENE_JOB_THREADS, EPISODE_SCENE_JOB_THREADS_LOCK, int(episode_id), worker)
    return status_payload


@router.get("/episodes/{episode_id}/script_generator/scenes/status", response_model=Dict[str, Any])
def get_episode_scenes_generation_job_status(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    status_payload = _read_episode_scene_generation_status(episode)
    if (
        bool(status_payload.get("running"))
        and _is_stale_running_payload(status_payload, stale_minutes=10)
        and not _is_episode_worker_alive(EPISODE_SCENE_JOB_THREADS, EPISODE_SCENE_JOB_THREADS_LOCK, int(episode_id))
    ):
        now_iso = now_bj_iso()
        status_payload["running"] = False
        status_payload["status"] = "canceled"
        status_payload["force_stopped"] = True
        status_payload["stopped_by_user"] = True
        status_payload["updated_at"] = now_iso
        status_payload["finished_at"] = status_payload.get("finished_at") or now_iso
        status_payload["message"] = "Recovered orphaned task state (no active worker)"
        _persist_episode_scene_generation_status(db, episode, status_payload)
    return status_payload


@router.post("/episodes/{episode_id}/script_generator/scenes/stop", response_model=Dict[str, Any])
def stop_episode_scenes_generation_job(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    status_payload = _read_episode_scene_generation_status(episode)
    removed = False
    info = _episode_runtime_info_from_episode(episode)
    if EPISODE_SCENE_GEN_STATUS_KEY in info:
        info.pop(EPISODE_SCENE_GEN_STATUS_KEY, None)
        episode.episode_info = info
        db.add(episode)
        db.commit()
        removed = True

    _clear_episode_worker(EPISODE_SCENE_JOB_THREADS, EPISODE_SCENE_JOB_THREADS_LOCK, int(episode_id))
    _log_batch_sys_event(
        kind="episode-scenes",
        phase="stop",
        user_id=current_user.id,
        user_name=current_user.username,
        project_id=episode.project_id,
        episode_id=episode_id,
        job_id=f"episode-scenes:{int(episode_id)}",
        result="canceled",
        message="Force removed by user",
    )
    return {
        "episode_id": int(episode_id),
        "running": False,
        "status": "canceled",
        "deleted": bool(removed),
        "message": "Force removed",
    }


@router.post("/projects/{project_id}/script_generator/episodes/scripts", response_model=Dict[str, Any])
async def generate_project_episode_scripts_from_global_framework(
    project_id: int,
    req: ProjectEpisodeScriptsGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    """Generate per-episode script drafts from Project Overview artifacts.

    Uses:
    - project.global_info.story_dna_global_md (Generated Global Framework)
    - project.global_info.character_canon_md OR project.global_info.character_profiles (Character Canon Project)

    Creates missing episodes up to N and writes each draft into Episode.script_content.
    """
    if async_mode == "1":
        tid = _submit_async(generate_project_episode_scripts_from_global_framework, user_id=current_user.id,
                            kind="episode_scripts", project_id=project_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    started_at = datetime.utcnow()
    started_at_iso = started_at.isoformat()
    call_meta = {
        "project_id": project_id,
        "user_id": current_user.id,
        "generator_kind": req.generator_kind,
        "episodes_count": req.episodes_count,
        "episode_id": req.episode_id,
        "episode_number": req.episode_number,
        "overwrite_existing": req.overwrite_existing,
        "retry_failed_only": req.retry_failed_only,
        "strict_markdown": req.strict_markdown,
        "extra_notes_len": len(req.extra_notes or ""),
        "started_at": started_at_iso,
    }
    logger.info(f"[generate_episode_scripts] START {json.dumps(call_meta, ensure_ascii=False)}")

    try:
        project = _require_project_access(db, project_id, current_user)
    except HTTPException as e:
        logger.warning(f"[generate_episode_scripts] project access denied. project_id={project_id} user_id={current_user.id} detail={e.detail}")
        logger.info(
            f"[generate_episode_scripts] RESPONSE success=False status_code={e.status_code} project_id={project_id} detail={e.detail}"
        )
        raise

    user_id = int(current_user.id)
    user_name = str(current_user.username or "").strip()
    project_global_info = dict(project.global_info or {})
    gi_story_input = project_global_info.get("story_generator_global_input") if isinstance(project_global_info.get("story_generator_global_input"), dict) else {}
    gi_basic_info = project_global_info.get("basic_information") if isinstance(project_global_info.get("basic_information"), dict) else {}
    req_script_title_hint = _strip_stacked_production_title_suffixes(req.script_title)
    project_title = _strip_stacked_production_title_suffixes(
        project_global_info.get("script_title")
        or gi_story_input.get("script_title")
        or gi_basic_info.get("script_title")
        or _extract_script_title_from_story_dna_markdown(project_global_info.get("story_dna_global_md") or "")
        or req_script_title_hint
        or project.title
        or ""
    )
    if req_script_title_hint and _normalize_title_for_compare(project_title) == _normalize_title_for_compare(req_script_title_hint):
        project_title = _build_non_literal_script_title(
            seed_title=project_title,
            project_type=gi_basic_info.get("type") or project_global_info.get("type"),
            global_style=gi_basic_info.get("Global_Style") or project_global_info.get("Global_Style") or project_global_info.get("global_style"),
            base_positioning=gi_basic_info.get("base_positioning") or project_global_info.get("base_positioning"),
        )

    try:
        log_action(
            db,
            user_id=user_id,
            user_name=user_name,
            action="GENERATE_EPISODE_SCRIPTS_START",
            details=json.dumps(call_meta, ensure_ascii=False),
        )
    except Exception as e:
        logger.warning(f"[generate_episode_scripts] failed to write START system log: {e}")

    gi = dict(project_global_info)
    status_key = "episode_script_generation_status"

    def _persist_run_status(status_payload: Dict[str, Any]) -> None:
        status_db = SessionLocal()
        try:
            latest_project = status_db.query(Project).filter(Project.id == project_id).first()
            latest_gi = dict((latest_project.global_info if latest_project else {}) or {})
            existing_status = latest_gi.get(status_key) if isinstance(latest_gi.get(status_key), dict) else {}

            merged_status = dict(status_payload or {})
            has_incoming_force_flag = "force_stopped" in merged_status
            if bool(existing_status.get("force_stopped")) and not has_incoming_force_flag:
                merged_status["force_stopped"] = True

            if bool(existing_status.get("stop_requested")):
                merged_status["stop_requested"] = True
                if existing_status.get("stop_requested_at") and not merged_status.get("stop_requested_at"):
                    merged_status["stop_requested_at"] = existing_status.get("stop_requested_at")
                if not merged_status.get("stopped_by_user"):
                    merged_status["stopped_by_user"] = bool(existing_status.get("stopped_by_user"))

            if bool(merged_status.get("force_stopped")):
                now_iso = now_bj_iso()
                merged_status["running"] = False
                merged_status["status"] = "canceled"
                merged_status["stopped_by_user"] = True
                merged_status["finished_at"] = merged_status.get("finished_at") or now_iso
                merged_status["updated_at"] = now_iso
                if not merged_status.get("message"):
                    merged_status["message"] = "Force stopped"

            latest_gi[status_key] = status_payload
            if latest_project:
                latest_gi[status_key] = merged_status
                merged_results = merged_status.get("results") if isinstance(merged_status, dict) else []
                latest_item = merged_results[-1] if isinstance(merged_results, list) and merged_results else {}
                logger.info(
                    "[generate_episode_scripts] STATUS_PERSIST project_id=%s running=%s processed=%s generated=%s failed=%s skipped=%s results_count=%s latest_episode_id=%r latest_episode_number=%r latest_episode_title=%r latest_project_episode_title=%r latest_llm_episode_title=%r latest_status=%r",
                    project_id,
                    bool(merged_status.get("running")),
                    int(merged_status.get("processed") or 0),
                    int(merged_status.get("generated") or 0),
                    int(merged_status.get("failed") or 0),
                    int(merged_status.get("skipped") or 0),
                    len(merged_results) if isinstance(merged_results, list) else 0,
                    latest_item.get("episode_id") if isinstance(latest_item, dict) else None,
                    latest_item.get("episode_number") if isinstance(latest_item, dict) else None,
                    latest_item.get("episode_title") if isinstance(latest_item, dict) else None,
                    latest_item.get("project_episode_title") if isinstance(latest_item, dict) else None,
                    latest_item.get("llm_episode_title") if isinstance(latest_item, dict) else None,
                    latest_item.get("status") if isinstance(latest_item, dict) else None,
                )
                latest_project.global_info = latest_gi
                status_db.add(latest_project)
                status_db.commit()
        except Exception as e:
            logger.warning(f"[generate_episode_scripts] failed to persist run status: {e}")
        finally:
            status_db.close()

    def _read_run_status() -> Dict[str, Any]:
        status_db = SessionLocal()
        try:
            latest_project = status_db.query(Project).filter(Project.id == project_id).first()
            latest_gi = dict((latest_project.global_info if latest_project else {}) or {})
            latest_status = latest_gi.get(status_key)
            if isinstance(latest_status, dict):
                return dict(latest_status)
        except Exception as e:
            logger.warning(f"[generate_episode_scripts] failed to read run status: {e}")
        finally:
            status_db.close()
        return {}

    def _is_stop_requested() -> bool:
        latest_status = _read_run_status()
        return bool(latest_status.get("stop_requested"))

    generator_kind = _normalize_generator_kind(req.generator_kind) or "story"
    requested_episode_number: Optional[int] = None
    if req.episode_number is not None:
        try:
            requested_episode_number = int(req.episode_number)
        except Exception:
            raise HTTPException(status_code=400, detail="episode_number must be an integer")
        if requested_episode_number <= 0:
            raise HTTPException(status_code=400, detail="episode_number must be greater than 0")

    # Determine target episode count
    target_n: Optional[int] = None
    if req.episodes_count is not None:
        try:
            target_n = int(req.episodes_count)
        except Exception:
            logger.info(
                f"[generate_episode_scripts] RESPONSE success=False status_code=400 project_id={project_id} detail=episodes_count must be an integer"
            )
            raise HTTPException(status_code=400, detail="episodes_count must be an integer")
    else:
        try:
            input_key = "promo_generator_input" if generator_kind == "promo" else "story_generator_global_input"
            saved = (gi.get(input_key) or {}).get("episodes_count")
            if saved is not None:
                target_n = int(saved)
        except Exception:
            target_n = None

    if not target_n or target_n <= 0:
        if req.episode_id:
            target_n = 999  # Dummy fallback if targeting single episode
        elif requested_episode_number:
            target_n = int(requested_episode_number)
        else:
            logger.warning(
                f"[generate_episode_scripts] invalid episodes_count. project_id={project_id} user_id={current_user.id} req={req.episodes_count}"
            )
            try:
                log_action(
                    db,
                    user_id=user_id,
                    user_name=user_name,
                    action="GENERATE_EPISODE_SCRIPTS_FAILED",
                    details=f"project_id={project_id}; reason=invalid_episodes_count; req={req.episodes_count}",
                )
            except Exception as e:
                logger.warning(f"[generate_episode_scripts] failed to write FAILED system log: {e}")
            logger.info(
                f"[generate_episode_scripts] RESPONSE success=False status_code=400 project_id={project_id} detail=episodes_count is required"
            )
            raise HTTPException(status_code=400, detail="episodes_count is required (or generate/save Global Story first)")

    global_md_key = "promo_dna_global_md" if generator_kind == "promo" else "story_dna_global_md"
    global_md = str(gi.get(global_md_key) or "").strip()
    if not global_md:
        logger.warning(
            f"[generate_episode_scripts] missing global framework. project_id={project_id} user_id={current_user.id}"
        )
        try:
            log_action(
                db,
                user_id=user_id,
                user_name=user_name,
                action="GENERATE_EPISODE_SCRIPTS_FAILED",
                details=f"project_id={project_id}; reason=missing_global_framework",
            )
        except Exception as e:
            logger.warning(f"[generate_episode_scripts] failed to write FAILED system log: {e}")
        logger.info(
            f"[generate_episode_scripts] RESPONSE success=False status_code=400 project_id={project_id} detail=Generated Global Framework is empty"
        )
        raise HTTPException(status_code=400, detail=f"Generated Global Framework ({global_md_key}) is empty")

    story_input_key = "promo_generator_input" if generator_kind == "promo" else "story_generator_global_input"
    saved_story_input = gi.get(story_input_key) if isinstance(gi.get(story_input_key), dict) else {}
    episode_script_mode = _pick_first_text(
        req.script_mode,
        saved_story_input.get("script_mode"),
        gi_story_input.get("script_mode"),
    )
    episode_target_audience = _pick_first_text(
        req.target_audience,
        saved_story_input.get("target_audience"),
        gi_story_input.get("target_audience"),
    )
    episode_duration_minutes = _resolve_episode_duration_minutes(
        req.episode_duration_minutes
        if req.episode_duration_minutes is not None
        else saved_story_input.get("episode_duration_minutes")
        if saved_story_input.get("episode_duration_minutes") is not None
        else gi_story_input.get("episode_duration_minutes")
    )
    episode_product_specs_block = _build_episode_script_product_specs_block(
        episodes_count=target_n,
        episode_duration_minutes=episode_duration_minutes,
        script_mode=episode_script_mode,
        target_audience=episode_target_audience,
    )

    character_canon_md = str(gi.get("character_canon_md") or "").strip()
    if not character_canon_md:
        # Best-effort build from profiles
        profiles = gi.get("character_profiles") or []
        blocks: List[str] = []
        if isinstance(profiles, list):
            for p in profiles:
                if not isinstance(p, dict):
                    continue
                name = str(p.get("name") or "").strip()
                md = str(p.get("description_md") or "").strip()
                if name and md:
                    blocks.append(f"## {name}\n\n{md}")
        character_canon_md = "\n\n".join(blocks).strip()

    if not character_canon_md:
        logger.warning(
            f"[generate_episode_scripts] missing character canon (allowed). project_id={project_id} user_id={current_user.id}"
        )

    relationships = str(gi.get("character_relationships") or "").strip()
    has_relationships = bool(relationships)
    constraints_obj: Dict[str, Any] = {}
    constraints_block = ""
    if str(gi.get("character_canon_md") or "").strip():
        character_canon_source = "character_canon_md"
    elif character_canon_md:
        character_canon_source = "character_profiles_fallback"
    else:
        character_canon_source = "empty"

    logger.info(
        "[generate_episode_scripts] INPUT_CONTEXT "
        f"project_id={project_id} user_id={current_user.id} "
        f"has_relationships={has_relationships} global_md_len={len(global_md)} "
        f"character_canon_len={len(character_canon_md)} character_source={character_canon_source} "
        f"script_mode={episode_script_mode!r} target_audience={episode_target_audience!r} "
        f"episodes_count={target_n} episode_duration_minutes={episode_duration_minutes}"
    )

    # Single stable prompt entry for episode script generation.
    prompt_filename = "master_episode_writer.md"
    try:
        sys_prompt = _resolve_prompt_text(prompt_filename)
    except FileNotFoundError:
        logger.error("Episode script generator prompt not found: %s", prompt_filename)
        logger.info(
            f"[generate_episode_scripts] RESPONSE success=False status_code=404 project_id={project_id} detail=Prompt file {prompt_filename} not found"
        )
        raise HTTPException(status_code=404, detail=f"Prompt file '{prompt_filename}' not found.")

    # Ensure episodes exist with stable numeric mapping.
    # Priority: explicit episode_info number -> parse from title -> create missing.
    existing_eps = (
        db.query(Episode)
        .filter(
            Episode.project_id == project_id,
            _active_episode_clause(),
        )
        .order_by(Episode.id.asc())
        .all()
    )

    def _safe_positive_int(value: Any) -> Optional[int]:
        try:
            num = int(value)
            return num if num > 0 else None
        except Exception:
            return None

    def _extract_episode_index(ep: Episode) -> Optional[int]:
        ep_info = _episode_runtime_info_from_episode(ep)
        for key in (
            "episode_script_episode_number",
            "story_dna_episode_number",
            "episode_number",
            "index",
        ):
            num = _safe_positive_int(ep_info.get(key) if isinstance(ep_info, dict) else None)
            if num:
                return num

        title = str(ep.title or "")
        m = re.search(r"(?:Episode|EP)\s*[-_#]?\s*(\d+)", title, flags=re.IGNORECASE)
        if m:
            return _safe_positive_int(m.group(1))

        m = re.search(r"第\s*(\d+)\s*集", title)
        if m:
            return _safe_positive_int(m.group(1))

        return None

    def _is_placeholder_episode_title(title: Any, episode_number: Optional[int] = None) -> bool:
        value = str(title or "").strip()
        if not value:
            return True
        compact = re.sub(r"\s+", "", value).lower()
        if compact in {"untitled", "tbd", "episode", "第集"}:
            return True

        candidates: List[str] = []
        if episode_number and int(episode_number) > 0:
            n = int(episode_number)
            candidates.extend([
                f"episode{n}",
                f"ep{n}",
                f"ep{n:02d}",
                f"第{n}集",
                f"第{n}话",
                f"第{n}章",
                f"第{n}回",
            ])

        if compact in candidates:
            return True

        if re.fullmatch(r"(?:episode|ep)0*\d+", compact):
            return True
        if re.fullmatch(r"第\d+[集话章回]", compact):
            return True
        return False

    by_idx: Dict[int, Episode] = {}
    idx_candidates: Dict[int, List[int]] = {}
    by_title: Dict[str, Episode] = {}
    for ep in existing_eps:
        title_key = str(ep.title or "").strip().lower()
        if title_key and title_key not in by_title:
            by_title[title_key] = ep

        idx_num = _extract_episode_index(ep)
        if idx_num:
            idx_candidates.setdefault(int(idx_num), []).append(int(ep.id))
            if idx_num not in by_idx:
                by_idx[idx_num] = ep

    def _bind_episode_index(ep: Episode, idx_value: int) -> None:
        if not ep or not idx_value:
            return
        info = _episode_runtime_info_from_episode(ep)
        current = _safe_positive_int(info.get("episode_script_episode_number") if isinstance(info, dict) else None)
        if current == int(idx_value):
            return
        info["episode_script_episode_number"] = int(idx_value)
        ep.episode_info = info
        db.add(ep)
        db.commit()
        db.refresh(ep)

    # Fallback mapping for legacy projects: if titles were renamed without numeric prefix,
    # keep existing episode rows and assign missing indexes by stable DB order before creating any new rows.
    mapped_ids = {int(ep.id) for ep in by_idx.values() if ep is not None}
    unmapped_eps = [ep for ep in existing_eps if int(ep.id) not in mapped_ids]
    if unmapped_eps:
        upper_bound = max(int(target_n or 0), len(existing_eps), int(requested_episode_number or 0))
        next_unmapped_idx = 0
        for slot in range(1, upper_bound + 1):
            if slot in by_idx:
                continue
            if next_unmapped_idx >= len(unmapped_eps):
                break
            ep = unmapped_eps[next_unmapped_idx]
            next_unmapped_idx += 1
            _bind_episode_index(ep, slot)
            by_idx[slot] = ep
            idx_candidates.setdefault(int(slot), []).append(int(ep.id))

    logger.info(
        "[generate_episode_scripts] EPISODE_INDEX_MAP project_id=%s existing=%s mapped=%s unmapped_after_fallback=%s target_n=%s requested_episode_number=%r",
        project_id,
        len(existing_eps),
        len(by_idx),
        max(0, len(existing_eps) - len(by_idx)),
        target_n,
        requested_episode_number,
    )

    created_episodes: List[int] = []
    episodes_in_order: List[Episode] = []

    # Strict single-episode mode: never auto-create episodes before target resolution.
    single_episode_mode = bool(requested_episode_number is not None or req.episode_id)
    loop_limit = 0 if single_episode_mode else (target_n if target_n != 999 else 0)
    for i in range(1, loop_limit + 1):
        title = f"Episode {i}"
        ep = by_idx.get(i)
        if not ep:
            ep = by_title.get(title.strip().lower())
        if not ep:
            ep = by_title.get(f"第{i}集")
        if not ep:
            ep = Episode(project_id=project_id, title=title, script_content="")
            ep_info = _episode_runtime_info_from_episode(ep)
            ep_info["episode_script_episode_number"] = int(i)
            ep.episode_info = ep_info
            db.add(ep)
            db.commit()
            db.refresh(ep)
            created_episodes.append(ep.id)
            by_title[title.strip().lower()] = ep
            by_idx[i] = ep
        else:
            ep_info = _episode_runtime_info_from_episode(ep)
            if _safe_positive_int(ep_info.get("episode_script_episode_number") if isinstance(ep_info, dict) else None) is None:
                ep_info["episode_script_episode_number"] = int(i)
                ep.episode_info = ep_info
                db.add(ep)
                db.commit()
                db.refresh(ep)
        episodes_in_order.append(ep)

    previous_status = gi.get(status_key) if isinstance(gi.get(status_key), dict) else {}
    if isinstance(previous_status, dict) and bool(previous_status.get("running")):
        logger.info(
            f"[generate_episode_scripts] RESPONSE success=False status_code=409 project_id={project_id} detail=Episode script generation already running"
        )
        raise HTTPException(status_code=409, detail="Episode script generation is already running")

    failed_episode_ids: set[int] = set()
    previous_results = previous_status.get("results") if isinstance(previous_status, dict) else []
    if isinstance(previous_results, list):
        for item in previous_results:
            if not isinstance(item, dict):
                continue
            if str(item.get("status") or "") != "failed":
                continue
            try:
                ep_id_temp = int(item.get("episode_id"))
                failed_episode_ids.add(ep_id_temp)
            except Exception:
                continue

    episodes_data: List[Dict[str, Any]] = [
        {"idx": n, "id": ep.id, "title": ep.title, "script_content": ep.script_content}
        for n, ep in enumerate(episodes_in_order, start=1)
    ]

    target_episode_id: Optional[int] = None
    target_resolution_source = "none"
    target_episode_id_from_number: Optional[int] = None
    if requested_episode_number:
        candidate_ids = idx_candidates.get(int(requested_episode_number), [])
        if len(candidate_ids) > 1:
            logger.error(
                "[generate_episode_scripts] TARGET_RESOLUTION_AMBIGUOUS project_id=%s requested_episode_number=%s candidate_episode_ids=%s",
                project_id,
                requested_episode_number,
                candidate_ids,
            )
            raise HTTPException(
                status_code=409,
                detail=(
                    f"episode_number={requested_episode_number} is ambiguous; matched multiple episodes: {candidate_ids}. "
                    "Please clean up duplicate numbering before retrying."
                ),
            )
        ep_by_number = by_idx.get(int(requested_episode_number))
        if ep_by_number:
            target_episode_id_from_number = int(ep_by_number.id)
            target_episode_id = target_episode_id_from_number
            target_resolution_source = "episode_number"

    if req.episode_id:
        req_episode_id_int = int(req.episode_id)
        if requested_episode_number and target_episode_id_from_number is None:
            logger.error(
                "[generate_episode_scripts] TARGET_EPISODE_CONFLICT project_id=%s requested_episode_number=%s provided_episode_id=%s decision=reject_reason=episode_number_not_resolved",
                project_id,
                requested_episode_number,
                req_episode_id_int,
            )
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Cannot safely resolve episode_number={requested_episode_number} to a unique episode. "
                    "Refusing provided episode_id to avoid wrong overwrite."
                ),
            )

        if target_episode_id is None:
            target_episode_id = req_episode_id_int
            target_resolution_source = "episode_id"
        elif req_episode_id_int != target_episode_id:
            logger.error(
                "[generate_episode_scripts] TARGET_EPISODE_CONFLICT "
                f"project_id={project_id} requested_episode_number={requested_episode_number} "
                f"resolved_episode_id_by_number={target_episode_id} provided_episode_id={req_episode_id_int} "
                "decision=reject_conflict"
            )
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Conflict between episode_number={requested_episode_number} and episode_id={req_episode_id_int}. "
                    "Refusing to continue to prevent wrong overwrite."
                ),
            )

    call_meta["target_resolution_source"] = target_resolution_source
    call_meta["target_episode_id"] = target_episode_id

    if requested_episode_number and target_episode_id_from_number is None:
        if req.episode_id:
            logger.error(
                "[generate_episode_scripts] TARGET_RESOLUTION_FAILED project_id=%s requested_episode_number=%s provided_episode_id=%r reason=episode_number_not_resolved_refuse_fallback",
                project_id,
                requested_episode_number,
                int(req.episode_id) if req.episode_id else None,
            )
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Cannot safely resolve episode_number={requested_episode_number} to a unique episode. "
                    "Refusing fallback to episode_id to avoid wrong overwrite. "
                    "Please refresh episodes and retry."
                ),
            )

        # Single-episode generation with a non-existing episode number should auto-create that episode.
        create_idx = int(requested_episode_number)
        created_ep = Episode(project_id=project_id, title=f"Episode {create_idx}", script_content="")
        created_info = _episode_runtime_info_from_episode(created_ep)
        created_info["episode_script_episode_number"] = int(create_idx)
        created_ep.episode_info = created_info
        db.add(created_ep)
        db.commit()
        db.refresh(created_ep)

        created_episodes.append(int(created_ep.id))
        by_idx[create_idx] = created_ep
        idx_candidates.setdefault(create_idx, []).append(int(created_ep.id))
        by_title[str(created_ep.title or "").strip().lower()] = created_ep

        target_episode_id_from_number = int(created_ep.id)
        target_episode_id = target_episode_id_from_number
        target_resolution_source = "episode_number_autocreate"
        episodes_data.append({
            "idx": create_idx,
            "id": int(created_ep.id),
            "title": created_ep.title,
            "script_content": created_ep.script_content,
        })
        logger.info(
            "[generate_episode_scripts] TARGET_AUTOCREATED project_id=%s requested_episode_number=%s created_episode_id=%s",
            project_id,
            requested_episode_number,
            int(created_ep.id),
        )

    resolved_target_title = None
    if target_episode_id:
        for _ed in episodes_data:
            if int(_ed.get("id") or 0) == int(target_episode_id):
                resolved_target_title = _ed.get("title")
                break
        if resolved_target_title is None:
            _target_ep_dbg = db.query(Episode).filter(Episode.id == int(target_episode_id)).first()
            if _target_ep_dbg is not None:
                resolved_target_title = _target_ep_dbg.title
    logger.info(
        "[generate_episode_scripts] TARGET_RESOLUTION project_id=%s requested_episode_number=%r provided_episode_id=%r resolved_episode_id=%r source=%s resolved_title=%r",
        project_id,
        requested_episode_number,
        int(req.episode_id) if req.episode_id else None,
        target_episode_id,
        target_resolution_source,
        resolved_target_title,
    )

    if target_episode_id:
        episodes_data = [ed for ed in episodes_data if ed["id"] == target_episode_id]
        if not episodes_data:
            # Maybe the episode is not in the first N episodes but exists in DB
            target_ep = db.query(Episode).filter(Episode.id == target_episode_id, Episode.project_id == project_id).first()
            if target_ep:
                parsed_idx = _extract_episode_index(target_ep)
                fallback_idx = 1
                if isinstance(target_n, int) and target_n != 999:
                    fallback_idx = target_n + 1
                if requested_episode_number:
                    idx = int(requested_episode_number)
                else:
                    idx = int(parsed_idx) if parsed_idx else fallback_idx
                episodes_data = [{"idx": idx, "id": target_ep.id, "title": target_ep.title, "script_content": target_ep.script_content}]
            else:
                raise HTTPException(status_code=404, detail="Target episode not found in this project.")
    elif req.retry_failed_only:
        episodes_data = [ed for ed in episodes_data if ed["id"] in failed_episode_ids]

    # Single-episode generation should always overwrite the target episode,
    # even if a caller accidentally sends overwrite_existing=false.
    effective_overwrite_existing = bool(req.overwrite_existing) or bool(target_episode_id)
    call_meta["overwrite_existing_effective"] = effective_overwrite_existing

    run_status = {
        "project_id": project_id,
        "running": True,
        "prompt_filename": prompt_filename,
        "mode": "retry_failed_only" if req.retry_failed_only else "full",
        "overwrite_existing_effective": effective_overwrite_existing,
        "started_at": started_at_iso,
        "updated_at": started_at_iso,
        "episodes_target": target_n,
        "episodes_in_run": len(episodes_data),
        "processed": 0,
        "generated": 0,
        "failed": 0,
        "skipped": 0,
        "stop_requested": False,
        "stop_requested_at": None,
        "stopped_by_user": False,
        "results": [],
    }

    if req.retry_failed_only and len(episodes_data) == 0:
        run_status["running"] = False
        run_status["finished_at"] = now_bj_iso()
        run_status["message"] = "No failed episodes found from previous run"
        _persist_run_status(run_status)
        return {
            "success": True,
            "generation_success": True,
            "project_id": project_id,
            "episodes_target": target_n,
            "episodes_created": len(created_episodes),
            "created_episode_ids": created_episodes,
            "results": [],
            "errors": [],
            "message": "No failed episodes to retry",
            "debug_context": {
                "retry_failed_only": True,
                "previous_failed_count": len(failed_episode_ids),
            },
        }

    _persist_run_status(run_status)

    llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        user_id,
        function_name=(getattr(req, "function_name", None) or "script_analysis"),
        system_api_id=getattr(req, "system_api_id", None),
        context="generate_episode_scripts",
        project_global_info=project_global_info,
    )
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured in active settings")
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None

    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    def _safe_log_episode(action: str, payload: Dict[str, Any]) -> None:
        log_db = SessionLocal()
        try:
            log_action(
                log_db,
                user_id=user_id,
                user_name=user_name,
                action=action,
                details=json.dumps(payload, ensure_ascii=False),
            )
        except Exception as e:
            logger.warning(f"[generate_episode_scripts] failed to write {action} system log: {e}")
        finally:
            log_db.close()

    for ep_data in episodes_data:
        idx = ep_data["idx"]
        ep_id = ep_data["id"]
        ep_title = ep_data["title"]
        ep_script_content = ep_data["script_content"]
        if _is_stop_requested():
            stopped_at = now_bj_iso()
            run_status["stop_requested"] = True
            if not run_status.get("stop_requested_at"):
                run_status["stop_requested_at"] = stopped_at
            run_status["stopped_by_user"] = True
            run_status["stopped_at_episode_number"] = idx
            run_status["stop_acknowledged_at"] = stopped_at
            run_status["message"] = "Stopped by user request"

            remaining = [ed for ed in episodes_data if ed["idx"] >= idx]
            for ep_rest in remaining:
                j = ep_rest["idx"]
                results.append({
                    "episode_id": ep_rest["id"],
                    "episode_number": j,
                    "episode_title": ep_rest["title"],
                    "generated": False,
                    "skipped": True,
                    "reason": "stopped by user request",
                })
                run_status["processed"] = int(run_status.get("processed") or 0) + 1
                run_status["skipped"] = int(run_status.get("skipped") or 0) + 1
                run_status["results"].append({
                    "episode_id": ep_rest["id"],
                    "episode_number": j,
                    "episode_title": ep_rest["title"],
                    "status": "skipped",
                    "reason": "stopped by user request",
                })

            run_status["updated_at"] = stopped_at
            _persist_run_status(run_status)
            _safe_log_episode("GENERATE_EPISODE_SCRIPTS_ABORTED", {
                "project_id": project_id,
                "stopped_at_episode_number": idx,
                "reason": "stopped by user request",
            })
            break

        should_write = True
        if not req.retry_failed_only and not effective_overwrite_existing and (ep_script_content or "").strip():
            should_write = False

        if not should_write:
            logger.info(
                f"[generate_episode_scripts] SKIP episode_number={idx} episode_id={ep_id} title={ep_title!r} reason=existing_script"
            )
            logger.info(
                "[generate_episode_scripts] SKIP_DIAGNOSTICS "
                f"episode_number={idx} episode_id={ep_id} "
                f"target_episode_id={target_episode_id} "
                f"retry_failed_only={bool(req.retry_failed_only)} "
                f"overwrite_existing_requested={bool(req.overwrite_existing)} "
                f"overwrite_existing_effective={bool(effective_overwrite_existing)} "
                f"has_existing_script={bool((ep_script_content or '').strip())}"
            )
            _safe_log_episode("GENERATE_EPISODE_SCRIPT_SKIP", {
                "project_id": project_id,
                "episode_number": idx,
                "episode_id": ep_id,
                "episode_title": ep_title,
                "reason": "script_content already exists",
                "target_episode_id": target_episode_id,
                "retry_failed_only": bool(req.retry_failed_only),
                "overwrite_existing_requested": bool(req.overwrite_existing),
                "overwrite_existing_effective": bool(effective_overwrite_existing),
                "has_existing_script": bool((ep_script_content or "").strip()),
            })
            results.append({
                "episode_id": ep_id,
                "episode_number": idx,
                "episode_title": ep_title,
                "generated": False,
                "skipped": True,
                "reason": "script_content already exists",
            })
            run_status["processed"] = int(run_status.get("processed") or 0) + 1
            run_status["skipped"] = int(run_status.get("skipped") or 0) + 1
            run_status["updated_at"] = now_bj_iso()
            run_status["results"].append({
                "episode_id": ep_id,
                "episode_number": idx,
                "episode_title": ep_title,
                "status": "skipped",
                "reason": "script_content already exists",
            })
            _persist_run_status(run_status)
            continue

        reservation_tx = None

        relationships_block = ""
        if relationships:
            relationships_block = f"Character Relationships (Plain Text):\n{relationships}\n\n"

        episode_title_is_placeholder = _is_placeholder_episode_title(ep_title, idx)
        if episode_title_is_placeholder:
            episode_title_policy_block = (
                "Episode Title Policy (Hard Constraint):\n"
                f"- Current DB title is a placeholder: {ep_title}\n"
                "- You MUST create a specific, plot-relevant episode title in the H1 heading.\n"
                "- Do NOT output placeholder titles such as 'Episode N', 'EPN', '第N集', 'Untitled', or 'TBD'.\n\n"
            )
        else:
            episode_title_policy_block = (
                "Episode Title Policy (Hard Constraint):\n"
                f"- Current DB title reference: {ep_title}\n"
                "- Keep or refine this title, but keep it specific and plot-relevant.\n"
                "- Do NOT output placeholder titles such as 'Episode N', 'EPN', '第N集', 'Untitled', or 'TBD'.\n\n"
            )

        generation_scope_block = (
            "Generation Scope (Hard Constraint):\n"
            f"- Requested Episodes Count Input: {target_n}\n"
            f"- Episodes In Current Run: {len(episodes_data)}\n"
            f"- Current Call Episode Number: {idx}\n"
            f"- Current Call Episode Title: {ep_title}\n"
            "- You must generate ONLY the current call episode above.\n"
            "- Do NOT generate content for any other episode number in this response.\n"
            "- Any information about other episodes is reference context only.\n"
            "- Even in batch generation mode, each call must output exactly one episode script (the current episode only).\n\n"
            "Output Format Contract (Hard Constraint):\n"
            f"- The first non-empty line MUST be exactly one H1 heading: # {idx}-{{episode_title}}\n"
            "- Output MUST be pure Markdown text only.\n"
            "- Do NOT output JSON, XML, YAML, code fences, or any wrapper text.\n"
            "- Do NOT output any preface, analysis, explanation, or postscript.\n"
            "- The response MUST contain exactly one episode H1 heading; do NOT include any second episode heading.\n"
            "- Do NOT include headings for other episode numbers (e.g., 第X集 / EPX / Episode X).\n"
            "- Keep all content strictly within the current episode scope.\n\n"
        )

        script_title_policy_block = (
            "Script Title Policy (Hard Constraint):\n"
            f"- Canonical Script Title (fixed for this run): {project_title}\n"
            "- Treat this script title as immutable context for all generated output in this call.\n"
            "- Do NOT replace, rename, or invent another project-level script title.\n\n"
        )

        prev_episode_block = ""
        if idx > 1:
            prev_ep = by_idx.get(idx - 1)
            _prev_ep_db = db.query(Episode).filter(Episode.id == prev_ep.id).first() if prev_ep else None
            if not _prev_ep_db:
                 prev_ep_id_temp = next((ed["id"] for ed in episodes_data if ed.get("idx") == idx - 1), None)
                 if prev_ep_id_temp:
                     _prev_ep_db = db.query(Episode).get(prev_ep_id_temp)
            
            p_text = getattr(_prev_ep_db, "script_content", None) or getattr(prev_ep, "script_content", None)
            if p_text and p_text.strip():
                p_text_clean = p_text.strip()
                last_500 = p_text_clean[-500:]
                prev_episode_block = (
                    "Previous Episode Context (Constraint):\n"
                    f"- The previous episode (Episode {idx - 1}) script ends with the following text.\n"
                    "- You must ensure the opening of the current episode (Episode {idx}) connects logically with this ending.\n"
                    "```markdown\n"
                    f"...{last_500}\n"
                    "```\n\n"
                )

        episode_language = _pick_first_text(
            gi_basic_info.get("language"),
            gi_story_input.get("language"),
            project_global_info.get("language"),
        )
        reference_search_block = await _prepare_episode_script_reference_block(
            user_id=user_id,
            project_global_info=project_global_info,
            llm_config=llm_config,
            global_md=global_md,
            episode_number=idx,
            project_title=project_title,
            language=episode_language,
        )

        user_prompt = (
            f"Project Title: {project_title}\n"
            f"Episode Number: {idx}\n"
            f"Episode Title (current DB value): {ep_title}\n"
            f"Extra Notes: {req.extra_notes or ''}\n\n"
            f"{episode_product_specs_block}"
            f"{script_title_policy_block}"
            f"{generation_scope_block}"
            f"{episode_title_policy_block}"
            f"{prev_episode_block}"
            f"Global Story DNA (Markdown):\n{global_md}\n\n"
            f"Character Canon (Markdown):\n{character_canon_md}\n\n"
            f"{relationships_block}"
        )
        if reference_search_block.strip():
            user_prompt += (
                "Episode Reference Research (MUST consult before writing; localize, do not copy verbatim):\n"
                f"{reference_search_block}\n\n"
            )
        user_prompt += "Write the episode script draft now."

        try:
            sys_prompt_episode = sys_prompt.format(episode_number=idx, episode_title=ep_title)
        except Exception:
            sys_prompt_episode = sys_prompt

        if billing_service.is_token_pricing(db, "llm_chat", provider, model):
            est = billing_service.estimate_reserve_tokens_from_messages(
                [
                    {"role": "system", "content": sys_prompt_episode},
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
                    "item": "generate_episode_script",
                    "episode_id": ep_id,
                    "episode_number": idx,
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
            logger.info(
                f"[generate_episode_scripts] GENERATE episode_number={idx} episode_id={ep_id} title={ep_title!r}"
            )
            logger.info(
                f"[generate_episode_scripts] REQUEST_PAYLOAD episode_number={idx} episode_id={ep_id} "
                f"user_prompt_len={len(user_prompt)} sys_prompt_len={len(sys_prompt_episode)} "
                f"has_constraints_block={bool(constraints_block)} has_relationships_block={bool(relationships_block)} "
                f"has_reference_search_block={bool(reference_search_block)} reference_search_block_len={len(reference_search_block or '')}"
            )
            _release_db_connection(db, f"generate_episode_scripts_episode_{ep_id}_llm_call")
            generated_payload = await generate_markdown_with_retry(
                user_prompt=user_prompt,
                sys_prompt=sys_prompt_episode,
                llm_config=llm_config,
                strict_markdown=(req.strict_markdown is not False),
                require_h1=True,
                return_meta=True,
            )
            content = str((generated_payload or {}).get("content") or "").strip()
            if not content:
                raise RuntimeError("LLM returned empty content")

            content_first_line = ""
            for _line in content.splitlines():
                _candidate = str(_line or "").strip()
                if _candidate:
                    content_first_line = _candidate
                    break
            parsed_heading = _parse_episode_heading_from_markdown(content)
            llm_episode_number = parsed_heading.get("episode_number")
            llm_episode_title = str(parsed_heading.get("episode_title") or ep_title or "").strip()
            llm_heading = str(parsed_heading.get("raw_heading") or "").strip()
            logger.info(
                "[generate_episode_scripts] HEADING_PARSE episode_number=%s episode_id=%s project_episode_title=%r first_line=%r parsed_heading=%s llm_episode_number=%r llm_episode_title=%r used_project_title_fallback=%s",
                idx,
                ep_id,
                ep_title,
                content_first_line,
                json.dumps(parsed_heading, ensure_ascii=False),
                llm_episode_number,
                llm_episode_title,
                not bool(parsed_heading.get("episode_title")),
            )
            title_mismatch = bool(llm_episode_number) and int(llm_episode_number) != int(idx)
            if title_mismatch:
                logger.error(
                    f"[generate_episode_scripts] EPISODE_TITLE_MISMATCH_BLOCKED project_episode_number={idx} llm_episode_number={llm_episode_number} episode_id={ep_id} raw_heading={llm_heading!r}"
                )
                raise RuntimeError(
                    f"LLM episode heading mismatch: expected episode {idx}, got episode {llm_episode_number}. Import blocked."
                )

            usage = (generated_payload or {}).get("usage") if isinstance(generated_payload, dict) else {}
            if not usage:
                usage = billing_service.estimate_input_output_tokens_from_messages(
                    [
                        {"role": "system", "content": sys_prompt_episode},
                        {"role": "user", "content": user_prompt},
                        {"role": "assistant", "content": content},
                    ],
                    output_ratio=1.0,
                )
            billing_details = {
                "item": "generate_episode_script",
                "episode_id": ep_id,
                "episode_number": idx,
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
            _apply_llm_routing_to_billing_details(billing_details, generated_payload)

            persist_db = SessionLocal()
            try:
                if reservation_tx:
                    billing_service.settle_reservation(persist_db, _reservation_tx_id(reservation_tx), billing_details)
                else:
                    billing_service.deduct_credits(persist_db, user_id, "llm_chat", provider, model, billing_details)

                ep_db = persist_db.query(Episode).get(ep_id)
                if not ep_db:
                    raise RuntimeError(f"Episode {ep_id} not found in database for update.")
                previous_title = str(ep_db.title or "")
                ep_db.script_content = content
                if llm_episode_title:
                    ep_db.title = llm_episode_title
                ep_script_content = content
                ei = _episode_runtime_info_from_episode(ep_db)
                ei["episode_script_generated_at"] = now_bj_iso()
                ei["episode_script_episode_number"] = int(idx)
                if llm_episode_title:
                    ei["episode_title"] = llm_episode_title
                if generator_kind == "promo":
                    ei["episode_script_source"] = "promo_global_framework_plus_project_character_canon"
                else:
                    ei["episode_script_source"] = "project_global_framework_plus_project_character_canon"
                ep_db.episode_info = ei
                logger.info(
                    "[generate_episode_scripts] PERSIST_PREPARE episode_number=%s episode_id=%s previous_title=%r next_title=%r episode_info_title=%r script_chars=%s",
                    idx,
                    ep_id,
                    previous_title,
                    str(ep_db.title or ""),
                    str(ei.get("episode_title") or ""),
                    len(content),
                )
                persist_db.add(ep_db)
                persist_db.commit()
                persist_db.refresh(ep_db)

                persisted_episode_info = _episode_runtime_info_from_episode(ep_db)
                logger.info(
                    "[generate_episode_scripts] PERSISTED_READBACK episode_number=%s episode_id=%s db_title=%r episode_info_title=%r script_chars=%s",
                    idx,
                    ep_id,
                    str(ep_db.title or ""),
                    str(persisted_episode_info.get("episode_title") or ""),
                    len(str(ep_db.script_content or "")),
                )
            finally:
                persist_db.close()

            logger.info(
                f"[generate_episode_scripts] SUCCESS episode_number={idx} episode_id={ep_id} output_chars={len(content)}"
            )
            _safe_log_episode("GENERATE_EPISODE_SCRIPT_SUCCESS", {
                "project_id": project_id,
                "episode_number": idx,
                "episode_id": ep_id,
                "episode_title": ep_title,
                "llm_episode_number": llm_episode_number,
                "llm_episode_title": llm_episode_title,
                "title_mismatch": title_mismatch,
                "output_chars": len(content),
            })

            results.append({
                "episode_id": ep_id,
                "episode_number": idx,
                "project_episode_title": ep_title,
                "episode_title": llm_episode_title,
                "llm_episode_number": llm_episode_number,
                "llm_episode_title": llm_episode_title,
                "title_mismatch": title_mismatch,
                "generated": True,
                "skipped": False,
                "output_chars": len(content),
            })
            run_status["processed"] = int(run_status.get("processed") or 0) + 1
            run_status["generated"] = int(run_status.get("generated") or 0) + 1
            run_status["updated_at"] = now_bj_iso()
            run_status["results"].append({
                "episode_id": ep_id,
                "episode_number": idx,
                "project_episode_title": ep_title,
                "episode_title": llm_episode_title,
                "llm_episode_number": llm_episode_number,
                "llm_episode_title": llm_episode_title,
                "title_mismatch": title_mismatch,
                "status": "generated",
                "output_chars": len(content),
            })
            _persist_run_status(run_status)
        except HTTPException:
            if reservation_tx:
                cancel_db = SessionLocal()
                try:
                    billing_service.cancel_reservation(cancel_db, _reservation_tx_id(reservation_tx), "episode generation HTTPException")
                finally:
                    cancel_db.close()
            raise
        except Exception as e:
            if reservation_tx:
                cancel_db = SessionLocal()
                try:
                    billing_service.cancel_reservation(cancel_db, _reservation_tx_id(reservation_tx), str(e))
                finally:
                    cancel_db.close()
            logger.exception(f"[generate_episode_scripts] FAILED episode_number={idx} episode_id={ep_id} error={e}")
            _safe_log_episode("GENERATE_EPISODE_SCRIPT_FAILED", {
                "project_id": project_id,
                "episode_number": idx,
                "episode_id": ep_id,
                "episode_title": ep_title,
                "error": str(e),
            })
            errors.append({
                "episode_number": idx,
                "episode_id": ep_id,
                "episode_title": ep_title,
                "error": str(e),
            })
            results.append({
                "episode_id": ep_id,
                "episode_number": idx,
                "episode_title": ep_title,
                "generated": False,
                "skipped": False,
                "error": str(e),
            })
            run_status["processed"] = int(run_status.get("processed") or 0) + 1
            run_status["failed"] = int(run_status.get("failed") or 0) + 1
            run_status["updated_at"] = now_bj_iso()
            run_status["results"].append({
                "episode_id": ep_id,
                "episode_number": idx,
                "episode_title": ep_title,
                "status": "failed",
                "error": str(e),
            })
            _persist_run_status(run_status)

            if "PROHIBITED_CONTENT" in str(e):
                logger.warning(
                    f"[generate_episode_scripts] ABORT remaining episodes due to provider moderation block at episode_number={idx}"
                )
                _safe_log_episode("GENERATE_EPISODE_SCRIPTS_ABORTED", {
                    "project_id": project_id,
                    "stopped_at_episode_number": idx,
                    "reason": "provider moderation block (PROHIBITED_CONTENT)",
                })
                remaining = [ed for ed in episodes_data if ed["idx"] > idx]
                for ep_rest in remaining:
                    j = ep_rest["idx"]
                    results.append({
                        "episode_id": ep_rest["id"],
                        "episode_number": j,
                        "episode_title": ep_rest["title"],
                        "generated": False,
                        "skipped": True,
                        "reason": "aborted due to provider moderation block",
                    })
                    run_status["processed"] = int(run_status.get("processed") or 0) + 1
                    run_status["skipped"] = int(run_status.get("skipped") or 0) + 1
                    run_status["results"].append({
                        "episode_id": ep_rest["id"],
                        "episode_number": j,
                        "episode_title": ep_rest["title"],
                        "status": "skipped",
                        "reason": "aborted due to provider moderation block",
                    })
                run_status["updated_at"] = now_bj_iso()
                _persist_run_status(run_status)
                break

    duration_ms = int((datetime.utcnow() - started_at).total_seconds() * 1000)
    logger.info(
        f"[generate_episode_scripts] END project_id={project_id} user_id={user_id} "
        f"target={target_n} created={len(created_episodes)} generated={sum(1 for r in results if r.get('generated'))} "
        f"errors={len(errors)} duration_ms={duration_ms}"
    )

    try:
        summary = {
            "project_id": project_id,
            "target": target_n,
            "created": len(created_episodes),
            "generated": sum(1 for r in results if r.get("generated")),
            "errors": len(errors),
            "duration_ms": duration_ms,
        }
        end_log_db = SessionLocal()
        try:
            log_action(
                end_log_db,
                user_id=user_id,
                user_name=user_name,
                action="GENERATE_EPISODE_SCRIPTS_END",
                details=json.dumps(summary, ensure_ascii=False),
            )
        finally:
            end_log_db.close()
    except Exception as e:
        logger.warning(f"[generate_episode_scripts] failed to write END system log: {e}")

    response_payload = {
        "success": True,
        "generation_success": len(errors) == 0,
        "project_id": project_id,
        "episodes_target": target_n,
        "episodes_generated": sum(1 for r in results if r.get("generated")),
        "episodes_created": len(created_episodes),
        "created_episode_ids": created_episodes,
        "results": results,
        "errors": errors,
        "debug_context": {
            "has_character_relationships": has_relationships,
            "has_global_story_dna": bool(global_md),
            "character_canon_source": character_canon_source,
            "global_story_dna_length": len(global_md),
            "character_canon_length": len(character_canon_md),
            "constraints_keys": list(constraints_obj.keys()) if isinstance(constraints_obj, dict) else [],
            "script_mode": episode_script_mode,
            "target_audience": episode_target_audience,
            "episodes_count": target_n,
            "episode_duration_minutes": episode_duration_minutes,
        },
    }

    run_status["running"] = False
    run_status["finished_at"] = now_bj_iso()
    run_status["updated_at"] = run_status["finished_at"]
    run_status["errors"] = errors
    run_status["generation_success"] = len(errors) == 0
    _persist_run_status(run_status)

    logger.info(
        f"[generate_episode_scripts] RESPONSE success=True status_code=200 project_id={project_id} "
        f"generation_success={response_payload.get('generation_success')} errors={len(errors)}"
    )
    return response_payload


@router.get("/projects/{project_id}/script_generator/episodes/scripts/status", response_model=Dict[str, Any])
def get_project_episode_scripts_generation_status(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)

    gi = dict(project.global_info or {})
    status_payload = gi.get("episode_script_generation_status") if isinstance(gi, dict) else None
    if not isinstance(status_payload, dict):
        return {
            "project_id": project_id,
            "running": False,
            "processed": 0,
            "generated": 0,
            "failed": 0,
            "skipped": 0,
            "stop_requested": False,
            "stopped_by_user": False,
            "episodes_in_run": 0,
            "results": [],
        }
    status_results = status_payload.get("results") if isinstance(status_payload, dict) else []
    status_latest = status_results[-1] if isinstance(status_results, list) and status_results else {}
    logger.info(
        "[generate_episode_scripts] STATUS_READ project_id=%s running=%s processed=%s generated=%s failed=%s skipped=%s results_count=%s latest_episode_id=%r latest_episode_number=%r latest_episode_title=%r latest_project_episode_title=%r latest_llm_episode_title=%r latest_status=%r",
        project_id,
        bool(status_payload.get("running")),
        int(status_payload.get("processed") or 0),
        int(status_payload.get("generated") or 0),
        int(status_payload.get("failed") or 0),
        int(status_payload.get("skipped") or 0),
        len(status_results) if isinstance(status_results, list) else 0,
        status_latest.get("episode_id") if isinstance(status_latest, dict) else None,
        status_latest.get("episode_number") if isinstance(status_latest, dict) else None,
        status_latest.get("episode_title") if isinstance(status_latest, dict) else None,
        status_latest.get("project_episode_title") if isinstance(status_latest, dict) else None,
        status_latest.get("llm_episode_title") if isinstance(status_latest, dict) else None,
        status_latest.get("status") if isinstance(status_latest, dict) else None,
    )
    return status_payload


@router.post("/projects/{project_id}/script_generator/episodes/scripts/stop", response_model=Dict[str, Any])
def stop_project_episode_scripts_generation(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)

    gi = dict(project.global_info or {})
    status_key = "episode_script_generation_status"
    removed = status_key in gi
    gi.pop(status_key, None)
    project.global_info = gi
    db.add(project)
    db.commit()
    now_iso = now_bj_iso()

    try:
        log_action(
            db,
            user_id=current_user.id,
            user_name=current_user.username,
            action="GENERATE_EPISODE_SCRIPTS_STOP_REQUESTED",
            details=json.dumps({
                "project_id": project_id,
                "requested_at": now_iso,
            }, ensure_ascii=False),
        )
    except Exception as e:
        logger.warning(f"[generate_episode_scripts] failed to write STOP_REQUESTED system log: {e}")

    return {
        "success": True,
        "project_id": project_id,
        "running": False,
        "status": "canceled",
        "deleted": bool(removed),
        "message": "Force removed",
    }

@router.delete("/episodes/{episode_id}", status_code=200)
def delete_episode(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(
        Episode.id == episode_id,
        _active_episode_clause(),
    ).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    _require_project_access(db, episode.project_id, current_user, owner_only=True)

    if _is_soft_deleted(episode):
        return {"status": "deleted", "batch_id": None}

    now = now_bj_iso()
    batch_id = _start_deletion_batch(
        db,
        user_id=current_user.id,
        project_id=int(episode.project_id),
        episode_id=int(episode.id),
        action_type="episode",
        label=str(episode.title or f"Episode {episode_id}"),
    )
    _track_deletion_batch_items(db, batch_id, "episode", [episode.id])
    episode.is_deleted = True
    episode.deleted_at = now
    _soft_delete_episode_children(db, int(episode.id), now=now, batch_id=batch_id)
    _finalize_deletion_batch(db, batch_id)
    db.add(episode)
    db.commit()
    return {"status": "deleted", "batch_id": batch_id}

# --- Scenes ---

class SceneCreate(BaseModel):
    scene_no: str
    original_script_text: str
    scene_name: Optional[str] = None
    equivalent_duration: Optional[str] = None
    core_scene_info: Optional[str] = None
    environment_name: Optional[str] = None
    linked_characters: Optional[str] = None
    key_props: Optional[str] = None

class SceneBatchUpsertRequest(BaseModel):
    scenes: List[SceneCreate]
    recompute_cost: Optional[bool] = False
    # When True (default), skip rows whose scene_no already exists (do not overwrite).
    # Set False only when an intentional full replace/update is required.
    skip_existing: Optional[bool] = True

class ScenePurgeRequest(BaseModel):
    clear_progress: Optional[bool] = True

class SceneOut(BaseModel):
    id: int
    scene_no: str
    original_script_text: str
    scene_name: Optional[str]
    equivalent_duration: Optional[str]
    core_scene_info: Optional[str]
    environment_name: Optional[str]
    linked_characters: Optional[str]
    key_props: Optional[str]
    class Config:
        from_attributes = True


class SceneRegenerateRequest(BaseModel):
    user_requirements: str
    prompt_file: Optional[str] = "scene_regenerate.txt"
    system_prompt: Optional[str] = None
    max_scenes: Optional[int] = 4
    entity_only_mode: Optional[bool] = False


def _build_project_subject_inventory(
    db: Session,
    project_id: int,
    limit_per_type: int = 120,
    episode_id: Optional[int] = None,
) -> Dict[str, List[Dict[str, str]]]:
    """Build subject inventory for prompt-time reuse and recognition.

    When episode_id is provided, inventory is scoped to that episode only.
    """
    inventory: Dict[str, List[Dict[str, str]]] = {
        "characters": [], "covers": [],
        "props": [],
        "environments": [],
        "posters": [],
    }

    entities_query = db.query(Entity).filter(Entity.project_id == int(project_id))
    if episode_id is not None:
        entities_query = entities_query.filter(Entity.episode_id == int(episode_id))
    entities = entities_query.order_by(Entity.id.asc()).all()
    seen_keys = set()

    for ent in entities:
        normalized_type = _normalize_subject_entity_type(getattr(ent, "type", None))
        bucket = (
            "characters" if normalized_type == "character"
            else "props" if normalized_type == "prop"
            else "environments" if normalized_type == "environment"
            else "covers"
        )

        name = str(getattr(ent, "name", None) or "").strip()
        name_en = str(getattr(ent, "name_en", None) or "").strip()
        canonical_name = name or name_en
        if not canonical_name:
            continue

        key = f"{bucket}:{canonical_name.lower()}"
        if key in seen_keys:
            continue
        if len(inventory[bucket]) >= limit_per_type:
            continue
        seen_keys.add(key)

        if bucket == "characters":
            subject_ref = f"CHAR:[@{canonical_name}]"
        elif bucket == "props":
            subject_ref = f"PROP:[{canonical_name}]"
        else:
            subject_ref = f"ENV:[{canonical_name}]"

        anchor_description = str(getattr(ent, "anchor_description", None) or "").strip()

        narrative_hint = str(getattr(ent, "description", None) or "").strip()

        inventory[bucket].append({
            "id": str(getattr(ent, "id", "") or "").strip(),
            "name": canonical_name,
            "name_en": name_en,
            "subject_ref": subject_ref,
            "anchor_description": anchor_description,
            "description": narrative_hint,
            "type": normalized_type or bucket[:-1],
        })

    return inventory


def _format_project_subject_inventory_block(inventory: Dict[str, List[Dict[str, str]]]) -> str:
    type_names = {
        "characters": "角色",
        "props": "道具",
        "environments": "场景",
        "covers": "封面",
        "posters": "海报"
    }

    def _format_bucket(bucket_name: str) -> str:
        items = inventory.get(bucket_name) or []
        if not items:
            return f"{bucket_name}: (none)"

        type_cn = type_names.get(bucket_name, bucket_name)
        lines: List[str] = [f"{bucket_name} ({len(items)}):"]
        for item in items:
            bits: List[str] = []
            bits.append(f"资产实体类型={type_cn}")
            
            name = str(item.get("name") or "").strip()
            if name:
                bits.append(f"实体中文名={name}")
                
            name_en = str(item.get("name_en") or "").strip()
            if name_en:
                bits.append(f"实体英文名={name_en}")
                
            archetype = str(item.get("archetype") or "").strip()
            if archetype:
                bits.append(f"archetype={archetype}")
                
            lines.append(f"  - {' | '.join(bits)}")
        return "\n".join(lines)

    inventory_body = (
        "Existing Entity Inventory By Category:\n"
        f"{_format_bucket('characters')}\n"
        f"{_format_bucket('props')}\n"
        f"{_format_bucket('environments')}"
    )
    return (
        "[Project Existing Subject Index]\n"
        f"{wrap_injection_section('项目既有Subject Index', inventory_body)}"
    )


_PRIOR_ENTITY_DESIGN_TYPES = frozenset({"character", "prop", "environment"})


def _normalize_prior_entity_design_type(raw_type: Any) -> str:
    """Normalize entity/subject type for prior-prompt reuse; posters/covers excluded."""
    t = str(raw_type or "").strip().lower()
    t = re.sub(r"[\s_\-]+", "", t)
    if t in {"character", "characters", "char", "人物", "角色"}:
        return "character"
    if t in {"prop", "props", "item", "items", "道具", "物件"}:
        return "prop"
    if t in {"environment", "environments", "env", "scene", "scenes", "场景", "环境"}:
        return "environment"
    return ""


def _parse_subject_index_entries_for_prior_prompts(
    subject_index_text: Any,
    allowed_types: Optional[set] = None,
) -> List[Dict[str, str]]:
    """Extract (type, name_zh, name_en) rows from Subject Index for prior-prompt lookup."""
    text = sanitize_subject_index_text(subject_index_text)
    if not text:
        return []

    allowed = {
        _normalize_prior_entity_design_type(item)
        for item in (allowed_types or _PRIOR_ENTITY_DESIGN_TYPES)
    }
    allowed = {item for item in allowed if item in _PRIOR_ENTITY_DESIGN_TYPES}
    if not allowed:
        return []

    entries: List[Dict[str, str]] = []
    seen_keys: set = set()

    def _push(entity_type: str, name_zh: str, name_en: str = "") -> None:
        normalized_type = _normalize_prior_entity_design_type(entity_type)
        if normalized_type not in allowed:
            return
        zh = str(name_zh or "").strip()
        en = str(name_en or "").strip()
        canonical = zh or en
        if not canonical:
            return
        compare_key = subject_compare_key(canonical)
        if not compare_key:
            return
        dedupe_key = f"{normalized_type}:{compare_key}"
        if dedupe_key in seen_keys:
            return
        seen_keys.add(dedupe_key)
        entries.append({
            "type": normalized_type,
            "name_zh": zh,
            "name_en": en,
            "name": canonical,
        })

    for raw_line in str(text).splitlines():
        line = str(raw_line or "").replace("\ufeff", "").strip()
        if not line:
            continue
        line = re.sub(r"^\s*>\s*", "", line)
        line = re.sub(r"^\s*[-*+]\s+", "", line).strip()

        key_value_type_match = re.search(r"\bsubject_type\s*=\s*([^|`\n]+)", line, flags=re.IGNORECASE)
        if key_value_type_match:
            name_zh_match = re.search(r"\bsubject_name_(?:zh|exact)\s*=\s*([^|`\n]+)", line, flags=re.IGNORECASE)
            name_en_match = re.search(r"\bsubject_name_en\s*=\s*([^|`\n]+)", line, flags=re.IGNORECASE)
            if name_zh_match or name_en_match:
                _push(
                    key_value_type_match.group(1),
                    (name_zh_match.group(1) if name_zh_match else ""),
                    (name_en_match.group(1) if name_en_match else ""),
                )
                continue

        normalized_line = line.strip("|").strip()
        parts = [p.strip() for p in normalized_line.split("|")]
        if len(parts) >= 4 and re.match(r"^S\d+\b", normalized_line, flags=re.IGNORECASE):
            _push(parts[1], parts[2], parts[3] if len(parts) > 3 else "")

    return entries


def _build_prior_entity_generation_prompts_block(
    db: Session,
    project_id: int,
    subject_index_text: Any,
    allowed_types: Optional[set] = None,
    episode_id: Optional[int] = None,
) -> str:
    """Look up same-type/same-name entities in the current episode and inject generation_prompt_cn.

    Injection is strictly episode-scoped: entities from other episodes are never included.
    Poster/cover entities are never included.
    """
    try:
        project_id_int = int(project_id)
    except Exception:
        return ""
    if project_id_int <= 0:
        return ""
    try:
        episode_id_int = int(episode_id) if episode_id is not None else 0
    except Exception:
        episode_id_int = 0
    if episode_id_int <= 0:
        logger.info(
            "[analyze_scene] prior entity prompts skipped: episode_id required project_id=%s",
            project_id_int,
        )
        return ""

    subject_entries = _parse_subject_index_entries_for_prior_prompts(
        subject_index_text,
        allowed_types=allowed_types,
    )
    if not subject_entries:
        return ""

    entities = (
        db.query(Entity)
        .filter(
            Entity.project_id == project_id_int,
            Entity.episode_id == episode_id_int,
            _active_entity_clause(),
        )
        .all()
    )
    if not entities:
        return ""

    episode_by_id: Dict[int, Episode] = {}
    episode_row = db.query(Episode).filter(Episode.id == episode_id_int).first()
    if episode_row is not None:
        episode_by_id[episode_id_int] = episode_row

    def _entity_episode_sort_tuple(ent: Entity) -> Tuple[int, int, int]:
        """Prefer newer entity id when multiple same-name matches exist in-episode."""
        entity_id = int(getattr(ent, "id", 0) or 0)
        return (1, entity_id, entity_id)

    # Index project entities by type + compare-key for O(1) name matching.
    entities_by_type_key: Dict[str, List[Entity]] = {}
    for ent in entities:
        normalized_type = _normalize_prior_entity_design_type(getattr(ent, "type", None))
        if normalized_type not in _PRIOR_ENTITY_DESIGN_TYPES:
            continue
        if not str(getattr(ent, "generation_prompt_cn", None) or "").strip():
            continue
        alias_keys: set = set()
        for alias in (getattr(ent, "name", None), getattr(ent, "name_en", None)):
            alias_keys.update(subject_compare_key_variants(alias))
        for key in alias_keys:
            if not key:
                continue
            bucket_key = f"{normalized_type}:{key}"
            entities_by_type_key.setdefault(bucket_key, []).append(ent)

    prompt_lines: List[str] = []
    seen_refs: set = set()
    for entry in subject_entries:
        entity_type = entry.get("type") or ""
        candidate_keys: set = set()
        for alias in (entry.get("name_zh"), entry.get("name_en"), entry.get("name")):
            candidate_keys.update(subject_compare_key_variants(alias))
        matched: List[Entity] = []
        seen_entity_ids: set = set()
        for key in candidate_keys:
            if not key:
                continue
            for ent in entities_by_type_key.get(f"{entity_type}:{key}", []):
                ent_id = int(getattr(ent, "id", 0) or 0)
                if ent_id in seen_entity_ids:
                    continue
                seen_entity_ids.add(ent_id)
                matched.append(ent)
        if not matched:
            continue
        best = max(matched, key=_entity_episode_sort_tuple)
        prompt_cn = re.sub(r"\s+", " ", str(getattr(best, "generation_prompt_cn", None) or "")).strip()
        if not prompt_cn:
            continue

        canonical_name = str(
            entry.get("name")
            or getattr(best, "name", None)
            or getattr(best, "name_en", None)
            or ""
        ).strip()
        if not canonical_name:
            continue
        if entity_type == "character":
            subject_ref = f"CHAR:[@{canonical_name}]"
        elif entity_type == "prop":
            subject_ref = f"PROP:[{canonical_name}]"
        else:
            subject_ref = f"ENV:[{canonical_name}]"
        if subject_ref in seen_refs:
            continue
        seen_refs.add(subject_ref)

        ep_id = getattr(best, "episode_id", None)
        try:
            ep_id_int = int(ep_id) if ep_id is not None else 0
        except Exception:
            ep_id_int = 0
        episode = episode_by_id.get(ep_id_int) if ep_id_int else None
        episode_number = _resolve_episode_sort_number(episode) if episode else None
        episode_label = (
            f"EP{int(episode_number):02d}"
            if episode_number is not None
            else (f"episode_id={ep_id_int}" if ep_id_int > 0 else "episode=project")
        )
        prompt_lines.append(
            f"- {subject_ref} | source={episode_label} | entity_id={getattr(best, 'id', '')} | generation_prompt_cn={prompt_cn}"
        )

    if not prompt_lines:
        return ""

    body = (
        "# Prior Entity Image Prompts (Design Baseline)\n"
        "The following Chinese image-generation prompts come from existing same-type / same-name "
        "entities already stored in THIS episode only. Entities from other episodes are never injected. "
        "Poster/cover entities are excluded.\n"
        "\n"
        "## Mandatory reuse rules (read carefully)\n"
        "1) **Stable / identity attributes MUST follow the injected prior prompt** as the authoritative "
        "visual reference. Evolve from it; do not invent a conflicting redesign.\n"
        "   - Character: facial bone structure, facial features, skin undertone, body proportions, "
        "silhouette, race/ethnicity cues, and other appearance-identity anchors. Even for aging, injury, "
        "or state variants, evolve from the prior appearance description (same person continuity).\n"
        "   - Prop: core form, structure, material family, distinctive markings, and recognition anchors.\n"
        "   - Environment: spatial identity, key fixed fixtures, layout anchors, and recognisable "
        "architectural/set DNA.\n"
        "2) **Variable attributes are NOT constrained by the prior prompt** and may be redesigned freely "
        "to match the current Subject Index / episode story needs.\n"
        "   - Character: clothing, hairstyle (when story allows change), makeup look, temporary accessories, "
        "and other outfit/grooming choices.\n"
        "   - Prop: transient state overlays that do not rewrite core identity (unless Subject Index "
        "explicitly requires a new identity form).\n"
        "   - Environment: lighting mood, temporary dressing, and ephemeral atmosphere overlays that do "
        "not rewrite the space's fixed identity.\n"
        "3) Prefer continuity of recognition: a viewer who saw the prior entity should still recognise "
        "this entity after the allowed variable changes.\n"
        + "\n".join(prompt_lines)
        + "\n"
    )
    logger.info(
        "[analyze_scene] built prior entity generation prompts project_id=%s episode_id=%s subjects=%s matched=%s",
        project_id_int,
        episode_id_int,
        len(subject_entries),
        len(prompt_lines),
    )
    return wrap_injection_section("既有实体中文生图提示词", body)


def _normalize_scene_header(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"[*_`]+", "", text)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[\.:\-_/\\|]+", "", text)
    return text


def _clean_scene_table_cell(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = text.replace("\\|", "|")
    return html.unescape(text).strip()


def _parse_scene_rows_from_markdown(markdown_text: str) -> List[Dict[str, str]]:
    if not markdown_text:
        return []

    lines = [line.rstrip("\n\r") for line in str(markdown_text).splitlines()]
    if not lines:
        return []

    def _split_row(line: str) -> List[str]:
        return _split_scene_table_cells(line)

    def _reconcile_row(cols: List[str], headers: List[str]) -> List[str]:
        return _reconcile_scene_table_row_cells(cols, headers)

    def _find_idx(headers: List[str], aliases: List[str]) -> int:
        normalized_headers = [_normalize_scene_header(h) for h in headers]
        normalized_aliases = [_normalize_scene_header(a) for a in aliases]
        for idx, h in enumerate(normalized_headers):
            for alias in normalized_aliases:
                if alias and (h == alias or alias in h):
                    return idx
        return -1

    fallback_scene_headers = [
        "Episode ID",
        "Scene ID",
        "Scene No",
        "Scene Name",
        "Equivalent Duration",
        "Core Scene Info",
        "Original Script Text",
        "Environment Name",
        "Environment Relation",
        "Base Environment Reference",
        "Environment Delta",
        "Entry State",
        "Exit State",
        "Linked Characters",
        "Key Props",
    ]

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue

        headers = _split_row(stripped)
        j = i + 1

        # Fallback for headerless tables: separator + data rows only.
        if re.fullmatch(r"[\|\s:\-]+", stripped or ""):
            first_data_idx = -1
            first_data_cols: List[str] = []
            for k in range(i + 1, len(lines)):
                candidate = lines[k].strip()
                if not candidate:
                    continue
                if not candidate.startswith("|"):
                    break
                if re.fullmatch(r"[\|\s:\-]+", candidate or ""):
                    continue
                first_data_cols = _split_row(candidate)
                first_data_idx = k
                break

            if first_data_idx < 0 or not first_data_cols:
                continue

            needed = len(first_data_cols)
            headers = list(fallback_scene_headers[:needed])
            if needed > len(headers):
                headers.extend([f"Column {idx}" for idx in range(len(headers) + 1, needed + 1)])
            j = first_data_idx

        if len(headers) < 4:
            continue

        scene_no_idx = _find_idx(headers, ["Scene No", "场次", "场次号"])
        core_idx = _find_idx(headers, ["Core Scene Info", "核心场景信息", "Core Goal"])
        original_idx = _find_idx(headers, ["Original Script Text", "原始剧本文本", "Description", "Adapted Script Text", "改编剧本", "改编剧本文本"])

        if core_idx < 0 and original_idx < 0:
            continue

        if j == i + 1 and j < len(lines):
            separator = lines[j].strip()
            if separator.startswith("|") and re.fullmatch(r"[\|\s:\-]+", separator or ""):
                j += 1

        parsed_rows: List[Dict[str, str]] = []

        scene_name_idx = _find_idx(headers, ["Scene Name", "场景名称", "场景名", "Title"])
        duration_idx = _find_idx(headers, ["Equivalent Duration", "Duration", "时长"])
        env_name_idx = _find_idx(headers, ["Environment Name", "环境名称", "环境锚点"])
        linked_chars_idx = _find_idx(headers, ["Linked Characters", "关联角色", "角色"])
        key_props_idx = _find_idx(headers, ["Key Props", "关键道具", "道具"])

        while j < len(lines):
            row_line = lines[j].strip()
            if not row_line.startswith("|"):
                break
            if re.fullmatch(r"[\|\s:\-]+", row_line or ""):
                j += 1
                continue

            cols = _reconcile_row(_split_row(row_line), headers)
            if not cols:
                j += 1
                continue

            def _get(idx: int) -> str:
                return _clean_scene_table_cell(cols[idx]) if idx >= 0 and idx < len(cols) else ""

            row_payload = {
                "scene_no": _get(scene_no_idx),
                "scene_name": _get(scene_name_idx),
                "equivalent_duration": _get(duration_idx),
                "core_scene_info": _get(core_idx),
                "original_script_text": _get(original_idx),
                "environment_name": _get(env_name_idx),
                "linked_characters": _get(linked_chars_idx),
                "key_props": _get(key_props_idx),
            }

            if any(str(v or "").strip() for v in row_payload.values()):
                parsed_rows.append(row_payload)

            j += 1

        if parsed_rows:
            return parsed_rows

    return []


def _normalize_subject_entity_type(raw_type: Any) -> str:
    text = str(raw_type or "").strip().lower()
    if text in {"character", "characters", "char", "人物", "角色"}:
        return "character"
    if text in {"prop", "props", "道具", "物件"}:
        return "prop"
    if text in {"environment", "environments", "env", "场景", "环境"}:
        return "environment"
    if text in {"cover", "covers", "poster", "posters", "cover_poster", "封面", "封面海报"}:
        return "cover"
    return "character"


def _collect_llm_json_text_candidates(raw_text: str) -> List[str]:
    text = str(raw_text or "").strip()
    if not text:
        return []

    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
    candidates: List[str] = []
    seen: set = set()

    def _push(value: str) -> None:
        candidate = str(value or "").strip()
        if not candidate or candidate in seen:
            return
        seen.add(candidate)
        candidates.append(candidate)

    fence_re = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
    for match in fence_re.finditer(text):
        _push(match.group(1))

    open_fence_re = re.compile(r"```(?:json)?\s*([\s\S]*)$", re.IGNORECASE)
    open_match = open_fence_re.search(text)
    if open_match:
        _push(open_match.group(1))

    if text.startswith("{") or text.startswith("["):
        _push(text)

    entity_key_re = re.compile(r'"(?:characters|props|environments|covers|posters)"\s*:\s*[\[{]', re.IGNORECASE)
    key_match = entity_key_re.search(text)
    if key_match:
        obj_start = text.rfind("{", 0, key_match.start())
        if obj_start >= 0:
            depth = 0
            in_str = False
            escape = False
            for i in range(obj_start, len(text)):
                ch = text[i]
                if in_str:
                    if escape:
                        escape = False
                        continue
                    if ch == "\\":
                        escape = True
                        continue
                    if ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        _push(text[obj_start:i + 1])
                        break

    reasoning_prefix_re = re.compile(
        r"^\s*(?:i will|let me|let's|analysis|reasoning|thought process|"
        r"分析|思路|推理|下面|我将|我认为|接下来|我先|我会|现在|首先)\b",
        flags=re.IGNORECASE,
    )
    lines = text.splitlines()
    while lines and not str(lines[0] or "").strip():
        lines.pop(0)
    while lines and reasoning_prefix_re.match(str(lines[0] or "")):
        first_line = str(lines[0] or "").strip()
        if first_line.startswith("{") or first_line.startswith("[") or first_line.startswith("```") or entity_key_re.search(first_line):
            break
        lines.pop(0)
    trimmed_reasoning = "\n".join(lines).strip()
    if trimmed_reasoning and trimmed_reasoning != text:
        if trimmed_reasoning.startswith("{") or trimmed_reasoning.startswith("["):
            _push(trimmed_reasoning)
        key_match = entity_key_re.search(trimmed_reasoning)
        if key_match:
            obj_start = trimmed_reasoning.rfind("{", 0, key_match.start())
            if obj_start >= 0:
                depth = 0
                in_str = False
                escape = False
                for i in range(obj_start, len(trimmed_reasoning)):
                    ch = trimmed_reasoning[i]
                    if in_str:
                        if escape:
                            escape = False
                            continue
                        if ch == "\\":
                            escape = True
                            continue
                        if ch == '"':
                            in_str = False
                        continue
                    if ch == '"':
                        in_str = True
                        continue
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            _push(trimmed_reasoning[obj_start:i + 1])
                            break

    return candidates


def _extract_subjects_json_from_text(raw_text: str) -> Dict[str, Any]:
    payload: Dict[str, List[Dict[str, Any]]] = {
        "characters": [], "covers": [],
        "props": [],
        "environments": [],
        "posters": [],
    }
    text = str(raw_text or "").strip()
    if not text:
        return payload

    candidates: List[str] = []
    for candidate in _collect_llm_json_text_candidates(text):
        candidates.append(candidate)

    fence_re = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
    for m in fence_re.finditer(text):
        candidate = str(m.group(1) or "").strip()
        if candidate:
            candidates.append(candidate)

    if text.startswith("{") or text.startswith("["):
        candidates.append(text)

    def _extract_balanced_json_objects(source: str, max_count: int = 24) -> List[str]:
        objects: List[str] = []
        depth = 0
        in_str = False
        escape = False
        obj_start = -1
        for i, ch in enumerate(source):
            if in_str:
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch == '"':
                    in_str = False
                continue

            if ch == '"':
                in_str = True
                continue

            if ch == "{":
                if depth == 0:
                    obj_start = i
                depth += 1
                continue

            if ch == "}":
                if depth <= 0:
                    continue
                depth -= 1
                if depth == 0 and obj_start >= 0:
                    candidate = source[obj_start:i + 1].strip()
                    if candidate:
                        objects.append(candidate)
                        if len(objects) >= max_count:
                            break
                    obj_start = -1

        return objects

    def _build_section_only_candidate(source: str, section: str) -> Optional[str]:
        section_key = str(section or "").strip()
        if not section_key:
            return None
        key_re = re.compile(rf'"{re.escape(section_key)}"\s*:\s*\[', re.IGNORECASE)
        m = key_re.search(source)
        if not m:
            return None

        start_bracket = source.find("[", m.start())
        if start_bracket < 0:
            return None

        depth = 0
        in_str = False
        escape = False
        end_bracket = -1
        for i in range(start_bracket, len(source)):
            ch = source[i]
            if in_str:
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch == '"':
                    in_str = False
                continue

            if ch == '"':
                in_str = True
                continue
            if ch == "[":
                depth += 1
                continue
            if ch == "]":
                depth -= 1
                if depth == 0:
                    end_bracket = i
                    break

        if end_bracket < 0:
            return None

        array_text = source[start_bracket:end_bracket + 1].strip()
        if not array_text:
            return None

        skeleton: Dict[str, Any] = {
            "characters": [],
            "props": [],
            "environments": [],
            "covers": [],
            "posters": [],
        }
        try:
            parsed_array = json.loads(array_text, strict=False)
            if isinstance(parsed_array, list):
                skeleton[section_key] = parsed_array
                # Keep both aliases synchronized to reduce downstream miss.
                if section_key == "covers":
                    skeleton["posters"] = parsed_array
                elif section_key == "posters":
                    skeleton["covers"] = parsed_array
                return json.dumps(skeleton, ensure_ascii=False)
        except Exception:
            return None
        return None

    def _extract_object_after_label(source: str, label: str) -> Optional[str]:
        lower = source.lower()
        idx = lower.find(label.lower())
        if idx < 0:
            return None
        obj_start = source.find("{", idx)
        if obj_start < 0:
            return None

        depth = 0
        in_str = False
        escape = False
        for i in range(obj_start, len(source)):
            ch = source[i]
            if in_str:
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch == '"':
                    in_str = False
                continue

            if ch == '"':
                in_str = True
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return source[obj_start:i + 1]
        return None

    def _extract_object_near_key(source: str, key_name: str) -> Optional[str]:
        lower = source.lower()
        needle = f'"{key_name.lower()}"'
        start_pos = 0
        while True:
            idx = lower.find(needle, start_pos)
            if idx < 0:
                return None
            obj_start = source.rfind("{", 0, idx)
            if obj_start < 0:
                start_pos = idx + 1
                continue

            depth = 0
            in_str = False
            escape = False
            for i in range(obj_start, len(source)):
                ch = source[i]
                if in_str:
                    if escape:
                        escape = False
                        continue
                    if ch == "\\":
                        escape = True
                        continue
                    if ch == '"':
                        in_str = False
                    continue

                if ch == '"':
                    in_str = True
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return source[obj_start:i + 1]

            start_pos = idx + 1

    for key_name in ("characters", "props", "environments", "covers", "posters"):
        key_object = _extract_object_near_key(text, key_name)
        if key_object:
            candidates.append(key_object)

    labeled_object = _extract_object_after_label(text, "SUBJECTS_JSON")
    if labeled_object:
        candidates.append(labeled_object)

    for candidate in _extract_balanced_json_objects(text):
        lower = candidate.lower()
        if any(token in lower for token in ('"characters"', '"props"', '"environments"', '"covers"', '"posters"')):
            candidates.append(candidate)

    for section_name in ("characters", "props", "environments", "covers", "posters"):
        section_candidate = _build_section_only_candidate(text, section_name)
        if section_candidate:
            candidates.append(section_candidate)

    def _pick_text(*values: Any) -> str:
        for value in values:
            candidate = str(value or "").strip()
            if candidate:
                return candidate
        return ""

    def _normalize_item(section: str, item: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(item)
        normalized["name"] = _pick_text(
            item.get("name"),
            item.get("subject_name_exact"),
            item.get("subject_name"),
            item.get("name_zh"),
            item.get("display_name"),
            item.get("name_en"),
        )
        normalized["name_en"] = _pick_text(
            item.get("name_en"),
            item.get("english_name"),
            item.get("en_name"),
        )
        normalized["base_name_en"] = _pick_text(
            item.get("base_name_en"),
        )

        if section == "characters":
            description_cn = _pick_text(
                item.get("description_cn"),
                item.get("description"),
                item.get("narrative_description"),
                item.get("appearance_cn"),
            )
            if not description_cn:
                description_cn = "；".join(
                    value for value in [
                        _pick_text(item.get("appearance_cn")),
                        _pick_text(item.get("clothing")),
                        _pick_text(item.get("action_characteristics")),
                    ] if value
                )
            normalized["description_cn"] = description_cn
        elif section in ("props", "environments", "covers", "posters"):
            normalized["description_cn"] = _pick_text(
                item.get("description_cn"),
                item.get("description"),
                item.get("narrative_description"),
            )

        return normalized

    dedup_keys = set()
    for candidate in candidates:
        dedup_key = candidate[:2000]
        if dedup_key in dedup_keys:
            continue
        dedup_keys.add(dedup_key)

        try:
            # Fix trailing commas before loads
            cleaned_candidate = re.sub(r",\s*([\]}])", r"\1", candidate)
            parsed = json.loads(cleaned_candidate, strict=False)
        except Exception:
            continue

        parsed_objects = []
        if isinstance(parsed, list):
            grouped = {"characters": [], "props": [], "environments": [], "covers": [], "posters": []}
            for item in parsed:
                if not isinstance(item, dict):
                    continue

                # Support array-wrapped payloads, e.g. [{"characters": [...]}]
                has_bucket_keys = any(k in item for k in ("characters", "props", "environments", "covers", "posters"))
                wrapped_payload = item.get("entities") or item.get("subjects") or item.get("payload")
                if has_bucket_keys:
                    parsed_objects.append(item)
                    continue
                if isinstance(wrapped_payload, dict):
                    parsed_objects.append(wrapped_payload)
                    continue

                # Flat typed-array fallback, e.g. [{"type":"character", ...}, ...]
                t = str(item.get("type") or item.get("subject_type") or item.get("entity_type") or "").strip().lower()
                if t in {"character", "characters", "char", "role", "roles", "人物", "角色"}:
                    grouped["characters"].append(item)
                elif t in {"prop", "props", "item", "items", "道具", "物件"}:
                    grouped["props"].append(item)
                elif t in {"environment", "environments", "env", "scene", "场景", "环境"}:
                    grouped["environments"].append(item)
                elif t in {"poster", "posters", "cover", "covers", "海报", "封面"}:
                    grouped["covers"].append(item)

            if any(len(grouped.get(k) or []) > 0 for k in ("characters", "props", "environments", "covers", "posters")):
                parsed_objects.append(grouped)
        elif isinstance(parsed, dict):
            parsed_objects.append(parsed)

        for obj in parsed_objects:
            if not isinstance(obj, dict):
                continue
                
            for wrapper_key in ("entities", "subjects", "payload"):
                if wrapper_key in obj and isinstance(obj[wrapper_key], dict):
                    obj = obj[wrapper_key]
                    break
                    
            for section in ("characters", "props", "environments", "covers", "posters"):
                items = obj.get(section)
                if section == "covers" and not items and "posters" in obj:
                    items = obj.get("posters")
                if not isinstance(items, list):
                    continue
                normalized_items = []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    normalized = _normalize_item(section, item)
                    if not normalized.get("name") and not normalized.get("subject_no"):
                        continue
                    normalized_items.append(normalized)
                payload[section].extend(normalized_items)

    # Merge all candidates first, then deduplicate to avoid losing entities when
    # early candidates are partial/incomplete.
    for section in ("characters", "props", "environments", "covers", "posters"):
        seen_item_keys = set()
        deduped_items: List[Dict[str, Any]] = []
        for item in payload.get(section) or []:
            if not isinstance(item, dict):
                continue
            item_key = "|".join([
                str(item.get("subject_no") or "").strip().lower(),
                str(item.get("name") or "").strip().lower(),
                str(item.get("name_en") or "").strip().lower(),
                section,
            ])
            if item_key in seen_item_keys:
                continue
            seen_item_keys.add(item_key)
            deduped_items.append(item)
        payload[section] = deduped_items

    cover_poster_items: List[Dict[str, Any]] = []
    cover_poster_seen: set = set()
    for item in (payload.get("covers") or []) + (payload.get("posters") or []):
        if not isinstance(item, dict):
            continue
        item_key = "|".join([
            str(item.get("subject_no") or "").strip().lower(),
            str(item.get("name") or "").strip().lower(),
            str(item.get("name_en") or "").strip().lower(),
        ])
        if item_key in cover_poster_seen:
            continue
        cover_poster_seen.add(item_key)
        cover_poster_items.append(item)
    if cover_poster_items:
        payload["covers"] = cover_poster_items
        payload["posters"] = cover_poster_items

    return payload


@router.get("/episodes/{episode_id}/scenes", response_model=List[SceneOut])
def read_scenes(
    episode_id: int,
    scene_code: Optional[str] = None,
    keyword: Optional[str] = None,
    skip: int = 0,
    limit: int = 300,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Ownership check
    episode = db.query(Episode).filter(Episode.id == episode_id, _active_episode_clause()).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
        
    _require_project_access(db, episode.project_id, current_user)
        
    query = db.query(Scene).filter(Scene.episode_id == episode_id, _active_scene_clause())
    if scene_code:
        token = f"%{scene_code.strip()}%"
        query = query.filter(Scene.scene_no.ilike(token))
    if keyword:
        token = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                Scene.scene_name.ilike(token),
                Scene.environment_name.ilike(token),
                Scene.linked_characters.ilike(token),
                Scene.key_props.ilike(token),
            )
        )
    safe_skip = max(int(skip or 0), 0)
    safe_limit = max(1, min(int(limit or 300), 500))
    rows = _sort_scenes_by_scene_no(query.all())
    return rows[safe_skip:safe_skip + safe_limit]

@router.post("/episodes/{episode_id}/scenes", response_model=SceneOut)
def create_scene(
    episode_id: int,
    scene: SceneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    scene_api_started_perf = time.perf_counter()
    episode = db.query(Episode).filter(Episode.id == episode_id, _active_episode_clause()).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
        
    _require_project_access(db, episode.project_id, current_user)

    canonical_scene_no = _canonicalize_scene_no(
        getattr(scene, "scene_no", None),
        scene_id=getattr(scene, "scene_id", None) if hasattr(scene, "scene_id") else None,
    )
    if not canonical_scene_no:
        raise HTTPException(status_code=422, detail="SCENE_NO_REQUIRED")

    existing_scene = _find_active_scene_by_scene_no(
        db,
        episode_id=episode_id,
        scene_no=canonical_scene_no,
    )
    if existing_scene:
        # Import control: scene_no already present — abandon overwrite, return existing.
        # Also heal legacy alias rows (EP01_SC03) onto the canonical number ("3").
        if str(existing_scene.scene_no or "").strip() != canonical_scene_no:
            existing_scene.scene_no = canonical_scene_no
            db.add(existing_scene)
            db.commit()
            db.refresh(existing_scene)
        elapsed_ms = int((time.perf_counter() - scene_api_started_perf) * 1000)
        logger.info(
            "[SceneImportAPI] skip-existing | episode_id=%s | project_id=%s | scene_id=%s | scene_no=%s | elapsed_ms=%s",
            episode_id,
            episode.project_id,
            existing_scene.id,
            str(existing_scene.scene_no or "").strip(),
            elapsed_ms,
        )
        return existing_scene

    logger.info(
        "[SceneImportAPI] create-new start | episode_id=%s | project_id=%s | scene_no=%s | scene_name=%s",
        episode_id,
        episode.project_id,
        canonical_scene_no,
        str(scene.scene_name or "").strip(),
    )
    db_scene = Scene(
        episode_id=episode_id,
        scene_no=canonical_scene_no,
        original_script_text=scene.original_script_text,
        scene_name=scene.scene_name,
        equivalent_duration=scene.equivalent_duration,
        core_scene_info=scene.core_scene_info,
        environment_name=scene.environment_name,
        linked_characters=scene.linked_characters,
        key_props=scene.key_props
    )
    db.add(db_scene)
    try:
        _recompute_and_persist_project_cost_estimation(db, int(episode.project_id))
    except Exception as cost_exc:
        logger.warning("create_scene cost recompute skipped | project_id=%s err=%s", episode.project_id, cost_exc)
    try:
        db.commit()
    except Exception as commit_exc:
        db.rollback()
        raced = _find_active_scene_by_scene_no(
            db,
            episode_id=episode_id,
            scene_no=canonical_scene_no,
        )
        if raced is not None:
            logger.info(
                "[SceneImportAPI] create-new unique-race | episode_id=%s | project_id=%s | scene_id=%s | scene_no=%s | err=%s",
                episode_id,
                episode.project_id,
                raced.id,
                canonical_scene_no,
                commit_exc,
            )
            return raced
        raise
    db.refresh(db_scene)
    elapsed_ms = int((time.perf_counter() - scene_api_started_perf) * 1000)
    logger.info(
        "[SceneImportAPI] create-new done | episode_id=%s | project_id=%s | scene_id=%s | scene_no=%s | elapsed_ms=%s",
        episode_id,
        episode.project_id,
        db_scene.id,
        str(db_scene.scene_no or "").strip(),
        elapsed_ms,
    )
    return db_scene

@router.post("/episodes/{episode_id}/scenes/batch_upsert", response_model=Dict[str, Any])
def batch_upsert_scenes(
    episode_id: int,
    request: SceneBatchUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    started_perf = time.perf_counter()
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    input_scenes = list(request.scenes or [])
    if not input_scenes:
        return {
            "status": "ok",
            "episode_id": int(episode_id),
            "project_id": int(episode.project_id),
            "processed": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "elapsed_ms": int((time.perf_counter() - started_perf) * 1000),
            "scenes": [],
        }

    # Canonicalize + dedupe scene_no within the same import payload (keep first).
    # EP01_SC03 / 03 / 3 collapse to the same key so one episode cannot create aliases.
    deduped_input: List[Any] = []
    seen_input_scene_nos: set = set()
    for item in input_scenes:
        raw_scene_no = str(getattr(item, "scene_no", "") or "").strip()
        scene_no = _canonicalize_scene_no(raw_scene_no)
        if not scene_no:
            deduped_input.append(item)
            continue
        if hasattr(item, "scene_no"):
            item.scene_no = scene_no
        if scene_no in seen_input_scene_nos:
            logger.warning(
                "[SceneImportAPI] batch_upsert skip duplicate scene_no in payload | episode_id=%s scene_no=%s raw=%s",
                episode_id,
                scene_no,
                raw_scene_no,
            )
            continue
        seen_input_scene_nos.add(scene_no)
        deduped_input.append(item)
    input_scenes = deduped_input

    skip_existing = bool(getattr(request, "skip_existing", True))

    lookup_keys: List[str] = []
    for item in input_scenes:
        lookup_keys.extend(_scene_no_lookup_keys(getattr(item, "scene_no", None)))
    lookup_keys = list(dict.fromkeys(lookup_keys))
    existing_rows = (
        db.query(Scene)
        .filter(
            Scene.episode_id == int(episode_id),
            Scene.scene_no.in_(lookup_keys),
            _active_scene_clause(),
        )
        .all()
    ) if lookup_keys else []
    # Collapse active alias/duplicate rows onto one canonical scene_no; keep newest id.
    existing_by_no: Dict[str, Any] = {}
    duplicate_scene_ids: List[int] = []
    for row in existing_rows:
        canonical = _canonicalize_scene_no(getattr(row, "scene_no", None))
        if not canonical:
            continue
        if str(row.scene_no or "").strip() != canonical:
            row.scene_no = canonical
        prev = existing_by_no.get(canonical)
        if prev is None:
            existing_by_no[canonical] = row
            continue
        keep = row if int(getattr(row, "id", 0) or 0) >= int(getattr(prev, "id", 0) or 0) else prev
        drop = prev if keep is row else row
        existing_by_no[canonical] = keep
        duplicate_scene_ids.append(int(drop.id))
    if duplicate_scene_ids:
        now = now_bj_iso()
        db.query(Scene).filter(Scene.id.in_(duplicate_scene_ids)).update(
            {Scene.is_deleted: True, Scene.deleted_at: now},
            synchronize_session=False,
        )
        logger.info(
            "[SceneImportAPI] soft_deleted duplicate active scenes count=%s episode_id=%s",
            len(duplicate_scene_ids),
            episode_id,
        )

    created = 0
    updated = 0
    skipped = 0
    touched_scene_nos: List[str] = []

    for item in input_scenes:
        scene_no = _canonicalize_scene_no(getattr(item, "scene_no", None))
        if not scene_no:
            skipped += 1
            continue
        touched_scene_nos.append(scene_no)
        existing = existing_by_no.get(scene_no)
        if existing is not None:
            if str(existing.scene_no or "").strip() != scene_no:
                existing.scene_no = scene_no
            if skip_existing:
                skipped += 1
                continue
            existing.scene_name = item.scene_name
            existing.original_script_text = item.original_script_text
            existing.equivalent_duration = item.equivalent_duration
            existing.core_scene_info = item.core_scene_info
            existing.environment_name = item.environment_name
            existing.linked_characters = item.linked_characters
            existing.key_props = item.key_props
            updated += 1
            continue

        soft_deleted = (
            db.query(Scene)
            .filter(
                Scene.episode_id == int(episode_id),
                Scene.scene_no.in_(_scene_no_lookup_keys(scene_no)),
                Scene.is_deleted.is_(True),
            )
            .order_by(Scene.id.desc())
            .first()
        )
        if soft_deleted is not None:
            soft_deleted.is_deleted = False
            soft_deleted.deleted_at = None
            soft_deleted.scene_no = scene_no
            soft_deleted.scene_name = item.scene_name
            soft_deleted.original_script_text = item.original_script_text
            soft_deleted.equivalent_duration = item.equivalent_duration
            soft_deleted.core_scene_info = item.core_scene_info
            soft_deleted.environment_name = item.environment_name
            soft_deleted.linked_characters = item.linked_characters
            soft_deleted.key_props = item.key_props
            existing_by_no[scene_no] = soft_deleted
            updated += 1
            continue

        row = Scene(
            episode_id=int(episode_id),
            scene_no=scene_no,
            original_script_text=item.original_script_text,
            scene_name=item.scene_name,
            equivalent_duration=item.equivalent_duration,
            core_scene_info=item.core_scene_info,
            environment_name=item.environment_name,
            linked_characters=item.linked_characters,
            key_props=item.key_props,
        )
        db.add(row)
        existing_by_no[scene_no] = row
        created += 1

    if bool(request.recompute_cost):
        try:
            _recompute_and_persist_project_cost_estimation(db, int(episode.project_id))
        except Exception as cost_exc:
            logger.warning("batch_upsert_scenes cost recompute skipped | project_id=%s err=%s", episode.project_id, cost_exc)

    try:
        db.commit()
    except Exception as commit_exc:
        db.rollback()
        logger.error(
            "[SceneImportAPI] batch_upsert commit failed | episode_id=%s | project_id=%s | err=%s",
            episode_id,
            episode.project_id,
            commit_exc,
        )
        raise HTTPException(status_code=409, detail="SCENE_NO_UNIQUE_CONFLICT") from commit_exc

    result_scenes: List[Dict[str, Any]] = []
    unique_touched = list(dict.fromkeys([s for s in touched_scene_nos if s]))
    if unique_touched:
        refreshed = (
            db.query(Scene)
            .filter(
                Scene.episode_id == int(episode_id),
                Scene.scene_no.in_(unique_touched),
                _active_scene_clause(),
            )
            .all()
        )
        refreshed_by_no = {str(row.scene_no or "").strip(): row for row in refreshed}
        for scene_no in unique_touched:
            row = refreshed_by_no.get(scene_no)
            if row is None:
                continue
            result_scenes.append({
                "id": int(row.id),
                "scene_no": str(row.scene_no or ""),
                "scene_name": str(row.scene_name or ""),
            })

    elapsed_ms = int((time.perf_counter() - started_perf) * 1000)
    logger.info(
        "[SceneImportAPI] batch_upsert done | episode_id=%s | project_id=%s | processed=%s | created=%s | updated=%s | skipped=%s | elapsed_ms=%s",
        episode_id,
        episode.project_id,
        len(input_scenes),
        created,
        updated,
        skipped,
        elapsed_ms,
    )
    return {
        "status": "ok",
        "episode_id": int(episode_id),
        "project_id": int(episode.project_id),
        "processed": int(len(input_scenes)),
        "created": int(created),
        "updated": int(updated),
        "skipped": int(skipped),
        "elapsed_ms": elapsed_ms,
        "scenes": result_scenes,
    }

@router.put("/scenes/{scene_id}", response_model=SceneOut)
def update_scene(
    scene_id: int,
    scene_in: SceneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not db_scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    # Ownership
    episode = db.query(Episode).filter(Episode.id == db_scene.episode_id).first()
    _require_project_access(db, episode.project_id, current_user)

    update_data = scene_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_scene, field, value)
        
    db.add(db_scene)
    try:
        _recompute_and_persist_project_cost_estimation(db, int(episode.project_id))
    except Exception as cost_exc:
        logger.warning("update_scene cost recompute skipped | project_id=%s err=%s", episode.project_id, cost_exc)
    db.commit()
    db.refresh(db_scene)
    return db_scene


@router.post("/episodes/{episode_id}/scenes/purge", response_model=Dict[str, Any])
def purge_episode_scenes(
    episode_id: int,
    request: ScenePurgeRequest = ScenePurgeRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == int(episode_id), _active_episode_clause()).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user, owner_only=True)

    deleted_scenes = _hard_purge_episode_scenes(db, int(episode_id))
    removed_progress = 0
    if bool(getattr(request, "clear_progress", True)):
        removed_progress = _purge_episode_scene_progress(
            db,
            project_id=int(episode.project_id),
            episode_id=int(episode_id),
        )

    try:
        _recompute_and_persist_project_cost_estimation(db, int(episode.project_id))
    except Exception as cost_exc:
        logger.warning("purge_episode_scenes cost recompute skipped | project_id=%s err=%s", episode.project_id, cost_exc)

    db.commit()
    return {
        "status": "ok",
        "episode_id": int(episode_id),
        "project_id": int(episode.project_id),
        "deleted_scenes": deleted_scenes,
        "removed_progress_units": removed_progress,
    }


@router.delete("/scenes/{scene_id}", status_code=200)
def delete_scene(
    scene_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_scene = db.query(Scene).filter(Scene.id == scene_id, _active_scene_clause()).first()
    if not db_scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    episode = db.query(Episode).filter(Episode.id == db_scene.episode_id, _active_episode_clause()).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    _require_project_access(db, episode.project_id, current_user, owner_only=True)

    if _is_soft_deleted(db_scene):
        return {"status": "deleted", "batch_id": None}

    now = now_bj_iso()
    scene_label = str(db_scene.scene_name or db_scene.scene_no or f"Scene {scene_id}")
    batch_id = _start_deletion_batch(
        db,
        user_id=current_user.id,
        project_id=int(episode.project_id),
        episode_id=int(episode.id),
        action_type="scene",
        label=scene_label,
    )
    _soft_delete_scenes(db, scene_id=scene_id, now=now, batch_id=batch_id)
    _finalize_deletion_batch(db, batch_id)
    try:
        _recompute_and_persist_project_cost_estimation(db, int(episode.project_id))
    except Exception as cost_exc:
        logger.warning("delete_scene cost recompute skipped | project_id=%s err=%s", episode.project_id, cost_exc)
    db.commit()
    return {"status": "deleted", "batch_id": batch_id}


@router.post("/scenes/{scene_id}/regenerate", response_model=Dict[str, Any])
async def regenerate_scene(
    scene_id: int,
    req: SceneRegenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(regenerate_scene, user_id=current_user.id,
                            kind="regenerate_scene", scene_id=scene_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    db_scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not db_scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    episode = db.query(Episode).filter(Episode.id == db_scene.episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    project = _require_project_access(db, episode.project_id, current_user, owner_only=True)

    user_requirements = str(req.user_requirements or "").strip()
    if not user_requirements:
        raise HTTPException(status_code=400, detail="user_requirements is required")

    safe_max_scenes = max(1, min(int(req.max_scenes or 4), 8))
    entity_only_mode = bool(req.entity_only_mode)

    system_instruction = ""
    if req.system_prompt:
        system_instruction = str(req.system_prompt)
    else:
        prompt_filename = str(req.prompt_file or "scene_regenerate.txt").strip() or "scene_regenerate.txt"
        try:
            system_instruction = _resolve_prompt_text(prompt_filename)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Prompt file '{prompt_filename}' not found.")

    project_global_info = project.global_info if isinstance(project.global_info, dict) else {}
    project_title_str = str(project.title or "")
    episode_title_str = str(episode.title or "")

    def _project_info_str(key: str) -> str:
        value = project_global_info.get(key)
        if value is None:
            return ""
        if isinstance(value, list):
            return ", ".join([str(v or "").strip() for v in value if str(v or "").strip()])
        return str(value or "").strip()

    project_context_lines = [
        f"Project Title: {project_title_str}",
        f"Episode Title: {episode_title_str}",
    ]
    for key, label in (
        ("script_title", "Script Title"),
        ("series_episode", "Series Episode"),
        ("type", "Type"),
        ("base_positioning", "Base Positioning"),
        ("language", "Language"),
        ("Global_Style", "Global Style"),
        ("tone", "Tone"),
        ("lighting", "Lighting"),
        ("borrowed_films", "Borrowed Films"),
    ):
        value = _project_info_str(key)
        if value:
            project_context_lines.append(f"{label}: {value}")

    project_context_block = "\n".join(project_context_lines)

    scene_subject_seed_lines = [
        f"Environment Name Seed: {str(db_scene.environment_name or '').strip() or '(empty)'}",
        f"Linked Characters Seed: {str(db_scene.linked_characters or '').strip() or '(empty)'}",
        f"Key Props Seed: {str(db_scene.key_props or '').strip() or '(empty)'}",
    ]
    scene_subject_seeds_block = "\n".join(scene_subject_seed_lines)
    original_script_grounding = str(db_scene.original_script_text or "").strip()
    original_script_grounding_block = original_script_grounding or "(empty)"

    if entity_only_mode:
        regen_injection = (
            "\n\n"
            "[Regeneration Mode Injection]\n"
            "You are in SCENE ENTITY SUPPLEMENT MODE for one existing scene row.\n"
            "Primary objective: supplement the missing entities required by this scene according to [User Requirements] with highest priority.\n"
            "You MUST use project context + existing subject inventory + current scene content + original script grounding together as the extraction and verification basis.\n"
            "You MUST use Original Script Text as the ground-truth reference to verify whether linked characters are missing, and whether core scene information has major omissions or obvious visual-guidance errors.\n"
            "You MAY ignore minor wording differences that do not materially affect story meaning, staging, or visual guidance.\n"
            "If Original Script Text reveals materially missing characters, core actions, location anchors, or visual-guidance facts, you MUST repair the current scene row patch in markdown instead of only patching entity fields.\n"
            "You MUST follow scene_analysis subject extraction principles: reuse existing subjects first, only add truly missing subjects, and keep naming stable.\n"
            "scene_analysis.txt is the final authority for all subject/entity prompt rules. scene_regenerate.txt must be interpreted to stay aligned with scene_analysis.txt, and if any runtime summary conflicts, scene_analysis.txt wins.\n"
            "You MUST follow the full Chinese subject-sync rules defined in scene_regenerate.txt; if any shorter runtime summary conflicts with those file rules, the file rules win.\n"
            "You MUST complete hidden required entities when an action physically depends on a source object, carrier, receiver, or container; for example, pouring implies a source container, and taking a tissue implies a tissue source container.\n"
            "You MUST keep concrete scene-visible object coverage explicit; do not collapse tables, cups, doors, windows, lamps, phones, keyboards, and similar visible objects into vague generic categories.\n"
            "You MUST NOT merge two readable outfits or two readable identity states into one character item; if two states are needed, output two separate character entities with dependency logic.\n"
            "You MUST apply clothing hint recognition: touching, adjusting, lifting, fastening, or straightening a distinctive garment/accessory counts as evidence that the corresponding outfit state already exists and may require a separate character entity.\n"
            "You MUST preserve project language rules from the prompt file: do not force dialogue, visible text, labels, or screen text into English unless the project language actually requires English.\n"
            "Character generation prompts must preserve full-body framing with shoes visible as the asset baseline.\n"
            "Environment generation prompts must remain clean-plate, no-human prompts: no over-shoulder wording, no shoulder silhouettes, no human reflections, no human shadows, no role labels, and no CHAR references inside environment prompts.\n"
            "Output must be import-first and parser-safe: do NOT output explanations, bullets, validation notes, or code fences.\n"
            "The final output must contain exactly 2 parts only: first exactly 1 markdown scene row patch table, then exactly 1 SUBJECTS_JSON object.\n"
            "SUBJECTS_JSON must be exactly one valid JSON object with top-level keys characters, props, environments, covers, and all keys must always exist even when empty.\n"
            "For each entity item, use only the field contract defined by scene_regenerate.txt and scene_analysis.txt; if an identifier is included, only subject_no may appear as an extra import field.\n"
            "Missing optional strings must use empty string, missing arrays must use empty array, and you must not output null, undefined, metadata wrappers, or parser-hint fields.\n"
            "Return exactly 1 scene row patch in markdown table format plus one SUBJECTS_JSON object for missing entities only.\n"
            "In entity-only mode, scene/shots are not replaced; the row patch may update scene_name / equivalent_duration / core_scene_info / original_script_text / environment_name / linked_characters / key_props when needed to reflect corrected scene grounding and supplemented entities."
        )
    else:
        regen_injection = (
            "\n\n"
            "[Regeneration Mode Injection]\n"
            "You are in FULL SCENE REGENERATION MODE for one existing scene row.\n"
            "Primary objective: regenerate the scene according to [User Requirements] while also supplementing any newly required entities.\n"
            "You MUST use project context + existing subject inventory + current scene content + original script grounding together as the generation basis.\n"
            "You MUST use Original Script Text as the ground-truth reference to verify whether linked characters are missing, and whether core scene information has major omissions or obvious visual-guidance errors.\n"
            "You MAY ignore minor wording differences that do not materially affect story meaning, staging, or visual guidance.\n"
            "You MUST follow scene_analysis subject extraction principles: reuse existing subjects first, only add truly missing subjects, and keep naming stable.\n"
            "scene_analysis.txt is the final authority for all subject/entity prompt rules. scene_regenerate.txt must be interpreted to stay aligned with scene_analysis.txt, and if any runtime summary conflicts, scene_analysis.txt wins.\n"
            "You MUST follow the full Chinese subject-sync rules defined in scene_regenerate.txt; if any shorter runtime summary conflicts with those file rules, the file rules win.\n"
            "You MUST complete hidden required entities when an action physically depends on a source object, carrier, receiver, or container; for example, pouring implies a source container, and taking a tissue implies a tissue source container.\n"
            "You MUST keep concrete scene-visible object coverage explicit; do not collapse tables, cups, doors, windows, lamps, phones, keyboards, and similar visible objects into vague generic categories.\n"
            "You MUST NOT merge two readable outfits or two readable identity states into one character item; if two states are needed, output two separate character entities with dependency logic.\n"
            "You MUST apply clothing hint recognition: touching, adjusting, lifting, fastening, or straightening a distinctive garment/accessory counts as evidence that the corresponding outfit state already exists and may require a separate character entity.\n"
            "You MUST preserve project language rules from the prompt file: do not force dialogue, visible text, labels, or screen text into English unless the project language actually requires English.\n"
            "Character generation prompts must preserve full-body framing with shoes visible as the asset baseline.\n"
            "Environment generation prompts must remain clean-plate, no-human prompts: no over-shoulder wording, no shoulder silhouettes, no human reflections, no human shadows, no role labels, and no CHAR references inside environment prompts.\n"
            "Output must be import-first and parser-safe: do NOT output explanations, bullets, validation notes, or code fences.\n"
            "The final output must contain exactly 2 parts only: markdown scene row patch table(s) first, then exactly 1 SUBJECTS_JSON object.\n"
            "SUBJECTS_JSON must be exactly one valid JSON object with top-level keys characters, props, environments, covers, and all keys must always exist even when empty.\n"
            "For each entity item, use only the field contract defined by scene_regenerate.txt and scene_analysis.txt; if an identifier is included, only subject_no may appear as an extra import field.\n"
            "Missing optional strings must use empty string, missing arrays must use empty array, and you must not output null, undefined, metadata wrappers, or parser-hint fields.\n"
            f"Return 1 to {safe_max_scenes} regenerated scene rows in markdown table format plus one SUBJECTS_JSON object for missing entities only."
        )
    system_instruction = f"{system_instruction}{regen_injection}"

    scene_snapshot = (
        f"| Episode ID | Scene ID | Scene No. | Scene Name | Equivalent Duration | Core Scene Info | Original Script Text | Environment Name | Linked Characters | Key Props |\n"
        f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        f"| EP{int(episode.id):02d} | EP{int(episode.id):02d}_SCXX | {db_scene.scene_no or ''} | {db_scene.scene_name or ''} | {db_scene.equivalent_duration or ''} | {(db_scene.core_scene_info or '').replace(chr(10), '<br>')} | {(db_scene.original_script_text or '').replace(chr(10), '<br>')} | {db_scene.environment_name or ''} | {db_scene.linked_characters or ''} | {db_scene.key_props or ''} |"
    )

    existing_subject_inventory = _build_project_subject_inventory(
        db,
        int(project.id),
        episode_id=int(episode.id),
    )
    existing_subjects_block = _format_project_subject_inventory_block(existing_subject_inventory)

    existing_subjects_system_guard = (
        "\n\n"
        "[Existing Entity Reuse Guard - High Priority]\n"
        "The following entities already exist in the current episode scope and are dependency baselines.\n"
        "You MUST treat them as immutable references: do NOT rewrite, rename, redefine, or replace these entities.\n"
        "Do NOT output them as newly generated entities in SUBJECTS_JSON.\n"
        "SUBJECTS_JSON must include only truly missing entities.\n"
        f"{existing_subjects_block}"
    )
    system_instruction = f"{system_instruction}{existing_subjects_system_guard}"

    logger.info(
        "[regenerate_scene] entity injection scene_id=%s project_id=%s counts: characters=%s props=%s environments=%s covers=%s",
        scene_id,
        project.id,
        len(existing_subject_inventory.get("characters") or []),
        len(existing_subject_inventory.get("props") or []),
        len(existing_subject_inventory.get("environments") or []),
    )

    mode_specific_task_lines = (
        "- This task is mainly for supplementing missing entities of the current scene, not rewriting the whole scene.\n"
        "- However, you MUST also use Original Script Text to verify missing characters and major core scene info / visual-guidance omissions or obvious errors.\n"
        "- If such omissions or obvious errors exist, repair them in the single current-scene row patch markdown while keeping the scene identity stable.\n"
        "- Return a single current-scene row patch only; do not split into multiple rows in entity supplement mode.\n"
    ) if entity_only_mode else (
        f"- Regenerate this scene into 1 to {safe_max_scenes} scene rows when needed by user requirements.\n"
        "- Use Original Script Text to verify missing characters and major core scene info / visual-guidance omissions or obvious errors before finalizing the regenerated row(s).\n"
        "- Supplement any newly required entities at the same time.\n"
    )

    mode_specific_output_line = (
        "1) One scene markdown table row patch for the current scene (importable by scene parser).\n"
        if entity_only_mode else
        "1) Scene markdown table rows (importable by scene parser).\n"
    )

    current_scene_section = wrap_injection_section(
        "当前场景",
        "Current Scene (Markdown Row):\n" + scene_snapshot,
    )
    original_script_section = wrap_injection_section(
        "原始剧本依据",
        "[Original Script Grounding]\n" + original_script_grounding_block,
    )
    scene_subject_seeds_section = wrap_injection_section(
        "场景Subject种子",
        "[Current Scene Subject Seeds]\n" + scene_subject_seeds_block,
    )
    user_supplement_section = wrap_injection_section(
        "用户补充要求",
        "[User Supplement Requirements]\n" + user_requirements,
    )

    user_prompt = (
        f"{wrap_injection_section('项目信息', project_context_block)}\n\n"
        f"Source Scene Database ID: {db_scene.id}\n\n"
        f"{current_scene_section}\n\n"
        f"{original_script_section}\n\n"
        f"{scene_subject_seeds_section}\n\n"
        f"{existing_subjects_block}\n\n"
        f"{user_supplement_section}\n\n"
        "Task Instructions:\n"
        "- Use Project Context + Current Scene + Original Script Grounding + Current Scene Subject Seeds + System-level Subjects Inventory together.\n"
        "- Original Script Grounding is the primary truth source for checking whether the current scene is missing characters, missing key actions, missing location anchors, or has major core scene info / visual-guidance errors.\n"
        "- You may ignore minor wording differences that do not affect plot understanding or visual staging.\n"
        "- Follow scene_analysis extraction principles for characters / props / environments / covers.\n"
        "- scene_analysis.txt is the final authority for subject/entity prompt rules; interpret scene_regenerate.txt and runtime instructions so they stay aligned with scene_analysis.txt.\n"
        "- Follow the full Chinese subject-sync rules in scene_regenerate.txt; if this runtime summary is shorter, the file rules still apply in full.\n"
        "- Prioritize User Supplement Requirements over the old scene wording when deciding what is missing.\n"
        f"{mode_specific_task_lines}"
        "- Treat System-level Subjects Inventory as authoritative dependency baselines already available in project DB.\n"
        "- Existing entities are immutable references: MUST NOT be rewritten, renamed, redefined, or replaced.\n"
        "- Reuse subject_ref tokens and keep anchor semantics consistent for recognition continuity.\n"
        "- They can be referenced/reused directly, but MUST NOT be regenerated as new entities.\n"
        "- MUST supplement complete missing subjects required by the current scene from scene content + user requirements, and return JSON with keys: characters, props, environments, covers.\n"
        "- Subject extraction MUST NOT depend on whether the subject already has an image or image_url. Even subjects with no image asset yet MUST still be extracted and returned when they are required by the scene.\n"
        "- Every returned subject item must include import-usable names and description: name + name_en + description_cn are mandatory content fields. Missing image assets are allowed; missing names/descriptions are not.\n"
        "- Hidden required entities must be completed when the action semantics require them; do not omit source containers, receivers, or scene-required support objects merely because they were implicit in the text.\n"
        "- Keep scene-visible concrete object coverage explicit; if a table, cup, door, window, lamp, phone, keyboard, or similar object matters to the scene, account for it specifically rather than replacing it with a vague category label.\n"
        "- Never combine two readable wardrobe or identity states into one character JSON item.\n"
        "- Clothing hint recognition is mandatory: touching, adjusting, lifting, fastening, or straightening a distinctive garment/accessory counts as evidence for that outfit state and may require a separate character entity.\n"
        "- Preserve the project language rules from the prompt file; do not convert visible language content to English unless the project language actually requires English.\n"
        "- Character prompts must remain full-body with shoes visible.\n"
        "- Environment prompts must stay no-human and clean-plate: no OTS shoulder wording, no human residue, no role labels, and no CHAR references.\n"
        "- SUBJECTS_JSON must contain ONLY missing/new entities that are not already listed in System-level Subjects Inventory.\n"
        "- Keep existing subject names stable; do not duplicate existing names in SUBJECTS_JSON.\n"
        "- If no missing entity exists for a category, return an empty array for that category.\n\n"
        "- Output must be parser-safe and directly importable: no explanations, no bullets outside the requested structure, no code fences, no metadata wrapper objects.\n"
        "- SUBJECTS_JSON top-level keys must be exactly characters, props, environments, covers, and all keys must always exist.\n"
        "- Each entity item may use only the prompt-defined import fields; if an identifier is included, only subject_no may be added as an extra import field.\n"
        "- Missing optional strings must use empty string, missing arrays must use empty array, and null/undefined are forbidden.\n\n"
        "Required Output Format:\n"
        f"{mode_specific_output_line}"
        "2) SUBJECTS_JSON: one valid JSON object only, with complete import-ready fields (same semantics as system subjects import):\n"
        "{\n"
        "  \"characters\": [{\"name\": \"...\", \"name_en\": \"...\", \"description_cn\": \"...\", \"gender\": \"...\", \"role\": \"...\", \"archetype\": \"...\", \"appearance_cn\": \"...\", \"clothing\": \"...\", \"action_characteristics\": \"...\", \"generation_prompt_cn\": \"...\", \"generation_prompt_en\": \"...\", \"negative_prompt_en\": \"...\", \"anchor_description\": \"...\", \"visual_dependencies\": [], \"dependency_strategy\": {\"type\": \"...\", \"logic\": \"...\"}}],\n"
        "  \"props\": [{\"name\": \"...\", \"name_en\": \"...\", \"description_cn\": \"...\", \"generation_prompt_cn\": \"...\", \"generation_prompt_en\": \"...\", \"negative_prompt_en\": \"...\", \"anchor_description\": \"...\", \"visual_dependencies\": [], \"dependency_strategy\": {\"type\": \"...\", \"logic\": \"...\"}}],\n"
        "  \"environments\": [{\"name\": \"...\", \"name_en\": \"...\", \"atmosphere\": \"...\", \"visual_params\": \"...\", \"description_cn\": \"...\", \"generation_prompt_cn\": \"...\", \"generation_prompt_en\": \"...\", \"negative_prompt_en\": \"...\", \"anchor_description\": \"...\", \"visual_dependencies\": [], \"dependency_strategy\": {\"type\": \"...\", \"logic\": \"...\"}}]\n"
        "}\n"
        "Image/image_url fields are NOT required for extraction and may be omitted. Name and description fields are mandatory for each entity item. Missing other optional fields should use empty string / empty array / empty object.\n"
        "No prose outside these two parts."
    )

    logger.info(
        "[regenerate_scene] prompt injection markers scene_id=%s has_existing_block_in_user_prompt=%s has_existing_guard_in_system_prompt=%s",
        scene_id,
        "System-level Subjects Inventory" in user_prompt,
        "[Existing Entity Reuse Guard - High Priority]" in system_instruction,
    )

    current_user_id = current_user.id
    episode_id = episode.id
    project_id = project.id

    old_scene_no = str(db_scene.scene_no or db_scene.id)
    fallback_original_script = str(db_scene.original_script_text or "").strip()
    fallback_scene_name = db_scene.scene_name
    fallback_duration = db_scene.equivalent_duration
    fallback_core_info = db_scene.core_scene_info
    fallback_env_name = db_scene.environment_name
    fallback_linked_chars = db_scene.linked_characters
    fallback_key_props = db_scene.key_props

    llm_config = agent_service.get_active_llm_config(current_user_id)
    llm_config = _inject_project_creativity_temperature(
        llm_config,
        project.global_info,
        context="regenerate_scene",
    )
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None
    billing_service.check_balance(db, current_user_id, "llm_chat", provider, model)

    _release_db_connection(db, "regenerate_scene_llm_call")
    resp = await llm_service.generate_content_with_fallback(user_prompt, system_instruction, llm_config)
    raw = str((resp or {}).get("content") or "").strip()
    if not raw:
        raise HTTPException(status_code=502, detail="LLM returned empty content")

    cleaned = sanitize_llm_markdown_output(raw)
    parsed_rows = _parse_scene_rows_from_markdown(cleaned)
    if not parsed_rows and not entity_only_mode:
        raise HTTPException(status_code=502, detail="Failed to parse regenerated scene markdown table")

    subjects_json = _extract_subjects_json_from_text(raw)
    if not any(len(subjects_json.get(k) or []) > 0 for k in ("characters", "props", "environments", "covers", "posters")):
        subjects_json = _extract_subjects_json_from_text(cleaned)

    parsed_rows = parsed_rows[:safe_max_scenes]

    created_scenes: List[Scene] = []
    try:
        if entity_only_mode:
            preferred_row = parsed_rows[0] if parsed_rows else {}
            if not isinstance(preferred_row, dict):
                preferred_row = {}

            db_scene = db.query(Scene).filter(Scene.id == scene_id).first()
            if db_scene:
                db_scene.scene_name = str(preferred_row.get("scene_name") or "").strip() or fallback_scene_name
                db_scene.original_script_text = str(preferred_row.get("original_script_text") or "").strip() or fallback_original_script
                db_scene.equivalent_duration = str(preferred_row.get("equivalent_duration") or "").strip() or fallback_duration
                db_scene.core_scene_info = str(preferred_row.get("core_scene_info") or "").strip() or fallback_core_info
                db_scene.environment_name = str(preferred_row.get("environment_name") or "").strip() or fallback_env_name
                db_scene.linked_characters = str(preferred_row.get("linked_characters") or "").strip() or fallback_linked_chars
                db_scene.key_props = str(preferred_row.get("key_props") or "").strip() or fallback_key_props
    
                db.add(db_scene)
                db.commit()
                created_scenes = [db_scene]
        else:
            _soft_delete_scenes(db, scene_id=scene_id)

            total_new = len(parsed_rows)
            for idx, row in enumerate(parsed_rows, start=1):
                if total_new > 1:
                    next_scene_no = f"{old_scene_no}.{idx}"
                else:
                    next_scene_no = str(row.get("scene_no") or "").strip() or old_scene_no

                original_script_text = str(row.get("original_script_text") or "").strip() or fallback_original_script
                if not original_script_text:
                    original_script_text = f"Scene regenerated from {old_scene_no}"

                new_scene = Scene(
                    episode_id=episode_id,
                    scene_no=next_scene_no,
                    scene_name=str(row.get("scene_name") or "").strip() or fallback_scene_name,
                    original_script_text=original_script_text,
                    equivalent_duration=str(row.get("equivalent_duration") or "").strip() or fallback_duration,
                    core_scene_info=str(row.get("core_scene_info") or "").strip() or fallback_core_info,
                    environment_name=str(row.get("environment_name") or "").strip() or fallback_env_name,
                    linked_characters=str(row.get("linked_characters") or "").strip() or fallback_linked_chars,
                    key_props=str(row.get("key_props") or "").strip() or fallback_key_props,
                )
                db.add(new_scene)
                created_scenes.append(new_scene)

            db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to replace scene: {str(e)}")

    for item in created_scenes:
        db.refresh(item)

    usage = (resp or {}).get("usage") if isinstance(resp, dict) else None
    details: Dict[str, Any] = {
        "item": "scene_regenerate",
        "source_scene_id": scene_id,
        "generated_scene_count": len(created_scenes),
    }
    if isinstance(usage, dict):
        details.update(usage)
        if "prompt_tokens" in details and "input_tokens" not in details:
            details["input_tokens"] = details.get("prompt_tokens", 0)
        if "completion_tokens" in details and "output_tokens" not in details:
            details["output_tokens"] = details.get("completion_tokens", 0)
    billing_service.deduct_credits(db, current_user_id, "llm_chat", provider, model, details)

    return {
        "replaced_scene_id": scene_id,
        "episode_id": episode_id,
        "project_id": project_id,
        "entity_only_mode": entity_only_mode,
        "scene_changes_applied": not entity_only_mode,
        "generated_scene_count": len(created_scenes),
        "raw_markdown": cleaned,
        "subjects_json": subjects_json,
        "subjects_json_count": {
            "characters": len(subjects_json.get("characters") or []),
            "props": len(subjects_json.get("props") or []),
            "environments": len(subjects_json.get("environments") or []),
            "covers": len(subjects_json.get("covers") or []),
            "posters": len(subjects_json.get("posters") or []),
        },
        "scenes": [
            {
                "id": s.id,
                "scene_no": s.scene_no,
                "scene_name": s.scene_name,
                "equivalent_duration": s.equivalent_duration,
                "core_scene_info": s.core_scene_info,
                "original_script_text": s.original_script_text,
                "environment_name": s.environment_name,
                "linked_characters": s.linked_characters,
                "key_props": s.key_props,
            }
            for s in created_scenes
        ],
    }

# --- Shots ---

class ShotCreate(BaseModel):
    shot_id: str
    shot_name: Optional[str] = None
    start_frame: Optional[str] = None
    end_frame: Optional[str] = None
    video_content: Optional[str] = None
    duration: Optional[str] = None
    associated_entities: Optional[str] = None
    scene_code: Optional[str] = None # 'Scene ID' from header user input
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    shot_logic_cn: Optional[str] = None
    keyframes: Optional[str] = None
    
    # Optional legacy/AI fields
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    prompt: Optional[str] = None
    technical_notes: Optional[str] = None

class ShotBatchCreateItem(BaseModel):
    scene_id: int
    shot: ShotCreate

class ShotBatchCreateRequest(BaseModel):
    items: List[ShotBatchCreateItem]
    recompute_cost: Optional[bool] = False
    # When True (default), skip entire scene if it already has active shots.
    skip_existing_scene_shots: Optional[bool] = True


class ShotUpdate(BaseModel):
    shot_id: Optional[str] = None
    shot_name: Optional[str] = None
    start_frame: Optional[str] = None
    end_frame: Optional[str] = None
    video_content: Optional[str] = None
    duration: Optional[str] = None
    associated_entities: Optional[str] = None
    scene_code: Optional[str] = None
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    shot_logic_cn: Optional[str] = None
    keyframes: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    prompt: Optional[str] = None
    technical_notes: Optional[str] = None

class ShotOut(BaseModel):
    id: int
    scene_id: int
    project_id: Optional[int]
    episode_id: Optional[int]
    shot_id: Optional[str]
    shot_name: Optional[str]
    start_frame: Optional[str]
    end_frame: Optional[str]
    video_content: Optional[str]
    duration: Optional[str]
    associated_entities: Optional[str]
    shot_logic_cn: Optional[str]
    keyframes: Optional[str]
    
    scene_code: Optional[str]

    image_url: Optional[str]
    video_url: Optional[str]
    prompt: Optional[str]
    technical_notes: Optional[str]
    end_frame_url: Optional[str] = None
    prompt_preview_cn: Optional[str] = None
    prompt_preview_en: Optional[str] = None
    is_compact: Optional[bool] = None
    
    class Config:
        from_attributes = True


_SHOT_LIST_COMPACT_TECH_KEYS = (
    "end_frame_url",
    "video_prompt_cn",
    "prompt_cn",
    "start_frame_cn",
    "end_frame_cn",
    "keyframes",
    "keyframes_cn",
    "keyframe_images",
    "voiceover_url",
    # Persist storyboard extract / preview media in compact list payloads so
    # reopening a shot can show previously captured frames without waiting on hydrate.
    "prev_shot_frames",
    "prev_shot_frame_images",
    "prev_shot_frame_meta",
    "multi_panel_image_url",
    "multi_panel_image_preset",
    "storyboard_url",
)
def _compact_shot_list_technical_notes(raw_notes: Any) -> Tuple[Optional[str], str, str]:
    notes = _asset_meta_to_dict(raw_notes)
    if not notes:
        return None, "", ""

    compact_notes: Dict[str, Any] = {}
    end_frame_url = str(notes.get("end_frame_url") or "").strip()
    prompt_preview_cn = ""

    for key in _SHOT_LIST_COMPACT_TECH_KEYS:
        if key not in notes:
            continue
        value = notes.get(key)
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                continue
            if key in {"video_prompt_cn", "prompt_cn", "start_frame_cn", "end_frame_cn"} and not prompt_preview_cn:
                prompt_preview_cn = normalized
            compact_notes[key] = normalized
            continue
        if isinstance(value, list):
            normalized_list = [str(item or "").strip() for item in value if str(item or "").strip()]
            if normalized_list:
                compact_notes[key] = normalized_list
            continue
        if value is not None:
            compact_notes[key] = value

    if end_frame_url and "end_frame_url" not in compact_notes:
        compact_notes["end_frame_url"] = end_frame_url

    compact_payload = json.dumps(compact_notes, ensure_ascii=False) if compact_notes else None
    return compact_payload, end_frame_url, prompt_preview_cn


def _build_compact_shot_payload(row: Any, db: Session) -> Dict[str, Any]:
    compact_notes, end_frame_url, prompt_preview_cn = _compact_shot_list_technical_notes(getattr(row, "technical_notes", None))
    image_url = _refresh_managed_media_url(getattr(row, "image_url", None), db)
    video_url = _refresh_managed_media_url(getattr(row, "video_url", None), db)
    end_frame_url = _refresh_managed_media_url(end_frame_url, db)

    prompt_preview_en = ""
    for candidate in (
        getattr(row, "video_content", None),
        getattr(row, "prompt", None),
        getattr(row, "start_frame", None),
        getattr(row, "end_frame", None),
        prompt_preview_cn,
        getattr(row, "shot_logic_cn", None),
    ):
        normalized = str(candidate or "").strip()
        if normalized:
            prompt_preview_en = normalized
            break

    return {
        "id": getattr(row, "id", None),
        "scene_id": getattr(row, "scene_id", None),
        "project_id": getattr(row, "project_id", None),
        "episode_id": getattr(row, "episode_id", None),
        "shot_id": getattr(row, "shot_id", None),
        "shot_name": getattr(row, "shot_name", None),
        "start_frame": getattr(row, "start_frame", None),
        "end_frame": getattr(row, "end_frame", None),
        "video_content": getattr(row, "video_content", None),
        "duration": getattr(row, "duration", None),
        "associated_entities": getattr(row, "associated_entities", None),
        "shot_logic_cn": getattr(row, "shot_logic_cn", None),
        "keyframes": getattr(row, "keyframes", None),
        "scene_code": getattr(row, "scene_code", None),
        "image_url": image_url or None,
        "video_url": video_url or None,
        "prompt": getattr(row, "prompt", None),
        "technical_notes": compact_notes,
        "end_frame_url": end_frame_url or None,
        "prompt_preview_cn": prompt_preview_cn or None,
        "prompt_preview_en": prompt_preview_en or None,
        "is_compact": True,
    }

@router.get("/episodes/{episode_id}/shots", response_model=List[ShotOut])
def read_episode_shots(
    episode_id: int,
    scene_code: Optional[str] = None,
    shot_id: Optional[str] = None,
    keyword: Optional[str] = None,
    compact: bool = Query(False),
    skip: int = 0,
    limit: int = 300,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
        
    project = _require_project_access(db, episode.project_id, current_user)

    query = db.query(Shot).filter(
        Shot.project_id == project.id,
        Shot.episode_id == episode_id,
        _active_shot_clause(),
    )

    if scene_code:
        normalized = scene_code.strip()
        like_token = f"%{normalized}%"
        query = query.filter(
            or_(
                Shot.scene_code.ilike(like_token),
                Shot.shot_id.ilike(f"{normalized}%"),
            )
        )

    if shot_id:
        like_token = f"%{shot_id.strip()}%"
        query = query.filter(Shot.shot_id.ilike(like_token))

    if keyword:
        like_token = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                Shot.shot_name.ilike(like_token),
                Shot.shot_logic_cn.ilike(like_token),
                Shot.associated_entities.ilike(like_token),
                Shot.video_content.ilike(like_token),
            )
        )

    safe_skip = max(int(skip or 0), 0)
    safe_limit = max(1, min(int(limit or 300), 500))

    if compact:
        compact_query = query.with_entities(
            Shot.id.label("id"),
            Shot.scene_id.label("scene_id"),
            Shot.project_id.label("project_id"),
            Shot.episode_id.label("episode_id"),
            Shot.shot_id.label("shot_id"),
            Shot.shot_name.label("shot_name"),
            Shot.start_frame.label("start_frame"),
            Shot.end_frame.label("end_frame"),
            Shot.video_content.label("video_content"),
            Shot.duration.label("duration"),
            Shot.associated_entities.label("associated_entities"),
            Shot.shot_logic_cn.label("shot_logic_cn"),
            Shot.keyframes.label("keyframes"),
            Shot.scene_code.label("scene_code"),
            Shot.image_url.label("image_url"),
            Shot.video_url.label("video_url"),
            Shot.prompt.label("prompt"),
            Shot.technical_notes.label("technical_notes"),
        )
        rows = compact_query.order_by(Shot.id).offset(safe_skip).limit(safe_limit).all()
        deduped_rows = _dedupe_active_shot_records_for_display(rows)
        return [_build_compact_shot_payload(row, db) for row in deduped_rows]

    shots = query.order_by(Shot.id).offset(safe_skip).limit(safe_limit).all()
    shots = _dedupe_active_shot_records_for_display(shots)
    repaired = _repair_shots_media_urls_from_assets(db, current_user, project, shots)
    return [_refresh_shot_media_urls(shot, db) for shot in repaired]


@router.get("/episodes/{episode_id}/shots/download-zip")
def download_episode_shot_videos_zip(
    episode_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    project = _require_project_access(db, episode.project_id, current_user)
    shots = (
        db.query(Shot)
        .filter(
            Shot.project_id == project.id,
            Shot.episode_id == episode_id,
            Shot.video_url.isnot(None),
            Shot.video_url != "",
            _active_shot_clause(),
        )
        .order_by(Shot.id)
        .all()
    )
    shots = _repair_shots_media_urls_from_assets(db, current_user, project, shots)

    if not shots:
        raise HTTPException(status_code=404, detail="No shot videos available for download")

    archive_dir = os.path.join(settings.UPLOAD_DIR, "_downloads")
    os.makedirs(archive_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    archive_name = f"episode_{episode_id}_shot_videos_{timestamp}.zip"
    archive_path = os.path.join(archive_dir, archive_name)

    success_count = 0
    failure_count = 0
    user_agent = {"User-Agent": "AIStoryShotZip/1.0"}

    try:
        with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_STORED) as archive:
            for index, shot in enumerate(shots, start=1):
                refreshed_shot = _refresh_shot_media_urls(shot, db)
                raw_url = str(getattr(refreshed_shot, "video_url", "") or "").strip()
                if not raw_url:
                    continue

                entry_name = _build_shot_video_zip_entry_name(refreshed_shot, index, raw_url)
                local_path = _resolve_local_upload_path_from_media_url(raw_url)

                try:
                    if local_path:
                        archive.write(local_path, arcname=entry_name)
                    else:
                        download_url = raw_url
                        if download_url.startswith("/"):
                            download_url = urllib.parse.urljoin(str(request.base_url), download_url.lstrip("/"))
                        with requests.get(download_url, stream=True, timeout=(15, 180), headers=user_agent) as response:
                            response.raise_for_status()
                            with archive.open(entry_name, mode="w") as zipped_file:
                                for chunk in response.iter_content(chunk_size=1024 * 1024):
                                    if chunk:
                                        zipped_file.write(chunk)
                    success_count += 1
                except Exception as exc:
                    failure_count += 1
                    logger.warning(
                        "Failed to package shot video episode_id=%s shot_id=%s url=%s error=%s",
                        episode_id,
                        getattr(refreshed_shot, "id", None),
                        raw_url,
                        exc,
                    )

        if success_count <= 0:
            _cleanup_temp_download_file(archive_path)
            raise HTTPException(status_code=502, detail="Failed to package shot videos")

        headers = {
            "X-AIStory-Download-Count": str(success_count),
            "X-AIStory-Download-Failures": str(failure_count),
        }
        return FileResponse(
            archive_path,
            media_type="application/zip",
            filename=archive_name,
            headers=headers,
            background=BackgroundTask(_cleanup_temp_download_file, archive_path),
        )
    except HTTPException:
        raise
    except Exception as exc:
        _cleanup_temp_download_file(archive_path)
        logger.error("Failed to build episode shot video zip episode_id=%s error=%s", episode_id, exc)
        raise HTTPException(status_code=500, detail="Failed to create shot video archive")


@router.get("/shots/{shot_id}", response_model=ShotOut)
def read_shot_detail(
    shot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    shot = db.query(Shot).filter(Shot.id == shot_id, _active_shot_clause()).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    project = _require_project_access(db, shot.project_id, current_user)
    _repair_shot_media_urls_from_assets(db, current_user, project, shot)
    _refresh_shot_media_urls(shot, db)
    return shot

class AIShotGenRequest(BaseModel):
    user_prompt: Optional[str] = None
    system_prompt: Optional[str] = None
    shot_generation_mode: Optional[str] = None
    shot_generation_features: Optional[Dict[str, Any]] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None


class AIShotRegenerateRequest(BaseModel):
    content: Optional[List[Dict[str, Any]]] = None
    additional_instructions: Optional[str] = None
    prompt_file: Optional[str] = "skills/shot_generation.md"
    shot_generation_mode: Optional[str] = None
    shot_generation_features: Optional[Dict[str, Any]] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None


def _strip_ai_shots_reasoning_prefix_lines(response_content: Any, *, context: str) -> str:
    reasoning_prefix_terms = [
        "i will",
        "let me",
        "let's",
        "analysis",
        "reasoning",
        "thought process",
        "分析",
        "思路",
        "推理",
        "我将",
        "我认为",
        "我認為",
    ]
    try:
        escaped_terms = [re.escape(term) for term in reasoning_prefix_terms if str(term or "").strip()]
        reasoning_line_re = re.compile(
            r"^\s*(?:" + "|".join(escaped_terms) + r")\b",
            flags=re.IGNORECASE,
        )
    except re.error as re_err:
        logger.warning("[%s] reasoning regex compile failed, fallback used: %s", context, re_err)
        reasoning_line_re = re.compile(r"^\s*(?:analysis|reasoning)\b", flags=re.IGNORECASE)

    cleaned_lines = []
    for line in str(response_content or "").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("|") and reasoning_line_re.match(stripped):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def _build_ai_shots_response_validator(
    *,
    context: str,
    scene_id: int,
    user_id: int,
    source_label: str,
    strip_reasoning_prefixes: bool = False,
    validate_regenerate_markers: bool = False,
):
    def _validator(response_dict: Dict[str, Any], candidate_config: Dict[str, Any]):
        provider = str((candidate_config or {}).get("provider") or "").strip()
        model = str((candidate_config or {}).get("model") or "").strip()
        response_content_raw = response_dict.get("content", "") if isinstance(response_dict, dict) else ""
        raw_str = str(response_content_raw or "").strip()
        route_label = f"{provider}/{model}" if provider or model else "unknown provider"

        if str(response_content_raw).startswith("Error:"):
            return False, str(response_content_raw), None
        if not raw_str:
            return False, "LLM returned empty response", None

        response_content = sanitize_llm_markdown_output(response_content_raw)
        if _is_provider_moderation_block_response(raw_str, response_content):
            return False, f"Provider moderation blocked {source_label.lower()} (PROHIBITED_CONTENT)", None

        if strip_reasoning_prefixes:
            response_content = _strip_ai_shots_reasoning_prefix_lines(response_content, context=context)

        response_content = sanitize_shots_markdown_table_text(response_content)
        if not response_content:
            return False, "LLM response became empty after sanitize", None

        headers, rows, table_line_count = parse_shots_markdown_table(response_content)
        if not rows:
            raw_preview = response_content.replace("\n", " ")[:300]
            return False, f"{source_label} returned 0 parsed rows; raw preview: {raw_preview}", None
        if table_line_count >= 4 and len(rows) > 0 and (len(rows) * 2) <= table_line_count:
            return False, f"{source_label} output may have lost rows during markdown parsing", None

        validated_rows = rows
        if validate_regenerate_markers:
            try:
                validated_rows = _validate_shot_rows_or_raise(
                    rows,
                    source_label="Regenerated shot diff table",
                    status_code=502,
                )
            except HTTPException as exc:
                return False, str(exc.detail or "Regenerated shot diff table validation failed"), None

            marker_errors: List[str] = []
            for idx, row in enumerate(validated_rows, start=1):
                shot_id = _pick_shot_cell(row, ["Shot ID", "shot_id", "镜头ID"], "")
                shot_logic = _pick_shot_cell(row, ["Shot Logic (CN)", "shot_logic_cn", "镜头逻辑", "镜头逻辑（中文）"], "")
                marker_mode, _ = _extract_shot_regenerate_marker(shot_logic)
                if marker_mode not in {"update", "add"}:
                    marker_errors.append(f"row {idx} ({shot_id or 'unknown shot'}) missing required Shot Logic marker")
                    continue
                if marker_mode == "add" and not re.search(r"_\d+$", str(shot_id or "")):
                    marker_errors.append(f"row {idx} ({shot_id or 'unknown shot'}) add-shot id must use _1/_2 style suffix")

            if marker_errors:
                detail = "; ".join(marker_errors[:5])
                if len(marker_errors) > 5:
                    detail += f"; and {len(marker_errors) - 5} more rows"
                return False, f"Regenerated shot diff failed marker validation: {detail}", None

        logger.info(
            "[%s] postprocess validation passed scene_id=%s user_id=%s route=%s parsed_rows=%s",
            context,
            scene_id,
            user_id,
            route_label,
            len(validated_rows),
        )
        return True, "", {
            "raw_text_original": str(response_content_raw or ""),
            "response_content": response_content,
            "headers": headers,
            "rows": validated_rows,
            "table_line_count": table_line_count,
        }

    return _validator


class ShotGenerationRoutePreviewRequest(BaseModel):
    scene_id: int
    shot_generation_mode: Optional[str] = None
    shot_generation_features: Optional[Dict[str, Any]] = None


def _map_shared_prompt_mode_to_shot_generation_mode(raw_mode: Any) -> Optional[str]:
    normalized = str(raw_mode or "").strip().lower().replace("-", "_")
    aliases = {
        "original": "classic",
        "base": "classic",
        "classic": "classic",
        "routed": "routed",
        "feature_stack": "routed",
        "decision_engine": "routed",
        "decisionengine": "routed",
        "skills": "routed",
        "skill_engine": "routed",
        "skillengine": "routed",
    }
    return aliases.get(normalized)


def _resolve_effective_shot_generation_mode(
    db: Session,
    *,
    requested_mode: Optional[str] = None,
    project_metadata: Optional[Dict[str, Any]] = None,
    log_context: str = "shot-generation",
) -> Optional[str]:
    explicit_mode = _map_shared_prompt_mode_to_shot_generation_mode(requested_mode)
    if explicit_mode:
        return explicit_mode

    try:
        shared_system_mode = _map_shared_prompt_mode_to_shot_generation_mode(
            get_scene_analysis_system_config(db).get("default_mode")
        )
        if shared_system_mode:
            return shared_system_mode
    except Exception as config_err:
        logger.warning("[%s] failed to read shared scene-analysis mode for shot generation: %s", log_context, config_err)

    metadata = project_metadata if isinstance(project_metadata, dict) else {}
    for key in ("shot_generation_mode", "shot_prompt_mode", "prompt_mode", "default_mode"):
        candidate = _map_shared_prompt_mode_to_shot_generation_mode(metadata.get(key))
        if candidate:
            return candidate

    return None


def _build_project_prompt_context(project_info_input: Any) -> Dict[str, Any]:
    project_info = project_info_input or {}
    if isinstance(project_info, str):
        try:
            project_info = json.loads(project_info)
        except Exception:
            project_info = {}
    if not isinstance(project_info, dict):
        project_info = {}

    basic_info_nested = project_info.get("basic_information") if isinstance(project_info.get("basic_information"), dict) else {}
    e_global_info = project_info.get("e_global_info") if isinstance(project_info.get("e_global_info"), dict) else {}
    story_input = project_info.get("story_generator_global_input") if isinstance(project_info.get("story_generator_global_input"), dict) else {}
    context_sources = [project_info, basic_info_nested, e_global_info, story_input]

    def _norm_key(key: Any) -> str:
        return str(key or "").strip().lower().replace("-", "_").replace(" ", "_")

    def _normalize_dict_keys(d: Any) -> Dict[str, Any]:
        if not isinstance(d, dict):
            return {}
        return {_norm_key(k): v for k, v in d.items()}

    context_sources_norm = [_normalize_dict_keys(src) for src in context_sources]

    def _clean_text(value: Any) -> str:
        return str(value or "").strip()

    def get_context_val(keys, allow_structured: bool = False):
        if isinstance(keys, str):
            keys = [keys]
        search_keys = [_norm_key(k) for k in keys]
        for src_norm in context_sources_norm:
            for sk in search_keys:
                if sk not in src_norm:
                    continue
                value = src_norm.get(sk)
                if allow_structured:
                    if isinstance(value, (dict, list)) and value:
                        return value
                    text = _clean_text(value)
                    if text:
                        return value
                else:
                    if isinstance(value, (dict, list)):
                        continue
                    text = _clean_text(value)
                    if text:
                        return text
        return {} if allow_structured else ""

    def get_context_list(keys) -> List[str]:
        value = get_context_val(keys, allow_structured=True)
        if isinstance(value, list):
            return [str(v or "").strip() for v in value if str(v or "").strip()]
        if isinstance(value, str):
            return [p.strip() for p in re.split(r"[,，;；\n]", value) if p and p.strip()]
        return []

    tech_params = get_context_val(["tech_params"], allow_structured=True)
    if not isinstance(tech_params, dict):
        tech_params = {}
    visual_standard = tech_params.get("visual_standard") or tech_params.get("visual standard") or {}
    if not isinstance(visual_standard, dict):
        visual_standard = {}
    visual_standard_norm = _normalize_dict_keys(visual_standard)

    def get_visual_val(keys) -> str:
        if isinstance(keys, str):
            keys = [keys]
        search_keys = [_norm_key(k) for k in keys]
        for sk in search_keys:
            if sk in visual_standard_norm:
                value = visual_standard_norm.get(sk)
                if isinstance(value, (dict, list)):
                    continue
                text = _clean_text(value)
                if text:
                    return text
        return get_context_val(keys)

    global_style = get_context_val(["global_style", "Global_Style", "Global Style", "Style"]) or "Cinematic"
    borrowed_films = get_context_list(["borrowed_films", "borrowedFilms", "reference_films", "referenceFilms"])

    title = get_context_val(["script_title", "title"])
    episode_label = get_context_val(["series_episode", "episode"])
    project_type = get_context_val(["type", "genre", "category", "film_type"])
    base_positioning = get_context_val(["base_positioning"])
    project_language = get_context_val(["language", "project_language", "lang"])
    tone = get_context_val(["tone", "mood", "atmosphere"])
    lighting = get_context_val(["lighting", "light_style", "light"])
    color_spectrum = get_context_val(["color_spectrum", "colorSpectrum", "色系光谱", "color_temperature_direction"])
    character_relationships = get_context_val(["character_relationships"])
    project_notes = get_context_val(["notes"])
    region_culture = get_context_val(["region_culture", "region", "country", "culture", "country_region"])
    era_setting = get_context_val(["era", "era_setting", "period", "time_setting"])
    shot_preference = get_context_val(["shot_preference", "lens_preference", "camera_preference"])
    broadcast_security_level = get_context_val([
        "broadcast_security_level",
        "broadcast_safety_level",
        "safety_broadcast_level",
        "safety_level",
        "broadcast_safety",
        "compliance_level",
    ])
    expected_model_family = get_context_val(["expected_model_family", "expected_model", "target_model", "model_family"])
    generation_workflow = get_context_val(["generation_workflow", "workflow", "pipeline"])
    continuity_priority = get_context_val(["continuity_priority", "continuity", "continuity_mode"])
    prompt_mode = get_context_val(["shot_generation_mode", "shot_prompt_mode", "prompt_mode"])

    field_mappings = {
        "Type": ["Type", "Genre", "Category", "Film Type"],
        "Tone": ["Tone", "Color Tone", "Mood", "Atmosphere"],
        "Language": ["Language", "Lang"],
        "Lighting": ["Lighting", "Light Style"],
        "Quality": ["Quality", "Production Quality"],
    }
    context_lines = []
    for field, keys in field_mappings.items():
        val = get_context_val(keys)
        if val:
            context_lines.append(f"{field}: {val}")
    additional_context = "\n".join(context_lines) if context_lines else ""

    project_context_lines = [
        "# Project Context",
        "Treat this project metadata as first-class constraints when generating outputs.",
        "[Basic Info]",
    ]
    if title:
        project_context_lines.append(f"Title: {title}")
    if episode_label:
        project_context_lines.append(f"Episode: {episode_label}")
    if project_type:
        project_context_lines.append(f"Type: {project_type}")
    if base_positioning:
        project_context_lines.append(f"Base Positioning: {base_positioning}")
    if project_language:
        project_context_lines.append(f"Language: {project_language}")
    else:
        project_context_lines.append("Language: (empty)")
    if global_style:
        project_context_lines.append(f"Global Style: {global_style}")
    if tone:
        project_context_lines.append(f"Tone: {tone}")
    if lighting:
        project_context_lines.append(f"Lighting: {lighting}")
    if color_spectrum:
        project_context_lines.append(f"Color Spectrum: {color_spectrum}")
    if era_setting:
        project_context_lines.append(f"Era / Period (年代): {era_setting}")
    if region_culture:
        project_context_lines.append(f"Region / Country (国家地域): {region_culture}")
    if shot_preference:
        project_context_lines.append(f"Shot / Lens Preference (镜头偏好): {shot_preference}")
    if broadcast_security_level:
        project_context_lines.append(f"Broadcast Safety Level (播出安全等级): {broadcast_security_level}")
    if borrowed_films:
        project_context_lines.append(f"Borrowed Films: {', '.join(borrowed_films)}")
    if character_relationships:
        project_context_lines.append(f"Character Relationships: {character_relationships}")
    if project_notes:
        project_context_lines.append(f"Project Notes: {project_notes}")

    project_context_lines.append("[Technical & Visual Parameters]")
    aspect_ratio = get_visual_val(["aspect_ratio", "aspectRatio"])
    image_size = get_visual_val(["image_size", "imageSize"])
    horizontal_resolution = get_visual_val(["horizontal_resolution", "horizontalResolution", "h_resolution", "width"])
    vertical_resolution = get_visual_val(["vertical_resolution", "verticalResolution", "v_resolution", "height"])
    frame_rate = get_visual_val(["frame_rate", "frameRate", "fps"])
    quality = get_visual_val(["quality"])

    if aspect_ratio:
        project_context_lines.append(f"Aspect Ratio: {aspect_ratio}")
    if image_size:
        project_context_lines.append(f"Image Size: {image_size}")
    if horizontal_resolution:
        project_context_lines.append(f"Horizontal Resolution: {horizontal_resolution}")
    if vertical_resolution:
        project_context_lines.append(f"Vertical Resolution: {vertical_resolution}")
    if frame_rate:
        project_context_lines.append(f"Frame Rate: {frame_rate}")
    if quality:
        project_context_lines.append(f"Quality: {quality}")
    if expected_model_family:
        project_context_lines.append(f"Expected Model Family: {expected_model_family}")
    if generation_workflow:
        project_context_lines.append(f"Generation Workflow: {generation_workflow}")
    if continuity_priority:
        project_context_lines.append(f"Continuity Priority: {continuity_priority}")

    project_context_lines.append("Use this project context as first-class constraints before analyzing the script.")
    project_context_section = wrap_injection_section("项目信息", "\n".join(project_context_lines))

    metadata = {
        "title": title,
        "episode": episode_label,
        "project_type": project_type,
        "type": project_type,
        "base_positioning": base_positioning,
        "project_language": project_language,
        "language": project_language,
        "global_style": global_style,
        "tone": tone,
        "lighting": lighting,
        "color_spectrum": color_spectrum,
        "region_culture": region_culture,
        "era_setting": era_setting,
        "broadcast_security_level": broadcast_security_level,
        "broadcast_safety_level": broadcast_security_level,
        "safety_broadcast_level": broadcast_security_level,
        "expected_model_family": expected_model_family,
        "generation_workflow": generation_workflow,
        "continuity_priority": continuity_priority,
        "shot_generation_mode": prompt_mode,
        "shot_prompt_mode": prompt_mode,
        "prompt_mode": prompt_mode,
    }

    return {
        "project_info": project_info,
        "global_style": global_style,
        "additional_context": additional_context,
        "project_context_section": project_context_section,
        "borrowed_films": borrowed_films,
        "metadata": metadata,
    }


def _build_shot_generation_project_context(project: Project) -> Dict[str, Any]:
    return _build_project_prompt_context(project.global_info)


def _build_scene_subject_image_prompts_cn_section(
    project_entities: List[Any],
    subject_match_keys: set,
    *,
    scene_id: Optional[int] = None,
) -> str:
    if not subject_match_keys:
        return ""

    def _entity_matches_subject_keys(ent: Any) -> bool:
        aliases = [getattr(ent, "name", None), getattr(ent, "name_en", None)]
        for alias in aliases:
            alias_text = str(alias or "").strip()
            if not alias_text:
                continue
            if subject_compare_key(alias_text) in subject_match_keys:
                return True
            if subject_match_keys.intersection(subject_compare_key_variants(alias_text)):
                return True
        return False

    type_order = {"character": 0, "prop": 1, "environment": 2, "cover": 3}
    matched_entities = [
        ent for ent in (project_entities or [])
        if not bool(getattr(ent, "is_deleted", False))
        and _entity_matches_subject_keys(ent)
        and str(getattr(ent, "generation_prompt_cn", None) or "").strip()
    ]
    matched_entities.sort(
        key=lambda ent: (
            type_order.get(_normalize_subject_entity_type(getattr(ent, "type", None)), 9),
            int(getattr(ent, "id", 0) or 0),
        )
    )

    prompt_lines: List[str] = []
    seen_refs: set = set()
    for ent in matched_entities:
        normalized_type = _normalize_subject_entity_type(getattr(ent, "type", None)) or "character"
        canonical_name = str(getattr(ent, "name", None) or getattr(ent, "name_en", None) or "").strip()
        if not canonical_name:
            continue
        if normalized_type == "character":
            subject_ref = f"CHAR:[@{canonical_name}]"
        elif normalized_type == "prop":
            subject_ref = f"PROP:[{canonical_name}]"
        elif normalized_type == "environment":
            subject_ref = f"ENV:[{canonical_name}]"
        else:
            subject_ref = f"COVER:[{canonical_name}]"
        if subject_ref in seen_refs:
            continue
        seen_refs.add(subject_ref)
        prompt_cn = re.sub(r"\s+", " ", str(getattr(ent, "generation_prompt_cn", None) or "")).strip()
        if not prompt_cn:
            continue
        prompt_lines.append(f"- {subject_ref} | generation_prompt_cn={prompt_cn}")

    if not prompt_lines:
        logger.info(
            "[_build_shot_prompts] no scene subject image prompts matched scene_id=%s keys=%s",
            scene_id,
            len(subject_match_keys),
        )
        return ""

    body = (
        "# Scene Subject Image Prompts (CN)\n"
        "Authoritative Chinese image-generation prompts for scene-involved subjects only. "
        "Use for visual identity consistency (appearance, materials, palette, anchor features, spatial tone) when writing Video Content (CN). "
        "Translate into dynamic video language; do not paste static framing/canvas instructions verbatim. "
        "Entity naming authority remains Scene Subject Index.\n"
        + "\n".join(prompt_lines)
        + "\n"
    )
    logger.info(
        "[_build_shot_prompts] injected scene subject image prompts scene_id=%s keys=%s rows=%s",
        scene_id,
        len(subject_match_keys),
        len(prompt_lines),
    )
    return wrap_injection_section("实体中文生图提示词", body)


def _build_shot_prompts(
    db: Session,
    scene: Scene,
    project: Project,
    *,
    mode: Optional[str] = None,
    explicit_features: Optional[Dict[str, Any]] = None,
):
    # 2. Gather Data
    # Global Style & Context
    project_context = _build_shot_generation_project_context(project)
    effective_mode = _resolve_effective_shot_generation_mode(
        db,
        requested_mode=mode,
        project_metadata=project_context.get("metadata"),
        log_context="_build_shot_prompts",
    )
    project_info = project_context.get("project_info") if isinstance(project_context.get("project_info"), dict) else {}
    global_style = str(project_context.get("global_style") or "Cinematic")
    additional_context = str(project_context.get("additional_context") or "")
    project_context_section = str(project_context.get("project_context_section") or "")

    # Scene Info
    project_entities = (
        db.query(Entity)
        .filter(Entity.project_id == project.id, Entity.is_deleted.is_(False))
        .order_by(Entity.id.asc())
        .all()
    )
    
    def _scene_subject_compare_key(value: Any) -> str:
        return subject_compare_key(value)

    def _scene_subject_compare_keys(value: Any) -> set:
        return subject_compare_key_variants(value)

    # Identify relevant entity names from scene editor fields only:
    # environment anchor + linked characters (comma-separated) + key props.
    relevant_names: set = set()
    relevant_name_keys: set = set()

    def _clean_br(s):
        return normalize_entity_token(s)

    def _split_scene_editor_subjects(raw_value: Any) -> List[str]:
        values: List[str] = []
        for part in re.split(r"[,，、;；\n]+", str(raw_value or "")):
            cleaned = _clean_br(part)
            if not cleaned:
                continue
            values.append(cleaned)
        return values

    def _extract_tagged_scene_subjects(raw_value: Any) -> List[str]:
        """Extract only scene-related CHAR/PROP/ENV tags (never EXTRA/COVER/poster)."""
        values: List[str] = []
        text = str(raw_value or "")
        for match in re.finditer(r"(?i)\b(?:CHAR|PROP|ENV)\s*:\s*\[\s*@?([^\]\n]+?)\s*\]", text):
            cleaned = _clean_br(match.group(1))
            if cleaned:
                values.append(cleaned)
        return values

    def _extract_scene_subjects_from_markdown_rows(raw_value: Any) -> List[str]:
        values: List[str] = []
        text = str(raw_value or "")
        if not text.strip():
            return values
        row_patterns = [
            r"(?im)^\s*\|\s*(?:\*\*)?\s*(?:Environment\s*Anchor|环境锚点|Environment\s*Name|环境名)\s*(?:\*\*)?\s*\|\s*(.*?)\s*\|\s*$",
            r"(?im)^\s*\|\s*(?:\*\*)?\s*(?:Linked\s*Characters|关联角色)\s*(?:\*\*)?\s*\|\s*(.*?)\s*\|\s*$",
            r"(?im)^\s*\|\s*(?:\*\*)?\s*(?:Key\s*Props|关键道具)\s*(?:\*\*)?\s*\|\s*(.*?)\s*\|\s*$",
        ]
        for pattern in row_patterns:
            for match in re.finditer(pattern, text):
                cell_value = str(match.group(1) or "").strip()
                if not cell_value:
                    continue
                values.extend(_split_scene_editor_subjects(cell_value))
                values.extend(_extract_tagged_scene_subjects(cell_value))
        return values

    def _extract_environment_context_from_text(raw_value: Any) -> str:
        text = str(raw_value or "")
        if not text.strip():
            return ""

        row_patterns = [
            r"(?im)^\s*\|\s*(?:\*\*)?\s*(?:Environment\s*Context|环境上下文|环境描述)\s*(?:\*\*)?\s*\|\s*(.*?)\s*\|\s*$",
        ]
        for pattern in row_patterns:
            match = re.search(pattern, text)
            if match:
                cell_value = str(match.group(1) or "").strip()
                if cell_value and cell_value.upper() != "N/A":
                    return cell_value

        block_patterns = [
            r"(?im)\*\*\{Environment\s*Context\}\*\*\s*[:：]\s*(.+?)(?=\n\s*(?:-\s*\*\*\{|\*\*\{|\|))",
            r"(?im)\{Environment\s*Context\}\s*[:：]\s*(.+?)(?=\n\s*(?:-\s*\*\*\{|\*\*\{|\|))",
        ]
        for pattern in block_patterns:
            match = re.search(pattern, text, flags=re.DOTALL)
            if match:
                block_value = str(match.group(1) or "").strip()
                if block_value:
                    return block_value
        return ""

    def _register_scene_subject_candidate(raw_value: Any) -> None:
        text = str(raw_value or "").strip()
        if not text:
            return
        relevant_names.add(text)
        for key in _scene_subject_compare_keys(text):
            if key:
                relevant_name_keys.add(key)

    scene_editor_fields = [scene.environment_name, scene.linked_characters, scene.key_props]
    for raw_field_value in scene_editor_fields:
        for part in _split_scene_editor_subjects(raw_field_value):
            _register_scene_subject_candidate(part)
        for part in _extract_tagged_scene_subjects(raw_field_value):
            _register_scene_subject_candidate(part)
    # Compatibility: if scene content includes markdown rows for these fields,
    # parse them as additional candidates.
    for part in _extract_scene_subjects_from_markdown_rows(scene.core_scene_info):
        _register_scene_subject_candidate(part)
    # Tagged subjects from scene body / original script grounding (CHAR/PROP/ENV only).
    for source_text in (scene.core_scene_info, getattr(scene, "original_script_text", None)):
        for part in _extract_tagged_scene_subjects(source_text):
            _register_scene_subject_candidate(part)

    logger.info(
        "[_build_shot_prompts] scene subject candidates merged scene_id=%s names=%s keys=%s",
        getattr(scene, "id", None),
        len(relevant_names),
        len(relevant_name_keys),
    )

    def _add_scene_subject_candidate(value: Any, target: set) -> None:
        for key in _scene_subject_compare_keys(value):
            if key:
                target.add(key)

    def _extract_scene_subject_candidates() -> set:
        candidates: set = set()
        for value in scene_editor_fields:
            for part in _split_scene_editor_subjects(value):
                _add_scene_subject_candidate(part, candidates)
            for part in _extract_tagged_scene_subjects(value):
                _add_scene_subject_candidate(part, candidates)
        for part in _extract_scene_subjects_from_markdown_rows(scene.core_scene_info):
            _add_scene_subject_candidate(part, candidates)
        for source_text in (scene.core_scene_info, getattr(scene, "original_script_text", None)):
            for part in _extract_tagged_scene_subjects(source_text):
                _add_scene_subject_candidate(part, candidates)
        return candidates

    def _normalize_subject_index_row_type(raw_type: Any) -> str:
        value = str(raw_type or "").strip().lower()
        value = re.sub(r"[\s_\-]+", "", value)
        mapping = {
            "character": "character",
            "characters": "character",
            "角色": "character",
            "char": "character",
            "prop": "prop",
            "props": "prop",
            "道具": "prop",
            "environment": "environment",
            "environments": "environment",
            "env": "environment",
            "场景": "environment",
            "环境": "environment",
            "poster": "poster",
            "posters": "poster",
            "海报": "poster",
            "cover": "cover",
            "covers": "cover",
            "封面": "cover",
            "coverposter": "cover",
            "封面海报": "cover",
        }
        return mapping.get(value, "")

    def _is_subject_index_row(parts: List[str], normalized_line: str) -> bool:
        if len(parts) < 4:
            return False
        if not re.match(r"^S\d+\b", normalized_line, flags=re.IGNORECASE):
            return False
        row_type = _normalize_subject_index_row_type(parts[1] if len(parts) > 1 else "")
        return bool(row_type)

    def _build_filtered_scene_subject_index(scene_subject_keys: set) -> Tuple[str, set]:
        """
        Inject only Subject Index rows that match this scene's related entities
        (environment / linked characters / key props, plus tagged names in Core Scene Info).
        Never inject the full episode Subject Index.
        """
        episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
        subject_index_text = sanitize_subject_index_text(
            getattr(episode, "ai_scene_analysis_subject_index", None) if episode else ""
        )
        if not subject_index_text:
            return "", set()

        if not scene_subject_keys:
            logger.info(
                "[_build_shot_prompts] skip subject index injection: no scene-linked entity candidates "
                "scene_id=%s env=%s chars=%s props=%s",
                getattr(scene, "id", None),
                bool(str(getattr(scene, "environment_name", "") or "").strip()),
                bool(str(getattr(scene, "linked_characters", "") or "").strip()),
                bool(str(getattr(scene, "key_props", "") or "").strip()),
            )
            return "", set()

        header_lines: List[str] = []
        separator_lines: List[str] = []
        kept_rows: List[str] = []
        seen_rows: set = set()
        index_subject_keys: set = set()
        allowed_row_types = {"character", "prop", "environment"}

        def _row_matches_scene_subjects(parts: List[str]) -> bool:
            # Match by display names only (zh/en). Do not keep rows merely because
            # scene candidates are empty, and do not match on subject_no alone.
            name_cells = []
            if len(parts) > 2:
                name_cells.append(parts[2])
            if len(parts) > 3:
                name_cells.append(parts[3])
            for candidate in name_cells:
                candidate_text = str(candidate or "").strip()
                if not candidate_text:
                    continue
                primary = _scene_subject_compare_key(candidate_text)
                if primary and primary in scene_subject_keys:
                    return True
                variants = _scene_subject_compare_keys(candidate_text)
                if variants and scene_subject_keys.intersection(variants):
                    return True
            return False

        for raw_line in str(subject_index_text).splitlines():
            line = str(raw_line or "")
            stripped = line.strip()
            if not stripped:
                continue

            normalized_line = stripped.strip("|").strip()
            parts = [part.strip() for part in normalized_line.split("|")]
            is_subject_row = _is_subject_index_row(parts, normalized_line)
            if is_subject_row:
                row_type = _normalize_subject_index_row_type(parts[1] if len(parts) > 1 else "")
                if row_type not in allowed_row_types:
                    continue
                if not _row_matches_scene_subjects(parts):
                    continue
                row_key = re.sub(r"\s+", "", stripped).lower()
                if row_key in seen_rows:
                    continue
                kept_rows.append(line)
                seen_rows.add(row_key)
                for candidate in [parts[2] if len(parts) > 2 else "", parts[3] if len(parts) > 3 else ""]:
                    key = _scene_subject_compare_key(candidate)
                    if key:
                        index_subject_keys.add(key)
                continue

            is_table_header = "|" in stripped and re.search(r"(?i)subject_no|subject_type|subject_name|name_zh|name_en", stripped)
            is_table_separator = bool(re.match(r"^\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?$", stripped))
            if is_table_header:
                header_lines = [line]
                continue
            if is_table_separator:
                separator_lines = [line]

        if not kept_rows:
            logger.info(
                "[_build_shot_prompts] filtered scene subject index has no matching rows "
                "(full index will NOT be injected) scene_id=%s candidate_count=%s",
                getattr(scene, "id", None),
                len(scene_subject_keys),
            )
            return "", set()

        lines = [
            "# Scene Subject Index",
            "Authoritative filtered Subject Index for this scene only "
            "(environment / linked characters / key props). "
            "Use subject_no/subject_type/subject_name fields as the sole entity naming source; "
            "do not infer subjects outside this list.",
        ]
        lines.extend(header_lines)
        lines.extend(separator_lines if header_lines else [])
        lines.extend(kept_rows)
        logger.info(
            "[_build_shot_prompts] injected filtered scene subject index scene_id=%s candidates=%s rows=%s",
            getattr(scene, "id", None),
            len(scene_subject_keys),
            len(kept_rows),
        )
        return wrap_injection_section("Subject Index", "\n".join(lines).strip() + "\n"), index_subject_keys

    env_narrative = _extract_environment_context_from_text(scene.core_scene_info).strip()
    if env_narrative:
        logger.info(
            "[_build_shot_prompts] using Environment Context from core_scene_info scene_id=%s",
            getattr(scene, "id", None),
        )

    scene_subject_keys = _extract_scene_subject_candidates()
    scene_subject_index_section, index_subject_keys = _build_filtered_scene_subject_index(scene_subject_keys)
    subject_match_keys = set(scene_subject_keys) | set(index_subject_keys)
    scene_subject_image_prompts_section = _build_scene_subject_image_prompts_cn_section(
        project_entities,
        subject_match_keys,
        scene_id=getattr(scene, "id", None),
    )

    # 3. Prepare System Prompt
    system_prompt = ""
    try:
        core_goal_text = scene.core_scene_info or ''
        feature_bundle = resolve_shot_generation_feature_bundle(
            project_metadata=project_context.get("metadata"),
            explicit_features=explicit_features,
            script_text=core_goal_text,
            mode=effective_mode,
        )
        base_prompt_file = str(feature_bundle.get("base_prompt_file") or "skills/shot_generation.md")
        system_prompt = _resolve_prompt_text(base_prompt_file)
        if feature_bundle.get("enabled"):
            system_prompt = render_shot_generation_routed_prompt(system_prompt, feature_bundle)
    except Exception as e:
        logger.error(f"Failed to load shot generation prompt stack: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Shot generation prompt stack could not be loaded: {str(e)}")

    # Environment Context is now a separate field in the table

    core_scene_info_block = wrap_injection_section(
        "Core Scene Info",
        f"""| Field | Value |
| :--- | :--- |
| **Scene No** | {scene.scene_no or ''} |
| **Scene Name** | {scene.scene_name or ''} |
| **Environment Anchor** | {scene.environment_name or ''} |
| **Environment Context** | {env_narrative or 'N/A'} |
| **Linked Characters** | {scene.linked_characters or ''} |
| **Key Props** | {scene.key_props or ''} |
| **Core Goal** | {core_goal_text} |""",
    )

    user_input = f"""{project_context_section}

{core_scene_info_block}

{scene_subject_index_section}
{scene_subject_image_prompts_section}
# Instruction
1. Analyze `# Core Scene Info` Beats and break them down into shots per §二.1.5/§二.1.6.
2. Output exactly one Shot List markdown table. Do not copy prompt example/template rows (e.g. `{{Scene ID}}_SHzz` or a second header).
3. Scene opening / OT- / 吸睛 must be P segments inside the Shot that covers Beat 1 — never an extra Shot outside Beat-Shot mapping.
4. Every Beat must appear in some row's `Beat-Shot映射`; do not invent unmapped opening shots.
"""
    
    return system_prompt, user_input


def _extract_shot_regenerate_marker(raw_logic: str) -> Tuple[Optional[str], str]:
    text = str(raw_logic or "").strip()
    if not text:
        return None, ""

    if re.search(r"=更新分镜\s*$", text):
        return "update", re.sub(r"\s*=更新分镜\s*$", "", text).strip()
    if re.search(r"=补充分镜\s*$", text):
        return "add", re.sub(r"\s*=补充分镜\s*$", "", text).strip()
    return None, text


def _build_shot_regenerate_prompts(
    db: Session,
    scene: Scene,
    project: Project,
    *,
    staged_markdown: str,
    additional_instructions: str,
    mode: Optional[str],
    explicit_features: Optional[Dict[str, Any]],
) -> Tuple[str, str]:
    system_prompt, base_user_prompt = _build_shot_prompts(
        db,
        scene,
        project,
        mode=mode,
        explicit_features=explicit_features,
    )

    safe_markdown = str(staged_markdown or "").strip()
    safe_instructions = str(additional_instructions or "").strip() or "(none)"

    runtime_rules = (
        "# Runtime Regeneration Rules\n"
        "You are not generating a full fresh shot list. You are producing a selective supplement/update diff against the current staged shot markdown.\n"
        "Return a markdown table only. Do not add prose before or after the table.\n"
        "Only include rows that need to change or be newly inserted. Omit unchanged rows entirely.\n"
        "For an existing shot that should be modified, preserve its existing Shot ID exactly and append '=更新分镜' to the end of 'Shot Logic (CN)'.\n"
        "For a newly inserted shot, create a Shot ID derived from its neighboring base shot using an underscore numeric suffix such as '_1', '_2', and append '=补充分镜' to the end of 'Shot Logic (CN)'.\n"
        "Every returned row must include a valid marker in 'Shot Logic (CN)' so downstream import can distinguish updates from additions.\n"
        "Do not rewrite or renumber unaffected shots.\n"
        "Keep the table schema compatible with the staged shot markdown table.\n"
    )

    user_prompt = (
        "# Scene Context Reference\n"
        "The following block is the authoritative current scene context, including project context, scene text, and subject index.\n\n"
        f"{str(base_user_prompt or '').strip()}\n\n"
        f"{runtime_rules}\n"
        "# Current Staged Shot Markdown (Authoritative Baseline)\n"
        "Use this markdown table as the source of truth for current shot order, existing Shot IDs, and current content.\n\n"
        f"{safe_markdown}\n\n"
        "# User Supplement Instructions\n"
        f"{safe_instructions}\n"
    )
    return system_prompt, user_prompt


def _persist_scene_shot_generation_result(
    *,
    db: Session,
    scene_id: int,
    raw_text: str,
    markdown_text: str,
    rows: List[Dict[str, Any]],
    usage: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Persist LLM shot-generation output to scene staging storage only.
    This method does NOT import into Shot table.
    """
    result_wrapper = {
        "timestamp": now_bj_iso(),
        "raw_text": str(raw_text or ""),
        "content": list(rows or []),
        "usage": usage or {},
        "warnings": [],
    }
    # The original ORM instance may be detached after _release_db_connection;
    # reload a session-bound instance before applying updates.
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    scene.ai_shots_result = str(markdown_text or "")
    db.commit()
    logger.info(
        "[shot_generation.persist] saved scene_id=%s markdown_len=%s rows=%s",
        scene_id,
        len(scene.ai_shots_result or ""),
        len(result_wrapper.get("content") or []),
    )
    return result_wrapper

@router.get("/scenes/{scene_id}/ai_prompt_preview")
def ai_prompt_preview(
    scene_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    project = _require_project_access(db, episode.project_id, current_user)
        
    project_context = _build_shot_generation_project_context(project)
    effective_mode = _resolve_effective_shot_generation_mode(
        db,
        project_metadata=project_context.get("metadata"),
        log_context="ai_prompt_preview",
    )
    feature_bundle = resolve_shot_generation_feature_bundle(
        project_metadata=project_context.get("metadata"),
        script_text=scene.core_scene_info or "",
        mode=effective_mode,
    )
    system, user = _build_shot_prompts(db, scene, project)
    return {
        "system_prompt": system,
        "user_prompt": user,
        "shot_generation_mode": feature_bundle.get("mode"),
        "base_prompt_file": feature_bundle.get("base_prompt_file"),
        "selected_skills": [
            {
                "skill_id": item.get("skill_id"),
                "dimension": item.get("dimension"),
                "value": item.get("value"),
                "title": item.get("title"),
                "slot_token": item.get("slot_token"),
            }
            for item in (feature_bundle.get("selected_skills") or [])
        ],
    }


@router.get("/prompts/shot-generation/features")
async def get_shot_generation_feature_options(current_user: User = Depends(get_current_user)):
    return get_shot_generation_feature_catalog()


def _shot_generation_slot_origin(slot_token: Any) -> str:
    token = str(slot_token or "").strip()
    if not token:
        return "unknown"
    if token == "[[SHOT_GENERATION_COMBO_RULES]]":
        return "global_combo"
    if token.startswith("[[SHOT_GENERATION_") and token.endswith("_RULES]]"):
        return "global_dimension"
    return "unknown"


@router.post("/prompts/shot-generation/route-preview")
async def preview_shot_generation_route(
    request: ShotGenerationRoutePreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scene = db.query(Scene).filter(Scene.id == request.scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    project = _require_project_access(db, episode.project_id, current_user)
    project_context = _build_shot_generation_project_context(project)
    effective_mode = _resolve_effective_shot_generation_mode(
        db,
        requested_mode=request.shot_generation_mode,
        project_metadata=project_context.get("metadata"),
        log_context="shot-generation-route-preview",
    )
    bundle = resolve_shot_generation_feature_bundle(
        project_metadata=project_context.get("metadata"),
        explicit_features=request.shot_generation_features,
        script_text=scene.core_scene_info or "",
        mode=effective_mode,
    )
    return {
        "scene_id": scene.id,
        "requested_mode": request.shot_generation_mode,
        "effective_mode": bundle.get("mode"),
        "enabled": bundle.get("enabled"),
        "base_prompt_file": bundle.get("base_prompt_file"),
        "slot_blocks": bundle.get("slot_blocks") or {},
        "known_slot_tokens": bundle.get("known_slot_tokens") or [],
        "normalized_features": bundle.get("normalized_features") or {},
        "resolved_dimensions": bundle.get("resolved_dimensions") or {},
        "selected_skills": [
            {
                "skill_id": item.get("skill_id"),
                "dimension": item.get("dimension"),
                "value": item.get("value"),
                "title": item.get("title"),
                "source": item.get("source"),
                "slot_token": item.get("slot_token"),
                "slot_origin": _shot_generation_slot_origin(item.get("slot_token")),
                "slot_has_block": bool((bundle.get("slot_blocks") or {}).get(str(item.get("slot_token") or ""))),
            }
            for item in (bundle.get("selected_skills") or [])
        ],
        "combo_matches": [
            {
                "skill_id": item.get("skill_id"),
                "title": item.get("title"),
                "when": item.get("when") or {},
                "slot_token": item.get("slot_token"),
                "slot_origin": _shot_generation_slot_origin(item.get("slot_token")),
                "slot_has_block": bool((bundle.get("slot_blocks") or {}).get(str(item.get("slot_token") or ""))),
            }
            for item in (bundle.get("combo_matches") or [])
        ],
        "diagnostics": bundle.get("diagnostics") or [],
    }

class AnalysisContent(BaseModel):
    content: Union[Dict[str, Any], List[Any]]
    # When False (default), abandon import if the scene already has active shots.
    # Set True only for intentional replace flows (UI confirm).
    replace_existing: Optional[bool] = False


class SceneAiShotsBatchStartRequest(BaseModel):
    scene_ids: Optional[List[int]] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None


SCENE_AI_SHOTS_BATCH_STATUS_KEY = "scene_ai_shots_batch_status"
SCENE_AI_SHOTS_BATCH_PER_SCENE_TIMEOUT_SEC = 600
SCENE_AI_SHOTS_BATCH_DEFAULT_CONCURRENCY = 3
SCENE_AI_SHOTS_BATCH_STATUS_ERROR_LIMIT = max(5, int(os.getenv("SCENE_AI_SHOTS_BATCH_STATUS_ERROR_LIMIT", "20") or 20))
SCENE_AI_SHOTS_BATCH_STATUS_ERROR_MAX_CHARS = max(80, int(os.getenv("SCENE_AI_SHOTS_BATCH_STATUS_ERROR_MAX_CHARS", "240") or 240))


def _read_scene_ai_shots_batch_status(episode: Episode) -> Dict[str, Any]:
    try:
        info = _episode_runtime_info_from_episode(episode)
        payload = info.get(SCENE_AI_SHOTS_BATCH_STATUS_KEY)
        if isinstance(payload, dict):
            return dict(payload)
    except Exception:
        pass
    return {
        "running": False,
        "total": 0,
        "completed": 0,
        "success": 0,
        "failed": 0,
        "current_scene_id": None,
        "current_scene_label": "",
        "message": "",
        "errors": [],
    }


def _persist_scene_ai_shots_batch_status(db: Session, episode: Episode, status_payload: Dict[str, Any]) -> None:
    latest_episode = (
        db.query(Episode)
        .execution_options(populate_existing=True)
        .filter(Episode.id == int(episode.id))
        .first()
    )
    target_episode = latest_episode or episode

    info = _episode_runtime_info_from_episode(target_episode)
    existing_status = info.get(SCENE_AI_SHOTS_BATCH_STATUS_KEY)
    merged_status = dict(status_payload or {})
    has_incoming_force_flag = "force_stopped" in merged_status

    if isinstance(existing_status, dict) and bool(existing_status.get("force_stopped")) and not has_incoming_force_flag:
        merged_status["force_stopped"] = True

    if bool(merged_status.get("force_stopped")):
        now_iso = now_bj_iso()
        merged_status["running"] = False
        merged_status["status"] = "canceled"
        merged_status["stopped_by_user"] = True
        merged_status["finished_at"] = merged_status.get("finished_at") or now_iso
        merged_status["updated_at"] = now_iso

    info[SCENE_AI_SHOTS_BATCH_STATUS_KEY] = merged_status
    target_episode.episode_info = info
    db.add(target_episode)
    db.commit()


def _build_scene_ai_shots_batch_status_response(status_payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(status_payload or {})
    response_payload: Dict[str, Any] = {
        "running": bool(payload.get("running")),
        "status": str(payload.get("status") or ("running" if payload.get("running") else "idle")).strip().lower(),
        "project_id": payload.get("project_id"),
        "episode_id": payload.get("episode_id"),
        "started_by_user_id": payload.get("started_by_user_id"),
        "started_by_username": payload.get("started_by_username"),
        "max_concurrency": payload.get("max_concurrency"),
        "total": int(payload.get("total") or 0),
        "completed": int(payload.get("completed") or 0),
        "success": int(payload.get("success") or 0),
        "failed": int(payload.get("failed") or 0),
        "current_scene_id": payload.get("current_scene_id"),
        "current_scene_label": str(payload.get("current_scene_label") or "").strip(),
        "message": str(payload.get("message") or "").strip()[:512],
        "stop_requested": bool(payload.get("stop_requested")),
        "force_stopped": bool(payload.get("force_stopped")),
        "stopped_by_user": bool(payload.get("stopped_by_user")),
        "started_at": payload.get("started_at"),
        "updated_at": payload.get("updated_at"),
        "finished_at": payload.get("finished_at"),
    }

    raw_errors = payload.get("errors") or []
    safe_errors: List[str] = []
    for item in (raw_errors if isinstance(raw_errors, list) else []):
        txt = str(item or "").strip()
        if not txt:
            continue
        safe_errors.append(txt[:SCENE_AI_SHOTS_BATCH_STATUS_ERROR_MAX_CHARS])
        if len(safe_errors) >= SCENE_AI_SHOTS_BATCH_STATUS_ERROR_LIMIT:
            break
    response_payload["errors"] = safe_errors
    response_payload["errors_total"] = len(raw_errors) if isinstance(raw_errors, list) else len(safe_errors)
    response_payload["errors_truncated"] = bool(response_payload["errors_total"] > len(safe_errors))
    response_payload["poll_interval_ms"] = 2500
    return response_payload


def _run_scene_ai_shots_batch_item(scene_id: int, episode_id: int, user_id: int, function_name: Optional[str] = None, system_api_id: Optional[int] = None) -> Dict[str, Any]:
    item_db = SessionLocal()
    try:
        scene = item_db.query(Scene).filter(Scene.id == scene_id, Scene.episode_id == episode_id).first()
        user = item_db.query(User).filter(User.id == user_id).first()
        if not scene or not user:
            raise RuntimeError("Scene or user not found")
        user_principal = _snapshot_user_principal(user)

        scene_label = str(scene.scene_no or scene.scene_name or f"#{scene_id}")
        existing_shot_count = (
            item_db.query(Shot)
            .filter(Shot.scene_id == scene_id, _active_shot_clause())
            .count()
        )
        if existing_shot_count > 0:
            logger.info(
                "[scene_ai_shots_batch] abandon scene already has shots | scene_id=%s count=%s",
                scene_id,
                existing_shot_count,
            )
            return {
                "scene_id": int(scene_id),
                "scene_label": scene_label,
                "ok": True,
                "skipped": True,
                "reason": f"scene already has {existing_shot_count} shot(s); import abandoned",
            }
        _release_db_connection(item_db, "scene_ai_shots_batch_item")
        generated = asyncio.run(
            asyncio.wait_for(
                ai_generate_shots(scene_id=scene_id, req=AIShotGenRequest(function_name=function_name, system_api_id=system_api_id), db=item_db, current_user=user_principal),
                timeout=SCENE_AI_SHOTS_BATCH_PER_SCENE_TIMEOUT_SEC,
            )
        )
        generated_rows = generated.get("content") if isinstance(generated, dict) else []
        if not isinstance(generated_rows, list) or len(generated_rows) == 0:
            raise RuntimeError("No parsed rows returned")

        apply_scene_ai_result(
            scene_id=scene_id,
            data=AnalysisContent(content=generated_rows, replace_existing=False),
            db=item_db,
            current_user=user_principal,
        )
        return {
            "scene_id": int(scene_id),
            "scene_label": scene_label,
            "ok": True,
        }
    except asyncio.TimeoutError:
        scene_label = str((scene.scene_no if 'scene' in locals() and scene else None) or (scene.scene_name if 'scene' in locals() and scene else None) or f"#{scene_id}")
        return {
            "scene_id": int(scene_id),
            "scene_label": scene_label,
            "ok": False,
            "error": f"scene processing exceeded {SCENE_AI_SHOTS_BATCH_PER_SCENE_TIMEOUT_SEC}s timeout",
        }
    except Exception as e:
        scene_label = str((scene.scene_no if 'scene' in locals() and scene else None) or (scene.scene_name if 'scene' in locals() and scene else None) or f"#{scene_id}")
        return {
            "scene_id": int(scene_id),
            "scene_label": scene_label,
            "ok": False,
            "error": str(e),
        }
    finally:
        item_db.close()


def _run_scene_ai_shots_batch_job(episode_id: int, scene_ids: List[int], user_id: int, batch_max_concurrency: int, function_name: Optional[str] = None, system_api_id: Optional[int] = None) -> None:
    try:
        with SessionLocal() as init_db:
            episode = init_db.query(Episode).filter(Episode.id == episode_id).first()
            user = init_db.query(User).filter(User.id == user_id).first()
            if not episode or not user:
                return

            user_name = str(user.username or f"user_{user_id}")
            project_id = int(episode.project_id)
            scene_label_map: Dict[int, str] = {}
            for sid in scene_ids:
                sc = init_db.query(Scene).filter(Scene.id == sid, Scene.episode_id == episode_id).first()
                if sc:
                    scene_label_map[sid] = str(sc.scene_no or sc.scene_name or f"#{sid}")

        job_id = f"scene-ai-shots-batch:{int(episode_id)}"

        total = len(scene_ids)
        completed = 0
        success = 0
        failed = 0
        errors: List[str] = []

        def _read_latest_episode(session: Session) -> Optional[Episode]:
            return (
                session.query(Episode)
                .execution_options(populate_existing=True)
                .filter(Episode.id == episode_id)
                .first()
            )

        def _stop_requested() -> bool:
            with SessionLocal() as status_db:
                latest_episode = _read_latest_episode(status_db)
                if not latest_episode:
                    return True
                latest_status = _read_scene_ai_shots_batch_status(latest_episode)
                return bool(latest_status.get("stop_requested") or latest_status.get("force_stopped"))

        effective_batch_max_concurrency = _resolve_user_batch_parallel_limit(
            batch_max_concurrency,
            default=SCENE_AI_SHOTS_BATCH_DEFAULT_CONCURRENCY,
        )
        next_scene_index = 0
        active_future_map: Dict[Any, int] = {}

        def _active_scene_ids() -> List[int]:
            return list(active_future_map.values())

        def _persist_active_scene_status(latest_message: Optional[str] = None) -> None:
            with SessionLocal() as status_db:
                latest_episode = _read_latest_episode(status_db)
                if not latest_episode:
                    return
                latest_status = _read_scene_ai_shots_batch_status(latest_episode)
                active_scene_ids = _active_scene_ids()
                active_scene_labels = [scene_label_map.get(sid) or f"#{sid}" for sid in active_scene_ids]
                latest_status["current_scene_id"] = active_scene_ids[0] if len(active_scene_ids) == 1 else None
                latest_status["current_scene_label"] = " / ".join(active_scene_labels)
                latest_status["current_scene_started_at"] = now_bj_iso() if active_scene_ids else latest_status.get("current_scene_started_at")
                latest_status["updated_at"] = now_bj_iso()
                if latest_message is not None:
                    latest_status["message"] = latest_message
                elif active_scene_labels:
                    latest_status["message"] = (
                        f"Processing scenes {', '.join(active_scene_labels)}..."
                        if len(active_scene_labels) > 1
                        else f"Processing scene {active_scene_labels[0]}..."
                    )
                _persist_scene_ai_shots_batch_status(status_db, latest_episode, latest_status)

        def _submit_next_scene(executor: ThreadPoolExecutor) -> bool:
            nonlocal next_scene_index
            if next_scene_index >= len(scene_ids):
                return False
            sid = scene_ids[next_scene_index]
            next_scene_index += 1
            active_future_map[executor.submit(_run_scene_ai_shots_batch_item, sid, episode_id, user_id, function_name, system_api_id)] = sid
            return True

        max_workers = max(1, min(effective_batch_max_concurrency, total or 1))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            while len(active_future_map) < max_workers and _submit_next_scene(executor):
                pass

            if _stop_requested():
                with SessionLocal() as status_db:
                    episode = _read_latest_episode(status_db)
                    if episode:
                        latest = _read_scene_ai_shots_batch_status(episode)
                        latest["running"] = False
                        latest["completed"] = completed
                        latest["success"] = success
                        latest["failed"] = failed
                        latest["errors"] = errors
                        latest["finished_at"] = now_bj_iso()
                        latest["stopped_by_user"] = True
                        latest["message"] = "Stopped by user request"
                        _persist_scene_ai_shots_batch_status(status_db, episode, latest)
                        _log_batch_sys_event(
                            kind="scene-ai-shots-batch",
                            phase="end",
                            user_id=user_id,
                            user_name=user_name,
                            project_id=project_id,
                            episode_id=episode_id,
                            job_id=job_id,
                            result="canceled",
                            message="Stopped by user request",
                            extra={"completed": completed, "success": success, "failed": failed},
                        )
                return
            _persist_active_scene_status()

            while active_future_map:
                completed_future = next(as_completed(list(active_future_map.keys())))
                sid = active_future_map.pop(completed_future)
                scene_label = scene_label_map.get(sid) or f"#{sid}"
                try:
                    result = completed_future.result()
                except Exception as e:
                    result = {
                        "scene_id": sid,
                        "scene_label": scene_label,
                        "ok": False,
                        "error": str(e),
                    }

                if bool(result.get("ok")):
                    success += 1
                    _log_batch_sys_event(
                        kind="scene-ai-shots-batch",
                        phase="item",
                        user_id=user_id,
                        user_name=user_name,
                        project_id=project_id,
                        episode_id=episode_id,
                        job_id=job_id,
                        item_id=sid,
                        item_label=result.get("scene_label") or scene_label,
                        result="success",
                        message="Scene AI shots generated",
                    )
                else:
                    failed += 1
                    error_message = str(result.get("error") or "Unknown error")
                    errors.append(f"{result.get('scene_label') or scene_label}: {error_message}")
                    _log_batch_sys_event(
                        kind="scene-ai-shots-batch",
                        phase="item",
                        user_id=user_id,
                        user_name=user_name,
                        project_id=project_id,
                        episode_id=episode_id,
                        job_id=job_id,
                        item_id=sid,
                        item_label=result.get("scene_label") or scene_label,
                        result="failed",
                        message=error_message,
                    )

                completed += 1
                with SessionLocal() as progress_db:
                    episode = _read_latest_episode(progress_db)
                    if not episode:
                        break

                    latest = _read_scene_ai_shots_batch_status(episode)
                    latest["completed"] = completed
                    latest["success"] = success
                    latest["failed"] = failed
                    latest["errors"] = errors
                    latest["current_scene_id"] = sid
                    latest["current_scene_label"] = result.get("scene_label") or scene_label
                    latest["updated_at"] = now_bj_iso()
                    latest["message"] = f"Progress {completed}/{total}"
                    _persist_scene_ai_shots_batch_status(progress_db, episode, latest)

                if not _stop_requested():
                    while len(active_future_map) < max_workers and _submit_next_scene(executor):
                        pass

                _persist_active_scene_status()

        if _stop_requested() and next_scene_index < len(scene_ids):
            with SessionLocal() as status_db:
                episode = _read_latest_episode(status_db)
                if episode:
                    latest_after_batch = _read_scene_ai_shots_batch_status(episode)
                    latest_after_batch["running"] = False
                    latest_after_batch["completed"] = completed
                    latest_after_batch["success"] = success
                    latest_after_batch["failed"] = failed
                    latest_after_batch["errors"] = errors
                    latest_after_batch["finished_at"] = now_bj_iso()
                    latest_after_batch["stopped_by_user"] = True
                    latest_after_batch["message"] = "Stopped by user request"
                    _persist_scene_ai_shots_batch_status(status_db, episode, latest_after_batch)
                    _log_batch_sys_event(
                        kind="scene-ai-shots-batch",
                        phase="end",
                        user_id=user_id,
                        user_name=user_name,
                        project_id=project_id,
                        episode_id=episode_id,
                        job_id=job_id,
                        result="canceled",
                        message="Stopped by user request",
                        extra={"completed": completed, "success": success, "failed": failed},
                    )
            return

        with SessionLocal() as final_db:
            episode = final_db.query(Episode).filter(Episode.id == episode_id).first()
            if episode:
                final_status = _read_scene_ai_shots_batch_status(episode)
                final_status["running"] = False
                final_status["completed"] = completed
                final_status["success"] = success
                final_status["failed"] = failed
                final_status["errors"] = errors
                final_status["finished_at"] = now_bj_iso()
                final_status["updated_at"] = final_status["finished_at"]
                final_status["stopped_by_user"] = bool(final_status.get("stop_requested"))
                final_status["message"] = f"Batch done: success {success}, failed {failed}"
                _persist_scene_ai_shots_batch_status(final_db, episode, final_status)
                _log_batch_sys_event(
                    kind="scene-ai-shots-batch",
                    phase="end",
                    user_id=user_id,
                    user_name=user_name,
                    project_id=project_id,
                    episode_id=episode_id,
                    job_id=job_id,
                    result="completed",
                    message=final_status.get("message"),
                    extra={"completed": completed, "success": success, "failed": failed},
                )
    except Exception as e:
        try:
            with SessionLocal() as error_db:
                episode = error_db.query(Episode).filter(Episode.id == episode_id).first()
                if episode:
                    failed_status = _read_scene_ai_shots_batch_status(episode)
                    failed_status["running"] = False
                    failed_status["finished_at"] = now_bj_iso()
                    failed_status["updated_at"] = failed_status["finished_at"]
                    failed_status["message"] = f"Batch failed: {str(e)}"
                    failed_status["errors"] = list(failed_status.get("errors") or []) + [str(e)]
                    _persist_scene_ai_shots_batch_status(error_db, episode, failed_status)
                    _log_batch_sys_event(
                        kind="scene-ai-shots-batch",
                        phase="end",
                        user_id=user_id,
                        user_name=str((user.username if 'user' in locals() and user else "") or f"user_{user_id}"),
                        project_id=int(episode.project_id),
                        episode_id=episode_id,
                        job_id=f"scene-ai-shots-batch:{int(episode_id)}",
                        result="failed",
                        message=str(e),
                    )
        except Exception:
            pass
    finally:
        _clear_episode_worker(SCENE_AI_SHOTS_BATCH_THREADS, SCENE_AI_SHOTS_BATCH_THREADS_LOCK, int(episode_id))


def _start_scene_ai_shots_batch_for_episode(
    db: Session,
    episode: Episode,
    current_user: User,
    scene_ids: Optional[List[int]] = None,
    function_name: Optional[str] = None,
    system_api_id: Optional[int] = None,
) -> Dict[str, Any]:
    episode_id = int(episode.id)
    latest_status = _read_scene_ai_shots_batch_status(episode)
    if bool(latest_status.get("running")):
        raise HTTPException(status_code=409, detail="Scene AI shots batch is already running")

    requested_scene_ids = [int(x) for x in (scene_ids or []) if x]
    scenes_query = db.query(Scene).filter(Scene.episode_id == episode_id, _active_scene_clause())
    if requested_scene_ids:
        scenes_query = scenes_query.filter(Scene.id.in_(requested_scene_ids))
    target_scenes = _sort_scenes_by_scene_no(scenes_query.all())
    scene_ids = [int(s.id) for s in target_scenes]
    if not scene_ids:
        raise HTTPException(status_code=400, detail="No saved scenes found for batch")

    batch_max_concurrency = _resolve_user_batch_parallel_limit(
        getattr(current_user, "is_active", USER_ACTIVE_LEVEL_DEFAULT),
        default=SCENE_AI_SHOTS_BATCH_DEFAULT_CONCURRENCY,
    )

    now_iso = now_bj_iso()
    status_payload = {
        "running": True,
        "project_id": episode.project_id,
        "episode_id": episode_id,
        "started_by_user_id": int(current_user.id),
        "started_by_username": str(current_user.username or ""),
        "scene_ids": scene_ids,
        "max_concurrency": batch_max_concurrency,
        "total": len(scene_ids),
        "completed": 0,
        "success": 0,
        "failed": 0,
        "current_scene_id": None,
        "current_scene_label": "",
        "message": "Batch task started",
        "errors": [],
        "stop_requested": False,
        "stop_requested_at": None,
        "force_stopped": False,
        "stopped_by_user": False,
        "started_at": now_iso,
        "updated_at": now_iso,
        "finished_at": None,
    }
    _persist_scene_ai_shots_batch_status(db, episode, status_payload)
    _log_batch_sys_event(
        kind="scene-ai-shots-batch",
        phase="start",
        user_id=current_user.id,
        user_name=current_user.username,
        project_id=episode.project_id,
        episode_id=episode_id,
        job_id=f"scene-ai-shots-batch:{int(episode_id)}",
        result="running",
        message="Batch task started",
        extra={"scene_ids": scene_ids, "total": len(scene_ids), "max_concurrency": batch_max_concurrency},
    )

    worker = threading.Thread(
        target=_run_scene_ai_shots_batch_job,
        args=(episode_id, scene_ids, current_user.id, batch_max_concurrency, function_name, system_api_id),
        daemon=True,
    )
    worker.start()
    _register_episode_worker(SCENE_AI_SHOTS_BATCH_THREADS, SCENE_AI_SHOTS_BATCH_THREADS_LOCK, int(episode_id), worker)

    return status_payload


@router.post("/episodes/{episode_id}/scenes/ai_shots/batch/start", response_model=Dict[str, Any])
def start_scene_ai_shots_batch(
    episode_id: int,
    req: SceneAiShotsBatchStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    return _start_scene_ai_shots_batch_for_episode(
        db=db,
        episode=episode,
        current_user=current_user,
        scene_ids=req.scene_ids or [],
        function_name=req.function_name,
        system_api_id=req.system_api_id,
    )


@router.get("/episodes/{episode_id}/scenes/ai_shots/batch/status", response_model=Dict[str, Any])
def get_scene_ai_shots_batch_status(
    episode_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _apply_no_store_headers(response)
    response.headers["X-Poll-Interval-Ms"] = "2500"
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    status_payload = _read_scene_ai_shots_batch_status(episode)
    if (
        bool(status_payload.get("running"))
        and _is_stale_running_payload(status_payload, stale_minutes=10)
        and not _is_episode_worker_alive(SCENE_AI_SHOTS_BATCH_THREADS, SCENE_AI_SHOTS_BATCH_THREADS_LOCK, int(episode_id))
    ):
        now_iso = now_bj_iso()
        status_payload["running"] = False
        status_payload["status"] = "canceled"
        status_payload["force_stopped"] = True
        status_payload["stopped_by_user"] = True
        status_payload["current_scene_id"] = None
        status_payload["current_scene_label"] = ""
        status_payload["updated_at"] = now_iso
        status_payload["finished_at"] = status_payload.get("finished_at") or now_iso
        status_payload["message"] = "Recovered orphaned task state (no active worker)"
        _persist_scene_ai_shots_batch_status(db, episode, status_payload)
    return _build_scene_ai_shots_batch_status_response(status_payload)


@router.post("/episodes/{episode_id}/scenes/ai_shots/batch/stop", response_model=Dict[str, Any])
def stop_scene_ai_shots_batch(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    removed = False
    info = _episode_runtime_info_from_episode(episode)
    if SCENE_AI_SHOTS_BATCH_STATUS_KEY in info:
        info.pop(SCENE_AI_SHOTS_BATCH_STATUS_KEY, None)
        episode.episode_info = info
        db.add(episode)
        db.commit()
        removed = True

    _clear_episode_worker(SCENE_AI_SHOTS_BATCH_THREADS, SCENE_AI_SHOTS_BATCH_THREADS_LOCK, int(episode_id))
    _log_batch_sys_event(
        kind="scene-ai-shots-batch",
        phase="stop",
        user_id=current_user.id,
        user_name=current_user.username,
        project_id=episode.project_id,
        episode_id=episode_id,
        job_id=f"scene-ai-shots-batch:{int(episode_id)}",
        result="canceled",
        message="Force removed by user",
    )
    return {
        "episode_id": int(episode_id),
        "running": False,
        "status": "canceled",
        "deleted": bool(removed),
        "message": "Force removed",
    }

@router.post("/scenes/{scene_id}/ai_generate_shots")
async def ai_generate_shots(
    scene_id: int,
    req: Optional[AIShotGenRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(ai_generate_shots, user_id=current_user.id,
                            kind="ai_generate_shots", scene_id=scene_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    current_user_id = int(getattr(current_user, "id", 0) or 0)
    try:
        req_has_custom_user_prompt = bool(req and (req.user_prompt or "").strip())
        req_has_custom_system_prompt = bool(req and (req.system_prompt or "").strip())
        logger.info(
            "[ai_generate_shots] start "
            f"scene_id={scene_id} user_id={current_user_id} "
            f"custom_user_prompt={req_has_custom_user_prompt} custom_system_prompt={req_has_custom_system_prompt}"
        )
        # 1. Fetch Scene and Context
        scene = db.query(Scene).filter(Scene.id == scene_id).first()
        if not scene:
            logger.warning(f"[ai_generate_shots] scene_not_found scene_id={scene_id} user_id={current_user_id}")
            raise HTTPException(status_code=404, detail="Scene not found")
            
        episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
        if not episode:
            logger.warning(
                f"[ai_generate_shots] episode_not_found scene_id={scene_id} episode_id={scene.episode_id} user_id={current_user_id}"
            )
            raise HTTPException(status_code=404, detail="Episode not found")

        try:
            project = _require_project_access(db, episode.project_id, current_user)
        except HTTPException:
            logger.warning(
                f"[ai_generate_shots] unauthorized_or_project_not_found "
                f"scene_id={scene_id} episode_id={episode.id} project_id={episode.project_id} user_id={current_user_id}"
            )
            raise

        logger.info(
            f"[ai_generate_shots] context scene_id={scene_id} episode_id={episode.id} project_id={project.id}"
        )

        if req and req.user_prompt:
             user_input = req.user_prompt
             system_prompt = req.system_prompt or "You are a Storyboard Master."
             logger.info("[ai_generate_shots] Using custom prompt from request")
        else:
               system_prompt, user_input = _build_shot_prompts(
                  db,
                  scene,
                  project,
                  mode=(req.shot_generation_mode if req else None),
                  explicit_features=(req.shot_generation_features if req else None),
               )

        logger.info(f"[ai_generate_shots] system_prompt_len={len(system_prompt)}")
        logger.info(f"[ai_generate_shots] user_input_len={len(user_input)}")

        # 4. Call LLM
        function_name = (getattr(req, "function_name", None) if req else None) or "script_analysis"
        system_api_id = getattr(req, "system_api_id", None) if req else None

        try:
            db.commit()
        except Exception:
            pass
        try:
            db.commit()
        except Exception:
            pass
        llm_config, selected_dropdown_id, dropdown_fallback_ids, dropdown_order_ids = _resolve_script_analysis_dropdown_llm_config(
            db,
            current_user_id,
            function_name,
            system_api_id,
            context="ai_generate_shots",
        )
            
        llm_config = _inject_user_advanced_llm_preferences(llm_config, current_user)
        llm_config = _inject_project_creativity_temperature(
            llm_config,
            project.global_info,
            context="ai_generate_shots",
        )
        
        # Billing (Reserve for token pricing)
        provider = llm_config.get("provider") 
        model = llm_config.get("model")
        logger.info(
            f"[ai_generate_shots] llm_selection source=dropdown_priority provider={provider} model={model} "
            f"scene_id={scene_id} selected_system_api_id={selected_dropdown_id} fallback_ids={dropdown_fallback_ids}"
        )
        reservation_tx = None
        reservation_tx_id: Optional[int] = None
        if billing_service.is_token_pricing(db, "llm_chat", provider, model):
            messages_est = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ]
            est = billing_service.estimate_reserve_tokens_from_messages(messages_est)
            reserve_details = {
                "item": "generate_shots",
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "system_prompt_len": len(system_prompt or ""),
                "user_prompt_len": len(user_input or ""),
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            }
            reservation_tx = billing_service.reserve_credits(db, current_user_id, "llm_chat", provider, model, reserve_details)
            try:
                reservation_tx_id = int(getattr(reservation_tx, "id", 0) or 0) or None
            except Exception:
                reservation_tx_id = None
            logger.info(
                f"[ai_generate_shots] token_reservation_created reservation_id={reservation_tx_id} "
                f"scene_id={scene_id} est_total_tokens={reserve_details.get('total_tokens', 0)}"
            )
        else:
            # Ensure we have at least a default task type if provider is missing (though check_balance handles None)
            billing_service.check_balance(db, current_user_id, "llm_chat", provider, model)

        _release_db_connection(db, "ai_generate_shots_llm_call")
        response_dict = await llm_service.generate_content_with_fallback(
            user_input,
            system_prompt,
            llm_config,
            response_validator=_build_ai_shots_response_validator(
                context="ai_generate_shots",
                scene_id=scene_id,
                user_id=current_user_id,
                source_label="Generate Shots",
                strip_reasoning_prefixes=True,
            ),
        )
        response_content_raw = response_dict.get("content", "")
        usage = response_dict.get("usage", {})

        logger.info(
            f"[ai_generate_shots] llm_response_received scene_id={scene_id} "
            f"llm_response_len_raw={len(response_content_raw)} usage_keys={list((usage or {}).keys())}"
        )

        if str(response_content_raw).startswith("Error:"):
            if reservation_tx_id is not None:
                billing_service.cancel_reservation(db, reservation_tx_id, str(response_content_raw))
            status_code = 502 if bool(response_dict.get("_postprocess_validation_failed")) else 500
            raise HTTPException(status_code=status_code, detail=str(response_content_raw))

        raw_str = str(response_content_raw or "").strip()
        if not raw_str:
            logger.warning(f"[ai_generate_shots] empty_llm_response scene_id={scene_id} user_id={current_user_id}")
            if reservation_tx_id is not None:
                billing_service.cancel_reservation(db, reservation_tx_id, "empty llm response")
            raise HTTPException(status_code=502, detail="LLM returned empty response")

        # Keep original model output for read-only auditing in UI.
        raw_text_original = str(response_content_raw or "")

        # Force-remove common reasoning leakage (e.g., "analysis", <think> blocks)
        # before moderation classification, parsing, and persistence.
        response_content = sanitize_llm_markdown_output(response_content_raw)

        if _is_provider_moderation_block_response(raw_str, response_content):
            logger.warning(
                f"[ai_generate_shots] prohibited_content_marker_detected scene_id={scene_id} user_id={current_user_id}"
            )
            if reservation_tx_id is not None:
                billing_service.cancel_reservation(db, reservation_tx_id, "provider moderation block")
            raise HTTPException(status_code=502, detail="Provider moderation blocked shot generation (PROHIBITED_CONTENT)")

        reasoning_prefix_terms = [
            "i will",
            "let me",
            "let's",
            "analysis",
            "reasoning",
            "thought process",
            "分析",
            "思路",
            "推理",
            "我将",
            "我认为",
            "我認為",
        ]
        try:
            escaped_terms = [re.escape(term) for term in reasoning_prefix_terms if str(term or "").strip()]
            reasoning_line_re = re.compile(
                r"^\s*(?:" + "|".join(escaped_terms) + r")\b",
                flags=re.IGNORECASE,
            )
        except re.error as re_err:
            logger.warning("[ai_generate_shots] reasoning regex compile failed, fallback used: %s", re_err)
            reasoning_line_re = re.compile(r"^\s*(?:analysis|reasoning)\b", flags=re.IGNORECASE)
        cleaned_lines = []
        for line in str(response_content or "").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("|") and reasoning_line_re.match(stripped):
                continue
            cleaned_lines.append(line)
        response_content = "\n".join(cleaned_lines).strip()

        # Keep only markdown table payload for shot generation flows.
        response_content = sanitize_shots_markdown_table_text(response_content)

        if not response_content:
            logger.warning(
                f"[ai_generate_shots] empty_after_sanitize scene_id={scene_id} user_id={current_user_id} raw_len={len(raw_str)}"
            )
            if reservation_tx_id is not None:
                billing_service.cancel_reservation(db, reservation_tx_id, "empty response after sanitize")
            raise HTTPException(status_code=502, detail="LLM response became empty after sanitize")

        logger.info(
            f"[ai_generate_shots] llm_response_cleaned scene_id={scene_id} llm_response_len_clean={len(response_content)}"
        )

        # Billing finalize
        if reservation_tx_id is not None:
            actual_details = {"item": "generate_shots"}
            if usage:
                actual_details.update(usage)
            _apply_llm_routing_to_billing_details(actual_details, response_dict)
            if "prompt_tokens" in actual_details and "input_tokens" not in actual_details:
                actual_details["input_tokens"] = actual_details.get("prompt_tokens", 0)
            if "completion_tokens" in actual_details and "output_tokens" not in actual_details:
                actual_details["output_tokens"] = actual_details.get("completion_tokens", 0)
            billing_service.settle_reservation(db, reservation_tx_id, actual_details)
            logger.info(
                f"[ai_generate_shots] token_reservation_settled reservation_id={reservation_tx_id} "
                f"scene_id={scene_id} actual_keys={list(actual_details.keys())}"
            )
        else:
            details = {"item": "generate_shots"}
            if usage:
                details.update(usage)
            _apply_llm_routing_to_billing_details(details, response_dict)
            if "prompt_tokens" in details and "input_tokens" not in details:
                details["input_tokens"] = details.get("prompt_tokens", 0)
            if "completion_tokens" in details and "output_tokens" not in details:
                details["output_tokens"] = details.get("completion_tokens", 0)
            billing_service.deduct_credits(db, current_user_id, "llm_chat", provider, model, details)
            logger.info(
                f"[ai_generate_shots] credits_deducted scene_id={scene_id} detail_keys={list(details.keys())}"
            )

        # 5. Parse Table
        headers, shots_data, table_line_count = parse_shots_markdown_table(response_content)
        if headers:
            logger.info(f"[ai_generate_shots] headers detected: {headers}")

        if not shots_data:
             logger.warning(f"DEBUG: No table found using delimiter |. Content snippet: {response_content[:200]}")
             raw_preview = response_content.replace("\n", " ")[:300]
             raise HTTPException(status_code=502, detail=f"Generate Shots returned 0 parsed rows; raw preview: {raw_preview}")
             
        logger.info(
            f"[ai_generate_shots] parsed_result scene_id={scene_id} table_lines={table_line_count} parsed_shots={len(shots_data)}"
        )
        if table_line_count >= 4 and len(shots_data) > 0 and (len(shots_data) * 2) <= table_line_count:
            logger.warning(
                f"[ai_generate_shots] suspicious_row_drop scene_id={scene_id} "
                f"table_lines={table_line_count} parsed_shots={len(shots_data)}"
            )
            raise HTTPException(
                status_code=502,
                detail="Shot generation output may have lost rows during markdown parsing; regenerate before apply.",
            )

        # Reject tables that cannot be applied (same structural rules as apply_ai_result).
        # Use tolerance so a single imperfect row does not discard an otherwise valid table;
        # fail only when zero rows remain applyable.
        try:
            shots_data, generate_skipped = _validate_shot_rows_for_apply_with_tolerance(
                shots_data,
                source_label="Generated shot table",
                status_code=502,
            )
            if generate_skipped:
                logger.warning(
                    "[ai_generate_shots] skipped_invalid_rows scene_id=%s skipped=%s details=%s",
                    scene_id,
                    len(generate_skipped),
                    generate_skipped[:5],
                )
        except HTTPException as exc:
            logger.warning(
                "[ai_generate_shots] structural_validation_failed scene_id=%s detail=%s",
                scene_id,
                str(getattr(exc, "detail", None) or exc)[:800],
            )
            raise

        # 6. Persist staging result only (no DB-shot import here)
        result_wrapper = _persist_scene_shot_generation_result(
            db=db,
            scene_id=scene_id,
            raw_text=raw_text_original,
            markdown_text=response_content,
            rows=shots_data,
            usage=usage,
        )
        if generate_skipped:
            result_wrapper["warnings"] = list(
                dict.fromkeys(
                    [str(w or "").strip() for w in (result_wrapper.get("warnings") or []) if str(w or "").strip()]
                    + [str(w or "").strip() for w in generate_skipped if str(w or "").strip()]
                )
            )

        logger.info(
            f"[ai_generate_shots] response_ready scene_id={scene_id} "
            f"response_keys={list(result_wrapper.keys())} content_count={len(result_wrapper.get('content') or [])}"
        )
        
        # Return the raw data so frontend can display it in the "Edit" modal
        return result_wrapper

    except HTTPException as e:
        logger.warning(
            f"[ai_generate_shots] http_exception scene_id={scene_id} user_id={current_user_id} "
            f"status_code={e.status_code} detail={e.detail}"
        )
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.exception(f"[ai_generate_shots] unhandled_error scene_id={scene_id} user_id={current_user_id} error={e}")
        # Log failure
        try:
            p_log = locals().get('provider')
            m_log = locals().get('model')
            billing_service.log_failed_transaction(db, current_user_id, "llm_chat", p_log, m_log, str(e))
        except: pass
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenes/{scene_id}/ai_regenerate_shots")
async def ai_regenerate_shots(
    scene_id: int,
    req: Optional[AIShotRegenerateRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(
            ai_regenerate_shots,
            user_id=current_user.id,
            kind="ai_regenerate_shots",
            scene_id=scene_id,
            req=req,
            async_mode="0",
        )
        return JSONResponse({"task_id": tid, "async": True})
    current_user_id = int(getattr(current_user, "id", 0) or 0)

    try:
        scene = db.query(Scene).filter(Scene.id == scene_id).first()
        if not scene:
            raise HTTPException(status_code=404, detail="Scene not found")

        episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
        if not episode:
            raise HTTPException(status_code=404, detail="Episode not found")

        project = _require_project_access(db, episode.project_id, current_user)

        staged_rows = []
        staged_markdown = ""
        if req and isinstance(req.content, list) and req.content:
            staged_rows, staged_markdown = _validate_shot_rows_roundtrip_or_raise(
                req.content,
                source_label="Current staged shot table",
                status_code=400,
            )
        else:
            stored_markdown = str(scene.ai_shots_result or "").strip()
            if not stored_markdown:
                raise HTTPException(
                    status_code=400,
                    detail="No staged AI shot markdown is available for regeneration",
                )
            _, parsed_rows, _ = _parse_shot_markdown_or_raise(
                stored_markdown,
                source_label="Stored staged shot table",
                status_code=400,
            )
            staged_rows, staged_markdown = _validate_shot_rows_roundtrip_or_raise(
                parsed_rows,
                source_label="Stored staged shot table",
                status_code=400,
            )

        prompt_filename = str((req.prompt_file if req else "") or "skills/shot_generation.md").strip() or "skills/shot_generation.md"
        try:
            if prompt_filename != "skills/shot_generation.md":
                system_prompt = _resolve_prompt_text(prompt_filename)
                _, base_user_prompt = _build_shot_prompts(db, scene, project)
                user_input = (
                    f"# Scene Context Reference\n{str(base_user_prompt or '').strip()}\n\n"
                    f"# Current Staged Shot Markdown\n{staged_markdown}\n\n"
                    f"# User Supplement Instructions\n{str((req.additional_instructions if req else '') or '').strip() or '(none)'}\n"
                )
            else:
                system_prompt, user_input = _build_shot_regenerate_prompts(
                    db,
                    scene,
                    project,
                    staged_markdown=staged_markdown,
                    additional_instructions=str((req.additional_instructions if req else "") or "").strip(),
                    mode=(req.shot_generation_mode if req else None),
                    explicit_features=(req.shot_generation_features if req else None),
                )
        except FileNotFoundError:
            raise HTTPException(status_code=500, detail=f"Prompt file '{prompt_filename}' could not be loaded.")

        function_name = (getattr(req, "function_name", None) if req else None) or "script_analysis"
        system_api_id = getattr(req, "system_api_id", None) if req else None

        try:
            db.commit()
        except Exception:
            pass
        try:
            db.commit()
        except Exception:
            pass
        llm_config, selected_dropdown_id, dropdown_fallback_ids, dropdown_order_ids = _resolve_script_analysis_dropdown_llm_config(
            db,
            current_user_id,
            function_name,
            system_api_id,
            context="ai_regenerate_shots",
        )

        llm_config = _inject_user_advanced_llm_preferences(llm_config, current_user)
        llm_config = _inject_project_creativity_temperature(
            llm_config,
            project.global_info,
            context="ai_regenerate_shots",
        )

        provider = llm_config.get("provider")
        model = llm_config.get("model")
        reservation_tx = None
        reservation_tx_id: Optional[int] = None
        if billing_service.is_token_pricing(db, "llm_chat", provider, model):
            messages_est = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ]
            est = billing_service.estimate_reserve_tokens_from_messages(messages_est)
            reserve_details = {
                "item": "regenerate_shots",
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "system_prompt_len": len(system_prompt or ""),
                "user_prompt_len": len(user_input or ""),
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            }
            reservation_tx = billing_service.reserve_credits(db, current_user_id, "llm_chat", provider, model, reserve_details)
            try:
                reservation_tx_id = int(getattr(reservation_tx, "id", 0) or 0) or None
            except Exception:
                reservation_tx_id = None
        else:
            billing_service.check_balance(db, current_user_id, "llm_chat", provider, model)

        _release_db_connection(db, "ai_regenerate_shots_llm_call")
        response_dict = await llm_service.generate_content_with_fallback(
            user_input,
            system_prompt,
            llm_config,
            response_validator=_build_ai_shots_response_validator(
                context="ai_regenerate_shots",
                scene_id=scene_id,
                user_id=current_user_id,
                source_label="Regenerate Shots",
                validate_regenerate_markers=True,
            ),
        )
        response_content_raw = response_dict.get("content", "")
        usage = response_dict.get("usage", {})

        if str(response_content_raw).startswith("Error:"):
            if reservation_tx_id is not None:
                billing_service.cancel_reservation(db, reservation_tx_id, str(response_content_raw))
            status_code = 502 if bool(response_dict.get("_postprocess_validation_failed")) else 500
            raise HTTPException(status_code=status_code, detail=str(response_content_raw))

        raw_str = str(response_content_raw or "").strip()
        if not raw_str:
            if reservation_tx_id is not None:
                billing_service.cancel_reservation(db, reservation_tx_id, "empty llm response")
            raise HTTPException(status_code=502, detail="LLM returned empty response")

        raw_text_original = str(response_content_raw or "")

        response_content = sanitize_llm_markdown_output(response_content_raw)
        if _is_provider_moderation_block_response(raw_str, response_content):
            if reservation_tx_id is not None:
                billing_service.cancel_reservation(db, reservation_tx_id, "provider moderation block")
            raise HTTPException(status_code=502, detail="Provider moderation blocked shot regeneration (PROHIBITED_CONTENT)")

        # Keep only markdown table payload for shot regeneration flows.
        response_content = sanitize_shots_markdown_table_text(response_content)

        if not response_content:
            if reservation_tx_id is not None:
                billing_service.cancel_reservation(db, reservation_tx_id, "empty response after sanitize")
            raise HTTPException(status_code=502, detail="LLM response became empty after sanitize")

        if reservation_tx_id is not None:
            actual_details = {"item": "regenerate_shots"}
            if usage:
                actual_details.update(usage)
            _apply_llm_routing_to_billing_details(actual_details, response_dict)
            if "prompt_tokens" in actual_details and "input_tokens" not in actual_details:
                actual_details["input_tokens"] = actual_details.get("prompt_tokens", 0)
            if "completion_tokens" in actual_details and "output_tokens" not in actual_details:
                actual_details["output_tokens"] = actual_details.get("completion_tokens", 0)
            billing_service.settle_reservation(db, reservation_tx_id, actual_details)
        else:
            details = {"item": "regenerate_shots"}
            if usage:
                details.update(usage)
            _apply_llm_routing_to_billing_details(details, response_dict)
            if "prompt_tokens" in details and "input_tokens" not in details:
                details["input_tokens"] = details.get("prompt_tokens", 0)
            if "completion_tokens" in details and "output_tokens" not in details:
                details["output_tokens"] = details.get("completion_tokens", 0)
            billing_service.deduct_credits(db, current_user_id, "llm_chat", provider, model, details)

        headers, regenerated_rows, table_line_count = parse_shots_markdown_table(response_content)
        if not regenerated_rows:
            raw_preview = response_content.replace("\n", " ")[:300]
            raise HTTPException(status_code=502, detail=f"Regenerate Shots returned 0 parsed rows; raw preview: {raw_preview}")
        if table_line_count >= 4 and len(regenerated_rows) > 0 and (len(regenerated_rows) * 2) <= table_line_count:
            raise HTTPException(
                status_code=502,
                detail="Shot regeneration output may have lost rows during markdown parsing; regenerate before apply.",
            )

        validated_rows = _validate_shot_rows_or_raise(
            regenerated_rows,
            source_label="Regenerated shot diff table",
            status_code=502,
        )

        marker_errors: List[str] = []
        for idx, row in enumerate(validated_rows, start=1):
            shot_id = _pick_shot_cell(row, ["Shot ID", "shot_id", "镜头ID"], "")
            shot_logic = _pick_shot_cell(row, ["Shot Logic (CN)", "shot_logic_cn", "镜头逻辑", "镜头逻辑（中文）"], "")
            marker_mode, _ = _extract_shot_regenerate_marker(shot_logic)
            if marker_mode not in {"update", "add"}:
                marker_errors.append(f"row {idx} ({shot_id or 'unknown shot'}) missing required Shot Logic marker")
                continue
            if marker_mode == "add" and not re.search(r"_\d+$", str(shot_id or "")):
                marker_errors.append(f"row {idx} ({shot_id or 'unknown shot'}) add-shot id must use _1/_2 style suffix")

        if marker_errors:
            detail = "; ".join(marker_errors[:5])
            if len(marker_errors) > 5:
                detail += f"; and {len(marker_errors) - 5} more rows"
            raise HTTPException(status_code=502, detail=f"Regenerated shot diff failed marker validation: {detail}")

        return {
            "timestamp": now_bj_iso(),
            "raw_text": raw_text_original,
            "content": validated_rows,
            "usage": usage,
            "warnings": [],
            "source_row_count": len(staged_rows),
            "result_row_count": len(validated_rows),
            "headers": headers,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "[ai_regenerate_shots] unhandled_error scene_id=%s user_id=%s error=%s",
            scene_id,
            current_user_id,
            e,
        )
        try:
            p_log = locals().get("provider")
            m_log = locals().get("model")
            billing_service.log_failed_transaction(db, current_user_id, "llm_chat", p_log, m_log, str(e))
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/scenes/{scene_id}/latest_ai_result")
def get_scene_latest_ai_result(
    scene_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Get the latest saved AI shot generation result for a scene.

    Storage (Scheme A): scenes.ai_shots_result is the raw Markdown table text.
    This endpoint returns a structured wrapper for the UI by parsing that Markdown.
    """
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    _require_project_access(db, episode.project_id, current_user)
         
    raw_value = scene.ai_shots_result
    if not raw_value:
        return {}

    # Backward compat: older versions stored JSON wrapper into scenes.ai_shots_result
    if isinstance(raw_value, str) and raw_value.strip().startswith('{'):
        try:
            legacy = json.loads(raw_value)
            if isinstance(legacy, dict) and ("raw_text" in legacy or "content" in legacy):
                raw_text = legacy.get("raw_text") or ""
                if raw_text:
                    scene.ai_shots_result = raw_text
                    db.commit()
                    raw_value = raw_text
                else:
                    # No raw_text; best effort keep the JSON string as raw.
                    raw_value = scene.ai_shots_result
        except Exception:
            pass

    # Parse markdown table into list-of-dicts for the staging editor
    warnings: List[str] = []
    _, shots_data, table_line_count = parse_shots_markdown_table(raw_value or "")
    if str(raw_value or "").strip() and not shots_data:
        warnings.append("Shot generation output did not produce a parseable markdown table; review the raw markdown before apply.")
    if table_line_count >= 4 and len(shots_data) > 0 and (len(shots_data) * 2) <= table_line_count:
        logger.warning(
            f"[get_scene_latest_ai_result] suspicious_row_drop scene_id={scene_id} "
            f"table_lines={table_line_count} parsed_shots={len(shots_data)}"
        )
        warnings.append("Shot generation output may have lost rows during markdown parsing; review the raw markdown before apply.")

    return {
        "raw_text": raw_value,
        "content": shots_data,
        "warnings": warnings,
    }

@router.put("/scenes/{scene_id}/latest_ai_result")
def update_scene_latest_ai_result(
    scene_id: int,
    data: AnalysisContent, # Reusing this schema: { "content": ... }
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Update (Save/Edit) the latest shot generation result without applying it.
    Expects data.content to be the list of shot dictionaries.
    """
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    _require_project_access(db, episode.project_id, current_user)
    
    validated_rows, md = _validate_shot_rows_roundtrip_or_raise(
        data.content,
        source_label="Edited scene shot table",
        status_code=400,
    )

    scene.ai_shots_result = md
    db.commit()

    return {
        "timestamp": now_bj_iso(),
        "raw_text": md,
        "content": validated_rows,
    }


def _import_scene_shot_rows_to_db(
    *,
    scene_id: int,
    db: Session,
    scene: Scene,
    episode: Episode,
    project: Project,
    shots_data: List[Dict[str, Any]],
    skipped_row_errors: Optional[List[str]] = None,
    replace_existing: bool = False,
) -> List[Shot]:
    """
    Import validated shot rows into Shot table.
    This method is DB-import only and does NOT call LLM or write staged LLM markdown.

    Default policy: if the scene already has active shots, abandon the import
    (unless replace_existing=True for intentional UI replace).
    """
    skipped_row_errors = list(skipped_row_errors or [])

    locked_scene = db.query(Scene).filter(Scene.id == scene_id).with_for_update().first()
    if not locked_scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    existing_shots = db.query(Shot).filter(Shot.scene_id == scene_id, _active_shot_clause()).all()
    existing_count = len(existing_shots or [])
    if existing_count > 0 and not replace_existing:
        logger.info(
            "[apply_scene_ai_result] abandon_import scene already has shots | scene_id=%s count=%s",
            scene_id,
            existing_count,
        )
        raise HTTPException(
            status_code=409,
            detail=(
                f"Scene already has {existing_count} shot(s); import abandoned. "
                "Delete existing shots first, or pass replace_existing=true to overwrite."
            ),
        )

    deduped_shots_data, dedupe_warnings = _dedupe_shot_rows_for_import(
        list(shots_data or []),
        scene_id=scene_id,
    )
    for warning in dedupe_warnings:
        skipped_row_errors.append(f"dedupe: {warning}")
    shots_data = deduped_shots_data

    # Episode-scoped uniqueness: project + episode + Shot ID (active rows only).
    # Blocks duplicate-scene imports from writing the same EP##_SC##_SH## twice.
    conflicting: List[str] = []
    for idx, row in enumerate(shots_data or [], start=1):
        raw_shot_id = _pick_shot_cell(row, ["Shot ID", "shot_id", "镜头ID"], "")
        business_id = _normalize_shot_business_id(raw_shot_id)
        if not business_id:
            continue
        if isinstance(row, dict):
            # Persist normalized business id so unique index compares consistently.
            for key in ("Shot ID", "shot_id", "镜头ID"):
                if key in row:
                    row[key] = business_id
                    break
            else:
                row["Shot ID"] = business_id
        # When replacing, this scene's actives will be soft-deleted first — only other scenes conflict.
        dup = _find_active_shot_by_business_id(
            db,
            project_id=int(project.id),
            episode_id=int(episode.id),
            shot_id=business_id,
            exclude_scene_id=int(scene_id) if replace_existing else None,
        )
        if dup is not None:
            conflicting.append(
                f"{business_id} (existing scene_id={getattr(dup, 'scene_id', None)} db_id={getattr(dup, 'id', None)})"
            )
    if conflicting:
        sample = "; ".join(conflicting[:5])
        more = f"; and {len(conflicting) - 5} more" if len(conflicting) > 5 else ""
        logger.info(
            "[apply_scene_ai_result] abandon_import episode-unique Shot ID conflict | scene_id=%s episode_id=%s conflicts=%s",
            scene_id,
            getattr(episode, "id", None),
            len(conflicting),
        )
        raise HTTPException(
            status_code=409,
            detail=(
                f"Shot ID already exists in this project/episode; import abandoned. "
                f"Conflicts: {sample}{more}"
            ),
        )

    # 1) Extract and normalize associated entities text only (no auto-create).
    try:
        if shots_data:
            existing_entities = db.query(Entity).filter(Entity.project_id == project.id).all()
            entity_map = {e.name: e for e in existing_entities}
            new_entities_buffer = set()

            for s_data in shots_data:
                assoc_str = s_data.get("Associated Entities", "")
                if assoc_str and assoc_str.lower() != "none" and assoc_str.strip():
                    potential_names = [n.strip() for n in re.split(r'[,\uff0c]', assoc_str) if n.strip()]
                    cleaned_names = []
                    for name in potential_names:
                        if name in entity_map:
                            cleaned_names.append(name)
                        elif name in new_entities_buffer:
                            cleaned_names.append(name)
                        else:
                            cleaned_names.append(name)
                    s_data["Associated Entities"] = ", ".join(cleaned_names)
    except Exception as e:
        logger.error(f"[Import] Entity auto-linking failed: {e}")

    # 2) Replace scene shots with imported rows (only when empty or replace_existing).
    old_shot_map = {(str(s.shot_id or "").strip()): s for s in existing_shots if str(s.shot_id or "").strip()}
    _soft_delete_shots(db, scene_id=scene_id)

    def _split_combined_cn_prompt(raw_text: str) -> Tuple[str, str, str, str]:
        text = str(raw_text or "").strip()
        if not text:
            return "", "", "", ""
        lines = [ln.strip() for ln in re.split(r"\n|<br\\s*/?>", text) if ln and ln.strip()]
        start_cn = ""
        video_cn = ""
        keyframes_cn = ""
        end_cn = ""
        for ln in lines:
            lower_ln = ln.lower()
            if (
                lower_ln.startswith("start frame:")
                or lower_ln.startswith("start frame cn:")
                or lower_ln.startswith("start:")
                or ln.startswith("起始帧:")
                or ln.startswith("起始帧：")
            ):
                start_cn = re.sub(r"^(start\s*frame\s*(cn)?\s*:|start\s*:|起始帧\s*[:：])", "", ln, flags=re.IGNORECASE).strip()
                continue
            if lower_ln.startswith("video:") or lower_ln.startswith("video cn:") or ln.startswith("视频:") or ln.startswith("视频提示词:"):
                video_cn = re.sub(r"^(video\s*(cn)?\s*:|视频提示词\s*[:：]|视频\s*[:：])", "", ln, flags=re.IGNORECASE).strip()
                continue
            if (
                lower_ln.startswith("keyframes:")
                or lower_ln.startswith("keyframes cn:")
                or lower_ln.startswith("keyframe:")
                or ln.startswith("关键帧:")
                or ln.startswith("关键帧：")
            ):
                keyframes_cn = re.sub(r"^(key\s*frames?\s*(cn)?\s*:|关键帧\s*[:：])", "", ln, flags=re.IGNORECASE).strip()
                continue
            if (
                lower_ln.startswith("end frame:")
                or lower_ln.startswith("end frame cn:")
                or lower_ln.startswith("end:")
                or ln.startswith("收尾帧:")
                or ln.startswith("收尾帧：")
                or ln.startswith("结束帧:")
                or ln.startswith("结束帧：")
            ):
                end_cn = re.sub(r"^(end\s*frame\s*(cn)?\s*:|end\s*:|收尾帧\s*[:：]|结束帧\s*[:：])", "", ln, flags=re.IGNORECASE).strip()
                continue

        if not start_cn and not video_cn and not keyframes_cn and not end_cn:
            return text, text, text, text
        if not end_cn and start_cn:
            end_cn = start_cn
        return start_cn, video_cn, keyframes_cn, end_cn

    known_col_aliases = [
        "Shot ID", "shot_id", "镜头ID",
        "Shot Name", "shot_name", "镜头名称",
        "Scene ID", "scene_id", "Scene Code", "scene_code", "场景ID", "场次号",
        "Start Frame", "start_frame", "起始帧",
        "End Frame", "end_frame", "结束帧",
        "Video Content", "video_content", "视频内容",
        "Duration (s)", "Duration", "duration", "时长", "时长(s)",
        "Associated Entities", "associated_entities", "关联实体",
        "Shot Logic (CN)", "shot_logic_cn", "镜头逻辑", "镜头逻辑（中文）",
        "Keyframes", "keyframes", "关键帧",
        "Prompt (CN)", "Prompts (CN)", "Prompt CN", "prompt_cn", "提示词（中文）", "中文提示词",
        "Start Frame (CN)", "start_frame_cn", "起始帧（中文）",
        "Video Content (CN)", "video_prompt_cn", "视频内容（中文）",
        "Keyframes (CN)", "keyframes_cn", "关键帧（中文）", "关键帧中文",
        "End Frame (CN)", "end_frame_cn", "结束帧（中文）",
    ]
    known_col_norm_set = {_normalize_shot_markdown_col_key(k) for k in known_col_aliases}

    for idx, s_data in enumerate(shots_data):
        try:
            dur_val = 2.0
            raw_duration = _pick_shot_cell(s_data, ["Duration (s)", "Duration", "duration", "时长", "时长(s)"], "")
            if raw_duration:
                match = re.search(r"[\d\.]+", str(raw_duration))
                dur_val = float(match.group()) if match else 2.0
        except Exception:
            dur_val = 2.0

        start_frame_text = _pick_shot_cell(s_data, ["Start Frame", "start_frame", "起始帧"], "")
        end_frame_text = _pick_shot_cell(s_data, ["End Frame", "end_frame", "结束帧"], "")
        video_content_text = _pick_shot_cell(s_data, ["Video Content", "video_content", "视频内容"], "")
        associated_entities_text = _pick_shot_cell(s_data, ["Associated Entities", "associated_entities", "关联实体"], "")
        shot_logic_cn_text = _pick_shot_cell(s_data, ["Shot Logic (CN)", "shot_logic_cn", "镜头逻辑", "镜头逻辑（中文）"], "")
        keyframes_text = _pick_shot_cell(s_data, ["Keyframes", "keyframes", "关键帧"], "NO")
        scene_code_text = _pick_shot_cell(s_data, ["Scene ID", "scene_id", "Scene Code", "scene_code", "场景ID", "场次号"], scene.scene_no or "")
        shot_id_text = _pick_shot_cell(s_data, ["Shot ID", "shot_id", "镜头ID"], str(idx + 1))
        shot_name_text = _pick_shot_cell(s_data, ["Shot Name", "shot_name", "镜头名称"], "Shot")

        prompt_cn_combined = _pick_shot_cell(
            s_data,
            ["Prompt (CN)", "Prompts (CN)", "Prompt CN", "prompt_cn", "提示词（中文）", "中文提示词"],
            "",
        )
        start_frame_cn_text = _pick_shot_cell(s_data, ["Start Frame (CN)", "start_frame_cn", "起始帧（中文）"], "")
        video_prompt_cn_text = _pick_shot_cell(s_data, ["Video Content (CN)", "video_prompt_cn", "视频内容（中文）"], "")
        keyframes_cn_text = _pick_shot_cell(s_data, ["Keyframes (CN)", "keyframes_cn", "关键帧（中文）", "关键帧中文"], "")
        end_frame_cn_text = _pick_shot_cell(s_data, ["End Frame (CN)", "end_frame_cn", "结束帧（中文）"], "")

        if prompt_cn_combined:
            start_cn_fallback, video_cn_fallback, keyframes_cn_fallback, end_cn_fallback = _split_combined_cn_prompt(prompt_cn_combined)
            if not start_frame_cn_text:
                start_frame_cn_text = start_cn_fallback
            if not end_frame_cn_text:
                end_frame_cn_text = end_cn_fallback
            if not video_prompt_cn_text:
                video_prompt_cn_text = video_cn_fallback
            if not keyframes_cn_text:
                keyframes_cn_text = keyframes_cn_fallback

        technical_notes_payload: Dict[str, Any] = {}
        if start_frame_cn_text:
            technical_notes_payload["start_frame_cn"] = start_frame_cn_text
        if video_prompt_cn_text:
            technical_notes_payload["video_prompt_cn"] = video_prompt_cn_text
        if keyframes_cn_text:
            technical_notes_payload["keyframes_cn"] = keyframes_cn_text
        if end_frame_cn_text:
            technical_notes_payload["end_frame_cn"] = end_frame_cn_text
        if start_frame_cn_text or video_prompt_cn_text or keyframes_cn_text or end_frame_cn_text:
            technical_notes_payload["shot_prompt_cn"] = "<br>".join([
                f"起始帧：{start_frame_cn_text or ''}",
                f"视频：{video_prompt_cn_text or ''}",
                f"关键帧：{keyframes_cn_text or ''}",
                f"收尾帧：{end_frame_cn_text or ''}",
            ])

        extra_columns: Dict[str, str] = {}
        if isinstance(s_data, dict):
            for raw_key, raw_val in s_data.items():
                nk = _normalize_shot_markdown_col_key(raw_key)
                if nk in known_col_norm_set:
                    continue
                val = str(raw_val or "").strip()
                if not val:
                    continue
                rule = SHOT_MARKDOWN_COLUMN_WHITELIST.get(nk)
                if rule and rule.get("target") == "tech_field":
                    tech_key = str(rule.get("field") or "").strip()
                    if tech_key:
                        technical_notes_payload[tech_key] = val
                        continue
                extra_columns[str(raw_key)] = val
        if extra_columns:
            technical_notes_payload["shot_extra_columns"] = extra_columns

        normalized_shot_id = _normalize_shot_business_id(shot_id_text) or str(shot_id_text or "").strip()
        old_shot = old_shot_map.get(normalized_shot_id) or old_shot_map.get(str(shot_id_text).strip())
        preserved_image_url = None
        preserved_video_url = None
        if old_shot:
            preserved_image_url = old_shot.image_url
            preserved_video_url = old_shot.video_url
            try:
                old_tech = json.loads(old_shot.technical_notes) if old_shot.technical_notes else {}
                for k, v in old_tech.items():
                    if k.endswith("_url") or k.endswith("_urls") or k in {"start_frame_supported", "supports_start_frame"}:
                        if k not in technical_notes_payload:
                            technical_notes_payload[k] = v
            except Exception:
                pass

        shot = Shot(
            scene_id=scene_id,
            project_id=project.id,
            episode_id=episode.id,
            shot_id=normalized_shot_id,
            shot_name=shot_name_text,
            scene_code=scene_code_text,
            start_frame=start_frame_text,
            end_frame=end_frame_text,
            video_content=video_content_text,
            duration=str(dur_val),
            associated_entities=associated_entities_text,
            shot_logic_cn=shot_logic_cn_text,
            keyframes=keyframes_text,
            prompt=video_content_text,
            image_url=preserved_image_url,
            video_url=preserved_video_url,
            technical_notes=(json.dumps(technical_notes_payload, ensure_ascii=False) if technical_notes_payload else None),
        )
        db.add(shot)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning(
            "[shot_import.apply] unique constraint conflict scene_id=%s episode_id=%s err=%s",
            scene_id,
            getattr(episode, "id", None),
            exc,
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "Shot ID already exists for this project/episode (unique index); import abandoned."
            ),
        ) from exc
    _soft_delete_duplicate_active_shots_in_db(
        db,
        episode_id=int(episode.id),
        project_id=int(project.id),
        scope="episode",
    )
    db.commit()

    applied_shots = db.query(Shot).filter(Shot.scene_id == scene_id, _active_shot_clause()).all()
    applied_shots = _dedupe_active_shot_records_for_display(applied_shots)
    if skipped_row_errors:
        try:
            for shot in applied_shots:
                notes_obj = {}
                if getattr(shot, "technical_notes", None):
                    try:
                        notes_obj = json.loads(shot.technical_notes) if isinstance(shot.technical_notes, str) else {}
                    except Exception:
                        notes_obj = {}
                notes_obj["import_warnings"] = list(
                    dict.fromkeys([str(x or "").strip() for x in skipped_row_errors if str(x or "").strip()])
                )
                shot.technical_notes = json.dumps(notes_obj, ensure_ascii=False)
            db.commit()
            applied_shots = db.query(Shot).filter(Shot.scene_id == scene_id, _active_shot_clause()).all()
        except Exception:
            db.rollback()
            applied_shots = db.query(Shot).filter(Shot.scene_id == scene_id, _active_shot_clause()).all()

    logger.info(
        "[shot_import.apply] applied scene_id=%s episode_id=%s project_id=%s rows=%s skipped=%s",
        scene_id,
        getattr(episode, "id", None),
        getattr(project, "id", None),
        len(applied_shots),
        len(skipped_row_errors),
    )
    return applied_shots

@router.post("/scenes/{scene_id}/apply_ai_result")
def apply_scene_ai_result(
    scene_id: int,
    data: Optional[AnalysisContent] = None, # Optional: apply provided content instead of stored
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Apply the stored (or provided) shot list to the actual Shots table.

    Default: abandon import when the scene already has active shots.
    Pass replace_existing=true only for intentional overwrite (UI confirm).
    Duplicate Shot IDs within the payload are deduped (last row wins).
    """
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    project = _require_project_access(db, episode.project_id, current_user)
         
    shots_data = []
    skipped_row_errors: List[str] = []
    replace_existing = bool(getattr(data, "replace_existing", False)) if data is not None else False
    
    # 1. Determine Source
    provided_content = None
    if data and data.content is not None:
        provided_content = data.content

    if str(getattr(scene, "ai_shots_result", None) or "").strip():
        shots_data, skipped_row_errors = _resolve_shots_data_for_apply(
            scene,
            provided_content,
            source_label="Scene shot table",
            status_code=400,
        )
    elif provided_content is not None:
        shots_data, skipped_row_errors = _validate_shot_rows_for_apply_with_tolerance(
            provided_content,
            source_label="Provided scene shot table",
            status_code=400,
        )
    else:
        shots_data, skipped_row_errors = _resolve_shots_data_for_apply(
            scene,
            None,
            source_label="Stored scene shot table",
            status_code=409,
        )

    if not shots_data:
        logger.warning(
            "[apply_scene_ai_result] empty_shots_data scene_id=%s has_stored=%s provided=%s skipped=%s",
            scene_id,
            bool(str(getattr(scene, "ai_shots_result", None) or "").strip()),
            provided_content is not None,
            skipped_row_errors[:5] if skipped_row_errors else [],
        )
        raise HTTPException(status_code=400, detail="No shot rows provided or available to apply")

    if skipped_row_errors:
        logger.warning(
            "[apply_scene_ai_result] skipped_invalid_rows scene_id=%s skipped=%s details=%s",
            scene_id,
            len(skipped_row_errors),
            skipped_row_errors[:5],
        )
                 
    return _import_scene_shot_rows_to_db(
        scene_id=scene_id,
        db=db,
        scene=scene,
        episode=episode,
        project=project,
        shots_data=shots_data,
        skipped_row_errors=skipped_row_errors,
        replace_existing=replace_existing,
    )

@router.get("/scenes/{scene_id}/shots", response_model=List[ShotOut])
def read_shots(
    scene_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    scene = db.query(Scene).filter(Scene.id == scene_id, _active_scene_clause()).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    # Check Project ownership via Episode
    episode = db.query(Episode).filter(Episode.id == scene.episode_id, _active_episode_clause()).first()
    project = _require_project_access(db, episode.project_id, current_user)
        
    # Optimized: Return shots strictly by Scene ID (Physical Association)
    # Removing logical 'scene_code' sync as requested.
    shots = db.query(Shot).filter(
        Shot.project_id == project.id,
        Shot.episode_id == episode.id,
        Shot.scene_id == scene_id,
        _active_shot_clause(),
    ).all()
    shots = _dedupe_active_shot_records_for_display(shots)
    repaired = _repair_shots_media_urls_from_assets(db, current_user, project, shots)
    return [_refresh_shot_media_urls(shot, db) for shot in repaired]

@router.post("/scenes/{scene_id}/shots", response_model=ShotOut)
def create_shot(
    scene_id: int,
    shot: ShotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    import os
    logger.info(f"[create_shot] START. scene_id={scene_id}")
    logger.info(f"[create_shot] DB URL: {settings.DATABASE_URL}")
    logger.info(f"[create_shot] Payload: shot_id={shot.shot_id}, logic_cn={'YES' if shot.shot_logic_cn else 'NO'}")

    scene = db.query(Scene).filter(Scene.id == scene_id, _active_scene_clause()).first()
    if not scene:
        logger.error(f"[create_shot] Scene {scene_id} not found")
        raise HTTPException(status_code=404, detail="Scene not found")
    
    # Ownership
    episode = db.query(Episode).filter(Episode.id == scene.episode_id, _active_episode_clause()).first()
    if not episode:
        logger.error(f"[create_shot] Scene {scene_id} refers to non-existent episode {scene.episode_id}")
        raise HTTPException(status_code=404, detail="Parent Episode not found")

    try:
        project = _require_project_access(db, episode.project_id, current_user)
    except HTTPException:
         logger.error(f"[create_shot] User {current_user.id} not authorized for Project {episode.project_id}")
         raise
         
    try:
        _assert_allowed_shot_media_payload(shot.dict(exclude_unset=True), db=db)

        business_id = _normalize_shot_business_id(getattr(shot, "shot_id", ""))
        if business_id:
            existing = _find_active_shot_by_business_id(
                db,
                project_id=int(project.id),
                episode_id=int(episode.id),
                shot_id=business_id,
            )
            if existing is not None:
                logger.warning(
                    "[create_shot] abandon duplicate Shot ID | scene_id=%s episode_id=%s shot_id=%s existing_db_id=%s existing_scene_id=%s",
                    scene_id,
                    episode.id,
                    business_id,
                    existing.id,
                    getattr(existing, "scene_id", None),
                )
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Shot ID '{shot.shot_id}' already exists in this project/episode; import abandoned."
                    ),
                )

        db_shot = Shot(
            scene_id=scene_id,
            project_id=project.id,
            episode_id=episode.id,
            shot_id=business_id or shot.shot_id,
            shot_name=shot.shot_name,
            start_frame=shot.start_frame,
            end_frame=shot.end_frame,
            video_content=shot.video_content,
            duration=shot.duration,
            associated_entities=shot.associated_entities,
            shot_logic_cn=shot.shot_logic_cn,
            keyframes=shot.keyframes,
            scene_code=shot.scene_code,
            image_url=shot.image_url,
            video_url=shot.video_url,
            prompt=shot.prompt,
            technical_notes=shot.technical_notes
        )
        db.add(db_shot)
        try:
            _recompute_and_persist_project_cost_estimation(db, int(project.id))
        except Exception as cost_exc:
            logger.warning("create_shot cost recompute skipped | project_id=%s err=%s", project.id, cost_exc)
        db.commit()
        db.refresh(db_shot)
        
        # Verify Write
        logger.info(f"[create_shot] Committed Shot ID: {db_shot.id}. Verifying...")
        verify = db.query(Shot).filter(Shot.id == db_shot.id).first()
        if verify:
             logger.info(f"[create_shot] SUCCESS. Shot {db_shot.id} (Display ID: {db_shot.shot_id}) exists in DB.")
        else:
             logger.error(f"[create_shot] CRITICAL FAILURE. Shot {db_shot.id} not found immediately after commit!")

        return _refresh_shot_media_urls(db_shot, db)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"[create_shot] EXCEPTION: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create shot: {str(e)}")

@router.post("/episodes/{episode_id}/shots/batch_create", response_model=Dict[str, Any])
def batch_create_shots(
    episode_id: int,
    request: ShotBatchCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    started_perf = time.perf_counter()
    episode = db.query(Episode).filter(Episode.id == int(episode_id), _active_episode_clause()).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    project = _require_project_access(db, episode.project_id, current_user)

    items = list(request.items or [])
    if not items:
        return {
            "status": "ok",
            "episode_id": int(episode_id),
            "project_id": int(project.id),
            "processed": 0,
            "created": 0,
            "skipped": 0,
            "elapsed_ms": int((time.perf_counter() - started_perf) * 1000),
        }

    scene_ids = sorted({int(item.scene_id) for item in items if int(getattr(item, "scene_id", 0) or 0) > 0})
    scenes = (
        db.query(Scene)
        .filter(
            Scene.id.in_(scene_ids),
            Scene.episode_id == int(episode_id),
            _active_scene_clause(),
        )
        .all()
    ) if scene_ids else []
    scene_by_id = {int(scene.id): scene for scene in scenes}

    skip_existing_scene_shots = bool(getattr(request, "skip_existing_scene_shots", True))
    scenes_with_existing_shots: set = set()
    if skip_existing_scene_shots and scene_ids:
        existing_rows = (
            db.query(Shot.scene_id)
            .filter(
                Shot.scene_id.in_(scene_ids),
                _active_shot_clause(),
            )
            .distinct()
            .all()
        )
        scenes_with_existing_shots = {
            int(row[0]) for row in existing_rows if row and int(row[0] or 0) > 0
        }
        if scenes_with_existing_shots:
            logger.info(
                "[ShotImportAPI] batch_create abandon scenes with existing shots | episode_id=%s scene_ids=%s",
                episode_id,
                sorted(scenes_with_existing_shots),
            )

    # Only clear scenes that are empty (or when skip_existing_scene_shots is off).
    clearable_scene_ids = [
        sid for sid in scene_ids
        if sid in scene_by_id and sid not in scenes_with_existing_shots
    ]
    for scene_id in clearable_scene_ids:
        _soft_delete_shots(db, scene_id=scene_id)

    created = 0
    skipped = 0
    seen_shot_keys: set = set()
    for item in items:
        scene_id = int(getattr(item, "scene_id", 0) or 0)
        shot = item.shot
        if scene_id <= 0 or scene_id not in scene_by_id:
            skipped += 1
            continue
        if scene_id in scenes_with_existing_shots:
            skipped += 1
            continue
        business_id = _normalize_shot_business_id(getattr(shot, "shot_id", ""))
        if business_id:
            # Episode-scoped unique key: project + episode + Shot ID
            dedup_key = f"{int(project.id)}::{int(episode.id)}::{business_id}"
            if dedup_key in seen_shot_keys:
                skipped += 1
                logger.warning(
                    "[ShotImportAPI] batch_create skip duplicate Shot ID | scene_id=%s episode_id=%s shot_id=%s",
                    scene_id,
                    episode.id,
                    business_id,
                )
                continue
            existing = _find_active_shot_by_business_id(
                db,
                project_id=int(project.id),
                episode_id=int(episode.id),
                shot_id=business_id,
                exclude_scene_id=scene_id if scene_id in clearable_scene_ids else None,
            )
            if existing is not None:
                skipped += 1
                logger.warning(
                    "[ShotImportAPI] batch_create skip Shot ID already in episode | scene_id=%s shot_id=%s existing_scene_id=%s",
                    scene_id,
                    business_id,
                    getattr(existing, "scene_id", None),
                )
                continue
            seen_shot_keys.add(dedup_key)
        payload = shot.dict(exclude_unset=True)
        _assert_allowed_shot_media_payload(payload, db=db)

        db_shot = Shot(
            scene_id=scene_id,
            project_id=project.id,
            episode_id=episode.id,
            shot_id=business_id or shot.shot_id,
            shot_name=shot.shot_name,
            start_frame=shot.start_frame,
            end_frame=shot.end_frame,
            video_content=shot.video_content,
            duration=shot.duration,
            associated_entities=shot.associated_entities,
            shot_logic_cn=shot.shot_logic_cn,
            keyframes=shot.keyframes,
            scene_code=shot.scene_code,
            image_url=shot.image_url,
            video_url=shot.video_url,
            prompt=shot.prompt,
            technical_notes=shot.technical_notes,
        )
        db.add(db_shot)
        created += 1

    if bool(request.recompute_cost):
        try:
            _recompute_and_persist_project_cost_estimation(db, int(project.id))
        except Exception as cost_exc:
            logger.warning("batch_create_shots cost recompute skipped | project_id=%s err=%s", project.id, cost_exc)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning(
            "[ShotImportAPI] batch_create unique conflict | episode_id=%s err=%s",
            episode_id,
            exc,
        )
        raise HTTPException(
            status_code=409,
            detail="Shot ID already exists for this project/episode; batch import abandoned.",
        ) from exc
    _soft_delete_duplicate_active_shots_in_db(
        db,
        episode_id=int(episode.id),
        project_id=int(project.id),
        scope="episode",
    )
    db.commit()
    elapsed_ms = int((time.perf_counter() - started_perf) * 1000)
    logger.info(
        "[ShotImportAPI] batch_create done | episode_id=%s | project_id=%s | processed=%s | created=%s | skipped=%s | abandoned_scenes=%s | elapsed_ms=%s",
        episode_id,
        project.id,
        len(items),
        created,
        skipped,
        len(scenes_with_existing_shots),
        elapsed_ms,
    )
    return {
        "status": "ok",
        "episode_id": int(episode_id),
        "project_id": int(project.id),
        "processed": int(len(items)),
        "created": int(created),
        "skipped": int(skipped),
        "abandoned_scenes": sorted(scenes_with_existing_shots),
        "elapsed_ms": elapsed_ms,
    }

@router.put("/shots/{shot_id}", response_model=ShotOut)
def update_shot(
    shot_id: int,
    shot_in: ShotUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_shot = db.query(Shot).filter(Shot.id == shot_id).first()
    if not db_shot:
        raise HTTPException(status_code=404, detail="Shot not found")
        
    scene = db.query(Scene).filter(Scene.id == db_shot.scene_id).first()
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    project = _require_project_access(db, episode.project_id, current_user)

    update_data = shot_in.dict(exclude_unset=True)
    update_data = _replace_legacy_temp_urls_in_shot_payload(db, current_user, project, db_shot, update_data)
    update_data = _normalize_ephemeral_shot_media_update(update_data, existing_shot=db_shot)
    _assert_allowed_shot_media_payload(update_data, db=db, existing_shot=db_shot)

    for key, value in update_data.items():
        setattr(db_shot, key, value)
    try:
        _recompute_and_persist_project_cost_estimation(db, int(project.id))
    except Exception as cost_exc:
        logger.warning("update_shot cost recompute skipped | project_id=%s err=%s", project.id, cost_exc)
        
    db.commit()
    db.refresh(db_shot)
    return _refresh_shot_media_urls(db_shot, db)


@router.post("/shots/{shot_id}/persist-media", response_model=Dict[str, Any])
def persist_shot_media(
    shot_id: int,
    payload: ShotPersistMediaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_shot = db.query(Shot).filter(Shot.id == shot_id, _active_shot_clause()).first()
    if not db_shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    scene = db.query(Scene).filter(Scene.id == db_shot.scene_id, _active_scene_clause()).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    episode = db.query(Episode).filter(Episode.id == scene.episode_id, _active_episode_clause()).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    project = _require_project_access(db, episode.project_id, current_user)

    _repair_shot_media_urls_from_assets(db, current_user, project, db_shot)

    result = _persist_shot_media_slot(
        db,
        current_user,
        project,
        db_shot,
        slot=str(payload.slot or "video"),
        source_url_override=payload.source_url,
    )
    refreshed = _refresh_shot_media_urls(db_shot, db)
    result["shot"] = {
        "id": refreshed.id,
        "video_url": refreshed.video_url,
        "image_url": refreshed.image_url,
        "technical_notes": refreshed.technical_notes,
    }
    return result


@router.post("/shots/{shot_id}/video-cleanup", response_model=Dict[str, Any])
def cleanup_shot_video_local(
    shot_id: int,
    payload: ShotVideoCleanupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Local ffmpeg cleanup: remove burned-in/soft subtitles and/or BGM (audio track)."""
    db_shot = db.query(Shot).filter(Shot.id == shot_id, _active_shot_clause()).first()
    if not db_shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    scene = db.query(Scene).filter(Scene.id == db_shot.scene_id, _active_scene_clause()).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    episode = db.query(Episode).filter(Episode.id == scene.episode_id, _active_episode_clause()).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    action = str(payload.action or "").strip().lower()
    remove_subtitle = action in {"remove_subtitle", "subtitle", "remove_subtitle_and_bgm", "both"}
    remove_bgm = action in {"remove_bgm", "bgm", "remove_audio", "mute", "remove_subtitle_and_bgm", "both"}
    if not remove_subtitle and not remove_bgm:
        raise HTTPException(
            status_code=400,
            detail="action must be one of: remove_subtitle, remove_bgm, remove_subtitle_and_bgm",
        )

    source_url = str(payload.source_url or getattr(db_shot, "video_url", None) or "").strip()
    if not source_url:
        raise HTTPException(status_code=400, detail="Shot has no video to clean up")

    try:
        result = process_video_cleanup_local(
            source_url,
            remove_subtitle=remove_subtitle,
            remove_bgm=remove_bgm,
            user_id=int(current_user.id or 0),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        detail = str(exc)
        if "busy" in detail.lower():
            raise HTTPException(status_code=429, detail=detail)
        raise HTTPException(status_code=500, detail=detail)
    except Exception as exc:
        logger.error("Shot video cleanup failed shot_id=%s action=%s err=%s", shot_id, action, exc)
        raise HTTPException(status_code=500, detail=f"Video cleanup failed: {exc}")

    new_url = str((result or {}).get("url") or "").strip()
    if not new_url:
        raise HTTPException(status_code=500, detail="Video cleanup returned empty url")

    db_shot.video_url = new_url
    try:
        db.add(db_shot)
        db.commit()
        db.refresh(db_shot)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to persist cleaned video_url shot_id=%s err=%s", shot_id, exc)
        raise HTTPException(status_code=500, detail="Cleanup succeeded but failed to save shot video_url")

    return {
        "url": new_url,
        "action": action,
        "remove_subtitle": bool(remove_subtitle),
        "remove_bgm": bool(remove_bgm),
        "shot": {
            "id": db_shot.id,
            "video_url": db_shot.video_url,
        },
    }


@router.post("/entities/{entity_id}/persist-media", response_model=Dict[str, Any])
def persist_entity_media(
    entity_id: int,
    payload: EntityPersistMediaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entity = db.query(Entity).filter(Entity.id == entity_id, _active_entity_clause()).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    project = _require_project_access(db, entity.project_id, current_user)
    _repair_entity_image_url_from_assets(db, current_user, project, entity)

    result = _persist_entity_image(
        db,
        current_user,
        project,
        entity,
        source_url_override=payload.source_url,
    )
    result["entity"] = {
        "id": entity.id,
        "image_url": entity.image_url,
        "custom_attributes": entity.custom_attributes,
    }
    return result


@router.get("/storage/oss-active-url-signatures", response_model=Dict[str, Any])
def get_oss_active_url_signatures(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    return oss_storage_service.get_active_url_signatures(db)


@router.get("/storage/media-url-inspect", response_model=Dict[str, Any])
def inspect_storage_media_url(
    url: str = Query("", description="Media URL to inspect against active OSS pool configuration"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    raw = str(url or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="url query parameter is required")
    inspection = oss_storage_service.inspect_media_url(raw, db)
    inspection["durable_persisted"] = _is_durable_persisted_media_url(raw, None, db)
    inspection["oss_upload_succeeded"] = _oss_upload_succeeded_for_url(raw, None, db)
    return inspection


@router.delete("/shots/{shot_id}")
def delete_shot(
    shot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_shot = db.query(Shot).filter(Shot.id == shot_id, _active_shot_clause()).first()
    if not db_shot:
         raise HTTPException(status_code=404, detail="Shot not found")
         
    scene = db.query(Scene).filter(Scene.id == db_shot.scene_id, _active_scene_clause()).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    episode = db.query(Episode).filter(Episode.id == scene.episode_id, _active_episode_clause()).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    project = _require_project_access(db, episode.project_id, current_user, owner_only=True)

    if _is_soft_deleted(db_shot):
        return {"ok": True, "batch_id": None}

    shot_label = str(db_shot.shot_name or db_shot.shot_id or f"Shot {shot_id}")
    batch_id = _start_deletion_batch(
        db,
        user_id=current_user.id,
        project_id=int(project.id),
        episode_id=int(episode.id),
        action_type="shot",
        label=shot_label,
    )
    _soft_delete_shots(db, shot_id=shot_id, batch_id=batch_id)
    _finalize_deletion_batch(db, batch_id)
    try:
        _recompute_and_persist_project_cost_estimation(db, int(project.id))
    except Exception as cost_exc:
        logger.warning("delete_shot cost recompute skipped | project_id=%s err=%s", project.id, cost_exc)
    db.commit()
    return {"ok": True, "batch_id": batch_id}

# --- Entities ---

class EntityCreate(BaseModel):
    name: str
    type: str # character, environment, prop
    description: str
    episode_id: Optional[int] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    generation_prompt_en: Optional[str] = None
    generation_prompt_cn: Optional[str] = None
    anchor_description: Optional[str] = None
    
    # New Fields
    name_en: Optional[str] = None
    base_name_en: Optional[str] = None
    gender: Optional[str] = None
    role: Optional[str] = None
    archetype: Optional[str] = None
    appearance_cn: Optional[str] = None
    clothing: Optional[str] = None
    action_characteristics: Optional[str] = None
    
    atmosphere: Optional[str] = None
    visual_params: Optional[str] = None
    narrative_description: Optional[str] = None

    visual_dependencies: Optional[List[str]] = []
    dependency_strategy: Optional[Dict[str, Any]] = {}
    custom_attributes: Optional[Dict[str, Any]] = {}

import pydantic
class EntityOut(BaseModel):
    id: int
    episode_id: Optional[int] = None
    name: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str]
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    generation_prompt_en: Optional[str]
    generation_prompt_cn: Optional[str]
    anchor_description: Optional[str]
    
    # New Fields
    name_en: Optional[str] = None
    base_name_en: Optional[str] = None
    gender: Optional[str] = None
    role: Optional[str] = None
    archetype: Optional[str] = None
    appearance_cn: Optional[str] = None
    clothing: Optional[str] = None
    action_characteristics: Optional[str] = None
    
    atmosphere: Optional[str] = None
    visual_params: Optional[str] = None
    narrative_description: Optional[str] = None

    visual_dependencies: Optional[List[str]] = []
    dependency_strategy: Optional[Dict[str, Any]] = {}
    custom_attributes: Optional[Dict[str, Any]] = {}

    @pydantic.field_validator("visual_dependencies", mode="before")
    @classmethod
    def validate_visual_dependencies(cls, v: Any) -> List[str]:
        return _coerce_visual_dependencies(v)

    @pydantic.field_validator("dependency_strategy", "custom_attributes", mode="before")
    @classmethod
    def validate_dict_fields(cls, v: Any) -> Dict[str, Any]:
        if isinstance(v, dict):
            return v
        if isinstance(v, str) and v.strip():
            import json
            try:
                parsed = json.loads(v.strip())
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                pass
        return {}

    class Config:
        from_attributes = True


def _coerce_visual_dependencies(value: Any) -> List[str]:
    candidates: List[Any] = []
    if isinstance(value, list):
        candidates = value
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        if (raw.startswith("[") and raw.endswith("]")) or (raw.startswith("{") and raw.endswith("}")):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    candidates = parsed
                elif isinstance(parsed, str):
                    candidates = [parsed]
            except Exception:
                candidates = []
        if not candidates:
            candidates = re.split(r"[\n,，;；|]", raw)
    elif value is not None:
        candidates = [value]

    out: List[str] = []
    seen = set()
    for item in candidates:
        stable = str(item or "").strip()
        if not stable:
            continue
        key = normalize_entity_token(stable)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(stable)
    return out


# entities CRUD moved to app.api.routers.entities


# assets routes moved to app.api.routers.assets

@router.get("/admin/runtime-stats")
def get_runtime_stats(current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    image_job_stats = _snapshot_image_job_stats()
    with IMAGE_JOB_LOCK:
        image_task_count = len(IMAGE_JOB_TASKS)
    with VIDEO_JOB_LOCK:
        video_store_items = len(VIDEO_JOB_STORE)
        video_task_count = len(VIDEO_JOB_TASKS)

    gunicorn_max_requests_raw = os.getenv("GUNICORN_MAX_REQUESTS", "")
    gunicorn_max_requests_jitter_raw = os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "")

    def _safe_int_env(raw: Any, default: Optional[int] = None) -> Optional[int]:
        try:
            txt = str(raw or "").strip()
            if txt == "":
                return default
            return int(txt)
        except Exception:
            return default

    gunicorn_max_requests = _safe_int_env(gunicorn_max_requests_raw)
    gunicorn_max_requests_jitter = _safe_int_env(gunicorn_max_requests_jitter_raw)

    return {
        "service": "aistory-backend",
        "pid": os.getpid(),
        "timestamp": now_bj_iso(),
        "render": {
            "service_id": os.getenv("RENDER_SERVICE_ID", ""),
            "instance_id": os.getenv("RENDER_INSTANCE_ID", ""),
            "git_commit": os.getenv("RENDER_GIT_COMMIT", ""),
        },
        "runtime": {
            "python": {
                "version": sys.version,
                "active_threads": threading.active_count(),
            },
            "gunicorn": {
                "workers": os.getenv("WEB_CONCURRENCY", ""),
                "timeout": os.getenv("GUNICORN_TIMEOUT", ""),
                "graceful_timeout": os.getenv("GUNICORN_GRACEFUL_TIMEOUT", ""),
                "keepalive": os.getenv("GUNICORN_KEEPALIVE", ""),
                "max_requests": gunicorn_max_requests_raw,
                "max_requests_jitter": gunicorn_max_requests_jitter_raw,
                "request_limit_disabled": (gunicorn_max_requests == 0 and (gunicorn_max_requests_jitter or 0) == 0),
            },
            "async_jobs": {
                "image_store_items": image_job_stats.get("store_items", 0),
                "image_live_tasks": image_task_count,
                "video_store_items": video_store_items,
                "video_live_tasks": video_task_count,
            },
        },
        "image_jobs": image_job_stats,
    }


@router.get("/admin/upstream-diagnostics/grsai")
def admin_diagnose_grsai_connectivity(
    timeout_seconds: int = 5,
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    timeout_seconds = max(2, min(int(timeout_seconds or 5), 20))

    targets = [
        {
            "name": "primary",
            "base_url": "https://grsai.dakka.com.cn",
            "submit_path": "/v1/draw/nano-banana",
            "poll_path": "/v1/draw/result",
        },
        {
            "name": "fallback",
            "base_url": "https://grsaiapi.com",
            "submit_path": "/v1/draw/completions",
            "poll_path": "/v1/draw/result",
        },
    ]

    def _check_one(target: Dict[str, str]) -> Dict[str, Any]:
        base_url = target["base_url"].rstrip("/")
        parsed = urllib.parse.urlparse(base_url)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        result: Dict[str, Any] = {
            "name": target["name"],
            "host": host,
            "port": port,
            "base_url": base_url,
            "submit_url": f"{base_url}{target['submit_path']}",
            "poll_url": f"{base_url}{target['poll_path']}",
            "dns": {"ok": False, "ips": [], "error": None, "ms": None},
            "tcp": {"ok": False, "error": None, "ms": None},
            "http": {
                "ok": False,
                "status": None,
                "error": None,
                "ms": None,
                "note": "HTTP 200/401/403/404/405 are all considered reachable",
            },
        }

        dns_start = time.perf_counter()
        try:
            infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
            ips = sorted({info[4][0] for info in infos if info and len(info) >= 5 and info[4]})
            result["dns"]["ok"] = len(ips) > 0
            result["dns"]["ips"] = ips
        except Exception as exc:
            result["dns"]["error"] = str(exc)
        finally:
            result["dns"]["ms"] = int((time.perf_counter() - dns_start) * 1000)

        tcp_start = time.perf_counter()
        try:
            conn = socket.create_connection((host, port), timeout=timeout_seconds)
            conn.close()
            result["tcp"]["ok"] = True
        except Exception as exc:
            result["tcp"]["error"] = str(exc)
        finally:
            result["tcp"]["ms"] = int((time.perf_counter() - tcp_start) * 1000)

        http_start = time.perf_counter()
        try:
            resp = requests.get(
                result["submit_url"],
                timeout=(timeout_seconds, timeout_seconds),
                verify=False,
            )
            result["http"]["status"] = resp.status_code
            result["http"]["ok"] = resp.status_code in {200, 401, 403, 404, 405}
        except Exception as exc:
            result["http"]["error"] = str(exc)
        finally:
            result["http"]["ms"] = int((time.perf_counter() - http_start) * 1000)

        return result

    checks = [_check_one(target) for target in targets]
    overall_ok = any(item.get("http", {}).get("ok") for item in checks)

    return {
        "ok": overall_ok,
        "timeout_seconds": timeout_seconds,
        "proxy_env": {
            "HTTP_PROXY": os.getenv("HTTP_PROXY") or "",
            "HTTPS_PROXY": os.getenv("HTTPS_PROXY") or "",
            "NO_PROXY": os.getenv("NO_PROXY") or "",
        },
        "checks": checks,
    }



# billing routes moved to app.api.routers.billing


# generate routes moved to app.api.routers.generate



# batch-media routes moved to app.api.routers.generate


# montage routes moved to app.api.routers.generate


# assets/analyze moved to assets router


# entity analyze moved to entities router


# analyze_scene/stream moved to prompts_analyze


# residual routes moved to workspace_residual



# Refresh cross-router helpers after local definitions are complete.
_bind_endpoint_helpers()

