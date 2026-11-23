"""Visible range is measured from the white model before staging."""

from app.services.script_analysis_flow.framing_visibility import (
    prepend_visibility_range,
    visible_range_block,
)
from app.services.scene_subskill_pipeline_runner import staging_scene_with_visibility


def _office(*people: str, extra: str = "", beat: str = "") -> str:
    body = "\n".join(people)
    return f"""【白模测算】
环境=总裁办公室｜原点=办公桌｜东0北0
具=办公桌｜东=0｜北=0｜底=0｜沿东=1.8｜沿北=0.9｜高=0.75｜朝向=朝上｜关系=留空｜透=不透
{extra}
人=CHAR:[@甲]｜拍=开场｜东=0｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60
人=CHAR:[@乙]｜拍=开场｜东=0｜北=-2.0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60
人=CHAR:[@丙]｜拍=开场｜东=3.0｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60
[BEAT_START:1]
拍法=正面｜主拍对象=CHAR:[@甲]｜景别=MS｜望=北｜机位距=两步
镜=B1｜东=0｜北=-1.4｜高=1.6｜望=北｜景别=MS｜视场=47
{body}
{beat}
[BEAT_END:1]
"""


def _line(block: str) -> str:
    return next(line for line in block.splitlines() if line.startswith("B1｜"))


def test_front_subject_is_visible_and_rear_subject_is_behind_camera():
    block = visible_range_block(
        _office(
            "人=CHAR:[@甲]｜拍=1｜东=0｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60",
            "人=CHAR:[@乙]｜拍=1｜东=0｜北=-2.0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60",
            "人=CHAR:[@丙]｜拍=1｜东=3.0｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60",
        ),
        use_blender=False,
    )
    line = _line(block)
    assert "来源=测算" in block
    assert "可见=CHAR:[@甲]" in line
    assert "镜后=CHAR:[@乙]" in line
    assert "CHAR:[@丙]" in line.split("景别外=", 1)[1].split("｜", 1)[0]


def test_opaque_box_between_camera_and_eye_blocks():
    block = visible_range_block(
        _office(
            "人=CHAR:[@甲]｜拍=1｜东=0｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60",
            extra="具=隔断｜东=0｜北=-0.4｜底=0｜沿东=2.0｜沿北=0.2｜高=2.0｜关系=贴上｜透=不透",
        ),
        use_blender=False,
    )
    assert "遮挡=CHAR:[@甲]<隔断>" in _line(block)


def test_blender_measures_the_same_block():
    framing = _office(
        "人=CHAR:[@甲]｜拍=1｜东=0｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60",
        extra="具=隔断｜东=0｜北=-0.4｜底=0｜沿东=2.0｜沿北=0.2｜高=2.0｜关系=贴上｜透=不透",
    )
    block = visible_range_block(framing, use_blender=True)
    assert "来源=Blender" in block or "来源=测算" in block
    assert "遮挡=CHAR:[@甲]<隔断>" in _line(block)


def test_transparent_sheet_does_not_block():
    block = visible_range_block(
        _office(
            "人=CHAR:[@甲]｜拍=1｜东=0｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60",
            extra="具=纱帘｜东=0｜北=-0.4｜底=0｜沿东=2.0｜沿北=0.2｜高=2.0｜关系=贴上｜透=透",
        ),
        use_blender=False,
    )
    assert "可见=CHAR:[@甲]" in _line(block)
    assert "遮挡=无" in _line(block)


def test_a_clipped_box_corner_does_not_keep_the_person():
    block = visible_range_block(
        _office(
            "人=CHAR:[@甲]｜拍=1｜东=0｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60",
            "人=CHAR:[@乙]｜拍=1｜东=0.35｜北=-0.6｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60",
            beat="拍法=过肩｜框主=CHAR:[@乙]｜主拍对象=CHAR:[@甲]｜景别=CU｜望=北｜机位距=贴身",
        ),
        use_blender=False,
    )
    line = _line(block)
    assert "CHAR:[@甲]{头,胸}" in line
    assert "CHAR:[@乙]" in line.split("景别外=", 1)[1]


