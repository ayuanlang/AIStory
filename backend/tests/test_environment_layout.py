# -*- coding: utf-8 -*-
import json

from app.services.script_analysis_flow.environment_layout import (
    LayoutError,
    _box_edges,
    _cameras,
    boxes_from_layout_payload,
    boxes_from_layout_script,
    extract_layout_script,
    layout_script_from_model_text,
    layout_script_gaps,
    layout_messages,
    parse_layout_boxes,
    parse_layout_model_text,
    project_point,
    render_layout_png,
    render_layout_sheet,
    supplement_layout_boxes,
)


OPENING = """
【六面一次】
场径=北4米｜东3.5米｜南4米｜西3.5米｜墙高=3.2米｜出入画口=大门
- 下=环氧地满铺｜距原点=北0米东0米｜尺度=南北8.0米×东西7.0米。
- 上=梁架天花｜距原点=北0米东0米｜高度=3.2米。吊灯号=#3｜半径=0.4米｜距原点=北0米东0米｜离平地=2.8米。
- [@会议桌]号=#4｜长边平行=Y线｜朝向=朝上｜距原点=北0米东0米｜占地=2.4×1.2米。[@主位转椅]号=#5｜朝向=南｜距原点=北1.9米东0米｜占地=0.6×0.6米。
【北壁】
抹灰墙号=#7｜壁关系=墙皮｜心点=正北｜距原点=北4米东0米｜占地=7.0×0.2米。百叶窗号=#8｜壁关系=窗洞｜距原点=北3.9米东0米｜占地=沿墙2.8米×高1.4米×厚0.08米｜开闭=全关。
【东壁】
混凝土墙号=#9｜壁关系=墙皮｜心点=正东｜距原点=北0米东3.5米｜占地=8.0×0.2米。
【南壁】
粉壁号=#11｜壁关系=墙皮｜心点=正南｜距原点=北-4米东0米｜占地=7.0×0.2米。大门号=#12｜壁关系=门洞｜距原点=北-3.9米东0米｜占地=沿墙1.1米×高2.1米×厚0.05米｜开闭=半开｜铰链端=东端。
【西壁】
涂料墙号=#13｜壁关系=墙皮｜心点=正西｜距原点=北0米东-3.5米｜占地=8.0×0.2米。
【光学说明】
焦段选择=偏35mm
"""


def _named(boxes, name):
    found = [box for box in boxes if box.name == name]
    assert found, name
    return found[0]


def test_opening_boxes_keep_locked_meters():
    boxes, meta = parse_layout_boxes(OPENING)
    table = _named(boxes, "会议桌")
    assert abs(table.cx) < 0.01 and abs(table.cy) < 0.01
    assert abs(table.sy - 2.4) < 0.01
    assert abs(table.sx - 1.2) < 0.01
    chair = _named(boxes, "主位转椅")
    assert chair.cy > table.cy
    assert abs(chair.sx - 0.6) < 0.01
    north = _named(boxes, "抹灰墙")
    assert north.kind == "wall" and north.cy > 0 and north.sx > north.sy
    east = _named(boxes, "混凝土墙")
    assert east.kind == "wall" and east.cx > 0 and east.sy > east.sx
    door = _named(boxes, "大门")
    assert door.kind == "door" and door.cy < 0 and door.extra
    lamp = _named(boxes, "吊灯")
    assert lamp.kind == "lamp" and lamp.cz > 2
    assert not any(box.name == "梁架天花" for box in boxes)
    assert meta["focal"] == 35
    assert meta["spans"][0] == 4


def test_box_edges_are_the_twelve_sides():
    boxes, _meta = parse_layout_boxes(OPENING)
    table = _named(boxes, "会议桌")
    edges = _box_edges(table)
    flat = [edge for edge in edges if abs(edge[0][2] - edge[1][2]) < 1e-6 and abs(edge[0][2] - (table.cz - table.sz / 2)) < 1e-6]
    assert len(edges) == 12
    assert any(abs(edge[0][0] - edge[1][0]) > 1 for edge in flat)


