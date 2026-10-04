# -*- coding: utf-8 -*-
from app.services.script_mode_helpers import (
    _build_mandatory_writing_logic,
    _normalize_script_mode_key,
    build_story_episode_coverage_block,
)
from app.services.series_ip_mode import (
    build_prior_episode_summaries_prompt_block,
    build_series_ip_episode_prompt_block,
    compose_series_ip_episode_brief,
    extract_series_episode_summary,
    fallback_series_episode_summary,
    is_series_ip_script_mode,
    series_ip_brief_is_usable,
    strip_series_episode_summary,
)


def test_episode_coverage_block_names_every_episode_and_dedups_character_bios():
    block = build_story_episode_coverage_block(24)
    assert "EP01–EP24" in block
    assert "共 24 块" in block
    assert "[EPISODE_BLOCK_START] 的个数 = 24" in block
    assert "全剧钩子" in block
    assert "人物小传只在 §8 Characters 写一次" in block
    assert "场景和道具只写注册名和一句基本功能" in block
    assert "不写用户原文保留区" in block
    assert "不写逐字落实映射" in block
    assert "不写故事环" in block
    assert build_story_episode_coverage_block(0) == ""
    assert build_story_episode_coverage_block("nope") == ""


def test_series_ip_mode_key_does_not_fall_through_to_general_series():
    assert is_series_ip_script_mode("系列剧（IP模式） / Series IP")
    assert _normalize_script_mode_key("系列剧（IP模式） / Series IP") == "series_ip"
    assert "不预" in _build_mandatory_writing_logic("系列剧（IP模式） / Series IP") or "没有预先" in _build_mandatory_writing_logic("系列剧（IP模式） / Series IP")
    assert not is_series_ip_script_mode("通用连续剧 / General Series")
    assert _normalize_script_mode_key("通用连续剧 / General Series") == "general_series"


def test_compose_brief_keeps_plot_conflict_and_reference():
    brief = compose_series_ip_episode_brief(
        plot="林一拒交工牌",
        conflict="自保对上留证",
        highlights="电梯镜面金句",
        reference="《消失的爱人》的证据战",
        guidance="基本剧情：林一拒交工牌\n要体现的冲突：自保对上留证\n重要亮点：电梯镜面金句\n对标参考（学机制，不搬剧情；可对标整体剧本）：《消失的爱人》的证据战",
    )
    assert "林一拒交工牌" in brief
    assert "自保对上留证" in brief
    assert brief.count("林一拒交工牌") == 1
    assert series_ip_brief_is_usable(brief)
    assert not series_ip_brief_is_usable("太短")


def test_summary_roundtrip_and_prior_block():
    script = """# 1-工牌
正文
[SERIES_EPISODE_SUMMARY_START]
本集发生：林一误刷电梯并留下信的照片。
冲突落地：她拒绝上交工牌。
人物状态：林一握着工牌。
未决钩子：保安已经出门。
后续约束：信的照片还在手机里。
[SERIES_EPISODE_SUMMARY_END]
"""
    summary = extract_series_episode_summary(script)
    assert "拒绝上交工牌" in summary
    cleaned = strip_series_episode_summary(script)
    assert "SERIES_EPISODE_SUMMARY" not in cleaned
    assert "正文" in cleaned

    prior = build_prior_episode_summaries_prompt_block(
        [{"number": 1, "title": "工牌", "summary": summary}],
        current_episode_number=2,
    )
    assert "第1集" in prior
    assert "已发生事实" in prior
    block = build_series_ip_episode_prompt_block(brief="基本剧情：保安上门\n要体现的冲突：交还是留", prior_summaries_block=prior)
    assert "没有预先写好的分集剧情框架" in block
    assert "保安上门" in block
    assert "信的照片还在手机里" in block


def test_fallback_summary_uses_handoff_logline():
    script = """[EMERGENCY_RECOVERY_BLOCK_START]
#剧情一句话与交接：林一仍握着工牌，审计倒计时未完
#结尾钩子：保安按响门铃
[EMERGENCY_RECOVERY_BLOCK_END]"""
    summary = fallback_series_episode_summary(script)
    assert "林一仍握着工牌" in summary
    assert "保安按响门铃" in summary
