# -*- coding: utf-8 -*-
"""Turn a locked opening into a Blender white-model script.

A text model writes the script. Blender builds the masses and renders the
four-grid sheet. This module does not call an image model and does not
change the opening.
"""
from __future__ import annotations

import io
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw

Vec3 = Tuple[float, float, float]

_METER = r"(-?\d+(?:\.\d+)?)"
_ORIGIN_RE = re.compile(rf"距原点=北{_METER}米东{_METER}米")
_ALONG_RE = re.compile(rf"占地=沿墙{_METER}米×高{_METER}米×厚{_METER}米")
_PLAN_RE = re.compile(rf"占地={_METER}×{_METER}米")
_RADIUS_RE = re.compile(rf"半径={_METER}米")
_FLOOR_RE = re.compile(rf"尺度=南北{_METER}米×东西{_METER}米")
_WALL_H_RE = re.compile(rf"墙高={_METER}米")
_FOCAL_RE = re.compile(rf"焦段(?:选择)?=[^\d]*{_METER}")
_SPAN_RE = re.compile(rf"场径=北{_METER}米｜东{_METER}米｜南{_METER}米｜西{_METER}米")
_NAME_RE = re.compile(r"\[@([^\]]+)\]")
_SHORT_NAME_RE = re.compile(r"([\u4e00-\u9fffA-Za-z0-9_]{1,12})号=#")
_REL_RE = re.compile(r"壁关系=([^｜\|。\n]+)")
_AXIS_RE = re.compile(r"长边平行=(X线|Y线)")
_WALL_SIDE_RE = re.compile(r"所属壁=([北东南西])")
_HEART_RE = re.compile(r"心点=正([北东南西])")
_OPEN_RE = re.compile(r"开闭=(全开|半开|全关)")
_HINGE_RE = re.compile(r"铰链端=([东西南北])端")
_LIFT_RE = re.compile(rf"离平地={_METER}米")
_SUBJECT_HEAD_RE = re.compile(r"\[@([^\]]+)\]|(?<![@\[])([\u4e00-\u9fffA-Za-z0-9_]{1,24})号=#")
_FACE_RE = re.compile(r"(椅面朝向|屏面朝向|(?<![室内面])朝向)=(朝上|无|北|东|南|西)")
_FACE_AXIS = {
    "东": (1.0, 0.0, 0.0),
    "西": (-1.0, 0.0, 0.0),
    "北": (0.0, 1.0, 0.0),
    "南": (0.0, -1.0, 0.0),
    "上": (0.0, 0.0, 1.0),
}
_FACE_WORDS = {"北": "北", "东": "东", "南": "南", "西": "西", "上": "上", "朝上": "上"}

_NEAR = 0.08
_ATTACH = 220
_SHEET = (1280, 720)
_CELL = (640, 360)
_SENSOR_MM = 36.0

_VIEWS = (
    ("望北", 0, 0),
    ("望东", 1, 0),
    ("望南", 0, 1),
    ("望西", 1, 1),
)


class LayoutError(ValueError):
    """The opening has no meters that can be projected."""


@dataclass
class LayoutBox:
    name: str
    kind: str
    cx: float
    cy: float
    cz: float
    sx: float
    sy: float
    sz: float
    extra: List[Tuple[Vec3, Vec3]] = field(default_factory=list)
    ramp: Optional[Tuple[float, float, float, float, float, float, float, float]] = None
    face: str = ""


def _nearest_index(pos: int, origins: Sequence[re.Match]) -> Optional[int]:
    best_i = None
    best_d = _ATTACH + 1
    for index, match in enumerate(origins):
        dist = min(abs(pos - match.start()), abs(pos - match.end()))
        if dist < best_d:
            best_d = dist
            best_i = index
    return best_i


def _name_before(text: str, pos: int) -> str:
    window = text[max(0, pos - 240):pos]
    found = [(item.end(), item.group(1).strip()) for item in _NAME_RE.finditer(window)]
    found.extend((item.end(), item.group(1).strip()) for item in _SHORT_NAME_RE.finditer(window))
    if not found:
        return ""
    found.sort(key=lambda item: item[0])
    return found[-1][1]


def _attach(pattern: re.Pattern, text: str, origins: Sequence[re.Match]) -> List[Optional[re.Match]]:
    slots: List[Optional[re.Match]] = [None] * len(origins)
    distances = [10**9] * len(origins)
    for item in pattern.finditer(text):
        index = _nearest_index(item.start(), origins)
        if index is None:
            continue
        dist = min(abs(item.start() - origins[index].start()), abs(item.start() - origins[index].end()))
        if dist < distances[index]:
            distances[index] = dist
            slots[index] = item
    return slots


def _axis(rel: str, side: str, heart: str, north: float, east: float) -> str:
    token = side or heart
    if token in {"北", "南"}:
        return "x"
    if token in {"东", "西"}:
        return "y"
    if rel in {"墙皮", "门洞", "窗洞", "贴墙", "齐平", "嵌入", "悬挂"}:
        return "x" if abs(north) >= abs(east) else "y"
    return "x"


def _normalize_face(value: Any) -> str:
    return _FACE_WORDS.get(str(value or "").strip(), "")


def facing_token(clause: str) -> str:
    """Compass facing wins. 朝上 is the mark only when nothing points sideways. 朝向=无 has none."""
    found: Dict[str, str] = {}
    for key, value in _FACE_RE.findall(str(clause or "")):
        found[key] = value
    if found.get("朝向") == "无":
        return ""
    for key in ("朝向", "椅面朝向", "屏面朝向"):
        token = _normalize_face(found.get(key))
        if token in {"北", "东", "南", "西"}:
            return token
    for key in ("朝向", "椅面朝向", "屏面朝向"):
        if _normalize_face(found.get(key)) == "上":
            return "上"
    return ""


def facing_by_name(opening: str) -> Dict[str, str]:
    """Registered name → 北|东|南|西|上. Empty when this subject has no facing."""
    text = str(opening or "")
    marks = list(_SUBJECT_HEAD_RE.finditer(text))
    found: Dict[str, str] = {}
    for index, mark in enumerate(marks):
        name = (mark.group(1) or mark.group(2) or "").strip()
        if not name:
            continue
        end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
        header = text.find("【", mark.end(), end)
        if header >= 0:
            end = header
        face = facing_token(text[mark.end():end])
        if face:
            found[name] = face
        else:
            found.setdefault(name, "")
    return found


def _furniture_height(name: str) -> float:
    if "凳" in name and "椅" not in name:
        return 0.45
    if any(token in name for token in ("椅", "沙发")):
        return 0.9
    if "床" in name or "榻" in name:
        return 0.55
    return 0.75


def _swing_lines(box_cx: float, box_cy: float, sx: float, sy: float, sz: float, hinge: str, opening: str) -> List[Tuple[Vec3, Vec3]]:
    if opening not in {"半开", "全开"}:
        return []
    long_x = sx >= sy
    if hinge == "东" and long_x:
        hx, hy, leaf = box_cx + sx / 2, box_cy, (-sx, 0.0)
    elif hinge == "西" and long_x:
        hx, hy, leaf = box_cx - sx / 2, box_cy, (sx, 0.0)
    elif hinge == "北" and not long_x:
        hx, hy, leaf = box_cx, box_cy + sy / 2, (0.0, -sy)
    elif hinge == "南" and not long_x:
        hx, hy, leaf = box_cx, box_cy - sy / 2, (0.0, sy)
    elif long_x:
        hx, hy, leaf = box_cx + sx / 2, box_cy, (-sx, 0.0)
    else:
        hx, hy, leaf = box_cx, box_cy + sy / 2, (0.0, -sy)
    inward = (-box_cx, -box_cy)
    if abs(inward[0]) + abs(inward[1]) < 0.05:
        inward = (0.0, 1.0)
    closed = leaf
    cross = closed[0] * inward[1] - closed[1] * inward[0]
    dot = closed[0] * inward[0] + closed[1] * inward[1]
    ang = math.atan2(cross, dot)
    step_mag = math.radians(45 if opening == "半开" else 75)
    step = step_mag if ang >= 0 else -step_mag
    if abs(ang) < abs(step):
        step = ang
    cos_s, sin_s = math.cos(step), math.sin(step)
    swung = (closed[0] * cos_s - closed[1] * sin_s, closed[0] * sin_s + closed[1] * cos_s)
    tip = (hx + swung[0], hy + swung[1])
    z0, z1 = 0.0, max(sz, 0.2)
    hinge_low = (hx, hy, z0)
    hinge_high = (hx, hy, z1)
    tip_low = (tip[0], tip[1], z0)
    tip_high = (tip[0], tip[1], z1)
    return [
        (hinge_low, tip_low),
        (hinge_high, tip_high),
        (hinge_low, hinge_high),
        (tip_low, tip_high),
    ]


def parse_layout_boxes(opening: str) -> Tuple[List[LayoutBox], dict]:
    text = str(opening or "")
    origins = list(_ORIGIN_RE.finditer(text))
    if not origins:
        raise LayoutError("开篇里没有距原点，画不出布局。")
    along = _attach(_ALONG_RE, text, origins)
    plan = _attach(_PLAN_RE, text, origins)
    radius = _attach(_RADIUS_RE, text, origins)
    floor = _attach(_FLOOR_RE, text, origins)
    rels = _attach(_REL_RE, text, origins)
    axes = _attach(_AXIS_RE, text, origins)
    sides = _attach(_WALL_SIDE_RE, text, origins)
    hearts = _attach(_HEART_RE, text, origins)
    openings = _attach(_OPEN_RE, text, origins)
    hinges = _attach(_HINGE_RE, text, origins)
    lifts = _attach(_LIFT_RE, text, origins)
    face_of = facing_by_name(text)
    wall_m = _WALL_H_RE.search(text)
    wall_h = float(wall_m.group(1)) if wall_m else 2.9
    focal_m = _FOCAL_RE.search(text)
    focal = float(focal_m.group(1)) if focal_m else 35.0
    focal = min(85.0, max(18.0, focal))

    boxes: List[LayoutBox] = []
    for index, origin in enumerate(origins):
        north = float(origin.group(1))
        east = float(origin.group(2))
        name = _name_before(text, origin.start()) or f"件{index + 1}"
        rel = rels[index].group(1).strip() if rels[index] else ""
        side = sides[index].group(1).strip() if sides[index] else ""
        heart = hearts[index].group(1).strip() if hearts[index] else ""
        axis = _axis(rel, side, heart, north, east)
        opening_state = openings[index].group(1).strip() if openings[index] else ""
        hinge = hinges[index].group(1).strip() if hinges[index] else ""
        lift = float(lifts[index].group(1)) if lifts[index] else None

        kind = ""
        sx = sy = sz = 0.0
        cz = 0.0
        extra: List[Tuple[Vec3, Vec3]] = []
        if along[index] is not None:
            length, height, thick = (float(along[index].group(i)) for i in (1, 2, 3))
            if axis == "x":
                sx, sy = length, thick
            else:
                sx, sy = thick, length
            sz = height
            if rel == "窗洞":
                bottom = max(0.3, (wall_h - height) * 0.45)
                cz = bottom + height / 2
            else:
                cz = height / 2
            kind = "door" if rel == "门洞" else "window" if rel == "窗洞" else "wall"
        elif plan[index] is not None and rel == "墙皮":
            long_m, thick = float(plan[index].group(1)), float(plan[index].group(2))
            if axis == "x":
                sx, sy = long_m, thick
            else:
                sx, sy = thick, long_m
            sz = wall_h
            cz = wall_h / 2
            kind = "wall"
        elif radius[index] is not None:
            diameter = float(radius[index].group(1)) * 2
            sx = sy = diameter
            sz = max(0.08, diameter * 0.15)
            cz = lift if lift is not None else max(0.2, wall_h - 0.4)
            kind = "lamp"
        elif plan[index] is not None:
            long_m, short_m = float(plan[index].group(1)), float(plan[index].group(2))
            parallel = axes[index].group(1).strip() if axes[index] else ""
            if parallel == "Y线":
                sy, sx = long_m, short_m
            else:
                sx, sy = long_m, short_m
            sz = _furniture_height(name)
            cz = sz / 2
            kind = "furniture"
        elif floor[index] is not None and "天花" not in name and "梁" not in name:
            sy, sx = float(floor[index].group(1)), float(floor[index].group(2))
            sz = 0.04
            cz = 0.02
            kind = "floor"

        if kind == "" or min(sx, sy, sz) <= 0 or max(sx, sy, sz) > 40:
            continue
        if kind == "door":
            extra = _swing_lines(east, north, sx, sy, sz, hinge, opening_state)
        boxes.append(LayoutBox(name, kind, east, north, cz, sx, sy, sz, extra, face=face_of.get(name, "")))

    if not boxes:
        raise LayoutError("开篇里没有可投影的米，画不出布局。")
    span_m = _SPAN_RE.search(text)
    if span_m:
        spans = tuple(float(span_m.group(i)) for i in (1, 2, 3, 4))
    else:
        faces = [box for box in boxes if box.kind in {"wall", "door", "window"}]

        def _span(keep, default):
            values = [abs(box.cy if keep in {"north", "south"} else box.cx) for box in faces if _on_span(box, keep)]
            return max(values) if values else default

        def _on_span(box, keep):
            if keep == "north":
                return box.cy > 0 and box.sy < box.sx
            if keep == "south":
                return box.cy < 0 and box.sy < box.sx
            if keep == "east":
                return box.cx > 0 and box.sx < box.sy
            return box.cx < 0 and box.sx < box.sy

        north_span = _span("north", 4.0)
        south_span = _span("south", 4.0)
        east_span = _span("east", 3.5)
        west_span = _span("west", 3.5)
        spans = (north_span, east_span, south_span, west_span)
    meta = {"spans": spans, "focal": focal, "wall_h": wall_h}
    return boxes, meta


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a: Vec3, k: float) -> Vec3:
    return (a[0] * k, a[1] * k, a[2] * k)


