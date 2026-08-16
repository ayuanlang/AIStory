# -*- coding: utf-8 -*-
from app.services.script_analysis_llm_config import _select_script_analysis_api_order
from app.services.subject_index_resolve import (
    _script_optimization_has_project_visual_backfill,
    extract_project_visual_backfill_object,
    merge_project_visual_backfill_into_result_text,
)


def test_visual_backfill_missing_when_empty_or_heading_only():
    assert _script_optimization_has_project_visual_backfill("") is False
    assert _script_optimization_has_project_visual_backfill("### 第三部分：Project Visual Backfill") is False
    assert extract_project_visual_backfill_object('{"project_visual_backfill": {') is None


def test_visual_backfill_detects_parseable_json():
    text = """
[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
hello
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]

### 第三部分：Project Visual Backfill
```json
{
  "project_visual_backfill": {
    "Global_Style": "live-action urban realism",
    "borrowed_films": ["电影A"],
    "tone": "冷峻",
    "color_spectrum": "冷调主导｜依据：对标电影A"
  }
}
```
"""
    obj = extract_project_visual_backfill_object(text)
    assert obj is not None
    assert obj["Global_Style"] == "live-action urban realism"
    assert _script_optimization_has_project_visual_backfill(text) is True


def test_merge_replaces_trailing_incomplete_section():
    source = "[SCENES_BLOCK_START]\nscene\n[SCENES_BLOCK_END]\n\n### 第三部分：Project Visual Backfill\nbroken"
    merged = merge_project_visual_backfill_into_result_text(
        source,
        {"Global_Style": "anime", "color_spectrum": "暖调主导｜依据：对标片"},
    )
    assert "[SCENES_BLOCK_START]" in merged
    assert "broken" not in merged
    obj = extract_project_visual_backfill_object(merged)
    assert obj["Global_Style"] == "anime"


def test_script_analysis_fallback_api_is_next_dropdown_id():
    primary, fallbacks = _select_script_analysis_api_order([10, 20, 30], 10)
    assert primary == 10
    assert fallbacks == [20, 30]
