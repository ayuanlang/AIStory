# -*- coding: utf-8 -*-
from app.services.shot_generation_prompts import _build_ai_shots_response_validator
from app.services.shot_markdown import (
    SHOT_GENERATION_INCOMPLETE_CODE,
    _validate_shot_rows_for_apply_with_tolerance,
    collect_shot_generation_completeness_errors,
    format_shot_generation_incomplete_detail,
    inspect_complete_shot_markdown_return,
    parse_shots_markdown_table,
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
    "物理文字生成：无。<br>"
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


def test_finish_reason_incomplete_is_rejected_even_if_markdown_is_closed():
    markdown = _table(_closed_row("EP01_SC01_SH01"))
    errors = collect_shot_generation_completeness_errors(
        markdown_text=markdown,
        raw_text=markdown,
        finish_reason="incomplete",
    )
    assert "finish_reason=incomplete" in errors


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