def _norm(a: Vec3) -> Vec3:
    length = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / length, a[1] / length, a[2] / length)


def _inside_box(box: LayoutBox, x: float, y: float, z: float) -> bool:
    if box.kind in {"floor", "ceiling"}:
        return False
    if box.ramp is not None:
        low_x, low_y, low_z, high_x, high_y, high_z, px, py = box.ramp
        run_x = high_x - low_x
        run_y = high_y - low_y
        length2 = run_x * run_x + run_y * run_y
        if length2 < 1e-6:
            return False
        along = ((x - low_x) * run_x + (y - low_y) * run_y) / length2
        if along < -0.05 or along > 1.05:
            return False
        cx = low_x + along * run_x
        cy = low_y + along * run_y
        if math.hypot(x - cx, y - cy) > math.hypot(px, py) + 0.08:
            return False
        surface = low_z + along * (high_z - low_z)
        return z < surface + 0.2
    return (
        abs(x - box.cx) <= box.sx / 2 + 0.05
        and abs(y - box.cy) <= box.sy / 2 + 0.05
        and box.cz - box.sz / 2 - 0.05 <= z <= box.cz + box.sz / 2 + 0.05
    )


def _clear_camera(pos: Vec3, boxes: Sequence[LayoutBox]) -> Vec3:
    x, y, z = pos
    for _ in range(40):
        if not any(_inside_box(box, x, y, z) for box in boxes):
            return (x, y, z)
        dist = math.hypot(x, y)
        if dist <= 0.7:
            break
        step = min(0.15, dist - 0.7)
        x -= x / dist * step
        y -= y / dist * step
    return (x, y, z)


def _cameras(spans: Sequence[float], wall_h: float, boxes: Sequence[LayoutBox]) -> List[Tuple[str, Vec3, Vec3]]:
    north, east, south, west = spans
    eye = 1.6 if wall_h >= 2.2 else max(1.2, wall_h * 0.55)

    def inset(span: float) -> float:
        return max(0.9, max(span, 1.2) * 0.42)

    def aim(x: float, y: float) -> Vec3:
        return _norm((x, y, -0.28))

    raw = [
        ("望北", (0.0, -south + inset(south), eye), aim(0.0, 1.0)),
        ("望东", (-west + inset(west), 0.0, eye), aim(1.0, 0.0)),
        ("望南", (0.0, north - inset(north), eye), aim(0.0, -1.0)),
        ("望西", (east - inset(east), 0.0, eye), aim(-1.0, 0.0)),
    ]
    return [(name, _clear_camera(pos, boxes), forward) for name, pos, forward in raw]


def project_point(point: Vec3, camera: Vec3, forward: Vec3, focal_px: float, center: Tuple[float, float]) -> Optional[Tuple[float, float]]:
    rel = _sub(point, camera)
    ahead = _norm(forward)
    right = _norm(_cross(ahead, (0.0, 0.0, 1.0)))
    up = _norm(_cross(right, ahead))
    depth = _dot(rel, ahead)
    if depth <= _NEAR:
        return None
    sx = center[0] + focal_px * _dot(rel, right) / depth
    sy = center[1] - focal_px * _dot(rel, up) / depth
    return sx, sy


def _clip_segment(p0: Vec3, p1: Vec3, camera: Vec3, forward: Vec3) -> Optional[Tuple[Vec3, Vec3]]:
    ahead = _norm(forward)
    z0 = _dot(_sub(p0, camera), ahead)
    z1 = _dot(_sub(p1, camera), ahead)
    if z0 < _NEAR and z1 < _NEAR:
        return None
    if z0 < _NEAR or z1 < _NEAR:
        denom = z1 - z0
        if abs(denom) < 1e-6:
            return None
        t = (_NEAR - z0) / denom
        hit = _add(p0, _mul(_sub(p1, p0), t))
        if z0 < _NEAR:
            p0 = hit
        else:
            p1 = hit
    return p0, p1


def _ramp_edges(ramp: Tuple[float, float, float, float, float, float, float, float]) -> List[Tuple[Vec3, Vec3]]:
    low_x, low_y, low_z, high_x, high_y, high_z, px, py = ramp
    low_left = (low_x + px, low_y + py, low_z)
    low_right = (low_x - px, low_y - py, low_z)
    high_left = (high_x + px, high_y + py, high_z)
    high_right = (high_x - px, high_y - py, high_z)
    floor = [
        (low_left[0], low_left[1], 0.0),
        (low_right[0], low_right[1], 0.0),
        (high_left[0], high_left[1], 0.0),
        (high_right[0], high_right[1], 0.0),
    ]
    edges = [
        (low_left, low_right),
        (high_left, high_right),
        (low_left, high_left),
        (low_right, high_right),
        (floor[0], floor[1]),
        (floor[2], floor[3]),
        (floor[0], floor[2]),
        (floor[1], floor[3]),
        (high_left, floor[2]),
        (high_right, floor[3]),
    ]
    if low_z > 0.05:
        edges.extend([(low_left, floor[0]), (low_right, floor[1])])
    return edges


def _box_edges(box: LayoutBox) -> List[Tuple[Vec3, Vec3]]:
    if box.ramp is not None:
        edges = _ramp_edges(box.ramp)
        edges.extend(box.extra)
        return edges

    def corner(ix: int, iy: int, iz: int) -> Vec3:
        return (
            box.cx + (ix - 0.5) * box.sx,
            box.cy + (iy - 0.5) * box.sy,
            box.cz + (iz - 0.5) * box.sz,
        )

    edges: List[Tuple[Vec3, Vec3]] = []
    for ix in (0, 1):
        for iy in (0, 1):
            for iz in (0, 1):
                here = corner(ix, iy, iz)
                if ix == 0:
                    edges.append((here, corner(1, iy, iz)))
                if iy == 0:
                    edges.append((here, corner(ix, 1, iz)))
                if iz == 0:
                    edges.append((here, corner(ix, iy, 1)))
    edges.extend(box.extra)
    return edges


def _quad_normal(quad: Sequence[Vec3]) -> Optional[Vec3]:
    normal = _cross(_sub(quad[1], quad[0]), _sub(quad[2], quad[0]))
    length = math.sqrt(_dot(normal, normal))
    if length < 1e-6:
        return None
    return (normal[0] / length, normal[1] / length, normal[2] / length)


def _orient_outward(quad: Sequence[Vec3], center: Vec3) -> Optional[Tuple[List[Vec3], Vec3]]:
    normal = _quad_normal(quad)
    if normal is None:
        return None
    mid = (
        sum(point[0] for point in quad) / len(quad),
        sum(point[1] for point in quad) / len(quad),
        sum(point[2] for point in quad) / len(quad),
    )
    points = list(quad)
    if _dot(normal, _sub(mid, center)) < 0:
        points.reverse()
        normal = (-normal[0], -normal[1], -normal[2])
    return points, normal


def _box_quads(box: LayoutBox) -> List[List[Vec3]]:
    def corner(ix: int, iy: int, iz: int) -> Vec3:
        return (
            box.cx + (ix - 0.5) * box.sx,
            box.cy + (iy - 0.5) * box.sy,
            box.cz + (iz - 0.5) * box.sz,
        )

    return [
        [corner(0, 0, 0), corner(1, 0, 0), corner(1, 1, 0), corner(0, 1, 0)],
        [corner(0, 0, 1), corner(0, 1, 1), corner(1, 1, 1), corner(1, 0, 1)],
        [corner(0, 0, 0), corner(0, 0, 1), corner(1, 0, 1), corner(1, 0, 0)],
        [corner(0, 1, 0), corner(1, 1, 0), corner(1, 1, 1), corner(0, 1, 1)],
        [corner(0, 0, 0), corner(0, 1, 0), corner(0, 1, 1), corner(0, 0, 1)],
        [corner(1, 0, 0), corner(1, 0, 1), corner(1, 1, 1), corner(1, 1, 0)],
    ]


def _ramp_quads(ramp: Tuple[float, float, float, float, float, float, float, float]) -> Tuple[List[List[Vec3]], Vec3]:
    low_x, low_y, low_z, high_x, high_y, high_z, px, py = ramp
    low_left = (low_x + px, low_y + py, low_z)
    low_right = (low_x - px, low_y - py, low_z)
    high_left = (high_x + px, high_y + py, high_z)
    high_right = (high_x - px, high_y - py, high_z)
    floor = [
        (low_left[0], low_left[1], 0.0),
        (low_right[0], low_right[1], 0.0),
        (high_left[0], high_left[1], 0.0),
        (high_right[0], high_right[1], 0.0),
    ]
    quads = [
        [low_left, low_right, high_right, high_left],
        [floor[0], floor[2], floor[3], floor[1]],
        [low_left, high_left, floor[2], floor[0]],
        [low_right, floor[1], floor[3], high_right],
        [low_left, floor[0], floor[1], low_right],
        [high_left, high_right, floor[3], floor[2]],
    ]
    center = ((low_x + high_x) / 2, (low_y + high_y) / 2, max(low_z, high_z) / 2)
    return quads, center


def _inner_opening(box: LayoutBox) -> Optional[Tuple[List[Vec3], Vec3]]:
    toward = (-box.cx, -box.cy)
    if abs(toward[0]) + abs(toward[1]) < 0.05:
        toward = (0.0, 1.0)
    nudge = 0.03
    z0, z1 = box.cz - box.sz / 2, box.cz + box.sz / 2
    if box.sx <= box.sy:
        sign = 1.0 if toward[0] >= 0 else -1.0
        x = box.cx + sign * (box.sx / 2 + nudge)
        y0, y1 = box.cy - box.sy / 2, box.cy + box.sy / 2
        quad = [(x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1)]
    else:
        sign = 1.0 if toward[1] >= 0 else -1.0
        y = box.cy + sign * (box.sy / 2 + nudge)
        x0, x1 = box.cx - box.sx / 2, box.cx + box.sx / 2
        quad = [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]
    outside = (quad[0][0] - toward[0], quad[0][1] - toward[1], box.cz)
    return quad, outside


def _same_point(left: Vec3, right: Vec3) -> bool:
    return all(abs(left[index] - right[index]) < 1e-4 for index in range(3))


