# -*- coding: utf-8 -*-
from app.services.scene_subskill_pipeline_runner import (
    DRAMA_PROMPT,
    FRAMING_PROMPT,
    _strip_subskill_completion_marker,
)
from app.services.script_analysis_flow_runner import (
    MIN_SCOPED_NODE_BODY_CHARS,
    _merge_environment_patches,
    _strip_required_completion_marker,
    scoped_node_body_usable,
)


def test_scene_transition_header_accepts_join_alias():
    from app.services.script_analysis_flow import extract_scene_transition_block_from_scene_text

    legacy = """【场景切换与首节拍转场】
服饰换装：Serena从员工便服换为裙子
[BEAT_START:1]
beat
[BEAT_END:1]"""
    modern = """【场景衔接】上场=开场｜手法=硬切｜音画=无
[BEAT_START:1]
beat
[BEAT_END:1]"""
    assert "服饰换装" in extract_scene_transition_block_from_scene_text(legacy)
    assert "手法=硬切" in extract_scene_transition_block_from_scene_text(modern)


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


def test_environment_patches_strip_nested_scene_markers():
    from app.services.script_analysis_flow import parse_scene_units_from_markers

    split_text = """[SCENES_BLOCK_START]
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
[SCENES_BLOCK_END]"""
    patch_text = """[ENV_SCENE_PATCH_START:EP01_SC01]
[SCENE_START:EP1_SC01]
[SCENE_ENV_IDENT_START:EP01_SC01]
主环境=one
[SCENE_ENV_IDENT_END:EP01_SC01]
[ENV_BLOCK_START]
【主环境】room one
[ENV_BLOCK_END]
[SCENE_END:EP1_SC01]
[ENV_SCENE_PATCH_END:EP01_SC01]
[ENV_SCENE_PATCH_START:EP01_SC02]
[SCENE_ENV_IDENT_START:EP01_SC02]
主环境=two
[SCENE_ENV_IDENT_END:EP01_SC02]
[ENV_BLOCK_START]
【主环境】room two
[ENV_BLOCK_END]
[ENV_SCENE_PATCH_END:EP01_SC02]"""

    merged = _merge_environment_patches(split_text, patch_text)
    units = parse_scene_units_from_markers(merged)
    assert [unit.scene_id for unit in units] == ["EP01_SC01", "EP01_SC02"]
    assert merged.count("[SCENE_START:") == 2
    assert "[SCENE_START:EP1_SC01]" not in merged


def test_scoped_node_body_rejects_end_marker_only_or_short_stub():
    marker = "[ENVIRONMENT_PLAN_OUTPUT_END]"
    assert scoped_node_body_usable("") is False
    assert scoped_node_body_usable(marker) is False
    assert scoped_node_body_usable(_strip_required_completion_marker(marker, marker)) is False
    assert scoped_node_body_usable("x" * MIN_SCOPED_NODE_BODY_CHARS) is False
    assert scoped_node_body_usable("x" * (MIN_SCOPED_NODE_BODY_CHARS + 1)) is True
    short_with_marker = f"{'stub'}\n{marker}"
    assert scoped_node_body_usable(_strip_required_completion_marker(short_with_marker, marker)) is False


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
定位=继承原定义
目标=本场空镜须=建立夜内对峙压迫｜服务=无｜可见落点=大门与空椅
情绪表达=主情绪=压迫｜空镜表达=灯下空堂｜光色倾向=暖灯压暗｜构图倾向=纵深压迫
[ENV] 名称=马车内舱｜复用=否｜来源=新建｜匹配主环境=无｜依据=原文：“上车”
定位=载具内舱，窄小，密闭座舱
目标=本场空镜须=锁前向驾驶座舱｜服务=无｜可见落点=前窗与驾驶台
情绪表达=主情绪=紧张｜空镜表达=窄舱前窗｜光色倾向=夜窗冷渗｜构图倾向=框中框
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

    occupancy_reuse = """[SCENE_ENV_IDENT_START:EP11_SC02]
[ENV] 名称=豪华游艇甲板｜环境族=占用｜占用面型=露天合建｜复用=是｜来源=本集｜匹配主环境=豪华游艇甲板｜依据=原文：“浑身抽搐的瘫倒在甲板上。”
定位=继承原定义
[SCENE_ENV_IDENT_END:EP11_SC02]"""
    occupancy_items = parse_scene_env_ident_items(occupancy_reuse, "EP11_SC02")
    assert occupancy_items[0]["reuse"] is True
    assert occupancy_items[0]["source"] == "本集"
    assert occupancy_items[0]["matched_name"] == "豪华游艇甲板"
    assert scene_has_new_environments(occupancy_items) is False

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
    assert "原定义=" in injection
    planning_injection = build_project_main_environment_injection(catalog, for_planning=True)
    assert "环境规划必须先读本清单及原定义" in planning_injection
    assert "继承原定义" in planning_injection
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
    assert "全复用场仍须输出 SCENE_ENV_IDENT" in text
    empty = format_reuse_lock_instruction([])
    assert "待复用主环境=无" in empty
    assert "场景勘探后对照已注入的项目主环境" in empty
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
    assert "原定义=夜市内堂，柜台在180度侧" in detailed
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


def test_ident_only_reuse_patch_merges_before_scene_content():
    split_text = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC03]
