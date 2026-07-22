# -*- coding: utf-8 -*-
"""Story-generator LLM helpers (JSON normalize, structure call, episode refs)."""
from __future__ import annotations

import importlib
import json
import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.billing_service import billing_service
from app.services.db_session_utils import _release_db_connection
from app.services.episode_script_reference_service import (
    build_episode_script_reference_user_prompt,
    collect_episode_script_reference_snippets,
    extract_episode_block_from_global_framework,
)
from app.services.llm_service import llm_service
from app.services.model_invocation_billing import (
    _apply_llm_routing_to_billing_details,
    _reservation_tx_id,
)
from app.services.prompt_resolve import _resolve_prompt_text
from app.services.script_analysis_llm_config import _resolve_story_generator_script_analysis_llm_config

logger = logging.getLogger("api_logger")


def _loads_json5_if_available(text: str) -> Optional[Any]:
    raw = str(text or "")
    if not raw.strip():
        return None
    try:
        json5_mod = importlib.import_module("json5")
    except Exception:
        return None
    try:
        return json5_mod.loads(raw)
    except Exception:
        return None

_CREATIVE_INPUT_STRUCTURE_KEYS = [
    "logline",
    "theme",
    "core_conflict",
    "background",
    "characters",
    "setup",
    "development",
    "turning_points",
    "climax",
    "resolution",
    "suspense",
    "foreshadowing",
    "extra_notes",
]


def _sanitize_llm_json_text(raw: str) -> str:
    content = re.sub(r"<think>.*?</think>", "", str(raw or ""), flags=re.DOTALL | re.IGNORECASE).strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content, re.IGNORECASE)
    if fenced:
        content = fenced.group(1).strip()
    content = content.replace("```json", "").replace("```", "").strip()
    # Keep Unicode curly quotes inside JSON string values; converting them to ASCII "
    # breaks valid payloads like: "core_conflict": "隐藏"穿越者"身份".
    content = re.sub(r",\s*}", "}", content)
    content = re.sub(r",\s*]", "]", content)
    return content


def _extract_llm_json_object_from_text(raw: str) -> Optional[Dict[str, Any]]:
    text = _sanitize_llm_json_text(raw)
    if not text:
        return None

    json5_obj = _loads_json5_if_available(text)
    if isinstance(json5_obj, dict):
        return json5_obj

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        candidate = text[start_idx:end_idx + 1]
        json5_obj = _loads_json5_if_available(candidate)
        if isinstance(json5_obj, dict):
            return json5_obj
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            parsed, _end = decoder.raw_decode(text[idx:])
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


def _normalize_llm_json_object(raw: str, *, context: str) -> Dict[str, Any]:
    data = _extract_llm_json_object_from_text(raw)
    if not isinstance(data, dict):
        logger.error("[%s] JSON parse failed. Raw len=%s", context, len(raw or ""))
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM JSON for {context}")
    return data


