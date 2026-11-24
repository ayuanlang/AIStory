# -*- coding: utf-8 -*-
from app.services.script_analysis_flow_runner import (
    asset_design_json_complete,
    asset_design_roster_gap,
    build_asset_design_supplement_payload,
    collect_complete_asset_design_items,
)


def test_truncated_environment_fence_is_incomplete():
    text = """先写思考。
```json
{
  "environments": [
    {
      "name": "都市街区与高空走廊",
      "generation_prompt_cn": "【定位】场所风格=现代街巷｜引用====
"""
    assert asset_design_json_complete(text, "asset_design_environment") is False


def test_closed_environment_json_with_both_roots_is_complete():
    text = """```json
{"environments": [{"name": "街"}], "posters": []}
```"""
    assert asset_design_json_complete(text, "asset_design_environment") is True


def test_closed_environment_json_without_posters_is_incomplete():
    text = '{"environments": []}'
    assert asset_design_json_complete(text, "asset_design_environment") is False


def test_prefix_object_does_not_count_when_the_rest_is_cut():
    text = '{"characters": [{"name": "甲"}]}\n{"characters": ['
    assert asset_design_json_complete(text, "asset_design_character") is False


def test_character_prop_and_quad_roots():
    assert asset_design_json_complete('{"characters": []}', "asset_design_character") is True
    assert asset_design_json_complete('{"props": []}', "asset_design_prop") is True
    assert asset_design_json_complete('{"environments": []}', "asset_design_environment_quad") is True
    assert asset_design_json_complete('{"props": []}', "asset_design_character") is False


def test_truncated_array_keeps_each_closed_object():
    text = """```json
{"environments": [
  {"name": "甲街", "generation_prompt_cn": "完整甲"},
  {"name": "乙巷", "generation_prompt_cn": "完整乙"},
  {"name": "丙坡", "generation_prompt_cn": "没写完
"""
    found, arrays_closed, document_closed = collect_complete_asset_design_items(
        text,
        "asset_design_environment",
    )
    assert [row["name"] for row in found["environments"]] == ["甲街", "乙巷"]
    assert found["posters"] == []
    assert arrays_closed["environments"] is False
    assert document_closed is False


def test_closed_item_without_prompt_is_not_stored():
    text = '{"characters": [{"name": "甲"}, {"name": "乙", "generation_prompt_cn": "有"}]}'
    found, arrays_closed, document_closed = collect_complete_asset_design_items(
        text,
        "asset_design_character",
    )
    assert [row["name"] for row in found["characters"]] == ["乙"]
    assert arrays_closed["characters"] is True
    assert document_closed is True


def test_roster_gap_is_only_the_unfinished_name():
    source = """
[ENV] 名称=甲街
[ENV_BLOCK_START]
【主环境】甲街
[ENV_BLOCK_END]
[ENV] 名称=乙巷
[ENV_BLOCK_START]
【主环境】乙巷
[ENV_BLOCK_END]
"""
    accumulated = {
        "environments": {"甲街": {"name": "甲街", "generation_prompt_cn": "完整甲"}},
        "posters": {},
    }
    gap = asset_design_roster_gap(
        "asset_design_environment",
        source,
        accumulated,
        {"environments": False, "posters": False},
        False,
    )
    assert gap["missing_names"] == ["乙巷"]
    assert gap["needs_full_retry"] is False


def test_supplement_payload_omits_the_stored_character():
    source = "[CHAR_EXTRACT_START]\n[CHAR] 名称=甲街\n衣着=未写\n\n[CHAR] 名称=乙巷\n衣着=未写\n[CHAR_EXTRACT_END]"
    payload = build_asset_design_supplement_payload(
        "asset_design_character",
        {"text": source, "scene_analysis_features": {}},
        ["乙巷"],
        include_poster=False,
    )
    assert "名称=乙巷" in payload["text"]
    assert "名称=甲街" not in payload["text"]
    assert payload["scene_analysis_features"]["asset_design_only_names"] == ["乙巷"]
    assert payload["skip_episode_persist"] is True


def test_single_entity_rerun_does_not_treat_the_others_as_missing():
    source = "[CHAR_EXTRACT_START]\n[CHAR] 名称=甲\n\n[CHAR] 名称=乙\n[CHAR_EXTRACT_END]"
    gap = asset_design_roster_gap(
        "asset_design_character",
        source,
        {"characters": {"甲": {"name": "甲", "generation_prompt_cn": "有"}}},
        {"characters": True},
        True,
        single_name="甲",
    )
    assert gap["missing_names"] == []


def test_earlier_closed_fence_does_not_save_a_cut_off_reply():
    text = """```json
{"environments": [], "posters": []}
```
```json
{"environments": [{"generation_prompt_cn": "没写完
"""
    assert asset_design_json_complete(text, "asset_design_environment") is False
