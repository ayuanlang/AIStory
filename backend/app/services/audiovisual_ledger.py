# -*- coding: utf-8 -*-
"""Sound, score, and nameplates are written in drama and restored later by beat.

Combat, floor staging, and blocking do not receive these lines. Storyboard
generation puts them back on the matching beat. Score generation and burn-in
read the drama copy.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_BEAT_START_RE = re.compile(r"\[BEAT_START:([^\]]+)\]", re.IGNORECASE)
_BEAT_PAIR_RE = re.compile(
    r"(\[BEAT_START:([^\]]+)\])(.*?)(\[BEAT_END:\2\])",
    re.IGNORECASE | re.DOTALL,
)
_HANG_BEAT_RE = re.compile(r"挂拍\s*=\s*B(\d+)", re.IGNORECASE)
_CUE_RE = re.compile(r"【声画综合】[^\n]*")
_SCORE_RE = re.compile(r"【配乐】[^【\n]*")
_SFX_RE = re.compile(r"【音效】[^【\n]*")
_HANG_RE = re.compile(r"【名牌挂位】[^【\n]*")
_PAINT_RE = re.compile(r"画面打出物理文字标签：[^\n]*")
_SPANS = (_SCORE_RE, _SFX_RE, _HANG_RE, _PAINT_RE)
_BRIEF_HEADS = ("【名牌展现】", "【名牌标签】", "【本场环境名牌】", "【本场角色标签】")


def beat_key(raw: Any) -> str:
    text = str(raw or "").strip()
    text = re.sub(r"^B", "", text, flags=re.IGNORECASE)
    text = text.lstrip("0")
    return text or "0"


def _fields(row: str) -> Dict[str, str]:
    found: Dict[str, str] = {}
    for part in re.split(r"[｜|]", str(row or "")):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        found[key.strip()] = value.strip()
    return found


def _plate_beat(row: str) -> str:
    match = _HANG_BEAT_RE.search(str(row or ""))
    return beat_key(match.group(1)) if match else ""


def _line_items(line: str, pattern: re.Pattern[str]) -> List[str]:
    return [item.strip() for item in pattern.findall(line) if item.strip()]


def extract_audiovisual_ledger(text: str) -> Dict[str, Any]:
    beats: Dict[str, Dict[str, List[str]]] = {}
    plates: List[Dict[str, str]] = []
    labels: List[str] = []
    cue = ""
    current = ""
    in_labels = False
    for raw in str(text or "").splitlines():
        start = _BEAT_START_RE.search(raw)
        if start:
            current = beat_key(start.group(1))
            beats.setdefault(current, {"score": [], "sfx": [], "nameplates": []})
            in_labels = False
        if "【名牌前后标签】" in raw:
            in_labels = True
            rest = raw.split("【名牌前后标签】", 1)[1].strip()
            if rest.startswith("无") and "主标=" not in rest:
                in_labels = False
            elif "主标=" in rest or rest.startswith("种类="):
                labels.append(rest)
                plates.append({"beat": _plate_beat(rest), "row": rest})
            continue
        if in_labels:
            stripped = raw.strip()
            if not stripped:
                continue
            if stripped.startswith("种类=") or "主标=" in stripped:
                labels.append(stripped)
                plates.append({"beat": _plate_beat(stripped), "row": stripped})
                continue
            in_labels = False
        if not cue:
            cue_match = _CUE_RE.search(raw)
            if cue_match:
                cue = cue_match.group(0).strip()
        if not current:
            continue
        bucket = beats[current]
        bucket["score"].extend(_line_items(raw, _SCORE_RE))
        bucket["sfx"].extend(_line_items(raw, _SFX_RE))
        bucket["nameplates"].extend(_line_items(raw, _HANG_RE))
        bucket["nameplates"].extend(_line_items(raw, _PAINT_RE))
    return {"cue": cue, "labels": labels, "plates": plates, "beats": beats}


def _drop_nameplate_block(text: str) -> str:
    kept: List[str] = []
    skipping = False
    for line in str(text or "").splitlines(keepends=True):
        stripped = line.strip()
        if "【名牌前后标签】" in stripped:
            skipping = True
            rest = stripped.split("【名牌前后标签】", 1)[1].strip()
            if rest.startswith("无") and "主标=" not in rest:
                skipping = False
            continue
        if skipping:
            if not stripped or stripped.startswith("种类=") or "主标=" in stripped:
                continue
            skipping = False
        kept.append(line)
    return "".join(kept)


def _clean_passthrough_line(line: str) -> Optional[str]:
    newline = "\n" if line.endswith("\n") else ""
    body = line[:-1] if newline else line
    if body.strip().startswith("【声画综合】"):
        return None
    cleaned = body
    for pattern in _SPANS:
        cleaned = pattern.sub("", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    if body.strip() and not cleaned:
        return None
    if cleaned == body:
        return line
    return f"{cleaned}{newline}" if cleaned else None


def strip_audiovisual_passthrough(text: str) -> str:
    """Drop score, sound effects, and nameplate rows from a downstream prompt."""
    source = _drop_nameplate_block(str(text or ""))
    kept: List[str] = []
    for line in source.splitlines(keepends=True):
        cleaned = _clean_passthrough_line(line)
        if cleaned is None:
            continue
        kept.append(cleaned)
    return re.sub(r"\n{3,}", "\n\n", "".join(kept)).strip()


def strip_nameplate_instructions(text: str) -> str:
    """Drop nameplate copy rules from a brief that is not going to drama."""
    kept: List[str] = []
    skipping = False
    for line in str(text or "").splitlines(keepends=True):
        stripped = line.strip()
        if any(head in stripped for head in _BRIEF_HEADS):
            skipping = True
            continue
        if skipping and (stripped.startswith("【") or stripped.startswith("[")):
            skipping = False
        if skipping:
            continue
        kept.append(line)
    return "".join(kept).strip()


def _enters_video(row: str) -> bool:
    text = str(row or "")
    if "进视频=否" in text:
        return False
    return "进视频=是" in text


def _plate_line_for_beat(row: str) -> str:
    fields = _fields(row)
    main = fields.get("主标") or ""
    sub = fields.get("副标") or "无"
    place = fields.get("落位") or "人物下方"
    font = fields.get("字体") or ""
    style = fields.get("样式") or "无"
    color = fields.get("字色") or ""
    size = fields.get("字级") or "中"
    target = fields.get("对象") or ""
    if _enters_video(row):
        glyph = f"【{main}】" if sub in {"", "无"} else f"【{main}】{sub}】"
        return (
            f"画面打出物理文字标签：{glyph}｜落位={place}｜字体={font}｜样式={style}"
            f"｜字色={color}｜字级={size}｜名牌出字=模型直出"
        )
    mode = "后期烧录" if "模型直出" not in fields.get("出字", "") else fields.get("出字") or "后期烧录"
    return (
        f"【名牌挂位】对象={target}｜主标={main}｜副标={sub or '无'}｜落位={place}"
        f"｜字体={font}｜样式={style}｜字色={color}｜字级={size}｜出字={mode}｜进视频=否"
    )


def _append_unique(body: str, lines: List[str]) -> str:
    extra = [line for line in lines if line and line not in body]
    if not extra:
        return body
    return body.rstrip() + "\n" + "\n".join(extra) + "\n"


def restore_audiovisual_by_beat(staging_text: str, drama_text: str) -> str:
    """Put drama's score, sound effects, and nameplates back onto the same beat."""
    drama = str(drama_text or "")
    staging = str(staging_text or "")
    if not drama.strip() or not staging.strip():
        return staging
    ledger = extract_audiovisual_ledger(drama)
    if not ledger["cue"] and not ledger["labels"] and not ledger["beats"] and not ledger["plates"]:
        return staging
    text = staging
    header: List[str] = []
    if ledger["cue"] and "【声画综合】" not in text:
        header.append(ledger["cue"])
    if ledger["labels"] and "【名牌前后标签】" not in text:
        header.append("【名牌前后标签】\n" + "\n".join(ledger["labels"]))
    if header:
        blob = "\n".join(header) + "\n"
        match = _BEAT_START_RE.search(text)
        if match:
            text = text[: match.start()] + blob + text[match.start() :]
        else:
            text = text.rstrip() + "\n" + blob

    additions: Dict[str, List[str]] = {}
    for key, bucket in ledger["beats"].items():
        additions.setdefault(key, [])
        additions[key].extend(bucket["score"])
        additions[key].extend(bucket["sfx"])
        additions[key].extend(bucket["nameplates"])
    for plate in ledger["plates"]:
        key = str(plate.get("beat") or "")
        if not key:
            continue
        line = _plate_line_for_beat(str(plate.get("row") or ""))
        additions.setdefault(key, [])
        if line not in additions[key]:
            additions[key].append(line)

    def _replace(match: re.Match[str]) -> str:
        key = beat_key(match.group(2))
        body = _append_unique(match.group(3), additions.get(key) or [])
        return f"{match.group(1)}{body}{match.group(4)}"

    return _BEAT_PAIR_RE.sub(_replace, text)


