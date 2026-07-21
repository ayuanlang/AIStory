# -*- coding: utf-8 -*-
"""Shared asset meta / denormalized field helpers."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from app.models.all_models import Asset


def _asset_meta_dict(raw_meta: Any) -> Dict[str, Any]:
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


def _asset_optional_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        raw = str(value).strip()
        if not raw:
            return None
        return int(raw)
    except Exception:
        return None


def _sync_asset_denormalized_fields(asset: Optional[Asset]) -> Optional[Asset]:
    if asset is None:
        return None
    meta = _asset_meta_dict(getattr(asset, "meta_info", None))
    if "project_id" in meta:
        asset.project_id = _asset_optional_int(meta.get("project_id"))
    elif getattr(asset, "project_id", None) is None:
        asset.project_id = _asset_optional_int(meta.get("project_id"))

    if "episode_id" in meta:
        asset.episode_id = _asset_optional_int(meta.get("episode_id"))
    elif getattr(asset, "episode_id", None) is None:
        asset.episode_id = _asset_optional_int(meta.get("episode_id"))
    return asset

