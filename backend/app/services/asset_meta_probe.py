"""Probe width/height/duration/size metadata for image and video assets."""

from __future__ import annotations

import io
import logging
import math
import os
import tempfile
import urllib.parse
from typing import Any, Dict, Optional

import requests
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")
_VIDEO_EXTENSIONS = (".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv")
_AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus")


def infer_media_kind(url: str, asset_type: Optional[str] = None) -> str:
    explicit = str(asset_type or "").strip().lower()
    if explicit in {"image", "video", "audio"}:
        return explicit

    parsed_path = urllib.parse.urlparse(str(url or "")).path.lower()
    if parsed_path.endswith(_IMAGE_EXTENSIONS):
        return "image"
    if parsed_path.endswith(_VIDEO_EXTENSIONS):
        return "video"
    if parsed_path.endswith(_AUDIO_EXTENSIONS):
        return "audio"
    return "unknown"


def resolve_local_upload_path(url: str) -> Optional[str]:
    raw = str(url or "").strip()
    if not raw:
        return None

    parsed_path = urllib.parse.urlparse(raw).path
    if not parsed_path.startswith("/uploads/"):
        return None

    rel_path = parsed_path[len("/uploads/") :]
    file_path = os.path.join(settings.UPLOAD_DIR, rel_path)
    return file_path if os.path.isfile(file_path) else None


def asset_meta_needs_probe(meta: Optional[Dict[str, Any]], media_kind: str) -> bool:
    data = dict(meta or {})
    if media_kind in {"image", "video"}:
        width = _safe_positive_int(data.get("width"))
        height = _safe_positive_int(data.get("height"))
        if not width or not height:
            return True
    if media_kind == "video" and data.get("duration") in (None, "", 0):
        return True
    if not data.get("size") and not data.get("file_size_bytes"):
        return True
    return False


def merge_probed_meta(
    existing: Optional[Dict[str, Any]],
    probed: Optional[Dict[str, Any]],
    *,
    overwrite: bool = False,
) -> Dict[str, Any]:
    merged = dict(existing or {})
    for key, value in (probed or {}).items():
        if value in (None, ""):
            continue
        if overwrite or key not in merged or merged.get(key) in (None, "", 0):
            merged[key] = value
    ensure_resolution_fields(merged)
    return merged


def ensure_resolution_fields(meta: Dict[str, Any]) -> None:
    width = _safe_positive_int(meta.get("width"))
    height = _safe_positive_int(meta.get("height"))
    if not width or not height:
        return

    if not meta.get("resolution"):
        meta["resolution"] = f"{width}x{height}"

    if meta.get("aspect_ratio"):
        return

    gcd = math.gcd(width, height)
    rw, rh = width // gcd, height // gcd
    ratio_map = {
        (16, 9): "16:9",
        (9, 16): "9:16",
        (4, 3): "4:3",
        (3, 4): "3:4",
        (1, 1): "1:1",
        (21, 9): "21:9",
        (3, 2): "3:2",
        (2, 3): "2:3",
    }
    if (rw, rh) in ratio_map:
        meta["aspect_ratio"] = ratio_map[(rw, rh)]
        return

    float_ratio = width / height
    ratios_target = {
        "16:9": 16 / 9,
        "9:16": 9 / 16,
        "4:3": 4 / 3,
        "3:4": 3 / 4,
        "1:1": 1.0,
        "21:9": 21 / 9,
        "3:2": 3 / 2,
        "2:3": 2 / 3,
    }
    for ratio_name, ratio_val in ratios_target.items():
        if abs(float_ratio - ratio_val) < 0.05:
            meta["aspect_ratio"] = ratio_name
            return
    meta["aspect_ratio"] = f"{rw}:{rh}"


