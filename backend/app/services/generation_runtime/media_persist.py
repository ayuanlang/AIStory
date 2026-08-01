# -*- coding: utf-8 -*-
"""Remote/local media persistence for generation jobs and shot/entity bind."""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import tempfile
import time
import urllib.parse
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

import requests
from fastapi import HTTPException
from PIL import Image
from pydantic import BaseModel
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time_utils import now_bj_iso
from app.db.session import SessionLocal
from app.models import all_models as models
from app.models.all_models import Asset, Entity, Project, Shot, User
from app.services.asset_meta_probe import enrich_asset_meta_info, ensure_resolution_fields, probe_media_from_path
from app.services.generation_runtime.generation_filename import (
    _build_persist_filename_base_from_context,
)
from app.services.generation_runtime.job_store import (
    ASSET_REGISTRATION_LOCK,
    VIDEO_JOB_LOCK,
    VIDEO_JOB_STORE,
    _extract_job_result_url,
    _read_video_job_file,
    _set_video_job,
)
from app.services.media_service import media_service
from app.services.oss_storage_service import oss_storage_service
from app.services.generation_runtime.asset_registration import (  # noqa: F401
    _bind_generated_media_to_entity,
    _bind_generated_media_to_shot,
    _register_asset_helper,
)
from app.services.asset_meta_utils import _asset_optional_int  # noqa: F401

logger = logging.getLogger("api_logger")

__all__ = [
    "EntityPersistMediaRequest",
    "ShotPersistMediaRequest",
    "ShotVideoCleanupRequest",
    "_EPHEMERAL_PROVIDER_MEDIA_HOST_PATTERNS",
    "_EPHEMERAL_PROVIDER_MEDIA_QUERY_MARKERS",
    "_KIE_GENERATED_MEDIA_HOST_PATTERNS",
    "_assert_allowed_persisted_media_url",
    "_assert_allowed_shot_media_payload",
    "_asset_meta_to_dict",
    "_attach_oss_metadata_from_managed_url",
    "_build_ephemeral_media_metadata",
    "_build_generation_job_req_context",
    "_build_shot_video_zip_entry_name",
    "_cleanup_temp_download_file",
    "_clear_ephemeral_persist_flags",
    "_diagnose_entity_image_url",
    "_enrich_media_metadata_from_generation_context",
    "_ensure_media_bound_at",
    "_extract_media_filename_from_url",
    "_hydrate_video_job_record",
    "_is_durable_persisted_media_url",
    "_is_ephemeral_provider_media_url",
    "_is_persisted_media_localization_success",
    "_is_provider_direct_oss_url",
    "_job_has_durable_result_url",
    "_looks_like_kie_generated_media_url",
    "_media_result_needs_persistence_retry",
    "_normalize_ephemeral_shot_media_update",
    "_oss_upload_succeeded_for_url",
    "_parse_generation_task_payload",
    "_persist_data_uri_image_result",
    "_persist_entity_image",
    "_persist_remote_image_result",
    "_persist_remote_media_result",
    "_persist_remote_video_result",
    "_persist_shot_media_slot",
    "_refresh_managed_media_url",
    "_refresh_shot_media_urls",
    "_repair_entities_image_urls_from_assets",
    "_repair_entity_image_url_from_assets",
    "_repair_shot_media_urls_from_assets",
    "_repair_shots_media_urls_from_assets",
    "_repair_stale_ephemeral_shot_media_notes",
    "_replace_legacy_temp_urls_in_shot_payload",
    "_resolve_job_owner_user",
    "_resolve_kie_download_api_key",
    "_resolve_kie_downloadable_url",
    "_resolve_local_upload_path_from_media_url",
    "_resolve_media_bind_url",
    "_resolve_media_persistence_source_url",
    "_resolve_precise_asset_library_url",
    "_resolve_shot_media_slot_url",
    "_resolve_video_bind_url",
    "_resolve_video_persistence_source_url",
    "_sanitize_zip_entry_token",
    "_stage_ephemeral_media_job_result",
    "_url_matches_configured_oss",
    "_video_result_needs_persistence_retry",
    "_visible_asset_owner_ids_for_project"
]


# Common aliases used by moved code
ProjectShare = getattr(models, "ProjectShare", None)
Episode = getattr(models, "Episode", None)
Scene = getattr(models, "Scene", None)


def _persist_data_uri_image_result(
    current_user: User,
    media_url: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    raw = str(media_url or "").strip()
    if not raw.startswith("data:image/"):
        return media_url, metadata

    marker = ";base64,"
    marker_idx = raw.find(marker)
    if marker_idx <= 5:
        raise ValueError("invalid image data URI: missing base64 marker")

    mime = raw[5:marker_idx].strip().lower()
    b64_part = raw[marker_idx + len(marker):].strip()
    if not b64_part:
        raise ValueError("invalid image data URI: empty payload")

    extension_map = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/bmp": ".bmp",
    }
    file_ext = extension_map.get(mime)
    if not file_ext:
        subtype = mime.split("/", 1)[1] if "/" in mime else "png"
        subtype = re.sub(r"[^a-z0-9]+", "", subtype.lower()) or "png"
        file_ext = f".{subtype}"

    binary = base64.b64decode(b64_part)
    filename = f"provider_result_{uuid.uuid4().hex[:16]}{file_ext}"

    updated_metadata = dict(metadata) if isinstance(metadata, dict) else {}
    updated_metadata["stored_from_data_uri"] = True
    updated_metadata["stored_from_data_uri_mime"] = mime
    updated_metadata["stored_from_data_uri_bytes"] = len(binary)

    uploaded = oss_storage_service.upload_bytes(
        binary,
        user_id=int(getattr(current_user, "id", 0) or 0),
        filename=filename,
        content_type=mime,
        category="generated",
        cache_control="public, max-age=31536000",
    )
    if uploaded and uploaded.get("url"):
        updated_metadata["oss"] = {
            "provider": uploaded.get("provider"),
            "bucket": uploaded.get("bucket"),
            "key": uploaded.get("key"),
            "endpoint": uploaded.get("endpoint"),
        }
        try:
            with Image.open(io.BytesIO(binary)) as img:
                updated_metadata["width"] = int(img.width)
                updated_metadata["height"] = int(img.height)
                if img.format:
                    updated_metadata["format"] = str(img.format)
        except Exception as exc:
            logger.warning("data-uri image metadata probe failed in-memory err=%s", exc)
        logger.info(
            "[ImageResultNormalize] stored provider data URI in OSS | user_id=%s bytes=%s mime=%s url=%s",
            getattr(current_user, "id", None),
            len(binary),
            mime,
            uploaded["url"],
        )
        return str(uploaded["url"]), updated_metadata

    upload_root = settings.UPLOAD_DIR
    if not os.path.isabs(upload_root):
        upload_root = os.path.abspath(upload_root)

    user_dir = os.path.join(upload_root, str(getattr(current_user, "id", "unknown")), "generated")
    os.makedirs(user_dir, exist_ok=True)
    save_path = os.path.join(user_dir, filename)
    with open(save_path, "wb") as f:
        f.write(binary)

    try:
        with Image.open(save_path) as img:
            updated_metadata["width"] = int(img.width)
            updated_metadata["height"] = int(img.height)
            if img.format:
                updated_metadata["format"] = str(img.format)
    except Exception as exc:
        logger.warning("data-uri image metadata probe failed path=%s err=%s", save_path, exc)

    relative_path = os.path.relpath(save_path, upload_root).replace("\\", "/")
    normalized_url = f"/uploads/{relative_path}"
    logger.info(
        "[ImageResultNormalize] stored provider data URI | user_id=%s bytes=%s mime=%s url=%s",
        getattr(current_user, "id", None),
        len(binary),
        mime,
        normalized_url,
    )
    return normalized_url, updated_metadata


_KIE_GENERATED_MEDIA_HOST_PATTERNS = [
    re.compile(r"(^|\.)aiquickdraw\.com$", re.IGNORECASE),
    re.compile(r"(^|\.)kie\.ai$", re.IGNORECASE),
]


def _looks_like_kie_generated_media_url(value: Any) -> bool:
    raw = str(value or "").strip()
    if not raw.lower().startswith(("http://", "https://")):
        return False
    try:
        parsed = urllib.parse.urlparse(raw)
    except Exception:
        return False
    hostname = str(parsed.hostname or "").strip().lower()
    if not hostname:
        return False
    for pattern in _KIE_GENERATED_MEDIA_HOST_PATTERNS:
        if pattern.search(hostname):
            return True
    return False


def _resolve_kie_download_api_key() -> str:
    candidates = [
        getattr(settings, "KIE_API_KEY", ""),
        os.getenv("KIE_API_KEY", ""),
        os.getenv("KIE_DOWNLOAD_API_KEY", ""),
    ]
    for candidate in candidates:
        key = str(candidate or "").strip()
        if key:
            return key
    return ""


def _resolve_kie_downloadable_url(source_url: Any) -> str:
    raw_url = str(source_url or "").strip()
    if not raw_url or not _looks_like_kie_generated_media_url(raw_url):
        return ""

    api_key = _resolve_kie_download_api_key()
    if not api_key:
        return ""

    endpoint = str(os.getenv("KIE_DOWNLOAD_URL_ENDPOINT") or "https://api.kie.ai/api/v1/common/download-url").strip()
    if not endpoint:
        return ""

    try:
        resp = requests.post(
            endpoint,
            json={"url": raw_url},
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "AIStory/1.0",
            },
            timeout=(10, 30),
        )
        if resp.status_code != 200:
            logger.info(
                "[ImageResultNormalize] KIE download-url non-200 | status=%s source_url=%s",
                resp.status_code,
                raw_url,
            )
            return ""

        data = resp.json() if resp.content else {}
        code = data.get("code") if isinstance(data, dict) else None
        candidate = str(data.get("data") or "").strip() if isinstance(data, dict) else ""
        if code in (200, "200") and candidate.lower().startswith(("http://", "https://")):
            return candidate
        return ""
    except Exception as exc:
        logger.info(
            "[ImageResultNormalize] KIE download-url resolve failed | source_url=%s err=%s",
            raw_url,
            exc,
        )
        return ""


