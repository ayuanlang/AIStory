# -*- coding: utf-8 -*-
from app.services.kie_suno_payload import (
    SUNO_JOB_MODEL,
    build_suno_generate_body,
    clamp_suno_duration,
    resolve_suno_model,
)


def test_retired_suno_versions_use_v6():
    assert resolve_suno_model("V4") == "V6"
    assert resolve_suno_model("V5") == "V6"
    assert resolve_suno_model("V6_MINI") == "V6_MINI"


def test_duration_stays_inside_suno_range():
    assert clamp_suno_duration(4) == 10
    assert clamp_suno_duration(90.4) == 90
    assert clamp_suno_duration(800) == 360
    assert clamp_suno_duration(None) is None


def test_score_brief_goes_to_style_not_lyrics():
    brief = "一首连续配乐，总长约90秒。纯器乐，不要歌词，不要人声。"
    body = build_suno_generate_body(
        prompt=brief,
        tool_conf={
            "customMode": True,
            "instrumental": True,
            "suno_model": "V4",
            "suno_style": brief,
            "suno_title": "第1场配乐",
            "negativeTags": "lyrics, vocals, speech, dialogue",
            "suno_duration": 90,
        },
    )
    assert body["model"] == SUNO_JOB_MODEL
    music = body["input"]
    assert music["model"] == "V6"
    assert music["custom_mode"] is True
    assert music["instrumental"] is True
    assert music["style"] == brief
    assert music["title"] == "第1场配乐"
    assert music["duration"] == 90
    assert music["negative_tags"] == "lyrics, vocals, speech, dialogue"
    assert "prompt" not in music
    assert "lyrics" not in music
    assert "customMode" not in body
