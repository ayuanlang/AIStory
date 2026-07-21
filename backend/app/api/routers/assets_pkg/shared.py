# -*- coding: utf-8 -*-
"""Assets library routes (P8)."""
from __future__ import annotations

import logging
import os
import re
import uuid
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.time_utils import BEIJING_TZ, now_bj_iso
from app.db.session import SessionLocal, get_db
from app.models import all_models as models
from app.models.all_models import *

logger = logging.getLogger("api_logger")
router = APIRouter(tags=["assets"])


def _bind_endpoint_helpers(*, include_routers: bool = True) -> None:
    from app.api.routers.helper_bind import bind_shared_helpers
    bind_shared_helpers(globals(), __name__, include_routers=include_routers)

_bind_endpoint_helpers(include_routers=False)


# --- Assets ---

from app.schemas.asset import (  # noqa: E402,F401
    AssetBackfillEpisodeMediaRequest,
    AssetBackfillMetadataRequest,
    AssetCreate,
    AssetRebindShotMediaRequest,
    AssetUpdate,
)

from app.services.generation_runtime.asset_registration import (  # noqa: E402,F401
    _find_existing_asset_for_registration,
    _serialize_asset_row,
)


from app.services.asset_meta_utils import (  # noqa: E402,F401
    _asset_meta_dict,
    _asset_optional_int,
    _sync_asset_denormalized_fields,
)

def _normalize_current_project_asset_filter(value: Any, *, project_scoped: bool) -> Optional[bool]:
    raw = str(value or "").strip().lower()
    if not raw:
        return True if project_scoped else None
    if raw in {"all", "any", "*"}:
        return None
    if raw in {"0", "false", "no", "off", "history", "historical"}:
        return False
    return True


def _parse_episode_sort_rank(title: Any, episode_id: Any) -> int:
    raw_title = str(title or "").strip()
    for pattern in (
        r"第\s*(\d+)\s*集",
        r"episode\s*0*(\d+)",
        r"ep\s*0*(\d+)",
    ):
        match = re.search(pattern, raw_title, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                break
    return int(_asset_optional_int(episode_id) or 0)


def _build_asset_current_group_key(asset: Asset, meta: Optional[Dict[str, Any]] = None) -> str:
    stable_meta = _asset_meta_dict(meta if meta is not None else getattr(asset, "meta_info", None))
    project_id = _asset_optional_int(getattr(asset, "project_id", None) or stable_meta.get("project_id"))
    if not project_id:
        return ""

    media_type = str(getattr(asset, "type", "") or stable_meta.get("type") or "asset").strip().lower() or "asset"
    frame_type = str(stable_meta.get("frame_type") or stable_meta.get("asset_type") or "").strip().lower()
    entity_id = _asset_optional_int(stable_meta.get("entity_id"))
    shot_id = _asset_optional_int(stable_meta.get("shot_id"))
    scene_id = _asset_optional_int(stable_meta.get("scene_id"))
    shot_number = str(stable_meta.get("shot_number") or "").strip().lower()
    subject_name = str(stable_meta.get("subject_name") or stable_meta.get("entity_name") or "").strip().lower()
    subject_type = str(stable_meta.get("subject_type") or stable_meta.get("entity_type") or "").strip().lower()

    parts = [f"project:{project_id}", f"media:{media_type}"]
    if frame_type:
        parts.append(f"frame:{frame_type}")
    if entity_id:
        parts.append(f"entity:{entity_id}")
    if shot_id:
        parts.append(f"shot:{shot_id}")
    if frame_type == "keyframe" and shot_number:
        parts.append(f"shot_number:{shot_number}")
    if scene_id:
        parts.append(f"scene:{scene_id}")
    if not entity_id and not shot_id and not scene_id and subject_name:
        if subject_type:
            parts.append(f"subject_type:{subject_type}")
        parts.append(f"subject:{subject_name}")
    if len(parts) <= 2:
        parts.append("scope:project")
    return "|".join(parts)



def _resolve_asset_response_type(asset: Optional[Asset], meta: Optional[Dict[str, Any]] = None) -> str:
    if asset is None:
        return "image"

    stable_meta = _asset_meta_dict(meta if meta is not None else getattr(asset, "meta_info", None))
    raw_type = str(getattr(asset, "type", "") or "").strip().lower()

    meta_type = str(stable_meta.get("type") or "").strip().lower()
    frame_type = str(stable_meta.get("frame_type") or stable_meta.get("asset_type") or "").strip().lower()
    mime_type = str(
        stable_meta.get("mime_type")
        or stable_meta.get("content_type")
        or stable_meta.get("stored_from_remote_url_content_type")
        or ""
    ).strip().lower()
    filename = str(getattr(asset, "filename", "") or stable_meta.get("filename") or "").strip().lower()
    url = str(getattr(asset, "url", "") or "").strip().lower()

    def _looks_like_video(value: str) -> bool:
        return bool(re.search(r"\.(mp4|mov|mkv|webm|avi|m4v)(\?.*)?$", str(value or "").strip().lower()))

    if raw_type == "video":
        return "video"
    if meta_type == "video":
        return "video"
    if "video" in frame_type:
        return "video"
    if mime_type.startswith("video/"):
        return "video"
    if _looks_like_video(filename):
        return "video"
    if _looks_like_video(url):
        return "video"

    return raw_type or "image"


def _infer_legacy_shot_asset_meta(
    db: Session,
    asset: Optional[Asset],
    meta: Optional[Dict[str, Any]] = None,
    *,
    shot_cache: Optional[Dict[int, Optional[Shot]]] = None,
    scene_cache: Optional[Dict[int, Optional[Scene]]] = None,
    episode_cache: Optional[Dict[int, Optional[Episode]]] = None,
) -> Dict[str, Any]:
    if asset is None:
        return _asset_meta_dict(meta)

    stable_meta = _asset_meta_dict(meta if meta is not None else getattr(asset, "meta_info", None))
    has_core_scope = bool(
        _asset_optional_int(stable_meta.get("project_id") or getattr(asset, "project_id", None))
        and _asset_optional_int(stable_meta.get("episode_id") or getattr(asset, "episode_id", None))
        and _asset_optional_int(stable_meta.get("shot_id"))
        and str(stable_meta.get("asset_type") or stable_meta.get("frame_type") or "").strip()
    )
    if has_core_scope:
        return stable_meta

    filename = str(getattr(asset, "filename", None) or "").strip()
    if not filename:
        return stable_meta

    inferred_asset_type = ""
    shot_match = re.search(r"^shot_(\d+)_keyframe_", filename, re.IGNORECASE)
    if shot_match:
        inferred_asset_type = "keyframe"
    else:
        shot_match = re.search(r"^shot_(\d+)_video_last_frame_", filename, re.IGNORECASE)
        if shot_match:
            inferred_asset_type = "end_frame"

    if not shot_match:
        return stable_meta

    shot_id_int = _asset_optional_int(shot_match.group(1))
    if not shot_id_int:
        return stable_meta

    local_shot_cache = shot_cache if shot_cache is not None else {}
    local_scene_cache = scene_cache if scene_cache is not None else {}
    local_episode_cache = episode_cache if episode_cache is not None else {}

    shot = local_shot_cache.get(shot_id_int)
    if shot_id_int not in local_shot_cache:
        shot = db.query(Shot).filter(Shot.id == shot_id_int).first()
        local_shot_cache[shot_id_int] = shot
    if not shot:
        return stable_meta

    scene_id_int = _asset_optional_int(getattr(shot, "scene_id", None))
    scene = local_scene_cache.get(scene_id_int or 0)
    if scene_id_int and scene_id_int not in local_scene_cache:
        scene = db.query(Scene).filter(Scene.id == scene_id_int).first()
        local_scene_cache[scene_id_int] = scene

    episode_id_int = _asset_optional_int(getattr(scene, "episode_id", None) if scene else None)
    episode = local_episode_cache.get(episode_id_int or 0)
    if episode_id_int and episode_id_int not in local_episode_cache:
        episode = db.query(Episode).filter(Episode.id == episode_id_int).first()
        local_episode_cache[episode_id_int] = episode

    next_meta = dict(stable_meta)
    next_meta.setdefault("shot_id", shot_id_int)
    if getattr(shot, "shot_id", None):
        next_meta.setdefault("shot_number", getattr(shot, "shot_id", None))
    if getattr(shot, "shot_name", None):
        next_meta.setdefault("shot_name", getattr(shot, "shot_name", None))
    if inferred_asset_type:
        next_meta.setdefault("asset_type", inferred_asset_type)
        next_meta.setdefault("frame_type", inferred_asset_type)
    if episode_id_int:
        next_meta.setdefault("episode_id", episode_id_int)
    project_id_int = _asset_optional_int(getattr(episode, "project_id", None) if episode else None)
    if project_id_int:
        next_meta.setdefault("project_id", project_id_int)

    if next_meta != stable_meta:
        asset.meta_info = next_meta
        if project_id_int:
            asset.project_id = project_id_int
        if episode_id_int:
            asset.episode_id = episode_id_int

    return next_meta


def _resolve_effective_current_project_asset_ids(db: Session, assets: List[Asset]) -> Set[int]:
    if not assets:
        return set()

    episode_ids: Set[int] = set()
    groups: Dict[str, List[Tuple[Asset, Dict[str, Any]]]] = {}
    for asset in assets:
        stable_meta = _asset_meta_dict(getattr(asset, "meta_info", None))
        _sync_asset_denormalized_fields(asset)
        group_key = _build_asset_current_group_key(asset, stable_meta)
        if not group_key:
            continue
        groups.setdefault(group_key, []).append((asset, stable_meta))
        if asset.episode_id:
            episode_ids.add(int(asset.episode_id))

    episode_title_map: Dict[int, str] = {}
    if episode_ids:
        episode_title_map = {
            int(row_id): str(row_title or "")
            for row_id, row_title in db.query(Episode.id, Episode.title).filter(Episode.id.in_(episode_ids)).all()
        }

    selected_ids: Set[int] = set()
    for entries in groups.values():
        explicit = [entry for entry in entries if bool(getattr(entry[0], "is_current_project_asset", False))]
        pool = explicit or entries

        def _sort_key(item: Tuple[Asset, Dict[str, Any]]) -> Tuple[int, str, int]:
            asset_row, _meta = item
            episode_rank = _parse_episode_sort_rank(episode_title_map.get(int(asset_row.episode_id or 0)), asset_row.episode_id)
            created_at = str(getattr(asset_row, "created_at", "") or "")
            return (episode_rank, created_at, int(getattr(asset_row, "id", 0) or 0))

        chosen_asset, _ = max(pool, key=_sort_key)
        selected_ids.add(int(chosen_asset.id))

    return selected_ids


def _mark_asset_as_current_project_asset(db: Session, asset: Optional[Asset]) -> Optional[Asset]:
    if asset is None:
        return None

    _sync_asset_denormalized_fields(asset)
    group_key = _build_asset_current_group_key(asset)
    if not group_key:
        asset.is_current_project_asset = False
        db.add(asset)
        return asset

    candidates = (
        db.query(Asset)
        .filter(Asset.user_id == asset.user_id, Asset.type == asset.type)
        .order_by(Asset.id.desc())
        .limit(5000)
        .all()
    )
    for candidate in candidates:
        _sync_asset_denormalized_fields(candidate)
        next_value = _build_asset_current_group_key(candidate) == group_key and int(candidate.id) == int(asset.id)
        if bool(getattr(candidate, "is_current_project_asset", False)) != bool(next_value):
            candidate.is_current_project_asset = bool(next_value)
            db.add(candidate)

    asset.is_current_project_asset = True
    db.add(asset)
    return asset


def _url_reference_tokens(raw_url: Any) -> set[str]:
    tokens: set[str] = set()
    raw = str(raw_url or "").strip()
    if not raw:
        return tokens

    tokens.add(raw)
    try:
        parsed = urllib.parse.urlparse(raw)
        path = urllib.parse.unquote(parsed.path or "").strip()
    except Exception:
        path = raw

    if path:
        tokens.add(path)
        stripped = path.lstrip("/")
        if stripped:
            tokens.add(stripped)

        if "/uploads/" in path:
            suffix = path.split("/uploads/", 1)[1].lstrip("/")
            if suffix:
                tokens.add(suffix)
                tokens.add(f"uploads/{suffix}")
                tokens.add(f"/uploads/{suffix}")

        if stripped.startswith("uploads/"):
            suffix = stripped.split("uploads/", 1)[1].lstrip("/")
            if suffix:
                tokens.add(suffix)
                tokens.add(f"uploads/{suffix}")
                tokens.add(f"/uploads/{suffix}")

        base_name = os.path.basename(path)
        if base_name:
            tokens.add(base_name)

    return {str(item).strip() for item in tokens if str(item or "").strip()}


def _resolve_upload_relative_path_from_media_url(url: Any) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""

    upload_suffix = ""
    if raw.startswith("/uploads/"):
        upload_suffix = raw[len("/uploads/"):].lstrip("/")
    else:
        try:
            parsed = urllib.parse.urlparse(raw)
            path = urllib.parse.unquote(parsed.path or "").strip()
            if path.startswith("/uploads/"):
                upload_suffix = path[len("/uploads/"):].lstrip("/")
        except Exception:
            upload_suffix = ""

    if not upload_suffix:
        return ""
    return upload_suffix.replace("\\", "/")


def _collect_shot_media_urls(
    img_url: Any,
    vid_url: Any,
    technical_notes: Any,
    start_frame: Any,
    keyframes_raw: Any,
) -> List[str]:
    urls: List[str] = []
    for candidate in (img_url, vid_url, start_frame, keyframes_raw):
        raw = str(candidate or "").strip()
        if raw:
            urls.append(raw)

    if technical_notes:
        try:
            notes = technical_notes
            if isinstance(notes, str):
                notes = json.loads(notes)
            if isinstance(notes, dict):
                for key in (
                    "end_frame_url",
                    "endFrameUrl",
                    "last_frame_url",
                    "start_frame_url",
                    "startFrameUrl",
                ):
                    val = notes.get(key)
                    if val:
                        urls.append(str(val))

                keyframes = notes.get("keyframes")
                if isinstance(keyframes, list):
                    urls.extend(str(item) for item in keyframes if item)
                elif isinstance(keyframes, str) and keyframes.strip():
                    urls.append(keyframes)

                for list_key in ("video_ref_image_urls", "ref_image_urls", "end_ref_image_urls"):
                    refs = notes.get(list_key)
                    if isinstance(refs, list):
                        urls.extend(str(item) for item in refs if item)
        except Exception:
            pass

    return urls


_ORPHAN_SCAN_SKIP_DIR_NAMES = {
    "_image_jobs",
    "_video_jobs",
    "_generation_callbacks",
    "_downloads",
    ".thumbs",
}
_ORPHAN_MEDIA_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".avi", ".webm"}


