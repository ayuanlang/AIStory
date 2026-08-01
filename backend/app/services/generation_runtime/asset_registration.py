# -*- coding: utf-8 -*-
"""Asset registration + generated media bind helpers."""
from __future__ import annotations

import json
import logging
import os
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from sqlalchemy import or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.all_models import Asset, Entity, Episode, Project, Scene, Shot, User
from app.services.asset_meta_probe import enrich_asset_meta_info, ensure_resolution_fields
from app.services.asset_meta_utils import (
    _asset_meta_dict,
    _asset_optional_int,
    _sync_asset_denormalized_fields,
)
from app.services.generation_runtime.job_store import ASSET_REGISTRATION_LOCK
from app.services.oss_storage_service import oss_storage_service
from app.services.provider_alias import (
    _attach_provider_alias_to_dict,
    _build_provider_alias_lookup,
)
from app.services.soft_delete import (
    _active_asset_clause,
    _active_entity_clause,
    _active_episode_clause,
)
from app.services.system_log_service import log_action

# workspace.shared does not import generation_runtime — safe at module load.
from app.services.project_access import _require_project_access  # noqa: E402
from app.services.project_episode_utils import _resolve_episode_sort_number  # noqa: E402

logger = logging.getLogger("api_logger")


def _normalize_entity_type(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text:
        return None
    if text in {"character", "char", "role", "人物", "角色"}:
        return "character"
    if text in {"environment", "env", "scene", "场景", "环境"}:
        return "environment"
    if text in {"prop", "props", "道具", "物件"}:
        return "prop"
    return text


def _serialize_asset_row(asset: Asset, db: Session = None) -> Dict[str, Any]:
    _sync_asset_denormalized_fields(asset)
    meta = _asset_meta_dict(getattr(asset, "meta_info", None))
    return {
        "id": asset.id,
        "type": asset.type,
        "url": oss_storage_service.refresh_url(asset.url) if oss_storage_service.is_enabled(db) else asset.url,
        "filename": asset.filename,
        "project_id": getattr(asset, "project_id", None),
        "episode_id": getattr(asset, "episode_id", None),
        "is_current_project_asset": bool(getattr(asset, "is_current_project_asset", False)),
        "meta_info": meta,
        "remark": asset.remark,
        "created_at": asset.created_at,
    }


def _normalize_asset_idempotency_key(value: Any) -> str:
    return str(value or "").strip()


def _normalize_asset_url_for_dedup(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urllib.parse.urlparse(raw)
        if str(parsed.scheme or "").lower() in {"http", "https"}:
            # Ignore volatile signed-query parameters when deduplicating assets.
            cleaned = parsed._replace(query="", fragment="")
            return urllib.parse.urlunparse(cleaned).strip().lower()
    except Exception:
        pass
    return raw.lower()


def _asset_meta_matches_registration_context(asset_meta: Any, expected_meta: Any) -> bool:
    asset_meta = _asset_meta_dict(asset_meta)
    expected_meta = _asset_meta_dict(expected_meta)

    compare_keys = [
        "project_id",
        "episode_id",
        "entity_id",
        "shot_id",
        "asset_type",
        "frame_type",
        "source_asset_url",
    ]
    for key in compare_keys:
        expected_value = str(expected_meta.get(key) or "").strip()
        if not expected_value:
            continue
        if key == "source_asset_url":
            if _normalize_asset_url_for_dedup(asset_meta.get(key)) != _normalize_asset_url_for_dedup(expected_value):
                return False
            continue
        if str(asset_meta.get(key) or "").strip() != expected_value:
            return False
    return True


def _find_existing_asset_for_registration(
    db: Session,
    user_id: int,
    *,
    url: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    meta_info: Optional[Dict[str, Any]] = None,
) -> Optional[Asset]:
    normalized_key = _normalize_asset_idempotency_key(idempotency_key)
    normalized_meta = dict(meta_info) if isinstance(meta_info, dict) else {}

    if normalized_key:
        keyed_candidates = (
            db.query(Asset)
            .filter(Asset.user_id == user_id, _active_asset_clause())
            .order_by(Asset.id.desc())
            .limit(500)
            .all()
        )
        for candidate in keyed_candidates:
            candidate_meta = candidate.meta_info if isinstance(candidate.meta_info, dict) else {}
            if _normalize_asset_idempotency_key(candidate_meta.get("idempotency_key")) != normalized_key:
                continue
            return candidate

    normalized_url = str(url or "").strip()
    if not normalized_url:
        return None
    normalized_compare_url = _normalize_asset_url_for_dedup(normalized_url)

    if normalized_compare_url:
        try:
            normalized_candidates = (
                db.query(Asset)
                .filter(
                    Asset.user_id == user_id,
                    Asset.url_normalized == normalized_compare_url,
                    _active_asset_clause(),
                )
                .order_by(Asset.id.desc())
                .limit(120)
                .all()
            )
            for candidate in normalized_candidates:
                if _asset_meta_matches_registration_context(candidate.meta_info, normalized_meta):
                    return candidate
            # Unique constraint is on (user, type, project, episode, url_normalized).
            # Reusing the same image onto another entity must hit this row even when
            # entity_id / shot_id meta differs — otherwise INSERT races into UniqueViolation
            # and poisons the parent Session.
            expected_project_id = _asset_optional_int(normalized_meta.get("project_id"))
            expected_episode_id = _asset_optional_int(normalized_meta.get("episode_id"))
            for candidate in normalized_candidates:
                candidate_project_id = _asset_optional_int(getattr(candidate, "project_id", None))
                candidate_episode_id = _asset_optional_int(getattr(candidate, "episode_id", None))
                if candidate_project_id != expected_project_id:
                    continue
                if candidate_episode_id != expected_episode_id:
                    continue
                return candidate
            if normalized_candidates and expected_project_id is None and expected_episode_id is None:
                return normalized_candidates[0]
        except Exception:
            # Backward-compatible fallback for old schemas before url_normalized exists.
            pass

    url_candidates = (
        db.query(Asset)
        .filter(
            Asset.user_id == user_id,
            Asset.url == normalized_url,
            _active_asset_clause(),
        )
        .order_by(Asset.id.desc())
        .limit(50)
        .all()
    )
    if url_candidates:
        for candidate in url_candidates:
            if _asset_meta_matches_registration_context(candidate.meta_info, normalized_meta):
                return candidate

    # Fallback dedupe for signed URLs where only query token differs.
    if normalized_compare_url:
        recent_candidates = (
            db.query(Asset)
            .filter(Asset.user_id == user_id, _active_asset_clause())
            .order_by(Asset.id.desc())
            .limit(600)
            .all()
        )
        for candidate in recent_candidates:
            if _normalize_asset_url_for_dedup(getattr(candidate, "url", None)) != normalized_compare_url:
                continue
            if _asset_meta_matches_registration_context(candidate.meta_info, normalized_meta):
                return candidate

    return None


def _resolve_subject_dependency_source_asset_url(db: Session, user_id: int, meta_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Auto-pick a prior-episode same-name subject image as source_asset_url.

    Hard rules:
    - same subject name (exact, case-insensitive trim)
    - source episode is not soft-deleted
    - source episode number must be strictly smaller than the current episode
    - asset / linked entity must not be soft-deleted

    Returns provenance dict: url, asset_id, episode_id/title, entity_id/name, subject_type.
    """
    meta = _asset_meta_dict(meta_info)
    project_id = _asset_optional_int(meta.get("project_id"))
    if not project_id:
        return None

    requested_subject_type = _normalize_entity_type(meta.get("subject_type") or meta.get("entity_type"))
    requested_entity_id = _asset_optional_int(meta.get("entity_id"))
    current_episode_id = _asset_optional_int(meta.get("episode_id"))
    requested_name = str(meta.get("subject_name") or "").strip().lower()
    requested_entity_name = str(meta.get("entity_name") or "").strip().lower()
    requested_name_tokens = {token for token in (requested_name, requested_entity_name) if token}

    # Resolve names / episode / type from the active entity row when meta is incomplete.
    if requested_entity_id:
        entity_row = (
            db.query(Entity)
            .filter(Entity.id == int(requested_entity_id), _active_entity_clause())
            .first()
        )
        if entity_row:
            for token in (
                str(getattr(entity_row, "name", None) or "").strip().lower(),
                str(getattr(entity_row, "name_en", None) or "").strip().lower(),
            ):
                if token:
                    requested_name_tokens.add(token)
            if not requested_subject_type:
                requested_subject_type = _normalize_entity_type(getattr(entity_row, "type", None))
            if not current_episode_id:
                current_episode_id = _asset_optional_int(getattr(entity_row, "episode_id", None))
        else:
            # Soft-deleted / missing entity cannot drive cross-episode reuse.
            if not requested_name_tokens:
                return None

    if not requested_name_tokens:
        return None
    # Cross-episode reuse requires knowing the current episode so we can compare episode numbers.
    if not current_episode_id:
        return None

    current_episode_row = (
        db.query(Episode)
        .filter(
            Episode.id == int(current_episode_id),
            Episode.project_id == int(project_id),
            _active_episode_clause(),
        )
        .first()
    )
    if not current_episode_row:
        return None
    current_episode_number = _resolve_episode_sort_number(current_episode_row)
    if not current_episode_number:
        return None

    # Eligible source episodes: active, same project, episode number < current.
    prior_episode_rows = (
        db.query(Episode)
        .filter(
            Episode.project_id == int(project_id),
            _active_episode_clause(),
            Episode.id != int(current_episode_id),
        )
        .all()
    )
    prior_episode_number_map: Dict[int, int] = {}
    for ep_row in prior_episode_rows or []:
        ep_id = _asset_optional_int(getattr(ep_row, "id", None))
        if not ep_id:
            continue
        ep_number = _resolve_episode_sort_number(ep_row)
        if not ep_number or int(ep_number) >= int(current_episode_number):
            continue
        prior_episode_number_map[int(ep_id)] = int(ep_number)
    if not prior_episode_number_map:
        return None

    candidates = (
        db.query(Asset)
        .filter(
            Asset.user_id == user_id,
            Asset.type == "image",
            Asset.project_id == project_id,
            _active_asset_clause(),
        )
        .order_by(Asset.id.desc())
        .limit(5000)
        .all()
    )
    if not candidates:
        return None

    matched: List[Asset] = []
    matched_entity_ids: Set[int] = set()
    for candidate in candidates:
        _sync_asset_denormalized_fields(candidate)
        candidate_meta = _asset_meta_dict(getattr(candidate, "meta_info", None))
        if _asset_optional_int(candidate.project_id or candidate_meta.get("project_id")) != project_id:
            continue

        candidate_episode_id = _asset_optional_int(
            getattr(candidate, "episode_id", None) or candidate_meta.get("episode_id")
        )
        # Must belong to a prior non-deleted episode with a smaller episode number.
        if not candidate_episode_id or int(candidate_episode_id) not in prior_episode_number_map:
            continue

        candidate_subject_type = _normalize_entity_type(
            candidate_meta.get("subject_type") or candidate_meta.get("entity_type")
        )
        # Keep type-consistent dependency reuse except for poster assets.
        if (
            requested_subject_type
            and requested_subject_type != "poster"
            and candidate_subject_type
            and candidate_subject_type != requested_subject_type
        ):
            continue

        candidate_subject_name = str(candidate_meta.get("subject_name") or "").strip().lower()
        candidate_entity_name = str(candidate_meta.get("entity_name") or "").strip().lower()
        candidate_name_tokens = {
            token for token in (candidate_subject_name, candidate_entity_name) if token
        }
        # Same name only — do not reuse by entity_id alone (that hits same-card regenerations).
        if not candidate_name_tokens or not requested_name_tokens.intersection(candidate_name_tokens):
            continue

        matched.append(candidate)
        candidate_entity_id = _asset_optional_int(candidate_meta.get("entity_id"))
        if candidate_entity_id:
            matched_entity_ids.add(int(candidate_entity_id))

    if not matched:
        return None

    active_entity_ids: Set[int] = set()
    if matched_entity_ids:
        active_entity_ids = {
            int(row_id)
            for (row_id,) in db.query(Entity.id)
            .filter(Entity.id.in_(matched_entity_ids), _active_entity_clause())
            .all()
        }

    filtered_matched: List[Asset] = []
    for row in matched:
        row_meta = _asset_meta_dict(getattr(row, "meta_info", None))
        episode_id = _asset_optional_int(getattr(row, "episode_id", None) or row_meta.get("episode_id"))
        if not episode_id or int(episode_id) not in prior_episode_number_map:
            continue
        entity_id = _asset_optional_int(row_meta.get("entity_id"))
        if entity_id and int(entity_id) not in active_entity_ids:
            continue
        filtered_matched.append(row)

    if not filtered_matched:
        return None

    episode_title_map: Dict[int, str] = {
        int(row_id): str(row_title or "")
        for row_id, row_title in db.query(Episode.id, Episode.title)
        .filter(Episode.id.in_(list(prior_episode_number_map.keys())))
        .all()
    }

    def _candidate_rank(asset: Asset) -> Tuple[int, int, str, int]:
        candidate_meta = _asset_meta_dict(getattr(asset, "meta_info", None))
        episode_id = _asset_optional_int(getattr(asset, "episode_id", None) or candidate_meta.get("episode_id"))
        # Prefer the nearest prior episode (largest episode number still < current).
        episode_rank = int(prior_episode_number_map.get(int(episode_id or 0), 0) or 0)
        is_current = 1 if bool(getattr(asset, "is_current_project_asset", False)) else 0
        created_at = str(getattr(asset, "created_at", "") or "")
        return (episode_rank, is_current, created_at, int(getattr(asset, "id", 0) or 0))

    chosen = max(filtered_matched, key=_candidate_rank)
    chosen_url = str(getattr(chosen, "url", "") or "").strip()
    if not chosen_url:
        return None

    chosen_meta = _asset_meta_dict(getattr(chosen, "meta_info", None))
    chosen_episode_id = _asset_optional_int(
        getattr(chosen, "episode_id", None) or chosen_meta.get("episode_id")
    )
    chosen_entity_id = _asset_optional_int(chosen_meta.get("entity_id"))
    chosen_entity_name = str(
        chosen_meta.get("entity_name")
        or chosen_meta.get("subject_name")
        or ""
    ).strip()
    chosen_subject_type = _normalize_entity_type(
        chosen_meta.get("subject_type") or chosen_meta.get("entity_type")
    )
    # Prefer script_title (分集名) over bare Episode.title ("Episode 1").
    chosen_episode_title = str(episode_title_map.get(int(chosen_episode_id or 0), "") or "").strip()
    if chosen_episode_id:
        try:
            ep_row = (
                db.query(Episode)
                .filter(Episode.id == int(chosen_episode_id), _active_episode_clause())
                .first()
            )
            ep_info = getattr(ep_row, "episode_info", None) if ep_row else None
            if isinstance(ep_info, dict):
                script_title = str(
                    ep_info.get("script_title")
                    or ep_info.get("episode_title")
                    or ep_info.get("episode_name")
                    or ""
                ).strip()
                if script_title:
                    chosen_episode_title = script_title
                elif not chosen_episode_title:
                    chosen_episode_title = str(getattr(ep_row, "title", "") or "").strip()
        except Exception:
            pass
    return {
        "url": chosen_url,
        "asset_id": int(getattr(chosen, "id", 0) or 0) or None,
        "episode_id": int(chosen_episode_id) if chosen_episode_id else None,
        "episode_title": chosen_episode_title or None,
        "entity_id": int(chosen_entity_id) if chosen_entity_id else None,
        "entity_name": chosen_entity_name or None,
        "subject_type": chosen_subject_type or None,
    }

def _register_asset_helper(db: Session, user_id: int, url: str, req: Any, source_metadata: Dict = None):
    # Handle dict or object
    def get_attr(obj, key):
        if isinstance(obj, dict): return obj.get(key)
        return getattr(obj, key, None)

    project_id = _asset_optional_int(get_attr(req, "project_id"))
    episode_id_hint = _asset_optional_int(get_attr(req, "episode_id"))
    shot_id_hint = _asset_optional_int(get_attr(req, "shot_id"))

    if not project_id and shot_id_hint:
        try:
            shot_row = db.query(Shot).filter(Shot.id == int(shot_id_hint)).first()
            if shot_row:
                project_id = _asset_optional_int(getattr(shot_row, "project_id", None))
                if not episode_id_hint:
                    episode_id_hint = _asset_optional_int(getattr(shot_row, "episode_id", None))
                if not episode_id_hint and getattr(shot_row, "scene_id", None):
                    scene_row = db.query(Scene).filter(Scene.id == int(shot_row.scene_id)).first()
                    if scene_row:
                        episode_id_hint = _asset_optional_int(getattr(scene_row, "episode_id", None))
        except Exception:
            pass

    if not project_id and episode_id_hint:
        try:
            episode_row = db.query(Episode).filter(Episode.id == int(episode_id_hint)).first()
            if episode_row:
                project_id = _asset_optional_int(getattr(episode_row, "project_id", None))
        except Exception:
            pass

    if not project_id:
        return

    try:
        # Determine paths
        import urllib.parse
        parsed_url_path = urllib.parse.urlparse(url).path
        if parsed_url_path.startswith('/uploads/'):
            rel_path = parsed_url_path[len('/uploads/'):]
            file_path = os.path.join(settings.UPLOAD_DIR, rel_path)
            fname = os.path.basename(parsed_url_path)
        else:
            fname = os.path.basename(parsed_url_path)
            file_path = os.path.join(settings.UPLOAD_DIR, fname)
            
        lower_path = parsed_url_path.lower()
        is_image = lower_path.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"))
        is_video = lower_path.endswith((".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"))
        is_audio = lower_path.endswith((".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"))

        meta = {}
        # Copy known fields
        for field in ["shot_number", "shot_id", "project_id", "episode_id", "asset_type", "entity_id", "entity_name", "subject_name", "subject_type", "entity_type", "source_asset_url", "idempotency_key"]:
            val = get_attr(req, field)
            if val: meta[field] = val

        if not meta.get("project_id") and project_id:
            meta["project_id"] = int(project_id)
        if not meta.get("episode_id") and episode_id_hint:
            meta["episode_id"] = int(episode_id_hint)

        # Map reference URLs to source_asset_url for asset dependency tracking
        if not meta.get("source_asset_url"):
            for ref_field in ["ref_image_url", "ref_video_urls", "last_frame_url", "base_image", "seed_image"]:
                ref_val = get_attr(req, ref_field)
                if ref_val:
                    actual_url = ref_val[0] if isinstance(ref_val, list) and len(ref_val) > 0 else ref_val
                    if isinstance(actual_url, str) and actual_url.startswith("http"):
                        meta["source_asset_url"] = actual_url
                        break

        if get_attr(req, "asset_type"): meta["frame_type"] = get_attr(req, "asset_type")
        if get_attr(req, "category"): meta["category"] = get_attr(req, "category")

        # Merge Source Metadata (Provider, Model, Dimensions, etc.)
        if source_metadata:
            for k in ["provider", "model", "duration", "width", "height", "aspect_ratio", "submit_aspect_ratio", "prompt", "seed", "idempotency_key"]:
                if k in source_metadata:
                    meta[k] = source_metadata[k]
            provider_usage = _extract_provider_usage_from_metadata(source_metadata)
            if provider_usage:
                meta["usage"] = provider_usage
                meta["provider_usage"] = provider_usage
                usage_source = str(source_metadata.get("usage_source") or "").strip()
                if usage_source:
                    meta["usage_source"] = usage_source

        provider_alias_map = _build_provider_alias_lookup(db)
        meta = _attach_provider_alias_to_dict(meta, provider_alias_map)
        ensure_resolution_fields(meta)

        is_subject_generation = str(get_attr(req, "asset_type") or "").strip().lower() == "subject"
        if is_subject_generation:
            resolved_type = _normalize_entity_type(
                get_attr(req, "subject_type")
                or get_attr(req, "entity_type")
                or get_attr(req, "category")
                or meta.get("subject_type")
                or meta.get("entity_type")
            )

            entity_id_val = get_attr(req, "entity_id")
            if not resolved_type and entity_id_val:
                try:
                    e = db.query(Entity).filter(Entity.id == int(entity_id_val)).first()
                    if e:
                        resolved_type = _normalize_entity_type(e.type)
                except Exception:
                    pass

            if not resolved_type and project_id:
                subject_label = str(get_attr(req, "entity_name") or get_attr(req, "subject_name") or "").strip()
                if subject_label:
                    e = db.query(Entity).filter(
                        Entity.project_id == int(project_id),
                        or_(Entity.name == subject_label, Entity.name_en == subject_label)
                    ).first()
                    if e:
                        resolved_type = _normalize_entity_type(e.type)
                        if not meta.get("entity_id"):
                            meta["entity_id"] = e.id

            if resolved_type:
                meta["subject_type"] = resolved_type
                meta["entity_type"] = resolved_type
                if resolved_type == "character":
                    meta["subject_type_cn"] = "角色"
                elif resolved_type == "environment":
                    meta["subject_type_cn"] = "环境"
                elif resolved_type == "prop":
                    meta["subject_type_cn"] = "道具"

        if is_subject_generation and not meta.get("source_asset_url"):
            inferred_source = _resolve_subject_dependency_source_asset_url(db, user_id, meta)
            inferred_source_url = str((inferred_source or {}).get("url") or "").strip()
            if inferred_source_url and inferred_source_url != str(url or "").strip():
                meta["source_asset_url"] = inferred_source_url
                meta["source_asset_auto"] = "same_name_other_episode_active"
                if inferred_source.get("asset_id"):
                    meta["source_asset_id"] = inferred_source["asset_id"]
                if inferred_source.get("episode_id"):
                    meta["source_asset_episode_id"] = inferred_source["episode_id"]
                if inferred_source.get("episode_title"):
                    meta["source_asset_episode_title"] = inferred_source["episode_title"]
                if inferred_source.get("entity_id"):
                    meta["source_asset_entity_id"] = inferred_source["entity_id"]
                if inferred_source.get("entity_name"):
                    meta["source_asset_entity_name"] = inferred_source["entity_name"]
                if inferred_source.get("subject_type"):
                    meta["source_asset_subject_type"] = inferred_source["subject_type"]

        media_kind = "image" if is_image else ("video" if is_video else ("audio" if is_audio else None))
        meta = enrich_asset_meta_info(
            meta,
            url=url,
            media_kind=media_kind,
            local_path=file_path if os.path.isfile(file_path) else None,
        )

        remark = get_attr(req, "remark")
        if not remark:
            provider = meta.get("provider", "Unknown")
            if get_attr(req, "entity_name"):
                 remark = f"Auto-registered from Entity: {get_attr(req, 'entity_name')} ({provider})"
            else:
                 remark = f"Generated {get_attr(req, 'asset_type')} for Shot {get_attr(req, 'shot_number')} by {provider}"

        with ASSET_REGISTRATION_LOCK:
            existing_asset = _find_existing_asset_for_registration(
                db,
                user_id,
                url=url,
                idempotency_key=meta.get("idempotency_key"),
                meta_info=meta,
            )
            if existing_asset:
                normalized_existing_url = _normalize_asset_url_for_dedup(getattr(existing_asset, "url", None))
                if normalized_existing_url and str(getattr(existing_asset, "url_normalized", "") or "").strip() != normalized_existing_url:
                    existing_asset.url_normalized = normalized_existing_url
                enriched_meta = enrich_asset_meta_info(
                    _asset_meta_dict(existing_asset.meta_info),
                    url=str(existing_asset.url or url or ""),
                    media_kind=str(existing_asset.type or media_kind or ""),
                )
                if enriched_meta != _asset_meta_dict(existing_asset.meta_info):
                    existing_asset.meta_info = enriched_meta
                _sync_asset_denormalized_fields(existing_asset)
                if existing_asset.project_id:
                    from app.api.routers.assets_pkg.shared import _mark_asset_as_current_project_asset

                    _mark_asset_as_current_project_asset(db, existing_asset)
                    db.commit()
                return existing_asset

            is_image_inferred = is_image
            is_video_inferred = is_video
            is_audio_inferred = is_audio
            if not is_image and not is_video and not is_audio:
                # Fallback based on metadata provider/model if possible
                provider_str = str(meta.get("provider", "")).lower()
                model_str = str(meta.get("model", "")).lower()
                if "video" in model_str or "video" in provider_str or any(k in provider_str for k in ("luma", "runway", "kling", "minimax")):
                    is_video_inferred = True
                elif "audio" in model_str or "tts" in model_str or "voice" in model_str:
                    is_audio_inferred = True
                else:
                    # Default to image if the extension and metadata are unknown
                    is_image_inferred = True

            asset = Asset(
                user_id=user_id,
                type=("image" if is_image_inferred else ("audio" if is_audio_inferred else "video")),
                url=url,
                url_normalized=_normalize_asset_url_for_dedup(url),
                filename=fname,
                project_id=_asset_optional_int(meta.get("project_id")),
                episode_id=_asset_optional_int(meta.get("episode_id")),
                meta_info=meta,
                remark=remark
            )
            try:
                with db.begin_nested():
                    db.add(asset)
                    db.flush()
            except IntegrityError:
                # Concurrent / signed-URL duplicate of uq_assets_user_type_scope_url_norm.
                existing_after_conflict = _find_existing_asset_for_registration(
                    db,
                    user_id,
                    url=url,
                    idempotency_key=meta.get("idempotency_key"),
                    meta_info=meta,
                )
                if existing_after_conflict:
                    return existing_after_conflict
                raise
            from app.api.routers.assets_pkg.shared import _mark_asset_as_current_project_asset

            _mark_asset_as_current_project_asset(db, asset)
            db.commit()
            return asset
    except Exception as e:
        logger.warning("[AssetRegister] failed | user_id=%s url=%s err=%s", user_id, str(url or "")[:180], e)
        return None


def _extract_provider_model_from_result(result: Any, req: Any) -> Tuple[Optional[str], Optional[str]]:
    provider = None
    model = None
    if isinstance(result, dict):
        meta = result.get("metadata")
        if isinstance(meta, dict):
            provider = str(meta.get("provider") or "").strip() or None
            model = str(meta.get("model") or "").strip() or None

    if not provider:
        provider = str(getattr(req, "provider", None) or "").strip() or None
    if not model:
        model = str(getattr(req, "model", None) or "").strip() or None
    return provider, model


from app.services.model_invocation_billing import (  # noqa: E402,F401
    _apply_llm_routing_to_billing_details,
    _attach_llm_provider_usage_to_billing_details,
    _build_standard_billing_details,
    _cancel_reservation_quietly,
    _extract_llm_routing_metadata,
    _extract_provider_usage_from_metadata,
    _finalize_model_invocation_billing,
    _maybe_refresh_kie_credits_from_record_info,
    _reservation_tx_id,
    _resolve_usage_token_total,
    _safe_int_token,
)



def _resolve_latest_asset_provider_model(
    db: Session,
    user_id: int,
    shot_id: Optional[int],
    media_type: str,
    asset_type: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    if not shot_id:
        return None, None

    normalized_media_type = str(media_type or "").strip().lower()
    if normalized_media_type not in {"image", "video"}:
        return None, None

    normalized_asset_type = str(asset_type or "").strip().lower() or None

    candidates = (
        db.query(Asset)
        .filter(Asset.user_id == user_id, Asset.type == normalized_media_type)
        .order_by(Asset.id.desc())
        .limit(300)
        .all()
    )

    shot_id_str = str(shot_id)
    for asset in candidates:
        meta = asset.meta_info if isinstance(asset.meta_info, dict) else {}
        if str(meta.get("shot_id") or "").strip() != shot_id_str:
            continue

        previous_asset_type = str(meta.get("asset_type") or meta.get("frame_type") or "").strip().lower() or None
        if normalized_asset_type and previous_asset_type and previous_asset_type != normalized_asset_type:
            continue

        prev_provider = str(meta.get("provider") or "").strip() or None
        prev_model = str(meta.get("model") or "").strip() or None
        return prev_provider, prev_model

    return None, None


def _log_api_switch_regenerate_if_needed(
    db: Session,
    current_user: User,
    req: Any,
    result: Any,
    media_type: str,
) -> None:
    try:
        shot_id_raw = getattr(req, "shot_id", None)
        shot_id = int(shot_id_raw) if shot_id_raw else None
    except Exception:
        return

    if not shot_id:
        return

    current_provider, current_model = _extract_provider_model_from_result(result, req)
    if not current_provider and not current_model:
        return

    req_asset_type = str(getattr(req, "asset_type", None) or "").strip().lower() or None
    prev_provider, prev_model = _resolve_latest_asset_provider_model(
        db=db,
        user_id=current_user.id,
        shot_id=shot_id,
        media_type=media_type,
        asset_type=req_asset_type,
    )

    if not prev_provider and not prev_model:
        return

    if (prev_provider or "") == (current_provider or "") and (prev_model or "") == (current_model or ""):
        return

    action = "SHOT_REGENERATE_IMAGE_API_SWITCH" if str(media_type).lower() == "image" else "SHOT_REGENERATE_VIDEO_API_SWITCH"
    detail_parts = [
        f"shot_id={shot_id}",
        f"asset_type={req_asset_type or 'unknown'}",
        f"from_provider={prev_provider or 'unknown'}",
        f"from_model={prev_model or 'unknown'}",
        f"to_provider={current_provider or 'unknown'}",
        f"to_model={current_model or 'unknown'}",
    ]
    project_id = getattr(req, "project_id", None)
    if project_id is not None:
        detail_parts.append(f"project_id={project_id}")

    log_action(
        db,
        user_id=current_user.id,
        user_name=current_user.username,
        action=action,
        details="; ".join(detail_parts),
    )


def _bind_generated_media_to_shot(
    db: Session,
    current_user: User,
    req: Any,
    media_url: Optional[str],
    oss_uploaded_success: Optional[bool] = None,
    media_metadata: Optional[Dict[str, Any]] = None,
) -> None:
    if not media_url:
        return

    def get_attr(obj, key):
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    shot_id = get_attr(req, "shot_id")
    if not shot_id:
        logger.warning("[ShotMediaBind] skipped; shot_id missing | media_url=%s", str(media_url or "")[:240])
        return

    try:
        shot_id_int = int(shot_id)
    except Exception:
        logger.warning("[ShotMediaBind] skipped; invalid shot_id=%s", shot_id)
        return

    shot = db.query(Shot).filter(Shot.id == shot_id_int).first()
    if not shot:
        logger.warning("[ShotMediaBind] skipped; shot not found | shot_id=%s", shot_id_int)
        return

    try:
        project_id = shot.project_id
        if not project_id and shot.scene_id:
            scene = db.query(Scene).filter(Scene.id == shot.scene_id).first()
            if scene and scene.episode_id:
                episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
                if episode:
                    project_id = episode.project_id
        if project_id:
            _require_project_access(db, int(project_id), current_user)
    except Exception as access_err:
        logger.warning(
            "[ShotMediaBind] skipped; project access failed | shot_id=%s user_id=%s err=%s",
            shot_id_int,
            getattr(current_user, "id", None),
            access_err,
        )
        return

    from app.services.generation_runtime.media_persist import (
        _enrich_media_metadata_from_generation_context,
        _ensure_media_bound_at,
    )

    asset_type = str(get_attr(req, "asset_type") or "").strip().lower()
    # Video jobs sometimes omit asset_type; infer from URL so bind is not a silent no-op.
    if not asset_type:
        media_lower = str(media_url or "").split("?", 1)[0].lower()
        if media_lower.endswith((".mp4", ".webm", ".mov", ".m4v", ".mkv")):
            asset_type = "video"
        else:
            logger.warning(
                "[ShotMediaBind] skipped; asset_type missing and url not video-like | shot_id=%s media_url=%s",
                shot_id_int,
                str(media_url or "")[:240],
            )
            return
    changed = False

    normalized_media_metadata: Optional[Dict[str, Any]] = None
    if isinstance(media_metadata, dict):
        try:
            normalized_media_metadata = json.loads(json.dumps(media_metadata, ensure_ascii=False, default=str))
        except Exception:
            normalized_media_metadata = dict(media_metadata)

    bind_context: Dict[str, Any] = {}
    for bind_key in (
        "provider", "model", "prompt", "negative_prompt", "aspect_ratio", "duration", "seed",
        "width", "height", "resolution", "image_size", "system_api_id", "shot_id", "project_id",
        "episode_id", "scene_id", "shot_number", "shot_name", "asset_type", "job_id", "idempotency_key",
    ):
        bind_value = get_attr(req, bind_key)
        if bind_value not in (None, ""):
            bind_context[bind_key] = bind_value
    bind_context.setdefault("asset_type", asset_type)
    if isinstance(normalized_media_metadata, dict):
        normalized_media_metadata = _enrich_media_metadata_from_generation_context(
            normalized_media_metadata,
            bind_context,
        )

    tech = {}
    try:
        tech = json.loads(shot.technical_notes or "{}")
        if not isinstance(tech, dict):
            tech = {}
    except Exception:
        tech = {}

    if asset_type in {"start_frame", "start"}:
        metadata_changed = False
        start_url_changed = shot.image_url != media_url
        if isinstance(normalized_media_metadata, dict):
            previous_meta = tech.get("start_frame_metadata")
            if not isinstance(previous_meta, dict) or previous_meta != normalized_media_metadata:
                tech["start_frame_metadata"] = normalized_media_metadata
                metadata_changed = True
        if start_url_changed:
            start_meta = tech.get("start_frame_metadata") if isinstance(tech.get("start_frame_metadata"), dict) else {}
            tech["start_frame_metadata"] = _ensure_media_bound_at(start_meta, refresh=True)
            metadata_changed = True
        if (
            shot.image_url != media_url
            or (oss_uploaded_success is not None and tech.get("start_frame_oss_uploaded") != oss_uploaded_success)
            or metadata_changed
        ):
            shot.image_url = media_url
            if oss_uploaded_success is not None:
                tech["start_frame_oss_uploaded"] = oss_uploaded_success
            shot.technical_notes = json.dumps(tech, ensure_ascii=False)
            changed = True

    elif asset_type in {"end_frame", "end"}:
        metadata_changed = False
        end_url_changed = tech.get("end_frame_url") != media_url
        if isinstance(normalized_media_metadata, dict):
            previous_meta = tech.get("end_frame_metadata")
            if not isinstance(previous_meta, dict) or previous_meta != normalized_media_metadata:
                tech["end_frame_metadata"] = normalized_media_metadata
                metadata_changed = True
        if end_url_changed:
            end_meta = tech.get("end_frame_metadata") if isinstance(tech.get("end_frame_metadata"), dict) else {}
            tech["end_frame_metadata"] = _ensure_media_bound_at(end_meta, refresh=True)
            metadata_changed = True
        if (
            tech.get("end_frame_url") != media_url
            or (oss_uploaded_success is not None and tech.get("end_frame_oss_uploaded") != oss_uploaded_success)
            or metadata_changed
        ):
            tech["end_frame_url"] = media_url
            if oss_uploaded_success is not None:
                tech["end_frame_oss_uploaded"] = oss_uploaded_success
            shot.technical_notes = json.dumps(tech, ensure_ascii=False)
            changed = True

    elif asset_type == "video":
        metadata_changed = False
        video_url_changed = shot.video_url != media_url
        if isinstance(normalized_media_metadata, dict):
            previous_meta = tech.get("video_metadata")
            if not isinstance(previous_meta, dict) or previous_meta != normalized_media_metadata:
                tech["video_metadata"] = normalized_media_metadata
                metadata_changed = True
        if video_url_changed:
            video_meta = dict(normalized_media_metadata) if isinstance(normalized_media_metadata, dict) else (
                tech.get("video_metadata") if isinstance(tech.get("video_metadata"), dict) else {}
            )
            video_meta = _ensure_media_bound_at(video_meta, refresh=True)
            video_meta = _enrich_media_metadata_from_generation_context(video_meta, bind_context)
            tech["video_metadata"] = video_meta
            metadata_changed = True
        if (
            shot.video_url != media_url
            or (oss_uploaded_success is not None and tech.get("video_oss_uploaded") != oss_uploaded_success)
            or metadata_changed
        ):
            shot.video_url = media_url
            if oss_uploaded_success is not None:
                tech["video_oss_uploaded"] = oss_uploaded_success
            shot.technical_notes = json.dumps(tech, ensure_ascii=False)
            changed = True

    if not changed:
        return

    db.add(shot)
    db.commit()
    logger.info(
        "[ShotMediaBind] shot_id=%s asset_type=%s media_url=%s project_id=%s user_id=%s",
        shot_id_int,
        asset_type or None,
        media_url,
        getattr(shot, "project_id", None),
        getattr(current_user, "id", None),
    )


def _bind_generated_media_to_entity(db: Session, current_user: User, req: Any, media_url: Optional[str], oss_uploaded_success: Optional[bool] = None) -> None:
    if not media_url:
        return

    def get_attr(obj, key):
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    asset_type = str(get_attr(req, "asset_type") or "").strip().lower()
    if asset_type != "subject":
        logger.info(
            "[SubjectMediaBind] skipped non-subject asset_type=%s media_url=%s user_id=%s",
            asset_type or None,
            media_url,
            getattr(current_user, "id", None),
        )
        return

    entity = None
    project = None
    entity_id_raw = get_attr(req, "entity_id")
    if entity_id_raw is not None:
        try:
            entity = db.query(Entity).filter(Entity.id == int(entity_id_raw)).first()
        except Exception:
            entity = None

    if not entity:
        subject_label = str(get_attr(req, "entity_name") or get_attr(req, "subject_name") or "").strip()
        project_id_raw = get_attr(req, "project_id")
        try:
            project_id = int(project_id_raw) if project_id_raw is not None else None
        except Exception:
            project_id = None
        if subject_label and project_id:
            entity = db.query(Entity).filter(
                Entity.project_id == project_id,
                or_(Entity.name == subject_label, Entity.name_en == subject_label),
            ).order_by(Entity.id.desc()).first()

    if not entity:
        logger.warning(
            "[SubjectMediaBind] entity_not_found entity_id=%s entity_name=%s subject_name=%s project_id=%s media_url=%s user_id=%s",
            entity_id_raw,
            get_attr(req, "entity_name"),
            get_attr(req, "subject_name"),
            get_attr(req, "project_id"),
            media_url,
            getattr(current_user, "id", None),
        )
        return

    try:
        from app.api.routers.workspace.shared import _require_project_access

        project = _require_project_access(db, int(entity.project_id), current_user)
    except Exception:
        return

    from app.services.generation_runtime.media_persist import (
        _is_ephemeral_provider_media_url,
        _resolve_precise_asset_library_url,
    )

    stable_media_url = str(media_url or "").strip()
    if _is_ephemeral_provider_media_url(stable_media_url):
        stable_media_url = _resolve_precise_asset_library_url(
            db,
            current_user,
            stable_media_url,
            project=project,
            entity_id=getattr(entity, "id", None),
            asset_type_aliases={"subject", "character", "char"},
            media_type="image",
        ) or ""
        if not stable_media_url:
            logger.warning(
                "[SubjectMediaBind] skipped temporary media url | entity_id=%s name=%s project_id=%s media_url=%s user_id=%s",
                getattr(entity, "id", None),
                getattr(entity, "name", None) or getattr(entity, "name_en", None),
                getattr(entity, "project_id", None),
                media_url,
                getattr(current_user, "id", None),
            )
            return

    tech_attrs = {}
    try:
        tech_attrs = json.loads(entity.custom_attributes or "{}")
        if not isinstance(tech_attrs, dict): tech_attrs = {}
    except Exception:
        pass

    if str(entity.image_url or "").strip() == stable_media_url and (oss_uploaded_success is None or tech_attrs.get("oss_uploaded_success") == oss_uploaded_success):
        logger.info(
            "[SubjectMediaBind] unchanged | entity_id=%s name=%s project_id=%s media_url=%s user_id=%s",
            getattr(entity, "id", None),
            getattr(entity, "name", None) or getattr(entity, "name_en", None),
            getattr(entity, "project_id", None),
            stable_media_url,
            getattr(current_user, "id", None),
        )
        return

    logger.info(
        "[SubjectMediaBind] update_begin | entity_id=%s name=%s project_id=%s previous_url=%s next_url=%s user_id=%s",
        getattr(entity, "id", None),
        getattr(entity, "name", None) or getattr(entity, "name_en", None),
        getattr(entity, "project_id", None),
        getattr(entity, "image_url", None),
        stable_media_url,
        getattr(current_user, "id", None),
    )
    if oss_uploaded_success is not None:
        tech_attrs["oss_uploaded_success"] = oss_uploaded_success
        entity.custom_attributes = json.dumps(tech_attrs, ensure_ascii=False)
        
    if oss_uploaded_success is not None:
        tech_attrs["oss_uploaded_success"] = oss_uploaded_success
        entity.custom_attributes = json.dumps(tech_attrs, ensure_ascii=False)
        
    entity.image_url = stable_media_url
    db.add(entity)
    db.commit()
    logger.info(
        "[SubjectMediaBind] entity_id=%s name=%s project_id=%s media_url=%s user_id=%s",
        getattr(entity, "id", None),
        getattr(entity, "name", None) or getattr(entity, "name_en", None),
        getattr(entity, "project_id", None),
        stable_media_url,
        getattr(current_user, "id", None),
    )
