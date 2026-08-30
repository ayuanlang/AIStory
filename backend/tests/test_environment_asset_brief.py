# -*- coding: utf-8 -*-
from app.services.script_analysis_flow.character_asset_brief import (
    build_character_asset_design_brief,
    char_extract_has_items,
    current_world_identity,
    parse_char_extract_records,
    splice_char_extract_into_script,
)
from app.services.script_analysis_flow.environment_asset_brief import (
    build_environment_asset_design_brief,
    environment_plan_has_ident,
)
from app.services.script_analysis_flow.prop_asset_brief import (
    build_prop_asset_design_brief,
    prop_extract_has_items,
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
尺度=约一掌可握
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
    assert "约一掌可握" in brief
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


def test_char_brief_uses_extract_and_excludes_beats():
    script = _script_with_char_extract()
    brief = build_character_asset_design_brief(script)
    assert "[全局统筹角色提取开始]" in brief
    assert "[全局统筹角色提取结束]" in brief
    assert "沈青" in brief
    assert "右耳银环" in brief
    assert "对白声线=江湖黑话夹杂霸气直球" in brief
    assert "现时/轨迹/曾经" in brief
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


def test_char_brief_empty_when_extract_is_none():
    empty = """[CHAR_EXTRACT_START]
无
[CHAR_EXTRACT_END]
"""
    assert char_extract_has_items(empty) is False
    assert build_character_asset_design_brief(empty) == ""
    assert build_character_asset_design_brief("") == ""


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
