"""Stream aggregation must not double Responses-API full-text snapshots."""


def test_coalesce_streamed_assistant_text_skips_exact_snapshot_replay():
    from app.services.llm_service import LLMService

    table = (
        "### Subject Index\n"
        "| subject_no | subject_type |\n"
        "| S001 | character |\n"
        "| S002 | cover_poster |\n"
    )
    # Simulate deltas then a done/completed full snapshot (same body).
    acc = ""
    for piece in ("### Subject Index\n", "| subject_no | subject_type |\n", "| S001 | character |\n", "| S002 | cover_poster |\n"):
        acc = LLMService._coalesce_streamed_assistant_text(acc, piece)
    doubled = LLMService._coalesce_streamed_assistant_text(acc, table)
    assert doubled == acc
    assert doubled.count("Subject Index") == 1
    assert doubled.count("S001") == 1


def test_coalesce_streamed_assistant_text_replaces_with_longer_snapshot():
    from app.services.llm_service import LLMService

    acc = LLMService._coalesce_streamed_assistant_text("", "Hello")
    acc = LLMService._coalesce_streamed_assistant_text(acc, " world")
    # Snapshot includes a trailing period deltas missed.
    acc = LLMService._coalesce_streamed_assistant_text(acc, "Hello world.")
    assert acc == "Hello world."


def test_coalesce_streamed_assistant_text_appends_normal_deltas():
    from app.services.llm_service import LLMService

    acc = ""
    for piece in ("A", "B", "C"):
        acc = LLMService._coalesce_streamed_assistant_text(acc, piece)
    assert acc == "ABC"


def test_extract_stream_marks_snapshot_event_types():
    from app.services.llm_service import LLMService

    svc = LLMService()
    assert "response.output_text.done" in svc._STREAM_FULL_TEXT_SNAPSHOT_TYPES
    assert "response.completed" in svc._STREAM_FULL_TEXT_SNAPSHOT_TYPES

    text, finish = svc._extract_stream_chunk_text_and_finish({
        "type": "response.output_text.delta",
        "delta": "Hello",
    })
    assert text == "Hello"
    assert finish is None

    text, finish = svc._extract_stream_chunk_text_and_finish({
        "type": "response.output_text.done",
        "text": "Hello",
    })
    assert text == "Hello"
    assert finish is None


def test_responses_api_terminal_events_are_stream_stop_signals():
    """KIE GPT (e.g. gpt-5-6-luna) uses /codex/v1/responses and may never send [DONE]."""
    from app.services.llm_service import LLMService

    svc = LLMService()
    for event_type in (
        "response.completed",
        "response.failed",
        "response.incomplete",
        "error",
        "message_stop",
    ):
        assert event_type in svc._STREAM_TERMINAL_EVENT_TYPES

    text, finish = svc._extract_stream_chunk_text_and_finish({
        "type": "response.completed",
        "response": {
            "status": "completed",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "done-body"}]}],
        },
    })
    assert "done-body" in text
    assert finish == "completed"


def test_kie_responses_input_keeps_system_and_user_prompts():
    """KIE codex responses has no instructions field — system must be in input."""
    from app.services.llm_service import LLMService

    svc = LLMService()
    instructions, response_input = svc._build_kie_responses_input([
        {"role": "system", "content": "SYSTEM_RULES"},
        {"role": "user", "content": "USER_SCRIPT"},
        {"role": "assistant", "content": "PRIOR"},
    ])
    assert instructions == "SYSTEM_RULES"
    assert [row["role"] for row in response_input] == ["system", "user", "assistant"]
    assert response_input[0]["content"] == [{"type": "input_text", "text": "SYSTEM_RULES"}]
    assert response_input[1]["content"] == [{"type": "input_text", "text": "USER_SCRIPT"}]
    assert response_input[2]["content"] == [{"type": "output_text", "text": "PRIOR"}]
