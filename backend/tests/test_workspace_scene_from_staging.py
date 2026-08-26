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
