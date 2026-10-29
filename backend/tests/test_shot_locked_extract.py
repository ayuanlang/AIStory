# -*- coding: utf-8 -*-
from app.services.script_analysis_flow.shot_locked_extract import (
    compose_shot_locked_body,
    extract_guidance_by_beat,
    strip_guidance_lines,
)


_SPLIT = """
[SCENE_START:EP01_SC01]
【场景衔接】上场=开篇｜切法转入=艺术覆写｜艺术转入=叠化｜动作=火光吞入｜切法转出=HARD CUT
【闪回分档】同场短闪回｜依据=原文：“三年前”｜新增主环境=无
【本场时地】季节=夏
[SCENE_CONTENT_START:EP01_SC01]
正文
[SCENE_END:EP01_SC01]
[SCENE_START:EP01_SC02]
【场景衔接】上场=SC01｜切法转入=HARD CUT
【闪回分档】无｜依据=无｜新增主环境=无
[SCENE_END:EP01_SC02]
"""

_DRAMA = """
[SCENE_START:EP01_SC01]
【场景衔接】上场=被改过｜切法转入=HARD CUT
【卖点综合】卖点=对质｜承接=对白断句@B2｜重点对象=CHAR:[@甲]
落地=表情特写@B2
【情绪峰谷综合】峰值放大=甲抬眼@B2
【叙事综合】功能=揭示｜关键人物=CHAR:[@甲]
【声画综合】起=CHAR:[@甲]@B1
[BEAT_START:1]
- Beat 1｜救猫咪拍=Opening：
【改编指导】角色=CHAR:[@甲]｜目标=入场｜障碍=无｜策略=建立｜潜台词=无
【世界物理】姿=站
[BEAT_END:1]
[BEAT_START:2]
- Beat 2｜救猫咪拍=Midpoint：
【改编指导】角色=CHAR:[@甲]｜目标=揭开｜障碍=不敢说｜策略=逼近｜潜台词=不是我
【建置】人已经站好
[BEAT_END:2]
"""


def test_locked_body_takes_join_from_split_and_fields_from_drama():
    body = compose_shot_locked_body(
        split_text=_SPLIT,
        beat_source_text=_DRAMA,
        scene_id="EP01_SC01",
    )
    assert "切法转入=艺术覆写" in body
    assert "被改过" not in body
    assert "同场短闪回" in body
    assert "【卖点综合】卖点=对质" in body
    assert "落地=表情特写@B2" in body
    assert "【情绪峰谷综合】" in body
    assert "【叙事综合】" in body
    assert "【声画综合】" not in body
    assert "【本场时地】" not in body
    assert "Beat2｜【改编指导】救猫咪拍=Midpoint｜" in body
    assert "潜台词=不是我" in body
    assert "EP01_SC02" not in body


def test_guidance_lines_leave_the_beat_body():
    rows = extract_guidance_by_beat(_DRAMA)
    assert rows[0].startswith("Beat1｜【改编指导】救猫咪拍=Opening")
    cleaned = strip_guidance_lines(
        "[BEAT_START:2]\n【改编指导】目标=揭开\n【建置】人已经站好\n"
    )
    assert "【改编指导】" not in cleaned
    assert "【建置】人已经站好" in cleaned


def test_other_scene_is_not_used_when_ids_differ():
    body = compose_shot_locked_body(
        split_text=_SPLIT,
        beat_source_text=_DRAMA,
        scene_id="EP01_SC02",
    )
    assert "切法转入=HARD CUT" in body
    assert "卖点=对质" not in body
    assert "潜台词=不是我" not in body