def enrich_asset_meta_info(
    meta: Optional[Dict[str, Any]],
    *,
    url: str,
    media_kind: Optional[str] = None,
    local_path: Optional[str] = None,
    overwrite: bool = False,
) -> Dict[str, Any]:
    merged = dict(meta or {})
    kind = infer_media_kind(url, media_kind or merged.get("type") or merged.get("asset_type"))
    if kind == "unknown":
        explicit_type = str(media_kind or merged.get("type") or "").strip().lower()
        if explicit_type in {"image", "video", "audio"}:
            kind = explicit_type

    if not asset_meta_needs_probe(merged, kind if kind != "unknown" else "image"):
        ensure_resolution_fields(merged)
        return merged

    probed: Dict[str, Any] = {}
    resolved_path = local_path or resolve_local_upload_path(url)
    if resolved_path and os.path.isfile(resolved_path):
        probed = probe_media_from_path(resolved_path, kind)
    elif kind in {"image", "video", "audio", "unknown"}:
        probed = probe_media_from_url(url, kind if kind != "unknown" else infer_media_kind(url))

    return merge_probed_meta(merged, probed, overwrite=overwrite)


def probe_media_from_path(file_path: str, media_kind: Optional[str] = None) -> Dict[str, Any]:
    kind = media_kind or infer_media_kind(file_path)
    probed: Dict[str, Any] = {}
    try:
        size_val = os.path.getsize(file_path)
        if size_val > 0:
            _apply_file_size(probed, size_val)
    except OSError:
        pass

    if kind == "image" or (kind == "unknown" and _looks_like_image_path(file_path)):
        probed.update(_probe_image_path(file_path))
    elif kind == "video" or (kind == "unknown" and _looks_like_video_path(file_path)):
        probed.update(_probe_video_path(file_path))
    ensure_resolution_fields(probed)
    return probed


def probe_media_from_url(url: str, media_kind: Optional[str] = None) -> Dict[str, Any]:
    raw_url = str(url or "").strip()
    if not raw_url.lower().startswith(("http://", "https://")):
        return {}

    kind = media_kind or infer_media_kind(raw_url)
    probed: Dict[str, Any] = {}

    try:
        head = requests.head(raw_url, timeout=8, allow_redirects=True)
        content_length = head.headers.get("Content-Length")
        if content_length:
            _apply_file_size(probed, content_length)
    except Exception:
        pass

    if kind == "image" or (kind == "unknown" and infer_media_kind(raw_url) == "image"):
        probed.update(_probe_remote_image(raw_url))
    elif kind == "video" or (kind == "unknown" and infer_media_kind(raw_url) == "video"):
        probed.update(_probe_remote_video(raw_url))

    ensure_resolution_fields(probed)
    return probed


def _probe_image_path(file_path: str) -> Dict[str, Any]:
    probed: Dict[str, Any] = {}
    try:
        with Image.open(file_path) as img:
            probed["width"] = int(img.width)
            probed["height"] = int(img.height)
            if img.format:
                probed["format"] = str(img.format)
    except Exception as exc:
        logger.warning("image metadata probe failed path=%s err=%s", file_path, exc)
    return probed


def _probe_video_path(file_path: str) -> Dict[str, Any]:
    probed: Dict[str, Any] = {}
    try:
        from moviepy import VideoFileClip

        with VideoFileClip(file_path) as clip:
            if clip.w and clip.h:
                probed["width"] = int(clip.w)
                probed["height"] = int(clip.h)
            if clip.duration:
                probed["duration"] = float(clip.duration)
    except Exception as moviepy_exc:
        logger.info("moviepy video probe failed path=%s err=%s", file_path, moviepy_exc)
        probed.update(_probe_video_with_imageio(file_path))
    return probed


def _probe_video_with_imageio(source: str) -> Dict[str, Any]:
    probed: Dict[str, Any] = {}
    reader = None
    try:
        import imageio

        reader = imageio.get_reader(source)
        meta = reader.get_meta_data() if hasattr(reader, "get_meta_data") else {}
        size = meta.get("size") if isinstance(meta, dict) else None
        if isinstance(size, (list, tuple)) and len(size) >= 2:
            probed["width"] = int(size[0])
            probed["height"] = int(size[1])
        duration = meta.get("duration") if isinstance(meta, dict) else None
        if duration:
            probed["duration"] = float(duration)
    except Exception as exc:
        logger.warning("imageio video probe failed source=%s err=%s", source, exc)
    finally:
        if reader is not None:
            try:
                reader.close()
            except Exception:
                pass
    return probed


