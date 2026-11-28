# -*- coding: utf-8 -*-
"""Facing lock taken from an environment white model, for the four-grid skill.

The lock names which cell sees the wide face, which cell sees a door from the
front, and whether that door is open. It does not carry meters or compass
words into the cells. Characters and props are left out.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional, Sequence

from app.services.script_analysis_flow.environment_layout import layout_mass_fields

_LONG = 0.4
_CELL_ORDER = ("左上", "右上", "左下", "右下")
_VIEW = {"左上": "北", "右上": "东", "左下": "南", "右下": "西"}
_OPPOSITE = {"北": "南", "南": "北", "东": "西", "西": "东"}
_SCREEN_RIGHT = {"北": "东", "东": "南", "南": "西", "西": "北"}
_SCREEN_LEFT = {"北": "西", "东": "北", "南": "东", "西": "南"}
_DOOR_CELL = {
    "北": {"左上": "在正面", "左下": "在镜头后，不点名", "右上": "在画面左", "右下": "在画面右"},
    "南": {"左下": "在正面", "左上": "在镜头后，不点名", "右上": "在画面右", "右下": "在画面左"},
    "东": {"右上": "在正面", "右下": "在镜头后，不点名", "左上": "在画面右", "左下": "在画面左"},
    "西": {"右下": "在正面", "右上": "在镜头后，不点名", "左上": "在画面左", "左下": "在画面右"},
}
_OPEN_STATE = {
    "全关": "全关",
    "半开": "半开，门板挡住洞口的一半",
    "全开": "全开",
}
_SKIP_KINDS = {"floor", "ceiling", "person", "prop", "ramp"}


def opening_digest(opening: str) -> str:
    return hashlib.sha256(str(opening or "").strip().encode("utf-8")).hexdigest()


def _number(row: Dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def _is_screen(name: str) -> bool:
    text = str(name or "")
    return any(token in text for token in ("屏", "显示", "巨幕"))


def _wide_sentence(row: Dict[str, Any]) -> str:
    along_east = _number(row, "along_east")
    along_north = _number(row, "along_north")
    if along_east >= along_north + _LONG:
        return "左上与左下用宽的一面。右上与右下用窄的一面。"
    if along_north >= along_east + _LONG:
        return "左上与左下用窄的一面。右上与右下用宽的一面。"
    return ""


def _wall_side(row: Dict[str, Any], walls: Sequence[Dict[str, Any]]) -> str:
    along_east = _number(row, "along_east")
    along_north = _number(row, "along_north")
    east = _number(row, "east")
    north = _number(row, "north")
    runs_east = along_east >= along_north
    candidates = [
        wall for wall in walls
        if (_number(wall, "along_east") >= _number(wall, "along_north")) == runs_east
    ]
    if candidates:
        axis = "north" if runs_east else "east"
        here = north if runs_east else east
        nearest = min(candidates, key=lambda wall: abs(_number(wall, axis) - here))
        if runs_east:
            return "北" if _number(nearest, "north") >= 0 else "南"
        return "东" if _number(nearest, "east") >= 0 else "西"
    if runs_east:
        if abs(north) < 0.3:
            return ""
        return "北" if north >= 0 else "南"
    if abs(east) < 0.3:
        return ""
    return "东" if east >= 0 else "西"


def _screen_sentence(face: str) -> str:
    parts = []
    for cell in _CELL_ORDER:
        view = _VIEW[cell]
        if face == _OPPOSITE[view]:
            phrase = "屏面朝着镜头"
        elif face == view:
            phrase = "屏面背对镜头"
        elif face == _SCREEN_RIGHT[view]:
            phrase = "屏面朝画面右，见侧沿"
        else:
            phrase = "屏面朝画面左，见侧沿"
        parts.append(f"{cell}{phrase}")
    return "。".join(parts) + "。"


def _cell_sentence(side: str) -> str:
    places = _DOOR_CELL.get(side) or {}
    if not places:
        return ""
    return "。".join(f"{cell}这一格{places[cell]}" for cell in _CELL_ORDER) + "。"


def _door_sentence(row: Dict[str, Any], walls: Sequence[Dict[str, Any]]) -> str:
    parts: List[str] = []
    state = _OPEN_STATE.get(str(row.get("state") or "").strip(), "")
    if state:
        parts.append(state)
    placed = _cell_sentence(_wall_side(row, walls)).rstrip("。")
    if placed:
        parts.append(placed)
    if not parts:
        return ""
    return "。".join(parts) + "。"


def quad_facing_lock(name: str, script: str) -> str:
    """View-language facing the four-grid skill must follow for this place."""
    rows = layout_mass_fields(script)
    walls = [row for row in rows if row.get("kind") == "wall"]
    lines: List[str] = []
    for row in rows:
        kind = str(row.get("kind") or "")
        if kind in _SKIP_KINDS:
            continue
        subject = str(row.get("name") or "").strip()
        if not subject:
            continue
        face = str(row.get("face") or "").strip()
        bits: List[str] = []
        if kind == "wall":
            placed = _cell_sentence(_wall_side(row, walls)).rstrip("。")
            if placed:
                bits.append(placed)
        if kind == "furniture" and not _is_screen(subject):
            wide = _wide_sentence(row)
            if wide:
                bits.append(wide.rstrip("。"))
            if face == "上":
                bits.append("朝上。四格不写成朝着镜头")
        if kind in {"door", "window"}:
            door = _door_sentence(row, walls).rstrip("。")
            if door:
                bits.append(door)
        if _is_screen(subject) and face in _OPPOSITE:
            bits.append(_screen_sentence(face).rstrip("。"))
        if not bits:
            continue
        lines.append(f"[@{subject}]：" + "。".join(bits) + "。")
    title = str(name or "").strip() or "这一处"
    if not lines:
        return ""
    head = (
        f"【朝向锁】{title}\n"
        "白模已经拍定这一处的朝向。宽面还是窄面、哪一壁在哪一格、门在哪一格的正面、开着还是关着、屏面朝哪，按下面写。"
        "锁里写了在镜头后、不点名的壁，那一格不画。格子里不写米，不写北东南西。"
        "长短边等朝向与白模不一致的，与白模保持一致。\n"
    )
    return head + "\n".join(lines) + "\n【/朝向锁】"


_WIDE_HOW = "靠近镜头的是宽的一面。长边朝画面左右，短边从靠近镜头伸向远离镜头。"
_NARROW_HOW = "靠近镜头的是窄的一面。长边从靠近镜头伸向远离镜头，短边朝画面左右。"


def _wide_how(row: Dict[str, Any], cell: str) -> str:
    along_east = _number(row, "along_east")
    along_north = _number(row, "along_north")
    if along_east >= along_north + _LONG:
        wide = cell in {"左上", "左下"}
    elif along_north >= along_east + _LONG:
        wide = cell in {"右上", "右下"}
    else:
        return ""
    return _WIDE_HOW if wide else _NARROW_HOW


def _place_how(cell: str, side: str, *, thickness: bool) -> str:
    phrase = (_DOOR_CELL.get(side) or {}).get(cell, "")
    if phrase == "在镜头后，不点名":
        return "这一格不画这具。"
    if phrase == "在正面":
        if thickness:
            return "这一格正对这具。"
        return "这一格这具在正面，从画面左铺到画面右。"
    if phrase == "在画面左":
        if thickness:
            return "这一格这具在画面左，只见向里的厚。"
        return "这一格这具贴在画面左，一头近一头远。"
    if phrase == "在画面右":
        if thickness:
            return "这一格这具在画面右，只见向里的厚。"
        return "这一格这具贴在画面右，一头近一头远。"
    return ""


def _screen_how(cell: str, face: str) -> str:
    view = _VIEW[cell]
    if face == _OPPOSITE[view]:
        return "屏面朝着镜头。"
    if face == view:
        return "屏面背对镜头。"
    if face == _SCREEN_RIGHT[view]:
        return "屏面朝画面右，见侧沿。"
    return "屏面朝画面左，见侧沿。"


def _match_row(rows: Sequence[Dict[str, Any]], subject: str) -> Optional[Dict[str, Any]]:
    wanted = re.sub(r"\s+", "", str(subject or "")).strip("，,、。 ")
    if not wanted:
        return None
    exact = [row for row in rows if str(row.get("name") or "") == wanted and row.get("kind") not in _SKIP_KINDS]
    if len(exact) == 1:
        return exact[0]
    scored = []
    for row in rows:
        if row.get("kind") in _SKIP_KINDS:
            continue
        name = str(row.get("name") or "")
        if name and (name in wanted or wanted in name):
            scored.append((len(name), row))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return scored[0][1]


def facing_how(script: str, cell: str, subject: str) -> str:
    """Picture-language facing of one subject in one white-model cell."""
    if cell not in _CELL_ORDER:
        return ""
    rows = layout_mass_fields(script)
    walls = [row for row in rows if row.get("kind") == "wall"]
    row = _match_row(rows, subject)
    if row is None:
        return ""
    kind = str(row.get("kind") or "")
    name = str(row.get("name") or "")
    face = str(row.get("face") or "").strip()
    parts: List[str] = []
    if kind == "wall":
        parts.append(_place_how(cell, _wall_side(row, walls), thickness=False))
    if kind == "furniture" and not _is_screen(name):
        wide = _wide_how(row, cell)
        if wide:
            parts.append(wide)
        if face == "上":
            parts.append("朝上，不写成朝着镜头。")
    if kind in {"door", "window"}:
        side = _wall_side(row, walls)
        place = (_DOOR_CELL.get(side) or {}).get(cell, "")
        if place == "在镜头后，不点名":
            parts.append("这一格不画这具。")
        else:
            state = _OPEN_STATE.get(str(row.get("state") or "").strip(), "")
            if state:
                parts.append(state if state.endswith("。") else state + "。")
            parts.append(_place_how(cell, side, thickness=True))
    if _is_screen(name) and face in _OPPOSITE:
        parts.append(_screen_how(cell, face))
    kept = []
    for part in parts:
        text = str(part or "").strip()
        if not text:
            continue
        if text[-1] not in "。":
            text += "。"
        if text not in kept:
            kept.append(text)
    return "".join(kept)
