# -*- coding: utf-8 -*-
import json

from app.services.script_analysis_flow.environment_layout import (
    LayoutError,
    _box_edges,
    _cameras,
    apply_facing,
    boxes_from_layout_payload,
    boxes_from_layout_script,
    extract_layout_script,
    facing_by_name,
    facing_tip,
    layout_messages,
    layout_script_from_model_text,
    layout_script_gaps,
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
    assert table.face == "上"
    assert chair.face == "南"
    assert north.face == ""
    tip = facing_tip(chair)
    assert tip is not None and tip[1] < chair.cy - chair.sy / 2
    top = facing_tip(table)
    assert top is not None and top[2] > table.cz + table.sz / 2
    assert facing_tip(north) is None


def test_facing_mark_follows_the_opening():
    assert facing_by_name("[@巨幕]号=#1｜屏面朝向=西｜距原点=北0米东2米。")["巨幕"] == "西"
    assert facing_by_name("[@石柱]号=#1｜朝向=无｜距原点=北1米东0米。")["石柱"] == ""
    assert facing_by_name("抹灰墙号=#7｜室内面朝向=南｜距原点=北4米东0米。")["抹灰墙"] == ""
    assert facing_by_name("[@控制台]号=#1｜朝向=朝上｜屏面朝向=北｜距原点=北0米东0米。")["控制台"] == "北"
    script = apply_facing(
        "\n".join([
            "FOCAL_MM = 35",
            'mass("会议桌", "furniture", east=0, north=0, along_east=1.2, along_north=2.4, height=0.75, bottom=0)',
            'mass("主位转椅", "furniture", east=0, north=1.9, along_east=0.6, along_north=0.6, height=0.9, bottom=0, face="东")',
            'mass("抹灰墙", "wall", east=0, north=4, along_east=7, along_north=0.2, height=3.2, bottom=0, face="南")',
        ]),
        OPENING,
    )
    boxes, _meta = boxes_from_layout_script(script)
    assert _named(boxes, "会议桌").face == "上"
    assert _named(boxes, "主位转椅").face == "南"
    assert _named(boxes, "抹灰墙").face == ""
    assert 'face="东"' not in script
    assert 'face="南"' in script
    assert "face=" in layout_messages(OPENING)[0]["content"]


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


def test_orientation_sheet_keeps_the_edge_and_drops_the_fill():
    from PIL import Image, ImageDraw

    from app.services.script_analysis_flow.environment_layout_blender import orientation_lines

    source = Image.new("RGB", (48, 48), (255, 255, 255))
    ImageDraw.Draw(source).rectangle((10, 12, 36, 34), fill=(20, 40, 60))
    sheet = orientation_lines(source)
    assert sheet.getpixel((1, 1)) == (255, 255, 255)
    assert sheet.getpixel((23, 23)) == (255, 255, 255)
    assert any(sheet.getpixel((x, 12))[0] < 40 for x in range(10, 37))


def test_white_model_keeps_opening_characters_and_props():
    from app.services.script_analysis_flow.environment_layout import (
        merge_occupant_script,
        occupant_mass_script,
    )
    from app.services.script_analysis_flow.environment_layout_job import white_model_groups

    text = """
【白模测算】
环境=客栈大堂｜原点=八仙桌｜东0北0
具=八仙桌｜东=0｜北=0｜底=0｜沿东=1.8｜沿北=0.9｜高=0.75
人=CHAR:[@甲]｜拍=开场｜东=0｜北=0.8｜底=0｜沿东=0.45｜沿北=0.25｜高=1.7｜罗盘朝向=南
件=PROP:[酒壶]｜拍=开场｜东=0.2｜北=0｜底=0.75｜沿东=0.2｜沿北=0.2｜高=0.2
人=CHAR:[@乙]｜拍=2｜东=1｜北=1｜底=0｜沿东=0.45｜沿北=0.25｜高=1.7
【/白模测算】
"""
    groups = white_model_groups(text)
    assert len(groups) == 1
    assert groups[0]["name"] == "客栈大堂"
    occupants = occupant_mass_script([*groups[0]["people"], *groups[0]["props"]])
    assert 'mass("CHAR:[@甲]", "person"' in occupants
    assert 'face="南"' in occupants
    assert 'mass("PROP:[酒壶]", "prop"' in occupants
    assert "CHAR:[@乙]" not in occupants
    user = layout_messages("【六面一次】\n距原点=北0米东0米", occupants=occupants)[1]["content"]
    assert "角色和道具必须各写一行" in user
    assert "CHAR:[@甲]" in user
    script = merge_occupant_script(
        'FOCAL_MM = 35\nmass("CHAR:[@甲]", "person", east=9, north=9, along_east=1, along_north=1, height=1, bottom=0)\nmass("八仙桌", "furniture", east=0, north=0, along_east=1.8, along_north=0.9, height=0.75, bottom=0)',
        occupants,
    )
    boxes, _meta = boxes_from_layout_script(script)
    person = next(box for box in boxes if box.kind == "person")
    prop = next(box for box in boxes if box.kind == "prop")
    assert person.name == "CHAR:[@甲]"
    assert abs(person.cy - 0.8) < 0.01
    assert person.face == "南"
    assert prop.name == "PROP:[酒壶]"
    assert abs(prop.cz - (0.75 + 0.2 / 2)) < 0.01


def test_scene_white_model_finds_framing_under_scene_number():
    from app.services.script_analysis_flow.environment_layout_job import framing_text_for_scene

    text = "【白模测算】\n环境=秘库｜原点=地面\n【/白模测算】"
    found = framing_text_for_scene({"SC02": {"framing": text}}, "EP01_SC02")
    assert "环境=秘库" in found
    from_block = framing_text_for_scene(
        {},
        "EP01_SC02",
        {"2": {"scene_block": text}},
    )
    assert "环境=秘库" in from_block
    assert framing_text_for_scene({"EP01_SC02A": {"framing": text}}, "EP01_SC02") == ""


def test_shot_motion_follows_the_locked_view():
    from app.services.script_analysis_flow.environment_layout import (
        animation_messages,
        animation_script_from_model_text,
        animation_skill_text,
        mass_motion_brief,
        missing_occupant_moves,
        shot_anim_seconds,
        shot_story_prompt,
    )

    story = shot_story_prompt(
        json.dumps({"video_prompt_cn": "(P1 0s–5s) 镜头离 CHAR:[@顾沉舟] 正前一条手臂。"}, ensure_ascii=False),
        "",
        "Beat-Shot映射:合镜Beat=Beat2+Beat3+Beat4｜Duration=15",
    )
    assert story.startswith("(P1 0s–5s)")
    assert shot_anim_seconds("6", "推近。") == 6
    assert shot_anim_seconds("", "末P止秒=12s") == 12
    assert shot_anim_seconds("15", "快门速度=1/96s｜P3(10s–15s)") == 15
    script = """
SECONDS = 4
FPS = 8
CAM t=0 view=east dolly=2 rise=0 pan=0
CAM t=0 view=north dolly=0 rise=0 pan=0
CAM t=4 view=north dolly=1 rise=0.2 pan=-10
MOVE "CHAR:[@甲]" t=0 east=0 north=-1
MOVE "墙" t=2 east=9 north=9
MOVE "CHAR:[@甲]" t=4 east=0.5 north=-0.2
"""
    motion = animation_script_from_model_text(
        script,
        view="north",
        names=["CHAR:[@甲]"],
        seconds=4,
    )
    assert "view=north" in motion
    assert "view=east" not in motion
    assert "dip=0" in motion
    assert 'MOVE "CHAR:[@甲]"' in motion
    assert "墙" not in motion
    brief = mass_motion_brief(
        'mass("重型保险台", "furniture", east=0, north=0, along_east=1.80, along_north=0.80, height=0.75, bottom=0)\n'
        'mass("CHAR:[@顾沉舟]", "person", east=0, north=-1.20, along_east=0.45, along_north=0.30, height=1.75, bottom=0)\n'
        'mass("北墙", "wall", east=0, north=3, along_east=6, along_north=0.20, height=2.90, bottom=0)\n'
    )
    assert "重型保险台｜东=0.00｜北=0.00" in brief
    assert "CHAR:[@顾沉舟]" in brief
    assert "北墙" not in brief
    dipped = animation_script_from_model_text(
        "CAM t=0 view=north dolly=0.70 rise=0 pan=0 dip=12\n"
        "CAM t=5 view=north dolly=1.00 rise=0 pan=0 dip=0\n",
        view="north",
        names=[],
        seconds=5,
    )
    assert "dip=12" in dipped
    assert "t=5.00 view=north" in dipped and "dip=0" in dipped
    skill = animation_skill_text()
    assert "每一个 `CHAR:`" in skill
    assert "插、拿、开、看不写 MOVE" not in skill
    flat = (
        "SECONDS = 15.00 FPS = 8 "
        "CAM t=0 view=north dolly=0.70 rise=0 pan=0 dip=12 "
        "CAM t=15 view=north dolly=0 rise=0 pan=0 dip=0 "
        "FOCAL t=0 mm=24 FOCAL t=15 mm=85 "
        "MOVE t=0 PROP:[最高权限令牌] 东=0.00 北=0.00 "
        "MOVE t=5 CHAR:[@顾沉舟] 东=0.00 北=0.20 "
        "MOVE t=5 PROP:[最高权限令牌] 东=0.00 北=-0.20"
    )
    kept = animation_script_from_model_text(
        flat,
        view="north",
        names=["CHAR:[@顾沉舟]", "PROP:[最高权限令牌]", "重型保险台"],
        seconds=15,
    )
    assert 'MOVE "CHAR:[@顾沉舟]" t=5.00 east=0.00 north=0.20' in kept
    assert 'MOVE "PROP:[最高权限令牌]" t=5.00 east=0.00 north=-0.20' in kept
    assert missing_occupant_moves(kept, ["CHAR:[@顾沉舟]", "PROP:[透明装甲手提箱_开态]"]) == "PROP:[透明装甲手提箱_开态]"
    messages = animation_messages("镜头推近。", 'mass("CHAR:[@甲]", "person", east=0, north=0, along_east=0.4, along_north=0.3, height=1.7, bottom=0)', "north", 15)
    assert messages[0]["content"] == skill
    assert "CHAR:[@甲]" in messages[1]["content"]
    assert "画面左是东减小" in messages[1]["content"]
    east_messages = animation_messages(
        "从画面右边走向画面左边。",
        'mass("CHAR:[@甲]", "person", east=0, north=0, along_east=0.4, along_north=0.3, height=1.7, bottom=0)',
        "east",
        5,
    )
    assert "画面左是北增大，画面右是北减小" in east_messages[1]["content"]
    from app.services.script_analysis_flow.environment_layout import boxes_from_layout_script, image_room_gaps
    glued = (
        "SECONDS = 15.00\nFPS = 8\n"
        "CAM t=0 view=north dolly=0.70 rise=0 pan=0 dip=0\n"
        "CAM t=15 view=north dolly=0 rise=0 pan=0 dip=0\n"
        "FOCAL t=5 mm=50FOCAL t=10 mm=50\n"
        "MOVE t=0CHAR:[@顾沉舟] 东=0.00 北=0.70\n"
        "MOVE t=0PROP:[透明装甲手提箱_开态] 东=0.00 北=0.00MOVE t=10 PROP:[透明装甲手提箱_开态] 东=0.00 北=-0.30\n"
    )
    parsed = animation_script_from_model_text(
        glued,
        view="north",
        names=["CHAR:[@顾沉舟]", "PROP:[透明装甲手提箱_开态]"],
        seconds=15,
    )
    assert 'MOVE "CHAR:[@顾沉舟]" t=0.00 east=0.00 north=0.70' in parsed
    assert 'MOVE "PROP:[透明装甲手提箱_开态]" t=10.00 east=0.00 north=-0.30' in parsed
    assert "FOCAL t=5.00 mm=50" in parsed and "FOCAL t=10.00 mm=50" in parsed
    people_only, _meta = boxes_from_layout_script(
        'mass("CHAR:[@顾沉舟]", "person", east=0, north=0.7, along_east=0.45, along_north=0.25, height=1.8, bottom=0)'
    )
    assert "缺地面和墙" in image_room_gaps(people_only)
    room, _meta = boxes_from_layout_script(
        'mass("地面", "floor", east=0, north=0, along_east=8, along_north=8, height=0.04, bottom=0)\n'
        'mass("北墙", "wall", east=0, north=4, along_east=8, along_north=0.2, height=3.2, bottom=0)'
    )
    assert image_room_gaps(room) == ""
    pictured = animation_messages(
        "镜头推近。",
        'mass("CHAR:[@甲]", "person", east=0, north=0, along_east=0.4, along_north=0.3, height=1.7, bottom=0)',
        "north",
        15,
        images=["https://example.com/north.png", "https://example.com/east.png"],
    )
    parts = pictured[1]["content"]
    assert parts[0]["type"] == "text" and "衍生环境" in parts[0]["text"]
    assert parts[1]["image_url"]["url"] == "https://example.com/north.png"
    assert parts[2]["image_url"]["url"] == "https://example.com/east.png"
    from app.services.script_analysis_flow.environment_layout import layout_messages
    sheet = layout_messages("", images=["https://example.com/north.png"])
    body = sheet[1]["content"][0]["text"]
    assert "不要开篇" in body
    assert "开篇原文" not in body
    assert body.index("不要开篇") < 80


def test_storyboard_stand_overrides_the_model_move():
    from app.services.script_analysis_flow.environment_layout import (
        animation_script_from_model_text,
        apply_prompt_room,
        lock_shot_motion,
    )

    room = """
FOCAL_MM = 35
mass("地面", "floor", east=0, north=0, along_east=8, along_north=8, height=0.04, bottom=0)
mass("金属大门", "door", east=0, north=4, along_east=2.2, along_north=0.2, height=2.2, bottom=0, state="全关")
mass("金属台", "furniture", east=0, north=-0.5, along_east=2.4, along_north=1.2, height=0.85, bottom=0, face="南")
mass("CHAR:[@顾沉舟]", "person", east=0, north=-2, along_east=0.45, along_north=0.25, height=1.8, bottom=0)
mass("PROP:[最高权限令牌]", "prop", east=0, north=-2, along_east=0.1, along_north=0.05, height=0.15, bottom=1.1)
"""
    prompt = (
        "镜头在重型保险台靠近镜头的这一边，离 CHAR:[@顾沉舟] 正前三步。"
        "CHAR:[@顾沉舟] 站在防爆重型金属门靠近镜头的这一侧的位置，更靠近镜头一条手臂，"
        "在这扇防爆重型金属门的左右正中，站着。左手拿着 PROP:[最高权限令牌]。"
        "防爆重型金属门开拍半开。"
        "从靠近镜头向远离镜头走，脚步停在重型保险台远离镜头的那一侧的位置，更远离镜头一条手臂，"
        "在这张重型保险台的左右正中，站着。"
    )
    patched = apply_prompt_room(room, prompt)
    assert 'mass("金属大门"' in patched and 'state="半开"' in patched
    assert 'state="全关"' not in patched
    raw = """
SECONDS = 5.00
CAM t=0 view=north dolly=0 rise=0 pan=0 dip=0
CAM t=5 view=north dolly=0.70 rise=0 pan=0 dip=0
FOCAL t=0 mm=50
FOCAL t=5 mm=50
MOVE t=0 CHAR:[@顾沉舟] 东=0.00 北=-2.00
MOVE t=5 CHAR:[@顾沉舟] 东=0.00 北=0.80
MOVE t=0 PROP:[最高权限令牌] 东=0.00 北=-2.00
MOVE t=5 PROP:[最高权限令牌] 东=0.00 北=0.80
"""
    parsed = animation_script_from_model_text(
        raw,
        view="north",
        names=["CHAR:[@顾沉舟]", "PROP:[最高权限令牌]"],
        seconds=5,
    )
    locked = lock_shot_motion(parsed, patched, prompt, "north")
    assert 'MOVE "CHAR:[@顾沉舟]" t=0.00 east=0.00 north=3.20' in locked
    assert 'MOVE "CHAR:[@顾沉舟]" t=5.00 east=0.00 north=0.80' in locked
    assert 'MOVE "PROP:[最高权限令牌]" t=0.00 east=0.36 north=3.20' in locked
    assert 'MOVE "PROP:[最高权限令牌]" t=5.00 east=0.36 north=0.80' in locked
    assert "dolly=-0.80" in locked
    assert "dolly=-0.10" in locked


def test_derived_view_image_uses_the_matching_cell():
    from app.services.script_analysis_flow.environment_layout_job import _quad_cell_url

    class Row:
        custom_attributes = {
            "quad_cell_images": {
                "cells": {
                    "左上": {"url": "https://cdn.example/north.png"},
                    "右上": "https://cdn.example/east.png",
                }
            }
        }

    assert _quad_cell_url(Row(), 0) == "https://cdn.example/north.png"
    assert _quad_cell_url(Row(), 90) == "https://cdn.example/east.png"
    assert _quad_cell_url(Row(), 180) == ""


def test_shot_white_model_uses_named_derived_views():
    from app.services.script_analysis_flow.environment_layout_job import shot_derived_targets

    hint = "背景参考图 ENV:[0度客栈大堂] 之后切到 ENV:[180度客栈大堂_破损]，主环境 ENV:[客栈大堂] 不单独出图。"
    targets = shot_derived_targets(hint)
    assert [(item["name"], item["view"], item["main"]) for item in targets] == [
        ("0度客栈大堂", "north", "客栈大堂"),
        ("180度客栈大堂_破损", "south", "客栈大堂"),
    ]


def test_shot_white_model_uses_that_beat_pose():
    from app.services.script_analysis_flow.environment_layout import occupant_mass_script
    from app.services.script_analysis_flow.environment_layout_job import shot_pose_boxes

    text = """
【白模测算】
环境=客栈大堂｜原点=八仙桌｜东0北0
具=八仙桌｜东=0｜北=0｜底=0｜沿东=1.8｜沿北=0.9｜高=0.75
人=CHAR:[@甲]｜拍=开场｜东=0｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.7
【/白模测算】
[BEAT_START:1]
人=CHAR:[@甲]｜拍=1｜东=1.2｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.7
件=PROP:[酒壶]｜拍=1｜东=0.2｜北=0｜底=0.75｜沿东=0.2｜沿北=0.2｜高=0.2
镜=B1｜东=0｜北=-2｜高=1.6｜望=北｜景别=MS｜视场=47
[BEAT_END:1]
"""
    pose = shot_pose_boxes(text, [1])
    assert pose["beat"] == "1"
    script = occupant_mass_script([*pose["people"], *pose["props"]])
    assert 'mass("CHAR:[@甲]", "person", east=1.2' in script
    assert 'mass("PROP:[酒壶]", "prop"' in script
    opening = shot_pose_boxes(text, [])
    assert opening["beat"] == "开场"
    assert occupant_mass_script(opening["people"]).count("east=0") >= 1


def test_blender_process_env_prefers_tree_lib(tmp_path):
    import os

    from app.services.script_analysis_flow.environment_layout_blender import blender_process_env

    lib = tmp_path / "lib"
    lib.mkdir()
    exe = tmp_path / "blender"
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    env = blender_process_env(str(exe))
    assert env["LD_LIBRARY_PATH"].split(os.pathsep)[0] == str(lib)


def test_long_lens_keeps_a_person_edge_when_they_step_closer():
    import os
    import subprocess
    import tempfile

    from PIL import Image

    from app.services.script_analysis_flow.environment_layout_blender import (
        LayoutRenderError,
        blender_executable,
        render_white_model,
    )
    try:
        blender_executable()
    except LayoutRenderError:
        return
    script = "\n".join([
        "FOCAL_MM = 35",
        'mass("地面", "floor", 0, 0, 8, 8, 0.1, 0)',
        'mass("北墙", "wall", 0, 4, 8, 0.2, 3, 0)',
        'mass("南墙", "wall", 0, -4, 8, 0.2, 3, 0)',
        'mass("东墙", "wall", 4, 0, 0.2, 8, 3, 0)',
        'mass("西墙", "wall", -4, 0, 0.2, 8, 3, 0)',
        'mass("台", "furniture", 0, -0.5, 2.0, 1.2, 1.0, 0)',
        'mass("CHAR:[@人]", "person", 0, 0.70, 0.45, 0.25, 1.80, 0, face="南")',
    ])
    motion = "\n".join([
        "SECONDS = 2.00",
        "FPS = 8",
        "CAM t=0 view=north dolly=0.70 rise=0 pan=0 dip=0",
        "CAM t=2 view=north dolly=1.00 rise=0 pan=0 dip=0",
        "FOCAL t=0 mm=85",
        "FOCAL t=2 mm=85",
        'MOVE "CHAR:[@人]" t=0.00 east=0.00 north=0.70',
        'MOVE "CHAR:[@人]" t=2.00 east=0.00 north=0.20',
    ])
    binary = render_white_model(script, view="north", motion=motion)
    import imageio_ffmpeg
    folder = tempfile.mkdtemp()
    path = os.path.join(folder, "clip.mp4")
    with open(path, "wb") as handle:
        handle.write(binary)
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([exe, "-y", "-i", path, os.path.join(folder, "f_%04d.png")], check=True, capture_output=True)
    frames = sorted(name for name in os.listdir(folder) if name.startswith("f_"))
    assert len(frames) >= 8
    for name in frames:
        gray = Image.open(os.path.join(folder, name)).convert("L")
        dark = sum(gray.histogram()[:80])
        assert dark > 400, name


def test_long_lens_keeps_the_prop_with_the_person():
    import os
    import subprocess
    import tempfile

    from PIL import Image

    from app.services.script_analysis_flow.environment_layout_blender import (
        LayoutRenderError,
        blender_executable,
        render_white_model,
    )
    try:
        blender_executable()
    except LayoutRenderError:
        return
    script = "\n".join([
        "FOCAL_MM = 35",
        'mass("地面", "floor", 0, 0, 8, 8, 0.04, 0)',
        'mass("北墙", "wall", 0, 4, 8, 0.2, 3.2, 0)',
        'mass("南墙", "wall", 0, -4, 8, 0.2, 3.2, 0)',
        'mass("东墙", "wall", 4, 0, 0.2, 8, 3.2, 0)',
        'mass("西墙", "wall", -4, 0, 0.2, 8, 3.2, 0)',
        'mass("主控台", "furniture", 0, 1.5, 2.2, 0.9, 0.75, 0)',
        'mass("CHAR:[@顾沉舟]", "person", 0, 0.7, 0.45, 0.25, 1.8, 0)',
        'mass("PROP:[透明装甲手提箱_开态]", "prop", 0, 0.0, 0.4, 0.3, 0.2, 0.75)',
    ])
    motion = "\n".join([
        "SECONDS = 2.00",
        "FPS = 8",
        "CAM t=0 view=north dolly=0.70 rise=0 pan=0 dip=0",
        "CAM t=2 view=north dolly=0 rise=0 pan=0 dip=12",
        "FOCAL t=0 mm=85",
        "FOCAL t=2 mm=85",
        'MOVE "CHAR:[@顾沉舟]" t=0.00 east=0.00 north=0.70',
        'MOVE "CHAR:[@顾沉舟]" t=2.00 east=0.00 north=0.70',
        'MOVE "PROP:[透明装甲手提箱_开态]" t=0.00 east=0.00 north=0.00',
        'MOVE "PROP:[透明装甲手提箱_开态]" t=2.00 east=0.00 north=-0.40',
    ])
    binary = render_white_model(script, view="north", motion=motion)
    import imageio_ffmpeg
    folder = tempfile.mkdtemp()
    path = os.path.join(folder, "clip.mp4")
    with open(path, "wb") as handle:
        handle.write(binary)
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([exe, "-y", "-i", path, os.path.join(folder, "f_%04d.png")], check=True, capture_output=True)
    frames = sorted(name for name in os.listdir(folder) if name.startswith("f_"))
    assert len(frames) >= 8

    def bands(name):
        image = Image.open(os.path.join(folder, name)).convert("L")
        width, height = image.size
        pixels = list(image.getdata())
        lower = height * 2 // 3
        bottom = sum(1 for index, value in enumerate(pixels) if value < 80 and index // width >= lower)
        return bottom, width, height

    start_bottom, _width, _height = bands(frames[0])
    end_bottom, _width, _height = bands(frames[-1])
    assert start_bottom > 80
    assert end_bottom > 80
    assert abs(start_bottom - end_bottom) > 20


def test_east_two_shot_keeps_both_people_while_one_walks():
    import os
    import subprocess
    import tempfile

    from PIL import Image

    from app.services.script_analysis_flow.environment_layout_blender import (
        LayoutRenderError,
        blender_executable,
        render_white_model,
    )
    try:
        blender_executable()
    except LayoutRenderError:
        return
    script = "\n".join([
        "FOCAL_MM = 35",
        'mass("地面", "floor", 0, 0, 10, 8, 0.04, 0)',
        'mass("南墙", "wall", 0, -4, 10, 0.25, 3.2, 0)',
        'mass("北墙", "wall", 0, 4, 10, 0.25, 3.2, 0)',
        'mass("东墙", "wall", 5, 0, 0.25, 8, 3.2, 0)',
        'mass("西墙", "wall", -5, 0, 0.25, 8, 3.2, 0)',
        'mass("中央金属台", "furniture", 0, 0, 2.6, 1.7, 0.75, 0)',
        'mass("CHAR:[@顾沉舟]", "person", 0, 0.70, 0.45, 0.25, 1.8, 0)',
        'mass("CHAR:[@沈清璃]", "person", 0, -1.80, 0.45, 0.25, 1.7, 0)',
    ])
    motion = "\n".join([
        "SECONDS = 5.00",
        "FPS = 8",
        "CAM t=0 view=east dolly=0 rise=0 pan=0 dip=0",
        "CAM t=5 view=east dolly=0 rise=0 pan=0 dip=0",
        "FOCAL t=0 mm=24",
        "FOCAL t=5 mm=24",
        'MOVE "CHAR:[@顾沉舟]" t=0.00 east=0.00 north=0.70',
        'MOVE "CHAR:[@顾沉舟]" t=5.00 east=0.00 north=0.70',
        'MOVE "CHAR:[@沈清璃]" t=0.00 east=0.00 north=-1.80',
        'MOVE "CHAR:[@沈清璃]" t=5.00 east=0.00 north=-0.80',
    ])
    binary = render_white_model(script, view="east", motion=motion)
    import imageio_ffmpeg
    folder = tempfile.mkdtemp()
    path = os.path.join(folder, "clip.mp4")
    with open(path, "wb") as handle:
        handle.write(binary)
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([exe, "-y", "-i", path, os.path.join(folder, "f_%04d.png")], check=True, capture_output=True)
    frames = sorted(name for name in os.listdir(folder) if name.startswith("f_"))
    assert len(frames) >= 16

    def dark_map(name):
        image = Image.open(os.path.join(folder, name)).convert("L")
        width, height = image.size
        pixels = list(image.getdata())
        third = width // 3
        left = sum(1 for index, value in enumerate(pixels) if value < 80 and index % width < third)
        right = sum(1 for index, value in enumerate(pixels) if value < 80 and index % width >= width - third)
        return left, right, pixels

    start_left, start_right, start_pixels = dark_map(frames[0])
    end_left, end_right, end_pixels = dark_map(frames[-1])
    assert start_left > 80 and start_right > 80
    assert end_left > 80 and end_right > 80
    changed = sum(1 for a, b in zip(start_pixels, end_pixels) if abs(a - b) > 30)
    assert changed > 400


def test_blender_renders_a_four_view_sheet_from_script():
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
    corner = image.getpixel((4, 4))
    assert sum(corner) > 700, corner
    gray = image.convert("L")
    divider = [gray.getpixel((640, y)) for y in range(0, 720, 24)]
    assert sum(divider) / len(divider) < 160


GATE_FACE_SCRIPT = "\n".join([
    "FOCAL_MM = 35",
    'mass("据点混凝土地面", "floor", east=0, north=0, along_east=6.5, along_north=7.5, height=0.04, bottom=0)',
    'mass("工业防爆吊灯所在天花", "ceiling", east=0, north=0, along_east=6.5, along_north=7.5, height=0.08, bottom=2.9)',
    'mass("加固闸门", "door", east=0, north=3.75, along_east=6.5, along_north=0.2, height=2.9, bottom=0)',
    'mass("粗粝工业墙皮", "wall", east=3.25, north=0, along_east=0.2, along_north=7.5, height=2.9, bottom=0)',
    'mass("工业立面墙皮", "wall", east=0, north=-3.75, along_east=6.5, along_north=0.2, height=2.9, bottom=0)',
    'mass("加固结构墙皮", "wall", east=-3.25, north=0, along_east=0.2, along_north=7.5, height=2.9, bottom=0)',
])


def test_full_face_gate_does_not_blank_the_facing_view():
    from app.services.script_analysis_flow.environment_layout_blender import (
        LayoutRenderError,
        blender_executable,
        render_white_model,
    )
    try:
        blender_executable()
    except LayoutRenderError:
        return
    binary = render_white_model(GATE_FACE_SCRIPT)
    from PIL import Image
    import io
    gray = Image.open(io.BytesIO(binary)).convert("L")
    assert gray.size == (1280, 720)

    def dark(box):
        return sum(1 for value in gray.crop(box).getdata() if value < 80)

    north = dark((16, 16, 624, 344))
    east = dark((656, 16, 1264, 344))
    south = dark((16, 376, 624, 704))
    west = dark((656, 376, 1264, 704))
    assert min(north, east, south, west) > 200, (north, east, south, west)
