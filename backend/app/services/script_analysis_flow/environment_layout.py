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
        boxes.append(LayoutBox(name, kind, east, north, cz, sx, sy, sz, extra))

    if not boxes:
        raise LayoutError("开篇里没有可投影的米，画不出布局。")
    span_m = _SPAN_RE.search(text)
    if span_m:
        spans = tuple(float(span_m.group(i)) for i in (1, 2, 3, 4))
    else:
        walls = [box for box in boxes if box.kind == "wall"]
        north_span = max((box.cy for box in walls if box.cy > 0), default=4.0)
        south_span = max((-box.cy for box in walls if box.cy < 0), default=4.0)
        east_span = max((box.cx for box in walls if box.cx > 0), default=3.5)
        west_span = max((-box.cx for box in walls if box.cx < 0), default=3.5)
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


def render_layout_sheet(boxes: Sequence[LayoutBox], meta: Dict[str, Any]) -> Tuple[bytes, int]:
    focal = float(meta["focal"])
    hfov = 2 * math.atan((_SENSOR_MM / 2) / focal)
    focal_px = (_CELL[0] / 2) / math.tan(hfov / 2)
    color = np.full((_SHEET[1], _SHEET[0], 3), (108, 108, 110), dtype=np.uint8)
    depth_buf = np.full((_SHEET[1], _SHEET[0]), 1e9, dtype=np.float32)
    cameras = _cameras(meta["spans"], float(meta["wall_h"]), boxes)
    solids = [(box, _clay_faces(box)) for box in boxes]
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
天空、远景，以及高、厚、沿墙长都没有米的具，不写。
纹样、颜色、材质不写进脚本。不要加开篇没有的具。
家具占地三个数时，最后一个是 height。只有长×宽时也要写：台、桌、案 height=0.75，床、榻 height=0.55，椅 height=0.9，凳 height=0.45。写了离平地，bottom 就等于那个米。灯 kind="lamp"。桌、椅、凳、床、台 kind="furniture"。
上=写了高度米数的帐顶、穹顶、天花、顶棚、梁架写成 kind="ceiling"，bottom 等于这个高度，height=0.08，along_east 和 along_north 抄地面。高度=无限制的不上这一行。
楼梯写低端和高端：kind="ramp"，再写 low_east、low_north、high_east、high_north、low_z、high_z。
四宫格不由你摆。焦段从开篇的毫米数抄进 FOCAL_MM，没有就写 35。
FOCAL_MM = 35
mass("注册名", "wall", east=0, north=0, along_east=24, along_north=2, height=12, bottom=0)
mass("注册名", "door", east=0, north=0, along_east=4, along_north=2, height=6, bottom=0, state="全开")"""


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


def layout_messages(opening: str, missing: str = "", previous: str = "") -> List[Dict[str, str]]:
    text = str(opening or "").strip()
    if not text:
        raise LayoutError("没有开篇，不能生成布局。")
    user = "以下是开篇原文。规划已经把白模的米、朝向和开闭写在里面。只根据这些写脚本：\n" + text[:80000]
    note = str(missing or "").strip()
    prior = str(previous or "").strip()
    if note:
        closing = "。仍只根据上面的开篇重写脚本。"
        if prior:
            closing = "。仍只根据上面的开篇重写脚本。米、朝向、开闭照开篇，不新造米。"
        user += "\n\n上一份脚本没有通过：" + note[:800] + closing
    if prior:
        user += "\n上一份脚本：\n" + prior[:6000]
    return [
        {"role": "system", "content": _LAYOUT_SYSTEM},
        {"role": "user", "content": user},
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
        lines.append("mass(" + ", ".join(parts) + ")")
    return "\n".join(lines)


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
        boxes.append(LayoutBox(name, kind, east, north, bottom + height / 2, along_east, along_north, height, ramp=ramp))
    if not boxes:
        raise LayoutError("脚本里没有白模。")
    if focal <= 0:
        focal = 35.0
    return boxes, {"focal": focal, "wall_h": 2.9, "spans": (4.0, 4.0, 4.0, 4.0)}


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
