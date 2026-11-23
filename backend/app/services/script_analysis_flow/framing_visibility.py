# -*- coding: utf-8 -*-
"""After 现场编排, measure each beat's visible range from 景别 and 机位.

The white-model boxes come from 【白模测算】. They name which object is where.
Body points and furniture lips follow ordinary sizes when a box falls outside
that range. Blender places the camera and ray-casts the clay boxes. The
resulting 【可见范围】 is staging's input.
"""
from __future__ import annotations

import base64
import json
import logging
import math
import os
import re
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

_FIELD_RE = re.compile(r"([^=｜|\n]+?)=([^｜|\n]*)")
_BEAT_SPLIT_RE = re.compile(r"\[BEAT_START:([^\s\]]+)\]")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_STEPS = (
    ("十步外", 7.2),
    ("十步", 7.2),
    ("五步远", 3.6),
    ("五步", 3.6),
    ("三步", 2.2),
    ("两步", 1.4),
    ("一臂", 0.7),
    ("贴身", 0.4),
)
_LOOK = {"北": (0.0, 1.0), "南": (0.0, -1.0), "东": (1.0, 0.0), "西": (-1.0, 0.0)}


def _fields(line: str) -> Dict[str, str]:
    return {key.strip(): value.strip() for key, value in _FIELD_RE.findall(line)}


def _num(value: str, default: float = 0.0) -> float:
    found = _NUMBER_RE.search(str(value or ""))
    if not found:
        return default
    try:
        return float(found.group(0))
    except ValueError:
        return default


def _beat_key(token: str) -> str:
    found = re.search(r"(\d+)", str(token or ""))
    return found.group(1) if found else str(token or "").strip()


def _distance(value: str) -> float:
    text = str(value or "")
    for word, meters in _STEPS:
        if word in text:
            return meters
    return _num(text, 1.4)


_LEGAL_FIELDS = (8, 18, 29, 47, 84, 107)
# plain degrees, then degrees marked 略松 / 偏松 / 偏紧 / 勉强. None means 无法.
_F2_CELLS = {
    ("贴身", "ECU"): ((18,), (29,)),
    ("贴身", "CU"): ((47,), ()),
    ("贴身", "MCU"): ((84,), ()),
    ("一臂", "ECU"): ((18,), ()),
    ("一臂", "CU"): ((29, 47), ()),
    ("一臂", "MCU"): ((84,), ()),
    ("一臂", "MS"): ((), (107,)),
    ("两步", "ECU"): ((8, 18), ()),
    ("两步", "CU"): ((18,), ()),
    ("两步", "MCU"): ((29,), (47,)),
    ("两步", "MS"): ((47,), ()),
    ("两步", "FS"): ((84,), ()),
    ("两步", "WS"): ((107,), ()),
    ("三步", "ECU"): ((8,), ()),
    ("三步", "CU"): ((8,), ()),
    ("三步", "MCU"): ((18, 29), ()),
    ("三步", "MS"): ((29, 47), ()),
    ("三步", "FS"): ((84,), (47,)),
    ("三步", "WS"): ((84, 107), ()),
    ("三步", "EWS"): ((107,), ()),
    ("五步", "CU"): ((8,), ()),
    ("五步", "MCU"): ((18,), ()),
    ("五步", "MS"): ((18, 29), ()),
    ("五步", "FS"): ((29, 47), ()),
    ("五步", "WS"): ((47, 84), ()),
    ("五步", "EWS"): ((84, 107), ()),
    ("十步", "MCU"): ((8,), ()),
    ("十步", "MS"): ((8, 18), ()),
    ("十步", "FS"): ((18, 29), ()),
    ("十步", "WS"): ((29, 47), ()),
    ("十步", "EWS"): ((84, 107), ()),
}
_DEFAULT_BAND = {
    "ECU": "贴身",
    "CU": "贴身",
    "MCU": "一臂",
    "MS": "两步",
    "FS": "三步",
    "WS": "五步",
    "EWS": "十步",
}
_BANDS = ("贴身", "一臂", "两步", "三步", "五步", "十步")


def _band_of(meters: float) -> str:
    if meters <= 0.5:
        return "贴身"
    if meters <= 1.0:
        return "一臂"
    if meters <= 1.8:
        return "两步"
    if meters <= 3.0:
        return "三步"
    if meters <= 5.5:
        return "五步"
    return "十步"


def _legal_field(explicit: str) -> Optional[int]:
    number = int(round(_num(explicit, 0)))
    if number in _LEGAL_FIELDS:
        return number
    return None


