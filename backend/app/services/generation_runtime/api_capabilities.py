# -*- coding: utf-8 -*-
"""API capability flag / enum mapping helpers for generation."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.effective_api_setting import _safe_json_dict


def _coerce_capability_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return None


def _iter_api_capability_containers(api_config: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    payload = api_config if isinstance(api_config, dict) else {}
    modality = _safe_json_dict(payload.get("modality"))
    containers: List[Dict[str, Any]] = []
    for raw in (
        modality.get("capability_flags"),
        modality.get("image_capabilities"),
        modality.get("video_capabilities"),
        modality.get("text_capabilities"),
        modality.get("digital_human_capabilities"),
        modality.get("voice_capabilities"),
        modality.get("music_capabilities"),
        modality,
    ):
        container = _safe_json_dict(raw)
        if container:
            containers.append(container)
    return containers


def _read_api_capability_bool(api_config: Optional[Dict[str, Any]], *keys: str) -> Optional[bool]:
    normalized_keys = [str(key or "").strip() for key in keys if str(key or "").strip()]
    if not normalized_keys:
        return None
    for container in _iter_api_capability_containers(api_config):
        for key in normalized_keys:
            value = _coerce_capability_bool(container.get(key))
            if value is not None:
                return value
    return None


def _read_api_capability_int(api_config: Optional[Dict[str, Any]], *keys: str) -> Optional[int]:
    normalized_keys = [str(key or "").strip() for key in keys if str(key or "").strip()]
    if not normalized_keys:
        return None
    for container in _iter_api_capability_containers(api_config):
        for key in normalized_keys:
            value = container.get(key)
            if value is None or str(value).strip() == "":
                continue
            try:
                parsed = int(float(value))
            except Exception:
                continue
            if parsed >= 0:
                return parsed
    return None


def _read_api_capability_number(api_config: Optional[Dict[str, Any]], *keys: str) -> Optional[float]:
    normalized_keys = [str(key or "").strip() for key in keys if str(key or "").strip()]
    if not normalized_keys:
        return None
    for container in _iter_api_capability_containers(api_config):
        for key in normalized_keys:
            value = container.get(key)
            if value is None or str(value).strip() == "":
                continue
            try:
                return float(value)
            except Exception:
                continue
    return None


def _read_api_capability_list(api_config: Optional[Dict[str, Any]], *keys: str) -> List[str]:
    normalized_keys = [str(key or "").strip() for key in keys if str(key or "").strip()]
    if not normalized_keys:
        return []
    for container in _iter_api_capability_containers(api_config):
        for key in normalized_keys:
            raw = container.get(key)
            if raw is None:
                continue
            if isinstance(raw, list):
                values = [str(item).strip() for item in raw if str(item).strip()]
            else:
                text = str(raw).strip()
                if not text:
                    values = []
                else:
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, list):
                            values = [str(item).strip() for item in parsed if str(item).strip()]
                        else:
                            values = [seg.strip() for seg in text.replace("\n", ",").split(",") if seg.strip()]
                    except Exception:
                        values = [seg.strip() for seg in text.replace("\n", ",").split(",") if seg.strip()]
            if values:
                deduped: List[str] = []
                seen = set()
                for item in values:
                    key_text = item.lower()
                    if key_text in seen:
                        continue
                    seen.add(key_text)
                    deduped.append(item)
                return deduped
    return []


def _read_api_capability_int_list(api_config: Optional[Dict[str, Any]], *keys: str) -> List[int]:
    values: List[int] = []
    seen = set()
    for item in _read_api_capability_list(api_config, *keys):
        try:
            parsed = int(float(item))
        except Exception:
            continue
        if parsed <= 0 or parsed in seen:
            continue
        seen.add(parsed)
        values.append(parsed)
    return sorted(values)


def _normalize_capability_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").strip().lower())


def _map_text_value_to_allowed(requested: Any, allowed_values: Any) -> Optional[str]:
    allowed = [str(item).strip() for item in (allowed_values or []) if str(item).strip()]
    if not allowed:
        return None
    req_text = str(requested or "").strip()
    if not req_text:
        return None
    exact_map = {item.lower(): item for item in allowed}
    req_lower = req_text.lower()
    if req_lower in exact_map:
        return exact_map[req_lower]
    req_token = _normalize_capability_token(req_text)
    if req_token:
        token_map = {_normalize_capability_token(item): item for item in allowed}
        mapped = token_map.get(req_token)
        if mapped:
            return mapped
    return allowed[0]


def _map_int_value_to_allowed(requested: Any, allowed_values: Any) -> Optional[int]:
    allowed: List[int] = []
    for item in allowed_values or []:
        try:
            parsed = int(float(item))
        except Exception:
            continue
        if parsed > 0:
            allowed.append(parsed)
    allowed = sorted(set(allowed))
    if not allowed:
        return None
    try:
        target = int(float(requested))
    except Exception:
        return allowed[0]
    return int(min(allowed, key=lambda current: (abs(current - target), current)))


def _parse_resolution_tier(value: Any) -> Optional[int]:
    text = str(value or "").strip().lower().replace(" ", "")
    if not text:
        return None
    match = re.match(r"^(\d+)(?:p)?$", text)
    if match:
        try:
            parsed = int(match.group(1))
        except Exception:
            return None
        return parsed if parsed > 0 else None
    match = re.match(r"^(\d+)[x:](\d+)$", text)
    if match:
        try:
            first = int(match.group(1))
            second = int(match.group(2))
        except Exception:
            return None
        if first > 0 and second > 0:
            return min(first, second)
        return None
    match = re.match(r"^(\d+(?:\.\d+)?)k$", text)
    if match:
        try:
            return int(float(match.group(1)) * 1000)
        except Exception:
            return None
    return None


def _map_resolution_to_allowed(requested: Any, allowed_values: Any) -> Optional[str]:
    allowed = [str(item).strip() for item in (allowed_values or []) if str(item).strip()]
    if not allowed:
        return None
    req_text = str(requested or "").strip()
    if not req_text:
        return None
    exact_map = {item.lower(): item for item in allowed}
    req_lower = req_text.lower()
    if req_lower in exact_map:
        return exact_map[req_lower]
    req_num = _parse_resolution_tier(req_text)
    numeric_allowed: List[Tuple[str, int]] = []
    for item in allowed:
        parsed = _parse_resolution_tier(item)
        if parsed is None:
            continue
        numeric_allowed.append((item, int(parsed)))
    if req_num is None or not numeric_allowed:
        return allowed[0]
    lower_or_equal = [pair for pair in numeric_allowed if pair[1] <= int(req_num)]
    if lower_or_equal:
        best_val = max(pair[1] for pair in lower_or_equal)
        for item, val in lower_or_equal:
            if val == best_val:
                return item
    min_val = min(pair[1] for pair in numeric_allowed)
    for item, val in numeric_allowed:
        if val == min_val:
            return item
    return allowed[0]

def _resolve_video_submit_image_urls(req: Any) -> List[str]:
    if isinstance(getattr(req, "image_urls", None), list):
        urls = [str(x).strip() for x in req.image_urls if str(x).strip()]
        if urls:
            return urls
    ref_value = getattr(req, "ref_image_url", None)
    if isinstance(ref_value, list):
        return [str(x).strip() for x in ref_value if str(x).strip()]
    if isinstance(ref_value, str) and ref_value.strip():
        return [ref_value.strip()]
    return []


def _limit_media_ref_input(value: Any, limit: Optional[int]) -> Any:
    if limit is None:
        return value
    if limit <= 0:
        return [] if isinstance(value, list) else None
    if isinstance(value, list):
        refs = [str(item).strip() for item in value if str(item).strip()]
        return refs[:limit]
    text = str(value or "").strip()
    if not text:
        return value
    return text if limit >= 1 else None


def _limit_string_list_input(value: Any, limit: Optional[int]) -> List[str]:
    if isinstance(value, list):
        values = [str(item).strip() for item in value if str(item).strip()]
    else:
        values = []
    if limit is None:
        return values
    if limit <= 0:
        return []
    return values[:limit]