def _persist_remote_image_result(
    current_user: User,
    media_url: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
    *,
    db: Optional[Session] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    raw = str(media_url or "").strip()
    if not raw:
        return media_url, metadata
    if raw.startswith("/"):
        return media_url, metadata
    if not raw.lower().startswith(("http://", "https://")):
        return media_url, metadata

    try:
        parsed = urllib.parse.urlparse(raw)
    except Exception:
        return media_url, metadata

    hostname = str(parsed.hostname or "").strip().lower()
    if hostname in {"localhost", "127.0.0.1"}:
        return media_url, metadata
    if oss_storage_service.is_active_managed_url(raw, db):
        logger.info(
            "[ImageResultNormalize] skip remote localization for managed oss url | user_id=%s url=%s",
            getattr(current_user, "id", None),
            raw,
        )
        return media_url, metadata
    updated_metadata = dict(metadata) if isinstance(metadata, dict) else {}
    if _is_provider_direct_oss_url(raw, updated_metadata, db):
        updated_metadata["provider_direct_oss_url"] = True
        logger.info(
            "[ImageResultNormalize] skip localization for provider direct oss url | user_id=%s provider=%s url=%s",
            getattr(current_user, "id", None),
            str(updated_metadata.get("provider") or "").strip() or None,
            raw,
        )
        return raw, updated_metadata

    source_url = raw
    temp_filename = _extract_media_filename_from_url(raw)
    resolved_kie_download_url = _resolve_kie_downloadable_url(source_url)
    if resolved_kie_download_url and resolved_kie_download_url != raw:
        raw = resolved_kie_download_url
        try:
            parsed = urllib.parse.urlparse(raw)
        except Exception:
            parsed = urllib.parse.urlparse(source_url)
        if not temp_filename:
            temp_filename = _extract_media_filename_from_url(raw)

    max_remote_image_bytes = max(1, int(os.getenv("REMOTE_IMAGE_LOCALIZE_MAX_MB", "25"))) * 1024 * 1024

    try:
        response = requests.get(
            raw,
            stream=False,
            timeout=120,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
    except Exception as exc:
        logger.warning(
            "[ImageResultNormalize] remote image download failed | user_id=%s url=%s temp_filename=%s err=%s",
            getattr(current_user, "id", None),
            raw,
            temp_filename,
            exc,
        )
        updated_metadata = dict(metadata) if isinstance(metadata, dict) else {}
        updated_metadata["remote_localization_failed"] = True
        updated_metadata["remote_localization_error"] = str(exc)
        updated_metadata["remote_localization_source_url"] = raw
        if temp_filename:
            updated_metadata["temporary_source_filename"] = temp_filename
        return media_url, updated_metadata

    content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    if content_type and not (content_type.startswith("image/") or content_type.startswith("video/") or content_type.startswith("audio/")):
        logger.warning(
            "[ImageResultNormalize] remote media skipped non-media content | user_id=%s url=%s content_type=%s",
            getattr(current_user, "id", None),
            raw,
            content_type,
        )
        return media_url, metadata

    extension_map = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/bmp": ".bmp",
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
        "video/webm": ".webm",
        "video/x-msvideo": ".avi",
        "video/x-matroska": ".mkv",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mp4": ".m4a",
        "audio/aac": ".aac",
        "audio/flac": ".flac",
        "audio/ogg": ".ogg",
        "audio/opus": ".opus",
    }
    file_ext = extension_map.get(content_type)
    if not file_ext:
        path_ext = os.path.splitext(parsed.path or "")[1].lower()
        if path_ext in extension_map.values():
            file_ext = ".jpg" if path_ext == ".jpeg" else path_ext
        else:
            if content_type.startswith("video/"):
                file_ext = ".mp4"
            elif content_type.startswith("audio/"):
                file_ext = ".mp3"
            else:
                file_ext = ".png"

    filename = f"provider_result_{uuid.uuid4().hex[:16]}{file_ext}"
    chunks: List[bytes] = []
    bytes_written = 0
    try:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            if not chunk:
                continue
            bytes_written += len(chunk)
            if bytes_written > max_remote_image_bytes:
                raise ValueError(f"remote image too large: {bytes_written} > {max_remote_image_bytes}")
            chunks.append(chunk)
    except Exception as exc:
        logger.warning(
            "[ImageResultNormalize] remote image persistence failed | user_id=%s url=%s err=%s",
            getattr(current_user, "id", None),
            raw,
            exc,
        )
        updated_metadata = dict(metadata) if isinstance(metadata, dict) else {}
        updated_metadata["remote_localization_failed"] = True
        updated_metadata["remote_localization_error"] = str(exc)
        updated_metadata["remote_localization_source_url"] = raw
        return media_url, updated_metadata
    finally:
        try:
            response.close()
        except Exception:
            pass

    if bytes_written <= 0:
        return media_url, metadata

    binary = b"".join(chunks)

    updated_metadata = dict(metadata) if isinstance(metadata, dict) else {}
    updated_metadata["stored_from_remote_url"] = raw
    if temp_filename:
        updated_metadata["temporary_source_filename"] = temp_filename
    if resolved_kie_download_url:
        updated_metadata["stored_from_remote_url_source"] = source_url
        updated_metadata["stored_from_remote_url_resolved_via"] = "kie_download_url"
    updated_metadata["stored_from_remote_url_bytes"] = bytes_written
    if content_type:
        updated_metadata["stored_from_remote_url_content_type"] = content_type

    uploaded = oss_storage_service.upload_bytes(
        binary,
        user_id=int(getattr(current_user, "id", 0) or 0),
        filename=filename,
        content_type=content_type or f"image/{file_ext.lstrip('.')}",
        category="generated",
        cache_control="public, max-age=31536000",
    )
    if uploaded and uploaded.get("url"):
        updated_metadata["oss"] = {
            "provider": uploaded.get("provider"),
            "bucket": uploaded.get("bucket"),
            "key": uploaded.get("key"),
            "endpoint": uploaded.get("endpoint"),
        }
        try:
            with Image.open(io.BytesIO(binary)) as img:
                updated_metadata["width"] = int(img.width)
                updated_metadata["height"] = int(img.height)
                if img.format:
                    updated_metadata["format"] = str(img.format)
        except Exception as exc:
            logger.warning("remote image metadata probe failed in-memory err=%s", exc)
        logger.info(
            "[ImageResultNormalize] stored remote image in OSS | user_id=%s source_url=%s normalized_url=%s bytes=%s",
            getattr(current_user, "id", None),
            raw,
            uploaded["url"],
            bytes_written,
        )
        return str(uploaded["url"]), updated_metadata

    upload_root = settings.UPLOAD_DIR
    if not os.path.isabs(upload_root):
        upload_root = os.path.abspath(upload_root)

    user_dir = os.path.join(upload_root, str(getattr(current_user, "id", "unknown")), "generated")
    os.makedirs(user_dir, exist_ok=True)
    save_path = os.path.join(user_dir, filename)
    with open(save_path, "wb") as f:
        f.write(binary)

    try:
        with Image.open(save_path) as img:
            updated_metadata["width"] = int(img.width)
            updated_metadata["height"] = int(img.height)
            if img.format:
                updated_metadata["format"] = str(img.format)
    except Exception as exc:
        logger.warning("remote image metadata probe failed path=%s err=%s", save_path, exc)

    relative_path = os.path.relpath(save_path, upload_root).replace("\\", "/")
    normalized_url = f"/uploads/{relative_path}"
    logger.info(
        "[ImageResultNormalize] stored remote image | user_id=%s source_url=%s normalized_url=%s bytes=%s",
        getattr(current_user, "id", None),
        raw,
        normalized_url,
        bytes_written,
    )
    return normalized_url, updated_metadata


def _attach_oss_metadata_from_managed_url(metadata: Dict[str, Any], url: str) -> Dict[str, Any]:
    updated = dict(metadata)
    if isinstance(updated.get("oss"), dict):
        return updated
    pool, key = oss_storage_service._extract_managed_target(str(url or ""))
    if pool and key:
        updated["oss"] = {
            "provider": getattr(pool, "provider", None),
            "bucket": getattr(pool, "bucket", None),
            "key": key,
            "endpoint": getattr(pool, "endpoint", None),
        }
    return updated


def _oss_upload_succeeded_for_url(url: Optional[str], metadata: Optional[Dict[str, Any]] = None, db: Optional[Session] = None) -> bool:
    if isinstance(metadata, dict) and isinstance(metadata.get("oss"), dict):
        oss_meta = metadata.get("oss") or {}
        if oss_meta.get("key") and _url_matches_configured_oss(str(url or ""), metadata, db):
            return True
    if _url_matches_configured_oss(str(url or ""), metadata, db):
        return True
    return False


def _url_matches_configured_oss(
    url: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None,
) -> bool:
    raw = str(url or "").strip()
    if not raw or _is_ephemeral_provider_media_url(raw):
        return False
    if oss_storage_service.is_active_managed_url(raw, db):
        return True

    meta = metadata if isinstance(metadata, dict) else {}
    oss_meta = meta.get("oss") if isinstance(meta.get("oss"), dict) else {}
    if oss_meta.get("key"):
        pool, key = oss_storage_service.match_active_pool(raw, db)
        if pool and key and str(oss_meta.get("key") or "").strip() == str(key).strip():
            return True

    if not raw.lower().startswith(("http://", "https://")):
        return False

    signatures = oss_storage_service.get_active_url_signatures(db)
    if not signatures.get("oss_enabled"):
        return False

    try:
        parsed = urllib.parse.urlparse(raw)
        hostname = str(parsed.hostname or "").strip().lower()
    except Exception:
        return False
    if not hostname:
        return False

    allowed_hosts = set(signatures.get("hostnames") or [])
    if hostname in allowed_hosts:
        return True

    for base in signatures.get("public_base_urls") or []:
        normalized_base = str(base or "").strip().rstrip("/")
        if normalized_base and (raw.startswith(f"{normalized_base}/") or raw == normalized_base):
            return True

    if bool(meta.get("provider_direct_oss_url")):
        provider = str(meta.get("provider") or "").strip().lower()
        configured_providers = {str(item or "").strip().lower() for item in (signatures.get("providers") or [])}
        if provider and provider in configured_providers:
            return True

    return False


def _is_provider_direct_oss_url(
    url: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None,
) -> bool:
    raw = str(url or "").strip()
    if not raw.lower().startswith(("http://", "https://")):
        return False
    if _is_ephemeral_provider_media_url(raw):
        return False
    meta = metadata if isinstance(metadata, dict) else {}
    if bool(meta.get("provider_direct_oss_url")):
        return True
    provider = str(meta.get("provider") or "").strip().lower()
    if provider != "grsai":
        return False
    if _url_matches_configured_oss(raw, metadata, db):
        return True
    try:
        parsed = urllib.parse.urlparse(raw)
        hostname = str(parsed.hostname or "").strip().lower()
    except Exception:
        return False
    if not hostname:
        return False
    return bool(
        re.match(r"(^|.+\.)clouddn\.com$", hostname, re.IGNORECASE)
        or re.match(r"(^|.+\.)qiniucs\.com$", hostname, re.IGNORECASE)
        or re.match(r"(^|.+\.)woola\.fun$", hostname, re.IGNORECASE)
        or re.match(r"(^|.+\.)aliyuncs\.com$", hostname, re.IGNORECASE)
        or ".bkt." in hostname
        or "backblaze" in hostname
    )


def _persist_remote_video_result(
    current_user: User,
    media_url: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
    *,
    filename_base: Optional[str] = None,
    db: Optional[Session] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]], bool]:
    raw = str(media_url or "").strip()
    updated_metadata = dict(metadata) if isinstance(metadata, dict) else {}
    if not raw:
        return media_url, updated_metadata or metadata, False

    if raw.startswith("/"):
        return raw, updated_metadata, _oss_upload_succeeded_for_url(raw, updated_metadata, db)

    if not raw.lower().startswith(("http://", "https://")):
        return media_url, updated_metadata or metadata, False

    if oss_storage_service.is_active_managed_url(raw, db):
        updated_metadata = _attach_oss_metadata_from_managed_url(updated_metadata, raw)
        logger.info(
            "[VideoResultNormalize] skip remote localization for managed oss url | user_id=%s url=%s",
            getattr(current_user, "id", None),
            raw,
        )
        return raw, updated_metadata, True
    if _is_provider_direct_oss_url(raw, updated_metadata, db):
        updated_metadata["provider_direct_oss_url"] = True
        logger.info(
            "[VideoResultNormalize] skip localization for provider direct oss url | user_id=%s provider=%s url=%s",
            getattr(current_user, "id", None),
            str(updated_metadata.get("provider") or "").strip() or None,
            raw,
        )
        return raw, updated_metadata, True

    temp_filename = _extract_media_filename_from_url(raw)
    source_url = raw
    resolved_kie_download_url = _resolve_kie_downloadable_url(source_url)
    if resolved_kie_download_url and resolved_kie_download_url != raw:
        raw = resolved_kie_download_url
        if not temp_filename:
            temp_filename = _extract_media_filename_from_url(raw)

    user_id = int(getattr(current_user, "id", 0) or 0)
    max_attempts = max(1, int(os.getenv("REMOTE_VIDEO_LOCALIZE_MAX_ATTEMPTS", "3")))
    retry_backoff_seconds = max(0.5, float(os.getenv("REMOTE_VIDEO_LOCALIZE_RETRY_BACKOFF_SECONDS", "2")))
    persisted_url = ""
    last_exc: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            candidate_url = media_service._download_and_save(
                raw,
                filename_base=filename_base,
                user_id=user_id,
            )
            candidate_url = str(candidate_url or "").strip() or raw
            if candidate_url != source_url or _is_durable_persisted_media_url(candidate_url):
                persisted_url = candidate_url
                last_exc = None
                break
            persisted_url = candidate_url
            last_exc = ValueError("download_and_save returned original provider url")
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "[VideoResultNormalize] remote video download/save attempt failed | user_id=%s url=%s attempt=%s/%s err=%s",
                user_id,
                raw,
                attempt,
                max_attempts,
                exc,
            )
        if attempt < max_attempts:
            time.sleep(retry_backoff_seconds * attempt)

    if last_exc is not None and not persisted_url:
        updated_metadata["remote_localization_failed"] = True
        updated_metadata["remote_localization_error"] = str(last_exc)
        updated_metadata["remote_localization_source_url"] = raw
        updated_metadata["persist_attempts"] = max_attempts
        if temp_filename:
            updated_metadata["temporary_source_filename"] = temp_filename
        return media_url, updated_metadata, False

    persisted_url = str(persisted_url or "").strip() or raw
    oss_ok = _oss_upload_succeeded_for_url(persisted_url, updated_metadata, db)

    if persisted_url != source_url:
        updated_metadata["stored_from_remote_url"] = raw
        updated_metadata["remote_localization_failed"] = False
        updated_metadata.pop("remote_localization_error", None)
        if temp_filename:
            updated_metadata["temporary_source_filename"] = temp_filename
        if resolved_kie_download_url:
            updated_metadata["stored_from_remote_url_source"] = source_url
            updated_metadata["stored_from_remote_url_resolved_via"] = "kie_download_url"

    if oss_ok:
        updated_metadata = _attach_oss_metadata_from_managed_url(updated_metadata, persisted_url)
    elif persisted_url.startswith("/uploads/"):
        updated_metadata["stored_locally"] = True

    localized_success = _is_persisted_media_localization_success(
        persisted_url,
        source_url=source_url,
        metadata=updated_metadata,
        db=db,
        oss_uploaded=oss_ok,
    )
    if localized_success:
        updated_metadata = _clear_ephemeral_persist_flags(updated_metadata)
        updated_metadata["stored_from_remote_url"] = raw
        updated_metadata["remote_localization_failed"] = False
        updated_metadata.pop("remote_localization_error", None)
        if temp_filename:
            updated_metadata["temporary_source_filename"] = temp_filename
        if resolved_kie_download_url:
            updated_metadata["stored_from_remote_url_source"] = source_url
            updated_metadata["stored_from_remote_url_resolved_via"] = "kie_download_url"
        if oss_ok:
            updated_metadata["oss_uploaded_success"] = True
        logger.info(
            "[VideoResultNormalize] stored remote video | user_id=%s source_url=%s normalized_url=%s oss=%s",
            user_id,
            source_url,
            persisted_url,
            oss_ok,
        )
        return persisted_url, updated_metadata, oss_ok

    if not _is_durable_persisted_media_url(persisted_url, updated_metadata, db):
        updated_metadata["remote_localization_failed"] = True
        updated_metadata.setdefault(
            "remote_localization_error",
            "download_and_save returned original provider url",
        )
        updated_metadata["remote_localization_source_url"] = source_url
        updated_metadata["needs_persistence_retry"] = True
        logger.warning(
            "[VideoResultNormalize] remote video persisted without durable storage | user_id=%s url=%s",
            user_id,
            source_url,
        )
        return persisted_url, updated_metadata, False

    logger.info(
        "[VideoResultNormalize] stored remote video | user_id=%s source_url=%s normalized_url=%s oss=%s",
        user_id,
        source_url,
        persisted_url,
        oss_ok,
    )
    return persisted_url, updated_metadata, oss_ok