def test_transparent_shell_does_not_block():
    block = visible_range_block(
        _office(
            "人=CHAR:[@甲]｜拍=1｜东=0｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60",
            extra="具=展示罩｜东=0｜北=-0.4｜底=0｜沿东=2.0｜沿北=0.2｜高=2.0｜关系=贴上｜壳=透视｜透=不透",
        ),
        use_blender=False,
    )
    assert "可见=CHAR:[@甲]" in _line(block)
    assert "遮挡=无" in _line(block)


def test_person_inside_the_cone_stays_on_a_close_shot():
    block = visible_range_block(
        _office(
            "人=CHAR:[@甲]｜拍=1｜东=0｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60",
            "人=CHAR:[@丁]｜拍=1｜东=0.3｜北=0.2｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60",
            beat="景别=CU｜望=北｜主拍对象=CHAR:[@甲]",
        ),
        use_blender=False,
    )
    line = _line(block)
    assert "景别=CU" in line
    assert "视场=47" in line
    assert "CHAR:[@甲]" in line.split("可见=", 1)[1].split("｜", 1)[0]
    assert "CHAR:[@丁]" in line.split("可见=", 1)[1].split("｜", 1)[0]


def test_person_outside_a_tight_field_is_out():
    text = """【白模测算】
人=CHAR:[@甲]｜拍=开场｜东=0｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60
人=CHAR:[@丁]｜拍=开场｜东=0.8｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60
[BEAT_START:1]
拍法=正面｜主拍对象=CHAR:[@甲]｜景别=ECU｜望=北｜机位距=贴身
镜=B1｜望=北｜景别=ECU
[BEAT_END:1]
"""
    block = visible_range_block(text, use_blender=False)
    line = _line(block)
    assert "视场=18" in line
    assert "可见=CHAR:[@甲]" in line
    assert "CHAR:[@丁]" in line.split("景别外=", 1)[1]


def test_medium_close_shot_uses_the_wide_field():
    text = """【白模测算】
人=CHAR:[@甲]｜拍=开场｜东=0｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60
人=CHAR:[@丁]｜拍=开场｜东=0.5｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60
[BEAT_START:1]
拍法=正面｜主拍对象=CHAR:[@甲]｜景别=MCU｜望=北｜机位距=一臂
镜=B1｜望=北｜景别=MCU
[BEAT_END:1]
"""
    block = visible_range_block(text, use_blender=False)
    line = _line(block)
    assert "视场=84" in line
    assert "机位=东0.0北-0.7高1.6" in line
    assert "CHAR:[@丁]" in line.split("可见=", 1)[1].split("｜", 1)[0]


def test_tight_field_keeps_only_the_head():
    text = """【白模测算】
人=CHAR:[@甲]｜拍=开场｜东=0｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60
[BEAT_START:1]
拍法=正面｜主拍对象=CHAR:[@甲]｜景别=ECU｜望=北｜机位距=贴身
镜=B1｜望=北｜景别=ECU
[BEAT_END:1]
"""
    line = _line(visible_range_block(text, use_blender=False))
    assert "CHAR:[@甲]{头}" in line
    assert "{头,胸" not in line


def test_counter_blocks_the_legs_and_leaves_the_upper_body():
    text = """【白模测算】
具=柜台｜东=0｜北=-0.5｜底=0｜沿东=1.8｜沿北=0.4｜高=1.20｜关系=贴上｜透=不透
人=CHAR:[@甲]｜拍=开场｜东=0｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60
[BEAT_START:1]
拍法=正面｜主拍对象=CHAR:[@甲]｜景别=FS｜望=北｜机位距=三步
镜=B1｜东=0｜北=-2.2｜高=1.6｜望=北｜景别=FS｜视场=84
[BEAT_END:1]
"""
    line = _line(visible_range_block(text, use_blender=False))
    shown = line.split("可见=", 1)[1].split("｜", 1)[0]
    assert "CHAR:[@甲]{头,胸}" in shown
    assert "腰" not in shown.split("CHAR:[@甲]{", 1)[1].split("}", 1)[0]
    assert "腿" not in shown.split("CHAR:[@甲]{", 1)[1].split("}", 1)[0]
    assert "遮挡=无" in line


