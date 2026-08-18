# -*- coding: utf-8 -*-
from app.services.script_analysis_flow import parse_scene_units_from_markers


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
