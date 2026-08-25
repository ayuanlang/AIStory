# -*- coding: utf-8 -*-
from types import SimpleNamespace

from app.core.entity_token import subject_compare_key
from app.services.shot_generation_prompts import _build_scene_subject_image_prompts_cn_section


def _env(**kwargs):
    defaults = {
        "id": 0,
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


def _keys(*names):
    return {subject_compare_key(name) for name in names}


def test_merge_derived_envs_that_share_one_main():
    main = _env(id=1, name="客栈大堂", generation_prompt_cn="四宫格：左上大门 右上柜台")
    d0 = _env(id=2, name="0度客栈大堂", visual_dependencies=["ENV:[客栈大堂]"], base_name_en="客栈大堂")
    d180 = _env(id=3, name="180度客栈大堂", visual_dependencies=["ENV:[客栈大堂]"], base_name_en="客栈大堂")
    other_main = _env(id=4, name="后巷", generation_prompt_cn="窄巷夜灯")
    d_other = _env(id=5, name="0度后巷", visual_dependencies=["ENV:[后巷]"], base_name_en="后巷")

    text = _build_scene_subject_image_prompts_cn_section(
        [main, d0, d180, other_main, d_other],
        _keys("0度客栈大堂", "180度客栈大堂", "0度后巷"),
        scene_id=11,
    )

    assert "同一主环境族：主环境=ENV:[客栈大堂]" in text
    assert "本场使用的衍生环境=ENV:[0度客栈大堂]、ENV:[180度客栈大堂]" in text
    assert "明确：以上衍生环境对应同一个主环境=ENV:[客栈大堂]" in text
    assert text.count("四宫格：左上大门 右上柜台") == 1
    assert text.count("窄巷夜灯") == 1
    assert "当前场景使用的衍生环境=ENV:[0度后巷]" in text
    assert "对应主环境=ENV:[后巷]" in text
    assert "同一主环境族：主环境=ENV:[后巷]" not in text


def test_main_plus_derived_still_injects_prompt_once():
    main = _env(id=8, name="办公室", generation_prompt_cn="日光窗侧冷调")
    d0 = _env(
        id=9,
        name="0度办公室",
        visual_dependencies=["ENV:[办公室]"],
        custom_attributes={"main_environment": "办公室"},
    )
    d90 = _env(id=10, name="90度办公室", visual_dependencies=["ENV:[办公室]"])

    text = _build_scene_subject_image_prompts_cn_section(
        [main, d0, d90],
        _keys("办公室", "0度办公室", "90度办公室"),
        scene_id=12,
    )

    assert "同一主环境族：主环境=ENV:[办公室]" in text
    assert "本场亦使用该主环境" in text
    assert text.count("日光窗侧冷调") == 1
    assert "当前场景环境=ENV:[办公室]（主环境）" not in text


def test_standalone_main_keeps_single_row():
    main = _env(id=21, name="机库", generation_prompt_cn="金属舱壁冷白")
    text = _build_scene_subject_image_prompts_cn_section(
        [main],
        _keys("机库"),
        scene_id=13,
    )
    assert "当前场景环境=ENV:[机库]（主环境）" in text
    assert "同一主环境族" not in text
    assert "金属舱壁冷白" in text