def _brace(line: str, name: str = "甲") -> str:
    shown = line.split("可见=", 1)[1].split("｜", 1)[0]
    token = f"CHAR:[@{name}]{{"
    if token not in shown:
        return ""
    return shown.split(token, 1)[1].split("}", 1)[0]


def _wide(person: str, furniture: str) -> str:
    return f"""【白模测算】
{furniture}
{person}
[BEAT_START:1]
拍法=正面｜主拍对象=CHAR:[@甲]｜景别=FS｜望=北｜机位距=三步
镜=B1｜东=0｜北=-2.2｜高=1.6｜望=北｜景别=FS｜视场=84
[BEAT_END:1]
"""


def test_table_hides_an_adults_legs_and_leaves_the_waist():
    line = _line(visible_range_block(_wide(
        "人=CHAR:[@甲]｜拍=开场｜东=0｜北=0.4｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60｜体格=成人",
        "具=餐桌｜东=0｜北=-0.3｜底=0｜沿东=1.6｜沿北=0.8｜高=0.75｜关系=留空｜透=不透",
    ), use_blender=False))
    assert _brace(line) == "头,胸,腰"


def test_table_hides_a_childs_waist_and_a_smaller_childs_chest():
    school = _line(visible_range_block(_wide(
        "人=CHAR:[@甲]｜拍=开场｜东=0｜北=0.4｜底=0｜沿东=0.35｜沿北=0.20｜高=1.15｜眼高=1.05｜体格=小孩",
        "具=餐桌｜东=0｜北=-0.3｜底=0｜沿东=1.6｜沿北=0.8｜高=0.75｜关系=留空｜透=不透",
    ).replace("高=1.6", "高=1.05"), use_blender=False))
    assert _brace(school) == "头,胸"
    small = _line(visible_range_block(_wide(
        "人=CHAR:[@甲]｜拍=开场｜东=0｜北=0.4｜底=0｜沿东=0.30｜沿北=0.18｜高=0.95｜眼高=0.85｜体格=小孩",
        "具=餐桌｜东=0｜北=-0.3｜底=0｜沿东=1.6｜沿北=0.8｜高=0.75｜关系=留空｜透=不透",
    ).replace("高=1.6", "高=0.85"), use_blender=False))
    assert _brace(small) == "头"


def test_chair_back_hides_an_adults_legs_and_a_childs_chest():
    adult = _line(visible_range_block(_wide(
        "人=CHAR:[@甲]｜拍=开场｜东=0｜北=0.4｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60｜体格=成人",
        "具=餐椅｜东=0｜北=-0.5｜底=0｜沿东=0.5｜沿北=0.5｜高=0.90｜关系=留空｜透=不透",
    ), use_blender=False))
    assert _brace(adult) == "头,胸,腰"
    child = _line(visible_range_block(_wide(
        "人=CHAR:[@甲]｜拍=开场｜东=0｜北=0.4｜底=0｜沿东=0.35｜沿北=0.20｜高=1.15｜眼高=1.05｜体格=小孩",
        "具=餐椅｜东=0｜北=-0.5｜底=0｜沿东=0.5｜沿北=0.5｜高=0.90｜关系=留空｜透=不透",
    ).replace("高=1.6", "高=1.05"), use_blender=False))
    assert _brace(child) == "头"


def test_a_shorter_child_is_hidden_behind_the_chair_back():
    line = _line(visible_range_block(_wide(
        "人=CHAR:[@甲]｜拍=开场｜东=0｜北=0.4｜底=0｜沿东=0.30｜沿北=0.18｜高=0.85｜眼高=0.75｜体格=小孩",
        "具=餐椅｜东=0｜北=-0.5｜底=0｜沿东=0.5｜沿北=0.5｜高=0.90｜关系=留空｜透=不透",
    ).replace("高=1.6", "高=0.75"), use_blender=False))
    assert "遮挡=CHAR:[@甲]<餐椅>" in line


