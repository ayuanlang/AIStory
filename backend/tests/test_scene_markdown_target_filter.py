# -*- coding: utf-8 -*-
from app.services.script_analysis_flow import (
    ParsedSceneUnit,
    _build_scene_markdown_from_table_row,
    coerce_target_scene_ids_for_orchestration,
    extract_derived_environment_names_from_scene_text,
    extract_environment_names_from_scene_text,
    extract_scene_name_value_from_scene_text,
    filter_scene_units_by_target_ids,
    patch_single_scene_markdown_for_orchestration,
    validate_single_scene_markdown_for_orchestration,
    wrap_scene_unit_as_script_block,
)


def _unit(scene_id, scene_order):
    return ParsedSceneUnit(
        scene_id=scene_id,
        scene_order=scene_order,
        scene_text=f"[{scene_id}]",
        marker_start_token=f"[SCENE_START:{scene_id}]",
        marker_end_token=f"[SCENE_END:{scene_id}]",
    )


def test_coerce_target_scene_ids_from_payload_and_instruction():
    assert coerce_target_scene_ids_for_orchestration(
        {"target_scene_ids": ["EP01_SC02", "EP01_SC02"]},
        "",
    ) == ["EP01_SC02"]
    assert coerce_target_scene_ids_for_orchestration(
        {"target_scene_id": "EP01_SC03"},
        "",
    ) == ["EP01_SC03"]
    assert coerce_target_scene_ids_for_orchestration(
        {},
        "【单场处理模式】本次仅处理 Scene ID `EP01_SC04`。输入剧本正文含该场",
    ) == ["EP01_SC04"]
    assert coerce_target_scene_ids_for_orchestration({}, "no target here") == []


def test_filter_scene_units_keeps_only_requested_scene():
    units = [
        _unit("EP01_SC01", 1),
        _unit("EP01_SC02", 2),
        _unit("EP01_SC03", 3),
    ]
    matched = filter_scene_units_by_target_ids(units, ["EP01_SC02"], episode_prefix="EP01")
    assert [item.scene_id for item in matched] == ["EP01_SC02"]


def test_filter_scene_units_accepts_numeric_alias():
    units = [
        _unit("EP01_SC01", 1),
        _unit("EP01_SC02", 2),
    ]
    matched = filter_scene_units_by_target_ids(units, ["2"], episode_prefix="EP01")
    assert [item.scene_id for item in matched] == ["EP01_SC02"]


def test_scene_table_cells_remove_markdown_pipe_characters():
    markdown = _build_scene_markdown_from_table_row(
        ["Episode ID", "Scene ID", "Scene Name", "Core Scene Info"],
        ["EP01", "EP01_SC03", "客栈｜黄昏|内", "方言|对白"],
    )

    assert "客栈·黄昏·内" in markdown
    assert "方言／对白" in markdown
    assert "客栈｜黄昏|内" not in markdown


def test_legacy_scene_name_drops_keys_and_moves_validation_out():
    scene_text = (
        "【场景名称】短名=客栈天井玉佩掉落与真气爆发｜日夜=黄昏｜内外=内"
        "｜叙事线=正常叙事｜校验=通过｜纯地名=否"
    )

    assert extract_scene_name_value_from_scene_text(scene_text) == (
        "客栈天井玉佩掉落与真气爆发·黄昏·内·正常叙事"
    )


def test_extract_environment_names_from_main_env_block():
    scene_text = """
[ENV_BLOCK_START]
────【主环境】────
【主环境】客栈废墟外｜日夜内外=黄昏·外｜主环境角色=当下主线
────【衍生环境】────
- `0度客栈废墟外`：所属主环境=客栈废墟外
[ENV_BLOCK_END]
"""
    assert extract_environment_names_from_scene_text(scene_text) == "客栈废墟外"
    assert extract_derived_environment_names_from_scene_text(scene_text) == "0度客栈废墟外"


def test_wrap_scene_unit_injects_derived_environment_names_only():
    unit = ParsedSceneUnit(
        scene_id="EP01_SC02",
        scene_order=2,
        scene_text="""【场景名称】客栈对峙·黄昏·外
[ENV_BLOCK_START]
────【主环境】────
【主环境】客栈废墟外｜日夜内外=黄昏·外
────【衍生环境】────
- `0度客栈废墟外`：所属主环境=客栈废墟外
- `180度客栈废墟外`：所属主环境=客栈废墟外
[ENV_BLOCK_END]
[BEAT_START:1]
- Beat 1（对峙）
────【建置】────
当前环境=0度客栈废墟外
────【入戏】────
林岳拔刀。
[BEAT_END:1]
""",
        marker_start_token="[SCENE_START:EP01_SC02]",
        marker_end_token="[SCENE_END:EP01_SC02]",
    )
    wrapped = wrap_scene_unit_as_script_block(unit)
    assert "【本场环境名】" not in wrapped
    assert "【本场衍生环境名】0度客栈废墟外，180度客栈废墟外" in wrapped
    assert "客栈废墟外" not in wrapped.split("【本场衍生环境名】", 1)[0]
    assert "[ENV_BLOCK_START]" not in wrapped


