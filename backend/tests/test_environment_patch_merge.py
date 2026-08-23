# -*- coding: utf-8 -*-
from app.services.scene_subskill_pipeline_runner import (
    DRAMA_PROMPT,
    FRAMING_PROMPT,
    _strip_subskill_completion_marker,
)
from app.services.script_analysis_flow_runner import (
    _merge_environment_patches,
    _strip_required_completion_marker,
)


def test_environment_patches_merge_into_matching_scenes_without_rewriting_source():
    split_text = """[SCENES_BLOCK_START]
[COMPREHENSIVE_INFO_START]
project canon
[COMPREHENSIVE_INFO_END]
[SCENE_START:EP01_SC01]
【场景名称】短名=one
[SCENE_CONTENT_START:EP01_SC01]
original one
[SCENE_CONTENT_END:EP01_SC01]
[SCENE_END:EP01_SC01]
[SCENE_START:EP01_SC02]
【场景名称】短名=two
[SCENE_CONTENT_START:EP01_SC02]
original two
[SCENE_CONTENT_END:EP01_SC02]
[SCENE_END:EP01_SC02]
[SCENES_BLOCK_END]
{"project_visual_backfill":{"tone":"cold"}}"""
    patch_text = """[ENV_SCENE_PATCH_START:EP01_SC01]
[ENV_BLOCK_START]
【主环境】room one
[ENV_BLOCK_END]
【Beat→衍生ENV剧情覆盖矩阵】
B1=R:{one}｜ENV:0度room one｜W:{one}｜R−W=∅
【ENV覆盖综合】Beat=全量｜缺项=0
[ENV_SCENE_PATCH_END:EP01_SC01]
[ENV_SCENE_PATCH_START:EP01_SC02]
[ENV_BLOCK_START]
【主环境】room two
[ENV_BLOCK_END]
【Beat→衍生ENV剧情覆盖矩阵】
B1=R:{two}｜ENV:0度room two｜W:{two}｜R−W=∅
【ENV覆盖综合】Beat=全量｜缺项=0
[ENV_SCENE_PATCH_END:EP01_SC02]"""

    merged = _merge_environment_patches(split_text, patch_text)

    assert merged.count("[ENV_BLOCK_START]") == 2
    assert merged.index("【主环境】room one") < merged.index("[SCENE_CONTENT_START:EP01_SC01]")
    assert merged.index("【主环境】room two") < merged.index("[SCENE_CONTENT_START:EP01_SC02]")
    assert "original one" in merged
    assert "original two" in merged
    assert "[COMPREHENSIVE_INFO_START]" in merged
    assert '{"project_visual_backfill":{"tone":"cold"}}' in merged
    assert "ENV_SCENE_PATCH_START" not in merged


def test_completion_markers_must_be_unique_and_terminal():
    environment_marker = "[ENVIRONMENT_PLAN_OUTPUT_END]"
    assert _strip_required_completion_marker(
        f"[ENV_SCENE_PATCH_START:EP01_SC01]\npatch\n{environment_marker}",
        environment_marker,
    ).endswith("patch")
    assert not _strip_required_completion_marker(
        f"{environment_marker}\nextra",
        environment_marker,
    )

    drama_marker = "[DRAMA_STANDARDIZATION_OUTPUT_END]"
    assert _strip_subskill_completion_marker(
        f"[SCENES_BLOCK_START]\nscene\n[SCENES_BLOCK_END]\n{drama_marker}",
        DRAMA_PROMPT,
    ).endswith("[SCENES_BLOCK_END]")
    assert _strip_subskill_completion_marker(
        f"[SCENES_BLOCK_START]\nscene\n[SCENES_BLOCK_END]\n`{drama_marker}`\n(ok)",
        DRAMA_PROMPT,
    ).endswith("[SCENES_BLOCK_END]")
    assert _strip_subskill_completion_marker(
        f"body\n{drama_marker}\nnote",
        DRAMA_PROMPT,
    ) == "body"

    framing_marker = "[DERIVED_FRAMING_OUTPUT_END]"
    assert _strip_subskill_completion_marker(
        f"[SCENES_BLOCK_START]\nscene\n[SCENES_BLOCK_END]\n{framing_marker}",
        FRAMING_PROMPT,
    ).endswith("[SCENES_BLOCK_END]")


