# -*- coding: utf-8 -*-
"""After 现场编排, measure each beat's visible range from 景别 and 机位.

The white-model boxes come from 【白模测算】. Blender places the camera and
ray-casts the clay boxes. The resulting 【可见范围】 is staging's input.
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
_WIDE = {"WS", "EWS"}
_CLOSE = {"CU", "ECU"}


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


def _field_of(shot_size: str, explicit: str) -> int:
    if _num(explicit, 0) >= 80 or str(explicit or "").strip() == "84":
        return 84
    if _num(explicit, 0) >= 40:
        return 47
    if str(shot_size or "").upper() in _WIDE:
        return 84
    return 47


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
        "transparent": fields.get("透", "") == "透" or "玻璃" in name or "水晶" in name,
        "open_state": fields.get("开闭", ""),
        "relation": relation,
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
        "field": _field_of(shot_size, fields.get("视场", "")),
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
        "field": _field_of(shot_size, fields.get("视场", "")),
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
            camera["field"] = _field_of(camera["shot_size"], merged.get("视场", "") or str(camera.get("field") or ""))
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


def _is_seat(person: Dict[str, Any], furniture: Dict[str, Any]) -> bool:
    if person["kind"] != "人" or furniture["kind"] != "具":
        return False
    seat = float(furniture["bottom"]) + float(furniture["height"])
    if abs(float(person["bottom"]) - seat) > 0.08:
        return False
    return (
        abs(float(person["east"]) - float(furniture["east"])) <= float(furniture["along_east"]) / 2.0 + 0.2
        and abs(float(person["north"]) - float(furniture["north"])) <= float(furniture["along_north"]) / 2.0 + 0.2
    )


def _occluder(camera: Dict[str, Any], box: Dict[str, Any], boxes: Sequence[Dict[str, Any]]) -> str:
    if box.get("transparent") or box.get("open_state") in {"全开", "半开"}:
        return ""
    origin = (float(camera["east"]), float(camera["north"]), float(camera["height"]))
    target = _target(box)
    for other in boxes:
        if other["name"] == box["name"]:
            continue
        if other.get("transparent") or other.get("relation") in {"地面", "天花"}:
            continue
        if other.get("open_state") in {"全开", "半开"}:
            continue
        if _is_seat(box, other):
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


def _names(token: str, box: Dict[str, Any]) -> bool:
    needle = str(token or "")
    name = str(box["name"])
    return bool(needle) and (needle == name or needle in name or name in needle)


def _in_band(camera: Dict[str, Any], box: Dict[str, Any], boxes: Sequence[Dict[str, Any]]) -> bool:
    shot_size = str(camera.get("shot_size") or "MS").upper()
    if shot_size in _WIDE or shot_size == "FS":
        return True
    host = _match_box(str(camera.get("subject") or ""), boxes)
    eye = float(host["eye"]) if host is not None and host.get("eye") else float(camera["height"])
    top = float(host["bottom"]) + float(host["height"]) if host is not None else eye + 0.2
    z = _target(box)[2]
    privileged = _names(str(camera.get("subject") or ""), box) or (
        camera.get("shot_method") == "过肩" and _names(str(camera.get("frame_owner") or ""), box)
    )
    if shot_size in _CLOSE:
        if privileged and camera.get("shot_method") == "过肩" and _names(str(camera.get("frame_owner") or ""), box):
            return True
        if not _names(str(camera.get("subject") or ""), box):
            return False
        return abs(z - eye) <= 0.20
    if shot_size == "MCU":
        return eye - 0.40 <= z <= top + 0.05 or privileged
    if eye - 0.70 <= z <= top + 0.15:
        return True
    return privileged


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
        if not probe.get("in_frustum") or not _in_band(camera, box, boxes):
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
        from app.services.script_analysis_flow.environment_layout_blender import blender_executable

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
