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
【本场角色】在场=CHAR:[@沈青]，CHAR:[@林岳]｜待入画=无｜群演=无
【本场道具】在场=PROP:[银打火机]｜待入画=无
[SCENE_CAST_END:EP01_SC01]
body
[SCENE_END:EP01_SC01]
[CHAR_EXTRACT_START]
[CHAR] 名称=沈青｜名称_en=Shen Qing｜番位=女主｜适用场=EP01_SC01
对白声线=江湖黑话夹杂霸气直球
[CHAR] 名称=林岳｜名称_en=Lin Yue
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
    assert names["characters"] == ["沈青", "林岳"]
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


def test_build_scene_entity_token_brief_empty():
    assert build_scene_entity_token_brief("", "EP01_SC01") == ""


def test_parse_char_extract_records_keeps_voice_profile():
    records = parse_char_extract_records(_script())
    assert [item["name"] for item in records] == ["沈青", "林岳"]
    shen = records[0]["text"]
    assert "对白声线=江湖黑话夹杂霸气直球" in shen