def test_scene_env_ident_parse_and_reuse_decision():
    from app.services.script_analysis_flow.environment_reuse import (
        build_project_main_environment_injection,
        build_reused_derived_environment_injection,
        build_reused_environment_patch,
        parse_scene_env_ident_items,
        scene_has_new_environments,
        scene_reused_environment_names,
    )

    text = """【场景名称】客栈对峙·夜·内
[SCENE_ENV_IDENT_START:EP02_SC01]
[ENV] 名称=客栈大堂｜复用=是｜来源=项目库｜匹配主环境=客栈大堂｜依据=原文：“大堂”
[ENV] 名称=马车内舱｜复用=否｜来源=新建｜匹配主环境=无｜依据=原文：“上车”
[SCENE_ENV_IDENT_END:EP02_SC01]
"""
    items = parse_scene_env_ident_items(text, "EP02_SC01")
    assert [item["name"] for item in items] == ["客栈大堂", "马车内舱"]
    assert items[0]["reuse"] is True
    assert items[1]["reuse"] is False
    assert scene_has_new_environments(items) is True
    assert scene_reused_environment_names(items) == ["客栈大堂"]

    reuse_only = """[SCENE_ENV_IDENT_START:EP02_SC03]
[ENV] 名称=客栈大堂｜复用=是｜来源=上集｜匹配主环境=客栈大堂｜依据=原文：“回客栈”
[SCENE_ENV_IDENT_END:EP02_SC03]"""
    reused_items = parse_scene_env_ident_items(reuse_only, "EP02_SC03")
    assert scene_has_new_environments(reused_items) is False

    catalog = [
        {
            "name": "客栈大堂",
            "normalized": "客栈大堂",
            "source": "项目库",
            "source_label": "项目库",
            "episode_tag": "EP01",
            "env_block": "",
            "derivatives": [
                {"name": "0度客栈大堂", "view_angle_from_main": 0, "generation_prompt_cn": "四向拼图"},
                {"name": "180度客栈大堂", "view_angle_from_main": 180, "generation_prompt_cn": ""},
            ],
        }
    ]
    injection = build_project_main_environment_injection(catalog)
    assert "[项目主环境名开始]" in injection
    assert "客栈大堂｜来源=项目库" in injection
    assert "已有衍生=`0度客栈大堂`" in injection or "0度客栈大堂" in injection
    empty_injection = build_project_main_environment_injection([])
    assert "[项目主环境名开始]" in empty_injection
    assert "可复用/可参考主环境=无" in empty_injection

    patch = build_reused_environment_patch("EP02_SC03", reused_items, catalog)
    assert "[ENV_SCENE_PATCH_START:EP02_SC03]" in patch
    assert "【主环境】客栈大堂" in patch
    assert "────【衍生环境】────" not in patch
    assert "`0度客栈大堂`" not in patch

    derived = build_reused_derived_environment_injection(reused_items, catalog)
    assert "[复用衍生环境开始]" in derived
    assert "`180度客栈大堂`" in derived


def test_missing_env_ident_defaults_to_new_planning():
    from app.services.script_analysis_flow.environment_reuse import scene_has_new_environments

    assert scene_has_new_environments([]) is True


def test_reuse_lock_instruction_is_whole_episode():
    from app.services.script_analysis_flow.environment_reuse import format_reuse_lock_instruction

    text = format_reuse_lock_instruction(["客栈大堂", "马车外"])
    assert "整集环境规划" in text
    assert "客栈大堂" in text
    assert "全复用场不要输出补丁" in text
    empty = format_reuse_lock_instruction([])
    assert "待复用主环境=无" in empty
    detailed = format_reuse_lock_instruction(
        ["客栈大堂"],
        [
            {
                "name": "客栈大堂",
                "normalized": "客栈大堂",
                "source_label": "项目库",
                "description": "夜市内堂，柜台在180度侧",
                "derivatives": [{"name": "0度客栈大堂"}],
            }
        ],
    )
    assert "待复用主环境：" in detailed
    assert "摘要=夜市内堂，柜台在180度侧" in detailed
    assert "0度客栈大堂" in detailed


def test_selected_global_environment_injection_marks_none_and_details():
    from app.services.script_analysis_flow.environment_reuse import (
        format_selected_global_environment_injection,
    )

    empty = format_selected_global_environment_injection([])
    assert "[用户选定全局环境开始]" in empty
    assert "用户选定全局环境=无" in empty

    selected = format_selected_global_environment_injection(
        [
            {
                "name": "清河城茶摊",
                "normalized": "清河城茶摊",
                "source_label": "用户选定全局资产",
                "description": "街边茶摊，角落方桌",
                "derivatives": [{"name": "0度清河城茶摊"}, {"name": "180度清河城茶摊"}],
            }
        ]
    )
    assert "清河城茶摊｜来源=用户选定全局资产" in selected
    assert "街边茶摊，角落方桌" in selected
    assert "0度清河城茶摊" in selected
    assert "逐条对照" in selected
    assert "禁止另起同义空壳" in selected