async def _normalize_llm_json_object_with_repair(
    raw: str,
    *,
    context: str,
    llm_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data = _extract_llm_json_object_from_text(raw)
    if isinstance(data, dict):
        return data

    content = _sanitize_llm_json_text(raw)
    if not content or not llm_config:
        logger.error("[%s] JSON parse failed and repair unavailable. Raw len=%s", context, len(raw or ""))
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM JSON for {context}")

    repair_system = (
        "You are a strict JSON formatter. "
        "Convert the user's text into one valid JSON object only. "
        "The first character must be '{' and the last character must be '}'. "
        "Escape internal double quotes inside strings as \\\". "
        "No markdown fences, no explanation, no extra text."
    )
    repair_user = (
        "Fix the following content into valid JSON while preserving fields and values as much as possible.\n\n"
        f"{content}"
    )
    try:
        repair_response = await llm_service.chat_completion_with_fallback(
            [
                {"role": "system", "content": repair_system},
                {"role": "user", "content": repair_user},
            ],
            llm_config,
        )
        repair_raw = str((repair_response or {}).get("content") or "").strip()
        repaired = _extract_llm_json_object_from_text(repair_raw)
        if isinstance(repaired, dict):
            logger.warning("[%s] JSON parse recovered via repair pass", context)
            return repaired
    except Exception as exc:
        logger.warning("[%s] JSON repair pass failed: %s", context, exc)

    logger.error("[%s] JSON parse failed after repair. Raw len=%s", context, len(raw or ""))
    raise HTTPException(status_code=500, detail=f"Failed to parse LLM JSON for {context}")


def _normalize_story_field_map(data: Dict[str, Any], keys: List[str]) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    for key in keys:
        val = data.get(key, "")
        if val is None:
            normalized[key] = ""
        elif isinstance(val, str):
            normalized[key] = val.strip()
        else:
            normalized[key] = str(val).strip()
    return normalized


async def _run_structure_llm_call(
    *,
    db: Session,
    user_id: int,
    project_global_info: Optional[Dict[str, Any]],
    req: Any,
    sys_prompt: str,
    user_prompt: str,
    billing_item: str,
    llm_context: str,
) -> str:
    function_name = (getattr(req, "function_name", None) if req else None) or "script_analysis"
    system_api_id = getattr(req, "system_api_id", None) if req else None
    llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        user_id,
        function_name=function_name,
        system_api_id=system_api_id,
        context=llm_context,
        project_global_info=project_global_info,
    )
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured in active settings")
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None
    reservation_tx = None
    if billing_service.is_token_pricing(db, "llm_chat", provider, model):
        est = billing_service.estimate_reserve_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        reservation_tx = billing_service.reserve_credits(
            db,
            user_id,
            "llm_chat",
            provider,
            model,
            {
                "item": billing_item,
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            },
        )
    else:
        billing_service.check_balance(db, user_id, "llm_chat", provider, model)

    try:
        _release_db_connection(db, f"{llm_context}_llm_call")
        resp = await llm_service.generate_content_with_fallback(user_prompt, sys_prompt, llm_config)
    except Exception as e:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(e))
        raise

    raw = (resp.get("content") or "").strip()
    if not raw:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), "LLM returned empty content")
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    usage = resp.get("usage") or {}
    if not usage:
        usage = billing_service.estimate_input_output_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": raw},
            ],
            output_ratio=1.0,
        )
    billing_details = {
        "item": billing_item,
        "prompt_tokens": int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0),
        "completion_tokens": int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
        "total_tokens": int(
            usage.get(
                "total_tokens",
                int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
                + int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
            )
            or 0
        ),
    }
    billing_details["input_tokens"] = billing_details["prompt_tokens"]
    billing_details["output_tokens"] = billing_details["completion_tokens"]
    _apply_llm_routing_to_billing_details(billing_details, resp)

    if reservation_tx:
        billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), billing_details)
    else:
        billing_service.deduct_credits(db, user_id, "llm_chat", provider, model, billing_details)

    return raw


