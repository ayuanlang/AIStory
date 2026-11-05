# -*- coding: utf-8 -*-
from app.services.edit_bay import extract_dialogue_lines, parse_subtitle_cue_json, split_subtitle_cues


def test_extract_dialogue_lines_keeps_spoken_braces():
    lines = extract_dialogue_lines("他看着她 {你先走} | 闭嘴 | {我留下}")
    assert lines == ["你先走", "我留下"]


def test_split_subtitle_cues_covers_the_shot():
    cues = split_subtitle_cues(["你先走", "我留下"], 6)
    assert cues[0]["start"] == 0
    assert cues[0]["end"] == 3
    assert cues[-1]["end"] == 6
    assert [item["text"] for item in cues] == ["你先走", "我留下"]


def test_parse_subtitle_cue_json_clamps_to_duration():
    raw = '说明 [{"start": 0, "end": 9, "text": "你先走"}, {"start": 2, "end": 4, "text": "我留下"}]'
    cues = parse_subtitle_cue_json(raw, 5)
    assert cues[0]["end"] == 5
    assert cues[1]["text"] == "我留下"
