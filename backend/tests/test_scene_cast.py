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
    assert "紧跟该人【建置】可见面整句" in brief
    assert "禁把多名牌攒到建置段末或入戏一起写" in brief
    assert "换主环境时另打环境名牌" in brief
    assert "落位=顶部中央" in brief
    assert "标签优先抄 CHAR|#身份 的客观身份" in brief
    assert "只上客观信息，禁透露剧情" in brief
    assert "禁推理" in brief


def test_build_scene_entity_token_brief_empty():
    assert build_scene_entity_token_brief("", "EP01_SC01") == ""


def test_parse_char_extract_records_keeps_voice_profile():
    records = parse_char_extract_records(_script())
    assert [item["name"] for item in records] == ["沈青", "林岳", "林岳_礼服版", "围观百姓"]
    shen = records[0]["text"]
    assert "对白声线=江湖黑话夹杂霸气直球" in shen
    assert "标签=江湖侠客" in shen


def test_nameplate_keeps_char_pipe_identity_tag():
    script = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
[SCENE_CAST_START:EP01_SC01]
【本场角色】在场=CHAR:[@沈青]｜待入画=无｜群演=无
【本场道具】在场=无｜待入画=无
[SCENE_CAST_END:EP01_SC01]
[SCENE_END:EP01_SC01]
[CHAR_EXTRACT_START]
[CHAR] 名称=沈青｜名称_en=Shen Qing｜番位=女主｜适用场=EP01_SC01
身份=现时=落寞寒门女眷｜轨迹=曾经富贵后落寞｜曾经=世家嫡女
标签=落魄千金
标签_en=Fallen Heiress
[CHAR_EXTRACT_END]
[SCENES_BLOCK_END]
"""
    brief = build_scene_entity_token_brief(script, "EP01_SC01")
    tag_section = brief.split("【本场角色标签】")[-1]
    assert "CHAR:[@沈青]｜标签=千金｜标签_en=Heiress" in tag_section
    assert "字幕=待落" in tag_section
    assert "落魄千金" not in tag_section
    assert "Fallen Heiress" not in tag_section
    assert "落寞寒门女眷" not in tag_section
    assert "曾经富贵后落寞" not in tag_section


def test_nameplate_does_not_infer_tag_from_identity():
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
[CHAR_EXTRACT_END]
[SCENES_BLOCK_END]
"""
    brief = build_scene_entity_token_brief(script, "EP01_SC01")
    tag_section = brief.split("【本场角色标签】")[-1]
    assert "CHAR:[@沈青]｜标签=无｜标签_en=无" in tag_section
    assert "江湖侠客" not in tag_section


def test_nameplate_keeps_heir_and_pet_identity_tags():
    script = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
[SCENE_CAST_START:EP01_SC01]
【本场角色】在场=CHAR:[@陆廷泽]，CHAR:[@奥利奥]｜待入画=无｜群演=无
【本场道具】在场=无｜待入画=无
[SCENE_CAST_END:EP01_SC01]
[SCENE_END:EP01_SC01]
[CHAR_EXTRACT_START]
[CHAR] 名称=陆廷泽｜名称_en=Lu Tengze｜番位=男主｜适用场=EP01_SC01
标签=第一家族继承人
标签_en=First Family Heir
[CHAR] 名称=奥利奥｜名称_en=Oreo｜番位=配角｜实体类=宠物｜适用场=EP01_SC01
标签=智能AI宠物猫
标签_en=AI Pet Cat
[CHAR_EXTRACT_END]
[SCENES_BLOCK_END]
"""
    brief = build_scene_entity_token_brief(script, "EP01_SC01")
    tag_section = brief.split("【本场角色标签】")[-1]
    assert "CHAR:[@陆廷泽]｜标签=第一家族继承人｜标签_en=First Family Heir" in tag_section
    assert "CHAR:[@奥利奥]｜标签=智能AI宠物猫｜标签_en=AI Pet Cat" in tag_section


def test_nameplate_rejects_arc_spoiler_tag():
    script = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
[SCENE_CAST_START:EP01_SC01]
【本场角色】在场=CHAR:[@顾清漪]｜待入画=无｜群演=无
【本场道具】在场=无｜待入画=无
[SCENE_CAST_END:EP01_SC01]
[SCENE_END:EP01_SC01]
[CHAR_EXTRACT_START]
[CHAR] 名称=顾清漪｜名称_en=Gu Qingyi｜番位=女主｜适用场=EP01_SC01
标签=复仇女皇
标签_en=Revenge Empress
[CHAR_EXTRACT_END]
[SCENES_BLOCK_END]
"""
    brief = build_scene_entity_token_brief(script, "EP01_SC01")
    tag_section = brief.split("【本场角色标签】")[-1]
    assert "CHAR:[@顾清漪]｜标签=女皇｜标签_en=Empress" in tag_section
    assert "复仇女皇" not in tag_section
    assert "Revenge Empress" not in tag_section


