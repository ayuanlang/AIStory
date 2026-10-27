# -*- coding: utf-8 -*-
import asyncio

from app.services.markdown_generation import (
    build_framework_continuation_user_prompt,
    generate_markdown_with_retry,
    merge_framework_continuation,
)


def test_merge_drops_repeated_tail_and_keeps_new_text():
    merged = merge_framework_continuation("甲段已经写到门口", "门口，然后推门进去。")
    assert merged == "甲段已经写到门口，然后推门进去。"


def test_merge_uses_echo_that_already_contains_the_draft():
    merged = merge_framework_continuation("已有全文", "已有全文\n后续补上")
    assert merged == "已有全文\n后续补上"


def test_merge_joins_unrelated_continuation_once():
    merged = merge_framework_continuation("上半", "下半")
    assert merged == "上半\n下半"


def test_continuation_prompt_keeps_original_request_and_existing_draft():
    prompt = build_framework_continuation_user_prompt("Mode: global\nEpisodes Count: 8", "§0 已经写完")
    assert prompt.startswith("Mode: global\nEpisodes Count: 8")
    assert "上次输出：" in prompt
    assert "不是本次输入" in prompt
    assert "§0 已经写完" in prompt
    assert "只返回续写" in prompt


def _patch_calls(monkeypatch, responses):
    calls = []

    async def _fake(user_prompt, system_prompt, config, image_urls=None, video_urls=None, **kwargs):
        calls.append({"user": user_prompt, "system": system_prompt})
        return responses[len(calls) - 1]

    monkeypatch.setattr(
        "app.services.markdown_generation.llm_service.generate_content_with_fallback",
        _fake,
    )
    return calls


def test_incomplete_framework_appends_draft_and_merges(monkeypatch):
    calls = _patch_calls(
        monkeypatch,
        [
            {
                "content": "框架写到第二节",
                "usage": {"prompt_tokens": 10, "completion_tokens": 4},
                "finish_reason": "incomplete",
            },
            {
                "content": "第二节之后把结局补完。\n[STORY_DNA_OUTPUT_END]",
                "usage": {"prompt_tokens": 30, "completion_tokens": 6},
                "finish_reason": "stop",
            },
        ],
    )

    async def _run():
        return await generate_markdown_with_retry(
            user_prompt="请写全局框架",
            sys_prompt="系统",
            llm_config={"config": {"continuation_max_segments": 4}},
            strict_markdown=False,
            require_h1=False,
            return_meta=True,
            continue_on_incomplete=True,
        )

    result = asyncio.run(_run())
    assert len(calls) == 2
    assert "请写全局框架" in calls[1]["user"]
    assert "框架写到第二节" in calls[1]["user"]
    assert "不是本次输入" in calls[1]["user"]
    assert "上次输出：" in calls[1]["user"]
    assert "只返回续写" in calls[1]["user"]
    assert result["content"] == "框架写到第二节之后把结局补完。\n[STORY_DNA_OUTPUT_END]"
    assert result["usage"]["prompt_tokens"] == 40
    assert result["usage"]["completion_tokens"] == 10
    assert result["usage"]["total_tokens"] == 50
    assert result["finish_reason"] == "stop"


def test_complete_framework_is_not_continued(monkeypatch):
    calls = _patch_calls(
        monkeypatch,
        [
            {
                "content": "# 完整框架\n[STORY_DNA_OUTPUT_END]",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                "finish_reason": "stop",
            }
        ],
    )

    async def _run():
        return await generate_markdown_with_retry(
            user_prompt="请写全局框架",
            sys_prompt="系统",
            llm_config={},
            strict_markdown=False,
            require_h1=False,
            return_meta=True,
            continue_on_incomplete=True,
        )

    result = asyncio.run(_run())
    assert len(calls) == 1
    assert result["content"] == "# 完整框架\n[STORY_DNA_OUTPUT_END]"


def test_incomplete_without_flag_returns_the_partial_once(monkeypatch):
    calls = _patch_calls(
        monkeypatch,
        [
            {
                "content": "半截",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                "finish_reason": "incomplete",
            }
        ],
    )

    async def _run():
        return await generate_markdown_with_retry(
            user_prompt="请写全局框架",
            sys_prompt="系统",
            llm_config={},
            strict_markdown=False,
            require_h1=False,
            return_meta=True,
        )

    result = asyncio.run(_run())
    assert len(calls) == 1
    assert result["content"] == "半截"


def test_length_cutoff_repeats_tail_once_then_stops(monkeypatch):
    calls = _patch_calls(
        monkeypatch,
        [
            {
                "content": "开场写完，转到",
                "usage": {"prompt_tokens": 2, "completion_tokens": 2},
                "finish_reason": "length",
            },
            {
                "content": "转到第二幕。",
                "usage": {"prompt_tokens": 3, "completion_tokens": 3},
                "finish_reason": "length",
            },
            {
                "content": "第二幕。收束。\n[STORY_DNA_OUTPUT_END]",
                "usage": {"prompt_tokens": 4, "completion_tokens": 4},
                "finish_reason": "stop",
            },
        ],
    )

    async def _run():
        return await generate_markdown_with_retry(
            user_prompt="请写全局框架",
            sys_prompt="系统",
            llm_config={"config": {"continuation_max_segments": 4}},
            strict_markdown=False,
            require_h1=False,
            return_meta=True,
            continue_on_incomplete=True,
        )

    result = asyncio.run(_run())
    assert len(calls) == 3
    assert "开场写完，转到" in calls[1]["user"]
    assert "开场写完，转到第二幕。" in calls[2]["user"]
    assert result["content"] == "开场写完，转到第二幕。收束。\n[STORY_DNA_OUTPUT_END]"
    assert result["usage"]["total_tokens"] == 18


def test_stop_without_output_end_still_continues(monkeypatch):
    calls = _patch_calls(
        monkeypatch,
        [
            {
                "content": "写到第八节就停了",
                "usage": {"prompt_tokens": 5, "completion_tokens": 5},
                "finish_reason": "stop",
            },
            {
                "content": "补上第九节\n[STORY_DNA_OUTPUT_END]",
                "usage": {"prompt_tokens": 6, "completion_tokens": 6},
                "finish_reason": "stop",
            },
        ],
    )

    async def _run():
        return await generate_markdown_with_retry(
            user_prompt="请写全局框架",
            sys_prompt="系统",
            llm_config={"config": {"continuation_max_segments": 4}},
            strict_markdown=False,
            require_h1=False,
            return_meta=True,
            continue_on_incomplete=True,
        )

    result = asyncio.run(_run())
    assert len(calls) == 2
    assert "写到第八节就停了" in calls[1]["user"]
    assert "[STORY_DNA_OUTPUT_END]" in calls[1]["user"]
    assert result["content"] == "写到第八节就停了\n补上第九节\n[STORY_DNA_OUTPUT_END]"


def test_output_end_stops_even_when_the_transport_was_cut(monkeypatch):
    calls = _patch_calls(
        monkeypatch,
        [
            {
                "content": "正文结束\n[ STORY_DNA_OUTPUT_END ]",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                "finish_reason": "length",
            }
        ],
    )

    async def _run():
        return await generate_markdown_with_retry(
            user_prompt="请写全局框架",
            sys_prompt="系统",
            llm_config={},
            strict_markdown=False,
            require_h1=False,
            return_meta=True,
            keep_truncated=True,
            continue_on_incomplete=True,
        )

    result = asyncio.run(_run())
    assert len(calls) == 1
    assert result["content"] == "正文结束\n[ STORY_DNA_OUTPUT_END ]"
