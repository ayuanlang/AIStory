# -*- coding: utf-8 -*-
from types import SimpleNamespace

from app.core.entity_token import subject_compare_key
from app.services.shot_generation_prompts import (
    _build_scene_subject_image_prompts_cn_section,
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


def test_injects_only_derived_env_info_for_scene_views():
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

    assert "【衍生环境信息】" in text
    assert "本场只注入用到的衍生环境信息" in text
    assert "四宫格：左上大门 右上柜台" not in text
    assert "窄巷夜灯" not in text
    assert "【主环境整份 generation_prompt_cn" not in text
    assert "同一主环境族" not in text
    assert "背景=柜台" not in text
    assert "ENV:[0度客栈大堂]｜所属主环境=ENV:[客栈大堂]｜view_angle_from_main=0" in text
    assert "ENV:[180度客栈大堂]｜所属主环境=ENV:[客栈大堂]｜view_angle_from_main=180" in text
    assert "ENV:[0度后巷]｜所属主环境=ENV:[后巷]" in text


def test_scene_that_also_names_the_main_still_omits_its_prompt():
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

    assert "日光窗侧冷调" not in text
    assert "本场亦使用该主环境" not in text
    assert "ENV:[0度办公室]｜所属主环境=ENV:[办公室]" in text
    assert "ENV:[90度办公室]｜所属主环境=ENV:[办公室]" in text
    assert "ENV:[办公室]｜所属主环境" not in text


def test_standalone_main_injects_nothing():
    main = _env(id=21, name="机库", generation_prompt_cn="金属舱壁冷白")
    text = _build_scene_subject_image_prompts_cn_section(
        [main],
        _keys("机库"),
        scene_id=13,
    )
    assert text == ""
    assert "金属舱壁冷白" not in text


def test_empty_main_prompt_still_injects_derived_info():
    derived = _env(
        id=31,
        name="0度客栈大堂",
        visual_dependencies=["ENV:[客栈大堂]"],
        generation_prompt_cn="只切割宫格",
        custom_attributes={"main_environment": "客栈大堂", "background": "柜台"},
    )
    main_empty = _env(id=30, name="客栈大堂", generation_prompt_cn="")
    text = _build_scene_subject_image_prompts_cn_section(
        [main_empty, derived],
        _keys("0度客栈大堂"),
        scene_id=21,
    )
    assert "ENV:[0度客栈大堂]｜所属主环境=ENV:[客栈大堂]" in text
    assert "背景=柜台" not in text
    assert "只切割宫格" not in text
    assert "【主环境整份 generation_prompt_cn" not in text


def test_injects_only_the_matching_quad_cell():
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
        generation_prompt_cn="只保留左下180度格，另外三格整块删除。",
        custom_attributes={"main_environment": "客栈大堂", "view_angle_from_main": 180},
    )
    text = _build_scene_subject_image_prompts_cn_section(
        [main, derived],
        _keys("180度客栈大堂"),
        scene_id=22,
    )
    assert "[180度格-左下·南]" in text
    assert "开篇斜阳从画面左、远离镜头、低打来。" in text
    assert "[0度格-左上·北]" not in text
    assert "开篇斜射金光从画面右、靠近镜头、低打来。" not in text
    assert "【六面一次】" not in text
    assert "只保留左下180度格" not in text
    assert "ENV:[180度客栈大堂]｜所属主环境=ENV:[客栈大堂]｜view_angle_from_main=180" in text


def test_injects_only_the_color_plan_line_from_the_main_prompt():
    main = _env(
        id=50,
        name="客栈大堂",
        generation_prompt_cn=(
            "【光学说明】主光=斜阳\n"
            "色光规划=本块对标片=英雄｜主冷暖=暖调主导｜光质=低斜阳｜主色=沙金\n"
            "【四向拼图】[0度格-左上·北] 开篇斜射金光"
        ),
    )
    other = _env(
        id=51,
        name="后巷",
        generation_prompt_cn="色光规划=本块对标片=七宗罪｜主冷暖=冷调主导｜光质=街灯",
    )
    derived = _env(
        id=52,
        name="0度客栈大堂",
        visual_dependencies=["ENV:[客栈大堂]"],
        custom_attributes={"main_environment": "客栈大堂", "background": "柜台"},
    )
    text = _build_scene_subject_image_prompts_cn_section(
        [main, other, derived],
        _keys("0度客栈大堂"),
        scene_id=23,
    )
    assert "【本场环境色光】" in text
    assert "ENV:[客栈大堂]｜色光规划=本块对标片=英雄｜主冷暖=暖调主导｜光质=低斜阳｜主色=沙金" in text
    assert "七宗罪" not in text
    assert "【光学说明】" not in text
    assert "[0度格-左上·北]" in text
    assert "开篇斜射金光" in text


