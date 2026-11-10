# -*- coding: utf-8 -*-
import asyncio

from app.services.llm_service import LLMService
from app.services.shot_generation_agentscope import repair_shot_markdown_cell_count_rows
from app.services.shot_generation_prompts import _build_ai_shots_response_validator
from app.services.shot_markdown import (
    SHOT_GENERATION_INCOMPLETE_CODE,
    _validate_shot_rows_for_apply_with_tolerance,
    build_shot_markdown_continuation_user_prompt,
    build_shot_markdown_row_format_repair_prompt,
    collect_shot_generation_completeness_errors,
    format_shot_generation_incomplete_detail,
    inspect_complete_shot_markdown_return,
    merge_shot_markdown_continuation,
    parse_shots_markdown_table,
    plan_shot_markdown_row_format_repair,
    shot_markdown_needs_continuation,
    splice_shot_markdown_row_format_repair,
)

LOGIC = (
    "Beat-Shot映射:合镜=Beat1｜Duration=5<br>"
    "节奏:中｜-<br>"
    "运镜:MCU Soft Push<br>"
    "取景:MCU｜平拍｜50mm｜浅<br>"
    "光影:窗侧Key｜冷静｜中｜冷<br>"
    "ENV:ENV:[0度客栈]<br>"
    "实体:CHAR:[@李玄]<br>"
    "P链:P1建置MCU<br>"
    "衔接:N/A首镜"
)

VIDEO = (
    "运镜与动作流：(P1 0s–5s) MCU, Eye-level, 50mm Standard。"
    "CHAR:[@李玄] 位于柜台内侧。<br>"
    "动态连续光影/焦点：窗侧 Key。<br>"
    "光线连动弧光：推门时光比略升。<br>"
    "全局动态风格：项目类型为真人实拍。<br>"
    "人物面部稳定不变形，动作自然流畅，无卡顿无闪烁，无背景音乐，无字幕"
)

HEADER = (
    "| Shot ID | Shot Name | Scene ID | Shot Logic (CN) | Start Frame | Video Content | "
    "Duration (s) | Keyframes | End Frame | Start Frame (CN) | Video Content (CN) | "
    "Keyframes (CN) | End Frame (CN) | Associated Entities |"
)
SEPARATOR = "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"


def _closed_row(shot_id: str, video: str = VIDEO) -> str:
    return (
        f"| {shot_id} | 推门 | EP01_SC01 | {LOGIC} |  |  | 5 |  |  |  | {video} |  |  | "
        "CHAR:[@李玄],ENV:[0度客栈] |"
    )


def _cut_row(shot_id: str) -> str:
    return (
        f"| {shot_id} | 推门 | EP01_SC01 | {LOGIC} |  |  | 5 |  |  |  | "
        "运镜与动作流：(P1 0s–5s) MCU, Eye-level。CHAR:[@李玄] 推门。<br>动态连续光影/焦点：窗侧"
    )


def _table(*rows: str) -> str:
    return "\n".join([HEADER, SEPARATOR, *rows])


def test_complete_markdown_table_has_no_errors():
    markdown = _table(_closed_row("EP01_SC01_SH01"))
    errors = inspect_complete_shot_markdown_return(markdown)
    assert errors == []
    assert collect_shot_generation_completeness_errors(
        markdown_text=markdown,
        raw_text=markdown,
        finish_reason="stop",
    ) == []


def test_unclosed_last_row_is_incomplete_markdown():
    markdown = _table(_cut_row("EP01_SC01_SH01"))
    errors = inspect_complete_shot_markdown_return(markdown)
    assert any("closed" in item or "cells" in item for item in errors)


def test_short_closed_last_row_is_incomplete_markdown():
    markdown = _table("| EP01_SC01_SH01 | 推门 | EP01_SC01 | 未写完 |")
    errors = inspect_complete_shot_markdown_return(markdown)
    assert any("14" in item or "Associated Entities" in item for item in errors)