def test_look_north_puts_east_on_the_right():
    camera = (0.0, -3.2, 1.6)
    forward = (0.0, 1.0, 0.0)
    east = project_point((1.0, 0.0, 1.0), camera, forward, 400, (320, 180))
    west = project_point((-1.0, 0.0, 1.0), camera, forward, 400, (320, 180))
    assert east is not None and west is not None
    assert east[0] > west[0]
    behind = project_point((0.0, -4.0, 1.0), camera, forward, 400, (320, 180))
    assert behind is None


def test_sheet_is_one_png():
    binary, count = render_layout_png(OPENING)
    assert binary.startswith(b"\x89PNG")
    assert count >= 8
    from PIL import Image, ImageStat
    import io
    image = Image.open(io.BytesIO(binary)).convert("L")
    assert image.size == (1280, 720)
    assert ImageStat.Stat(image).mean[0] > 170
    assert image.getextrema()[1] > 220


def test_opening_without_meters_refuses():
    try:
        parse_layout_boxes("【四向拼图】\n左上望北。")
    except LayoutError as exc:
        assert "距原点" in str(exc)
    else:
        raise AssertionError("expected LayoutError")


INN_PAYLOAD = {
    "wall_h": 2.9,
    "focal_mm": 35,
    "span_north": 3.75,
    "span_east": 3.25,
    "span_south": 3.75,
    "span_west": 3.25,
    "boxes": [
        {
            "name": "红木八仙桌",
            "kind": "furniture",
            "east": 0,
            "north": 0,
            "along_east": 1.8,
            "along_north": 0.9,
            "height": 0.75,
            "bottom": 0,
        },
        {
            "name": "雕花木匾",
            "kind": "wall",
            "east": 0,
            "north": 3.73,
            "along_east": 1.2,
            "along_north": 0.04,
            "height": 0.45,
            "bottom": 2.25,
        },
        {
            "name": "直跑木梯",
            "kind": "wall",
            "east": 2.8,
            "north": 0,
            "along_east": 0.9,
            "along_north": 4.6,
            "height": 2.9,
            "bottom": 0,
            "low_east": 2.8,
            "low_north": -2.3,
            "high_east": 2.8,
            "high_north": 2.3,
            "low_z": 0,
            "high_z": 2.9,
        },
        {
            "name": "雕花房梁天井顶棚",
            "kind": "ceiling",
            "east": 0,
            "north": 0,
            "along_east": 6.5,
            "along_north": 7.5,
            "height": 0.08,
            "bottom": 2.9,
        },
    ],
}


def test_missing_height_names_the_piece_and_ramp_uses_its_ends():
    payload = {
        "wall_h": 2.9,
        "focal_mm": 35,
        "span_north": 3.75,
        "span_east": 3.25,
        "span_south": 3.75,
        "span_west": 3.25,
        "boxes": [
            {"kind": "floor", "north": 0, "east": 0, "along_east": 6.5, "along_north": 7.5, "bottom": 0, "height": 0.04},
            {"kind": "furniture", "north": 0, "east": 0, "along_east": 1.8, "along_north": 0.9, "bottom": 0, "height": None},
            {
                "kind": "ramp",
                "north": 0.8,
                "east": 3.15,
                "along_east": 0.2,
                "along_north": 2,
                "height": None,
                "bottom": None,
                "low_east": 3.15,
                "low_north": -0.2,
                "high_east": 3.15,
                "high_north": 1.8,
                "low_z": 0,
                "high_z": 2.9,
            },
        ],
    }
    try:
        boxes_from_layout_payload(payload)
    except LayoutError as exc:
        assert "第2件家具的高" in str(exc)
        assert "未名" not in str(exc)
    else:
        raise AssertionError("expected LayoutError")
    payload["boxes"][1]["height"] = 0.75
    boxes, _meta = boxes_from_layout_payload(payload)
    stair = _named(boxes, "第3件楼梯")
    assert stair.kind == "ramp" and abs(stair.sz - 2.9) < 0.01
    messages = layout_messages("【六面一次】\n距原点=北0米东0米｜占地=1.8米×0.9米×0.75米", "第2件家具的高")
    assert messages[1]["content"].startswith("以下是开篇原文")
    assert "占地=1.8米×0.9米×0.75米" in messages[1]["content"]
    assert "第2件家具的高" in messages[1]["content"]
    assert "上一份脚本：" not in messages[1]["content"]
    revised = layout_messages(
        "【六面一次】\n距原点=北0米东0米｜占地=1.8米×0.9米×0.75米",
        "白模渲染报错：ReferenceError",
        'FOCAL_MM = 35\nmass("案", "furniture", east=0, north=0, along_east=1.8, along_north=0.9, height=0.75, bottom=0)',
    )
    revised_user = revised[1]["content"]
    assert "白模渲染报错：ReferenceError" in revised_user
    assert "不新造米" in revised_user
    assert 'mass("案"' in revised_user


