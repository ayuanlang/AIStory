# -*- coding: utf-8 -*-
from app.services.script_analysis_flow.character_asset_brief import (
    assemble_character_asset_design_user_content,
    build_character_asset_design_brief,
    char_extract_has_items,
    char_extract_is_explicit_none,
    current_world_identity,
    first_text_with_char_extract,
    parse_char_extract_records,
    splice_char_extract_into_script,
)
from app.core.prompt_injection import wrap_injection_section
from app.services.script_analysis_flow.cover_poster_brief import build_cover_poster_brief
from app.services.script_analysis_flow.environment_asset_brief import (
    align_environment_json_names_with_ident,
    assemble_environment_asset_design_user_content,
    build_environment_asset_design_brief,
    collect_ident_environment_names,
    environment_plan_has_ident,
)
from app.services.script_analysis_flow.prop_asset_brief import (
    assemble_prop_asset_design_user_content,
    build_prop_asset_design_brief,
    first_text_with_prop_extract,
    prop_extract_has_items,
    prop_extract_is_explicit_none,
    splice_prop_extract_into_script,
)
from app.services.script_analysis_flow.registry import get_script_analysis_flow_registry


def _planned_script() -> str:
    return """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
【场景名称】客栈对峙
[SCENE_ENV_IDENT_START:EP01_SC01]
[ENV] 名称=客栈大堂｜复用=否｜来源=新建｜匹配主环境=无｜依据=原文：“大堂”
定位=夜内对峙大厅
目标=本场空镜须=建立压迫｜服务=无｜可见落点=大门与空椅
情绪表达=主情绪=压迫｜空镜表达=灯下空堂｜光色倾向=暖灯压暗｜构图倾向=纵深压迫
[SCENE_ENV_IDENT_END:EP01_SC01]
[ENV_BLOCK_START]
────【主环境】────
【主环境】客栈大堂；【活动空间】主舞台=堂心
────【未落环境实体清单】────
【未落环境实体清单】空椅
────【衍生环境】────
【衍生环境】0度客栈大堂
[ENV_BLOCK_END]
【场景综合】对峙开场
【卖点综合】美景
[BEAT_START:1]
这是不该进入环境设计简报的 Beat 正文。
[BEAT_END:1]
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]
"""


def test_environment_brief_uses_plan_only_and_excludes_scene_analysis():
    brief = build_environment_asset_design_brief(_planned_script())
    assert "[环境规划开始]" in brief
    assert "[环境规划结束]" in brief
    assert "客栈大堂" in brief
    assert "environments[].name 必须与 IDENT [ENV] 名称= / name 逐字符完全一致" in brief
    assert "定位=夜内对峙大厅" in brief
    assert "【主环境】客栈大堂" in brief
    assert "【未落环境实体清单】空椅" in brief
    assert "0度客栈大堂" not in brief
    assert "【场景综合】" not in brief
    assert "【卖点综合】" not in brief
    assert "不该进入环境设计简报" not in brief
    assert environment_plan_has_ident(_planned_script()) is True


def test_environment_brief_empty_without_plan():
    assert build_environment_asset_design_brief("") == ""
    assert environment_plan_has_ident("no ident here") is False


def test_environment_design_user_content_excludes_script_to_analyze():
    script = _planned_script()
    env_brief = build_environment_asset_design_brief(script)
    cover_brief = build_cover_poster_brief(script)
    leaked_script = wrap_injection_section("待分析剧本", f"Script to Analyze:\n\n{script}")
    composed = assemble_environment_asset_design_user_content(
        cover_brief,
        env_brief,
        leaked_script,
    )
    assert "[封面海报简报开始]" in composed
    assert "[环境规划开始]" in composed
    assert "客栈大堂" in composed
    assert "[待分析剧本开始]" not in composed
    assert "Script to Analyze:" not in composed
    assert "不该进入环境设计简报" not in composed


def test_environment_brief_reads_patches_outside_scene_split():
    merged = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
【场景名称】客栈对峙
[BEAT_START:1]
这是全局统筹正文，不应进入环境设计简报。
[BEAT_END:1]
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]