def test_parser_pads_cut_row_but_markdown_check_fails():
    markdown = _table(
        _closed_row("EP01_SC01_SH01"),
        _cut_row("EP01_SC01_SH02"),
    )
    _, rows, _ = parse_shots_markdown_table(markdown)
    applyable, _skipped = _validate_shot_rows_for_apply_with_tolerance(
        rows,
        source_label="Generated shot table",
        status_code=502,
    )
    assert len(applyable) >= 1
    errors = collect_shot_generation_completeness_errors(
        markdown_text=markdown,
        raw_text=markdown,
        rows=rows,
        finish_reason="stop",
    )
    assert errors
    assert any("row 2" in item or "closed" in item or "cells" in item for item in errors)


def test_linebreak_inside_last_row_is_incomplete_markdown():
    raw = (
        _table(_closed_row("EP01_SC01_SH01", "运镜与动作流：(P1 0s–5s) MCU, Eye-level。"))
        + "\n动态连续光影/焦点：窗侧 Key 尚未写完"
    )
    errors = inspect_complete_shot_markdown_return(raw)
    assert any("line break" in item or "closed" in item for item in errors)


def test_header_only_is_incomplete_markdown():
    errors = inspect_complete_shot_markdown_return(f"{HEADER}\n{SEPARATOR}")
    assert errors


def test_finish_reason_incomplete_does_not_reject_a_closed_table():
    markdown = _table(_closed_row("EP01_SC01_SH01"))
    errors = collect_shot_generation_completeness_errors(
        markdown_text=markdown,
        raw_text=markdown,
        finish_reason="incomplete",
        continuation_stopped_by_max_segments=True,
    )
    assert errors == []


def test_finish_reason_incomplete_is_kept_when_markdown_is_cut():
    markdown = _table(_cut_row("EP01_SC01_SH01"))
    errors = collect_shot_generation_completeness_errors(
        markdown_text=markdown,
        raw_text=markdown,
        finish_reason="incomplete",
    )
    assert "finish_reason=incomplete" in errors
    assert any("closed" in item or "cells" in item for item in errors)


def test_length_finish_is_accepted_when_markdown_is_complete():
    markdown = _table(_closed_row("EP01_SC01_SH01"))
    errors = collect_shot_generation_completeness_errors(
        markdown_text=markdown,
        raw_text=markdown,
        finish_reason="length",
    )
    assert errors == []


def test_validator_rejects_cut_markdown_table():
    markdown = _table(
        _closed_row("EP01_SC01_SH01"),
        _cut_row("EP01_SC01_SH02"),
    )
    validator = _build_ai_shots_response_validator(
        context="ai_generate_shots",
        scene_id=1,
        user_id=1,
        source_label="Generate Shots",
    )
    ok, reason, payload = validator({"content": markdown, "finish_reason": "stop"}, {"provider": "x", "model": "y"})
    assert ok is False
    assert SHOT_GENERATION_INCOMPLETE_CODE in reason
    assert "markdown" in reason.lower()
    assert payload is None


def test_validator_accepts_complete_markdown_table():
    markdown = _table(_closed_row("EP01_SC01_SH01"), _closed_row("EP01_SC01_SH02"))
    validator = _build_ai_shots_response_validator(
        context="ai_generate_shots",
        scene_id=1,
        user_id=1,
        source_label="Generate Shots",
    )
    ok, reason, payload = validator({"content": markdown, "finish_reason": "stop"}, {"provider": "x", "model": "y"})
    assert ok is True
    assert reason == ""
    assert payload and len(payload.get("rows") or []) == 2


def test_incomplete_detail_uses_stable_code():
    detail = format_shot_generation_incomplete_detail(
        ["markdown data row 2 is not a closed | ... | row"],
        source_label="Generate Shots",
    )
    assert detail.startswith(f"{SHOT_GENERATION_INCOMPLETE_CODE}:")
    assert "markdown return incomplete" in detail


def _named_closed(shot_id: str, name: str) -> str:
    return (
        f"| {shot_id} | {name} | EP01_SC01 | {LOGIC} |  |  | 5 |  |  |  | {VIDEO} |  |  | "
        "CHAR:[@李玄],ENV:[0度客栈] |"
    )


def _short_named(shot_id: str, name: str) -> str:
    return (
        f"| {shot_id} | {name} | EP01_SC01 | {LOGIC} |  |  | 5 |  |  |  | {VIDEO} | "
        "CHAR:[@李玄],ENV:[0度客栈] |"
    )


