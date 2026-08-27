# -*- coding: utf-8 -*-
from app.services.script_analysis_flow.character_asset_brief import parse_char_extract_records
from app.services.script_analysis_flow.scene_cast import (
    build_scene_entity_token_brief,
    extract_scene_cast_block,
    extract_scene_cast_blocks,
    scene_cast_token_names,
)


def _script() -> str:
    return """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
【场景名称】客栈对峙
[SCENE_CAST_START:EP01_SC01]
【本场角色】在场=CHAR:[@沈青]，CHAR:[@林岳]｜待入画=无｜群演=CHAR:[@围观百姓]
【本场道具】在场=PROP:[银打火机]｜待入画=无
[SCENE_CAST_END:EP01_SC01]
body
[SCENE_END:EP01_SC01]
[CHAR_EXTRACT_START]
[CHAR] 名称=沈青｜名称_en=Shen Qing｜番位=女主｜适用场=EP01_SC01|EP01_SC02
身份=江湖侠客
标签=江湖侠客
标签_en=Jianghu Knight
标签字体=魏碑
标签字色=鎏金
对白声线=江湖黑话夹杂霸气直球
[CHAR] 名称=林岳｜名称_en=Lin Yue｜番位=男主｜适用场=EP01_SC01
身份=客栈掌柜
标签=客栈掌柜
标签_en=Innkeeper
标签字体=魏碑
标签字色=朱红
[CHAR] 名称=林岳_礼服版｜名称_en=Lin Yue Formal｜番位=男主｜适用场=EP01_SC02
基名=林岳
标签=客栈掌柜
[CHAR] 名称=围观百姓｜名称_en=Onlookers｜番位=群演簇｜适用场=EP01_SC01
标签=无
标签_en=无
标签字体=无
标签字色=无
[CHAR_EXTRACT_END]
[PROP_EXTRACT_START]
[PROP] 名称=银打火机｜名称_en=Silver Lighter
[PROP_EXTRACT_END]
[SCENES_BLOCK_END]
"""


def test_extract_scene_cast_block():
    script = _script()
    block = extract_scene_cast_block(script, "EP01_SC01")
    assert "[SCENE_CAST_START:EP01_SC01]" in block
    assert "CHAR:[@沈青]" in block
    assert "PROP:[银打火机]" in block
    assert extract_scene_cast_blocks(script)["EP01_SC01"] == block


def test_scene_cast_token_names():
    names = scene_cast_token_names(extract_scene_cast_block(_script(), "EP01_SC01"))
    assert names["characters"] == ["沈青", "林岳", "围观百姓"]
    assert names["props"] == ["银打火机"]


def test_build_scene_entity_token_brief():
    brief = build_scene_entity_token_brief(_script(), "EP01_SC01")
    assert "[本场角色道具白名单开始]" in brief
    assert "[本场角色道具白名单结束]" in brief
    assert "CHAR: 沈青，林岳" in brief
    assert "PROP: 银打火机" in brief
    assert "CHAR:[@沈青]" in brief
    assert "禁止 `ENV:`" in brief
    assert "【本场对白声线】" in brief
    assert "CHAR:[@沈青]｜对白声线=江湖黑话夹杂霸气直球" in brief
    assert "voice_identity" in brief
    assert "【本场角色标签】" in brief
    assert "CHAR:[@沈青]｜标签=江湖侠客｜标签_en=Jianghu Knight｜标签字体=魏碑｜标签字色=鎏金｜裸名=沈青｜裸名_en=Shen Qing｜字幕=待落" in brief
    assert "CHAR:[@林岳]｜标签=客栈掌柜｜标签_en=Innkeeper｜标签字体=魏碑｜标签字色=朱红｜裸名=林岳｜裸名_en=Lin Yue｜字幕=待落" in brief
    assert "CHAR:[@围观百姓]｜标签=无｜标签_en=无｜标签字体=无｜标签字色=无｜裸名=围观百姓｜裸名_en=Onlookers｜字幕=无" in brief
    assert "中文项目用 裸名+标签" in brief
    assert "物理文字标签" in brief
    assert "不是对白硬字幕" in brief


def test_build_scene_entity_token_brief_empty():
    assert build_scene_entity_token_brief("", "EP01_SC01") == ""


def test_parse_char_extract_records_keeps_voice_profile():
    records = parse_char_extract_records(_script())
    assert [item["name"] for item in records] == ["沈青", "林岳", "林岳_礼服版", "围观百姓"]
    shen = records[0]["text"]
    assert "对白声线=江湖黑话夹杂霸气直球" in shen
    assert "标签=江湖侠客" in shen


def test_character_label_style_pending_when_missing():
    script = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
[SCENE_CAST_START:EP01_SC01]
【本场角色】在场=CHAR:[@沈青]｜待入画=无｜群演=无
【本场道具】在场=无｜待入画=无
[SCENE_CAST_END:EP01_SC01]
[SCENE_END:EP01_SC01]
[CHAR_EXTRACT_START]
[CHAR] 名称=沈青｜名称_en=Shen Qing｜番位=女主｜适用场=EP01_SC01
身份=江湖侠客
标签=江湖侠客
标签_en=Jianghu Knight
[CHAR_EXTRACT_END]
[SCENES_BLOCK_END]
"""
    brief = build_scene_entity_token_brief(script, "EP01_SC01")
    assert "标签字体=待补｜标签字色=待补" in brief


def test_character_intro_tag_later_scene_and_variants():
    script = _script() + """
[SCENE_START:EP01_SC02]
[SCENE_CAST_START:EP01_SC02]
【本场角色】在场=CHAR:[@沈青]，CHAR:[@林岳_礼服版]｜待入画=无｜群演=无
【本场道具】在场=无｜待入画=无
[SCENE_CAST_END:EP01_SC02]
[SCENE_END:EP01_SC02]
"""
    later = build_scene_entity_token_brief(script, "EP01_SC02")
    assert "CHAR:[@沈青]｜标签=江湖侠客｜标签_en=Jianghu Knight｜标签字体=魏碑｜标签字色=鎏金｜裸名=沈青｜裸名_en=Shen Qing｜字幕=已过" in later
    assert "CHAR:[@林岳_礼服版]｜标签=客栈掌柜｜标签_en=Innkeeper｜标签字体=魏碑｜标签字色=朱红｜裸名=林岳｜裸名_en=Lin Yue｜字幕=无" in later
    assert "CHAR:[@围观百姓]" not in later