[ENV_SCENE_PATCH_START:EP01_SC01]
[SCENE_ENV_IDENT_START:EP01_SC01]
[ENV] 名称=客栈大堂｜复用=否｜来源=新建｜匹配主环境=无｜依据=原文：“大堂”
定位=夜内对峙大厅
目标=本场空镜须=建立压迫｜服务=无｜可见落点=大门与空椅
情绪表达=主情绪=压迫｜空镜表达=灯下空堂｜光色倾向=暖灯压暗｜构图倾向=纵深压迫
[SCENE_ENV_IDENT_END:EP01_SC01]
[ENV_BLOCK_START]
────【主环境】────
【主环境】客栈大堂｜日夜内外=夜·内｜主环境角色=当下主线
────【未落环境实体清单】────
【未落环境实体清单】空椅
[ENV_BLOCK_END]
[ENV_SCENE_PATCH_END:EP01_SC01]
"""
    brief = build_environment_asset_design_brief(merged)
    assert "[环境规划开始]" in brief
    assert "客栈大堂" in brief
    assert "定位=夜内对峙大厅" in brief
    assert "【主环境】客栈大堂" in brief
    assert "这是全局统筹正文" not in brief
    assert environment_plan_has_ident(merged) is True


def test_environment_brief_reads_reuse_ident_patch_without_env_block():
    patch = """[ENV_SCENE_PATCH_START:EP02_SC03]
[SCENE_ENV_IDENT_START:EP02_SC03]
[ENV] 名称=客栈大堂｜复用=是｜来源=项目库｜匹配主环境=客栈大堂｜依据=原文：“回客栈”
定位=继承原定义
目标=本场空镜须=复场承接｜服务=无｜可见落点=大门
情绪表达=主情绪=疲惫｜空镜表达=空堂夜灯｜光色倾向=暖灯｜构图倾向=中景
[SCENE_ENV_IDENT_END:EP02_SC03]
[ENV_SCENE_PATCH_END:EP02_SC03]
"""
    brief = build_environment_asset_design_brief(patch)
    assert "客栈大堂" in brief
    assert "定位=继承原定义" in brief
    assert environment_plan_has_ident(patch) is True


def test_environment_design_starts_from_environment_plan_only():
    registry = get_script_analysis_flow_registry()
    nodes = {str(node.get("key")): node for node in (registry.get("nodes") or [])}
    scene_split = nodes["scene_split"]
    env_plan = nodes["environment_plan"]
    env_design = nodes["asset_design_environment"]
    char_design = nodes["asset_design_character"]
    prop_design = nodes["asset_design_prop"]
    assets = nodes["assets_extraction"]
    scene_markdown = nodes["scene_markdown"]
    storyboard = nodes["storyboard_generation"]
    assert scene_split.get("fan_out") == [
        "environment_plan",
        "scene_subskill_pipeline",
        "asset_design_character",
        "asset_design_prop",
    ]
    assert env_plan.get("fan_out") == [
        "asset_design_environment",
    ]
    assert env_design.get("depends_on") == ["environment_plan"]
    assert char_design.get("depends_on") == ["scene_split"]
    assert prop_design.get("depends_on") == ["scene_split"]
    assert storyboard.get("depends_on") == [
        "scene_subskill_pipeline",
        "asset_design_environment",
    ]
    assert "scene_subskill_pipeline" not in (env_design.get("depends_on") or [])
    assert "assets_extraction" not in (env_design.get("depends_on") or [])
    assert "assets_extraction" not in (char_design.get("depends_on") or [])
    assert "assets_extraction" not in (prop_design.get("depends_on") or [])
    assert assets.get("enabled") is False
    assert scene_markdown.get("enabled") is False
    assert assets.get("fan_out") is None


def _script_with_prop_extract() -> str:
    return """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
