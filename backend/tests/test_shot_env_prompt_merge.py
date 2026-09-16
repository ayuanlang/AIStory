# -*- coding: utf-8 -*-
from types import SimpleNamespace

from app.core.entity_token import subject_compare_key
from app.services.shot_generation_prompts import (
    _build_scene_subject_image_prompts_cn_section,
    collect_missing_main_env_prompt_names,
)


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
    d0 = _env(
        id=2,
        name="0度客栈大堂",
        visual_dependencies=["ENV:[客栈大堂]"],
        base_name_en="客栈大堂",
        custom_attributes={
            "main_environment": "客栈大堂",
            "view_angle_from_main": 0,
            "background": "柜台",
            "frame_left": "楼梯口",
            "frame_right": "账房窗",
        },
    )
    d180 = _env(
        id=3,
        name="180度客栈大堂",
        visual_dependencies=["ENV:[客栈大堂]"],
        base_name_en="客栈大堂",
        custom_attributes={
            "main_environment": "客栈大堂",
            "view_angle_from_main": 180,
            "background": "正门",
            "frame_left": "账房窗",
            "frame_right": "楼梯口",
        },
    )
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
    assert "【衍生环境信息】" in text
    assert "must not restate the environment plate" in text
    assert "【主环境整份 generation_prompt_cn｜开篇世界锁+四向拼图宫格；光线只读当前衍生度数对应格】" in text
    assert "【/主环境整份 generation_prompt_cn】" in text
    assert "Lighting control MUST follow the current derived-degree ENV" in text
    assert "光线控制只读当前拍衍生度数 ENV 对应宫格" in text
    assert "主环境 generation_prompt_cn=" not in text
    assert (
        "ENV:[0度客栈大堂]｜所属主环境=ENV:[客栈大堂]｜view_angle_from_main=0｜"
        "背景=柜台｜画左=楼梯口｜画右=账房窗"
    ) in text
    assert (
        "ENV:[180度客栈大堂]｜所属主环境=ENV:[客栈大堂]｜view_angle_from_main=180｜"
        "背景=正门｜画左=账房窗｜画右=楼梯口"
    ) in text
    assert "ENV:[0度后巷]｜所属主环境=ENV:[后巷]" in text


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
    assert "【衍生环境信息】" not in text


def test_missing_main_prompt_blocks_storyboard_injection():
    derived = _env(
        id=31,
        name="0度客栈大堂",
        visual_dependencies=["ENV:[客栈大堂]"],
        generation_prompt_cn="只切割宫格",
    )
    main_empty = _env(id=30, name="客栈大堂", generation_prompt_cn="")
    assert _build_scene_subject_image_prompts_cn_section(
        [main_empty, derived],
        _keys("0度客栈大堂"),
        scene_id=21,
    ) == ""
    missing = collect_missing_main_env_prompt_names([main_empty, derived], _keys("0度客栈大堂"))
    assert missing


def test_injects_full_main_env_prompt_with_grid_line_breaks():
    main = _env(
        id=40,
        name="客栈大堂",
        generation_prompt_cn=(
            "【六面一次】主光=斜阳｜辅光=天花散射｜Key世界向=东南\n"
            "【四向拼图】\n"
            "[0度格-左上·北] 开篇斜射金光从画面右、靠近镜头、低打来。影子投向画面左、远离镜头。\n"
            "[180度格-左下·南] 开篇斜阳从画面左、远离镜头、低打来。影子投向画面右、靠近镜头。"
        ),
    )
    derived = _env(
        id=41,
        name="180度客栈大堂",
        visual_dependencies=["ENV:[客栈大堂]"],
        custom_attributes={"main_environment": "客栈大堂", "view_angle_from_main": 180},
    )
    text = _build_scene_subject_image_prompts_cn_section(
        [main, derived],
        _keys("180度客栈大堂"),
        scene_id=22,
    )
    assert "[0度格-左上·北]" in text
    assert "[180度格-左下·南]" in text
    assert "\n[180度格-左下·南]" in text
    assert "开篇斜阳从画面左、远离镜头、低打来。" in text
    flattened = " ".join(main.generation_prompt_cn.split())
    assert f"主环境 generation_prompt_cn={flattened}" not in text