def test_ninety_degree_view_uses_the_east_cell_only():
    main = _env(
        id=60,
        name="客栈大堂",
        generation_prompt_cn=(
            "【四向拼图】\n"
            "[0度格-左上·北]\n正面：大门。\n"
            "[90度格-右上·东]\n正面：东窗。左侧面：柜台。\n"
            "[180度格-左下·南]\n正面：南门。\n"
            "[270度格-右下·西]\n正面：西柜。\n"
        ),
    )
    derived = _env(
        id=61,
        name="90度客栈大堂",
        visual_dependencies=["ENV:[客栈大堂]"],
        generation_prompt_cn="待生成",
        custom_attributes={"main_environment": "客栈大堂", "view_angle_from_main": 90},
    )
    text = _build_scene_subject_image_prompts_cn_section(
        [main, derived],
        _keys("90度客栈大堂"),
        scene_id=24,
    )
    assert "[90度格-右上·东]" in text
    assert "正面：东窗。左侧面：柜台。" in text
    assert "[0度格-左上·北]" not in text
    assert "正面：大门" not in text
    assert "[180度格-左下·南]" not in text
    assert "[270度格-右下·西]" not in text
    assert "待生成" not in text
    assert "ENV:[90度客栈大堂]｜所属主环境=ENV:[客栈大堂]｜view_angle_from_main=90" in text


def test_state_derivative_uses_the_derived_main_not_the_source():
    source = _env(
        id=70,
        name="客栈大堂",
        generation_prompt_cn=(
            "【四向拼图】\n"
            "[0度格-左上·北]\n正面：大门。\n"
            "[90度格-右上·东]\n正面：东窗。\n"
            "[180度格-左下·南]\n正面：南门。\n"
            "[270度格-右下·西]\n正面：西柜。\n"
        ),
    )
    derived_main = _env(
        id=71,
        name="客栈大堂_破洞",
        generation_prompt_cn="衍生主环境=客栈大堂_破洞。状态Delta=北墙一个洞。",
        custom_attributes={
            "derived_kind": "derived_main",
            "source_main_environment": "客栈大堂",
        },
    )
    derived = _env(
        id=72,
        name="90度客栈大堂_破洞",
        visual_dependencies=["ENV:[客栈大堂_破洞]"],
        generation_prompt_cn="待生成",
        custom_attributes={
            "main_environment": "客栈大堂_破洞",
            "source_main_environment": "客栈大堂",
            "view_angle_from_main": 90,
        },
    )
    text = _build_scene_subject_image_prompts_cn_section(
        [source, derived_main, derived],
        _keys("90度客栈大堂_破洞"),
        scene_id=25,
    )
    assert "ENV:[90度客栈大堂_破洞]｜所属主环境=ENV:[客栈大堂_破洞]｜view_angle_from_main=90" in text
    assert "所属主环境=ENV:[客栈大堂]" not in text
    assert "正面：东窗" not in text
    assert "正面：大门" not in text
    assert "状态Delta=北墙一个洞" not in text
    assert "待生成" not in text
    assert "[0度格-左上·北]" not in text


def test_state_derivative_reads_the_derived_main_cell_even_if_deps_name_the_source():
    source = _env(
        id=73,
        name="客栈大堂",
        generation_prompt_cn=(
            "【四向拼图】\n"
            "[90度格-右上·东]\n正面：完好东窗。\n"
        ),
    )
    derived_main = _env(
        id=74,
        name="客栈大堂_破洞",
        generation_prompt_cn=(
            "【四向拼图】\n"
            "[0度格-左上·北]\n正面：破洞北墙。\n"
            "[90度格-右上·东]\n正面：破洞东窗。\n"
            "[180度格-左下·南]\n正面：南门。\n"
            "[270度格-右下·西]\n正面：西柜。\n"
        ),
        custom_attributes={
            "derived_kind": "derived_main",
            "source_main_environment": "客栈大堂",
        },
    )
    derived = _env(
        id=75,
        name="90度客栈大堂_破洞",
        visual_dependencies=["ENV:[客栈大堂]"],
        base_name_en="客栈大堂",
        generation_prompt_cn="待生成",
        custom_attributes={
            "derived_from_state": True,
            "main_environment": "客栈大堂_破洞",
            "derived_main_environment": "客栈大堂_破洞",
            "source_main_environment": "客栈大堂",
            "view_angle_from_main": 90,
        },
    )
    text = _build_scene_subject_image_prompts_cn_section(
        [source, derived_main, derived],
        _keys("90度客栈大堂_破洞"),
        scene_id=27,
    )
    assert "所属主环境=ENV:[客栈大堂_破洞]" in text
    assert "正面：破洞东窗。" in text
    assert "正面：完好东窗" not in text
    assert "[0度格-左上·北]" not in text


def test_injected_cell_drops_direction_corner_badge():
    main = _env(
        id=80,
        name="停机坪",
        generation_prompt_cn=(
            "【四向拼图】\n"
            "[0度格-左上·北]\n角标=0度·望北\n正面：大门。\n"
            "[90度格-右上·东]\n角标=90度·望东\n正面：护栏。\n"
            "[180度格-左下·南]\n角标=180度·望南\n正面：南门。\n"
            "[270度格-右下·西]\n角标=270度·望西\n正面：西门。\n"
        ),
    )
    derived = _env(
        id=81,
        name="90度停机坪",
        visual_dependencies=["ENV:[停机坪]"],
        generation_prompt_cn="待生成",
        custom_attributes={"main_environment": "停机坪", "view_angle_from_main": 90},
    )
    text = _build_scene_subject_image_prompts_cn_section(
        [main, derived],
        _keys("90度停机坪"),
        scene_id=26,
    )
    assert "[90度格-右上·东]" in text
    assert "正面：护栏。" in text
    assert "角标=" not in text
    assert "望东" not in text
    assert "望北" not in text
    assert "正面：大门" not in text
    assert "正面：南门" not in text
    assert "正面：西门" not in text
