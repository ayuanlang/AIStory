# -*- coding: utf-8 -*-
"""Tools + Agent routes (P4)."""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import SessionLocal, get_db
from app.models.all_models import User
from app.schemas.agent import AgentRequest, AgentResponse
from app.services.agent_service import agent_service
from app.services.billing_service import billing_service
from app.services.llm_service import llm_service

logger = logging.getLogger("api_logger")
router = APIRouter(tags=["tools-agent"])


def _bind_endpoint_helpers() -> None:
    from app.api.routers.helper_bind import bind_shared_helpers
    bind_shared_helpers(globals(), __name__)

_bind_endpoint_helpers()


# --- Tools ---
class TranslateRequest(BaseModel):
    q: str
    from_lang: str = 'en'
    to_lang: str = 'zh'

@router.post("/tools/translate")
async def translate_text(
    req: TranslateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(translate_text, user_id=current_user.id, kind="translate",
                            req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    request_id = uuid.uuid4().hex[:12]
    user_id = current_user.id
    user_name = current_user.username


    started_at = datetime.utcnow()
    text = str(req.q or "")
    from_lang = str(req.from_lang or "en").strip() or "en"
    to_lang = str(req.to_lang or "zh").strip() or "zh"

    lang_aliases = {
        "zh-cn": "zh",
        "zh_cn": "zh",
        "zh-hans": "zh",
        "zh-hant": "cht",
        "zh-tw": "cht",
        "zh_tw": "cht",
        "cn": "zh",
        "chs": "zh",
        "cht": "cht",
        "en-us": "en",
        "en_us": "en",
        "english": "en",
        "chinese": "zh",
    }
    from_lang = lang_aliases.get(from_lang.lower(), from_lang.lower())
    to_lang = lang_aliases.get(to_lang.lower(), to_lang.lower())

    llm_config = agent_service.get_active_llm_config(user_id, category="LLM")
    if not llm_config or not llm_config.get("api_key"):
        raise HTTPException(status_code=400, detail="Active LLM Settings not found. Please configure and activate an LLM provider.")

    provider = llm_config.get("provider") or "llm"
    model = llm_config.get("model") or "unknown"

    try:
        log_action(
            db,
            user_id=user_id,
            user_name=user_name,
            action="TRANSLATE_START",
            details=f"request_id={request_id}; from={from_lang}; to={to_lang}; chars={len(text)}; provider={provider}; model={model}"
        )
    except Exception as e:
        logger.warning(f"[translate:{request_id}] failed to write START system log: {e}")

    logger.info(
        f"[translate:{request_id}] start user_id={user_id} from={from_lang} to={to_lang} chars={len(text)} provider={provider} model={model}"
    )

    if from_lang == to_lang:
        logger.info(f"[translate:{request_id}] skip same language from={from_lang} to={to_lang}")
        return {"translated_text": text, "request_id": request_id}

    reservation_tx = None
    try:
        if billing_service.is_token_pricing(db, "llm_chat", provider, model):
            est = billing_service.estimate_reserve_tokens_from_messages(
                [{"role": "user", "content": text}],
                output_ratio=1.0
            )
            reserve_details = {
                "item": "translate",
                "request_id": request_id,
                "from_lang": from_lang,
                "to_lang": to_lang,
                "chars": len(text),
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": 1.0,
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            }
            reservation_tx = billing_service.reserve_credits(db, user_id, "llm_chat", provider, model, reserve_details)
        else:
            billing_service.check_balance(db, user_id, "llm_chat", provider, model)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[translate:{request_id}] pre-billing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Translation billing precheck failed. request_id={request_id}")

    lang_name = {
        "zh": "Simplified Chinese",
        "cht": "Traditional Chinese",
        "en": "English",
        "ja": "Japanese",
        "ko": "Korean",
        "fr": "French",
        "de": "German",
        "es": "Spanish",
        "ru": "Russian",
        "pt": "Portuguese",
    }
    from_lang_name = lang_name.get(from_lang, from_lang)
    to_lang_name = lang_name.get(to_lang, to_lang)
    system_prompt = (
        "You are a professional translation engine. "
        "Translate the user's text accurately while preserving original meaning, tone, named entities, and formatting. "
        "Do not explain. Return ONLY the translated text."
    )
    user_prompt = (
        f"Source Language: {from_lang_name} ({from_lang})\n"
        f"Target Language: {to_lang_name} ({to_lang})\n\n"
        "Text to translate:\n"
        f"{text}"
    )

    _release_db_connection(db, "translate_llm_call")

    try:
        llm_resp = await llm_service.generate_content_with_fallback(user_prompt, system_prompt, llm_config)
        dst = llm_service.sanitize_text_output(str(llm_resp.get("content") or "").strip())
        usage = llm_resp.get("usage") or {}

        if dst.lower().startswith("error:"):
            raise HTTPException(status_code=502, detail=f"LLM translate failed: {dst[:300]} (request_id={request_id})")

        if not dst:
            raise HTTPException(status_code=502, detail=f"Translation returned empty result (request_id={request_id})")

        if not usage:
            usage = billing_service.estimate_input_output_tokens_from_messages(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": dst},
                ],
                output_ratio=1.0,
            )

        prompt_tokens = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
        completion_tokens = int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0)
        total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens) or 0)

        if reservation_tx:
            actual_details = {
                "item": "translate",
                "request_id": request_id,
                "from_lang": from_lang,
                "to_lang": to_lang,
                "chars": len(text),
                "translated_chars": len(dst),
                "input_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
            _apply_llm_routing_to_billing_details(actual_details, llm_resp)
            billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), actual_details)
        else:
            deduct_details = {
                "item": "translate",
                "request_id": request_id,
                "from_lang": from_lang,
                "to_lang": to_lang,
                "chars": len(text),
                "translated_chars": len(dst),
                "input_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
            _apply_llm_routing_to_billing_details(deduct_details, llm_resp)
            billing_service.deduct_credits(
                db,
                user_id,
                "llm_chat",
                provider,
                model,
                deduct_details
            )

        elapsed_ms = int((datetime.utcnow() - started_at).total_seconds() * 1000)
        logger.info(
            f"[translate:{request_id}] success user_id={user_id} from={from_lang} to={to_lang} chars={len(text)} translated_chars={len(dst)} elapsed_ms={elapsed_ms}"
        )
        try:
            log_action(
                db,
                user_id=user_id,
                user_name=user_name,
                action="TRANSLATE_SUCCESS",
                details=f"request_id={request_id}; from={from_lang}; to={to_lang}; chars={len(text)}; translated_chars={len(dst)}; elapsed_ms={elapsed_ms}"
            )
        except Exception as e:
            logger.warning(f"[translate:{request_id}] failed to write SUCCESS system log: {e}")

        return {"translated_text": dst, "request_id": request_id}
    except HTTPException as e:
        if reservation_tx:
            try:
                billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(e.detail))
            except Exception:
                pass
        billing_service.log_failed_transaction(
            db,
            user_id,
            "llm_chat",
            provider,
            model,
            str(e.detail),
            {
                "item": "translate",
                "request_id": request_id,
                "from_lang": from_lang,
                "to_lang": to_lang,
                "chars": len(text),
            }
        )
        logger.warning(f"[translate:{request_id}] HTTPException: {e.detail}")
        try:
            log_action(
                db,
                user_id=user_id,
                user_name=user_name,
                action="TRANSLATE_FAILED",
                details=f"request_id={request_id}; error={str(e.detail)[:300]}"
            )
        except Exception as le:
            logger.warning(f"[translate:{request_id}] failed to write FAILED system log: {le}")
        raise
    except Exception as e:
        if reservation_tx:
            try:
                billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(e))
            except Exception:
                pass
        billing_service.log_failed_transaction(
            db,
            user_id,
            "llm_chat",
            provider,
            model,
            str(e),
            {
                "item": "translate",
                "request_id": request_id,
                "from_lang": from_lang,
                "to_lang": to_lang,
                "chars": len(text),
            }
        )
        logger.error(f"[translate:{request_id}] failed: {e}", exc_info=True)
        try:
            log_action(
                db,
                user_id=user_id,
                user_name=user_name,
                action="TRANSLATE_FAILED",
                details=f"request_id={request_id}; error={str(e)[:300]}"
            )
        except Exception as le:
            logger.warning(f"[translate:{request_id}] failed to write FAILED system log: {le}")
        raise HTTPException(status_code=500, detail=f"Translation failed. request_id={request_id}; reason={str(e)}")