def _swing_slab_quads(extra: Sequence[Tuple[Vec3, Vec3]]) -> Tuple[List[List[Vec3]], Vec3]:
    points: List[Vec3] = []
    for start, end in extra:
        for point in (start, end):
            if not any(_same_point(point, kept) for kept in points):
                points.append(point)
    groups: List[List[Vec3]] = []
    for point in points:
        placed = False
        for group in groups:
            if abs(group[0][0] - point[0]) < 1e-3 and abs(group[0][1] - point[1]) < 1e-3:
                group.append(point)
                placed = True
                break
        if not placed:
            groups.append([point])
    if len(groups) != 2 or any(len(group) < 2 for group in groups):
        return [], (0.0, 0.0, 0.0)
    groups.sort(key=lambda group: group[0][0] + group[0][1])
    hinge = sorted(groups[0], key=lambda point: point[2])
    tip = sorted(groups[1], key=lambda point: point[2])
    run_x, run_y = tip[0][0] - hinge[0][0], tip[0][1] - hinge[0][1]
    length = math.hypot(run_x, run_y) or 1.0
    nx, ny = -run_y / length * 0.02, run_x / length * 0.02

    def shift(point: Vec3, side: float) -> Vec3:
        return (point[0] + nx * side, point[1] + ny * side, point[2])

    front = [shift(hinge[0], 1), shift(tip[0], 1), shift(tip[-1], 1), shift(hinge[-1], 1)]
    back = [shift(hinge[0], -1), shift(hinge[-1], -1), shift(tip[-1], -1), shift(tip[0], -1)]
    quads = [front, back]
    center = (
        (hinge[0][0] + tip[0][0]) / 2,
        (hinge[0][1] + tip[0][1]) / 2,
        (hinge[0][2] + hinge[-1][2]) / 2,
    )
    return quads, center


def _into_room(box: LayoutBox, distance: float) -> LayoutBox:
    if abs(box.cy) >= abs(box.cx):
        cy = box.cy + (distance if box.cy < 0 else -distance)
        return LayoutBox(box.name, box.kind, box.cx, cy, box.cz, box.sx, box.sy, box.sz, list(box.extra), box.ramp)
    cx = box.cx + (distance if box.cx < 0 else -distance)
    return LayoutBox(box.name, box.kind, cx, box.cy, box.cz, box.sx, box.sy, box.sz, list(box.extra), box.ramp)


def _clay_faces(box: LayoutBox) -> List[Tuple[List[Vec3], Vec3, str]]:
    faces: List[Tuple[List[Vec3], Vec3, str]] = []
    if box.kind == "door" and not box.extra:
        opening = _inner_opening(_into_room(box, 0.12))
        if opening is not None:
            oriented = _orient_outward(opening[0], opening[1])
            if oriented is not None:
                faces.append((oriented[0], oriented[1], "void"))
        shown = _into_room(box, 0.18)
        for quad in _box_quads(shown):
            oriented = _orient_outward(quad, (shown.cx, shown.cy, shown.cz))
            if oriented is not None:
                faces.append((oriented[0], oriented[1], "clay"))
        return faces
    if box.kind in {"window", "door"} and (box.kind == "window" or box.extra):
        opening = _inner_opening(box)
        if opening is not None:
            quad, outside = opening
            oriented = _orient_outward(quad, outside)
            if oriented is not None:
                faces.append((oriented[0], oriented[1], "void"))
        if box.kind == "door":
            quads, center = _swing_slab_quads(box.extra)
            for quad in quads:
                oriented = _orient_outward(quad, center)
                if oriented is not None:
                    faces.append((oriented[0], oriented[1], "clay"))
        return faces
    if box.ramp is not None:
        quads, center = _ramp_quads(box.ramp)
    else:
        quads = _box_quads(box)
        center = (box.cx, box.cy, box.cz)
        if box.kind == "floor":
            quads = [quads[1]]
        elif box.kind == "ceiling":
            quads = [quads[0]]
    for quad in quads:
        oriented = _orient_outward(quad, center)
        if oriented is not None:
            faces.append((oriented[0], oriented[1], "clay"))
    return faces


def _view_light(forward: Vec3) -> Vec3:
    ahead = _norm(forward)
    right = _norm(_cross(ahead, (0.0, 0.0, 1.0)))
    up = _norm(_cross(right, ahead))
    return _norm(_add(_add(_mul(ahead, -0.62), _mul(up, 0.68)), _mul(right, -0.28)))


def _shade(normal: Vec3, light: Vec3, draw_kind: str, tone: str) -> Tuple[int, int, int]:
    if draw_kind == "void":
        return (58, 60, 64)
    if draw_kind == "mark":
        lit = max(0.0, _dot(normal, light))
        shade = 0.55 + 0.45 * lit
        return tuple(max(0, min(255, int(round(channel * shade)))) for channel in (186, 48, 40))
    lit = max(0.0, _dot(normal, light))
    shade = 0.5 + 0.5 * lit
    gain = 1.0
    if tone == "floor":
        gain = 0.72
    elif tone == "wall":
        gain = 0.86
    elif tone == "ceiling":
        gain = 0.64
    return tuple(max(0, min(255, int(round(channel * shade * gain)))) for channel in (252, 250, 246))


def _clip_stroke(start: Tuple[float, float], end: Tuple[float, float], bounds: Tuple[int, int, int, int]) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    x0, y0 = start
    x1, y1 = end
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    edges = (
        (-dx, x0 - bounds[0]),
        (dx, bounds[2] - 1 - x0),
        (-dy, y0 - bounds[1]),
        (dy, bounds[3] - 1 - y0),
    )
    for direction, room in edges:
        if abs(direction) < 1e-9:
            if room < 0:
                return None
            continue
        hit = room / direction
        if direction < 0:
            if hit > t1:
                return None
            if hit > t0:
                t0 = hit
        else:
            if hit < t0:
                return None
            if hit < t1:
                t1 = hit
    if t1 < t0:
        return None
    return (x0 + t0 * dx, y0 + t0 * dy), (x0 + t1 * dx, y0 + t1 * dy)


def _clip_polygon(points: Sequence[Vec3], camera: Vec3, forward: Vec3) -> List[Vec3]:
    ahead = _norm(forward)
    plane = _NEAR + 0.02
    depths = [_dot(_sub(point, camera), ahead) for point in points]
    if all(depth <= plane for depth in depths):
        return []
    if all(depth > plane for depth in depths):
        return list(points)
    clipped: List[Vec3] = []
    count = len(points)
    for index in range(count):
        start, start_z = points[index], depths[index]
        end, end_z = points[(index + 1) % count], depths[(index + 1) % count]
        if start_z > plane and end_z > plane:
            clipped.append(end)
        elif start_z > plane >= end_z:
            span = end_z - start_z
            clipped.append(_add(start, _mul(_sub(end, start), (plane - start_z) / span)))
        elif start_z <= plane < end_z:
            span = end_z - start_z
            clipped.append(_add(start, _mul(_sub(end, start), (plane - start_z) / span)))
            clipped.append(end)
    return clipped


def _raster_triangle(
    color: np.ndarray,
    depth_buf: np.ndarray,
    triangle: Sequence[Tuple[float, float, float]],
    rgb: Tuple[int, int, int],
    bounds: Tuple[int, int, int, int],
) -> None:
    xs = np.array([triangle[0][0], triangle[1][0], triangle[2][0]], dtype=np.float64)
    ys = np.array([triangle[0][1], triangle[1][1], triangle[2][1]], dtype=np.float64)
    zs = np.array([triangle[0][2], triangle[1][2], triangle[2][2]], dtype=np.float64)
    area = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0])
    if abs(area) < 0.5:
        return
    min_x = max(int(math.floor(float(xs.min()))), bounds[0])
    max_x = min(int(math.ceil(float(xs.max()))), bounds[2] - 1)
    min_y = max(int(math.floor(float(ys.min()))), bounds[1])
    max_y = min(int(math.ceil(float(ys.max()))), bounds[3] - 1)
    if min_x > max_x or min_y > max_y:
        return
    grid_x, grid_y = np.meshgrid(
        np.arange(min_x, max_x + 1, dtype=np.float64) + 0.5,
        np.arange(min_y, max_y + 1, dtype=np.float64) + 0.5,
    )
    w0 = ((xs[1] - grid_x) * (ys[2] - grid_y) - (xs[2] - grid_x) * (ys[1] - grid_y)) / area
    w1 = ((xs[2] - grid_x) * (ys[0] - grid_y) - (xs[0] - grid_x) * (ys[2] - grid_y)) / area
    w2 = 1.0 - w0 - w1
    depth = w0 * zs[0] + w1 * zs[1] + w2 * zs[2]
    view = depth_buf[min_y:max_y + 1, min_x:max_x + 1]
    hit = (w0 >= 0) & (w1 >= 0) & (w2 >= 0) & (depth < view) & (depth > _NEAR)
    if not np.any(hit):
        return
    view[hit] = depth[hit]
    color[min_y:max_y + 1, min_x:max_x + 1][hit] = rgb


def _facing_placement(box: LayoutBox) -> Optional[Tuple[Vec3, Vec3, float, float]]:
    direction = _FACE_AXIS.get(box.face)
    if direction is None:
        return None
    ax, ay, az = direction
    if az:
        span = min(box.sx, box.sy)
        half = box.sz / 2
    elif ay:
        span = min(box.sx, box.sz)
        half = box.sy / 2
    else:
        span = min(box.sy, box.sz)
        half = box.sx / 2
    length = max(0.08, min(0.28, span * 0.42))
    radius = max(0.035, min(0.11, length * 0.42))
    base = (box.cx + ax * half, box.cy + ay * half, box.cz + az * half)
    return base, direction, length, radius


def facing_tip(box: LayoutBox) -> Optional[Vec3]:
    placed = _facing_placement(box)
    if placed is None:
        return None
    base, direction, length, _radius = placed
    return (
        base[0] + direction[0] * length,
        base[1] + direction[1] * length,
        base[2] + direction[2] * length,
    )


def _facing_mark(box: LayoutBox) -> List[Tuple[List[Vec3], Vec3, str]]:
    placed = _facing_placement(box)
    if placed is None:
        return []
    base, direction, length, radius = placed
    tip = facing_tip(box)
    if tip is None:
        return []
    ax, ay, az = direction
    if abs(az) > 0.5:
        across, up = (radius, 0.0, 0.0), (0.0, radius, 0.0)
    elif abs(ay) > 0.5:
        across, up = (radius, 0.0, 0.0), (0.0, 0.0, radius)
    else:
        across, up = (0.0, radius, 0.0), (0.0, 0.0, radius)
    ring = []
    for sign_u, sign_v in ((1.0, 1.0), (-1.0, 1.0), (-1.0, -1.0), (1.0, -1.0)):
        ring.append((
            base[0] + across[0] * sign_u + up[0] * sign_v,
            base[1] + across[1] * sign_u + up[1] * sign_v,
            base[2] + across[2] * sign_u + up[2] * sign_v,
        ))
    polygons: List[List[Vec3]] = [[ring[index], ring[(index + 1) % 4], tip] for index in range(4)]
    polygons.append(ring)
    marks: List[Tuple[List[Vec3], Vec3, str]] = []
    for polygon in polygons:
        oriented = _orient_outward(polygon, (box.cx, box.cy, box.cz))
        if oriented is not None:
            marks.append((oriented[0], oriented[1], "mark"))
    return marks


