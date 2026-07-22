# -*- coding: utf-8 -*-
"""Voice / music generation runner."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.all_models import Episode, Scene, Shot, User
from app.schemas.generation import VoiceGenerationRequest
from app.services.billing_service import billing_service
from app.services.db_session_utils import _release_db_connection
from app.services.generation_runtime.api_capabilities import (
    _map_text_value_to_allowed,
    _read_api_capability_bool,
    _read_api_capability_list,
    _read_api_capability_number,
)
from app.services.generation_runtime.asset_registration import _register_asset_helper
from app.services.generation_runtime.callbacks import _merge_provider_task_ids_into_settle
from app.services.generation_runtime.generation_errors import _format_generation_failure_detail
from app.services.generation_runtime.generation_filename import _build_generation_filename_base
from app.services.generation_runtime.media_persist import (
    _persist_remote_media_result,
    _resolve_media_bind_url,
)
from app.services.generation_runtime.media_runtime_target import _resolve_media_runtime_target
from app.services.generation_runtime.project_generation_context import (
    _ensure_project_generation_seed,
    _normalize_seed_value,
    _resolve_effective_negative_prompt,
    _resolve_project_id_for_generation,
)
from app.services.generation_runtime.voice_planning import (
    _build_voice_suno_provider_options,
    _build_voice_tts_planner_prompts,
    _clamp_float,
    _extract_dialogue_text_for_tts,
    _is_suno_voice_runtime,
    _normalize_language_code,
    _plan_voice_params_with_llm,
    _sanitize_kie_tts_plan,
    _strip_subject_prompt_context_for_voice,
)
from app.services.media_service import media_service
from app.services.model_invocation_billing import (
    _extract_provider_usage_from_metadata,
    _reservation_tx_id,
    _resolve_usage_token_total,
)

logger = logging.getLogger("api_logger")


async def _run_generate_voice(
    req: VoiceGenerationRequest,
    current_user: User,
    db: Session,
):
    reservation_tx = None
    voice_task_type = "voice_gen"
    runtime_target = _resolve_media_runtime_target(
        provider=req.provider,
        model=req.model,
        media_type="voice",
        category="Voice",
        user_id=current_user.id,
        user_credits=(current_user.credits or 0),
        function_name=getattr(req, "function_name", None),
        system_api_id=getattr(req, "system_api_id", None),
    )
    runtime_llm_config = dict(runtime_target.get("runtime_llm_config") or {})
    pre_api_cfg = runtime_target.get("pre_api_cfg") or {}
    if isinstance(pre_api_cfg, dict) and pre_api_cfg:
        runtime_llm_config["__pre_resolved_api_config"] = dict(pre_api_cfg)
    reserve_provider = runtime_target.get("resolved_provider")
    reserve_model = runtime_target.get("resolved_model")
    reserve_system_api_id = runtime_target.get("resolved_system_api_id")
    is_token_billing = billing_service.is_token_pricing(db, voice_task_type, reserve_provider, reserve_model)

    try:
        stable_prompt_raw = str(req.prompt or "").strip()
        stable_prompt = _strip_subject_prompt_context_for_voice(stable_prompt_raw)
        if not stable_prompt:
            raise HTTPException(status_code=400, detail="Voice prompt is empty")

        # Early resolution of project/episode for billing
        voice_project_id = _normalize_seed_value(getattr(req, "project_id", None))
        voice_episode_id = None
        _voice_shot_id = _normalize_seed_value(getattr(req, "shot_id", None))
        if _voice_shot_id:
            _voice_shot = db.query(Shot).filter(Shot.id == _voice_shot_id).first()
            if _voice_shot and getattr(_voice_shot, "scene_id", None):
                _voice_scene = db.query(Scene).filter(Scene.id == _voice_shot.scene_id).first()
                if _voice_scene and _voice_scene.episode_id:
                    voice_episode_id = int(_voice_scene.episode_id)
                    if not voice_project_id:
                        _voice_ep = db.query(Episode).filter(Episode.id == voice_episode_id).first()
                        if _voice_ep and _voice_ep.project_id:
                            voice_project_id = int(_voice_ep.project_id)

        if is_token_billing:
            est_messages = [{"role": "user", "content": stable_prompt}]
            est_usage = billing_service.estimate_input_output_tokens_from_messages(est_messages, output_ratio=1.2)
            reserve_details = {
                "input_tokens": int(est_usage.get("input_tokens") or 0),
                "output_tokens": int(est_usage.get("output_tokens") or 0),
                "total_tokens": int(est_usage.get("total_tokens") or 0),
                "billing_mode": "RESERVE",
                "estimation_method": "voice_prompt_tokens",
            }
        else:
            reserve_details = {
                "duration": 5,
                "duration_seconds": 5,
                "billing_mode": "RESERVE",
            }

        if reserve_provider:
            reserve_details["provider"] = reserve_provider
            reserve_details["resolved_provider"] = reserve_provider
        if reserve_model:
            reserve_details["model"] = reserve_model
            reserve_details["resolved_model"] = reserve_model
        if reserve_system_api_id is not None:
            reserve_details["system_api_id"] = reserve_system_api_id
            reserve_details["resolved_system_api_id"] = reserve_system_api_id
        if voice_project_id:
            reserve_details["project_id"] = voice_project_id
        if voice_episode_id:
            reserve_details["episode_id"] = voice_episode_id

        reservation_tx = billing_service.reserve_credits(
            db,
            current_user.id,
            voice_task_type,
            reserve_provider,
            reserve_model,
            reserve_details,
        )

        resolved_project_id = _resolve_project_id_for_generation(req, db)
        project_seed = _ensure_project_generation_seed(db, resolved_project_id, current_user)
        explicit_seed = _normalize_seed_value(getattr(req, "seed", None))

        extracted_dialogue = _extract_dialogue_text_for_tts(stable_prompt)
        extracted_dialogue_lines = [line for line in str(extracted_dialogue or "").splitlines() if str(line or "").strip()]
        has_explicit_dialogue = bool(extracted_dialogue_lines)

        provider_options: Dict[str, Any] = _build_voice_suno_provider_options(req)
        planned_payload: Dict[str, Any] = {}
        planner_system_prompt = ""
        planner_user_prompt = ""
        planner_prompt_meta: Dict[str, Any] = {}
        effective_prompt = stable_prompt
        explicit_language_code = _normalize_language_code(req.language_code)
        explicit_project_language = str(req.project_language or "").strip()
        is_suno_voice = _is_suno_voice_runtime(reserve_model, provider_options)

        if bool(req.use_llm_param_planning) and not is_suno_voice:
            # Strict mode: voice TTS input must come from planner-extracted dialogue only.
            effective_prompt = ""
            planner_system_prompt, planner_user_prompt, planner_prompt_meta = _build_voice_tts_planner_prompts(stable_prompt)
            planner_system_prompt_override = str(req.planner_system_prompt or "").strip()
            if planner_system_prompt_override:
                planner_system_prompt = planner_system_prompt_override
                planner_prompt_meta = {
                    **(planner_prompt_meta or {}),
                    "template_source": "superuser_override",
                    "system_prompt_len": len(planner_system_prompt),
                    "user_prompt_len": len(planner_user_prompt or ""),
                }
            logger.info(
                "[GenerateVoice] planner prompts | user_id=%s source=%s system_prompt_len=%s user_prompt_len=%s",
                current_user.id,
                planner_prompt_meta.get("template_source"),
                planner_prompt_meta.get("system_prompt_len"),
                planner_prompt_meta.get("user_prompt_len"),
            )
            try:
                _release_db_connection(db, "generate_voice_planner_llm_call")
                planned_payload = await _plan_voice_params_with_llm(
                    current_user.id,
                    stable_prompt,
                    planner_prompts=(planner_system_prompt, planner_user_prompt),
                )
            except Exception as planning_err:
                logger.warning("[GenerateVoice] LLM planning failed: %s", planning_err)
                planned_payload = {}

            if planned_payload:
                raw_planned_text = str((planned_payload or {}).get("text") or "").strip()
                planned_payload = _sanitize_kie_tts_plan(planned_payload)
                planned_text = str(planned_payload.get("text") or "").strip()
                non_dialogue_text_stripped = bool(raw_planned_text) and (raw_planned_text != planned_text)
                fallback_dialogue_used = False
                logger.warning(
                    "[GenerateVoice] dialogue extraction | user_id=%s prompt_chars=%s has_explicit_dialogue=%s dialogue_line_count=%s dialogue_chars=%s planned_text_chars=%s fallback_dialogue_used=%s non_dialogue_text_stripped=%s",
                    current_user.id,
                    len(stable_prompt),
                    has_explicit_dialogue,
                    len(extracted_dialogue_lines),
                    len(extracted_dialogue),
                    len(planned_text),
                    fallback_dialogue_used,
                    non_dialogue_text_stripped,
                )
                if planned_text:
                    effective_prompt = planned_text
                    effective_prompt = _extract_dialogue_text_for_tts(effective_prompt)
                for key in [
                    "text",
                    "voice",
                    "language_code",
                    "stability",
                    "similarity_boost",
                    "style",
                    "speed",
                    "timestamps",
                    "previous_text",
                    "next_text",
                ]:
                    if planned_payload.get(key) is not None:
                        provider_options[key] = planned_payload.get(key)

                if planned_text:
                    provider_options["text"] = planned_text
                    logger.info(
                        "[GenerateVoice] planner text applied | user_id=%s raw_len=%s sanitized_len=%s preview=%s",
                        current_user.id,
                        len(raw_planned_text),
                        len(planned_text),
                        planned_text[:120],
                    )
            else:
                logger.warning(
                    "[GenerateVoice] dialogue extraction | user_id=%s prompt_chars=%s has_explicit_dialogue=%s dialogue_line_count=%s dialogue_chars=%s planned_text_chars=0 fallback_dialogue_used=%s",
                    current_user.id,
                    len(stable_prompt),
                    has_explicit_dialogue,
                    len(extracted_dialogue_lines),
                    len(extracted_dialogue),
                    False,
                )

            if not str(effective_prompt or "").strip():
                raise HTTPException(
                    status_code=400,
                    detail="No explicit dialogue extracted by LLM planner; voice generation cancelled in strict dialogue mode",
                )

        if explicit_language_code:
            provider_options["language_code"] = explicit_language_code

        if explicit_seed:
            provider_options["seed"] = int(explicit_seed)
            provider_options["seeds"] = int(explicit_seed)
        elif project_seed:
            provider_options["seed"] = int(project_seed)
            provider_options["seeds"] = int(project_seed)

        if explicit_project_language:
            logger.warning(
                "[GenerateVoice] project language hint | user_id=%s project_language=%s language_code=%s",
                current_user.id,
                explicit_project_language,
                provider_options.get("language_code"),
            )

        timestamps_supported = _read_api_capability_bool(
            pre_api_cfg,
            "supports_timestamps",
            "timestamps_supported",
        )
        previous_text_supported = _read_api_capability_bool(
            pre_api_cfg,
            "supports_previous_text",
            "previous_text_supported",
            "supports_context_text",
            "context_text_supported",
        )
        next_text_supported = _read_api_capability_bool(
            pre_api_cfg,
            "supports_next_text",
            "next_text_supported",
            "supports_context_text",
            "context_text_supported",
        )
        if timestamps_supported is False:
            provider_options.pop("timestamps", None)
        if previous_text_supported is False:
            provider_options.pop("previous_text", None)
        if next_text_supported is False:
            provider_options.pop("next_text", None)

        allowed_voice_values = _read_api_capability_list(
            pre_api_cfg,
            "voice_values",
            "voices",
            "allowed_voices",
            "supported_voices",
        )
        allowed_language_values = _read_api_capability_list(
            pre_api_cfg,
            "language_code_values",
            "language_values",
            "languages",
            "allowed_languages",
            "supported_languages",
        )
        mapped_voice = _map_text_value_to_allowed(provider_options.get("voice"), allowed_voice_values)
        if mapped_voice:
            provider_options["voice"] = mapped_voice
        mapped_language = _map_text_value_to_allowed(provider_options.get("language_code"), allowed_language_values)
        if mapped_language:
            provider_options["language_code"] = mapped_language

        voice_numeric_fields = {
            "stability": ("stability_min", "stability_max", 0.0, 1.0),
            "similarity_boost": ("similarity_boost_min", "similarity_boost_max", 0.0, 1.0),
            "style": ("style_min", "style_max", 0.0, 1.0),
            "speed": ("speed_min", "speed_max", 0.7, 1.2),
        }
        for field_name, (min_key, max_key, default_min, default_max) in voice_numeric_fields.items():
            if provider_options.get(field_name) is None:
                continue
            if is_suno_voice and field_name == "style":
                continue
            min_value = _read_api_capability_number(pre_api_cfg, min_key)
            max_value = _read_api_capability_number(pre_api_cfg, max_key)
            effective_min = default_min if min_value is None else float(min_value)
            effective_max = default_max if max_value is None else float(max_value)
            if effective_max < effective_min:
                effective_min, effective_max = effective_max, effective_min
            provider_options[field_name] = _clamp_float(
                provider_options.get(field_name),
                effective_min,
                effective_max,
                effective_min,
            )

        logger.warning(
            "[GenerateVoice] planned params | user_id=%s voice=%s language_code=%s stability=%s similarity_boost=%s style=%s speed=%s timestamps=%s seed=%s",
            current_user.id,
            provider_options.get("voice"),
            provider_options.get("language_code"),
            provider_options.get("stability"),
            provider_options.get("similarity_boost"),
            provider_options.get("style"),
            provider_options.get("speed"),
            provider_options.get("timestamps"),
            provider_options.get("seed") or provider_options.get("seeds"),
        )

        # Final strict gate before provider submission: never send non-dialogue text.
        if not is_suno_voice:
            final_dialogue_prompt = _extract_dialogue_text_for_tts(provider_options.get("text") or effective_prompt)
            if bool(req.use_llm_param_planning) and not str(final_dialogue_prompt or "").strip():
                raise HTTPException(
                    status_code=400,
                    detail="No valid dialogue remained after final sanitization; voice generation cancelled",
                )
            if str(final_dialogue_prompt or "").strip():
                effective_prompt = str(final_dialogue_prompt).strip()
                provider_options["text"] = effective_prompt
                provider_options["prompt"] = effective_prompt
                provider_options["__voice_submit_text"] = effective_prompt
                provider_options["__voice_strict_text_only"] = bool(req.use_llm_param_planning)

        logger.info(
            "[GenerateVoice] final submit text | user_id=%s prompt_len=%s text_len=%s preview=%s",
            current_user.id,
            len(str(effective_prompt or "")),
            len(str(provider_options.get("text") or "")),
            str(effective_prompt or "")[:120],
        )

        effective_negative_prompt, negative_prompt_source = _resolve_effective_negative_prompt(
            req.negative_prompt,
            req.asset_type,
            "voice",
        )

        _release_db_connection(db, "generate_voice_provider_call")

        result = await media_service.generate_voice(
            prompt=effective_prompt,
            negative_prompt=effective_negative_prompt,
            llm_config=runtime_llm_config,
            duration=5,
            provider_options=provider_options,
            user_id=current_user.id,
            user_credits=(current_user.credits or 0),
            skip_download=False,
        )

        if isinstance(result, dict):
            stable_meta = result.get("metadata")
            if not isinstance(stable_meta, dict):
                stable_meta = {}
            active_seed = explicit_seed or project_seed
            if active_seed:
                stable_meta.setdefault("seed", int(active_seed))
            if effective_negative_prompt:
                stable_meta["negative_prompt_submitted"] = effective_negative_prompt
            stable_meta["negative_prompt_source"] = negative_prompt_source
            result["metadata"] = stable_meta

        if "error" in result:
            detail = _format_generation_failure_detail(result, "Voice generation failed")
            if reservation_tx:
                try:
                    billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), detail)
                    reservation_tx = None
                except Exception:
                    pass
            raise HTTPException(status_code=400, detail=detail)

        voice_url = str((result or {}).get("url") or "").strip()
        if not voice_url:
            if reservation_tx:
                try:
                    billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), "Voice generation returned empty URL")
                    reservation_tx = None
                except Exception:
                    pass
            raise HTTPException(status_code=400, detail="Voice generation returned empty URL")

        final_meta = result.get("metadata") if isinstance(result, dict) else {}
        final_meta = final_meta if isinstance(final_meta, dict) else {}
        smart_meta = final_meta.get("smart_routing") if isinstance(final_meta.get("smart_routing"), dict) else {}

        final_provider = str(
            final_meta.get("provider")
            or smart_meta.get("provider")
            or reserve_provider
            or req.provider
            or ""
        ).strip() or None
        final_model = str(
            final_meta.get("model")
            or smart_meta.get("model")
            or reserve_model
            or req.model
            or ""
        ).strip() or None
        final_system_api_id_raw = (
            final_meta.get("system_api_id")
            if final_meta.get("system_api_id") is not None
            else smart_meta.get("system_api_id")
        )
        try:
            final_system_api_id = int(final_system_api_id_raw) if final_system_api_id_raw is not None else None
        except Exception:
            final_system_api_id = None

        if reservation_tx:
            if is_token_billing:
                usage = _extract_provider_usage_from_metadata(final_meta)
                api_tokens = _resolve_usage_token_total(usage)
                settle_details = {
                    "input_tokens": int((usage or {}).get("input_tokens") or (usage or {}).get("prompt_tokens") or 0),
                    "output_tokens": int((usage or {}).get("output_tokens") or (usage or {}).get("completion_tokens") or api_tokens or 0),
                    "total_tokens": api_tokens,
                    "status": "SETTLED",
                    "billing_mode": "ACTUAL",
                    "token_source": "api_usage" if api_tokens > 0 else "estimate",
                }
            else:
                settle_details = {
                    "duration": 5,
                    "duration_seconds": 5,
                    "status": "SETTLED",
                    "billing_mode": "ACTUAL",
                }

            provider_usage = _extract_provider_usage_from_metadata(final_meta)
            if provider_usage:
                settle_details["provider_usage"] = provider_usage
                settle_details["usage_source"] = str(final_meta.get("usage_source") or "provider").strip() or "provider"

            if final_provider:
                settle_details["provider"] = final_provider
            if final_model:
                settle_details["model"] = final_model
            if final_system_api_id is not None:
                settle_details["system_api_id"] = final_system_api_id
            if voice_project_id:
                settle_details["project_id"] = voice_project_id
            if voice_episode_id:
                settle_details["episode_id"] = voice_episode_id

            settle_details = _merge_provider_task_ids_into_settle(
                settle_details,
                final_meta if isinstance(final_meta, dict) else {},
                smart_meta if isinstance(smart_meta, dict) else {},
            )

            billing_service.settle_reservation(
                db,
                _reservation_tx_id(reservation_tx),
                settle_details,
            )
            reservation_tx = None

        if req.shot_id:
            shot = db.query(Shot).filter(Shot.id == int(req.shot_id)).first()
            if shot:
                tech = {}
                try:
                    tech = json.loads(shot.technical_notes or "{}")
                    if not isinstance(tech, dict):
                        tech = {}
                except Exception:
                    tech = {}
                tech["voiceover_url"] = voice_url
                tech["voiceover_prompt"] = effective_prompt
                if bool(req.use_llm_param_planning):
                    tech["voiceover_plan"] = planned_payload
                    tech["voiceover_plan_prompts"] = {
                        "system_prompt": planner_system_prompt,
                        "user_prompt": planner_user_prompt,
                        "template_source": (planner_prompt_meta or {}).get("template_source"),
                    }
                shot.technical_notes = json.dumps(tech, ensure_ascii=False)
                db.add(shot)
                db.commit()

        # Register voice asset so frontend can resolve metadata panels by URL.
        if voice_url:
            if voice_url.startswith("http"):
                async def _bg_upload_and_update_voice(user: User, req_obj: Any, raw_url: str, prompt_text: str, meta: Optional[dict] = None):
                    bg_db = SessionLocal()
                    try:
                        bg_user = bg_db.query(User).filter(User.id == user.id).first()
                        if not bg_user: return
                        norm_url, norm_meta, oss_uploaded = await asyncio.to_thread(
                            _persist_remote_media_result,
                            bg_user,
                            raw_url,
                            meta,
                            filename_base=_build_generation_filename_base(req_obj, bg_db),
                        )
                        final_url = str(norm_url or raw_url).strip()
                        final_meta = dict(norm_meta if norm_meta is not None else (meta or {}))
                        if not str(final_meta.get("idempotency_key") or "").strip() and req_obj.shot_id:
                            final_meta["idempotency_key"] = f"voice-shot-{int(req_obj.shot_id)}"

                        bind_url, ephemeral_binding, final_meta = _resolve_media_bind_url(
                            raw_url=raw_url,
                            normalized_url=final_url,
                            normalized_meta=final_meta,
                        )
                        if bind_url and req_obj.shot_id:
                            bg_shot = bg_db.query(Shot).filter(Shot.id == int(req_obj.shot_id)).first()
                            if bg_shot:
                                bg_tech = {}
                                try:
                                    bg_tech = json.loads(bg_shot.technical_notes or "{}")
                                except Exception:
                                    bg_tech = {}
                                current_voice = str(bg_tech.get("voiceover_url") or "").strip()
                                if current_voice in {raw_url, bind_url}:
                                    bg_tech["voiceover_url"] = bind_url
                                    if ephemeral_binding:
                                        bg_tech["voiceover_ephemeral_binding"] = True
                                    elif oss_uploaded:
                                        bg_tech["voiceover_oss_uploaded"] = True
                                    bg_shot.technical_notes = json.dumps(bg_tech, ensure_ascii=False)
                                    bg_db.add(bg_shot)
                                    bg_db.commit()

                        if bind_url:
                            await asyncio.to_thread(_register_asset_helper, bg_db, bg_user.id, bind_url, req_obj, final_meta)
                    except Exception as e:
                        logger.error(f"[_bg_upload_and_update_voice] failed for user={user.id} url={raw_url}: {e}")
                    finally:
                        bg_db.close()
                asyncio.create_task(_bg_upload_and_update_voice(current_user, req, voice_url, effective_prompt, result.get("metadata")))
            else:
                try:
                    await asyncio.to_thread(
                        _register_asset_helper,
                        db,
                        current_user.id,
                        voice_url,
                        req,
                        (result.get("metadata") if isinstance(result, dict) else None),
                    )
                except Exception as asset_err:
                    logger.warning("[GenerateVoice] asset registration failed: %s", asset_err)

        if isinstance(result, dict):
            result["effective_prompt"] = effective_prompt
            if bool(req.use_llm_param_planning):
                result["voiceover_plan"] = planned_payload if isinstance(planned_payload, dict) else {}
                result["voiceover_plan_prompts"] = {
                    "system_prompt": planner_system_prompt,
                    "user_prompt": planner_user_prompt,
                    "template_source": (planner_prompt_meta or {}).get("template_source"),
                }

        return result
    except HTTPException:
        if reservation_tx:
            try:
                billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), "voice generation http exception")
            except Exception:
                pass
        raise
    except Exception as e:
        if reservation_tx:
            try:
                billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(e))
            except Exception:
                pass
        try:
            billing_service.log_failed_transaction(db, current_user.id, voice_task_type, req.provider, req.model, str(e))
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
