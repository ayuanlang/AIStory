# -*- coding: utf-8 -*-
"""Analyze-scene sync execution path."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.settings import get_scene_analysis_system_config
from app.core.prompt_injection import strip_injection_section, wrap_injection_section
from app.core.prompts.scene_analysis_feature_skills import (
    render_scene_analysis_routed_prompt,
    resolve_scene_analysis_feature_bundle,
)
from app.models.all_models import Entity, Episode, Project, User
from app.schemas.agent import AnalyzeSceneRequest
from app.services.analyze_scene_dedup import (
    _ANALYZE_SCENE_CONTINUATION_SEGMENT_HARD_CAP,
    _ANALYZE_SCENE_OUTPUT_CHAR_HARD_CAP,
    _ANALYZE_SCENE_SEGMENT_HARD_TIMEOUT_SECONDS,
    _ANALYZE_SCENE_SEGMENT_TIMEOUT_SECONDS,
    _await_analyze_scene_segment,
)
from app.services.analyze_scene_integrity import (
    _dedupe_overlap,
    _detect_output_integrity,
    _detect_scene_output_sections,
    _estimate_tokens,
    _is_length_finish_reason,
    _merge_usage,
    _to_int,
)
from app.services.analyze_scene_subject_checks import (
    _detect_prompt_template_syntax_warnings,
    _detect_subject_consistency_warnings,
    _detect_subject_index_coverage_warnings,
    _detect_subjects_json_extraction_gap,
    _format_subject_ref,
    _reconcile_subjects_json_with_subject_index,
)
from app.services.analyze_scene_text_ops import (
    _build_script_to_analyze_block,
    _extract_embedded_subject_index_from_stage_text,
    _filter_subject_index_text_by_types,
    _infer_subject_index_allowed_types_for_request,
    _normalize_subject_index_entity_type,
    _resolve_scene_beats_adapted_script_text,
    _trim_to_scenes_block,
)
from app.services.billing_service import billing_service
from app.services.db_session_utils import _release_db_connection, _snapshot_user_principal
from app.services.endpoint_misc import (
    _build_scene_analysis_blocking_failure_detail,
    _vendor_failed_message,
)
from app.services.llm_markdown_sanitize import sanitize_subject_index_text
from app.services.llm_service import llm_service
from app.services.model_invocation_billing import (
    _apply_llm_routing_to_billing_details,
    _extract_llm_routing_metadata,
    _reservation_tx_id,
)
from app.services.project_access import _require_project_access
from app.services.prompt_resolve import _resolve_prompt_text
from app.services.scene_subject_helpers import (
    _PRIOR_ENTITY_DESIGN_TYPES,
    _build_prior_entity_generation_prompts_block,
    _collect_llm_json_text_candidates,
    _extract_subjects_json_from_text,
    _normalize_prior_entity_design_type,
)
from app.services.script_analysis_flow import (
    assemble_character_asset_design_user_content,
    assemble_environment_asset_design_user_content,
    assemble_prop_asset_design_user_content,
    build_character_asset_design_brief,
    build_cover_poster_brief,
    pick_environment_plan_source_and_brief,
    build_prop_asset_design_brief,
    first_text_with_char_extract,
    first_text_with_prop_extract,
    extract_derived_environment_names_from_scene_text,
    extract_scenes_table_markdown_block,
    persist_analyze_scene_stage_result,
    resolve_analyze_scene_stage,
    sanitize_scene_markdown_llm_output,
    should_require_subject_index,
    validate_analyze_scene_llm_finish_reason,
)
from app.services.subject_index_resolve import _script_optimization_has_project_visual_backfill
from app.services.script_analysis_flow.subject_index_name_align import (
    align_scene_markdown_names_with_subject_index,
    align_subjects_json_names_with_subject_index,
    apply_text_name_replacements,
    format_entity_table_names_for_orchestration,
)
from app.services.script_analysis_llm_config import (
    _inject_llm_call_log_trace,
    _inject_project_creativity_temperature,
    _resolve_script_analysis_dropdown_llm_config,
    _script_analysis_action_label,
)
from app.services.kb_rag_service import build_kb_rag_injection_for_analyze
from app.services.shot_generation_prompts import _build_project_prompt_context
from app.services.soft_delete import _active_entity_clause, _active_episode_clause
from app.services.subject_index_resolve import (
    _coerce_subject_index_candidate,
    _subject_index_has_usable_content,
    _subject_index_rows_present,
    resolve_usable_episode_subject_index,
)
from app.services.user_model_preferences import _inject_user_advanced_llm_preferences
from app.services.video_submit_dedup import ANALYSIS_PROMPT_TEMPLATE_SYNTAX_RULES

logger = logging.getLogger("api_logger")


async def execute_analyze_scene(
    *,
    request: AnalyzeSceneRequest,
    current_user: User,
    db: Session,
) -> Dict[str, Any]:
    """Sync path for /analyze_scene (async_mode handled by the route wrapper)."""
    analysis_trace_id = str(getattr(request, "analysis_trace_id", "") or "").strip()
    current_user_snapshot = _snapshot_user_principal(current_user)
    current_user_id = int(getattr(current_user_snapshot, "id", 0) or 0)
    current_user_is_superuser = bool(getattr(current_user_snapshot, "is_superuser", False))
    logger.info("Received analyze_scene request")
    try:
        logger.info(f"[analyze_scene] request.episode_id={getattr(request, 'episode_id', None)}")
    except Exception:
        pass

    request_episode = None
    if getattr(request, "episode_id", None):
        request_episode = (
            db.query(Episode)
            .filter(Episode.id == request.episode_id, _active_episode_clause())
            .first()
        )
        if not request_episode:
            raise HTTPException(status_code=404, detail="Episode not found or has been deleted")

    if request_episode:
        try:
            _auto_pr = db.query(Project).filter(Project.id == request_episode.project_id).first()
            db_global_info = (
                _auto_pr.global_info
                if _auto_pr and isinstance(getattr(_auto_pr, "global_info", None), dict)
                else None
            )
            if isinstance(db_global_info, dict) and db_global_info:
                incoming_meta = request.project_metadata if isinstance(request.project_metadata, dict) else None
                if not incoming_meta:
                    request.project_metadata = dict(db_global_info)
                    logger.info("[analyze_scene] Automatically populated project_metadata from DB")
                else:
                    # Sparse/legacy payloads (e.g. {title, language: undefined→missing}) must not
                    # block DB project info. Use DB as base; overlay only meaningful request fields.
                    def _meaningful_meta_value(value: Any) -> bool:
                        if value is None:
                            return False
                        if isinstance(value, str):
                            return bool(value.strip())
                        if isinstance(value, (list, dict)):
                            return bool(value)
                        return True

                    merged_meta = dict(db_global_info)
                    for key, value in incoming_meta.items():
                        if _meaningful_meta_value(value):
                            merged_meta[key] = value
                    request.project_metadata = merged_meta
                    logger.info(
                        "[analyze_scene] Merged request project_metadata with DB global_info (keys=%s)",
                        list(merged_meta.keys())[:40],
                    )
        except Exception as e:
            logger.warning(f"[analyze_scene] Failed to auto-fetch/merge project_metadata: {e}")

    if request.project_metadata:
        try:
            keys = list(request.project_metadata.keys())
        except Exception:
            keys = []
        logger.info(f"Project Metadata received (keys only): {keys}")
    else:
        logger.info("No Project Metadata received")

    try:
        # Cache user primitives before releasing DB session for long LLM calls.



















        requested_scene_analysis_mode = str(getattr(request, "scene_analysis_mode", "") or "").strip() or None
        effective_scene_analysis_mode = requested_scene_analysis_mode
        if not effective_scene_analysis_mode:
            try:
                effective_scene_analysis_mode = str(get_scene_analysis_system_config(db).get("default_mode") or "").strip() or None
            except Exception as scene_analysis_cfg_err:
                logger.warning("[analyze_scene] failed to read system scene analysis mode, fallback to request/default: %s", scene_analysis_cfg_err)

        feature_bundle: Dict[str, Any] = {}
        try:
            feature_bundle = resolve_scene_analysis_feature_bundle(
                project_metadata=request.project_metadata,
                explicit_features=getattr(request, "scene_analysis_features", None),
                script_text=getattr(request, "text", None),
                mode=effective_scene_analysis_mode,
            )
        except Exception as feature_bundle_err:
            logger.warning("[analyze_scene] failed to resolve scene analysis feature stack: %s", feature_bundle_err)
            feature_bundle = {}

        # Load the prompt template or use provided system_prompt
        system_instruction = ""
        template_signature: Dict[str, Any] = {}
        
        if request.system_prompt:
            system_instruction = request.system_prompt
            template_signature = {
                "template_source": "inline_system_prompt",
                "template_version": "inline@v1",
                "template_hash_sha256": hashlib.sha256(str(system_instruction or "").encode("utf-8")).hexdigest(),
            }
        else:
            prompt_filename = request.prompt_file or "skills/scene_analysis_feature_stack/scene_planning_1_script_optimization.md"
            if feature_bundle.get("enabled") and not request.prompt_file:
                prompt_filename = str(feature_bundle.get("base_prompt_file") or "skills/scene_analysis_feature_stack/scene_planning_1_script_optimization.md")
            prompt_filename = {
                "skills/scene_analysis_feature_stack/scene_planning_1_subskill_vfx.md": (
                    "skills/scene_analysis_feature_stack/scene_planning_1_subskill_combat.md"
                ),
                "skills/scene_analysis_feature_stack/scene_planning_1_subskill_xian_attack.md": (
                    "skills/scene_analysis_feature_stack/scene_planning_1_subskill_combat.md"
                ),
            }.get(str(prompt_filename or "").replace("\\", "/"), prompt_filename)
            try:
                system_instruction = _resolve_prompt_text(prompt_filename)
            except FileNotFoundError:
                logger.error("Scene analysis prompt not found: %s", prompt_filename)
                raise HTTPException(status_code=404, detail=f"Prompt file '{prompt_filename}' not found.")
            template_signature = {
                "template_source": f"prompt_file:{prompt_filename}",
                "template_version": "prompt_file@v1",
                "template_hash_sha256": hashlib.sha256(str(system_instruction or "").encode("utf-8")).hexdigest(),
            }

        if feature_bundle.get("enabled"):
            system_instruction = render_scene_analysis_routed_prompt(system_instruction, feature_bundle)
            logger.info(
                "Rendered routed scene analysis prompt with explicit slots: requested_mode=%s effective_mode=%s base_prompt=%s slots=%s skills=%s features=%s combos=%s",
                requested_scene_analysis_mode,
                feature_bundle.get("mode"),
                feature_bundle.get("base_prompt_file") or request.prompt_file or "skills/scene_analysis_feature_stack/scene_planning_1_script_optimization.md",
                sorted((feature_bundle.get("slot_blocks") or {}).keys()),
                [item.get("skill_id") for item in (feature_bundle.get("selected_skills") or [])],
                feature_bundle.get("normalized_features") or {},
                [item.get("skill_id") for item in (feature_bundle.get("combo_matches") or [])],
            )

        include_negative_prompt = getattr(request, "include_negative_prompt", True)
        
        is_asset_json_stage = "asset_design" in str(getattr(request, "system_api_id", "")) or "subject" in str(getattr(request, "system_api_id", "")) or "planning_1_stage_1_main" in str(getattr(request, "prompt_file", ""))
        
        if is_asset_json_stage:
            if include_negative_prompt:
                system_instruction += (
                    "\n\n"
                    "# Output Hard Constraint (Negative Prompt)\n"
                    "In Part 2 JSON, every entity item (characters / props / environments / covers) MUST include key \"negative_prompt_en\". "
                    "Each negative_prompt_en must be English-only, style-aware, and aligned to that entity's generation_prompt_en. "
                    "For live-action realism, explicitly exclude plastic/waxy/CGI look and other realism-breaking artifacts."
                )

            system_instruction += (
                "\n\n"
                "# Output Hard Constraint (English Naming)\n"
                "For every entity JSON item, name_en MUST use natural English word spacing. "
                "Use readable Title Case phrases like 'Demon Slayer Captain' or 'Harbor Office Front Mid Night', "
                "and avoid 'DemonSlayerCaptain', 'Demon_Slayer_Captain', 'demon-slayer-captain', or 'HarborOffice_Front_Mid_Night'."
            )

        # Inject authoritative character canon (if provided via episode_id)
        try:
            ep_id = getattr(request, "episode_id", None)
            if ep_id:
                episode = (
                    db.query(Episode)
                    .filter(Episode.id == ep_id, _active_episode_clause())
                    .first()
                )
                if episode:
                    # Prefer project-level canon (Overview) and merge episode-specific overrides.
                    project_profiles = []
                    try:
                        project = db.query(Project).filter(Project.id == episode.project_id).first()
                        if project and isinstance(project.global_info, dict):
                            project_profiles = project.global_info.get("character_profiles") or []
                    except Exception:
                        project_profiles = []

                    episode_profiles = episode.character_profiles or []

                    merged_profiles: List[Dict[str, Any]] = []
                    by_name: Dict[str, int] = {}

                    def _add_profile(p: Any) -> None:
                        if not isinstance(p, dict):
                            return
                        nm = (p.get("name") or "").strip()
                        if not nm:
                            return
                        if nm in by_name:
                            merged_profiles[by_name[nm]] = p
                        else:
                            by_name[nm] = len(merged_profiles)
                            merged_profiles.append(p)

                    for p in (project_profiles or []):
                        _add_profile(p)
                    for p in (episode_profiles or []):
                        _add_profile(p)

                    canon_blocks = []
                    for p in merged_profiles:
                        if not isinstance(p, dict):
                            continue
                        nm = (p.get("name") or "").strip()
                        if not nm:
                            continue
                        md = (p.get("description_md") or "").strip()
                        if md:
                            canon_blocks.append(md)
                        else:
                            canon_blocks.append(f"### {nm} (Canonical)\n- Identity: {p.get('identity') or ''}\n- Body Features: {p.get('body_features') or ''}\n- Style Tags: {', '.join(p.get('style_tags') or [])}\n")

                    canon_text = "\n\n".join(canon_blocks).strip()
                    if canon_text:
                        # Keep the injection bounded to avoid blowing prompt size.
                        canon_text = canon_text[:8000]
                        system_instruction += (
                            "\n\n"
                            "# Character Canon (Authoritative)\n"
                            "The following character profiles are AUTHORITATIVE for this script. "
                            "You MUST use them as the single source of truth for character identity and appearance, "
                            "and IGNORE conflicting character descriptions found elsewhere in the script.\n\n"
                            + canon_text
                        )
        except Exception as e:
            logger.warning(f"[analyze_scene] failed to inject character canon: {e}")
        
        # Prepare user content with optional project metadata
        prompt_file_lower = str(getattr(request, "prompt_file", "") or "").strip().lower()
        mode_lower = str(effective_scene_analysis_mode or "").strip().lower()
        function_name_lower = str(getattr(request, "function_name", "") or "").strip().lower()
        stage_ctx = resolve_analyze_scene_stage(
            effective_scene_analysis_mode=effective_scene_analysis_mode,
            prompt_file=getattr(request, "prompt_file", ""),
            function_name=getattr(request, "function_name", ""),
        )
        is_scene_beats_stage = stage_ctx.is_scene_beats_stage
        is_subject_index_extraction_stage = stage_ctx.is_subject_index_extraction_stage
        is_script_optimization_stage = stage_ctx.is_script_optimization_stage
        is_entity_design_phase = stage_ctx.is_entity_design_phase
        is_scene_split_stage = bool(
            "cut_transition" in prompt_file_lower
            or "scene_split" in function_name_lower
            or mode_lower in {"scene_split"}
        )
        is_environment_plan_stage = bool(
            "subskill_environment" in prompt_file_lower
            or "environment_plan" in function_name_lower
            or mode_lower in {"environment_plan"}
        )
        is_derived_framing_stage = bool(
            "subskill_derived_framing" in prompt_file_lower
            or "derived_framing" in function_name_lower
            or mode_lower in {"derived_framing"}
        )
        is_subject_index_consumer_stage = bool(
            "scene_planning_2_2" in prompt_file_lower
            or "entity_design" in prompt_file_lower
            or "subject_generation" in prompt_file_lower
            or mode_lower.startswith("2_pass_generate_assets")
            or mode_lower in {"entity_design", "beats_generation", "scene_planning_beats", "scene_beats_only"}
        )


        # Keep full outputs for stage1/stage2.1/stage2.2.
        # Stage 2.2 contract is Scenes Table markdown (header+sep+rows; title optional),
        # not SCENES_BLOCK markers, so do not trim to marker block for beats stage.
        should_trim_before_submit = False




        subject_index_allowed_types_for_request = _infer_subject_index_allowed_types_for_request(
            request=request,
            mode_lower=mode_lower,
            prompt_file_lower=prompt_file_lower,
        )
        is_environment_asset_design = bool(
            "entity_design_environment" in prompt_file_lower
            or "2_pass_generate_assets_environments" in mode_lower
            or (
                subject_index_allowed_types_for_request
                and "environment" in subject_index_allowed_types_for_request
            )
        )
        is_prop_asset_design = bool(
            "entity_design_prop" in prompt_file_lower
            or "2_pass_generate_assets_props" in mode_lower
            or (
                subject_index_allowed_types_for_request
                and "prop" in subject_index_allowed_types_for_request
            )
        )
        is_character_asset_design = bool(
            "entity_design_character" in prompt_file_lower
            or "2_pass_generate_assets_characters" in mode_lower
            or (
                subject_index_allowed_types_for_request
                and "character" in subject_index_allowed_types_for_request
            )
        )
        is_scoped_asset_design = bool(
            is_environment_asset_design or is_prop_asset_design or is_character_asset_design
        )


        persisted_subject_index_for_prompt = ""
        persisted_subject_index_raw_for_gate = ""
        episode_adaptation_for_scene_beats = ""
        orchestration_project_id = None
        if is_subject_index_consumer_stage and getattr(request, "episode_id", None):
            try:
                _ep_for_subject_index = (
                    db.query(Episode)
                    .filter(Episode.id == request.episode_id, _active_episode_clause())
                    .first()
                )
                if _ep_for_subject_index:
                    episode_adaptation_for_scene_beats = str(
                        getattr(_ep_for_subject_index, "ai_scene_analysis_adaptation", "") or ""
                    ).strip()
                    persisted_subject_index_raw_for_gate = resolve_usable_episode_subject_index(
                        _ep_for_subject_index,
                        request_text=getattr(request, "text", None),
                        explicit_subject_index=getattr(request, "subject_index_text", None),
                        heal_episode_field=True,
                        db=db,
                    )
                    persisted_subject_index_for_prompt = persisted_subject_index_raw_for_gate
                    if persisted_subject_index_for_prompt and subject_index_allowed_types_for_request:
                        persisted_subject_index_for_prompt = _filter_subject_index_text_by_types(
                            persisted_subject_index_for_prompt,
                            subject_index_allowed_types_for_request,
                            log_mode=effective_scene_analysis_mode,
                            log_prompt_file=getattr(request, "prompt_file", None),
                        )
            except Exception as _subject_idx_inject_err:
                logger.warning("[analyze_scene] failed loading persisted subject index for prompt injection: %s", _subject_idx_inject_err)








        # Asset design reads CHAR/PROP extracts or the environment plan — not Subject Index.
        # Scene orchestration (2.2) injects names from the asset table instead.
        if is_subject_index_consumer_stage and should_require_subject_index(stage_ctx):
            request_embedded_subject_index = _extract_embedded_subject_index_from_stage_text(request.text)
            gate_subject_index = (
                persisted_subject_index_raw_for_gate
                if _subject_index_has_usable_content(persisted_subject_index_raw_for_gate)
                else request_embedded_subject_index
            )
            if not _subject_index_has_usable_content(gate_subject_index):
                detail = _build_scene_analysis_blocking_failure_detail(
                    ["ANALYSIS_SUBJECT_INDEX_REQUIRED"],
                    [],
                    [
                        "缺少资产清单（Subject Index），无法继续场景编排或资产生成。请先完成第二阶段资产提取后再重试。"
                    ],
                )
                logger.error(
                    "[analyze_scene] subject_index_required_blocking episode_id=%s mode=%s prompt_file=%s is_scene_beats_stage=%s",
                    getattr(request, "episode_id", None),
                    effective_scene_analysis_mode,
                    getattr(request, "prompt_file", None),
                    is_scene_beats_stage,
                )
                raise HTTPException(status_code=400, detail=detail)
            # Prefer persisted index for injection; fall back to request-embedded when episode field is empty.
            if not persisted_subject_index_for_prompt and request_embedded_subject_index:
                persisted_subject_index_for_prompt = request_embedded_subject_index
                if subject_index_allowed_types_for_request:
                    persisted_subject_index_for_prompt = _filter_subject_index_text_by_types(
                        persisted_subject_index_for_prompt,
                        subject_index_allowed_types_for_request,
                        log_mode=effective_scene_analysis_mode,
                        log_prompt_file=getattr(request, "prompt_file", None),
                    )

        if is_scoped_asset_design:
            # Seed is assembled below from the category brief + project info only.
            user_content = ""
        elif is_scene_beats_stage:
            orchestration_project_id = getattr(request, "project_id", None)
            if not orchestration_project_id and getattr(request, "episode_id", None):
                try:
                    _ep_for_assets = (
                        db.query(Episode)
                        .filter(Episode.id == request.episode_id, _active_episode_clause())
                        .first()
                    )
                    orchestration_project_id = getattr(_ep_for_assets, "project_id", None)
                except Exception:
                    orchestration_project_id = None
            index_for_prompt = format_entity_table_names_for_orchestration(
                db,
                project_id=orchestration_project_id,
                episode_id=getattr(request, "episode_id", None),
                extra_derived_environment_names=extract_derived_environment_names_from_scene_text(
                    request.text
                ),
                subject_index_text=persisted_subject_index_for_prompt
                or persisted_subject_index_raw_for_gate,
            )
            saved_asset_table_block = ""
            if index_for_prompt:
                saved_asset_table_block = (
                    "[Saved Asset Table Injection - Authoritative]\n"
                    "CHAR/PROP name whitelist from the project asset table (中文名 / 英文名), plus 【服化道连续性】 when present.\n"
                    "Do not expect other asset descriptions. Do not use the full Subject Index table.\n"
                    "Inject all CHAR and PROP names. ENV is derived-only ({N}度…) — never a bare main-environment name.\n"
                    "CHAR/PROP wrap names MUST be character-identical to the CHAR:/PROP: names below.\n"
                    "【服化道连续性】 tells which scene / beat a CHAR or PROP form change starts; use it to wrap the matching variant name.\n"
                    "ENV:[] and Environment Name MUST use the ENV list or 【本场衍生环境名】 — never a bare main-environment name.\n"
                    "Do NOT wrap names inside dialogue/台词 or physical text on letters, screens, books, signs.\n"
                    "If a Beat entity is not in these lists, keep Stage-1 natural language and do NOT wrap it.\n\n"
                    f"{wrap_injection_section('资产表', index_for_prompt)}"
                )
            canonical_stage_text = _resolve_scene_beats_adapted_script_text(request.text, episode_adaptation_for_scene_beats)
            if should_trim_before_submit:
                canonical_stage_text = _trim_to_scenes_block(canonical_stage_text)
            script_block = _build_script_to_analyze_block(canonical_stage_text)
            user_content = (
                f"{saved_asset_table_block}\n\n{script_block}".strip()
                if saved_asset_table_block
                else script_block
            )
            logger.info(
                "[analyze_scene] injected asset-table names into user prompt episode_id=%s project_id=%s name_chars=%s mode=%s prompt_file=%s",
                getattr(request, "episode_id", None),
                orchestration_project_id,
                len(index_for_prompt),
                effective_scene_analysis_mode,
                getattr(request, "prompt_file", None),
            )
        elif persisted_subject_index_for_prompt:
            index_for_prompt = persisted_subject_index_for_prompt
            saved_subject_index_block = (
                "[Saved Subject Index Injection - Authoritative]\n"
                "The following Subject Index is loaded from persisted sanitized episode data.\n"
                "For this stage, treat this block as the ONLY authoritative Subject Index source.\n"
                "Ignore any Subject Index-like prose or reasoning fragments that may appear elsewhere in the input.\n"
                "NAME LOCK (hard fail): every CHAR:/ENV:/PROP: bracket name and every output "
                "name/name_en/visual_dependencies entity name MUST be character-identical to a "
                "subject_name_zh (or subject_name_en when that column is required) cell in THIS "
                "Subject Index. Copy-paste the cell text; do not retype from memory; do not use "
                "Stage-1 aliases/nicknames/job titles inside brackets; do not invent names absent "
                "from this Index. If a Beat entity has no Index row, keep Stage-1 natural language "
                "and do NOT wrap it with any TYPE:[...] prefix.\n\n"
                f"{wrap_injection_section('Subject Index', persisted_subject_index_for_prompt)}"
            )
            # In downstream Subject-Index consumer stages, use persisted sanitized
            # Subject Index as canonical source to avoid request text contamination.
            if is_subject_index_consumer_stage:
                canonical_stage_text = str(request.text or "")
                if should_trim_before_submit:
                    canonical_stage_text = _trim_to_scenes_block(canonical_stage_text)
                user_content = canonical_stage_text
            else:
                canonical_stage_text = str(request.text or "")
                if should_trim_before_submit:
                    canonical_stage_text = _trim_to_scenes_block(canonical_stage_text)
                user_content = f"{saved_subject_index_block}\n\n{_build_script_to_analyze_block(canonical_stage_text)}"
            logger.info(
                "[analyze_scene] injected subject index into user prompt episode_id=%s saved_chars=%s prompt_chars=%s mode=%s prompt_file=%s is_scene_beats_stage=%s",
                getattr(request, "episode_id", None),
                len(persisted_subject_index_for_prompt),
                len(index_for_prompt),
                effective_scene_analysis_mode,
                getattr(request, "prompt_file", None),
                is_scene_beats_stage,
            )
        else:
            request_text_for_prompt = str(request.text or "")
            if is_scene_beats_stage:
                request_text_for_prompt = _resolve_scene_beats_adapted_script_text(request_text_for_prompt, episode_adaptation_for_scene_beats)
            if should_trim_before_submit:
                request_text_for_prompt = _trim_to_scenes_block(request_text_for_prompt)
            if is_subject_index_consumer_stage and subject_index_allowed_types_for_request:
                request_text_for_prompt = _filter_subject_index_text_by_types(
                    request_text_for_prompt,
                    subject_index_allowed_types_for_request,
                    log_mode=effective_scene_analysis_mode,
                    log_prompt_file=getattr(request, "prompt_file", None),
                )
            user_content = _build_script_to_analyze_block(request_text_for_prompt)

        if is_environment_asset_design:
            request_text = str(getattr(request, "text", "") or "").strip()
            episode_plan_texts = []
            if getattr(request, "episode_id", None):
                try:
                    _ep_for_brief = (
                        db.query(Episode)
                        .filter(Episode.id == request.episode_id, _active_episode_clause())
                        .first()
                    )
                    if _ep_for_brief:
                        episode_plan_texts.append(
                            str(getattr(_ep_for_brief, "ai_scene_analysis_adaptation", "") or "")
                        )
                        raw_outputs = str(getattr(_ep_for_brief, "ai_stage_outputs", "") or "").strip()
                        if raw_outputs:
                            try:
                                payload = json.loads(raw_outputs)
                                outputs = ((payload.get("stages") or {}).get("stage1") or {}).get("outputs") or {}
                                for key in ("environment_plan", "adapted_script", "raw_text"):
                                    slot = outputs.get(key)
                                    if isinstance(slot, dict):
                                        episode_plan_texts.append(str(slot.get("content") or ""))
                                    elif isinstance(slot, str):
                                        episode_plan_texts.append(slot)
                            except Exception:
                                pass
                        episode_plan_texts.append(
                            str(getattr(_ep_for_brief, "ai_scene_analysis_result", "") or "")
                        )
                except Exception as brief_load_err:
                    logger.warning(
                        "[analyze_scene] failed loading adaptation for env design brief: %s",
                        brief_load_err,
                    )
            brief_source, env_brief = pick_environment_plan_source_and_brief(
                request_text,
                episode_adaptation_for_scene_beats,
                *episode_plan_texts,
            )
            cover_brief = build_cover_poster_brief(brief_source)
            user_content = assemble_environment_asset_design_user_content(
                cover_brief,
                env_brief,
            )
            logger.info(
                "[analyze_scene] environment asset design user seed episode_id=%s env_brief=%s cover_brief=%s script_block=omitted",
                getattr(request, "episode_id", None),
                len(env_brief or ""),
                len(cover_brief or ""),
            )

        if is_prop_asset_design:
            brief_source = episode_adaptation_for_scene_beats
            extra_prop_sources = [str(getattr(request, "text", "") or "")]
            if getattr(request, "episode_id", None):
                try:
                    _ep_for_prop = (
                        db.query(Episode)
                        .filter(Episode.id == request.episode_id, _active_episode_clause())
                        .first()
                    )
                    if _ep_for_prop:
                        extra_prop_sources.append(
                            str(getattr(_ep_for_prop, "ai_scene_analysis_adaptation", "") or "")
                        )
                        extra_prop_sources.append(
                            str(getattr(_ep_for_prop, "ai_scene_analysis_result", "") or "")
                        )
                        raw_outputs = str(getattr(_ep_for_prop, "ai_stage_outputs", "") or "").strip()
                        if raw_outputs:
                            try:
                                payload = json.loads(raw_outputs)
                                stage1 = ((payload.get("stages") or {}).get("stage1") or {})
                                outputs = stage1.get("outputs") or {}
                                for key in ("scene_split", "environment_plan", "raw_text", "adapted_script"):
                                    slot = outputs.get(key)
                                    if isinstance(slot, dict):
                                        extra_prop_sources.append(str(slot.get("content") or ""))
                                    elif isinstance(slot, str):
                                        extra_prop_sources.append(slot)
                            except Exception:
                                pass
                except Exception as prop_brief_err:
                    logger.warning(
                        "[analyze_scene] failed loading adaptation for prop design brief: %s",
                        prop_brief_err,
                    )
            brief_source = first_text_with_prop_extract(
                str(getattr(request, "text", "") or ""),
                brief_source,
                *extra_prop_sources,
            ) or brief_source
            prop_brief = build_prop_asset_design_brief(brief_source)
            user_content = assemble_prop_asset_design_user_content(prop_brief)
            logger.info(
                "[analyze_scene] prop asset design user seed episode_id=%s prop_brief=%s script_block=omitted char_brief=omitted",
                getattr(request, "episode_id", None),
                len(prop_brief or ""),
            )

        if is_character_asset_design:
            brief_source = episode_adaptation_for_scene_beats
            extra_char_sources = [str(getattr(request, "text", "") or "")]
            if getattr(request, "episode_id", None):
                try:
                    _ep_for_char = (
                        db.query(Episode)
                        .filter(Episode.id == request.episode_id, _active_episode_clause())
                        .first()
                    )
                    if _ep_for_char:
                        extra_char_sources.append(
                            str(getattr(_ep_for_char, "ai_scene_analysis_adaptation", "") or "")
                        )
                        extra_char_sources.append(
                            str(getattr(_ep_for_char, "ai_scene_analysis_result", "") or "")
                        )
                        raw_outputs = str(getattr(_ep_for_char, "ai_stage_outputs", "") or "").strip()
                        if raw_outputs:
                            try:
                                payload = json.loads(raw_outputs)
                                stage1 = ((payload.get("stages") or {}).get("stage1") or {})
                                outputs = stage1.get("outputs") or {}
                                for key in ("scene_split", "raw_text", "adapted_script"):
                                    slot = outputs.get(key)
                                    if isinstance(slot, dict):
                                        extra_char_sources.append(str(slot.get("content") or ""))
                                    elif isinstance(slot, str):
                                        extra_char_sources.append(slot)
                            except Exception:
                                pass
                except Exception as char_brief_err:
                    logger.warning(
                        "[analyze_scene] failed loading adaptation for character design brief: %s",
                        char_brief_err,
                    )
            brief_source = first_text_with_char_extract(
                str(getattr(request, "text", "") or ""),
                brief_source,
                *extra_char_sources,
            ) or brief_source
            char_brief = build_character_asset_design_brief(brief_source)
            user_content = assemble_character_asset_design_user_content(char_brief)
            logger.info(
                "[analyze_scene] character asset design user seed episode_id=%s char_brief=%s script_block=omitted prop_brief=omitted",
                getattr(request, "episode_id", None),
                len(char_brief or ""),
            )

        
        if request.project_metadata:
            # Frontend Stage 1/2.1 may already bake [项目信息…] into request text
            # (skipMetadata=true). Do not prepend a second copy from DB auto-fill.
            user_content_has_project_info = (
                "[项目信息开始]" in str(user_content or "")
                or "Project Context (prepend and treat as high-priority constraints):" in str(user_content or "")
                or "# Project Context" in str(user_content or "")
            )
            if user_content_has_project_info:
                logger.info(
                    "[analyze_scene] skipped Project Context injection: already present in user content chars=%s",
                    len(str(user_content or "")),
                )
            else:
                project_context = _build_project_prompt_context(request.project_metadata)
                meta_str = str(project_context.get("project_context_section") or "").strip()

                metadata = project_context.get("metadata") if isinstance(project_context.get("metadata"), dict) else {}
                project_language = str(metadata.get("project_language") or "").strip()
                extra_rules: List[str] = []
                if project_language:
                    if any(tag in project_language.lower() for tag in ["zh", "cn", "中文", "chinese"]):
                        extra_rules.extend([
                            "Subject Naming Rule: For this project, subject 'name' must be Chinese by default. Use English in 'name' only for explicit proper nouns that are canonically English.",
                            "Subject Naming Rule (EN): Use spaces between English words in name_en and keep it as a readable Title Case phrase (e.g., 'Demon Slayer Captain', 'Harbor Office Front Mid Night'). Do NOT use snake_case, kebab-case, camelCase, or concatenated forms like 'DemonSlayerCaptain' or 'HarborOffice_Front_Mid_Night'.",
                            "Subject Prompt Rule: Every subject JSON item must include BOTH generation_prompt_cn and generation_prompt_en, and the two prompts must be semantically aligned.",
                        ])
                else:
                    extra_rules.append(
                        "Language Warning: project language is empty. You MUST infer one target natural language from script context and keep all natural-language descriptions consistently in that single language."
                    )

                if extra_rules:
                    if meta_str:
                        meta_str = f"{meta_str}\n" + "\n".join(extra_rules)
                    else:
                        meta_str = "\n".join(extra_rules)

                if meta_str:
                    user_content = f"{meta_str}\n\n{user_content}"
                    logger.info(
                        "Injected Project Context into Prompt (summary): lines=%s chars=%s tokens_est=%s",
                        len(meta_str.splitlines()),
                        len(meta_str),
                        _estimate_tokens(meta_str),
                    )

        catalog_project_id = int(getattr(request, "project_id", 0) or 0)
        if catalog_project_id <= 0 and request_episode is not None:
            catalog_project_id = int(getattr(request_episode, "project_id", 0) or 0)
        if (is_scene_split_stage or is_environment_plan_stage) and catalog_project_id > 0:
            try:
                from app.services.script_analysis_flow.environment_reuse import (
                    PROJECT_MAIN_ENV_LABEL,
                    build_project_main_environment_injection,
                    collect_project_main_environment_catalog,
                )

                already_has_catalog = f"[{PROJECT_MAIN_ENV_LABEL}开始]" in str(user_content or "")
                if already_has_catalog:
                    logger.info("[analyze_scene] skipped project main env catalog: already present")
                else:
                    catalog = collect_project_main_environment_catalog(
                        db,
                        project_id=int(catalog_project_id),
                        current_episode_id=int(getattr(request, "episode_id", 0) or 0),
                    )
                    catalog_block = build_project_main_environment_injection(
                        catalog,
                        for_planning=is_environment_plan_stage,
                    )
                    if catalog_block:
                        user_content = f"{catalog_block}\n\n{user_content}"
                        logger.info(
                            "[analyze_scene] injected project main env catalog count=%s stage=%s",
                            len(catalog),
                            "scene_split" if is_scene_split_stage else "environment_plan",
                        )
            except Exception as env_catalog_exc:
                logger.warning("[analyze_scene] failed to inject project main env catalog: %s", env_catalog_exc)

        # Optional platform knowledge-base RAG (reference-only; never mutates Subject Index names).
        if (is_script_optimization_stage or is_entity_design_phase) and not is_scoped_asset_design:
            try:
                kb_query_source = str(getattr(request, "text", "") or "")
                kb_inject = build_kb_rag_injection_for_analyze(
                    db,
                    project_metadata=request.project_metadata if isinstance(request.project_metadata, dict) else {},
                    request_text=kb_query_source,
                    is_script_optimization_stage=is_script_optimization_stage,
                    is_entity_design_phase=is_entity_design_phase,
                    prompt_file=getattr(request, "prompt_file", ""),
                )
                kb_block = str((kb_inject or {}).get("block") or "").strip()
                if kb_block:
                    user_content = f"{kb_block}\n\n{user_content}"
                    logger.info(
                        "[analyze_scene] injected KB RAG references hit_count=%s categories=%s chars=%s",
                        (kb_inject or {}).get("hit_count"),
                        (kb_inject or {}).get("categories"),
                        len(kb_block),
                    )
            except Exception as kb_exc:
                logger.warning("[analyze_scene] KB RAG injection skipped: %s", kb_exc)

        if (is_script_optimization_stage or is_derived_framing_stage) and getattr(request, "project_id", None):
            try:
                from app.api.routers.entities_pkg.analyze import _entity_analysis_is_main_environment
                
                global_envs = db.query(Entity).filter(
                    Entity.project_id == request.project_id,
                    Entity.type == "environment",
                    _active_entity_clause(),
                ).all()
                
                # 按格式提取 [ENV_BLOCK_START] 后第一个逗号前的环境名
                extracted_env_names = set()
                env_block_pattern = re.compile(r"\[ENV_BLOCK_START\]\s*([^,，\n]+)[,，]")
                
                for match in env_block_pattern.finditer(user_content):
                    extracted_env_names.add(match.group(1).strip())
                for match in env_block_pattern.finditer(request_text_for_prompt):
                    extracted_env_names.add(match.group(1).strip())

                env_prompts = []
                for env in global_envs:
                    if _entity_analysis_is_main_environment(env):
                        env_name = str(getattr(env, "name", "") or "").strip()
                        prompt_cn = str(getattr(env, "generation_prompt_cn", "") or getattr(env, "description", "")).strip()
                        if env_name and prompt_cn and (env_name in extracted_env_names):
                            env_prompts.append(f"环境名称：{env_name}\n既有提示词：{prompt_cn}")
                
                if env_prompts:
                    env_injection = "\n\n".join(env_prompts)
                    user_content += (
                        "\n\n[已存在的全局主环境约束]\n"
                        "当前项目已存在以下主环境（含上集/跨集须复用者）。你在剧本优化设计相关场景与环境时，"
                        "请务必严格按以下既有提示词延续和参考，不可与既有提示词产生冲突：\n"
                        f"{env_injection}\n\n"
                        "【复用主环境·衍生角度锁（最高）】\n"
                        "1. 主环境 0°轴、四向扇区实体归属、头尾双锚、固定清单须与既有提示词同核；禁止重定 0° 或对调四向。\n"
                        "2. 为本场生成的每一衍生环境（含 `0度…`/`{N}度…`）必须与该既有主环境保持完全一致的角度——"
                        "`view_angle_from_main=N` 与该角后景半空间须与原来角度一致；禁止重映射度数或旋转坐标系。\n"
                        "3. Beat 选择可拍衍生环境时，必须根据该环境的设置（四向扇区内容 / 活动适配 / 后景应见何物）匹配对应角度行；"
                        "绝不能随机选角，也绝不能按 0→90→180→270 顺序轮角。\n"
                    )
                    logger.info("[analyze_scene] injected %d global environment prompts for script optimization", len(env_prompts))
            except Exception as e:
                logger.warning("[analyze_scene] failed to inject global environments for script optimization: %s", e)

        attention_notes_raw = (getattr(request, "analysis_attention_notes", None) or "").strip()
        attention_notes = attention_notes_raw
        if attention_notes and (not is_scene_beats_stage):
            # Guardrail: do not inject directives that force Subject-Index-only output,
            # which can suppress scene table generation in scene analysis runs.
            banned_line_patterns = [
                re.compile(r"(?i)only\s+output\s+(?:the\s+)?subjects?\s*index"),
                re.compile(r"(?i)only\s+return\s+(?:the\s+)?subjects?\s*index"),
                re.compile(r"(?i)只\s*输出\s*subjects?\s*index"),
                re.compile(r"(?i)仅\s*输出\s*subjects?\s*index"),
                re.compile(r"(?i)只\s*输出\s*subject\s*index"),
                re.compile(r"(?i)仅\s*输出\s*subject\s*index"),
                re.compile(r"(?i)只\s*返回\s*subjects?\s*index"),
                re.compile(r"(?i)仅\s*返回\s*subjects?\s*index"),
            ]

            cleaned_lines = []
            removed_line_count = 0
            for raw_line in str(attention_notes).splitlines():
                line = str(raw_line or "")
                if any(p.search(line) for p in banned_line_patterns):
                    removed_line_count += 1
                    continue
                cleaned_lines.append(line)

            attention_notes = "\n".join(cleaned_lines).strip()
            if removed_line_count > 0:
                logger.info(
                    "Sanitized analysis attention notes: removed_subject_index_only_lines=%s raw_chars=%s cleaned_chars=%s",
                    removed_line_count,
                    len(attention_notes_raw),
                    len(attention_notes),
                )

        if attention_notes and (not is_scene_beats_stage):
            attention_block = wrap_injection_section(
                "重生成注意力备注",
                (
                    "Regeneration Attention Notes (High Priority):\n"
                    "When regenerating AI Scene Analysis, you MUST prioritize and satisfy these constraints:\n"
                    f"{attention_notes}"
                ),
            )
            user_content = f"{attention_block}\n\n{user_content}"
            logger.info(
                "Injected analysis attention notes into prompt: chars=%s tokens_est=%s",
                len(attention_notes),
                _estimate_tokens(attention_notes),
            )

        reuse_subject_assets = getattr(request, "reuse_subject_assets", None) or []
        # Global Assets UI is project-wide: keep selected IDs owned by this project
        # (any episode, including episode_id NULL). Reject cross-project IDs only.
        if isinstance(reuse_subject_assets, list) and reuse_subject_assets:
            request_episode_id_for_reuse = None
            try:
                raw_ep = getattr(request, "episode_id", None)
                if raw_ep is not None and str(raw_ep).strip() != "":
                    request_episode_id_for_reuse = int(raw_ep)
            except Exception:
                request_episode_id_for_reuse = None
            request_project_id_for_reuse = None
            try:
                raw_pid = getattr(request, "project_id", None)
                if raw_pid is not None and str(raw_pid).strip() != "":
                    request_project_id_for_reuse = int(raw_pid)
            except Exception:
                request_project_id_for_reuse = None
            if (not request_project_id_for_reuse or request_project_id_for_reuse <= 0) and request_episode is not None:
                try:
                    request_project_id_for_reuse = int(getattr(request_episode, "project_id", 0) or 0) or None
                except Exception:
                    request_project_id_for_reuse = None
            if request_project_id_for_reuse and request_project_id_for_reuse > 0:
                reuse_ids: List[int] = []
                for item in reuse_subject_assets:
                    if not isinstance(item, dict):
                        continue
                    try:
                        eid = int(item.get("id"))
                    except Exception:
                        continue
                    if eid > 0:
                        reuse_ids.append(eid)
                owned_ids: set = set()
                if reuse_ids:
                    ownership_filters = [
                        Entity.id.in_(list(set(reuse_ids))),
                        Entity.project_id == int(request_project_id_for_reuse),
                        _active_entity_clause(),
                    ]
                    owned_ids = {
                        int(getattr(row, "id", 0) or 0)
                        for row in db.query(Entity.id).filter(*ownership_filters).all()
                        if getattr(row, "id", None) is not None
                    }
                before_reuse_count = len(reuse_subject_assets)
                filtered_reuse_assets = []
                for item in reuse_subject_assets:
                    if not isinstance(item, dict):
                        continue
                    try:
                        item_id = int(item.get("id"))
                    except Exception:
                        continue
                    if item_id > 0 and item_id in owned_ids:
                        filtered_reuse_assets.append(item)
                reuse_subject_assets = filtered_reuse_assets
                if before_reuse_count != len(reuse_subject_assets):
                    logger.info(
                        "[analyze_scene] filtered reuse_subject_assets to current project project_id=%s episode_id=%s before=%s after=%s",
                        request_project_id_for_reuse,
                        request_episode_id_for_reuse,
                        before_reuse_count,
                        len(reuse_subject_assets),
                    )
            else:
                if reuse_subject_assets:
                    logger.info(
                        "[analyze_scene] cleared reuse_subject_assets: project_id required for project-scoped injection"
                    )
                reuse_subject_assets = []
        if is_subject_index_consumer_stage and persisted_subject_index_for_prompt:
            if isinstance(reuse_subject_assets, list) and reuse_subject_assets:
                logger.info(
                    "[analyze_scene] skipped reusable subject assets injection because persisted subject index is already injected episode_id=%s request_asset_count=%s",
                    getattr(request, "episode_id", None),
                    len(reuse_subject_assets),
                )
            reuse_subject_assets = []
        elif subject_index_allowed_types_for_request and isinstance(reuse_subject_assets, list):
            original_reuse_count = len(reuse_subject_assets)
            reuse_subject_assets = [
                item for item in reuse_subject_assets
                if isinstance(item, dict)
                and _normalize_subject_index_entity_type(item.get("type")) in subject_index_allowed_types_for_request
            ]
            if original_reuse_count != len(reuse_subject_assets):
                logger.info(
                    "[analyze_scene] filtered request reuse_subject_assets for target types types=%s before=%s after=%s mode=%s",
                    sorted(subject_index_allowed_types_for_request),
                    original_reuse_count,
                    len(reuse_subject_assets),
                    effective_scene_analysis_mode,
                )
        if (not is_scene_beats_stage) and isinstance(reuse_subject_assets, list) and len(reuse_subject_assets) > 0:
            # Stage 2.1 frontend may already embed [可复用Subject资产…] in user text.
            if "[可复用Subject资产开始]" in str(user_content or ""):
                logger.info(
                    "[analyze_scene] skipped reusable subject assets injection: already present in user content request_asset_count=%s",
                    len(reuse_subject_assets),
                )
            else:
                normalized_assets = []
                for item in reuse_subject_assets:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name") or "").strip()
                    if not name:
                        continue
                    asset_type = str(item.get("type") or "").strip()
                    normalized_type = _normalize_subject_index_entity_type(asset_type)
                    description = str(item.get("description") or "").strip()
                    anchor_description = str(item.get("anchor_description") or "").strip()
                    normalized_assets.append({
                        "name": name,
                        "type": asset_type,
                        "normalized_type": normalized_type,
                        "subject_ref": _format_subject_ref(name, normalized_type),
                        "description": description,
                        "anchor_description": anchor_description,
                    })

                if normalized_assets:
                    lines = [
                        "Reusable Subject Assets (High Priority):",
                        "The following assets are MUST-REUSE subjects for this analysis.",
                        "Do NOT regenerate or rename them. Keep their identity and anchor traits consistent.",
                        "When referencing these assets in Scene Subjects / Beats / JSON, use canonical syntax: CHAR:[@Name], PROP:[Name], ENV:[Name].",
                    ]
                    for asset in normalized_assets:
                        detail_parts = []
                        if asset.get("type"):
                            detail_parts.append(f"type={asset['type']}")
                        if asset.get("description"):
                            detail_parts.append(f"description={asset['description']}")
                        if asset.get("anchor_description"):
                            detail_parts.append(f"anchors={asset['anchor_description']}")
                        details = " | ".join(detail_parts)
                        subject_ref = str(asset.get("subject_ref") or "").strip() or f"SUBJECT:[{asset['name']}]"
                        lines.append(f"- {subject_ref} (name={asset['name']}) {details}".strip())

                    reuse_block = wrap_injection_section("可复用Subject资产", "\n".join(lines))
                    user_content = f"{reuse_block}\n\n{user_content}"
                    logger.info(
                        "Injected reusable subject assets into prompt: count=%s tokens_est=%s",
                        len(normalized_assets),
                        _estimate_tokens(reuse_block),
                    )

        # Stage 3 entity design: inject prior same-type/same-name generation_prompt_cn
        # from THIS episode's entities only (never other episodes). Poster/cover excluded.
        request_episode_id_for_prior = None
        try:
            raw_ep = getattr(request, "episode_id", None)
            if raw_ep is not None and str(raw_ep).strip() != "":
                request_episode_id_for_prior = int(raw_ep)
        except Exception:
            request_episode_id_for_prior = None
        if is_entity_design_phase and getattr(request, "project_id", None):
            prior_prompt_types = {
                _normalize_prior_entity_design_type(item)
                for item in (subject_index_allowed_types_for_request or _PRIOR_ENTITY_DESIGN_TYPES)
            }
            prior_prompt_types = {item for item in prior_prompt_types if item in _PRIOR_ENTITY_DESIGN_TYPES}
            if not prior_prompt_types and (
                "entity_design_character" in prompt_file_lower
                or "entity_design_prop" in prompt_file_lower
                or "entity_design_environment" in prompt_file_lower
                or mode_lower.startswith("2_pass_generate_assets")
            ):
                # Fallback when target types were not inferred: allow all non-poster design types.
                prior_prompt_types = set(_PRIOR_ENTITY_DESIGN_TYPES)

            if prior_prompt_types and request_episode_id_for_prior and request_episode_id_for_prior > 0:
                subject_index_for_prior_lookup = (
                    persisted_subject_index_for_prompt
                    or sanitize_subject_index_text(getattr(request, "text", None))
                    or sanitize_subject_index_text(user_content)
                )
                try:
                    prior_prompts_block = _build_prior_entity_generation_prompts_block(
                        db,
                        int(request.project_id),
                        subject_index_for_prior_lookup,
                        allowed_types=prior_prompt_types,
                        episode_id=request_episode_id_for_prior,
                    )
                except Exception as prior_prompt_err:
                    logger.warning(
                        "[analyze_scene] failed building prior entity generation prompts: %s",
                        prior_prompt_err,
                    )
                    prior_prompts_block = ""
                if prior_prompts_block:
                    user_content = f"{prior_prompts_block}\n\n{user_content}"
                    logger.info(
                        "[analyze_scene] injected prior entity generation prompts project_id=%s episode_id=%s types=%s chars=%s",
                        getattr(request, "project_id", None),
                        request_episode_id_for_prior,
                        sorted(prior_prompt_types),
                        len(prior_prompts_block),
                    )
            elif prior_prompt_types:
                logger.info(
                    "[analyze_scene] skipped prior entity generation prompts: episode_id required for episode-scoped injection project_id=%s episode_id=%s",
                    getattr(request, "project_id", None),
                    getattr(request, "episode_id", None),
                )

        if is_scoped_asset_design:
            user_content = strip_injection_section(str(user_content or ""), "待分析剧本")
            if is_character_asset_design:
                user_content = strip_injection_section(user_content, "全局统筹道具提取")
            if is_prop_asset_design:
                user_content = strip_injection_section(user_content, "全局统筹角色提取")

        # Construct messages
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content}
        ]

        # Resolve script-analysis LLM config strictly from the function API dropdown order.
        try:
            db.commit()
        except Exception:
            pass
        config, selected_dropdown_id, dropdown_fallback_ids, dropdown_order_ids = _resolve_script_analysis_dropdown_llm_config(
            db,
            current_user_id,
            getattr(request, "function_name", None),
            getattr(request, "system_api_id", None),
            context="analyze_scene",
        )
        config = _inject_user_advanced_llm_preferences(config, current_user_snapshot)
        config = _inject_project_creativity_temperature(
            config,
            request.project_metadata,
            context="analyze_scene",
        )
        _trace_project_id = None
        try:
            _trace_project_id = (
                int(getattr(request, "project_id", None) or 0)
                or int(getattr(request_episode, "project_id", None) or 0)
                or None
            )
        except Exception:
            _trace_project_id = None
        config = _inject_llm_call_log_trace(
            config,
            user_id=current_user_id,
            user_name=getattr(current_user_snapshot, "username", None),
            project_id=_trace_project_id,
            action_name=(
                str(getattr(request, "action_name", None) or "").strip()
                or _script_analysis_action_label(
                    stage_key=getattr(stage_ctx, "stage_key", None),
                    context="analyze_scene",
                    function_name=getattr(request, "function_name", None),
                )
            ),
        )
        logger.info(
            "[analyze_scene][routing] source=dropdown_priority function_name=%s requested_system_api_id=%s selected_system_api_id=%s fallback_ids=%s provider=%s model=%s episode_id=%s trace_id=%s",
            getattr(request, "function_name", None),
            getattr(request, "system_api_id", None),
            selected_dropdown_id,
            dropdown_fallback_ids,
            (config or {}).get("provider"),
            (config or {}).get("model"),
            getattr(request, "episode_id", None),
            analysis_trace_id or "-",
        )

        # --- Debug / Truncation tracing ---
        debug_meta: Dict[str, Any] = {
            "stage": "pre_llm",
            "analysis_trace_id": analysis_trace_id,
            "request_episode_id": getattr(request, "episode_id", None),
            "provider": (config or {}).get("provider"),
            "model": (config or {}).get("model"),
            "system_prompt_chars": len(system_instruction or ""),
            "user_prompt_chars": len(user_content or ""),
            "request_text_chars": len((request.text or "")),
            "system_prompt_tokens_est": _estimate_tokens(system_instruction or ""),
            "user_prompt_tokens_est": _estimate_tokens(user_content or ""),
        }
        if template_signature:
            debug_meta.update(template_signature)

        # Billing (task_type = analysis)
        provider = (config or {}).get("provider")
        model = (config or {}).get("model")
        reservation_tx = None
        if billing_service.is_token_pricing(db, "analysis", provider, model):
            est = billing_service.estimate_reserve_tokens_from_messages(messages)
            debug_meta.update({
                "est_input_tokens": est.get("input_tokens", 0),
                "est_output_tokens": est.get("output_tokens", 0),
                "est_total_tokens": est.get("total_tokens", 0),
            })
            reserve_details = {
                "item": "scene_analysis",
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "system_prompt_len": len(system_instruction or ""),
                "user_prompt_len": len(user_content or ""),
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            }
            _scene_episode_id = getattr(request, "episode_id", None)
            if _scene_episode_id:
                reserve_details["episode_id"] = int(_scene_episode_id)
                _scene_ep = (
                    db.query(Episode)
                    .filter(Episode.id == int(_scene_episode_id), _active_episode_clause())
                    .first()
                )
                if _scene_ep and _scene_ep.project_id:
                    reserve_details["project_id"] = int(_scene_ep.project_id)
            reservation_tx = billing_service.reserve_credits(db, current_user_id, "analysis", provider, model, reserve_details)
        else:
            billing_service.check_balance(db, current_user_id, "analysis", provider, model)

        # Record max token config for diagnostics only.
        cfg_obj = (config or {}).get("config") or {}
        if not isinstance(cfg_obj, dict):
            cfg_obj = {}


        requested_cap = (
            _to_int(cfg_obj.get("max_tokens"))
            or _to_int(cfg_obj.get("max_completion_tokens"))
            or _to_int(cfg_obj.get("max_output_tokens"))
        )

        # KIE call hardening for scene analysis:
        # 1) Remove mutually-exclusive/irrelevant options that can degrade long-form outputs.
        # 2) Do not force max token cap; let provider/model defaults apply unless user set one.
        provider_name = str((config or {}).get("provider") or "").strip().lower()
        kie_removed_conflict_keys: List[str] = []
        kie_output_cap_forced = False
        kie_output_cap_source = "provider_default"
        if provider_name == "kie":
            for key in ("tools", "tool_choice", "response_format"):
                if key in cfg_obj:
                    cfg_obj.pop(key, None)
                    kie_removed_conflict_keys.append(key)

            # Scene analysis expects strict final-format output, not thought traces.
            if "include_thoughts" in cfg_obj:
                cfg_obj["include_thoughts"] = False

            # Do not force an output cap for KIE scene analysis.
            # Leave max token policy to the upstream model/provider unless user explicitly set one.
            kie_output_cap_forced = False
            if requested_cap > 0:
                kie_output_cap_source = "user_configured"

        if (config or {}).get("config") is not cfg_obj:
            config["config"] = cfg_obj

        debug_meta["config_max_tokens"] = cfg_obj.get("max_tokens")
        debug_meta["config_max_completion_tokens"] = cfg_obj.get("max_completion_tokens")
        # analyze_scene already implements endpoint-level continuation logic.
        # Disable generic llm_service auto-continuation here to avoid nested loops.
        cfg_obj["auto_continue_on_length"] = False
        debug_meta["config_max_tokens_effective"] = (
            _to_int(cfg_obj.get("max_tokens"))
            or _to_int(cfg_obj.get("max_completion_tokens"))
            or _to_int(cfg_obj.get("max_output_tokens"))
            or None
        )
        debug_meta["requested_output_cap_tokens"] = requested_cap
        debug_meta["default_output_cap_applied"] = False
        debug_meta["local_output_cap_removed"] = False
        debug_meta["kie_removed_conflict_keys"] = kie_removed_conflict_keys
        debug_meta["kie_output_cap_forced"] = kie_output_cap_forced
        debug_meta["kie_output_cap_source"] = kie_output_cap_source
        if provider_name == "kie" and (kie_removed_conflict_keys or kie_output_cap_forced):
            logger.warning(
                "[analyze_scene][kie_call_hardening] removed_keys=%s forced_cap=%s effective_max_tokens=%s",
                kie_removed_conflict_keys,
                kie_output_cap_forced,
                debug_meta.get("config_max_tokens_effective"),
            )
        elif provider_name == "kie":
            logger.info(
                "[analyze_scene][kie_call_hardening] removed_keys=%s forced_cap=%s cap_source=%s effective_max_tokens=%s",
                kie_removed_conflict_keys,
                kie_output_cap_forced,
                kie_output_cap_source,
                debug_meta.get("config_max_tokens_effective"),
            )

        logger.info(f"Analyzing scene for user {current_user_id} with model {config.get('model')}")
        # Auto-continue if provider truncates or the stream drops after yielding partial content.
        # Important: keep continuation prompts small (do NOT send the entire prior output back)
        # to avoid blowing up prompt size / hitting context window.
        # Token cap is controlled by provider/model config; local continuation only keeps a high safety ceiling.
        requested_max_segments = max(1, _to_int(cfg_obj.get("continuation_max_segments")) or 12)
        max_segments = min(_ANALYZE_SCENE_CONTINUATION_SEGMENT_HARD_CAP, requested_max_segments)
        tail_chars = 1600
        continuation_instruction_tpl = (
            "Continue exactly where you left off, immediately after the following suffix. "
            "Do NOT repeat any of the suffix text. "
            "Return ONLY the continuation in the same format as before.\n\n"
            "SUFFIX (do not repeat):\n{suffix}"
        )
        continuation_instruction_incomplete_tpl = (
            "Your previous response ended before all required sections were completed. "
            "Continue exactly from the end of the existing response. "
            "Do NOT rewrite or repeat completed content. "
            "You MUST complete these missing sections: {missing_sections}. "
            "Return ONLY the continuation text in the same format.\n\n"
            "SUFFIX (do not repeat):\n{suffix}"
        )


        async def _run_loop(target_messages):
            result_parts_loop: List[str] = []
            segments_meta_loop: List[Dict[str, Any]] = []
            usage_total_loop: Dict[str, Any] = {}
            resolved_llm_routing_loop: Dict[str, Any] = {}
            finish_reason_loop = None
            continuation_stopped_by_max_segments_loop = False
            output_char_cap_reached_loop = False
            continuation_reason_counts_loop: Dict[str, int] = {}
            continuation_by_structure_loop = 0
            provider_limit_hints_loop: List[str] = []
            llm_fallback_warnings_loop: List[str] = []

            current_messages = list(target_messages)
            system_only_messages = []
            try:
                if target_messages and isinstance(target_messages[0], dict) and target_messages[0].get("role") == "system":
                    system_only_messages = [target_messages[0]]
            except Exception:
                system_only_messages = []

            for seg_idx in range(1, max_segments + 1):
                llm_resp = await _await_analyze_scene_segment(current_messages, config)
                current_routing = _extract_llm_routing_metadata(llm_resp)
                if current_routing:
                    resolved_llm_routing_loop = current_routing
                raw_part = llm_resp.get("raw_content")
                if not isinstance(raw_part, str):
                    raw_part = llm_resp.get("content", "") or ""
                part_usage = llm_resp.get("usage", {}) or {}
                part_finish = llm_resp.get("finish_reason")
                part_limit_hints = llm_resp.get("token_limit_hints", []) or []
                part_extraction_diag = llm_resp.get("extraction_diagnostics", {}) or {}
                part_fallback_warnings = llm_resp.get("fallback_warnings", []) or []
                if isinstance(part_limit_hints, list):
                    for hint in part_limit_hints:
                        hint_text = str(hint or "").strip()
                        if hint_text and hint_text not in provider_limit_hints_loop:
                            provider_limit_hints_loop.append(hint_text)
                if isinstance(part_fallback_warnings, list):
                    for warn in part_fallback_warnings:
                        warn_text = str(warn or "").strip()
                        if warn_text and warn_text not in llm_fallback_warnings_loop:
                            llm_fallback_warnings_loop.append(warn_text)

                usage_total_loop = _merge_usage(usage_total_loop, part_usage)
                finish_reason_loop = part_finish

                existing = "".join(result_parts_loop)
                part_content = _dedupe_overlap(existing, raw_part)
                result_parts_loop.append(part_content)
                segments_meta_loop.append({
                    "index": seg_idx,
                    "finish_reason": part_finish,
                    "output_chars": len(raw_part),
                    "output_tokens_est": _estimate_tokens(raw_part),
                    "deduped_chars": len(part_content),
                    "usage": part_usage,
                    "token_limit_hints": part_limit_hints,
                    "extraction_diagnostics": part_extraction_diag,
                })

                accumulated = "".join(result_parts_loop)
                
                if part_finish == "error":
                    break
                    
                if len(accumulated) >= _ANALYZE_SCENE_OUTPUT_CHAR_HARD_CAP:
                    output_char_cap_reached_loop = True
                    finish_reason_loop = part_finish or finish_reason_loop or "safety_output_cap"
                    logger.warning(
                        "[analyze_scene] safety_output_cap_reached episode_id=%s provider=%s model=%s chars=%s cap=%s segments=%s",
                        getattr(request, "episode_id", None),
                        (config or {}).get("provider"),
                        (config or {}).get("model"),
                        len(accumulated),
                        _ANALYZE_SCENE_OUTPUT_CHAR_HARD_CAP,
                        len(segments_meta_loop or []),
                    )
                    break
                section_meta = _detect_scene_output_sections(accumulated)
                missing_sections = [str(x) for x in (section_meta.get("missing_sections") or []) if str(x)]
                continue_due_to_length = _is_length_finish_reason(part_finish)
                continue_due_to_incomplete = (
                    str(part_finish or "").strip().lower().replace("-", "_") == "incomplete"
                    and bool(accumulated.strip())
                    and seg_idx < max_segments
                )
                continue_due_to_structure = (
                    not continue_due_to_length
                    and not continue_due_to_incomplete
                    and bool(missing_sections)
                    and seg_idx < max_segments
                    and continuation_by_structure_loop < 3
                    and bool(accumulated.strip())
                )

                # Stop if not truncated.
                if not continue_due_to_length and not continue_due_to_incomplete and not continue_due_to_structure:
                    break

                # Stop if provider returned nothing new.
                if not raw_part.strip():
                    break

                # Ask for continuation; include only a short suffix of the accumulated output.
                suffix = accumulated[-tail_chars:] if len(accumulated) > tail_chars else accumulated
                continuation_reason = "length"
                if continue_due_to_structure:
                    continuation_by_structure_loop += 1
                    continuation_reason = "missing_required_sections"
                    continuation_instruction = continuation_instruction_incomplete_tpl.format(
                        missing_sections=", ".join(missing_sections),
                        suffix=suffix,
                    )
                elif continue_due_to_incomplete:
                    continuation_reason = "incomplete_stream"
                    continuation_instruction = continuation_instruction_tpl.format(suffix=suffix)
                else:
                    continuation_instruction = continuation_instruction_tpl.format(suffix=suffix)

                continuation_reason_counts_loop[continuation_reason] = int(continuation_reason_counts_loop.get(continuation_reason) or 0) + 1

                logger.info(
                    "[analyze_scene] LLM Continuation Triggered (seg_idx=%s) reason=%s missing_sections=%s part_usage=%s part_finish=%s accumulated_chars=%s",
                    seg_idx,
                    continuation_reason,
                    missing_sections,
                    part_usage,
                    part_finish,
                    len(accumulated),
                )

                # MUST re-send the whole script (target_messages) so the model knows the story.
                # Do NOT drop the user message, otherwise it will hallucinate the ending.
                current_messages = list(target_messages) + [
                    {"role": "assistant", "content": suffix},
                    {"role": "user", "content": continuation_instruction},
                ]

            finish_reason_loop_norm = str(finish_reason_loop or "").strip().lower().replace("-", "_")
            if finish_reason_loop_norm and (finish_reason_loop_norm == "incomplete" or _is_length_finish_reason(finish_reason_loop_norm)) and len(segments_meta_loop) >= max_segments:
                continuation_stopped_by_max_segments_loop = True

            return {
                "result_content": "".join(result_parts_loop),
                "segments_meta": segments_meta_loop,
                "usage_total": usage_total_loop,
                "resolved_llm_routing": resolved_llm_routing_loop,
                "finish_reason": finish_reason_loop,
                "continuation_stopped_by_max_segments": continuation_stopped_by_max_segments_loop,
                "output_char_cap_reached": output_char_cap_reached_loop,
                "continuation_reason_counts": continuation_reason_counts_loop,
                "continuation_by_structure": continuation_by_structure_loop,
                "provider_limit_hints": provider_limit_hints_loop,
                "llm_fallback_warnings": llm_fallback_warnings_loop,
            }

        # Check cache
        skip_step1 = False
        cached_result_1 = ""
        script_hash = ""
        
        req_text = getattr(request, "text", "")
        if req_text:
            script_hash = hashlib.sha256(req_text.encode("utf-8")).hexdigest()

        ep_id = getattr(request, "episode_id", None)
        if ep_id:
            ep_cache = (
                db.query(Episode)
                .filter(Episode.id == ep_id, _active_episode_clause())
                .first()
            )
            if ep_cache and script_hash:
                exist_res = ep_cache.ai_scene_analysis_result or ""
                if f"<!-- script_hash: {script_hash} -->" in exist_res:
                    if re.search(r"(?i)subject\s*index", exist_res) and "```json" not in exist_res.lower() and '"characters": [' not in exist_res:
                        skip_step1 = True
                        cached_result_1 = exist_res

        _release_db_connection(db, "analyze_scene_llm_call")

        # Step 1: LLM call (all stages share the same transport loop).
        # Execute the LLM loop generically for all modes
        try:
            loop1_res = await _run_loop(messages)
        except getattr(llm_service, "AmbiguousLLMTransportError", Exception) as e:
            if type(e).__name__ == "AmbiguousLLMTransportError":
                logger.error(f"[analyze_scene] {e}")
                raise HTTPException(status_code=504, detail=str(e))
            raise
        result_content_1 = loop1_res.get("result_content", "")
        
        # In phase 1, attach script_hash for future reference if needed
        if not is_entity_design_phase and script_hash:
            result_content_1 = f"<!-- script_hash: {script_hash} -->\n" + result_content_1

        # For script optimization / scene markdown(beats) stages,
        # drop any content before [SCENES_BLOCK_START] from returned/persisted output.
        if should_trim_before_submit:
            result_content_1 = _trim_to_scenes_block(result_content_1)
            
        result_content = result_content_1

        # Expose all loop variables so the rest of the endpoint works seamlessly
        segments_meta = loop1_res.get("segments_meta", [])
        usage_total = loop1_res.get("usage_total", {})
        resolved_llm_routing = loop1_res.get("resolved_llm_routing", {})
        finish_reason = loop1_res.get("finish_reason", "stop")
        continuation_stopped_by_max_segments = loop1_res.get("continuation_stopped_by_max_segments", False)
        output_char_cap_reached = loop1_res.get("output_char_cap_reached", False)
        continuation_reason_counts = dict(loop1_res.get("continuation_reason_counts", {}))
        continuation_by_structure = loop1_res.get("continuation_by_structure", 0)
        provider_limit_hints = list(set(loop1_res.get("provider_limit_hints", [])))
        llm_fallback_warnings = list(set(loop1_res.get("llm_fallback_warnings", [])))
        usage = usage_total
        integrity_meta = _detect_output_integrity(
            result_content,
            segments_meta,
            finish_reason,
            is_scene_beats_stage=is_scene_beats_stage,
            is_subject_index_extraction_stage=is_subject_index_extraction_stage,
        )
        if integrity_meta.get("json_invalid_suppressed"):
            logger.info(
                "[analyze_scene] suppressed_json_invalid_warning episode_id=%s mode=%s function=%s prompt_file=%s explicit_json_response=%s json_error=%s",
                getattr(request, "episode_id", None),
                mode_lower,
                function_name_lower,
                prompt_file_lower,
                integrity_meta.get("explicit_json_response"),
                integrity_meta.get("json_error"),
            )

        raw_total_chars = 0
        dedup_total_chars = 0
        try:
            raw_total_chars = sum(int(seg.get("output_chars") or 0) for seg in (segments_meta or []))
            dedup_total_chars = sum(int(seg.get("deduped_chars") or 0) for seg in (segments_meta or []))
        except Exception:
            raw_total_chars = 0
            dedup_total_chars = 0

        logger.info(
            "[analyze_scene] llm_output_length episode_id=%s provider=%s model=%s segments=%s finish_reason=%s output_chars=%s raw_total_chars=%s dedup_total_chars=%s",
            getattr(request, "episode_id", None),
            (config or {}).get("provider"),
            (config or {}).get("model"),
            len(segments_meta or []),
            finish_reason,
            len(result_content or ""),
            raw_total_chars,
            dedup_total_chars,
        )

        completion_tokens_val = usage.get("completion_tokens")
        if completion_tokens_val is None:
            completion_tokens_val = usage.get("output_tokens")
        output_cap_reached_suspected = False
        try:
            req_cap = int(debug_meta.get("requested_output_cap_tokens") or 0)
            comp_val = int(completion_tokens_val or 0)
            if req_cap > 0 and comp_val > 0 and comp_val >= int(req_cap * 0.98):
                output_cap_reached_suspected = True
        except Exception:
            output_cap_reached_suspected = False

        debug_meta.update({
            "stage": "post_llm",
            "finish_reason": finish_reason,
            "output_chars": len(result_content or ""),
            "output_tokens_est": _estimate_tokens(result_content or ""),
            "completion_tokens": completion_tokens_val,
            "output_cap_reached_suspected": output_cap_reached_suspected,
            "usage": usage,
            "segments": segments_meta,
            "max_segments": max_segments,
            "requested_max_segments": requested_max_segments,
            "segment_timeout_seconds": _ANALYZE_SCENE_SEGMENT_HARD_TIMEOUT_SECONDS,
            "output_char_hard_cap": _ANALYZE_SCENE_OUTPUT_CHAR_HARD_CAP,
            "output_char_cap_reached": output_char_cap_reached,
            "continuation_stopped_by_max_segments": continuation_stopped_by_max_segments,
            "continuation_reason_counts": continuation_reason_counts,
            "continuation_by_structure": continuation_by_structure,
            "provider_limit_hints": provider_limit_hints,
            "llm_fallback_warnings": llm_fallback_warnings,
            "integrity": integrity_meta,
            "raw_total_chars": raw_total_chars,
            "dedup_total_chars": dedup_total_chars,
        })

        # Step 2: validate transport result (no staging persist on incomplete/error).
        try:
            validate_analyze_scene_llm_finish_reason(
                finish_reason=finish_reason,
                result_content=result_content,
                provider=(config or {}).get("provider", ""),
                model=(config or {}).get("model", ""),
                episode_id=getattr(request, "episode_id", None),
            )
        except HTTPException as transport_exc:
            llm_service._safe_log_json("LLM_STREAM_INCOMPLETE_REJECTED", {
                "provider": (config or {}).get("provider", ""),
                "model": (config or {}).get("model", ""),
                "episode_id": getattr(request, "episode_id", None),
                "error": str(getattr(transport_exc, "detail", "") or ""),
                "response": {
                    "partial_content_len": len(result_content or ""),
                    "partial_content": result_content,
                },
            })
            raise

        # Subject Index completeness guard applies only to Stage 2.1 assets extraction.
        # Fail before persist so incomplete indexes cannot unlock scene orchestration / asset design.
        blocking_codes: List[str] = []
        blocking_subject_warnings: List[str] = []
        source_subject_index_text = ""
        should_check_subject_index_guard = bool(
            (not is_entity_design_phase)
            and is_subject_index_extraction_stage
        )
        if should_check_subject_index_guard:
            # Align with episode resolve path: sanitize first, then coerce/raw fallback
            # so delimiter/header quirks do not false-reject usable S00x rows.
            source_subject_index_text = sanitize_subject_index_text(result_content)
            if not _subject_index_has_usable_content(source_subject_index_text):
                source_subject_index_text = _coerce_subject_index_candidate(result_content)

            probe_text = source_subject_index_text or str(result_content or "")
            has_subject_section = bool(
                re.search(
                    r"(?i)(?:subject\s*index|subjects?\s*index|角色|道具|场景|设计资产|Entities|"
                    r"character|prop|environment|cover_poster)",
                    probe_text,
                )
                or re.search(r"(?i)(?:subject_no|subject_type)", probe_text)
            )
            has_subject_header = bool(
                re.search(
                    r"(?im)^\s*\|\s*subject_no\s*\|\s*subject_type\s*\|",
                    probe_text,
                )
                or re.search(
                    r"(?im)^\s*subject_no\s*\|\s*subject_type\s*\|",
                    probe_text,
                )
                or re.search(
                    r"(?im)^\s*subject_no(?:\s+|\t+|\s*\|\s*)subject_type\b",
                    probe_text,
                )
                or re.search(r"(?i)subject_no\s*=\s*", probe_text)
            )
            has_subject_rows = _subject_index_rows_present(probe_text) or _subject_index_has_usable_content(
                source_subject_index_text
            )

            # Entity rows alone are sufficient; section title/header is not required.
            if not has_subject_rows:
                if has_subject_header or has_subject_section:
                    blocking_codes.append("ANALYSIS_SUBJECT_INDEX_HEADER_ONLY")
                    blocking_subject_warnings.append(
                        "资产提取仅解析到 Subject Index 表头，缺少实体条目（如 S001... 行或 subject_no=... 条目），请重试。"
                    )
                else:
                    blocking_codes.append("ANALYSIS_SUBJECT_INDEX_MISSING")
                    blocking_subject_warnings.append(
                        "资产提取未解析到完整的 Subject Index 区块，请确认返回结果中包含完整的 Subject Index 内容（如标题区块与 S001... 实体行）后重试。"
                    )

        if blocking_codes:
            for code in blocking_codes:
                if code not in (integrity_meta.get("warning_codes") or []):
                    integrity_meta.setdefault("warning_codes", []).append(code)
            for warn in blocking_subject_warnings:
                warn_text = str(warn or "").strip()
                if warn_text and warn_text not in (integrity_meta.get("warnings") or []):
                    integrity_meta.setdefault("warnings", []).append(warn_text)

            detail = _build_scene_analysis_blocking_failure_detail(
                blocking_codes,
                integrity_meta.get("warnings") or [],
                blocking_subject_warnings,
            )
            output_preview = str(result_content or "").strip().replace("\n", "\\n")
            if len(output_preview) > 800:
                output_preview = output_preview[:800] + "…"
            logger.error(
                "[analyze_scene] subject_index_missing_blocking episode_id=%s codes=%s warnings=%s "
                "output_chars=%s output_preview=%s",
                getattr(request, "episode_id", None),
                blocking_codes,
                blocking_subject_warnings,
                len(result_content or ""),
                output_preview,
            )
            raise HTTPException(status_code=400, detail=detail)

        # Subject Index name lock repair (scene orchestration): if Environment Name /
        # Linked Characters / Key Props / CHAR|ENV|PROP tokens in Beats are not in the
        # Index whitelist, one LLM remap.
        subject_index_name_align_meta: Dict[str, Any] = {
            "scene_markdown": None,
            "subjects_json": None,
        }
        if (
            is_scene_beats_stage
            and str(result_content or "").strip()
            and _subject_index_has_usable_content(persisted_subject_index_for_prompt)
        ):
            scene_table_candidate = (
                extract_scenes_table_markdown_block(result_content)
                or sanitize_scene_markdown_llm_output(result_content)
                or str(result_content or "")
            )
            try:
                align_scene_id = str(getattr(request, "target_scene_id", "") or "").strip()
                scene_name_align = await align_scene_markdown_names_with_subject_index(
                    scene_markdown=scene_table_candidate,
                    subject_index_text=persisted_subject_index_for_prompt,
                    llm_config=config,
                    db=db,
                    project_id=getattr(request, "project_id", None) or orchestration_project_id,
                    episode_id=getattr(request, "episode_id", None),
                    extra_derived_environment_names=extract_derived_environment_names_from_scene_text(
                        getattr(request, "text", "") or ""
                    ),
                    action_name=(
                        f"实体名对齐 · {align_scene_id}"
                        if align_scene_id
                        else "实体名对齐 · 场景表"
                    ),
                )
                subject_index_name_align_meta["scene_markdown"] = {
                    "mismatch_count": scene_name_align.get("mismatch_count") or 0,
                    "applied_count": scene_name_align.get("applied_count") or 0,
                    "remaining_count": len(scene_name_align.get("remaining_mismatches") or []),
                    "replacements": scene_name_align.get("replacements") or [],
                }
                if scene_name_align.get("changed") and str(scene_name_align.get("text") or "").strip():
                    result_content = str(scene_name_align.get("text") or "")
                    logger.info(
                        "[analyze_scene] subject_index_name_align scene_markdown applied=%s mismatches=%s episode_id=%s",
                        scene_name_align.get("applied_count") or 0,
                        scene_name_align.get("mismatch_count") or 0,
                        getattr(request, "episode_id", None),
                    )
            except Exception as scene_name_align_exc:
                logger.warning(
                    "[analyze_scene] subject_index_name_align scene_markdown failed episode_id=%s err=%s",
                    getattr(request, "episode_id", None),
                    scene_name_align_exc,
                    exc_info=scene_name_align_exc,
                )

        # Step 3: persist staging fields only (no scenes/entities/shots import).
        saved_to_episode = False
        persist_skipped = bool(getattr(request, "skip_episode_persist", False))
        if (
            not persist_skipped
            and (is_scene_split_stage or is_script_optimization_stage)
            and not _script_optimization_has_project_visual_backfill(result_content)
        ):
            persist_skipped = True
            debug_meta["persist_skipped_incomplete_visual_backfill"] = True
            logger.warning(
                "[analyze_scene] skip persist: scene_split missing project_visual_backfill episode_id=%s",
                getattr(request, "episode_id", None),
            )
        persisted_field_name = None
        persisted_chars_readback = None
        if getattr(request, "episode_id", None) and not persist_skipped:
            episode_id = request.episode_id
            episode = (
                db.query(Episode)
                .filter(Episode.id == episode_id, _active_episode_clause())
                .first()
            )
            if episode and not current_user_is_superuser:
                auth_user = db.query(User).filter(User.id == current_user_id).first()
                if not auth_user:
                    raise HTTPException(status_code=401, detail="User not found")
                _require_project_access(db, episode.project_id, auth_user)
            if not episode:
                raise HTTPException(status_code=404, detail="Episode not found or has been deleted")

            try:
                persist_result = persist_analyze_scene_stage_result(
                    db=db,
                    episode=episode,
                    result_content=result_content,
                    stage_ctx=stage_ctx,
                )
            except Exception:
                db.rollback()
                raise

            saved_to_episode = bool(persist_result.get("saved_to_episode"))
            persisted_field_name = persist_result.get("saved_field")
            persisted_chars_readback = int(persist_result.get("saved_chars_readback") or 0)
            debug_meta["saved_to_episode"] = saved_to_episode
            debug_meta["saved_episode_id"] = persist_result.get("saved_episode_id")
            debug_meta["saved_field"] = persisted_field_name
            debug_meta["saved_chars_readback"] = persisted_chars_readback
            debug_meta["stage_key"] = persist_result.get("stage_key")
            if saved_to_episode:
                logger.info(
                    "[analyze_scene] persisted_readback episode_id=%s field=%s chars=%s raw_total_chars=%s dedup_total_chars=%s output_chars=%s stage_key=%s",
                    episode_id,
                    persisted_field_name,
                    persisted_chars_readback,
                    raw_total_chars,
                    dedup_total_chars,
                    len(result_content or ""),
                    persist_result.get("stage_key"),
                )
        else:
            debug_meta["saved_to_episode"] = False
            debug_meta["persist_skipped"] = persist_skipped
            debug_meta["saved_field"] = None
            debug_meta["saved_chars_readback"] = 0
            debug_meta["stage_key"] = stage_ctx.stage_key
            if persist_skipped:
                logger.info(
                    "[analyze_scene] skip_episode_persist episode_id=%s provider=%s model=%s output_chars=%s stage_key=%s",
                    getattr(request, "episode_id", None),
                    (config or {}).get("provider"),
                    (config or {}).get("model"),
                    len(result_content or ""),
                    stage_ctx.stage_key,
                )
            else:
                logger.warning(
                    "[analyze_scene] no_episode_id_skip_persist provider=%s model=%s output_chars=%s raw_total_chars=%s dedup_total_chars=%s stage_key=%s",
                    (config or {}).get("provider"),
                    (config or {}).get("model"),
                    len(result_content or ""),
                    raw_total_chars,
                    dedup_total_chars,
                    stage_ctx.stage_key,
                )

        if integrity_meta.get("truncation_suspected") or continuation_stopped_by_max_segments:
            logger.warning(
                "[analyze_scene] final_output_incomplete episode_id=%s provider=%s model=%s ended_with_length=%s truncation_detected=%s structure_incomplete=%s missing_sections=%s continuation_stopped_by_max_segments=%s warning_codes=%s",
                getattr(request, "episode_id", None),
                (config or {}).get("provider"),
                (config or {}).get("model"),
                integrity_meta.get("ended_with_length"),
                integrity_meta.get("truncation_detected"),
                integrity_meta.get("structure_incomplete"),
                integrity_meta.get("missing_sections") or [],
                continuation_stopped_by_max_segments,
                integrity_meta.get("warning_codes") or [],
            )
        elif integrity_meta.get("truncation_detected"):
            logger.info(
                "[analyze_scene] length_limited_segments_resolved episode_id=%s provider=%s model=%s segments=%s warning_codes=%s",
                getattr(request, "episode_id", None),
                (config or {}).get("provider"),
                (config or {}).get("model"),
                len(segments_meta or []),
                integrity_meta.get("warning_codes") or [],
            )

        # Billing finalize (commit happens inside billing service; will persist episode update if set above)
        if reservation_tx:
            actual_details = {"item": "scene_analysis"}
            if usage:
                actual_details.update(usage)
            _apply_llm_routing_to_billing_details(actual_details, resolved_llm_routing)
            # Normalize common usage keys
            if "prompt_tokens" in actual_details and "input_tokens" not in actual_details:
                actual_details["input_tokens"] = actual_details.get("prompt_tokens", 0)
            if "completion_tokens" in actual_details and "output_tokens" not in actual_details:
                actual_details["output_tokens"] = actual_details.get("completion_tokens", 0)
            billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), actual_details)
        else:
            details = {"item": "scene_analysis"}
            if usage:
                details.update(usage)
            _apply_llm_routing_to_billing_details(details, resolved_llm_routing)
            # Normalize usage keys for token-based calculation if provider returns OpenAI-style usage
            if "prompt_tokens" in details and "input_tokens" not in details:
                details["input_tokens"] = details.get("prompt_tokens", 0)
            if "completion_tokens" in details and "output_tokens" not in details:
                details["output_tokens"] = details.get("completion_tokens", 0)
            billing_service.deduct_credits(db, current_user_id, "analysis", provider, model, details)

        response_payload: Dict[str, Any] = {"success": True, "result": result_content, "meta": debug_meta}
        if is_scene_beats_stage and str(result_content or "").strip():
            extracted_beats_table = extract_scenes_table_markdown_block(result_content)
            if extracted_beats_table:
                result_content = extracted_beats_table
                response_payload["result"] = result_content
            else:
                logger.warning(
                    "[analyze_scene] scene_beats table extraction produced no data row | episode_id=%s output_chars=%s output_tail=%s",
                    getattr(request, "episode_id", None),
                    len(str(result_content or "")),
                    str(result_content or "")[-400:],
                )
        if not saved_to_episode and not persist_skipped and not getattr(request, "episode_id", None):
            response_payload["warnings"] = [
                *list(response_payload.get("warnings") or []),
                "No episode_id was provided; raw LLM output was returned but not persisted to episode fields.",
            ]
            response_payload["warning_codes"] = [
                *list(response_payload.get("warning_codes") or []),
                "ANALYSIS_EPISODE_ID_MISSING_NOT_PERSISTED",
            ]

        # Extract subjects_json from LLM output so frontend can use pre-parsed
        # clean JSON instead of re-parsing the raw markdown with heuristic regex.
        # Scene beats orchestration only validates Scenes Table output; skip Subject Index checks.
        sc_warning_codes: List[str] = []
        sc_warnings: List[str] = []
        template_warning_codes: List[str] = []
        template_warnings: List[str] = []
        coverage_warning_codes: List[str] = []
        coverage_warnings: List[str] = []
        extraction_gap_warning_codes: List[str] = []
        extraction_gap_warnings: List[str] = []
        subject_index_reconcile_warning_codes: List[str] = []
        subject_index_reconcile_warnings: List[str] = []

        if is_scene_beats_stage:
            subjects_json = {
                "characters": [],
                "props": [],
                "environments": [],
                "covers": [],
                "posters": [],
            }
            response_payload["subjects_json"] = subjects_json
            response_payload["subjects_json_count"] = {
                "characters": 0,
                "props": 0,
                "environments": 0,
                "covers": 0,
                "posters": 0,
            }
            debug_meta["subject_post_process_skipped"] = True
            debug_meta["subject_index_name_align"] = subject_index_name_align_meta
            scene_align_meta = subject_index_name_align_meta.get("scene_markdown") or {}
            if int(scene_align_meta.get("applied_count") or 0) > 0:
                response_payload["warnings"] = [
                    *list(response_payload.get("warnings") or []),
                    (
                        "Subject Index name alignment via LLM applied: "
                        f"remapped {int(scene_align_meta.get('applied_count') or 0)} "
                        f"of {int(scene_align_meta.get('mismatch_count') or 0)} off-index "
                        "names (table columns and/or CHAR/ENV/PROP tokens in Beats)."
                    ),
                ]
                response_payload["warning_codes"] = [
                    *list(response_payload.get("warning_codes") or []),
                    "ANALYSIS_SUBJECT_INDEX_NAME_LLM_ALIGNED",
                ]
        else:
            subjects_json = _extract_subjects_json_from_text(result_content)
            if not any(len(subjects_json.get(k) or []) > 0 for k in ("characters", "props", "environments", "covers", "posters")):
                for cleaned_for_json in _collect_llm_json_text_candidates(result_content):
                    subjects_json = _extract_subjects_json_from_text(cleaned_for_json)
                    if any(len(subjects_json.get(k) or []) > 0 for k in ("characters", "props", "environments", "covers", "posters")):
                        break

            if not source_subject_index_text:
                source_subject_index_text = sanitize_subject_index_text(result_content)

            subject_index_reconcile_result = _reconcile_subjects_json_with_subject_index(source_subject_index_text, subjects_json)
            subjects_json = subject_index_reconcile_result.get("subjects_json") or subjects_json
            subject_index_reconcile_meta = subject_index_reconcile_result.get("meta") or {}
            subject_index_reconcile_warning_codes = subject_index_reconcile_result.get("warning_codes") or []
            subject_index_reconcile_warnings = subject_index_reconcile_result.get("warnings") or []

            # Subject Index name lock repair (asset design): if name/name_en are not in
            # the Index whitelist, one LLM remap, then re-reconcile.
            align_index_text = (
                persisted_subject_index_for_prompt
                if _subject_index_has_usable_content(persisted_subject_index_for_prompt)
                else source_subject_index_text
            )
            if is_entity_design_phase and _subject_index_has_usable_content(align_index_text):
                try:
                    subjects_name_align = await align_subjects_json_names_with_subject_index(
                        subjects_json=subjects_json,
                        subject_index_text=align_index_text,
                        llm_config=config,
                        action_name="实体名对齐 · 资产设计",
                    )
                    subject_index_name_align_meta["subjects_json"] = {
                        "mismatch_count": subjects_name_align.get("mismatch_count") or 0,
                        "applied_count": subjects_name_align.get("applied_count") or 0,
                        "remaining_count": len(subjects_name_align.get("remaining_mismatches") or []),
                        "replacements": subjects_name_align.get("replacements") or [],
                    }
                    if subjects_name_align.get("changed"):
                        subjects_json = subjects_name_align.get("subjects_json") or subjects_json
                        # Re-run deterministic reconcile so subject_no/name/name_en stay canonical.
                        subject_index_reconcile_result = _reconcile_subjects_json_with_subject_index(
                            align_index_text,
                            subjects_json,
                        )
                        subjects_json = subject_index_reconcile_result.get("subjects_json") or subjects_json
                        subject_index_reconcile_meta = subject_index_reconcile_result.get("meta") or subject_index_reconcile_meta
                        for code in (subject_index_reconcile_result.get("warning_codes") or []):
                            if code not in subject_index_reconcile_warning_codes:
                                subject_index_reconcile_warning_codes.append(code)
                        for warn in (subject_index_reconcile_result.get("warnings") or []):
                            if warn not in subject_index_reconcile_warnings:
                                subject_index_reconcile_warnings.append(warn)

                        replacements = subjects_name_align.get("replacements") or []
                        if replacements:
                            patched_result = apply_text_name_replacements(result_content, replacements)
                            if patched_result != str(result_content or ""):
                                result_content = patched_result
                                response_payload["result"] = result_content
                                if saved_to_episode and getattr(request, "episode_id", None):
                                    try:
                                        episode_for_realign = (
                                            db.query(Episode)
                                            .filter(
                                                Episode.id == int(request.episode_id),
                                                _active_episode_clause(),
                                            )
                                            .first()
                                        )
                                        if episode_for_realign is not None:
                                            persist_analyze_scene_stage_result(
                                                db=db,
                                                episode=episode_for_realign,
                                                result_content=result_content,
                                                stage_ctx=stage_ctx,
                                            )
                                    except Exception as realign_persist_exc:
                                        db.rollback()
                                        logger.warning(
                                            "[analyze_scene] subject_index_name_align re-persist failed episode_id=%s err=%s",
                                            getattr(request, "episode_id", None),
                                            realign_persist_exc,
                                        )
                        logger.info(
                            "[analyze_scene] subject_index_name_align subjects_json applied=%s mismatches=%s episode_id=%s",
                            subjects_name_align.get("applied_count") or 0,
                            subjects_name_align.get("mismatch_count") or 0,
                            getattr(request, "episode_id", None),
                        )
                        subject_index_reconcile_warning_codes = [
                            *list(subject_index_reconcile_warning_codes),
                            "ANALYSIS_SUBJECT_INDEX_NAME_LLM_ALIGNED",
                        ]
                        subject_index_reconcile_warnings = [
                            *list(subject_index_reconcile_warnings),
                            (
                                "Subject Index name alignment via LLM applied: "
                                f"remapped {int(subjects_name_align.get('applied_count') or 0)} "
                                f"of {int(subjects_name_align.get('mismatch_count') or 0)} off-index name/name_en values."
                            ),
                        ]
                except Exception as subjects_name_align_exc:
                    logger.warning(
                        "[analyze_scene] subject_index_name_align subjects_json failed episode_id=%s err=%s",
                        getattr(request, "episode_id", None),
                        subjects_name_align_exc,
                        exc_info=subjects_name_align_exc,
                    )

            response_payload["subjects_json"] = subjects_json
            response_payload["subjects_json_count"] = {
                "characters": len(subjects_json.get("characters") or []),
                "props": len(subjects_json.get("props") or []),
                "environments": len(subjects_json.get("environments") or []),
                "covers": len(subjects_json.get("covers") or []),
                "posters": len(subjects_json.get("posters") or []),
            }

            extraction_gap_meta = _detect_subjects_json_extraction_gap(result_content, subjects_json)
            debug_meta["subjects_json_extraction_gap"] = extraction_gap_meta

            try:
                subject_index_coverage_meta = _detect_subject_index_coverage_warnings(
                    source_subject_index_text, subjects_json
                )
            except Exception as coverage_exc:
                logger.warning(
                    "[analyze_scene] subject_index_coverage check failed episode_id=%s err=%s",
                    getattr(request, "episode_id", None),
                    coverage_exc,
                    exc_info=coverage_exc,
                )
                subject_index_coverage_meta = {
                    "expected_total": 0,
                    "expected_by_bucket": {
                        "characters": 0,
                        "props": 0,
                        "environments": 0,
                        "covers": 0,
                        "posters": 0,
                    },
                    "missing_total": 0,
                    "missing_by_bucket": {
                        "characters": [],
                        "props": [],
                        "environments": [],
                        "covers": [],
                        "posters": [],
                    },
                    "warning_codes": [],
                    "warnings": [],
                }
            debug_meta["subject_index_coverage"] = subject_index_coverage_meta
            debug_meta["subject_index_reconciliation"] = subject_index_reconcile_meta
            debug_meta["subject_index_name_align"] = subject_index_name_align_meta

            subject_consistency_meta = _detect_subject_consistency_warnings(result_content, subjects_json)
            debug_meta["subject_consistency"] = subject_consistency_meta

            prompt_syntax_rules = ANALYSIS_PROMPT_TEMPLATE_SYNTAX_RULES

            prompt_template_meta = _detect_prompt_template_syntax_warnings(result_content, prompt_syntax_rules)
            debug_meta["prompt_template_syntax"] = prompt_template_meta

            diagnosis_hints: List[str] = []
            if (extraction_gap_meta.get("missing_total") or 0) > 0:
                diagnosis_hints.append("subjects_json_parser_selected_partial_candidate")

            expected_by_bucket = subject_index_coverage_meta.get("expected_by_bucket") or {}
            missing_by_bucket = subject_index_coverage_meta.get("missing_by_bucket") or {}
            expected_props = int(expected_by_bucket.get("props") or 0)
            missing_props_count = len(missing_by_bucket.get("props") or [])

            if expected_props > 0 and missing_props_count > 0 and not diagnosis_hints:
                if bool(output_char_cap_reached) or bool((integrity_meta or {}).get("truncation_detected")):
                    diagnosis_hints.append("llm_output_truncated_under_token_or_char_pressure")
                elif str(finish_reason or "").strip().lower().replace("-", "_") in {"length", "incomplete", "max_tokens"}:
                    diagnosis_hints.append("llm_stopped_early_before_prop_sections")
                else:
                    diagnosis_hints.append("llm_subject_bucket_collapse_or_instruction_conflict")

            if expected_props > 0 and missing_props_count == expected_props:
                diagnosis_hints.append("all_expected_props_missing")
            elif missing_props_count > 0:
                diagnosis_hints.append("partial_props_missing")

            if diagnosis_hints:
                debug_meta["entity_design_diagnosis_hints"] = list(dict.fromkeys(diagnosis_hints))

            sc_warning_codes = subject_consistency_meta.get("warning_codes") or []
            sc_warnings = subject_consistency_meta.get("warnings") or []
            template_warning_codes = prompt_template_meta.get("warning_codes") or []
            template_warnings = prompt_template_meta.get("warnings") or []
            coverage_warning_codes = subject_index_coverage_meta.get("warning_codes") or []
            coverage_warnings = subject_index_coverage_meta.get("warnings") or []
            extraction_gap_warning_codes = extraction_gap_meta.get("warning_codes") or []
            extraction_gap_warnings = extraction_gap_meta.get("warnings") or []
            if subject_index_reconcile_warnings:
                response_payload["warnings"] = [
                    *list(response_payload.get("warnings") or []),
                    *list(subject_index_reconcile_warnings),
                ]
            if subject_index_reconcile_warning_codes:
                response_payload["warning_codes"] = [
                    *list(response_payload.get("warning_codes") or []),
                    *list(subject_index_reconcile_warning_codes),
                ]

        if integrity_meta.get("warnings"):
            response_payload["warnings"] = integrity_meta.get("warnings")
        if integrity_meta.get("warning_codes"):
            response_payload["warning_codes"] = integrity_meta.get("warning_codes")

        if output_char_cap_reached:
            response_payload["warnings"] = [
                *list(response_payload.get("warnings") or []),
                f"Analysis output reached safety cap of {_ANALYZE_SCENE_OUTPUT_CHAR_HARD_CAP} characters and was stopped early.",
            ]
            response_payload["warning_codes"] = [
                *list(response_payload.get("warning_codes") or []),
                "ANALYSIS_OUTPUT_CHAR_CAP_REACHED",
            ]

        if sc_warnings:
            response_payload["warnings"] = [
                *list(response_payload.get("warnings") or []),
                *list(sc_warnings),
            ]
        if sc_warning_codes:
            response_payload["warning_codes"] = [
                *list(response_payload.get("warning_codes") or []),
                *list(sc_warning_codes),
            ]

        if template_warnings:
            response_payload["warnings"] = [
                *list(response_payload.get("warnings") or []),
                *list(template_warnings),
            ]
        if template_warning_codes:
            response_payload["warning_codes"] = [
                *list(response_payload.get("warning_codes") or []),
                *list(template_warning_codes),
            ]

        if coverage_warnings:
            response_payload["warnings"] = [
                *list(response_payload.get("warnings") or []),
                *list(coverage_warnings),
            ]
        if coverage_warning_codes:
            response_payload["warning_codes"] = [
                *list(response_payload.get("warning_codes") or []),
                *list(coverage_warning_codes),
            ]

        if extraction_gap_warnings:
            response_payload["warnings"] = [
                *list(response_payload.get("warnings") or []),
                *list(extraction_gap_warnings),
            ]
        if extraction_gap_warning_codes:
            response_payload["warning_codes"] = [
                *list(response_payload.get("warning_codes") or []),
                *list(extraction_gap_warning_codes),
            ]

        if llm_fallback_warnings:
            response_payload["warnings"] = [
                *list(response_payload.get("warnings") or []),
                *list(llm_fallback_warnings),
            ]
            response_payload["warning_codes"] = [
                *list(response_payload.get("warning_codes") or []),
                "ANALYSIS_LLM_CALL_FAILED_RETRIED",
            ]

        if response_payload.get("warnings"):
            response_payload["warnings"] = list(dict.fromkeys([str(x or "").strip() for x in response_payload["warnings"] if str(x or "").strip()]))
        if response_payload.get("warning_codes"):
            response_payload["warning_codes"] = list(dict.fromkeys([str(x or "").strip() for x in response_payload["warning_codes"] if str(x or "").strip()]))

        if integrity_meta.get("warning_codes") or integrity_meta.get("warnings"):
            try:
                logger.warning(
                    "[analyze_scene] integrity warning episode_id=%s codes=%s warnings=%s",
                    getattr(request, "episode_id", None),
                    integrity_meta.get("warning_codes") or [],
                    integrity_meta.get("warnings") or [],
                )
            except Exception:
                pass
        if sc_warning_codes or sc_warnings:
            try:
                logger.warning(
                    "[analyze_scene] subject consistency warning episode_id=%s codes=%s warnings=%s",
                    getattr(request, "episode_id", None),
                    sc_warning_codes,
                    sc_warnings,
                )
            except Exception:
                pass
        if template_warning_codes or template_warnings:
            try:
                logger.warning(
                    "[analyze_scene] prompt template syntax warning episode_id=%s codes=%s warnings=%s mismatches=%s",
                    getattr(request, "episode_id", None),
                    template_warning_codes,
                    template_warnings,
                    (prompt_template_meta or {}).get("mismatch_count", 0),
                )
            except Exception:
                pass

        if coverage_warning_codes or coverage_warnings:
            try:
                logger.warning(
                    "[analyze_scene] subject index coverage warning episode_id=%s codes=%s warnings=%s missing_total=%s",
                    getattr(request, "episode_id", None),
                    coverage_warning_codes,
                    coverage_warnings,
                    (subject_index_coverage_meta or {}).get("missing_total", 0),
                )
            except Exception:
                pass

        if extraction_gap_warning_codes or extraction_gap_warnings:
            try:
                logger.warning(
                    "[analyze_scene] subjects_json extraction gap episode_id=%s codes=%s selected=%s aggregated=%s",
                    getattr(request, "episode_id", None),
                    extraction_gap_warning_codes,
                    (extraction_gap_meta or {}).get("selected_counts") or {},
                    (extraction_gap_meta or {}).get("aggregated_counts") or {},
                )
            except Exception:
                pass

        if subject_index_reconcile_warning_codes or subject_index_reconcile_warnings:
            try:
                logger.warning(
                    "[analyze_scene] subject index reconciliation episode_id=%s codes=%s meta=%s warnings=%s",
                    getattr(request, "episode_id", None),
                    subject_index_reconcile_warning_codes,
                    subject_index_reconcile_meta,
                    subject_index_reconcile_warnings,
                )
            except Exception:
                pass

        review_required_codes = set()
        review_required_codes.update(integrity_meta.get("warning_codes") or [])
        severe_import_review_codes = {
            "ANALYSIS_JSON_INVALID",
            "ANALYSIS_STRUCTURE_INCOMPLETE",
        }
        if not is_scene_beats_stage:
            severe_import_review_codes.update(
                {
                    "ANALYSIS_SUBJECT_INDEX_MISSING",
                    "ANALYSIS_SUBJECT_INDEX_HEADER_ONLY",
                }
            )
        matched_review_codes = [code for code in severe_import_review_codes if code in review_required_codes]
        if matched_review_codes:
            review_messages: List[str] = []
            review_messages.extend([str(x or "").strip() for x in (integrity_meta.get("warnings") or []) if str(x or "").strip()])
            review_messages = list(dict.fromkeys(review_messages))
            logger.warning(
                "[analyze_scene] import_review_required_non_blocking episode_id=%s codes=%s warnings=%s",
                getattr(request, "episode_id", None),
                matched_review_codes,
                review_messages,
            )
            response_payload["import_review_required"] = True
            response_payload["import_review_codes"] = matched_review_codes
            if review_messages:
                response_payload["import_review_messages"] = review_messages
        return response_payload

    except HTTPException as e:
        # Preserve original status codes (e.g., 402 insufficient credits)
        conf_log = locals().get("config") or {}
        p_log = conf_log.get("provider")
        prefixed_detail = _vendor_failed_message(p_log, e.detail)
        logger.warning(f"Scene Analysis HTTPException: {prefixed_detail}")
        try:
            reservation_tx = locals().get("reservation_tx")
            if reservation_tx:
                billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), prefixed_detail)
        except:
            pass
        try:
            m_log = conf_log.get("model")
            billing_service.log_failed_transaction(db, current_user_id, "analysis", p_log, m_log, prefixed_detail)
        except:
            pass
        raise HTTPException(status_code=e.status_code, detail=prefixed_detail)
    except Exception as e:
        conf_log = locals().get("config") or {}
        p_log = conf_log.get("provider")
        prefixed_detail = _vendor_failed_message(p_log, e)
        logger.error(f"Scene Analysis Failed: {prefixed_detail}", exc_info=True)
        try:
            reservation_tx = locals().get("reservation_tx")
            if reservation_tx:
                billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), prefixed_detail)
        except:
            pass
        # Log failure
        try:
             m_log = conf_log.get("model")
             billing_service.log_failed_transaction(db, current_user_id, "analysis", p_log, m_log, prefixed_detail)
        except:
             pass # Fail safe
        raise HTTPException(status_code=500, detail=prefixed_detail)
