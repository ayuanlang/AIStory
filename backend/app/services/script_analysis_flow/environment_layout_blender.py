# -*- coding: utf-8 -*-
"""Run a white-model script in Blender and render the four-grid sheet.

The model writes mass() calls. This module supplies the Blender scene, the
clay materials, and the four cameras: look north, east, south, west.
"""
from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile
from typing import List

from PIL import Image, ImageDraw


class LayoutRenderError(RuntimeError):
    """Blender could not render the white model."""


_SHEET = (1280, 720)
_CELL = (640, 360)

_BLENDER_TEMPLATE = r"""
import base64
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

OUT = sys.argv[sys.argv.index("--") + 1]
SCRIPT = base64.b64decode("{script_b64}").decode("utf-8")

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

def make_material(name, color):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (color[0], color[1], color[2], 1.0)
    return material

CLAY = {{
    "floor": make_material("Floor", (0.70, 0.69, 0.66)),
    "wall": make_material("Wall", (0.86, 0.85, 0.82)),
    "ceiling": make_material("Ceiling", (0.60, 0.60, 0.58)),
    "furniture": make_material("Furniture", (0.97, 0.96, 0.93)),
    "lamp": make_material("Lamp", (0.93, 0.90, 0.84)),
    "door": make_material("Door", (0.48, 0.47, 0.45)),
    "window": make_material("Window", (0.62, 0.70, 0.74)),
    "ramp": make_material("Ramp", (0.90, 0.89, 0.86)),
}}

MADE = []

def add_box(name, kind, east, north, bottom, along_east, along_north, height):
    mesh = bpy.data.meshes.new(name)
    tool = bmesh.new()
    bmesh.ops.create_cube(tool, size=1.0)
    tool.to_mesh(mesh)
    tool.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (float(east), float(north), float(bottom) + float(height) / 2)
    obj.scale = (float(along_east), float(along_north), float(height))
    obj.data.materials.append(CLAY.get(kind, CLAY["furniture"]))
    bpy.context.scene.collection.objects.link(obj)
    return obj

def mass(name, kind, east, north, along_east, along_north, height, bottom=0, state="", low_east=None, low_north=None, high_east=None, high_north=None, low_z=0, high_z=None):
    obj = add_box(str(name), str(kind), float(east), float(north), float(bottom), float(along_east), float(along_north), float(height))
    MADE.append({{
        "name": str(name),
        "kind": str(kind),
        "east": float(east),
        "north": float(north),
        "bottom": float(bottom),
        "along_east": float(along_east),
        "along_north": float(along_north),
        "height": float(height),
        "state": str(state or ""),
        "obj": obj,
    }})

scope = {{"mass": mass, "__builtins__": {{}}}}
exec(SCRIPT, scope)
focal = float(scope.get("FOCAL_MM", 35) or 35)
if focal <= 0:
    focal = 35.0

def covers(host, east, north):
    return abs(east - host["east"]) <= host["along_east"] / 2 + 0.08 and abs(north - host["north"]) <= host["along_north"] / 2 + 0.08

def punch(host, east, north, along_east, along_north, height, bottom):
    cutter = add_box(host["name"] + "口", "window", east, north, bottom, max(along_east, 0.05), max(along_north, 0.05), height)
    depth = min(host["along_east"], host["along_north"]) + 0.3
    if along_east >= along_north:
        cutter.scale.y = depth / max(along_north, 0.02)
    else:
        cutter.scale.x = depth / max(along_east, 0.02)
    for obj in list(bpy.context.view_layer.objects):
        if obj is not None:
            obj.select_set(False)
    bpy.context.view_layer.objects.active = host["obj"]
    host["obj"].select_set(True)
    modifier = host["obj"].modifiers.new(name="Opening", type="BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.object = cutter
    try:
        modifier.solver = "FLOAT"
    except Exception:
        pass
    try:
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    except Exception:
        host["obj"].modifiers.remove(modifier)
    host["obj"].select_set(False)
    bpy.data.objects.remove(cutter, do_unlink=True)

floors = [item for item in MADE if item["kind"] == "floor"]
if floors:
    room = (floors[0]["east"], floors[0]["north"])
else:
    room = (0.0, 0.0)

for item in list(MADE):
    if item["kind"] not in {{"door", "window"}}:
        continue
    hosts = [host for host in MADE if host["kind"] == "wall" and covers(host, item["east"], item["north"])]
    if not hosts:
        continue
    host = min(hosts, key=lambda host: abs(host["east"] - item["east"]) + abs(host["north"] - item["north"]))
    punch(host, item["east"], item["north"], item["along_east"], item["along_north"], item["height"], item["bottom"])
    opened = item["state"] in {{"全开", "open"}}
    if item["kind"] == "window" or opened:
        bpy.data.objects.remove(item["obj"], do_unlink=True)
        continue
    inward_x = room[0] - item["east"]
    inward_y = room[1] - item["north"]
    span = math.hypot(inward_x, inward_y) or 1.0
    shift = min(item["along_east"], item["along_north"]) / 2 + 0.06
    item["obj"].location.x += inward_x / span * shift
    item["obj"].location.y += inward_y / span * shift
    if item["state"] in {{"半开", "half"}}:
        item["obj"].scale.x *= 0.5

bpy.context.view_layer.update()
meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
if not meshes:
    raise RuntimeError("脚本没有生成白模")

low = Vector((1e9, 1e9, 1e9))
high = Vector((-1e9, -1e9, -1e9))
for obj in meshes:
    for corner in obj.bound_box:
        point = obj.matrix_world @ Vector(corner)
        low.x, low.y, low.z = min(low.x, point.x), min(low.y, point.y), min(low.z, point.z)
        high.x, high.y, high.z = max(high.x, point.x), max(high.y, point.y), max(high.z, point.z)
center_x = (low.x + high.x) / 2
center_y = (low.y + high.y) / 2
room_h = max(0.8, high.z - low.z)
eye = 1.6 if room_h >= 2.2 else max(1.15, room_h * 0.55)
eye = min(max(low.z + 1.05, eye), high.z - 0.2)
depth = max(0.8, high.y - low.y)
width = max(0.8, high.x - low.x)
walls = [item for item in MADE if item["kind"] == "wall" and item["obj"].name in bpy.data.objects]
inside = len(walls) >= 2

def camera(name, location, target):
    data = bpy.data.cameras.new(name)
    data.lens = focal
    data.sensor_width = 36.0
    data.sensor_fit = "HORIZONTAL"
    data.clip_start = 0.05
    data.clip_end = 500.0
    obj = bpy.data.objects.new(name, data)
    obj.location = location
    direction = Vector(target) - Vector(location)
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(obj)
    return obj

half_h = math.atan(18.0 / focal)
half_v = math.atan((36.0 * 9.0 / 16.0 / 2.0) / focal)

def world_corners(obj):
    return [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]

def in_frame(cam, target, points):
    forward = (Vector(target) - Vector(cam))
    if forward.length < 0.05:
        return False
    forward.normalize()
    right = forward.cross(Vector((0.0, 0.0, 1.0)))
    if right.length < 1e-5:
        right = Vector((1.0, 0.0, 0.0))
    right.normalize()
    up = right.cross(forward).normalized()
    for point in points:
        rel = Vector(point) - Vector(cam)
        depth_in = rel.dot(forward)
        if depth_in < 0.2:
            return False
        if abs(rel.dot(right)) > depth_in * math.tan(half_h) * 0.90:
            return False
        if abs(rel.dot(up)) > depth_in * math.tan(half_v) * 0.86:
            return False
    return True

def rear_of(axis, sign):
    walls = [item for item in MADE if item["kind"] == "wall" and item["obj"].name in bpy.data.objects]
    if not walls:
        return []
    edge = max(walls, key=lambda item: item[axis]) if sign > 0 else min(walls, key=lambda item: item[axis])
    chosen = [edge]
    for item in MADE:
        if item["kind"] in {{"door", "window"}} and item["obj"].name in bpy.data.objects and covers(edge, item["east"], item["north"]):
            chosen.append(item)
    return chosen

views = (
    ("north", "north", -1, Vector((0.0, 1.0, 0.0))),
    ("east", "east", -1, Vector((1.0, 0.0, 0.0))),
    ("south", "north", 1, Vector((0.0, -1.0, 0.0))),
    ("west", "east", 1, Vector((-1.0, 0.0, 0.0))),
)
posts = []
for view_name, axis, sign, cardinal in views:
    hidden = rear_of(axis, sign) if inside else []
    skip = {{item["obj"].name for item in hidden}}
    points = []
    for obj in meshes:
        if obj.name not in skip:
            points.extend(world_corners(obj))
    if not points:
        points = [Vector((center_x, center_y, eye))]
    target = sum(points, Vector()) / len(points)
    target.z = min(max(float(target.z), 0.85), eye)
    if inside and hidden:
        wall = hidden[0]
        if axis == "east":
            outside = wall["east"] + sign * (wall["along_east"] / 2 + 0.4)
            cam = Vector((outside, target.y, eye))
        else:
            outside = wall["north"] + sign * (wall["along_north"] / 2 + 0.4)
            cam = Vector((target.x, outside, eye))
    else:
        cam = Vector((target.x, target.y, eye)) - cardinal * (max(width, depth, room_h) + 1.2)
    for _step in range(40):
        if in_frame(cam, target, points):
            break
        cam = cam - cardinal * 0.4
    posts.append((view_name, (cam.x, cam.y, cam.z), (target.x, target.y, target.z), hidden))

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.view_settings.view_transform = "Standard"
scene.view_settings.exposure = 0.4
scene.render.resolution_x = 640
scene.render.resolution_y = 360
scene.render.resolution_percentage = 100
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"
shading = scene.display.shading
shading.light = "STUDIO"
shading.color_type = "MATERIAL"
for attr, value in (("show_object_outline", True), ("show_cavity", True), ("show_shadows", True)):
    if hasattr(shading, attr):
        setattr(shading, attr, value)
if hasattr(shading, "background_type"):
    shading.background_type = "VIEWPORT"
if hasattr(shading, "background_color"):
    shading.background_color = (0.40, 0.40, 0.42)

for name, location, target, hidden in posts:
    for item in hidden:
        item["obj"].hide_render = True
        item["obj"].hide_set(True)
    scene.camera = camera(name, location, target)
    scene.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    for item in hidden:
        item["obj"].hide_render = False
        item["obj"].hide_set(False)
"""