async def _prepare_episode_script_reference_block(
    *,
    user_id: int,
    project_global_info: Optional[Dict[str, Any]],
    llm_config: Dict[str, Any],
    global_md: str,
    episode_number: int,
    project_title: str = "",
    language: str = "",
) -> str:
    """Extract current-episode framework block, LLM key elements, web search (10 snippets), format for user prompt."""
    episode_block = extract_episode_block_from_global_framework(global_md, episode_number)
    if not episode_block.strip():
        logger.info(
            "[generate_episode_scripts] REFERENCE_SEARCH_SKIP episode_number=%s reason=empty_episode_block",
            episode_number,
        )
        return ""

    try:
        extract_prompt_template = _resolve_prompt_text("story_generator_episode_extract_key_elements.txt")
    except FileNotFoundError:
        logger.warning(
            "[generate_episode_scripts] REFERENCE_SEARCH_SKIP episode_number=%s reason=missing_extract_prompt",
            episode_number,
        )
        return ""

    try:
        extract_sys_prompt = extract_prompt_template.format(episode_block=episode_block)
    except Exception:
        extract_sys_prompt = extract_prompt_template

    extract_user_prompt = (
        f"Project Title: {project_title or '(none)'}\n"
        f"Episode Number: {episode_number}\n"
        f"Preferred Language: {language or 'zh'}\n\n"
        "Extract searchable key elements from this episode's framework block, with emphasis on climax moments, iconic scenes, golden quotes, and trope patterns."
    )

    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None
    reservation_tx = None
    key_elements: Dict[str, Any] = {}

    ref_db = SessionLocal()
    try:
        if billing_service.is_token_pricing(ref_db, "llm_chat", provider, model):
            est = billing_service.estimate_reserve_tokens_from_messages(
                [
                    {"role": "system", "content": extract_sys_prompt},
                    {"role": "user", "content": extract_user_prompt},
                ],
            )
            reservation_tx = billing_service.reserve_credits(
                ref_db,
                user_id,
                "llm_chat",
                provider,
                model,
                {
                    "item": "episode_extract_key_elements",
                    "episode_number": episode_number,
                    "estimation_method": "prompt_tokens_ratio",
                    "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                    "input_tokens": est.get("input_tokens", 0),
                    "output_tokens": est.get("output_tokens", 0),
                    "total_tokens": est.get("total_tokens", 0),
                },
            )
        else:
            billing_service.check_balance(ref_db, user_id, "llm_chat", provider, model)

        _release_db_connection(ref_db, f"episode_extract_key_elements_ep{episode_number}_llm_call")
        ref_db = None
        resp = await llm_service.generate_content_with_fallback(extract_user_prompt, extract_sys_prompt, llm_config)
        raw = (resp.get("content") or "").strip()
        if not raw:
            raise RuntimeError("LLM returned empty content for episode key-element extraction")

        usage = resp.get("usage") or {}
        if not usage:
            usage = billing_service.estimate_input_output_tokens_from_messages(
                [
                    {"role": "system", "content": extract_sys_prompt},
                    {"role": "user", "content": extract_user_prompt},
                    {"role": "assistant", "content": raw},
                ],
                output_ratio=1.0,
            )
        billing_details = {
            "item": "episode_extract_key_elements",
            "episode_number": episode_number,
            "prompt_tokens": int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0),
            "completion_tokens": int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
            "total_tokens": int(
                usage.get(
                    "total_tokens",
                    int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
                    + int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
                )
                or 0
            ),
        }
        billing_details["input_tokens"] = billing_details["prompt_tokens"]
        billing_details["output_tokens"] = billing_details["completion_tokens"]
        _apply_llm_routing_to_billing_details(billing_details, resp)

        settle_db = SessionLocal()
        try:
            if reservation_tx:
                billing_service.settle_reservation(settle_db, _reservation_tx_id(reservation_tx), billing_details)
            else:
                billing_service.deduct_credits(settle_db, user_id, "llm_chat", provider, model, billing_details)
        finally:
            settle_db.close()

        key_elements = _normalize_llm_json_object(raw, context="episode_extract_key_elements")
    except Exception as exc:
        if reservation_tx:
            cancel_db = SessionLocal()
            try:
                billing_service.cancel_reservation(cancel_db, _reservation_tx_id(reservation_tx), str(exc))
            finally:
                cancel_db.close()
        if ref_db is not None:
            try:
                ref_db.close()
            except Exception:
                pass
        logger.warning(
            "[generate_episode_scripts] REFERENCE_SEARCH_KEY_EXTRACT_FAILED episode_number=%s err=%s",
            episode_number,
            exc,
        )
        key_elements = {
            "conflict_hooks": [episode_block[:240]],
            "iconic_scene_search_terms": [f"第{episode_number}集 短剧 名场面"],
            "climax_search_terms": [f"第{episode_number}集 高潮 反转"],
        }
    finally:
        if ref_db is not None:
            try:
                ref_db.close()
            except Exception:
                pass

    try:
        search_bundle = await collect_episode_script_reference_snippets(
            key_elements,
            episode_number=episode_number,
        )
    except Exception as exc:
        logger.warning(
            "[generate_episode_scripts] REFERENCE_SEARCH_FAILED episode_number=%s err=%s",
            episode_number,
            exc,
        )
        return ""

    snippet_count = len(search_bundle.get("snippets") or [])
    rendered_snippet_count = int(search_bundle.get("rendered_snippet_count") or 0)
    reference_text = build_episode_script_reference_user_prompt(
        search_bundle,
        key_elements,
        episode_number=episode_number,
        episode_block=episode_block,
        project_title=project_title,
        language=language,
    )
    rendered_snippet_count = int(search_bundle.get("rendered_snippet_count") or rendered_snippet_count)
    logger.info(
        "[generate_episode_scripts] REFERENCE_SEARCH_OK episode_number=%s episode_block_len=%s query_count=%s snippet_count=%s rendered_snippet_count=%s reference_block_len=%s",
        episode_number,
        len(episode_block),
        len(search_bundle.get("queries") or []),
        snippet_count,
        rendered_snippet_count,
        len(reference_text),
    )
    if not reference_text.strip():
        return ""

    return reference_text + "\n\n"