def test_model_payload_lifts_plaque_and_ramps_the_stair():
    wrapped = "读完开篇。\n```json\n" + json.dumps(INN_PAYLOAD, ensure_ascii=False) + "\n```"
    boxes, meta = boxes_from_layout_payload(parse_layout_model_text(wrapped))
    table = _named(boxes, "红木八仙桌")
    assert abs(table.sx - 1.8) < 0.01 and abs(table.sz - 0.75) < 0.01
    plaque = _named(boxes, "雕花木匾")
    assert abs((plaque.cz - plaque.sz / 2) - 2.25) < 0.01
    stair = _named(boxes, "直跑木梯")
    assert stair.kind == "ramp" and stair.ramp is not None
    heights = {round(point[2], 2) for edge in _box_edges(stair) for point in edge}
    assert 0.0 in heights and 2.9 in heights
    ceiling = _named(boxes, "雕花房梁天井顶棚")
    assert ceiling.kind == "ceiling" and ceiling.cz > 2.9
    west = next(camera for camera in _cameras(meta["spans"], meta["wall_h"], boxes) if camera[0] == "望西")
    assert west[1][0] < 2.27
    binary, count = render_layout_sheet(boxes, meta)
    assert binary.startswith(b"\x89PNG")
    assert count == 4


TENT_OPENING = """
【六面一次】
场径=北3.75米｜东3.25米｜南3.75米｜西3.25米｜墙高=2.9米｜焦段选择=偏35mm
下=帐内羊毛地毡地面满铺｜号=#1｜距原点=北0米东0米｜尺度=南北7.5米×东西6.5米。
上=穹顶毛毡帐顶｜号=#2｜高度=2.9米｜距原点=北0米东0米。
[@北狄王帐木台高位]号=#3｜长边平行=X线｜距原点=北0米东0米｜占地=1.8×0.9米。
[@角落木框矮凳]号=#4｜朝向=北｜距原点=北-2.9米东-2.0米｜占地=0.5×0.5米。
"""