def _pick_cell(shot_size: str, band: str) -> Optional[int]:
    cell = _F2_CELLS.get((band, shot_size))
    if cell is None:
        return None
    plain, marked = cell
    options = plain or marked
    if not options:
        return None
    if len(options) == 1:
        return options[0]
    if shot_size in {"ECU", "CU", "MCU"}:
        return min(options)
    return max(options)


def _field_of(shot_size: str, explicit: str, distance: float = 1.4) -> int:
    locked = _legal_field(explicit)
    if locked is not None:
        return locked
    shot_size = str(shot_size or "MS").upper()
    band = _band_of(distance)
    chosen = _pick_cell(shot_size, band)
    if chosen is not None:
        return chosen
    fallback = _pick_cell(shot_size, _DEFAULT_BAND.get(shot_size, "两步"))
    return fallback if fallback is not None else 47


def _split_beats(text: str) -> tuple[str, List[tuple[str, str]]]:
    parts = _BEAT_SPLIT_RE.split(str(text or ""))
    header = parts[0]
    beats: List[tuple[str, str]] = []
    index = 1
    while index + 1 < len(parts):
        body = parts[index + 1]
        end = body.find("[BEAT_END:")
        if end >= 0:
            body = body[:end]
        beats.append((parts[index].strip(), body))
        index += 2
    return header, beats


def _box_from(kind: str, fields: Dict[str, str]) -> Optional[Dict[str, Any]]:
    name = fields.get(kind) or fields.get("名") or ""
    if not name or name in {"地面", "天花"}:
        return None
    relation = fields.get("关系", "")
    if relation in {"地面", "天花"}:
        return None
    eye = _num(fields.get("眼高", ""), 0.0)
    height = max(0.05, _num(fields.get("高", ""), 0.2))
    bottom = _num(fields.get("底", ""), 0.0)
    if kind == "人" and eye <= 0:
        eye = bottom + min(1.60, height * 0.94)
    return {
        "name": name,
        "kind": kind,
        "east": _num(fields.get("东", "")),
        "north": _num(fields.get("北", "")),
        "bottom": bottom,
        "along_east": max(0.05, _num(fields.get("沿东", ""), 0.4)),
        "along_north": max(0.05, _num(fields.get("沿北", ""), 0.4)),
        "height": height,
        "eye": eye,
        "transparent": (
            fields.get("透", "") == "透"
            or fields.get("壳", "") == "透视"
            or fields.get("实体类", "") == "虚拟"
            or any(word in name for word in ("玻璃", "水晶", "全息", "投影", "幻影"))
        ),
        "open_state": fields.get("开闭", ""),
        "relation": relation,
        "stature": fields.get("体格", ""),
        "stature_m": _num(fields.get("身高", ""), 0.0),
        "chest_h": _num(fields.get("胸高", ""), 0.0),
        "waist_h": _num(fields.get("腰高", ""), 0.0),
        "knee_h": _num(fields.get("膝高", ""), 0.0),
    }


