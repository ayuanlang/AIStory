# -*- coding: utf-8 -*-
from app.services.scene_score import (
    build_scene_score_prompt,
    build_scene_score_timeline,
    build_volume_expr,
    extract_score_cue,
    extract_score_lines,
    extract_score_style,
    parse_duration_seconds,
    score_needs_vocals,
)


def test_parse_duration_seconds():
    assert parse_duration_seconds("4") == 4
    assert parse_duration_seconds("4.5s") == 4.5
    assert parse_duration_seconds("12秒") == 12
    assert parse_duration_seconds("01:05") == 65
    assert parse_duration_seconds("") is None


def test_timeline_uses_shot_duration_and_scales_score_marks():
    segments, total, missing = build_scene_score_timeline([
        {
            "shot_id": "EP01_SC01_SH02",
            "duration": "6",
            "logic": "配乐:出声=后期｜一条｜P1(0s–3s)=续·中",
        },
        {
            "shot_id": "EP01_SC01_SH01",
            "duration": "4s",
            "logic": "配乐:出声=后期｜一条｜P1(0s–4s)=起·弱",
        },
    ])
    assert missing == []
    assert total == 10
    assert segments[0]["shot_id"].endswith("SH01")
    assert segments[0]["state"] == "起"
    assert segments[0]["volume"] == "弱"
    assert segments[0]["end"] == 4
    assert segments[1]["state"] == "续"
    assert segments[1]["start"] == 4
    assert segments[1]["end"] == 10


def test_missing_duration_is_reported():
    _segments, total, missing = build_scene_score_timeline([
        {"shot_id": "SH01", "duration": "", "logic": "配乐:出声=后期｜一条"},
    ])
    assert total == 0
    assert missing == ["SH01"]


def test_prompt_and_volume_follow_one_cue():
    segments, total, _missing = build_scene_score_timeline([
        {"shot_id": "SH01", "duration": "4", "logic": "配乐:P1(0s–4s)=起·弱"},
        {"shot_id": "SH02", "duration": "3", "logic": "配乐:P1(0s–3s)=收·强"},
    ])
    prompt = build_scene_score_prompt(
        total_seconds=total,
        segments=segments,
        music_recommendation="乐器=钢琴｜风格=温暖弦乐｜音量=垫底",
        cue=extract_score_cue("【声画综合】钢琴领句，低弦铺底。配乐出声=后期｜一条=起至落"),
        instrumental=not score_needs_vocals("钢琴", "低弦"),
    )
    assert "总长约7秒" in prompt
    assert "0秒起，音量弱" in prompt
    assert "4秒收，音量强" in prompt
    assert "同一首" in prompt
    assert extract_score_style(prompt) == "温暖弦乐"
    expr = build_volume_expr(segments)
    assert expr.startswith("if(lt(t,4.000),0.28,")
    assert score_needs_vocals("本场梵唱") is True


def test_prompt_combines_storyboard_picture_and_score_lines():
    segments, total, _missing = build_scene_score_timeline([
        {"shot_id": "SH01", "duration": "4", "logic": "配乐:P1(0s–4s)=起·弱"},
    ])
    block = "【配乐】 | （低弦缓推、温暖垫底） | 态=起 | 音量=弱 | 出声=后期"
    prompt = build_scene_score_prompt(
        total_seconds=total,
        segments=segments,
        music_recommendation="风格=温暖弦乐",
        cue="",
        instrumental=True,
        score_lines=extract_score_lines(block),
        shot_pictures={"SH01": "甲推门停住，乙抬眼"},
    )
    assert "低弦缓推" in prompt
    assert "甲推门停住" in prompt
    assert "0–4秒" in prompt
    assert "SH01" in prompt
    assert "当前分镜" in prompt
