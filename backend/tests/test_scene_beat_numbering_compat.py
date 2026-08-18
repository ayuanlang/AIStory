# -*- coding: utf-8 -*-
from app.services.script_analysis_flow import (
    ParsedSceneUnit,
    extract_beat_blocks_from_scene_text,
    is_canonical_first_beat_number,
    scene_first_beat_number,
    scene_text_has_beat,
    scene_text_has_beat_1,
    wrap_scene_unit_as_script_block,
)


CROSS_SCENE_BEATS = """【场景名称】茶馆后院｜夜·外
[BEAT_START:11]
- Beat 11：
────【建置】────
沈渊站在中景中央。
────【入戏】────
沈渊抬眼。
[BEAT_END:11]
[BEAT_START:12]
~ Beat 12：
────【建置】────
沈渊仍在中景中央。
────【入戏】────
沈渊开口。
[BEAT_END:12]
"""

NO_BEAT_SCENE = """【场景名称】空场｜日·内
【主环境】大厅
"""


def test_cross_scene_numbering_counts_as_valid_beats():
    assert scene_text_has_beat(CROSS_SCENE_BEATS) is True
    assert scene_text_has_beat_1(CROSS_SCENE_BEATS) is True
    assert scene_first_beat_number(CROSS_SCENE_BEATS) == "11"
    assert is_canonical_first_beat_number("11") is False
    assert is_canonical_first_beat_number("1") is True
    blocks = extract_beat_blocks_from_scene_text(CROSS_SCENE_BEATS)
    assert "[BEAT_START:11]" in blocks
    assert "[BEAT_START:12]" in blocks


def test_scene_without_beats_is_invalid():
    assert scene_text_has_beat(NO_BEAT_SCENE) is False
    assert scene_first_beat_number(NO_BEAT_SCENE) == ""


def test_wrap_scene_unit_accepts_continued_beat_numbers():
    unit = ParsedSceneUnit(
        scene_id="EP01_SC03",
        scene_order=3,
        scene_text=CROSS_SCENE_BEATS,
        marker_start_token="[SCENE_START:EP01_SC03]",
        marker_end_token="[SCENE_END:EP01_SC03]",
    )
    wrapped = wrap_scene_unit_as_script_block(unit)
    assert "[BEAT_START:11]" in wrapped
    assert "Beat 11" in wrapped
    assert "EP01_SC03" in wrapped
