# -*- coding: utf-8 -*-
"""Check that a shot only names environment subjects and lights that exist in its derived-env cell."""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.services.shot_markdown import extract_merged_beat_ids

_BEAT_START_RE = re.compile(r"\[BEAT_START:([^\s\]]+)\]", re.IGNORECASE)
_BEAT_END_RE = re.compile(r"\[BEAT_END[^\]]*\]", re.IGNORECASE)
_BEAT_GUIDANCE_LINE_RE = re.compile(r"^Beat(\d+)｜")
_ENV_TAG_RE = re.compile(r"ENV\s*:\s*\[\s*@?([^\]\n]+?)\s*\]", re.IGNORECASE)
_SUBJECT_TAG_RE = re.compile(r"\[@([^\]\n]+)\]")
_CHAR_TAG_RE = re.compile(r"CHAR\s*:\s*\[\s*@?([^\]\n]+?)\s*\]", re.IGNORECASE)
_PROP_TAG_RE = re.compile(r"PROP\s*:\s*\[\s*@?([^\]\n]+?)\s*\]", re.IGNORECASE)
_CAMERA_ANCHOR_RE = re.compile(r"机位\s*=\s*([^｜|\n<]+)")
_ANCHOR_TAIL_RE = re.compile(
    r"(?:正前|正后|左颊|右颊|左侧|右侧|靠近镜头|远离镜头|画面左|画面右|半空|贴身|一掌|一臂|一肩).*$"
)
_LIGHT_RE = re.compile(
    r"[0-9A-Za-z\u4e00-\u9fff]{0,18}(?:照明灯|壁灯|吊灯|台灯|落地灯|灯笼|烛台|火塘|油灯|宫灯|射灯|筒灯|灯带|补光灯|主灯|炉膛|火光)"
)
_LIGHT_TRIM_RE = re.compile(r"(?:冷白|暖橘|暖|冷|Key|Fill|｜|\|).*$")
_SKIP_ANCHORS = {"镜头", "画面", "中心", "主拍", "环境", "背景"}


def _norm(value: Any) -> str:
    text = str(value or "")
    text = text.replace("[@", "").replace("]", "")
    text = re.sub(r"\s+", "", text)
    return text.strip("，,。；;、")


def _beat_num(raw: str) -> Optional[int]:
    text = str(raw or "").strip()
    if text.isdigit():
        return int(text)
    match = re.search(r"(\d+)", text)
    if not match:
        return None
    return int(match.group(1))


def slice_core_scene_to_beats(text: str, beat_ids: Sequence[int]) -> str:
    """Keep the scene preamble and only the requested beat blocks."""
    source = str(text or "")
    wanted = {int(num) for num in beat_ids if int(num) > 0}
    if not source.strip() or not wanted:
        return source
    starts = list(_BEAT_START_RE.finditer(source))
    if not starts:
        return source
    preamble = source[: starts[0].start()].rstrip()
    chunks: List[str] = []
    for index, start in enumerate(starts):
        number = _beat_num(start.group(1))
        if number not in wanted:
            continue
        next_at = starts[index + 1].start() if index + 1 < len(starts) else len(source)
        end = _BEAT_END_RE.search(source, start.end())
        stop = end.end() if end and end.start() < next_at else next_at
        chunk = source[start.start() : stop].strip()
        if chunk:
            chunks.append(chunk)
    body = "\n\n".join(chunks)
    if preamble and body:
        return preamble + "\n\n" + body
    return body or preamble


def filter_shot_locked_to_beats(body: str, beat_ids: Sequence[int]) -> str:
    """Drop per-beat guidance lines that belong to other shots. Field blocks stay."""
    wanted = {int(num) for num in beat_ids if int(num) > 0}
    if not str(body or "").strip() or not wanted:
        return str(body or "")
    kept: List[str] = []
    for line in str(body).splitlines():
        match = _BEAT_GUIDANCE_LINE_RE.match(line.strip())
        if match and int(match.group(1)) not in wanted:
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def _entity_names(entities: Iterable[Any], *types: str) -> set:
    wanted = {item.lower() for item in types}
    names = set()
    for ent in entities or []:
        if bool(getattr(ent, "is_deleted", False)):
            continue
        kind = str(getattr(ent, "type", "") or "").strip().lower()
        if kind not in wanted:
            continue
        for value in (getattr(ent, "name", None), getattr(ent, "name_en", None)):
            cleaned = _norm(value)
            if cleaned:
                names.add(cleaned)
    return names


def _env_names_from_text(text: str) -> List[str]:
    found: List[str] = []
    for match in _ENV_TAG_RE.finditer(str(text or "")):
        name = str(match.group(1) or "").strip()
        if name and name not in found:
            found.append(name)
    return found


