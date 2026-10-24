# -*- coding: utf-8 -*-
import pytest

from app.services.episode_script_prompt import (
    build_framework_prompt_block,
    build_structured_prefill_prompt_block,
    dedupe_framework_against_prefill,
    build_trailer_generation_prompt_block,
    clamp_plot_title,
    format_trailer_episode_title,
    resolve_trailer_sample_range,
    rewrite_script_heading,
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
    assert "侧重点不写进标题" in block
    assert "不超过 8 字" in block


def test_prompt_without_focus_stays_balanced():
    block = build_trailer_generation_prompt_block(episode_from=1, episode_to=4)
    assert "侧重点=未指定" in block
    assert "建置、娱乐时间、反派逼近" in block
    assert "01–05" in block
    assert "不收成只有铺垫" in block
    assert "不取结局" in block


def test_title_keeps_each_trailer_distinct():
    assert format_trailer_episode_title(
        seq=2,
        episode_title="雨夜",
        episode_from=3,
        episode_to=8,
        series_episode_count=12,
        focus="感情线",
    ) == "预告片2·第3-8集·雨夜"
    assert format_trailer_episode_title(
        seq=1,
        episode_title="开场",
        episode_from=1,
        episode_to=12,
        series_episode_count=12,
    ) == "预告片1·开场"


def test_title_drops_focus_and_caps_length():
    brief = "把感情线写成雨夜对峙并且交代来龙去脉"
    assert format_trailer_episode_title(
        seq=2,
        episode_title=brief,
        episode_from=3,
        episode_to=8,
        series_episode_count=12,
        focus=brief,
    ) == "预告片2·第3-8集"
    assert format_trailer_episode_title(
        seq=2,
        episode_title="预告-雨夜交牌留证之后她走了",
        episode_from=3,
        episode_to=8,
        series_episode_count=12,
        focus="感情线",
    ) == "预告片2·第3-8集·雨夜交牌留证之后"
    long_row = format_trailer_episode_title(
        seq=100,
        episode_title="一二三四五六七八",
        episode_from=100,
        episode_to=120,
        series_episode_count=200,
    )
    assert long_row == "预告片100·第100-120集·一二三四五六七"
    assert len(long_row) <= 24


def test_plot_title_ignores_guidance_and_stays_short():
    guidance = "本集把开场写成雨夜对峙，并且回收门铃。"
    assert clamp_plot_title(guidance, instructions=(guidance,)) == ""
    assert clamp_plot_title("侧重点：把感情线写满直到交牌", instructions=("把感情线写满直到交牌",)) == ""
    assert clamp_plot_title("雨夜交牌") == "雨夜交牌"
    assert clamp_plot_title("一二三四五六七八九十") == "一二三四五六七八"
    rewritten = rewrite_script_heading(
        "# 3-本集把开场写成雨夜对峙\n\n正文",
        "雨夜交牌",
        trailer=False,
        episode_number=3,
    )
    assert rewritten.startswith("# 3-雨夜交牌\n")


def test_blank_prefill_is_omitted():
    assert build_structured_prefill_prompt_block({}, trailer=True) == ""
    assert build_structured_prefill_prompt_block({"logline": "  "}, trailer=False) == ""


def test_prefill_is_required_input_and_trailer_keeps_length():
    source = {
        "logline": "林一要留证，人事要她交牌。",
        "theme": "证据比职位贵，因为交牌就没人能查。",
        "core_conflict": "交牌自保对上留证担责。",
        "characters": "林一从怕丢工作，到肯为证据担责。",
        "stc_14_finale": "她当众拆穿周薇。",
    }
    trailer = build_structured_prefill_prompt_block(source, trailer=True)
    episode = build_structured_prefill_prompt_block(source, trailer=False)
    assert "概念=I1" in trailer
    assert "核心建置" in trailer
    assert "人物弧光" in trailer
    assert "世界背景" in trailer
    assert "林一要留证" in trailer
    assert "5000 字" in trailer
    assert "10–20" in trailer
    assert "跨距" in trailer
    assert "11–15" in trailer
    assert "原句入短拍" in trailer
    assert "已锁救猫咪拍" in episode
    assert "说者与听者的微动作和表情" in episode
    assert "证据比职位贵" in episode
    block = build_trailer_generation_prompt_block(episode_from=1, episode_to=4)
    assert "概念 (I1)" in block
    assert "人物弧光" in block
    assert "世界背景" in block
    assert "5000 字" in block
    assert "10–20" in block
    assert "host space" in block
    assert "speaker's micro-action" in block


def test_framework_drops_prefill_repeats_and_keeps_episode_placement():
    source = {
        "logline": "林一要留证，人事要她交牌。",
        "theme": "证据比职位贵，因为交牌就没人能查。",
        "stc_01_opening_image": "晨会上林一把总裁卡套放进自己的工位。",
    }
    framework = "\n".join([
        "## 0) 项目概览",
        "#高概念: 林一要留证，人事要她交牌。",
        "#Opening: 晨会上林一把总裁卡套放进自己的工位。电梯对位是这一拍多出来的落点。",
        "世界背景: WB01｜工牌开门认的是权限不是人。",
        "专业领域: 领域=法律｜触因=林一要留证，人事要她交牌。｜规程=越权留下审计｜错法=当场删掉｜覆盖=EP01",
        "[EPISODE_BLOCK_START:EP01]",
        "- **摘要**：因为误拿总裁卡套，所以看见解雇信。林一要留证，人事要她交牌。",
        "- **救猫咪拍**：拍=Opening｜收完=是",
        "- **专业**：领域=法律｜动作=审计留在屏上｜对白=二十四小时内把卡交上来",
        "[EPISODE_BLOCK_END:EP01]",
    ])
    deduped = dedupe_framework_against_prefill(framework, source)
    preamble = deduped.split("[EPISODE_BLOCK_START")[0]
    assert "#高概念" not in preamble
    assert "专业领域: 领域=法律｜触因=林一要留证，人事要她交牌。" in preamble
    assert "电梯对位是这一拍多出来的落点" in deduped
    assert "世界背景" in deduped
    assert "专业领域: 领域=法律" in deduped
    assert "越权留下审计" in deduped
    assert "审计留在屏上" in deduped
    assert "拍=Opening" in deduped
    assert "因为误拿总裁卡套" in deduped
    block = build_framework_prompt_block(framework, source)
    assert "剧本框架和这份分集大纲都要落实" in block
    assert "全局事实以剧本框架为准" in block
    assert "本集专业行" in block
    assert "Global Story DNA" not in block
    episode = build_structured_prefill_prompt_block(source, trailer=False)
    assert "以剧本框架为准" in episode
    assert "以框架为准" not in episode


def test_series_ip_note_uses_the_same_range():
    note = build_series_ip_trailer_note(episode_from=2, episode_to=5)
    assert "第2集到第5集" in note
    assert "只从这一段已经写好的分集摘要取样" in note
    assert "核心建置" in note
    assert "人物弧光" in note
    assert "世界背景" in note
