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


# --- Agent ---
@router.post("/agent/command", response_model=AgentResponse)
async def process_agent_command(
    request: AgentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    async_mode: str = Query("0"),
):
    current_user_snapshot = _snapshot_user_principal(current_user)
    current_user_id = int(getattr(current_user_snapshot, "id", 0) or 0)
    current_user_is_superuser = bool(getattr(current_user_snapshot, "is_superuser", False))
    current_user_is_authorized = bool(getattr(current_user_snapshot, "is_authorized", False))
    current_user_username = getattr(current_user_snapshot, "username", None)
    if async_mode == "1":
        tid = _submit_async(process_agent_command, user_id=current_user_id, kind="agent_command",
                            request=request, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    # Resolve Project ID
    project_id = request.project_id or request.context.get("projectId")
    
    if project_id:
        _require_project_access(db, int(project_id), current_user_snapshot)

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

    from app.services.script_analysis_llm_config import _inject_llm_call_log_trace
    resolved_llm_config = _inject_llm_call_log_trace(
        resolved_llm_config,
        user_id=current_user_id,
        user_name=current_user_username,
        project_id=(request.context or {}).get("project_id"),
        action_name="Agent对话",
    )

    provider = resolved_llm_config.get("provider")
    model = resolved_llm_config.get("model")
    resolved_cfg_meta = resolved_llm_config.get("config") if isinstance(resolved_llm_config.get("config"), dict) else {}
    logger.info(
        "[agent.command] resolved_user_active_llm | user_id=%s provider=%s model=%s setting_id=%s source=%s category=%s",
        current_user_id,
        provider,
        model,
        resolved_cfg_meta.get("__resolved_setting_id"),
        resolved_cfg_meta.get("__selection_source"),
        resolved_cfg_meta.get("__resolved_category"),
    )

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
    
    reservation_tx = None
    reserve_episode_id = None
    # Billing Check / Reserve
    # Only reserve for intent-analysis LLM call (skip refinement flow which doesn't call LLM)
    if (not request.context.get("is_refinement")) and billing_service.is_token_pricing(db, "llm_chat", provider, model):
        try:
            from app.services.llm_service import SYSTEM_PROMPT
        except Exception:
            SYSTEM_PROMPT = ""

        import json as _json
        messages_est = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"Current Project Context: {_json.dumps(request.context or {}, default=str)}"},
        ]
        for msg in (request.history or [])[-5:]:
            messages_est.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        messages_est.append({"role": "user", "content": request.query})

        est = billing_service.estimate_reserve_tokens_from_messages(messages_est)
        reserve_details = {
            "item": "agent_intent",
            "estimation_method": "prompt_tokens_ratio",
            "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
            "query_len": len(request.query or ""),
            "input_tokens": est.get("input_tokens", 0),
            "output_tokens": est.get("output_tokens", 0),
            "total_tokens": est.get("total_tokens", 0),
        }
        if request.project_id:
            reserve_details["project_id"] = int(request.project_id)
        _agent_episode_id = request.context.get("episode_id") or request.context.get("episodeId")
        if _agent_episode_id:
            try:
                reserve_episode_id = int(_agent_episode_id)
                reserve_details["episode_id"] = reserve_episode_id
            except Exception:
                pass
        reservation_tx = billing_service.reserve_credits(db, current_user_id, "llm_chat", provider, model, reserve_details)
    else:
        billing_service.check_balance(db, current_user_id, "llm_chat", provider, model)

    try:
        _release_db_connection(db, "agent_command_before_process")
        result = await agent_service.process_command(request_for_agent, db, current_user_snapshot)
        usage_payload = result.usage if isinstance(result.usage, dict) else {}
        _finalize_model_invocation_billing(
            db=db,
            current_user=current_user_snapshot,
            task_type="llm_chat",
            provider=provider,
            model=model,
            reservation_tx=reservation_tx,
            item="agent_intent",
            usage_payload=usage_payload,
            extra_details={
                "query": (request.query or "")[:50],
                "request_scope": "agent_command",
                **({"project_id": int(request.project_id)} if request.project_id else {}),
                **({"episode_id": int(reserve_episode_id)} if reserve_episode_id else {}),
            },
            routing_payload=result.dict() if hasattr(result, "dict") else None,
            cancel_if_missing_usage=True,
            missing_usage_reason="No usage returned",
        )
        
        return result
    except Exception as e:
        logger.error(f"Agent Command Failed: {e}")
        _cancel_reservation_quietly(db, reservation_tx, str(e))
        billing_service.log_failed_transaction(db, current_user_id, "llm_chat", provider, model, str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/system-management/command", response_model=AgentResponse)
async def process_system_management_agent_command(
    request: AgentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    async_mode: str = Query("0"),
):
    current_user_snapshot = _snapshot_user_principal(current_user)
    current_user_id = int(getattr(current_user_snapshot, "id", 0) or 0)
    current_user_is_superuser = bool(getattr(current_user_snapshot, "is_superuser", False))
    current_user_is_authorized = bool(getattr(current_user_snapshot, "is_authorized", False))
    current_user_username = getattr(current_user_snapshot, "username", None)
    if async_mode == "1":
        tid = _submit_async(process_system_management_agent_command, user_id=current_user_id,
                            kind="system_agent_command", request=request, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
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

    from app.services.script_analysis_llm_config import _inject_llm_call_log_trace
    resolved_llm_config = _inject_llm_call_log_trace(
        resolved_llm_config,
        user_id=current_user_id,
        user_name=current_user_username,
        action_name="系统管理Agent",
    )

    provider = resolved_llm_config.get("provider")
    model = resolved_llm_config.get("model")
    resolved_cfg_meta = resolved_llm_config.get("config") if isinstance(resolved_llm_config.get("config"), dict) else {}
    logger.info(
        "[agent.system_management.command] resolved_llm | user_id=%s provider=%s model=%s setting_id=%s source=%s category=%s",
        current_user_id,
        provider,
        model,
        resolved_cfg_meta.get("__resolved_setting_id"),
        resolved_cfg_meta.get("__selection_source"),
        resolved_cfg_meta.get("__resolved_category"),
    )

    reservation_tx = None
    if billing_service.is_token_pricing(db, "llm_chat", provider, model):
        import json as _json
        messages_est = [
            {"role": "system", "content": "System management agent mode"},
            {"role": "system", "content": f"Runtime Context: {_json.dumps(request.context or {}, default=str)}"},
        ]
        for msg in (request.history or [])[-5:]:
            messages_est.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        messages_est.append({"role": "user", "content": request.query})

        est = billing_service.estimate_reserve_tokens_from_messages(messages_est)
        reserve_details = {
            "item": "system_management_agent_intent",
            "estimation_method": "prompt_tokens_ratio",
            "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
            "query_len": len(request.query or ""),
            "input_tokens": est.get("input_tokens", 0),
            "output_tokens": est.get("output_tokens", 0),
            "total_tokens": est.get("total_tokens", 0),
        }
        if request.project_id:
            reserve_details["project_id"] = int(request.project_id)
        reservation_tx = billing_service.reserve_credits(db, current_user_id, "llm_chat", provider, model, reserve_details)
    else:
        billing_service.check_balance(db, current_user_id, "llm_chat", provider, model)

    try:
        _release_db_connection(db, "system_agent_command_before_process")
        request_for_system_agent = request.copy(update={
            "context": {
                **dict(request.context or {}),
                "auth": {
                    "user_id": current_user_id,
                    "is_superuser": current_user_is_superuser,
                    "is_authorized": current_user_is_authorized,
                    "username": current_user_username,
                },
            }
        })
        result = await agent_service.process_system_management_command(request_for_system_agent, db, current_user_snapshot)
        usage_payload = result.usage if isinstance(result.usage, dict) else {}
        _finalize_model_invocation_billing(
            db=db,
            current_user=current_user_snapshot,
            task_type="llm_chat",
            provider=provider,
            model=model,
            reservation_tx=reservation_tx,
            item="system_management_agent_intent",
            usage_payload=usage_payload,
            extra_details={
                "query": (request.query or "")[:80],
                "request_scope": "system_management_agent_command",
                **({"project_id": int(request.project_id)} if request.project_id else {}),
            },
            routing_payload=result.dict() if hasattr(result, "dict") else None,
            cancel_if_missing_usage=True,
            missing_usage_reason="No usage returned",
        )
        return result
    except PermissionError as e:
        _cancel_reservation_quietly(db, reservation_tx, str(e))
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"System Management Agent Command Failed: {e}")
        _cancel_reservation_quietly(db, reservation_tx, str(e))
        billing_service.log_failed_transaction(db, current_user_id, "llm_chat", provider, model, str(e))
        raise HTTPException(status_code=500, detail=str(e))