def _cells_by_env(injection: str) -> Dict[str, str]:
    text = str(injection or "")
    cells: Dict[str, str] = {}
    matches = list(re.finditer(r"(?m)^ENV\s*:\s*\[([^\]]+)\]", text))
    for index, match in enumerate(matches):
        name = str(match.group(1) or "").strip()
        if not name or name in cells:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        cells[name] = text[start:end]
    return cells


def _registered_subjects(cell: str) -> List[str]:
    names: List[str] = []
    for match in _SUBJECT_TAG_RE.finditer(str(cell or "")):
        name = str(match.group(1) or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _mentions_match(mention: str, names: Sequence[str], cell_text: str) -> bool:
    cleaned = _norm(mention)
    if len(cleaned) < 2:
        return True
    cell_norm = _norm(cell_text)
    if cleaned and cleaned in cell_norm:
        return True
    for name in names:
        registered = _norm(name)
        if not registered:
            continue
        if cleaned == registered or registered in cleaned:
            return True
        if len(cleaned) >= 4 and cleaned in registered:
            return True
    return False


def _camera_anchors(text: str) -> List[str]:
    anchors: List[str] = []
    for match in _CAMERA_ANCHOR_RE.finditer(str(text or "")):
        raw = str(match.group(1) or "")
        for piece in re.split(r"→|->", raw):
            piece = _ANCHOR_TAIL_RE.sub("", piece).strip(" ，,。；")
            piece = re.sub(r"^(?:从|到|向)", "", piece).strip()
            if not piece or "ENV:" in piece or piece in _SKIP_ANCHORS:
                continue
            if piece not in anchors:
                anchors.append(piece)
    return anchors


def _light_mentions(text: str) -> List[str]:
    found: List[str] = []
    for match in _LIGHT_RE.finditer(str(text or "")):
        phrase = _LIGHT_TRIM_RE.sub("", match.group(0)).strip(" ，,。；")
        if len(_norm(phrase)) < 2:
            continue
        if phrase not in found:
            found.append(phrase)
    found.sort(key=len, reverse=True)
    kept: List[str] = []
    for phrase in found:
        if any(phrase in longer for longer in kept):
            continue
        kept.append(phrase)
    return kept


def _tagged_subjects(text: str) -> List[str]:
    found: List[str] = []
    for match in _SUBJECT_TAG_RE.finditer(str(text or "")):
        name = str(match.group(1) or "").strip()
        if name and name not in found:
            found.append(name)
    return found


def check_shot_derived_subjects(
    project_entities: Sequence[Any],
    *,
    shot_logic: str,
    video_content: str,
    scene_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Return mismatches between this shot and the derived-env cells it names."""
    from app.core.entity_token import subject_compare_key
    from app.services.shot_generation_prompts import _build_scene_subject_image_prompts_cn_section

    combined = "\n".join(part for part in (shot_logic, video_content) if part)
    env_names = _env_names_from_text(combined)
    beat_ids = extract_merged_beat_ids(shot_logic)
    people = _entity_names(project_entities, "character", "角色", "char")
    props = _entity_names(project_entities, "prop", "道具")
    for match in _CHAR_TAG_RE.finditer(combined):
        people.add(_norm(match.group(1)))
    for match in _PROP_TAG_RE.finditer(combined):
        props.add(_norm(match.group(1)))

    keys = {subject_compare_key(name) for name in env_names}
    injection = ""
    if keys:
        injection = _build_scene_subject_image_prompts_cn_section(
            list(project_entities or []),
            keys,
            scene_id=scene_id,
        )
    cells = _cells_by_env(injection)
    registered: List[str] = []
    cell_text_parts: List[str] = []
    for env_name in env_names:
        cell = cells.get(env_name) or ""
        cell_text_parts.append(cell)
        for name in _registered_subjects(cell):
            if name not in registered:
                registered.append(name)
    cell_text = "\n".join(cell_text_parts)
    cell_ready = bool(registered) or ("度格-" in cell_text)

    missing: List[Dict[str, str]] = []
    seen = set()

    def _add(name: str, kind: str) -> None:
        cleaned = str(name or "").strip()
        token = _norm(cleaned)
        if len(token) < 2 or token in people or token in props or token in seen:
            return
        if _mentions_match(cleaned, registered, cell_text):
            return
        seen.add(token)
        missing.append({"name": cleaned, "kind": kind})

    for name in _tagged_subjects(combined):
        _add(name, "subject")
    for name in _camera_anchors(combined):
        _add(name, "subject")
    for name in _light_mentions(combined):
        _add(name, "light")

    reason = ""
    if not env_names:
        reason = "no_env"
    elif not cell_ready:
        reason = "no_cell"
    ok = not missing and not reason
    return {
        "ok": ok,
        "reason": reason,
        "envs": env_names,
        "beat_ids": beat_ids,
        "missing": missing,
        "cell_ready": cell_ready,
        "registered_count": len(registered),
    }
