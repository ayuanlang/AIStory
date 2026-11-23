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
from mathutils import Matrix, Vector

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
MARK = make_material("Facing", (0.72, 0.16, 0.12))

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

def mass(name, kind, east, north, along_east, along_north, height, bottom=0, state="", face="", low_east=None, low_north=None, high_east=None, high_north=None, low_z=0, high_z=None):
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
        "face": str(face or ""),
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
    thick = min(host["along_east"], host["along_north"])
    depth = thick + 0.8
    if along_east >= along_north:
        cutter_east, cutter_north = max(along_east, 0.05) * 1.04, depth
    else:
        cutter_east, cutter_north = depth, max(along_north, 0.05) * 1.04
    cutter = add_box(host["name"] + "口", "window", east, north, bottom - 0.02, cutter_east, cutter_north, max(height, 0.05) * 1.04)
    bpy.context.view_layer.update()
    modifier = host["obj"].modifiers.new(name="Opening", type="BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.object = cutter
    try:
        modifier.solver = "EXACT"
    except Exception:
        pass
    depsgraph = bpy.context.evaluated_depsgraph_get()
    baked = bpy.data.meshes.new_from_object(host["obj"].evaluated_get(depsgraph))
    old = host["obj"].data
    host["obj"].modifiers.remove(modifier)
    host["obj"].data = baked
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(cutter, do_unlink=True)


def swing_half(item, outward):
    obj = item["obj"]
    wide_east = item["along_east"] >= item["along_north"]
    if wide_east:
        hinge = Vector((obj.location.x - item["along_east"] / 2.0, obj.location.y, obj.location.z))
        angle = math.radians(60.0 if outward.y > 0 else -60.0)
    else:
        hinge = Vector((obj.location.x, obj.location.y - item["along_north"] / 2.0, obj.location.z))
        angle = math.radians(60.0 if outward.x < 0 else -60.0)
    turned = Matrix.Rotation(angle, 4, "Z")
    obj.location = hinge + turned @ (obj.location - hinge)
    obj.rotation_euler.z += angle

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
        MADE.remove(item)
        continue
    inward = Vector((room[0] - item["east"], room[1] - item["north"], 0.0))
    if inward.length < 1e-6:
        inward = Vector((0.0, 1.0, 0.0))
    inward = inward.normalized()
    if item["state"] in {{"半开", "half"}}:
        swing_half(item, -inward)
    else:
        shift = min(item["along_east"], item["along_north"]) / 2 + 0.02
        item["obj"].location.x += inward.x * shift
        item["obj"].location.y += inward.y * shift

bpy.context.view_layer.update()

def still_here(item):
    try:
        return item["obj"].name in bpy.data.objects
    except ReferenceError:
        return False

def add_facing_mark(item):
    axis = {{"东": (1.0, 0.0, 0.0), "西": (-1.0, 0.0, 0.0), "北": (0.0, 1.0, 0.0), "南": (0.0, -1.0, 0.0), "上": (0.0, 0.0, 1.0)}}.get(str(item.get("face") or ""))
    if axis is None or not still_here(item):
        return
    ax, ay, az = axis
    host = item["obj"]
    local_face = Vector((ax * 0.5, ay * 0.5, az * 0.5))
    world_face = host.matrix_world @ local_face
    world_dir = (host.matrix_world.to_3x3() @ Vector((ax, ay, az)))
    if world_dir.length < 1e-6:
        return
    world_dir = world_dir.normalized()
    if az:
        span = min(item["along_east"], item["along_north"])
    elif ay:
        span = min(item["along_east"], item["height"])
    else:
        span = min(item["along_north"], item["height"])
    length = max(0.08, min(0.28, float(span) * 0.42))
    radius = max(0.035, min(0.11, length * 0.42))
    mesh = bpy.data.meshes.new(item["name"] + "朝向")
    tool = bmesh.new()
    bmesh.ops.create_cone(tool, cap_ends=True, segments=8, radius1=radius, radius2=0.0, depth=length)
    quat = Vector((0.0, 0.0, 1.0)).rotation_difference(world_dir)
    bmesh.ops.rotate(tool, verts=list(tool.verts), cent=Vector((0.0, 0.0, 0.0)), matrix=quat.to_matrix().to_4x4())
    tool.to_mesh(mesh)
    tool.free()
    mark = bpy.data.objects.new(item["name"] + "朝向", mesh)
    mark.location = world_face + world_dir * (length / 2.0)
    mark.data.materials.append(MARK)
    bpy.context.scene.collection.objects.link(mark)
    item["mark"] = mark

for item in list(MADE):
    add_facing_mark(item)
bpy.context.view_layer.update()

def set_hidden(item, hidden):
    item["obj"].hide_render = hidden
    item["obj"].hide_set(hidden)
    mark = item.get("mark")
    if mark is not None:
        mark.hide_render = hidden
        mark.hide_set(hidden)

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
room_h = max(0.3, high.z - low.z)
walls = [item for item in MADE if item["kind"] == "wall" and still_here(item)]
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
tan_h = math.tan(half_h)
tan_v = math.tan(half_v)
mid_z = (low.z + high.z) / 2.0

def fill_distance(span_w, span_h):
    wide = max(float(span_w), 0.3)
    tall = max(float(span_h), 0.3)
    return max(0.35, min((wide / 2.0) / tan_h, (tall / 2.0) / tan_v))

def opening_for(look):
    finite = [item for item in MADE if item["kind"] == "floor" and item["along_east"] <= 20 and item["along_north"] <= 20]
    ceilings = [item for item in MADE if item["kind"] == "ceiling" and still_here(item) and item["along_east"] <= 20 and item["along_north"] <= 20]
    wall_top = max((item["bottom"] + item["height"]) for item in walls) if walls else high.z
    ceil = min((item["bottom"] for item in ceilings), default=wall_top)
    if finite:
        slab = finite[0]
        floor_top = slab["bottom"] + slab["height"]
        height = max(0.3, ceil - floor_top)
        if abs(look.y) > 0.5:
            width = slab["along_east"]
            near = slab["north"] - math.copysign(slab["along_north"] / 2.0, look.y)
            far = slab["north"] + math.copysign(slab["along_north"] / 2.0, look.y)
            sideways = slab["east"]
        else:
            width = slab["along_north"]
            near = slab["east"] - math.copysign(slab["along_east"] / 2.0, look.x)
            far = slab["east"] + math.copysign(slab["along_east"] / 2.0, look.x)
            sideways = slab["north"]
        return near, far, width, floor_top, height, sideways
    floor_top = low.z
    height = max(0.3, ceil - floor_top)
    if abs(look.y) > 0.5:
        rear = min(walls, key=lambda item: item["north"]) if look.y > 0 else max(walls, key=lambda item: item["north"])
        far_wall = max(walls, key=lambda item: item["north"]) if look.y > 0 else min(walls, key=lambda item: item["north"])
        near = rear["north"] + math.copysign(rear["along_north"] / 2.0, look.y)
        far = far_wall["north"] - math.copysign(far_wall["along_north"] / 2.0, look.y)
        faces = []
        for item in walls:
            if item["along_east"] < item["along_north"]:
                sign = 1.0 if item["east"] >= center_x else -1.0
                faces.append(item["east"] - sign * item["along_east"] / 2.0)
        width = (max(faces) - min(faces)) if len(faces) >= 2 else max(0.3, high.x - low.x)
        return near, far, width, floor_top, height, center_x
    rear = min(walls, key=lambda item: item["east"]) if look.x > 0 else max(walls, key=lambda item: item["east"])
    far_wall = max(walls, key=lambda item: item["east"]) if look.x > 0 else min(walls, key=lambda item: item["east"])
    near = rear["east"] + math.copysign(rear["along_east"] / 2.0, look.x)
    far = far_wall["east"] - math.copysign(far_wall["along_east"] / 2.0, look.x)
    faces = []
    for item in walls:
        if item["along_north"] < item["along_east"]:
            sign = 1.0 if item["north"] >= center_y else -1.0
            faces.append(item["north"] - sign * item["along_north"] / 2.0)
    width = (max(faces) - min(faces)) if len(faces) >= 2 else max(0.3, high.y - low.y)
    return near, far, width, floor_top, height, center_y

def clamp_inside(value, rear, far, look_sign):
    inner_rear = rear + look_sign * 0.25
    inner_far = far - look_sign * 0.25
    if look_sign > 0:
        if inner_rear > inner_far:
            return (rear + far) / 2.0
        return min(max(value, inner_rear), inner_far)
    if inner_rear < inner_far:
        return (rear + far) / 2.0
    return max(min(value, inner_rear), inner_far)

def occupies(item, point):
    if item["kind"] not in {{"furniture", "lamp", "door"}}:
        return False
    if not still_here(item):
        return False
    corners = [item["obj"].matrix_world @ Vector(corner) for corner in item["obj"].bound_box]
    pad = 0.12
    return (
        min(corner.x for corner in corners) - pad < point.x < max(corner.x for corner in corners) + pad
        and min(corner.y for corner in corners) - pad < point.y < max(corner.y for corner in corners) + pad
        and min(corner.z for corner in corners) - pad < point.z < max(corner.z for corner in corners) + pad
    )

def clear_props(cam, look, rear, far, skipped):
    hidden_names = {{item["obj"].name for item in skipped if still_here(item)}}
    for _step in range(16):
        if not any(still_here(item) and occupies(item, cam) and item["obj"].name not in hidden_names for item in MADE):
            return cam
        nxt = cam + look * 0.25
        if abs(look.y) > 0.5:
            nxt.y = clamp_inside(nxt.y, rear, far, look.y)
        else:
            nxt.x = clamp_inside(nxt.x, rear, far, look.x)
        if (nxt - cam).length < 0.02:
            return cam
        cam = nxt
    return cam

def on_wall(item, wall):
    return abs(item["east"] - wall["east"]) <= wall["along_east"] / 2 + 0.2 and abs(item["north"] - wall["north"]) <= wall["along_north"] / 2 + 0.2

def rear_of(axis, sign):
    walls = [item for item in MADE if item["kind"] == "wall" and still_here(item)]
    if not walls:
        return []
    edge = max(walls, key=lambda item: item[axis]) if sign > 0 else min(walls, key=lambda item: item[axis])
    chosen = [edge]
    for item in MADE:
        if not still_here(item):
            continue
        if item["kind"] in {{"door", "window", "furniture"}} and on_wall(item, edge):
            chosen.append(item)
    return chosen

def central_subject():
    finite = [item for item in MADE if item["kind"] == "floor" and item["along_east"] <= 20 and item["along_north"] <= 20]
    origin = (finite[0]["east"], finite[0]["north"]) if finite else (center_x, center_y)
    items = [item for item in MADE if item["kind"] == "furniture" and still_here(item)]
    if not items:
        return None
    return min(items, key=lambda item: (item["east"] - origin[0]) ** 2 + (item["north"] - origin[1]) ** 2)

def interior_pose(look):
    near, far, width, floor_top, height, sideways = opening_for(look)
    ceil = floor_top + height
    cam_z = min(max(floor_top + 1.05, floor_top + height * 0.68), ceil - 0.22)
    subject = central_subject()
    component = look.y if abs(look.y) > 0.5 else look.x
    if subject is None:
        dist = fill_distance(width, height)
        return near - component * dist, cam_z, far, cam_z, sideways
    if abs(look.y) > 0.5:
        front = subject["north"] - math.copysign(subject["along_north"] / 2.0, look.y)
    else:
        front = subject["east"] - math.copysign(subject["along_east"] / 2.0, look.x)
    front_top = subject["bottom"] + subject["height"]

    def measure(stand):
        cam_axis = near - component * stand
        d_front = (front - cam_axis) * component
        d_far = (far - cam_axis) * component
        return cam_axis, d_front, d_far

    for step in range(0, 48):
        stand = -0.4 + step * 0.18
        cam_axis, d_front, d_far = measure(stand)
        d_floor = d_front - 0.35
        if d_floor < 0.55 or d_far < d_front + 0.4:
            continue
        ang_floor = math.atan((floor_top - cam_z) / d_floor)
        ang_ceil = math.atan((ceil - cam_z) / d_far)
        if ang_ceil - ang_floor < (2.0 * half_v) - 0.16:
            aim_z = cam_z + math.tan((ang_ceil + ang_floor) / 2.0) * d_far
            return cam_axis, cam_z, far, aim_z, sideways
    for step in range(0, 48):
        stand = -0.4 + step * 0.18
        cam_axis, d_front, d_far = measure(stand)
        if d_front < 0.7 or d_far < d_front + 0.4:
            continue
        ang_front = math.atan((front_top - cam_z) / d_front)
        ang_ceil = math.atan((ceil - cam_z) / d_far)
        if ang_ceil - ang_front < (2.0 * half_v) - 0.08:
            aim_z = cam_z + math.tan((ang_ceil + ang_front) / 2.0) * d_far
            return cam_axis, cam_z, far, aim_z, sideways
    dist = fill_distance(width, height)
    return near - component * dist, cam_z, far, cam_z, sideways

views = (
    ("north", "north", -1, Vector((0.0, 1.0, 0.0))),
    ("east", "east", -1, Vector((1.0, 0.0, 0.0))),
    ("south", "north", 1, Vector((0.0, -1.0, 0.0))),
    ("west", "east", 1, Vector((-1.0, 0.0, 0.0))),
)
posts = []
for view_name, axis, sign, cardinal in views:
    hidden = rear_of(axis, sign) if inside else []
    look = cardinal.normalized()
    if abs(look.y) > 0.5:
        span_w = high.x - low.x
        far = high.y if look.y > 0 else low.y
        rear = low.y if look.y > 0 else high.y
        if inside:
            cam_axis, cam_z, aim_axis, aim_z, sideways = interior_pose(look)
            center_x = sideways
        else:
            near = low.y if look.y > 0 else high.y
            cam_axis = near - look.y * fill_distance(span_w, room_h)
            cam_z = mid_z
            aim_axis = center_y
            aim_z = mid_z
        cam = clear_props(Vector((center_x, cam_axis, cam_z)), look, rear, far, hidden)
        aim = Vector((center_x, aim_axis, aim_z))
    else:
        span_w = high.y - low.y
        far = high.x if look.x > 0 else low.x
        rear = low.x if look.x > 0 else high.x
        if inside:
            cam_axis, cam_z, aim_axis, aim_z, sideways = interior_pose(look)
            center_y = sideways
        else:
            near = low.x if look.x > 0 else high.x
            cam_axis = near - look.x * fill_distance(span_w, room_h)
            cam_z = mid_z
            aim_axis = center_x
            aim_z = mid_z
        cam = clear_props(Vector((cam_axis, center_y, cam_z)), look, rear, far, hidden)
        aim = Vector((aim_axis, center_y, aim_z))
    posts.append((view_name, (cam.x, cam.y, cam.z), (aim.x, aim.y, aim.z), hidden))

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.view_settings.view_transform = "Standard"
scene.view_settings.exposure = 0.0
scene.render.resolution_x = 640
scene.render.resolution_y = 360
scene.render.resolution_percentage = 100
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"
shading = scene.display.shading
shading.light = "FLAT"
shading.color_type = "MATERIAL"
for attr, value in (("show_object_outline", True), ("show_cavity", False), ("show_shadows", True), ("shadow_intensity", 0.25)):
    if hasattr(shading, attr):
        setattr(shading, attr, value)
if hasattr(shading, "background_type"):
    shading.background_type = "VIEWPORT"
if hasattr(shading, "background_color"):
    shading.background_color = (0.40, 0.40, 0.42)

for name, location, target, hidden in posts:
    for item in hidden:
        set_hidden(item, True)
    scene.camera = camera(name, location, target)
    scene.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    for item in hidden:
        set_hidden(item, False)
"""


def _windows_blender_exes() -> List[str]:
    roots: List[str] = []
    for key in ("ProgramW6432", "ProgramFiles"):
        value = str(os.environ.get(key) or "").strip()
        if value and value not in roots:
            roots.append(value)
    if r"C:\Program Files" not in roots:
        roots.append(r"C:\Program Files")
    found: List[str] = []
    for root in roots:
        base = os.path.join(root, "Blender Foundation")
        if not os.path.isdir(base):
            continue
        for name in os.listdir(base):
            path = os.path.join(base, name, "blender.exe")
            if os.path.isfile(path):
                found.append(path)
    return sorted(set(found))


def _bundled_blender() -> str:
    """Official Linux build unpacked by scripts/install_blender_linux.sh."""
    backend = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    for name in ("blender-launcher", "blender"):
        path = os.path.join(backend, ".blender", name)
        if os.path.isfile(path):
            return path
    return ""


def blender_executable() -> str:
    env = str(os.environ.get("BLENDER_EXE") or "").strip().strip('"')
    if env and os.path.isfile(env):
        return env
    found = shutil.which("blender")
    if found:
        return found
    bundled = _bundled_blender()
    if bundled:
        return bundled
    windows = _windows_blender_exes()
    if windows:
        return windows[-1]
    raise LayoutRenderError("本机没有 Blender，不能生成白模。")


def blender_process_env(exe: str) -> dict:
    """Prefer the Blender tree's lib/ so a machine without X11 can still start it."""
    env = os.environ.copy()
    lib_dir = os.path.join(os.path.dirname(os.path.abspath(exe)), "lib")
    if os.path.isdir(lib_dir):
        previous = str(env.get("LD_LIBRARY_PATH") or "")
        env["LD_LIBRARY_PATH"] = lib_dir if not previous else lib_dir + os.pathsep + previous
    return env


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
                env=blender_process_env(exe),
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