def _persist_remote_media_result(
    current_user: User,
    media_url: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
    *,
    filename_base: Optional[str] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]], bool]:
    """Stream-download remote media and persist to OSS/local (video/audio/large files)."""
    return _persist_remote_video_result(
        current_user,
        media_url,
        metadata,
        filename_base=filename_base,
    )


def _resolve_media_bind_url(
    *,
    raw_url: str,
    normalized_url: Optional[str],
    normalized_meta: Dict[str, Any],
    oss_uploaded: bool = False,
    db: Optional[Session] = None,
) -> Tuple[Optional[str], bool, Dict[str, Any]]:
    return _resolve_video_bind_url(
        raw_url=raw_url,
        normalized_url=normalized_url,
        normalized_meta=normalized_meta,
        oss_uploaded=oss_uploaded,
        db=db,
    )


def _resolve_media_persistence_source_url(result: Dict[str, Any]) -> str:
    return _resolve_video_persistence_source_url(result)


def _media_result_needs_persistence_retry(result: Any) -> bool:
    return _video_result_needs_persistence_retry(result)


_EPHEMERAL_PROVIDER_MEDIA_HOST_PATTERNS = [
    re.compile(r"^file\d*\.aitohumanize\.com$", re.IGNORECASE),
    re.compile(r"(^|.+\.)aiquickdraw\.com$", re.IGNORECASE),
    re.compile(r"(^|.+\.)tempfile\.aiquickdraw\.com$", re.IGNORECASE),
    # Volcengine Ark / Seedance temporary TOS delivery URLs (must be localized to OSS).
    re.compile(r"(^|.+\.)volces\.com$", re.IGNORECASE),
]

_EPHEMERAL_PROVIDER_MEDIA_QUERY_MARKERS = (
    "x-tos-algorithm",
    "x-tos-signature",
    "x-tos-credential",
    "x-amz-algorithm",
    "x-amz-signature",
    "x-amz-credential",
)


