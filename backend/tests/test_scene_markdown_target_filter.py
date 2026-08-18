# -*- coding: utf-8 -*-
from app.services.script_analysis_flow import (
    ParsedSceneUnit,
    coerce_target_scene_ids_for_orchestration,
    filter_scene_units_by_target_ids,
)


def _unit(scene_id, scene_order):
    return ParsedSceneUnit(
        scene_id=scene_id,
        scene_order=scene_order,
        scene_text=f"[{scene_id}]",
        marker_start_token=f"[SCENE_START:{scene_id}]",
        marker_end_token=f"[SCENE_END:{scene_id}]",
    )


def test_coerce_target_scene_ids_from_payload_and_instruction():
    assert coerce_target_scene_ids_for_orchestration(
        {"target_scene_ids": ["EP01_SC02", "EP01_SC02"]},
        "",
    ) == ["EP01_SC02"]
    assert coerce_target_scene_ids_for_orchestration(
        {"target_scene_id": "EP01_SC03"},
        "",
    ) == ["EP01_SC03"]
    assert coerce_target_scene_ids_for_orchestration(
        {},
        "【单场处理模式】本次仅处理 Scene ID `EP01_SC04`。输入剧本正文含该场",
    ) == ["EP01_SC04"]
    assert coerce_target_scene_ids_for_orchestration({}, "no target here") == []


def test_filter_scene_units_keeps_only_requested_scene():
    units = [
        _unit("EP01_SC01", 1),
        _unit("EP01_SC02", 2),
        _unit("EP01_SC03", 3),
    ]
    matched = filter_scene_units_by_target_ids(units, ["EP01_SC02"], episode_prefix="EP01")
    assert [item.scene_id for item in matched] == ["EP01_SC02"]


def test_filter_scene_units_accepts_numeric_alias():
    units = [
        _unit("EP01_SC01", 1),
        _unit("EP01_SC02", 2),
    ]
    matched = filter_scene_units_by_target_ids(units, ["2"], episode_prefix="EP01")
    assert [item.scene_id for item in matched] == ["EP01_SC02"]