def test_nameplate_rejects_character_positioning_tag():
    script = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
[SCENE_CAST_START:EP01_SC01]
【本场角色】在场=CHAR:[@沈青]｜待入画=无｜群演=无
【本场道具】在场=无｜待入画=无
[SCENE_CAST_END:EP01_SC01]
[SCENE_END:EP01_SC01]
[CHAR_EXTRACT_START]
[CHAR] 名称=沈青｜名称_en=Shen Qing｜番位=女主｜适用场=EP01_SC01
身份=现时=落寞寒门女眷｜轨迹=曾经富贵后落寞｜曾经=世家嫡女
标签=女主
标签_en=Female Lead
[CHAR_EXTRACT_END]
[SCENES_BLOCK_END]
"""
    brief = build_scene_entity_token_brief(script, "EP01_SC01")
    tag_section = brief.split("【本场角色标签】")[-1]
    assert "标签=无｜标签_en=无" in tag_section
    assert "女主" not in tag_section
    assert "Female Lead" not in tag_section


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


def test_nameplate_blocked_when_masked():
    script = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
[SCENE_CAST_START:EP01_SC01]
【本场角色】在场=CHAR:[@沈青]｜待入画=无｜群演=无
【本场道具】在场=无｜待入画=无
[SCENE_CAST_END:EP01_SC01]
[SCENE_END:EP01_SC01]
[CHAR_EXTRACT_START]
[CHAR] 名称=沈青｜名称_en=Shen Qing｜番位=女主｜适用场=EP01_SC01
衣着=黑巾蒙面劲装
标签=江湖侠客
标签_en=Jianghu Knight
[CHAR_EXTRACT_END]
[SCENES_BLOCK_END]
"""
    brief = build_scene_entity_token_brief(script, "EP01_SC01")
    tag_section = brief.split("【本场角色标签】")[-1]
    assert "CHAR:[@沈青]" in tag_section
    assert "字幕=无" in tag_section
    assert "字幕=待落" not in tag_section
    assert "蒙面/易容" in brief


def test_nameplate_blocked_when_field_says_no():
    script = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
[SCENE_CAST_START:EP01_SC01]
【本场角色】在场=CHAR:[@沈青]｜待入画=无｜群演=无
【本场道具】在场=无｜待入画=无
[SCENE_CAST_END:EP01_SC01]
[SCENE_END:EP01_SC01]
[CHAR_EXTRACT_START]
[CHAR] 名称=沈青｜名称_en=Shen Qing｜番位=女主｜适用场=EP01_SC01
衣着=青衫常服
名牌=无
标签=江湖侠客
标签_en=Jianghu Knight
[CHAR_EXTRACT_END]
[SCENES_BLOCK_END]
"""
    brief = build_scene_entity_token_brief(script, "EP01_SC01")
    assert "字幕=无" in brief.split("【本场角色标签】")[-1]
    assert "字幕=待落" not in brief.split("【本场角色标签】")[-1]


def test_nameplate_waits_for_unmask():
    script = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
[SCENE_CAST_START:EP01_SC01]
【本场角色】在场=CHAR:[@沈青]｜待入画=无｜群演=无
【本场道具】在场=无｜待入画=无
[SCENE_CAST_END:EP01_SC01]
[SCENE_END:EP01_SC01]
[CHAR_EXTRACT_START]
[CHAR] 名称=沈青｜名称_en=Shen Qing｜番位=女主｜适用场=EP01_SC01
衣着=黑巾蒙面
名牌=揭面后
形态连续=EP01_SC01 Beat3起：蒙面→揭面
[CHAR_EXTRACT_END]
[SCENES_BLOCK_END]
"""
    brief = build_scene_entity_token_brief(script, "EP01_SC01")
    tag_section = brief.split("【本场角色标签】")[-1]
    assert "字幕=待落" in tag_section
    assert "名牌条件=须真脸" in tag_section
