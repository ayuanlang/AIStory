# -*- coding: utf-8 -*-
from pathlib import Path

from app.services.project_season import classify_project_season, format_project_season_prompt
from app.services.story_generator_llm import (
    _CREATIVE_INPUT_STRUCTURE_KEYS,
    format_story_creative_input_block,
)


def test_locked_bilingual_season_overrides_saved_project():
    info = classify_project_season("秋 / Autumn")
    assert info["tier"] == "locked"
    assert info["season"] == "秋"
    block = format_project_season_prompt("夏 / Summer", {"season_occurrence": "冬 / Winter"})
    assert "档=已锁" in block
    assert "季=夏" in block
    assert "季=冬" not in block


def test_year_and_open_seasons():
    assert "档=全年" in format_project_season_prompt("全年 / All Seasons")
    assert "档=未锁" in format_project_season_prompt("不限制 / No Limit")
    assert "季=冬" in format_project_season_prompt("", {"basic_information": {"season_occurrence": "冬 / Winter"}})
    assert classify_project_season("秋季")["season"] == "秋"


def test_prefill_and_prompts_carry_season_and_ai_vfx():
    assert "ai_vfx_strategy" in _CREATIVE_INPUT_STRUCTURE_KEYS
    block = format_story_creative_input_block({"ai_vfx_strategy": "拍=14｜特效=满幅异象"})
    assert "AI优势应用与劣势回避" in block
    assert "拍=14" in block

    root = Path(__file__).resolve().parents[1] / "app" / "core" / "prompts"
    structure = (root / "story_generator_structure_creative_input.txt").read_text(encoding="utf-8")
    architect = (root / "master_story_architect.md").read_text(encoding="utf-8")
    writer = (root / "master_episode_writer.md").read_text(encoding="utf-8")
    assert "ai_vfx_strategy" in structure
    chain = "项目信息 → 剧本结构化预填 → 剧本框架 → 剧本生成"
    assert chain in structure
    assert chain in architect
    assert chain in writer
    assert "【项目季节 — 必须应用】" in structure
    assert "【项目季节 — 必须应用】" in architect
    assert "AI优势应用与劣势回避" in architect
    assert "【项目季节 — 必须应用】" in writer
    assert "继承=项目季节" in writer
    assert "不得用项目季节改掉框架或预填已经写明的另一季" in writer