def _misplaced_entities(shot_id: str) -> str:
    return (
        f"| {shot_id} | 推门 | EP01_SC01 | {LOGIC} |  |  | 5 |  |  |  | {VIDEO} |  | "
        "CHAR:[@李玄],ENV:[0度客栈] | 乱列 |"
    )


def test_cell_count_plan_names_only_short_rows():
    markdown = "场记说明\n" + _table(
        _named_closed("EP01_SC01_SH01", "好镜"),
        _short_named("EP01_SC01_SH02", "坏镜"),
    )
    plan = plan_shot_markdown_row_format_repair(markdown)
    assert plan is not None
    assert [row["index"] for row in plan["rows"]] == [2]
    assert plan["rows"][0]["cell_count"] == 12
    _system, user = build_shot_markdown_row_format_repair_prompt(plan)
    assert "坏镜" in user
    assert "好镜" not in user
    assert "EP01_SC01_SH01" not in user
    assert "现有12列，需要 14 列" in user


def test_unclosed_row_is_not_a_format_repair():
    markdown = _table(_closed_row("EP01_SC01_SH01"), _cut_row("EP01_SC01_SH02"))
    assert plan_shot_markdown_row_format_repair(markdown) is None


def test_splice_replaces_only_the_short_row():
    markdown = "场记说明\n" + _table(
        _named_closed("EP01_SC01_SH01", "好镜"),
        _short_named("EP01_SC01_SH02", "坏镜"),
    )
    fixed = _named_closed("EP01_SC01_SH02", "坏镜")
    spliced = splice_shot_markdown_row_format_repair(markdown, "```markdown\n" + fixed + "\n```")
    assert spliced is not None
    assert spliced.startswith("场记说明")
    assert "好镜" in spliced
    assert inspect_complete_shot_markdown_return(spliced) == []
    assert _short_named("EP01_SC01_SH02", "坏镜") not in spliced


def test_splice_matches_bad_row_when_repair_also_returns_the_good_row():
    markdown = _table(
        _named_closed("EP01_SC01_SH01", "好镜"),
        _short_named("EP01_SC01_SH02", "坏镜"),
    )
    repaired = "\n".join([
        HEADER,
        SEPARATOR,
        _named_closed("EP01_SC01_SH01", "好镜被改"),
        _named_closed("EP01_SC01_SH02", "坏镜"),
    ])
    spliced = splice_shot_markdown_row_format_repair(markdown, repaired)
    assert spliced is not None
    assert "好镜被改" not in spliced
    assert "好镜" in spliced
    assert inspect_complete_shot_markdown_return(spliced) == []


def test_misplaced_entities_row_is_a_format_repair():
    markdown = _table(_misplaced_entities("EP01_SC01_SH01"))
    plan = plan_shot_markdown_row_format_repair(markdown)
    assert plan is not None
    assert plan["rows"][0]["kind"] == "entities"
    _system, user = build_shot_markdown_row_format_repair_prompt(plan)
    assert "Associated Entities" in user
    spliced = splice_shot_markdown_row_format_repair(
        markdown,
        _named_closed("EP01_SC01_SH01", "推门"),
    )
    assert spliced is not None
    assert inspect_complete_shot_markdown_return(spliced) == []


class _FakeAgent:
    def __init__(self, fallbacks):
        self._fallbacks = fallbacks

    def get_fallback_configs(self, *args, **kwargs):
        return list(self._fallbacks)

    def get_fallback_configs_by_ids(self, ids):
        return list(self._fallbacks)


def _shot_validator():
    return _build_ai_shots_response_validator(
        context="ai_generate_shots",
        scene_id=1,
        user_id=1,
        source_label="Generate Shots",
    )