class RefinePromptRequest(BaseModel):
    original_prompt: str
    instruction: str
    type: str = "image"


class TuneShotPromptRequest(BaseModel):
    original_prompt: str
    instruction: str
    prompt_lang: str = "cn"
    function_name: Optional[str] = "script_analysis"
    system_api_id: Optional[int] = None


_SHOT_PROMPT_MODIFICATION_SKILL = "skills/shot_prompt_modification.md"
_REFINED_PROMPT_START = "<<<REFINED_PROMPT_START>>>"
_REFINED_PROMPT_END = "<<<REFINED_PROMPT_END>>>"
_SHOT_PROMPT_OUTPUT_DELIMITER = "----------------*****--------------"


def _extract_refined_shot_prompt(raw_content: Any) -> str:
    text = llm_service.sanitize_text_output(str(raw_content or "")).strip()
    if not text:
        return ""

    delimiter_idx = text.find(_SHOT_PROMPT_OUTPUT_DELIMITER)
    if delimiter_idx >= 0:
        text = text[delimiter_idx + len(_SHOT_PROMPT_OUTPUT_DELIMITER):].strip()

    start_idx = text.find(_REFINED_PROMPT_START)
    end_idx = text.find(_REFINED_PROMPT_END)
    if start_idx >= 0 and end_idx > start_idx:
        extracted = text[start_idx + len(_REFINED_PROMPT_START):end_idx].strip()
        if extracted:
            return extracted

    # Fallback: strip common markdown fences if markers are missing.
    cleaned = re.sub(r"^```(?:markdown|md|text)?\s*", "", text, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


@router.post("/tools/tune_shot_prompt")
async def tune_shot_prompt(
    req: TuneShotPromptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(
            tune_shot_prompt,
            user_id=current_user.id,
            kind="tune_shot_prompt",
            req=req,
            async_mode="0",
        )
        return JSONResponse({"task_id": tid, "async": True})

    user_id = current_user.id
    original_prompt = str(req.original_prompt or "").strip()
    instruction = str(req.instruction or "").strip()
    if not original_prompt:
        raise HTTPException(status_code=400, detail="original_prompt is required")
    if not instruction:
        raise HTTPException(status_code=400, detail="instruction is required")

    function_name = _script_analysis_function_api_name(req.function_name or "script_analysis")
    config, selected_dropdown_id, _, _ = _resolve_script_analysis_dropdown_llm_config(
        db,
        user_id,
        function_name,
        req.system_api_id,
        context="tune_shot_prompt",
    )

    try:
        system_prompt = _resolve_prompt_text(_SHOT_PROMPT_MODIFICATION_SKILL)
    except Exception as exc:
        logger.error("Failed to load shot prompt modification skill: %s", exc)
        raise HTTPException(status_code=500, detail="Prompt file 'skills/shot_prompt_modification.md' could not be loaded.")

    prompt_lang = str(req.prompt_lang or "cn").strip().lower()
    lang_label = "中文" if prompt_lang in {"cn", "zh", "zh-cn", "chinese"} else "English"

    user_content = (
        f"# Original Prompt ({lang_label})\n{original_prompt}\n\n"
        f"# Modification Request\n{instruction}\n\n"
        "Apply the modification request to the original prompt. "
        "Return ONLY the required delimiter and tagged refined prompt."
    )

    _release_db_connection(db, "tune_shot_prompt_llm_call")

    try:
        llm_response = await llm_service.chat_completion_with_fallback(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            config,
        )
        raw_content = str((llm_response or {}).get("content", "") or "")
        refined_prompt = _extract_refined_shot_prompt(raw_content)
        if not refined_prompt:
            raise HTTPException(status_code=422, detail="LLM response did not contain a refined prompt between output markers.")

        return {
            "refined_prompt": refined_prompt,
            "system_api_id": selected_dropdown_id,
            "function_name": function_name,
        }
    except HTTPException:
        raise
    except Exception as exc:
        with SessionLocal() as error_db:
            billing_service.log_failed_transaction(
                error_db,
                user_id,
                "llm_chat",
                config.get("provider"),
                config.get("model"),
                str(exc),
            )
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/tools/refine_prompt")
async def refine_prompt(
    req: RefinePromptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(refine_prompt, user_id=current_user.id, kind="refine_prompt",
                            req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
        
    user_id = current_user.id
        
    # 1. Get LLM Config
    config = agent_service.get_active_llm_config(user_id)
    if not config or not config.get("api_key"):
        raise HTTPException(status_code=400, detail="Active LLM Settings not found. Please configure and activate an LLM provider.")
        
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    model = config.get("model")
    
    # Auto-adjust URL to Chat Completions
    url = base_url
    if not url.endswith("/chat/completions"):
        if url.endswith("/"): url += "chat/completions"
        elif "chat/completions" not in url: url += "/chat/completions"

    # 2. Build Prompt
    sys_prompt = "You are an expert storyboard artist."
    if req.type == "video":
        sys_prompt += " Your task is to refine the video generation prompt based on user feedback. Focus on modifying character actions, spatial relationships, and pose rationality without changing the main core content. Ensure the action is physically logical."
    else:
        sys_prompt += " Your task is to refine the image generation prompt based on user feedback. Focus on modifying character spatial relationships and poses without changing the main core content."
        
    sys_prompt += "\nConstraint: Return ONLY the refined prompt string. Do not include any explanations, markdown, quotes, or extra text."
    
    user_content = f"Original Prompt: {req.original_prompt}\nModification Request: {req.instruction}\nRefined Prompt:"
    
    # 3. Call LLM
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.7
    }
    
    try:
        def _post():
            return requests.post(url, json=payload, headers=headers, timeout=60)

        _release_db_connection(db, "refine_prompt_llm_call")

        response = await asyncio.to_thread(_post)
        if response.status_code != 200:
             raise HTTPException(status_code=500, detail=f"LLM Error {response.status_code}: {response.text}")
             
        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()
        content = llm_service.sanitize_text_output(content)
        # Clean quotes/markdown if any
        if content.startswith('"') and content.endswith('"'):
             content = content[1:-1]
        
        return {"refined_prompt": content}
    except Exception as e:
        with SessionLocal() as error_db:
            billing_service.log_failed_transaction(error_db, user_id, "llm_chat", config.get("provider"), model, str(e))
        raise HTTPException(status_code=500, detail=str(e))

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




# Refresh cross-router helpers after local definitions are complete.
_bind_endpoint_helpers()

