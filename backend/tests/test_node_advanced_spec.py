# -*- coding: utf-8 -*-
from types import SimpleNamespace

from app.services.script_analysis_flow.node_advanced_spec import (
    format_node_advanced_spec_block,
    prepend_node_advanced_spec,
    resolve_flow_node_advanced_spec,
    resolve_storyboard_advanced_spec,
    resolve_subskill_advanced_spec,
)


def _episode():
    return SimpleNamespace(episode_info={
        "node_advanced_specs": {
            "scene_split": "全剧一场",
            "asset_design_character": "名牌只用职业",
            "asset_design_prop": "包必须提取",
            "drama_opt:EP01_SC01": "这场对白放慢",
            "storyboard:EP01_SC01": "开场先给全景",
            "blank": "   ",
        }
    })


def test_empty_spec_does_not_change_the_user_prompt():
    assert prepend_node_advanced_spec("正文", "") == "正文"
    assert prepend_node_advanced_spec("正文", "   ") == "正文"
    assert format_node_advanced_spec_block("") == ""


def test_spec_is_labeled_and_placed_before_the_user_prompt():
    merged = prepend_node_advanced_spec("待分析正文", "名牌只用职业")
    assert merged.index("必须满足的高级规格") < merged.index("待分析正文")
    assert "名牌只用职业" in merged
    assert "必须满足这些规格" in merged


def test_flow_node_spec_follows_the_node_and_reextract_target():
    episode = _episode()
    assert resolve_flow_node_advanced_spec(episode, node_key="scene_split") == "全剧一场"
    assert resolve_flow_node_advanced_spec(episode, node_key="environment_plan") == ""
    assert resolve_flow_node_advanced_spec(
        episode,
        node_key="scene_split",
        reextract_target="character",
    ) == "名牌只用职业"
    assert resolve_flow_node_advanced_spec(
        episode,
        node_key="scene_split",
        reextract_target="prop",
    ) == "包必须提取"


def test_scene_step_specs_are_separate():
    episode = _episode()
    assert resolve_subskill_advanced_spec(
        episode,
        prompt_file="skills/scene_analysis_feature_stack/scene_planning_1_subskill_drama_standardization.md",
        scene_id="EP01_SC01",
    ) == "这场对白放慢"
    assert resolve_subskill_advanced_spec(
        episode,
        prompt_file="skills/scene_analysis_feature_stack/scene_planning_1_subskill_combat.md",
        scene_id="EP01_SC01",
    ) == ""
    assert resolve_storyboard_advanced_spec(episode, "EP01_SC01") == "开场先给全景"
    assert resolve_storyboard_advanced_spec(episode, "") == ""


def test_row_and_scene_specs_join_the_node_spec():
    episode = _episode()
    episode.episode_info["node_advanced_specs"]["art_direction_row"] = "整排保持雨夜"
    episode.episode_info["node_advanced_specs"]["scene_rerun:EP01_SC01"] = "这一场只在店内"
    split_spec = resolve_flow_node_advanced_spec(episode, node_key="scene_split")
    assert split_spec.index("整排保持雨夜") < split_spec.index("全剧一场")
    assert "本排规格" in split_spec
    assert "本节点规格" in split_spec
    assert resolve_flow_node_advanced_spec(episode, node_key="environment_plan") == "整排保持雨夜"
    assert resolve_flow_node_advanced_spec(episode, node_key="script_optimization") == ""
    drama_spec = resolve_subskill_advanced_spec(
        episode,
        prompt_file="skills/scene_analysis_feature_stack/scene_planning_1_subskill_drama_standardization.md",
        scene_id="EP01_SC01",
    )
    assert drama_spec.index("这一场只在店内") < drama_spec.index("这场对白放慢")
    assert resolve_subskill_advanced_spec(
        episode,
        prompt_file="skills/scene_analysis_feature_stack/scene_planning_1_subskill_combat.md",
        scene_id="EP01_SC01",
    ) == "这一场只在店内"
    board_spec = resolve_storyboard_advanced_spec(episode, "EP01_SC01")
    assert "这一场只在店内" in board_spec
    assert "开场先给全景" in board_spec
    assert resolve_storyboard_advanced_spec(episode, "EP01_SC02") == ""