def test_extract_environment_names_joins_multiple_with_chinese_comma():
    scene_text = """
[ENV_BLOCK_START]
【主环境】清河城茶摊｜日夜内外=日·外
【主环境】客栈废墟外｜日夜内外=黄昏·外
[ENV_BLOCK_END]
"""
    assert extract_environment_names_from_scene_text(scene_text) == "清河城茶摊，客栈废墟外"


def test_patch_orchestration_backfills_environment_name_and_picks_correct_row():
    llm_table = """
| Episode ID | Scene ID | Scene No. | Scene Name | Equivalent Duration | Core Scene Info | Adapted Script Excerpt | Environment Name | Environment Relation | Base Environment Reference | Environment Delta | Entry State | Exit State | Linked Characters | Key Props |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| EP01 | EP01_SC05 | 1 | 金镶玉看破李玄伪装·黄昏·内·正常叙事 | None | beat-sc01 | None | None | None | None | None | None | None | CHAR:[@金镶玉] | None |
| EP01 | EP01_SC05 | 5 | 两人并肩迎敌·黄昏·外·正常叙事 | None | beat-sc05 | None | None | None | None | None | None | None | CHAR:[@金镶玉] | PROP:[纯金算盘] |
"""
    patched = patch_single_scene_markdown_for_orchestration(
        llm_table,
        "EP01_SC05",
        scene_order=5,
        scene_name="两人并肩迎敌·黄昏·外·正常叙事",
        environment_name="0度客栈废墟外，180度客栈废墟外",
    )
    assert "beat-sc05" in patched
    assert "beat-sc01" not in patched
    assert "0度客栈废墟外，180度客栈废墟外" in patched
    assert validate_single_scene_markdown_for_orchestration(
        patched,
        "EP01_SC05",
        scene_order=5,
    ) is None


def test_patch_orchestration_replaces_bare_main_environment_name():
    llm_table = """
| Episode ID | Scene ID | Scene No. | Scene Name | Equivalent Duration | Core Scene Info | Adapted Script Excerpt | Environment Name | Linked Characters | Key Props |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| EP01 | EP01_SC02 | 2 | 客栈对峙·黄昏·外 | None | beat-sc02 | None | 客栈废墟外 | CHAR:[@林岳] | None |
"""
    patched = patch_single_scene_markdown_for_orchestration(
        llm_table,
        "EP01_SC02",
        scene_order=2,
        environment_name="0度客栈废墟外，180度客栈废墟外",
    )
    assert "0度客栈废墟外，180度客栈废墟外" in patched
    assert "| 客栈废墟外 |" not in patched


def test_orchestration_workspace_row_uses_scene_id_and_canonical_no():
    from app.services.scene_markdown_orchestration import (
        _select_workspace_row_from_orchestration_markdown,
    )

    markdown = """
| Episode ID | Scene ID | Scene No. | Scene Name | Core Scene Info | Original Script Text | Environment Name | Linked Characters | Key Props |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| EP01 | EP01_SC05 | 5 | 荒漠铁骑压境·黄昏·外 | 大军压境 | 残阳古道 | 荒漠残阳古道 | 无 | 无 |
"""
    row = _select_workspace_row_from_orchestration_markdown(
        markdown,
        target_scene_id="EP01_SC05",
        scene_order=5,
    )
    assert row is not None
    assert row["scene_id"] == "EP01_SC05"
    assert row["scene_no"] == "5"
    assert row["environment_name"] == "荒漠残阳古道"


def test_orchestration_workspace_row_reads_adapted_script_excerpt():
    from app.services.scene_markdown_orchestration import (
        _select_workspace_row_from_orchestration_markdown,
    )

    markdown = """
| Episode ID | Scene ID | Scene No. | Scene Name | Equivalent Duration | Core Scene Info | Adapted Script Excerpt | Environment Name | Linked Characters | Key Props |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| EP01 | EP01_SC01 | 1 | 客栈对峙·黄昏·外 | None | beat-sc01 | 林岳拔刀 | 0度客栈废墟外 | CHAR:[@林岳] | None |
"""
    row = _select_workspace_row_from_orchestration_markdown(
        markdown,
        target_scene_id="EP01_SC01",
        scene_order=1,
    )
    assert row is not None
    assert row["original_script_text"] == "林岳拔刀"


def test_scene_out_coerces_null_original_script_text():
    from app.schemas.scene import SceneOut

    scene = SceneOut.model_validate(
        {
            "id": 1,
            "scene_no": "1",
            "original_script_text": None,
            "scene_name": "客栈对峙",
            "equivalent_duration": None,
            "core_scene_info": None,
            "environment_name": "0度客栈废墟外",
            "linked_characters": None,
            "key_props": None,
        }
    )
    assert scene.original_script_text == ""
