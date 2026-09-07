# -*- coding: utf-8 -*-
from app.services.analyze_scene_subject_checks import (
    _collect_missing_generation_prompt_cn,
    _detect_prompt_template_syntax_warnings,
    _is_empty_generation_prompt_cn,
)
from app.services.scene_subject_helpers import _extract_subjects_json_from_text
from app.services.video_submit_dedup import ANALYSIS_PROMPT_TEMPLATE_SYNTAX_RULES


TRUNCATED_CHARACTER_JSON = """```json
{
  "characters": [
    {
      "subject_no": "S001",
      "name": "朵朵",
      "name_en": "Duo Duo",
      "base_name_en": "Duo Duo",
      "description_cn": "",
      "gender": "F",
      "role": "Orphan",
      "archetype": "娇俏慌乱的脸庞，十指在虚拟键盘上疯狂敲击",
      "appearance_cn": "三维动画风格化渲染。约11岁中国女孩，身高135cm。",
      "clothing": "播出安全等级：非成人。服色散：主色=深渊黑｜辅色=科技紫｜点缀=霓虹青、泡泡糖粉｜色数=4｜档=中（机灵毒舌的赛博孤女）。借鉴=时装｜风格=赛博朋克｜落点=不对称机能分割、肩甲或外骨骼插件、线缆/导管外露、夜光滚边或缝线灯、
"""


def test_empty_description_cn_is_allowed_when_generation_prompt_cn_exists():
    payload = {
        "characters": [
            {
                "subject_no": "S001",
                "name": "朵朵",
                "name_en": "Duo Duo",
                "base_name_en": "Duo Duo",
                "description_cn": "",
                "gender": "F",
                "role": "Orphan",
                "archetype": "娇俏慌乱",
                "appearance_cn": "约11岁中国女孩",
                "clothing": "赛博机能外套",
                "action_characteristics": "敲击键盘",
                "generation_prompt_cn": "三维动画风格化渲染。约11岁中国女孩，黑色双丸子头。",
                "generation_prompt_en": "",
                "negative_prompt_en": "low quality",
                "anchor_description": "正面定妆",
                "visual_dependencies": [],
                "dependency_strategy": {"type": "BaselineDefinition", "logic": "主稿"},
            }
        ],
        "props": [],
        "environments": [],
    }
    meta = _detect_prompt_template_syntax_warnings(
        "",
        ANALYSIS_PROMPT_TEMPLATE_SYNTAX_RULES,
        payload,
        sections=["characters"],
    )
    assert meta["missing_generation_prompt_cn"] == []
    assert "ANALYSIS_GENERATION_PROMPT_CN_MISSING" not in meta["warning_codes"]


def test_missing_generation_prompt_cn_is_reported():
    payload = {
        "characters": [
            {
                "subject_no": "S001",
                "name": "朵朵",
                "description_cn": "",
                "appearance_cn": "约11岁中国女孩",
                "clothing": "赛博机能外套",
                "generation_prompt_cn": "",
            }
        ],
        "props": [
            {
                "name": "全息键盘",
                "generation_prompt_cn": "待补",
            }
        ],
        "environments": [
            {
                "name": "赛博公寓",
                "generation_prompt_cn": "……",
            }
        ],
    }
    missing = _collect_missing_generation_prompt_cn(payload)
    names = {(item["section"], item["name"]) for item in missing}
    assert names == {
        ("characters", "朵朵"),
        ("props", "全息键盘"),
        ("environments", "赛博公寓"),
    }

    meta = _detect_prompt_template_syntax_warnings(
        "",
        ANALYSIS_PROMPT_TEMPLATE_SYNTAX_RULES,
        payload,
        sections=["characters", "props", "environments"],
    )
    assert "ANALYSIS_GENERATION_PROMPT_CN_MISSING" in meta["warning_codes"]
    assert any("generation_prompt_cn" in warn for warn in meta["warnings"])


def test_truncated_character_json_without_prompt_cn_is_caught_via_parsed_payload():
    subjects_json = _extract_subjects_json_from_text(TRUNCATED_CHARACTER_JSON)
    characters = subjects_json.get("characters") or []
    assert characters
    assert characters[0].get("name") == "朵朵"

    raw_only = _detect_prompt_template_syntax_warnings(
        TRUNCATED_CHARACTER_JSON,
        ANALYSIS_PROMPT_TEMPLATE_SYNTAX_RULES,
    )
    parsed = _detect_prompt_template_syntax_warnings(
        TRUNCATED_CHARACTER_JSON,
        ANALYSIS_PROMPT_TEMPLATE_SYNTAX_RULES,
        subjects_json,
        sections=["characters"],
    )
    assert parsed["missing_generation_prompt_cn"]
    assert parsed["missing_generation_prompt_cn"][0]["name"] == "朵朵"
    assert "ANALYSIS_GENERATION_PROMPT_CN_MISSING" in parsed["warning_codes"]
    # Raw json.loads cannot see the truncated object; the check must use salvaged subjects_json.
    assert raw_only["missing_generation_prompt_cn"] == []


def test_placeholder_generation_prompt_cn_is_empty():
    assert _is_empty_generation_prompt_cn("")
    assert _is_empty_generation_prompt_cn("待补")
    assert _is_empty_generation_prompt_cn("停止成稿")
    assert _is_empty_generation_prompt_cn("…")
    assert not _is_empty_generation_prompt_cn("三维动画风格化渲染。约11岁中国女孩。")
