# -*- coding: utf-8 -*-
from types import SimpleNamespace

from app.services.shot_derived_subject_check import (
    check_shot_derived_subjects,
    filter_shot_locked_to_beats,
    slice_core_scene_to_beats,
)


def _env(**kwargs):
    defaults = {
        "id": 1,
        "type": "environment",
        "is_deleted": False,
        "name": "",
        "name_en": "",
        "generation_prompt_cn": "",
        "visual_dependencies": [],
        "base_name_en": None,
        "dependency_strategy": None,
        "custom_attributes": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


_CELL = (
    "【四向拼图】\n"
    "[0度格-左上·北]\n正面：[@溪心卧牛青石]（N-001）。\n"
    "[90度格-右上·东]\n正面：东窗。\n"
    "[180度格-左下·南]\n正面：南门。\n"
    "[270度格-右下·西]\n正面：西柜。\n"
)
_KITCHEN = (
    "【四向拼图】\n"
    "[0度格-左上·北]\n正面：[@黑色铸铁猛火双眼炒灶台]（N-001）。\n"
    "[90度格-右上·东]\n正面：东墙。\n"
    "[180度格-左下·南]\n正面：南门。\n"
    "[270度格-右下·西]\n正面：西柜。\n"
)


def test_slice_keeps_only_the_requested_beats():
    text = (
        "阶段：开场\n"
        "[BEAT_START:1]\n【建置】甲\n[BEAT_END:1]\n"
        "[BEAT_START:2]\n【建置】乙\n[BEAT_END:2]\n"
        "[BEAT_START:3]\n【建置】丙\n[BEAT_END:3]\n"
    )
    sliced = slice_core_scene_to_beats(text, [1, 3])
    assert "【建置】甲" in sliced
    assert "【建置】丙" in sliced
    assert "【建置】乙" not in sliced
    assert "阶段：开场" in sliced


def test_locked_guidance_drops_other_beats():
    body = "【卖点综合】卖点=对质\nBeat1｜【改编指导】甲\nBeat2｜【改编指导】乙\n"
    kept = filter_shot_locked_to_beats(body, [2])
    assert "卖点=对质" in kept
    assert "Beat2｜" in kept
    assert "Beat1｜" not in kept


def test_registered_anchor_passes_and_invented_light_fails():
    mountain = _env(id=1, name="山野", generation_prompt_cn=_CELL)
    kitchen = _env(id=2, name="厨房", generation_prompt_cn=_KITCHEN)
    d0 = _env(
        id=3,
        name="0度山野",
        visual_dependencies=["ENV:[山野]"],
        custom_attributes={"main_environment": "山野", "view_angle_from_main": 0},
    )
    d_kitchen = _env(
        id=4,
        name="0度厨房",
        visual_dependencies=["ENV:[厨房]"],
        custom_attributes={"main_environment": "厨房", "view_angle_from_main": 0},
    )
    cook = _env(id=5, type="character", name="老周")
    logic = (
        "Beat-Shot映射:合镜Beat=Beat1+Beat2｜Duration=8｜"
        "机位=溪心卧牛青石正前半空十步外→黑色铸铁猛火双眼炒灶台正前一掌贴身｜"
        "光影:源=ENV:[0度山野]→ENV:[0度厨房]｜天花内嵌LED平板照明灯冷白Key"
    )
    result = check_shot_derived_subjects(
        [mountain, kitchen, d0, d_kitchen, cook],
        shot_logic=logic,
        video_content="老周站在灶前。",
        scene_id=9,
    )
    names = [item["name"] for item in result["missing"]]
    assert result["ok"] is False
    assert "天花内嵌LED平板照明灯" in names
    assert "溪心卧牛青石" not in names
    assert "黑色铸铁猛火双眼炒灶台" not in names
    assert result["beat_ids"] == [1, 2]


def test_matching_shot_is_ok():
    kitchen = _env(id=2, name="厨房", generation_prompt_cn=_KITCHEN)
    derived = _env(
        id=4,
        name="0度厨房",
        visual_dependencies=["ENV:[厨房]"],
        custom_attributes={"main_environment": "厨房", "view_angle_from_main": 0},
    )
    logic = (
        "Beat-Shot映射:合镜Beat=Beat4｜Duration=4｜"
        "机位=黑色铸铁猛火双眼炒灶台正前一掌｜"
        "光影:源=ENV:[0度厨房]"
    )
    result = check_shot_derived_subjects(
        [kitchen, derived],
        shot_logic=logic,
        video_content="",
        scene_id=9,
    )
    assert result["missing"] == []
    assert result["ok"] is True