def blender_executable() -> str:
    env = str(os.environ.get("BLENDER_EXE") or "").strip().strip('"')
    if env and os.path.isfile(env):
        return env
    found = shutil.which("blender")
    if found:
        return found
    root = os.environ.get("ProgramFiles", r"C:\Program Files")
    base = os.path.join(root, "Blender Foundation")
    found_paths: List[str] = []
    if os.path.isdir(base):
        for name in os.listdir(base):
            path = os.path.join(base, name, "blender.exe")
            if os.path.isfile(path):
                found_paths.append(path)
    if not found_paths:
        raise LayoutRenderError("本机没有 Blender，不能生成白模。")
    return sorted(found_paths)[-1]


def render_white_model(script: str) -> bytes:
    """Render the model's mass() script to one 16:9 four-grid PNG."""
    exe = blender_executable()
    payload = base64.b64encode(str(script or "").encode("utf-8")).decode("ascii")
    body = _BLENDER_TEMPLATE.format(script_b64=payload)
    with tempfile.TemporaryDirectory(prefix="aistory-clay-") as folder:
        script_path = os.path.join(folder, "white_model.py")
        with open(script_path, "w", encoding="utf-8") as handle:
            handle.write(body)
        try:
            completed = subprocess.run(
                [exe, "--background", "--python", script_path, "--", folder],
                capture_output=True,
                timeout=180,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise LayoutRenderError("白模渲染超时。") from exc
        missing = [name for name in ("north", "east", "south", "west") if not os.path.isfile(os.path.join(folder, name + ".png"))]
        if completed.returncode != 0 or missing:
            log = ((completed.stderr or b"") + b"\n" + (completed.stdout or b"")).decode("utf-8", "replace")
            tail = " ".join(line.strip() for line in log.splitlines() if line.strip())[-400:]
            raise LayoutRenderError(tail or "白模渲染失败。")
        sheet = Image.new("RGB", _SHEET, (48, 48, 50))
        for name, (left, top) in zip(("north", "east", "south", "west"), ((0, 0), (_CELL[0], 0), (0, _CELL[1]), (_CELL[0], _CELL[1]))):
            cell = Image.open(os.path.join(folder, name + ".png")).convert("RGB").resize(_CELL)
            sheet.paste(cell, (left, top))
        draw = ImageDraw.Draw(sheet)
        draw.line((_CELL[0], 0, _CELL[0], _SHEET[1]), fill=(24, 24, 26), width=2)
        draw.line((0, _CELL[1], _SHEET[0], _CELL[1]), fill=(24, 24, 26), width=2)
        return _png_bytes(sheet)


def _png_bytes(image: Image.Image) -> bytes:
    import io

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