【场景名称】客栈对峙
[SCENE_ENV_IDENT_START:EP01_SC01]
[ENV] 名称=客栈大堂｜复用=否｜来源=新建｜匹配主环境=无｜依据=原文：“大堂”
定位=夜内对峙大厅
目标=本场空镜须=建立压迫｜服务=无｜可见落点=大门与空椅
情绪表达=主情绪=压迫｜空镜表达=灯下空堂｜光色倾向=暖灯压暗｜构图倾向=纵深压迫
[SCENE_ENV_IDENT_END:EP01_SC01]
[ENV_BLOCK_START]
────【主环境】────
【主环境】客栈大堂；【活动空间】主舞台=堂心
────【未落环境实体清单】────
【未落环境实体清单】空椅
[ENV_BLOCK_END]
[BEAT_START:1]
这是不该进入道具设计简报的 Beat 正文。
[BEAT_END:1]
[SCENE_END:EP01_SC01]
[PROP_EXTRACT_START]
[PROP] 名称=银打火机｜名称_en=Silver Lighter｜全局性道具=是｜挂场ENV=客栈大堂
定位=男主随身火机，掌心可握，冷峻金属
作用=会谈时把玩
外形=扁长方形银色金属机身
尺度=长=1/2掌长｜高=1/3掌宽｜宽≈1/4掌厚
参照主体=名=成人男性手掌线性图｜长=1/2掌长｜高=1/3掌宽｜宽≈1/4掌厚｜依据=掌心把玩｜隔离=是
材质=银色金属
形态=按压火轮
情绪=主情绪=压迫｜挂场ENV=客栈大堂｜服化或材质响应=冷金属
适用场=EP01_SC01
[PROP_EXTRACT_END]
[SCENES_BLOCK_END]
"""


def test_prop_brief_uses_extract_and_excludes_beats():
    script = _script_with_prop_extract()
    brief = build_prop_asset_design_brief(script)
    assert "[全局统筹道具提取开始]" in brief
    assert "[全局统筹道具提取结束]" in brief
    assert "银打火机" in brief
    assert "道具资产设计真源" not in brief
    assert "长=1/2掌长" in brief
    assert "参照主体=名=成人男性手掌线性图" in brief
    assert "高=1/3掌宽" in brief
    assert "客栈大堂" in brief
    assert "不该进入道具设计简报" not in brief
    assert "【主环境】客栈大堂" not in brief
    assert prop_extract_has_items(script) is True


def test_prop_brief_empty_when_extract_is_none():
    empty = """[PROP_EXTRACT_START]
无
[PROP_EXTRACT_END]
"""
    assert prop_extract_has_items(empty) is False
    assert build_prop_asset_design_brief(empty) == ""
    assert build_prop_asset_design_brief("") == ""


def test_prop_extract_splices_before_scenes_block_end():
    script = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
body
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]
{"project_visual_backfill":{"tone":"cold"}}
"""
    extract = """[PROP_EXTRACT_START]
[PROP] 名称=玉佩｜名称_en=Jade Pendant
[PROP_EXTRACT_END]"""
    merged = splice_prop_extract_into_script(script, extract)
    assert merged.index("[PROP] 名称=玉佩") < merged.index("[SCENES_BLOCK_END]")
    assert merged.index("[SCENES_BLOCK_END]") < merged.index("project_visual_backfill")
    assert splice_prop_extract_into_script(merged, extract).count("[PROP_EXTRACT_START") == 1


def _script_with_char_extract() -> str:
    return """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
【场景名称】客栈对峙
[SCENE_ENV_IDENT_START:EP01_SC01]
[ENV] 名称=客栈大堂｜复用=否｜来源=新建｜匹配主环境=无｜依据=原文：“大堂”
[SCENE_ENV_IDENT_END:EP01_SC01]
[BEAT_START:1]
这是不该进入角色设计简报的 Beat 正文。
[BEAT_END:1]
[SCENE_END:EP01_SC01]
[CHAR_EXTRACT_START]
[CHAR] 名称=沈青｜名称_en=Shen Qing｜番位=男主｜适用场=EP01_SC01
定位=客栈对峙的冷峻掌柜
外形=瘦长、眉骨深
衣着=深色长袍；右耳银环
对白声线=江湖黑话夹杂霸气直球
[CHAR_EXTRACT_END]
[SCENES_BLOCK_END]
"""


def test_char_brief_rebuilds_from_loose_items_without_wrapper():
    script = """[SCENES_BLOCK_START]
[SCENE_END:EP01_SC01]
[CHAR] 名称=沈青｜名称_en=Shen Qing｜番位=男主
外形=瘦长
[CHAR] 名称=阿宁｜名称_en=A Ning｜番位=女主
外形=短发
[SCENES_BLOCK_END]
"""
    brief = build_character_asset_design_brief(script)
    assert "[CHAR_EXTRACT_START]" in brief
    assert "[CHAR_EXTRACT_END]" in brief
    assert "沈青" in brief
    assert "阿宁" in brief
    assert "瘦长" in brief
    assert char_extract_has_items(script) is True


