# -*- coding: utf-8 -*-
"""Section routes — symbols pulled from shared module."""
from __future__ import annotations

from app.api.routers.tools_agent_pkg import shared as _shared

router = _shared.router
globals().update(
    {
        k: v
        for k, v in vars(_shared).items()
        if k
        not in {
            "__name__",
            "__file__",
            "__package__",
            "__loader__",
            "__spec__",
            "__doc__",
            "__builtins__",
        }
    }
)


# --- Agent Streaming (SSE) ---

async def _sse_event_generator(events_gen):
    """Wrap an async generator of dicts into SSE-formatted text lines."""
    import json as _json
    try:
        from contextlib import aclosing
        async with aclosing(events_gen) as _stream:
            async for event in _stream:
                if event is None:
                    continue
                event_type = event.get("type", "message")
                data = _json.dumps(event, ensure_ascii=False, default=str)
                yield f"event: {event_type}\ndata: {data}\n\n"
    except Exception as exc:
        logger.error("SSE generator error: %s", exc)
        err = _json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False)
        yield f"event: error\ndata: {err}\n\n"


@router.post("/agent/command/stream")
async def stream_agent_command(
    request: AgentRequest,
    current_user: User = Depends(get_current_user),
):
    current_user_snapshot = _snapshot_user_principal(current_user)
    current_user_id = int(getattr(current_user_snapshot, "id", 0) or 0)
    current_user_is_superuser = bool(getattr(current_user_snapshot, "is_superuser", False))
    current_user_is_authorized = bool(getattr(current_user_snapshot, "is_authorized", False))
    current_user_username = getattr(current_user_snapshot, "username", None)
    print(f"[STREAM-DEBUG] === stream_agent_command entered === query={request.query[:80] if request.query else 'N/A'}, user={current_user_id}")
    project_id = request.project_id or request.context.get("projectId")
    if project_id:
        with SessionLocal() as auth_db:
            _require_project_access(auth_db, int(project_id), current_user_snapshot)

    agent_function_name = (
        getattr(request, "function_name", None)
        or (request.context or {}).get("function_name")
        or "ai_assistant"
    )
    agent_system_api_id = getattr(request, "system_api_id", None) or (request.context or {}).get("system_api_id")

    resolved_llm_config = agent_service.get_active_llm_config(
        current_user_id,
        category="LLM",
        function_name=agent_function_name,
        system_api_id=agent_system_api_id,
    )
    if not resolved_llm_config or not resolved_llm_config.get("api_key"):
        raise HTTPException(status_code=400, detail="No active LLM API config found. Please check your LLM settings.")

    provider = resolved_llm_config.get("provider")
    model = resolved_llm_config.get("model")

    merged_context = dict(request.context or {})
    merged_context["agent_mode"] = "project"
    merged_context["auth"] = {
        "user_id": current_user_id,
        "is_superuser": current_user_is_superuser,
        "is_authorized": current_user_is_authorized,
        "username": current_user_username,
    }

    request_for_agent = request.copy(update={
        "llm_config": resolved_llm_config,
        "context": merged_context,
    })

    # Billing: simple deduction (streaming cannot easily do reservation/settlement)
    with SessionLocal() as billing_db:
        billing_service.check_balance(billing_db, current_user_id, "llm_chat", provider, model)
    print(f"[STREAM-DEBUG] endpoint: billing OK, calling stream_process_command, provider={provider}, model={model}")

    async def _generate():
        print(f"[STREAM-DEBUG] _generate() started iterating stream_process_command")
        try:
            from contextlib import aclosing
            async with aclosing(agent_service.stream_process_command(request_for_agent, current_user_snapshot)) as _stream:
                async for event in _stream:
                    if event.get("type") == "heartbeat":
                        yield event
                        continue
                    print(f"[STREAM-DEBUG] endpoint yielding event: type={event.get('type')}, content_len={len(str(event.get('content','')))}, keys={list(event.keys())}")
                    yield event
            # Billing deduction after successful completion
            with SessionLocal() as billing_db:
                billing_service.deduct_credits(
                    billing_db,
                    current_user_id,
                    "llm_chat",
                    provider,
                    model,
                    {"item": "agent_intent_stream", "query": (request.query or "")[:80]},
                )
        except Exception as e:
            logger.error("stream_agent_command error: %s", e)
            try:
                with SessionLocal() as billing_db:
                    billing_service.log_failed_transaction(billing_db, current_user_id, "llm_chat", provider, model, str(e))
            except Exception:
                logger.warning("stream_agent_command failed to record billing failure", exc_info=True)
            yield {"type": "error", "message": str(e)}

    return StreamingResponse(
        _sse_event_generator(_generate()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/agent/system-management/command/stream")
async def stream_system_management_agent_command(
    request: AgentRequest,
    current_user: User = Depends(get_current_user),
):
    current_user_snapshot = _snapshot_user_principal(current_user)
    current_user_id = int(getattr(current_user_snapshot, "id", 0) or 0)
    current_user_is_superuser = bool(getattr(current_user_snapshot, "is_superuser", False))
    if not current_user_is_superuser:
        raise HTTPException(status_code=403, detail="Only superuser can use system management AI agent")

    agent_function_name = (
        getattr(request, "function_name", None)
        or (request.context or {}).get("function_name")
        or "ai_assistant"
    )
    agent_system_api_id = getattr(request, "system_api_id", None) or (request.context or {}).get("system_api_id")

    resolved_llm_config = agent_service.get_active_llm_config(
        current_user_id,
        category="LLM",
        function_name=agent_function_name,
        system_api_id=agent_system_api_id,
    )
    if not resolved_llm_config or not resolved_llm_config.get("api_key"):
        raise HTTPException(status_code=400, detail="No active LLM API config found. Please check your LLM settings.")

    provider = resolved_llm_config.get("provider")
    model = resolved_llm_config.get("model")

    with SessionLocal() as billing_db:
        billing_service.check_balance(billing_db, current_user_id, "llm_chat", provider, model)

    async def _generate():
        try:
            from contextlib import aclosing
            async with aclosing(agent_service.stream_process_system_management_command(request, current_user_snapshot)) as _stream:
                async for event in _stream:
                    yield event
            with SessionLocal() as billing_db:
                billing_service.deduct_credits(
                    billing_db,
                    current_user_id,
                    "llm_chat",
                    provider,
                    model,
                    {"item": "system_agent_intent_stream", "query": (request.query or "")[:80]},
                )
        except Exception as e:
            logger.error("stream_system_management_agent_command error: %s", e)
            try:
                with SessionLocal() as billing_db:
                    billing_service.log_failed_transaction(billing_db, current_user_id, "llm_chat", provider, model, str(e))
            except Exception:
                logger.warning("stream_system_management_agent_command failed to record billing failure", exc_info=True)
            yield {"type": "error", "message": str(e)}

    return StreamingResponse(
        _sse_event_generator(_generate()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )




