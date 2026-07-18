"""Best-effort cleanup for local upload files and managed OSS URLs."""

from __future__ import annotations

import logging
import os
import urllib.parse
from typing import Iterable, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def _to_upload_path(url_or_path: str, upload_root: str) -> Optional[str]:
    raw = str(url_or_path or "").strip()
    if not raw:
        return None
    try:
        parsed = urllib.parse.urlparse(raw)
        path_part = parsed.path if parsed.scheme else raw
    except Exception:
        path_part = raw
    path_part = urllib.parse.unquote(path_part).lstrip("/")
    if path_part.startswith("uploads/"):
        rel = path_part.replace("uploads/", "", 1)
    elif "/uploads/" in path_part:
        rel = path_part.split("/uploads/", 1)[1]
    else:
        rel = path_part
    abs_path = os.path.abspath(os.path.join(upload_root, rel))
    try:
        if os.path.commonpath([upload_root, abs_path]) != upload_root:
            return None
    except Exception:
        return None
    return abs_path


def cleanup_media_files(urls: Iterable[str]) -> dict:
    """Delete local /uploads files and managed OSS objects referenced by URLs."""
    unique_urls: List[str] = []
    seen = set()
    for item in urls or []:
        raw = str(item or "").strip()
        if not raw or raw in seen:
            continue
        seen.add(raw)
        unique_urls.append(raw)

    result = {"requested": len(unique_urls), "oss_deleted": 0, "local_deleted": 0, "errors": 0}
    if not unique_urls:
        return result

    upload_root = settings.UPLOAD_DIR
    if not os.path.isabs(upload_root):
        upload_root = os.path.abspath(upload_root)

    try:
        from app.services.oss_storage_service import oss_storage_service
    except Exception as exc:
        logger.warning("media cleanup: OSS service unavailable: %s", exc)
        oss_storage_service = None

    for raw_url in unique_urls:
        try:
            if oss_storage_service is not None and oss_storage_service.is_managed_url(raw_url):
                if oss_storage_service.delete_url(raw_url):
                    result["oss_deleted"] += 1
                continue
            path = _to_upload_path(raw_url, upload_root)
            if path and os.path.isfile(path):
                os.remove(path)
                result["local_deleted"] += 1
        except Exception as exc:
            result["errors"] += 1
            logger.warning("media cleanup failed for %s: %s", raw_url, exc)
    return result