def _is_ephemeral_provider_media_url(value: Any) -> bool:
    raw = str(value or "").strip()
    if not raw or raw.startswith("/") or raw.startswith("data:"):
        return False

    try:
        parsed = urllib.parse.urlparse(raw)
    except Exception:
        return False

    if str(parsed.scheme or "").lower() not in {"http", "https"}:
        return False

    hostname = str(parsed.hostname or "").strip().lower()
    if not hostname:
        return False

    for pattern in _EPHEMERAL_PROVIDER_MEDIA_HOST_PATTERNS:
        if pattern.match(hostname):
            return True

    query_lower = str(parsed.query or "").strip().lower()
    if query_lower and any(marker in query_lower for marker in _EPHEMERAL_PROVIDER_MEDIA_QUERY_MARKERS):
        return True
    return False


def _job_has_durable_result_url(job: Dict[str, Any]) -> bool:
    if not isinstance(job, dict):
        return False
    result = job.get("result")
    current_url = _extract_job_result_url(result)
    if not current_url:
        return False
    meta: Dict[str, Any] = {}
    if isinstance(result, dict) and isinstance(result.get("metadata"), dict):
        meta = dict(result.get("metadata") or {})
    return _is_durable_persisted_media_url(current_url, meta)


def _is_durable_persisted_media_url(
    value: Any,
    metadata: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None,
) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    if _is_ephemeral_provider_media_url(raw):
        return False

    oss_enabled = oss_storage_service.is_enabled(db)
    if raw.startswith("/uploads/") or (raw.startswith("/") and not raw.startswith("//")):
        if oss_enabled:
            return False
        return True

    if _url_matches_configured_oss(raw, metadata, db):
        return True
    if _is_provider_direct_oss_url(raw, metadata, db):
        return True
    return False


def _resolve_video_persistence_source_url(result: Dict[str, Any]) -> str:
    meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    for key in ("remote_localization_source_url", "stored_from_remote_url", "pending_source_url"):
        candidate = str(meta.get(key) or "").strip()
        if candidate:
            return candidate
    direct = str(result.get("url") or "").strip()
    if direct:
        return direct
    return _extract_job_result_url(result)


def _video_result_needs_persistence_retry(result: Any, db: Optional[Session] = None) -> bool:
    if not isinstance(result, dict):
        return False
    meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    current = str(result.get("url") or "").strip() or _extract_job_result_url(result)
    source = _resolve_video_persistence_source_url(result)
    if current and _is_persisted_media_localization_success(
        current,
        source_url=source,
        metadata=meta,
        db=db,
    ):
        return False
    if meta.get("persistence_gave_up") is True:
        return False
    # Runner already owns bg localization after provisional publish; poll-path retry
    # would race the same OSS key and delay shot bind.
    if meta.get("bg_persist_owned") or meta.get("oss_persist_pending"):
        return False
    if not source:
        return False
    if meta.get("remote_localization_failed") or meta.get("needs_persistence_retry") or meta.get("ephemeral_binding"):
        return True
    if _is_ephemeral_provider_media_url(current) or _is_ephemeral_provider_media_url(source):
        return True
    if current.lower().startswith(("http://", "https://")) and not _url_matches_configured_oss(current, meta, db):
        return True
    return False