def test_prop_brief_rebuilds_from_loose_items_without_wrapper():
    script = """[PROP] 名称=银打火机｜名称_en=Silver Lighter
外形=扁长方形银色金属机身
"""
    brief = build_prop_asset_design_brief(script)
    assert "[PROP_EXTRACT_START]" in brief
    assert "[PROP_EXTRACT_END]" in brief
    assert "银打火机" in brief
    assert prop_extract_has_items(script) is True


def test_char_brief_keeps_extract_start_tag_for_multiline_and_fullwidth():
    script = """[CHAR_EXTRACT_START]
[CHAR]
名称：沈青｜名称_en=Shen Qing
外形=瘦长
[CHAR_EXTRACT_END]
"""
    brief = build_character_asset_design_brief(script)
    assert "[CHAR_EXTRACT_START]" in brief
    assert "[CHAR_EXTRACT_END]" in brief
    assert "沈青" in brief
    assert char_extract_has_items(script) is True


def test_prop_brief_keeps_extract_start_tag_for_multiline_and_fullwidth():
    script = """[PROP_EXTRACT_START]
[PROP]
名称：银打火机｜名称_en=Silver Lighter
外形=扁长方形
[PROP_EXTRACT_END]
"""
    brief = build_prop_asset_design_brief(script)
    assert "[PROP_EXTRACT_START]" in brief
    assert "[PROP_EXTRACT_END]" in brief
    assert "银打火机" in brief
    assert prop_extract_has_items(script) is True


def test_char_brief_uses_extract_and_excludes_beats():
    script = _script_with_char_extract()
    brief = build_character_asset_design_brief(script)
    assert "[全局统筹角色提取开始]" in brief
    assert "[全局统筹角色提取结束]" in brief
    assert "沈青" in brief
    assert "右耳银环" in brief
    assert "对白声线=江湖黑话夹杂霸气直球" in brief
    assert "角色资产设计真源" not in brief
    assert "不该进入角色设计简报" not in brief
    assert "客栈大堂" not in brief
    assert char_extract_has_items(script) is True


def test_current_world_identity_strips_trajectory():
    assert current_world_identity(
        "现时=落寞寒门女眷｜轨迹=曾经富贵后落寞｜曾经=世家嫡女"
    ) == "落寞寒门女眷"
    assert current_world_identity("江湖侠客") == "江湖侠客"
    assert current_world_identity("无") == ""
    assert current_world_identity("") == ""


def test_char_design_user_content_excludes_script_and_prop_brief():
    script = _script_with_char_extract()
    char_brief = build_character_asset_design_brief(script)
    prop_brief = build_prop_asset_design_brief(_script_with_prop_extract())
    leaked_script = wrap_injection_section("待分析剧本", f"Script to Analyze:\n\n{script}")
    composed = assemble_character_asset_design_user_content(
        char_brief,
        prop_brief,
        leaked_script,
    )
    assert "[全局统筹角色提取开始]" in composed
    assert "沈青" in composed
    assert "[待分析剧本开始]" not in composed
    assert "Script to Analyze:" not in composed
    assert "[全局统筹道具提取开始]" not in composed
    assert "银打火机" not in composed
    assert "不该进入角色设计简报" not in composed


def test_prop_design_user_content_excludes_script_and_char_brief():
    script = _script_with_prop_extract()
    prop_brief = build_prop_asset_design_brief(script)
    char_brief = build_character_asset_design_brief(_script_with_char_extract())
    leaked_script = wrap_injection_section("待分析剧本", f"Script to Analyze:\n\n{script}")
    composed = assemble_prop_asset_design_user_content(
        prop_brief,
        char_brief,
        leaked_script,
    )
    assert "[全局统筹道具提取开始]" in composed
    assert "银打火机" in composed
    assert "[待分析剧本开始]" not in composed
    assert "Script to Analyze:" not in composed
    assert "[全局统筹角色提取开始]" not in composed
    assert "沈青" not in composed
    assert "不该进入道具设计简报" not in composed


def test_char_brief_empty_when_extract_is_none():
    empty = """[CHAR_EXTRACT_START]
无
[CHAR_EXTRACT_END]
"""
    assert char_extract_has_items(empty) is False
    assert char_extract_is_explicit_none(empty) is True
    assert build_character_asset_design_brief(empty) == ""
    assert build_character_asset_design_brief("") == ""
    assert first_text_with_char_extract(empty, _script_with_char_extract()) == ""


