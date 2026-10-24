# -*- coding: utf-8 -*-
from app.schemas.episode_requests import StoryGeneratorRequest
from app.services.episode_script_prompt import build_structured_prefill_prompt_block
from app.services.prompt_resolve import _resolve_prompt_text
from app.services.script_mode_helpers import (
    _build_mandatory_writing_logic,
    _normalize_script_mode_key,
    build_emotion_driven_episode_coverage_block,
    is_emotion_driven_script_mode,
    is_global_story_framework_prompt,
    resolve_global_story_framework_prompt,
)
from app.services.story_generator_llm import format_story_creative_input_block


def test_emotion_driven_mode_does_not_fall_through_to_romance_or_series():
    label = "情绪驱动类 / Emotion-Driven"
    assert _normalize_script_mode_key(label) == "emotion_driven"
    assert is_emotion_driven_script_mode(label)
    assert not is_emotion_driven_script_mode("爱情情感 / Romance / Emotional")
    assert _normalize_script_mode_key("通用连续剧 / General Series") == "general_series"
    assert resolve_global_story_framework_prompt(label) == "emotion_driven_story_framework.md"
    assert resolve_global_story_framework_prompt("短剧快节奏 / Short Drama") == "master_story_architect.md"
    assert is_global_story_framework_prompt("emotion_driven_story_framework.md")
    assert is_global_story_framework_prompt("master_story_architect.md")


def test_emotion_driven_writing_logic_and_coverage_use_egri_steps():
    logic = _build_mandatory_writing_logic("情绪驱动类 / Emotion-Driven")
    assert "埃格里" in logic
    assert "冲突阶" in logic
    assert "禁止改走救猫咪" in logic
    block = build_emotion_driven_episode_coverage_block(8)
    assert "EP01–EP08" in block
    assert "冲突阶确认本集在完成哪一阶" in block
    assert "攻击点" in block
    assert "结局" in block
    assert "拍=Opening" not in block
    assert "禁止写成救猫咪拍" in block
    assert "故事环确认本集在走哪一步" in block
    assert "经典借鉴必须留下主框架" in block
    assert "不写故事环" not in block
    assert build_emotion_driven_episode_coverage_block(0) == ""


def test_emotion_driven_prefill_formats_egri_not_save_the_cat():
    source = {
        "script_mode": "情绪驱动类 / Emotion-Driven",
        "logline": "陈晓要页脚上的真名。",
        "egri_premise": "怕连累班组的人，经过署名冲突，会把真名留下。",
        "egri_01_attack": "陈晓把事故页按在桌上。",
        "story_circle": "你@攻击点：陈晓还相信页脚会自己对上。",
        "classic_framework": "主框架：《入殓师》— 论证：用一次署名选择证明怕连累的人会把名字留下。",
        "stc_01_opening_image": "不该出现的开场画面。",
    }
    block = format_story_creative_input_block(source)
    assert "上升冲突八阶" in block
    assert "阶01 攻击点" in block
    assert "陈晓把事故页按在桌上" in block
    assert "节拍01" not in block
    assert "不该出现的开场画面" not in block
    assert "[故事环]" in block
    assert "你@攻击点" in block
    assert "[经典借鉴]" in block
    assert "入殓师" in block
    episode = build_structured_prefill_prompt_block(source, trailer=False)
    assert "冲突阶" in episode
    assert "故事环" in episode
    assert "经典借鉴" in episode
    assert "已锁救猫咪拍" not in episode
    request = StoryGeneratorRequest(
        mode="global",
        script_mode=source["script_mode"],
        egri_premise=source["egri_premise"],
        story_circle=source["story_circle"],
    )
    assert request.egri_premise.startswith("怕连累")
    assert request.story_circle.startswith("你@攻击点")


def test_emotion_driven_skills_resolve_as_independent_prompts():
    structure = _resolve_prompt_text("emotion_driven_structure_prefill.txt")
    framework = _resolve_prompt_text("emotion_driven_story_framework.md")
    assert "埃格里" in structure
    assert "egri_01_attack" in structure
    assert "story_circle" in structure
    assert "经典借鉴" in structure
    assert "禁止改用救猫咪十五拍" in structure
    assert "冲突阶" in framework
    assert "故事环管分集" in framework
    assert "经典借鉴" in framework
    assert "### A)" not in framework.split("禁止输出")[0]
    assert "[EPISODE_BLOCK_START:EP01]" in framework
    default_framework = _resolve_prompt_text("master_story_architect.md")
    assert "救猫咪" in default_framework
    assert default_framework != framework