def render_layout_sheet(boxes: Sequence[LayoutBox], meta: Dict[str, Any]) -> Tuple[bytes, int]:
    focal = float(meta["focal"])
    hfov = 2 * math.atan((_SENSOR_MM / 2) / focal)
    focal_px = (_CELL[0] / 2) / math.tan(hfov / 2)
    color = np.full((_SHEET[1], _SHEET[0], 3), (108, 108, 110), dtype=np.uint8)
    depth_buf = np.full((_SHEET[1], _SHEET[0]), 1e9, dtype=np.float32)
    cameras = _cameras(meta["spans"], float(meta["wall_h"]), boxes)
    solids = [(box, _clay_faces(box) + _facing_mark(box)) for box in boxes]
    strokes: List[Tuple[Tuple[int, int, int, int], Tuple[float, float], Tuple[float, float]]] = []
    for (_label, camera, forward), (_name, col, row) in zip(cameras, _VIEWS):
        light = _view_light(forward)
        ox, oy = col * _CELL[0], row * _CELL[1]
        bounds = (ox, oy, ox + _CELL[0], oy + _CELL[1])
        origin = (ox + _CELL[0] / 2, oy + _CELL[1] / 2)
        ahead = _norm(forward)
        for box, faces in solids:
            for quad, normal, kind in faces:
                mid = (
                    sum(point[0] for point in quad) / len(quad),
                    sum(point[1] for point in quad) / len(quad),
                    sum(point[2] for point in quad) / len(quad),
                )
                if _dot(normal, _sub(camera, mid)) <= 0.02:
                    continue
                clipped = _clip_polygon(quad, camera, forward)
                if len(clipped) < 3:
                    continue
                projected: List[Tuple[float, float, float]] = []
                for point in clipped:
                    flat = project_point(point, camera, forward, focal_px, origin)
                    if flat is None:
                        projected = []
                        break
                    projected.append((flat[0], flat[1], _dot(_sub(point, camera), ahead)))
                if len(projected) < 3:
                    continue
                rgb = _shade(normal, light, kind, box.kind if kind == "clay" else "void")
                for index in range(1, len(projected) - 1):
                    _raster_triangle(color, depth_buf, (projected[0], projected[index], projected[index + 1]), rgb, bounds)
                count = len(projected)
                for index in range(count):
                    strokes.append((bounds, (projected[index][0], projected[index][1]), (projected[(index + 1) % count][0], projected[(index + 1) % count][1])))
    image = Image.fromarray(color)
    draw = ImageDraw.Draw(image)
    for bounds, start, end in strokes:
        clipped = _clip_stroke(start, end, bounds)
        if clipped is None:
            continue
        draw.line((clipped[0][0], clipped[0][1], clipped[1][0], clipped[1][1]), fill=(36, 36, 38), width=2)
    draw.line((_CELL[0], 0, _CELL[0], _SHEET[1]), fill=(70, 70, 72), width=2)
    draw.line((0, _CELL[1], _SHEET[0], _CELL[1]), fill=(70, 70, 72), width=2)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue(), len(boxes)


def render_layout_png(opening: str) -> Tuple[bytes, int]:
    boxes, meta = parse_layout_boxes(opening)
    return render_layout_sheet(boxes, meta)


def _near_same(left: LayoutBox, right: LayoutBox) -> bool:
    return left.kind == right.kind and abs(left.cx - right.cx) < 0.4 and abs(left.cy - right.cy) < 0.4


def _ceiling_from_opening(opening: str, boxes: Sequence[LayoutBox], meta: Dict[str, Any]) -> Optional[LayoutBox]:
    match = re.search(rf"上=([^｜\n]{{1,24}}).{{0,160}}?高度={_METER}米", opening)
    if match is None:
        return None
    name = match.group(1).strip().strip("[]@")
    if not name or name == "无":
        return None
    bottom = float(match.group(2))
    floor = next((box for box in boxes if box.kind == "floor"), None)
    if floor is not None:
        cx, cy, sx, sy = floor.cx, floor.cy, floor.sx, floor.sy
    else:
        spans = meta.get("spans") or (3.25, 3.25, 3.25, 3.25)
        cx, cy = 0.0, 0.0
        sy = float(spans[0]) + float(spans[2])
        sx = float(spans[1]) + float(spans[3])
    if min(sx, sy) <= 0:
        return None
    height = 0.08
    return LayoutBox(name, "ceiling", cx, cy, bottom + height / 2, sx, sy, height)


def supplement_layout_boxes(opening: str, boxes: Sequence[LayoutBox], meta: Dict[str, Any]) -> List[LayoutBox]:
    """Add furniture and the ceiling the projection JSON left out."""
    kept = list(boxes)
    try:
        found, _parsed = parse_layout_boxes(opening)
    except LayoutError:
        found = []
    for box in found:
        if box.kind not in {"furniture", "lamp"}:
            continue
        if any(_near_same(box, have) for have in kept):
            continue
        kept.append(box)
    if not any(box.kind == "ceiling" for box in kept):
        ceiling = _ceiling_from_opening(opening, kept, meta)
        if ceiling is not None:
            kept.append(ceiling)
    return kept


_UNLIMITED_AXIS = 24.0

_LAYOUT_SYSTEM = """你写白模脚本。只输出脚本。不要复述开篇，不要 Markdown，不要解释。
禁止输出 JSON。禁止写 wall_h、boxes、focal_mm、span_north。第一个字符是 F。
第一行只写 FOCAL_MM = 数字。每个 mass() 单独占一行。FOCAL_MM 和 mass 不能写在同一行。
不要 import，不要建相机，不要渲染，不要写 bpy。
east 东为正，north 北为正，高度向上。east 和 north 是这一具的中心。
along_east 是东西向全长，along_north 是南北向全长，单位米。height 是竖直高度。bottom 是底面离地。
有距原点、并且高、厚、沿墙长里至少有一个写成米的具，必须各写一行。壁关系=墙皮和壁关系=门洞即使距原点相同，也各写一行。写了门不能代替这面墙皮。
某一轴写成无限制时，不要把这一具整行删掉。无限制的那一轴写 24，只给白模盒子用。写成米的轴照抄，不改。
北墙或南墙：沿墙长写入 along_east，厚写入 along_north。东墙或西墙：沿墙长写入 along_north，厚写入 along_east。height 用这一具自己的高，墙皮用墙高，门用门高。bottom=0。
地面 kind="floor"，height=0.04，bottom=0。两轴都是无限制时 along_east=24，along_north=24。墙皮 kind="wall"。门 kind="door"，窗 kind="window"，并写 state="全关"、"半开"或"全开"，只抄开篇的开闭。
这一具写了朝向、椅面朝向或屏面朝向，并且不是无，这一行加 face。朝向或椅面朝向是北、东、南、西，face 写这一向。屏面朝向是这四向、而朝向不是这四向，face 写屏面这一向。只有朝上，face="上"。朝向=无，或没写朝向，不加 face。室内面朝向不加 face。
全息屏、立式全息终端、中继屏、固定显示屏、巨幕、矩阵屏、壁挂屏、光幕，以及注册名里有屏、全息、光幕、巨幕的具，kind="screen"。没有米也要写。屏面朝向是北或南，along_north 写厚，along_east 写宽。屏面朝向是东或西，along_east 写厚，along_north 写宽。厚没有写成米就写 0.06。宽和高没有写成米：贴墙的宽 1.6、高 0.9，bottom 离开地面；立在中部的宽 1.2、高 1.6、bottom=0。face 写屏面朝向。
台、桌、案写了朝向=朝上，又写了屏面朝向：台身 kind="furniture"，face="上"。另起一行 kind="screen"，名字是注册名加屏面，薄板立在台身朝向屏面朝向的那一侧、底在台面上。屏面朝向是北，板心在台身北侧外沿，along_north 是厚。东、南、西照此。face 写屏面朝向。没有米的台身写 along_east=0.9，along_north=0.9，height=0.75。
天空、远景不写。高、厚、沿墙长都没有米的具不写，屏和有屏面朝向的台除外。
纹样、颜色、材质不写进脚本。不要加开篇没有的具。
另附了角色或道具时，人 kind="person"，道具 kind="prop"，每人、每件各写一行。东、北、底、沿东、沿北、高照附上的数，不改。没有附上的角色和道具，不自己加。
家具占地三个数时，最后一个是 height。只有长×宽时也要写：台、桌、案 height=0.75，床、榻 height=0.55，椅 height=0.9，凳 height=0.45。写了离平地，bottom 就等于那个米。灯 kind="lamp"。桌、椅、凳、床、台 kind="furniture"。
上=写了高度米数的帐顶、穹顶、天花、顶棚、梁架写成 kind="ceiling"，bottom 等于这个高度，height=0.08，along_east 和 along_north 抄地面。高度=无限制的不上这一行。
楼梯写低端和高端：kind="ramp"，再写 low_east、low_north、high_east、high_north、low_z、high_z。
四宫格不由你摆。焦段从开篇的毫米数抄进 FOCAL_MM，没有就写 35。
FOCAL_MM = 35
mass("注册名", "wall", east=0, north=0, along_east=24, along_north=2, height=12, bottom=0)
mass("注册名", "door", east=0, north=0, along_east=4, along_north=2, height=6, bottom=0, state="全开")
mass("注册名", "furniture", east=0, north=0, along_east=0.6, along_north=0.6, height=0.9, bottom=0, face="南")
mass("注册名", "screen", east=0, north=0, along_east=1.6, along_north=0.06, height=0.9, bottom=1.0, face="南")"""


_FOOTPRINT_RE = re.compile(
    r"占地=沿墙(?:无限制|(-?\d+(?:\.\d+)?)米)×高(-?\d+(?:\.\d+)?)米×厚(-?\d+(?:\.\d+)?)米"
)
_GROUND_SPAN_RE = re.compile(
    r"尺度=南北(?:无限制|(-?\d+(?:\.\d+)?)米)×东西(?:无限制|(-?\d+(?:\.\d+)?)米)"
)
_RELATION_RE = re.compile(r"壁关系=(墙皮|门洞|窗洞)")


def _script_lines(text: str) -> List[str]:
    lines: List[str] = []
    for raw in str(text or "").splitlines():
        line = raw.strip().rstrip(",")
        if "mass(" in line and not line.startswith("mass("):
            parts = re.split(r"(?=mass\()", line)
            lines.extend(part.strip() for part in parts if part.strip())
        elif line:
            lines.append(line)
    return lines


def _clause_name(text: str, pos: int) -> str:
    start = max(text.rfind("\n", 0, pos), text.rfind("。", 0, pos))
    chunk = text[start + 1:pos]
    names = [(item.end(), item.group(1).strip()) for item in _NAME_RE.finditer(chunk)]
    names.extend((item.end(), item.group(1).strip()) for item in _SHORT_NAME_RE.finditer(chunk))
    if not names:
        return ""
    names.sort(key=lambda item: item[0])
    return names[-1][1]


def _required_from_opening(opening: str) -> List[Dict[str, Any]]:
    text = str(opening or "")
    required: List[Dict[str, Any]] = []
    for item in _FOOTPRINT_RE.finditer(text):
        window = text[max(0, item.start() - 500):item.start()]
        origins = list(_ORIGIN_RE.finditer(window))
        if not origins:
            continue
        north = float(origins[-1].group(1))
        east = float(origins[-1].group(2))
        relations = list(_RELATION_RE.finditer(window))
        relation = relations[-1].group(1) if relations else "墙皮"
        kind = {"门洞": "door", "窗洞": "window"}.get(relation, "wall")
        length = _UNLIMITED_AXIS if item.group(1) is None else float(item.group(1))
        height = float(item.group(2))
        thick = float(item.group(3))
        name = _clause_name(text, item.start()) or relation
        required.append({
            "name": name,
            "kind": kind,
            "north": north,
            "east": east,
            "length": length,
            "height": height,
            "thick": thick,
            "unlimited": item.group(1) is None,
        })
    for item in _GROUND_SPAN_RE.finditer(text):
        window = text[max(0, item.start() - 500):item.start()]
        origins = list(_ORIGIN_RE.finditer(window))
        if not origins:
            continue
        north_span = _UNLIMITED_AXIS if item.group(1) is None else float(item.group(1))
        east_span = _UNLIMITED_AXIS if item.group(2) is None else float(item.group(2))
        required.append({
            "name": _clause_name(text, item.start()) or "地面",
            "kind": "floor",
            "north": float(origins[-1].group(1)),
            "east": float(origins[-1].group(2)),
            "length": north_span,
            "height": 0.04,
            "thick": east_span,
            "unlimited": item.group(1) is None or item.group(2) is None,
        })
    return required


def layout_script_gaps(opening: str, boxes: Sequence[LayoutBox]) -> str:
    """Name subjects the opening already sized, when the script left them out."""
    missing: List[str] = []
    for item in _required_from_opening(opening):
        present = any(
            box.kind == item["kind"]
            and abs(box.cx - item["east"]) <= 1.5
            and abs(box.cy - item["north"]) <= 1.5
            for box in boxes
        )
        if present:
            continue
        axis = "沿墙无限制写成24" if item["unlimited"] and item["kind"] != "floor" else "米照抄"
        if item["kind"] == "floor" and item["unlimited"]:
            axis = "无限制的轴写24"
        missing.append(
            f"{item['name']}（{item['kind']}，北{item['north']:g}东{item['east']:g}，"
            f"高{item['height']:g}，{axis}）"
        )
    if not missing:
        return ""
    return "缺这些具：" + "；".join(missing) + "。墙皮和门各写一行。FOCAL_MM 单独一行。"