def _clear_ephemeral_persist_flags(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    cleaned = dict(meta or {})
    for key in (
        "ephemeral_binding",
        "needs_persistence_retry",
        "remote_localization_failed",
        "remote_localization_error",
        "pending_source_url",
        "persistence_retry_count",
        "persistence_retry_at",
    ):
        cleaned.pop(key, None)
    cleaned["remote_localization_failed"] = False
    return cleaned


def _ensure_media_bound_at(meta: Optional[Dict[str, Any]], *, refresh: bool = False) -> Dict[str, Any]:
    stamped = dict(meta or {})
    if refresh or not stamped.get("media_bound_at"):
        stamped["media_bound_at"] = now_bj_iso()
    return stamped


def _is_persisted_media_localization_success(
    url: Any,
    *,
    source_url: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None,
    oss_uploaded: bool = False,
) -> bool:
    raw = str(url or "").strip()
    if not raw or _is_ephemeral_provider_media_url(raw):
        return False
    if oss_uploaded or _oss_upload_succeeded_for_url(raw, metadata, db):
        return True
    if _is_durable_persisted_media_url(raw, metadata, db):
        return True
    source = str(source_url or "").strip()
    if source and raw != source and raw.lower().startswith(("http://", "https://")):
        return True
    return False


def _resolve_video_bind_url(
    *,
    raw_url: str,
    normalized_url: Optional[str],
    normalized_meta: Dict[str, Any],
    oss_uploaded: bool = False,
    db: Optional[Session] = None,
) -> Tuple[Optional[str], bool, Dict[str, Any]]:
    meta = dict(normalized_meta or {})
    durable = str(normalized_url or "").strip()
    if durable and _is_persisted_media_localization_success(
        durable,
        source_url=raw_url,
        metadata=meta,
        db=db,
        oss_uploaded=oss_uploaded,
    ):
        meta = _clear_ephemeral_persist_flags(meta)
        if oss_uploaded:
            meta["oss_uploaded_success"] = True
        return durable, False, meta

    source = str(raw_url or "").strip()
    if not source:
        return None, False, meta

    if _is_provider_direct_oss_url(source, meta, db):
        # Provider-side direct OSS links are durable object keys, but often private.
        # Return a freshly signed URL so bind/proxy/clients can fetch immediately.
        # Lazy import: callbacks imports media_persist at module load.
        from app.services.generation_runtime.callbacks import _ensure_accessible_media_result_url

        meta["provider_direct_oss_url"] = True
        accessible = _ensure_accessible_media_result_url(source, meta)
        return accessible or source, False, meta

    if source.lower().startswith(("http://", "https://")) or _is_ephemeral_provider_media_url(source):
        meta["ephemeral_binding"] = True
        meta["needs_persistence_retry"] = True
        meta.setdefault("pending_source_url", source)
        return source, True, meta

    return None, False, meta


def _build_ephemeral_media_metadata(
    raw_url: str,
    base_meta: Optional[Dict[str, Any]] = None,
    *,
    temp_filename: Optional[str] = None,
) -> Dict[str, Any]:
    meta = dict(base_meta or {})
    meta["ephemeral_binding"] = True
    meta["needs_persistence_retry"] = True
    meta.setdefault("pending_source_url", raw_url)
    meta.setdefault("remote_localization_source_url", raw_url)
    meta["remote_localization_failed"] = True
    if temp_filename:
        meta.setdefault("temporary_source_filename", temp_filename)
    return _ensure_media_bound_at(meta, refresh=True)


def _build_generation_job_req_context(job: Dict[str, Any], db: Optional[Session] = None) -> Dict[str, Any]:
    req_context: Dict[str, Any] = {}
    for key in (
        "prompt", "negative_prompt", "provider", "model", "aspect_ratio",
        "duration", "project_id", "episode_id", "scene_id", "shot_id",
        "shot_number", "shot_name", "asset_type", "seed", "subject_id",
        "entity_id", "entity_name", "entity_type", "subject_name", "subject_type", "mode",
    ):
        value = job.get(key)
        if value is not None and value != "":
            req_context[key] = value

    if db is not None and not req_context.get("project_id") and req_context.get("shot_id"):
        try:
            shot_row = db.query(Shot).filter(Shot.id == int(req_context.get("shot_id"))).first()
            if shot_row:
                if getattr(shot_row, "project_id", None):
                    req_context["project_id"] = int(shot_row.project_id)
                if getattr(shot_row, "episode_id", None):
                    req_context["episode_id"] = int(shot_row.episode_id)
                if getattr(shot_row, "shot_id", None) and not req_context.get("shot_number"):
                    req_context["shot_number"] = shot_row.shot_id
                if getattr(shot_row, "shot_name", None) and not req_context.get("shot_name"):
                    req_context["shot_name"] = shot_row.shot_name
        except Exception:
            pass
    return req_context


def _enrich_media_metadata_from_generation_context(
    meta: Optional[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Fill provider/model and generation params into media metadata without overwriting existing values."""
    enriched = dict(meta or {})
    ctx = context if isinstance(context, dict) else {}

    for key in (
        "provider",
        "model",
        "prompt",
        "negative_prompt",
        "aspect_ratio",
        "submit_aspect_ratio",
        "duration",
        "seed",
        "width",
        "height",
        "resolution",
        "image_size",
        "system_api_id",
        "shot_id",
        "project_id",
        "episode_id",
        "scene_id",
        "shot_number",
        "shot_name",
        "asset_type",
        "job_id",
        "idempotency_key",
    ):
        if enriched.get(key) not in (None, ""):
            continue
        value = ctx.get(key)
        if value not in (None, ""):
            enriched[key] = value

    smart_meta = enriched.get("smart_routing") if isinstance(enriched.get("smart_routing"), dict) else {}
    if not smart_meta and isinstance(ctx.get("smart_routing"), dict):
        smart_meta = ctx.get("smart_routing") or {}
    if not enriched.get("provider") and smart_meta.get("provider"):
        enriched["provider"] = smart_meta.get("provider")
    if not enriched.get("model") and smart_meta.get("model"):
        enriched["model"] = smart_meta.get("model")
    if enriched.get("system_api_id") is None and smart_meta.get("system_api_id") is not None:
        enriched["system_api_id"] = smart_meta.get("system_api_id")

    return enriched


def _hydrate_video_job_record(job_id: str, job: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    stable_job_id = str(job_id or (job or {}).get("job_id") or "").strip()
    merged = dict(job or {})
    if stable_job_id:
        merged["job_id"] = stable_job_id

    with VIDEO_JOB_LOCK:
        live = dict(VIDEO_JOB_STORE.get(stable_job_id) or {})
    if live:
        for key, value in live.items():
            if value in (None, ""):
                continue
            if merged.get(key) in (None, ""):
                merged[key] = value

    if stable_job_id:
        file_job = _read_video_job_file(stable_job_id)
        if isinstance(file_job, dict):
            for key, value in file_job.items():
                if value in (None, ""):
                    continue
                if merged.get(key) in (None, ""):
                    merged[key] = value

        try:
            from app.services.generation_task_queue import get_generation_task_status

            task_row = get_generation_task_status(stable_job_id) or {}
            task_user_id = task_row.get("user_id")
            if task_user_id not in (None, "") and merged.get("user_id") in (None, ""):
                merged["user_id"] = int(task_user_id)
            task_payload = _parse_generation_task_payload(task_row)
            recovered_fields: Dict[str, Any] = {}
            for key in (
                "shot_id", "project_id", "episode_id", "scene_id", "shot_number", "shot_name",
                "asset_type", "provider", "model", "prompt", "username",
                "reservation_tx_id", "billing_pending", "billing_settled", "billing_context",
                "provider_task_id", "task_id", "taskId", "system_api_id", "query_endpoint",
                "final_provider_payload", "combined_payload",
            ):
                if task_payload.get(key) in (None, "", {}, []):
                    continue
                if merged.get(key) in (None, "", {}, []):
                    merged[key] = task_payload.get(key)
                    recovered_fields[key] = task_payload.get(key)
            # Promote nested NukoAi/poll task ids onto top-level for re-download lookup.
            if merged.get("provider_task_id") in (None, ""):
                from app.services.generation_runtime.callbacks import _extract_job_provider_task_id

                nested_task_id = _extract_job_provider_task_id(task_payload) or _extract_job_provider_task_id(merged)
                if nested_task_id:
                    merged["provider_task_id"] = nested_task_id
                    merged["task_id"] = nested_task_id
                    merged["taskId"] = nested_task_id
                    recovered_fields["provider_task_id"] = nested_task_id
            if recovered_fields:
                logger.info(
                    "[VideoJob] hydrated missing fields from task payload | job_id=%s fields=%s",
                    stable_job_id,
                    sorted(list(recovered_fields.keys())),
                )
                _set_video_job(stable_job_id, **recovered_fields)
        except Exception:
            pass

    return merged


def _parse_generation_task_payload(task_row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(task_row, dict):
        return {}
    payload = task_row.get("payload")
    if isinstance(payload, dict):
        return dict(payload)
    raw_json = task_row.get("payload_json")
    if isinstance(raw_json, dict):
        return dict(raw_json)
    if isinstance(raw_json, str) and raw_json.strip():
        try:
            parsed = json.loads(raw_json)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _resolve_job_owner_user(db: Session, job: Dict[str, Any]) -> Optional[Any]:
    from app.models.all_models import User

    try:
        user_id = int(job.get("user_id") or 0)
    except Exception:
        user_id = 0
    if user_id > 0:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return user

    username = str(job.get("username") or "").strip()
    if username:
        user = db.query(User).filter(User.username == username).first()
        if user:
            return user

    shot_id = job.get("shot_id")
    if shot_id:
        try:
            shot = db.query(Shot).filter(Shot.id == int(shot_id)).first()
        except Exception:
            shot = None
        if shot:
            project_id = getattr(shot, "project_id", None)
            if not project_id and getattr(shot, "scene_id", None):
                scene = db.query(Scene).filter(Scene.id == int(shot.scene_id)).first()
                if scene and getattr(scene, "episode_id", None):
                    episode = db.query(Episode).filter(Episode.id == int(scene.episode_id)).first()
                    if episode:
                        project_id = getattr(episode, "project_id", None)
            if project_id:
                project = db.query(Project).filter(Project.id == int(project_id)).first()
                owner_id = int(getattr(project, "owner_id", 0) or 0) if project else 0
                if owner_id > 0:
                    user = db.query(User).filter(User.id == owner_id).first()
                    if user:
                        job.setdefault("user_id", owner_id)
                        job.setdefault("project_id", int(project_id))
                        return user
    return None


def _stage_ephemeral_media_job_result(
    job_id: str,
    job: Dict[str, Any],
    result: Dict[str, Any],
    *,
    media_kind: str = "video",
) -> Dict[str, Any]:
    """Save ephemeral provider URL to job metadata and bind shot/entity before OSS download."""
    if not isinstance(result, dict):
        return result

    raw_url = _extract_job_result_url(result)
    if not raw_url or not _is_ephemeral_provider_media_url(raw_url):
        return result

    existing_meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    if _is_durable_persisted_media_url(raw_url, existing_meta):
        return result
    if existing_meta.get("ephemeral_binding") and existing_meta.get("needs_persistence_retry"):
        return result

    temp_filename = _extract_media_filename_from_url(raw_url)
    staged_meta = _build_ephemeral_media_metadata(
        raw_url,
        existing_meta,
        temp_filename=temp_filename or None,
    )
    staged_result = dict(result)
    staged_result["url"] = raw_url

    temp_label = f" temp_filename={temp_filename}" if temp_filename else ""
    log_prefix = "VideoJobPersist" if media_kind == "video" else "ImageJobPersist"

    if media_kind == "video":
        job = _hydrate_video_job_record(job_id, job)

    try:
        user_id = int(job.get("user_id") or 0)
    except Exception:
        user_id = 0

    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        current_user = _resolve_job_owner_user(db, job)
        req_context = _build_generation_job_req_context(job, db)
        staged_meta = _enrich_media_metadata_from_generation_context(staged_meta, job)
        staged_meta = _enrich_media_metadata_from_generation_context(staged_meta, req_context)
        staged_meta["job_id"] = job_id
        staged_result["metadata"] = staged_meta
        if media_kind == "video" and not str(req_context.get("asset_type") or "").strip():
            req_context["asset_type"] = "video"

        if not current_user:
            logger.warning(
                "[%s] staged ephemeral provider url without owner user | job_id=%s shot_id=%s user_id=%s%s url=%s",
                log_prefix,
                job_id,
                req_context.get("shot_id"),
                user_id or None,
                temp_label,
                raw_url,
            )
            return staged_result

        logger.warning(
            "[%s] staged ephemeral provider url | job_id=%s shot_id=%s user_id=%s%s url=%s",
            log_prefix,
            job_id,
            req_context.get("shot_id"),
            getattr(current_user, "id", None),
            temp_label,
            raw_url,
        )

        if req_context.get("shot_id"):
            _bind_generated_media_to_shot(
                db,
                current_user,
                req_context,
                raw_url,
                oss_uploaded_success=False,
                media_metadata=staged_meta,
            )
        elif media_kind == "video":
            logger.warning(
                "[VideoJobPersist] ephemeral url saved to job but shot_id missing | job_id=%s url=%s",
                job_id,
                raw_url,
            )

        request_mode = str(req_context.get("mode") or "").strip().lower()
        if media_kind == "image" and request_mode != "joint_diptych":
            _bind_generated_media_to_entity(
                db,
                current_user,
                req_context,
                raw_url,
                oss_uploaded_success=False,
            )
    except Exception as exc:
        logger.warning(
            "[EphemeralStage] bind failed | job_id=%s media_kind=%s error=%s",
            job_id,
            media_kind,
            exc,
        )
    finally:
        db.close()

    return staged_result


def _extract_media_filename_from_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urllib.parse.urlparse(raw)
    except Exception:
        return ""

    pathname = str(parsed.path or "").strip()
    if not pathname:
        return ""

    try:
        return os.path.basename(pathname).strip()
    except Exception:
        return ""


def _assert_allowed_persisted_media_url(
    value: Any,
    *,
    field_label: str,
    metadata: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None,
    existing_value: Any = None,
) -> None:
    raw = str(value or "").strip()
    if not raw:
        return
    if _is_ephemeral_provider_media_url(raw):
        meta = metadata if isinstance(metadata, dict) else {}
        if meta.get("ephemeral_binding") or meta.get("needs_persistence_retry"):
            return
        if existing_value is not None and str(existing_value or "").strip() == raw:
            return
        raise HTTPException(
            status_code=400,
            detail=f"{field_label} cannot use a temporary provider URL; persist to OSS first",
        )
    if oss_storage_service.is_enabled(db) and not _is_durable_persisted_media_url(raw, metadata, db):
        raise HTTPException(
            status_code=400,
            detail=f"{field_label} must use configured OSS storage URL; run persist-media first",
        )


def _normalize_ephemeral_shot_media_update(
    update_data: Dict[str, Any],
    *,
    existing_shot: Optional[Shot] = None,
) -> Dict[str, Any]:
    patched = dict(update_data or {})

    def _ensure_ephemeral_notes(
        url_value: Any,
        *,
        meta_key: str,
        oss_flag_key: str,
    ) -> None:
        url = str(url_value or "").strip()
        if not url or not _is_ephemeral_provider_media_url(url):
            return

        raw_notes = patched.get("technical_notes")
        if raw_notes is None and existing_shot is not None:
            notes = _asset_meta_to_dict(getattr(existing_shot, "technical_notes", None))
        elif isinstance(raw_notes, dict):
            notes = dict(raw_notes)
        elif isinstance(raw_notes, str):
            notes = _asset_meta_to_dict(raw_notes)
        else:
            notes = {}

        slot_meta = dict(notes.get(meta_key) or {}) if isinstance(notes.get(meta_key), dict) else {}
        if slot_meta.get("ephemeral_binding") and slot_meta.get("needs_persistence_retry"):
            return

        notes[meta_key] = _build_ephemeral_media_metadata(url, slot_meta)
        notes[oss_flag_key] = False
        if isinstance(raw_notes, dict):
            patched["technical_notes"] = notes
        else:
            patched["technical_notes"] = json.dumps(notes, ensure_ascii=False)

    if "video_url" in patched:
        _ensure_ephemeral_notes(patched.get("video_url"), meta_key="video_metadata", oss_flag_key="video_oss_uploaded")
    if "image_url" in patched:
        _ensure_ephemeral_notes(patched.get("image_url"), meta_key="start_frame_metadata", oss_flag_key="start_frame_oss_uploaded")

    raw_notes = patched.get("technical_notes")
    notes_dict: Optional[Dict[str, Any]] = None
    if isinstance(raw_notes, dict):
        notes_dict = dict(raw_notes)
    elif isinstance(raw_notes, str):
        notes_dict = _asset_meta_to_dict(raw_notes)
    if isinstance(notes_dict, dict) and notes_dict.get("end_frame_url"):
        end_url = str(notes_dict.get("end_frame_url") or "").strip()
        if end_url and _is_ephemeral_provider_media_url(end_url):
            end_meta = dict(notes_dict.get("end_frame_metadata") or {}) if isinstance(notes_dict.get("end_frame_metadata"), dict) else {}
            if not (end_meta.get("ephemeral_binding") and end_meta.get("needs_persistence_retry")):
                notes_dict["end_frame_metadata"] = _build_ephemeral_media_metadata(end_url, end_meta)
                notes_dict["end_frame_oss_uploaded"] = False
                patched["technical_notes"] = notes_dict if isinstance(raw_notes, dict) else json.dumps(notes_dict, ensure_ascii=False)

    return patched


def _assert_allowed_shot_media_payload(
    update_data: Dict[str, Any],
    db: Optional[Session] = None,
    existing_shot: Optional[Shot] = None,
) -> None:
    if not isinstance(update_data, dict):
        return

    notes: Optional[Dict[str, Any]] = None
    raw_technical_notes = update_data.get("technical_notes")
    if isinstance(raw_technical_notes, dict):
        notes = raw_technical_notes
    elif isinstance(raw_technical_notes, str):
        try:
            parsed = json.loads(raw_technical_notes)
            notes = parsed if isinstance(parsed, dict) else None
        except Exception:
            notes = None

    start_meta = (
        dict(notes.get("start_frame_metadata") or {})
        if isinstance(notes, dict) and isinstance(notes.get("start_frame_metadata"), dict)
        else {}
    )
    video_meta = (
        dict(notes.get("video_metadata") or {})
        if isinstance(notes, dict) and isinstance(notes.get("video_metadata"), dict)
        else {}
    )
    end_meta = (
        dict(notes.get("end_frame_metadata") or {})
        if isinstance(notes, dict) and isinstance(notes.get("end_frame_metadata"), dict)
        else {}
    )

    _assert_allowed_persisted_media_url(
        update_data.get("image_url"),
        field_label="shot.image_url",
        metadata=start_meta,
        db=db,
        existing_value=getattr(existing_shot, "image_url", None) if existing_shot is not None else None,
    )
    _assert_allowed_persisted_media_url(
        update_data.get("video_url"),
        field_label="shot.video_url",
        metadata=video_meta,
        db=db,
        existing_value=getattr(existing_shot, "video_url", None) if existing_shot is not None else None,
    )

    if isinstance(notes, dict):
        existing_notes: Dict[str, Any] = {}
        if existing_shot is not None:
            existing_notes = _asset_meta_to_dict(getattr(existing_shot, "technical_notes", None))
        _assert_allowed_persisted_media_url(
            notes.get("end_frame_url"),
            field_label="shot.technical_notes.end_frame_url",
            metadata=end_meta,
            db=db,
            existing_value=existing_notes.get("end_frame_url") if isinstance(existing_notes, dict) else None,
        )


def _asset_meta_to_dict(raw_meta: Any) -> Dict[str, Any]:
    if isinstance(raw_meta, dict):
        return raw_meta
    if isinstance(raw_meta, str):
        try:
            parsed = json.loads(raw_meta)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _visible_asset_owner_ids_for_project(project: Optional[Project], current_user: User) -> List[int]:
    owner_ids = {int(current_user.id)}
    try:
        if project and getattr(project, "owner_id", None) is not None:
            owner_ids.add(int(project.owner_id))
    except Exception:
        pass
    return sorted(owner_ids)


def _resolve_precise_asset_library_url(
    db: Session,
    current_user: User,
    legacy_url: Any,
    *,
    project: Optional[Project],
    entity_id: Optional[int] = None,
    shot_id: Optional[int] = None,
    asset_type_aliases: Optional[set] = None,
    media_type: Optional[str] = None,
    limit: int = 256,
) -> Optional[str]:
    raw_legacy_url = str(legacy_url or "").strip()
    if not _is_ephemeral_provider_media_url(raw_legacy_url):
        return None

    project_id = getattr(project, "id", None)
    if not project_id:
        return None
    if entity_id is None and shot_id is None:
        return None

    owner_ids = _visible_asset_owner_ids_for_project(project, current_user)
    query = db.query(Asset).filter(Asset.user_id.in_(owner_ids))
    if media_type:
        query = query.filter(Asset.type == str(media_type).strip().lower())

    meta_text = cast(Asset.meta_info, String)
    query = query.filter(meta_text.contains(raw_legacy_url))
    query = query.filter(meta_text.contains(str(project_id)))
    if entity_id is not None:
        query = query.filter(meta_text.contains(str(entity_id)))
    if shot_id is not None:
        query = query.filter(meta_text.contains(str(shot_id)))
    if asset_type_aliases:
        alias_filters = [meta_text.contains(alias) for alias in sorted(asset_type_aliases) if str(alias or "").strip()]
        if alias_filters:
            query = query.filter(or_(*alias_filters))

    matched_urls: List[str] = []
    candidates = query.order_by(Asset.id.desc()).limit(max(int(limit or 0), 1)).all()
    for asset in candidates:
        meta = _asset_meta_to_dict(asset.meta_info)
        if str(meta.get("source_asset_url") or "").strip() != raw_legacy_url:
            continue
        if str(meta.get("project_id") or "").strip() != str(project_id):
            continue
        if entity_id is not None and str(meta.get("entity_id") or "").strip() != str(entity_id):
            continue
        if shot_id is not None and str(meta.get("shot_id") or "").strip() != str(shot_id):
            continue

        candidate_asset_type = str(meta.get("asset_type") or meta.get("frame_type") or "").strip().lower()
        if asset_type_aliases and candidate_asset_type not in asset_type_aliases:
            continue

        stable_url = str(asset.url or "").strip()
        if not stable_url or stable_url == raw_legacy_url or _is_ephemeral_provider_media_url(stable_url):
            continue

        matched_urls.append(stable_url)

    unique_urls = sorted(set(matched_urls))
    if len(unique_urls) != 1:
        return None
    return unique_urls[0]


def _repair_entity_image_url_from_assets(
    db: Session,
    current_user: User,
    project: Optional[Project],
    entity: Optional[Entity],
) -> bool:
    if not entity:
        return False

    legacy_url = str(getattr(entity, "image_url", None) or "").strip()
    if not _is_ephemeral_provider_media_url(legacy_url):
        return False

    resolved_url = _resolve_precise_asset_library_url(
        db,
        current_user,
        legacy_url,
        project=project,
        entity_id=getattr(entity, "id", None),
        asset_type_aliases={"subject", "character", "char"},
        media_type="image",
    )
    if not resolved_url:
        return False

    entity.image_url = resolved_url
    db.add(entity)
    logger.info(
        "[LegacyAssetRepair] entity_id=%s project_id=%s legacy_url=%s repaired_url=%s",
        getattr(entity, "id", None),
        getattr(entity, "project_id", None),
        legacy_url,
        resolved_url,
    )
    return True


def _repair_shot_media_urls_from_assets(
    db: Session,
    current_user: User,
    project: Optional[Project],
    shot: Optional[Shot],
) -> bool:
    if not shot:
        return False

    changed = False
    legacy_image_url = str(getattr(shot, "image_url", None) or "").strip()
    if _is_ephemeral_provider_media_url(legacy_image_url):
        resolved_image_url = _resolve_precise_asset_library_url(
            db,
            current_user,
            legacy_image_url,
            project=project,
            shot_id=getattr(shot, "id", None),
            asset_type_aliases={"start_frame", "start"},
            media_type="image",
        )
        if resolved_image_url:
            shot.image_url = resolved_image_url
            db.add(shot)
            changed = True
            logger.info(
                "[LegacyAssetRepair] shot_id=%s slot=start project_id=%s legacy_url=%s repaired_url=%s",
                getattr(shot, "id", None),
                getattr(shot, "project_id", None),
                legacy_image_url,
                resolved_image_url,
            )

    notes_changed = False
    notes = _asset_meta_to_dict(getattr(shot, "technical_notes", None))
    legacy_end_frame_url = str(notes.get("end_frame_url") or "").strip()
    if _is_ephemeral_provider_media_url(legacy_end_frame_url):
        resolved_end_frame_url = _resolve_precise_asset_library_url(
            db,
            current_user,
            legacy_end_frame_url,
            project=project,
            shot_id=getattr(shot, "id", None),
            asset_type_aliases={"end_frame", "end"},
            media_type="image",
        )
        if resolved_end_frame_url:
            notes["end_frame_url"] = resolved_end_frame_url
            notes_changed = True
            logger.info(
                "[LegacyAssetRepair] shot_id=%s slot=end project_id=%s legacy_url=%s repaired_url=%s",
                getattr(shot, "id", None),
                getattr(shot, "project_id", None),
                legacy_end_frame_url,
                resolved_end_frame_url,
            )

    legacy_video_url = str(getattr(shot, "video_url", None) or "").strip()
    if _is_ephemeral_provider_media_url(legacy_video_url):
        resolved_video_url = _resolve_precise_asset_library_url(
            db,
            current_user,
            legacy_video_url,
            project=project,
            shot_id=getattr(shot, "id", None),
            asset_type_aliases={"video"},
            media_type="video",
        )
        if resolved_video_url:
            shot.video_url = resolved_video_url
            video_meta = notes.get("video_metadata") if isinstance(notes.get("video_metadata"), dict) else {}
            video_meta = dict(video_meta or {})
            video_meta.pop("needs_persistence_retry", None)
            video_meta.pop("ephemeral_binding", None)
            video_meta["remote_localization_failed"] = False
            notes["video_metadata"] = video_meta
            notes["video_oss_uploaded"] = True
            notes_changed = True
            db.add(shot)
            changed = True
            logger.info(
                "[LegacyAssetRepair] shot_id=%s slot=video project_id=%s legacy_url=%s repaired_url=%s",
                getattr(shot, "id", None),
                getattr(shot, "project_id", None),
                legacy_video_url,
                resolved_video_url,
            )

    if notes_changed:
        shot.technical_notes = json.dumps(notes, ensure_ascii=False)
        db.add(shot)
        changed = True

    return changed


def _repair_entities_image_urls_from_assets(
    db: Session,
    current_user: User,
    project: Optional[Project],
    entities: List[Entity],
) -> List[Entity]:
    changed = False
    for entity in entities or []:
        if _repair_entity_image_url_from_assets(db, current_user, project, entity):
            changed = True
    if changed:
        db.commit()
    return entities


def _diagnose_entity_image_url(image_url: Any) -> Dict[str, Any]:
    raw = str(image_url or "").strip()
    info: Dict[str, Any] = {
        "raw": raw,
        "is_empty": not bool(raw),
        "is_relative_upload": False,
        "is_absolute_upload": False,
        "upload_suffix": "",
        "local_path": "",
        "local_exists": None,
    }
    if not raw:
        return info

    upload_suffix = ""
    if raw.startswith("/uploads/"):
        info["is_relative_upload"] = True
        upload_suffix = raw[len("/uploads/"):].lstrip("/")
    else:
        try:
            parsed = urllib.parse.urlparse(raw)
            if parsed.path.startswith("/uploads/"):
                info["is_absolute_upload"] = True
                upload_suffix = parsed.path[len("/uploads/"):].lstrip("/")
        except Exception:
            upload_suffix = ""

    info["upload_suffix"] = upload_suffix
    if upload_suffix:
        local_path = os.path.normpath(os.path.join(settings.UPLOAD_DIR, upload_suffix))
        info["local_path"] = local_path
        info["local_exists"] = bool(os.path.exists(local_path))
    return info


def _repair_shots_media_urls_from_assets(
    db: Session,
    current_user: User,
    project: Optional[Project],
    shots: List[Shot],
) -> List[Shot]:
    changed = False
    for shot in shots or []:
        if _repair_shot_media_urls_from_assets(db, current_user, project, shot):
            changed = True
    if changed:
        db.commit()
    return shots


def _refresh_managed_media_url(url: Any, db: Session) -> str:
    raw = str(url or "").strip()
    if not raw:
        return raw
    if not oss_storage_service.is_enabled(db):
        return raw
    try:
        return str(oss_storage_service.refresh_url(raw) or raw)
    except Exception:
        return raw


def _repair_stale_ephemeral_shot_media_notes(shot: Shot, db: Optional[Session] = None) -> bool:
    """Clear ephemeral persist flags when the stored URL is already on managed OSS."""
    if not shot:
        return False

    changed = False
    notes = _asset_meta_to_dict(getattr(shot, "technical_notes", None))
    if not isinstance(notes, dict):
        notes = {}

    def _repair_slot(
        media_url: str,
        meta_key: str,
        oss_flag_key: str,
    ) -> None:
        nonlocal changed
        url = str(media_url or "").strip()
        if not url:
            return
        slot_meta = dict(notes.get(meta_key) or {}) if isinstance(notes.get(meta_key), dict) else {}
        has_stale_flags = bool(
            slot_meta.get("ephemeral_binding")
            or slot_meta.get("needs_persistence_retry")
            or slot_meta.get("remote_localization_failed")
            or notes.get(oss_flag_key) is False
        )
        if not has_stale_flags:
            return
        if not (
            _is_persisted_media_localization_success(
                url,
                source_url=str(
                    slot_meta.get("remote_localization_source_url")
                    or slot_meta.get("pending_source_url")
                    or ""
                ).strip()
                or None,
                metadata=slot_meta,
                db=db,
            )
            or _is_durable_persisted_media_url(url, slot_meta, db)
        ):
            return
        notes[meta_key] = _clear_ephemeral_persist_flags(slot_meta)
        notes[oss_flag_key] = True
        changed = True

    _repair_slot(str(getattr(shot, "video_url", None) or "").strip(), "video_metadata", "video_oss_uploaded")
    _repair_slot(str(getattr(shot, "image_url", None) or "").strip(), "start_frame_metadata", "start_frame_oss_uploaded")
    _repair_slot(str(notes.get("end_frame_url") or "").strip(), "end_frame_metadata", "end_frame_oss_uploaded")

    if changed:
        if isinstance(getattr(shot, "technical_notes", None), dict):
            shot.technical_notes = notes
        else:
            shot.technical_notes = json.dumps(notes, ensure_ascii=False)
    return changed


def _refresh_shot_media_urls(shot: Shot, db: Session) -> Shot:
    if not shot:
        return shot

    shot.image_url = _refresh_managed_media_url(getattr(shot, "image_url", None), db)
    shot.video_url = _refresh_managed_media_url(getattr(shot, "video_url", None), db)

    notes = _asset_meta_to_dict(getattr(shot, "technical_notes", None))
    if notes:
        end_frame_url = str(notes.get("end_frame_url") or "").strip()
        refreshed_end = _refresh_managed_media_url(end_frame_url, db)
        if refreshed_end and refreshed_end != end_frame_url:
            notes["end_frame_url"] = refreshed_end
            if isinstance(shot.technical_notes, dict):
                shot.technical_notes = notes
            else:
                shot.technical_notes = json.dumps(notes, ensure_ascii=False)

    if _repair_stale_ephemeral_shot_media_notes(shot, db):
        try:
            db.add(shot)
            db.commit()
            db.refresh(shot)
        except Exception as exc:
            logger.warning(
                "[ShotMediaRepair] failed to persist stale ephemeral note cleanup | shot_id=%s err=%s",
                getattr(shot, "id", None),
                exc,
            )
            try:
                db.rollback()
            except Exception:
                pass
    return shot


def _resolve_local_upload_path_from_media_url(url: Any) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""

    upload_suffix = ""
    if raw.startswith("/uploads/"):
        upload_suffix = raw[len("/uploads/"):].lstrip("/")
    else:
        try:
            parsed = urllib.parse.urlparse(raw)
            if parsed.path.startswith("/uploads/"):
                upload_suffix = parsed.path[len("/uploads/"):].lstrip("/")
        except Exception:
            upload_suffix = ""

    if not upload_suffix:
        return ""

    upload_root = os.path.abspath(settings.UPLOAD_DIR)
    file_path = os.path.abspath(os.path.join(upload_root, upload_suffix))
    try:
        if os.path.commonpath([upload_root, file_path]) != upload_root:
            return ""
    except ValueError:
        return ""
    return file_path if os.path.exists(file_path) else ""


def _sanitize_zip_entry_token(value: Any, fallback: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z._-]+", "_", str(value or "").strip()).strip("._-")
    return normalized or fallback


def _build_shot_video_zip_entry_name(shot: Shot, index: int, video_url: str) -> str:
    scene_token = _sanitize_zip_entry_token(getattr(shot, "scene_code", None) or f"scene_{getattr(shot, 'scene_id', index) or index}", f"scene_{index}")
    shot_token = _sanitize_zip_entry_token(getattr(shot, "shot_id", None) or getattr(shot, "shot_name", None) or f"shot_{index}", f"shot_{index}")
    ext = ".mp4"
    try:
        parsed = urllib.parse.urlparse(str(video_url or "").strip())
        candidate = os.path.splitext(parsed.path or "")[1].strip().lower()
        if candidate and len(candidate) <= 8:
            ext = candidate
    except Exception:
        ext = ".mp4"
    return f"{index:03d}_{scene_token}_{shot_token}{ext}"


def _cleanup_temp_download_file(file_path: str) -> None:
    stable_path = str(file_path or "").strip()
    if not stable_path:
        return
    try:
        if os.path.exists(stable_path):
            os.remove(stable_path)
    except Exception as exc:
        logger.warning("Failed to cleanup temporary download file path=%s error=%s", stable_path, exc)


def _replace_legacy_temp_urls_in_shot_payload(
    db: Session,
    current_user: User,
    project: Optional[Project],
    shot: Shot,
    update_data: Dict[str, Any],
) -> Dict[str, Any]:
    patched = dict(update_data or {})

    image_url = patched.get("image_url")
    if _is_ephemeral_provider_media_url(image_url):
        resolved_image_url = _resolve_precise_asset_library_url(
            db,
            current_user,
            image_url,
            project=project,
            shot_id=getattr(shot, "id", None),
            asset_type_aliases={"start_frame", "start"},
            media_type="image",
        )
        if resolved_image_url:
            patched["image_url"] = resolved_image_url

    raw_technical_notes = patched.get("technical_notes")
    if raw_technical_notes is not None:
        notes = _asset_meta_to_dict(raw_technical_notes)
        end_frame_url = notes.get("end_frame_url")
        if _is_ephemeral_provider_media_url(end_frame_url):
            resolved_end_frame_url = _resolve_precise_asset_library_url(
                db,
                current_user,
                end_frame_url,
                project=project,
                shot_id=getattr(shot, "id", None),
                asset_type_aliases={"end_frame", "end"},
                media_type="image",
            )
            if resolved_end_frame_url:
                notes["end_frame_url"] = resolved_end_frame_url
                patched["technical_notes"] = notes if isinstance(raw_technical_notes, dict) else json.dumps(notes, ensure_ascii=False)

    video_url = patched.get("video_url")
    if _is_ephemeral_provider_media_url(video_url):
        resolved_video_url = _resolve_precise_asset_library_url(
            db,
            current_user,
            video_url,
            project=project,
            shot_id=getattr(shot, "id", None),
            asset_type_aliases={"video"},
            media_type="video",
        )
        if resolved_video_url:
            patched["video_url"] = resolved_video_url

    return patched


class ShotPersistMediaRequest(BaseModel):
    slot: str = "video"
    source_url: Optional[str] = None


class ShotVideoCleanupRequest(BaseModel):
    action: str  # remove_subtitle | remove_bgm | remove_subtitle_and_bgm
    source_url: Optional[str] = None


def _resolve_shot_media_slot_url(shot: Shot, slot: str) -> Tuple[str, str, Dict[str, Any], Dict[str, Any]]:
    normalized_slot = str(slot or "video").strip().lower()
    notes = _asset_meta_to_dict(getattr(shot, "technical_notes", None))

    if normalized_slot in {"start", "start_frame"}:
        return (
            str(getattr(shot, "image_url", None) or "").strip(),
            "start_frame",
            notes,
            dict(notes.get("start_frame_metadata") or {}) if isinstance(notes.get("start_frame_metadata"), dict) else {},
        )
    if normalized_slot in {"end", "end_frame"}:
        return (
            str(notes.get("end_frame_url") or "").strip(),
            "end_frame",
            notes,
            dict(notes.get("end_frame_metadata") or {}) if isinstance(notes.get("end_frame_metadata"), dict) else {},
        )
    if normalized_slot == "video":
        return (
            str(getattr(shot, "video_url", None) or "").strip(),
            "video",
            notes,
            dict(notes.get("video_metadata") or {}) if isinstance(notes.get("video_metadata"), dict) else {},
        )
    raise HTTPException(status_code=400, detail=f"Unsupported media slot: {slot}")


def _persist_shot_media_slot(
    db: Session,
    current_user: User,
    project: Project,
    shot: Shot,
    *,
    slot: str = "video",
    source_url_override: Optional[str] = None,
) -> Dict[str, Any]:
    source_url, asset_type, notes, slot_meta = _resolve_shot_media_slot_url(shot, slot)
    if source_url_override:
        source_url = str(source_url_override or "").strip()

    if not source_url:
        raise HTTPException(status_code=400, detail=f"Shot has no URL for slot={slot}")

    if _is_persisted_media_localization_success(
        source_url,
        source_url=source_url,
        metadata=slot_meta,
        db=db,
    ) or _is_durable_persisted_media_url(source_url, slot_meta, db):
        oss_ok = _oss_upload_succeeded_for_url(source_url, slot_meta, db) or _is_persisted_media_localization_success(
            source_url,
            source_url=source_url,
            metadata=slot_meta,
            db=db,
        )
        if oss_ok and asset_type == "video":
            clean_meta = _clear_ephemeral_persist_flags(dict(slot_meta or {}))
            clean_meta["oss_uploaded_success"] = True
            _bind_generated_media_to_shot(
                db,
                current_user,
                {
                    "shot_id": int(shot.id),
                    "project_id": int(getattr(shot, "project_id", None) or getattr(project, "id", None) or 0) or None,
                    "episode_id": getattr(shot, "episode_id", None),
                    "shot_number": getattr(shot, "shot_id", None),
                    "shot_name": getattr(shot, "shot_name", None),
                    "asset_type": asset_type,
                },
                source_url,
                True,
                clean_meta,
            )
            db.refresh(shot)
        return {
            "shot_id": int(shot.id),
            "slot": asset_type,
            "source_url": source_url,
            "persisted_url": source_url,
            "oss_uploaded": oss_ok,
            "already_persisted": True,
            "metadata": slot_meta or None,
        }

    req_context: Dict[str, Any] = {
        "shot_id": int(shot.id),
        "project_id": int(getattr(shot, "project_id", None) or getattr(project, "id", None) or 0) or None,
        "episode_id": getattr(shot, "episode_id", None),
        "shot_number": getattr(shot, "shot_id", None),
        "shot_name": getattr(shot, "shot_name", None),
        "asset_type": asset_type,
    }
    filename_base = _build_persist_filename_base_from_context(req_context, db)

    if asset_type == "video":
        normalized_url, normalized_meta, oss_uploaded = _persist_remote_video_result(
            current_user,
            source_url,
            slot_meta,
            filename_base=filename_base,
            db=db,
        )
    else:
        normalized_url, normalized_meta = _persist_remote_image_result(
            current_user,
            source_url,
            slot_meta,
            db=db,
        )
        normalized_meta = dict(normalized_meta or {})
        oss_uploaded = _oss_upload_succeeded_for_url(normalized_url, normalized_meta, db)

    normalized_url = str(normalized_url or "").strip() or source_url
    normalized_meta = dict(normalized_meta or {})

    bind_url, ephemeral_binding, normalized_meta = _resolve_video_bind_url(
        raw_url=source_url,
        normalized_url=normalized_url,
        normalized_meta=normalized_meta,
        oss_uploaded=oss_uploaded,
        db=db,
    )

    localization_ok = _is_persisted_media_localization_success(
        normalized_url,
        source_url=source_url,
        metadata=normalized_meta,
        db=db,
        oss_uploaded=oss_uploaded,
    )
    if localization_ok:
        final_url = normalized_url
        normalized_meta = _clear_ephemeral_persist_flags(normalized_meta)
        ephemeral_binding = False
    elif bind_url and _is_persisted_media_localization_success(
        bind_url,
        source_url=source_url,
        metadata=normalized_meta,
        db=db,
        oss_uploaded=oss_uploaded,
    ):
        final_url = bind_url
        ephemeral_binding = False
    elif bind_url:
        final_url = bind_url
    else:
        final_url = normalized_url or source_url

    if not _is_persisted_media_localization_success(
        final_url,
        source_url=source_url,
        metadata=normalized_meta,
        db=db,
        oss_uploaded=oss_uploaded,
    ):
        error_detail = str(
            normalized_meta.get("remote_localization_error")
            or "Failed to persist media to durable storage (OSS/local)"
        ).strip()
        raise HTTPException(
            status_code=502,
            detail=error_detail,
        )

    bind_oss_flag = bool(
        (oss_uploaded or _oss_upload_succeeded_for_url(final_url, normalized_meta, db))
        and not ephemeral_binding
        and not _is_ephemeral_provider_media_url(final_url)
    )
    if bind_oss_flag:
        normalized_meta = _clear_ephemeral_persist_flags(normalized_meta)
        normalized_meta["oss_uploaded_success"] = True

    try:
        _register_asset_helper(db, current_user.id, final_url, req_context, normalized_meta)
    except Exception as reg_exc:
        logger.warning("[ShotMediaPersist] register asset failed | shot_id=%s slot=%s err=%s", shot.id, asset_type, reg_exc)

    _bind_generated_media_to_shot(
        db,
        current_user,
        req_context,
        final_url,
        bind_oss_flag,
        normalized_meta,
    )

    db.refresh(shot)
    return {
        "shot_id": int(shot.id),
        "slot": asset_type,
        "source_url": source_url,
        "persisted_url": final_url,
        "oss_uploaded": bind_oss_flag,
        "already_persisted": False,
        "metadata": normalized_meta or None,
    }


class EntityPersistMediaRequest(BaseModel):
    source_url: Optional[str] = None


def _persist_entity_image(
    db: Session,
    current_user: User,
    project: Project,
    entity: Entity,
    *,
    source_url_override: Optional[str] = None,
) -> Dict[str, Any]:
    source_url = str(source_url_override or getattr(entity, "image_url", None) or "").strip()
    if not source_url:
        raise HTTPException(status_code=400, detail="Entity has no image URL")

    attrs = _asset_meta_to_dict(getattr(entity, "custom_attributes", None))
    slot_meta = dict(attrs or {})

    if _is_durable_persisted_media_url(source_url, slot_meta, db):
        return {
            "entity_id": int(entity.id),
            "source_url": source_url,
            "persisted_url": source_url,
            "oss_uploaded": _oss_upload_succeeded_for_url(source_url, slot_meta, db),
            "already_persisted": True,
            "metadata": slot_meta or None,
        }

    entity_type = str(getattr(entity, "type", None) or "subject").strip().lower()
    req_context: Dict[str, Any] = {
        "entity_id": int(entity.id),
        "project_id": int(getattr(project, "id", None) or getattr(entity, "project_id", None) or 0) or None,
        "entity_name": getattr(entity, "name", None),
        "subject_name": getattr(entity, "name", None),
        "entity_type": entity_type,
        "asset_type": "subject",
        "category": entity_type,
    }

    normalized_url, normalized_meta = _persist_remote_image_result(
        current_user,
        source_url,
        slot_meta,
        db=db,
    )
    normalized_meta = dict(normalized_meta or {})
    oss_uploaded = _oss_upload_succeeded_for_url(normalized_url, normalized_meta, db)

    bind_url, ephemeral_binding, normalized_meta = _resolve_video_bind_url(
        raw_url=source_url,
        normalized_url=str(normalized_url or "").strip() or None,
        normalized_meta=normalized_meta,
    )

    final_url = str(normalized_url or "").strip()
    if final_url and _is_durable_persisted_media_url(final_url, normalized_meta, db):
        bind_url = final_url
        ephemeral_binding = False
    elif bind_url and _is_durable_persisted_media_url(bind_url, normalized_meta, db):
        final_url = bind_url
        ephemeral_binding = False
    elif bind_url:
        final_url = bind_url
    else:
        final_url = normalized_url or source_url

    if not _is_durable_persisted_media_url(final_url, normalized_meta, db):
        error_detail = str(
            normalized_meta.get("remote_localization_error")
            or "Failed to persist entity image to durable storage (OSS/local)"
        ).strip()
        raise HTTPException(status_code=502, detail=error_detail)

    try:
        _register_asset_helper(db, current_user.id, final_url, req_context, normalized_meta)
    except Exception as reg_exc:
        logger.warning("[EntityMediaPersist] register asset failed | entity_id=%s err=%s", entity.id, reg_exc)

    _bind_generated_media_to_entity(
        db,
        current_user,
        req_context,
        final_url,
        bool(oss_uploaded and not ephemeral_binding),
    )

    db.refresh(entity)
    return {
        "entity_id": int(entity.id),
        "source_url": source_url,
        "persisted_url": final_url,
        "oss_uploaded": bool(oss_uploaded and not ephemeral_binding),
        "already_persisted": False,
        "metadata": normalized_meta or None,
    }



# video job file I/O -> generation_runtime.job_store

