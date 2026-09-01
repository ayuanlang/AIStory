# -*- coding: utf-8 -*-
from app.services.script_analysis_flow.workspace_scene_from_staging import (
    build_scene_table_markdown_from_staging,
    build_workspace_scene_payload_from_staging,
)


def _staging_block() -> str:
    return """[SCENE_START:EP01_SC02]
【场景名称】客栈对峙·夜·内
[SCENE_CAST_START:EP01_SC02]
【本场角色】在场=CHAR:[@林岳]，CHAR:[@陈]
【本场道具】在场=PROP:[信]
[SCENE_CAST_END:EP01_SC02]
【本场衍生环境名】180度客栈大堂
[BEAT_START:1]
────【建置】────
当前环境=ENV:[180度客栈大堂]
CHAR:[@林岳] 把 PROP:[信] 放在桌上。
────【入戏】────
对峙开始。
[BEAT_END:1]
[SCENE_END:EP01_SC02]
"""


def test_workspace_payload_extracts_staging_fields():
    payload = build_workspace_scene_payload_from_staging(
        scene_id="EP01_SC02",
        scene_order=2,
        staging_text=_staging_block(),
    )
    assert payload["scene_no"] == "2"
    assert payload["scene_name"] == "客栈对峙·夜·内"
    assert "180度客栈大堂" in (payload["environment_name"] or "")
    assert "CHAR:[@林岳]" in (payload["linked_characters"] or "")
    assert "PROP:[信]" in (payload["key_props"] or "")
    assert "[BEAT_START:1]" in (payload["core_scene_info"] or "")
    assert "{Beats}" in (payload["core_scene_info"] or "")
    assert "{登场实体}" in (payload["core_scene_info"] or "")


def test_scene_table_markdown_has_identity_columns():
    markdown = build_scene_table_markdown_from_staging(
        scene_id="EP01_SC02",
        scene_order=2,
        staging_text=_staging_block(),
    )
    assert "### Part 1: Scenes Table" in markdown
    assert "| Scene ID |" in markdown
    assert "EP01_SC02" in markdown
    assert "客栈对峙" in markdown


def test_workspace_beats_strip_per_beat_continuity_notes():
    staging = """[SCENE_START:EP01_SC02]
【场景名称】客栈对峙·夜·内
[BEAT_START:1]
────【建置】────
CHAR:[@林岳] 位于桌近镜头侧旁，站。
────【入戏】────
对峙开始。
────【场记分析】────
开拍在场角色数=2｜开拍在场道具数=0｜开拍在场主体数=2
开拍在场=CHAR:[@林岳]，CHAR:[@陈]
本拍主体=CHAR:[@林岳]|宫格=中中|在场=是|可见=画内|因=本拍主拍
CHAR:[@陈]|宫格=中左|在场=是|可见=暂不可见|因=景别:CU仅主拍
收拍在场角色数=2｜收拍在场主体数=2
────【场记分析结束】────
[BEAT_END:1]
[SCENE_END:EP01_SC02]
"""
    payload = build_workspace_scene_payload_from_staging(
        scene_id="EP01_SC02",
        scene_order=2,
        staging_text=staging,
    )
    core = payload["core_scene_info"] or ""
    assert "[BEAT_START:1]" in core
    assert "【建置】" in core
    assert "对峙开始" in core
    assert "场记分析" not in core
    assert "开拍在场角色数" not in core
    assert "暂不可见" not in core


def test_appearing_entities_strip_stacked_env_english_and_dedupe():
    staging = """[SCENE_START:EP01_SC01]
【场景名称】高空追杀·夜·外
[SCENE_CAST_START:EP01_SC01]
【本场角色】在场=CHAR:[@顾沉]，CHAR:[@异兽翼群]，CHAR:[@翼兽]
【本场道具】在场=PROP:[飞行器]，PROP:[无人猎杀号]
[SCENE_CAST_END:EP01_SC01]
【本场衍生环境名】ENV:[0度岚京高空交通层 (Lan-Jing Aerial Transit Layer) (Lan-Jing Aerial Transit Layer)]，ENV:[90度岚京高空交通层 (Lan-Jing Aerial Transit Layer)]，ENV:[0度岚京高空交通层 (Lan-Jing Aerial Transit Layer)]
[BEAT_START:1]
────【建置】────
当前环境=ENV:[0度岚京高空交通层 (Lan-Jing Aerial Transit Layer) (Lan-Jing Aerial Transit Layer)]
CHAR:[@顾沉] 驾驶 PROP:[飞行器]。
[BEAT_END:1]
[SCENE_END:EP01_SC01]
"""
    payload = build_workspace_scene_payload_from_staging(
        scene_id="EP01_SC01",
        scene_order=1,
        staging_text=staging,
    )
    appearing = payload["core_scene_info"] or ""
    entity_line = next(
        (line for line in appearing.splitlines() if "{登场实体}" in line),
        "",
    )
    assert "Lan-Jing Aerial Transit Layer" not in appearing
    assert entity_line.count("ENV:[0度岚京高空交通层]") == 1
    assert "ENV:[90度岚京高空交通层]" in entity_line
    assert "CHAR:[@顾沉]" in appearing
    assert "CHAR:[@异兽翼群]" in appearing
    assert "CHAR:[@翼兽]" in appearing
    assert "PROP:[飞行器]" in appearing
    assert payload["environment_name"] == "0度岚京高空交通层，90度岚京高空交通层"
