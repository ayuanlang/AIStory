# -*- coding: utf-8 -*-
import pytest

from app.services.episode_script_prompt import (
    build_trailer_generation_prompt_block,
    format_trailer_episode_title,
    resolve_trailer_sample_range,
)
from app.services.series_ip_mode import build_series_ip_trailer_note


def test_range_defaults_to_whole_series():
    assert resolve_trailer_sample_range(
        episode_from=None,
        episode_to=None,
        series_episode_count=12,
    ) == (1, 12)


def test_range_fills_the_missing_bound():
    assert resolve_trailer_sample_range(
        episode_from=3,
        episode_to=None,
        series_episode_count=12,
    ) == (3, 12)
    assert resolve_trailer_sample_range(
        episode_from=None,
        episode_to=8,
        series_episode_count=12,
    ) == (1, 8)


def test_range_rejects_out_of_series_and_reversed_bounds():
    with pytest.raises(ValueError, match="trailer_episode_to"):
        resolve_trailer_sample_range(episode_from=1, episode_to=13, series_episode_count=12)
    with pytest.raises(ValueError, match="less than or equal"):
        resolve_trailer_sample_range(episode_from=6, episode_to=2, series_episode_count=12)


def test_prompt_locks_range_and_focus():
    block = build_trailer_generation_prompt_block(
        focus="感情线",
        episode_from=3,
        episode_to=8,
    )
    assert "取材范围=第3集到第8集" in block
    assert "侧重点=感情线" in block
    assert "does not replace any earlier trailer" in block
    assert "不把范围外的高光" in block


def test_prompt_without_focus_stays_balanced():
    block = build_trailer_generation_prompt_block(episode_from=1, episode_to=4)
    assert "侧重点=未指定" in block
    assert "均衡取样" in block


def test_title_keeps_each_trailer_distinct():
    assert format_trailer_episode_title(
        seq=2,
        episode_title="雨夜",
        episode_from=3,
        episode_to=8,
        series_episode_count=12,
        focus="感情线",
    ) == "预告片2·第3-8集·感情线·雨夜"
    assert format_trailer_episode_title(
        seq=1,
        episode_title="开场",
        episode_from=1,
        episode_to=12,
        series_episode_count=12,
    ) == "预告片1·开场"


def test_series_ip_note_uses_the_same_range():
    note = build_series_ip_trailer_note(episode_from=2, episode_to=5)
    assert "第2集到第5集" in note
    assert "只从这一段已经写好的分集摘要取样" in note