def test_prop_none_does_not_fall_back_to_previous_extract():
    empty = """[PROP_EXTRACT_START]
无
[PROP_EXTRACT_END]
"""
    previous = _script_with_prop_extract()
    assert prop_extract_is_explicit_none(empty) is True
    assert first_text_with_prop_extract(empty, previous) == ""
    assert build_prop_asset_design_brief(empty) == ""
    brief = build_prop_asset_design_brief(previous)
    assert "银打火机" in brief
    assert "道具资产设计真源" not in brief


def test_char_extract_splices_before_scenes_block_end():
    script = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
body
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]
{"project_visual_backfill":{"tone":"cold"}}
"""
    extract = """[CHAR_EXTRACT_START]
[CHAR] 名称=沈青｜名称_en=Shen Qing
[CHAR_EXTRACT_END]"""
    merged = splice_char_extract_into_script(script, extract)
    assert merged.index("[CHAR] 名称=沈青") < merged.index("[SCENES_BLOCK_END]")
    assert merged.index("[SCENES_BLOCK_END]") < merged.index("project_visual_backfill")
    assert splice_char_extract_into_script(merged, extract).count("[CHAR_EXTRACT_START") == 1


def test_trim_stage1_keeps_extracts_after_scenes_block_end():
    from app.services.script_analysis_flow.analyze_scene_stages import (
        _trim_stage1_adapted_script_body,
    )

    source = """[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
body
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]
{"project_visual_backfill":{"tone":"cold"}}
[CHAR_EXTRACT_START]
[CHAR] 名称=沈青｜名称_en=Shen Qing
[CHAR_EXTRACT_END]
[PROP_EXTRACT_START]
[PROP] 名称=玉佩｜名称_en=Jade Pendant
[PROP_EXTRACT_END]
"""
    trimmed = _trim_stage1_adapted_script_body(source)
    assert trimmed.index("[CHAR] 名称=沈青") < trimmed.index("[SCENES_BLOCK_END]")
    assert trimmed.index("[PROP] 名称=玉佩") < trimmed.index("[SCENES_BLOCK_END]")
    assert "project_visual_backfill" not in trimmed


def test_asset_design_does_not_require_subject_index():
    from app.services.script_analysis_flow.analyze_scene_stages import (
        resolve_analyze_scene_stage,
        should_require_subject_index,
    )

    env_stage = resolve_analyze_scene_stage(
        effective_scene_analysis_mode="2_pass_generate_assets_environments",
        prompt_file="skills/scene_analysis_feature_stack/entity_design_environment_and_poster.md",
    )
    char_stage = resolve_analyze_scene_stage(
        effective_scene_analysis_mode="2_pass_generate_assets_characters",
        prompt_file="skills/scene_analysis_feature_stack/entity_design_character.md",
    )
    beats_stage = resolve_analyze_scene_stage(
        effective_scene_analysis_mode="beats_generation",
        prompt_file="skills/scene_analysis_feature_stack/scene_planning_2_2_beats_generation.md",
    )
    assert env_stage.is_entity_design_phase is True
    assert should_require_subject_index(env_stage) is False
    assert should_require_subject_index(char_stage) is False
    assert should_require_subject_index(beats_stage) is False


def test_environment_plan_is_not_scoped_asset_design():
    from app.services.analyze_scene_text_ops import _resolve_scoped_asset_design_category
    from app.services.script_analysis_flow.analyze_scene_stages import resolve_analyze_scene_stage

    plan_stage = resolve_analyze_scene_stage(
        effective_scene_analysis_mode="stage1",
        prompt_file="skills/scene_analysis_feature_stack/scene_planning_1_subskill_environment.md",
        function_name="script_analysis",
    )
    assert plan_stage.is_entity_design_phase is False
    assert _resolve_scoped_asset_design_category(
        scene_analysis_mode="stage1",
        prompt_file="skills/scene_analysis_feature_stack/scene_planning_1_subskill_environment.md",
        action_name="环境规划",
    ) == ""
    assert _resolve_scoped_asset_design_category(
        scene_analysis_mode="environment_plan",
        prompt_file="skills/scene_analysis_feature_stack/scene_planning_1_subskill_environment.md",
        action_name="环境规划",
    ) == ""
    assert _resolve_scoped_asset_design_category(
        scene_analysis_mode="2_pass_generate_assets_environments",
        prompt_file="skills/scene_analysis_feature_stack/entity_design_environment_and_poster.md",
        action_name="环境/封面设计",
    ) == "environment"


def test_scoped_category_stays_exclusive_when_targets_include_siblings():
    from app.core.prompt_injection import strip_injection_section
    from app.services.analyze_scene_text_ops import _resolve_scoped_asset_design_category

    features = {
        "target_entity_types": ["characters", "props", "environments"],
        "asset_task_key": "characters",
    }
    assert _resolve_scoped_asset_design_category(
        scene_analysis_features=features,
        scene_analysis_mode="2_pass_generate_assets_characters__targets_characters_props_environments",
        prompt_file="skills/scene_analysis_feature_stack/entity_design_character.md",
    ) == "character"
    assert _resolve_scoped_asset_design_category(
        scene_analysis_features={"target_entity_types": ["characters", "props"], "asset_task_key": "props"},
        scene_analysis_mode="2_pass_generate_assets_props__targets_characters_props",
        prompt_file="skills/scene_analysis_feature_stack/entity_design_prop.md",
    ) == "prop"

    char_brief = build_character_asset_design_brief(_script_with_char_extract())
    composed = assemble_character_asset_design_user_content(char_brief)
    composed = strip_injection_section(composed, "待分析剧本")
    composed = strip_injection_section(composed, "全局统筹道具提取")
    assert "[全局统筹角色提取开始]" in composed
    assert "[CHAR_EXTRACT_START]" in composed
    assert "沈青" in composed


def test_character_brief_keeps_extract_only_request_text():
    extract_only = """[CHAR_EXTRACT_START]
