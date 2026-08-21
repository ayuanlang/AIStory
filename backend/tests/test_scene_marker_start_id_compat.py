# -*- coding: utf-8 -*-
from app.services.script_analysis_flow import (
    build_scene_subskill_task_payloads,
    parse_scene_units_from_markers,
)
from app.services.scene_subskill_pipeline_runner import _extract_single_scene_block


def test_start_end_id_mismatch_uses_start_scene_id():
    script = """
[SCENES_BLOCK_START]
[SCENE_START:EP01_SC05]
scene five body
[SCENE_END:EP01_SC03]
[SCENE_START:EP01_SC06]
scene six body
[SCENE_END:EP01_SC06]
[SCENES_BLOCK_END]
"""
    units = parse_scene_units_from_markers(script)
    assert [u.scene_id for u in units] == ["EP01_SC05", "EP01_SC06"]
    assert units[0].scene_text == "scene five body"
    assert units[1].scene_text == "scene six body"


def test_matching_start_end_ids_still_parse():
    script = """
[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
one
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]
"""
    units = parse_scene_units_from_markers(script)
    assert len(units) == 1
    assert units[0].scene_id == "EP01_SC01"


def test_missing_outer_end_is_recovered_when_start_and_scene_pairs_exist():
    script = """
[SCENES_BLOCK_START]
[SCENE_START:EP01_SC01]
one
[SCENE_END:EP01_SC01]
"""
    units = parse_scene_units_from_markers(script)
    assert len(units) == 1
    assert units[0].scene_id == "EP01_SC01"
    assert units[0].scene_text == "one"


def test_missing_outer_wrappers_are_recovered_when_scene_pairs_exist():
    script = """
[SCENE_START:EP01_SC02]
two
[SCENE_END:EP01_SC02]
"""
    units = parse_scene_units_from_markers(script)
    assert len(units) == 1
    assert units[0].scene_id == "EP01_SC02"
    assert units[0].scene_text == "two"


def test_missing_outer_start_is_recovered_when_scene_pairs_and_end_exist():
    script = """
[COMPREHENSIVE_INFO_START]
overall plot
[COMPREHENSIVE_INFO_END]
[SCENE_START:EP01_SC01]
one
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]
"""
    units = parse_scene_units_from_markers(script)
    assert len(units) == 1
    assert units[0].scene_id == "EP01_SC01"
    assert units[0].scene_text == "one"


def test_special_routing_and_comprehensive_info_are_attached_to_scene_tasks():
    script = """
[SCENES_BLOCK_START]
[COMPREHENSIVE_INFO_START]
[INFO_ITEM_START:PLOT:1]
overall plot
[INFO_ITEM_END:PLOT:1]
[COMPREHENSIVE_INFO_END]
[SPECIAL_SCENE_ANALYSIS_START:EP01_SC01]
[VFX] 命中=是｜类型=近身打斗｜证据=原文：“挥拳”
[XIAN] 命中=否｜类型=无｜证据=无
[SPECIAL_SCENE_ANALYSIS_END:EP01_SC01]
[SCENE_START:EP01_SC01]
scene body
[SCENE_END:EP01_SC01]
[SCENES_BLOCK_END]
{"project_visual_backfill": {"tone": "tense"}}
"""
    units = parse_scene_units_from_markers(script)
    assert units[0].special_routing["VFX"]["hit"] is True
    assert units[0].special_routing["XIAN"]["hit"] is False
    assert "[COMPREHENSIVE_INFO_START]" in units[0].comprehensive_info

    tasks = build_scene_subskill_task_payloads(script)
    assert len(tasks) == 1
    assert tasks[0]["call_vfx"] is True
    assert tasks[0]["call_xian"] is False
    assert tasks[0]["special_analysis"].startswith("[SPECIAL_SCENE_ANALYSIS_START:EP01_SC01]")


def test_subskill_duplicate_readonly_metadata_is_replaced_by_authoritative_block():
    authoritative_special = """[SPECIAL_SCENE_ANALYSIS_START:EP01_SC03]
[VFX] 命中=否｜类型=无｜证据=无
[XIAN] 命中=否｜类型=无｜证据=无
[SPECIAL_SCENE_ANALYSIS_END:EP01_SC03]"""
    duplicated_output = f"""
[SCENES_BLOCK_START]
[COMPREHENSIVE_INFO_START]
first copy
[COMPREHENSIVE_INFO_END]
{authoritative_special}
{authoritative_special}
[SCENE_START:EP01_SC03]
optimized scene body
[SCENE_END:EP01_SC03]
[SCENES_BLOCK_END]
"""

    extracted = _extract_single_scene_block(
        duplicated_output,
        "EP01_SC03",
        authoritative_special,
    )

    assert extracted.count("[SPECIAL_SCENE_ANALYSIS_START:EP01_SC03]") == 1
    assert "[COMPREHENSIVE_INFO_START]" not in extracted
    assert "optimized scene body" in extracted