def test_cell_count_failure_repairs_rows_instead_of_regenerating_the_table(monkeypatch):
    service = LLMService()
    calls = []
    chat_prompts = []
    fallbacks = [{"provider": "openai", "model": "gpt-backup", "config": {"__resolved_setting_id": 2}}]
    import app.services.agent_service as agent_mod

    monkeypatch.setattr(agent_mod, "agent_service", _FakeAgent(fallbacks))
    markdown = "场记说明\n" + _table(
        _named_closed("EP01_SC01_SH01", "好镜"),
        _short_named("EP01_SC01_SH02", "坏镜"),
    )

    async def fake_generate(user_prompt, system_prompt, config, image_urls=None, video_urls=None):
        calls.append(config.get("model"))
        return {"content": markdown, "usage": {"output_tokens": 10}, "finish_reason": "stop"}

    async def fake_chat(messages, config):
        chat_prompts.append(messages[-1]["content"])
        return {
            "content": _named_closed("EP01_SC01_SH02", "坏镜"),
            "usage": {"output_tokens": 4},
        }

    monkeypatch.setattr(service, "generate_content", fake_generate)
    import app.services.shot_generation_agentscope as repair_mod

    monkeypatch.setattr(repair_mod.llm_service, "chat_completion", fake_chat)

    async def _run():
        return await service.generate_content_with_fallback(
            "user",
            "system",
            {
                "provider": "grsai",
                "model": "gemini-3.8-flash",
                "config": {"__resolved_setting_id": 1, "__active_retry_attempts": 2},
            },
            response_validator=_shot_validator(),
            validation_repair=repair_shot_markdown_cell_count_rows,
        )

    result = asyncio.run(_run())
    assert calls == ["gemini-3.8-flash"]
    assert len(chat_prompts) == 1
    assert "坏镜" in chat_prompts[0]
    assert "好镜" not in chat_prompts[0]
    assert result["content"].startswith("场记说明")
    assert "好镜" in result["content"]
    assert inspect_complete_shot_markdown_return(result["content"]) == []
    assert result["usage"]["output_tokens"] == 14
    assert result.get("_shot_row_format_repair") == "ok"


def test_failed_row_repair_does_not_start_another_full_generation(monkeypatch):
    service = LLMService()
    calls = []
    fallbacks = [{"provider": "openai", "model": "gpt-backup", "config": {"__resolved_setting_id": 2}}]
    import app.services.agent_service as agent_mod

    monkeypatch.setattr(agent_mod, "agent_service", _FakeAgent(fallbacks))
    markdown = _table(_short_named("EP01_SC01_SH01", "坏镜"))

    async def fake_generate(user_prompt, system_prompt, config, image_urls=None, video_urls=None):
        calls.append(config.get("model"))
        return {"content": markdown, "usage": {}, "finish_reason": "stop"}

    async def fake_chat(messages, config):
        return {"content": _short_named("EP01_SC01_SH01", "坏镜"), "usage": {}}

    monkeypatch.setattr(service, "generate_content", fake_generate)
    import app.services.shot_generation_agentscope as repair_mod

    monkeypatch.setattr(repair_mod.llm_service, "chat_completion", fake_chat)

    async def _run():
        return await service.generate_content_with_fallback(
            "user",
            "system",
            {
                "provider": "grsai",
                "model": "gemini-3.8-flash",
                "config": {"__resolved_setting_id": 1, "__active_retry_attempts": 2},
            },
            response_validator=_shot_validator(),
            validation_repair=repair_shot_markdown_cell_count_rows,
        )

    result = asyncio.run(_run())
    assert calls == ["gemini-3.8-flash"]
    assert str(result["content"]).startswith("Error:")
    assert SHOT_GENERATION_INCOMPLETE_CODE in result["content"]
    assert result.get("_postprocess_validation_failed") is True
    assert result.get("_abort_full_retry") is True


def _cut_closed_row(shot_id: str, name: str) -> tuple:
    closed = _named_closed(shot_id, name)
    suffix = " |  |  | CHAR:[@李玄],ENV:[0度客栈] |"
    assert closed.endswith(suffix)
    return closed[: -len(suffix)], suffix


def test_unclosed_row_merges_continuation_onto_the_same_line():
    cut, suffix = _cut_closed_row("EP01_SC01_SH02", "续镜")
    markdown = "场记说明\n" + _table(_named_closed("EP01_SC01_SH01", "好镜"), cut)
    assert shot_markdown_needs_continuation(markdown) is True
    assert shot_markdown_needs_continuation(_table(_short_named("EP01_SC01_SH02", "坏镜"))) is False
    prompt = build_shot_markdown_continuation_user_prompt("原任务", markdown)
    assert "【上次输出】" in prompt
    assert "原任务" in prompt
    assert "好镜" in prompt
    assert "续镜" in prompt
    merged = merge_shot_markdown_continuation(markdown, suffix)
    assert merged.startswith("场记说明")
    assert "好镜" in merged
    assert inspect_complete_shot_markdown_return(merged) == []