def image_room_gaps(boxes: Sequence[LayoutBox]) -> str:
    """An image-only room that copies only people and props is not a room."""
    kinds = {box.kind for box in boxes}
    if "floor" in kinds and "wall" in kinds:
        return ""
    return "缺地面和墙。按图把地面、墙和看得见的台各写一行。角色和道具照抄，不能只写人和道具。"


def mass_names(script: str) -> List[str]:
    return re.findall(r'mass\(\s*"([^"]+)"', str(script or ""))


def shot_story_prompt(technical_notes: str, video_content: str = "", shot_logic_cn: str = "") -> str:
    """The storyboard prompt is the Chinese video prompt. Shot logic is only a fallback."""
    notes: Dict[str, Any] = {}
    try:
        parsed = json.loads(technical_notes or "{}")
        if isinstance(parsed, dict):
            notes = parsed
    except json.JSONDecodeError:
        notes = {}
    for item in (notes.get("video_prompt_cn"), video_content, shot_logic_cn):
        text = str(item or "").strip()
        if text:
            return text
    return ""


def shot_anim_seconds(duration: str, prompt: str) -> float:
    """Clip length from the shot duration, not from a shutter fraction such as 1/96s."""
    bare = str(duration or "").strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", bare):
        return max(2.0, min(15.0, float(bare)))
    text = str(prompt or "")
    marked = re.search(r"Duration\s*=\s*(\d+(?:\.\d+)?)", text, flags=re.I)
    if marked:
        return max(2.0, min(15.0, float(marked.group(1))))
    ends = [
        float(item)
        for item in re.findall(r"(?<![\d/])(\d+(?:\.\d+)?)\s*(?:s|秒)", text, flags=re.I)
    ]
    span = max(ends) if ends else 4.0
    return max(2.0, min(15.0, span))


def animation_skill_text() -> str:
    """The shot white-model skill. The model writes the whole clip from this file."""
    path = (
        Path(__file__).resolve().parents[2]
        / "core"
        / "prompts"
        / "skills"
        / "shot_white_model_animation"
        / "SKILL.md"
    )
    raw = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n.*?\n---\s*\n", raw, flags=re.DOTALL)
    return (raw[match.end():] if match else raw).strip()


def fallback_motion(view: str, seconds: float) -> str:
    span = max(2.0, min(15.0, float(seconds or 4)))
    face = str(view or "north").strip().lower()
    if face not in {"north", "east", "south", "west"}:
        face = "north"
    return (
        f"SECONDS = {span:.2f}\nFPS = 8\n"
        f"CAM t=0 view={face} dolly=0 rise=0 pan=0\n"
        f"CAM t={span:.2f} view={face} dolly=0.8 rise=0.15 pan=0\n"
    )


def _toward_lens(view: str) -> str:
    face = str(view or "").strip().lower()
    lines = {
        "north": "靠近镜头是北减小，远离镜头是北增大。画面左是东减小，画面右是东增大。",
        "south": "靠近镜头是北增大，远离镜头是北减小。画面左是东增大，画面右是东减小。",
        "east": "靠近镜头是东减小，远离镜头是东增大。画面左是北增大，画面右是北减小。",
        "west": "靠近镜头是东增大，远离镜头是东减小。画面左是北减小，画面右是北增大。",
    }
    return lines.get(face, "")


def mass_motion_brief(script: str) -> str:
    """Positions the animation may move: people, props, and furniture."""
    lines: List[str] = []
    for raw in str(script or "").splitlines():
        found = _MASS_CALL.match(raw.strip())
        if found is None:
            continue
        kind = _KIND_WORDS.get(_unquote(found.group("kind")).strip(), "")
        if kind not in {"person", "prop", "furniture"}:
            continue
        name = _unquote(found.group("name")).strip()
        values: Dict[str, float] = {}
        for key, token in _MASS_ARG.findall(found.group("rest") or ""):
            if key in {"east", "north", "bottom", "height", "along_east", "along_north"} and token[:1] not in {"'", '"'}:
                values[key] = float(token)
        if "east" not in values or "north" not in values:
            continue
        lines.append(
            f"{name}｜东={values['east']:.2f}｜北={values['north']:.2f}"
            f"｜沿东={values.get('along_east', 0):.2f}｜沿北={values.get('along_north', 0):.2f}"
            f"｜底={values.get('bottom', 0):.2f}｜高={values.get('height', 0):.2f}"
        )
        if len(lines) >= 24:
            break
    return "\n".join(lines)


def _message_content(text: str, images: Sequence[str] = ()) -> Any:
    """Plain text, or text plus image attachments when this shot has derived views."""
    urls = []
    for item in images or []:
        url = str(item or "").strip()
        if url and url not in urls:
            urls.append(url)
    if not urls:
        return text
    content: List[Dict[str, Any]] = [{"type": "text", "text": text}]
    for url in urls:
        content.append({"type": "image_url", "image_url": {"url": url}})
    return content


def animation_messages(
    prompt: str,
    script: str,
    view: str,
    seconds: float,
    missing: str = "",
    images: Sequence[str] = (),
) -> List[Dict[str, Any]]:
    text = str(prompt or "").strip()
    if not text:
        raise LayoutError("这一镜没有分镜提示词")
    names = "\n".join(mass_names(script)[:80])
    brief = mass_motion_brief(script)
    user = (
        f"这一镜只拍 {view} 这一面。SECONDS 用 {float(seconds):.2f}。\n"
        + _toward_lens(view) + "\n"
    )
    if images:
        user += "附上的图是这一镜这一面的衍生环境。主体朝向和看得见的具以这张图为准。\n"
    user += "盒子名字：\n" + names + "\n\n"
    if brief:
        user += "可移动的位置：\n" + brief + "\n\n"
    user += "分镜提示词：\n" + text[:8000]
    gap = str(missing or "").strip()
    if gap:
        user += "\n\n这些角色和道具还没有写进 MOVE。按技能补上，已经写对的镜头行保持：\n" + gap
    return [
        {"role": "system", "content": animation_skill_text()},
        {"role": "user", "content": _message_content(user, images)},
    ]


def _animation_lines(text: str) -> List[str]:
    """One key per line. Keys glued onto the previous value are split apart."""
    cleaned = re.sub(r"<think>.*?</think>", "", str(text or ""), flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"```(?:\w+)?", "", cleaned).strip()
    rows: List[str] = []
    for line in cleaned.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [
            part.strip()
            for part in re.split(r"(?=(?:SECONDS|FPS|CAM|FOCAL|MOVE)\b)", line)
            if part.strip()
        ]
        rows.extend(parts)
    return rows


def _move_from_line(line: str) -> Optional[Tuple[str, float, float, float]]:
    quoted = re.match(
        r'^MOVE\s+"([^"]+)"\s+t=(-?\d+(?:\.\d+)?)\s+east=(-?\d+(?:\.\d+)?)\s+north=(-?\d+(?:\.\d+)?)\s*$',
        line,
        flags=re.I,
    )
    if quoted:
        return quoted.group(1), float(quoted.group(2)), float(quoted.group(3)), float(quoted.group(4))
    plain = re.match(
        r"^MOVE\s+t=(-?\d+(?:\.\d+)?)\s*(.+?)\s+(?:东|east)=(-?\d+(?:\.\d+)?)\s+(?:北|north)=(-?\d+(?:\.\d+)?)\s*$",
        line,
        flags=re.I,
    )
    if plain is None:
        return None
    name = plain.group(2).strip().strip('"')
    return name, float(plain.group(1)), float(plain.group(3)), float(plain.group(4))


def animation_script_from_model_text(text: str, *, view: str, names: Sequence[str], seconds: float) -> str:
    """Keep camera and named moves. Drop anything that is not this view or this room."""
    face = str(view or "").strip().lower()
    if face not in {"north", "east", "south", "west"}:
        raise LayoutError("没有这一面的机位")
    span = max(2.0, min(15.0, float(seconds or 4)))
    known = {str(name) for name in names if str(name or "").strip()}
    cams: List[Tuple[float, float, float, float, float]] = []
    focals: List[Tuple[float, float]] = []
    moves: List[Tuple[str, float, float, float]] = []
    cam_re = re.compile(
        r"^CAM\s+t=(-?\d+(?:\.\d+)?)\s+view=(north|east|south|west)\s+"
        r"dolly=(-?\d+(?:\.\d+)?)\s+rise=(-?\d+(?:\.\d+)?)\s+pan=(-?\d+(?:\.\d+)?)"
        r"(?:\s+dip=(-?\d+(?:\.\d+)?))?\s*$",
        re.I,
    )
    for line in _animation_lines(text):
        cam = cam_re.match(line)
        if cam:
            if cam.group(2).lower() != face:
                continue
            dip = 0.0 if cam.group(6) is None else float(cam.group(6))
            cams.append((
                max(0.0, min(span, float(cam.group(1)))),
                max(-1.5, min(1.10, float(cam.group(3)))),
                max(-0.4, min(0.6, float(cam.group(4)))),
                max(-30.0, min(30.0, float(cam.group(5)))),
                max(0.0, min(20.0, dip)),
            ))
            continue
        focal = re.match(
            r"^FOCAL\s+t=(-?\d+(?:\.\d+)?)\s+mm=(-?\d+(?:\.\d+)?)\s*$",
            line,
            flags=re.I,
        )
        if focal:
            focals.append((
                max(0.0, min(span, float(focal.group(1)))),
                max(18.0, min(85.0, float(focal.group(2)))),
            ))
            continue
        move = _move_from_line(line)
        if move and move[0] in known:
            moves.append((
                move[0],
                max(0.0, min(span, move[1])),
                move[2],
                move[3],
            ))
    if not cams:
        raise LayoutError("动画没有这一面的镜头")
    cams.sort(key=lambda item: item[0])
    if cams[0][0] > 0:
        cams.insert(0, (0.0, cams[0][1], cams[0][2], cams[0][3], cams[0][4]))
    if cams[-1][0] < span:
        last = cams[-1]
        cams.append((span, last[1], last[2], last[3], last[4]))
    lines = [f"SECONDS = {span:.2f}", "FPS = 8"]
    focals.sort(key=lambda item: item[0])
    if focals and focals[0][0] > 0:
        focals.insert(0, (0.0, focals[0][1]))
    if focals and focals[-1][0] < span:
        focals.append((span, focals[-1][1]))
    for item in cams:
        lines.append(
            f"CAM t={item[0]:.2f} view={face} dolly={item[1]:.2f} rise={item[2]:.2f} pan={item[3]:.2f} dip={item[4]:.0f}"
        )
    for tick, mm in focals:
        lines.append(f"FOCAL t={tick:.2f} mm={mm:.0f}")
    for name, tick, east, north in moves:
        lines.append(f'MOVE "{name}" t={tick:.2f} east={east:.2f} north={north:.2f}')
    return "\n".join(lines) + "\n"


_STEP_METERS = {
    "贴身": 0.40,
    "一臂": 0.70,
    "一条手臂": 0.70,
    "两步": 1.40,
    "三步": 2.20,
    "五步": 3.60,
}
# Toward the camera, the depth axis changes by this sign. North view: north decreases.
_TOWARD_SIGN = {"north": ("north", -1.0), "south": ("north", 1.0), "east": ("east", -1.0), "west": ("east", 1.0)}
# Person facing the camera: their left hand, as east/north signs.
_LEFT_HAND = {"north": (1.0, 0.0), "south": (-1.0, 0.0), "east": (0.0, -1.0), "west": (0.0, 1.0)}
_STAND_RE = re.compile(
    r"(?:站在|停在)(?P<host>.{1,32}?)(?P<side>靠近镜头|远离镜头)的[这那][一侧边]{1,2}"
    r"(?:[^。]{0,80}?更(?P=side))?"
    r"(?:[^。]{0,40}?(?P<dist>贴身|一条手臂|一臂|两步|三步|五步))?"
)


def _depth_span(box: Dict[str, Any], axis: str) -> float:
    key = "along_north" if axis == "north" else "along_east"
    return float(box.get(key) or 0.0)