TENT_PAYLOAD = {
    "wall_h": 2.9,
    "focal_mm": 35,
    "span_north": 3.75,
    "span_east": 3.25,
    "span_south": 3.75,
    "span_west": 3.25,
    "boxes": [
        {"name": "帐内羊毛地毡地面", "kind": "floor", "north": 0, "east": 0, "along_east": 6.5, "along_north": 7.5, "height": 0.04, "bottom": 0},
        {"name": "狼首云纹厚毡帐壁", "kind": "wall", "north": 3.75, "east": 0, "along_east": 6.5, "along_north": 0.2, "height": 2.9, "bottom": 0},
        {"name": "木骨墨渍厚毡帐壁", "kind": "wall", "north": 0, "east": 3.25, "along_east": 0.2, "along_north": 7.5, "height": 2.9, "bottom": 0},
        {"name": "纵缝墨渍厚毡帐壁", "kind": "wall", "north": -3.75, "east": 0, "along_east": 6.5, "along_north": 0.2, "height": 2.9, "bottom": 0},
        {"name": "木框厚毡帐门", "kind": "door", "north": -3.75, "east": 0, "along_east": 1, "along_north": 0.05, "height": 2.1, "bottom": 0},
        {"name": "木条水渍厚毡帐壁", "kind": "wall", "north": 0, "east": -3.25, "along_east": 0.2, "along_north": 7.5, "height": 2.9, "bottom": 0},
        {"name": "立架青铜油灯", "kind": "lamp", "north": 1, "east": 2.95, "along_east": 0.3, "along_north": 0.5, "height": 1.5, "bottom": 0},
    ],
}


def test_omitted_platform_stool_and_roof_are_filled_and_readable():
    boxes, meta = boxes_from_layout_payload(TENT_PAYLOAD)
    filled = supplement_layout_boxes(TENT_OPENING, boxes, meta)
    platform = _named(filled, "北狄王帐木台高位")
    assert platform.kind == "furniture"
    assert abs(platform.sx - 1.8) < 0.01 and abs(platform.sy - 0.9) < 0.01
    assert abs(platform.sz - 0.75) < 0.01
    stool = _named(filled, "角落木框矮凳")
    assert abs(stool.sx - 0.5) < 0.01 and abs(stool.sz - 0.45) < 0.01
    roof = _named(filled, "穹顶毛毡帐顶")
    assert roof.kind == "ceiling" and abs((roof.cz - roof.sz / 2) - 2.9) < 0.01
    binary, count = render_layout_sheet(filled, meta)
    assert count == 10
    from PIL import Image, ImageStat
    import io
    image = Image.open(io.BytesIO(binary)).convert("L")
    north = image.crop((0, 0, 640, 360))
    assert ImageStat.Stat(north).stddev[0] > 18


ROOM_SCRIPT = """
说明先丢掉。
```python
FOCAL_MM = 35
mass("地面", "floor", east=0, north=0, along_east=6, along_north=8, height=0.04, bottom=0)
mass("北墙", "wall", east=0, north=4, along_east=6, along_north=0.2, height=2.9, bottom=0)
mass("南墙", "wall", east=0, north=-4, along_east=6, along_north=0.2, height=2.9, bottom=0)
mass("门", "door", east=0, north=-4, along_east=1.0, along_north=0.05, height=2.1, bottom=0, state="全关")
mass("桌", "furniture", east=0, north=0, along_east=1.8, along_north=0.9, height=0.75, bottom=0)
```
"""


def test_model_script_keeps_only_mass_calls():
    script = extract_layout_script(ROOM_SCRIPT)
    assert script.startswith("FOCAL_MM")
    assert "说明" not in script
    boxes, meta = boxes_from_layout_script(script)
    assert meta["focal"] == 35
    table = _named(boxes, "桌")
    assert abs(table.sx - 1.8) < 0.01 and abs(table.sz - 0.75) < 0.01
    door = _named(boxes, "门")
    assert door.kind == "door"
    try:
        boxes_from_layout_script(extract_layout_script('mass("桌", "furniture", east=0, north=0)'))
    except LayoutError:
        pass
    else:
        raise AssertionError("expected LayoutError")


