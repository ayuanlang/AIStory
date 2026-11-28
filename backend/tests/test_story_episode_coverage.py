# -*- coding: utf-8 -*-
import asyncio
import re

from app.schemas.episode_requests import StoryGeneratorRequest, story_generator_payload
from app.services.story_episode_coverage import (
    build_gap_fill_user_prompt,
    ensure_story_episode_blocks,
    episode_blocks_need_sort,
    missing_episode_numbers,
    order_episode_blocks,
    splice_episode_blocks,
)


def test_splice_fills_gap_and_drops_unclosed_tail():
    base = """[STORY_DNA_OUTPUT_START]
## 9) 分集规划
[EPISODE_BLOCK_START:EP01]
- EP01 标题
[EPISODE_BLOCK_END:EP01]
[EPISODE_BLOCK_START:EP03]
半截没有收束
### Episode Coverage Audit
Planned:3
[STORY_DNA_OUTPUT_END]
"""
    addition = """
[EPISODE_BLOCK_START:EP02]
- EP02 正文
[EPISODE_BLOCK_END:EP02]
[EPISODE_BLOCK_START:EP03]
- EP03 正文
[EPISODE_BLOCK_END:EP03]
"""
    merged = splice_episode_blocks(base, addition)
    assert missing_episode_numbers(merged, 3) == []
    assert "半截没有收束" not in merged
    assert merged.index("EP02") < merged.index("EP03")
    assert merged.index("[EPISODE_BLOCK_END:EP03]") < merged.index("Episode Coverage Audit")
    assert "[STORY_DNA_OUTPUT_END]" in merged


def test_gap_fill_prompt_keeps_original_request_and_existing_outline():
    existing = "[EPISODE_BLOCK_START:EP01]\n- EP01 已有\n[EPISODE_BLOCK_END:EP01]"
    prompt = build_gap_fill_user_prompt("原提示词：按剧本框架写分集", existing, [2], 3)
    assert prompt.startswith("原提示词：按剧本框架写分集")
    assert "上次输出：" in prompt
    assert "EP01 已有" in prompt
    assert "只输出：EP02" in prompt
    assert prompt.rstrip().endswith("已闭合的集保持原样。")


def test_gap_fill_submits_original_prompt_and_inserts_in_order(monkeypatch):
    calls = []

    async def _fake(user_prompt, system_prompt, config, image_urls=None, video_urls=None, **kwargs):
        calls.append({"user": user_prompt, "system": system_prompt})
        return {
            "content": (
                "[EPISODE_BLOCK_START:EP01]\n- EP01 被重写\n[EPISODE_BLOCK_END:EP01]\n"
                "[EPISODE_BLOCK_START:EP02]\n- EP02 正文\n[EPISODE_BLOCK_END:EP02]\n"
            ),
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        }

    monkeypatch.setattr(
        "app.services.story_episode_coverage.llm_service.generate_content_with_fallback",
        _fake,
    )
    base = "[EPISODE_BLOCK_START:EP01]\n- EP01 已有\n[EPISODE_BLOCK_END:EP01]\n"

    async def _run():
        return await ensure_story_episode_blocks(
            base,
            episodes_count=2,
            llm_config={},
            source_user_prompt="原提示词：按剧本框架写分集",
            source_system="原系统提示",
            fill_system="专用补写提示，这条不该用",
        )

    merged, usage = asyncio.run(_run())
    assert len(calls) == 1
    assert calls[0]["system"] == "原系统提示"
    assert "原提示词：按剧本框架写分集" in calls[0]["user"]
    assert "EP01 已有" in calls[0]["user"]
    assert "只输出：EP02" in calls[0]["user"]
    assert "EP01 已有" in merged
    assert "EP01 被重写" not in merged
    assert merged.index("EP01") < merged.index("EP02")
    assert missing_episode_numbers(merged, 2) == []
    assert usage["total_tokens"] == 8


def test_fill_continues_until_every_episode_is_closed(monkeypatch):
    calls = []

    async def _fake(user_prompt, system_prompt, config, image_urls=None, video_urls=None, **kwargs):
        calls.append(user_prompt)
        labels = re.search(r"这次只补：([^。\n]+)", user_prompt).group(1)
        blocks = []
        for label in (part.strip() for part in labels.split(",")):
            blocks.append(
                f"[EPISODE_BLOCK_START:{label}]\n- {label} 正文\n[EPISODE_BLOCK_END:{label}]"
            )
        return {"content": "\n".join(blocks), "usage": {"prompt_tokens": 1, "completion_tokens": 1}}

    monkeypatch.setattr(
        "app.services.story_episode_coverage.llm_service.generate_content_with_fallback",
        _fake,
    )

    async def _run():
        return await ensure_story_episode_blocks("", episodes_count=33, llm_config={})

    merged, usage = asyncio.run(_run())
    assert len(calls) == 9
    assert missing_episode_numbers(merged, 33) == []
    assert usage["total_tokens"] == 18


def test_story_generator_payload_drops_outline_check_fields():
    payload = story_generator_payload(StoryGeneratorRequest(
        mode="global",
        episodes_count=3,
        check_episode_outlines=True,
        existing_outline_md="[EPISODE_BLOCK_START:EP01]\n已有\n[EPISODE_BLOCK_END:EP01]",
    ))
    assert payload["mode"] == "global"
    assert payload["episodes_count"] == 3
    assert "check_episode_outlines" not in payload
    assert "existing_outline_md" not in payload


def test_completeness_check_sorts_closed_blocks_before_looking_for_gaps():
    shuffled = """[STORY_DNA_OUTPUT_START]
## 9) 分集规划
[EPISODE_BLOCK_START:EP03]
- EP03 正文
[EPISODE_BLOCK_END:EP03]
[EPISODE_BLOCK_START:EP01]
- EP01 正文
[EPISODE_BLOCK_END:EP01]
[EPISODE_BLOCK_START:EP02]
- EP02 正文
[EPISODE_BLOCK_END:EP02]
### Episode Coverage Audit
Planned:3
[STORY_DNA_OUTPUT_END]
"""
    assert episode_blocks_need_sort(shuffled)
    ordered = order_episode_blocks(shuffled)
    assert ordered.index("EP01") < ordered.index("EP02") < ordered.index("EP03")
    assert ordered.index("[EPISODE_BLOCK_END:EP03]") < ordered.index("Episode Coverage Audit")
    assert not episode_blocks_need_sort(ordered)
    assert order_episode_blocks(ordered) == ordered

    async def _run():
        return await ensure_story_episode_blocks(shuffled, episodes_count=3, llm_config={})

    merged, usage = asyncio.run(_run())
    assert merged.index("EP01") < merged.index("EP02") < merged.index("EP03")
    assert missing_episode_numbers(merged, 3) == []
    assert usage == {}


def test_missing_ignores_summary_without_block_markers():
    text = """
[EPISODE_BLOCK_START:EP01]
- EP01
[EPISODE_BLOCK_END:EP01]
EP02–EP04 同上，略。
"""
    assert missing_episode_numbers(text, 4) == [2, 3, 4]
