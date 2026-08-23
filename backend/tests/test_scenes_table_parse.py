# -*- coding: utf-8 -*-
import pytest

from app.services.script_analysis_flow import (
    SceneMarkerParseError,
    _find_scenes_table_header_pos,
    parse_scene_units_from_scenes_table,
)
from app.services.script_analysis_flow.analyze_scene_stages import (
    extract_scene_markdown_text_from_analyze_result,
)


TEA_STALL_SCENES_TABLE = """
| Episode ID | Scene ID | Scene No. | Scene Name | Equivalent Duration | Core Scene Info | Adapted Script Excerpt | Environment Name | Environment Relation | Base Environment Reference | Environment Delta | Entry State | Exit State | Linked Characters | Key Props |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| EP01 | EP01_SC02 | 2 | 清河城茶摊碰头·日·外·正常叙事 | None | - **{剧情阶段}**: 正常叙事<br>- **{Beats}**:<br>[BEAT_START:1]<br>- Beat 1：<br>────【建置】────<br>【实层表】CHAR:[@大量百姓]:前景,画面中央<br>环境：当前环境 ENV:[0度清河城茶摊]，日，外。<br>角色与站位：<br>CHAR:[@大量百姓]：前景，画面中央，规模约数十人，散布在街道上，多侧面或背对镜头行走，行走姿态。<br>CHAR:[@楚玄_隐匿版]：坐在角落方桌内侧客位端、远镜头一侧的长凳上。正面朝向镜头可读，面向前景CHAR:[@大量百姓]，坐姿。面具在正面/脸部佩戴。<br>────【入戏】────<br><街道上人声喧哗，叫卖声此起彼伏> 画面打出字幕：一年后。街道上人来人往，CHAR:[@楚玄_隐匿版]一身素衣，戴着面具独自坐在街边茶摊的角落位置，身形隐匿在CHAR:[@大量百姓]的边缘，保持着低调与警惕。<br>[BEAT_END:1]<br>[BEAT_START:2]<br>~ Beat 2：<br>────【建置】────<br>【实层表】CHAR:[@大量百姓]:前景,画面中央<br>环境：当前环境 ENV:[0度清河城茶摊]，日，外。<br>CHAR:[@血钢丝]：在CHAR:[@楚玄_隐匿版]正面/右小臂上，姿态蜿蜒。<br>────【入戏】────<br>voice_type=内心／voice_identity=楚玄·青年内敛音／tone=压抑紧迫／speed=偏快／volume=低沉／rhythm=急促／stress=三日／pause=无<br>{只剩三日了，}<br>[BEAT_END:2] | <街道上人声喧哗，叫卖声此起彼伏> 画面打出字幕：一年后。街道上人来人往，CHAR:[@楚玄_隐匿版]一身素衣...／夸奖的话待会再说，妖兽血珠带来了吗？ | 清河城茶摊 | None | None | None | None | None | CHAR:[@大量百姓]／CHAR:[@楚玄_隐匿版]／CHAR:[@血钢丝]／CHAR:[@何亮] | None |
"""


def test_tea_stall_scenes_table_parses_environment_name():
    units = parse_scene_units_from_scenes_table(TEA_STALL_SCENES_TABLE)
    assert len(units) == 1
    assert units[0].scene_id == "EP01_SC02"
    assert "清河城茶摊" in (units[0].scene_text or "")
    assert "EP01_SC02" in (units[0].scene_markdown or "")


def test_extra_pipes_in_core_info_keep_environment_name():
    table = """
| Episode ID | Scene ID | Scene No. | Scene Name | Equivalent Duration | Core Scene Info | Adapted Script Excerpt | Environment Name | Environment Relation | Base Environment Reference | Environment Delta | Entry State | Exit State | Linked Characters | Key Props |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| EP01 | EP01_SC02 | 2 | 茶摊碰头 | None | beat A | leftover | more leftover | excerpt | 清河城茶摊 | None | None | None | None | None | CHAR:[@楚玄] | None |
"""
    units = parse_scene_units_from_scenes_table(table)
    assert len(units) == 1
    assert units[0].scene_id == "EP01_SC02"
    assert "清河城茶摊" in (units[0].scene_text or "")


def test_scenes_table_does_not_fallback_to_marker_missing():
    table = """
| Episode ID | Scene ID | Scene No. | Scene Name | Equivalent Duration | Core Scene Info | Adapted Script Excerpt | Environment Name | Environment Relation | Base Environment Reference | Environment Delta | Entry State | Exit State | Linked Characters | Key Props |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| EP01 | EP01_SC02 | 2 | 茶摊碰头 | None | beat | excerpt | None | None | None | None | None | None | CHAR:[@楚玄] | None |
"""
    assert _find_scenes_table_header_pos(table) >= 0
    with pytest.raises(SceneMarkerParseError) as exc:
        parse_scene_units_from_scenes_table(table)
    assert exc.value.code == "SCENES_TABLE_EMPTY_ENVIRONMENT_NAME"


def test_extract_scene_markdown_prefers_table_over_adapted_script():
    table = TEA_STALL_SCENES_TABLE.strip()
    extracted = extract_scene_markdown_text_from_analyze_result(
        {
            "adapted_script": "[SCENES_BLOCK_START]\nnot a table\n[SCENES_BLOCK_END]",
            "result": table,
            "content": "ignore me",
        }
    )
    assert extracted == table
