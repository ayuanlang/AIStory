# -*- coding: utf-8 -*-
"""Run a white-model script in Blender.

The model writes mass() calls. An environment white model is one 16:9 sheet of
four views: north at the top left, east at the top right, south at the bottom
left, west at the bottom right. A shot white model is one frame, or a clip,
looking the named way.
The picture is an orientation drawing: black lines on white. A short tab marks
the facing side. Fill, shadow, and lamp color stay out of the picture.
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
VIEW = "{view}"
MOTION = base64.b64decode("{motion_b64}").decode("utf-8")

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

def make_material(name, color):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (color[0], color[1], color[2], 1.0)
    return material

COLOR_N = [1]

def next_color():
    n = COLOR_N[0]
    COLOR_N[0] += 1
    return (((n * 53) % 200 + 20) / 255.0, ((n * 97) % 200 + 20) / 255.0, ((n * 29) % 200 + 20) / 255.0)

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
    obj.data.materials.append(make_material(name, next_color()))
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
    world_dir = host.matrix_world.to_3x3() @ Vector((ax, ay, az))
    if world_dir.length < 1e-6:
        return
    world_dir = world_dir.normalized()
    world_face = host.matrix_world @ Vector((ax * 0.5, ay * 0.5, az * 0.5))
    if az:
        span = min(item["along_east"], item["along_north"])
    elif ay:
        span = min(item["along_east"], item["height"])
    else:
        span = min(item["along_north"], item["height"])
    length = max(0.12, min(0.45, float(span) * 0.35))
    thick = max(0.04, min(0.12, float(span) * 0.16))
    mark = add_box(item["name"] + "朝向", "furniture", 0, 0, -thick / 2.0, length, thick, thick)
    mark.location = world_face + world_dir * (length / 2.0)
    mark.rotation_euler = Vector((1.0, 0.0, 0.0)).rotation_difference(world_dir).to_euler()
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
closures = [
    item for item in MADE
    if item["kind"] in {{"wall", "door", "window"}} and still_here(item) and item["along_east"] != item["along_north"]
]
inside = len(closures) >= 2

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
    if direction.length < 1e-6:
        direction = Vector((0.0, 0.0, -1.0))
    if VIEW:
        if abs(direction.normalized().z) > 0.98:
            obj.rotation_euler = (0.0, 0.0, 0.0) if direction.z <= 0 else (math.pi, 0.0, 0.0)
        else:
            obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    else:
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
        ends = [item for item in closures if item["along_north"] < item["along_east"]] or walls
        if not ends:
            return (low.y if look.y > 0 else high.y), (high.y if look.y > 0 else low.y), max(0.3, high.x - low.x), floor_top, height, center_x
        rear = min(ends, key=lambda item: item["north"]) if look.y > 0 else max(ends, key=lambda item: item["north"])
        far_wall = max(ends, key=lambda item: item["north"]) if look.y > 0 else min(ends, key=lambda item: item["north"])
        near = rear["north"] + math.copysign(rear["along_north"] / 2.0, look.y)
        far = far_wall["north"] - math.copysign(far_wall["along_north"] / 2.0, look.y)
        faces = []
        for item in closures:
            if item["along_east"] < item["along_north"]:
                sign = 1.0 if item["east"] >= center_x else -1.0
                faces.append(item["east"] - sign * item["along_east"] / 2.0)
        width = (max(faces) - min(faces)) if len(faces) >= 2 else max(0.3, high.x - low.x)
        return near, far, width, floor_top, height, center_x
    ends = [item for item in closures if item["along_east"] < item["along_north"]] or walls
    if not ends:
        return (low.x if look.x > 0 else high.x), (high.x if look.x > 0 else low.x), max(0.3, high.y - low.y), floor_top, height, center_y
    rear = min(ends, key=lambda item: item["east"]) if look.x > 0 else max(ends, key=lambda item: item["east"])
    far_wall = max(ends, key=lambda item: item["east"]) if look.x > 0 else min(ends, key=lambda item: item["east"])
    near = rear["east"] + math.copysign(rear["along_east"] / 2.0, look.x)
    far = far_wall["east"] - math.copysign(far_wall["along_east"] / 2.0, look.x)
    faces = []
    for item in closures:
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
    if item["kind"] not in {{"furniture", "lamp", "door", "person", "prop", "screen"}}:
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

def face_slab(item, axis):
    if item["kind"] not in {{"wall", "door", "window"}} or not still_here(item):
        return False
    if axis == "north":
        return item["along_north"] < item["along_east"]
    return item["along_east"] < item["along_north"]

def outer_face(item, axis, sign):
    half = (item["along_north"] if axis == "north" else item["along_east"]) / 2.0
    return item[axis] + sign * half

def rear_of(axis, sign):
    slabs = [item for item in MADE if face_slab(item, axis)]
    if not slabs:
        return []
    faces = [outer_face(item, axis, sign) for item in slabs]
    edge_value = max(faces) if sign > 0 else min(faces)
    chosen = [item for item, face in zip(slabs, faces) if abs(face - edge_value) <= 0.35]
    seen = {{id(item) for item in chosen}}
    for item in MADE:
        if not still_here(item) or id(item) in seen:
            continue
        if item["kind"] in {{"door", "window", "furniture"}} and any(on_wall(item, host) for host in chosen if host["kind"] == "wall"):
            chosen.append(item)
            seen.add(id(item))
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
    cam_z = min(max(floor_top + 1.05, min(floor_top + 1.60, floor_top + height * 0.55)), ceil - 0.22)
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

posts = []
all_views = (
    ("north", "north", -1, Vector((0.0, 1.0, 0.0))),
    ("east", "east", -1, Vector((1.0, 0.0, 0.0))),
    ("south", "north", 1, Vector((0.0, -1.0, 0.0))),
    ("west", "east", 1, Vector((-1.0, 0.0, 0.0))),
)
views = all_views if not VIEW else tuple(item for item in all_views if item[0] == VIEW)
if not views:
    raise RuntimeError("没有这一面的机位")
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
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.resolution_percentage = 100
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"
shading = scene.display.shading
shading.light = "FLAT"
shading.color_type = "MATERIAL"
for attr, value in (("show_object_outline", False), ("show_cavity", False), ("show_shadows", False), ("shadow_intensity", 0.0)):
    if hasattr(shading, attr):
        setattr(shading, attr, value)
if hasattr(shading, "background_type"):
    shading.background_type = "VIEWPORT"
if hasattr(shading, "background_color"):
    shading.background_color = (1.0, 1.0, 1.0)

def motion_pose(base, aim, dolly, rise, pan_deg, dip_deg=0.0):
    forward = Vector(aim) - Vector(base)
    flat = Vector((forward.x, forward.y, 0.0))
    if flat.length < 1e-4:
        flat = Vector((0.0, 1.0, 0.0))
    else:
        flat = flat.normalized()
    look = Matrix.Rotation(math.radians(float(pan_deg)), 4, "Z") @ forward
    loc = Vector(base) + flat * float(dolly) + Vector((0.0, 0.0, float(rise)))
    dip = math.radians(max(0.0, min(20.0, float(dip_deg))))
    level = Vector((look.x, look.y, 0.0))
    focus = loc + Vector((level.x * math.cos(dip), level.y * math.cos(dip), -level.length * math.sin(dip)))
    return loc, focus

def frame_of(tick, seconds, last):
    if seconds <= 0:
        return 1
    return max(1, min(last, 1 + int(round((float(tick) / seconds) * (last - 1)))))

def linearize(obj, step=False):
    data = obj.animation_data
    action = data.action if data is not None else None
    curves = getattr(action, "fcurves", None) if action is not None else None
    mode = "CONSTANT" if step else "LINEAR"
    for curve in curves or []:
        for point in curve.keyframe_points:
            point.interpolation = mode

def subject_stand(look):
    people = [item for item in MADE if item["kind"] == "person" and still_here(item)]
    subject = people[0] if people else central_subject()
    if subject is None:
        return None
    finite = [item for item in MADE if item["kind"] == "floor" and still_here(item) and item["along_east"] <= 20 and item["along_north"] <= 20]
    floor_z = (finite[0]["bottom"] + finite[0]["height"]) if finite else 0.0
    cam_z = floor_z + 1.60
    if abs(look.y) > 0.5:
        front = subject["north"] - math.copysign(subject["along_north"] / 2.0, look.y)
        cam_x = subject["east"]
        cam_y = front - look.y * 1.40
        aim_x = subject["east"]
        aim_y = subject["north"]
    else:
        front = subject["east"] - math.copysign(subject["along_east"] / 2.0, look.x)
        cam_y = subject["north"]
        cam_x = front - look.x * 1.40
        aim_x = subject["east"]
        aim_y = subject["north"]
    if finite:
        slab = finite[0]
        pad = 0.35
        cam_x = min(max(cam_x, slab["east"] - slab["along_east"] / 2.0 + pad), slab["east"] + slab["along_east"] / 2.0 - pad)
        cam_y = min(max(cam_y, slab["north"] - slab["along_north"] / 2.0 + pad), slab["north"] + slab["along_north"] / 2.0 - pad)
    return (cam_x, cam_y, cam_z), (aim_x, aim_y, cam_z)

if MOTION.strip():
    seconds = 4.0
    fps = 8
    cams = []
    focals = []
    moves = []
    for raw in MOTION.splitlines():
        line = raw.strip()
        if line.startswith("SECONDS"):
            seconds = max(1.0, float(line.split("=", 1)[1]))
        elif line.startswith("FPS"):
            fps = max(4, int(float(line.split("=", 1)[1])))
        elif line.startswith("CAM"):
            fields = {{}}
            for part in line.split()[1:]:
                if "=" in part:
                    key, value = part.split("=", 1)
                    fields[key] = value
            cams.append(fields)
        elif line.startswith("FOCAL"):
            fields = {{}}
            for part in line.split()[1:]:
                if "=" in part:
                    key, value = part.split("=", 1)
                    fields[key] = value
            focals.append(fields)
        elif line.startswith("MOVE"):
            bits = line.split('"', 2)
            if len(bits) < 3:
                continue
            fields = {{"name": bits[1]}}
            for part in bits[2].split():
                if "=" in part:
                    key, value = part.split("=", 1)
                    fields[key] = value
            moves.append(fields)
    if not posts:
        raise RuntimeError("没有这一面的机位")
    name, location, target, hidden = posts[0]
    cardinals = {{
        "north": Vector((0.0, 1.0, 0.0)),
        "east": Vector((1.0, 0.0, 0.0)),
        "south": Vector((0.0, -1.0, 0.0)),
        "west": Vector((-1.0, 0.0, 0.0)),
    }}
    posed = subject_stand(cardinals.get(VIEW, Vector((0.0, 1.0, 0.0))))
    if posed is not None:
        location, target = posed
    for item in hidden:
        set_hidden(item, True)
    last = max(2, int(round(seconds * fps)))
    scene.frame_start = 1
    scene.frame_end = last
    scene.render.fps = fps
    scene.render.resolution_x = 854
    scene.render.resolution_y = 480
    cam_obj = camera(name, location, target)
    scene.camera = cam_obj
    def focal_now(tick):
        chosen = float(focal)
        best_t = -1.0
        for item in focals:
            try:
                mark = float(item.get("t", 0))
                mm = float(item.get("mm", chosen))
            except (TypeError, ValueError):
                continue
            if mark <= float(tick) + 1e-3 and mark >= best_t:
                best_t = mark
                chosen = mm
        return max(18.0, min(85.0, chosen))

    def box_at(item, tick):
        east = item["east"]
        north = item["north"]
        keys = []
        for fields in moves:
            if fields.get("name") != item["name"]:
                continue
            try:
                keys.append((float(fields.get("t", 0)), float(fields.get("east", east)), float(fields.get("north", north))))
            except (TypeError, ValueError):
                continue
        keys.sort()
        if not keys:
            return east, north
        if tick <= keys[0][0]:
            return keys[0][1], keys[0][2]
        if tick >= keys[-1][0]:
            return keys[-1][1], keys[-1][2]
        for left, right in zip(keys, keys[1:]):
            t0, e0, n0 = left
            t1, e1, n1 = right
            if t0 <= tick <= t1 and t1 > t0:
                blend = (tick - t0) / (t1 - t0)
                return e0 + (e1 - e0) * blend, n0 + (n1 - n0) * blend
        return east, north

    def cam_fields(tick):
        ordered = sorted(cams, key=lambda fields: float(fields.get("t", 0) or 0))
        if not ordered:
            return 0.0, 0.0, 0.0, 0.0
        def pick(key, default=0.0):
            prev = None
            nxt = None
            for fields in ordered:
                mark = float(fields.get("t", 0) or 0)
                if mark <= tick + 1e-4:
                    prev = (mark, fields)
                elif nxt is None:
                    nxt = (mark, fields)
                    break
            if prev is None:
                prev = (float(ordered[0].get("t", 0) or 0), ordered[0])
            if nxt is None or nxt[0] <= prev[0]:
                try:
                    return float(prev[1].get(key, default) or default)
                except (TypeError, ValueError):
                    return default
            try:
                v0 = float(prev[1].get(key, default) or default)
                v1 = float(nxt[1].get(key, default) or default)
            except (TypeError, ValueError):
                return default
            return v0 + (v1 - v0) * ((tick - prev[0]) / (nxt[0] - prev[0]))
        return pick("dolly"), pick("rise"), pick("pan"), pick("dip")

    def buried_in_wall(point):
        for item in MADE:
            if item["kind"] != "wall" or not still_here(item):
                continue
            if (
                abs(point.x - item["east"]) < item["along_east"] / 2.0 - 0.05
                and abs(point.y - item["north"]) < item["along_north"] / 2.0 - 0.05
                and item["bottom"] - 0.05 < point.z < item["bottom"] + item["height"] + 0.05
            ):
                return True
        return False

    def person_span(loc, tick):
        flat = Vector((target[0] - location[0], target[1] - location[1], 0.0))
        if flat.length < 1e-4:
            flat = Vector((0.0, 1.0, 0.0))
        else:
            flat = flat.normalized()
        best = None
        for item in MADE:
            if item["kind"] != "person" or not still_here(item):
                continue
            east, north = box_at(item, tick)
            along = (east - loc.x) * flat.x + (north - loc.y) * flat.y
            wide = item["along_east"] if abs(flat.y) >= abs(flat.x) else item["along_north"]
            deep = item["along_north"] if abs(flat.y) >= abs(flat.x) else item["along_east"]
            half = deep / 2.0
            if along + half <= 0.02:
                continue
            near = along - half
            if best is None or near < best[0]:
                best = (near, wide, flat)
        return best

    def frame_group(loc, focus, tick, mm, dolly):
        people = []
        for item in MADE:
            if item["kind"] != "person" or not still_here(item):
                continue
            east, north = box_at(item, tick)
            people.append((east, north, item))
        if len(people) < 2 or mm > 36.0 or float(dolly) > 0.2:
            return loc, focus, mm
        cx = sum(item[0] for item in people) / float(len(people))
        cy = sum(item[1] for item in people) / float(len(people))
        forward = Vector((focus.x - loc.x, focus.y - loc.y, 0.0))
        if forward.length < 1e-4:
            forward = Vector((1.0, 0.0, 0.0))
        else:
            forward = forward.normalized()
        side = Vector((-forward.y, forward.x, 0.0))
        span = 0.8
        for east, north, item in people:
            wide = item["along_north"] if abs(forward.x) >= abs(forward.y) else item["along_east"]
            lateral = abs((east - cx) * side.x + (north - cy) * side.y) + wide / 2.0 + 0.35
            span = max(span, lateral)
        chosen = float(mm)
        trial = loc
        for _try in range(8):
            dist = span / max((18.0 / max(chosen, 1.0)) * 0.68, 0.08)
            dist = max(1.8, dist)
            trial = Vector((cx, cy, loc.z)) - forward * dist
            if not buried_in_wall(trial):
                break
            chosen = max(18.0, chosen - 3.0)
        return trial, Vector((cx, cy, loc.z)), chosen

    def hold_props(loc, focus, tick, mm, dolly):
        if float(mm) <= 36.0 and float(dolly) <= 0.2:
            return loc, focus, mm
        people = []
        props = []
        for item in MADE:
            if not still_here(item) or item["kind"] not in {{"person", "prop"}}:
                continue
            east, north = box_at(item, tick)
            center_z = item["bottom"] + item["height"] * (0.55 if item["kind"] == "person" else 0.5)
            row = (east, north, center_z, item)
            if item["kind"] == "person":
                people.append(row)
            else:
                props.append(row)
        if not people or not props:
            return loc, focus, mm
        forward = Vector((focus.x - loc.x, focus.y - loc.y, 0.0))
        if forward.length < 1e-4:
            forward = Vector((0.0, 1.0, 0.0))
        else:
            forward = forward.normalized()
        px = sum(row[0] for row in props) / float(len(props))
        py = sum(row[1] for row in props) / float(len(props))
        pz = sum(row[2] for row in props) / float(len(props))
        hx = sum(row[0] for row in people) / float(len(people))
        hy = sum(row[1] for row in people) / float(len(people))
        hz = sum(row[2] for row in people) / float(len(people))
        aim = Vector((px * 0.6 + hx * 0.4, py * 0.6 + hy * 0.4, pz * 0.55 + hz * 0.45))
        head = max(row[2] + row[3]["height"] * 0.45 for row in people)
        low = min(row[2] - row[3]["height"] * 0.5 for row in props)
        half_v = max(abs(head - aim.z), abs(aim.z - low)) + 0.2
        side = Vector((-forward.y, forward.x, 0.0))
        half_h = 0.35
        for east, north, _cz, item in people + props:
            wide = item["along_north"] if abs(forward.x) >= abs(forward.y) else item["along_east"]
            lateral = abs((east - aim.x) * side.x + (north - aim.y) * side.y) + wide / 2.0
            half_h = max(half_h, lateral + 0.15)
        chosen = float(mm) if float(mm) <= 36.0 else min(float(mm), 35.0)
        trial = loc
        for _try in range(8):
            tan_h = 18.0 / max(chosen, 1.0)
            tan_v = 10.125 / max(chosen, 1.0)
            dist = max(half_h / max(tan_h * 0.7, 0.05), half_v / max(tan_v * 0.7, 0.05), 1.6)
            trial = Vector((aim.x, aim.y, loc.z)) - forward * dist
            if not buried_in_wall(trial):
                break
            chosen = max(24.0, chosen - 3.0)
            dist = max(1.6, dist - 0.35)
            trial = Vector((aim.x, aim.y, loc.z)) - forward * dist
        return trial, aim, chosen

    ticks = {{0.0, float(seconds)}}
    for fields in cams:
        try:
            ticks.add(float(fields.get("t", 0) or 0))
        except (TypeError, ValueError):
            continue
    for fields in moves:
        try:
            ticks.add(float(fields.get("t", 0) or 0))
        except (TypeError, ValueError):
            continue
    for fields in focals:
        try:
            ticks.add(float(fields.get("t", 0) or 0))
        except (TypeError, ValueError):
            continue
    for tick in sorted(ticks):
        if tick < -1e-4 or tick > float(seconds) + 1e-4:
            continue
        dolly, rise, pan, dip = cam_fields(tick)
        dolly = min(dolly, 1.40 - 0.55 * focal_now(tick) / 36.0)
        loc, focus = motion_pose(location, target, dolly, rise, pan, dip)
        span = person_span(loc, tick)
        if span is not None and (float(dolly) > 0.2 or focal_now(tick) > 36.0):
            near, wide, flat = span
            need = max(0.45, wide * 1.35 * focal_now(tick) / 36.0)
            if near < need:
                delta = flat * (near - need)
                loc = loc + delta
                focus = focus + delta
        loc, focus, grouped_mm = frame_group(loc, focus, tick, focal_now(tick), dolly)
        loc, focus, held_mm = hold_props(loc, focus, tick, focal_now(tick), dolly)
        for _step in range(24):
            if not buried_in_wall(loc):
                break
            forward = Vector((focus.x - loc.x, focus.y - loc.y, 0.0))
            if forward.length < 1e-4:
                break
            forward = forward.normalized()
            loc = loc + forward * 0.12
            focus = focus + forward * 0.12
        mm = min(focal_now(tick), grouped_mm, held_mm)
        span = person_span(loc, tick)
        if span is not None and span[0] > 0.2:
            fit = span[0] * 36.0 / max(span[1] * 1.35, 0.2)
            mm = max(18.0, min(mm, fit))
        cam_obj.location = loc
        direction = focus - loc
        if direction.length < 1e-6:
            direction = Vector((0.0, 0.0, -1.0))
        if abs(direction.normalized().z) > 0.98:
            cam_obj.rotation_euler = (0.0, 0.0, 0.0) if direction.z <= 0 else (math.pi, 0.0, 0.0)
        else:
            cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        mark = frame_of(tick, seconds, last)
        cam_obj.keyframe_insert("location", frame=mark)
        cam_obj.keyframe_insert("rotation_euler", frame=mark)
        cam_obj.data.lens = mm
        cam_obj.data.keyframe_insert(data_path="lens", frame=mark)
    linearize(cam_obj)
    linearize(cam_obj.data, True)
    for fields in moves:
        obj = bpy.data.objects.get(fields.get("name") or "")
        if obj is None:
            continue
        obj.location.x = float(fields.get("east", obj.location.x))
        obj.location.y = float(fields.get("north", obj.location.y))
        obj.keyframe_insert("location", frame=frame_of(fields.get("t", 0), seconds, last))
        linearize(obj)
    scene.render.filepath = os.path.join(OUT, "frame_")
    bpy.ops.render.render(animation=True)
else:
    if not VIEW:
        scene.render.resolution_x = 640
        scene.render.resolution_y = 360
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


def orientation_lines(cell: Image.Image) -> Image.Image:
    """Turn each flat color into a boundary. The fill never reaches the sheet."""
    rgb = cell.convert("RGB")
    width, height = rgb.size
    src = rgb.load()
    out = Image.new("L", (width, height), 255)
    dst = out.load()
    for y in range(height):
        row = [src[x, y] for x in range(width)]
        below = [src[x, y + 1] for x in range(width)] if y + 1 < height else None
        for x, here in enumerate(row):
            right = row[x + 1] if x + 1 < width else None
            if right is not None and abs(here[0] - right[0]) + abs(here[1] - right[1]) + abs(here[2] - right[2]) >= 24:
                dst[x, y] = 0
            elif below is not None and abs(here[0] - below[x][0]) + abs(here[1] - below[x][1]) + abs(here[2] - below[x][2]) >= 24:
                dst[x, y] = 0
    return out.convert("RGB")


def _encode_line_video(folder: str, fps: int) -> bytes:
    import glob

    import imageio_ffmpeg

    frames = sorted(glob.glob(os.path.join(folder, "frame_*.png")))
    if not frames:
        raise LayoutRenderError("白模动画没有画面。")
    lined = os.path.join(folder, "lined")
    os.makedirs(lined, exist_ok=True)
    for index, path in enumerate(frames, start=1):
        orientation_lines(Image.open(path).convert("RGB")).save(os.path.join(lined, f"frame_{index:04d}.png"))
    out = os.path.join(folder, "anim.mp4")
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    completed = subprocess.run(
        [
            exe, "-y", "-framerate", str(max(4, int(fps or 8))),
            "-i", os.path.join(lined, "frame_%04d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            out,
        ],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0 or not os.path.isfile(out):
        tail = ((completed.stderr or b"")).decode("utf-8", "replace")[-300:]
        raise LayoutRenderError(tail or "白模动画没有合成。")
    with open(out, "rb") as handle:
        return handle.read()


def _composite_quad(folder: str) -> bytes:
    """North, east, south, west, in that order, on one 16:9 sheet."""
    missing = [name for name in ("north", "east", "south", "west") if not os.path.isfile(os.path.join(folder, name + ".png"))]
    if missing:
        raise LayoutRenderError("白模四宫缺了一格。")
    sheet = Image.new("RGB", _SHEET, (255, 255, 255))
    for name, (left, top) in zip(("north", "east", "south", "west"), ((0, 0), (_CELL[0], 0), (0, _CELL[1]), (_CELL[0], _CELL[1]))):
        cell = orientation_lines(Image.open(os.path.join(folder, name + ".png")).convert("RGB").resize(_CELL))
        sheet.paste(cell, (left, top))
    draw = ImageDraw.Draw(sheet)
    draw.line((_CELL[0], 0, _CELL[0], _SHEET[1]), fill=(0, 0, 0), width=2)
    draw.line((0, _CELL[1], _SHEET[0], _CELL[1]), fill=(0, 0, 0), width=2)
    return _png_bytes(sheet)


def render_white_model(script: str, view: str = "", motion: str = "") -> bytes:
    """Render the model's mass() script.

    An empty view is the four-view sheet. north, east, south, or west is one
    16:9 frame looking that way. Motion renders that view as a white-model clip.
    """
    chosen = str(view or "").strip().lower()
    clip = str(motion or "").strip()
    if clip and chosen not in {"north", "east", "south", "west"}:
        raise LayoutRenderError("没有这一面的机位")
    if chosen and chosen not in {"north", "east", "south", "west"}:
        raise LayoutRenderError("没有这一面的机位")
    exe = blender_executable()
    payload = base64.b64encode(str(script or "").encode("utf-8")).decode("ascii")
    motion_b64 = base64.b64encode(clip.encode("utf-8")).decode("ascii")
    body = _BLENDER_TEMPLATE.format(script_b64=payload, view=chosen, motion_b64=motion_b64)
    with tempfile.TemporaryDirectory(prefix="aistory-clay-") as folder:
        script_path = os.path.join(folder, "white_model.py")
        with open(script_path, "w", encoding="utf-8") as handle:
            handle.write(body)
        try:
            completed = subprocess.run(
                [exe, "--background", "--python", script_path, "--", folder],
                capture_output=True,
                timeout=420 if clip else 180,
                check=False,
                env=blender_process_env(exe),
            )
        except subprocess.TimeoutExpired as exc:
            raise LayoutRenderError("白模渲染超时。") from exc
        if clip:
            if completed.returncode != 0:
                log = ((completed.stderr or b"") + b"\n" + (completed.stdout or b"")).decode("utf-8", "replace")
                tail = " ".join(line.strip() for line in log.splitlines() if line.strip())[-400:]
                raise LayoutRenderError(tail or "白模动画渲染失败。")
            fps = 8
            for line in clip.splitlines():
                if line.strip().upper().startswith("FPS"):
                    try:
                        fps = int(float(line.split("=", 1)[1]))
                    except ValueError:
                        fps = 8
            return _encode_line_video(folder, fps)
        if completed.returncode != 0:
            log = ((completed.stderr or b"") + b"\n" + (completed.stdout or b"")).decode("utf-8", "replace")
            tail = " ".join(line.strip() for line in log.splitlines() if line.strip())[-400:]
            raise LayoutRenderError(tail or "白模渲染失败。")
        if not chosen:
            return _composite_quad(folder)
        image_path = os.path.join(folder, chosen + ".png")
        if not os.path.isfile(image_path):
            raise LayoutRenderError("白模渲染失败。")
        frame = orientation_lines(Image.open(image_path).convert("RGB"))
        return _png_bytes(frame)


def _png_bytes(image: Image.Image) -> bytes:
    import io

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
