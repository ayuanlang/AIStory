# -*- coding: utf-8 -*-
from app.services.script_analysis_llm_config import _select_script_analysis_api_order
from app.services.subject_index_resolve import (
    _script_optimization_has_project_visual_backfill,
    build_project_visual_backfill_readonly_injection,
    extract_project_visual_backfill_object,
    merge_project_visual_backfill_into_result_text,
    strip_project_visual_backfill_sections,
)


def test_visual_backfill_missing_when_empty_or_heading_only():
    assert _script_optimization_has_project_visual_backfill("") is False
    assert _script_optimization_has_project_visual_backfill("### 第三部分：Project Visual Backfill") is False
    assert extract_project_visual_backfill_object('{"project_visual_backfill": {') is None


def test_visual_backfill_rejects_unrelated_tone_json_in_scene_body():
    text = """
[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
{"tone": "cold", "lighting": "soft", "plot_summary": "not the trailer"}
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]
"""
    assert extract_project_visual_backfill_object(text) is None
    assert _script_optimization_has_project_visual_backfill(text) is False


def test_visual_backfill_rejects_wrapper_without_global_style():
    text = """
[SCENES_BLOCK_END]

{"project_visual_backfill": {"tone": "cold", "lighting": "soft"}}
"""
    obj = extract_project_visual_backfill_object(text)
    assert obj is not None
    assert obj.get("tone") == "cold"
    assert _script_optimization_has_project_visual_backfill(text) is False


def test_visual_backfill_rejects_empty_global_style():
    text = '{"project_visual_backfill": {"Global_Style": "   ", "tone": "cold"}}'
    assert _script_optimization_has_project_visual_backfill(text) is False


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


def test_strip_leading_visual_backfill_keeps_scene_body():
    text = """```json
{
  "project_visual_backfill": {
    "Global_Style": "古典/古装",
    "music_recommendation": "风格=弦乐"
  }
}
```
[SCENE_START:EP01_SC01]
【宫格草稿】已写
【Beat主体定位】B1=甲=可见性=V
[DERIVED_ENV_EXTRACT_START]
[DERIVED_ENV:0度客栈]
[DERIVED_ENV_EXTRACT_END]
[SCENE_END:EP01_SC01]
[DERIVED_FRAMING_OUTPUT_END]
"""
    stripped = strip_project_visual_backfill_sections(text)
    assert "project_visual_backfill" not in stripped
    assert "[SCENE_START:EP01_SC01]" in stripped
    assert "【Beat主体定位】" in stripped
    assert "[DERIVED_FRAMING_OUTPUT_END]" in stripped


def test_readonly_injection_is_compact_and_not_json_dump():
    injection = build_project_visual_backfill_readonly_injection(
        {
            "Global_Style": "古典/古装",
            "music_recommendation": "节奏=慢板｜拍型指导=蓄压",
            "comprehensive_plot": "主线=对质",
        }
    )
    assert "项目视觉回填" in injection
    assert "Global_Style=古典/古装" in injection
    assert '"project_visual_backfill"' not in injection


def test_framing_gate_accepts_scene_after_stripping_leading_backfill():
    from app.services.scene_subskill_pipeline_runner import (
        _extract_single_scene_block,
        assert_derived_framing_ready_for_staging,
    )

    raw = """```json
{"project_visual_backfill": {"Global_Style": "古典/古装"}}
```
[SCENE_START:EP01_SC01]
【宫格草稿】0度格
【主体定位方案】甲=0度格
【Beat主体定位】B1=甲=可见性=V｜组=无
[DERIVED_ENV_EXTRACT_START]
[DERIVED_ENV:0度客栈大堂]
[DERIVED_ENV_EXTRACT_END]
[BEAT_STREAM_START]
[BEAT_START:1]
【取景锁定】当前环境=ENV:[0度客栈大堂]｜景别=MS｜构图=中景｜镜头角度=平视｜选择证据=原文:开场
[DERIVED_ENV:0度客栈大堂]
[BEAT_END:1]
[BEAT_STREAM_END]
[SCENE_END:EP01_SC01]
[DERIVED_FRAMING_OUTPUT_END]
"""
    from app.services.subject_index_resolve import strip_project_visual_backfill_sections

    cleaned = strip_project_visual_backfill_sections(raw)
    extracted = _extract_single_scene_block(cleaned, "EP01_SC01", "")
    ready = assert_derived_framing_ready_for_staging(extracted, "EP01_SC01")
    assert "【取景锁定】" in ready
    assert "project_visual_backfill" not in ready


def test_extract_adapted_script_ignores_leading_visual_backfill():
    from app.services.script_analysis_flow.analyze_scene_stages import (
        extract_stage1_adapted_script_body,
    )

    raw = """```json
{"project_visual_backfill": {"Global_Style": "古典/古装"}}
```
[SCENE_START:EP01_SC01]
现场编排正文
[SCENE_END:EP01_SC01]
"""
    body = extract_stage1_adapted_script_body(raw)
    assert "现场编排正文" in body
    assert "project_visual_backfill" not in body


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