def _probe_remote_image(url: str) -> Dict[str, Any]:
    probed: Dict[str, Any] = {}
    max_probe_bytes = max(
        128 * 1024,
        int(os.getenv("ASSET_REMOTE_META_PROBE_MAX_BYTES", str(2 * 1024 * 1024)) or (2 * 1024 * 1024)),
    )
    try:
        resp = requests.get(url, timeout=12, stream=True, headers={"User-Agent": "Mozilla/5.0"})
        content_len = int(resp.headers.get("Content-Length") or 0)
        if content_len > 0:
            _apply_file_size(probed, content_len)
        if content_len and content_len > max_probe_bytes:
            resp.close()
            return probed
        if not resp.ok:
            resp.close()
            return probed

        probe = bytearray()
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            probe.extend(chunk)
            if len(probe) > max_probe_bytes:
                break
        resp.close()
        if probe:
            with Image.open(io.BytesIO(bytes(probe))) as img:
                probed["width"] = int(img.width)
                probed["height"] = int(img.height)
                if img.format:
                    probed["format"] = str(img.format)
    except Exception as exc:
        logger.warning("remote image metadata probe failed url=%s err=%s", url, exc)
    return probed


def _probe_remote_video(url: str) -> Dict[str, Any]:
    probed: Dict[str, Any] = {}
    max_download_mb = max(1, int(os.getenv("ASSET_REMOTE_VIDEO_META_PROBE_MAX_MB", "64") or 64))
    max_download_bytes = max_download_mb * 1024 * 1024

    try:
        import imageio

        reader = imageio.get_reader(url)
        meta = reader.get_meta_data() if hasattr(reader, "get_meta_data") else {}
        size = meta.get("size") if isinstance(meta, dict) else None
        if isinstance(size, (list, tuple)) and len(size) >= 2:
            probed["width"] = int(size[0])
            probed["height"] = int(size[1])
        duration = meta.get("duration") if isinstance(meta, dict) else None
        if duration:
            probed["duration"] = float(duration)
        reader.close()
        if probed.get("width") and probed.get("height"):
            return probed
    except Exception as exc:
        logger.info("direct remote video probe failed url=%s err=%s", url, exc)

    temp_path = None
    try:
        resp = requests.get(url, timeout=30, stream=True, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        suffix = os.path.splitext(urllib.parse.urlparse(url).path)[1] or ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = tmp.name
            downloaded = 0
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                downloaded += len(chunk)
                if downloaded > max_download_bytes:
                    break
                tmp.write(chunk)
        resp.close()
        if temp_path and os.path.getsize(temp_path) > 0:
            probed.update(_probe_video_path(temp_path))
            if downloaded <= max_download_bytes:
                _apply_file_size(probed, os.path.getsize(temp_path))
    except Exception as exc:
        logger.warning("remote video metadata probe failed url=%s err=%s", url, exc)
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
    return probed


def _apply_file_size(target: Dict[str, Any], bytes_size: Any) -> None:
    try:
        size_val = int(bytes_size)
    except Exception:
        return
    if size_val <= 0:
        return
    target["size"] = size_val
    target["file_size_bytes"] = size_val
    if size_val >= 1024 * 1024:
        display = f"{size_val / 1024 / 1024:.2f} MB"
    else:
        display = f"{size_val / 1024:.2f} KB"
    target["size_display"] = display
    target["file_size_display"] = display


def _safe_positive_int(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except Exception:
        return None
    return parsed if parsed > 0 else None


def _looks_like_image_path(path: str) -> bool:
    return str(path or "").lower().endswith(_IMAGE_EXTENSIONS)


def _looks_like_video_path(path: str) -> bool:
    return str(path or "").lower().endswith(_VIDEO_EXTENSIONS)