def test_bed_hides_only_the_standing_adults_legs():
    line = _line(visible_range_block(_wide(
        "人=CHAR:[@甲]｜拍=开场｜东=0｜北=0.6｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60｜体格=成人",
        "具=木床｜东=0｜北=-0.4｜底=0｜沿东=1.2｜沿北=2.0｜高=0.55｜关系=留空｜透=不透",
    ), use_blender=False))
    assert _brace(line) == "头,胸,腰"


def test_sofa_back_hides_a_standing_child_down_to_the_head():
    line = _line(visible_range_block(_wide(
        "人=CHAR:[@甲]｜拍=开场｜东=0｜北=0.8｜底=0｜沿东=0.35｜沿北=0.20｜高=1.15｜眼高=1.05｜体格=小孩",
        "具=沙发｜东=0｜北=-0.2｜底=0｜沿东=1.8｜沿北=0.9｜高=0.90｜关系=留空｜透=不透",
    ).replace("高=1.6", "高=1.05"), use_blender=False))
    assert _brace(line) == "头"


def test_the_seat_does_not_hide_the_person_sitting_on_it():
    text = """【白模测算】
具=餐椅｜东=0｜北=0｜底=0｜沿东=0.5｜沿北=0.5｜高=0.90｜关系=留空｜透=不透
人=CHAR:[@甲]｜拍=开场｜东=0｜北=0｜底=0.45｜沿东=0.45｜沿北=0.25｜高=1.25｜眼高=1.15｜体格=成人
[BEAT_START:1]
拍法=正面｜主拍对象=CHAR:[@甲]｜景别=MS｜望=北｜机位距=两步
镜=B1｜东=0｜北=-1.4｜高=1.15｜望=北｜景别=MS｜视场=47
[BEAT_END:1]
"""
    line = _line(visible_range_block(text, use_blender=False))
    assert "头" in _brace(line)
    assert "遮挡=无" in line or "遮挡=CHAR:[@甲]" not in line


def test_a_table_hides_a_seated_adults_lap_and_a_seated_childs_chest():
    adult = _line(visible_range_block(_wide(
        "人=CHAR:[@甲]｜拍=开场｜东=0｜北=0.5｜底=0.45｜沿东=0.45｜沿北=0.25｜高=1.25｜眼高=1.15｜体格=成人",
        "具=餐桌｜东=0｜北=-0.2｜底=0｜沿东=1.6｜沿北=0.9｜高=0.75｜关系=留空｜透=不透",
    ).replace("高=1.6", "高=1.15"), use_blender=False))
    assert _brace(adult) == "头,胸"
    child = _line(visible_range_block(_wide(
        "人=CHAR:[@甲]｜拍=开场｜东=0｜北=0.5｜底=0.45｜沿东=0.35｜沿北=0.20｜高=0.85｜眼高=0.78｜体格=小孩",
        "具=餐桌｜东=0｜北=-0.2｜底=0｜沿东=1.6｜沿北=0.9｜高=0.75｜关系=留空｜透=不透",
    ).replace("高=1.6", "高=0.78"), use_blender=False))
    assert _brace(child) == "头"


def test_someone_on_the_near_side_of_the_table_is_not_hidden_by_it():
    text = """【白模测算】
具=餐桌｜东=0｜北=0.8｜底=0｜沿东=1.6｜沿北=0.8｜高=0.75｜关系=留空｜透=不透
人=CHAR:[@甲]｜拍=开场｜东=0｜北=-0.4｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60｜体格=成人
[BEAT_START:1]
拍法=正面｜主拍对象=CHAR:[@甲]｜景别=FS｜望=北｜机位距=三步
镜=B1｜东=0｜北=-2.2｜高=1.1｜望=北｜景别=FS｜视场=84
[BEAT_END:1]
"""
    line = _line(visible_range_block(text, use_blender=False))
    assert _brace(line) == "头,胸,腰,腿"