def test_box_json_becomes_a_blender_script():
    raw = """
    {"wall_h":2.9,"focal_mm":35,"span_north":3.75,"span_east":3.25,"span_south":3.75,"span_west":3.25,"boxes":[
    {"name":"穹顶毛毡帐顶","kind":"ceiling","north":0,"east":0,"along_east":6.5,"along_north":7.5,"bottom":2.9,"height":0.08},
    {"name":"北狄王帐木台高位","kind":"furniture","north":0,"east":0,"along_east":1.8,"along_north":0.9,"bottom":0,"height":0.75},
    {"name":"角落木框矮凳","kind":"furniture","north":-2.9,"east":-2,"along_east":0.5,"along_north":0.5,"bottom":0,"height":0.45},
    {"name":"木框厚毡帐门","kind":"door","north":-3.75,"east":0,"along_east":1,"along_north":0.05,"bottom":0,"height":2.1}
    ]}
    """
    script, boxes = layout_script_from_model_text(raw)
    assert script.startswith("FOCAL_MM = 35")
    assert 'mass("穹顶毛毡帐顶", "ceiling"' in script
    assert 'mass("北狄王帐木台高位", "furniture"' in script
    assert 'mass("角落木框矮凳", "furniture"' in script
    roof = _named(boxes, "穹顶毛毡帐顶")
    assert roof.kind == "ceiling" and abs((roof.cz - roof.sz / 2) - 2.9) < 0.01
    stool = _named(boxes, "角落木框矮凳")
    assert abs(stool.sz - 0.45) < 0.01
    again, _boxes = layout_script_from_model_text(script)
    assert again == script


GATE = """
城门号=#3｜壁关系=墙皮｜距原点=北2.0米东0米｜占地=沿墙无限制×高12.0米×厚2.0米。
单孔城门券洞号=#4｜壁关系=门洞｜距原点=北2.0米东0米｜占地=沿墙4.0米×高6.0米×厚2.0米｜开闭=全开。
下=墨色留白地面满铺｜距原点=北0米东0米｜尺度=南北无限制×东西无限制。
天空号=#9｜高度=无限制。
"""

DOOR_ONLY = '''开篇先丢掉。
FOCAL_MM = 24 mass("单孔城门券洞", "door", east=0, north=2, along_east=4, along_north=2, height=6, bottom=0, state="全开")
'''

GATE_SCRIPT = """
FOCAL_MM = 24
mass("地面", "floor", east=0, north=0, along_east=24, along_north=24, height=0.04, bottom=0)
mass("城门", "wall", east=0, north=2, along_east=24, along_north=2, height=12, bottom=0)
mass("单孔城门券洞", "door", east=0, north=2, along_east=4, along_north=2, height=6, bottom=0, state="全开")
"""


def test_unlimited_wall_stays_in_the_white_model_script():
    system = layout_messages(GATE)[0]["content"]
    assert "无限制的那一轴写 24" in system
    assert "写了门不能代替这面墙皮" in system
    assert "FOCAL_MM 和 mass 不能写在同一行" in system
    script = extract_layout_script(DOOR_ONLY)
    assert script.splitlines()[0] == "FOCAL_MM = 24"
    assert script.splitlines()[1].startswith("mass(")
    boxes, _meta = boxes_from_layout_script(script)
    gap = layout_script_gaps(GATE, boxes)
    assert "城门" in gap
    assert "地面" in gap
    assert "天空" not in gap
    full_boxes, _full_meta = boxes_from_layout_script(extract_layout_script(GATE_SCRIPT))
    assert layout_script_gaps(GATE, full_boxes) == ""
    wall = next(box for box in full_boxes if box.kind == "wall")
    assert abs(wall.sz - 12) < 0.01 and abs(wall.sy - 2) < 0.01


def test_blender_renders_four_grid_from_script():
    from app.services.script_analysis_flow.environment_layout_blender import (
        LayoutRenderError,
        blender_executable,
        render_white_model,
    )
    try:
        blender_executable()
    except LayoutRenderError:
        return
    binary = render_white_model(extract_layout_script(ROOM_SCRIPT))
    assert binary.startswith(b"\x89PNG")
    from PIL import Image, ImageStat
    import io
    image = Image.open(io.BytesIO(binary)).convert("RGB")
    assert image.size == (1280, 720)
    assert ImageStat.Stat(image.convert("L")).stddev[0] > 12
    center = image.getpixel((320, 180))
    assert sum(center) > 280, center