def _lines_of(chunk: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for raw in str(chunk or "").splitlines():
        fields = _fields(raw)
        if fields:
            rows.append(fields)
    return rows


def _camera_from_mirror(fields: Dict[str, str], beat: str) -> Optional[Dict[str, Any]]:
    look = fields.get("望", "")
    if look not in _LOOK:
        return None
    shot_size = str(fields.get("景别", "") or "MS").upper()
    placed = "东" in fields and "北" in fields
    return {
        "beat": beat,
        "east": _num(fields.get("东", "")),
        "north": _num(fields.get("北", "")),
        "height": _num(fields.get("高", ""), 1.6),
        "look": look,
        "shot_size": shot_size,
        "field": _field_of(shot_size, fields.get("视场", ""), _distance(fields.get("机位距", ""))),
        "field_explicit": fields.get("视场", "") if _legal_field(fields.get("视场", "")) else "",
        "subject": fields.get("主拍对象", ""),
        "frame_owner": fields.get("框主", ""),
        "shot_method": fields.get("拍法", ""),
        "placed": placed,
    }


def _derive_camera(fields: Dict[str, str], beat: str, boxes: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    look = fields.get("望", "")
    shot_size = str(fields.get("景别", "") or "").upper()
    if look not in _LOOK or not shot_size:
        return None
    subject = fields.get("主拍对象", "")
    host = _match_box(subject, boxes)
    if host is None:
        return None
    distance = _distance(fields.get("机位距", ""))
    east = float(host["east"])
    north = float(host["north"])
    if look == "北":
        north -= distance
    elif look == "南":
        north += distance
    elif look == "东":
        east -= distance
    else:
        east += distance
    eye = float(host.get("eye") or host["bottom"] + host["height"] * 0.5)
    height_word = fields.get("机高", "")
    if "略高" in height_word:
        eye += 0.15
    elif "略低" in height_word:
        eye -= 0.15
    elif "远高于" in height_word or "航拍" in height_word or "鸟瞰" in height_word:
        eye = float(host["bottom"]) + float(host["height"]) + 3.60
    elif "膝" in height_word:
        eye = 0.50
    elif "腰" in height_word:
        eye = 1.00
    return {
        "beat": beat,
        "east": east,
        "north": north,
        "height": eye,
        "look": look,
        "shot_size": shot_size,
        "field": _field_of(shot_size, fields.get("视场", ""), _distance(fields.get("机位距", ""))),
        "field_explicit": fields.get("视场", "") if _legal_field(fields.get("视场", "")) else "",
        "subject": subject,
        "frame_owner": fields.get("框主", ""),
        "shot_method": fields.get("拍法", ""),
        "placed": False,
    }


def _match_box(token: str, boxes: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    needle = str(token or "").strip()
    if not needle:
        return None
    for box in boxes:
        name = str(box["name"])
        if needle == name or needle in name or name in needle:
            return box
    return None


def parse_framing(text: str) -> Dict[str, Any]:
    """Read white-model boxes and one camera per beat."""
    header, beats = _split_beats(text)
    boxes: List[Dict[str, Any]] = []
    mirrors: Dict[str, Dict[str, Any]] = {}
    for fields in _lines_of(header):
        for kind in ("具", "人", "件"):
            if kind in fields:
                box = _box_from(kind, fields)
                if box is not None:
                    box["beat"] = _beat_key(fields.get("拍", "开场")) or "开场"
                    boxes.append(box)
        if "镜" in fields:
            camera = _camera_from_mirror(fields, _beat_key(fields.get("镜", "")))
            if camera is not None:
                mirrors[camera["beat"]] = camera
    shots: List[Dict[str, Any]] = []
    beat_boxes: Dict[str, List[Dict[str, Any]]] = {}
    for beat_id, body in beats:
        key = _beat_key(beat_id)
        body_rows = _lines_of(body)
        present = {"人": [], "件": []}
        local = [box for box in boxes if box.get("kind") == "具" and box.get("beat") in {"开场", "", key}]
        for fields in body_rows:
            for kind in ("人", "件", "具"):
                if kind not in fields:
                    continue
                box = _box_from(kind, fields)
                if box is None:
                    continue
                if kind in present:
                    present[kind].append(box)
                    continue
                local = [item for item in local if item["name"] != box["name"]]
                local.append(box)
        for kind, rows in present.items():
            if rows:
                local.extend(rows)
            else:
                local.extend(box for box in boxes if box.get("kind") == kind and box.get("beat") in {"开场", "", key})
        for fields in body_rows:
            if "镜" in fields:
                camera = _camera_from_mirror(fields, key)
                if camera is not None:
                    mirrors[key] = camera
        merged: Dict[str, str] = {}
        for fields in body_rows:
            merged.update(fields)
        camera = mirrors.get(key)
        if camera is None or not camera.get("placed"):
            derived = _derive_camera(merged, key, local)
            if derived is not None:
                if camera is not None and camera.get("placed"):
                    derived["east"] = camera["east"]
                    derived["north"] = camera["north"]
                    derived["height"] = camera["height"]
                camera = derived
        if camera is None:
            continue
        camera = dict(camera)
        camera["beat"] = key
        camera["subject"] = camera.get("subject") or merged.get("主拍对象", "")
        camera["frame_owner"] = camera.get("frame_owner") or merged.get("框主", "")
        camera["shot_method"] = camera.get("shot_method") or merged.get("拍法", "")
        if merged.get("景别"):
            camera["shot_size"] = str(merged.get("景别")).upper()
        explicit = merged.get("视场", "") or str(camera.get("field_explicit") or "")
        distance = _distance(merged.get("机位距", ""))
        if "机位距" not in merged and camera.get("placed"):
            host = _match_box(str(camera.get("subject") or ""), local)
            if host is not None:
                distance = math.hypot(float(camera["east"]) - float(host["east"]), float(camera["north"]) - float(host["north"]))
        camera["field"] = _field_of(str(camera.get("shot_size") or ""), explicit, distance)
        shots.append(camera)
        beat_boxes[key] = local
    return {"boxes": boxes, "shots": shots, "beat_boxes": beat_boxes}


def _target(box: Dict[str, Any]) -> tuple[float, float, float]:
    if box["kind"] == "人":
        return (float(box["east"]), float(box["north"]), float(box["eye"] or box["bottom"] + 1.6))
    return (
        float(box["east"]),
        float(box["north"]),
        float(box["bottom"]) + float(box["height"]) * 0.5,
    )


def _depth_and_lateral(look: str, camera: Dict[str, Any], point: Sequence[float]) -> tuple[float, float, float]:
    east = float(point[0]) - float(camera["east"])
    north = float(point[1]) - float(camera["north"])
    if look == "北":
        return north, east, float(point[2]) - float(camera["height"])
    if look == "南":
        return -north, -east, float(point[2]) - float(camera["height"])
    if look == "东":
        return east, -north, float(point[2]) - float(camera["height"])
    return -east, north, float(point[2]) - float(camera["height"])


def _half_angles(field: int) -> tuple[float, float]:
    half_h = math.tan(math.radians(float(field) / 2.0))
    half_v = half_h * 9.0 / 16.0
    return half_h, half_v


def _corners(box: Dict[str, Any]) -> List[tuple[float, float, float]]:
    hx = float(box["along_east"]) / 2.0
    hy = float(box["along_north"]) / 2.0
    z0 = float(box["bottom"])
    z1 = z0 + float(box["height"])
    cx = float(box["east"])
    cy = float(box["north"])
    return [
        (cx + sx, cy + sy, sz)
        for sx in (-hx, hx)
        for sy in (-hy, hy)
        for sz in (z0, z1)
    ]


def _in_frustum(camera: Dict[str, Any], box: Dict[str, Any]) -> tuple[float, bool]:
    half_h, half_v = _half_angles(int(camera["field"]))
    depth, lateral, vertical = _depth_and_lateral(camera["look"], camera, _target(box))
    points = [_target(box), *_corners(box)]
    inside = False
    nearest = depth
    for point in points:
        point_depth, point_lateral, point_vertical = _depth_and_lateral(camera["look"], camera, point)
        nearest = min(nearest, point_depth)
        if point_depth <= 0.05:
            continue
        allowance_h = point_depth * half_h
        allowance_v = point_depth * half_v
        if abs(point_lateral) <= allowance_h and abs(point_vertical) <= allowance_v:
            inside = True
    return nearest, inside


def _segment_hits(origin: Sequence[float], target: Sequence[float], box: Dict[str, Any]) -> bool:
    bounds = (
        (float(box["east"]) - float(box["along_east"]) / 2.0, float(box["east"]) + float(box["along_east"]) / 2.0),
        (float(box["north"]) - float(box["along_north"]) / 2.0, float(box["north"]) + float(box["along_north"]) / 2.0),
        (float(box["bottom"]), float(box["bottom"]) + float(box["height"])),
    )
    start = 0.02
    end = 0.92
    for axis in range(3):
        delta = float(target[axis]) - float(origin[axis])
        lo, hi = bounds[axis]
        if abs(delta) < 1e-8:
            if float(origin[axis]) < lo or float(origin[axis]) > hi:
                return False
            continue
        inv = 1.0 / delta
        near = (lo - float(origin[axis])) * inv
        far = (hi - float(origin[axis])) * inv
        if near > far:
            near, far = far, near
        start = max(start, near)
        end = min(end, far)
        if start > end:
            return False
    return True


def _posture(box: Dict[str, Any]) -> str:
    bottom = float(box["bottom"])
    height = float(box["height"])
    if bottom >= 0.25 and height <= 0.55:
        return "躺"
    if bottom >= 0.25:
        return "坐"
    return "站"


def _is_child(box: Dict[str, Any]) -> bool:
    stature = str(box.get("stature") or "")
    if "小孩" in stature or "儿童" in stature or "幼儿" in stature:
        return True
    if "成人" in stature:
        return False
    eye = float(box.get("eye") or 0.0)
    height = float(box["height"])
    posture = _posture(box)
    if posture == "站":
        return height < 1.40 or (0.0 < eye < 1.30)
    if posture == "坐":
        return (0.0 < eye < 1.00) or height < 1.05
    return height < 0.30


def _in_band(value: float, low: float, high: float, fallback: float) -> float:
    if low <= value <= high:
        return value
    return fallback


def _cover(box: Dict[str, Any]) -> Optional[tuple]:
    """Functional lip of a common piece: (kind, blocking height, seat height).

    The box only says which object this is. The lip is the ordinary edge that
    hides a person on the far side. A box height outside that object's range
    falls back to the ordinary height.
    """
    if box.get("kind") != "具":
        return None
    name = str(box["name"])
    top = float(box["bottom"]) + float(box["height"])
    height = float(box["height"])
    if any(word in name for word in ("柜台", "吧台", "隔断", "墙")):
        return None
    if "柜" in name and not any(word in name for word in ("桌", "案")):
        return None
    if any(word in name for word in ("床", "榻")):
        lip = _in_band(top, 0.40, 0.70, 0.55)
        return ("床", lip, lip)
    if "沙发" in name:
        lip = _in_band(top, 0.75, 1.05, 0.90)
        return ("沙发", lip, float(box["bottom"]) + 0.42)
    if "凳" in name and "椅" not in name:
        lip = _in_band(top, 0.35, 0.55, 0.45)
        return ("凳", lip, lip)
    if "椅" in name:
        if height <= 0.60:
            lip = _in_band(top, 0.35, 0.60, 0.45)
            return ("椅", lip, lip)
        lip = _in_band(top, 0.75, 1.05, 0.90)
        return ("椅", lip, float(box["bottom"]) + 0.45)
    if "几" in name and not any(word in name for word in ("桌", "案", "台")):
        return ("几", _in_band(top, 0.28, 0.55, 0.42), None)
    if any(word in name for word in ("桌", "案", "台")):
        return ("桌", _in_band(top, 0.60, 0.85, 0.75), None)
    return None


def _plan_overlap(person: Dict[str, Any], furniture: Dict[str, Any]) -> bool:
    return (
        abs(float(person["east"]) - float(furniture["east"])) <= float(furniture["along_east"]) / 2.0 + 0.2
        and abs(float(person["north"]) - float(furniture["north"])) <= float(furniture["along_north"]) / 2.0 + 0.2
    )


def _is_seat(person: Dict[str, Any], furniture: Dict[str, Any]) -> bool:
    if person.get("kind") != "人" or furniture.get("kind") != "具":
        return False
    if not _plan_overlap(person, furniture):
        return False
    top = float(furniture["bottom"]) + float(furniture["height"])
    bottom = float(person["bottom"])
    if abs(bottom - top) <= 0.08:
        return True
    cover = _cover(furniture)
    seat = cover[2] if cover is not None else None
    return seat is not None and abs(bottom - float(seat)) <= 0.12


def _physical_body(box: Dict[str, Any]) -> tuple:
    """Locked 身高 and 眼高 win. A box is used only while it sits in range."""
    posture = _posture(box)
    child = _is_child(box)
    height = float(box["height"])
    eye = float(box.get("eye") or 0.0)
    bottom = float(box["bottom"])
    stature = float(box.get("stature_m") or 0.0)
    if posture == "站" and 0.70 <= stature <= 2.20 and 0.55 <= eye <= stature:
        return posture, stature < 1.45, stature, eye, 0.0 if bottom < 0.25 else bottom
    if posture == "站":
        if child and 0.70 <= height <= 1.40 and 0.60 <= eye <= 1.30:
            return posture, child, height, eye, bottom
        if child:
            return posture, child, 1.15, 1.05, 0.0
        if 1.50 <= height <= 1.95 and 1.40 <= eye <= 1.80:
            return posture, child, height, eye, bottom
        return posture, child, 1.70, 1.60, 0.0
    if posture == "坐":
        seat = 0.45 if bottom > 0.60 else bottom
        if float(box.get("chest_h") or 0.0) > 0 and eye > 0:
            return posture, child, stature or height, eye, seat
        if child and 0.65 <= eye <= 0.95:
            return posture, child, height, eye, seat
        if child:
            return posture, child, 0.85, 0.78, 0.45
        if 1.05 <= eye <= 1.30:
            return posture, child, height, eye, seat
        return posture, child, 1.25, 1.15, 0.45
    return posture, child, height, eye or bottom + 0.25, bottom


def _locked_marks(box: Dict[str, Any], posture: str, height: float, eye: float, bottom: float) -> Optional[Dict[str, float]]:
    chest = float(box.get("chest_h") or 0.0)
    waist = float(box.get("waist_h") or 0.0)
    knee = float(box.get("knee_h") or 0.0)
    if chest <= 0 or waist <= 0 or knee <= 0 or eye <= 0:
        return None
    if posture == "站":
        return {"头": eye, "胸": chest, "腰": waist, "腿": knee}
    if posture == "坐":
        seat = 0.45 if bottom > 0.60 else bottom
        hip = height * 0.53
        return {
            "头": seat + (eye - hip),
            "胸": seat + (chest - hip),
            "腰": seat + 0.18,
            "腿": max(0.12, seat - 0.12),
        }
    return None


def _body_points(box: Dict[str, Any]) -> List[tuple]:
    east = float(box["east"])
    north = float(box["north"])
    posture, child, height, eye, bottom = _physical_body(box)
    locked = _locked_marks(box, posture, height, eye, bottom)
    if locked is not None:
        marks = locked
    elif posture == "躺":
        marks = {
            "头": bottom + min(0.28, height * 0.7),
            "胸": bottom + min(0.20, height * 0.5),
            "腰": bottom + min(0.14, height * 0.35),
            "腿": bottom + min(0.08, height * 0.2),
        }
    elif posture == "坐":
        seat = 0.45 if bottom > 0.60 else bottom
        marks = {
            "头": eye,
            "胸": eye - (0.12 if child else 0.20),
            "腰": seat + 0.18,
            "腿": max(0.12, seat - 0.12),
        }
    elif child:
        marks = {
            "头": eye,
            "胸": bottom + height * 0.75,
            "腰": bottom + height * 0.58,
            "腿": bottom + height * 0.30,
        }
    else:
        marks = {
            "头": eye,
            "胸": eye - 0.22,
            "腰": eye - 0.50,
            "腿": min(max(eye - 1.05, bottom + 0.15), eye - 0.35),
        }
    if posture != "坐":
        top = bottom + height
        marks = {name: z for name, z in marks.items() if bottom - 0.02 <= z <= top + 0.02}
    return [(name, (east, north, z)) for name, z in (("头", marks.get("头")), ("胸", marks.get("胸")), ("腰", marks.get("腰")), ("腿", marks.get("腿"))) if z is not None]


def _plan_between(origin: Sequence[float], target: Sequence[float], box: Dict[str, Any]) -> bool:
    bounds = (
        (float(box["east"]) - float(box["along_east"]) / 2.0, float(box["east"]) + float(box["along_east"]) / 2.0),
        (float(box["north"]) - float(box["along_north"]) / 2.0, float(box["north"]) + float(box["along_north"]) / 2.0),
    )
    start = 0.0
    end = 0.98
    for axis in range(2):
        delta = float(target[axis]) - float(origin[axis])
        lo, hi = bounds[axis]
        if abs(delta) < 1e-8:
            if float(origin[axis]) < lo or float(origin[axis]) > hi:
                return False
            continue
        inv = 1.0 / delta
        near = (lo - float(origin[axis])) * inv
        far = (hi - float(origin[axis])) * inv
        if near > far:
            near, far = far, near
        start = max(start, near)
        end = min(end, far)
        if start > end:
            return False
    return True


def _point_in_cone(camera: Dict[str, Any], point: Sequence[float]) -> bool:
    depth, lateral, vertical = _depth_and_lateral(camera["look"], camera, point)
    if depth <= 0.05:
        return False
    half_h, half_v = _half_angles(int(camera["field"]))
    return abs(lateral) <= depth * half_h and abs(vertical) <= depth * half_v


def _occluder(camera: Dict[str, Any], box: Dict[str, Any], boxes: Sequence[Dict[str, Any]], point: Optional[Sequence[float]] = None) -> str:
    if box.get("transparent") or box.get("open_state") in {"全开", "半开"}:
        return ""
    origin = (float(camera["east"]), float(camera["north"]), float(camera["height"]))
    target = tuple(point) if point is not None else _target(box)
    for other in boxes:
        if other["name"] == box["name"]:
            continue
        if other.get("transparent") or other.get("relation") in {"地面", "天花"}:
            continue
        if other.get("open_state") in {"全开", "半开"}:
            continue
        if _is_seat(box, other):
            continue
        cover = _cover(other) if point is not None else None
        if cover is not None:
            if float(target[2]) <= float(cover[1]) + 0.02 and _plan_between(origin, target, other):
                return str(other["name"])
            continue
        if _segment_hits(origin, target, other):
            return str(other["name"])
    return ""


def python_probes(camera: Dict[str, Any], boxes: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    probes: List[Dict[str, Any]] = []
    for box in boxes:
        depth, inside = _in_frustum(camera, box)
        probes.append({
            "name": box["name"],
            "depth": round(depth, 3),
            "in_frustum": inside,
            "occluder": "" if depth <= 0.05 or not inside else _occluder(camera, box, boxes),
        })
    return probes


def classify_shot(camera: Dict[str, Any], boxes: Sequence[Dict[str, Any]], probes: Sequence[Dict[str, Any]]) -> Dict[str, List[str]]:
    by_name = {str(item["name"]): item for item in probes}
    groups = {"可见": [], "镜后": [], "景别外": [], "遮挡": []}
    for box in boxes:
        probe = by_name.get(str(box["name"]))
        if probe is None:
            continue
        depth = float(probe.get("depth") or 0.0)
        if depth <= 0.05:
            groups["镜后"].append(str(box["name"]))
            continue
        if not probe.get("in_frustum"):
            groups["景别外"].append(str(box["name"]))
            continue
        if box.get("kind") == "人":
            shown = []
            blocker = ""
            for part, point in _body_points(box):
                if not _point_in_cone(camera, point):
                    continue
                hit = _occluder(camera, box, boxes, point)
                if hit:
                    blocker = blocker or hit
                else:
                    shown.append(part)
            if shown:
                groups["可见"].append(f"{box['name']}{{{','.join(shown)}}}")
                continue
            if blocker:
                groups["遮挡"].append(f"{box['name']}<{blocker}>")
                continue
            groups["景别外"].append(str(box["name"]))
            continue
        blocker = str(probe.get("occluder") or "")
        if blocker:
            groups["遮挡"].append(f"{box['name']}<{blocker}>")
            continue
        groups["可见"].append(str(box["name"]))
    return groups


def _join(names: Sequence[str]) -> str:
    return "，".join(names) if names else "无"


def format_block(shots: Sequence[Dict[str, Any]], grouped: Dict[str, Dict[str, List[str]]], source: str) -> str:
    lines = ["【可见范围】", f"来源={source}｜依据=景别+机位"]
    for shot in shots:
        groups = grouped.get(shot["beat"], {"可见": [], "镜后": [], "景别外": [], "遮挡": []})
        lines.append(
            "｜".join([
                f"B{shot['beat']}",
                f"景别={shot['shot_size']}",
                f"视场={int(shot['field'])}",
                f"望={shot['look']}",
                f"机位=东{_num(str(shot['east'])):.1f}北{_num(str(shot['north'])):.1f}高{_num(str(shot['height'])):.1f}",
                f"可见={_join(groups['可见'])}",
                f"镜后={_join(groups['镜后'])}",
                f"景别外={_join(groups['景别外'])}",
                f"遮挡={_join(groups['遮挡'])}",
            ])
        )
    return "\n".join(lines)


_BLENDER_TEMPLATE = r"""
import base64
import json
import math
import sys

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

PAYLOAD = json.loads(base64.b64decode("{payload_b64}").decode("utf-8"))
OUT = sys.argv[sys.argv.index("--") + 1]

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

def add_box(name, east, north, bottom, along_east, along_north, height):
    mesh = bpy.data.meshes.new(name)
    tool = bmesh.new()
    bmesh.ops.create_cube(tool, size=1.0)
    tool.to_mesh(mesh)
    tool.free()
    mesh.transform(Matrix.Diagonal((float(along_east), float(along_north), float(height))).to_4x4())
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (float(east), float(north), float(bottom) + float(height) / 2.0)
    bpy.context.scene.collection.objects.link(obj)
    return obj

def point_in_frame(scene, cam, target):
    co = world_to_camera_view(scene, cam, target)
    return co.z > 0.05 and 0.0 <= co.x <= 1.0 and 0.0 <= co.y <= 1.0

LOOK = {{"北": Vector((0.0, 1.0, 0.0)), "南": Vector((0.0, -1.0, 0.0)), "东": Vector((1.0, 0.0, 0.0)), "西": Vector((-1.0, 0.0, 0.0))}}

scene = bpy.context.scene
scene.render.resolution_x = 64
scene.render.resolution_y = 36
made = {{}}
for box in PAYLOAD["boxes"]:
    if box.get("transparent") or box.get("relation") in ("地面", "天花") or box.get("open_state") in ("全开", "半开"):
        continue
    made[box["name"]] = add_box(box["name"], box["east"], box["north"], box["bottom"], box["along_east"], box["along_north"], box["height"])
bpy.context.view_layer.update()
depsgraph = bpy.context.evaluated_depsgraph_get()

def camera(shot):
    data = bpy.data.cameras.new("cam")
    field = float(shot.get("field") or 47)
    data.lens = 18.0 / math.tan(math.radians(field / 2.0))
    data.sensor_width = 36.0
    data.sensor_fit = "HORIZONTAL"
    data.clip_start = 0.02
    obj = bpy.data.objects.new("cam", data)
    obj.location = (float(shot["east"]), float(shot["north"]), float(shot["height"]))
    obj.rotation_euler = LOOK[shot["look"]].to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(obj)
    return obj

results = []
for shot in PAYLOAD["shots"]:
    cam = camera(shot)
    scene.camera = cam
    bpy.context.view_layer.update()
    origin = Vector((float(shot["east"]), float(shot["north"]), float(shot["height"])))
    probes = []
    for box in shot["boxes"]:
        target = Vector(box["target"])
        direction = target - origin
        distance = direction.length
        if distance < 0.05:
            probes.append({{"name": box["name"], "in_frustum": False, "occluder": ""}})
            continue
        direction.normalize()
        hit, _loc, _normal, _face, obj, _matrix = scene.ray_cast(depsgraph, origin + direction * 0.05, direction, distance=max(0.0, distance - 0.08))
        occluder = ""
        if hit and obj is not None and obj.name != box["name"]:
            occluder = obj.name
        co = point_in_frame(scene, cam, target)
        probes.append({{"name": box["name"], "in_frustum": bool(co), "occluder": occluder}})
    results.append({{"beat": shot["beat"], "probes": probes}})
    bpy.data.objects.remove(cam, do_unlink=True)

with open(OUT, "w", encoding="utf-8") as handle:
    json.dump(results, handle, ensure_ascii=False)
"""


def _blender_payload(parsed: Dict[str, Any]) -> Dict[str, Any]:
    shots = []
    for shot in parsed["shots"]:
        boxes = parsed["beat_boxes"].get(shot["beat"], [])
        shots.append({
            "beat": shot["beat"],
            "east": shot["east"],
            "north": shot["north"],
            "height": shot["height"],
            "look": shot["look"],
            "field": shot["field"],
            "boxes": [
                {"name": box["name"], "target": list(_target(box))}
                for box in boxes
            ],
        })
    opaque = []
    seen = set()
    for box in parsed["boxes"]:
        if box["name"] in seen:
            continue
        seen.add(box["name"])
        opaque.append(box)
    for boxes in parsed["beat_boxes"].values():
        for box in boxes:
            if box["name"] in seen:
                continue
            seen.add(box["name"])
            opaque.append(box)
    return {"boxes": opaque, "shots": shots}


def measure_with_blender(parsed: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    try:
        from app.services.script_analysis_flow.environment_layout_blender import (
            blender_executable,
            blender_process_env,
        )

        exe = blender_executable()
    except Exception as exc:
        logger.info("visibility blender unavailable: %s", exc)
        return None
    payload = base64.b64encode(json.dumps(_blender_payload(parsed), ensure_ascii=False).encode("utf-8")).decode("ascii")
    script = _BLENDER_TEMPLATE.format(payload_b64=payload)
    with tempfile.TemporaryDirectory(prefix="aistory-view-") as folder:
        script_path = os.path.join(folder, "visibility.py")
        out_path = os.path.join(folder, "visibility.json")
        with open(script_path, "w", encoding="utf-8") as handle:
            handle.write(script)
        try:
            completed = subprocess.run(
                [exe, "--background", "--python", script_path, "--", out_path],
                capture_output=True,
                timeout=120,
                check=False,
                env=blender_process_env(exe),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.info("visibility blender failed: %s", exc)
            return None
        if completed.returncode != 0 or not os.path.isfile(out_path):
            log = ((completed.stderr or b"") + b"\n" + (completed.stdout or b"")).decode("utf-8", "replace")
            logger.info("visibility blender rejected: %s", " ".join(log.splitlines()[-8:]))
            return None
        try:
            data = json.loads(open(out_path, encoding="utf-8").read())
        except (OSError, json.JSONDecodeError):
            return None
    return data if isinstance(data, list) else None


def _merge_probes(camera: Dict[str, Any], boxes: Sequence[Dict[str, Any]], blender_rows: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    base = {item["name"]: item for item in python_probes(camera, boxes)}
    if not blender_rows:
        return list(base.values())
    row = next((item for item in blender_rows if str(item.get("beat")) == str(camera["beat"])), None)
    if not row:
        return list(base.values())
    for probe in row.get("probes") or []:
        name = str(probe.get("name") or "")
        if name not in base:
            continue
        base[name]["in_frustum"] = bool(probe.get("in_frustum"))
        base[name]["occluder"] = str(probe.get("occluder") or "")
    return list(base.values())


def visible_range_block(framing_text: str, *, use_blender: bool = True) -> str:
    """Build 【可见范围】 from the framing draft. Empty when the draft has no camera."""
    parsed = parse_framing(framing_text)
    if not parsed["shots"]:
        return ""
    blender_rows = measure_with_blender(parsed) if use_blender else None
    source = "Blender" if blender_rows else "测算"
    grouped: Dict[str, Dict[str, List[str]]] = {}
    for shot in parsed["shots"]:
        boxes = parsed["beat_boxes"].get(shot["beat"], [])
        probes = _merge_probes(shot, boxes, blender_rows)
        grouped[shot["beat"]] = classify_shot(shot, boxes, probes)
    return format_block(parsed["shots"], grouped, source)


def prepend_visibility_range(staging_text: str, framing_text: str) -> str:
    """Put the measured range in front of the staging scene. Keep the framing draft unchanged."""
    block = visible_range_block(framing_text)
    if not block:
        return staging_text
    body = re.sub(r"【可见范围】[\s\S]*?(?=\n【|\n\[|\Z)", "", str(staging_text or "")).strip()
    return f"{block}\n\n{body}".strip()