def _collect_admin_referenced_upload_paths(db: Session) -> set[str]:
    referenced: set[str] = set()

    for (url,) in db.query(Asset.url).filter(_active_asset_clause()).all():
        rel = _resolve_upload_relative_path_from_media_url(url)
        if rel:
            referenced.add(rel)

    shot_rows = db.query(
        Shot.image_url,
        Shot.video_url,
        Shot.technical_notes,
        Shot.start_frame,
        Shot.keyframes,
    ).filter(_active_shot_clause()).all()
    for row in shot_rows:
        for url in _collect_shot_media_urls(*row):
            rel = _resolve_upload_relative_path_from_media_url(url)
            if rel:
                referenced.add(rel)

    return referenced


def _scan_admin_orphan_files(
    upload_root: Path,
    referenced: set[str],
    user_map: Dict[int, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int, int]:
    orphan_files: List[Dict[str, Any]] = []
    total_size = 0
    total_count = 0

    for child in upload_root.iterdir():
        if not child.is_dir() or child.name in _ORPHAN_SCAN_SKIP_DIR_NAMES:
            continue
        try:
            user_id = int(child.name)
        except Exception:
            continue

        for root, dirnames, files in os.walk(child):
            dirnames[:] = [name for name in dirnames if name not in _ORPHAN_SCAN_SKIP_DIR_NAMES]
            for filename in files:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in _ORPHAN_MEDIA_EXTENSIONS:
                    continue

                path = Path(root) / filename
                if path.is_symlink():
                    continue
                try:
                    rel_path = str(path.relative_to(upload_root)).replace("\\", "/")
                    stat = path.stat()
                except Exception:
                    continue

                if rel_path in referenced:
                    continue

                info = user_map.get(user_id, {})
                orphan_files.append(
                    {
                        "user_id": user_id,
                        "username": str(info.get("username", f"user_{user_id}")),
                        "email": info.get("email"),
                        "filepath": rel_path,
                        "size": int(stat.st_size),
                        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    }
                )
                total_size += int(stat.st_size)
                total_count += 1

    orphan_files.sort(key=lambda item: item["size"], reverse=True)
    return orphan_files, total_size, total_count


def _resolve_accessible_project_ids_for_user(db: Session, current_user: User) -> List[int]:
    owner_ids = [
        pid for (pid,) in db.query(Project.id).filter(
            Project.owner_id == current_user.id,
            _active_project_clause(),
        ).all()
        if pid is not None
    ]
    shared_ids = [
        pid for (pid,) in db.query(ProjectShare.project_id).join(
            Project, Project.id == ProjectShare.project_id
        ).filter(
            ProjectShare.user_id == current_user.id,
            _active_project_clause(),
        ).all()
        if pid is not None
    ]
    return sorted(set([int(pid) for pid in owner_ids + shared_ids]))


@router.get("/assets/unreferenced-ids", response_model=dict)
def get_unreferenced_asset_ids(
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Base asset query for the user
    query = db.query(Asset).filter(Asset.user_id == current_user.id, _active_asset_clause())
    
    if project_id is not None:
        _require_project_access(db, project_id, current_user)
        accessible_project_ids = [project_id]
        # Just fetch all user assets, the filtering will happen by matching referenced tokens
        # which is fast enough, and avoids missing assets that don't have project_id in meta_info.
    else:
        accessible_project_ids = _resolve_accessible_project_ids_for_user(db, current_user)
        
    assets = query.all()
    if not assets:
        return {"unreferenced_ids": [], "referenced_ids": [], "total_assets": 0}
    referenced_tokens: set[str] = set()

    if accessible_project_ids:
        for (img_url,) in db.query(Entity.image_url).filter(Entity.project_id.in_(accessible_project_ids)).all():
            referenced_tokens.update(_url_reference_tokens(img_url))

        direct_shot_rows = db.query(
            Shot.image_url,
            Shot.video_url,
            Shot.technical_notes,
            Shot.start_frame,
            Shot.keyframes,
        ).filter(
            Shot.project_id.in_(accessible_project_ids)
        ).all()

        joined_shot_rows = (
            db.query(
                Shot.image_url,
                Shot.video_url,
                Shot.technical_notes,
                Shot.start_frame,
                Shot.keyframes,
            )
            .join(Scene, Scene.id == Shot.scene_id)
            .join(Episode, Episode.id == Scene.episode_id)
            .filter(Episode.project_id.in_(accessible_project_ids))
            .all()
        )

        seen_row_keys: set[tuple[str, str, str]] = set()
        for img_url, vid_url, technical_notes, start_frame, keyframes_raw in direct_shot_rows + joined_shot_rows:
            row_key = (str(img_url or ""), str(vid_url or ""), str(technical_notes or ""))
            if row_key in seen_row_keys:
                continue
            seen_row_keys.add(row_key)

            referenced_tokens.update(_url_reference_tokens(img_url))
            referenced_tokens.update(_url_reference_tokens(vid_url))
            referenced_tokens.update(_url_reference_tokens(start_frame))
            referenced_tokens.update(_url_reference_tokens(keyframes_raw))
            if technical_notes:
                try:
                    notes = technical_notes
                    if isinstance(notes, str):
                        notes = json.loads(notes)
                    if isinstance(notes, dict):
                        referenced_tokens.update(_url_reference_tokens(notes.get("end_frame_url")))
                        referenced_tokens.update(_url_reference_tokens(notes.get("endFrameUrl")))
                        referenced_tokens.update(_url_reference_tokens(notes.get("last_frame_url")))
                        referenced_tokens.update(_url_reference_tokens(notes.get("start_frame_url")))
                        referenced_tokens.update(_url_reference_tokens(notes.get("startFrameUrl")))

                        keyframes = notes.get("keyframes")
                        if isinstance(keyframes, list):
                            for item in keyframes:
                                referenced_tokens.update(_url_reference_tokens(item))
                        elif isinstance(keyframes, str):
                            referenced_tokens.update(_url_reference_tokens(keyframes))

                        for list_key in ("video_ref_image_urls", "ref_image_urls", "end_ref_image_urls"):
                            refs = notes.get(list_key)
                            if isinstance(refs, list):
                                for item in refs:
                                    referenced_tokens.update(_url_reference_tokens(item))
                except Exception:
                    pass

    referenced_ids: List[int] = []
    unreferenced_ids: List[int] = []

    def _meta_dict(raw_meta: Any) -> Dict[str, Any]:
        if isinstance(raw_meta, dict):
            meta = dict(raw_meta)
        elif isinstance(raw_meta, str):
            try:
                parsed = json.loads(raw_meta)
                meta = parsed if isinstance(parsed, dict) else {}
            except Exception:
                meta = {}
        else:
            meta = {}

        nested = meta.get("metadata")
        if isinstance(nested, dict):
            merged = dict(meta)
            merged.update(nested)
            return merged
        return meta

    def _has_value(value: Any) -> bool:
        if value is None:
            return False
        raw = str(value).strip().lower()
        return raw not in {"", "null", "none", "undefined"}

    def _is_model_generated_asset(meta: Dict[str, Any]) -> bool:
        if _has_value(meta.get("provider")) or _has_value(meta.get("model")):
            return True

        source = str(meta.get("source") or "").strip().lower()
        if source in {
            "ai_generation",
            "generated",
            "model_generation",
            "image_gen",
            "video_gen",
        }:
            return True

        return False

    generated_assets_count = 0
    is_source_ids: set[int] = set()
    is_dependent_ids: set[int] = set()

    url_to_id = {asset.url: asset.id for asset in assets if asset.url}

    for asset in assets:
        meta = _meta_dict(asset.meta_info)
        src_url = meta.get("source_asset_url") or meta.get("sourceUrl") or meta.get("base_image")
        if _has_value(src_url):
            is_dependent_ids.add(asset.id)
            if src_url in url_to_id:
                is_source_ids.add(url_to_id[src_url])

        if not _is_model_generated_asset(meta):
            continue

        generated_assets_count += 1
        asset_tokens = _url_reference_tokens(asset.url)
        if asset_tokens and asset_tokens.intersection(referenced_tokens):
            referenced_ids.append(asset.id)
        else:
            unreferenced_ids.append(asset.id)

    return {
        "unreferenced_ids": sorted(unreferenced_ids),
        "referenced_ids": sorted(referenced_ids),
        "total_assets": len(assets),
        "generated_assets": generated_assets_count,
        "is_source_ids": sorted(list(is_source_ids)),
        "is_dependent_ids": sorted(list(is_dependent_ids)),
    }

import imageio
from PIL import Image
from fastapi.responses import FileResponse, Response, StreamingResponse
import httpx

@router.get("/assets/proxy")
async def proxy_asset(url: str, request: Request):
    """Proxy external media through backend to avoid client-side network resets/CORS issues."""
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL scheme")

    from urllib.parse import urlparse

    # Private Qiniu / managed OSS URLs often arrive without (or with stale) download tokens.
    # Refresh before fetch so proxy clients (multi-panel split, canvas, assets library) get 200.
    fetch_url = str(url or "").strip()
    try:
        refreshed = str(oss_storage_service.refresh_url(fetch_url) or "").strip()
        if refreshed and refreshed != fetch_url:
            fetch_url = refreshed
    except Exception as refresh_exc:
        logger.warning(
            "[AssetProxy] refresh_url failed | url=%s err=%s",
            url,
            refresh_exc,
        )

    parsed = urlparse(fetch_url)
    host = (parsed.hostname or "").strip().lower()
    bypass_env_proxy = (
        host == "qn.woola.fun"
        or host.endswith(".woola.fun")
        or host.endswith(".clouddn.com")
        or host.endswith(".qiniucs.com")
        or host.endswith(".qiniu.com")
    )

    forward_headers: Dict[str, str] = {}
    for header_name in ("range", "if-none-match", "if-modified-since"):
        header_value = request.headers.get(header_name)
        if header_value:
            forward_headers[header_name] = header_value
    forward_headers.setdefault("User-Agent", "Mozilla/5.0")
    forward_headers.setdefault("Connection", "close")

    timeout = (10, 90)
    last_error: Optional[Exception] = None
    last_upstream_status: Optional[int] = None

    def _fetch_upstream(target_url: str) -> requests.Response:
        if not bypass_env_proxy:
            return requests.get(
                target_url,
                headers=forward_headers,
                timeout=timeout,
                allow_redirects=True,
                stream=False,
            )

        session = requests.Session()
        session.trust_env = False
        try:
            return session.get(
                target_url,
                headers=forward_headers,
                timeout=timeout,
                allow_redirects=True,
                stream=False,
            )
        finally:
            session.close()

    for attempt in range(1, 4):
        try:
            upstream = await asyncio.to_thread(_fetch_upstream, fetch_url)

            status_code = int(upstream.status_code or 502)
            last_upstream_status = status_code
            if status_code >= 400:
                # One retry with a freshly signed URL when private OSS auth fails.
                if status_code in {401, 403} and attempt < 3:
                    try:
                        retried = str(oss_storage_service.refresh_url(url) or "").strip()
                        if retried and retried != fetch_url:
                            fetch_url = retried
                            continue
                    except Exception:
                        pass
                logger.warning(
                    "[AssetProxy] upstream error | attempt=%s status=%s host=%s url=%s",
                    attempt,
                    status_code,
                    host,
                    fetch_url.split("?", 1)[0],
                )
                raise HTTPException(status_code=502, detail=f"Upstream returned status {status_code}")

            passthrough_headers: Dict[str, str] = {}
            for header_name in (
                "content-type",
                "content-length",
                "content-range",
                "accept-ranges",
                "cache-control",
                "etag",
                "last-modified",
            ):
                header_value = upstream.headers.get(header_name)
                if header_value:
                    # Keep canonical header casing for response output.
                    passthrough_headers["-".join(part.capitalize() for part in header_name.split("-"))] = header_value

            if "Cache-Control" not in passthrough_headers:
                passthrough_headers["Cache-Control"] = "private, max-age=120, stale-while-revalidate=60"

            return Response(content=upstream.content, status_code=status_code, headers=passthrough_headers)
        except HTTPException:
            raise
        except Exception as e:
            last_error = e
            if attempt < 3:
                continue

    logger.error(
        "Failed to proxy asset %s after retries: %s (last_upstream_status=%s)",
        url.split("?", 1)[0],
        last_error,
        last_upstream_status,
    )
    raise HTTPException(status_code=502, detail=f"Failed to proxy asset: {last_error}")

@router.get("/assets/thumb/{filename:path}")
def get_asset_thumbnail(filename: str):
    file_path = os.path.join(settings.UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        return Response(status_code=404)
        
    thumb_dir = os.path.join(settings.UPLOAD_DIR, ".thumbs")
    os.makedirs(thumb_dir, exist_ok=True)
    safe_name = filename.replace("/", "_").replace("\\", "_") + ".jpg"
    thumb_path = os.path.join(thumb_dir, safe_name)
    
    if not os.path.exists(thumb_path):
        try:
            if file_path.lower().endswith((".mp4", ".mov", ".avi", ".webm")):
                reader = imageio.get_reader(file_path)
                frame = reader.get_data(0)
                img = Image.fromarray(frame)
                reader.close()
            else:
                img = Image.open(file_path)
                
            img.thumbnail((128, 128), Image.Resampling.LANCZOS)
            img.convert("RGB").save(thumb_path, format="JPEG", optimize=True, quality=40)
        except Exception as e:
            logger.error(f"Failed to generate thumbnail for {filename}: {e}")
            return FileResponse(file_path)
            
    return FileResponse(thumb_path)

@router.get("/assets/", response_model=List[dict])
def get_assets(
    type: Optional[str] = None,
    project_id: Optional[str] = None,
    episode_id: Optional[str] = None,
    include_project_null_episode: Optional[str] = None,
    current_project_asset: Optional[str] = None,
    entity_id: Optional[str] = None,
    shot_id: Optional[str] = None,
    scene_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 120,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    safe_skip = max(int(skip or 0), 0)
    safe_limit = max(1, min(int(limit or 120), 200))
    accessible_project_ids = _resolve_accessible_project_ids_for_user(db, current_user)
    accessible_project_owner_ids = [
        owner_id
        for (owner_id,) in db.query(Project.owner_id).filter(Project.id.in_(accessible_project_ids)).all()
        if owner_id is not None
    ]
    accessible_project_id_set = set(int(pid) for pid in accessible_project_ids)
    visible_owner_ids = sorted(set([int(current_user.id)] + [int(x) for x in accessible_project_owner_ids]))

    query = db.query(Asset).filter(Asset.user_id.in_(visible_owner_ids), _active_asset_clause())
    if type:
        normalized_type = str(type or "").strip().lower()
        if normalized_type == "video":
            meta_text = func.lower(cast(Asset.meta_info, String))
            url_text = func.lower(func.coalesce(Asset.url, ""))
            filename_text = func.lower(func.coalesce(Asset.filename, ""))
            video_ext_like = or_(
                url_text.like("%.mp4%"),
                url_text.like("%.mov%"),
                url_text.like("%.mkv%"),
                url_text.like("%.webm%"),
                url_text.like("%.avi%"),
                url_text.like("%.m4v%"),
                filename_text.like("%.mp4%"),
                filename_text.like("%.mov%"),
                filename_text.like("%.mkv%"),
                filename_text.like("%.webm%"),
                filename_text.like("%.avi%"),
                filename_text.like("%.m4v%"),
            )
            query = query.filter(
                or_(
                    func.lower(func.coalesce(Asset.type, "")) == "video",
                    meta_text.like('%"type": "video"%'),
                    meta_text.like('%"asset_type": "video"%'),
                    meta_text.like('%"frame_type": "video"%'),
                    meta_text.like("%video/%"),
                    video_ext_like,
                )
            )
        else:
            query = query.filter(func.lower(func.coalesce(Asset.type, "")) == normalized_type)
    
    # Ideally use database-side JSON filtering if supported (e.g., Postgres)
    # Since we are likely using SQLite or generic, we might need to filter manually or use cast
    # SQLite supports json_extract but SQLAlchemy syntax depends on dialect.
    # For fail-safe prototype, we'll fetch then filter in Python if specific meta filters are requested.
    
    strict_meta_filter = str(os.getenv("ASSETS_META_FILTER_STRICT", "1")).strip().lower() not in {"0", "false", "no", "off"}
    current_only_mode = _normalize_current_project_asset_filter(current_project_asset, project_scoped=bool(project_id))
    include_null_episode_for_project_scope = bool(_to_bool(include_project_null_episode))
    assets_filter_debug = str(os.getenv("ASSETS_FILTER_DEBUG", "1")).strip().lower() not in {"0", "false", "no", "off"}

    filter_stats: Dict[str, int] = {
        "scanned": 0,
        "inaccessible": 0,
        "meta_filtered": 0,
        "matched": 0,
        "returned": 0,
        "skipped_by_paging": 0,
    }
    filter_reason_stats: Dict[str, int] = {}
    episode_reject_samples: List[Dict[str, Any]] = []
    asset_shot_cache: Dict[int, Optional[Shot]] = {}
    asset_scene_cache: Dict[int, Optional[Scene]] = {}
    asset_episode_cache: Dict[int, Optional[Episode]] = {}
    project_entity_image_token_cache: Optional[Set[str]] = None

    def _collect_asset_url_tokens(value: Any) -> Set[str]:
        raw = str(value or '').strip()
        if not raw:
            return set()

        tokens: Set[str] = set()

        def _push(token_value: Any) -> None:
            token_text = str(token_value or '').strip()
            if token_text:
                tokens.add(token_text.lower())

        _push(raw)
        try:
            parsed = urllib.parse.urlparse(raw)
            path = urllib.parse.unquote(parsed.path or '').strip()
        except Exception:
            path = ''

        if path:
            normalized_path = path.replace('\\', '/').strip()
            trimmed_path = normalized_path.lstrip('/')
            _push(normalized_path)
            _push(trimmed_path)
            base_name = os.path.basename(trimmed_path)
            if base_name:
                _push(base_name)
            path_parts = [part for part in trimmed_path.split('/') if part]
            if len(path_parts) >= 2:
                _push('/'.join(path_parts[-2:]))
            if len(path_parts) >= 3:
                _push('/'.join(path_parts[-3:]))

        return tokens

    def _get_project_entity_image_tokens() -> Set[str]:
        nonlocal project_entity_image_token_cache
        if project_entity_image_token_cache is not None:
            return project_entity_image_token_cache

        project_entity_image_token_cache = set()
        req_project_text = _normalize_filter_text(project_id)
        if not req_project_text:
            return project_entity_image_token_cache

        try:
            req_project_int = int(req_project_text)
        except Exception:
            return project_entity_image_token_cache

        try:
            entity_rows = db.query(Entity.image_url).filter(Entity.project_id == req_project_int).all()
        except Exception:
            logger.exception('[AssetsFilterDiag] failed to preload entity image tokens for project_id=%s', req_project_text)
            return project_entity_image_token_cache

        for (image_url,) in entity_rows:
            project_entity_image_token_cache.update(_collect_asset_url_tokens(image_url))
        return project_entity_image_token_cache

    def _asset_matches_project_entity_image(asset_row: Asset) -> bool:
        if str(getattr(asset_row, 'type', '') or '').strip().lower() != 'image':
            return False
        project_tokens = _get_project_entity_image_tokens()
        if not project_tokens:
            return False
        asset_tokens = _collect_asset_url_tokens(getattr(asset_row, 'url', None))
        if not asset_tokens:
            return False
        return any(token in project_tokens for token in asset_tokens)

    def _normalize_filter_text(value: Any) -> str:
        raw = str(value or '').strip()
        if not raw:
            return ''
        lowered = raw.lower()
        if lowered in {'null', 'none', 'undefined', 'nan'}:
            return ''
        return raw

    def _eval_meta_filters(asset_row: Asset, meta: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        if project_id:
            p_id = meta.get('project_id') or getattr(asset_row, 'project_id', None)
            p_text = _normalize_filter_text(p_id)
            req_project_text = _normalize_filter_text(project_id)
            project_image_backed = False
            if p_text != req_project_text:
                project_image_backed = _asset_matches_project_entity_image(asset_row)
            if strict_meta_filter:
                if p_text != req_project_text and not project_image_backed:
                    return False, "project_mismatch", {
                        "asset_project": p_text,
                        "request_project": req_project_text,
                        "project_image_backed": project_image_backed,
                    }
            elif p_text and p_text != req_project_text and not project_image_backed:
                return False, "project_mismatch", {
                    "asset_project": p_text,
                    "request_project": req_project_text,
                    "project_image_backed": project_image_backed,
                }

        if episode_id:
            ep_id = meta.get('episode_id') or getattr(asset_row, 'episode_id', None)
            ep_text = _normalize_filter_text(ep_id)
            req_ep_text = _normalize_filter_text(episode_id)
            if include_null_episode_for_project_scope and project_id:
                # Allow either the current episode or project-level shared assets with NULL episode.
                if ep_text and ep_text != req_ep_text:
                    return False, "episode_mismatch_when_include_null", {
                        "asset_episode": ep_text,
                        "request_episode": req_ep_text,
                    }
            elif strict_meta_filter:
                if ep_text != req_ep_text:
                    return False, "episode_mismatch", {
                        "asset_episode": ep_text,
                        "request_episode": req_ep_text,
                    }
            elif ep_text and ep_text != req_ep_text:
                return False, "episode_mismatch", {
                    "asset_episode": ep_text,
                    "request_episode": req_ep_text,
                }

        if entity_id:
            e_id = meta.get('entity_id')
            if strict_meta_filter:
                if str(e_id or '').strip() != str(entity_id):
                    return False, "entity_mismatch", {}
            elif e_id and str(e_id) != str(entity_id):
                return False, "entity_mismatch", {}

        if shot_id:
            s_id = meta.get('shot_id')
            if strict_meta_filter:
                if str(s_id or '').strip() != str(shot_id):
                    return False, "shot_mismatch", {}
            elif s_id and str(s_id) != str(shot_id):
                return False, "shot_mismatch", {}

        if scene_id:
            sc_id = meta.get('scene_id')
            if strict_meta_filter:
                if str(sc_id or '').strip() != str(scene_id):
                    return False, "scene_mismatch", {}
            elif sc_id and str(sc_id) != str(scene_id):
                return False, "scene_mismatch", {}

        return True, "ok", {}

    def _is_asset_accessible(asset_row: Asset, meta: Dict[str, Any]) -> bool:
        owner_id = int(asset_row.user_id or 0)
        if owner_id == int(current_user.id):
            return True

        # Shared-project assets are visible only when they are explicitly tied to an accessible project.
        project_meta_id = meta.get('project_id')
        try:
            project_meta_id_int = int(project_meta_id)
        except Exception:
            return False

        return project_meta_id_int in accessible_project_id_set

    ordered_query = query.order_by(Asset.created_at.desc())

    filtered_assets: List[Asset] = []
    matched_assets: List[Asset] = []
    scan_offset = 0
    scanned_rows = 0
    matched_skipped = 0
    batch_size = min(400, max(120, safe_limit * 2))
    max_scan_rows = max(1000, int(os.getenv("ASSETS_LIST_MAX_SCAN_ROWS", "5000") or 5000))

    while len(filtered_assets) < safe_limit and scanned_rows < max_scan_rows:
        batch = ordered_query.offset(scan_offset).limit(batch_size).all()
        if not batch:
            break

        for asset_row in batch:
            filter_stats["scanned"] += 1
            meta = _infer_legacy_shot_asset_meta(
                db,
                asset_row,
                _asset_meta_dict(asset_row.meta_info),
                shot_cache=asset_shot_cache,
                scene_cache=asset_scene_cache,
                episode_cache=asset_episode_cache,
            )
            _sync_asset_denormalized_fields(asset_row)
            if not _is_asset_accessible(asset_row, meta):
                filter_stats["inaccessible"] += 1
                continue
            is_match, reason, detail = _eval_meta_filters(asset_row, meta)
            if not is_match:
                filter_stats["meta_filtered"] += 1
                filter_reason_stats[reason] = int(filter_reason_stats.get(reason, 0)) + 1
                if reason.startswith("episode") and len(episode_reject_samples) < 12:
                    episode_reject_samples.append({
                        "asset_id": int(getattr(asset_row, "id", 0) or 0),
                        "asset_episode_raw": str(meta.get("episode_id") or getattr(asset_row, "episode_id", None) or "").strip(),
                        "asset_project_raw": str(meta.get("project_id") or getattr(asset_row, "project_id", None) or "").strip(),
                        "detail": detail,
                    })
                continue

            filter_stats["matched"] += 1

            if current_only_mode is not None:
                matched_assets.append(asset_row)
                continue

            if matched_skipped < safe_skip:
                matched_skipped += 1
                filter_stats["skipped_by_paging"] += 1
                continue

            filtered_assets.append(asset_row)
            if len(filtered_assets) >= safe_limit:
                break

        scan_offset += len(batch)
        scanned_rows += len(batch)

    if current_only_mode is not None:
        effective_current_ids = _resolve_effective_current_project_asset_ids(db, matched_assets)
        scoped_assets = [
            asset_row
            for asset_row in matched_assets
            if (int(asset_row.id) in effective_current_ids) == bool(current_only_mode)
        ]
        filtered_assets = scoped_assets[safe_skip:safe_skip + safe_limit]

    filter_stats["returned"] = len(filtered_assets)

    effective_current_ids_for_results: Set[int] = set()
    if project_id:
        effective_source_assets = matched_assets if current_only_mode is not None else filtered_assets
        effective_current_ids_for_results = _resolve_effective_current_project_asset_ids(db, effective_source_assets)

    # Enrichment Logic for Grouping
    project_ids = set()
    episode_ids = set()
    entity_ids = set()
    shot_ids = set()


    for a in filtered_assets:
        # Ensure meta is a dict
        meta = _infer_legacy_shot_asset_meta(
            db,
            a,
            _asset_meta_dict(a.meta_info),
            shot_cache=asset_shot_cache,
            scene_cache=asset_scene_cache,
            episode_cache=asset_episode_cache,
        )
            
        p_id = meta.get('project_id')
        if p_id: 
            try: project_ids.add(int(p_id))
            except: pass

        ep_id = getattr(a, 'episode_id', None) or meta.get('episode_id')
        if ep_id:
            try: episode_ids.add(int(ep_id))
            except: pass
            
        e_id = meta.get('entity_id')
        if e_id: 
            try: entity_ids.add(int(e_id))
            except: pass
            
        s_id = meta.get('shot_id')
        if s_id: 
            try: shot_ids.add(int(s_id))
            except: pass

    # ... Fetch Maps ...
    
    # ... Populate Results ...
    project_map = {}
    if project_ids:
        projects = db.query(Project.id, Project.title).filter(Project.id.in_(project_ids)).all()
        project_map = {p.id: p.title for p in projects}

    episode_map = {}
    if episode_ids:
        episodes = db.query(Episode.id, Episode.title).filter(Episode.id.in_(episode_ids)).all()
        episode_map = {e.id: e.title for e in episodes}
        
    entity_map = {}
    if entity_ids:
        entities = db.query(Entity.id, Entity.name).filter(Entity.id.in_(entity_ids)).all()
        entity_map = {e.id: e.name for e in entities}
        
    shot_map = {}
    if shot_ids:
        shots = db.query(Shot.id, Shot.shot_id).filter(Shot.id.in_(shot_ids)).all()
        shot_map = {s.id: s.shot_id for s in shots}

    provider_alias_map = _build_provider_alias_lookup(db)
    results = []
    for a in filtered_assets:
        meta = _asset_meta_dict(a.meta_info)
        
        # Make a copy to avoid mutating SQLAlchemy object if it was a dict
        meta = dict(meta)
        
        # Enrich
        p_id = meta.get('project_id')
        if not p_id and project_id and _asset_matches_project_entity_image(a):
            try:
                meta['project_id'] = int(str(project_id).strip())
                p_id = meta['project_id']
                meta.setdefault('asset_origin', 'entity_image_url_linked_upload')
            except Exception:
                pass
        if p_id:
            try:
                pid_int = int(p_id)
                if pid_int in project_map: meta['project_title'] = project_map[pid_int]
            except: pass

        ep_id = getattr(a, 'episode_id', None) or meta.get('episode_id')
        if ep_id:
            try:
                eid_int = int(ep_id)
                meta['episode_id'] = eid_int
                if eid_int in episode_map:
                    meta['episode_title'] = episode_map[eid_int]
            except: pass
            
        e_id = meta.get('entity_id')
        if e_id:
            try:
                eid_int = int(e_id)
                if eid_int in entity_map: meta['entity_name'] = entity_map[eid_int]
            except: pass
            
        s_id = meta.get('shot_id')
        if s_id:
            try:
                sid_int = int(s_id)
                if sid_int in shot_map: meta['shot_number'] = shot_map[sid_int]
            except: pass

        meta = _attach_provider_alias_to_dict(meta, provider_alias_map)

        results.append({
            "id": a.id,
            "type": _resolve_asset_response_type(a, meta),
            "url": oss_storage_service.refresh_url(a.url) if oss_storage_service.is_enabled(db) else a.url,
            "filename": a.filename,
            "project_id": getattr(a, 'project_id', None),
            "episode_id": getattr(a, 'episode_id', None),
            "is_current_project_asset": int(a.id) in effective_current_ids_for_results if effective_current_ids_for_results else bool(getattr(a, 'is_current_project_asset', False)),
            "meta_info": meta,
            "remark": a.remark,
            "created_at": a.created_at
        })

    return results

@router.post("/assets/", response_model=dict)
def create_asset_url(
    asset_in: AssetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meta = asset_in.meta_info if asset_in.meta_info else {}
    meta['source'] = 'external_url'
    meta = enrich_asset_meta_info(
        meta,
        url=asset_in.url,
        media_kind=asset_in.type,
    )

    existing_asset = _find_existing_asset_for_registration(
        db,
        current_user.id,
        url=asset_in.url,
        idempotency_key=meta.get("idempotency_key"),
        meta_info=meta,
    )
    if existing_asset:
        enriched_meta = enrich_asset_meta_info(
            _asset_meta_dict(existing_asset.meta_info),
            url=str(existing_asset.url or asset_in.url or ""),
            media_kind=str(existing_asset.type or asset_in.type or ""),
        )
        if enriched_meta != _asset_meta_dict(existing_asset.meta_info):
            existing_asset.meta_info = enriched_meta
        _sync_asset_denormalized_fields(existing_asset)
        if existing_asset.project_id:
            _mark_asset_as_current_project_asset(db, existing_asset)
        db.commit()
        db.refresh(existing_asset)
        return _serialize_asset_row(existing_asset, db)

    asset = Asset(
        user_id=current_user.id,
        type=asset_in.type,
        url=asset_in.url,
        url_normalized=_normalize_asset_url_for_dedup(asset_in.url),
        project_id=_asset_optional_int(meta.get('project_id')),
        episode_id=_asset_optional_int(meta.get('episode_id')),
        meta_info=meta,
        remark=asset_in.remark
    )
    db.add(asset)
    db.flush()
    _mark_asset_as_current_project_asset(db, asset)
    db.commit()
    db.refresh(asset)
    return _serialize_asset_row(asset, db)

@router.post("/assets/upload", response_model=dict)
def upload_asset(
    file: UploadFile = File(...),
    type: str = Form("image"), # image or video
    remark: Optional[str] = Form(None),
    project_id: Optional[str] = Form(None),
    episode_id: Optional[str] = Form(None),
    entity_id: Optional[str] = Form(None),
    shot_id: Optional[str] = Form(None),
    shot_number: Optional[str] = Form(None),
    shot_name: Optional[str] = Form(None),
    asset_type: Optional[str] = Form(None),
    source_asset_url: Optional[str] = Form(None),
    idempotency_key: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    max_upload_bytes = max(int(settings.MAX_ASSET_UPLOAD_MB or 100), 1) * 1024 * 1024
    allowed_image_ext = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    allowed_video_ext = {'.mp4', '.mov', '.avi', '.webm'}
    normalized_idempotency_key = _normalize_asset_idempotency_key(idempotency_key)

    if normalized_idempotency_key:
        existing_asset = _find_existing_asset_for_registration(
            db,
            current_user.id,
            idempotency_key=normalized_idempotency_key,
        )
        if existing_asset:
            _sync_asset_denormalized_fields(existing_asset)
            if getattr(existing_asset, "project_id", None):
                _mark_asset_as_current_project_asset(db, existing_asset)
                db.commit()
                db.refresh(existing_asset)
            return _serialize_asset_row(existing_asset, db)

    # Ensure upload directory
    upload_dir = settings.UPLOAD_DIR
    
    # Store by user
    user_upload_dir = os.path.join(upload_dir, str(current_user.id))
    if not os.path.exists(user_upload_dir):
        os.makedirs(user_upload_dir)
    
    # Generate unique filename
    ext = (os.path.splitext(file.filename or "")[1] or "").lower()
    if ext not in (allowed_image_ext | allowed_video_ext):
        raise HTTPException(status_code=400, detail="Unsupported file extension")

    content_type = (file.content_type or "").lower()
    if ext in allowed_video_ext and not content_type.startswith('video/'):
        raise HTTPException(status_code=400, detail="File content type does not match video extension")
    if ext in allowed_image_ext and not content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File content type does not match image extension")

    filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(user_upload_dir, filename)

    # Auto-detect type
    if ext in allowed_video_ext:
        type = 'video'
    elif ext in allowed_image_ext:
        type = 'image'

    bytes_written = 0
    try:
        with open(file_path, "wb") as buffer:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_upload_bytes:
                    raise HTTPException(status_code=413, detail=f"File too large (max {settings.MAX_ASSET_UPLOAD_MB}MB)")
                buffer.write(chunk)
    except HTTPException:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    except Exception:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

    if bytes_written <= 0:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail="Empty file")
        
    # Extract Metadata
    meta_info = {'source': 'file_upload'}
    if project_id: meta_info['project_id'] = project_id
    if episode_id: meta_info['episode_id'] = episode_id
    if entity_id: meta_info['entity_id'] = entity_id
    if shot_id: meta_info['shot_id'] = shot_id
    if shot_number: meta_info['shot_number'] = shot_number
    if shot_name: meta_info['shot_name'] = shot_name
    if asset_type:
        meta_info['asset_type'] = asset_type
        meta_info['frame_type'] = asset_type
    if source_asset_url:
        meta_info['source_asset_url'] = source_asset_url
    if normalized_idempotency_key:
        meta_info['idempotency_key'] = normalized_idempotency_key
    
    try:
        probed_meta = probe_media_from_path(file_path, type)
        if probed_meta:
            meta_info.update(probed_meta)
        elif os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            meta_info['size'] = f"{file_size / 1024:.2f} KB"
    except Exception as e:
        logger.warning("Metadata extraction failed during upload: %s", e)

    # Construct URL (assuming /uploads is mounted)
    # Get base URL from request ideally, but relative works for frontend
    base_url = settings.RENDER_EXTERNAL_URL.rstrip('/') if settings.RENDER_EXTERNAL_URL else ""
    url = f"{base_url}/uploads/{current_user.id}/{filename}"

    oss_url = None
    if oss_storage_service.is_enabled(db):
        try:
            oss_res = oss_storage_service.upload_file(
                file_path,
                user_id=current_user.id,
                filename=file.filename,
                content_type=file.content_type,
                category="uploads"
            )
            if oss_res and oss_res.get("url"):
                oss_url = oss_res.get("url")
                meta_info['oss'] = {
                    'provider': oss_res.get('provider'),
                    'bucket': oss_res.get('bucket'),
                    'key': oss_res.get('key'),
                }
        except Exception as e:
            logger.warning(f"OSS upload failed for asset: {e}")

    if oss_url:
        url = oss_url
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass

    asset = Asset(
        user_id=current_user.id,
        type=type,
        url=url,
        filename=file.filename,
        project_id=_asset_optional_int(meta_info.get('project_id')),
        episode_id=_asset_optional_int(meta_info.get('episode_id')),
        meta_info=meta_info,
        remark=remark
    )
    db.add(asset)
    db.flush()
    _mark_asset_as_current_project_asset(db, asset)
    db.commit()
    db.refresh(asset)

    return _serialize_asset_row(asset, db)


@router.delete("/assets/{asset_id}")
def delete_asset(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    asset = db.query(Asset).filter(
        Asset.id == asset_id,
        Asset.user_id == current_user.id,
        _active_asset_clause(),
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    if _is_soft_deleted(asset):
        return {"status": "success", "batch_id": None}

    episode_id = _assert_episode_scoped_delete(asset, label="Asset")
    project_id = int(asset.project_id or 0)
    if project_id <= 0:
        meta = asset.meta_info if isinstance(asset.meta_info, dict) else {}
        try:
            project_id = int(meta.get("project_id") or 0)
        except Exception:
            project_id = 0
    if project_id <= 0:
        raise HTTPException(status_code=400, detail="Asset is missing project scope")
    _require_project_access(db, project_id, current_user, owner_only=True)

    batch_id = _start_deletion_batch(
        db,
        user_id=current_user.id,
        project_id=project_id if project_id > 0 else 0,
        episode_id=episode_id,
        action_type="asset",
        label=str(asset.filename or asset.url or f"Asset {asset_id}"),
    )
    _soft_delete_assets(db, asset_id=asset_id, user_id=current_user.id, batch_id=batch_id)
    _finalize_deletion_batch(db, batch_id)
    db.commit()
    return {"status": "success", "batch_id": batch_id}

@router.post("/assets/batch-delete")
def batch_delete_assets(
    asset_ids: List[int] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    assets = db.query(Asset).filter(
        Asset.id.in_(asset_ids), 
        Asset.user_id == current_user.id,
        _active_asset_clause(),
    ).all()

    episode_scoped_assets: List[Asset] = []
    skipped_project_scoped = 0
    for asset in assets:
        if _resolve_record_episode_id(asset) is None:
            skipped_project_scoped += 1
            continue
        episode_scoped_assets.append(asset)

    from collections import defaultdict

    grouped: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for asset in episode_scoped_assets:
        episode_id = int(_resolve_record_episode_id(asset) or 0)
        project_id = int(asset.project_id or 0)
        if project_id <= 0:
            meta = asset.meta_info if isinstance(asset.meta_info, dict) else {}
            try:
                project_id = int(meta.get("project_id") or 0)
            except Exception:
                project_id = 0
        if project_id <= 0 or episode_id <= 0:
            skipped_project_scoped += 1
            continue
        grouped[(project_id, episode_id)].append(int(asset.id))

    batch_ids: List[str] = []
    deleted_count = 0
    for (project_id, episode_id), scoped_ids in grouped.items():
        _require_project_access(db, project_id, current_user, owner_only=True)
        batch_id = _start_deletion_batch(
            db,
            user_id=current_user.id,
            project_id=project_id,
            episode_id=episode_id,
            action_type="assets_batch",
            label=f"Batch delete {len(scoped_ids)} assets",
        )
        deleted_count += _soft_delete_assets(
            db,
            asset_ids=scoped_ids,
            user_id=current_user.id,
            batch_id=batch_id,
        )
        _finalize_deletion_batch(db, batch_id)
        batch_ids.append(batch_id)
        
    db.commit()
    return {
        "status": "success",
        "deleted_count": deleted_count,
        "skipped_project_scoped": skipped_project_scoped,
        "batch_id": batch_ids[0] if len(batch_ids) == 1 else None,
        "batch_ids": batch_ids,
    }

@router.put("/assets/{asset_id}", response_model=dict)
def update_asset(
    asset_id: int,
    asset_update: AssetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    asset = db.query(Asset).filter(
        Asset.id == asset_id,
        Asset.user_id == current_user.id,
        _active_asset_clause(),
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    if asset_update.remark is not None:
        asset.remark = asset_update.remark
    if asset_update.meta_info is not None:
         # Merge or replace? Let's replace for now or merge if needed
         # asset.meta_info = {**asset.meta_info, **asset_update.meta_info} 
         asset.meta_info = asset_update.meta_info
         _sync_asset_denormalized_fields(asset)
         if asset.project_id:
             _mark_asset_as_current_project_asset(db, asset)
         
    db.commit()
    db.refresh(asset)

    return _serialize_asset_row(asset, db)


def _probe_and_update_asset_metadata(
    asset: Asset,
    *,
    overwrite: bool = False,
) -> Tuple[Dict[str, Any], bool]:
    current_meta = _asset_meta_dict(getattr(asset, "meta_info", None))
    enriched_meta = enrich_asset_meta_info(
        current_meta,
        url=str(getattr(asset, "url", "") or ""),
        media_kind=str(getattr(asset, "type", "") or ""),
        overwrite=overwrite,
    )
    changed = enriched_meta != current_meta
    if changed:
        asset.meta_info = enriched_meta
        _sync_asset_denormalized_fields(asset)
    return enriched_meta, changed


@router.post("/assets/{asset_id}/probe-metadata", response_model=dict)
def probe_asset_metadata(
    asset_id: int,
    overwrite: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    asset = db.query(Asset).filter(
        Asset.id == asset_id,
        Asset.user_id == current_user.id,
        _active_asset_clause(),
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    _, changed = _probe_and_update_asset_metadata(asset, overwrite=overwrite)
    if changed and asset.project_id:
        _mark_asset_as_current_project_asset(db, asset)
    db.commit()
    db.refresh(asset)
    return {
        "ok": True,
        "updated": changed,
        "asset": _serialize_asset_row(asset, db),
    }


@router.post("/assets/backfill-metadata", response_model=dict)
def backfill_assets_metadata(
    payload: AssetBackfillMetadataRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    safe_limit = max(1, min(int(payload.limit or 200), 1000))
    query = db.query(Asset).filter(Asset.user_id == current_user.id, _active_asset_clause())

    if payload.asset_ids:
        scoped_ids = [int(item) for item in payload.asset_ids if int(item) > 0][:safe_limit]
        if not scoped_ids:
            return {"ok": True, "dry_run": payload.dry_run, "scanned": 0, "updated": 0, "skipped": 0, "asset_ids": []}
        query = query.filter(Asset.id.in_(scoped_ids))
    else:
        if payload.project_id:
            query = query.filter(Asset.project_id == int(payload.project_id))
        if payload.episode_id:
            query = query.filter(Asset.episode_id == int(payload.episode_id))
        query = query.order_by(Asset.id.desc()).limit(safe_limit)

    assets = query.all()
    updated_ids: List[int] = []
    skipped = 0

    for asset in assets:
        media_kind = str(getattr(asset, "type", "") or "")
        if not asset_meta_needs_probe(_asset_meta_dict(asset.meta_info), media_kind or "image") and not payload.overwrite_existing:
            skipped += 1
            continue

        if payload.dry_run:
            if asset_meta_needs_probe(_asset_meta_dict(asset.meta_info), media_kind or "image") or payload.overwrite_existing:
                updated_ids.append(int(asset.id))
            else:
                skipped += 1
            continue

        _, changed = _probe_and_update_asset_metadata(asset, overwrite=payload.overwrite_existing)
        if changed:
            updated_ids.append(int(asset.id))
            if asset.project_id:
                _mark_asset_as_current_project_asset(db, asset)
        else:
            skipped += 1

    if not payload.dry_run and updated_ids:
        db.commit()

    return {
        "ok": True,
        "dry_run": payload.dry_run,
        "scanned": len(assets),
        "updated": len(updated_ids),
        "skipped": skipped,
        "asset_ids": updated_ids,
    }


@router.post("/assets/{asset_id}/mark-current", response_model=dict)
def mark_asset_current_project_asset(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    asset = db.query(Asset).filter(
        Asset.id == asset_id,
        Asset.user_id == current_user.id,
        _active_asset_clause(),
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    _sync_asset_denormalized_fields(asset)
    if not asset.project_id:
        raise HTTPException(status_code=400, detail="Asset is not scoped to a project")

    _mark_asset_as_current_project_asset(db, asset)
    db.commit()
    db.refresh(asset)
    return _serialize_asset_row(asset, db)


def _resolve_asset_shot_media_slot(asset: Asset, meta: Dict[str, Any]) -> Optional[str]:
    asset_type = str(meta.get("asset_type") or meta.get("frame_type") or "").strip().lower()
    if asset_type in {"start_frame", "start"}:
        return "start"
    if asset_type in {"end_frame", "end"}:
        return "end"
    if asset_type == "video" or str(getattr(asset, "type", "") or "").strip().lower() == "video":
        return "video"
    if str(getattr(asset, "type", "") or "").strip().lower() == "image":
        return "start"
    return None


def _resolve_asset_entity_media_slot(asset: Asset, meta: Dict[str, Any]) -> Optional[str]:
    asset_type = str(meta.get("asset_type") or meta.get("frame_type") or "").strip().lower()
    media_type = str(getattr(asset, "type", "") or meta.get("type") or "").strip().lower()
    if media_type == "video" or asset_type == "video":
        return "video"
    if media_type == "audio" or asset_type in {"audio", "voice", "tts"}:
        return "audio"
    if media_type == "image" or asset_type in {
        "subject",
        "character",
        "char",
        "environment",
        "prop",
        "poster",
    }:
        return "image"
    return None


def _backfill_episode_media_from_library(
    db: Session,
    current_user: User,
    project_id: int,
    episode_id: int,
    *,
    dry_run: bool = False,
    include_shots: bool = True,
    include_entities: bool = True,
    limit: int = 10000,
    overwrite_existing: bool = True,
) -> Dict[str, Any]:
    project = _require_project_access(db, project_id, current_user)
    episode = db.query(Episode).filter(
        Episode.id == episode_id,
        Episode.project_id == project_id,
        _active_episode_clause(),
    ).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    safe_limit = max(1, min(int(limit or 10000), 10000))
    owner_ids = _visible_asset_owner_ids_for_project(project, current_user)

    scene_rows = db.query(Scene.id).filter(
        Scene.episode_id == episode_id,
        _active_scene_clause(),
    ).all()
    scene_ids = [int(row[0]) for row in scene_rows if row and row[0] is not None]
    episode_shot_ids = set()
    if scene_ids:
        shot_rows = db.query(Shot.id).filter(
            Shot.scene_id.in_(scene_ids),
            _active_shot_clause(),
        ).all()
        episode_shot_ids = {int(row[0]) for row in shot_rows if row and row[0] is not None}

    entity_cache: Dict[int, Entity] = {}
    entity_name_index: Dict[str, Entity] = {}
    if include_entities:
        episode_entities = db.query(Entity).filter(
            Entity.project_id == project_id,
            Entity.episode_id == episode_id,
            _active_entity_clause(),
        ).all()
        for entity in episode_entities:
            entity_cache[int(entity.id)] = entity
            for label in (getattr(entity, "name", None), getattr(entity, "name_en", None)):
                normalized = str(label or "").strip().lower()
                if normalized and normalized not in entity_name_index:
                    entity_name_index[normalized] = entity

    assets = (
        db.query(Asset)
        .filter(
            Asset.user_id.in_(owner_ids),
            _active_asset_clause(),
            Asset.url.isnot(None),
            Asset.url != "",
            Asset.project_id == project_id,
            or_(Asset.episode_id == episode_id, Asset.episode_id.is_(None)),
        )
        .order_by(Asset.created_at.desc(), Asset.id.desc())
        .limit(safe_limit)
        .all()
    )

    shot_cache: Dict[int, Optional[Shot]] = {}
    scene_cache: Dict[int, Optional[Scene]] = {}
    touched_shots: Dict[int, Shot] = {}
    touched_entities: Dict[int, Entity] = {}
    stats = {
        "scanned": 0,
        "eligible": 0,
        "bound_shots": 0,
        "bound_entities": 0,
        "skipped_existing": 0,
        "skipped_no_target": 0,
        "skipped_filter": 0,
        "skipped_unknown_type": 0,
    }

    def _meta_dict(raw_meta: Any) -> Dict[str, Any]:
        return _asset_meta_dict(raw_meta)

    def _to_int(value: Any) -> Optional[int]:
        return _asset_optional_int(value)

    def _shot_belongs_to_episode(shot: Shot) -> bool:
        scene_id_int = _to_int(getattr(shot, "scene_id", None))
        if not scene_id_int:
            return False
        if scene_id_int in scene_ids:
            return True
        if scene_id_int not in scene_cache:
            scene_cache[scene_id_int] = db.query(Scene).filter(Scene.id == scene_id_int).first()
        scene = scene_cache.get(scene_id_int)
        return bool(scene and _to_int(getattr(scene, "episode_id", None)) == episode_id)

    def _entity_in_episode_scope(entity: Entity) -> bool:
        return _to_int(getattr(entity, "episode_id", None)) == episode_id

    def _asset_episode_id(asset: Asset, meta: Dict[str, Any]) -> Optional[int]:
        return _to_int(getattr(asset, "episode_id", None) or meta.get("episode_id"))

    def _asset_in_project_scope(asset: Asset, meta: Dict[str, Any]) -> bool:
        asset_project_id = _to_int(getattr(asset, "project_id", None) or meta.get("project_id"))
        return asset_project_id == project_id

    def _asset_in_episode_scope(asset: Asset, meta: Dict[str, Any], shot: Optional[Shot]) -> bool:
        asset_episode_id = _asset_episode_id(asset, meta)
        if asset_episode_id is not None:
            return asset_episode_id == episode_id
        if shot and _shot_belongs_to_episode(shot):
            return True
        return False

    best_shot_bindings: Dict[Tuple[int, str], Tuple[Shot, str]] = {}
    best_entity_bindings: Dict[Tuple[int, str], Tuple[Entity, str]] = {}

    for asset in assets:
        stats["scanned"] += 1
        meta = _meta_dict(asset.meta_info)
        if not _asset_in_project_scope(asset, meta):
            stats["skipped_filter"] += 1
            continue

        media_url = str(asset.url or "").strip()
        if not media_url or _is_ephemeral_provider_media_url(media_url):
            stats["skipped_filter"] += 1
            continue

        stable_url = _refresh_managed_media_url(media_url, db)

        shot: Optional[Shot] = None
        shot_id = _to_int(meta.get("shot_id"))
        if shot_id:
            if shot_id not in shot_cache:
                shot_cache[shot_id] = db.query(Shot).filter(
                    Shot.id == shot_id,
                    _active_shot_clause(),
                ).first()
            shot = shot_cache.get(shot_id)

        if include_shots and shot and _asset_in_episode_scope(asset, meta, shot):
            slot = _resolve_asset_shot_media_slot(asset, meta)
            if not slot:
                stats["skipped_unknown_type"] += 1
            else:
                shot_key = (int(shot.id), slot)
                if shot_key not in best_shot_bindings:
                    stats["eligible"] += 1
                    best_shot_bindings[shot_key] = (shot, stable_url)

        if not include_entities:
            continue

        entity: Optional[Entity] = None
        entity_id = _to_int(meta.get("entity_id"))
        if entity_id:
            entity = entity_cache.get(entity_id)
        if not entity and _asset_episode_id(asset, meta) == episode_id:
            subject_name = str(meta.get("subject_name") or meta.get("entity_name") or "").strip().lower()
            if subject_name:
                entity = entity_name_index.get(subject_name)

        if not entity or not _entity_in_episode_scope(entity):
            if shot:
                continue
            stats["skipped_no_target"] += 1
            continue

        if not _asset_in_episode_scope(asset, meta, shot):
            stats["skipped_filter"] += 1
            continue

        slot = _resolve_asset_entity_media_slot(asset, meta)
        if not slot:
            stats["skipped_unknown_type"] += 1
            continue

        entity_key = (int(entity.id), slot)
        if entity_key not in best_entity_bindings:
            stats["eligible"] += 1
            best_entity_bindings[entity_key] = (entity, stable_url)

    for (_shot_id, slot), (shot, stable_url) in best_shot_bindings.items():
        changed = False
        if slot == "start":
            current = str(getattr(shot, "image_url", "") or "").strip()
            if current and not overwrite_existing:
                stats["skipped_existing"] += 1
                continue
            stats["bound_shots"] += 1
            if not dry_run and (overwrite_existing or not current):
                shot.image_url = stable_url
                changed = True
        elif slot == "video":
            current = str(getattr(shot, "video_url", "") or "").strip()
            if current and not overwrite_existing:
                stats["skipped_existing"] += 1
                continue
            stats["bound_shots"] += 1
            if not dry_run and (overwrite_existing or not current):
                shot.video_url = stable_url
                changed = True
        elif slot == "end":
            tech = _asset_meta_to_dict(getattr(shot, "technical_notes", None))
            current = str(tech.get("end_frame_url") or "").strip()
            if current and not overwrite_existing:
                stats["skipped_existing"] += 1
                continue
            stats["bound_shots"] += 1
            if not dry_run and (overwrite_existing or not current):
                tech["end_frame_url"] = stable_url
                shot.technical_notes = json.dumps(tech, ensure_ascii=False)
                changed = True
        if changed:
            db.add(shot)
            touched_shots[int(shot.id)] = shot

    for (_entity_id, slot), (entity, stable_url) in best_entity_bindings.items():
        changed = False
        if slot == "image":
            current = str(getattr(entity, "image_url", "") or "").strip()
            if current and not overwrite_existing:
                stats["skipped_existing"] += 1
                continue
            stats["bound_entities"] += 1
            if not dry_run and (overwrite_existing or not current):
                entity.image_url = stable_url
                changed = True
        elif slot == "video":
            current = str(getattr(entity, "video_url", "") or "").strip()
            if current and not overwrite_existing:
                stats["skipped_existing"] += 1
                continue
            stats["bound_entities"] += 1
            if not dry_run and (overwrite_existing or not current):
                entity.video_url = stable_url
                changed = True
        elif slot == "audio":
            current = str(getattr(entity, "audio_url", "") or "").strip()
            if current and not overwrite_existing:
                stats["skipped_existing"] += 1
                continue
            stats["bound_entities"] += 1
            if not dry_run and (overwrite_existing or not current):
                entity.audio_url = stable_url
                changed = True

        if changed:
            db.add(entity)
            touched_entities[int(entity.id)] = entity

    return {
        **stats,
        "dry_run": bool(dry_run),
        "project_id": project_id,
        "episode_id": episode_id,
        "updated_shots": len(touched_shots),
        "updated_entities": len(touched_entities),
        "limit": safe_limit,
    }


@router.post("/assets/rebind-shot-media", response_model=dict)
def rebind_shot_media_from_assets(
    payload: AssetRebindShotMediaRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if payload.project_id and payload.episode_id:
        _require_project_access(db, int(payload.project_id), current_user)
        safe_limit = max(1, min(int(payload.limit or 10000), 10000))
        result = _backfill_episode_media_from_library(
            db,
            current_user,
            int(payload.project_id),
            int(payload.episode_id),
            dry_run=bool(payload.dry_run),
            include_shots=bool(payload.include_shots),
            include_entities=bool(payload.include_entities),
            limit=safe_limit,
            overwrite_existing=bool(payload.overwrite_existing),
        )
        if not payload.dry_run and (
            int(result.get("updated_shots") or 0) > 0
            or int(result.get("updated_entities") or 0) > 0
        ):
            db.commit()
        result["bound"] = int(result.get("bound_shots") or 0) + int(result.get("bound_entities") or 0)
        return result

    if payload.project_id:
        _require_project_access(db, int(payload.project_id), current_user)

    safe_limit = max(1, min(int(payload.limit or 2000), 10000))

    query = db.query(Asset).filter(Asset.user_id == current_user.id, _active_asset_clause()).order_by(
        Asset.created_at.desc(),
        Asset.id.desc(),
    )
    assets = query.limit(safe_limit).all()

    shot_cache: Dict[int, Optional[Shot]] = {}
    scene_cache: Dict[int, Optional[Scene]] = {}
    episode_cache: Dict[int, Optional[Episode]] = {}

    touched_shots: Dict[int, Shot] = {}
    stats = {
        "scanned": 0,
        "eligible": 0,
        "bound": 0,
        "skipped_existing": 0,
        "skipped_no_shot": 0,
        "skipped_filter": 0,
        "skipped_unknown_type": 0,
    }

    def _meta_dict(raw_meta: Any) -> Dict[str, Any]:
        if isinstance(raw_meta, dict):
            return raw_meta
        if isinstance(raw_meta, str):
            try:
                parsed = json.loads(raw_meta)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    def _to_int(value: Any) -> Optional[int]:
        try:
            if value is None or value == "":
                return None
            return int(value)
        except Exception:
            return None

    for asset in assets:
        stats["scanned"] += 1
        meta = _meta_dict(asset.meta_info)

        sid = _to_int(meta.get("shot_id"))
        if not sid:
            stats["skipped_no_shot"] += 1
            continue

        if payload.shot_id and int(payload.shot_id) != sid:
            stats["skipped_filter"] += 1
            continue

        if payload.project_id:
            meta_project_id = _to_int(meta.get("project_id"))
            if meta_project_id and meta_project_id != int(payload.project_id):
                stats["skipped_filter"] += 1
                continue

        shot = shot_cache.get(sid)
        if sid not in shot_cache:
            shot = db.query(Shot).filter(Shot.id == sid).first()
            shot_cache[sid] = shot

        if not shot:
            stats["skipped_no_shot"] += 1
            continue

        if payload.scene_id and int(payload.scene_id) != int(shot.scene_id or 0):
            stats["skipped_filter"] += 1
            continue

        current_scene = None
        current_episode = None

        if payload.episode_id or payload.project_id:
            scene_id_int = int(shot.scene_id or 0)
            if not scene_id_int:
                stats["skipped_filter"] += 1
                continue

            if scene_id_int not in scene_cache:
                scene_cache[scene_id_int] = db.query(Scene).filter(Scene.id == scene_id_int).first()
            current_scene = scene_cache.get(scene_id_int)
            if not current_scene:
                stats["skipped_filter"] += 1
                continue

            episode_id_int = int(current_scene.episode_id or 0)
            if not episode_id_int:
                stats["skipped_filter"] += 1
                continue

            if episode_id_int not in episode_cache:
                episode_cache[episode_id_int] = db.query(Episode).filter(Episode.id == episode_id_int).first()
            current_episode = episode_cache.get(episode_id_int)
            if not current_episode:
                stats["skipped_filter"] += 1
                continue

        if payload.episode_id and current_episode and int(payload.episode_id) != int(current_episode.id):
            stats["skipped_filter"] += 1
            continue

        if payload.project_id and current_episode and int(payload.project_id) != int(current_episode.project_id or 0):
            stats["skipped_filter"] += 1
            continue

        asset_type = str(meta.get("asset_type") or meta.get("frame_type") or "").strip().lower()
        slot = None
        if asset_type in {"start_frame", "start"}:
            slot = "start"
        elif asset_type in {"end_frame", "end"}:
            slot = "end"
        elif asset_type == "video" or str(asset.type or "").lower() == "video":
            slot = "video"
        elif str(asset.type or "").lower() == "image":
            slot = "start"

        if not slot:
            stats["skipped_unknown_type"] += 1
            continue

        stats["eligible"] += 1
        changed = False

        if slot == "start":
            if str(shot.image_url or "").strip():
                stats["skipped_existing"] += 1
                continue
            if not payload.dry_run:
                shot.image_url = _refresh_managed_media_url(asset.url, db)
                changed = True

        elif slot == "video":
            if str(shot.video_url or "").strip():
                stats["skipped_existing"] += 1
                continue
            if not payload.dry_run:
                shot.video_url = _refresh_managed_media_url(asset.url, db)
                changed = True

        elif slot == "end":
            tech = {}
            try:
                tech = json.loads(shot.technical_notes or "{}")
                if not isinstance(tech, dict):
                    tech = {}
            except Exception:
                tech = {}

            if str(tech.get("end_frame_url") or "").strip():
                stats["skipped_existing"] += 1
                continue

            if not payload.dry_run:
                tech["end_frame_url"] = _refresh_managed_media_url(asset.url, db)
                shot.technical_notes = json.dumps(tech, ensure_ascii=False)
                changed = True

        if changed:
            touched_shots[shot.id] = shot
        stats["bound"] += 1

    if not payload.dry_run and touched_shots:
        db.commit()

    return {
        **stats,
        "dry_run": bool(payload.dry_run),
        "updated_shots": len(touched_shots),
        "limit": safe_limit,
    }


@router.post("/assets/backfill-episode-media", response_model=dict)
def backfill_episode_media_from_assets(
    payload: AssetBackfillEpisodeMediaRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_project_access(db, int(payload.project_id), current_user)
    result = _backfill_episode_media_from_library(
        db,
        current_user,
        int(payload.project_id),
        int(payload.episode_id),
        dry_run=bool(payload.dry_run),
        include_shots=bool(payload.include_shots),
        include_entities=bool(payload.include_entities),
        limit=int(payload.limit or 10000),
        overwrite_existing=bool(payload.overwrite_existing),
    )
    if not payload.dry_run and (
        int(result.get("updated_shots") or 0) > 0
        or int(result.get("updated_entities") or 0) > 0
    ):
        db.commit()
    result["bound"] = int(result.get("bound_shots") or 0) + int(result.get("bound_entities") or 0)
    return result



from app.schemas.billing import TransactionOut, FeaturePricingUpdate, FeaturePricingOut, DefaultApiPricingUpdate, DefaultApiPricingOut
from app.models.all_models import RechargePlan, PaymentOrder
import uuid
import io

from app.schemas.billing import (  # noqa: E402
    PaymentOrderOut,
    RechargePlanOut,
)

# RechargePlanOut/PaymentOrderOut moved to app.schemas.billing

# Payment/SMTP/Maintenance schemas moved to app.schemas.admin_ops
from app.schemas.admin_ops import (  # noqa: E402
    MaintenanceConfig,
    MaintenanceStatusOut,
    PaymentConfig,
    SMTPBroadcastRequest,
    SMTPConfig,
    SMTPTestRequest,
)

# Maintenance status cache lives in app.services.maintenance_status
from app.services.maintenance_status import (  # noqa: E402
    _MAINTENANCE_CATEGORY,
    _MAINTENANCE_PROVIDER,
    _LOGIN_MAINTENANCE_CACHE,
    _LOGIN_MAINTENANCE_CACHE_LOCK,
    _LOGIN_MAINTENANCE_CACHE_TTL_SECONDS,
    _LOGIN_MAINTENANCE_FAILURE_CIRCUIT_OPEN_SECONDS,
    _LOGIN_MAINTENANCE_FAILURE_CIRCUIT_THRESHOLD,
    _LOGIN_MAINTENANCE_FAILURE_COOLDOWN_SECONDS,
    _build_maintenance_status_payload,
    _default_maintenance_status_payload,
    _get_login_maintenance_status_cached,
    _parse_iso_datetime_safe,
    _refresh_login_maintenance_cache_sync,
    _resolve_maintenance_config_raw,
    _schedule_login_maintenance_cache_refresh,
    _store_login_maintenance_cache,
)

from app.services.wechat_pay_config import (  # noqa: E402
    _get_active_wechat_config,
    _wechat_config_to_dict,
)

# wechat helpers moved to app.services.wechat_pay_config