[CHAR] 名称=沈青｜名称_en=Shen Qing｜番位=男主
外形=瘦长
[CHAR_EXTRACT_END]"""
    brief = build_character_asset_design_brief(extract_only)
    composed = assemble_character_asset_design_user_content(brief)
    assert "[全局统筹角色提取开始]" in composed
    assert "[CHAR_EXTRACT_START]" in composed
    assert "沈青" in composed
    assert "[待分析剧本开始]" not in composed


def test_prop_brief_keeps_extract_only_request_text():
    extract_only = """[PROP_EXTRACT_START]
[PROP] 名称=银打火机｜名称_en=Silver Lighter
外形=扁长方形银色金属机身
[PROP_EXTRACT_END]"""
    brief = build_prop_asset_design_brief(extract_only)
    composed = assemble_prop_asset_design_user_content(brief)
    assert "[全局统筹道具提取开始]" in composed
    assert "[PROP_EXTRACT_START]" in composed
    assert "银打火机" in composed
    assert "[待分析剧本开始]" not in composed


def test_collect_ident_environment_names_keeps_exact_spelling():
    names = collect_ident_environment_names(_planned_script())
    assert names == ["客栈大堂"]


def test_align_environment_json_names_with_ident_rewrites_near_miss():
    payload = {
        "environments": [
            {
                "name": "客栈 大堂",
                "generation_prompt_cn": "所属主环境=客栈 大堂。请按「客栈 大堂」四向拼图",
                "visual_dependencies": [],
            }
        ]
    }
    aligned = align_environment_json_names_with_ident(payload, _planned_script())
    assert aligned["environments"][0]["name"] == "客栈大堂"
    assert "所属主环境=客栈大堂" in aligned["environments"][0]["generation_prompt_cn"]
    assert "「客栈大堂」" in aligned["environments"][0]["generation_prompt_cn"]


def test_align_environment_json_names_with_ident_maps_single_synonym():
    payload = {
        "environments": [
            {
                "name": "客栈大厅",
                "generation_prompt_cn": "所属主环境=客栈大厅",
            }
        ]
    }
    aligned = align_environment_json_names_with_ident(payload, _planned_script())
    assert aligned["environments"][0]["name"] == "客栈大堂"
    assert aligned["environments"][0]["generation_prompt_cn"] == "所属主环境=客栈大堂"


def test_align_environment_json_names_skips_derived_rows():
    payload = {
        "environments": [
            {"name": "0度客栈大堂"},
            {"name": "客栈 大堂"},
        ]
    }
    aligned = align_environment_json_names_with_ident(payload, _planned_script())
    assert aligned["environments"][0]["name"] == "0度客栈大堂"
    assert aligned["environments"][1]["name"] == "客栈大堂"