def drama_text_for_scene(db: Any, episode_id: int, scene_id: str) -> str:
    from app.services.script_analysis_flow.analyze_scene_stages import (
        load_scene_subskill_results_map,
        lookup_persisted_scene_subskill_steps,
    )

    result_map = load_scene_subskill_results_map(db, int(episode_id or 0))
    steps = lookup_persisted_scene_subskill_steps(result_map, scene_id)
    return str(steps.get("drama") or "")


def restore_audiovisual_for_storyboard(
    db: Any,
    *,
    episode_id: int,
    scene_id: str,
    staging_text: str,
) -> str:
    return restore_audiovisual_by_beat(
        staging_text,
        drama_text_for_scene(db, episode_id, scene_id),
    )


def audiovisual_public(db: Any, episode_id: int, scene_marker: str) -> Dict[str, Any]:
    drama = drama_text_for_scene(db, episode_id, scene_marker)
    ledger = extract_audiovisual_ledger(drama)
    score_lines: List[str] = []
    sfx_lines: List[str] = []
    for bucket in ledger["beats"].values():
        for line in bucket["score"]:
            if line not in score_lines:
                score_lines.append(line)
        for line in bucket["sfx"]:
            if line not in sfx_lines:
                sfx_lines.append(line)
    return {
        "scene_marker": str(scene_marker or "").strip(),
        "cue": ledger["cue"],
        "score_lines": score_lines,
        "sfx_lines": sfx_lines,
        "nameplates": ledger["plates"],
    }