【场景名称】回客栈
[SCENE_CONTENT_START:EP01_SC03]
original three
[SCENE_CONTENT_END:EP01_SC03]
[SCENE_END:EP01_SC03]
[SCENES_BLOCK_END]"""
    patch_text = """[ENV_SCENE_PATCH_START:EP01_SC03]
[SCENE_ENV_IDENT_START:EP01_SC03]
[ENV] 名称=客栈大堂｜复用=是｜来源=项目库｜匹配主环境=客栈大堂｜依据=原文：“回客栈”
[SCENE_ENV_IDENT_END:EP01_SC03]
[ENV_SCENE_PATCH_END:EP01_SC03]"""

    merged = _merge_environment_patches(split_text, patch_text)

    assert "[SCENE_ENV_IDENT_START:EP01_SC03]" in merged
    assert merged.index("【场景名称】回客栈") < merged.index("[SCENE_ENV_IDENT_START:EP01_SC03]")
    assert merged.index("[SCENE_ENV_IDENT_END:EP01_SC03]") < merged.index("[SCENE_CONTENT_START:EP01_SC03]")
    assert "original three" in merged
    assert "ENV_SCENE_PATCH_START" not in merged


def test_ident_and_env_block_merge_together():
    split_text = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
【场景名称】短名=one
[SCENE_CONTENT_START:EP01_SC01]
original one
[SCENE_CONTENT_END:EP01_SC01]
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]"""
    patch_text = """[ENV_SCENE_PATCH_START:EP01_SC01]
[SCENE_ENV_IDENT_START:EP01_SC01]
[ENV] 名称=room one｜复用=否｜来源=新建｜匹配主环境=无｜依据=原文：“室内”
[SCENE_ENV_IDENT_END:EP01_SC01]
[ENV_BLOCK_START]
【主环境】room one
[ENV_BLOCK_END]
[ENV_SCENE_PATCH_END:EP01_SC01]"""

    merged = _merge_environment_patches(split_text, patch_text)

    assert merged.index("【场景名称】") < merged.index("[SCENE_ENV_IDENT_START:EP01_SC01]")
    assert merged.index("[SCENE_ENV_IDENT_END:EP01_SC01]") < merged.index("[ENV_BLOCK_START]")
    assert merged.index("【主环境】room one") < merged.index("[SCENE_CONTENT_START:EP01_SC01]")
    assert "original one" in merged


def test_framing_waits_for_environment_plan_node_success():
    from app.services.scene_subskill_pipeline_runner import (
        environment_plan_ready_for_framing,
        environment_plan_terminal_without_payload,
        script_has_environment_blocks,
    )

    planned = "[ENV_BLOCK_START]\n【主环境】客栈大堂\n[ENV_BLOCK_END]"
    ident_only = (
        "[SCENE_ENV_IDENT_START:EP01_SC01]\n"
        "[ENV] 名称=龙门风月客栈内部｜复用=是｜来源=项目库｜匹配主环境=龙门风月客栈内部｜依据=复用\n"
        "[SCENE_ENV_IDENT_END:EP01_SC01]"
    )
    assert script_has_environment_blocks(planned)
    assert script_has_environment_blocks(ident_only)
    assert environment_plan_ready_for_framing("success", planned) is True
    assert environment_plan_ready_for_framing("warning", planned) is True
    assert environment_plan_ready_for_framing("success", ident_only) is True
    assert environment_plan_ready_for_framing("running", planned) is False
    assert environment_plan_ready_for_framing("queued", planned) is False
    assert environment_plan_ready_for_framing("", planned) is False
    assert environment_plan_ready_for_framing("success", "[SCENE_START:EP01_SC01]") is False
    assert environment_plan_terminal_without_payload("success", "", "") is True
    assert environment_plan_terminal_without_payload("running", "", "") is False
    assert environment_plan_terminal_without_payload("success", ident_only, "") is False


def test_reuse_ident_backfills_inherited_main_env_block():
    from app.services.scene_subskill_pipeline_runner import _ensure_reused_main_env_block

    ident_only = (
        "[SCENE_START:EP01_SC01]\n"
        "[SCENE_ENV_IDENT_START:EP01_SC01]\n"
        "[ENV] 名称=龙门风月客栈内部｜复用=是｜来源=项目库｜匹配主环境=龙门风月客栈内部｜依据=复用\n"
        "[SCENE_ENV_IDENT_END:EP01_SC01]\n"
        "[SCENE_CONTENT_START:EP01_SC01]\n"
        "对峙\n"
        "[SCENE_CONTENT_END:EP01_SC01]\n"
        "[SCENE_END:EP01_SC01]"
    )
    filled = _ensure_reused_main_env_block(ident_only, "EP01_SC01", [])
    assert "[ENV_BLOCK_START]" in filled
    assert "【主环境】龙门风月客栈内部" in filled
    assert filled.index("[SCENE_ENV_IDENT_END:EP01_SC01]") < filled.index("[ENV_BLOCK_START]")
    assert filled.index("[ENV_BLOCK_END]") < filled.index("[SCENE_CONTENT_START:EP01_SC01]")


def test_staging_splices_env_plan_scene_onto_drama_enhance():
    from app.services.scene_subskill_pipeline_runner import (
        extract_environment_planning_sections,
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
    extracted_env = extract_environment_planning_sections(env_scene)
    assert "[SCENE_ENV_IDENT_START:EP01_SC01]" in extracted_env
    assert "【主环境】客栈大堂" in extracted_env


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
