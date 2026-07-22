# -*- coding: utf-8 -*-
"""Video/image ref resolution, Kling element merge, and submit payload prep."""
from __future__ import annotations

import json
import logging
import os
import re
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.entity_token import (
    entity_subject_keys_match,
    extract_entity_raw_names_from_prompt,
    normalize_entity_token,
    subject_compare_key_variants,
)
from app.db.session import SessionLocal
from app.models.all_models import Entity, Episode, Shot
from app.services.effective_api_setting import _safe_json_dict
from app.services.generation_runtime.api_capabilities import _resolve_video_submit_image_urls
from app.services.soft_delete import _active_entity_clause
from app.services.system_api_lookup import get_system_api_setting

logger = logging.getLogger("api_logger")


def _to_positive_int_or_none(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        parsed = int(value)
        return parsed if parsed > 0 else None
    except Exception:
        return None


def _parse_shot_tech(shot: Shot) -> Dict[str, Any]:
    try:
        payload = json.loads(shot.technical_notes or "{}")
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return {}


def _normalize_entity_anchor_token(value: Any) -> str:
    return normalize_entity_token(value)


def _entity_lookup_alias_keys(*raw_names: Any) -> set:
    """Build lookup aliases aligned with frontend entityTokenMatchesName."""
    keys: set = set()
    for raw in raw_names:
        text = str(raw or "").strip()
        if not text:
            continue
        normalized = _normalize_entity_anchor_token(text)
        if normalized:
            keys.add(normalized)
            base = normalized.split("(")[0].strip()
            if base:
                keys.add(base)
        for compare_key in subject_compare_key_variants(text):
            if compare_key:
                keys.add(compare_key)
    return {key for key in keys if key}


def _build_project_entity_lookup(
    db: Session,
    project_id: int,
    episode_id: Optional[int] = None,
) -> Dict[str, Dict[str, Any]]:
    """Build name→entity lookup for video/image ref resolution.

    When episode_id is provided, prefer entities from that episode, then project-global
    (episode_id IS NULL), then other episodes. This prevents same-name subjects from
    earlier episodes winning via first-insert setdefault.
    """
    rows = (
        db.query(Entity)
        .filter(Entity.project_id == project_id, _active_entity_clause())
        .all()
    )
    preferred_episode_id = _to_positive_int_or_none(episode_id)

    def _preference_score(row: Entity) -> Tuple[int, int, int]:
        raw_ep = getattr(row, "episode_id", None)
        try:
            ep_id_int = int(raw_ep) if raw_ep is not None else 0
        except Exception:
            ep_id_int = 0
        entity_id = int(getattr(row, "id", 0) or 0)
        if preferred_episode_id:
            if ep_id_int == int(preferred_episode_id):
                return (3, ep_id_int, entity_id)
            if raw_ep is None:
                return (2, 0, entity_id)
            # Other episodes: prefer nearer (higher) episode as weak fallback only.
            return (1, ep_id_int, entity_id)
        if ep_id_int > 0:
            return (2, ep_id_int, entity_id)
        return (1, 0, entity_id)

    # Highest preference first so setdefault keeps the best row per alias.
    ordered_rows = sorted(rows, key=_preference_score, reverse=True)

    lookup: Dict[str, Dict[str, Any]] = {}
    for row in ordered_rows:
        canonical_name = str(row.name or row.name_en or "").strip()
        anchor_description = str(row.anchor_description or "").strip()
        anchor = str(
            row.anchor_description
            or row.narrative_description
            or canonical_name
            or ""
        ).strip()
        image_url = str(row.image_url or "").strip()
        entity_type = str(row.type or "").strip().lower()
        payload = {
            "name": canonical_name,
            "name_en": str(getattr(row, "name_en", None) or "").strip(),
            "anchor_description": anchor_description,
            "anchor": anchor,
            "description": str(row.description or row.narrative_description or anchor or "").strip(),
            "image_url": image_url,
            "entity_id": row.id,
            "entity_type": entity_type,
            "episode_id": getattr(row, "episode_id", None),
        }
        for key in _entity_lookup_alias_keys(row.name, row.name_en, canonical_name):
            # Prefer first writer after preference sort (current episode / best fallback).
            lookup.setdefault(key, payload)
    return lookup


def _extract_kling_character_mentions(prompt: Any) -> List[str]:
    text = str(prompt or "")
    if not text:
        return []

    mentions: List[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"CHAR\s*:\s*\[@([^\]]+)\]", text, flags=re.IGNORECASE):
        raw_name = str(match.group(1) or "").strip()
        normalized = _normalize_entity_anchor_token(raw_name)
        if not raw_name or not normalized or normalized in seen:
            continue
        seen.add(normalized)
        mentions.append(raw_name)
    return mentions


def _collect_kling_prompt_alias_maps(
    prompt_candidates: List[str],
    entity_lookup: Dict[str, Dict[str, Any]],
) -> Tuple[List[str], Dict[str, str], Dict[int, str]]:
    mentions: List[str] = []
    alias_by_norm: Dict[str, str] = {}
    alias_by_entity_id: Dict[int, str] = {}
    seen_mentions: set[str] = set()

    for candidate in prompt_candidates:
        for raw_name in _extract_kling_character_mentions(candidate):
            alias_name = str(raw_name or "").strip().lstrip("@").strip()
            normalized = _normalize_entity_anchor_token(raw_name)
            if not alias_name or not normalized or normalized in seen_mentions:
                continue
            seen_mentions.add(normalized)
            mentions.append(alias_name)
            alias_by_norm[normalized] = alias_name

            row = entity_lookup.get(normalized) or {}
            entity_id = row.get("entity_id")
            if isinstance(entity_id, int) and entity_id not in alias_by_entity_id:
                alias_by_entity_id[entity_id] = alias_name

    return mentions, alias_by_norm, alias_by_entity_id


def _build_auto_kling_elements(
    prompt_candidates: List[str],
    entity_lookup: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    allowed_types = {"subject", "character", "char"}
    mentions, _, _ = _collect_kling_prompt_alias_maps(prompt_candidates, entity_lookup)

    elements: List[Dict[str, Any]] = []
    for raw_name in mentions:
        row = entity_lookup.get(_normalize_entity_anchor_token(raw_name)) or {}
        entity_type = str(row.get("entity_type") or "").strip().lower() if row else ""
        if entity_type not in allowed_types:
            continue

        name = str(raw_name or "").strip().lstrip("@").strip()
        if not name:
            continue

        description = str(row.get("anchor") or row.get("description") or name).strip() or name
        element: Dict[str, Any] = {
            "name": name,
            "description": description,
        }

        image_url = str(row.get("image_url") or "").strip()
        if image_url:
            element["element_input_urls"] = [image_url, image_url]

        elements.append(element)

    return elements


def _align_kling_elements_to_prompt_mentions(
    elements: List[Dict[str, Any]],
    prompt_candidates: List[str],
    entity_lookup: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    _, alias_by_norm, alias_by_entity_id = _collect_kling_prompt_alias_maps(prompt_candidates, entity_lookup)
    if not alias_by_norm and not alias_by_entity_id:
        return elements

    aligned: List[Dict[str, Any]] = []
    for element in elements:
        if not isinstance(element, dict):
            continue

        name = str(element.get("name") or "").strip()
        normalized = _normalize_entity_anchor_token(name)
        if not name or not normalized:
            continue

        row = entity_lookup.get(normalized) or {}
        entity_id = row.get("entity_id")
        alias_name = alias_by_entity_id.get(entity_id) if isinstance(entity_id, int) else None
        if not alias_name:
            alias_name = alias_by_norm.get(normalized)

        if alias_name and alias_name != name:
            updated = dict(element)
            updated["name"] = alias_name
            aligned.append(updated)
        else:
            aligned.append(element)

    return aligned


def _merge_kling_elements(explicit_elements: Any, auto_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    max_elements = 3
    merged: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def _push(candidate: Any) -> None:
        if len(merged) >= max_elements:
            return
        if not isinstance(candidate, dict):
            return

        name = str(candidate.get("name") or "").strip()
        normalized = _normalize_entity_anchor_token(name)
        description = str(candidate.get("description") or "").strip()
        if not name or not normalized or normalized in seen or not description:
            return

        item: Dict[str, Any] = {
            "name": name,
            "description": description,
        }

        image_inputs = candidate.get("element_input_urls")
        if isinstance(image_inputs, list):
            urls = [str(url).strip() for url in image_inputs if str(url).strip()]
            if urls:
                if len(urls) == 1:
                    urls.append(urls[0])
                elif len(urls) > 4:
                    urls = urls[:4]
                item["element_input_urls"] = urls

        video_inputs = candidate.get("element_input_video_urls")
        if isinstance(video_inputs, list):
            urls = [str(url).strip() for url in video_inputs if str(url).strip()]
            if urls:
                item["element_input_video_urls"] = urls

        seen.add(normalized)
        merged.append(item)

    if isinstance(explicit_elements, list):
        for element in explicit_elements:
            _push(element)
            if len(merged) >= max_elements:
                break

    for element in auto_elements:
        _push(element)
        if len(merged) >= max_elements:
            break

    return merged


def _inject_shot_prompt_anchors(
    prompt: str,
    entity_lookup: Dict[str, Dict[str, Any]],
    global_style: str = "",
    subject_ref_index_map: Optional[Dict[str, int]] = None,
) -> str:
    text = str(prompt or "")
    if not text:
        return text

    regex = re.compile(r"\[[\s\S]+?\]|\{[\s\S]+?\}|【[\s\S]+?】|｛[\s\S]+?｝|(?<=^)@[^\s,，;；\]\[\(\)（）\{\}【】]+|(?<=[\s,，;；])@[^\s,，;；\]\[\(\)（）\{\}【】]+")
    injected_entities: set[str] = set()

    def _replace(match: re.Match) -> str:
        token = str(match.group(0) or "").strip()
        normalized = _normalize_entity_anchor_token(token)
        tail = text[match.end():]
        if re.match(r"^\s*[\(（]", tail):
            return match.group(0)

        if normalized in {"global style", "global_style"} and global_style:
            return f"{match.group(0)}({global_style})"

        row = entity_lookup.get(normalized)
        if row and row.get("anchor"):
            anchor = str(row.get("anchor") or "").strip()
            entity_id = str(row.get("entity_id") or "").strip()
            ref_no = (subject_ref_index_map or {}).get(entity_id)

            if normalized in injected_entities:
                # Duplicate reference: skip anchor description to prevent
                # image models from interpreting repeated descriptions as
                # multiple subjects (二宫格 / split-panel issue).
                if ref_no:
                    logger.info(f"[_inject_shot_prompt_anchors] Re-injected: {normalized} -> ref_image_url: #{ref_no}")
                    return f"{match.group(0)}(ref_image_url: #{ref_no})"
                return match.group(0)

            injected_entities.add(normalized)
            anchor_with_ref = anchor
            if ref_no:
                anchor_with_ref = f"{anchor} | ref_image_url: #{ref_no}"
            
            logger.info(f"[_inject_shot_prompt_anchors] Injected: {normalized} -> {anchor_with_ref}")
            return f"{match.group(0)}({anchor_with_ref})"
        return match.group(0)

    return regex.sub(_replace, text)


def _collect_associated_entities_refs(associated_entities_str: Optional[str], entity_lookup: Dict[str, Dict[str, Any]]) -> List[str]:
    if not isinstance(associated_entities_str, str) or not associated_entities_str.strip():
        return []

    refs: List[str] = []
    names = extract_entity_raw_names_from_prompt(associated_entities_str)
    if not names:
        names = [x.strip() for x in re.split(r"[,，]", associated_entities_str) if x.strip()]

    for name in names:
        norm_name = _normalize_entity_anchor_token(name)
        if not norm_name:
            continue
        row = entity_lookup.get(norm_name)
        if row:
            image_url = str((row or {}).get("image_url") or "").strip()
            if image_url:
                refs.append(image_url)

    return [x for x in dict.fromkeys(refs) if x]


def _extract_frontend_aligned_entity_raw_names(text: str) -> list[str]:
    return extract_entity_raw_names_from_prompt(text)

def _collect_prompt_entity_ref_images(prompt: str, entity_lookup: Dict[str, Dict[str, Any]]) -> List[str]:
    text = str(prompt or "")
    if not text:
        return []

    refs: List[str] = []
    raw_names = _extract_frontend_aligned_entity_raw_names(text)
    for raw_name in raw_names:
        normalized = _normalize_entity_anchor_token(raw_name)
        if not normalized:
            continue
        row = entity_lookup.get(normalized)
        image_url = str((row or {}).get("image_url") or "").strip()
        if image_url:
            refs.append(image_url)
    return [x for x in dict.fromkeys(refs) if x]


def _collect_prompt_entity_ref_images_relaxed(prompt: str, entity_lookup: Dict[str, Dict[str, Any]]) -> List[str]:
    text = str(prompt or "").strip()
    if not text:
        return []

    refs: List[str] = []

    allowed_types = {"subject", "character", "char", "environment", "env", "prop", "props"}

    refs.extend(_collect_prompt_entity_ref_images(text, entity_lookup))

    normalized_text = _normalize_entity_anchor_token(text)
    if not normalized_text:
        return [x for x in dict.fromkeys(refs) if x]

    for key, row in (entity_lookup or {}).items():
        norm_key = str(key or "").strip()
        if not norm_key:
            continue

        entity_type = str((row or {}).get("entity_type") or "").strip().lower()
        if entity_type and entity_type not in allowed_types:
            continue

        image_url = str((row or {}).get("image_url") or "").strip()
        if not image_url:
            continue

        has_ascii = bool(re.search(r"[a-z0-9]", norm_key, flags=re.IGNORECASE))
        if has_ascii:
            pattern = rf"(?<![a-z0-9]){re.escape(norm_key)}(?![a-z0-9])"
            matched = re.search(pattern, normalized_text, flags=re.IGNORECASE) is not None
        else:
            matched = norm_key in normalized_text

        if matched:
            refs.append(image_url)

    return [x for x in dict.fromkeys(refs) if x]


def _normalize_video_ref_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    if not mode or mode == "auto":
        return ""
    refs_aliases = {"entity_refs", "entity-refs", "refs_video", "refs-video", "reference", "reference_image", "reference_images"}
    if mode in refs_aliases:
        return "entity_refs"
    if mode in {"keyframes_entity_refs", "keyframe_entity_refs", "keyframes-entity-refs", "keyframe-entity-refs"}:
        return "keyframes_entity_refs"
    if mode in {"entity_refs_start_end", "entity-refs-start-end", "ref_start_end", "ref+start_end"}:
        return "entity_refs_start_end"
    if mode in {"start", "start_only", "start-only", "only_start", "only-start"}:
        return "start"
    if mode in {"start_end", "start-end", "start+end", "both", "both_ends"}:
        return "start_end"
    if mode in {"end", "end_only", "end-only", "only_end", "only-end"}:
        return "end"
    return ""


DEFAULT_SHOT_VIDEO_MODE = "entity_refs"

# Modes that bind prompt entity names to @ImageN (and may also carry start/end frames).
VIDEO_REFERENCE_IMAGE_MODES = frozenset({
    "entity_refs",
    "keyframes_entity_refs",
    "entity_refs_start_end",
})

# Modes that use start/end frame role instructions in the prompt.
VIDEO_FRAME_ROLE_MODES = frozenset({
    "start",
    "start_end",
    "end",
    "entity_refs_start_end",
})


def _is_video_reference_image_mode(ref_mode: Any) -> bool:
    return _normalize_video_ref_mode(ref_mode) in VIDEO_REFERENCE_IMAGE_MODES


def _listify_video_ref_urls(value: Optional[Union[str, List[str]]]) -> List[str]:
    if isinstance(value, list):
        return _dedupe_media_ref_urls([str(x).strip() for x in value if str(x).strip()])
    text = str(value or "").strip()
    return [text] if text else []


def _pack_video_ref_urls(urls: List[str]) -> Optional[Union[str, List[str]]]:
    cleaned = _dedupe_media_ref_urls(urls)
    if not cleaned:
        return None
    if len(cleaned) == 1:
        return cleaned[0]
    return cleaned


def _resolve_shot_video_mode(payload: Dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return DEFAULT_SHOT_VIDEO_MODE

    unified = _normalize_video_ref_mode(payload.get("video_mode_unified"))
    if unified:
        return unified

    ref_submit = str(payload.get("video_ref_submit_mode") or "").strip().lower()
    if ref_submit in {"entity_refs", "refs_video"}:
        return "entity_refs"

    legacy_gen = _normalize_video_ref_mode(payload.get("video_gen_mode"))
    if legacy_gen and ref_submit == "auto":
        return legacy_gen

    return DEFAULT_SHOT_VIDEO_MODE


def _dedupe_media_ref_urls(values: Optional[List[str]]) -> List[str]:
    refs = [str(x).strip() for x in (values or []) if str(x).strip()]
    unique_refs = []
    seen = set()
    for x in refs:
        base = x.split("?")[0]
        if base not in seen:
            seen.add(base)
            unique_refs.append(x)
    return unique_refs


def _system_api_supports_last_frame_flag(provider: Any, model: Any) -> Optional[bool]:
    provider_text = str(provider or "").strip()
    model_text = str(model or "").strip()
    if not provider_text or not model_text:
        return None

    try:
        with SessionLocal() as lookup_db:
            row = get_system_api_setting(
                lookup_db,
                provider=provider_text,
                category="Video",
                model=model_text,
            )
            if row is None:
                return None

            modality = _safe_json_dict(getattr(row, "modality", None))
            capability_flags = _safe_json_dict(modality.get("capability_flags"))
            video_caps = _safe_json_dict(modality.get("video_capabilities"))
            for container in (capability_flags, video_caps):
                for key in ("supports_last_frame", "supports_last_frame_mode", "last_frame_supported"):
                    value = container.get(key)
                    if isinstance(value, bool):
                        return value
                    if value is not None:
                        text = str(value).strip().lower()
                        if text in {"1", "true", "yes", "y", "on"}:
                            return True
                        if text in {"0", "false", "no", "n", "off"}:
                            return False
    except Exception:
        return None

    return None


def _video_api_supports_last_frame_mode(provider: Any, model: Any) -> bool:
    explicit_flag = _system_api_supports_last_frame_flag(provider, model)
    if explicit_flag is not None:
        return explicit_flag

    provider_text = str(provider or "").strip().lower()
    model_text = str(model or "").strip().lower()

    # Seedance 2 multi-ref path consumes all images as reference_image + @ImageN.
    # A separate last_frame slot is dropped by the ark-seedance adapter.
    if provider_text in {"ark-seedance", "ark_seedance"}:
        return False
    if "seedance-2" in model_text or "seedance_2" in model_text or "seedance2" in model_text:
        return False

    if provider_text == "kie" and model_text in {
        "kling-2.6/image-to-video",
        "sora-2-image-to-video",
        "sora-2-pro-image-to-video",
        "hailuo/2-3-image-to-video-standard",
        "hailuo/2-3-image-to-video-pro",
    }:
        return False

    if provider_text == "wanxiang":
        if "happyhorse" in model_text:
            return False
        if model_text and "kf2v" not in model_text and ("image-to-video" in model_text or model_text.endswith("i2v") or "-i2v" in model_text):
            return False

    if provider_text == "happyhorse":
        return False

    return True


def _exclude_role_slot_refs(
    refs: List[str],
    *,
    last_frame_url: Optional[str] = None,
    keyframes: Optional[List[str]] = None,
) -> List[str]:
    """Drop last-frame / keyframe URLs that are submitted via dedicated API slots."""
    exclude_keys: Set[str] = set()
    for url in (keyframes or []):
        key = _normalize_media_ref_key(url)
        if key:
            exclude_keys.add(key)
    last_key = _normalize_media_ref_key(last_frame_url)
    if last_key:
        exclude_keys.add(last_key)
    if not exclude_keys:
        return _dedupe_media_ref_urls(refs)
    return [
        str(url).strip()
        for url in _dedupe_media_ref_urls(refs)
        if str(url).strip() and _normalize_media_ref_key(url) not in exclude_keys
    ]


def _ensure_video_frame_role_instructions(
    prompt: str,
    *,
    ref_mode: Any,
    image_urls: Optional[List[str]],
    last_frame_url: Optional[str] = None,
    start_frame_url: Optional[str] = None,
) -> str:
    """Rewrite start/end frame role lines so @ImageN matches final image_urls order."""
    mode = _normalize_video_ref_mode(ref_mode)
    if mode not in VIDEO_FRAME_ROLE_MODES:
        return str(prompt or "")

    text = str(prompt or "").strip()
    text = re.sub(r"参考@Image\d+\s*作为第一帧\s*[,，]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[,，]?\s*参考@Image\d+\s*作为最后一帧", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[,，]?\s*并以(?:提交的)?尾帧作为最后一帧", "", text, flags=re.IGNORECASE)
    text = text.strip().strip(",，").strip()

    urls = _dedupe_media_ref_urls(image_urls if isinstance(image_urls, list) else [])
    start_url = str(start_frame_url or "").strip()
    end_url = str(last_frame_url or "").strip()

    start_idx: Optional[int] = None
    end_idx: Optional[int] = None

    if mode in {"start", "start_end", "entity_refs_start_end"}:
        if start_url:
            for idx, url in enumerate(urls, start=1):
                if _normalize_media_ref_key(url) == _normalize_media_ref_key(start_url):
                    start_idx = idx
                    break
        if start_idx is None and mode in {"start", "start_end"} and urls:
            start_idx = 1
        if start_idx is None and mode == "entity_refs_start_end" and urls:
            # Panel order is entities… + start (+ end if merged).
            start_idx = len(urls) if end_url else (len(urls) - 1 if len(urls) >= 2 else len(urls))

    if mode in {"start_end", "entity_refs_start_end", "end"}:
        if end_url:
            for idx, url in enumerate(urls, start=1):
                if _normalize_media_ref_key(url) == _normalize_media_ref_key(end_url):
                    end_idx = idx
                    break
        elif mode == "end" and urls:
            end_idx = len(urls)
        elif mode in {"start_end", "entity_refs_start_end"} and len(urls) >= 2:
            end_idx = len(urls)

    prefix = f"参考@Image{start_idx} 作为第一帧, " if start_idx else ""
    if end_idx:
        suffix = f", 参考@Image{end_idx} 作为最后一帧"
    elif end_url:
        # Dedicated last_frame API slot (e.g. Doubao first/last roles).
        suffix = ", 并以提交的尾帧作为最后一帧"
    else:
        suffix = ""

    if not prefix and not suffix:
        return text
    if not text:
        return f"{prefix.rstrip(', ')}{suffix}".strip(" ,，")
    return f"{prefix}{text}{suffix}".strip()


def _normalize_video_request_refs(
    ref_image_url: Optional[Union[str, List[str]]],
    last_frame_url: Optional[str],
    ref_mode: Any,
    *,
    supports_last_frame_mode: bool,
) -> Tuple[Optional[Union[str, List[str]]], Optional[str], Dict[str, Any]]:
    normalized_mode = _normalize_video_ref_mode(ref_mode)
    start_refs = _dedupe_media_ref_urls(
        ref_image_url if isinstance(ref_image_url, list) else ([ref_image_url] if str(ref_image_url or "").strip() else [])
    )
    end_ref = str(last_frame_url or "").strip() or None

    info: Dict[str, Any] = {
        "normalized_mode": normalized_mode,
        "supports_last_frame_mode": supports_last_frame_mode,
        "fallback_to_refs": False,
        "start_count_before": len(start_refs),
        "had_last_frame_before": bool(end_ref),
    }

    if normalized_mode in {"entity_refs", "keyframes_entity_refs"}:
        info["start_count_after"] = len(start_refs)
        info["had_last_frame_after"] = False
        return (start_refs or None), None, info

    if normalized_mode == "end":
        if not end_ref and start_refs:
            end_ref = start_refs[-1]
        start_refs = []
    elif normalized_mode == "start_end":
        if not end_ref and len(start_refs) >= 2:
            end_ref = start_refs[-1]
        start_refs = start_refs[:1]
    elif normalized_mode == "start":
        start_refs = start_refs[:1]
        end_ref = None

    if end_ref and not supports_last_frame_mode:
        merged_refs = list(start_refs)
        if end_ref not in merged_refs:
            merged_refs.append(end_ref)
        start_refs = merged_refs
        end_ref = None
        info["fallback_to_refs"] = True

    normalized_ref_image_url: Optional[Union[str, List[str]]] = None
    if len(start_refs) == 1:
        normalized_ref_image_url = start_refs[0]
    elif start_refs:
        normalized_ref_image_url = start_refs

    info["start_count_after"] = len(start_refs)
    info["had_last_frame_after"] = bool(end_ref)
    return normalized_ref_image_url, end_ref, info


def _limit_keyframes_for_video_mode(keyframes: Optional[List[str]], ref_mode: Any) -> List[str]:
    normalized_mode = _normalize_video_ref_mode(ref_mode)
    normalized_keyframes = _dedupe_media_ref_urls(keyframes if isinstance(keyframes, list) else [])
    if normalized_mode == "keyframes_entity_refs":
        return normalized_keyframes[:1]
    return normalized_keyframes


def _collect_video_prompt_entity_refs(
    prompt_candidates: List[str],
    entity_lookup: Dict[str, Dict[str, Any]],
    *,
    strict: bool = True,
) -> List[str]:
    refs: List[str] = []
    collector = _collect_prompt_entity_ref_images if strict else _collect_prompt_entity_ref_images_relaxed
    for candidate_text in (prompt_candidates or []):
        if not str(candidate_text or "").strip():
            continue
        refs.extend(collector(candidate_text, entity_lookup))
    return _dedupe_media_ref_urls(refs)


def _is_video_media_ref_url(url: Any) -> bool:
    raw = str(url or "").strip()
    if not raw:
        return False
    path = raw.split("?", 1)[0].split("#", 1)[0].lower()
    return bool(re.search(r"\.(mp4|webm|mov|m4v|avi|mkv)$", path))


def _filter_image_media_ref_urls(urls: Optional[List[str]]) -> List[str]:
    return [
        str(url).strip()
        for url in _dedupe_media_ref_urls(urls if isinstance(urls, list) else [])
        if str(url or "").strip() and not _is_video_media_ref_url(url)
    ]


def _resolve_shot_video_panel_image_refs(
    shot: Any,
    tech: Dict[str, Any],
    entity_lookup: Dict[str, Dict[str, Any]],
) -> List[str]:
    """Image refs from the shot video Refs panel (frontend WYSIWYG source of truth)."""
    notes = tech if isinstance(tech, dict) else {}
    deleted = {str(x).strip() for x in (notes.get("deleted_ref_urls") or []) if str(x).strip()}
    video_manual = bool(notes.get("video_ref_image_urls_manual") or notes.get("video_ref_image_urls_user_edited"))

    if video_manual and isinstance(notes.get("video_ref_image_urls"), list):
        refs = [
            str(x).strip()
            for x in (notes.get("video_ref_image_urls") or [])
            if str(x).strip() and str(x).strip() not in deleted
        ]
        # Keep newly matched video-prompt entities unless explicitly deleted (frontend parity).
        prompt_candidates = [
            str(getattr(shot, "video_content", None) or "").strip(),
            str(notes.get("video_prompt_cn") or "").strip(),
            str(getattr(shot, "prompt", None) or "").strip(),
        ]
        for url in _collect_video_prompt_entity_refs(prompt_candidates, entity_lookup):
            if url and url not in deleted and url not in refs:
                refs.append(url)
        return _filter_image_media_ref_urls(refs)

    video_mode = _resolve_shot_video_mode(notes)
    prompt_candidates = [
        str(getattr(shot, "video_content", None) or "").strip(),
        str(notes.get("video_prompt_cn") or "").strip(),
        str(getattr(shot, "prompt", None) or "").strip(),
    ]
    entity_refs = _collect_video_prompt_entity_refs(prompt_candidates, entity_lookup)
    start_ref = str(getattr(shot, "image_url", None) or "").strip()
    end_ref = str(notes.get("end_frame_url") or "").strip()
    keyframes = _limit_keyframes_for_video_mode(notes.get("keyframes"), video_mode)

    if video_mode == "entity_refs":
        refs = list(entity_refs)
    elif video_mode == "entity_refs_start_end":
        refs = list(entity_refs)
        if start_ref:
            refs.append(start_ref)
        if end_ref:
            refs.append(end_ref)
    elif video_mode == "keyframes_entity_refs":
        refs = [*keyframes, *entity_refs]
        if not refs and start_ref:
            refs.append(start_ref)
    elif video_mode == "end":
        refs = [end_ref] if end_ref else []
    elif video_mode == "start_end":
        refs = []
        if start_ref:
            refs.append(start_ref)
        if end_ref:
            refs.append(end_ref)
    else:
        refs = [start_ref] if start_ref else []

    refs = [url for url in refs if url and url not in deleted]
    return _filter_image_media_ref_urls(refs)


def _resolve_default_shot_image_gen_refs(
    shot: Any,
    tech: Dict[str, Any],
    entity_lookup: Dict[str, Dict[str, Any]],
    *,
    panel: str = "start",
) -> List[str]:
    """Default start/end image-gen refs = video panel refs; panel lists only after user edit."""
    notes = tech if isinstance(tech, dict) else {}
    deleted = {str(x).strip() for x in (notes.get("deleted_ref_urls") or []) if str(x).strip()}
    storage_key = "end_ref_image_urls" if panel == "end" else "ref_image_urls"
    user_edited = bool(notes.get(f"{storage_key}_user_edited"))

    if user_edited and isinstance(notes.get(storage_key), list):
        refs = [
            str(x).strip()
            for x in (notes.get(storage_key) or [])
            if str(x).strip() and str(x).strip() not in deleted
        ]
    else:
        refs = _resolve_shot_video_panel_image_refs(shot, notes, entity_lookup)

    if panel == "end" and not user_edited:
        start_image = str(getattr(shot, "image_url", None) or "").strip()
        if start_image and start_image not in deleted and start_image not in refs:
            refs = [start_image, *refs]

    return _filter_image_media_ref_urls(refs)


def _merge_entity_refs_for_video_mode(
    base_refs: List[str],
    *,
    ref_mode: Any,
    prompt_candidates: List[str],
    entity_lookup: Dict[str, Dict[str, Any]],
    manual_override: bool = False,
    associated_entities: Optional[str] = None,
) -> Tuple[List[str], List[str]]:
    normalized_mode = _normalize_video_ref_mode(ref_mode)
    current_refs = _dedupe_media_ref_urls(base_refs)
    if normalized_mode not in {"entity_refs", "keyframes_entity_refs"} or manual_override:
        return current_refs, []

    auto_entity_refs: List[str] = []
    auto_entity_refs.extend(_collect_video_prompt_entity_refs(prompt_candidates, entity_lookup))
    auto_entity_refs = _dedupe_media_ref_urls(auto_entity_refs)

    if not auto_entity_refs:
        return current_refs, []

    if normalized_mode == "keyframes_entity_refs":
        return _dedupe_media_ref_urls([*current_refs, *auto_entity_refs]), auto_entity_refs

    # If entity_refs mode is selected, we ONLY return the entity refs and ignore the base_refs
    # to avoid mixing first frame/last frame/keyframes into the entity reference list sent to the provider.
    return _dedupe_media_ref_urls(auto_entity_refs), auto_entity_refs


def _prepend_keyframe_story_progression_instruction(prompt: Any, keyframe_ref_count: int, *, language: str = "en") -> str:
    base_prompt = str(prompt or "").strip()
    if keyframe_ref_count <= 0:
        return base_prompt

    ref_label = "参考@Image1"
    normalized_language = str(language or "en").strip().lower()
    if normalized_language.startswith("zh") or normalized_language.startswith("cn"):
        prefix = f"{ref_label} 的画面顺序生成视频。"
    else:
        prefix = f"Generate the video following the frame order of {ref_label}."

    if not base_prompt:
        return prefix
    return f"{prefix} {base_prompt}" if not prefix.endswith("。") else f"{prefix}{base_prompt}"

def _compute_subject_ref_index_map(prompt: str, entity_lookup: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    text = str(prompt or "")
    if not text:
        return {}

    refs: List[str] = []
    index_map: Dict[str, int] = {}
    raw_names = _extract_frontend_aligned_entity_raw_names(text)
    for raw_name in raw_names:
        normalized = _normalize_entity_anchor_token(raw_name)
        if not normalized:
            continue

        row = entity_lookup.get(normalized)
        if not row:
            continue

        entity_type = str(row.get("entity_type") or "").strip().lower() if row else ""
        if entity_type and entity_type not in {
            "subject",
            "character",
            "char",
            "environment",
            "env",
            "prop",
            "props",
        }:
            continue

        image_url = str(row.get("image_url") or "").strip()
        if not image_url:
            continue

        if image_url not in refs:
            refs.append(image_url)

        entity_id = str(row.get("entity_id") or "").strip()
        if entity_id:
            index_map[entity_id] = refs.index(image_url) + 1

    return index_map


def _normalize_media_ref_key(url: Any) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    return text.split("?")[0].rstrip("/")


def _media_ref_basename(url: Any) -> str:
    key = _normalize_media_ref_key(url)
    if not key:
        return ""
    return key.rsplit("/", 1)[-1].strip().lower()


def _lookup_entity_row_for_token(
    normalized: str,
    entity_lookup: Optional[Dict[str, Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    if not normalized or not entity_lookup:
        return None
    for key in _entity_lookup_alias_keys(normalized):
        row = entity_lookup.get(key)
        if row:
            return row

    token_keys = subject_compare_key_variants(normalized)
    if not token_keys:
        return None
    for row in _iter_unique_entity_rows(entity_lookup):
        entity_keys = _entity_lookup_alias_keys(row.get("name"), row.get("name_en"))
        if entity_subject_keys_match(entity_keys, token_keys):
            return row
    return None


def _pick_submitted_ref_for_entity(
    *,
    entity_row: Dict[str, Any],
    available_refs: List[str],
    used_keys: set,
) -> str:
    """Bind a submitted ref URL to an entity by verifying image_url (name→URL audit)."""
    preferred = str((entity_row or {}).get("image_url") or "").strip()
    preferred_key = _normalize_media_ref_key(preferred)
    preferred_base = _media_ref_basename(preferred)
    if not preferred_key and not preferred_base:
        return ""

    for url in available_refs:
        key = _normalize_media_ref_key(url)
        if not key or key in used_keys:
            continue
        if preferred and (url == preferred or key == preferred_key):
            return url
        if preferred_base and _media_ref_basename(url) == preferred_base:
            return url
    return ""


def _iter_unique_entity_rows(
    entity_lookup: Optional[Dict[str, Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen_ids: set = set()
    for row in (entity_lookup or {}).values():
        if not isinstance(row, dict):
            continue
        entity_id = row.get("entity_id")
        dedupe_key = f"id:{entity_id}" if entity_id is not None else f"url:{_normalize_media_ref_key(row.get('image_url'))}:{row.get('name')}"
        if dedupe_key in seen_ids:
            continue
        seen_ids.add(dedupe_key)
        rows.append(row)
    return rows


def _build_url_to_entity_rows(
    entity_lookup: Optional[Dict[str, Dict[str, Any]]],
) -> Dict[str, Dict[str, Any]]:
    mapping: Dict[str, Dict[str, Any]] = {}
    for row in _iter_unique_entity_rows(entity_lookup):
        image_url = str(row.get("image_url") or "").strip()
        if not image_url:
            continue
        for key in (
            image_url,
            _normalize_media_ref_key(image_url),
            _media_ref_basename(image_url),
        ):
            if key and key not in mapping:
                mapping[key] = row
    return mapping


def _collect_prompt_entity_mentions_for_mapping(
    prompt: str,
    entity_lookup: Optional[Dict[str, Dict[str, Any]]],
    ordered_refs: Optional[List[str]] = None,
) -> Tuple[List[Tuple[str, str, Dict[str, Any]]], str]:
    """
    Collect (normalized, display_name, row) for @Image mapping.
    Prefer structured CHAR/ENV/PROP tokens; fall back to URL→entity reverse + name appearance.
    """
    allowed_types = {"subject", "character", "char", "environment", "env", "prop", "props"}
    text = str(prompt or "")
    mentions: List[Tuple[str, str, Dict[str, Any]]] = []
    seen_norms: set = set()
    seen_ids: set = set()

    def _append_mention(normalized: str, display_name: str, row: Dict[str, Any]) -> bool:
        if not normalized or not display_name or not isinstance(row, dict):
            return False
        entity_type = str(row.get("entity_type") or "").strip().lower()
        if entity_type and entity_type not in allowed_types:
            return False
        entity_id = row.get("entity_id")
        dedupe_key = f"id:{entity_id}" if entity_id is not None else f"name:{normalized}"
        if dedupe_key in seen_ids or normalized in seen_norms:
            return False
        seen_ids.add(dedupe_key)
        seen_norms.add(normalized)
        mentions.append((normalized, display_name, row))
        return True

    for raw_name in _extract_frontend_aligned_entity_raw_names(text):
        raw_name = str(raw_name or "").strip()
        normalized = _normalize_entity_anchor_token(raw_name)
        if not normalized:
            continue
        row = _lookup_entity_row_for_token(normalized, entity_lookup)
        if not row:
            continue
        display_name = raw_name.lstrip("@").strip() or str(row.get("name") or "").strip()
        _append_mention(normalized, display_name, row)

    mention_source = "structured" if mentions else "none"

    # Even when structured mentions exist, recover entities that the frontend already
    # put into image_urls but whose prompt token failed exact-name lookup.
    if entity_lookup and ordered_refs:
        url_map = _build_url_to_entity_rows(entity_lookup)
        reverse_hits: List[Tuple[int, int, str, str, Dict[str, Any]]] = []
        for ref_idx, url in enumerate(ordered_refs):
            row = (
                url_map.get(str(url or "").strip())
                or url_map.get(_normalize_media_ref_key(url))
                or url_map.get(_media_ref_basename(url))
            )
            if not row:
                continue
            entity_id = row.get("entity_id")
            dedupe_key = f"id:{entity_id}" if entity_id is not None else f"name:{row.get('name')}"
            if dedupe_key in seen_ids:
                continue
            display_name = str(row.get("name") or "").strip()
            normalized = _normalize_entity_anchor_token(display_name)
            if not display_name or not normalized:
                continue
            # Confirm the entity actually appears in the prompt (typed token or plain name).
            prompt_hit = False
            row_keys = _entity_lookup_alias_keys(row.get("name"), row.get("name_en"))
            for raw_name in _extract_frontend_aligned_entity_raw_names(text):
                raw_norm = _normalize_entity_anchor_token(raw_name)
                if not raw_norm:
                    continue
                if entity_subject_keys_match(row_keys, subject_compare_key_variants(raw_norm)) or raw_norm in row_keys:
                    prompt_hit = True
                    # Prefer the prompt-facing token for @Image injection regex.
                    display_name = str(raw_name or "").lstrip("@").strip() or display_name
                    normalized = raw_norm
                    break
            if not prompt_hit:
                if text.find(display_name) < 0 and text.lower().find(normalized) < 0:
                    continue
            pos = text.find(display_name)
            if pos < 0:
                pos = text.lower().find(normalized)
            if pos < 0:
                pos = 10**9 + ref_idx
            reverse_hits.append((pos, ref_idx, normalized, display_name, row))

        reverse_hits.sort(key=lambda item: (item[0], item[1]))
        recovered = 0
        for _pos, _ref_idx, norm, name, row in reverse_hits:
            if _append_mention(norm, name, row):
                recovered += 1
        if recovered:
            mention_source = "structured+url_reverse" if mention_source == "structured" else "url_reverse"

        # Keep prompt appearance order for structured names, then append recovered by prompt pos.
        if mention_source.startswith("structured") and recovered:
            # Re-sort all mentions by earliest prompt appearance for stable @Image indices.
            def _mention_pos(item: Tuple[str, str, Dict[str, Any]]) -> int:
                _norm, name, _row = item
                pos = text.find(name)
                if pos < 0:
                    pos = text.lower().find(_norm)
                return pos if pos >= 0 else 10**9

            mentions.sort(key=_mention_pos)

    return mentions, mention_source


def _reconcile_video_refs_by_entity_names(
    prompt: str,
    ordered_refs: List[str],
    entity_lookup: Optional[Dict[str, Dict[str, Any]]],
    *,
    preserve_submitted_refs: bool = False,
) -> Tuple[List[str], List[Tuple[int, str, str]], List[str]]:
    """
    Align image ref order to prompt entity mentions by entity name.

    Primary contract: @ImageN must refer to the N-th bound entity's image.
    Fallback audit uses entity.name → entity.image_url instead of blind index zip.
    Returns (aligned_refs, pairs[(1-based idx, display_name, anchor)], audit_notes).

    When preserve_submitted_refs=True (explicit UI / image_urls submit):
    - Keep submitted ref order and count as source of truth
    - Keep unpaired / user-added images as additional refs
    - Do not re-inject official entity images the panel omitted
    """
    refs = [str(x).strip() for x in (ordered_refs or []) if str(x).strip()]
    audit: List[str] = []
    if not refs:
        audit.append("skip:no_refs")
        return refs, [], audit
    if not entity_lookup:
        # Do NOT invent 附加参考 pairs here: that forces prompt rewrite and can
        # wipe frontend first/last-frame @Image role lines. Caller decides
        # whether to preserve original markers or emit a fallback map.
        audit.append("skip:no_entity_lookup")
        return refs, [], audit

    mentions, mention_source = _collect_prompt_entity_mentions_for_mapping(
        prompt,
        entity_lookup,
        ordered_refs=refs,
    )
    audit.append(f"mention_source={mention_source}")
    audit.append(f"mentions={len(mentions)}")
    if preserve_submitted_refs:
        audit.append("preserve_submitted=1")

    if not mentions and not preserve_submitted_refs:
        sample_keys = list(entity_lookup.keys())[:6]
        audit.append(f"skip:no_mentions lookup_keys_sample={sample_keys}")
        return refs, [], audit

    used_keys: set = set()
    bound: List[Tuple[str, str, str]] = []
    unbound: List[Tuple[str, Dict[str, Any]]] = []
    bound_by_key: Dict[str, Tuple[str, str]] = {}
    for _norm, display_name, row in mentions:
        matched_url = _pick_submitted_ref_for_entity(
            entity_row=row,
            available_refs=refs,
            used_keys=used_keys,
        )
        if not matched_url:
            unbound.append((display_name, row))
            continue
        key = _normalize_media_ref_key(matched_url)
        if not key or key in used_keys:
            unbound.append((display_name, row))
            continue
        used_keys.add(key)
        chosen = matched_url
        for url in refs:
            if _normalize_media_ref_key(url) == key or _media_ref_basename(url) == _media_ref_basename(matched_url):
                chosen = url
                break
        anchor = str(row.get("anchor_description") or "").strip()
        bound.append((chosen, display_name, anchor))
        bound_by_key[key] = (display_name, anchor)

    if preserve_submitted_refs:
        # Panel / explicit image_urls win: never drop extras, never resurrect omitted official refs.
        for display_name, _row in unbound:
            audit.append(f"omitted_by_panel:{display_name}")

        url_map = _build_url_to_entity_rows(entity_lookup)
        pairs: List[Tuple[int, str, str]] = []
        extra_count = 0
        for idx, url in enumerate(refs, start=1):
            key = _normalize_media_ref_key(url)
            if key and key in bound_by_key:
                display_name, anchor = bound_by_key[key]
                pairs.append((idx, display_name, anchor))
                continue
            row = (
                url_map.get(str(url or "").strip())
                or url_map.get(key)
                or url_map.get(_media_ref_basename(url))
            )
            if isinstance(row, dict):
                display_name = str(row.get("name") or row.get("name_en") or "").strip() or f"附加参考{idx}"
                anchor = str(row.get("anchor_description") or "").strip()
                pairs.append((idx, display_name, anchor))
                continue
            extra_count += 1
            pairs.append((idx, f"附加参考{idx}", ""))

        if extra_count:
            audit.append(f"kept_additional_refs={extra_count}")
        audit.append(f"bound={len(bound_by_key)}")
        audit.append(f"preserved_count={len(refs)}")
        return refs, pairs, audit

    # Name fallback: inject official entity image when submitted list missed it.
    # Never blind-zip leftover URLs to leftover names (that caused Image1↔Image3 swaps).
    for display_name, row in unbound:
        preferred = str((row or {}).get("image_url") or "").strip()
        preferred_key = _normalize_media_ref_key(preferred)
        if not preferred or not preferred_key or preferred_key in used_keys:
            audit.append(f"missing_image:{display_name}")
            continue
        used_keys.add(preferred_key)
        anchor = str(row.get("anchor_description") or "").strip()
        bound.append((preferred, display_name, anchor))
        audit.append(f"injected_official_ref:{display_name}")

    aligned = [url for url, _, _ in bound]
    if bound:
        bound_keys = {_normalize_media_ref_key(u) for u in aligned if _normalize_media_ref_key(u)}
        dropped = 0
        for url in refs:
            key = _normalize_media_ref_key(url)
            if key and key not in bound_keys:
                # Keep user-added / unpaired images as trailing additional refs.
                aligned.append(url)
                bound.append((url, f"附加参考{len(bound) + 1}", ""))
                dropped += 1
        if dropped:
            audit.append(f"kept_unpaired_refs={dropped}")
    else:
        aligned = list(refs)

    pairs = [(idx, name, anchor) for idx, (_url, name, anchor) in enumerate(bound, start=1)]
    audit.append(f"bound={len(bound)}")
    if [_normalize_media_ref_key(u) for u in aligned] != [_normalize_media_ref_key(u) for u in refs]:
        after_names = [name for _, name, _ in bound]
        after_preview = ",".join(after_names[:8])
        audit.append(f"reordered:after_names=[{after_preview}]")
    return aligned, pairs, audit


def _sync_request_image_refs_with_aligned(
    *,
    aligned_refs: List[str],
    image_urls: Optional[List[str]],
    ref_image_url: Optional[Union[str, List[str]]],
    last_frame_url: Optional[str],
    keyframes: Optional[List[str]],
) -> Tuple[Optional[List[str]], Optional[Union[str, List[str]]]]:
    """Keep provider image_urls / ref_image_url in the same order as @ImageN tags."""
    exclude_keys = set()
    for url in (keyframes or []):
        key = _normalize_media_ref_key(url)
        if key:
            exclude_keys.add(key)
    last_key = _normalize_media_ref_key(last_frame_url)
    if last_key:
        exclude_keys.add(last_key)

    synced = [
        str(url).strip()
        for url in (aligned_refs or [])
        if str(url).strip() and _normalize_media_ref_key(url) not in exclude_keys
    ]

    if isinstance(image_urls, list) and image_urls:
        return synced, ref_image_url

    if isinstance(ref_image_url, list):
        return image_urls, synced if synced else ref_image_url
    if isinstance(ref_image_url, str) and ref_image_url.strip():
        if not synced:
            return image_urls, None
        if len(synced) == 1:
            return image_urls, synced[0]
        return image_urls, synced
    return image_urls, ref_image_url


def _resolve_video_project_id_from_payload(db: Session, payload: Dict[str, Any]) -> Optional[int]:
    resolved = _to_positive_int_or_none(payload.get("project_id"))
    if resolved:
        return resolved
    shot_id = _to_positive_int_or_none(payload.get("shot_id"))
    if not shot_id:
        return None
    submit_shot = db.query(Shot).filter(Shot.id == int(shot_id)).first()
    if not submit_shot:
        return None
    resolved = _to_positive_int_or_none(getattr(submit_shot, "project_id", None))
    if resolved:
        return resolved
    episode_id = _to_positive_int_or_none(getattr(submit_shot, "episode_id", None))
    if not episode_id:
        return None
    submit_episode = db.query(Episode).filter(Episode.id == int(episode_id)).first()
    if submit_episode:
        return _to_positive_int_or_none(getattr(submit_episode, "project_id", None))
    return None


def _collect_video_flat_refs_from_payload(payload: Dict[str, Any]) -> List[str]:
    refs: List[str] = []
    image_urls = payload.get("image_urls")
    if isinstance(image_urls, list):
        refs.extend([str(x).strip() for x in image_urls if str(x).strip()])
    ref_image_url = payload.get("ref_image_url")
    if isinstance(ref_image_url, list):
        refs.extend([str(x).strip() for x in ref_image_url if str(x).strip()])
    elif isinstance(ref_image_url, str) and ref_image_url.strip():
        refs.append(ref_image_url.strip())
    keyframes = payload.get("keyframes")
    if isinstance(keyframes, list):
        refs.extend([str(x).strip() for x in keyframes if str(x).strip()])
    last_frame_url = payload.get("last_frame_url")
    if isinstance(last_frame_url, str) and last_frame_url.strip():
        refs.append(last_frame_url.strip())
    return [x for x in dict.fromkeys([str(x).strip() for x in refs if str(x).strip()]) if x]


def _preprocess_video_submit_payload(
    db: Session,
    req_payload: Dict[str, Any],
    *,
    provider: str = "",
    model: str = "",
) -> Dict[str, Any]:
    """Align queued video job payload with runtime entity-ref merge + @Image mapping."""
    submit_prompt = str(req_payload.get("prompt") or "").strip()
    if not submit_prompt:
        return req_payload

    normalized_ref_mode = _normalize_video_ref_mode(req_payload.get("ref_mode"))
    is_reference_image_mode = _is_video_reference_image_mode(normalized_ref_mode)
    submit_image_urls = _resolve_video_submit_image_urls(SimpleNamespace(**req_payload))
    uses_submit_image_urls = bool(submit_image_urls)

    submit_ref_image_url = req_payload.get("ref_image_url")
    submit_last_frame_url = req_payload.get("last_frame_url")
    submit_keyframes = req_payload.get("keyframes") if isinstance(req_payload.get("keyframes"), list) else None
    submit_ref_video_urls = req_payload.get("ref_video_urls") if isinstance(req_payload.get("ref_video_urls"), list) else None

    supports_last_frame_mode = _video_api_supports_last_frame_mode(provider, model)
    normalize_source = submit_image_urls if uses_submit_image_urls else submit_ref_image_url
    normalized_refs, submit_last_frame_url, ref_info = _normalize_video_request_refs(
        normalize_source,
        submit_last_frame_url,
        normalized_ref_mode,
        supports_last_frame_mode=supports_last_frame_mode,
    )
    if uses_submit_image_urls:
        submit_image_urls = _listify_video_ref_urls(normalized_refs)
        req_payload["image_urls"] = submit_image_urls
        req_payload["ref_image_url"] = None
        submit_ref_image_url = None
    else:
        submit_ref_image_url = normalized_refs
        req_payload["ref_image_url"] = normalized_refs
    req_payload["last_frame_url"] = submit_last_frame_url

    flat_refs = _listify_video_ref_urls(normalized_refs)
    resolved_project_id = _resolve_video_project_id_from_payload(db, req_payload)
    entity_lookup: Dict[str, Dict[str, Any]] = {}
    resolved_episode_id = _to_positive_int_or_none(req_payload.get("episode_id"))
    shot_id_for_episode = _to_positive_int_or_none(req_payload.get("shot_id"))
    start_frame_url = ""
    shot_for_ref: Optional[Shot] = None
    if shot_id_for_episode:
        shot_for_ref = db.query(Shot).filter(Shot.id == int(shot_id_for_episode)).first()
        if shot_for_ref:
            if not resolved_episode_id:
                resolved_episode_id = _to_positive_int_or_none(getattr(shot_for_ref, "episode_id", None))
            start_frame_url = str(getattr(shot_for_ref, "image_url", None) or "").strip()

    has_explicit_visual_refs = uses_submit_image_urls
    if not has_explicit_visual_refs and isinstance(submit_ref_image_url, list):
        has_explicit_visual_refs = any(str(x).strip() for x in submit_ref_image_url)
    elif not has_explicit_visual_refs and isinstance(submit_ref_image_url, str) and submit_ref_image_url.strip():
        has_explicit_visual_refs = True

    if is_reference_image_mode and resolved_project_id and not uses_submit_image_urls:
        entity_lookup = _build_project_entity_lookup(
            db, int(resolved_project_id), episode_id=resolved_episode_id
        )
        prompt_candidates: List[str] = [submit_prompt]
        if shot_for_ref:
            prompt_candidates.extend([
                str(shot_for_ref.video_content or "").strip(),
                str(shot_for_ref.prompt or "").strip(),
            ])
            shot_tech = _parse_shot_tech(shot_for_ref)
            if isinstance(shot_tech, dict):
                prompt_candidates.append(str(shot_tech.get("video_prompt_cn") or "").strip())

        existing_start_refs = _listify_video_ref_urls(submit_ref_image_url)
        merged_refs, auto_entity_refs = _merge_entity_refs_for_video_mode(
            existing_start_refs,
            ref_mode=normalized_ref_mode,
            prompt_candidates=prompt_candidates,
            entity_lookup=entity_lookup,
            manual_override=has_explicit_visual_refs,
            associated_entities=shot_for_ref.associated_entities if shot_for_ref else None,
        )
        if merged_refs:
            flat_refs = merged_refs
            submit_ref_image_url = _pack_video_ref_urls(merged_refs)
            req_payload["ref_image_url"] = submit_ref_image_url
        if auto_entity_refs:
            logger.info(
                "[VideoSubmit] merged entity refs | shot_id=%s project_id=%s ref_mode=%s explicit_refs=%s detected=%s final_refs=%s fallback_to_refs=%s",
                req_payload.get("shot_id"),
                resolved_project_id,
                normalized_ref_mode or "list_ref",
                has_explicit_visual_refs,
                len(auto_entity_refs),
                len(merged_refs or []),
                bool(ref_info.get("fallback_to_refs")),
            )
    elif is_reference_image_mode and resolved_project_id:
        entity_lookup = _build_project_entity_lookup(
            db, int(resolved_project_id), episode_id=resolved_episode_id
        )

    logger.info(
        "[VideoSubmit] prompt mapping prepare | shot_id=%s ref_mode=%s refs=%s project_id=%s lookup_keys=%s supports_last_frame=%s",
        req_payload.get("shot_id"),
        normalized_ref_mode or "<empty>",
        len(flat_refs),
        resolved_project_id,
        len(entity_lookup or {}),
        supports_last_frame_mode,
    )

    mapped_prompt, flat_refs = _append_video_api_ref_mapping(
        submit_prompt,
        flat_refs,
        submit_ref_image_url if not uses_submit_image_urls else submit_image_urls,
        submit_last_frame_url,
        submit_keyframes,
        submit_ref_video_urls,
        entity_lookup=entity_lookup if is_reference_image_mode else None,
        use_prev_video=bool(req_payload.get("use_prev_video")),
        provider=provider,
        model=model,
        preserve_submitted_refs=bool(uses_submit_image_urls or has_explicit_visual_refs),
    )

    synced_image_urls, synced_ref_image_url = _sync_request_image_refs_with_aligned(
        aligned_refs=flat_refs,
        image_urls=submit_image_urls if uses_submit_image_urls else None,
        ref_image_url=submit_ref_image_url if not uses_submit_image_urls else None,
        last_frame_url=submit_last_frame_url,
        keyframes=submit_keyframes,
    )
    if uses_submit_image_urls and isinstance(synced_image_urls, list) and synced_image_urls:
        submit_image_urls = synced_image_urls
        req_payload["image_urls"] = synced_image_urls
    elif synced_ref_image_url is not None:
        submit_ref_image_url = synced_ref_image_url
        req_payload["ref_image_url"] = synced_ref_image_url
        req_payload.pop("image_urls", None)
        submit_image_urls = _listify_video_ref_urls(synced_ref_image_url)
    elif is_reference_image_mode and flat_refs:
        req_payload["image_urls"] = flat_refs
        req_payload["ref_image_url"] = _pack_video_ref_urls(flat_refs)
        submit_image_urls = list(flat_refs)
    elif not uses_submit_image_urls:
        req_payload.pop("image_urls", None)

    final_image_urls = submit_image_urls if submit_image_urls else _listify_video_ref_urls(
        req_payload.get("image_urls") or req_payload.get("ref_image_url")
    )
    mapped_prompt = _ensure_video_frame_role_instructions(
        mapped_prompt,
        ref_mode=normalized_ref_mode,
        image_urls=final_image_urls,
        last_frame_url=submit_last_frame_url,
        start_frame_url=start_frame_url,
    )
    req_payload["prompt"] = mapped_prompt

    image_tag_count = len(re.findall(r"@Image\d+", str(mapped_prompt or ""), flags=re.IGNORECASE))
    logger.info(
        "[VideoSubmit] prompt mapping done | shot_id=%s ref_mode=%s refs=%s lookup=%s image_tags=%s prompt_len=%s",
        req_payload.get("shot_id"),
        normalized_ref_mode or "<empty>",
        len(flat_refs),
        len(entity_lookup or {}),
        image_tag_count,
        len(str(mapped_prompt or "")),
    )

    if isinstance(req_payload.get("multi_prompt"), list):
        patched_multi_prompt: List[Dict[str, Any]] = []
        for item in req_payload.get("multi_prompt") or []:
            if not isinstance(item, dict):
                continue
            patched_item = dict(item)
            item_prompt = str(patched_item.get("prompt") or "").strip()
            if item_prompt:
                item_mapped, _ = _append_video_api_ref_mapping(
                    item_prompt,
                    flat_refs,
                    req_payload.get("ref_image_url") if not uses_submit_image_urls else final_image_urls,
                    submit_last_frame_url,
                    submit_keyframes,
                    submit_ref_video_urls,
                    entity_lookup=entity_lookup if is_reference_image_mode else None,
                    use_prev_video=bool(req_payload.get("use_prev_video")),
                    provider=provider,
                    model=model,
                    preserve_submitted_refs=bool(uses_submit_image_urls or has_explicit_visual_refs),
                )
                patched_item["prompt"] = _ensure_video_frame_role_instructions(
                    item_mapped,
                    ref_mode=normalized_ref_mode,
                    image_urls=final_image_urls,
                    last_frame_url=submit_last_frame_url,
                    start_frame_url=start_frame_url,
                )
            patched_multi_prompt.append(patched_item)
        req_payload["multi_prompt"] = patched_multi_prompt

    return req_payload


def _append_video_api_ref_mapping(
    prompt: str,
    refs: List[str],
    ref_image_url: Optional[Union[str, List[str]]],
    last_frame_url: Optional[str],
    keyframes: Optional[List[str]] = None,
    reference_video_urls: Optional[List[str]] = None,
    entity_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
    use_prev_video: bool = False,
    provider: str = "",
    model: str = "",
    preserve_submitted_refs: bool = False,
) -> Tuple[str, List[str]]:
    is_seedance = "seedance" in str(provider or "").lower() or "seedance" in str(model or "").lower()
    original_use_prev_video = use_prev_video
    if is_seedance:
        use_prev_video = True

    original_text = str(prompt or "").strip()
    # @ImageN must only number images that remain in provider image_urls after
    # last_frame / keyframes are peeled into dedicated API slots.
    ordered_refs = _exclude_role_slot_refs(
        [str(x).strip() for x in (refs or []) if str(x).strip()],
        last_frame_url=last_frame_url,
        keyframes=keyframes,
    )
    has_existing_image_tags = bool(re.search(r"@Image\d+", original_text, flags=re.IGNORECASE))

    def _append_reference_video_instruction(source_text: str) -> str:
        updated_source = str(source_text or "").strip()
        if not updated_source:
            return updated_source
        if not (reference_video_urls and is_seedance):
            return updated_source

        if original_use_prev_video:
            vid_tag_nospace = "@Video1"
            has_continuation_instruction = bool(
                re.search(r"延长\s*@?Video\s*1", updated_source, flags=re.IGNORECASE)
                or re.search(r"延长\s*视频\s*@?Video\s*1", updated_source, flags=re.IGNORECASE)
            )
            if not has_continuation_instruction:
                updated_source = f"延长{vid_tag_nospace}，一镜到底，要参考视频的角色站位建置运镜。\n\n{updated_source.strip()}"

        added_videos = False
        for idx in range(1, len(reference_video_urls) + 1):
            vid_tag = f"@Video {idx}"
            vid_tag_nospace = f"@Video{idx}"
            if vid_tag not in updated_source and vid_tag_nospace not in updated_source:
                if not added_videos:
                    updated_source = f"{updated_source.strip()}，参考视频是 {vid_tag}"
                    added_videos = True
                else:
                    updated_source = f"{updated_source.strip()} {vid_tag}"

        return updated_source

    if not original_text:
        logger.info(
            "[_append_video_api_ref_mapping] skip empty prompt | refs=%s lookup=%s",
            len(ordered_refs),
            len(entity_lookup or {}),
        )
        return original_text, ordered_refs

    if not ordered_refs and not isinstance(reference_video_urls, list):
        logger.info("[_append_video_api_ref_mapping] skip no refs/videos | prompt_len=%s", len(original_text))
        return original_text, ordered_refs

    # Frame-only / hybrid prompts may already carry correct @Image role lines.
    # Without an entity lookup, preserve them instead of rewriting to 附加参考N.
    if not entity_lookup and has_existing_image_tags:
        logger.info(
            "[_append_video_api_ref_mapping] preserve existing @Image tags | refs=%s",
            len(ordered_refs),
        )
        return _append_reference_video_instruction(original_text), ordered_refs

    # Working copy: strip prior markers only when we successfully rebuild pairs.
    text = original_text
    text = re.sub(r"(?:参考)?@Image\d+\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\(\s*ref_image_url\s*:\s*#\d+\s*\)",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\|\s*ref_image_url\s*:\s*#\d+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^\s*API\s+ref\s+mapping\s*:\s*.*$",
        "",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    text = re.sub(
        r"^\s*实体参考映射\s*:\s*.*$",
        "",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    text = re.sub(
        r"^\s*实体参考图映射\s*:\s*.*$",
        "",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    # Also strip prior first/last frame role wrappers; they are re-applied later.
    text = re.sub(r"作为第一帧\s*[,，]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[,，]?\s*作为最后一帧", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[,，]?\s*并以(?:提交的)?尾帧作为最后一帧", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    aligned_refs, pairs, audit_notes = _reconcile_video_refs_by_entity_names(
        text,
        ordered_refs,
        entity_lookup,
        preserve_submitted_refs=preserve_submitted_refs,
    )

    # Fallback mapping line only when there are refs but no entity names to bind,
    # and the prompt did not already declare @Image tags.
    if not pairs and preserve_submitted_refs and ordered_refs and not has_existing_image_tags:
        pairs = [(idx, f"附加参考{idx}", "") for idx, _url in enumerate(ordered_refs, start=1)]
        aligned_refs = list(ordered_refs)
        audit_notes = list(audit_notes or []) + ["fallback:additional_ref_map"]
    logger.info(
        "[_append_video_api_ref_mapping] reconcile | refs_in=%s refs_out=%s pairs=%s lookup=%s preserve=%s audit=%s",
        len(ordered_refs),
        len(aligned_refs),
        len(pairs),
        len(entity_lookup or {}),
        int(bool(preserve_submitted_refs)),
        "; ".join(audit_notes) if audit_notes else "-",
    )
    ordered_refs = aligned_refs

    if not pairs:
        # Critical: do NOT return the stripped working copy — that wiped @Image tags
        # when name reconcile failed (some scenes ended with zero injection).
        logger.warning(
            "[_append_video_api_ref_mapping] no pairs; preserve original prompt markers | refs=%s audit=%s",
            len(ordered_refs),
            "; ".join(audit_notes) if audit_notes else "-",
        )
        return _append_reference_video_instruction(original_text), ordered_refs

    updated_text = text
    injected = 0
    failed_names: List[str] = []
    for mapped_idx, entity_name, anchor_text in pairs:
        prefix = f"参考@Image{mapped_idx} "
        name_candidates: List[str] = []
        for candidate in (
            entity_name,
            str(entity_name or "").split("(")[0].strip(),
            _normalize_entity_anchor_token(entity_name),
        ):
            text_candidate = str(candidate or "").strip().lstrip("@").strip()
            if text_candidate and text_candidate not in name_candidates:
                name_candidates.append(text_candidate)

        replaced = False
        for name_candidate in name_candidates:
            escaped_entity = re.escape(name_candidate)
            anchor_patterns = [
                rf"(?<![a-zA-Z0-9_])(?:(?:参考)?@Image\d+\s*)*(?:(?:CHAR|ENV|PROP)\s*:\s*)?(?:(?:参考)?@Image\d+\s*)*[\[【]\s*@?{escaped_entity}\s*[\]】](?:\([^\)]*\))?",
                rf"(?<![a-zA-Z0-9_])(?:(?:参考)?@Image\d+\s*)*[\[【]\s*(?:CHAR|ENV|PROP)\s*:\s*(?:(?:参考)?@Image\d+\s*)*@?{escaped_entity}\s*[\]】](?:\([^\)]*\))?",
                rf"(?<![a-zA-Z0-9_])(?:(?:参考)?@Image\d+\s*)*[\{{｛]\s*(?:(?:参考)?@Image\d+\s*)*@?{escaped_entity}\s*[\}}｝](?:\([^\)]*\))?",
                rf"(?<![a-zA-Z0-9_])(?:(?:参考)?@Image\d+\s*)*(@{escaped_entity})(?:\([^\)]*\))?",
            ]

            for pattern in anchor_patterns:
                def _prepend_prefix(match: re.Match[str], _prefix=prefix, _anchor=anchor_text) -> str:
                    token = str(match.group(0) or "")
                    base = re.sub(r"(?:参考)?@Image\d+\s*", "", token, flags=re.IGNORECASE)
                    if _anchor:
                        if "(" in base and ")" in base:
                            base = re.sub(r"\([^\)]*\)", f"({_anchor})", base)
                        else:
                            base = f"{base}({_anchor})"
                    else:
                        base = re.sub(r"\([^\)]*\)", "", base)
                    return f"{_prefix}{base}"

                replaced_text, count = re.subn(pattern, _prepend_prefix, updated_text, flags=re.IGNORECASE)
                if count > 0:
                    updated_text = replaced_text
                    replaced = True
                    injected += 1
                    break
            if replaced:
                break

            plain_pattern = rf'(?<![a-zA-Z0-9_])(?:(?:参考)?@Image\d+\s*)*{escaped_entity}(?![a-zA-Z0-9_])'

            def _prepend_marker(match: re.Match[str], _prefix=prefix, _anchor=anchor_text) -> str:
                token = str(match.group(0) or "")
                base = re.sub(r"(?:参考)?@Image\d+\s*", "", token, flags=re.IGNORECASE)
                if _anchor:
                    if "(" in base and ")" in base:
                        base = re.sub(r"\([^\)]*\)", f"({_anchor})", base)
                    else:
                        base = f"{base}({_anchor})"
                else:
                    base = re.sub(r"\([^\)]*\)", "", base)
                return f"{_prefix}{base}"

            replaced_text, count = re.subn(plain_pattern, _prepend_marker, updated_text, flags=re.IGNORECASE)
            if count > 0:
                updated_text = replaced_text
                replaced = True
                injected += 1
                break

        if not replaced:
            failed_names.append(f"{entity_name}->Image{mapped_idx}")

    if failed_names:
        logger.warning(
            "[_append_video_api_ref_mapping] inject pattern miss | failed=%s",
            ",".join(failed_names[:12]),
        )

    # When prompt has no CHAR/ENV/PROP tokens (or names only appear as plain text
    # that regex missed), still emit an explicit ImageN↔name map so the provider
    # can bind refs. Prefer in-prompt injection; mapping line is last resort.
    # Also append for partial misses so a single failed character (e.g. 小宝) is not silently dropped.
    if (injected <= 0 and pairs) or failed_names:
        mapping_pairs = pairs if injected <= 0 else [
            (idx, name, anchor)
            for idx, name, anchor in pairs
            if any(f"{name}->Image{idx}" == failed for failed in failed_names)
        ]
        if mapping_pairs:
            mapping_line = "实体参考图映射: " + "; ".join(
                f"@Image{idx}={name}" for idx, name, _anchor in mapping_pairs
            )
            updated_text = f"{updated_text.strip()}\n\n{mapping_line}".strip()
            if injected <= 0:
                injected = len(pairs)
            else:
                injected += len(mapping_pairs)
            logger.info(
                "[_append_video_api_ref_mapping] appended explicit mapping line | pairs=%s",
                len(mapping_pairs),
            )

    logger.info(
        "[_append_video_api_ref_mapping] injected | pairs=%s applied=%s failed=%s sample=%s",
        len(pairs),
        injected,
        len(failed_names),
        ",".join(f"Image{idx}:{name}" for idx, name, _ in pairs[:6]),
    )

    # If nothing could be written into the prompt, keep original markers.
    if injected <= 0:
        logger.warning(
            "[_append_video_api_ref_mapping] zero applied; preserve original prompt | pairs=%s",
            len(pairs),
        )
        return _append_reference_video_instruction(original_text), ordered_refs

    return _append_reference_video_instruction(updated_text), ordered_refs


def _find_previous_shot_end_frame_url(db: Session, episode_id: int, shot_id: int) -> Optional[str]:
    prev_shot = (
        db.query(Shot)
        .filter(Shot.episode_id == episode_id, Shot.id < shot_id)
        .order_by(Shot.id.desc())
        .first()
    )
    if not prev_shot:
        return None
    prev_tech = _parse_shot_tech(prev_shot)
    prev_end = str(prev_tech.get("end_frame_url") or "").strip()
    return prev_end or None


def _make_public_upload_url_for_provider(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if re.match(r"^https?://", raw, flags=re.IGNORECASE):
        return raw
    upload_suffix = ""
    if raw.startswith("/uploads/"):
        upload_suffix = raw
    elif "/uploads/" in raw:
        upload_suffix = raw[raw.index("/uploads/"):]
    if not upload_suffix:
        return raw
    public_base = str(
        os.getenv("AISTORY_PUBLIC_BASE_URL")
        or os.getenv("PUBLIC_BASE_URL")
        or os.getenv("RENDER_EXTERNAL_URL")
        or getattr(settings, "RENDER_EXTERNAL_URL", "")
        or os.getenv("RAILWAY_STATIC_URL")
        or ""
    ).strip().rstrip("/")
    if not public_base:
        frontend_base = str(
            os.getenv("AISTORY_FRONTEND_BASE_URL")
            or os.getenv("FRONTEND_BASE_URL")
            or getattr(settings, "FRONTEND_BASE_URL", "")
            or ""
        ).strip()
        match = re.match(r"^https?://[^/]+", frontend_base, flags=re.IGNORECASE)
        if match:
            public_base = match.group(0).replace("-frontend.", "-backend.").replace("frontend.onrender.com", "backend.onrender.com")
    if not public_base:
        return raw
    if not re.match(r"^https?://", public_base, flags=re.IGNORECASE):
        public_base = f"https://{public_base}"
    return f"{public_base.rstrip('/')}{upload_suffix}"


def _find_previous_shot_video_url(db: Session, episode_id: int, shot_id: int) -> Optional[str]:
    prev_shot = (
        db.query(Shot)
        .filter(Shot.episode_id == episode_id, Shot.id < shot_id, Shot.video_url.isnot(None), Shot.video_url != "")
        .order_by(Shot.id.desc())
        .first()
    )
    if not prev_shot:
        return None
    prev_video = str(prev_shot.video_url or "").strip()
    return _make_public_upload_url_for_provider(prev_video) or None