def test_unclosed_row_continues_from_previous_output(monkeypatch):
    service = LLMService()
    calls = []
    chat_prompts = []
    fallbacks = [{"provider": "openai", "model": "gpt-backup", "config": {"__resolved_setting_id": 2}}]
    import app.services.agent_service as agent_mod

    monkeypatch.setattr(agent_mod, "agent_service", _FakeAgent(fallbacks))
    cut, suffix = _cut_closed_row("EP01_SC01_SH02", "续镜")
    markdown = "场记说明\n" + _table(_named_closed("EP01_SC01_SH01", "好镜"), cut)

    async def fake_generate(user_prompt, system_prompt, config, image_urls=None, video_urls=None):
        calls.append(config.get("model"))
        return {"content": markdown, "usage": {"output_tokens": 8}, "finish_reason": "length"}

    async def fake_chat(messages, config):
        chat_prompts.append(messages[-1]["content"])
        return {"content": suffix, "usage": {"output_tokens": 2}}

    monkeypatch.setattr(service, "generate_content", fake_generate)
    import app.services.shot_generation_agentscope as repair_mod

    monkeypatch.setattr(repair_mod.llm_service, "chat_completion", fake_chat)

    async def _run():
        return await service.generate_content_with_fallback(
            "原任务",
            "系统",
            {
                "provider": "grsai",
                "model": "gemini-3.8-flash",
                "config": {"__resolved_setting_id": 1, "__active_retry_attempts": 2},
            },
            response_validator=_shot_validator(),
            validation_repair=lambda result, config, error: repair_shot_markdown_cell_count_rows(
                result,
                config,
                error,
                user_prompt="原任务",
                system_prompt="系统",
            ),
        )

    result = asyncio.run(_run())
    assert calls == ["gemini-3.8-flash"]
    assert len(chat_prompts) == 1
    assert "【上次输出】" in chat_prompts[0]
    assert "原任务" in chat_prompts[0]
    assert "好镜" in chat_prompts[0]
    assert chat_prompts[0].rstrip().endswith(cut.strip()) or "续镜" in chat_prompts[0]
    assert result["content"].startswith("场记说明")
    assert "好镜" in result["content"]
    assert inspect_complete_shot_markdown_return(result["content"]) == []
    assert result["usage"]["output_tokens"] == 10
    assert result.get("_shot_row_format_repair") == "continued"


def test_failed_continuation_does_not_regenerate_the_whole_table(monkeypatch):
    service = LLMService()
    calls = []
    fallbacks = [{"provider": "openai", "model": "gpt-backup", "config": {"__resolved_setting_id": 2}}]
    import app.services.agent_service as agent_mod

    monkeypatch.setattr(agent_mod, "agent_service", _FakeAgent(fallbacks))
    markdown = _table(_closed_row("EP01_SC01_SH01"), _cut_row("EP01_SC01_SH02"))

    async def fake_generate(user_prompt, system_prompt, config, image_urls=None, video_urls=None):
        calls.append(config.get("model"))
        return {"content": markdown, "usage": {}, "finish_reason": "stop"}

    async def fake_chat(messages, config):
        return {"content": "", "usage": {}}

    monkeypatch.setattr(service, "generate_content", fake_generate)
    import app.services.shot_generation_agentscope as repair_mod

    monkeypatch.setattr(repair_mod.llm_service, "chat_completion", fake_chat)

    async def _run():
        return await service.generate_content_with_fallback(
            "user",
            "system",
            {
                "provider": "grsai",
                "model": "gemini-3.8-flash",
                "config": {"__resolved_setting_id": 1, "__active_retry_attempts": 2},
            },
            response_validator=_shot_validator(),
            validation_repair=repair_shot_markdown_cell_count_rows,
        )

    result = asyncio.run(_run())
    assert calls == ["gemini-3.8-flash"]
    assert str(result["content"]).startswith("Error:")
    assert SHOT_GENERATION_INCOMPLETE_CODE in result["content"]
    assert result.get("_abort_full_retry") is True
