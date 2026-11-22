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


def test_close_shot_keeps_only_the_main_subject():
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
    assert "可见=CHAR:[@甲]" in line
    assert "CHAR:[@丁]" in line.split("景别外=")[1]


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