def test_framing_waits_for_environment_plan_node_success():
    from app.services.scene_subskill_pipeline_runner import (
        environment_plan_ready_for_framing,
        script_has_environment_blocks,
    )

    planned = "[ENV_BLOCK_START]\n【主环境】客栈大堂\n[ENV_BLOCK_END]"
    assert script_has_environment_blocks(planned)
    assert environment_plan_ready_for_framing("success", planned) is True
    assert environment_plan_ready_for_framing("warning", planned) is True
    assert environment_plan_ready_for_framing("running", planned) is False
    assert environment_plan_ready_for_framing("queued", planned) is False
    assert environment_plan_ready_for_framing("", planned) is False
    assert environment_plan_ready_for_framing("success", "[SCENE_START:EP01_SC01]") is False


def test_staging_splices_env_plan_scene_onto_drama_enhance():
    from app.services.scene_subskill_pipeline_runner import (
        splice_environment_and_enhance_scene,
        strip_environment_planning_sections,
    )

    env_scene = """[SPECIAL_SCENE_ANALYSIS_START:EP01_SC01]
[VFX] 命中=否
[SPECIAL_SCENE_ANALYSIS_END:EP01_SC01]
[SCENE_START:EP01_SC01]
【场景名称】客栈对峙
[SCENE_ENV_IDENT_START:EP01_SC01]
[ENV] 名称=客栈大堂｜复用=否｜来源=新建
[SCENE_ENV_IDENT_END:EP01_SC01]
[ENV_BLOCK_START]
【主环境】客栈大堂
[ENV_BLOCK_END]
【Beat→衍生ENV剧情覆盖矩阵】
B1=R:{desk}｜ENV:0度客栈大堂｜W:{desk}｜R−W=∅
【ENV覆盖综合】Beat=全量｜缺项=0
[SCENE_CONTENT_START:EP01_SC01]
split body
[SCENE_CONTENT_END:EP01_SC01]
[SCENE_END:EP01_SC01]"""
    enhance = """[SPECIAL_SCENE_ANALYSIS_START:EP01_SC01]
[VFX] 命中=否
[SPECIAL_SCENE_ANALYSIS_END:EP01_SC01]
[SCENE_START:EP01_SC01]
【场景名称】客栈对峙
[SCENE_ENV_IDENT_START:EP01_SC01]
[ENV] 名称=客栈大堂｜复用=否｜来源=新建
[SCENE_ENV_IDENT_END:EP01_SC01]
[SCENE_CONTENT_START:EP01_SC01]
drama body
[BEAT_START:B1]
standardized beat
[BEAT_END:B1]
[SCENE_CONTENT_END:EP01_SC01]
[SCENE_END:EP01_SC01]"""

    spliced = splice_environment_and_enhance_scene(
        "EP01_SC01",
        env_scene,
        enhance,
        "[SPECIAL_SCENE_ANALYSIS_START:EP01_SC01]\n[VFX] 命中=否\n[SPECIAL_SCENE_ANALYSIS_END:EP01_SC01]",
    )
    assert spliced.index("[ENV_BLOCK_START]") < spliced.index("[SCENE_CONTENT_START:EP01_SC01]")
    assert "【主环境】客栈大堂" in spliced
    assert "drama body" in spliced
    assert "standardized beat" in spliced
    assert "split body" not in spliced

    mixed = enhance.replace(
        "[SCENE_ENV_IDENT_END:EP01_SC01]",
        "[SCENE_ENV_IDENT_END:EP01_SC01]\n[ENV_BLOCK_START]\n【主环境】旧稿\n[ENV_BLOCK_END]",
    )
    assert "【主环境】旧稿" not in strip_environment_planning_sections(mixed)


def test_assets_extraction_uses_scene_split_plus_per_scene_env():
    from app.core.prompt_injection import wrap_injection_section
    from app.services.script_analysis_flow import resolve_assets_extraction_source_text

    split_only = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
【场景名称】客栈
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]"""
    planned = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
【场景名称】客栈
[ENV_BLOCK_START]
【主环境】客栈大堂
[ENV_BLOCK_END]
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]"""

    assert resolve_assets_extraction_source_text(planned, "") == planned
    assert resolve_assets_extraction_source_text(split_only, planned) == planned

    wrapped_split = "\n\n".join(
        (
            "请执行第二阶段的第一步",
            wrap_injection_section("优化后剧本", split_only),
        )
    )
    resolved = resolve_assets_extraction_source_text(wrapped_split, planned)
    assert "[ENV_BLOCK_START]" in resolved
    assert "【主环境】客栈大堂" in resolved
    assert "[优化后剧本开始]" in resolved
    assert "请执行第二阶段的第一步" in resolved

    framed = planned.replace(
        "[ENV_BLOCK_END]",
        "────【衍生环境】────\n- `0度客栈大堂`\n[ENV_BLOCK_END]",
    )
    assert "【衍生环境】" in resolve_assets_extraction_source_text(planned, framed)