def test_a_box_outside_ordinary_range_does_not_change_the_occlusion():
    tall_table = _line(visible_range_block(_wide(
        "人=CHAR:[@甲]｜拍=开场｜东=0｜北=0.4｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60｜体格=成人",
        "具=餐桌｜东=0｜北=-0.3｜底=0｜沿东=1.6｜沿北=0.8｜高=2.40｜关系=留空｜透=不透",
    ), use_blender=False))
    assert _brace(tall_table) == "头,胸,腰"
    labeled_child = _line(visible_range_block(_wide(
        "人=CHAR:[@甲]｜拍=开场｜东=0｜北=0.4｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60｜体格=小孩",
        "具=餐桌｜东=0｜北=-0.3｜底=0｜沿东=1.6｜沿北=0.8｜高=0.75｜关系=留空｜透=不透",
    ).replace("高=1.6", "高=1.05"), use_blender=False))
    assert _brace(labeled_child) == "头,胸"


def test_extracted_body_measurements_set_the_occlusion_points():
    woman = _line(visible_range_block(_wide(
        "人=CHAR:[@甲]｜拍=开场｜东=0｜北=0.4｜底=0｜沿东=0.38｜沿北=0.25｜高=1.80｜眼高=1.68｜身高=1.80｜肩宽=0.38｜胸围=84｜胸高=1.40｜腰围=62｜腰高=1.12｜膝高=0.52｜体格=小孩",
        "具=餐桌｜东=0｜北=-0.3｜底=0｜沿东=1.6｜沿北=0.8｜高=0.75｜关系=留空｜透=不透",
    ).replace("｜高=1.6｜", "｜高=1.68｜"), use_blender=False))
    assert _brace(woman) == "头,胸,腰"
    child = _line(visible_range_block(_wide(
        "人=CHAR:[@甲]｜拍=开场｜东=0｜北=0.4｜底=0｜沿东=0.28｜沿北=0.25｜高=1.15｜眼高=1.05｜身高=1.15｜肩宽=0.28｜胸围=58｜胸高=0.86｜腰围=52｜腰高=0.67｜膝高=0.35｜体格=小孩",
        "具=餐桌｜东=0｜北=-0.3｜底=0｜沿东=1.6｜沿北=0.8｜高=0.75｜关系=留空｜透=不透",
    ).replace("｜高=1.6｜", "｜高=1.05｜"), use_blender=False))
    assert _brace(child) == "头,胸"


def test_missing_white_model_returns_empty():
    assert visible_range_block("[BEAT_START:1]\n掌柜拨算盘。\n[BEAT_END:1]", use_blender=False) == ""


def test_camera_is_placed_from_shot_size_when_the_mirror_has_no_meters():
    text = """【白模测算】
人=CHAR:[@甲]｜拍=开场｜东=0｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60
[BEAT_START:1]
拍法=正面｜主拍对象=CHAR:[@甲]｜景别=MS｜望=北｜机位距=两步
镜=B1｜望=北｜景别=MS｜视场=47
[BEAT_END:1]
"""
    block = visible_range_block(text, use_blender=False)
    assert "机位=东0.0北-1.4高1.6" in block
    assert "可见=CHAR:[@甲]" in block


def test_visibility_block_is_prepended_and_framing_stays_unchanged():
    framing = _office("人=CHAR:[@甲]｜拍=1｜东=0｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60")
    staged = prepend_visibility_range("【可见范围】\n来源=旧\n\n【建置】开拍", framing)
    assert staged.startswith("【可见范围】")
    assert "来源=Blender" in staged or "来源=测算" in staged
    assert "来源=旧" not in staged
    assert "可见=CHAR:[@甲]" in staged
    assert "【白模测算】" in framing
    assert "【可见范围】" not in framing


def test_staging_scene_receives_the_measured_range(monkeypatch):
    framing = _office("人=CHAR:[@甲]｜拍=1｜东=0｜北=0｜底=0｜沿东=0.45｜沿北=0.25｜高=1.70｜眼高=1.60")
    monkeypatch.setattr(
        "app.services.scene_subskill_pipeline_runner.prepend_visibility_range",
        lambda scene, source: f"【可见范围】\n来源=测算\n\n{scene}",
    )
    staged = staging_scene_with_visibility(framing, "")
    assert staged.startswith("【可见范围】")
    assert "CHAR:[@甲]" in framing