def _match_host(label: str, rows: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    text = str(label or "").strip()
    if "门" in text:
        chosen = [row for row in rows if row.get("kind") == "door" or "门" in str(row.get("name") or "")]
    elif any(word in text for word in ("台", "桌", "案")):
        chosen = [
            row for row in rows
            if row.get("kind") == "furniture" and any(word in str(row.get("name") or "") for word in ("台", "桌", "案"))
        ]
    elif "柜" in text:
        chosen = [row for row in rows if "柜" in str(row.get("name") or "")]
    else:
        chosen = []
    if len(chosen) == 1:
        return chosen[0]
    best = None
    best_score = 0
    for row in chosen or list(rows):
        name = str(row.get("name") or "")
        score = sum(2 for index in range(len(text) - 1) if text[index:index + 2] in name)
        if score > best_score:
            best = row
            best_score = score
    return best if best_score >= 2 else None


def _stand_point(box: Dict[str, Any], view: str, side: str, dist: float) -> Tuple[float, float]:
    axis, toward = _TOWARD_SIGN[view]
    center = float(box.get(axis) or 0.0)
    half = _depth_span(box, axis) / 2.0
    if side == "靠近镜头":
        depth = center + toward * half + toward * dist
    else:
        depth = center - toward * half - toward * dist
    lateral = "east" if axis == "north" else "north"
    east = depth if axis == "east" else float(box.get(lateral) or 0.0)
    north = depth if axis == "north" else float(box.get(lateral) or 0.0)
    return east, north


def _prompt_stands(prompt: str, rows: Sequence[Dict[str, Any]], view: str) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
    start = None
    end = None
    for found in _STAND_RE.finditer(str(prompt or "")):
        host = _match_host(found.group("host") or "", rows)
        if host is None:
            continue
        dist = _STEP_METERS.get(found.group("dist") or "", 0.70)
        point = _stand_point(host, view, found.group("side"), dist)
        phrase = found.group(0)
        if phrase.startswith("停在"):
            end = point
        else:
            start = point
    return start, end


def apply_prompt_room(script: str, prompt: str) -> str:
    """The storyboard's door state overrides a closed door copied from the picture."""
    text = str(prompt or "")
    if not re.search(r"门[^。]{0,16}半开|半开[^。]{0,16}门", text):
        return script
    lines: List[str] = []
    for line in str(script or "").splitlines():
        if "mass(" in line and ('"door"' in line or "门" in line):
            if re.search(r'state\s*=\s*"', line):
                line = re.sub(r'state\s*=\s*"[^"]*"', 'state="半开"', line)
            elif re.search(r"state\s*=", line):
                line = re.sub(r"state\s*=\s*\S+", 'state="半开"', line)
            elif line.rstrip().endswith(")"):
                line = line.rstrip()[:-1] + ', state="半开")'
        lines.append(line)
    return "\n".join(lines)


def lock_shot_motion(motion: str, room_script: str, prompt: str, view: str) -> str:
    """Rewrite stands, a held prop, and the front step from the storyboard."""
    face = str(view or "").strip().lower()
    if face not in _TOWARD_SIGN:
        return motion
    rows = layout_mass_fields(room_script)
    start, end = _prompt_stands(prompt, rows, face)
    people = [
        name for name in re.findall(r"CHAR:\[@[^\]]+\]", str(prompt or ""))
        if any(str(row.get("name") or "") == name for row in rows)
    ]
    person = people[0] if people else ""
    held = re.findall(r"(左手|右手)拿着\s*(PROP:\[[^\]]+\])", str(prompt or ""))
    front = re.search(r"正前(贴身|一条手臂|一臂|两步|三步|五步)", str(prompt or ""))
    if start is None and end is None and not held and front is None:
        return motion
    lines = [line for line in str(motion or "").splitlines() if line.strip()]
    seconds = 4.0
    cams: List[Tuple[float, float, float, float, float]] = []
    focals: List[str] = []
    moves: List[Tuple[str, float, float, float]] = []
    cam_re = re.compile(
        r"^CAM\s+t=(-?\d+(?:\.\d+)?)\s+view=(north|east|south|west)\s+"
        r"dolly=(-?\d+(?:\.\d+)?)\s+rise=(-?\d+(?:\.\d+)?)\s+pan=(-?\d+(?:\.\d+)?)"
        r"(?:\s+dip=(-?\d+(?:\.\d+)?))?\s*$",
        re.I,
    )
    for line in lines:
        if line.startswith("SECONDS"):
            try:
                seconds = float(line.split("=", 1)[1])
            except ValueError:
                seconds = 4.0
            continue
        if line.startswith("FOCAL"):
            focals.append(line)
            continue
        cam = cam_re.match(line)
        if cam:
            dip = 0.0 if cam.group(6) is None else float(cam.group(6))
            cams.append((float(cam.group(1)), float(cam.group(3)), float(cam.group(4)), float(cam.group(5)), dip))
            continue
        move = _move_from_line(line)
        if move:
            moves.append(move)
    if person and (start is not None or end is not None):
        own = [item for item in moves if item[0] == person]
        if not own:
            own = [(person, 0.0, 0.0, 0.0)]
        if start is not None and end is not None and len(own) < 2:
            own.append((person, seconds, own[0][2], own[0][3]))
        begin = start or end
        finish = end or start
        t0 = own[0][1]
        t1 = own[-1][1]
        span = t1 - t0
        rewritten = []
        for _name, tick, _east, _north in own:
            blend = 0.0 if abs(span) < 1e-6 else (tick - t0) / span
            rewritten.append((
                person,
                tick,
                begin[0] + (finish[0] - begin[0]) * blend,
                begin[1] + (finish[1] - begin[1]) * blend,
            ))
        moves = [item for item in moves if item[0] != person] + rewritten
        for hand, prop in held:
            if not any(str(row.get("name") or "") == prop for row in rows):
                continue
            sign = _LEFT_HAND[face] if hand == "左手" else (-_LEFT_HAND[face][0], -_LEFT_HAND[face][1])
            body = next(row for row in rows if row.get("name") == person)
            piece = next(row for row in rows if row.get("name") == prop)
            if abs(sign[0]) >= abs(sign[1]):
                gap = float(body.get("along_east") or 0.45) / 2.0 + float(piece.get("along_east") or 0.1) / 2.0 + 0.08
            else:
                gap = float(body.get("along_north") or 0.25) / 2.0 + float(piece.get("along_north") or 0.05) / 2.0 + 0.08
            offset = (sign[0] * gap, sign[1] * gap)
            moves = [item for item in moves if item[0] != prop]
            for _name, tick, east, north in rewritten:
                moves.append((prop, tick, east + offset[0], north + offset[1]))
    if front is not None and cams:
        desired = _STEP_METERS[front.group(1)]
        opening = max(-1.5, min(1.10, 1.40 - desired))
        shift = opening - cams[0][1]
        cams = [
            (tick, max(-1.5, min(1.10, dolly + shift)), rise, pan, dip)
            for tick, dolly, rise, pan, dip in cams
        ]
    out = [f"SECONDS = {seconds:.2f}", "FPS = 8"]
    for tick, dolly, rise, pan, dip in cams:
        out.append(
            f"CAM t={tick:.2f} view={face} dolly={dolly:.2f} rise={rise:.2f} pan={pan:.2f} dip={dip:.0f}"
        )
    out.extend(focals)
    for name, tick, east, north in moves:
        out.append(f'MOVE "{name}" t={tick:.2f} east={east:.2f} north={north:.2f}')
    return "\n".join(out) + "\n"


def missing_occupant_moves(script: str, names: Sequence[str]) -> str:
    """CHAR and PROP names the animation script never moves."""
    present = set(re.findall(r'MOVE\s+"([^"]+)"', str(script or "")))
    missing = [
        str(name)
        for name in names
        if str(name).startswith(("CHAR:", "PROP:")) and str(name) not in present
    ]
    return "\n".join(missing)


def layout_messages(
    opening: str,
    missing: str = "",
    previous: str = "",
    occupants: str = "",
    images: Sequence[str] = (),
) -> List[Dict[str, Any]]:
    text = str(opening or "").strip()
    pictures = [str(item or "").strip() for item in images or [] if str(item or "").strip()]
    if pictures:
        user = (
            "这一次不要开篇。附上的图是这一镜的衍生环境，按顺序各是一处。\n"
            "墙、门、窗、柜、台、地面、天花只按图里看得见的写。图里没有的不写。\n"
            "朝向按图里哪一面朝镜头。开闭按图里是开着还是关着。\n"
            "米按图里的相对大小估计，围成这一间。FOCAL_MM 没有就写 35。\n"
            "地面、墙和看得见的台各写一行。只写角色和道具、不写地面和墙，这一稿不交。\n"
            "系统提示里关于开篇的句子，这一次不执行。\n"
        )
    elif text:
        user = "以下是开篇原文。规划已经把白模的米、朝向和开闭写在里面。只根据这些写脚本：\n" + text[:80000]
    else:
        raise LayoutError("没有开篇，不能生成布局。")
    people = str(occupants or "").strip()
    if people:
        user += "\n\n以下角色和道具必须各写一行，米和 kind 照抄，不改：\n" + people[:12000]
    note = str(missing or "").strip()
    prior = str(previous or "").strip()
    if note:
        if pictures:
            closing = "。仍只根据附上的衍生环境图重写。不要开篇。"
        else:
            closing = "。仍只根据上面的开篇重写脚本。"
            if prior:
                closing = "。仍只根据上面的开篇重写脚本。米、朝向、开闭照开篇，不新造米。"
        user += "\n\n上一份脚本没有通过：" + note[:800] + closing
    if prior:
        user += "\n上一份脚本：\n" + prior[:6000]
    return [
        {"role": "system", "content": _LAYOUT_SYSTEM},
        {"role": "user", "content": _message_content(user, pictures)},
    ]


def parse_layout_model_text(text: str) -> Dict[str, Any]:
    cleaned = re.sub(r"<think>.*?</think>", "", str(text or ""), flags=re.DOTALL | re.IGNORECASE).strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise LayoutError("模型没有返回布局。")
    try:
        data = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError as exc:
        raise LayoutError("模型返回的布局不是 JSON。") from exc
    if not isinstance(data, dict):
        raise LayoutError("模型返回的布局不是对象。")
    return data


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in {"", "null", "none"}:
        return True
    return False


def _layout_number(value: Any, label: str, default: Optional[float] = None) -> float:
    if _is_blank(value):
        if default is not None:
            return float(default)
        raise LayoutError(f"布局缺了{label}。")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise LayoutError(f"布局缺了{label}。") from exc
    if not math.isfinite(number):
        raise LayoutError(f"布局的{label}不是数。")
    return number


def _ramp_offset(item: Dict[str, Any], along_east: float, along_north: float) -> Optional[Tuple[float, float, float, float, float, float, float, float]]:
    keys = ("low_east", "low_north", "high_east", "high_north")
    if not all(key in item and item.get(key) is not None for key in keys):
        return None
    low_x = _layout_number(item.get("low_east"), "低端东")
    low_y = _layout_number(item.get("low_north"), "低端北")
    high_x = _layout_number(item.get("high_east"), "高端东")
    high_y = _layout_number(item.get("high_north"), "高端北")
    low_z = _layout_number(item.get("low_z"), "低端高", 0.0)
    high_raw = item.get("high_z")
    if _is_blank(high_raw):
        high_raw = item.get("height")
    high_z = _layout_number(high_raw, "高端高")
    run_x = high_x - low_x
    run_y = high_y - low_y
    length = math.hypot(run_x, run_y)
    if length < 0.05:
        return None
    width = along_east if abs(run_y) >= abs(run_x) else along_north
    half = max(width, 0.05) / 2
    px = -run_y / length * half
    py = run_x / length * half
    return (low_x, low_y, low_z, high_x, high_y, high_z, px, py)


_KIND_LABEL = {
    "floor": "地面",
    "ceiling": "天花",
    "wall": "墙",
    "door": "门",
    "window": "窗",
    "lamp": "灯",
    "ramp": "楼梯",
    "furniture": "家具",
    "screen": "屏",
    "person": "人",
    "prop": "道具",
}


_KIND_WORDS = {
    "floor": "floor",
    "地面": "floor",
    "地坪": "floor",
    "ceiling": "ceiling",
    "天花": "ceiling",
    "顶棚": "ceiling",
    "wall": "wall",
    "墙": "wall",
    "墙皮": "wall",
    "door": "door",
    "门": "door",
    "window": "window",
    "窗": "window",
    "lamp": "lamp",
    "灯": "lamp",
    "ramp": "ramp",
    "楼梯": "ramp",
    "梯": "ramp",
    "furniture": "furniture",
    "家具": "furniture",
    "screen": "screen",
    "屏": "screen",
    "屏幕": "screen",
    "person": "person",
    "人": "person",
    "角色": "person",
    "prop": "prop",
    "件": "prop",
    "道具": "prop",
}


def boxes_from_layout_payload(data: Dict[str, Any]) -> Tuple[List[LayoutBox], Dict[str, Any]]:
    raw_boxes = data.get("boxes") if isinstance(data, dict) else None
    if not isinstance(raw_boxes, list) or not raw_boxes:
        raise LayoutError("布局结果里没有主体。")
    boxes: List[LayoutBox] = []
    for index, item in enumerate(raw_boxes[:40], start=1):
        if not isinstance(item, dict):
            continue
        kind = _KIND_WORDS.get(str(item.get("kind") or "").strip(), "furniture")
        raw_name = item.get("name")
        name = "" if _is_blank(raw_name) else str(raw_name).strip()
        if not name:
            name = f"第{index}件{_KIND_LABEL.get(kind, kind)}"
        along_east = _layout_number(item.get("along_east"), f"{name}的东西长")
        along_north = _layout_number(item.get("along_north"), f"{name}的南北长")
        height_value = item.get("height")
        bottom_value = item.get("bottom")
        if _is_blank(height_value) and not _is_blank(item.get("high_z")):
            high_z = _layout_number(item.get("high_z"), f"{name}的高端高")
            low_z = _layout_number(item.get("low_z"), f"{name}的低端高", 0.0)
            height_value = abs(high_z - low_z) or high_z
            if _is_blank(bottom_value):
                bottom_value = low_z
        if _is_blank(height_value) and kind == "floor":
            height_value = 0.04
        if _is_blank(height_value) and kind == "ceiling":
            height_value = 0.08
        height = _layout_number(height_value, f"{name}的高")
        if along_east <= 0 or along_north <= 0 or height <= 0:
            raise LayoutError(f"{name}的大小不是正数。")
        if max(along_east, along_north, height) > 200:
            raise LayoutError(f"{name}的大小超出这一间。")
        east = _layout_number(item.get("east"), f"{name}的东")
        north = _layout_number(item.get("north"), f"{name}的北")
        bottom = _layout_number(bottom_value, f"{name}的离地", 0.0)
        ramp = _ramp_offset(item, along_east, along_north)
        if ramp is not None:
            kind = "ramp"
        boxes.append(
            LayoutBox(
                name=name,
                kind=kind,
                cx=east,
                cy=north,
                cz=bottom + height / 2,
                sx=along_east,
                sy=along_north,
                sz=height,
                ramp=ramp,
                face=_normalize_face(item.get("face")),
            )
        )
    if not boxes:
        raise LayoutError("布局结果里没有可投影的主体。")
    wall_h = _layout_number(data.get("wall_h", 2.9), "墙高")
    focal = _layout_number(data.get("focal_mm", 35), "焦段")
    if focal <= 0:
        focal = 35.0
    spans = (
        _layout_number(data.get("span_north", 4), "北场径"),
        _layout_number(data.get("span_east", 4), "东场径"),
        _layout_number(data.get("span_south", 4), "南场径"),
        _layout_number(data.get("span_west", 4), "西场径"),
    )
    return boxes, {"wall_h": wall_h, "focal": focal, "spans": spans}


_FOCAL_LINE = re.compile(r"^FOCAL_MM\s*=\s*(\d+(?:\.\d+)?)\s*$")
_MASS_CALL = re.compile(
    r"^mass\(\s*(?P<name>\"[^\"]*\"|'[^']*')\s*,\s*(?P<kind>\"[^\"]*\"|'[^']*')"
    r"(?P<rest>(?:\s*,\s*[A-Za-z_]+\s*=\s*(?:-?\d+(?:\.\d+)?|\"[^\"]*\"|'[^']*'))*)\s*\)\s*$"
)
_MASS_ARG = re.compile(r"([A-Za-z_]+)\s*=\s*(-?\d+(?:\.\d+)?|\"[^\"]*\"|'[^']*')")
_MASS_KEYS = {
    "east",
    "north",
    "along_east",
    "along_north",
    "height",
    "bottom",
    "state",
    "low_east",
    "low_north",
    "high_east",
    "high_north",
    "low_z",
    "high_z",
    "face",
}


def _unquote(token: str) -> str:
    return token[1:-1] if len(token) >= 2 and token[0] == token[-1] and token[0] in {"'", '"'} else token


def extract_layout_script(text: str) -> str:
    """Keep the mass() calls the model wrote and drop the prose around them."""
    cleaned = re.sub(r"<think>.*?</think>", "", str(text or ""), flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"```(?:python)?", "", cleaned, flags=re.IGNORECASE)
    kept: List[str] = []
    for line in _script_lines(cleaned):
        if line.startswith("#"):
            continue
        if _FOCAL_LINE.match(line) or _MASS_CALL.match(line):
            kept.append(line)
            continue
        if "mass(" in line or line.startswith("FOCAL_MM"):
            raise LayoutError("这一行脚本读不成：" + line[:80])
    if not any(line.startswith("mass(") for line in kept):
        raise LayoutError("脚本里没有白模。")
    return "\n".join(kept)


def _script_number(value: float) -> str:
    text = f"{float(value):.4f}".rstrip("0").rstrip(".")
    return text or "0"


def script_from_boxes(boxes: Sequence[LayoutBox], focal: float = 35) -> str:
    """Turn the model's box list into the mass() script Blender runs."""
    lines = [f"FOCAL_MM = {_script_number(focal if focal > 0 else 35)}"]
    for box in boxes:
        bottom = box.cz - box.sz / 2
        parts = [
            json.dumps(box.name, ensure_ascii=False),
            json.dumps(box.kind, ensure_ascii=False),
            f"east={_script_number(box.cx)}",
            f"north={_script_number(box.cy)}",
            f"along_east={_script_number(box.sx)}",
            f"along_north={_script_number(box.sy)}",
            f"height={_script_number(box.sz)}",
            f"bottom={_script_number(bottom)}",
        ]
        if box.ramp is not None:
            low_x, low_y, low_z, high_x, high_y, high_z, _px, _py = box.ramp
            parts.extend(
                [
                    f"low_east={_script_number(low_x)}",
                    f"low_north={_script_number(low_y)}",
                    f"high_east={_script_number(high_x)}",
                    f"high_north={_script_number(high_y)}",
                    f"low_z={_script_number(low_z)}",
                    f"high_z={_script_number(high_z)}",
                ]
            )
        if box.face:
            parts.append("face=" + json.dumps(box.face, ensure_ascii=False))
        lines.append("mass(" + ", ".join(parts) + ")")
    return "\n".join(lines)


def occupant_mass_script(rows: Sequence[Dict[str, Any]]) -> str:
    """Locked person and prop boxes. The white model keeps these meters."""
    lines: List[str] = []
    seen = set()
    for row in rows:
        name = str(row.get("name") or "").strip()
        raw_kind = str(row.get("kind") or "").strip()
        if not name or name in seen:
            continue
        if raw_kind in {"人", "person", "角色"}:
            kind = "person"
        elif raw_kind in {"件", "prop", "道具"}:
            kind = "prop"
        else:
            continue
        seen.add(name)
        face = str(row.get("face") or "").strip()
        face_bit = ""
        if face in {"东", "南", "西", "北", "上"}:
            face_bit = ", face=" + json.dumps(face, ensure_ascii=False)
        lines.append(
            "mass("
            + ", ".join(
                [
                    json.dumps(name, ensure_ascii=False),
                    json.dumps(kind, ensure_ascii=False),
                    f"east={_script_number(float(row.get('east') or 0))}",
                    f"north={_script_number(float(row.get('north') or 0))}",
                    f"along_east={_script_number(float(row.get('along_east') or 0.4))}",
                    f"along_north={_script_number(float(row.get('along_north') or 0.4))}",
                    f"height={_script_number(float(row.get('height') or 0.2))}",
                    f"bottom={_script_number(float(row.get('bottom') or 0))}",
                ]
            )
            + face_bit
            + ")"
        )
    return "\n".join(lines)


def merge_occupant_script(script: str, occupants: str) -> str:
    """Drop model copies of these names and append the locked person and prop lines."""
    extra = [line.strip() for line in str(occupants or "").splitlines() if line.strip()]
    if not extra:
        return str(script or "").strip()
    names = set()
    kept_extra: List[str] = []
    for line in extra:
        found = _MASS_CALL.match(line)
        if found is None:
            continue
        names.add(_unquote(found.group("name")).strip())
        kept_extra.append(line)
    if not kept_extra:
        return str(script or "").strip()
    kept: List[str] = []
    for line in str(script or "").splitlines():
        found = _MASS_CALL.match(line.strip())
        if found is not None and _unquote(found.group("name")).strip() in names:
            continue
        kept.append(line)
    return "\n".join([*kept, *kept_extra]).strip()


def layout_script_from_model_text(text: str) -> Tuple[str, List[LayoutBox]]:
    """Accept a mass() script, or the box JSON the model still returns."""
    try:
        script = extract_layout_script(text)
        boxes, _meta = boxes_from_layout_script(script)
        return script, boxes
    except LayoutError:
        data = parse_layout_model_text(text)
        boxes, meta = boxes_from_layout_payload(data)
        script = script_from_boxes(boxes, float(meta.get("focal") or 35))
        return script, boxes


def boxes_from_layout_script(script: str) -> Tuple[List[LayoutBox], Dict[str, Any]]:
    boxes: List[LayoutBox] = []
    focal = 35.0
    for line in str(script or "").splitlines():
        focal_match = _FOCAL_LINE.match(line.strip())
        if focal_match:
            focal = float(focal_match.group(1))
            continue
        found = _MASS_CALL.match(line.strip())
        if found is None:
            continue
        name = _unquote(found.group("name")).strip() or f"第{len(boxes) + 1}件"
        kind = _KIND_WORDS.get(_unquote(found.group("kind")).strip(), "furniture")
        values: Dict[str, Any] = {}
        for key, raw in _MASS_ARG.findall(found.group("rest") or ""):
            if key not in _MASS_KEYS:
                raise LayoutError(f"{name}写了不能用的参数。")
            values[key] = _unquote(raw) if raw[:1] in {"'", '"'} else float(raw)
        along_east = _layout_number(values.get("along_east"), f"{name}的东西长")
        along_north = _layout_number(values.get("along_north"), f"{name}的南北长")
        height = _layout_number(values.get("height"), f"{name}的高")
        if min(along_east, along_north, height) <= 0 or max(along_east, along_north, height) > 200:
            raise LayoutError(f"{name}的大小超出这一间。")
        east = _layout_number(values.get("east"), f"{name}的东")
        north = _layout_number(values.get("north"), f"{name}的北")
        bottom = _layout_number(values.get("bottom"), f"{name}的离地", 0.0)
        ramp = None
        if all(key in values for key in ("low_east", "low_north", "high_east", "high_north")):
            ramp = _ramp_offset(
                {
                    "low_east": values["low_east"],
                    "low_north": values["low_north"],
                    "high_east": values["high_east"],
                    "high_north": values["high_north"],
                    "low_z": values.get("low_z", 0),
                    "high_z": values.get("high_z", height),
                },
                along_east,
                along_north,
            )
            if ramp is not None:
                kind = "ramp"
        boxes.append(
            LayoutBox(
                name,
                kind,
                east,
                north,
                bottom + height / 2,
                along_east,
                along_north,
                height,
                ramp=ramp,
                face=_normalize_face(values.get("face")),
            )
        )
    if not boxes:
        raise LayoutError("脚本里没有白模。")
    if focal <= 0:
        focal = 35.0
    return boxes, {"focal": focal, "wall_h": 2.9, "spans": (4.0, 4.0, 4.0, 4.0)}


_SCREEN_HOST_RE = re.compile(r"控制台|操作台|整备台|保险台|操纵台|全息台")
_SCREEN_SLAB_RE = re.compile(r"屏|全息|光幕|巨幕|矩阵")
_SCREEN_WALL_RE = re.compile(r"壁关系=(贴墙|悬挂|齐平|嵌入)|落点=([北东南西])")


def _clause_faces(clause: str) -> Dict[str, str]:
    found: Dict[str, str] = {}
    for key, value in _FACE_RE.findall(str(clause or "")):
        found[key] = value
    return found


def _screen_subjects(opening: str) -> List[Dict[str, Any]]:
    """Each registered screen or display top: where it sits, and which way the screen faces."""
    text = str(opening or "")
    marks = list(_SUBJECT_HEAD_RE.finditer(text))
    wall_m = _WALL_H_RE.search(text)
    wall_h = float(wall_m.group(1)) if wall_m else 2.9
    subjects: List[Dict[str, Any]] = []
    for index, mark in enumerate(marks):
        name = (mark.group(1) or mark.group(2) or "").strip()
        if not name or name.endswith("屏面"):
            continue
        end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
        header = text.find("【", mark.end(), end)
        if header >= 0:
            end = header
        clause = text[mark.end():end]
        faces = _clause_faces(clause)
        screen_face = _normalize_face(faces.get("屏面朝向"))
        if screen_face not in {"北", "东", "南", "西"}:
            continue
        top_face = _normalize_face(faces.get("朝向"))
        host = top_face == "上" or bool(_SCREEN_HOST_RE.search(name))
        if host and _SCREEN_SLAB_RE.search(name) and top_face != "上" and not _SCREEN_HOST_RE.search(name):
            host = False
        origin = _ORIGIN_RE.search(clause)
        along = _ALONG_RE.search(clause)
        plan = _PLAN_RE.search(clause)
        lift = _LIFT_RE.search(clause)
        parallel = _AXIS_RE.search(clause)
        subjects.append(
            {
                "name": name,
                "host": host,
                "face": screen_face,
                "east": float(origin.group(2)) if origin else None,
                "north": float(origin.group(1)) if origin else None,
                "along": tuple(float(along.group(i)) for i in (1, 2, 3)) if along else None,
                "plan": tuple(float(plan.group(i)) for i in (1, 2)) if plan else None,
                "parallel": parallel.group(1) if parallel else "",
                "lift": float(lift.group(1)) if lift else None,
                "on_wall": bool(_SCREEN_WALL_RE.search(clause)) or ("壁" in name and "立式" not in name),
                "standing": "立式" in name,
                "wall_h": wall_h,
            }
        )
    return subjects


def _screen_axes(face: str, width: float, height: float, thick: float) -> Tuple[float, float, float]:
    if face in {"北", "南"}:
        return width, thick, height
    if face in {"东", "西"}:
        return thick, width, height
    return width, max(width, height), thick


def _screen_oriented(face: str, along_east: float, along_north: float, height: float) -> bool:
    if face in {"北", "南"}:
        return along_north <= along_east and along_north <= height
    if face in {"东", "西"}:
        return along_east <= along_north and along_east <= height
    return height <= along_east and height <= along_north


def _reshape_screen(face: str, along_east: float, along_north: float, height: float, along: Optional[Tuple[float, float, float]]) -> Tuple[float, float, float]:
    if along is not None:
        return _screen_axes(face, along[0], along[1], along[2])
    if _screen_oriented(face, along_east, along_north, height):
        return along_east, along_north, height
    thick = min(along_east, along_north, height)
    if abs(height - thick) <= 1e-6:
        width, risen = max(along_east, along_north), min(along_east, along_north)
        return _screen_axes(face, width, risen, thick)
    across = [value for value in (along_east, along_north) if abs(value - thick) > 1e-6]
    width = max(across) if across else max(along_east, along_north)
    return _screen_axes(face, width, height, thick)


def _default_screen_size(item: Dict[str, Any]) -> Tuple[float, float, float, float]:
    """Width, height, thick, bottom. Meters already on the subject stay; the rest is only the white-model slab."""
    if item["along"] is not None:
        width, height, thick = item["along"]
    elif item["standing"]:
        width, height, thick = 0.9, 1.6, 0.06
    elif item["on_wall"]:
        width, height, thick = 1.6, 0.9, 0.06
    else:
        width, height, thick = 1.2, 0.9, 0.06
    if item["lift"] is not None:
        bottom = item["lift"]
    elif item["standing"]:
        bottom = 0.0
    elif item["on_wall"]:
        bottom = max(0.3, item["wall_h"] * 0.35)
    else:
        bottom = 0.9
    return width, height, thick, bottom


def _mass_line(name: str, kind: str, values: Dict[str, Any]) -> str:
    parts = [json.dumps(name, ensure_ascii=False), json.dumps(kind, ensure_ascii=False)]
    for key in (
        "east",
        "north",
        "along_east",
        "along_north",
        "height",
        "bottom",
        "state",
        "low_east",
        "low_north",
        "high_east",
        "high_north",
        "low_z",
        "high_z",
        "face",
    ):
        if key not in values or values[key] in ("", None):
            continue
        if key in {"state", "face"}:
            parts.append(key + "=" + json.dumps(str(values[key]), ensure_ascii=False))
        else:
            parts.append(f"{key}={_script_number(float(values[key]))}")
    return "mass(" + ", ".join(parts) + ")"


def _mass_values(found: re.Match) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    for key, raw in _MASS_ARG.findall(found.group("rest") or ""):
        if key not in _MASS_KEYS:
            continue
        values[key] = _unquote(raw) if str(raw)[:1] in {"'", '"'} else float(raw)
    return values


def _panel_on(host: Dict[str, Any], face: str) -> Dict[str, Any]:
    along_east = float(host.get("along_east") or 0.9)
    along_north = float(host.get("along_north") or 0.9)
    height = float(host.get("height") or 0.75)
    bottom = float(host.get("bottom") or 0.0)
    east = float(host.get("east") or 0.0)
    north = float(host.get("north") or 0.0)
    across = along_east if face in {"北", "南"} else along_north
    width = max(0.45, min(across * 0.7, 1.2))
    panel_h = 0.42
    thick = 0.04
    sx, sy, sz = _screen_axes(face, width, panel_h, thick)
    shift = {"北": (0.0, along_north / 2), "南": (0.0, -along_north / 2), "东": (along_east / 2, 0.0), "西": (-along_east / 2, 0.0)}
    dx, dy = shift[face]
    return {
        "east": east + dx,
        "north": north + dy,
        "along_east": sx,
        "along_north": sy,
        "height": sz,
        "bottom": bottom + height,
        "face": face,
    }


def apply_screens(script: str, opening: str) -> str:
    """Stand each screen on the axis its screen faces. A display top keeps the table and adds the panel."""
    subjects = [item for item in _screen_subjects(opening) if item["east"] is not None and item["north"] is not None]
    if not subjects:
        return str(script or "")
    lines = str(script or "").splitlines()
    parsed: List[Optional[re.Match]] = [_MASS_CALL.match(line.strip()) for line in lines]
    names = []
    for found in parsed:
        if found is None:
            names.append("")
        else:
            names.append(_unquote(found.group("name")).strip())
    extra: List[str] = []
    for item in subjects:
        panel_name = item["name"] + "屏面"
        if item["host"]:
            host_at = names.index(item["name"]) if item["name"] in names else -1
            if host_at < 0:
                long_m, short_m = item["plan"] if item["plan"] else (0.9, 0.9)
                if item["parallel"] == "Y线":
                    along_east, along_north = short_m, long_m
                else:
                    along_east, along_north = long_m, short_m
                host_values = {
                    "east": item["east"],
                    "north": item["north"],
                    "along_east": along_east,
                    "along_north": along_north,
                    "height": _furniture_height(item["name"]),
                    "bottom": item["lift"] or 0.0,
                    "face": "上",
                }
                extra.append(_mass_line(item["name"], "furniture", host_values))
            else:
                found = parsed[host_at]
                assert found is not None
                host_values = _mass_values(found)
                host_values["face"] = "上"
                host_values.setdefault("east", item["east"])
                host_values.setdefault("north", item["north"])
                lines[host_at] = _mass_line(item["name"], "furniture", host_values)
            panel = _panel_on(host_values, item["face"])
            if panel_name in names:
                at = names.index(panel_name)
                lines[at] = _mass_line(panel_name, "screen", panel)
            else:
                extra.append(_mass_line(panel_name, "screen", panel))
            continue
        width, height, thick, bottom = _default_screen_size(item)
        along_east, along_north, risen = _screen_axes(item["face"], width, height, thick)
        values = {
            "east": item["east"],
            "north": item["north"],
            "along_east": along_east,
            "along_north": along_north,
            "height": risen,
            "bottom": bottom,
            "face": item["face"],
        }
        if item["name"] in names:
            at = names.index(item["name"])
            found = parsed[at]
            assert found is not None
            current = _mass_values(found)
            shaped = _reshape_screen(
                item["face"],
                float(current.get("along_east") or along_east),
                float(current.get("along_north") or along_north),
                float(current.get("height") or risen),
                item["along"],
            )
            values["along_east"], values["along_north"], values["height"] = shaped
            values["east"] = float(current.get("east", item["east"]))
            values["north"] = float(current.get("north", item["north"]))
            if "bottom" in current and item["lift"] is None:
                values["bottom"] = float(current["bottom"])
            if item["lift"] is not None:
                values["bottom"] = item["lift"]
            lines[at] = _mass_line(item["name"], "screen", values)
        else:
            extra.append(_mass_line(item["name"], "screen", values))
    if extra:
        lines.extend(extra)
    return "\n".join(lines)


def apply_facing(script: str, opening: str) -> str:
    """Put the opening's facing onto each mass. A subject with no facing loses a guessed face."""
    faces = facing_by_name(opening)
    lines: List[str] = []
    for raw in str(script or "").splitlines():
        found = _MASS_CALL.match(raw.strip())
        if found is None:
            lines.append(raw)
            continue
        name = _unquote(found.group("name")).strip()
        rest = re.sub(r",\s*face\s*=\s*(?:\"[^\"]*\"|'[^']*')", "", found.group("rest") or "")
        face = faces.get(name, "")
        if face:
            rest += ", face=" + json.dumps(face, ensure_ascii=False)
        lines.append(f"mass({found.group('name')}, {found.group('kind')}{rest})")
    return "\n".join(lines)


def layout_mass_fields(script: str) -> List[Dict[str, Any]]:
    """One dict per mass() line, including face and state."""
    rows: List[Dict[str, Any]] = []
    for line in str(script or "").splitlines():
        found = _MASS_CALL.match(line.strip())
        if found is None:
            continue
        name = _unquote(found.group("name")).strip()
        kind = _KIND_WORDS.get(_unquote(found.group("kind")).strip(), "furniture")
        values: Dict[str, Any] = {"name": name, "kind": kind}
        for key, raw in _MASS_ARG.findall(found.group("rest") or ""):
            if key not in _MASS_KEYS:
                continue
            values[key] = _unquote(raw) if str(raw)[:1] in {"'", '"'} else float(raw)
        rows.append(values)
    return rows


def layout_box_records(boxes: Sequence[LayoutBox]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for box in boxes:
        record: Dict[str, Any] = {
            "name": box.name,
            "kind": box.kind,
            "east": round(box.cx, 3),
            "north": round(box.cy, 3),
            "bottom": round(box.cz - box.sz / 2, 3),
            "along_east": round(box.sx, 3),
            "along_north": round(box.sy, 3),
            "height": round(box.sz, 3),
        }
        if box.face:
            record["face"] = box.face
        if box.ramp is not None:
            low_x, low_y, low_z, high_x, high_y, high_z, _px, _py = box.ramp
            record.update(
                low_east=round(low_x, 3),
                low_north=round(low_y, 3),
                low_z=round(low_z, 3),
                high_east=round(high_x, 3),
                high_north=round(high_y, 3),
                high_z=round(high_z, 3),
            )
        records.append(record)
    return records
