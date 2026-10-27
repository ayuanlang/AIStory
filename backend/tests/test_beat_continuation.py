"""Beat-scoped continuation for truncated scene subskill output."""

from app.services.scene_subskill_pipeline_runner import (
    FRAMING_PROMPT,
    STAGING_PROMPT,
    beat_continuation_progressed,
    build_beat_continuation_input,
    merge_beat_continuation,
)


def _framing_beat(beat_id: int, *, closed: bool = True) -> str:
    body = (
        f"[BEAT_START:{beat_id}]\n"
        "【角色道具世界分布图】\n"
        f"当前环境=0度总裁办\n"
        "景别=MS\n"
    )
    if closed:
        body += f"[BEAT_END:{beat_id}]"
    return body


def _staging_beat(beat_id: int, *, closed: bool = True, with_action: bool = True) -> str:
    body = (
        f"[BEAT_START:{beat_id}]\n"
        "────【建置】────\n"
        "人在桌边。\n"
    )
    if with_action:
        body += "────【入戏】────\n他坐下。\n"
    if closed:
        body += f"[BEAT_END:{beat_id}]"
    return body


def test_merge_appends_new_beats_and_drops_repeated_tail():
    base = "\n".join(
        [
            "[SCENE_START:EP01_SC01]",
            "[BEAT_STREAM_START]",
            _framing_beat(1),
            _framing_beat(2),
            _framing_beat(3),
            _framing_beat(4, closed=False),
        ]
    )
    continuation = "\n".join(
        [
            _framing_beat(2),
            _framing_beat(3),
            _framing_beat(4),
            _framing_beat(5),
            "[BEAT_STREAM_END]",
            "[DERIVED_FRAMING_OUTPUT_END]",
        ]
    )
    merged = merge_beat_continuation(base, continuation, FRAMING_PROMPT)
    assert merged.count("[BEAT_START:2]") == 1
    assert merged.count("[BEAT_START:3]") == 1
    assert "[BEAT_START:4]" in merged and "[BEAT_END:4]" in merged
    assert "[BEAT_START:5]" in merged
    assert merged.index("[BEAT_END:3]") < merged.index("[BEAT_START:4]")
    assert merged.index("[BEAT_END:4]") < merged.index("[BEAT_START:5]")
    assert "[SCENE_START:EP01_SC01]" in merged
    assert merged.strip().endswith("[DERIVED_FRAMING_OUTPUT_END]")
    assert beat_continuation_progressed(base, merged, FRAMING_PROMPT)


def test_incomplete_staging_beat_is_rewritten_not_duplicated():
    base = "\n".join([_staging_beat(1), _staging_beat(2, with_action=False)])
    continuation = "\n".join(
        [
            _staging_beat(2),
            _staging_beat(3),
            "[STAGING_ENV_OUTPUT_END]",
        ]
    )
    merged = merge_beat_continuation(base, continuation, STAGING_PROMPT)
    assert merged.count("[BEAT_START:2]") == 1
    assert "────【入戏】────" in merged.split("[BEAT_START:2]", 1)[1]
    assert "[BEAT_START:3]" in merged
    assert "[STAGING_ENV_OUTPUT_END]" in merged


def test_continuation_input_uses_only_the_last_three_finished_beats():
    kept = [(str(index), _framing_beat(index)) for index in range(1, 6)]
    text = build_beat_continuation_input(
        "场头原文",
        kept,
        "6",
        FRAMING_PROMPT,
        beats_already_closed=False,
    )
    assert "[BEAT_START:1]" not in text
    assert "[BEAT_START:2]" not in text
    assert "[BEAT_START:3]" in text
    assert "[BEAT_START:4]" in text
    assert "[BEAT_START:5]" in text
    assert "从 Beat 6 接着写" in text
    assert "场头原文" in text
    assert "不是本次输入" in text
    assert "上次输出：" in text


def test_closed_stream_asks_only_for_the_end_marker():
    kept = [(str(index), _staging_beat(index)) for index in (1, 2, 3)]
    text = build_beat_continuation_input(
        "场头",
        kept,
        "4",
        STAGING_PROMPT,
        beats_already_closed=True,
    )
    assert "不要再写新拍" in text
    assert "[STAGING_ENV_OUTPUT_END]" in text
    assert "从 Beat 4 接着写" not in text


def test_same_beats_do_not_count_as_progress():
    base = _framing_beat(1)
    assert beat_continuation_progressed(base, base, FRAMING_PROMPT) is False
