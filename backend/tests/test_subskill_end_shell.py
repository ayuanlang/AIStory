"""现场编排只交结束标签时，要把藏起来的正文捞回来，并在下一次点明上次是空壳。"""

from app.services.analyze_scene_text_ops import prepend_derived_framing_task


def test_framing_user_message_names_the_only_task():
    framed = prepend_derived_framing_task("[SCENES_BLOCK_START]\n场次素材\n[SCENES_BLOCK_END]")
    assert framed.startswith("【本次任务】按场景现场编排规范")
    assert "不要请用户选择是生成还是检查" in framed
    assert framed.index("【本次任务】") < framed.index("[SCENES_BLOCK_START]")
    continued = prepend_derived_framing_task("【上次输出】\n已写到一半")
    assert not continued.startswith("【本次任务】")

SHELL = (
    "[BEAT_STREAM_END] [SCENE_END:EP01_SC01] "
    "[SCENES_BLOCK_END] [DERIVED_FRAMING_OUTPUT_END]"
)
DRAFT = (
    "[SCENES_BLOCK_START]\n"
    "[SCENE_START:EP01_SC01]\n"
    "[DERIVED_ENV_EXTRACT_START]\n"
    "【全场调度】甲站在门内。\n"
    "[BEAT_START:1]\n"
    "甲站在门内。\n"
    "[BEAT_END:1]"
)


def test_visible_end_shell_matches_framing_closers():
    from app.services.llm_service import visible_text_is_end_shell

    assert visible_text_is_end_shell(SHELL)
    assert visible_text_is_end_shell("")
    assert not visible_text_is_end_shell("好的")
    assert not visible_text_is_end_shell(DRAFT)


def test_promote_think_draft_when_visible_is_only_closers():
    from app.services.llm_service import LLMService, promote_think_draft_when_visible_is_end_shell

    raw = f"<think>{DRAFT}</think>\n{SHELL}"
    promoted = promote_think_draft_when_visible_is_end_shell(raw)
    assert "[BEAT_START:1]" in promoted
    assert "[DERIVED_FRAMING_OUTPUT_END]" in promoted
    assert "<think>" not in promoted

    cleaned = LLMService().sanitize_text_output(raw)
    assert "[BEAT_START:1]" in cleaned
    assert "[DERIVED_FRAMING_OUTPUT_END]" in cleaned
    assert "<think>" not in cleaned


def test_promote_leaves_a_real_visible_body():
    from app.services.llm_service import promote_think_draft_when_visible_is_end_shell

    raw = f"<think>先想一下</think>\n{DRAFT}\n{SHELL}"
    assert promote_think_draft_when_visible_is_end_shell(raw) == raw


def test_merge_reasoning_only_when_content_is_end_shell():
    from app.services.llm_service import LLMService, merge_reasoning_when_visible_is_end_shell

    merged = merge_reasoning_when_visible_is_end_shell(SHELL, DRAFT)
    assert "[BEAT_START:1]" in merged
    assert "[DERIVED_FRAMING_OUTPUT_END]" in merged
    assert merge_reasoning_when_visible_is_end_shell(DRAFT, "另写一份推理") == DRAFT

    extracted = LLMService()._extract_text_from_response(
        {
            "choices": [
                {
                    "message": {
                        "content": SHELL,
                        "reasoning_content": DRAFT,
                    }
                }
            ]
        }
    )
    assert "[BEAT_START:1]" in extracted
    assert extracted.endswith("[DERIVED_FRAMING_OUTPUT_END]")


def test_stream_chunk_keeps_reasoning_draft_beside_closer_delta():
    from app.services.llm_service import LLMService

    text, finish = LLMService()._extract_stream_chunk_text_and_finish(
        {
            "choices": [
                {
                    "delta": {
                        "content": SHELL,
                        "reasoning_content": DRAFT,
                    },
                    "finish_reason": "stop",
                }
            ]
        }
    )
    assert "[BEAT_START:1]" in text
    assert finish == "stop"


def test_prepare_drops_reasoning_and_leaves_the_closer_shell():
    from app.services.scene_subskill_pipeline_runner import (
        _prepare_subskill_llm_text,
        _subskill_output_is_end_shell,
    )

    raw = f"<think>这一场对不上，先停。</think>\n{SHELL}"
    prepared = _prepare_subskill_llm_text(raw)
    assert _subskill_output_is_end_shell(prepared)
    assert "对不上" not in prepared

    recovered = _prepare_subskill_llm_text(f"<thinking>{DRAFT}</thinking>\n{SHELL}")
    assert "[BEAT_START:1]" in recovered
    assert "[DERIVED_FRAMING_OUTPUT_END]" in recovered
    assert "<thinking>" not in recovered


def test_gemini_thought_draft_replaces_end_shell():
    from app.services.llm_service import LLMService

    svc = LLMService()
    payload = {
        "candidates": [{
            "content": {
                "parts": [
                    {"text": DRAFT, "thought": True},
                    {"text": SHELL},
                ],
            },
            "finishReason": "STOP",
        }],
    }
    visible, thought, finish = svc._gemini_visible_and_thought(payload)
    assert visible == SHELL
    assert "[BEAT_START:1]" in thought
    assert finish == "stop"
    answer = svc._extract_text_from_response(payload)
    assert "[BEAT_START:1]" in answer
    assert answer.endswith("[DERIVED_FRAMING_OUTPUT_END]")

    ordinary = svc._extract_text_from_response({
        "candidates": [{
            "content": {
                "parts": [
                    {"text": "Beijing is clear.", "thought": True},
                    {"text": "Beijing is sunny."},
                ],
            },
        }],
    })
    assert ordinary == "Beijing is sunny."


def test_framing_opening_is_prefixed_once():
    from app.services.scene_subskill_pipeline_runner import (
        FRAMING_PROMPT,
        _with_framing_visible_opening,
    )

    once = _with_framing_visible_opening(FRAMING_PROMPT, "[SCENES_BLOCK_START]")
    assert once.startswith("可见回答从第一行")
    assert _with_framing_visible_opening(FRAMING_PROMPT, once) == once
    assert _with_framing_visible_opening("other.md", "正文") == "正文"


def test_framing_retry_note_names_the_missing_body():
    from app.services.scene_subskill_pipeline_runner import (
        FRAMING_PROMPT,
        _end_shell_retry_note,
        _subskill_output_is_end_shell,
    )

    assert _subskill_output_is_end_shell(SHELL)
    assert not _subskill_output_is_end_shell("")
    assert not _subskill_output_is_end_shell(DRAFT)
    note = _end_shell_retry_note(FRAMING_PROMPT, "EP01_SC01")
    assert "EP01_SC01" in note
    assert "全场调度" in note
    assert "[DERIVED_FRAMING_OUTPUT_END]" in note
    assert "[SCENES_BLOCK_START]" in note
