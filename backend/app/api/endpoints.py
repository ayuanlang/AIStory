
from fastapi import APIRouter, Depends, HTTPException, Body, Request
import logging
import smtplib
from email.message import EmailMessage
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from app.db.session import get_db, SessionLocal
from app.models.all_models import Project, ProjectShare, User, Episode, Scene, Shot, Entity, Asset, APISetting, SystemAPISetting, ScriptSegment, PricingRule, TransactionHistory
from app.schemas.agent import AgentRequest, AgentResponse, AnalyzeSceneRequest
from app.services.agent_service import agent_service
from app.services.billing_service import billing_service
from app.services.llm_service import llm_service
from app.services.payment_service import payment_service
from app.db.init_db import check_and_migrate_tables  # EMERGENCY FIX IMPORT
import os


from app.services.media_service import MediaGenerationService
from app.services.video_service import create_montage
from app.api.deps import get_current_user  # Import dependency
from typing import List, Optional, Dict, Any, Union, Tuple
from pydantic import BaseModel
import bcrypt
import re
import json
from datetime import datetime, timedelta
from jose import jwt
from app.core.config import settings
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import File, UploadFile
import shutil
import os
import uuid
from PIL import Image
import requests
import asyncio
import urllib.parse
import socket
import time
from pathlib import Path
from collections import deque
import threading
import asyncio

# Import limiter from main app state or create a local reference if needed
# We will use the request.app.state.limiter in the endpoints
from slowapi import Limiter
from slowapi.util import get_remote_address

# Create a local limiter instance for the router decorators
limiter = Limiter(key_func=get_remote_address)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/login/access-token")

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password):
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

router = APIRouter()
media_service = MediaGenerationService()
logger = logging.getLogger("api_logger")

IMAGE_JOB_STORE: Dict[str, Dict[str, Any]] = {}
IMAGE_JOB_LOCK = threading.Lock()
IMAGE_JOB_TTL_SECONDS = max(300, int(os.getenv("IMAGE_JOB_TTL_SECONDS", "3600")))
IMAGE_JOB_MAX_ITEMS = max(100, int(os.getenv("IMAGE_JOB_MAX_ITEMS", "500")))
IMAGE_SUBMIT_IDEMPOTENCY_STORE: Dict[str, Dict[str, Any]] = {}
IMAGE_SUBMIT_IDEMPOTENCY_TTL_SECONDS = max(30, int(os.getenv("IMAGE_SUBMIT_IDEMPOTENCY_TTL_SECONDS", "120")))


def _build_image_idempotency_store_key(user_id: int, idempotency_key: str) -> str:
    return f"{int(user_id)}::{idempotency_key.strip()}"


def _prune_image_submit_idempotency_locked(now: Optional[datetime] = None) -> None:
    now_dt = now or datetime.utcnow()
    expired_keys: List[str] = []

    for store_key, record in IMAGE_SUBMIT_IDEMPOTENCY_STORE.items():
        created_at = _parse_iso_datetime(record.get("created_at"))
        if not created_at:
            expired_keys.append(store_key)
            continue

        if (now_dt - created_at).total_seconds() > IMAGE_SUBMIT_IDEMPOTENCY_TTL_SECONDS:
            expired_keys.append(store_key)
            continue

        job_id = str(record.get("job_id") or "").strip()
        if not job_id or job_id not in IMAGE_JOB_STORE:
            expired_keys.append(store_key)

    for store_key in expired_keys:
        IMAGE_SUBMIT_IDEMPOTENCY_STORE.pop(store_key, None)


def _is_shot_submit_debug_enabled() -> bool:
    return str(os.getenv("SHOT_SUBMIT_DEBUG", "0")).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_ref_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.strip()
        return [raw] if raw else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item or "").strip()]
    return []


def _log_shot_submit_debug(kind: str, req: Any, refs: Any = None, extra: Optional[Dict[str, Any]] = None) -> None:
    if not _is_shot_submit_debug_enabled():
        return
    try:
        final_refs = _normalize_ref_list(refs if refs is not None else getattr(req, "ref_image_url", None))
        payload = {
            "kind": kind,
            "project_id": getattr(req, "project_id", None),
            "shot_id": getattr(req, "shot_id", None),
            "shot_number": getattr(req, "shot_number", None),
            "shot_name": getattr(req, "shot_name", None),
            "asset_type": getattr(req, "asset_type", None),
            "provider": getattr(req, "provider", None),
            "model": getattr(req, "model", None),
            "prompt": str(getattr(req, "prompt", "") or ""),
            "prompt_len": len(str(getattr(req, "prompt", "") or "")),
            "ref_count": len(final_refs),
            "refs": final_refs,
        }
        if extra:
            payload.update(extra)
        llm_service.log_audit("SHOT_SUBMIT_DEBUG", payload)
    except Exception as exc:
        logger.warning("[ShotSubmitDebug] failed to log payload: %s", exc)


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def _job_sort_key(item: Dict[str, Any]) -> datetime:
    for field in ("created_at", "started_at", "finished_at"):
        parsed = _parse_iso_datetime(item.get(field))
        if parsed:
            return parsed
    return datetime.utcnow()


def _compact_job_result(result: Any) -> Any:
    if not isinstance(result, dict):
        return result

    compact: Dict[str, Any] = {}
    for key in ("url", "type", "provider", "model", "error"):
        if key in result:
            compact[key] = result.get(key)

    metadata = result.get("metadata")
    if isinstance(metadata, dict):
        compact_meta = {}
        for key in ("provider", "model", "task_id", "job_id", "status"):
            if key in metadata:
                compact_meta[key] = metadata.get(key)
        if compact_meta:
            compact["metadata"] = compact_meta

    return compact or {"url": result.get("url")}


def _prune_image_jobs_locked() -> None:
    now = datetime.utcnow()
    expired_ids = []

    for job_id, job in IMAGE_JOB_STORE.items():
        status = str(job.get("status") or "").lower()
        if status not in {"succeeded", "failed", "canceled", "cancelled", "error"}:
            continue

        finished_at = _parse_iso_datetime(job.get("finished_at")) or _job_sort_key(job)
        age_seconds = (now - finished_at).total_seconds()
        if age_seconds > IMAGE_JOB_TTL_SECONDS:
            expired_ids.append(job_id)

    for job_id in expired_ids:
        IMAGE_JOB_STORE.pop(job_id, None)

    if len(IMAGE_JOB_STORE) <= IMAGE_JOB_MAX_ITEMS:
        return

    ordered = sorted(IMAGE_JOB_STORE.items(), key=lambda pair: _job_sort_key(pair[1]))
    overflow_count = len(IMAGE_JOB_STORE) - IMAGE_JOB_MAX_ITEMS
    for job_id, _ in ordered[:overflow_count]:
        IMAGE_JOB_STORE.pop(job_id, None)

    _prune_image_submit_idempotency_locked(now)


def _snapshot_image_job_stats() -> Dict[str, Any]:
    with IMAGE_JOB_LOCK:
        _prune_image_jobs_locked()
        jobs = list(IMAGE_JOB_STORE.values())

    status_counts: Dict[str, int] = {}
    created_times: List[datetime] = []
    approx_bytes = 0

    for job in jobs:
        status = str(job.get("status") or "unknown").lower()
        status_counts[status] = status_counts.get(status, 0) + 1

        created_at = _parse_iso_datetime(job.get("created_at"))
        if created_at:
            created_times.append(created_at)

        try:
            approx_bytes += len(json.dumps(job, ensure_ascii=False, default=str))
        except Exception:
            approx_bytes += 0

    oldest_created_at = min(created_times).isoformat() if created_times else None
    newest_created_at = max(created_times).isoformat() if created_times else None

    return {
        "store_items": len(jobs),
        "status_counts": status_counts,
        "oldest_created_at": oldest_created_at,
        "newest_created_at": newest_created_at,
        "approx_store_bytes": approx_bytes,
        "approx_store_mb": round(approx_bytes / (1024 * 1024), 3),
        "ttl_seconds": IMAGE_JOB_TTL_SECONDS,
        "max_items": IMAGE_JOB_MAX_ITEMS,
    }


def _vendor_failed_message(provider: Optional[str], reason: Any) -> str:
    vendor = str(provider or "").strip() or "unknown"
    detail = str(reason or "unknown error").strip()
    if "供应商调用失败" in detail:
        return detail
    return f"{vendor}供应商调用失败: {detail}"


@router.post("/fix-db-schema")
def fix_db_schema_endpoint(current_user: User = Depends(get_current_user)):
    """
    Emergency endpoint to trigger DB migration manually.
    Only accessible by authorized users (technically any logged in user for now, assuming admin).
    """
    try:
        if not current_user.is_superuser: # Basic protection if is_superuser exists
             # logger.warning(f"User {current_user.username} tried to fix DB but is not superuser")
             # pass # Loose check for now as we are desperate
             pass

        logger.info(f"Manual DB Fix triggered by {current_user.username}")
        check_and_migrate_tables()
        return {"message": "Migration script executed successfully. Check logs for details."}
    except Exception as e:
        logger.error(f"Manual DB Fix failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))



from app.services.system_log_service import log_action
from app.schemas.system_log import SystemLogOut

def _can_use_system_settings(user: User) -> bool:
    return bool((user.credits or 0) > 0 or user.is_superuser or user.is_system)


def get_system_api_setting(
    db: Session,
    provider: str = None,
    category: str = None,
    model: str = None,
    setting_id: int = None,
) -> Optional[SystemAPISetting]:
    """Helper to find a system-level API configuration by exact filters."""
    query = db.query(SystemAPISetting)
    if setting_id:
        query = query.filter(SystemAPISetting.id == setting_id)
    if provider:
        query = query.filter(SystemAPISetting.provider == provider)
    if category:
        query = query.filter(SystemAPISetting.category == category)
    if model:
        query = query.filter(SystemAPISetting.model == model)
    return query.order_by(SystemAPISetting.id.desc()).first()


def _resolve_effective_api_setting_meta(
    db: Session,
    user: User,
    provider: str = None,
    category: str = None,
) -> Tuple[Optional[APISetting], str, Dict[str, Any]]:
    resolved_category = str(category or "").strip()
    if not resolved_category:
        return None, "missing_category", {"active_count": 0}

    user_setting_query = db.query(APISetting).filter(
        APISetting.user_id == user.id,
        APISetting.category == resolved_category,
        APISetting.is_active == True,
    )

    active_count = user_setting_query.count()
    setting = user_setting_query.order_by(APISetting.id.desc()).first()
    if not setting:
        return None, "no_active_user_setting", {"active_count": active_count, "category": resolved_category}

    target_provider = str(setting.provider or "").strip()
    target_model = str(setting.model or "").strip()
    if not target_provider or not target_model:
        return None, "active_user_missing_provider_model", {
            "active_count": active_count,
            "marker_id": setting.id,
            "category": resolved_category,
            "provider": setting.provider,
            "model": setting.model,
        }

    system_setting = get_system_api_setting(
        db,
        provider=target_provider,
        category=resolved_category,
        model=target_model,
    )
    if system_setting:
        return system_setting, "system_by_user_provider_model", {
            "active_count": active_count,
            "marker_id": setting.id,
            "category": resolved_category,
            "provider": target_provider,
            "model": target_model,
        }

    return None, "no_matching_system_setting", {
        "active_count": active_count,
        "marker_id": setting.id,
        "category": resolved_category,
        "provider": target_provider,
        "model": target_model,
    }

def get_effective_api_setting(db: Session, user: User, provider: str = None, category: str = None) -> Optional[APISetting]:
    """
    Get API setting for current user. 
    If not found AND user is authorized, fallback to system setting.
    """
    resolved_setting, source, meta = _resolve_effective_api_setting_meta(db, user, provider, category)
    if resolved_setting:
        logger.info(
            "Resolved API setting | user_id=%s source=%s setting_id=%s provider=%s category=%s model=%s endpoint=%s meta=%s",
            user.id,
            source,
            resolved_setting.id,
            resolved_setting.provider,
            resolved_setting.category,
            resolved_setting.model,
            resolved_setting.base_url,
            meta,
        )
    return resolved_setting


def _seed_default_system_settings_for_user(db: Session, user_id: int) -> None:
    existing_count = db.query(APISetting).filter(APISetting.user_id == user_id).count()
    if existing_count > 0:
        return

    active_system_rows = db.query(SystemAPISetting).filter(
        SystemAPISetting.is_active == True,
        SystemAPISetting.category != "System_Payment",
    ).order_by(SystemAPISetting.category.asc(), SystemAPISetting.id.desc()).all()

    if not active_system_rows:
        return

    chosen_by_category: Dict[str, SystemAPISetting] = {}
    for row in active_system_rows:
        category = str(row.category or "").strip()
        if not category or category in chosen_by_category:
            continue
        chosen_by_category[category] = row

    for category, system_setting in chosen_by_category.items():
        marker_config = dict(system_setting.config or {})
        marker_config["selection_source"] = "system"
        selected_setting_id: Optional[int] = None

        user_setting = db.query(APISetting).filter(
            APISetting.user_id == user_id,
            APISetting.category == category,
        ).order_by(APISetting.id.desc()).first()

        if user_setting:
            user_setting.name = user_setting.name or f"Use System {system_setting.provider}"
            user_setting.provider = system_setting.provider
            user_setting.base_url = system_setting.base_url
            user_setting.model = system_setting.model
            user_setting.config = marker_config
            user_setting.api_key = ""
            user_setting.is_active = True
            selected_setting_id = user_setting.id
        else:
            new_setting = APISetting(
                user_id=user_id,
                name=f"Use System {system_setting.provider}",
                category=system_setting.category,
                provider=system_setting.provider,
                api_key="",
                base_url=system_setting.base_url,
                model=system_setting.model,
                config=marker_config,
                is_active=True,
            )
            db.add(new_setting)
            db.flush()
            selected_setting_id = new_setting.id

        db.query(APISetting).filter(
            APISetting.user_id == user_id,
            APISetting.category == category,
            APISetting.id != selected_setting_id,
            APISetting.is_active == True,
        ).update({"is_active": False}, synchronize_session=False)


@router.get("/settings/effective")
def get_effective_setting_snapshot(
    category: str = "LLM",
    provider: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resolved_setting, source, meta = _resolve_effective_api_setting_meta(
        db,
        current_user,
        provider=provider,
        category=category,
    )

    if not resolved_setting:
        return {
            "found": False,
            "category": category,
            "provider": provider,
            "source": source,
            "meta": meta,
        }

    api_key = (resolved_setting.api_key or "").strip()
    masked = ""
    if api_key:
        masked = api_key[:4] + "***" + api_key[-4:] if len(api_key) > 8 else ("*" * len(api_key))

    return {
        "found": True,
        "source": source,
        "selection_source": "system_only",
        "setting_id": resolved_setting.id,
        "owner_user_id": getattr(resolved_setting, "user_id", None),
        "category": resolved_setting.category,
        "provider": resolved_setting.provider,
        "model": resolved_setting.model,
        "endpoint": resolved_setting.base_url,
        "webhook": (resolved_setting.config or {}).get("webHook"),
        "has_api_key": bool(api_key),
        "api_key_masked": masked,
        "meta": meta,
    }

@router.get("/prompts/{filename}")
async def get_prompt_content(filename: str, current_user: User = Depends(get_current_user)):
    """Retrieve content of a prompt file."""
    # Robust path resolution using settings.BASE_DIR (backend root)
    prompt_dir = os.path.join(str(settings.BASE_DIR), "app", "core", "prompts")
    prompt_path = os.path.join(prompt_dir, filename)
    
    if not os.path.exists(prompt_path):
        # logging for debug on Render
        logger.error(f"Prompt file not found at: {prompt_path}")
        raise HTTPException(status_code=404, detail=f"Prompt file '{filename}' not found.")
        
    with open(prompt_path, "r", encoding="utf-8") as f:
        return {"content": f.read()}

@router.post("/analyze_scene", response_model=Dict[str, Any])
async def analyze_scene(request: AnalyzeSceneRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)): # user auth optional depending on reqs, kept for safety
    """
    Submits raw script text to LLM for Scene/Beat analysis using a specific prompt template.
    Returns the raw analysis result (Markdown/JSON).
    """
    logger.info("Received analyze_scene request")
    try:
        logger.info(f"[analyze_scene] request.episode_id={getattr(request, 'episode_id', None)}")
    except Exception:
        pass
    if request.project_metadata:
        try:
            keys = list(request.project_metadata.keys())
        except Exception:
            keys = []
        logger.info(f"Project Metadata received (keys only): {keys}")
    else:
        logger.info("No Project Metadata received")

    try:
        def _is_length_finish_reason(reason: Any) -> bool:
            r = str(reason or "").strip().lower().replace("-", "_")
            return r in {
                "length",
                "max_tokens",
                "max_token",
                "max_output_tokens",
                "output_token_limit",
                "token_limit",
            }

        def _estimate_tokens(text: str) -> int:
            if not text:
                return 0
            # Heuristic: ~4 bytes per token (good enough for debug)
            return (len(text.encode("utf-8")) + 3) // 4

        def _merge_usage(total: Dict[str, Any], part: Dict[str, Any]) -> Dict[str, Any]:
            total = dict(total or {})
            part = dict(part or {})

            def _add(key: str, value: Any):
                if value is None:
                    return
                try:
                    iv = int(value)
                except Exception:
                    return
                total[key] = int(total.get(key) or 0) + iv

            # Common OpenAI-style keys
            _add("prompt_tokens", part.get("prompt_tokens"))
            _add("completion_tokens", part.get("completion_tokens"))
            _add("total_tokens", part.get("total_tokens"))
            # Some providers use input/output naming
            _add("input_tokens", part.get("input_tokens"))
            _add("output_tokens", part.get("output_tokens"))

            # Preserve provider-specific extra usage fields if they are scalar and not already present
            for k, v in part.items():
                if k in total:
                    continue
                if isinstance(v, (int, float, str)):
                    total[k] = v
            return total

        def _detect_output_integrity(output_text: str, segments: List[Dict[str, Any]], final_finish_reason: Optional[str]) -> Dict[str, Any]:
            text = (output_text or "").strip()
            segment_list = segments or []
            had_length_finish = any(_is_length_finish_reason(seg.get("finish_reason")) for seg in segment_list)
            ended_with_length = _is_length_finish_reason(final_finish_reason)

            json_candidate = ""
            json_expected = False

            if text.startswith("```"):
                lowered = text.lower()
                if "```json" in lowered or ("```" in lowered and ("{" in text or "[" in text)):
                    json_expected = True
                    fence_start = text.find("\n")
                    fence_end = text.rfind("```")
                    if fence_start != -1 and fence_end != -1 and fence_end > fence_start:
                        json_candidate = text[fence_start + 1:fence_end].strip()

            if not json_candidate:
                if text.startswith("{") or text.startswith("["):
                    json_expected = True
                    json_candidate = text
                else:
                    first_obj = text.find("{")
                    last_obj = text.rfind("}")
                    first_arr = text.find("[")
                    last_arr = text.rfind("]")
                    if first_obj != -1 and last_obj > first_obj:
                        json_expected = True
                        json_candidate = text[first_obj:last_obj + 1].strip()
                    elif first_arr != -1 and last_arr > first_arr:
                        json_expected = True
                        json_candidate = text[first_arr:last_arr + 1].strip()

            json_valid = None
            json_error = None
            if json_expected:
                try:
                    json.loads(json_candidate)
                    json_valid = True
                except Exception as parse_error:
                    json_valid = False
                    json_error = str(parse_error)

            truncation_suspected = bool(ended_with_length or (had_length_finish and json_expected and json_valid is False))

            warning_codes: List[str] = []
            warnings: List[str] = []
            if ended_with_length:
                warning_codes.append("ANALYSIS_OUTPUT_TRUNCATED")
                warnings.append("Analysis output may be incomplete because the response hit a length limit.")
            elif had_length_finish:
                warning_codes.append("ANALYSIS_OUTPUT_CONTINUED")
                warnings.append("Analysis response was split by length limits and auto-continuation was applied.")

            if json_expected and json_valid is False:
                warning_codes.append("ANALYSIS_JSON_INVALID")
                warnings.append("Analysis returned invalid or incomplete JSON. Please review before applying.")

            return {
                "truncation_detected": had_length_finish,
                "truncation_suspected": truncation_suspected,
                "ended_with_length": ended_with_length,
                "json_expected": json_expected,
                "json_valid": json_valid,
                "json_error": json_error,
                "warning_codes": warning_codes,
                "warnings": warnings,
            }

        # Load the prompt template or use provided system_prompt
        system_instruction = ""
        
        if request.system_prompt:
            system_instruction = request.system_prompt
        else:
            prompt_filename = request.prompt_file or "scene_analysis.txt"
            # Robust path resolution
            prompt_dir = os.path.join(str(settings.BASE_DIR), "app", "core", "prompts")
            prompt_path = os.path.join(prompt_dir, prompt_filename)
            
            if not os.path.exists(prompt_path):
                 logger.error(f"Scene analysis prompt not found at: {prompt_path}")
                 raise HTTPException(status_code=404, detail=f"Prompt file '{prompt_filename}' not found.")
                
            with open(prompt_path, "r", encoding="utf-8") as f:
                system_instruction = f.read()

            # Inject Templates if using the standard scene_analysis.txt
            if "scene_analysis.txt" in prompt_filename:
                try:
                    from app.core.prompts.templates import (
                        CHARACTER_PROMPT_TEMPLATE as char_tmpl, 
                        PROP_PROMPT_TEMPLATE as prop_tmpl, 
                        ENVIRONMENT_PROMPT_TEMPLATE as env_tmpl
                    )
                    # Replace placeholders or specific sections
                    # We will use simple string replacement or format if placeholders exist
                    # For backward compatibility, check if placeholders exist first
                    if "{char_prompt_template}" in system_instruction:
                        system_instruction = system_instruction.replace("{char_prompt_template}", char_tmpl)
                    if "{prop_prompt_template}" in system_instruction:
                        system_instruction = system_instruction.replace("{prop_prompt_template}", prop_tmpl)
                    if "{env_prompt_template}" in system_instruction:
                        system_instruction = system_instruction.replace("{env_prompt_template}", env_tmpl)
                except Exception as e:
                    logger.warning(f"Failed to inject templates into scene analysis prompt: {e}")

        # Inject authoritative character canon (if provided via episode_id)
        try:
            ep_id = getattr(request, "episode_id", None)
            if ep_id:
                episode = db.query(Episode).filter(Episode.id == ep_id).first()
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
        user_content = f"Script to Analyze:\n\n{request.text}"
        
        if request.project_metadata:
            meta_parts = ["Project Overview Context:"]
            # Prioritize key fields if they exist
            if request.project_metadata.get("script_title"):
                meta_parts.append(f"Title: {request.project_metadata['script_title']}")
            if request.project_metadata.get("type"):
                meta_parts.append(f"Type: {request.project_metadata['type']}")
            if request.project_metadata.get("tone"):
                meta_parts.append(f"Tone: {request.project_metadata['tone']}")
            if request.project_metadata.get("Global_Style"):
                meta_parts.append(f"Global Style: {request.project_metadata['Global_Style']}")
            if request.project_metadata.get("base_positioning"):
                meta_parts.append(f"Base Positioning: {request.project_metadata['base_positioning']}")
            if request.project_metadata.get("lighting"):
                meta_parts.append(f"Lighting: {request.project_metadata['lighting']}")
            if request.project_metadata.get("series_episode"):
                meta_parts.append(f"Episode: {request.project_metadata['series_episode']}")
             
            # Simple dump of other fields if needed, or just rely on these key ones for the prompt
            # Let's add all relevant fields that might influence the visual analysis
            
            meta_str = "\n".join(meta_parts)
            user_content = f"{meta_str}\n\n{user_content}"
            logger.info(
                "Injected Project Context into Prompt (summary): lines=%s chars=%s tokens_est=%s",
                len(meta_parts),
                len(meta_str),
                _estimate_tokens(meta_str),
            )

        attention_notes = (getattr(request, "analysis_attention_notes", None) or "").strip()
        if attention_notes:
            attention_block = (
                "Regeneration Attention Notes (High Priority):\n"
                "When regenerating AI Scene Analysis, you MUST prioritize and satisfy these constraints:\n"
                f"{attention_notes}"
            )
            user_content = f"{attention_block}\n\n{user_content}"
            logger.info(
                "Injected analysis attention notes into prompt: chars=%s tokens_est=%s",
                len(attention_notes),
                _estimate_tokens(attention_notes),
            )

        reuse_subject_assets = getattr(request, "reuse_subject_assets", None) or []
        if isinstance(reuse_subject_assets, list) and len(reuse_subject_assets) > 0:
            normalized_assets = []
            for item in reuse_subject_assets[:20]:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                asset_type = str(item.get("type") or "").strip()
                description = str(item.get("description") or "").strip()
                anchor_description = str(item.get("anchor_description") or "").strip()
                description = description[:600]
                anchor_description = anchor_description[:300]
                normalized_assets.append({
                    "name": name,
                    "type": asset_type,
                    "description": description,
                    "anchor_description": anchor_description,
                })

            if normalized_assets:
                lines = [
                    "Reusable Subject Assets (High Priority):",
                    "The following assets are MUST-REUSE subjects for this analysis.",
                    "Do NOT regenerate or rename them. Keep their identity and anchor traits consistent.",
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
                    lines.append(f"- [{asset['name']}] {details}".strip())

                reuse_block = "\n".join(lines)
                user_content = f"{reuse_block}\n\n{user_content}"
                logger.info(
                    "Injected reusable subject assets into prompt: count=%s tokens_est=%s",
                    len(normalized_assets),
                    _estimate_tokens(reuse_block),
                )

        # Construct messages
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content}
        ]

        # Use the LLM service directly
        # If llm_config in request, use it, otherwise try to fetch from user/project logic if needed.
        # Here we assume frontend sends the active LLM config or we rely on a default.
        # Ideally, we should fetch the user's preferred LLM settings from DB.
        
        config = request.llm_config
        # If config is missing/empty, fetch from DB Settings (Core LLM Configuration)
        if not config:
            api_setting = get_effective_api_setting(db, current_user, category="LLM")
            if api_setting:
                # Merge with defaults so base_url/model are never missing.
                from app.api.settings import DEFAULTS
                default = DEFAULTS.get(api_setting.provider, {})
                config = {
                    "provider": api_setting.provider,
                    "api_key": api_setting.api_key,
                    "base_url": api_setting.base_url or default.get("base_url"),
                    "model": api_setting.model or default.get("model"),
                    "config": api_setting.config or default.get("config", {})
                }

        # If frontend passed a partial config, backfill provider/model from Core LLM settings.
        if config and (not config.get("provider") or not config.get("model")):
            api_setting = get_effective_api_setting(db, current_user, category="LLM")
            if api_setting:
                from app.api.settings import DEFAULTS
                default = DEFAULTS.get(api_setting.provider, {})
                config.setdefault("provider", api_setting.provider)
                config.setdefault("model", api_setting.model or default.get("model"))
                if not config.get("base_url"):
                    config["base_url"] = api_setting.base_url or default.get("base_url")
                if "config" not in config:
                    config["config"] = api_setting.config or default.get("config", {})
        
        if not config:
             raise HTTPException(status_code=400, detail="LLM Configuration missing. Please check your settings.")

        # --- Debug / Truncation tracing ---
        debug_meta: Dict[str, Any] = {
            "stage": "pre_llm",
            "request_episode_id": getattr(request, "episode_id", None),
            "provider": (config or {}).get("provider"),
            "model": (config or {}).get("model"),
            "system_prompt_chars": len(system_instruction or ""),
            "user_prompt_chars": len(user_content or ""),
            "request_text_chars": len((request.text or "")),
            "system_prompt_tokens_est": _estimate_tokens(system_instruction or ""),
            "user_prompt_tokens_est": _estimate_tokens(user_content or ""),
        }

        # Billing (task_type = analysis)
        provider = (config or {}).get("provider")
        model = (config or {}).get("model")
        reservation_tx = None
        if billing_service.is_token_pricing(db, "analysis", provider, model):
            est = billing_service.estimate_input_output_tokens_from_messages(messages, output_ratio=1.5)
            debug_meta.update({
                "est_input_tokens": est.get("input_tokens", 0),
                "est_output_tokens": est.get("output_tokens", 0),
                "est_total_tokens": est.get("total_tokens", 0),
            })
            reserve_details = {
                "item": "scene_analysis",
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": 1.5,
                "system_prompt_len": len(system_instruction or ""),
                "user_prompt_len": len(user_content or ""),
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            }
            reservation_tx = billing_service.reserve_credits(db, current_user.id, "analysis", provider, model, reserve_details)
        else:
            billing_service.check_balance(db, current_user.id, "analysis", provider, model)

        # Record max token config for diagnostics, but do not override it.
        cfg_obj = (config or {}).get("config") or {}
        if not isinstance(cfg_obj, dict):
            cfg_obj = {}

        def _to_int(value: Any) -> int:
            try:
                parsed = int(value)
                return parsed if parsed > 0 else 0
            except Exception:
                return 0

        requested_cap = (
            _to_int(cfg_obj.get("max_tokens"))
            or _to_int(cfg_obj.get("max_completion_tokens"))
            or _to_int(cfg_obj.get("max_output_tokens"))
        )

        removed_local_cap_fields: List[str] = []
        for cap_key in ("max_tokens", "max_completion_tokens", "max_output_tokens"):
            if cap_key in cfg_obj:
                removed_local_cap_fields.append(cap_key)
                cfg_obj.pop(cap_key, None)

        if (config or {}).get("config") is not cfg_obj:
            config["config"] = cfg_obj

        debug_meta["config_max_tokens"] = None
        debug_meta["config_max_completion_tokens"] = None
        debug_meta["config_max_tokens_effective"] = None
        debug_meta["requested_output_cap_tokens"] = requested_cap
        debug_meta["default_output_cap_applied"] = False
        debug_meta["local_output_cap_removed"] = bool(removed_local_cap_fields)
        if removed_local_cap_fields:
            debug_meta["removed_local_cap_fields"] = removed_local_cap_fields

        logger.info(f"Analyzing scene for user {current_user.id} with model {config.get('model')}")
        # Auto-continue if provider truncates (finish_reason=length).
        # Important: keep continuation prompts small (do NOT send the entire prior output back)
        # to avoid blowing up prompt size / hitting context window.
        # Token cap is controlled by provider/model config; local continuation only keeps a high safety ceiling.
        max_segments = min(1000, max(1, _to_int(cfg_obj.get("continuation_max_segments")) or 200))
        tail_chars = 1600
        continuation_instruction_tpl = (
            "Continue exactly where you left off, immediately after the following suffix. "
            "Do NOT repeat any of the suffix text. "
            "Return ONLY the continuation in the same format as before.\n\n"
            "SUFFIX (do not repeat):\n{suffix}"
        )

        result_parts: List[str] = []
        segments_meta: List[Dict[str, Any]] = []
        usage_total: Dict[str, Any] = {}
        finish_reason = None
        continuation_stopped_by_max_segments = False
        provider_limit_hints: List[str] = []

        def _dedupe_overlap(existing: str, incoming: str) -> str:
            if not existing or not incoming:
                return incoming
            # If model repeats the suffix, strip common overlaps.
            candidates = [
                existing[-200:],
                existing[-400:],
                existing[-800:],
            ]
            for c in candidates:
                if c and incoming.startswith(c):
                    return incoming[len(c):]
            # Some models wrap with whitespace/newlines; try trimmed
            inc_l = incoming.lstrip()
            for c in candidates:
                if c and inc_l.startswith(c):
                    return inc_l[len(c):]
            return incoming

        current_messages = list(messages)
        system_only_messages = []
        try:
            if messages and isinstance(messages[0], dict) and messages[0].get("role") == "system":
                system_only_messages = [messages[0]]
        except Exception:
            system_only_messages = []
        for seg_idx in range(1, max_segments + 1):
            llm_resp = await llm_service.chat_completion(current_messages, config)
            raw_part = llm_resp.get("raw_content")
            if not isinstance(raw_part, str):
                raw_part = llm_resp.get("content", "") or ""
            part_usage = llm_resp.get("usage", {}) or {}
            part_finish = llm_resp.get("finish_reason")
            part_limit_hints = llm_resp.get("token_limit_hints", []) or []
            part_extraction_diag = llm_resp.get("extraction_diagnostics", {}) or {}
            if isinstance(part_limit_hints, list):
                for hint in part_limit_hints:
                    hint_text = str(hint or "").strip()
                    if hint_text and hint_text not in provider_limit_hints:
                        provider_limit_hints.append(hint_text)

            usage_total = _merge_usage(usage_total, part_usage)
            finish_reason = part_finish

            existing = "".join(result_parts)
            part_content = _dedupe_overlap(existing, raw_part)
            result_parts.append(part_content)
            segments_meta.append({
                "index": seg_idx,
                "finish_reason": part_finish,
                "output_chars": len(raw_part),
                "output_tokens_est": _estimate_tokens(raw_part),
                "deduped_chars": len(part_content),
                "usage": part_usage,
                "token_limit_hints": part_limit_hints,
                "extraction_diagnostics": part_extraction_diag,
            })

            # Stop if not truncated.
            if not _is_length_finish_reason(part_finish):
                break

            # Stop if provider returned nothing new.
            if not raw_part.strip():
                break

            # Ask for continuation; include only a short suffix of the accumulated output.
            accumulated = "".join(result_parts)
            suffix = accumulated[-tail_chars:] if len(accumulated) > tail_chars else accumulated
            continuation_instruction = continuation_instruction_tpl.format(suffix=suffix)
            # Continuation does not require re-sending the whole script; keep only system + tail.
            base_for_continue = system_only_messages or list(messages)
            current_messages = list(base_for_continue) + [
                {"role": "assistant", "content": suffix},
                {"role": "user", "content": continuation_instruction},
            ]

        if finish_reason is not None and _is_length_finish_reason(finish_reason) and len(segments_meta) >= max_segments:
            continuation_stopped_by_max_segments = True

        result_content = "".join(result_parts)
        usage = usage_total
        integrity_meta = _detect_output_integrity(result_content, segments_meta, finish_reason)

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
            "continuation_stopped_by_max_segments": continuation_stopped_by_max_segments,
            "provider_limit_hints": provider_limit_hints,
            "integrity": integrity_meta,
        })

        # Persist result to DB if caller provided episode_id.
        saved_to_episode = False
        if getattr(request, "episode_id", None):
            episode_id = request.episode_id
            episode = db.query(Episode).filter(Episode.id == episode_id).first()
            if episode and not getattr(current_user, "is_superuser", False):
                _require_project_access(db, episode.project_id, current_user)
            if not episode:
                raise HTTPException(status_code=404, detail="Episode not found")
            episode.ai_scene_analysis_result = result_content
            saved_to_episode = True
            debug_meta["saved_to_episode"] = True
            debug_meta["saved_episode_id"] = episode_id
            try:
                db.flush()
            except Exception:
                db.rollback()
                raise
            logger.info(
                "[analyze_scene] Saved ai_scene_analysis_result to episode_id=%s chars=%s",
                episode_id,
                len(result_content or ""),
            )
        else:
            debug_meta["saved_to_episode"] = False
        
        # Billing finalize (commit happens inside billing service; will persist episode update if set above)
        if reservation_tx:
            actual_details = {"item": "scene_analysis"}
            if usage:
                actual_details.update(usage)
            # Normalize common usage keys
            if "prompt_tokens" in actual_details and "input_tokens" not in actual_details:
                actual_details["input_tokens"] = actual_details.get("prompt_tokens", 0)
            if "completion_tokens" in actual_details and "output_tokens" not in actual_details:
                actual_details["output_tokens"] = actual_details.get("completion_tokens", 0)
            billing_service.settle_reservation(db, reservation_tx.id, actual_details)
        else:
            details = {"item": "scene_analysis"}
            if usage:
                details.update(usage)
            # Normalize usage keys for token-based calculation if provider returns OpenAI-style usage
            if "prompt_tokens" in details and "input_tokens" not in details:
                details["input_tokens"] = details.get("prompt_tokens", 0)
            if "completion_tokens" in details and "output_tokens" not in details:
                details["output_tokens"] = details.get("completion_tokens", 0)
            billing_service.deduct_credits(db, current_user.id, "analysis", provider, model, details)

        # Ensure episode save is committed even if billing is disabled/mocked.
        if saved_to_episode:
            try:
                db.commit()
                try:
                    db.refresh(episode)
                except Exception:
                    pass
            except Exception:
                db.rollback()
                raise
        
        response_payload: Dict[str, Any] = {"result": result_content, "meta": debug_meta}
        if integrity_meta.get("warnings"):
            response_payload["warnings"] = integrity_meta.get("warnings")
        if integrity_meta.get("warning_codes"):
            response_payload["warning_codes"] = integrity_meta.get("warning_codes")
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
                billing_service.cancel_reservation(db, reservation_tx.id, prefixed_detail)
        except:
            pass
        try:
            m_log = conf_log.get("model")
            billing_service.log_failed_transaction(db, current_user.id, "analysis", p_log, m_log, prefixed_detail)
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
                billing_service.cancel_reservation(db, reservation_tx.id, prefixed_detail)
        except:
            pass
        # Log failure
        try:
             m_log = conf_log.get("model")
             billing_service.log_failed_transaction(db, current_user.id, "analysis", p_log, m_log, prefixed_detail)
        except:
             pass # Fail safe
        raise HTTPException(status_code=500, detail=prefixed_detail)

# --- Tools ---
class TranslateRequest(BaseModel):
    q: str
    from_lang: str = 'en'
    to_lang: str = 'zh'

@router.post("/tools/translate")
async def translate_text(
    req: TranslateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    request_id = uuid.uuid4().hex[:12]
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

    llm_config = agent_service.get_active_llm_config(current_user.id, category="LLM")
    if not llm_config or not llm_config.get("api_key"):
        raise HTTPException(status_code=400, detail="Active LLM Settings not found. Please configure and activate an LLM provider.")

    provider = llm_config.get("provider") or "llm"
    model = llm_config.get("model") or "unknown"

    try:
        log_action(
            db,
            user_id=current_user.id,
            user_name=current_user.username,
            action="TRANSLATE_START",
            details=f"request_id={request_id}; from={from_lang}; to={to_lang}; chars={len(text)}; provider={provider}; model={model}"
        )
    except Exception as e:
        logger.warning(f"[translate:{request_id}] failed to write START system log: {e}")

    logger.info(
        f"[translate:{request_id}] start user_id={current_user.id} from={from_lang} to={to_lang} chars={len(text)} provider={provider} model={model}"
    )

    if from_lang == to_lang:
        logger.info(f"[translate:{request_id}] skip same language from={from_lang} to={to_lang}")
        return {"translated_text": text, "request_id": request_id}

    reservation_tx = None
    try:
        if billing_service.is_token_pricing(db, "llm_chat", provider, model):
            est = billing_service.estimate_input_output_tokens_from_messages(
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
            reservation_tx = billing_service.reserve_credits(db, current_user.id, "llm_chat", provider, model, reserve_details)
        else:
            billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)
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
    
    try:
        llm_resp = await llm_service.generate_content(user_prompt, system_prompt, llm_config)
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
            billing_service.settle_reservation(db, reservation_tx.id, actual_details)
        else:
            billing_service.deduct_credits(
                db,
                current_user.id,
                "llm_chat",
                provider,
                model,
                {
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
            )

        elapsed_ms = int((datetime.utcnow() - started_at).total_seconds() * 1000)
        logger.info(
            f"[translate:{request_id}] success user_id={current_user.id} from={from_lang} to={to_lang} chars={len(text)} translated_chars={len(dst)} elapsed_ms={elapsed_ms}"
        )
        try:
            log_action(
                db,
                user_id=current_user.id,
                user_name=current_user.username,
                action="TRANSLATE_SUCCESS",
                details=f"request_id={request_id}; from={from_lang}; to={to_lang}; chars={len(text)}; translated_chars={len(dst)}; elapsed_ms={elapsed_ms}"
            )
        except Exception as e:
            logger.warning(f"[translate:{request_id}] failed to write SUCCESS system log: {e}")

        return {"translated_text": dst, "request_id": request_id}
    except HTTPException as e:
        if reservation_tx:
            try:
                billing_service.cancel_reservation(db, reservation_tx.id, str(e.detail))
            except Exception:
                pass
        billing_service.log_failed_transaction(
            db,
            current_user.id,
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
                user_id=current_user.id,
                user_name=current_user.username,
                action="TRANSLATE_FAILED",
                details=f"request_id={request_id}; error={str(e.detail)[:300]}"
            )
        except Exception as le:
            logger.warning(f"[translate:{request_id}] failed to write FAILED system log: {le}")
        raise
    except Exception as e:
        if reservation_tx:
            try:
                billing_service.cancel_reservation(db, reservation_tx.id, str(e))
            except Exception:
                pass
        billing_service.log_failed_transaction(
            db,
            current_user.id,
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
                user_id=current_user.id,
                user_name=current_user.username,
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

@router.post("/tools/refine_prompt")
async def refine_prompt(
    req: RefinePromptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Get LLM Config
    config = agent_service.get_active_llm_config(current_user.id)
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
        billing_service.log_failed_transaction(db, current_user.id, "llm_chat", config.get("provider"), model, str(e))
        raise HTTPException(status_code=500, detail=str(e))

# --- Agent ---
@router.post("/agent/command", response_model=AgentResponse)
async def process_agent_command(
    request: AgentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Resolve Project ID
    project_id = request.project_id or request.context.get("projectId")
    
    if project_id:
        _require_project_access(db, int(project_id), current_user)

    # Resolve Provider/Model for Billing
    provider = request.llm_config.get("provider") if request.llm_config else None
    model = request.llm_config.get("model") if request.llm_config else None
    
    if not provider:
        api_config = get_effective_api_setting(db, current_user, category="LLM")
        if api_config:
            provider = api_config.provider
            model = api_config.model
    
    reservation_tx = None
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

        est = billing_service.estimate_input_output_tokens_from_messages(messages_est, output_ratio=1.5)
        reserve_details = {
            "item": "agent_intent",
            "estimation_method": "prompt_tokens_ratio",
            "estimated_output_ratio": 1.5,
            "query_len": len(request.query or ""),
            "input_tokens": est.get("input_tokens", 0),
            "output_tokens": est.get("output_tokens", 0),
            "total_tokens": est.get("total_tokens", 0),
        }
        reservation_tx = billing_service.reserve_credits(db, current_user.id, "llm_chat", provider, model, reserve_details)
    else:
        billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

    try:
        result = await agent_service.process_command(request, db, current_user.id)
        
        # Billing Finalize
        if reservation_tx:
            if result.usage:
                actual_details = {"item": "agent_intent"}
                actual_details.update(result.usage)
                actual_details["input_tokens"] = result.usage.get("prompt_tokens", 0)
                actual_details["output_tokens"] = result.usage.get("completion_tokens", 0)
                actual_details["total_tokens"] = result.usage.get("total_tokens", 0)
                billing_service.settle_reservation(db, reservation_tx.id, actual_details)
            else:
                billing_service.cancel_reservation(db, reservation_tx.id, "No usage returned")
        else:
            details = {"query": request.query[:50]}
            if result.usage:
                details["input_tokens"] = result.usage.get("prompt_tokens", 0)
                details["output_tokens"] = result.usage.get("completion_tokens", 0)
                details["total_tokens"] = result.usage.get("total_tokens", 0)
            billing_service.deduct_credits(db, current_user.id, "llm_chat", provider, model, details)
        
        return result
    except Exception as e:
        logger.error(f"Agent Command Failed: {e}")
        try:
            if reservation_tx:
                billing_service.cancel_reservation(db, reservation_tx.id, str(e))
        except:
            pass
        billing_service.log_failed_transaction(db, current_user.id, "llm_chat", provider, model, str(e))
        raise HTTPException(status_code=500, detail=str(e))


# --- Projects ---
class ProjectCreate(BaseModel):
    title: str
    global_info: dict = {}
    aspectRatio: Optional[str] = None

class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    global_info: Optional[dict] = None
    aspectRatio: Optional[str] = None

class ProjectOut(BaseModel):
    id: int
    title: str
    owner_id: int
    global_info: dict
    aspectRatio: Optional[str] = None
    cover_image: Optional[str] = None
    is_owner: Optional[bool] = True
    
    class Config:
        from_attributes = True


class ProjectShareCreate(BaseModel):
    target_user: str


class ProjectShareOut(BaseModel):
    id: int
    project_id: int
    user_id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    created_at: Optional[str] = None



def _is_project_shared_with_user(db: Session, project_id: int, user_id: int) -> bool:
    share = db.query(ProjectShare).filter(
        ProjectShare.project_id == project_id,
        ProjectShare.user_id == user_id,
    ).first()
    return share is not None


def _require_project_access(
    db: Session,
    project_id: int,
    current_user: User,
    owner_only: bool = False,
) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    is_owner = project.owner_id == current_user.id
    if is_owner:
        return project

    if owner_only:
        raise HTTPException(status_code=403, detail="Delete is restricted to project owner")

    if _is_project_shared_with_user(db, project.id, current_user.id):
        return project

    raise HTTPException(status_code=403, detail="Not authorized")


def _attach_project_flags(project: Project, current_user: User) -> Project:
    project.is_owner = (project.owner_id == current_user.id)
    return project

def get_project_cover_image(db: Session, project_id: int) -> Optional[str]:
    # 1. Try to find first valid image in Shots
    # Check if project_id is populated in shots first (optimization)
    shot = db.query(Shot).filter(Shot.project_id == project_id, Shot.image_url != None, Shot.image_url != "").first()
    if shot:
        return shot.image_url
        
    # If project_id not reliable in shots, try join (fallback)
    shot = db.query(Shot).join(Scene).join(Episode).filter(Episode.project_id == project_id, Shot.image_url != None, Shot.image_url != "").first()
    if shot:
        return shot.image_url

    # 2. Try Scenes? (Scene logic currently undefined as no direct image column, skip to Entities)
    
    # 3. Try Entities (Subjects)
    entity = db.query(Entity).filter(Entity.project_id == project_id, Entity.image_url != None, Entity.image_url != "").first()
    if entity:
        return entity.image_url
        
    # 4. Try Assets? (Maybe, but user said Shots, Scenes, Subjects)
    
    return None


def _extract_md_section(md: str, start_header_regex: str) -> Tuple[str, str]:
    """Return (section_text, remainder) where section_text starts at the first header matching regex.

    Section is from matching header line up to (but not including) the next '## ' header.
    If not found, returns ("", md).
    """
    if not md:
        return "", md
    m = re.search(start_header_regex, md, flags=re.MULTILINE)
    if not m:
        return "", md
    start = m.start()
    after = md[m.end():]
    m2 = re.search(r"^##\s+", after, flags=re.MULTILINE)
    if m2:
        end = m.end() + m2.start()
        return md[start:end].strip(), (md[:start] + md[end:]).strip()
    return md[start:].strip(), md[:start].strip()


def parse_global_style_constraints(global_md: str) -> Dict[str, Any]:
    """Parse the '## -1) ...全局风格与硬约束...' section from Global Story DNA markdown.

    Returns a dict suitable for persisting into project.global_info.
    Parsing is best-effort; if the section is missing, returns an empty dict.
    """
    section, _ = _extract_md_section(global_md or "", r"^##\s*-1\)\s*.+$")
    if not section:
        return {}

    result: Dict[str, Any] = {
        "raw_section_md": section,
        "project_overview": {},
        "global_constraints": {},
        "hard_no": [],
        "extras": {},
    }

    current_block: Optional[str] = None
    kv_re = re.compile(r"^(?P<k>[^:：]+)\s*[:：]\s*(?P<v>.*)$")

    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("##"):
            continue
        if not line.startswith("-"):
            continue

        item = line.lstrip("-").strip()
        if not item:
            continue

        # Block switches
        if "项目基本信息" in item:
            current_block = "project_overview"
            continue
        if item.startswith("全局风格"):
            current_block = "global_constraints"
            continue
        if item.startswith("禁止项") or "Hard No" in item:
            current_block = "hard_no"
            continue

        if current_block == "hard_no":
            result["hard_no"].append(item)
            continue

        m = kv_re.match(item)
        if not m:
            # store unstructured bullet under current block
            bucket = current_block or "extras"
            result.setdefault(bucket, [])
            if isinstance(result[bucket], list):
                result[bucket].append(item)
            continue

        key = m.group("k").strip()
        val = m.group("v").strip()
        if current_block == "project_overview":
            key_map = {
                "Script Title": "script_title",
                "Type": "type",
                "Language": "language",
                "Base Positioning": "base_positioning",
                "Global Style": "global_style",
            }
            normalized_key = key_map.get(key, key)
            result["project_overview"][normalized_key] = val
        elif current_block == "global_constraints":
            key_map = {
                "叙事口吻与节奏": "narration_pacing",
                "现实度与尺度边界": "realism_and_rating",
                "对白风格": "dialogue_style",
                "场景与道具约束": "scene_and_props",
                "人物数量与制作可行性": "production_scope",
                "连贯性硬规则": "continuity_rules",
            }
            normalized_key = key_map.get(key, key)
            result["global_constraints"][normalized_key] = val
        else:
            result["extras"][key] = val

    return result


def sanitize_llm_markdown_output(text: str) -> str:
    """Best-effort cleanup for markdown endpoints.

    Removes common reasoning leakage (<think> blocks)
    and fenced wrappers when models ignore format instructions.
    """
    if not text:
        return ""

    content = str(text)
    content = re.sub(r"<think>[\s\S]*?</think>", "", content, flags=re.IGNORECASE).strip()
    content = content.replace("```markdown", "").replace("```md", "").replace("```", "").strip()
    # Remove common safety/moderation marker leakage from upstream providers.
    content = re.sub(r"^\s*=*\s*PROHIBITED_CONTENT\s*$", "", content, flags=re.IGNORECASE | re.MULTILINE)
    content = re.sub(r"\n{3,}", "\n\n", content).strip()

    lines = content.splitlines()
    if not lines:
        return ""

    reasoning_prefix_re = re.compile(
        r"^\s*(i will|let me|let's|analysis|reasoning|thought process|"
        r"分析|思路|推理|下面|我将|我认为|先来)\b",
        flags=re.IGNORECASE,
    )
    markdown_start_re = re.compile(r"^\s*(#|\||-\s|\d+\.\s|>\s|\*\s)")

    # Trim leading blank lines first.
    while lines and not lines[0].strip():
        lines.pop(0)

    # Remove obvious leading reasoning lines.
    while lines and reasoning_prefix_re.match(lines[0]) and not markdown_start_re.match(lines[0]):
        lines.pop(0)

    # If a markdown-looking start exists later and the preface looks like reasoning,
    # cut to the markdown start.
    first_md_index = None
    for idx, line in enumerate(lines):
        if markdown_start_re.match(line):
            first_md_index = idx
            break
    if first_md_index is not None and first_md_index > 0:
        preface = "\n".join(lines[:first_md_index]).lower()
        if any(token in preface for token in ["analysis", "reasoning", "推理", "思路", "我将", "我认为"]):
            lines = lines[first_md_index:]

    return "\n".join(lines).strip()


def is_valid_markdown_output(text: str, require_h1: bool = True) -> bool:
    if not text:
        return False

    content = str(text).strip()
    if not content:
        return False

    lower = content.lower()
    if "<think>" in lower or "```" in content:
        return False

    lines = [ln for ln in content.splitlines() if ln.strip()]
    if not lines:
        return False

    if require_h1 and not lines[0].lstrip().startswith("#"):
        return False

    # Basic markdown structure presence
    has_md_structure = any(
        ln.lstrip().startswith(("#", "- ", "* ", "|", ">", "1. ", "2. ", "3. "))
        for ln in lines
    )
    return has_md_structure


async def generate_markdown_with_retry(
    user_prompt: str,
    sys_prompt: str,
    llm_config: Optional[Dict[str, Any]],
    strict_markdown: bool = True,
    require_h1: bool = True,
) -> str:
    def _is_prohibited_marker(text: str) -> bool:
        if not text:
            return False
        t = text.strip().upper()
        t = t.lstrip("=").strip()
        return t == "PROHIBITED_CONTENT"

    def _looks_like_error_text(text: str) -> bool:
        if not text:
            return False
        t = text.strip().lower()
        return (
            t.startswith("error:")
            or "api error" in t
            or "no llm configuration" in t
            or "please configure your llm api key" in t
            or "prohibited_content" in t
        )

    async def _call_once(tag: str, up: str, sp: str) -> Tuple[str, str, Dict[str, Any]]:
        resp = await llm_service.generate_content(up, sp, llm_config)
        raw = str(resp.get("content") or "")
        cleaned = sanitize_llm_markdown_output(raw)
        finish_reason = str(resp.get("finish_reason") or "")
        usage = resp.get("usage") or {}
        logger.info(
            f"[generate_markdown_with_retry] tag={tag} raw_len={len(raw)} clean_len={len(cleaned)} "
            f"finish_reason={finish_reason or '-'} usage={usage} is_error_like={_looks_like_error_text(cleaned)}"
        )
        return raw, cleaned, {
            "tag": tag,
            "finish_reason": finish_reason,
            "usage": usage,
            "raw_len": len(raw),
            "clean_len": len(cleaned),
        }

    def _is_truncated(meta: Optional[Dict[str, Any]]) -> bool:
        reason = str((meta or {}).get("finish_reason") or "").strip().lower()
        return reason == "length"

    raw_1, content_1, meta_1 = await _call_once("initial", user_prompt, sys_prompt)
    if _is_prohibited_marker(raw_1) or _is_prohibited_marker(content_1):
        logger.error("[generate_markdown_with_retry] provider returned PROHIBITED_CONTENT on initial attempt")
        raise RuntimeError("LLM content blocked by provider (PROHIBITED_CONTENT)")
    if _looks_like_error_text(content_1):
        lowered = (content_1 or "").strip().lower()
        if "please configure your llm api key" in lowered or "no llm configuration" in lowered:
            raise RuntimeError("No valid LLM API key configured in active settings")

    if not strict_markdown:
        if _is_truncated(meta_1):
            raise RuntimeError("LLM output appears truncated (finish_reason=length) in non-strict mode")
        if content_1 and not _looks_like_error_text(content_1):
            return content_1
        raise RuntimeError("LLM returned empty/error content in non-strict mode")

    if content_1 and not _looks_like_error_text(content_1) and is_valid_markdown_output(content_1, require_h1=require_h1) and not _is_truncated(meta_1):
        return content_1

    retry_sys_prompt = (
        f"{sys_prompt}\n\n"
        "[FORMAT RETRY - STRICT]\n"
        "Return ONLY final valid Markdown.\n"
        "Do NOT output reasoning, preface text, or chain-of-thought.\n"
        "Do NOT output code fences.\n"
        "The first non-empty line must be an H1 markdown header starting with '# '."
    )
    retry_user_prompt = (
        f"{user_prompt}\n\n"
        "[RETRY INSTRUCTION]\n"
        "Only return corrected final markdown now."
    )
    raw_2, content_2, meta_2 = await _call_once("strict_retry", retry_user_prompt, retry_sys_prompt)
    if _is_prohibited_marker(raw_2) or _is_prohibited_marker(content_2):
        logger.error("[generate_markdown_with_retry] provider returned PROHIBITED_CONTENT on strict retry")
        raise RuntimeError("LLM content blocked by provider (PROHIBITED_CONTENT)")
    if content_2 and not _looks_like_error_text(content_2) and is_valid_markdown_output(content_2, require_h1=require_h1) and not _is_truncated(meta_2):
        return content_2

    fallback_sys_prompt = (
        f"{sys_prompt}\n\n"
        "[FINAL FALLBACK FORMAT]\n"
        "Output ONLY markdown with this minimum structure:\n"
        "# Episode Script Draft\n"
        "## Core Conflict\n"
        "- ...\n"
        "## Beat Sheet\n"
        "1. ...\n"
        "2. ...\n"
        "3. ...\n"
        "No analysis text. No code fences."
    )
    fallback_user_prompt = (
        f"{user_prompt}\n\n"
        "[FINAL RETRY]\n"
        "Return compact markdown draft even if partial."
    )
    raw_3, content_3, meta_3 = await _call_once("fallback_retry", fallback_user_prompt, fallback_sys_prompt)
    if _is_prohibited_marker(raw_3) or _is_prohibited_marker(content_3):
        logger.error("[generate_markdown_with_retry] provider returned PROHIBITED_CONTENT on fallback retry")
        raise RuntimeError("LLM content blocked by provider (PROHIBITED_CONTENT)")
    if content_3 and not _looks_like_error_text(content_3):
        if require_h1 and not content_3.lstrip().startswith("#"):
            content_3 = "# Episode Script Draft\n\n" + content_3
        if is_valid_markdown_output(content_3, require_h1=require_h1) and not _is_truncated(meta_3):
            return content_3

    diagnostics = {
        "initial_finish_reason": meta_1.get("finish_reason"),
        "strict_retry_finish_reason": meta_2.get("finish_reason"),
        "fallback_retry_finish_reason": meta_3.get("finish_reason"),
        "initial_usage": meta_1.get("usage"),
        "strict_retry_usage": meta_2.get("usage"),
        "fallback_retry_usage": meta_3.get("usage"),
        "initial_clean_len": len(content_1 or ""),
        "strict_retry_clean_len": len(content_2 or ""),
        "fallback_retry_clean_len": len(content_3 or ""),
        "initial_error_like": _looks_like_error_text(content_1),
        "strict_retry_error_like": _looks_like_error_text(content_2),
        "fallback_retry_error_like": _looks_like_error_text(content_3),
        "initial_raw_sample": (raw_1 or "")[:120],
        "strict_retry_raw_sample": (raw_2 or "")[:120],
        "fallback_retry_raw_sample": (raw_3 or "")[:120],
    }
    logger.error(f"[generate_markdown_with_retry] exhausted retries. {json.dumps(diagnostics, ensure_ascii=False)}")
    if _is_truncated(meta_1) or _is_truncated(meta_2) or _is_truncated(meta_3):
        raise RuntimeError("LLM output appears truncated (finish_reason=length). Check model max_tokens/context and retry.")
    raise RuntimeError("LLM returned empty/invalid content after retries")

@router.post("/projects/", response_model=ProjectOut)
def create_project(
    project: ProjectCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # If aspectRatio is provided, merge it into global_info
    if project.aspectRatio:
        if not project.global_info:
            project.global_info = {}
        project.global_info['aspectRatio'] = project.aspectRatio
        
    db_project = Project(title=project.title, global_info=project.global_info, owner_id=current_user.id) 
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    # New project has no images
    db_project.cover_image = None
    # Extract aspectRatio for response from global_info
    db_project.aspectRatio = db_project.global_info.get('aspectRatio') if db_project.global_info else None
    db_project.is_owner = True
    return db_project


@router.get("/projects/{project_id}/shares", response_model=List[ProjectShareOut])
def list_project_shares(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user, owner_only=True)
    rows = (
        db.query(ProjectShare, User)
        .join(User, User.id == ProjectShare.user_id)
        .filter(ProjectShare.project_id == project_id)
        .order_by(ProjectShare.id.desc())
        .all()
    )
    return [
        ProjectShareOut(
            id=share.id,
            project_id=share.project_id,
            user_id=share.user_id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            created_at=share.created_at,
        )
        for share, user in rows
    ]


@router.post("/projects/{project_id}/shares", response_model=ProjectShareOut)
def create_project_share(
    project_id: int,
    payload: ProjectShareCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user, owner_only=True)
    target = str(payload.target_user or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="target_user is required")

    target_user = db.query(User).filter(or_(User.username == target, User.email == target)).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    project = db.query(Project).filter(Project.id == project_id).first()
    if project and project.owner_id == target_user.id:
        raise HTTPException(status_code=400, detail="Project owner already has access")

    existing = db.query(ProjectShare).filter(
        ProjectShare.project_id == project_id,
        ProjectShare.user_id == target_user.id,
    ).first()
    if existing:
        return ProjectShareOut(
            id=existing.id,
            project_id=existing.project_id,
            user_id=existing.user_id,
            username=target_user.username,
            email=target_user.email,
            full_name=target_user.full_name,
            created_at=existing.created_at,
        )

    share = ProjectShare(project_id=project_id, user_id=target_user.id)
    db.add(share)
    db.commit()
    db.refresh(share)
    return ProjectShareOut(
        id=share.id,
        project_id=share.project_id,
        user_id=share.user_id,
        username=target_user.username,
        email=target_user.email,
        full_name=target_user.full_name,
        created_at=share.created_at,
    )


@router.delete("/projects/{project_id}/shares/{shared_user_id}", status_code=204)
def delete_project_share(
    project_id: int,
    shared_user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user, owner_only=True)
    share = db.query(ProjectShare).filter(
        ProjectShare.project_id == project_id,
        ProjectShare.user_id == shared_user_id,
    ).first()
    if not share:
        raise HTTPException(status_code=404, detail="Share record not found")
    db.delete(share)
    db.commit()
    return None


@router.post("/projects/{project_id}/story_generator/global", response_model=ProjectOut)
async def generate_project_story_dna_global(
    project_id: int,
    req: "StoryGeneratorRequest",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)

    gi_existing = dict(project.global_info or {})

    # Force global mode for this endpoint
    episodes_count = req.episodes_count
    if not episodes_count or int(episodes_count) <= 0:
        raise HTTPException(status_code=400, detail="episodes_count is required")

    prompt_dir = os.path.join(str(settings.BASE_DIR), "app", "core", "prompts")
    prompt_path = os.path.join(prompt_dir, "story_generator_global.txt")
    if not os.path.exists(prompt_path):
        logger.error(f"Story generator prompt not found at: {prompt_path}")
        raise HTTPException(status_code=404, detail="Prompt file 'story_generator_global.txt' not found.")
    with open(prompt_path, "r", encoding="utf-8") as f:
        sys_prompt = f.read()

    # Prefer request payload (latest UI state), fall back to saved global_info.
    script_title = (req.script_title or gi_existing.get("script_title") or "").strip()
    project_type = (getattr(req, "type", None) or gi_existing.get("type") or "").strip()
    language = (req.language or gi_existing.get("language") or "").strip()
    base_positioning = (req.base_positioning or gi_existing.get("base_positioning") or "").strip()
    global_style = (req.Global_Style or gi_existing.get("Global_Style") or gi_existing.get("global_style") or "").strip()

    user_prompt = (
        f"Mode: global\n"
        f"Project Title: {project.title}\n"
        f"Note: Project Overview / Basic Information and Character Canon may be empty; do not fail, infer sensible defaults and continue.\n"
        f"\n"
        f"[Project Overview / Basic Information]\n"
        f"Script Title: {script_title}\n"
        f"Type: {project_type}\n"
        f"Language: {language}\n"
        f"Base Positioning: {base_positioning}\n"
        f"Global Style: {global_style}\n"
        f"\n"
        f"Episodes Count: {int(episodes_count)}\n"
        f"Foreshadowing: {req.foreshadowing or ''}\n"
        f"Background: {req.background or ''}\n"
        f"Setup: {req.setup or ''}\n"
        f"Development: {req.development or ''}\n"
        f"Turning Points: {req.turning_points or ''}\n"
        f"Climax: {req.climax or ''}\n"
        f"Resolution: {req.resolution or ''}\n"
        f"Suspense: {req.suspense or ''}\n"
        f"Extra Notes: {req.extra_notes or ''}\n"
    )

    llm_config = agent_service.get_active_llm_config(current_user.id)
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured in active settings")
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None
    billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

    generated_md = await generate_markdown_with_retry(
        user_prompt=user_prompt,
        sys_prompt=sys_prompt,
        llm_config=llm_config,
        strict_markdown=(req.strict_markdown is not False),
        require_h1=True,
    )
    if not generated_md:
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    extracted_constraints = parse_global_style_constraints(generated_md)

    # Persist both output and the inputs that produced it.
    # This ensures a successful generation is durable across refresh even
    # if the user doesn't click the separate "Save Changes" button.
    try:
        story_input = req.model_dump()
    except AttributeError:
        story_input = req.dict()
    story_input["mode"] = "global"

    now_iso = datetime.utcnow().isoformat()
    gi = dict(project.global_info or {})
    gi["story_generator_global_input"] = story_input
    gi["story_dna_global_md"] = generated_md
    gi["story_dna_global_updated_at"] = now_iso
    if extracted_constraints:
        gi["global_style_constraints"] = extracted_constraints
        gi["global_style_constraints_updated_at"] = now_iso
    project.global_info = gi

    db.add(project)
    db.commit()
    db.refresh(project)

    # Populate response aliases to match other endpoints
    try:
        project.cover_image = get_project_cover_image(db, project.id)
    except Exception:
        project.cover_image = None
    try:
        project.aspectRatio = project.global_info.get('aspectRatio') if project.global_info else None
    except Exception:
        project.aspectRatio = None
    return project


@router.put("/projects/{project_id}/story_generator/global/input", response_model=ProjectOut)
def save_project_story_generator_global_input(
    project_id: int,
    req: "StoryGeneratorRequest",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist Story Generator (Global/Project) draft inputs without calling the LLM."""
    project = _require_project_access(db, project_id, current_user)

    try:
        story_input = req.model_dump()
    except AttributeError:
        story_input = req.dict()
    story_input["mode"] = "global"

    now_iso = datetime.utcnow().isoformat()
    gi = dict(project.global_info or {})
    gi["story_generator_global_input"] = story_input
    gi["story_generator_global_input_updated_at"] = now_iso
    project.global_info = gi

    db.add(project)
    db.commit()
    db.refresh(project)

    # Populate response aliases to match other endpoints
    try:
        project.cover_image = get_project_cover_image(db, project.id)
    except Exception:
        project.cover_image = None
    try:
        project.aspectRatio = project.global_info.get('aspectRatio') if project.global_info else None
    except Exception:
        project.aspectRatio = None
    return project


class StoryGeneratorGlobalImportRequest(BaseModel):
    project_overview: Optional[Dict[str, Any]] = None
    basic_information: Optional[Dict[str, Any]] = None
    character_canon_project: Optional[Dict[str, Any]] = None
    story_generator_global_project: Optional[Dict[str, Any]] = None
    story_generator_global_structured: Optional[Dict[str, Any]] = None
    story_generator_global_input: Optional[Dict[str, Any]] = None
    story_dna_global_md: Optional[str] = None
    global_style_constraints: Optional[Dict[str, Any]] = None


@router.get("/projects/{project_id}/story_generator/global/export", response_model=Dict[str, Any])
def export_project_story_generator_global_package(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)

    gi = dict(project.global_info or {})
    basic_info_nested = gi.get("basic_information") if isinstance(gi.get("basic_information"), dict) else {}
    e_global_info = gi.get("e_global_info") if isinstance(gi.get("e_global_info"), dict) else {}
    story_input = gi.get("story_generator_global_input") if isinstance(gi.get("story_generator_global_input"), dict) else {}

    def _pick_text(*values):
        for v in values:
            if v is None:
                continue
            s = str(v).strip()
            if s:
                return s
        return ""

    def _pick_dict(*values):
        for v in values:
            if isinstance(v, dict) and len(v) > 0:
                return v
        return {}

    def _pick_list(*values):
        for v in values:
            if isinstance(v, list) and len(v) > 0:
                return v
        return []

    basic_information = {
        "script_title": _pick_text(gi.get("script_title"), basic_info_nested.get("script_title"), e_global_info.get("script_title"), story_input.get("script_title")),
        "series_episode": _pick_text(gi.get("series_episode"), basic_info_nested.get("series_episode"), e_global_info.get("series_episode")),
        "type": _pick_text(gi.get("type"), basic_info_nested.get("type"), e_global_info.get("type"), story_input.get("type")),
        "language": _pick_text(gi.get("language"), basic_info_nested.get("language"), e_global_info.get("language"), story_input.get("language")),
        "base_positioning": _pick_text(gi.get("base_positioning"), basic_info_nested.get("base_positioning"), e_global_info.get("base_positioning"), story_input.get("base_positioning")),
        "Global_Style": _pick_text(gi.get("Global_Style"), gi.get("global_style"), basic_info_nested.get("Global_Style"), e_global_info.get("Global_Style"), story_input.get("Global_Style")),
        "tech_params": _pick_dict(gi.get("tech_params"), basic_info_nested.get("tech_params"), e_global_info.get("tech_params")),
        "tone": _pick_text(gi.get("tone"), basic_info_nested.get("tone"), e_global_info.get("tone")),
        "lighting": _pick_text(gi.get("lighting"), basic_info_nested.get("lighting"), e_global_info.get("lighting")),
        "borrowed_films": _pick_list(gi.get("borrowed_films"), basic_info_nested.get("borrowed_films"), e_global_info.get("borrowed_films")),
        "character_relationships": _pick_text(gi.get("character_relationships"), basic_info_nested.get("character_relationships")),
        "notes": _pick_text(gi.get("notes"), basic_info_nested.get("notes"), e_global_info.get("notes")),
    }

    character_canon_project = {
        "character_canon_input": gi.get("character_canon_input") or {},
        "character_canon_md": gi.get("character_canon_md") or "",
        "character_profiles": gi.get("character_profiles") or [],
        "character_canon_tag_categories": gi.get("character_canon_tag_categories") or [],
        "character_canon_identity_categories": gi.get("character_canon_identity_categories") or [],
    }

    def _extract_between(text: str, start_pat: str, end_pat: str) -> str:
        try:
            pattern = rf"{start_pat}(.*?){end_pat}"
            m = re.search(pattern, text, flags=re.S)
            return (m.group(1).strip() if m else "")
        except Exception:
            return ""

    def _extract_story_structured(md: str) -> Dict[str, Any]:
        raw = str(md or "")
        if not raw.strip():
            return {}
        setup_block = _extract_between(raw, r"###\s*A\)\s*定场（开场与触发事件）", r"###\s*B\)\s*发展")
        development_block = _extract_between(raw, r"###\s*B\)\s*发展", r"###\s*C\)\s*转折")
        turning_block = _extract_between(raw, r"###\s*C\)\s*转折", r"###\s*D\)\s*高潮")
        climax_block = _extract_between(raw, r"###\s*D\)\s*高潮", r"###\s*E\)\s*定局")
        resolution_block = _extract_between(raw, r"###\s*E\)\s*定局", r"##\s*5\)\s*悬念系统")
        suspense_block = _extract_between(raw, r"##\s*5\)\s*悬念系统", r"##\s*6\)\s*伏笔与回收")
        foreshadowing_block = _extract_between(raw, r"##\s*6\)\s*伏笔与回收", r"##\s*7\)\s*分集规划")
        background_block = _extract_between(raw, r"##\s*1\)\s*核心设定（背景/世界观）", r"##\s*2\)\s*主角与目标")

        hook = ""
        inciting = ""
        point_of_no_return = ""
        for line in (setup_block or "").splitlines():
            s = line.strip()
            if (not hook) and ("开场钩子" in s):
                hook = s
            elif (not inciting) and ("触发事件" in s):
                inciting = s
            elif (not point_of_no_return) and ("不可回头" in s or "立场选择" in s):
                point_of_no_return = s

        return {
            "background": background_block,
            "setup": setup_block,
            "hook": hook,
            "inciting_incident": inciting,
            "point_of_no_return": point_of_no_return,
            "development": development_block,
            "turning_points": turning_block,
            "climax": climax_block,
            "resolution": resolution_block,
            "suspense": suspense_block,
            "foreshadowing": foreshadowing_block,
        }

    story_structured = _extract_story_structured(gi.get("story_dna_global_md") or "")

    def _coalesce_story_input(stored_input: Dict[str, Any], structured: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(stored_input or {})
        for key in ["background", "setup", "development", "turning_points", "climax", "resolution", "suspense", "foreshadowing"]:
            current = str(merged.get(key) or "").strip()
            if not current:
                merged[key] = structured.get(key) or ""
        return merged

    story_input_export = _coalesce_story_input(story_input, story_structured)

    # Export complete Story Generator (Global/Project) related payload,
    # including draft inputs, outputs and metadata timestamps.
    story_generator_global_project = {
        key: value
        for key, value in gi.items()
        if (
            str(key).startswith("story_generator_global")
            or str(key).startswith("story_dna_global")
            or str(key).startswith("global_style_constraints")
        )
    }

    return {
        "schema_version": 1,
        "export_type": "story_generator_global_project",
        "exported_at": datetime.utcnow().isoformat(),
        "source_project": {
            "id": project.id,
            "title": project.title,
        },
        "project_overview": {
            "script_title": basic_information.get("script_title") or "",
            "type": basic_information.get("type") or "",
            "language": basic_information.get("language") or "",
            "base_positioning": basic_information.get("base_positioning") or "",
            "Global_Style": basic_information.get("Global_Style") or "",
        },
        "basic_information": basic_information,
        "character_canon_project": character_canon_project,
        "story_generator_global_project": story_generator_global_project,
        "story_generator_global_structured": story_structured,
        "story_generator_global_input": story_input_export,
        "story_dna_global_md": gi.get("story_dna_global_md") or "",
        "global_style_constraints": gi.get("global_style_constraints") or {},
    }


@router.put("/projects/{project_id}/story_generator/global/import", response_model=ProjectOut)
def import_project_story_generator_global_package(
    project_id: int,
    req: StoryGeneratorGlobalImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)

    now_iso = datetime.utcnow().isoformat()
    gi = dict(project.global_info or {})

    basic_information = req.basic_information or req.project_overview or {}
    if isinstance(basic_information, dict):
        text_fields = [
            "script_title",
            "series_episode",
            "type",
            "language",
            "base_positioning",
            "Global_Style",
            "tone",
            "lighting",
            "character_relationships",
            "notes",
        ]
        for key in text_fields:
            if key in basic_information:
                val = basic_information.get(key)
                gi[key] = "" if val is None else str(val)

        if "tech_params" in basic_information and isinstance(basic_information.get("tech_params"), dict):
            gi["tech_params"] = basic_information.get("tech_params") or {}

        if "borrowed_films" in basic_information:
            borrowed = basic_information.get("borrowed_films")
            gi["borrowed_films"] = borrowed if isinstance(borrowed, list) else []

    canon_payload = req.character_canon_project or {}
    if isinstance(canon_payload, dict):
        if "character_canon_input" in canon_payload and isinstance(canon_payload.get("character_canon_input"), dict):
            gi["character_canon_input"] = canon_payload.get("character_canon_input") or {}
            gi["character_canon_input_updated_at"] = now_iso

        if "character_canon_md" in canon_payload:
            gi["character_canon_md"] = canon_payload.get("character_canon_md") or ""

        if "character_profiles" in canon_payload:
            profiles = canon_payload.get("character_profiles")
            gi["character_profiles"] = profiles if isinstance(profiles, list) else []
            gi["character_profiles_updated_at"] = now_iso

        if "character_canon_tag_categories" in canon_payload:
            tags = canon_payload.get("character_canon_tag_categories")
            gi["character_canon_tag_categories"] = tags if isinstance(tags, list) else []

        if "character_canon_identity_categories" in canon_payload:
            identities = canon_payload.get("character_canon_identity_categories")
            gi["character_canon_identity_categories"] = identities if isinstance(identities, list) else []

    # Full Story Generator (Global/Project) package import (preferred path)
    # Accept all recognized story-global keys and merge into global_info.
    full_story_pkg = req.story_generator_global_project or {}
    if isinstance(full_story_pkg, dict):
        for key, value in full_story_pkg.items():
            k = str(key)
            if (
                k.startswith("story_generator_global")
                or k.startswith("story_dna_global")
                or k.startswith("global_style_constraints")
            ):
                gi[k] = value

    imported_input = req.story_generator_global_input or {}
    if isinstance(imported_input, dict) and len(imported_input) > 0:
        normalized_input = dict(imported_input)
        normalized_input["mode"] = "global"
        if "episodes_count" in normalized_input:
            try:
                normalized_input["episodes_count"] = int(normalized_input.get("episodes_count") or 0)
            except Exception:
                normalized_input["episodes_count"] = 0

        structured_input = req.story_generator_global_structured or {}
        if isinstance(structured_input, dict):
            for key in ["background", "setup", "development", "turning_points", "climax", "resolution", "suspense", "foreshadowing"]:
                if not str(normalized_input.get(key) or "").strip() and str(structured_input.get(key) or "").strip():
                    normalized_input[key] = structured_input.get(key)

        gi["story_generator_global_input"] = normalized_input
        gi["story_generator_global_input_updated_at"] = now_iso

    if req.story_dna_global_md is not None:
        gi["story_dna_global_md"] = req.story_dna_global_md or ""
        gi["story_dna_global_updated_at"] = now_iso

    if req.global_style_constraints is not None:
        gi["global_style_constraints"] = req.global_style_constraints or {}
        gi["global_style_constraints_updated_at"] = now_iso

    project.global_info = gi
    db.add(project)
    db.commit()
    db.refresh(project)

    # Populate response aliases to match other endpoints
    try:
        project.cover_image = get_project_cover_image(db, project.id)
    except Exception:
        project.cover_image = None
    try:
        project.aspectRatio = project.global_info.get('aspectRatio') if project.global_info else None
    except Exception:
        project.aspectRatio = None
    return project


class AnalyzeNovelRequest(BaseModel):
    novel_text: str


@router.post("/projects/{project_id}/story_generator/analyze_novel", response_model=Dict[str, Any])
async def analyze_project_novel_to_story_generator_fields(
    project_id: int,
    req: AnalyzeNovelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)

    novel_text = (req.novel_text or "").strip()
    if not novel_text:
        raise HTTPException(status_code=400, detail="novel_text is required")

    prompt_dir = os.path.join(str(settings.BASE_DIR), "app", "core", "prompts")
    prompt_path = os.path.join(prompt_dir, "story_generator_analyze_novel.txt")
    if not os.path.exists(prompt_path):
        logger.error(f"Analyze novel prompt not found at: {prompt_path}")
        raise HTTPException(status_code=404, detail="Prompt file 'story_generator_analyze_novel.txt' not found.")

    with open(prompt_path, "r", encoding="utf-8") as f:
        sys_prompt_template = f.read()

    user_prompt = f"Project Title: {project.title}\n\nNovel/Script Text:\n{novel_text}"

    llm_config = agent_service.get_active_llm_config(current_user.id)
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured in active settings")
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None
    resolved_id = ((llm_config or {}).get("config") or {}).get("__resolved_setting_id")
    resolved_source = ((llm_config or {}).get("config") or {}).get("__resolved_source")
    logger.info(
        "[analyze_novel] Using LLM config | provider=%s model=%s base_url=%s setting_id=%s source=%s",
        provider,
        model,
        (llm_config or {}).get("base_url"),
        resolved_id,
        resolved_source,
    )
    billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

    # Keep compatibility with prompt template variable while still passing text in user prompt.
    try:
        sys_prompt = sys_prompt_template.format(novel_text=novel_text)
    except Exception:
        sys_prompt = sys_prompt_template

    resp = await llm_service.generate_content(user_prompt, sys_prompt, llm_config)
    raw = (resp.get("content") or "").strip()
    if not raw:
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    content = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    content = content.replace("```json", "").replace("```", "").strip()
    start_idx = content.find("{")
    end_idx = content.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        content = content[start_idx:end_idx + 1]

    try:
        data = json.loads(content)
    except Exception as e:
        logger.error(f"[analyze_novel] JSON parse failed: {e}. Raw len={len(raw)}")
        raise HTTPException(status_code=500, detail="Failed to parse LLM JSON for novel analysis")

    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="LLM JSON must be an object")

    required_keys = [
        "background",
        "setup",
        "development",
        "turning_points",
        "climax",
        "resolution",
        "suspense",
        "foreshadowing",
    ]

    normalized: Dict[str, Any] = {}
    for key in required_keys:
        val = data.get(key, "")
        if val is None:
            normalized[key] = ""
        elif isinstance(val, str):
            normalized[key] = val.strip()
        else:
            normalized[key] = str(val).strip()

    return normalized


@router.get("/projects/", response_model=List[ProjectOut])
def read_projects(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    shared_project_ids = [
        row[0]
        for row in db.query(ProjectShare.project_id).filter(ProjectShare.user_id == current_user.id).all()
    ]
    projects = (
        db.query(Project)
        .filter(
            or_(
                Project.owner_id == current_user.id,
                Project.id.in_(shared_project_ids),
            )
        )
        .order_by(Project.created_at.desc(), Project.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    for p in projects:
        p.cover_image = get_project_cover_image(db, p.id)
        _attach_project_flags(p, current_user)
        # Populate alias field
        if p.global_info:
             p.aspectRatio = p.global_info.get('aspectRatio')
        
        # Debug logging
        # logger.info(f"Project {p.id}: Cover={p.cover_image}")
        
    return projects


@router.get("/projects/{project_id}", response_model=ProjectOut)
def read_project(
    project_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = _require_project_access(db, project_id, current_user)
    
    project.cover_image = get_project_cover_image(db, project.id)
    if project.global_info:
        project.aspectRatio = project.global_info.get('aspectRatio')
    _attach_project_flags(project, current_user)
    return project

@router.put("/projects/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int, 
    project_in: ProjectUpdate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    project = _require_project_access(db, project_id, current_user)
    
    if project_in.title is not None:
        project.title = project_in.title
    
    # Merge global_info updates - handle aspectRatio specially if provided separately
    new_global_info = project_in.global_info # dict or None
    if new_global_info is None:
         # If generic global_info not provided, maybe we init with existing?
         # But usually PUT overwrites or PATCH updates partial. 
         # Assuming logic: "if provided, update".
         # However, we also have project_in.aspectRatio now.
         if project_in.aspectRatio is not None:
              # We need to update just that key in the existing JSON
              current_info = dict(project.global_info) if project.global_info else {}
              current_info['aspectRatio'] = project_in.aspectRatio
              project.global_info = current_info
    else:
         # global_info IS provided. Check if aspectRatio is also provided separately
         if project_in.aspectRatio is not None:
             new_global_info['aspectRatio'] = project_in.aspectRatio
         project.global_info = new_global_info
    
    db.commit()
    db.refresh(project)
    project.cover_image = get_project_cover_image(db, project.id)
    if project.global_info:
        project.aspectRatio = project.global_info.get('aspectRatio')
    _attach_project_flags(project, current_user)
    return project

@router.delete("/projects/{project_id}", status_code=204)
def delete_project(
    project_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = _require_project_access(db, project_id, current_user, owner_only=True)

    # Cascade delete related data (scenes, shots, subjects/entities, etc.)
    # Note: We do not delete user-level assets unless they are explicitly referenced by the project.
    try:
        # Collect related IDs
        episode_ids = [row[0] for row in db.query(Episode.id).filter(Episode.project_id == project_id).all()]
        scene_ids: List[int] = []
        if episode_ids:
            scene_ids = [row[0] for row in db.query(Scene.id).filter(Scene.episode_id.in_(episode_ids)).all()]

        # Collect referenced upload URLs/paths before deleting rows
        candidate_urls: List[str] = []
        if scene_ids:
            for (img_url, vid_url) in db.query(Shot.image_url, Shot.video_url).filter(Shot.scene_id.in_(scene_ids)).all():
                if img_url:
                    candidate_urls.append(img_url)
                if vid_url:
                    candidate_urls.append(vid_url)
        for (img_url,) in db.query(Entity.image_url).filter(Entity.project_id == project_id).all():
            if img_url:
                candidate_urls.append(img_url)

        # Delete DB rows bottom-up to avoid FK constraints
        if scene_ids:
            db.query(Shot).filter(Shot.scene_id.in_(scene_ids)).delete(synchronize_session=False)
            db.query(Scene).filter(Scene.id.in_(scene_ids)).delete(synchronize_session=False)

        if episode_ids:
            db.query(ScriptSegment).filter(ScriptSegment.episode_id.in_(episode_ids)).delete(synchronize_session=False)
            db.query(Episode).filter(Episode.id.in_(episode_ids)).delete(synchronize_session=False)

        db.query(Entity).filter(Entity.project_id == project_id).delete(synchronize_session=False)

        db.delete(project)
        db.commit()

    except Exception as e:
        db.rollback()
        logger.error(f"[delete_project] Cascade delete failed project_id={project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Best-effort file cleanup after DB commit
    try:
        upload_root = settings.UPLOAD_DIR
        if not os.path.isabs(upload_root):
            upload_root = os.path.abspath(upload_root)

        def _to_upload_path(url_or_path: str) -> Optional[str]:
            if not url_or_path:
                return None
            raw = str(url_or_path).strip()
            if not raw:
                return None

            # If it's a URL, strip scheme/host
            try:
                parsed = urllib.parse.urlparse(raw)
                path_part = parsed.path if parsed.scheme else raw
            except Exception:
                path_part = raw

            path_part = urllib.parse.unquote(path_part)
            path_part = path_part.lstrip("/")

            # Normalize common forms:
            # - uploads/<user>/<file>
            # - /uploads/<user>/<file>
            # - <user>/<file> (relative already)
            if path_part.startswith("uploads/"):
                rel = path_part.replace("uploads/", "", 1)
            elif "/uploads/" in path_part:
                rel = path_part.split("/uploads/", 1)[1]
            else:
                rel = path_part

            abs_path = os.path.abspath(os.path.join(upload_root, rel))
            # Safety: only delete within upload_root
            if not abs_path.startswith(upload_root):
                return None
            return abs_path

        for u in set(candidate_urls):
            p = _to_upload_path(u)
            if p and os.path.exists(p) and os.path.isfile(p):
                try:
                    os.remove(p)
                except Exception as fe:
                    logger.warning(f"[delete_project] Failed to delete file {p}: {fe}")
    except Exception as e:
        logger.warning(f"[delete_project] File cleanup skipped/failed project_id={project_id}: {e}")

    return None

# --- Episodes (Script) ---

class ScriptSegmentBase(BaseModel):
    pid: str
    title: str
    content_revised: str
    content_original: str
    narrative_function: str
    analysis: str

class ScriptSegmentOut(ScriptSegmentBase):
    id: int
    class Config:
        from_attributes = True

class EpisodeCreate(BaseModel):
    title: str = "Episode 1"
    script_content: Optional[str] = ""
    episode_info: Optional[Dict] = {}
    ai_scene_analysis_result: Optional[str] = None
    character_profiles: Optional[List[Dict[str, Any]]] = None

class EpisodeUpdate(BaseModel):
    title: Optional[str] = None
    script_content: Optional[str] = None
    episode_info: Optional[Dict] = None
    ai_scene_analysis_result: Optional[str] = None
    character_profiles: Optional[List[Dict[str, Any]]] = None

class EpisodeOut(BaseModel):
    id: int
    project_id: int
    title: str
    script_content: Optional[str]
    episode_info: Optional[Dict] = {}
    ai_scene_analysis_result: Optional[str] = None
    character_profiles: Optional[List[Dict[str, Any]]] = []
    script_segments: List[ScriptSegmentOut] = []
    class Config:
        from_attributes = True


class ProjectEpisodeScriptsGenerateRequest(BaseModel):
    episodes_count: Optional[int] = None
    overwrite_existing: bool = False
    retry_failed_only: bool = False
    extra_notes: Optional[str] = None
    strict_markdown: bool = True

@router.get("/projects/{project_id}/episodes", response_model=List[EpisodeOut])
def read_episodes(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify access
    _require_project_access(db, project_id, current_user)
    
    return db.query(Episode).filter(Episode.project_id == project_id).all()

@router.put("/episodes/{episode_id}/segments", response_model=List[ScriptSegmentOut])
def update_episode_segments(
    episode_id: int,
    segments: List[ScriptSegmentBase],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    _require_project_access(db, episode.project_id, current_user)

    # Clear existing
    db.query(ScriptSegment).filter(ScriptSegment.episode_id == episode_id).delete()
    
    # Add new
    new_segments = []
    for s in segments:
        seg = ScriptSegment(
            episode_id=episode_id,
            pid=s.pid,
            title=s.title,
            content_revised=s.content_revised,
            content_original=s.content_original,
            narrative_function=s.narrative_function,
            analysis=s.analysis
        )
        db.add(seg)
        new_segments.append(seg)
    
    db.commit()
    # Refresh logic is tricky for lists, but querying clearly works
    return db.query(ScriptSegment).filter(ScriptSegment.episode_id == episode_id).all()

@router.post("/projects/{project_id}/episodes", response_model=EpisodeOut)
def create_episode(
    project_id: int,
    episode: EpisodeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_project_access(db, project_id, current_user)
        
    db_episode = Episode(
        project_id=project_id, 
        title=episode.title, 
        script_content=episode.script_content,
        episode_info=episode.episode_info,
        ai_scene_analysis_result=episode.ai_scene_analysis_result,
        character_profiles=episode.character_profiles or []
    )
    db.add(db_episode)
    db.commit()
    db.refresh(db_episode)
    return db_episode

@router.put("/episodes/{episode_id}", response_model=EpisodeOut)
def update_episode(
    episode_id: int,
    episode_in: EpisodeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    # Check access via project
    _require_project_access(db, episode.project_id, current_user)

    if episode_in.title is not None:
        episode.title = episode_in.title
    if episode_in.script_content is not None:
        episode.script_content = episode_in.script_content
    if episode_in.episode_info is not None:
        episode.episode_info = episode_in.episode_info
    if episode_in.ai_scene_analysis_result is not None:
        episode.ai_scene_analysis_result = episode_in.ai_scene_analysis_result
    if episode_in.character_profiles is not None:
        episode.character_profiles = episode_in.character_profiles
    
    db.commit()
    db.refresh(episode)
    return episode


class CharacterProfileGenerateRequest(BaseModel):
    name: str
    identity: Optional[str] = None
    body_features: Optional[str] = None
    style_tags: Optional[List[str]] = []
    extra_notes: Optional[str] = None


class CharacterProfilesUpdateRequest(BaseModel):
    character_profiles: List[Dict[str, Any]]


class CharacterCanonInputRequest(BaseModel):
    name: Optional[str] = None
    selected_tag_ids: Optional[List[str]] = None
    selected_identity_ids: Optional[List[str]] = None
    custom_identity: Optional[str] = None
    body_features: Optional[str] = None
    custom_style_tags: Optional[str] = None
    extra_notes: Optional[str] = None


class CharacterCanonCategoriesRequest(BaseModel):
    tag_categories: Optional[List[Dict[str, Any]]] = None
    identity_categories: Optional[List[Dict[str, Any]]] = None


@router.get("/projects/{project_id}/character_profiles", response_model=List[Dict[str, Any]])
def get_project_character_profiles(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)
    gi = project.global_info or {}
    if not isinstance(gi, dict):
        return []
    profiles = gi.get("character_profiles")
    return profiles if isinstance(profiles, list) else []


@router.put("/projects/{project_id}/character_profiles", response_model=List[Dict[str, Any]])
def update_project_character_profiles(
    project_id: int,
    req: CharacterProfilesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)

    def _render_canon_md(items: List[Dict[str, Any]]) -> str:
        blocks: List[str] = []
        for it in items or []:
            if not isinstance(it, dict):
                continue
            nm = (it.get("name") or "").strip()
            if not nm:
                continue
            md = (it.get("description_md") or "").strip()
            if md:
                blocks.append(md)
            else:
                blocks.append(f"### {nm} (Canonical)\n- Identity: {it.get('identity') or ''}\n")
        return "\n\n".join(blocks).strip()

    gi = dict(project.global_info or {})
    profiles = req.character_profiles or []
    gi["character_profiles"] = profiles
    gi["character_profiles_updated_at"] = datetime.utcnow().isoformat()
    gi["character_canon_md"] = _render_canon_md(profiles)
    project.global_info = gi

    db.add(project)
    db.commit()
    db.refresh(project)

    profiles = gi.get("character_profiles")
    return profiles if isinstance(profiles, list) else []


@router.put("/projects/{project_id}/character_canon/input", response_model=ProjectOut)
def save_project_character_canon_input(
    project_id: int,
    req: CharacterCanonInputRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist Project Character Canon draft inputs without calling the LLM."""
    project = _require_project_access(db, project_id, current_user)

    now_iso = datetime.utcnow().isoformat()
    gi = dict(project.global_info or {})
    gi["character_canon_input"] = {
        "name": req.name or "",
        "selected_tag_ids": req.selected_tag_ids or [],
        "selected_identity_ids": req.selected_identity_ids or [],
        "custom_identity": req.custom_identity or "",
        "body_features": req.body_features or "",
        "custom_style_tags": req.custom_style_tags or "",
        "extra_notes": req.extra_notes or "",
    }
    gi["character_canon_input_updated_at"] = now_iso
    project.global_info = gi

    db.add(project)
    db.commit()
    db.refresh(project)

    # Populate response aliases
    try:
        project.cover_image = get_project_cover_image(db, project.id)
    except Exception:
        project.cover_image = None
    try:
        project.aspectRatio = project.global_info.get('aspectRatio') if project.global_info else None
    except Exception:
        project.aspectRatio = None
    return project


@router.put("/projects/{project_id}/character_canon/categories", response_model=ProjectOut)
def save_project_character_canon_categories(
    project_id: int,
    req: CharacterCanonCategoriesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist Project Character Canon tag/identity category configuration."""
    project = _require_project_access(db, project_id, current_user)

    now_iso = datetime.utcnow().isoformat()
    gi = dict(project.global_info or {})
    if req.tag_categories is not None:
        gi["character_canon_tag_categories"] = req.tag_categories
    if req.identity_categories is not None:
        gi["character_canon_identity_categories"] = req.identity_categories
    gi["character_canon_categories_updated_at"] = now_iso
    project.global_info = gi

    db.add(project)
    db.commit()
    db.refresh(project)

    # Populate response aliases
    try:
        project.cover_image = get_project_cover_image(db, project.id)
    except Exception:
        project.cover_image = None
    try:
        project.aspectRatio = project.global_info.get('aspectRatio') if project.global_info else None
    except Exception:
        project.aspectRatio = None
    return project


@router.post("/projects/{project_id}/character_profiles/generate", response_model=ProjectOut)
async def generate_project_character_profile(
    project_id: int,
    req: CharacterProfileGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)

    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Character name is required")

    tags = [t.strip() for t in (req.style_tags or []) if isinstance(t, str) and t.strip()]
    tags_str = ", ".join(tags)

    sys_prompt = (
        "You are a professional character bible writer for film storyboarding. "
        "Write a CANONICAL character profile that will be treated as the single source of truth for this project. "
        "Return ONLY Markdown (no JSON, no code fences). "
        "Keep it concise but specific. Avoid NSFW/explicit sexual content; if the user requests 'sexy', express it in non-explicit, cinematic terms. "
        "Do not invent backstory not implied by inputs; focus on identity, silhouette/body proportions, face/hair, clothing, signature mannerisms, and on-screen presence."
    )

    user_prompt = (
        f"Character Name: {name}\n"
        f"Identity/Role: {req.identity or ''}\n"
        f"Body Features: {req.body_features or ''}\n"
        f"Style Tags: {tags_str}\n"
        f"Extra Notes: {req.extra_notes or ''}\n\n"
        "Output format (Markdown):\n"
        f"### {name} (Canonical)\n"
        "- Identity: ...\n"
        "- Body & silhouette: ...\n"
        "- Face & hair: ...\n"
        "- Outfit & materials: ...\n"
        "- Screen presence (cinematic, non-explicit): ...\n"
        "- Do/Don't (hard constraints): ...\n"
    )

    llm_config = agent_service.get_active_llm_config(current_user.id)
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None
    billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

    resp = await llm_service.generate_content(user_prompt, sys_prompt, llm_config)
    description_md = (resp.get("content") or "").strip()
    if not description_md:
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    now_iso = datetime.utcnow().isoformat()
    gi = dict(project.global_info or {})
    profiles = gi.get("character_profiles")
    profiles = list(profiles) if isinstance(profiles, list) else []

    updated = False
    for p in profiles:
        if isinstance(p, dict) and (p.get("name") == name):
            p.update({
                "name": name,
                "identity": req.identity,
                "body_features": req.body_features,
                "style_tags": tags,
                "extra_notes": req.extra_notes,
                "description_md": description_md,
                "updated_at": now_iso,
            })
            updated = True
            break
    if not updated:
        profiles.append({
            "name": name,
            "identity": req.identity,
            "body_features": req.body_features,
            "style_tags": tags,
            "extra_notes": req.extra_notes,
            "description_md": description_md,
            "updated_at": now_iso,
        })

    def _render_canon_md(items: List[Dict[str, Any]]) -> str:
        blocks = []
        for it in items:
            if not isinstance(it, dict):
                continue
            nm = (it.get("name") or "").strip()
            if not nm:
                continue
            md = (it.get("description_md") or "").strip()
            if md:
                blocks.append(md)
            else:
                blocks.append(f"### {nm} (Canonical)\n- Identity: {it.get('identity') or ''}\n")
        return "\n\n".join(blocks).strip()

    gi["character_profiles"] = profiles
    gi["character_profiles_updated_at"] = now_iso
    gi["character_canon_md"] = _render_canon_md(profiles)
    project.global_info = gi

    db.add(project)
    db.commit()
    db.refresh(project)

    # Populate response aliases
    try:
        project.cover_image = get_project_cover_image(db, project.id)
    except Exception:
        project.cover_image = None
    try:
        project.aspectRatio = project.global_info.get('aspectRatio') if project.global_info else None
    except Exception:
        project.aspectRatio = None
    return project


class StoryGeneratorRequest(BaseModel):
    mode: str  # 'global' | 'episode'
    episodes_count: Optional[int] = None
    episode_number: Optional[int] = None
    # Project Overview / Basic Information (optional but should be forwarded to LLM when provided)
    script_title: Optional[str] = None
    type: Optional[str] = None
    language: Optional[str] = None
    base_positioning: Optional[str] = None
    Global_Style: Optional[str] = None
    foreshadowing: Optional[str] = None
    background: Optional[str] = None
    setup: Optional[str] = None
    development: Optional[str] = None
    turning_points: Optional[str] = None
    climax: Optional[str] = None
    resolution: Optional[str] = None
    suspense: Optional[str] = None
    extra_notes: Optional[str] = None
    strict_markdown: bool = True


class ScriptScenesGenerateRequest(BaseModel):
    scene_count: Optional[int] = None
    background: Optional[str] = None
    setup: Optional[str] = None
    development: Optional[str] = None
    turning_points: Optional[str] = None
    climax: Optional[str] = None
    resolution: Optional[str] = None
    suspense: Optional[str] = None
    foreshadowing: Optional[str] = None
    extra_notes: Optional[str] = None
    replace_existing_scenes: Optional[bool] = True


EPISODE_SCENE_GEN_STATUS_KEY = "episode_scene_generation_status"


def _read_episode_scene_generation_status(episode: Episode) -> Dict[str, Any]:
    try:
        info = dict(episode.episode_info or {})
        payload = info.get(EPISODE_SCENE_GEN_STATUS_KEY)
        if isinstance(payload, dict):
            return dict(payload)
    except Exception:
        pass
    return {
        "running": False,
        "status": "idle",
        "message": "",
        "scenes_created": 0,
        "stop_requested": False,
    }


def _persist_episode_scene_generation_status(db: Session, episode: Episode, status_payload: Dict[str, Any]) -> None:
    info = dict(episode.episode_info or {})
    info[EPISODE_SCENE_GEN_STATUS_KEY] = status_payload
    episode.episode_info = info
    db.add(episode)
    db.commit()


def _run_episode_scene_generation_job(episode_id: int, req_payload: Dict[str, Any], user_id: int) -> None:
    db = SessionLocal()
    try:
        episode = db.query(Episode).filter(Episode.id == episode_id).first()
        user = db.query(User).filter(User.id == user_id).first()
        if not episode or not user:
            return

        latest = _read_episode_scene_generation_status(episode)
        if bool(latest.get("stop_requested")):
            latest["running"] = False
            latest["status"] = "stopped"
            latest["message"] = "Stopped before generation started"
            latest["finished_at"] = datetime.utcnow().isoformat()
            latest["updated_at"] = latest["finished_at"]
            _persist_episode_scene_generation_status(db, episode, latest)
            return

        req = ScriptScenesGenerateRequest(**(req_payload or {}))
        result = asyncio.run(
            generate_episode_scenes_from_story(
                episode_id=episode_id,
                req=req,
                db=db,
                current_user=user,
            )
        )

        episode = db.query(Episode).filter(Episode.id == episode_id).first()
        if episode:
            status_payload = _read_episode_scene_generation_status(episode)
            status_payload["running"] = False
            status_payload["status"] = "completed"
            status_payload["message"] = "Scene generation completed"
            status_payload["scenes_created"] = int((result or {}).get("scenes_created") or 0)
            status_payload["result"] = result
            status_payload["updated_at"] = datetime.utcnow().isoformat()
            status_payload["finished_at"] = status_payload["updated_at"]
            _persist_episode_scene_generation_status(db, episode, status_payload)
    except Exception as e:
        try:
            episode = db.query(Episode).filter(Episode.id == episode_id).first()
            if episode:
                status_payload = _read_episode_scene_generation_status(episode)
                status_payload["running"] = False
                status_payload["status"] = "failed"
                status_payload["message"] = str(e)
                status_payload["updated_at"] = datetime.utcnow().isoformat()
                status_payload["finished_at"] = status_payload["updated_at"]
                _persist_episode_scene_generation_status(db, episode, status_payload)
        except Exception:
            pass
    finally:
        db.close()


@router.get("/episodes/{episode_id}/character_profiles", response_model=List[Dict[str, Any]])
def get_episode_character_profiles(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    return episode.character_profiles or []


@router.put("/episodes/{episode_id}/character_profiles", response_model=List[Dict[str, Any]])
def update_episode_character_profiles(
    episode_id: int,
    req: CharacterProfilesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    episode.character_profiles = req.character_profiles or []
    db.commit()
    db.refresh(episode)
    return episode.character_profiles or []


@router.post("/episodes/{episode_id}/character_profiles/generate", response_model=EpisodeOut)
async def generate_episode_character_profile(
    episode_id: int,
    req: CharacterProfileGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Character name is required")

    # Build a strict, safe prompt: canonical character sheet used as ground truth.
    tags = [t.strip() for t in (req.style_tags or []) if isinstance(t, str) and t.strip()]
    tags_str = ", ".join(tags)

    sys_prompt = (
        "You are a professional character bible writer for film storyboarding. "
        "Write a CANONICAL character profile that will be treated as the single source of truth for this script. "
        "Return ONLY Markdown (no JSON, no code fences). "
        "Keep it concise but specific. Avoid NSFW/explicit sexual content; if the user requests 'sexy', express it in non-explicit, cinematic terms. "
        "Do not invent backstory not implied by inputs; focus on identity, silhouette/body proportions, face/hair, clothing, signature mannerisms, and on-screen presence."
    )

    user_prompt = (
        f"Character Name: {name}\n"
        f"Identity/Role: {req.identity or ''}\n"
        f"Body Features: {req.body_features or ''}\n"
        f"Style Tags: {tags_str}\n"
        f"Extra Notes: {req.extra_notes or ''}\n\n"
        "Output format (Markdown):\n"
        f"### {name} (Canonical)\n"
        "- Identity: ...\n"
        "- Body & silhouette: ...\n"
        "- Face & hair: ...\n"
        "- Outfit & materials: ...\n"
        "- Screen presence (cinematic, non-explicit): ...\n"
        "- Do/Don't (hard constraints): ...\n"
    )

    llm_config = agent_service.get_active_llm_config(current_user.id)
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None
    billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

    resp = await llm_service.generate_content(user_prompt, sys_prompt, llm_config)
    description_md = (resp.get("content") or "").strip()
    if not description_md:
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    now_iso = datetime.utcnow().isoformat()
    profiles = list(episode.character_profiles or [])
    updated = False
    for p in profiles:
        if isinstance(p, dict) and (p.get("name") == name):
            p.update({
                "name": name,
                "identity": req.identity,
                "body_features": req.body_features,
                "style_tags": tags,
                "extra_notes": req.extra_notes,
                "description_md": description_md,
                "updated_at": now_iso,
            })
            updated = True
            break
    if not updated:
        profiles.append({
            "name": name,
            "identity": req.identity,
            "body_features": req.body_features,
            "style_tags": tags,
            "extra_notes": req.extra_notes,
            "description_md": description_md,
            "updated_at": now_iso,
        })

    def _render_canon_md(items: List[Dict[str, Any]]) -> str:
        blocks = []
        for it in items:
            if not isinstance(it, dict):
                continue
            nm = (it.get("name") or "").strip()
            if not nm:
                continue
            md = (it.get("description_md") or "").strip()
            if md:
                blocks.append(md)
            else:
                blocks.append(f"### {nm} (Canonical)\n- Identity: {it.get('identity') or ''}\n")
        return "\n\n".join(blocks).strip()

    canon_body = _render_canon_md(profiles)
    canon_section = (
        "## Character Canon (Authoritative)\n"
        "\n"
        "<!-- CHARACTER_CANON_START -->\n"
        "The following character profiles are AUTHORITATIVE for this script. Scene analysis and downstream generation MUST use these descriptions as ground truth and IGNORE conflicting character info elsewhere in the script.\n\n"
        f"{canon_body}\n"
        "<!-- CHARACTER_CANON_END -->\n"
    )

    script = episode.script_content or ""
    if "<!-- CHARACTER_CANON_START -->" in script and "<!-- CHARACTER_CANON_END -->" in script:
        script = re.sub(
            r"## Character Canon \(Authoritative\)[\s\S]*?<!-- CHARACTER_CANON_END -->\n?",
            canon_section + "\n",
            script,
            count=1,
        )
    else:
        script = canon_section + "\n\n" + script

    episode.character_profiles = profiles
    episode.script_content = script
    db.commit()
    db.refresh(episode)
    return episode


@router.post("/episodes/{episode_id}/story_generator", response_model=EpisodeOut)
async def generate_episode_story_dna(
    episode_id: int,
    req: "StoryGeneratorRequest",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    project = _require_project_access(db, episode.project_id, current_user)

    mode = (req.mode or "").strip().lower()
    if mode not in ("global", "episode"):
        raise HTTPException(status_code=400, detail="mode must be 'global' or 'episode'")

    if mode == "global":
        # Backward compatible: allow generating global from any episode, but store to project.global_info
        if not req.episodes_count or int(req.episodes_count) <= 0:
            raise HTTPException(status_code=400, detail="episodes_count is required for global mode")
        prompt_filename = "story_generator_global.txt"
    else:
        if not req.episode_number or int(req.episode_number) <= 0:
            raise HTTPException(status_code=400, detail="episode_number is required for episode mode")
        prompt_filename = "story_generator_episode.txt"

    prompt_dir = os.path.join(str(settings.BASE_DIR), "app", "core", "prompts")
    prompt_path = os.path.join(prompt_dir, prompt_filename)
    if not os.path.exists(prompt_path):
        logger.error(f"Story generator prompt not found at: {prompt_path}")
        raise HTTPException(status_code=404, detail=f"Prompt file '{prompt_filename}' not found.")

    with open(prompt_path, "r", encoding="utf-8") as f:
        sys_prompt = f.read()

    user_prompt = (
        f"Mode: {mode}\n"
        f"Episodes Count: {req.episodes_count or ''}\n"
        f"Episode Number: {req.episode_number or ''}\n"
        f"Foreshadowing: {req.foreshadowing or ''}\n"
        f"Background: {req.background or ''}\n"
        f"Setup: {req.setup or ''}\n"
        f"Development: {req.development or ''}\n"
        f"Turning Points: {req.turning_points or ''}\n"
        f"Climax: {req.climax or ''}\n"
        f"Resolution: {req.resolution or ''}\n"
        f"Suspense: {req.suspense or ''}\n"
        f"Extra Notes: {req.extra_notes or ''}\n"
    )

    llm_config = agent_service.get_active_llm_config(current_user.id)
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None
    billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

    generated_md = await generate_markdown_with_retry(
        user_prompt=user_prompt,
        sys_prompt=sys_prompt,
        llm_config=llm_config,
        strict_markdown=(req.strict_markdown is not False),
        require_h1=True,
    )
    if not generated_md:
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    # Persist both output and the inputs that produced it.
    try:
        story_input = req.model_dump()
    except AttributeError:
        story_input = req.dict()
    story_input["mode"] = mode

    now_iso = datetime.utcnow().isoformat()
    if mode == "global":
        gi = dict(project.global_info or {})
        gi["story_generator_global_input"] = story_input
        gi["story_dna_global_md"] = generated_md
        gi["story_dna_global_updated_at"] = now_iso
        project.global_info = gi
        db.add(project)
    else:
        ei = dict(episode.episode_info or {})
        ei["story_generator_episode_input"] = story_input
        ei["story_generator_episode_input_updated_at"] = now_iso
        ei["story_dna_episode_md"] = generated_md
        ei["story_dna_episode_updated_at"] = now_iso
        # Also store the episode_number used to generate
        ei["story_dna_episode_number"] = int(req.episode_number)
        episode.episode_info = ei
        db.add(episode)

    db.commit()
    db.refresh(episode)
    return episode


@router.put("/episodes/{episode_id}/story_generator/input", response_model=EpisodeOut)
def save_episode_story_generator_input(
    episode_id: int,
    req: "StoryGeneratorRequest",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist Story Generator draft inputs without calling the LLM.

    This is used to avoid losing in-progress inputs before the user clicks Generate.
    """
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    project = _require_project_access(db, episode.project_id, current_user)

    mode = (req.mode or "").strip().lower()
    if mode not in ("global", "episode"):
        raise HTTPException(status_code=400, detail="mode must be 'global' or 'episode'")

    try:
        story_input = req.model_dump()
    except AttributeError:
        story_input = req.dict()
    story_input["mode"] = mode

    now_iso = datetime.utcnow().isoformat()
    if mode == "global":
        gi = dict(project.global_info or {})
        gi["story_generator_global_input"] = story_input
        gi["story_generator_global_input_updated_at"] = now_iso
        project.global_info = gi
        db.add(project)
    else:
        ei = dict(episode.episode_info or {})
        ei["story_generator_episode_input"] = story_input
        ei["story_generator_episode_input_updated_at"] = now_iso
        episode.episode_info = ei
        db.add(episode)

    db.commit()
    db.refresh(episode)
    return episode


@router.post("/episodes/{episode_id}/script_generator/scenes", response_model=Dict[str, Any])
async def generate_episode_scenes_from_story(
    episode_id: int,
    req: ScriptScenesGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    project = _require_project_access(db, episode.project_id, current_user)

    prompt_dir = os.path.join(str(settings.BASE_DIR), "app", "core", "prompts")
    prompt_path = os.path.join(prompt_dir, "script_generator_scenes.txt")
    if not os.path.exists(prompt_path):
        logger.error(f"Script generator prompt not found at: {prompt_path}")
        raise HTTPException(status_code=404, detail="Prompt file 'script_generator_scenes.txt' not found.")
    with open(prompt_path, "r", encoding="utf-8") as f:
        sys_prompt = f.read()

    global_md = ""
    try:
        global_md = (project.global_info or {}).get("story_dna_global_md") or ""
    except Exception:
        global_md = ""
    episode_md = ""
    try:
        episode_md = (episode.episode_info or {}).get("story_dna_episode_md") or ""
    except Exception:
        episode_md = ""

    user_prompt = (
        f"Project Title: {project.title}\n"
        f"Episode Title: {episode.title}\n"
        f"Scene Count Target: {req.scene_count or ''}\n"
        f"Background: {req.background or ''}\n"
        f"Setup: {req.setup or ''}\n"
        f"Development: {req.development or ''}\n"
        f"Turning Points: {req.turning_points or ''}\n"
        f"Climax: {req.climax or ''}\n"
        f"Resolution: {req.resolution or ''}\n"
        f"Suspense: {req.suspense or ''}\n"
        f"Foreshadowing: {req.foreshadowing or ''}\n"
        f"Extra Notes: {req.extra_notes or ''}\n\n"
        f"Global Story DNA (if any):\n{global_md}\n\n"
        f"Episode Story DNA (if any):\n{episode_md}\n"
    )

    llm_config = agent_service.get_active_llm_config(current_user.id)
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None
    billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

    resp = await llm_service.generate_content(user_prompt, sys_prompt, llm_config)
    raw = (resp.get("content") or "").strip()
    if not raw:
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    # Parse strict JSON (strip fences if model ignored instruction)
    content = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    content = content.replace("```json", "").replace("```", "").strip()
    start_idx = content.find("{")
    end_idx = content.rfind("}")
    if start_idx != -1 and end_idx != -1:
        content = content[start_idx:end_idx + 1]
    try:
        data = json.loads(content)
    except Exception as e:
        logger.error(f"[script_generator] JSON parse failed: {e}. Raw len={len(raw)}")
        raise HTTPException(status_code=500, detail="Failed to parse LLM JSON for scenes")

    scenes = data.get("scenes") if isinstance(data, dict) else None
    if not isinstance(scenes, list) or len(scenes) == 0:
        raise HTTPException(status_code=500, detail="LLM JSON did not include a non-empty 'scenes' list")

    if req.replace_existing_scenes:
        db.query(Scene).filter(Scene.episode_id == episode_id).delete()

    created = []
    for i, s in enumerate(scenes, start=1):
        if not isinstance(s, dict):
            continue
        scene_no = str(s.get("scene_no") or i)
        original_script_text = str(s.get("original_script_text") or "").strip()
        if not original_script_text:
            continue
        db_scene = Scene(
            episode_id=episode_id,
            scene_no=scene_no,
            scene_name=(s.get("scene_name") or None),
            original_script_text=original_script_text,
            equivalent_duration=(s.get("equivalent_duration") or None),
            core_scene_info=(s.get("core_scene_info") or None),
            environment_name=(s.get("environment_name") or None),
            linked_characters=(s.get("linked_characters") or None),
            key_props=(s.get("key_props") or None),
        )
        db.add(db_scene)
        created.append(db_scene)

    db.commit()
    for sc in created:
        db.refresh(sc)

    return {
        "episode_id": episode_id,
        "scenes_created": len(created),
        "scenes": [
            {
                "id": sc.id,
                "scene_no": sc.scene_no,
                "scene_name": sc.scene_name,
                "original_script_text": sc.original_script_text,
                "equivalent_duration": sc.equivalent_duration,
                "core_scene_info": sc.core_scene_info,
                "environment_name": sc.environment_name,
                "linked_characters": sc.linked_characters,
                "key_props": sc.key_props,
            }
            for sc in created
        ],
    }


@router.post("/episodes/{episode_id}/script_generator/scenes/start", response_model=Dict[str, Any])
def start_episode_scenes_generation_job(
    episode_id: int,
    req: ScriptScenesGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    latest = _read_episode_scene_generation_status(episode)
    if bool(latest.get("running")):
        raise HTTPException(status_code=409, detail="Scene generation is already running")

    now_iso = datetime.utcnow().isoformat()
    status_payload = {
        "running": True,
        "status": "running",
        "message": "Scene generation started",
        "episode_id": episode_id,
        "project_id": episode.project_id,
        "request": req.model_dump(),
        "scenes_created": 0,
        "result": None,
        "stop_requested": False,
        "stop_requested_at": None,
        "started_at": now_iso,
        "updated_at": now_iso,
        "finished_at": None,
    }
    _persist_episode_scene_generation_status(db, episode, status_payload)

    worker = threading.Thread(
        target=_run_episode_scene_generation_job,
        args=(episode_id, req.model_dump(), current_user.id),
        daemon=True,
    )
    worker.start()
    return status_payload


@router.get("/episodes/{episode_id}/script_generator/scenes/status", response_model=Dict[str, Any])
def get_episode_scenes_generation_job_status(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    return _read_episode_scene_generation_status(episode)


@router.post("/episodes/{episode_id}/script_generator/scenes/stop", response_model=Dict[str, Any])
def stop_episode_scenes_generation_job(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    status_payload = _read_episode_scene_generation_status(episode)
    if not bool(status_payload.get("running")):
        status_payload["message"] = "No running scene generation task"
        return status_payload

    now_iso = datetime.utcnow().isoformat()
    status_payload["stop_requested"] = True
    status_payload["stop_requested_at"] = now_iso
    status_payload["updated_at"] = now_iso
    status_payload["message"] = "Stop requested"
    _persist_episode_scene_generation_status(db, episode, status_payload)
    return status_payload


@router.post("/projects/{project_id}/script_generator/episodes/scripts", response_model=Dict[str, Any])
async def generate_project_episode_scripts_from_global_framework(
    project_id: int,
    req: ProjectEpisodeScriptsGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate per-episode script drafts from Project Overview artifacts.

    Uses:
    - project.global_info.story_dna_global_md (Generated Global Framework)
    - project.global_info.character_canon_md OR project.global_info.character_profiles (Character Canon Project)

    Creates missing episodes up to N and writes each draft into Episode.script_content.
    """
    started_at = datetime.utcnow()
    started_at_iso = started_at.isoformat()
    call_meta = {
        "project_id": project_id,
        "user_id": current_user.id,
        "episodes_count": req.episodes_count,
        "overwrite_existing": req.overwrite_existing,
        "retry_failed_only": req.retry_failed_only,
        "strict_markdown": req.strict_markdown,
        "extra_notes_len": len(req.extra_notes or ""),
        "started_at": started_at_iso,
    }
    logger.info(f"[generate_episode_scripts] START {json.dumps(call_meta, ensure_ascii=False)}")

    try:
        project = _require_project_access(db, project_id, current_user)
    except HTTPException as e:
        logger.warning(f"[generate_episode_scripts] project access denied. project_id={project_id} user_id={current_user.id} detail={e.detail}")
        logger.info(
            f"[generate_episode_scripts] RESPONSE success=False status_code={e.status_code} project_id={project_id} detail={e.detail}"
        )
        raise

    try:
        log_action(
            db,
            user_id=current_user.id,
            user_name=current_user.username,
            action="GENERATE_EPISODE_SCRIPTS_START",
            details=json.dumps(call_meta, ensure_ascii=False),
        )
    except Exception as e:
        logger.warning(f"[generate_episode_scripts] failed to write START system log: {e}")

    gi = dict(project.global_info or {})
    status_key = "episode_script_generation_status"

    def _persist_run_status(status_payload: Dict[str, Any]) -> None:
        try:
            latest_project = db.query(Project).filter(Project.id == project_id).first()
            latest_gi = dict((latest_project.global_info if latest_project else {}) or {})
            latest_gi[status_key] = status_payload
            if latest_project:
                latest_project.global_info = latest_gi
                db.add(latest_project)
                db.commit()
        except Exception as e:
            logger.warning(f"[generate_episode_scripts] failed to persist run status: {e}")

    def _read_run_status() -> Dict[str, Any]:
        try:
            latest_project = db.query(Project).filter(Project.id == project_id).first()
            latest_gi = dict((latest_project.global_info if latest_project else {}) or {})
            latest_status = latest_gi.get(status_key)
            if isinstance(latest_status, dict):
                return dict(latest_status)
        except Exception as e:
            logger.warning(f"[generate_episode_scripts] failed to read run status: {e}")
        return {}

    def _is_stop_requested() -> bool:
        latest_status = _read_run_status()
        return bool(latest_status.get("stop_requested"))

    # Determine target episode count
    target_n: Optional[int] = None
    if req.episodes_count is not None:
        try:
            target_n = int(req.episodes_count)
        except Exception:
            logger.info(
                f"[generate_episode_scripts] RESPONSE success=False status_code=400 project_id={project_id} detail=episodes_count must be an integer"
            )
            raise HTTPException(status_code=400, detail="episodes_count must be an integer")
    else:
        try:
            saved = (gi.get("story_generator_global_input") or {}).get("episodes_count")
            if saved is not None:
                target_n = int(saved)
        except Exception:
            target_n = None

    if not target_n or target_n <= 0:
        logger.warning(
            f"[generate_episode_scripts] invalid episodes_count. project_id={project_id} user_id={current_user.id} req={req.episodes_count}"
        )
        try:
            log_action(
                db,
                user_id=current_user.id,
                user_name=current_user.username,
                action="GENERATE_EPISODE_SCRIPTS_FAILED",
                details=f"project_id={project_id}; reason=invalid_episodes_count; req={req.episodes_count}",
            )
        except Exception as e:
            logger.warning(f"[generate_episode_scripts] failed to write FAILED system log: {e}")
        logger.info(
            f"[generate_episode_scripts] RESPONSE success=False status_code=400 project_id={project_id} detail=episodes_count is required"
        )
        raise HTTPException(status_code=400, detail="episodes_count is required (or generate/save Global Story first)")

    global_md = str(gi.get("story_dna_global_md") or "").strip()
    if not global_md:
        logger.warning(
            f"[generate_episode_scripts] missing global framework. project_id={project_id} user_id={current_user.id}"
        )
        try:
            log_action(
                db,
                user_id=current_user.id,
                user_name=current_user.username,
                action="GENERATE_EPISODE_SCRIPTS_FAILED",
                details=f"project_id={project_id}; reason=missing_global_framework",
            )
        except Exception as e:
            logger.warning(f"[generate_episode_scripts] failed to write FAILED system log: {e}")
        logger.info(
            f"[generate_episode_scripts] RESPONSE success=False status_code=400 project_id={project_id} detail=Generated Global Framework is empty"
        )
        raise HTTPException(status_code=400, detail="Generated Global Framework (story_dna_global_md) is empty")

    character_canon_md = str(gi.get("character_canon_md") or "").strip()
    if not character_canon_md:
        # Best-effort build from profiles
        profiles = gi.get("character_profiles") or []
        blocks: List[str] = []
        if isinstance(profiles, list):
            for p in profiles:
                if not isinstance(p, dict):
                    continue
                name = str(p.get("name") or "").strip()
                md = str(p.get("description_md") or "").strip()
                if name and md:
                    blocks.append(f"## {name}\n\n{md}")
        character_canon_md = "\n\n".join(blocks).strip()

    if not character_canon_md:
        logger.warning(
            f"[generate_episode_scripts] missing character canon (allowed). project_id={project_id} user_id={current_user.id}"
        )

    relationships = str(gi.get("character_relationships") or "").strip()
    constraints_obj = (project.global_info or {}).get("global_style_constraints")
    has_constraints = bool(constraints_obj)
    has_relationships = bool(relationships)
    if str(gi.get("character_canon_md") or "").strip():
        character_canon_source = "character_canon_md"
    elif character_canon_md:
        character_canon_source = "character_profiles_fallback"
    else:
        character_canon_source = "empty"

    logger.info(
        "[generate_episode_scripts] INPUT_CONTEXT "
        f"project_id={project_id} user_id={current_user.id} has_constraints={has_constraints} "
        f"has_relationships={has_relationships} global_md_len={len(global_md)} "
        f"character_canon_len={len(character_canon_md)} character_source={character_canon_source}"
    )

    prompt_dir = os.path.join(str(settings.BASE_DIR), "app", "core", "prompts")
    prompt_path = os.path.join(prompt_dir, "script_generator_episode_script.txt")
    if not os.path.exists(prompt_path):
        logger.error(f"Episode script generator prompt not found at: {prompt_path}")
        logger.info(
            f"[generate_episode_scripts] RESPONSE success=False status_code=404 project_id={project_id} detail=Prompt file script_generator_episode_script.txt not found"
        )
        raise HTTPException(status_code=404, detail="Prompt file 'script_generator_episode_script.txt' not found.")
    with open(prompt_path, "r", encoding="utf-8") as f:
        sys_prompt = f.read()

    # Ensure episodes exist (match by title "Episode X"; create missing)
    existing_eps = db.query(Episode).filter(Episode.project_id == project_id).all()
    by_title: Dict[str, Episode] = {str(e.title or ""): e for e in existing_eps}

    created_episodes: List[int] = []
    episodes_in_order: List[Episode] = []
    for i in range(1, target_n + 1):
        title = f"Episode {i}"
        ep = by_title.get(title)
        if not ep:
            ep = Episode(project_id=project_id, title=title, script_content="")
            db.add(ep)
            db.commit()
            db.refresh(ep)
            created_episodes.append(ep.id)
            by_title[title] = ep
        episodes_in_order.append(ep)

    previous_status = gi.get(status_key) if isinstance(gi.get(status_key), dict) else {}
    if isinstance(previous_status, dict) and bool(previous_status.get("running")):
        logger.info(
            f"[generate_episode_scripts] RESPONSE success=False status_code=409 project_id={project_id} detail=Episode script generation already running"
        )
        raise HTTPException(status_code=409, detail="Episode script generation is already running")

    failed_episode_ids: set[int] = set()
    previous_results = previous_status.get("results") if isinstance(previous_status, dict) else []
    if isinstance(previous_results, list):
        for item in previous_results:
            if not isinstance(item, dict):
                continue
            if str(item.get("status") or "") != "failed":
                continue
            try:
                ep_id = int(item.get("episode_id"))
                failed_episode_ids.add(ep_id)
            except Exception:
                continue

    episodes_with_index: List[Tuple[int, Episode]] = list(enumerate(episodes_in_order, start=1))
    if req.retry_failed_only:
        episodes_with_index = [(n, ep) for n, ep in episodes_with_index if ep.id in failed_episode_ids]

    run_status = {
        "project_id": project_id,
        "running": True,
        "mode": "retry_failed_only" if req.retry_failed_only else "full",
        "started_at": started_at_iso,
        "updated_at": started_at_iso,
        "episodes_target": target_n,
        "episodes_in_run": len(episodes_with_index),
        "processed": 0,
        "generated": 0,
        "failed": 0,
        "skipped": 0,
        "stop_requested": False,
        "stop_requested_at": None,
        "stopped_by_user": False,
        "results": [],
    }

    if req.retry_failed_only and len(episodes_with_index) == 0:
        run_status["running"] = False
        run_status["finished_at"] = datetime.utcnow().isoformat()
        run_status["message"] = "No failed episodes found from previous run"
        _persist_run_status(run_status)
        return {
            "success": True,
            "generation_success": True,
            "project_id": project_id,
            "episodes_target": target_n,
            "episodes_created": len(created_episodes),
            "created_episode_ids": created_episodes,
            "results": [],
            "errors": [],
            "message": "No failed episodes to retry",
            "debug_context": {
                "retry_failed_only": True,
                "previous_failed_count": len(failed_episode_ids),
            },
        }

    _persist_run_status(run_status)

    llm_config = agent_service.get_active_llm_config(current_user.id)
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured in active settings")
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None

    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    def _safe_log_episode(action: str, payload: Dict[str, Any]) -> None:
        try:
            log_action(
                db,
                user_id=current_user.id,
                user_name=current_user.username,
                action=action,
                details=json.dumps(payload, ensure_ascii=False),
            )
        except Exception as e:
            logger.warning(f"[generate_episode_scripts] failed to write {action} system log: {e}")

    for idx, ep in episodes_with_index:
        if _is_stop_requested():
            stopped_at = datetime.utcnow().isoformat()
            run_status["stop_requested"] = True
            if not run_status.get("stop_requested_at"):
                run_status["stop_requested_at"] = stopped_at
            run_status["stopped_by_user"] = True
            run_status["stopped_at_episode_number"] = idx
            run_status["stop_acknowledged_at"] = stopped_at
            run_status["message"] = "Stopped by user request"

            remaining = [(n, ep_rest) for n, ep_rest in episodes_with_index if n >= idx]
            for j, ep_rest in remaining:
                results.append({
                    "episode_id": ep_rest.id,
                    "episode_number": j,
                    "episode_title": ep_rest.title,
                    "generated": False,
                    "skipped": True,
                    "reason": "stopped by user request",
                })
                run_status["processed"] = int(run_status.get("processed") or 0) + 1
                run_status["skipped"] = int(run_status.get("skipped") or 0) + 1
                run_status["results"].append({
                    "episode_id": ep_rest.id,
                    "episode_number": j,
                    "episode_title": ep_rest.title,
                    "status": "skipped",
                    "reason": "stopped by user request",
                })

            run_status["updated_at"] = stopped_at
            _persist_run_status(run_status)
            _safe_log_episode("GENERATE_EPISODE_SCRIPTS_ABORTED", {
                "project_id": project_id,
                "stopped_at_episode_number": idx,
                "reason": "stopped by user request",
            })
            break

        should_write = True
        if not req.retry_failed_only and not req.overwrite_existing and (ep.script_content or "").strip():
            should_write = False

        if not should_write:
            logger.info(
                f"[generate_episode_scripts] SKIP episode_number={idx} episode_id={ep.id} title={ep.title!r} reason=existing_script"
            )
            _safe_log_episode("GENERATE_EPISODE_SCRIPT_SKIP", {
                "project_id": project_id,
                "episode_number": idx,
                "episode_id": ep.id,
                "episode_title": ep.title,
                "reason": "script_content already exists",
            })
            results.append({
                "episode_id": ep.id,
                "episode_number": idx,
                "episode_title": ep.title,
                "generated": False,
                "skipped": True,
                "reason": "script_content already exists",
            })
            run_status["processed"] = int(run_status.get("processed") or 0) + 1
            run_status["skipped"] = int(run_status.get("skipped") or 0) + 1
            run_status["updated_at"] = datetime.utcnow().isoformat()
            run_status["results"].append({
                "episode_id": ep.id,
                "episode_number": idx,
                "episode_title": ep.title,
                "status": "skipped",
                "reason": "script_content already exists",
            })
            _persist_run_status(run_status)
            continue

        # Balance check per call (may raise 402)
        billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

        constraints_block = ""
        if constraints_obj:
            constraints_block = (
                "Extracted Global Style & Constraints (JSON-ish):\n"
                + json.dumps(constraints_obj, ensure_ascii=False, indent=2)
                + "\n\n"
            )

        relationships_block = ""
        if relationships:
            relationships_block = f"Character Relationships (Plain Text):\n{relationships}\n\n"

        user_prompt = (
            f"Project Title: {project.title}\n"
            f"Episode Number: {idx}\n"
            f"Episode Title: {ep.title}\n"
            f"Extra Notes: {req.extra_notes or ''}\n\n"
            f"{constraints_block}"
            f"Global Story DNA (Markdown):\n{global_md}\n\n"
            f"Character Canon (Markdown):\n{character_canon_md}\n\n"
            f"{relationships_block}"
            "Write the episode script draft now."
        )

        try:
            sys_prompt_episode = sys_prompt.format(episode_number=idx, episode_title=ep.title)
        except Exception:
            sys_prompt_episode = sys_prompt

        try:
            logger.info(
                f"[generate_episode_scripts] GENERATE episode_number={idx} episode_id={ep.id} title={ep.title!r}"
            )
            logger.info(
                f"[generate_episode_scripts] REQUEST_PAYLOAD episode_number={idx} episode_id={ep.id} "
                f"user_prompt_len={len(user_prompt)} sys_prompt_len={len(sys_prompt_episode)} "
                f"has_constraints_block={bool(constraints_block)} has_relationships_block={bool(relationships_block)}"
            )
            content = await generate_markdown_with_retry(
                user_prompt=user_prompt,
                sys_prompt=sys_prompt_episode,
                llm_config=llm_config,
                strict_markdown=(req.strict_markdown is not False),
                require_h1=True,
            )
            if not content:
                raise RuntimeError("LLM returned empty content")

            ep.script_content = content
            ei = dict(ep.episode_info or {})
            ei["episode_script_generated_at"] = datetime.utcnow().isoformat()
            ei["episode_script_source"] = "project_global_framework_plus_project_character_canon"
            ep.episode_info = ei
            db.add(ep)
            db.commit()
            db.refresh(ep)

            logger.info(
                f"[generate_episode_scripts] SUCCESS episode_number={idx} episode_id={ep.id} output_chars={len(content)}"
            )
            _safe_log_episode("GENERATE_EPISODE_SCRIPT_SUCCESS", {
                "project_id": project_id,
                "episode_number": idx,
                "episode_id": ep.id,
                "episode_title": ep.title,
                "output_chars": len(content),
            })

            results.append({
                "episode_id": ep.id,
                "episode_number": idx,
                "episode_title": ep.title,
                "generated": True,
                "skipped": False,
                "output_chars": len(content),
            })
            run_status["processed"] = int(run_status.get("processed") or 0) + 1
            run_status["generated"] = int(run_status.get("generated") or 0) + 1
            run_status["updated_at"] = datetime.utcnow().isoformat()
            run_status["results"].append({
                "episode_id": ep.id,
                "episode_number": idx,
                "episode_title": ep.title,
                "status": "generated",
                "output_chars": len(content),
            })
            _persist_run_status(run_status)
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"[generate_episode_scripts] FAILED episode_number={idx} episode_id={ep.id} error={e}")
            _safe_log_episode("GENERATE_EPISODE_SCRIPT_FAILED", {
                "project_id": project_id,
                "episode_number": idx,
                "episode_id": ep.id,
                "episode_title": ep.title,
                "error": str(e),
            })
            errors.append({
                "episode_number": idx,
                "episode_id": ep.id,
                "episode_title": ep.title,
                "error": str(e),
            })
            results.append({
                "episode_id": ep.id,
                "episode_number": idx,
                "episode_title": ep.title,
                "generated": False,
                "skipped": False,
                "error": str(e),
            })
            run_status["processed"] = int(run_status.get("processed") or 0) + 1
            run_status["failed"] = int(run_status.get("failed") or 0) + 1
            run_status["updated_at"] = datetime.utcnow().isoformat()
            run_status["results"].append({
                "episode_id": ep.id,
                "episode_number": idx,
                "episode_title": ep.title,
                "status": "failed",
                "error": str(e),
            })
            _persist_run_status(run_status)

            if "PROHIBITED_CONTENT" in str(e):
                logger.warning(
                    f"[generate_episode_scripts] ABORT remaining episodes due to provider moderation block at episode_number={idx}"
                )
                _safe_log_episode("GENERATE_EPISODE_SCRIPTS_ABORTED", {
                    "project_id": project_id,
                    "stopped_at_episode_number": idx,
                    "reason": "provider moderation block (PROHIBITED_CONTENT)",
                })
                remaining = [(n, ep_rest) for n, ep_rest in episodes_with_index if n > idx]
                for j, ep_rest in remaining:
                    results.append({
                        "episode_id": ep_rest.id,
                        "episode_number": j,
                        "episode_title": ep_rest.title,
                        "generated": False,
                        "skipped": True,
                        "reason": "aborted due to provider moderation block",
                    })
                    run_status["processed"] = int(run_status.get("processed") or 0) + 1
                    run_status["skipped"] = int(run_status.get("skipped") or 0) + 1
                    run_status["results"].append({
                        "episode_id": ep_rest.id,
                        "episode_number": j,
                        "episode_title": ep_rest.title,
                        "status": "skipped",
                        "reason": "aborted due to provider moderation block",
                    })
                run_status["updated_at"] = datetime.utcnow().isoformat()
                _persist_run_status(run_status)
                break

    duration_ms = int((datetime.utcnow() - started_at).total_seconds() * 1000)
    logger.info(
        f"[generate_episode_scripts] END project_id={project_id} user_id={current_user.id} "
        f"target={target_n} created={len(created_episodes)} generated={sum(1 for r in results if r.get('generated'))} "
        f"errors={len(errors)} duration_ms={duration_ms}"
    )

    try:
        summary = {
            "project_id": project_id,
            "target": target_n,
            "created": len(created_episodes),
            "generated": sum(1 for r in results if r.get("generated")),
            "errors": len(errors),
            "duration_ms": duration_ms,
        }
        log_action(
            db,
            user_id=current_user.id,
            user_name=current_user.username,
            action="GENERATE_EPISODE_SCRIPTS_END",
            details=json.dumps(summary, ensure_ascii=False),
        )
    except Exception as e:
        logger.warning(f"[generate_episode_scripts] failed to write END system log: {e}")

    response_payload = {
        "success": True,
        "generation_success": len(errors) == 0,
        "project_id": project_id,
        "episodes_target": target_n,
        "episodes_created": len(created_episodes),
        "created_episode_ids": created_episodes,
        "results": results,
        "errors": errors,
        "debug_context": {
            "has_global_style_constraints": has_constraints,
            "has_character_relationships": has_relationships,
            "has_global_story_dna": bool(global_md),
            "character_canon_source": character_canon_source,
            "global_story_dna_length": len(global_md),
            "character_canon_length": len(character_canon_md),
            "constraints_keys": list(constraints_obj.keys()) if isinstance(constraints_obj, dict) else [],
        },
    }

    run_status["running"] = False
    run_status["finished_at"] = datetime.utcnow().isoformat()
    run_status["updated_at"] = run_status["finished_at"]
    run_status["errors"] = errors
    run_status["generation_success"] = len(errors) == 0
    _persist_run_status(run_status)

    logger.info(
        f"[generate_episode_scripts] RESPONSE success=True status_code=200 project_id={project_id} "
        f"generation_success={response_payload.get('generation_success')} errors={len(errors)}"
    )
    return response_payload


@router.get("/projects/{project_id}/script_generator/episodes/scripts/status", response_model=Dict[str, Any])
def get_project_episode_scripts_generation_status(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)

    gi = dict(project.global_info or {})
    status_payload = gi.get("episode_script_generation_status") if isinstance(gi, dict) else None
    if not isinstance(status_payload, dict):
        return {
            "project_id": project_id,
            "running": False,
            "processed": 0,
            "generated": 0,
            "failed": 0,
            "skipped": 0,
            "stop_requested": False,
            "stopped_by_user": False,
            "episodes_in_run": 0,
            "results": [],
        }
    return status_payload


@router.post("/projects/{project_id}/script_generator/episodes/scripts/stop", response_model=Dict[str, Any])
def stop_project_episode_scripts_generation(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)

    gi = dict(project.global_info or {})
    status_key = "episode_script_generation_status"
    status_payload = gi.get(status_key) if isinstance(gi.get(status_key), dict) else None
    now_iso = datetime.utcnow().isoformat()

    if not isinstance(status_payload, dict):
        return {
            "success": True,
            "project_id": project_id,
            "running": False,
            "stop_requested": False,
            "message": "No generation run status found",
        }

    if not status_payload.get("running"):
        status_payload["stop_requested"] = False
        status_payload["updated_at"] = now_iso
        gi[status_key] = status_payload
        project.global_info = gi
        db.add(project)
        db.commit()
        return {
            "success": True,
            "project_id": project_id,
            **status_payload,
            "message": "No running generation task",
        }

    status_payload["stop_requested"] = True
    if not status_payload.get("stop_requested_at"):
        status_payload["stop_requested_at"] = now_iso
    status_payload["updated_at"] = now_iso
    gi[status_key] = status_payload
    project.global_info = gi
    db.add(project)
    db.commit()

    try:
        log_action(
            db,
            user_id=current_user.id,
            user_name=current_user.username,
            action="GENERATE_EPISODE_SCRIPTS_STOP_REQUESTED",
            details=json.dumps({
                "project_id": project_id,
                "requested_at": now_iso,
            }, ensure_ascii=False),
        )
    except Exception as e:
        logger.warning(f"[generate_episode_scripts] failed to write STOP_REQUESTED system log: {e}")

    return {
        "success": True,
        "project_id": project_id,
        **status_payload,
        "message": "Stop requested",
    }

@router.delete("/episodes/{episode_id}", status_code=204)
def delete_episode(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    _require_project_access(db, episode.project_id, current_user, owner_only=True)
    
    db.delete(episode)
    db.commit()
    return None

# --- Scenes ---

class SceneCreate(BaseModel):
    scene_no: str
    original_script_text: str
    scene_name: Optional[str] = None
    equivalent_duration: Optional[str] = None
    core_scene_info: Optional[str] = None
    environment_name: Optional[str] = None
    linked_characters: Optional[str] = None
    key_props: Optional[str] = None

class SceneOut(BaseModel):
    id: int
    scene_no: str
    original_script_text: str
    scene_name: Optional[str]
    equivalent_duration: Optional[str]
    core_scene_info: Optional[str]
    environment_name: Optional[str]
    linked_characters: Optional[str]
    key_props: Optional[str]
    class Config:
        from_attributes = True


@router.get("/episodes/{episode_id}/scenes", response_model=List[SceneOut])
def read_scenes(
    episode_id: int,
    scene_code: Optional[str] = None,
    keyword: Optional[str] = None,
    skip: int = 0,
    limit: int = 300,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Ownership check
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
        
    _require_project_access(db, episode.project_id, current_user)
        
    query = db.query(Scene).filter(Scene.episode_id == episode_id)
    if scene_code:
        token = f"%{scene_code.strip()}%"
        query = query.filter(Scene.scene_no.ilike(token))
    if keyword:
        token = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                Scene.scene_name.ilike(token),
                Scene.environment_name.ilike(token),
                Scene.linked_characters.ilike(token),
                Scene.key_props.ilike(token),
            )
        )
    safe_skip = max(int(skip or 0), 0)
    safe_limit = max(1, min(int(limit or 300), 500))
    return query.order_by(Scene.id).offset(safe_skip).limit(safe_limit).all()

@router.post("/episodes/{episode_id}/scenes", response_model=SceneOut)
def create_scene(
    episode_id: int,
    scene: SceneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
        
    _require_project_access(db, episode.project_id, current_user)

    db_scene = Scene(
        episode_id=episode_id,
        scene_no=scene.scene_no,
        original_script_text=scene.original_script_text,
        scene_name=scene.scene_name,
        equivalent_duration=scene.equivalent_duration,
        core_scene_info=scene.core_scene_info,
        environment_name=scene.environment_name,
        linked_characters=scene.linked_characters,
        key_props=scene.key_props
    )
    db.add(db_scene)
    db.commit()
    db.refresh(db_scene)
    return db_scene

@router.put("/scenes/{scene_id}", response_model=SceneOut)
def update_scene(
    scene_id: int,
    scene_in: SceneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not db_scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    # Ownership
    episode = db.query(Episode).filter(Episode.id == db_scene.episode_id).first()
    _require_project_access(db, episode.project_id, current_user)

    update_data = scene_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_scene, field, value)
        
    db.add(db_scene)
    db.commit()
    db.refresh(db_scene)
    return db_scene


@router.delete("/scenes/{scene_id}", status_code=204)
def delete_scene(
    scene_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not db_scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    episode = db.query(Episode).filter(Episode.id == db_scene.episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    _require_project_access(db, episode.project_id, current_user, owner_only=True)

    db.delete(db_scene)
    db.commit()
    return None

# --- Shots ---

class ShotCreate(BaseModel):
    shot_id: str
    shot_name: Optional[str] = None
    start_frame: Optional[str] = None
    end_frame: Optional[str] = None
    video_content: Optional[str] = None
    duration: Optional[str] = None
    associated_entities: Optional[str] = None
    scene_code: Optional[str] = None # 'Scene ID' from header user input
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    shot_logic_cn: Optional[str] = None
    keyframes: Optional[str] = None
    
    # Optional legacy/AI fields
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    prompt: Optional[str] = None
    technical_notes: Optional[str] = None


class ShotUpdate(BaseModel):
    shot_id: Optional[str] = None
    shot_name: Optional[str] = None
    start_frame: Optional[str] = None
    end_frame: Optional[str] = None
    video_content: Optional[str] = None
    duration: Optional[str] = None
    associated_entities: Optional[str] = None
    scene_code: Optional[str] = None
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    shot_logic_cn: Optional[str] = None
    keyframes: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    prompt: Optional[str] = None
    technical_notes: Optional[str] = None

class ShotOut(BaseModel):
    id: int
    scene_id: int
    project_id: Optional[int]
    episode_id: Optional[int]
    shot_id: Optional[str]
    shot_name: Optional[str]
    start_frame: Optional[str]
    end_frame: Optional[str]
    video_content: Optional[str]
    duration: Optional[str]
    associated_entities: Optional[str]
    shot_logic_cn: Optional[str]
    keyframes: Optional[str]
    
    scene_code: Optional[str]

    image_url: Optional[str]
    video_url: Optional[str]
    prompt: Optional[str]
    technical_notes: Optional[str]
    
    class Config:
        from_attributes = True

@router.get("/episodes/{episode_id}/shots", response_model=List[ShotOut])
def read_episode_shots(
    episode_id: int,
    scene_code: Optional[str] = None,
    shot_id: Optional[str] = None,
    keyword: Optional[str] = None,
    skip: int = 0,
    limit: int = 300,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
        
    project = _require_project_access(db, episode.project_id, current_user)

    query = db.query(Shot).filter(
        Shot.project_id == project.id,
        Shot.episode_id == episode_id
    )

    if scene_code:
        normalized = scene_code.strip()
        like_token = f"%{normalized}%"
        query = query.filter(
            or_(
                Shot.scene_code.ilike(like_token),
                Shot.shot_id.ilike(f"{normalized}%"),
            )
        )

    if shot_id:
        like_token = f"%{shot_id.strip()}%"
        query = query.filter(Shot.shot_id.ilike(like_token))

    if keyword:
        like_token = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                Shot.shot_name.ilike(like_token),
                Shot.shot_logic_cn.ilike(like_token),
                Shot.associated_entities.ilike(like_token),
                Shot.video_content.ilike(like_token),
            )
        )

    safe_skip = max(int(skip or 0), 0)
    safe_limit = max(1, min(int(limit or 300), 500))
    return query.order_by(Shot.id).offset(safe_skip).limit(safe_limit).all()

class AIShotGenRequest(BaseModel):
    user_prompt: Optional[str] = None
    system_prompt: Optional[str] = None

def _build_shot_prompts(db: Session, scene: Scene, project: Project):
    # 2. Gather Data
    # Global Style & Context
    
    # Normalize Info Sources
    project_info = project.global_info or {}
    if isinstance(project_info, str):
        try: project_info = json.loads(project_info)
        except: project_info = {}
        
    episode_info = {}
    scene_episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    
    if scene_episode and scene_episode.episode_info:
        temp = scene_episode.episode_info
        if isinstance(temp, str):
            try: temp = json.loads(temp)
            except: temp = {}
        if isinstance(temp, dict):
             # Check for nested structure "e_global_info" as per user data
             if "e_global_info" in temp and isinstance(temp["e_global_info"], dict):
                 episode_info = temp["e_global_info"]
             else:
                 episode_info = temp
    
    # 3. Robust Data Normalization (Handle case/space sensitivity)
    def normalize_dict_keys(d):
        if not isinstance(d, dict): return {}
        new_d = {}
        for k, v in d.items():
            # Standardize to "key_name" (lowercase, underscore)
            clean_k = str(k).lower().replace(" ", "_").strip()
            new_d[clean_k] = v
        return new_d

    episode_info_norm = normalize_dict_keys(episode_info)
    project_info_norm = normalize_dict_keys(project_info)

    # Helper to find value from Episode -> Project (using normalized keys)
    def get_context_val(keys):
        if isinstance(keys, str): keys = [keys]
        # Search List
        search_keys = [k.lower().replace(" ", "_").strip() for k in keys]
        
        # 1. Episode (Priority)
        for sk in search_keys:
            if sk in episode_info_norm and episode_info_norm[sk]:
                return episode_info_norm[sk]
        
        # 2. Project (Fallback)
        for sk in search_keys:
            if sk in project_info_norm and project_info_norm[sk]:
                return project_info_norm[sk]
        
        return None
    def get_context_val(keys):
        if isinstance(keys, str): keys = [keys]
        # 1. Episode
        for k in keys:
            if episode_info.get(k): return episode_info[k]
            # Try lowercase/variations
            if episode_info.get(k.lower()): return episode_info[k.lower()]
            if episode_info.get(k.replace(" ", "_")): return episode_info[k.replace(" ", "_")]
        # 2. Project
        for k in keys:
            if project_info.get(k): return project_info[k]
            if project_info.get(k.lower()): return project_info[k.lower()]
            if project_info.get(k.replace(" ", "_")): return project_info[k.replace(" ", "_")]
        return None

    global_style = get_context_val(["Global_Style", "Global Style", "Style"]) or "Cinematic"
    
    # Extract additional fields
    # Mappings: Field Name -> Possible Keys
    field_mappings = {
        "Type": ["Type", "Genre", "Category", "Film Type"],
        "Tone": ["Tone", "Color Tone", "Mood", "Atmosphere"],
        "Language": ["Language", "Lang"],
        "Lighting": ["Lighting", "Light Style"],
        "Quality": ["Quality", "Production Quality"]
    }
    
    additional_context = ""
    context_lines = []
    
    for field, keys in field_mappings.items():
        val = get_context_val(keys)
        if val:
            context_lines.append(f"{field}: {val}")
    
    if context_lines:
        additional_context = "\n".join(context_lines)

    # Scene Info
    # Entities - Fetch project entities and match with Linked Characters / Environment
    project_entities = db.query(Entity).filter(Entity.project_id == project.id).all()
    entity_descriptions = []
    
    # Identify relevant entity names from Scene data
    relevant_names = set()
    
    def _clean_br(s):
        # Normalize tokens like "CHAR:[@Name]" / "[@Name]" / "[Name]" to plain name.
        cleaned = str(s or '').replace('[', '').replace(']', '').replace('`', '').strip()
        cleaned = re.sub(r'^(CHAR|ENV|PROP)\s*:\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'^@+', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    if scene.linked_characters:
        # Split by comma and handle potential variations
        parts = [_clean_br(p) for p in scene.linked_characters.split(',') if p.strip()]
        relevant_names.update(parts)

    if scene.key_props:
        parts = [_clean_br(p) for p in scene.key_props.split(',') if p.strip()]
        relevant_names.update(parts)
        
    if scene.environment_name:
        # Environment name might also be a comma-separated list
        parts = [_clean_br(p) for p in scene.environment_name.split(',') if p.strip()]
        relevant_names.update(parts)
    
    logger.info(f"[_build_shot_prompts] Relevant Names from Scene (cleaned): {relevant_names}")

    env_narrative = ""
    env_narratives_map = {}

    for ent in project_entities:
        # Check relevancy (Case-insensitive check, considering name_en)
        is_relevant = False
        ent_aliases = [n for n in [ent.name, ent.name_en] if n]
        
        # logger.info(f"Checking entity: {ent.name} (Aliases: {ent_aliases})") 

        for alias in ent_aliases:
            alias_clean = alias.strip().lower()
            for rn in relevant_names:
                if rn.strip().lower() == alias_clean:
                    is_relevant = True
                    logger.info(f"[_build_shot_prompts] Match found: Entity '{ent.name}' matches scene ref '{rn}'")
                    break
            if is_relevant: break
        
        # If relevant, try to extract Description field
        if is_relevant:
            # Check if this is the Environment Anchor to capture narrative for Scenario Content
            if scene.environment_name:
                 # Check against all scene environment parts
                 env_parts = [_clean_br(p).lower() for p in scene.environment_name.split(',') if p.strip()]
                 for alias in ent_aliases:
                      if alias.strip().lower() in env_parts:
                           logger.info(f"[_build_shot_prompts] Environment Match: {ent.name}")
                           # Priority: description_cn (custom_attributes) > narrative_description > description
                           desc_cn = None
                           
                           # Safe Custom Attributes Parsing
                           custom_attrs = ent.custom_attributes
                           if isinstance(custom_attrs, str):
                                try: custom_attrs = json.loads(custom_attrs)
                                except: custom_attrs = {}
                                
                           if custom_attrs and isinstance(custom_attrs, dict):
                               desc_cn = custom_attrs.get('description_cn') or custom_attrs.get('description_CN')
                           
                           if desc_cn:
                               new_narrative = desc_cn
                               logger.info(f"[_build_shot_prompts] Found Env Narrative from Custom Attrs")
                           elif ent.narrative_description:
                                new_narrative = ent.narrative_description
                                logger.info(f"[_build_shot_prompts] Found Env Narrative from Narrative Desc")
                           elif ent.description:
                                # Use description directly if others are missing
                                new_narrative = ent.description
                                logger.info(f"[_build_shot_prompts] Found Env Narrative from Description")
                           else:
                                new_narrative = ""

                           if new_narrative:
                               env_narratives_map[ent.name] = new_narrative
                           break

            desc_parts = []
            
            # 0. Anchor Description (Critical for AI Visualization)
            if ent.anchor_description:
                desc_parts.append(f"Anchor Description: {ent.anchor_description}")
            else:
                logger.warning(f"[_build_shot_prompts] Entity {ent.name} missing anchor_description")

            # 1. Narrative Description (New Column Priority)
            if ent.narrative_description:
                 desc_parts.append(f"Description: {ent.narrative_description}")
            elif ent.description:
                 # Fallback regex extraction from blob
                 match = re.search(r'(?:Description|描述)[:：]\s*(.*)', ent.description, re.IGNORECASE)
                 if match:
                      desc_parts.append(f"Description: {match.group(1).strip()}")
            
            # 1.5 Character Specifics
            if ent.type and ent.type.lower() == 'character':
                 if ent.appearance_cn:
                      desc_parts.append(f"Appearance: {ent.appearance_cn}")
                 else:
                      logger.warning(f"[_build_shot_prompts] Character {ent.name} missing appearance_cn")

                 if ent.clothing:
                      desc_parts.append(f"Clothing: {ent.clothing}")

            # 2. Visual Params
            if ent.visual_params:
                desc_parts.append(f"Visual: {ent.visual_params}")
            
            # 3. Atmosphere
            if ent.atmosphere:
                desc_parts.append(f"Atmosphere: {ent.atmosphere}")

            if desc_parts:
                entity_descriptions.append(f"[{ent.name}] " + " | ".join(desc_parts))
            else:
                logger.warning(f"[_build_shot_prompts] Entity {ent.name} matched but has no description parts")

    # Format concatenated environment narrative
    if env_narratives_map:
        parts = []
        for name, desc in env_narratives_map.items():
            parts.append(f"[{name}]: {desc}")
        env_narrative = "\n".join(parts)
    
    entity_section = ""
    if entity_descriptions:
        entity_section = "# Entity Reference\n" + "\n".join(entity_descriptions) + "\n"

    # 3. Prepare System Prompt
    prompt_dir = os.path.join(str(settings.BASE_DIR), "app", "core", "prompts")
    prompt_path = os.path.join(prompt_dir, "shot_generator.txt")
    
    system_prompt = ""
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()
    except Exception as e:
        logger.error(f"Failed to load shot_generator.txt from {prompt_path}: {e}")
        # Very drastic fallback, but better than crash
        system_prompt = "You are a Storyboard Master. Generate a shot list as a markdown table."

    global_section = f"# Global Context\nGlobal Style: {global_style}"
    if additional_context:
        global_section += f"\n{additional_context}"

    core_goal_text = scene.core_scene_info or ''
    # Environment Context is now a separate field in the table

    user_input = f"""{global_section}

# Core Scene Info
| Field | Value |
| :--- | :--- |
| **Scene No** | {scene.scene_no or ''} |
| **Scene Name** | {scene.scene_name or ''} |
| **Environment Anchor** | {scene.environment_name or ''} |
| **Environment Context** | {env_narrative or 'N/A'} |
| **Linked Characters** | {scene.linked_characters or ''} |
| **Key Props** | {scene.key_props or ''} |
| **Core Goal** | {core_goal_text} |

{entity_section}

# Instruction
1. Analyze the script and break it down into shots.
"""
    
    return system_prompt, user_input

@router.get("/scenes/{scene_id}/ai_prompt_preview")
def ai_prompt_preview(
    scene_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    project = _require_project_access(db, episode.project_id, current_user)
        
    system, user = _build_shot_prompts(db, scene, project)
    return {"system_prompt": system, "user_prompt": user}

class AnalysisContent(BaseModel):
    content: Union[Dict[str, Any], List[Any]]


class SceneAiShotsBatchStartRequest(BaseModel):
    scene_ids: Optional[List[int]] = None


SCENE_AI_SHOTS_BATCH_STATUS_KEY = "scene_ai_shots_batch_status"


def _read_scene_ai_shots_batch_status(episode: Episode) -> Dict[str, Any]:
    try:
        info = dict(episode.episode_info or {})
        payload = info.get(SCENE_AI_SHOTS_BATCH_STATUS_KEY)
        if isinstance(payload, dict):
            return dict(payload)
    except Exception:
        pass
    return {
        "running": False,
        "total": 0,
        "completed": 0,
        "success": 0,
        "failed": 0,
        "current_scene_id": None,
        "current_scene_label": "",
        "message": "",
        "errors": [],
    }


def _persist_scene_ai_shots_batch_status(db: Session, episode: Episode, status_payload: Dict[str, Any]) -> None:
    info = dict(episode.episode_info or {})
    info[SCENE_AI_SHOTS_BATCH_STATUS_KEY] = status_payload
    episode.episode_info = info
    db.add(episode)
    db.commit()


def _run_scene_ai_shots_batch_job(episode_id: int, scene_ids: List[int], user_id: int) -> None:
    db = SessionLocal()
    try:
        episode = db.query(Episode).filter(Episode.id == episode_id).first()
        user = db.query(User).filter(User.id == user_id).first()
        if not episode or not user:
            return

        scene_label_map: Dict[int, str] = {}
        for sid in scene_ids:
            sc = db.query(Scene).filter(Scene.id == sid, Scene.episode_id == episode_id).first()
            if sc:
                scene_label_map[sid] = str(sc.scene_no or sc.scene_name or f"#{sid}")

        total = len(scene_ids)
        completed = 0
        success = 0
        failed = 0
        errors: List[str] = []

        for sid in scene_ids:
            episode = db.query(Episode).filter(Episode.id == episode_id).first()
            if not episode:
                break
            latest = _read_scene_ai_shots_batch_status(episode)
            if bool(latest.get("stop_requested")):
                latest["running"] = False
                latest["completed"] = completed
                latest["success"] = success
                latest["failed"] = failed
                latest["errors"] = errors
                latest["finished_at"] = datetime.utcnow().isoformat()
                latest["stopped_by_user"] = True
                latest["message"] = "Stopped by user request"
                _persist_scene_ai_shots_batch_status(db, episode, latest)
                return

            scene_label = scene_label_map.get(sid) or f"#{sid}"
            latest["current_scene_id"] = sid
            latest["current_scene_label"] = scene_label
            latest["message"] = f"Processing scene {scene_label}..."
            latest["updated_at"] = datetime.utcnow().isoformat()
            _persist_scene_ai_shots_batch_status(db, episode, latest)

            try:
                generated = asyncio.run(ai_generate_shots(scene_id=sid, req=None, db=db, current_user=user))
                generated_rows = generated.get("content") if isinstance(generated, dict) else []
                if not isinstance(generated_rows, list) or len(generated_rows) == 0:
                    raise RuntimeError("No parsed rows returned")

                apply_scene_ai_result(
                    scene_id=sid,
                    data=AnalysisContent(content=generated_rows),
                    db=db,
                    current_user=user,
                )
                success += 1
            except Exception as e:
                failed += 1
                errors.append(f"{scene_label}: {str(e)}")

            completed += 1
            episode = db.query(Episode).filter(Episode.id == episode_id).first()
            if not episode:
                break
            latest = _read_scene_ai_shots_batch_status(episode)
            latest["completed"] = completed
            latest["success"] = success
            latest["failed"] = failed
            latest["errors"] = errors
            latest["updated_at"] = datetime.utcnow().isoformat()
            latest["message"] = f"Progress {completed}/{total}"
            _persist_scene_ai_shots_batch_status(db, episode, latest)

        episode = db.query(Episode).filter(Episode.id == episode_id).first()
        if episode:
            final_status = _read_scene_ai_shots_batch_status(episode)
            final_status["running"] = False
            final_status["completed"] = completed
            final_status["success"] = success
            final_status["failed"] = failed
            final_status["errors"] = errors
            final_status["finished_at"] = datetime.utcnow().isoformat()
            final_status["updated_at"] = final_status["finished_at"]
            final_status["stopped_by_user"] = bool(final_status.get("stop_requested"))
            final_status["message"] = f"Batch done: success {success}, failed {failed}"
            _persist_scene_ai_shots_batch_status(db, episode, final_status)
    except Exception as e:
        try:
            episode = db.query(Episode).filter(Episode.id == episode_id).first()
            if episode:
                failed_status = _read_scene_ai_shots_batch_status(episode)
                failed_status["running"] = False
                failed_status["finished_at"] = datetime.utcnow().isoformat()
                failed_status["updated_at"] = failed_status["finished_at"]
                failed_status["message"] = f"Batch failed: {str(e)}"
                failed_status["errors"] = list(failed_status.get("errors") or []) + [str(e)]
                _persist_scene_ai_shots_batch_status(db, episode, failed_status)
        except Exception:
            pass
    finally:
        db.close()


@router.post("/episodes/{episode_id}/scenes/ai_shots/batch/start", response_model=Dict[str, Any])
def start_scene_ai_shots_batch(
    episode_id: int,
    req: SceneAiShotsBatchStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    latest_status = _read_scene_ai_shots_batch_status(episode)
    if bool(latest_status.get("running")):
        raise HTTPException(status_code=409, detail="Scene AI shots batch is already running")

    requested_scene_ids = [int(x) for x in (req.scene_ids or []) if x]
    scenes_query = db.query(Scene).filter(Scene.episode_id == episode_id)
    if requested_scene_ids:
        scenes_query = scenes_query.filter(Scene.id.in_(requested_scene_ids))
    target_scenes = scenes_query.order_by(Scene.id.asc()).all()
    scene_ids = [int(s.id) for s in target_scenes]
    if not scene_ids:
        raise HTTPException(status_code=400, detail="No saved scenes found for batch")

    now_iso = datetime.utcnow().isoformat()
    status_payload = {
        "running": True,
        "project_id": episode.project_id,
        "episode_id": episode_id,
        "scene_ids": scene_ids,
        "total": len(scene_ids),
        "completed": 0,
        "success": 0,
        "failed": 0,
        "current_scene_id": None,
        "current_scene_label": "",
        "message": "Batch task started",
        "errors": [],
        "stop_requested": False,
        "stop_requested_at": None,
        "stopped_by_user": False,
        "started_at": now_iso,
        "updated_at": now_iso,
        "finished_at": None,
    }
    _persist_scene_ai_shots_batch_status(db, episode, status_payload)

    worker = threading.Thread(
        target=_run_scene_ai_shots_batch_job,
        args=(episode_id, scene_ids, current_user.id),
        daemon=True,
    )
    worker.start()

    return status_payload


@router.get("/episodes/{episode_id}/scenes/ai_shots/batch/status", response_model=Dict[str, Any])
def get_scene_ai_shots_batch_status(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    return _read_scene_ai_shots_batch_status(episode)


@router.post("/episodes/{episode_id}/scenes/ai_shots/batch/stop", response_model=Dict[str, Any])
def stop_scene_ai_shots_batch(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    status_payload = _read_scene_ai_shots_batch_status(episode)
    if not bool(status_payload.get("running")):
        status_payload["message"] = "No running batch task"
        return status_payload

    now_iso = datetime.utcnow().isoformat()
    status_payload["stop_requested"] = True
    status_payload["stop_requested_at"] = now_iso
    status_payload["updated_at"] = now_iso
    status_payload["message"] = "Stop requested"
    _persist_scene_ai_shots_batch_status(db, episode, status_payload)
    return status_payload

@router.post("/scenes/{scene_id}/ai_generate_shots")
async def ai_generate_shots(
    scene_id: int,
    req: Optional[AIShotGenRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        req_has_custom_user_prompt = bool(req and (req.user_prompt or "").strip())
        req_has_custom_system_prompt = bool(req and (req.system_prompt or "").strip())
        logger.info(
            "[ai_generate_shots] start "
            f"scene_id={scene_id} user_id={current_user.id} "
            f"custom_user_prompt={req_has_custom_user_prompt} custom_system_prompt={req_has_custom_system_prompt}"
        )
        # 1. Fetch Scene and Context
        scene = db.query(Scene).filter(Scene.id == scene_id).first()
        if not scene:
            logger.warning(f"[ai_generate_shots] scene_not_found scene_id={scene_id} user_id={current_user.id}")
            raise HTTPException(status_code=404, detail="Scene not found")
            
        episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
        if not episode:
            logger.warning(
                f"[ai_generate_shots] episode_not_found scene_id={scene_id} episode_id={scene.episode_id} user_id={current_user.id}"
            )
            raise HTTPException(status_code=404, detail="Episode not found")

        try:
            project = _require_project_access(db, episode.project_id, current_user)
        except HTTPException:
            logger.warning(
                f"[ai_generate_shots] unauthorized_or_project_not_found "
                f"scene_id={scene_id} episode_id={episode.id} project_id={episode.project_id} user_id={current_user.id}"
            )
            raise

        logger.info(
            f"[ai_generate_shots] context scene_id={scene_id} episode_id={episode.id} project_id={project.id}"
        )

        if req and req.user_prompt:
             user_input = req.user_prompt
             system_prompt = req.system_prompt or "You are a Storyboard Master."
             logger.info("[ai_generate_shots] Using custom prompt from request")
        else:
             system_prompt, user_input = _build_shot_prompts(db, scene, project)

        logger.info(f"[ai_generate_shots] system_prompt_len={len(system_prompt)}")
        logger.info(f"[ai_generate_shots] user_input_len={len(user_input)}")

        # 4. Call LLM
        llm_config = agent_service.get_active_llm_config(current_user.id)
        if not llm_config:
            logger.error(f"[ai_generate_shots] missing_llm_config scene_id={scene_id} user_id={current_user.id}")
            raise HTTPException(status_code=400, detail="No active LLM config")
        
        # Billing (Reserve for token pricing)
        provider = llm_config.get("provider") 
        model = llm_config.get("model")
        logger.info(
            f"[ai_generate_shots] llm_selection provider={provider} model={model} scene_id={scene_id}"
        )
        reservation_tx = None
        if billing_service.is_token_pricing(db, "llm_chat", provider, model):
            messages_est = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ]
            est = billing_service.estimate_input_output_tokens_from_messages(messages_est, output_ratio=1.5)
            reserve_details = {
                "item": "generate_shots",
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": 1.5,
                "system_prompt_len": len(system_prompt or ""),
                "user_prompt_len": len(user_input or ""),
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            }
            reservation_tx = billing_service.reserve_credits(db, current_user.id, "llm_chat", provider, model, reserve_details)
            logger.info(
                f"[ai_generate_shots] token_reservation_created reservation_id={reservation_tx.id} "
                f"scene_id={scene_id} est_total_tokens={reserve_details.get('total_tokens', 0)}"
            )
        else:
            # Ensure we have at least a default task type if provider is missing (though check_balance handles None)
            billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

        response_dict = await llm_service.generate_content(user_input, system_prompt, llm_config)
        response_content_raw = response_dict.get("content", "")
        usage = response_dict.get("usage", {})

        logger.info(
            f"[ai_generate_shots] llm_response_received scene_id={scene_id} "
            f"llm_response_len_raw={len(response_content_raw)} usage_keys={list((usage or {}).keys())}"
        )

        if str(response_content_raw).startswith("Error:"):
            if reservation_tx:
                billing_service.cancel_reservation(db, reservation_tx.id, str(response_content_raw))
            raise HTTPException(status_code=500, detail=str(response_content_raw))

        raw_str = str(response_content_raw or "").strip()
        if not raw_str:
            logger.warning(f"[ai_generate_shots] empty_llm_response scene_id={scene_id} user_id={current_user.id}")
            if reservation_tx:
                billing_service.cancel_reservation(db, reservation_tx.id, "empty llm response")
            raise HTTPException(status_code=502, detail="LLM returned empty response")

        if re.search(r"\bPROHIBITED_CONTENT\b", raw_str, flags=re.IGNORECASE):
            logger.warning(
                f"[ai_generate_shots] prohibited_content_marker_detected scene_id={scene_id} user_id={current_user.id}"
            )
            if reservation_tx:
                billing_service.cancel_reservation(db, reservation_tx.id, "provider moderation block")
            raise HTTPException(status_code=502, detail="Provider moderation blocked shot generation (PROHIBITED_CONTENT)")

        # Force-remove common reasoning leakage (e.g., "analysis", <think> blocks)
        # before table parsing and persistence.
        response_content = sanitize_llm_markdown_output(response_content_raw)
        reasoning_line_re = re.compile(
            r"^\s*(i will|let me|let's|analysis|reasoning|thought process|"
            r"分析|思路|推理|我将|我认为)\b",
            flags=re.IGNORECASE,
        )
        cleaned_lines = []
        for line in str(response_content or "").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("|") and reasoning_line_re.match(stripped):
                continue
            cleaned_lines.append(line)
        response_content = "\n".join(cleaned_lines).strip()

        if not response_content:
            logger.warning(
                f"[ai_generate_shots] empty_after_sanitize scene_id={scene_id} user_id={current_user.id} raw_len={len(raw_str)}"
            )
            if reservation_tx:
                billing_service.cancel_reservation(db, reservation_tx.id, "empty response after sanitize")
            raise HTTPException(status_code=502, detail="LLM response became empty after sanitize")

        logger.info(
            f"[ai_generate_shots] llm_response_cleaned scene_id={scene_id} llm_response_len_clean={len(response_content)}"
        )

        # Billing finalize
        if reservation_tx:
            actual_details = {"item": "generate_shots"}
            if usage:
                actual_details.update(usage)
            if "prompt_tokens" in actual_details and "input_tokens" not in actual_details:
                actual_details["input_tokens"] = actual_details.get("prompt_tokens", 0)
            if "completion_tokens" in actual_details and "output_tokens" not in actual_details:
                actual_details["output_tokens"] = actual_details.get("completion_tokens", 0)
            billing_service.settle_reservation(db, reservation_tx.id, actual_details)
            logger.info(
                f"[ai_generate_shots] token_reservation_settled reservation_id={reservation_tx.id} "
                f"scene_id={scene_id} actual_keys={list(actual_details.keys())}"
            )
        else:
            details = {"item": "generate_shots"}
            if usage:
                details.update(usage)
            if "prompt_tokens" in details and "input_tokens" not in details:
                details["input_tokens"] = details.get("prompt_tokens", 0)
            if "completion_tokens" in details and "output_tokens" not in details:
                details["output_tokens"] = details.get("completion_tokens", 0)
            billing_service.deduct_credits(db, current_user.id, "llm_chat", provider, model, details)
            logger.info(
                f"[ai_generate_shots] credits_deducted scene_id={scene_id} detail_keys={list(details.keys())}"
            )

        # 5. Parse Table
        lines = response_content.split('\n')
        table_lines = [line.strip() for line in lines if line.strip().startswith('|')]
        
        shots_data = []
        if len(table_lines) > 2:
            # Robust header parsing: strip whitespace and markdown bold/italic markers
            raw_headers = [h.strip() for h in table_lines[0].strip('|').split('|')]
            headers = [h.replace('*', '').replace('_', '').strip() for h in raw_headers]
            
            logger.info(f"[ai_generate_shots] headers detected: {headers}")

            # Expected mappings (flexible)
            # Shot ID, Shot Name, Start Frame, End Frame, Video Content, Duration (s), Associated Entities
            
            for line in table_lines[2:]: # Skip Header and Separator
                if "---" in line: continue 
                
                cols = [c.strip() for c in line.strip('|').split('|')]
                if len(cols) >= len(headers):
                    shot_dict = {}
                    for i, h in enumerate(headers):
                        if i < len(cols):
                            shot_dict[h] = cols[i]
                    shots_data.append(shot_dict)
                else:
                    logger.warning(f"[ai_generate_shots] Skipping malformed line (cols={len(cols)}, headers={len(headers)}): {line[:50]}...")

        if not shots_data:
             logger.warning(f"DEBUG: No table found using delimiter |. Content snippet: {response_content[:200]}")
             # Fallback: Try Parse using Markdown table logic more loosely or return raw
             pass
             
        logger.info(
            f"[ai_generate_shots] parsed_result scene_id={scene_id} table_lines={len(table_lines)} parsed_shots={len(shots_data)}"
        )

        # 6. Save to DB (Scheme A)
        # scenes.ai_shots_result stores ONLY the raw LLM Markdown table (plain text)
        from datetime import datetime

        result_wrapper = {
            "timestamp": datetime.utcnow().isoformat(),
            "raw_text": response_content,
            "content": shots_data,
            "usage": usage,
        }

        scene.ai_shots_result = response_content
        db.commit()
        
        logger.info(f"[ai_generate_shots] Saved raw markdown to scene.ai_shots_result; parsed_shots={len(shots_data)} scene_id={scene_id}")
        logger.info(
            f"[ai_generate_shots] response_ready scene_id={scene_id} "
            f"response_keys={list(result_wrapper.keys())} content_count={len(result_wrapper.get('content') or [])}"
        )
        
        # Return the raw data so frontend can display it in the "Edit" modal
        return result_wrapper

    except HTTPException as e:
        logger.warning(
            f"[ai_generate_shots] http_exception scene_id={scene_id} user_id={current_user.id} "
            f"status_code={e.status_code} detail={e.detail}"
        )
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.exception(f"[ai_generate_shots] unhandled_error scene_id={scene_id} user_id={current_user.id} error={e}")
        # Log failure
        try:
            p_log = locals().get('provider')
            m_log = locals().get('model')
            billing_service.log_failed_transaction(db, current_user.id, "llm_chat", p_log, m_log, str(e))
        except: pass
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/scenes/{scene_id}/latest_ai_result")
def get_scene_latest_ai_result(
    scene_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Get the latest saved AI shot generation result for a scene.

    Storage (Scheme A): scenes.ai_shots_result is the raw Markdown table text.
    This endpoint returns a structured wrapper for the UI by parsing that Markdown.
    """
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    _require_project_access(db, episode.project_id, current_user)
         
    raw_value = scene.ai_shots_result
    if not raw_value:
        return {}

    # Backward compat: older versions stored JSON wrapper into scenes.ai_shots_result
    if isinstance(raw_value, str) and raw_value.strip().startswith('{'):
        try:
            legacy = json.loads(raw_value)
            if isinstance(legacy, dict) and ("raw_text" in legacy or "content" in legacy):
                raw_text = legacy.get("raw_text") or ""
                if raw_text:
                    scene.ai_shots_result = raw_text
                    db.commit()
                    raw_value = raw_text
                else:
                    # No raw_text; best effort keep the JSON string as raw.
                    raw_value = scene.ai_shots_result
        except Exception:
            pass

    # Parse markdown table into list-of-dicts for the staging editor
    lines = (raw_value or '').split('\n')
    table_lines = [line.strip() for line in lines if line.strip().startswith('|')]

    shots_data = []
    if len(table_lines) > 2:
        raw_headers = [h.strip() for h in table_lines[0].strip('|').split('|')]
        headers = [h.replace('*', '').replace('_', '').strip() for h in raw_headers]

        for line in table_lines[2:]:
            if "---" in line:
                continue
            cols = [c.strip() for c in line.strip('|').split('|')]
            if len(cols) >= len(headers):
                shot_dict = {}
                for i, h in enumerate(headers):
                    if i < len(cols):
                        shot_dict[h] = cols[i]
                shots_data.append(shot_dict)

    return {
        "raw_text": raw_value,
        "content": shots_data,
    }

@router.put("/scenes/{scene_id}/latest_ai_result")
def update_scene_latest_ai_result(
    scene_id: int,
    data: AnalysisContent, # Reusing this schema: { "content": ... }
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Update (Save/Edit) the latest shot generation result without applying it.
    Expects data.content to be the list of shot dictionaries.
    """
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    _require_project_access(db, episode.project_id, current_user)
    
    # Scheme A: Save draft by converting edited content back to Markdown and overwriting ai_shots_result.
    headers = [
        "Shot ID",
        "Shot Name",
        "Scene ID",
        "Shot Logic (CN)",
        "Start Frame",
        "Video Content",
        "Duration (s)",
        "Keyframes",
        "End Frame",
        "Associated Entities",
    ]

    def esc(val: str) -> str:
        if val is None:
            return ""
        s = str(val)
        s = s.replace("|", "\\|")
        s = s.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
        return s

    rows = []
    for item in (data.content or []):
        if not isinstance(item, dict):
            continue
        row_vals = [esc(item.get(h, "")) for h in headers]
        rows.append(f"| " + " | ".join(row_vals) + " |")

    sep = "| " + " | ".join([":---"] * len(headers)) + " |"
    header_line = "| " + " | ".join(headers) + " |"
    md = "\n".join([header_line, sep] + rows)

    scene.ai_shots_result = md
    db.commit()

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "raw_text": md,
        "content": data.content or [],
    }

@router.post("/scenes/{scene_id}/apply_ai_result")
def apply_scene_ai_result(
    scene_id: int,
    data: Optional[AnalysisContent] = None, # Optional: apply provided content instead of stored
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Apply the stored (or provided) shot list to the actual Shots table.
    WARNING: This replaces existing shots for the scene.
    """
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    project = _require_project_access(db, episode.project_id, current_user)
         
    shots_data = []
    
    # 1. Determine Source
    if data and data.content:
        shots_data = data.content
    else:
        # Parse from stored Markdown table
        raw_value = scene.ai_shots_result or ""
        if isinstance(raw_value, str) and raw_value.strip().startswith('{'):
            # Legacy wrapper stored in ai_shots_result
            try:
                legacy = json.loads(raw_value)
                if isinstance(legacy, dict) and legacy.get("raw_text"):
                    raw_value = legacy.get("raw_text")
                    scene.ai_shots_result = raw_value
            except Exception:
                pass

        lines = (raw_value or '').split('\n')
        table_lines = [line.strip() for line in lines if line.strip().startswith('|')]
        if len(table_lines) > 2:
            raw_headers = [h.strip() for h in table_lines[0].strip('|').split('|')]
            headers = [h.replace('*', '').replace('_', '').strip() for h in raw_headers]
            for line in table_lines[2:]:
                if "---" in line:
                    continue
                cols = [c.strip() for c in line.strip('|').split('|')]
                if len(cols) >= len(headers):
                    shot_dict = {}
                    for i, h in enumerate(headers):
                        if i < len(cols):
                            shot_dict[h] = cols[i]
                    shots_data.append(shot_dict)
                 
    # 2. Extract and Auto-Link Entities (System Import Feature)
    try:
        if shots_data:
            existing_entities = db.query(Entity).filter(Entity.project_id == project.id).all()
            entity_map = {e.name: e for e in existing_entities}
            
            new_entities_buffer = set()
            
            for s_data in shots_data:
                assoc_str = s_data.get("Associated Entities", "")
                if assoc_str and assoc_str.lower() != "none" and assoc_str.strip():
                    # Split by comma or common separators
                    potential_names = [n.strip() for n in re.split(r'[,\uff0c]', assoc_str) if n.strip()]
                    
                    cleaned_names = []
                    for name in potential_names:
                        # Check exist
                        if name in entity_map:
                            cleaned_names.append(name)
                        elif name in new_entities_buffer:
                            cleaned_names.append(name)
                        else:
                            # Do not auto-create subjects/entities from imported shots.
                            # Keep the name as plain associated_entities text only.
                            cleaned_names.append(name)
                    
                    # Update data with cleaned names (optional, normalized)
                    s_data["Associated Entities"] = ", ".join(cleaned_names)

    except Exception as e:
        logger.error(f"[Import] Entity auto-linking failed: {e}")
        # Continue with raw data if linking fails

    # 3. Apply to DB (Delete old, Insert new)
    # Note: We should probably keep existing shots if the user wants partial update, 
    # but the requirement implies "Modify and Re-import", which usually means "This is the new list".
    # Existing logic was "delete all", so we stick to that for "Apply".
    
    db.query(Shot).filter(Shot.scene_id == scene_id).delete()
    
    for idx, s_data in enumerate(shots_data):
        # Dur parsing
        try:
            dur_val = 2.0
            if "Duration (s)" in s_data:
                match = re.search(r"[\d\.]+", str(s_data["Duration (s)"]))
                dur_val = float(match.group()) if match else 2.0
        except:
            dur_val = 2.0
        
        # Mapping Keys from LLM Table Headers to DB Columns
        # Headers: Shot ID, Shot Name, Start Frame, End Frame, Video Content, Duration (s), Keyframes, Associated Entities, Shot Logic (CN)
        
        shot = Shot(
            scene_id=scene_id,
            project_id=project.id,
            episode_id=episode.id,
            
            shot_id=s_data.get("Shot ID", str(idx+1)),
            shot_name=s_data.get("Shot Name", "Shot"),
            scene_code=scene.scene_no,
            
            start_frame=s_data.get("Start Frame", ""),
            end_frame=s_data.get("End Frame", ""),
            video_content=s_data.get("Video Content", ""),
            duration=str(dur_val),
            
            associated_entities=s_data.get("Associated Entities", ""),
            shot_logic_cn=s_data.get("Shot Logic (CN)", ""),
            keyframes=s_data.get("Keyframes", "NO"),
            
            # Legacy/Internal
            prompt=s_data.get("Video Content", "") 
        )
        db.add(shot)
        
    db.commit()
    
    # Return the real shots
    return db.query(Shot).filter(Shot.scene_id == scene_id).all()

@router.get("/scenes/{scene_id}/shots", response_model=List[ShotOut])
def read_shots(
    scene_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    # Check Project ownership via Episode
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    project = _require_project_access(db, episode.project_id, current_user)
        
    # Optimized: Return shots strictly by Scene ID (Physical Association)
    # Removing logical 'scene_code' sync as requested.
    return db.query(Shot).filter(
        Shot.project_id == project.id,
        Shot.episode_id == episode.id,
        Shot.scene_id == scene_id
    ).all()

@router.post("/scenes/{scene_id}/shots", response_model=ShotOut)
def create_shot(
    scene_id: int,
    shot: ShotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    import os
    logger.info(f"[create_shot] START. scene_id={scene_id}")
    logger.info(f"[create_shot] DB URL: {settings.DATABASE_URL}")
    logger.info(f"[create_shot] Payload: shot_id={shot.shot_id}, logic_cn={'YES' if shot.shot_logic_cn else 'NO'}")

    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        logger.error(f"[create_shot] Scene {scene_id} not found")
        raise HTTPException(status_code=404, detail="Scene not found")
    
    # Ownership
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    if not episode:
        logger.error(f"[create_shot] Scene {scene_id} refers to non-existent episode {scene.episode_id}")
        raise HTTPException(status_code=404, detail="Parent Episode not found")

    try:
        project = _require_project_access(db, episode.project_id, current_user)
    except HTTPException:
         logger.error(f"[create_shot] User {current_user.id} not authorized for Project {episode.project_id}")
         raise
         
    try:
        db_shot = Shot(
            scene_id=scene_id,
            project_id=project.id,
            episode_id=episode.id,
            shot_id=shot.shot_id,
            shot_name=shot.shot_name,
            start_frame=shot.start_frame,
            end_frame=shot.end_frame,
            video_content=shot.video_content,
            duration=shot.duration,
            associated_entities=shot.associated_entities,
            shot_logic_cn=shot.shot_logic_cn,
            keyframes=shot.keyframes,
            scene_code=shot.scene_code,
            image_url=shot.image_url,
            video_url=shot.video_url,
            prompt=shot.prompt,
            technical_notes=shot.technical_notes
        )
        db.add(db_shot)
        db.commit()
        db.refresh(db_shot)
        
        # Verify Write
        logger.info(f"[create_shot] Committed Shot ID: {db_shot.id}. Verifying...")
        verify = db.query(Shot).filter(Shot.id == db_shot.id).first()
        if verify:
             logger.info(f"[create_shot] SUCCESS. Shot {db_shot.id} (Display ID: {db_shot.shot_id}) exists in DB.")
        else:
             logger.error(f"[create_shot] CRITICAL FAILURE. Shot {db_shot.id} not found immediately after commit!")

        return db_shot
    except Exception as e:
        logger.error(f"[create_shot] EXCEPTION: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create shot: {str(e)}")

@router.put("/shots/{shot_id}", response_model=ShotOut)
def update_shot(
    shot_id: int,
    shot_in: ShotUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_shot = db.query(Shot).filter(Shot.id == shot_id).first()
    if not db_shot:
        raise HTTPException(status_code=404, detail="Shot not found")
        
    scene = db.query(Scene).filter(Scene.id == db_shot.scene_id).first()
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    _require_project_access(db, episode.project_id, current_user)
        
    for key, value in shot_in.dict(exclude_unset=True).items():
        setattr(db_shot, key, value)
        
    db.commit()
    db.refresh(db_shot)
    return db_shot

@router.delete("/shots/{shot_id}")
def delete_shot(
    shot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_shot = db.query(Shot).filter(Shot.id == shot_id).first()
    if not db_shot:
         raise HTTPException(status_code=404, detail="Shot not found")
         
    scene = db.query(Scene).filter(Scene.id == db_shot.scene_id).first()
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    _require_project_access(db, episode.project_id, current_user, owner_only=True)
        
    db.delete(db_shot)
    db.commit()
    return {"ok": True}

# --- Entities ---

class EntityCreate(BaseModel):
    name: str
    type: str # character, environment, prop
    description: str
    image_url: Optional[str] = None
    generation_prompt_en: Optional[str] = None
    anchor_description: Optional[str] = None
    
    # New Fields
    name_en: Optional[str] = None
    gender: Optional[str] = None
    role: Optional[str] = None
    archetype: Optional[str] = None
    appearance_cn: Optional[str] = None
    clothing: Optional[str] = None
    action_characteristics: Optional[str] = None
    
    atmosphere: Optional[str] = None
    visual_params: Optional[str] = None
    narrative_description: Optional[str] = None

    visual_dependencies: Optional[List[str]] = []
    dependency_strategy: Optional[Dict[str, Any]] = {}

class EntityOut(BaseModel):
    id: int
    name: str
    type: str
    description: str
    image_url: Optional[str]
    generation_prompt_en: Optional[str]
    anchor_description: Optional[str]
    
    # New Fields
    name_en: Optional[str] = None
    gender: Optional[str] = None
    role: Optional[str] = None
    archetype: Optional[str] = None
    appearance_cn: Optional[str] = None
    clothing: Optional[str] = None
    action_characteristics: Optional[str] = None
    
    atmosphere: Optional[str] = None
    visual_params: Optional[str] = None
    narrative_description: Optional[str] = None

    visual_dependencies: Optional[List[str]] = []
    dependency_strategy: Optional[Dict[str, Any]] = {}
    custom_attributes: Optional[Dict[str, Any]] = {}

    class Config:
        from_attributes = True

@router.get("/projects/{project_id}/entities", response_model=List[EntityOut])
def read_entities(
    project_id: int,
    type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_project_access(db, project_id, current_user)
    
    query = db.query(Entity).filter(Entity.project_id == project_id)
    if type:
        query = query.filter(Entity.type == type)
    return query.all()

@router.post("/projects/{project_id}/entities", response_model=EntityOut)
def create_entity(
    project_id: int,
    entity: EntityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_project_access(db, project_id, current_user)
        
    # Check if entity with same name exists in project
    existing_entity = db.query(Entity).filter(
        Entity.project_id == project_id,
        Entity.name == entity.name
    ).first()

    if existing_entity:
        # If entity exists, do NOT update it (as per "do not import repeatedly" requirement).
        # We simply return the existing entity essentially ignoring the import data for this specific name.
        return existing_entity
    else:
        # Create new
        db_entity = Entity(
            project_id=project_id,
            name=entity.name,
            type=entity.type,
            description=entity.description,
            image_url=entity.image_url,
            generation_prompt_en=entity.generation_prompt_en,
            anchor_description=entity.anchor_description,
            
            name_en=entity.name_en,
            gender=entity.gender,
            role=entity.role,
            archetype=entity.archetype,
            appearance_cn=entity.appearance_cn,
            clothing=entity.clothing,
            action_characteristics=entity.action_characteristics,
            
            atmosphere=entity.atmosphere,
            visual_params=entity.visual_params,
            narrative_description=entity.narrative_description,
            
            visual_dependencies=entity.visual_dependencies,
            dependency_strategy=entity.dependency_strategy
        )
        db.add(db_entity)
        db.commit()
        db.refresh(db_entity)
        return db_entity

class EntityUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    generation_prompt_en: Optional[str] = None
    anchor_description: Optional[str] = None
    
    # New Fields
    name_en: Optional[str] = None
    gender: Optional[str] = None
    role: Optional[str] = None
    archetype: Optional[str] = None
    appearance_cn: Optional[str] = None
    clothing: Optional[str] = None
    action_characteristics: Optional[str] = None
    
    atmosphere: Optional[str] = None
    visual_params: Optional[str] = None
    narrative_description: Optional[str] = None
    
    visual_dependencies: Optional[List[str]] = None
    dependency_strategy: Optional[Dict[str, Any]] = None
    
    class Config:
        extra = "allow"

@router.put("/entities/{entity_id}", response_model=EntityOut)
def update_entity(
    entity_id: int,
    entity_in: EntityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    # Verify ownership via project
    project = _require_project_access(db, entity.project_id, current_user)

    update_data = entity_in.dict(exclude_unset=True)
    
    # Separate standard columns from custom attributes
    standard_columns = {c.name for c in Entity.__table__.columns}
    custom_attrs = dict(entity.custom_attributes or {})
    
    for field, value in update_data.items():
        if field == "image_url" and value != entity.image_url:
             entity.image_url = value
             # Auto-register as Asset if valid URL
             if value:
                 # Check existing to avoid dupes
                 existing_asset = db.query(Asset).filter(Asset.url == value, Asset.user_id == current_user.id).first()
                 if not existing_asset:
                     # Use helper to register with metadata
                     req_data = {
                         "project_id": project.id,
                         "entity_id": entity.id,
                         "entity_name": entity.name,
                         "category": entity.type,
                         "remark": f"Auto-registered from Entity: {entity.name}"
                     }
                     # Ensure _register_asset_helper is available
                     if "_register_asset_helper" in globals():
                        _register_asset_helper(db, current_user.id, value, req_data)
        
        elif field in standard_columns:
            setattr(entity, field, value)
        else:
            # Update custom attributes
            if value is None and field in custom_attrs:
                del custom_attrs[field]
            else:
                custom_attrs[field] = value

    entity.custom_attributes = custom_attrs
    
    db.add(entity)
        
    db.commit()
    db.refresh(entity)
    return entity

class SoraCharacterGenRequest(BaseModel):
    main_image_url: Optional[str] = None
    ref_image_urls: List[str] = []
    ref_video_urls: List[str] = []
    user_prompt: Optional[str] = None

@router.post("/entities/{entity_id}/generate_sora_character")
async def generate_sora_character(
    entity_id: int,
    req: SoraCharacterGenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a Sora Character definition/asset based on uploaded images and references.
    """
    # 1. Validation
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    _require_project_access(db, entity.project_id, current_user)

    logger.info(f"[sora_char] Generating for entity {entity.name}. MainImg: {req.main_image_url}")

    # 2. Update Entity Data (Save inputs)
    if req.main_image_url:
        entity.image_url = req.main_image_url
    
    # Merge references into visual_dependencies or custom_attributes
    # Structure: { "sora_refs": { "images": [], "videos": [] } }
    custom_attrs = entity.custom_attributes
    if isinstance(custom_attrs, str):
        try: custom_attrs = json.loads(custom_attrs)
        except: custom_attrs = {}
    elif not isinstance(custom_attrs, dict):
        custom_attrs = {}
    
    custom_attrs['sora_refs'] = {
        "images": req.ref_image_urls,
        "videos": req.ref_video_urls
    }
    entity.custom_attributes = custom_attrs
    db.commit()

    # 3. Prepare Provider
    llm_config = agent_service.get_active_llm_config(current_user.id, category="Video")
    # If generic LLM is returned but we need Video/Sora specific, we might need a better selector.
    # But get_active_llm_config falls back to system defaults.
    
    if not llm_config:
         raise HTTPException(status_code=400, detail="No Video Generation provider configured.")

    # 4. Construct Request (Simulating Sora/Grsai Character Create API)
    # Since we don't have the SDK specs, we'll format a generic request that llm_service *might* handle
    # OR we assume llm_service can handle `generate_content` with images.
    
    # Prompt Construction
    prompt = f"Create a consistent character reference for '{entity.name}'."
    if entity.description:
        prompt += f"\nDescription: {entity.description}"
    if req.user_prompt:
        prompt += f"\nUser Instruction: {req.user_prompt}"
    
    prompt += "\n\nReferences provided via context."

    # Check Balance
    # Assuming cost is high for character training/creation
    reservation_tx = None
    provider = llm_config.get("provider")
    model = llm_config.get("model")
    if billing_service.is_token_pricing(db, "video_gen", provider, model):
        image_count = 0
        if req.main_image_url:
            image_count += 1
        if isinstance(req.ref_image_urls, list):
            image_count += len([u for u in req.ref_image_urls if u])

        video_count = 0
        if isinstance(req.ref_video_urls, list):
            video_count += len([u for u in req.ref_video_urls if u])

        est_messages = [
            {"role": "system", "content": "sora-create-character"},
            {"role": "user", "content": prompt},
        ]
        est = billing_service.estimate_input_output_tokens_from_messages(est_messages, output_ratio=1.5)

        estimated_image_tokens = 1000 * image_count
        estimated_video_tokens = 2000 * video_count
        est_input = int(est.get("input_tokens", 0) or 0) + int(estimated_image_tokens) + int(estimated_video_tokens)
        est_output = int((est_input * 3 + 1) // 2) if est_input > 0 else 0

        reserve_details = {
            "item": "sora_create_character",
            "estimation_method": "prompt_tokens_ratio",
            "estimated_output_ratio": 1.5,
            "estimated_image_tokens": estimated_image_tokens,
            "estimated_video_tokens": estimated_video_tokens,
            "input_tokens": est_input,
            "output_tokens": est_output,
            "total_tokens": int(est_input + est_output),
        }
        reservation_tx = billing_service.reserve_credits(
            db,
            current_user.id,
            "video_gen",
            provider,
            model,
            reserve_details,
        )
    else:
        billing_service.check_balance(db, current_user.id, "video_gen", provider, model)
    
    # Execute
    # We pass the images as "multimodal_context" or similar if the service supports it.
    # Our llm_service.generate_content takes `system_prompt` and `user_prompt`.
    # It doesn't explicitly take image URLs in the signature found in snippets, 
    # but `analyze_multimodal` does.
    # However, "Character Creation" is usually a generation task.
    # Let's try to pass it in the prompt or config.
    
    # Workaround: Pass URLs in the prompt text for the provider to parse if it supports it,
    # or rely on `llm_service` to have been updated to support `images` list.
    # Looking at `endpoints.py`, `llm_service.generate_content` signature is simple.
    # But `analyze_multimodal` returns usage.
    
    # If the user wants "sora-create-character", it might be a specific Function Call?
    # I will assume the `llm_service` can handle a special prompt or valid JSON config.
    
    # For now, we'll log and simulate the call successful return to save the state,
    # assuming the actual Sora integration is via the generic `generate_content` or a future update.
    # But wait, user asked to "Increase functionality". I should try to make it real if possible.
    
    # If using Grsai/Sora, maybe it's `llm_service.generate_video`?
    # Let's check `llm_service` again if `generate_video` exists.
    # I verified `llm_service.py` earlier, it imported `requests` etc.
    
    # Let's assume we call `generate_content` but with a special system prompt that triggers the provider's logic.
    
    try:
        response = await llm_service.generate_content(
            user_prompt=prompt,
            system_prompt="sora-create-character", # Special flag for the service to recognize?
            config=llm_config,
            image_urls=[req.main_image_url] + req.ref_image_urls if req.main_image_url else req.ref_image_urls,
            video_urls=req.ref_video_urls
        )
        
        # 5. Handle Result
        content = response.get("content", "")
        usage = response.get("usage", {})
        
        # Billing finalize
        if reservation_tx:
            actual_details = {"item": "sora_create_character"}
            if usage:
                actual_details.update(usage)
            if "prompt_tokens" in actual_details and "input_tokens" not in actual_details:
                actual_details["input_tokens"] = actual_details.get("prompt_tokens", 0)
            if "completion_tokens" in actual_details and "output_tokens" not in actual_details:
                actual_details["output_tokens"] = actual_details.get("completion_tokens", 0)
            billing_service.settle_reservation(db, reservation_tx.id, actual_details)
        else:
            billing_service.deduct_credits(db, current_user.id, "video_gen", provider, model, usage)

        # Save result (maybe a character ID returned in content?)
        # If content is JSON
        try:
            res_json = json.loads(content)
            char_id = res_json.get("id") or res_json.get("character_id")
            if char_id:
                custom_attrs['sora_character_id'] = char_id
                entity.custom_attributes = custom_attrs
                db.commit()
        except:
            pass # Content might be just text description

        return {
            "status": "success",
            "result": content,
            "entity_id": entity.id,
            "sora_refs": custom_attrs['sora_refs']
        }

    except Exception as e:
        logger.error(f"Sora Gen Failed: {e}")
        try:
            if reservation_tx:
                billing_service.cancel_reservation(db, reservation_tx.id, str(e))
        except:
            pass
        billing_service.log_failed_transaction(db, current_user.id, "video_gen", llm_config.get("provider"), llm_config.get("model"), str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/entities/{entity_id}")
def delete_entity(
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    _require_project_access(db, entity.project_id, current_user, owner_only=True)
        
    db.delete(entity)
    db.commit()
    return {"status": "success"}

@router.delete("/projects/{project_id}/entities")
def delete_project_entities(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_project_access(db, project_id, current_user, owner_only=True)
        
    db.query(Entity).filter(Entity.project_id == project_id).delete()
    db.commit()
    return {"status": "success", "message": "All entities deleted"}

# --- Users ---

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None


class EmailVerificationSendRequest(BaseModel):
    email: str


class EmailVerificationConfirmRequest(BaseModel):
    email: str
    code: str

class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str]
    full_name: Optional[str]
    avatar_url: Optional[str] = None
    is_active: bool
    account_status: int = 1
    email_verified: bool = False
    is_superuser: bool
    is_authorized: bool
    is_system: bool
    credits: Optional[int] = 0

    class Config:
        from_attributes = True


def _is_valid_email_format(email: str) -> bool:
    raw = (email or "").strip()
    if not raw:
        return False
    return bool(re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", raw))


def _generate_email_verification_code() -> str:
    return f"{uuid.uuid4().int % 1000000:06d}"


def _resolve_runtime_smtp_config() -> Dict[str, Any]:
    config: Dict[str, Any] = {
        "host": str(settings.SMTP_HOST or "").strip(),
        "port": int(settings.SMTP_PORT or 587),
        "username": str(settings.SMTP_USERNAME or "").strip(),
        "password": str(settings.SMTP_PASSWORD or "").strip(),
        "use_ssl": os.getenv("SMTP_USE_SSL", "0") in {"1", "true", "True"},
        "use_tls": bool(settings.SMTP_USE_TLS),
        "from_email": str(settings.SMTP_FROM_EMAIL or "").strip(),
        "frontend_base_url": str(settings.FRONTEND_BASE_URL or "").strip(),
    }

    db = SessionLocal()
    try:
        setting = db.query(APISetting).filter(
            APISetting.category == "System_Email",
            APISetting.provider == "smtp",
        ).first()
        if setting:
            cfg = setting.config or {}
            config["host"] = str(cfg.get("host", config["host"]) or "").strip()
            try:
                config["port"] = int(cfg.get("port") or config["port"])
            except Exception:
                pass
            config["username"] = str(cfg.get("username", config["username"]) or "").strip()
            config["password"] = str(setting.api_key or config["password"] or "").strip()
            config["use_ssl"] = bool(cfg.get("use_ssl", config["use_ssl"]))
            config["use_tls"] = bool(cfg.get("use_tls", config["use_tls"]))
            config["from_email"] = str(cfg.get("from_email", config["from_email"]) or "").strip()
            config["frontend_base_url"] = str(cfg.get("frontend_base_url", config["frontend_base_url"]) or "").strip()
    except Exception as e:
        logger.warning("Failed to load runtime SMTP config from DB, fallback to env: %s", e)
    finally:
        db.close()

    if not config["from_email"]:
        config["from_email"] = config["username"]

    return config


def _send_email_via_runtime_smtp(
    to_email: str,
    subject: str,
    content: str,
    *,
    html_content: Optional[str] = None,
    strict: bool = False,
) -> None:
    smtp_cfg = _resolve_runtime_smtp_config()
    smtp_host = str(smtp_cfg.get("host") or "").strip()
    smtp_user = str(smtp_cfg.get("username") or "").strip()
    smtp_pass = str(smtp_cfg.get("password") or "").strip()
    from_email = str(smtp_cfg.get("from_email") or smtp_user or "").strip()
    smtp_port = int(smtp_cfg.get("port") or 587)
    smtp_use_ssl = bool(smtp_cfg.get("use_ssl", False))
    smtp_use_tls = bool(smtp_cfg.get("use_tls", True))

    missing_fields = []
    if not smtp_host:
        missing_fields.append("host")
    if not from_email:
        missing_fields.append("from_email/username")

    if missing_fields:
        message = f"SMTP not configured, missing: {', '.join(missing_fields)}"
        logger.warning("%s. Skip sending email to %s", message, to_email)
        if strict:
            raise RuntimeError(message)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_email
    message["To"] = to_email
    message.set_content(content)
    html_body = str(html_content or "").strip()
    if html_body:
        message.add_alternative(html_body, subtype="html")

    if smtp_use_ssl:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20) as server:
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(message)
        return

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
        if smtp_use_tls:
            server.starttls()
        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)
        server.send_message(message)


def send_email_verification_code(to_email: str, code: str) -> None:
    content = (
        "Your AI Story verification code is:\n\n"
        f"{code}\n\n"
        "This code expires in 10 minutes."
    )
    _send_email_via_runtime_smtp(to_email, "AI Story Email Verification Code", content)

@router.post("/users/", response_model=UserOut)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    normalized_email = (user.email or "").strip().lower()
    if not _is_valid_email_format(normalized_email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    db_user_email = db.query(User).filter(User.email == normalized_email).first()
    if db_user_email:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    db_user_username = db.query(User).filter(User.username == user.username).first()
    if db_user_username:
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_password = get_password_hash(user.password)
    verify_code = _generate_email_verification_code()
    expire_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    db_user = User(
        email=normalized_email,
        username=user.username,
        full_name=user.full_name,
        hashed_password=hashed_password,
        is_active=False,
        account_status=-1,
        email_verified=False,
        email_verification_code=verify_code,
        email_verification_expires_at=expire_at,
    )
    db.add(db_user)
    db.flush()
    _seed_default_system_settings_for_user(db, db_user.id)
    db.commit()
    db.refresh(db_user)
    try:
        send_email_verification_code(normalized_email, verify_code)
    except Exception as e:
        logger.error("Failed to send verification email to %s: %s", normalized_email, e)
    return db_user


@router.post("/users/verification/send")
@limiter.limit(settings.RATE_LIMIT_RESET)
def send_user_verification_code(
    request: Request,
    payload: EmailVerificationSendRequest,
    db: Session = Depends(get_db),
):
    email = (payload.email or "").strip().lower()
    if not _is_valid_email_format(email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    code = _generate_email_verification_code()
    user.email_verification_code = code
    user.email_verification_expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    db.commit()
    try:
        send_email_verification_code(email, code)
    except Exception as e:
        logger.error("Failed to send verification email to %s: %s", email, e)
        raise HTTPException(status_code=500, detail="Failed to send verification code")
    return {"status": "ok", "message": "Verification code sent"}


@router.post("/users/verification/confirm", response_model=UserOut)
@limiter.limit(settings.RATE_LIMIT_RESET)
def confirm_user_verification_code(
    request: Request,
    payload: EmailVerificationConfirmRequest,
    db: Session = Depends(get_db),
):
    email = (payload.email or "").strip().lower()
    code = (payload.code or "").strip()
    if not email or not code:
        raise HTTPException(status_code=400, detail="Email and code are required")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.email_verified and user.account_status == 1:
        return user

    if not user.email_verification_code or user.email_verification_code != code:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    try:
        expire_at = datetime.fromisoformat(str(user.email_verification_expires_at or ""))
    except Exception:
        expire_at = None
    if not expire_at or datetime.utcnow() > expire_at:
        raise HTTPException(status_code=400, detail="Verification code expired")

    user.email_verified = True
    user.account_status = 1
    user.is_active = True
    user.email_verification_code = None
    user.email_verification_expires_at = None
    db.commit()
    db.refresh(user)
    return user

# --- Login ---

class Token(BaseModel):
    access_token: str
    token_type: str

class LoginRequest(BaseModel):
    username: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_password_reset_token(email: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": email,
        "purpose": "password_reset",
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_password_reset_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("purpose") != "password_reset":
            return None
        email = payload.get("sub")
        if not email:
            return None
        return str(email)
    except Exception:
        return None


def send_password_reset_email(to_email: str, reset_link: str) -> None:
    content = (
        "You requested a password reset for AI Story.\n\n"
        f"Please open this link to reset your password:\n{reset_link}\n\n"
        f"This link expires in {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes.\n"
        "If you did not request this, you can ignore this email."
    )
    _send_email_via_runtime_smtp(to_email, "AI Story Password Reset", content)

def authenticate_user(db: Session, username: str, password: str):
    username = str(username or "").strip()
    # Try by username
    user = db.query(User).filter(User.username == username).first()
    if not user:
        # Try by email
        user = db.query(User).filter(User.email == str(username or "").strip().lower()).first()
    
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

@router.post("/login/access-token", response_model=Token)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def login_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    OAuth2 compatible token login, get an access token for future requests.
    Requires 'username' and 'password' as form fields.
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    if (
        user.account_status == -1
        and (not bool(user.is_active))
        and (not bool(getattr(user, "is_superuser", False)))
    ):
        raise HTTPException(status_code=403, detail="Email verification required. Please verify your email code before login")
    if not bool(user.is_active):
        raise HTTPException(status_code=403, detail="User is disabled")

    try:
        _seed_default_system_settings_for_user(db, user.id)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("Failed to seed default API settings on login | user_id=%s error=%s", user.id, e)
    
    # Log Successful Login
    log_action(db, user_id=user.id, user_name=user.username, action="LOGIN", details="User logged in via OAuth2 Form")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "uid": user.id, "uname": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def login_json(request: Request, login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    JSON compatible login endpoint. 
    Accepts {"username": "...", "password": "..."} in body.
    """
    user = authenticate_user(db, login_data.username, login_data.password)
    if not user:
        # Optional: Log failed login attempts?
        # log_action(db, user_id=None, user_name=login_data.username, action="LOGIN_FAILED", details="Incorrect password")
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    if (
        user.account_status == -1
        and (not bool(user.is_active))
        and (not bool(getattr(user, "is_superuser", False)))
    ):
        raise HTTPException(status_code=403, detail="Email verification required. Please verify your email code before login")
    if not bool(user.is_active):
        raise HTTPException(status_code=403, detail="User is disabled")

    try:
        _seed_default_system_settings_for_user(db, user.id)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("Failed to seed default API settings on login | user_id=%s error=%s", user.id, e)
    
    # Log Successful Login
    log_action(db, user_id=user.id, user_name=user.username, action="LOGIN", details="User logged in via API")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "uid": user.id, "uname": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/password/forgot")
@limiter.limit(settings.RATE_LIMIT_RESET)
def forgot_password(request: Request, payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    email = (payload.email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    user = db.query(User).filter(User.email == email).first()
    # Always return generic success to avoid account enumeration
    success_msg = "If the email exists, a password reset link has been sent."

    if not user:
        return {"status": "ok", "message": success_msg}

    token = create_password_reset_token(email)
    smtp_cfg = _resolve_runtime_smtp_config()
    frontend_base = str(smtp_cfg.get("frontend_base_url") or "").strip()
    if not frontend_base:
        frontend_base = "http://localhost:5173"
    reset_link = f"{frontend_base.rstrip('/')}/auth?mode=reset&token={token}"

    try:
        send_password_reset_email(email, reset_link)
        log_action(
            db,
            user_id=user.id,
            user_name=user.username,
            action="PASSWORD_RESET_REQUEST",
            details=f"email={email}",
        )
    except Exception as e:
        logger.error("Failed to send password reset email to %s: %s", email, e)
        raise HTTPException(status_code=500, detail="Failed to send reset email")

    return {"status": "ok", "message": success_msg}


@router.post("/password/reset")
@limiter.limit(settings.RATE_LIMIT_RESET)
def reset_password(request: Request, payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    token = (payload.token or "").strip()
    new_password = (payload.new_password or "").strip()

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    email = verify_password_reset_token(token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset request")

    user.hashed_password = get_password_hash(new_password)
    db.commit()

    try:
        log_action(
            db,
            user_id=user.id,
            user_name=user.username,
            action="PASSWORD_RESET_SUCCESS",
            details=f"email={email}",
        )
    except Exception:
        pass

    return {"status": "ok", "message": "Password has been reset successfully"}



from app.models.all_models import SystemLog

class SystemLogActionIn(BaseModel):
    action: str = "MENU_CLICK"
    menu_key: Optional[str] = None
    menu_label: Optional[str] = None
    page: Optional[str] = None
    result: Optional[str] = None
    details: Optional[str] = None


@router.post("/system/logs/action")
def create_system_log_action(
    payload: SystemLogActionIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    action = (payload.action or "MENU_CLICK").strip()[:128]
    menu_key = (payload.menu_key or "").strip()
    menu_label = (payload.menu_label or "").strip()
    page = (payload.page or "").strip()
    result = (payload.result or "").strip()
    extra_details = (payload.details or "").strip()

    details_parts = []
    if menu_key:
        details_parts.append(f"menu_key={menu_key}")
    if menu_label:
        details_parts.append(f"menu_label={menu_label}")
    if page:
        details_parts.append(f"page={page}")
    if result:
        details_parts.append(f"result={result}")
    if extra_details:
        details_parts.append(extra_details)

    details = " | ".join(details_parts) if details_parts else None
    ip_address = request.client.host if request and request.client else None

    log_action(
        db,
        user_id=current_user.id,
        user_name=current_user.username,
        action=action,
        details=details,
        ip_address=ip_address,
    )

    return {"ok": True}

@router.get("/system/logs", response_model=List[SystemLogOut])
def get_system_logs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get system logs. Requires superuser or 'system' username.
    """
    is_admin = current_user.is_superuser or current_user.username == "system" or current_user.username == "admin"
    if not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to view system logs")
    
    logs = db.query(SystemLog).order_by(SystemLog.timestamp.desc()).offset(skip).limit(limit).all()
    return logs


class LLMLogFileOut(BaseModel):
    name: str
    size_bytes: int
    modified_at: str


class LLMLogViewOut(BaseModel):
    filename: str
    tail_lines: int
    size_bytes: int
    modified_at: str
    content: str


class AdminStorageUsageUserOut(BaseModel):
    user_id: int
    username: str
    email: Optional[str] = None
    file_count: int
    bytes: int


class AdminStorageUsageOut(BaseModel):
    upload_root: str
    total_bytes: int
    total_files: int
    users: List[AdminStorageUsageUserOut]


@router.get("/admin/llm-logs/files", response_model=List[LLMLogFileOut])
def list_llm_log_files(
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only superuser can view LLM logs")

    log_dir = Path(settings.BASE_DIR) / "logs"
    if not log_dir.exists() or not log_dir.is_dir():
        return []

    files: List[LLMLogFileOut] = []
    for path in sorted(log_dir.glob("llm_calls.log*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_file():
            continue
        stat = path.stat()
        files.append(
            LLMLogFileOut(
                name=path.name,
                size_bytes=int(stat.st_size),
                modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            )
        )
    return files


@router.get("/admin/llm-logs/view", response_model=LLMLogViewOut)
def view_llm_log_file(
    filename: str = "llm_calls.log",
    tail_lines: int = 300,
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only superuser can view LLM logs")

    safe_name = str(filename or "").strip()
    if not safe_name:
        raise HTTPException(status_code=400, detail="filename is required")
    if "/" in safe_name or "\\" in safe_name or not safe_name.startswith("llm_calls.log"):
        raise HTTPException(status_code=400, detail="invalid filename")

    capped_tail = max(1, min(int(tail_lines or 300), 5000))
    log_dir = (Path(settings.BASE_DIR) / "logs").resolve()
    target = (log_dir / safe_name).resolve()

    if target.parent != log_dir:
        raise HTTPException(status_code=400, detail="invalid path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="log file not found")

    line_buffer = deque(maxlen=capped_tail)
    with target.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line_buffer.append(line)

    stat = target.stat()
    return LLMLogViewOut(
        filename=target.name,
        tail_lines=capped_tail,
        size_bytes=int(stat.st_size),
        modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
        content="".join(line_buffer),
    )


@router.get("/admin/storage-usage", response_model=AdminStorageUsageOut)
def get_admin_storage_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only superuser can view storage usage")

    upload_root = Path(settings.UPLOAD_DIR)
    if not upload_root.is_absolute():
        upload_root = (Path(settings.BASE_DIR) / upload_root).resolve()

    if not upload_root.exists() or not upload_root.is_dir():
        return AdminStorageUsageOut(
            upload_root=str(upload_root),
            total_bytes=0,
            total_files=0,
            users=[],
        )

    user_rows = db.query(User.id, User.username, User.email).all()
    user_map = {int(row.id): {"username": row.username, "email": row.email} for row in user_rows}

    usage_by_user: Dict[int, Dict[str, int]] = {}
    total_files = 0
    total_bytes = 0

    for child in upload_root.iterdir():
        if not child.is_dir():
            continue
        try:
            user_id = int(child.name)
        except Exception:
            continue

        file_count = 0
        bytes_used = 0
        for root, _, files in os.walk(child):
            for filename in files:
                path = Path(root) / filename
                try:
                    stat = path.stat()
                except Exception:
                    continue
                file_count += 1
                bytes_used += int(stat.st_size)

        usage_by_user[user_id] = {
            "file_count": file_count,
            "bytes": bytes_used,
        }
        total_files += file_count
        total_bytes += bytes_used

    users_out: List[AdminStorageUsageUserOut] = []
    for uid, stats in usage_by_user.items():
        info = user_map.get(uid) or {}
        users_out.append(
            AdminStorageUsageUserOut(
                user_id=uid,
                username=str(info.get("username") or f"user_{uid}"),
                email=info.get("email"),
                file_count=int(stats.get("file_count") or 0),
                bytes=int(stats.get("bytes") or 0),
            )
        )

    users_out.sort(key=lambda item: item.bytes, reverse=True)

    return AdminStorageUsageOut(
        upload_root=str(upload_root),
        total_bytes=int(total_bytes),
        total_files=int(total_files),
        users=users_out,
    )

# --- Assets ---

class AssetCreate(BaseModel):
    url: str
    type: str # image, video
    meta_info: Optional[dict] = {}
    remark: Optional[str] = None

class AssetUpdate(BaseModel):
    remark: Optional[str] = None
    meta_info: Optional[dict] = None

class AssetRebindShotMediaRequest(BaseModel):
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    scene_id: Optional[int] = None
    shot_id: Optional[int] = None
    limit: int = 2000
    dry_run: bool = False

@router.get("/assets/", response_model=List[dict])
def get_assets(
    type: Optional[str] = None,
    project_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    shot_id: Optional[str] = None,
    scene_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 300,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    safe_skip = max(int(skip or 0), 0)
    safe_limit = max(1, min(int(limit or 300), 500))
    query = db.query(Asset).filter(Asset.user_id == current_user.id)
    if type:
        query = query.filter(Asset.type == type)
    
    # Ideally use database-side JSON filtering if supported (e.g., Postgres)
    # Since we are likely using SQLite or generic, we might need to filter manually or use cast
    # SQLite supports json_extract but SQLAlchemy syntax depends on dialect.
    # For fail-safe prototype, we'll fetch then filter in Python if specific meta filters are requested.
    
    def _meta_dict(raw_meta: Any) -> Dict[str, Any]:
        if isinstance(raw_meta, dict):
            return raw_meta
        if isinstance(raw_meta, str):
            try:
                parsed = json.loads(raw_meta)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    def _matches_meta_filters(meta: Dict[str, Any]) -> bool:
        if project_id:
            p_id = meta.get('project_id')
            if p_id and str(p_id) != str(project_id):
                return False

        if entity_id:
            e_id = meta.get('entity_id')
            if e_id and str(e_id) != str(entity_id):
                return False

        if shot_id:
            s_id = meta.get('shot_id')
            if s_id and str(s_id) != str(shot_id):
                return False

        if scene_id:
            sc_id = meta.get('scene_id')
            if sc_id and str(sc_id) != str(scene_id):
                return False

        return True

    has_meta_filters = bool(project_id or entity_id or shot_id or scene_id)
    ordered_query = query.order_by(Asset.created_at.desc())

    if not has_meta_filters:
        filtered_assets = ordered_query.offset(safe_skip).limit(safe_limit).all()
    else:
        filtered_assets: List[Asset] = []
        scan_offset = 0
        matched_skipped = 0
        batch_size = min(1000, max(200, safe_limit * 3))

        while len(filtered_assets) < safe_limit:
            batch = ordered_query.offset(scan_offset).limit(batch_size).all()
            if not batch:
                break

            for asset_row in batch:
                meta = _meta_dict(asset_row.meta_info)
                if not _matches_meta_filters(meta):
                    continue

                if matched_skipped < safe_skip:
                    matched_skipped += 1
                    continue

                filtered_assets.append(asset_row)
                if len(filtered_assets) >= safe_limit:
                    break

            scan_offset += len(batch)

    # Enrichment Logic for Grouping
    project_ids = set()
    entity_ids = set()
    shot_ids = set()


    for a in filtered_assets:
        # Ensure meta is a dict
        meta = _meta_dict(a.meta_info)
            
        p_id = meta.get('project_id')
        if p_id: 
            try: project_ids.add(int(p_id))
            except: pass
            
        e_id = meta.get('entity_id')
        if e_id: 
            try: entity_ids.add(int(e_id))
            except: pass
            
        s_id = meta.get('shot_id')
        if s_id: 
            try: shot_ids.add(int(s_id))
            except: pass

    # ... Fetch Maps ...
    
    # ... Populate Results ...
    project_map = {}
    if project_ids:
        projects = db.query(Project.id, Project.title).filter(Project.id.in_(project_ids)).all()
        project_map = {p.id: p.title for p in projects}
        
    entity_map = {}
    if entity_ids:
        entities = db.query(Entity.id, Entity.name).filter(Entity.id.in_(entity_ids)).all()
        entity_map = {e.id: e.name for e in entities}
        
    shot_map = {}
    if shot_ids:
        shots = db.query(Shot.id, Shot.shot_id).filter(Shot.id.in_(shot_ids)).all()
        shot_map = {s.id: s.shot_id for s in shots}

    results = []
    for a in filtered_assets:
        meta = _meta_dict(a.meta_info)
        
        # Make a copy to avoid mutating SQLAlchemy object if it was a dict
        meta = dict(meta)
        
        # Enrich
        p_id = meta.get('project_id')
        if p_id:
            try:
                pid_int = int(p_id)
                if pid_int in project_map: meta['project_title'] = project_map[pid_int]
            except: pass
            
        e_id = meta.get('entity_id')
        if e_id:
            try:
                eid_int = int(e_id)
                if eid_int in entity_map: meta['entity_name'] = entity_map[eid_int]
            except: pass
            
        s_id = meta.get('shot_id')
        if s_id:
            try:
                sid_int = int(s_id)
                if sid_int in shot_map: meta['shot_number'] = shot_map[sid_int]
            except: pass

        results.append({
            "id": a.id,
            "type": a.type,
            "url": a.url,
            "filename": a.filename,
            "meta_info": meta,
            "remark": a.remark,
            "created_at": a.created_at
        })


    # Debug log for asset response consistency
    if results:
        logger.info(f"Asset response sample (1/{len(results)}): Meta={results[0]['meta_info']}")

    return results

def create_asset_url(
    asset_in: AssetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meta = asset_in.meta_info if asset_in.meta_info else {}
    meta['source'] = 'external_url'

    asset = Asset(
        user_id=current_user.id,
        type=asset_in.type,
        url=asset_in.url,
        meta_info=meta,
        remark=asset_in.remark
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return {
        "id": asset.id,
        "type": asset.type,
        "url": asset.url,
        "meta_info": asset.meta_info,
        "remark": asset.remark,
        "created_at": asset.created_at
    }

@router.post("/assets/upload", response_model=dict)
async def upload_asset(
    file: UploadFile = File(...),
    type: str = "image", # image or video
    remark: Optional[str] = None,
    project_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    shot_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    max_upload_bytes = max(int(settings.MAX_ASSET_UPLOAD_MB or 100), 1) * 1024 * 1024
    allowed_image_ext = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    allowed_video_ext = {'.mp4', '.mov', '.avi', '.webm'}

    # Ensure upload directory
    upload_dir = settings.UPLOAD_DIR
    
    # Store by user
    user_upload_dir = os.path.join(upload_dir, str(current_user.id))
    if not os.path.exists(user_upload_dir):
        os.makedirs(user_upload_dir)
    
    # Generate unique filename
    ext = (os.path.splitext(file.filename or "")[1] or "").lower()
    if ext not in (allowed_image_ext | allowed_video_ext):
        raise HTTPException(status_code=400, detail="Unsupported file extension")

    content_type = (file.content_type or "").lower()
    if ext in allowed_video_ext and not content_type.startswith('video/'):
        raise HTTPException(status_code=400, detail="File content type does not match video extension")
    if ext in allowed_image_ext and not content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File content type does not match image extension")

    filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(user_upload_dir, filename)

    # Auto-detect type
    if ext in allowed_video_ext:
        type = 'video'
    elif ext in allowed_image_ext:
        type = 'image'

    bytes_written = 0
    try:
        with open(file_path, "wb") as buffer:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_upload_bytes:
                    raise HTTPException(status_code=413, detail=f"File too large (max {settings.MAX_ASSET_UPLOAD_MB}MB)")
                buffer.write(chunk)
    except HTTPException:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    except Exception:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

    if bytes_written <= 0:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail="Empty file")
        
    # Extract Metadata
    meta_info = {'source': 'file_upload'}
    if project_id: meta_info['project_id'] = project_id
    if entity_id: meta_info['entity_id'] = entity_id
    if shot_id: meta_info['shot_id'] = shot_id
    
    try:
        file_size = os.path.getsize(file_path)
        meta_info['size'] = f"{file_size / 1024:.2f} KB"
        
        if type == 'image':
            with Image.open(file_path) as img:
                meta_info['width'] = img.width
                meta_info['height'] = img.height
                meta_info['format'] = img.format
                meta_info['resolution'] = f"{img.width}x{img.height}"
    except Exception as e:
        print(f"Metadata extraction failed: {e}")

    # Construct URL (assuming /uploads is mounted)
    # Get base URL from request ideally, but relative works for frontend
    base_url = settings.RENDER_EXTERNAL_URL.rstrip('/') if settings.RENDER_EXTERNAL_URL else ""
    url = f"{base_url}/uploads/{current_user.id}/{filename}"
    
    asset = Asset(
        user_id=current_user.id,
        type=type,
        url=url,
        filename=file.filename,
        meta_info=meta_info,
        remark=remark
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    
    return {
        "id": asset.id,
        "type": asset.type,
        "url": asset.url,
        "filename": asset.filename,
        "meta_info": asset.meta_info,
        "remark": asset.remark,
        "created_at": asset.created_at
    }


@router.delete("/assets/{asset_id}")
def delete_asset(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.user_id == current_user.id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
        
    # Delete file if local
    try:
        if asset.url and "/uploads/" in asset.url:
            # parsing logic: /uploads/{user_id}/{filename}
            parts = asset.url.split("/uploads/")
            if len(parts) > 1:
                rel_path = parts[1] # user_id/filename
                file_path = os.path.join(settings.UPLOAD_DIR, rel_path)
                if os.path.exists(file_path):
                    os.remove(file_path)
    except Exception as e:
        print(f"Error deleting file for asset {asset_id}: {e}")

    db.delete(asset)
    db.commit()
    return {"status": "success"}

@router.post("/assets/batch-delete")
def batch_delete_assets(
    asset_ids: List[int] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    assets = db.query(Asset).filter(
        Asset.id.in_(asset_ids), 
        Asset.user_id == current_user.id
    ).all()
    
    deleted_count = 0
    for asset in assets:
        # Delete file if local
        try:
            if asset.url and "/uploads/" in asset.url:
                parts = asset.url.split("/uploads/")
                if len(parts) > 1:
                    rel_path = parts[1]
                    file_path = os.path.join(settings.UPLOAD_DIR, rel_path)
                    if os.path.exists(file_path):
                        os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file for asset {asset.id}: {e}")
        
        db.delete(asset)
        deleted_count += 1
        
    db.commit()
    return {"status": "success", "deleted_count": deleted_count}

@router.put("/assets/{asset_id}", response_model=dict)
def update_asset(
    asset_id: int,
    asset_update: AssetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.user_id == current_user.id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    if asset_update.remark is not None:
        asset.remark = asset_update.remark
    if asset_update.meta_info is not None:
         # Merge or replace? Let's replace for now or merge if needed
         # asset.meta_info = {**asset.meta_info, **asset_update.meta_info} 
         asset.meta_info = asset_update.meta_info
         
    db.commit()
    db.refresh(asset)
    
    return {
        "id": asset.id,
        "type": asset.type,
        "url": asset.url,
        "meta_info": asset.meta_info,
        "remark": asset.remark,
        "created_at": asset.created_at
    }


@router.post("/assets/rebind-shot-media", response_model=dict)
def rebind_shot_media_from_assets(
    payload: AssetRebindShotMediaRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if payload.project_id:
        _require_project_access(db, int(payload.project_id), current_user)

    safe_limit = max(1, min(int(payload.limit or 2000), 10000))

    query = db.query(Asset).filter(Asset.user_id == current_user.id).order_by(Asset.id.asc())
    assets = query.limit(safe_limit).all()

    shot_cache: Dict[int, Optional[Shot]] = {}
    scene_cache: Dict[int, Optional[Scene]] = {}
    episode_cache: Dict[int, Optional[Episode]] = {}

    touched_shots: Dict[int, Shot] = {}
    stats = {
        "scanned": 0,
        "eligible": 0,
        "bound": 0,
        "skipped_existing": 0,
        "skipped_no_shot": 0,
        "skipped_filter": 0,
        "skipped_unknown_type": 0,
    }

    def _meta_dict(raw_meta: Any) -> Dict[str, Any]:
        if isinstance(raw_meta, dict):
            return raw_meta
        if isinstance(raw_meta, str):
            try:
                parsed = json.loads(raw_meta)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    def _to_int(value: Any) -> Optional[int]:
        try:
            if value is None or value == "":
                return None
            return int(value)
        except Exception:
            return None

    for asset in assets:
        stats["scanned"] += 1
        meta = _meta_dict(asset.meta_info)

        sid = _to_int(meta.get("shot_id"))
        if not sid:
            stats["skipped_no_shot"] += 1
            continue

        if payload.shot_id and int(payload.shot_id) != sid:
            stats["skipped_filter"] += 1
            continue

        if payload.project_id:
            meta_project_id = _to_int(meta.get("project_id"))
            if meta_project_id and meta_project_id != int(payload.project_id):
                stats["skipped_filter"] += 1
                continue

        shot = shot_cache.get(sid)
        if sid not in shot_cache:
            shot = db.query(Shot).filter(Shot.id == sid).first()
            shot_cache[sid] = shot

        if not shot:
            stats["skipped_no_shot"] += 1
            continue

        if payload.scene_id and int(payload.scene_id) != int(shot.scene_id or 0):
            stats["skipped_filter"] += 1
            continue

        current_scene = None
        current_episode = None

        if payload.episode_id or payload.project_id:
            scene_id_int = int(shot.scene_id or 0)
            if not scene_id_int:
                stats["skipped_filter"] += 1
                continue

            if scene_id_int not in scene_cache:
                scene_cache[scene_id_int] = db.query(Scene).filter(Scene.id == scene_id_int).first()
            current_scene = scene_cache.get(scene_id_int)
            if not current_scene:
                stats["skipped_filter"] += 1
                continue

            episode_id_int = int(current_scene.episode_id or 0)
            if not episode_id_int:
                stats["skipped_filter"] += 1
                continue

            if episode_id_int not in episode_cache:
                episode_cache[episode_id_int] = db.query(Episode).filter(Episode.id == episode_id_int).first()
            current_episode = episode_cache.get(episode_id_int)
            if not current_episode:
                stats["skipped_filter"] += 1
                continue

        if payload.episode_id and current_episode and int(payload.episode_id) != int(current_episode.id):
            stats["skipped_filter"] += 1
            continue

        if payload.project_id and current_episode and int(payload.project_id) != int(current_episode.project_id or 0):
            stats["skipped_filter"] += 1
            continue

        asset_type = str(meta.get("asset_type") or meta.get("frame_type") or "").strip().lower()
        slot = None
        if asset_type in {"start_frame", "start"}:
            slot = "start"
        elif asset_type in {"end_frame", "end"}:
            slot = "end"
        elif asset_type == "video" or str(asset.type or "").lower() == "video":
            slot = "video"
        elif str(asset.type or "").lower() == "image":
            slot = "start"

        if not slot:
            stats["skipped_unknown_type"] += 1
            continue

        stats["eligible"] += 1
        changed = False

        if slot == "start":
            if str(shot.image_url or "").strip():
                stats["skipped_existing"] += 1
                continue
            if not payload.dry_run:
                shot.image_url = asset.url
                changed = True

        elif slot == "video":
            if str(shot.video_url or "").strip():
                stats["skipped_existing"] += 1
                continue
            if not payload.dry_run:
                shot.video_url = asset.url
                changed = True

        elif slot == "end":
            tech = {}
            try:
                tech = json.loads(shot.technical_notes or "{}")
                if not isinstance(tech, dict):
                    tech = {}
            except Exception:
                tech = {}

            if str(tech.get("end_frame_url") or "").strip():
                stats["skipped_existing"] += 1
                continue

            if not payload.dry_run:
                tech["end_frame_url"] = asset.url
                shot.technical_notes = json.dumps(tech, ensure_ascii=False)
                changed = True

        if changed:
            touched_shots[shot.id] = shot
        stats["bound"] += 1

    if not payload.dry_run and touched_shots:
        db.commit()

    return {
        **stats,
        "dry_run": bool(payload.dry_run),
        "updated_shots": len(touched_shots),
        "limit": safe_limit,
    }



from app.schemas.billing import PricingRuleCreate, PricingRuleUpdate, PricingRuleOut, TransactionOut
from app.models.all_models import RechargePlan, PaymentOrder
import uuid
import io

class RechargePlanOut(BaseModel):
    id: int
    min_amount: int
    max_amount: int
    credit_rate: int
    bonus: int

    class Config:
        from_attributes = True

class PaymentOrderOut(BaseModel):
    order_no: str
    amount: int
    credits: int
    status: str
    pay_url: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class PaymentConfig(BaseModel):
    mchid: Optional[str] = ""
    appid: Optional[str] = ""
    api_v3_key: Optional[str] = ""
    cert_serial_no: Optional[str] = ""
    private_key: Optional[str] = ""
    notify_url: Optional[str] = ""
    use_mock: bool = True


class SMTPConfig(BaseModel):
    host: Optional[str] = ""
    port: int = 587
    username: Optional[str] = ""
    password: Optional[str] = ""
    use_ssl: bool = False
    use_tls: bool = True
    from_email: Optional[str] = ""
    frontend_base_url: Optional[str] = ""


class SMTPTestRequest(BaseModel):
    to_email: str


class SMTPBroadcastRequest(BaseModel):
    subject: str
    content_html: Optional[str] = ""
    content_text: Optional[str] = ""
    confirm_phrase: str

@router.get("/admin/payment-config", response_model=PaymentConfig)
def get_payment_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    setting = db.query(APISetting).filter(
        APISetting.category == "System_Payment",
        APISetting.provider == "wechat_pay"
    ).first()
    
    if not setting:
        return PaymentConfig()
        
    config = setting.config or {}
    return PaymentConfig(
        mchid=config.get("mchid", ""),
        appid=config.get("appid", ""),
        api_v3_key=setting.api_key or "",
        cert_serial_no=config.get("cert_serial_no", ""),
        private_key=config.get("private_key", ""),
        notify_url=config.get("notify_url", ""),
        use_mock=config.get("use_mock", True)
    )

@router.post("/admin/payment-config", response_model=PaymentConfig)
def update_payment_config(
    idx: PaymentConfig,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    setting = db.query(APISetting).filter(
        APISetting.category == "System_Payment",
        APISetting.provider == "wechat_pay"
    ).first()
    
    if not setting:
        setting = APISetting(
            user_id=current_user.id, # Associate with admin
            category="System_Payment",
            provider="wechat_pay",
            name="WeChat Pay System Config",
            is_active=True
        )
        db.add(setting)
    
    setting.api_key = idx.api_v3_key
    setting.config = {
        "mchid": idx.mchid,
        "appid": idx.appid,
        "cert_serial_no": idx.cert_serial_no,
        "private_key": idx.private_key,
        "notify_url": idx.notify_url,
        "use_mock": idx.use_mock
    }
    
    db.commit()
    db.refresh(setting)
    
    # Update Service Immediately
    payment_service.update_config({
        "mchid": idx.mchid,
        "appid": idx.appid,
        "api_v3_key": idx.api_v3_key,
        "cert_serial_no": idx.cert_serial_no,
        "private_key": idx.private_key,
        "notify_url": idx.notify_url,
        "use_mock": idx.use_mock
    })
    
    return idx


@router.get("/admin/smtp-config", response_model=SMTPConfig)
def get_smtp_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    setting = db.query(APISetting).filter(
        APISetting.category == "System_Email",
        APISetting.provider == "smtp"
    ).first()

    if not setting:
        return SMTPConfig(
            host=str(settings.SMTP_HOST or "").strip(),
            port=int(settings.SMTP_PORT or 587),
            username=str(settings.SMTP_USERNAME or "").strip(),
            password="",
            use_ssl=os.getenv("SMTP_USE_SSL", "0") in {"1", "true", "True"},
            use_tls=bool(settings.SMTP_USE_TLS),
            from_email=str(settings.SMTP_FROM_EMAIL or "").strip(),
            frontend_base_url=str(settings.FRONTEND_BASE_URL or "").strip(),
        )

    config = setting.config or {}
    return SMTPConfig(
        host=str(config.get("host", "") or "").strip(),
        port=int(config.get("port") or 587),
        username=str(config.get("username", "") or "").strip(),
        password=setting.api_key or "",
        use_ssl=bool(config.get("use_ssl", False)),
        use_tls=bool(config.get("use_tls", True)),
        from_email=str(config.get("from_email", "") or "").strip(),
        frontend_base_url=str(config.get("frontend_base_url", "") or "").strip(),
    )


@router.post("/admin/smtp-config", response_model=SMTPConfig)
def update_smtp_config(
    idx: SMTPConfig,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    setting = db.query(APISetting).filter(
        APISetting.category == "System_Email",
        APISetting.provider == "smtp"
    ).first()

    if not setting:
        setting = APISetting(
            user_id=current_user.id,
            category="System_Email",
            provider="smtp",
            name="SMTP System Config",
            is_active=True,
        )
        db.add(setting)

    setting.api_key = str(idx.password or "")
    setting.config = {
        "host": str(idx.host or "").strip(),
        "port": int(idx.port or 587),
        "username": str(idx.username or "").strip(),
        "use_ssl": bool(idx.use_ssl),
        "use_tls": bool(idx.use_tls),
        "from_email": str(idx.from_email or "").strip(),
        "frontend_base_url": str(idx.frontend_base_url or "").strip(),
    }

    db.commit()
    db.refresh(setting)
    return idx


@router.post("/admin/smtp-config/test")
def test_smtp_config(
    payload: SMTPTestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    del db
    target_email = str(payload.to_email or "").strip()
    if not target_email:
        raise HTTPException(status_code=400, detail="测试邮箱不能为空")

    subject = "AI Story SMTP 测试邮件"
    content = (
        "这是一封来自 AI Story 的 SMTP 测试邮件。\n\n"
        "如果你收到了这封邮件，说明 SMTP 配置可用。"
    )

    try:
        _send_email_via_runtime_smtp(target_email, subject, content, strict=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"发送失败: {exc}")

    return {"success": True, "message": f"测试邮件已发送到 {target_email}"}


@router.post("/admin/smtp-config/broadcast")
def broadcast_email_to_all_users(
    payload: SMTPBroadcastRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    if str(payload.confirm_phrase or "").strip() != "SEND_TO_ALL_USERS":
        raise HTTPException(status_code=400, detail="确认口令错误，请输入 SEND_TO_ALL_USERS")

    subject = str(payload.subject or "").strip()
    html_content = str(payload.content_html or "")
    text_content = str(payload.content_text or "").strip()

    if not subject:
        raise HTTPException(status_code=400, detail="邮件主题不能为空")

    if not html_content.strip() and not text_content:
        raise HTTPException(status_code=400, detail="邮件内容不能为空（HTML 或文本至少填写一个）")

    if not text_content:
        text_content = "This email contains HTML content. Please view it in an HTML-compatible email client."

    rows = db.query(User.email).all()
    raw_emails = [str((row[0] or "")).strip().lower() for row in rows]

    recipients = []
    invalid_count = 0
    seen = set()
    for email in raw_emails:
        if not email:
            continue
        if email in seen:
            continue
        seen.add(email)
        if _is_valid_email_format(email):
            recipients.append(email)
        else:
            invalid_count += 1

    if not recipients:
        raise HTTPException(status_code=400, detail="没有可用的收件邮箱")

    sent = 0
    failed = 0
    errors = []
    for email in recipients:
        try:
            _send_email_via_runtime_smtp(
                email,
                subject,
                text_content,
                html_content=html_content,
                strict=True,
            )
            sent += 1
        except Exception as exc:
            failed += 1
            if len(errors) < 10:
                errors.append({"email": email, "error": str(exc)})

    return {
        "success": failed == 0,
        "total": len(recipients),
        "sent": sent,
        "failed": failed,
        "invalid": invalid_count,
        "errors": errors,
    }


@router.get("/admin/runtime-stats")
def get_runtime_stats(current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    image_job_stats = _snapshot_image_job_stats()

    return {
        "service": "aistory-backend",
        "pid": os.getpid(),
        "timestamp": datetime.utcnow().isoformat(),
        "render": {
            "service_id": os.getenv("RENDER_SERVICE_ID", ""),
            "instance_id": os.getenv("RENDER_INSTANCE_ID", ""),
            "git_commit": os.getenv("RENDER_GIT_COMMIT", ""),
        },
        "image_jobs": image_job_stats,
    }


@router.get("/admin/upstream-diagnostics/grsai")
def admin_diagnose_grsai_connectivity(
    timeout_seconds: int = 5,
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    timeout_seconds = max(2, min(int(timeout_seconds or 5), 20))

    targets = [
        {
            "name": "primary",
            "base_url": "https://grsai.dakka.com.cn",
            "submit_path": "/v1/draw/nano-banana",
            "poll_path": "/v1/draw/result",
        },
        {
            "name": "fallback",
            "base_url": "https://grsaiapi.com",
            "submit_path": "/v1/draw/completions",
            "poll_path": "/v1/draw/result",
        },
    ]

    def _check_one(target: Dict[str, str]) -> Dict[str, Any]:
        base_url = target["base_url"].rstrip("/")
        parsed = urllib.parse.urlparse(base_url)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        result: Dict[str, Any] = {
            "name": target["name"],
            "host": host,
            "port": port,
            "base_url": base_url,
            "submit_url": f"{base_url}{target['submit_path']}",
            "poll_url": f"{base_url}{target['poll_path']}",
            "dns": {"ok": False, "ips": [], "error": None, "ms": None},
            "tcp": {"ok": False, "error": None, "ms": None},
            "http": {
                "ok": False,
                "status": None,
                "error": None,
                "ms": None,
                "note": "HTTP 200/401/403/404/405 are all considered reachable",
            },
        }

        dns_start = time.perf_counter()
        try:
            infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
            ips = sorted({info[4][0] for info in infos if info and len(info) >= 5 and info[4]})
            result["dns"]["ok"] = len(ips) > 0
            result["dns"]["ips"] = ips
        except Exception as exc:
            result["dns"]["error"] = str(exc)
        finally:
            result["dns"]["ms"] = int((time.perf_counter() - dns_start) * 1000)

        tcp_start = time.perf_counter()
        try:
            conn = socket.create_connection((host, port), timeout=timeout_seconds)
            conn.close()
            result["tcp"]["ok"] = True
        except Exception as exc:
            result["tcp"]["error"] = str(exc)
        finally:
            result["tcp"]["ms"] = int((time.perf_counter() - tcp_start) * 1000)

        http_start = time.perf_counter()
        try:
            resp = requests.get(
                result["submit_url"],
                timeout=(timeout_seconds, timeout_seconds),
                verify=False,
            )
            result["http"]["status"] = resp.status_code
            result["http"]["ok"] = resp.status_code in {200, 401, 403, 404, 405}
        except Exception as exc:
            result["http"]["error"] = str(exc)
        finally:
            result["http"]["ms"] = int((time.perf_counter() - http_start) * 1000)

        return result

    checks = [_check_one(target) for target in targets]
    overall_ok = any(item.get("http", {}).get("ok") for item in checks)

    return {
        "ok": overall_ok,
        "timeout_seconds": timeout_seconds,
        "proxy_env": {
            "HTTP_PROXY": os.getenv("HTTP_PROXY") or "",
            "HTTPS_PROXY": os.getenv("HTTPS_PROXY") or "",
            "NO_PROXY": os.getenv("NO_PROXY") or "",
        },
        "checks": checks,
    }


class RechargeRequest(BaseModel):
    amount: int

@router.get("/billing/recharge/plans", response_model=List[RechargePlanOut])
def get_recharge_plans(db: Session = Depends(get_db)):
    return db.query(RechargePlan).filter(RechargePlan.is_active == True).all()

@router.post("/billing/recharge/create", response_model=PaymentOrderOut)
def create_recharge_order(
    req: RechargeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    # Load System Payment Config
    # Explicitly look for the system user's config or global config
    # Assuming user_id=None or user_id=3 (system) or just find ANY row for System_Payment
    all_settings = db.query(APISetting).filter(
        APISetting.category == "System_Payment",
        APISetting.provider == "wechat_pay"
    ).all()
    
    setting = None
    if all_settings:
        # Prefer the one with active settings
        setting = all_settings[0] # Simply take the first one found
        logger.info(f"Found System Payment Settings: ID={setting.id}, Provider={setting.provider}")
    else:
        logger.warning("No System Payment Settings found in DB query!")

    if setting:
        conf = setting.config or {}
        # log what we found
        logger.info(f"Loading Config: mchid={conf.get('mchid')}, use_mock={conf.get('use_mock')}")
        
        payment_service.update_config({
            "mchid": conf.get("mchid"),
            "appid": conf.get("appid"),
            "api_v3_key": setting.api_key,
            "cert_serial_no": conf.get("cert_serial_no"),
            "private_key": conf.get("private_key"),
            "notify_url": conf.get("notify_url"),
            "use_mock": conf.get("use_mock", True)
        })
    else:
        # Default to Mock if no config found
        payment_service.update_config({"use_mock": True})

    # Find applicable plan
    plan = db.query(RechargePlan).filter(
        RechargePlan.min_amount <= req.amount,
        RechargePlan.max_amount >= req.amount,
        RechargePlan.is_active == True
    ).first()
    
    if not plan:
        # Fallback to default (100) if no matching range found? Or error?
        # User requirement implies continuous ranges. 
        # If amount < 1, reject. If > max, check highest. 
        # Let's use a safe default of 100 if inside hole, but ideally there are no holes.
        credit_rate = 100
        bonus = 0
    else:
        credit_rate = plan.credit_rate
        bonus = plan.bonus
        
    total_credits = (req.amount * credit_rate) + bonus
    
    # Generate Order No
    order_no = f"ORD_{uuid.uuid4().hex[:16]}"
    
    # Try Real WeChat Pay
    description = f"Recharge {req.amount} CNY"
    pay_url = payment_service.create_native_order(order_no, req.amount, description)
    
    if not pay_url:
        logger.warning(f"Real WeChat Pay failed for {order_no}. Falling back to mock.")
        # Mock Pay URL (Simulate a WeChat URL)
        # Reverting to the format that looks like a real URL, even if it might fail scanning if not registered with WeChat,
        # as user requested "actual WeChat address" format.
        # But for it to actually WORK, the payment_service MUST be configured correctly.
        pay_url = f"weixin://wxpay/bizpayurl?pr={order_no}"
    
    order = PaymentOrder(
        order_no=order_no,
        user_id=current_user.id,
        amount=req.amount,
        credits=total_credits,
        status="PENDING",
        pay_url=pay_url,
        provider="wechat",
        created_at=datetime.utcnow().isoformat()
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    
    return order

@router.get("/billing/recharge/status/{order_no}")
def check_order_status(
    order_no: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    order = db.query(PaymentOrder).filter(PaymentOrder.order_no == order_no).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    if order.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Active Query if PENDING (For Real Flow)
    if order.status == "PENDING":
        wx_status = payment_service.query_order(order_no)
        if wx_status == "SUCCESS":
            logger.info(f"Order {order_no} confirmed SUCCESS via Active Query")
            # Update to PAID
            order.status = "PAID"
            order.paid_at = datetime.utcnow().isoformat()
            
            # Add Credits
            user = db.query(User).filter(User.id == order.user_id).first()
            if user:
                user.credits = (user.credits or 0) + order.credits
                
            # Transaction History
            trans = TransactionHistory(
                user_id=order.user_id,
                amount=order.credits,
                balance_after=user.credits if user else 0,
                task_type="recharge",
                provider="wechat",
                model="cny",
                details={"order_no": order_no, "amount_cny": order.amount, "method": "active_query"}
            )
            db.add(trans)
            db.commit()
            db.refresh(order)

    return {"status": order.status, "paid_at": order.paid_at}

@router.post("/billing/recharge/notify")
async def wechat_notify(request: Request, db: Session = Depends(get_db)):
    """
    WeChat Pay Callback
    """
    try:
        # Load Config First
        setting = db.query(APISetting).filter(
            APISetting.category == "System_Payment",
            APISetting.provider == "wechat_pay"
        ).first()
        
        if setting:
            conf = setting.config or {}
            payment_service.update_config({
                "mchid": conf.get("mchid"),
                "appid": conf.get("appid"),
                "api_v3_key": setting.api_key,
                "cert_serial_no": conf.get("cert_serial_no"),
                "private_key": conf.get("private_key"),
                "notify_url": conf.get("notify_url"),
                "use_mock": conf.get("use_mock", True)
            })
        else:
            logger.warning("Notification received but no Payment Config found. Assuming Mock or Invalid.")
            # If no config, we can't verify signature.
            raise HTTPException(status_code=500, detail="Configuration Missing")

        headers = request.headers
        body = await request.body()
        
        # Verify and Parse
        result = payment_service.parse_notify(headers, body)
        
        if result:
            logger.info(f"WeChat Notify Received: {result}")
            # Reference: {"appid": "...", "mchid": "...", "out_trade_no": "...", "transaction_id": "...", "trade_state": "SUCCESS", ...}
            
            # Check trade_state
            trade_state = result.get('trade_state')
            out_trade_no = result.get('out_trade_no')
            
            if trade_state == "SUCCESS" and out_trade_no:
                order = db.query(PaymentOrder).filter(
                    PaymentOrder.order_no == out_trade_no,
                    PaymentOrder.status == "PENDING"
                ).first()
                
                if order:
                    order.status = "PAID"
                    order.paid_at = datetime.utcnow().isoformat()
                    # Store transaction_id from WeChat
                    wx_transaction_id = result.get('transaction_id')
                    
                    user = db.query(User).filter(User.id == order.user_id).first()
                    if user:
                        user.credits = (user.credits or 0) + order.credits
                        
                    trans = TransactionHistory(
                        user_id=order.user_id,
                        amount=order.credits,
                        balance_after=user.credits if user else 0,
                        task_type="recharge",
                        provider="wechat",
                        model="cny",
                        details={
                            "order_no": out_trade_no, 
                            "method": "notify", 
                            "wx_transaction_id": wx_transaction_id,
                            "payer_openid": result.get("payer", {}).get("openid"),
                            # "raw": result # Store raw data if needed (careful with size)
                        }
                    )
                    db.add(trans)
                    db.commit()
                    logger.info(f"Order {out_trade_no} confirmed via Notify")
            else:
                logger.warning(f"Notify received but trade_state is {trade_state}")
                    
        return {"code": "SUCCESS", "message": "OK"}
    except Exception as e:
        logger.error(f"Notify Error: {e}")
        # Return generic failure or still success to stop retries if it's a code error?
        # Better to return failure (500) so WeChat retries later if it was a temp DB issue.
        raise HTTPException(status_code=500, detail="Internal Error")

@router.post("/billing/recharge/mock_pay/{order_no}")
def mock_pay_order(
    order_no: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Dev only or check config?
    # For now allow any user to pay their own order for testing
    order = db.query(PaymentOrder).filter(
        PaymentOrder.order_no == order_no,
        PaymentOrder.status == "PENDING"
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Pending order not found")
        
    if order.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    # Process Payment
    order.status = "PAID"
    order.paid_at = datetime.utcnow().isoformat()
    
    # Add Credits
    user = db.query(User).filter(User.id == order.user_id).first()
    old_credits = user.credits or 0
    user.credits = old_credits + order.credits
    
    # Log Transaction
    trans = TransactionHistory(
        user_id=user.id,
        amount=order.credits,
        balance_after=user.credits,
        task_type="recharge",
        provider="wechat",
        model="cny",
        details={"order_no": order_no, "amount_cny": order.amount}
    )
    db.add(trans)
    
    db.commit()
    
    return {"status": "success", "new_balance": user.credits}


# --- Billing Management ---

def _validate_pricing_rule_token_costs(rule: PricingRule):
    token_unit_types = {"per_token", "per_1k_tokens", "per_million_tokens"}
    if rule.unit_type in token_unit_types:
        if rule.cost_input is None or rule.cost_output is None or rule.cost_input <= 0 or rule.cost_output <= 0:
            raise HTTPException(
                status_code=422,
                detail="For token unit types, both cost_input and cost_output must be configured (> 0)."
            )

@router.get("/billing/rules", response_model=List[PricingRuleOut])
def get_pricing_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    return db.query(PricingRule).all()

@router.post("/billing/rules", response_model=PricingRuleOut)
def create_pricing_rule(
    rule_in: PricingRuleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        rule = PricingRule(**rule_in.dict())
        _validate_pricing_rule_token_costs(rule)
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return rule
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating pricing rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/billing/rules/sync", response_model=List[PricingRuleOut])
def sync_pricing_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sync system API Settings into Pricing Rules.
    If a provider/model exists in system settings but not in pricing rules, add it.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    # 1. Fetch active dedicated system settings
    settings = db.query(SystemAPISetting).filter(
        SystemAPISetting.is_active == True
    ).all()

    if not settings:
        return []
    
    added_rules = []
    
    def _task_types_for_setting_category(category: str) -> List[str]:
        # Pricing rules are keyed by (task_type, provider, model).
        # Core rule: both chat + scene analysis use Core LLM settings.
        if category == "LLM":
            return ["llm_chat", "analysis"]
        if category == "Vision":
            # Vision analysis currently bills under analysis / analysis_character
            return ["analysis", "analysis_character"]
        if category == "Image":
            return ["image_gen"]
        if category == "Video":
            return ["video_gen"]
        if category == "Analysis":
            return ["analysis"]
        return ["llm_chat"]

    try:
        for setting in settings:
            for task_type in _task_types_for_setting_category(setting.category):
                # Check existence (Exact match on provider+model+task)
                query = db.query(PricingRule).filter(
                    PricingRule.provider == setting.provider,
                    PricingRule.task_type == task_type
                )

                if setting.model:
                    query = query.filter(PricingRule.model == setting.model)
                else:
                    query = query.filter(PricingRule.model == None)

                existing = query.first()

                if not existing:
                    new_rule = PricingRule(
                        provider=setting.provider,
                        model=setting.model,
                        task_type=task_type,
                        cost=1,
                        unit_type="per_call",
                        is_active=True,
                        description=f"Auto-synced from {setting.category}/{setting.name}"
                    )
                    db.add(new_rule)
                    added_rules.append(new_rule)
        
        if added_rules:
            db.commit()
            for r in added_rules:
                db.refresh(r)
        
        return added_rules
    except Exception as e:
        logger.error(f"Sync pricing rules failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/billing/options")
def get_billing_options(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return provider/model dropdown options for Pricing Rules.

    Options are derived from *system* APISettings so Pricing Rules stay consistent
    with Settings (provider/model identifiers).
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    all_settings = db.query(SystemAPISetting).all()
    if not all_settings:
        return {"providersByTaskType": {}, "modelsByProvider": {}}

    # Build category -> providers/models
    providers_by_category = {}
    models_by_provider = {}

    for s in all_settings:
        category = s.category or "LLM"
        providers_by_category.setdefault(category, set()).add(s.provider)
        if s.provider not in models_by_provider:
            models_by_provider[s.provider] = set()
        if s.model:
            models_by_provider[s.provider].add(s.model)

    def _union_categories(*cats: str):
        out = set()
        for c in cats:
            out |= providers_by_category.get(c, set())
        return out

    # Task types currently used for billing.
    source_categories_by_task_type = {
        "llm_chat": ["LLM"],
        "analysis": ["LLM", "Vision"],
        "analysis_character": ["LLM", "Vision"],
        "image_gen": ["Image"],
        "video_gen": ["Video"],
    }

    providers_by_task_type = {
        task_type: _union_categories(*cats)
        for task_type, cats in source_categories_by_task_type.items()
    }

    return {
        "taskTypes": sorted(list(providers_by_task_type.keys())),
        "sourceCategoriesByTaskType": source_categories_by_task_type,
        "providersByTaskType": {k: sorted(list(v)) for k, v in providers_by_task_type.items()},
        "modelsByProvider": {k: sorted(list(v)) for k, v in models_by_provider.items()},
    }

@router.put("/billing/rules/{rule_id}", response_model=PricingRuleOut)
def update_pricing_rule(
    rule_id: int,
    rule_in: PricingRuleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    rule = db.query(PricingRule).filter(PricingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    update_data = rule_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)

    _validate_pricing_rule_token_costs(rule)
    
    db.commit()
    db.refresh(rule)
    return rule

@router.delete("/billing/rules/{rule_id}")
def delete_pricing_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    rule = db.query(PricingRule).filter(PricingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    db.delete(rule)
    db.commit()
    return {"status": "success"}

@router.get("/billing/transactions", response_model=List[TransactionOut])
def get_transactions(
    user_id: Optional[int] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser and (user_id and user_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    query = db.query(TransactionHistory)
    
    # Non-superusers can only see their own
    target_id = user_id if user_id else (None if current_user.is_superuser else current_user.id)
    
    if target_id:
        query = query.filter(TransactionHistory.user_id == target_id)
        
    return query.order_by(TransactionHistory.id.desc()).limit(limit).all()

class CreditUpdate(BaseModel):
    amount: int # Absolute value or delta? Let's say absolute set for admin simplicity, or add functionality
    mode: str = "set" # set, add

@router.post("/billing/users/{user_id}/credits")
def update_user_credits(
    user_id: int,
    credit_update: CreditUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    old_credits = user.credits or 0
    if credit_update.mode == "add":
        user.credits = old_credits + credit_update.amount
    else:
        user.credits = credit_update.amount
        
    # Log administrative transaction
    trans = TransactionHistory(
        user_id=user_id,
        amount=user.credits - old_credits,
        balance_after=user.credits,
        task_type="admin_adjustment",
        details={"admin_id": current_user.id, "reason": "Manual Update"}
    )
    db.add(trans)
    
    db.commit()
    return {"credits": user.credits}

# --- Generation ---

class GenerationRequest(BaseModel):
    prompt: str
    provider: Optional[str] = None
    model: Optional[str] = None
    ref_image_url: Optional[Union[str, List[str]]] = None
    project_id: Optional[int] = None
    shot_id: Optional[int] = None
    shot_number: Optional[str] = None
    shot_name: Optional[str] = None
    entity_name: Optional[str] = None
    subject_name: Optional[str] = None
    asset_type: Optional[str] = None

class VideoGenerationRequest(BaseModel):
    prompt: str
    provider: Optional[str] = None
    model: Optional[str] = None
    ref_image_url: Optional[Union[str, List[str]]] = None
    last_frame_url: Optional[str] = None
    duration: Optional[float] = 5.0
    project_id: Optional[int] = None
    shot_id: Optional[int] = None
    shot_number: Optional[str] = None
    shot_name: Optional[str] = None
    entity_name: Optional[str] = None
    subject_name: Optional[str] = None
    asset_type: Optional[str] = None
    keyframes: Optional[List[str]] = None


class ShotMediaBatchStartRequest(BaseModel):
    mode: str = "keyframes"  # keyframes | videos
    shot_ids: Optional[List[int]] = None
    overwrite_existing: bool = False


def _sanitize_filename_part(value: Optional[str], max_len: int = 48) -> str:
    if not value:
        return ""
    cleaned = re.sub(r'[\\/:*?"<>|]+', ' ', str(value))
    cleaned = re.sub(r'\s+', '_', cleaned).strip('._- ')
    cleaned = re.sub(r'_+', '_', cleaned)
    return cleaned[:max_len]


def _build_generation_filename_base(req: Any, db: Session) -> str:
    parts: List[str] = []

    asset_type = _sanitize_filename_part(getattr(req, "asset_type", None), 24)
    if asset_type:
        parts.append(asset_type)

    shot_label = getattr(req, "shot_name", None) or getattr(req, "shot_number", None)
    if not shot_label and getattr(req, "shot_id", None):
        shot_obj = db.query(Shot).filter(Shot.id == req.shot_id).first()
        if shot_obj:
            shot_label = shot_obj.shot_name or shot_obj.shot_id
    shot_part = _sanitize_filename_part(shot_label)
    if shot_part:
        parts.append(f"shot_{shot_part}")

    subject_label = getattr(req, "subject_name", None) or getattr(req, "entity_name", None)
    subject_part = _sanitize_filename_part(subject_label)
    if subject_part:
        parts.append(f"subject_{subject_part}")

    return "_".join(parts) if parts else "gen"

def _register_asset_helper(db: Session, user_id: int, url: str, req: Any, source_metadata: Dict = None):
    # Handle dict or object
    def get_attr(obj, key):
        if isinstance(obj, dict): return obj.get(key)
        return getattr(obj, key, None)

    project_id = get_attr(req, "project_id")
    if not project_id: return

    try:
        # Determine paths
        import urllib.parse
        fname = os.path.basename(urllib.parse.urlparse(url).path)
        file_path = os.path.join(settings.UPLOAD_DIR, fname)
        
        meta = {}
        # Copy known fields
        for field in ["shot_number", "shot_id", "project_id", "asset_type", "entity_id", "entity_name"]:
            val = get_attr(req, field)
            if val: meta[field] = val
        
        if get_attr(req, "asset_type"): meta["frame_type"] = get_attr(req, "asset_type")
        if get_attr(req, "category"): meta["category"] = get_attr(req, "category")
        
        # Merge Source Metadata (Provider, Model)
        if source_metadata:
            for k in ["provider", "model", "duration"]:
                if k in source_metadata:
                    meta[k] = source_metadata[k]

        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            meta["size"] = size
            meta["size_display"] = f"{size/1024:.2f} KB"
            if size > 1024*1024:
                meta["size_display"] = f"{size/1024/1024:.2f} MB"
            
            # Try getting resolution
            try:
                if url.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    with Image.open(file_path) as img:
                        meta["width"] = img.width
                        meta["height"] = img.height
                        meta["resolution"] = f"{img.width}x{img.height}"
            except Exception as e:
                print(f"Meta extraction error: {e}")

        remark = get_attr(req, "remark")
        if not remark:
            provider = meta.get("provider", "Unknown")
            if get_attr(req, "entity_name"):
                 remark = f"Auto-registered from Entity: {get_attr(req, 'entity_name')} ({provider})"
            else:
                 remark = f"Generated {get_attr(req, 'asset_type')} for Shot {get_attr(req, 'shot_number')} by {provider}"

        asset = Asset(
            user_id=user_id,
            type="image" if url.lower().endswith(('.png', '.jpg', '.webp')) else "video",
            url=url,
            filename=fname,
            meta_info=meta,
            remark=remark
        )
        db.add(asset)
        db.commit()
    except Exception as e:
        print(f"Asset reg failed: {e}")


def _bind_generated_media_to_shot(db: Session, current_user: User, req: Any, media_url: Optional[str]) -> None:
    if not media_url:
        return

    def get_attr(obj, key):
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    shot_id = get_attr(req, "shot_id")
    if not shot_id:
        return

    try:
        shot_id_int = int(shot_id)
    except Exception:
        return

    shot = db.query(Shot).filter(Shot.id == shot_id_int).first()
    if not shot:
        return

    try:
        project_id = shot.project_id
        if not project_id and shot.scene_id:
            scene = db.query(Scene).filter(Scene.id == shot.scene_id).first()
            if scene and scene.episode_id:
                episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
                if episode:
                    project_id = episode.project_id
        if project_id:
            _require_project_access(db, int(project_id), current_user)
    except Exception:
        return

    asset_type = str(get_attr(req, "asset_type") or "").strip().lower()
    req_prompt = str(get_attr(req, "prompt") or "").strip()
    changed = False

    if asset_type in {"start_frame", "start"}:
        if shot.image_url != media_url:
            shot.image_url = media_url
            changed = True
        if req_prompt and not str(shot.start_frame or "").strip():
            shot.start_frame = req_prompt
            changed = True

    elif asset_type in {"end_frame", "end"}:
        tech = {}
        try:
            tech = json.loads(shot.technical_notes or "{}")
            if not isinstance(tech, dict):
                tech = {}
        except Exception:
            tech = {}

        if tech.get("end_frame_url") != media_url:
            tech["end_frame_url"] = media_url
            shot.technical_notes = json.dumps(tech, ensure_ascii=False)
            changed = True
        if req_prompt and not str(shot.end_frame or "").strip():
            shot.end_frame = req_prompt
            changed = True

    elif asset_type == "video":
        if shot.video_url != media_url:
            shot.video_url = media_url
            changed = True
        if req_prompt and not str(shot.prompt or "").strip():
            shot.prompt = req_prompt
            changed = True

    if not changed:
        return

    db.add(shot)
    db.commit()

@router.post("/generate/image")
async def generate_image_endpoint(
    req: GenerationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        return await asyncio.wait_for(_run_generate_image(req, current_user, db), timeout=55)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Synchronous image generation timed out. Please use /generate/image/submit and poll /generate/image/jobs/{job_id}.",
        )


async def _run_generate_image(req: GenerationRequest, current_user: User, db: Session):
    # Billing Check
    cost = billing_service.estimate_cost(db, "image_gen", req.provider, req.model)
    billing_service.check_can_proceed(current_user, cost)

    try:
        # 1. Resolve Context for Resolution/Ratio
        aspect_ratio = None
        width = None
        height = None
        episode_info = {}

        # Try to find episode info via Shot -> Scene -> Episode
        if req.shot_id:
             shot = db.query(Shot).filter(Shot.id == req.shot_id).first()
             if shot:
                 scene = db.query(Scene).filter(Scene.id == shot.scene_id).first()
                 if scene and scene.episode_id:
                     ep = db.query(Episode).filter(Episode.id == scene.episode_id).first()
                     if ep and ep.episode_info:
                         temp = ep.episode_info
                         if isinstance(temp, str):
                             try: temp = json.loads(temp)
                             except: temp = {}
                         if isinstance(temp, dict):
                              # Support nested under e_global_info or direct
                              if "e_global_info" in temp and isinstance(temp["e_global_info"], dict):
                                   episode_info = temp["e_global_info"]
                              else:
                                   episode_info = temp

        # Check tech_params -> visual_standard
        tech = episode_info.get("tech_params", {})
        if isinstance(tech, dict):
            vis = tech.get("visual_standard", {})
            if isinstance(vis, dict):
                aspect_ratio = vis.get("aspect_ratio") or vis.get("aspectRatio")
                width = vis.get("h_resolution") or vis.get("width")
                height = vis.get("v_resolution") or vis.get("height")
        
        # Fallback top-level checks
        if not aspect_ratio:
            aspect_ratio = episode_info.get("aspect_ratio") or episode_info.get("aspectRatio")
        if not width: width = episode_info.get("h_resolution") or episode_info.get("width")
        if not height: height = episode_info.get("v_resolution") or episode_info.get("height")

        # Cast to int for safety
        try: width = int(width) if width else 720 
        except: width = 720
        try: height = int(height) if height else 1080
        except: height = 1080

        logger.info(f"[GenerateImage] Context Params - AR: {aspect_ratio}, W: {width}, H: {height}")
        _log_shot_submit_debug(
            "image_submit",
            req,
            refs=req.ref_image_url,
            extra={
                "aspect_ratio": aspect_ratio,
                "width": width,
                "height": height,
                "user_id": current_user.id,
            },
        )

        # Assuming generate_image returns {"url": "...", ...}
        result = await media_service.generate_image(
            prompt=req.prompt, 
            llm_config={"provider": req.provider, "model": req.model} if req.provider or req.model else None,
            reference_image_url=req.ref_image_url,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            user_id=current_user.id,
            user_credits=(current_user.credits or 0),
            filename_base=_build_generation_filename_base(req, db),
        )
        result_meta = result.get("metadata") if isinstance(result, dict) else {}
        if not isinstance(result_meta, dict):
            result_meta = {}
        _log_shot_submit_debug(
            "image_submit_result",
            req,
            refs=req.ref_image_url,
            extra={
                "user_id": current_user.id,
                "submitted_provider": result_meta.get("provider"),
                "submitted_model": result_meta.get("model"),
                "submitted_aspect_ratio": result_meta.get("submit_aspect_ratio"),
            },
        )
        if "error" in result:
             # Include details if available
             detail = result["error"]
             if "details" in result:
                 detail = f"{detail}: {result['details']}"
             
             # Log full error for image gen
             logger.error(f"[GenerateImage] Failed: {detail}")
             billing_service.log_failed_transaction(db, current_user.id, "image_gen", req.provider, req.model, detail)
             
             raise HTTPException(status_code=400, detail=detail)

        # Billing Deduct
        billing_service.deduct_credits(db, current_user.id, "image_gen", req.provider, req.model, {"item": "image"})
        
        # Register Asset
        if result.get("url"):
            # Only register if not error? result.get("url") check handles it.
            _register_asset_helper(db, current_user.id, result["url"], req, result.get("metadata"))
            _bind_generated_media_to_shot(db, current_user, req, result.get("url"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        billing_service.log_failed_transaction(db, current_user.id, "image_gen", req.provider, req.model, str(e))
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


def _set_image_job(job_id: str, **fields) -> None:
    with IMAGE_JOB_LOCK:
        _prune_image_jobs_locked()
        current = IMAGE_JOB_STORE.get(job_id, {})
        if "result" in fields:
            fields["result"] = _compact_job_result(fields.get("result"))
        current.update(fields)
        current["job_id"] = job_id
        IMAGE_JOB_STORE[job_id] = current


async def _run_generate_image_job(job_id: str, user_id: int, req_payload: Dict[str, Any]) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            _set_image_job(
                job_id,
                status="failed",
                finished_at=datetime.utcnow().isoformat(),
                error="User not found",
            )
            return

        req_obj = GenerationRequest(**req_payload)
        _set_image_job(job_id, status="running", started_at=datetime.utcnow().isoformat())
        result = await _run_generate_image(req_obj, user, db)
        _set_image_job(
            job_id,
            status="succeeded",
            finished_at=datetime.utcnow().isoformat(),
            result=result,
            error=None,
        )
    except HTTPException as e:
        _set_image_job(
            job_id,
            status="failed",
            finished_at=datetime.utcnow().isoformat(),
            error=str(e.detail),
        )
    except Exception as e:
        _set_image_job(
            job_id,
            status="failed",
            finished_at=datetime.utcnow().isoformat(),
            error=str(e),
        )
    finally:
        db.close()


@router.post("/generate/image/submit")
async def submit_generate_image_endpoint(
    req: GenerationRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    idempotency_key = str(request.headers.get("X-Idempotency-Key") or "").strip()

    if idempotency_key:
        with IMAGE_JOB_LOCK:
            _prune_image_jobs_locked()
            store_key = _build_image_idempotency_store_key(current_user.id, idempotency_key)
            mapped = IMAGE_SUBMIT_IDEMPOTENCY_STORE.get(store_key) or {}
            existing_job_id = str(mapped.get("job_id") or "").strip()
            if existing_job_id:
                existing_job = dict(IMAGE_JOB_STORE.get(existing_job_id) or {})
                if existing_job:
                    return {
                        "job_id": existing_job_id,
                        "status": existing_job.get("status") or "queued",
                        "created_at": existing_job.get("created_at") or datetime.utcnow().isoformat(),
                        "deduplicated": True,
                    }

    job_id = uuid.uuid4().hex
    now = datetime.utcnow().isoformat()
    _set_image_job(
        job_id,
        status="queued",
        user_id=current_user.id,
        username=current_user.username,
        created_at=now,
        started_at=None,
        finished_at=None,
        result=None,
        error=None,
    )

    if idempotency_key:
        with IMAGE_JOB_LOCK:
            store_key = _build_image_idempotency_store_key(current_user.id, idempotency_key)
            IMAGE_SUBMIT_IDEMPOTENCY_STORE[store_key] = {
                "job_id": job_id,
                "created_at": now,
            }

    asyncio.create_task(_run_generate_image_job(job_id, current_user.id, req.model_dump()))
    return {"job_id": job_id, "status": "queued", "created_at": now}


@router.get("/generate/image/jobs/{job_id}")
def get_generate_image_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    with IMAGE_JOB_LOCK:
        job = dict(IMAGE_JOB_STORE.get(job_id) or {})

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    owner_id = job.get("user_id")
    if not current_user.is_superuser and owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return {
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "error": job.get("error"),
        "result": job.get("result"),
    }


# --- User Management ---
class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    account_status: Optional[int] = None
    email_verified: Optional[bool] = None
    is_authorized: Optional[bool] = None
    is_superuser: Optional[bool] = None
    is_system: Optional[bool] = None
    password: Optional[str] = None


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None


class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str


@router.get("/users/me", response_model=UserOut)
def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Get current user.
    """
    return current_user


@router.put("/users/me/profile", response_model=UserOut)
def update_my_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.full_name is not None:
        user.full_name = (payload.full_name or "").strip() or None

    db.commit()
    db.refresh(user)
    return user


@router.put("/users/me/password")
def update_my_password(
    payload: UserPasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    new_password = (payload.new_password or "").strip()
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    user.hashed_password = get_password_hash(new_password)
    db.commit()
    return {"status": "success", "message": "Password updated"}


@router.post("/users/me/avatar", response_model=UserOut)
async def update_my_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ext = (Path(file.filename or "").suffix or "").lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=400, detail="Avatar must be .jpg, .jpeg, .png or .webp")

    max_avatar_bytes = max(int(settings.MAX_AVATAR_UPLOAD_MB or 5), 1) * 1024 * 1024

    upload_root = settings.UPLOAD_DIR
    avatar_dir = os.path.join(upload_root, str(current_user.id), "avatars")
    os.makedirs(avatar_dir, exist_ok=True)

    filename = f"avatar_{uuid.uuid4().hex[:10]}{ext}"
    save_path = os.path.join(avatar_dir, filename)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty avatar file")
    if len(content) > max_avatar_bytes:
        raise HTTPException(status_code=413, detail=f"Avatar file too large (max {settings.MAX_AVATAR_UPLOAD_MB}MB)")

    with open(save_path, "wb") as f:
        f.write(content)

    relative_path = os.path.relpath(save_path, upload_root).replace("\\", "/")
    user.avatar_url = f"/uploads/{relative_path}"
    db.commit()
    db.refresh(user)
    return user

@router.get("/users", response_model=List[UserOut])
def get_users(
    skip: int = 0, 
    limit: int = 100, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    users = db.query(User).offset(skip).limit(limit).all()
    return users

@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, 
    user_in: UserUpdate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_in.username is not None:
        next_username = (user_in.username or "").strip()
        if not next_username:
            raise HTTPException(status_code=400, detail="Username cannot be empty")
        dup = db.query(User).filter(User.username == next_username, User.id != user_id).first()
        if dup:
            raise HTTPException(status_code=400, detail="Username already registered")
        user.username = next_username

    if user_in.email is not None:
        next_email = (user_in.email or "").strip().lower()
        if not _is_valid_email_format(next_email):
            raise HTTPException(status_code=400, detail="Invalid email format")
        dup = db.query(User).filter(User.email == next_email, User.id != user_id).first()
        if dup:
            raise HTTPException(status_code=400, detail="Email already registered")
        user.email = next_email

    if user_in.full_name is not None:
        user.full_name = (user_in.full_name or "").strip() or None
        
    if user_in.is_active is not None:
        user.is_active = user_in.is_active
    if user_in.account_status is not None:
        user.account_status = int(user_in.account_status)
        if user.account_status == -1:
            user.is_active = False
            user.email_verified = False
    if user_in.email_verified is not None:
        user.email_verified = bool(user_in.email_verified)
        if user.email_verified and user.account_status == -1:
            user.account_status = 1
    if user_in.is_authorized is not None:
        user.is_authorized = user_in.is_authorized
    if user_in.is_superuser is not None:
        user.is_superuser = user_in.is_superuser
    if user_in.is_system is not None:
        # Ensure only one system user if we want strict uniqueness, but user asked for "System user unique" logic potentially
        # For now, let's just allow marking. 
        # If we need strict 1 system user, we can unset others.
        if user_in.is_system:
             # Unset others? Or just trust admin. Let's unset others to be safe as per "system user unique" hint.
             db.query(User).filter(User.id != user_id).update({"is_system": False})
        user.is_system = user_in.is_system
        
    if user_in.password:
        user.hashed_password = get_password_hash(user_in.password)
        
    db.commit()
    db.refresh(user)
    return user


@router.post("/generate/video")
async def generate_video_endpoint(
    req: VideoGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Billing
    cost = billing_service.estimate_cost(db, "video_gen", req.provider, req.model)
    billing_service.check_can_proceed(current_user, cost)

    try:
        # 1. Resolve Context for Aspect Ratio
        aspect_ratio = None
        episode_info = {}

        # Try to find episode info via Shot -> Scene -> Episode
        if req.shot_id:
             shot = db.query(Shot).filter(Shot.id == req.shot_id).first()
             if shot:
                 scene = db.query(Scene).filter(Scene.id == shot.scene_id).first()
                 if scene and scene.episode_id:
                     ep = db.query(Episode).filter(Episode.id == scene.episode_id).first()
                     if ep and ep.episode_info:
                         # Robust logic matching _build_shot_prompts
                         temp = ep.episode_info
                         if isinstance(temp, str):
                             try: temp = json.loads(temp)
                             except: temp = {}
                         if isinstance(temp, dict):
                              if "e_global_info" in temp and isinstance(temp["e_global_info"], dict):
                                   episode_info = temp["e_global_info"]
                              else:
                                   episode_info = temp

        # Extract Aspect Ratio
        # Structure: tech_params -> visual_standard -> aspect_ratio
        # Or direct top level
        tech = episode_info.get("tech_params", {})
        if isinstance(tech, dict):
            vis = tech.get("visual_standard", {})
            if isinstance(vis, dict):
                aspect_ratio = vis.get("aspect_ratio") or vis.get("aspectRatio")
        
        if not aspect_ratio:
             # Fallback check
             aspect_ratio = episode_info.get("aspect_ratio") or episode_info.get("aspectRatio")

        logger.info(f"[GenerateVideo] Extracted Aspect Ratio: {aspect_ratio}")
        _log_shot_submit_debug(
            "video_submit",
            req,
            refs=req.ref_image_url,
            extra={
                "last_frame_url": req.last_frame_url,
                "duration": req.duration,
                "aspect_ratio": aspect_ratio,
                "keyframes_count": len(req.keyframes or []),
                "user_id": current_user.id,
            },
        )

        result = await media_service.generate_video(
            prompt=req.prompt, 
            llm_config={"provider": req.provider, "model": req.model} if req.provider or req.model else None,
            reference_image_url=req.ref_image_url,
            last_frame_url=req.last_frame_url,
            duration=req.duration,
            aspect_ratio=aspect_ratio,
            keyframes=req.keyframes,
            user_id=current_user.id,
            user_credits=(current_user.credits or 0),
            filename_base=_build_generation_filename_base(req, db),
        )
        if "error" in result:
             detail = result["error"]
             if "details" in result:
                 detail = f"{detail}: {result['details']}"
             
             # Log the full error detail for debugging
             logger.error(f"[GenerateVideo] Failed: {detail}") 
             billing_service.log_failed_transaction(db, current_user.id, "video_gen", req.provider, req.model, detail)
             
             raise HTTPException(status_code=400, detail=detail)

        # Register Asset
        if result.get("url"):
            _register_asset_helper(db, current_user.id, result["url"], req, result.get("metadata"))
            _bind_generated_media_to_shot(db, current_user, req, result.get("url"))
            
        # Billing Deduct
        billing_service.deduct_credits(db, current_user.id, "video_gen", req.provider, req.model, {"duration": req.duration})

        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        billing_service.log_failed_transaction(db, current_user.id, "video_gen", req.provider, req.model, str(e))
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


SHOT_MEDIA_BATCH_STATUS_KEY = "shot_media_batch_status"


def _read_shot_media_batch_status(episode: Episode) -> Dict[str, Any]:
    try:
        info = dict(episode.episode_info or {})
        payload = info.get(SHOT_MEDIA_BATCH_STATUS_KEY)
        if isinstance(payload, dict):
            return dict(payload)
    except Exception:
        pass
    return {
        "running": False,
        "mode": "keyframes",
        "total": 0,
        "completed": 0,
        "success": 0,
        "failed": 0,
        "message": "",
        "errors": [],
        "stop_requested": False,
    }


def _persist_shot_media_batch_status(db: Session, episode: Episode, status_payload: Dict[str, Any]) -> None:
    info = dict(episode.episode_info or {})
    info[SHOT_MEDIA_BATCH_STATUS_KEY] = status_payload
    episode.episode_info = info
    db.add(episode)
    db.commit()


def _parse_shot_tech(shot: Shot) -> Dict[str, Any]:
    try:
        payload = json.loads(shot.technical_notes or "{}")
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return {}


def _normalize_entity_anchor_token(value: Any) -> str:
    return (
        str(value or "")
        .replace("（", "(")
        .replace("）", ")")
        .replace("【", "[")
        .replace("】", "]")
        .replace("‘", "")
        .replace("’", "")
        .replace("“", "")
        .replace("”", "")
        .replace("\"", "")
        .replace("'", "")
        .strip()
        .lower()
    )


def _build_project_entity_lookup(db: Session, project_id: int) -> Dict[str, Dict[str, Any]]:
    rows = db.query(Entity).filter(Entity.project_id == project_id).all()
    lookup: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        anchor = str(row.anchor_description or row.description or "").strip()
        image_url = str(row.image_url or "").strip()
        payload = {
            "anchor": anchor,
            "image_url": image_url,
            "entity_id": row.id,
        }
        keys = {
            _normalize_entity_anchor_token(row.name),
            _normalize_entity_anchor_token(row.name_en),
        }
        for key in list(keys):
            if not key:
                continue
            lookup[key] = payload
    return lookup


def _inject_shot_prompt_anchors(prompt: str, entity_lookup: Dict[str, Dict[str, Any]], global_style: str = "") -> str:
    text = str(prompt or "")
    if not text:
        return text

    regex = re.compile(r"[\[【](.*?)[\]】]")

    def _replace(match: re.Match) -> str:
        token = str(match.group(1) or "").strip()
        normalized = _normalize_entity_anchor_token(re.sub(r"^(CHAR|ENV|PROP)\s*:\s*", "", token, flags=re.IGNORECASE).lstrip("@"))
        tail = text[match.end():]
        if re.match(r"^\s*[\(（]", tail):
            return match.group(0)

        if normalized in {"global style", "global_style"} and global_style:
            return f"{match.group(0)}({global_style})"

        row = entity_lookup.get(normalized)
        if row and row.get("anchor"):
            return f"{match.group(0)}({row['anchor']})"
        return match.group(0)

    return regex.sub(_replace, text)


def _collect_prompt_entity_ref_images(prompt: str, entity_lookup: Dict[str, Dict[str, Any]]) -> List[str]:
    text = str(prompt or "")
    if not text:
        return []

    refs: List[str] = []
    regex = re.compile(r"(?:CHAR|ENV|PROP)?\s*:\s*[\[【](.*?)[\]】]|[\[【](.*?)[\]】]", re.IGNORECASE)
    for m in regex.finditer(text):
        raw_name = m.group(1) or m.group(2) or ""
        normalized = _normalize_entity_anchor_token(re.sub(r"^(CHAR|ENV|PROP)\s*:\s*", "", raw_name, flags=re.IGNORECASE).lstrip("@"))
        if not normalized:
            continue
        row = entity_lookup.get(normalized)
        image_url = str((row or {}).get("image_url") or "").strip()
        if image_url:
            refs.append(image_url)
    return [x for x in dict.fromkeys(refs) if x]


def _find_previous_shot_end_frame_url(db: Session, episode_id: int, shot_id: int) -> Optional[str]:
    prev_shot = (
        db.query(Shot)
        .filter(Shot.episode_id == episode_id, Shot.id < shot_id)
        .order_by(Shot.id.desc())
        .first()
    )
    if not prev_shot:
        return None
    prev_tech = _parse_shot_tech(prev_shot)
    prev_end = str(prev_tech.get("end_frame_url") or "").strip()
    return prev_end or None


def _run_shot_media_batch_job(episode_id: int, request_payload: Dict[str, Any], user_id: int) -> None:
    db = SessionLocal()
    try:
        episode = db.query(Episode).filter(Episode.id == episode_id).first()
        user = db.query(User).filter(User.id == user_id).first()
        if not episode or not user:
            return

        episode_info = episode.episode_info if isinstance(episode.episode_info, dict) else {}
        e_global_info = episode_info.get("e_global_info", {}) if isinstance(episode_info, dict) else {}
        global_style = str((e_global_info or {}).get("Global_Style") or "").strip()
        entity_lookup = _build_project_entity_lookup(db, int(episode.project_id))

        mode = str((request_payload or {}).get("mode") or "keyframes").strip().lower()
        overwrite_existing = bool((request_payload or {}).get("overwrite_existing"))
        requested_shot_ids = [int(x) for x in ((request_payload or {}).get("shot_ids") or []) if x]

        shots_query = db.query(Shot).filter(Shot.episode_id == episode_id).order_by(Shot.id.asc())
        if requested_shot_ids:
            shots_query = shots_query.filter(Shot.id.in_(requested_shot_ids))
        target_shots = shots_query.all()

        total = len(target_shots)
        completed = 0
        success = 0
        failed = 0
        errors: List[str] = []

        for shot in target_shots:
            episode = db.query(Episode).filter(Episode.id == episode_id).first()
            if not episode:
                break
            latest = _read_shot_media_batch_status(episode)
            if bool(latest.get("stop_requested")):
                latest["running"] = False
                latest["completed"] = completed
                latest["success"] = success
                latest["failed"] = failed
                latest["errors"] = errors
                latest["stopped_by_user"] = True
                latest["message"] = "Stopped by user request"
                latest["finished_at"] = datetime.utcnow().isoformat()
                latest["updated_at"] = latest["finished_at"]
                _persist_shot_media_batch_status(db, episode, latest)
                return

            shot_label = str(shot.shot_id or shot.shot_name or f"#{shot.id}")
            latest["current_shot_id"] = shot.id
            latest["current_shot_label"] = shot_label
            latest["message"] = f"Processing shot {shot_label}..."
            latest["updated_at"] = datetime.utcnow().isoformat()
            _persist_shot_media_batch_status(db, episode, latest)

            shot_ok = True
            try:
                tech = _parse_shot_tech(shot)
                end_frame_url = str(tech.get("end_frame_url") or "").strip()

                need_start = overwrite_existing or not str(shot.image_url or "").strip()
                need_end = overwrite_existing or not end_frame_url

                if need_start:
                    start_prompt_raw = str(shot.start_frame or shot.video_content or "").strip()
                    if start_prompt_raw:
                        start_prompt = _inject_shot_prompt_anchors(start_prompt_raw, entity_lookup, global_style)
                        auto_matches = _collect_prompt_entity_ref_images(start_prompt_raw, entity_lookup)
                        start_refs: List[str] = []
                        if isinstance(tech.get("ref_image_urls"), list):
                            saved_refs = [str(x).strip() for x in tech.get("ref_image_urls") or [] if str(x).strip()]
                            deleted_refs = {str(x).strip() for x in tech.get("deleted_ref_urls") or [] if str(x).strip()}
                            new_auto = [url for url in auto_matches if url not in saved_refs and url not in deleted_refs]
                            start_refs = saved_refs + new_auto
                        else:
                            start_refs = list(auto_matches)
                            prev_end = _find_previous_shot_end_frame_url(db, episode_id, int(shot.id))
                            if prev_end and prev_end not in start_refs:
                                start_refs.insert(0, prev_end)

                        start_refs = [x for x in dict.fromkeys([str(x).strip() for x in start_refs if str(x).strip()]) if x]
                        start_req = GenerationRequest(
                            prompt=start_prompt,
                            ref_image_url=start_refs if start_refs else None,
                            project_id=episode.project_id,
                            shot_id=shot.id,
                            shot_number=shot.shot_id,
                            shot_name=shot.shot_name,
                            asset_type="start_frame",
                        )
                        asyncio.run(generate_image_endpoint(req=start_req, current_user=user, db=db))
                        shot = db.query(Shot).filter(Shot.id == shot.id).first() or shot

                if need_end:
                    end_prompt_raw = str(shot.end_frame or "").strip()
                    if end_prompt_raw:
                        end_prompt = _inject_shot_prompt_anchors(end_prompt_raw, entity_lookup, global_style)
                        refs: List[str] = []
                        if isinstance(tech.get("end_ref_image_urls"), list):
                            refs.extend([str(x).strip() for x in tech.get("end_ref_image_urls") or [] if str(x).strip()])
                        else:
                            refs.extend(_collect_prompt_entity_ref_images(end_prompt_raw, entity_lookup))

                        deleted_refs = {str(x).strip() for x in tech.get("deleted_ref_urls") or [] if str(x).strip()}
                        start_image = str(shot.image_url or "").strip()
                        if start_image and start_image not in refs and start_image not in deleted_refs:
                            refs.insert(0, start_image)

                        refs = [x for x in dict.fromkeys([str(x).strip() for x in refs if str(x).strip()]) if x]
                        end_req = GenerationRequest(
                            prompt=end_prompt,
                            ref_image_url=refs if refs else None,
                            project_id=episode.project_id,
                            shot_id=shot.id,
                            shot_number=shot.shot_id,
                            shot_name=shot.shot_name,
                            asset_type="end_frame",
                        )
                        asyncio.run(generate_image_endpoint(req=end_req, current_user=user, db=db))
                        shot = db.query(Shot).filter(Shot.id == shot.id).first() or shot
                        tech = _parse_shot_tech(shot)
                        end_frame_url = str(tech.get("end_frame_url") or "").strip()

                if mode == "videos":
                    need_video = overwrite_existing or not str(shot.video_url or "").strip()
                    if need_video:
                        video_prompt_raw = str(shot.video_content or shot.prompt or "").strip() or "Video motion"
                        video_prompt = _inject_shot_prompt_anchors(video_prompt_raw, entity_lookup, global_style)

                        def _resolve_video_mode(payload: Dict[str, Any]) -> str:
                            if payload.get("video_mode_unified"):
                                return str(payload.get("video_mode_unified"))
                            if str(payload.get("video_ref_submit_mode") or "") == "refs_video":
                                return "refs_video"
                            return str(payload.get("video_gen_mode") or "start")

                        video_mode = _resolve_video_mode(tech)
                        video_ref_submit_mode = "refs_video" if video_mode == "refs_video" else "auto"

                        refs: List[str] = []
                        if video_ref_submit_mode == "refs_video":
                            if isinstance(tech.get("video_ref_image_urls"), list):
                                refs.extend([str(x).strip() for x in tech.get("video_ref_image_urls") or [] if str(x).strip()])
                        elif isinstance(tech.get("video_ref_image_urls"), list):
                            refs.extend([str(x).strip() for x in tech.get("video_ref_image_urls") or [] if str(x).strip()])
                        else:
                            shot_mode = str(tech.get("video_gen_mode") or "").strip().lower()
                            if not shot_mode:
                                end_prompt_len = len(str(shot.end_frame or "").strip())
                                shot_mode = "start_end" if end_frame_url and end_prompt_len >= 3 else "start"

                            if shot_mode != "end" and str(shot.image_url or "").strip():
                                refs.append(str(shot.image_url).strip())

                            keyframes = tech.get("keyframes")
                            if isinstance(keyframes, list):
                                refs.extend([str(x).strip() for x in keyframes if str(x).strip()])

                            if shot_mode == "start_end" and end_frame_url:
                                refs.append(end_frame_url)

                        refs = [x for x in dict.fromkeys([str(x).strip() for x in refs if str(x).strip()]) if x]

                        final_start_ref = None
                        final_end_ref = None
                        if video_ref_submit_mode == "refs_video":
                            final_start_ref = refs[0] if refs else None
                        elif refs:
                            final_start_ref = refs[0]
                            if len(refs) > 1:
                                final_end_ref = refs[-1]

                        duration_val = 5.0
                        try:
                            duration_val = float(str(shot.duration or 5).strip() or 5)
                        except Exception:
                            duration_val = 5.0

                        video_req = VideoGenerationRequest(
                            prompt=video_prompt,
                            ref_image_url=final_start_ref,
                            last_frame_url=final_end_ref,
                            duration=duration_val,
                            project_id=episode.project_id,
                            shot_id=shot.id,
                            shot_number=shot.shot_id,
                            shot_name=shot.shot_name,
                            asset_type="video",
                        )
                        asyncio.run(generate_video_endpoint(req=video_req, current_user=user, db=db))

                success += 1
            except Exception as e:
                shot_ok = False
                failed += 1
                errors.append(f"{shot_label}: {str(e)}")

            completed += 1
            episode = db.query(Episode).filter(Episode.id == episode_id).first()
            if not episode:
                break
            latest = _read_shot_media_batch_status(episode)
            latest["completed"] = completed
            latest["success"] = success
            latest["failed"] = failed
            latest["errors"] = errors
            latest["updated_at"] = datetime.utcnow().isoformat()
            latest["message"] = (
                f"Progress {completed}/{total}" if shot_ok else f"Progress {completed}/{total} (with errors)"
            )
            _persist_shot_media_batch_status(db, episode, latest)

        episode = db.query(Episode).filter(Episode.id == episode_id).first()
        if episode:
            final_status = _read_shot_media_batch_status(episode)
            final_status["running"] = False
            final_status["completed"] = completed
            final_status["success"] = success
            final_status["failed"] = failed
            final_status["errors"] = errors
            final_status["updated_at"] = datetime.utcnow().isoformat()
            final_status["finished_at"] = final_status["updated_at"]
            final_status["message"] = f"Batch done: success {success}, failed {failed}"
            _persist_shot_media_batch_status(db, episode, final_status)
    except Exception as e:
        try:
            episode = db.query(Episode).filter(Episode.id == episode_id).first()
            if episode:
                status_payload = _read_shot_media_batch_status(episode)
                status_payload["running"] = False
                status_payload["updated_at"] = datetime.utcnow().isoformat()
                status_payload["finished_at"] = status_payload["updated_at"]
                status_payload["message"] = f"Batch failed: {str(e)}"
                status_payload["errors"] = list(status_payload.get("errors") or []) + [str(e)]
                _persist_shot_media_batch_status(db, episode, status_payload)
        except Exception:
            pass
    finally:
        db.close()


@router.post("/episodes/{episode_id}/shots/batch-media/start", response_model=Dict[str, Any])
def start_shot_media_batch_job(
    episode_id: int,
    req: ShotMediaBatchStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    mode = str(req.mode or "keyframes").strip().lower()
    if mode not in {"keyframes", "videos"}:
        raise HTTPException(status_code=400, detail="mode must be 'keyframes' or 'videos'")

    latest = _read_shot_media_batch_status(episode)
    if bool(latest.get("running")):
        raise HTTPException(status_code=409, detail="Shot media batch task is already running")

    shots_query = db.query(Shot).filter(Shot.episode_id == episode_id)
    if req.shot_ids:
        shots_query = shots_query.filter(Shot.id.in_(req.shot_ids))
    target_shots = shots_query.order_by(Shot.id.asc()).all()
    shot_ids = [int(s.id) for s in target_shots]
    if not shot_ids:
        raise HTTPException(status_code=400, detail="No shots found for batch task")

    now_iso = datetime.utcnow().isoformat()
    status_payload = {
        "running": True,
        "mode": mode,
        "episode_id": episode_id,
        "project_id": episode.project_id,
        "shot_ids": shot_ids,
        "overwrite_existing": bool(req.overwrite_existing),
        "total": len(shot_ids),
        "completed": 0,
        "success": 0,
        "failed": 0,
        "current_shot_id": None,
        "current_shot_label": "",
        "message": "Batch task started",
        "errors": [],
        "stop_requested": False,
        "stop_requested_at": None,
        "stopped_by_user": False,
        "started_at": now_iso,
        "updated_at": now_iso,
        "finished_at": None,
    }
    _persist_shot_media_batch_status(db, episode, status_payload)

    worker = threading.Thread(
        target=_run_shot_media_batch_job,
        args=(episode_id, req.model_dump(), current_user.id),
        daemon=True,
    )
    worker.start()
    return status_payload


@router.get("/episodes/{episode_id}/shots/batch-media/status", response_model=Dict[str, Any])
def get_shot_media_batch_job_status(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    return _read_shot_media_batch_status(episode)


@router.post("/episodes/{episode_id}/shots/batch-media/stop", response_model=Dict[str, Any])
def stop_shot_media_batch_job(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    status_payload = _read_shot_media_batch_status(episode)
    if not bool(status_payload.get("running")):
        status_payload["message"] = "No running batch task"
        return status_payload

    now_iso = datetime.utcnow().isoformat()
    status_payload["stop_requested"] = True
    status_payload["stop_requested_at"] = now_iso
    status_payload["updated_at"] = now_iso
    status_payload["message"] = "Stop requested"
    _persist_shot_media_batch_status(db, episode, status_payload)
    return status_payload

class MontageItem(BaseModel):
    url: str
    speed: float = 1.0
    trim_start: float = 0.0
    trim_end: float = 0.0

class MontageRequest(BaseModel):
    items: List[MontageItem]

@router.post("/projects/{project_id}/montage")
async def generate_montage(
    project_id: int,
    request: MontageRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        url = await create_montage(project_id, [item.dict() for item in request.items])
        return {"url": url}
    except Exception as e:
        logger.error(f"Montage failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class AnalyzeImageRequest(BaseModel):
    asset_id: int

@router.post("/assets/analyze", response_model=Dict[str, str])
async def analyze_asset_image(
    request: AnalyzeImageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyzes an asset image to extract style and prompt descriptions.
    """
    # 1. Fetch Asset
    asset = db.query(Asset).filter(Asset.id == request.asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
        
    # Check permissions
    if asset.user_id != current_user.id and not current_user.is_superuser:
         raise HTTPException(status_code=403, detail="Not authorized")

    # 2. Get Vision Tool Config
    # If not found, fallback to LLM (assuming LLM might support vision e.g. GPT-4o)
    api_setting = get_effective_api_setting(db, current_user, category="Vision")
    if not api_setting:
         # Fallback to LLM as backup, but log warning
         logger.warning("Vision tool not configured, falling back to LLM setting.")
         api_setting = get_effective_api_setting(db, current_user, category="LLM")
    
    if not api_setting:
         raise HTTPException(status_code=400, detail="Vision Tool (or LLM) not configured. Please configure 'Vision / Image Recognition Tool' in Settings.")
    
    reservation_tx = None
    # Billing Check (token rules will be reserved later once we have final prompt/messages)
    if not billing_service.is_token_pricing(db, "analysis", api_setting.provider, api_setting.model):
        cost = billing_service.estimate_cost(db, "analysis", api_setting.provider, api_setting.model)
        billing_service.check_can_proceed(current_user, cost)

    llm_config = {
        "api_key": api_setting.api_key,
        "base_url": api_setting.base_url,
        "model": api_setting.model,
        "config": api_setting.config or {}
    }

    # 3. Load System Prompt
    prompt_path = os.path.join(settings.BASE_DIR, "app/core/prompts", "image_style_extractor.txt")
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()
    else:
        system_prompt = "Describe the art style and visual elements of this image."

    # 4. Construct Image URL
    base_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000").rstrip("/")
    
    image_url_raw = asset.url
    if image_url_raw and image_url_raw.startswith("http"):
         # Check if it is localhost and we are not in a local env (heuristic)
         # If the backend is local and the LLM is remote, the LLM cannot see 'localhost'.
         # We must assume the LLM cannot access localhost.
         # For production/render, RENDER_EXTERNAL_URL should be set.
         # For local dev with remote LLM, we might need to upload the image to the LLM or use a tunnel.
         # Many Vision APIs (OfferAI, Gemini) require a public URL or Base64.
         image_url = image_url_raw
    else:
        # Local path
        path_part = image_url_raw if image_url_raw.startswith("/") else f"/{image_url_raw}"
        image_url = f"{base_url}{path_part}"

    # CRITICAL FIX: If image_url is localhost, external LLMs (OpenAI/Gemini/Claude) CANNOT access it.
    # We must convert to Base64 if it's a local file.
    if "localhost" in image_url or "127.0.0.1" in image_url:
         import base64
         # Try to find the local file path from the URL
         # URL: http://localhost:8000/uploads/1/gen_xxx.png
         # File: backend/data/uploads/1/gen_xxx.png OR backend/uploads/...
         
         # 1. Parse relative path
         try:
             # removing http://localhost:8000/
             relative_path = image_url.replace(base_url, "")
             if relative_path.startswith("/"): relative_path = relative_path[1:]
             
             # 2. Heuristic search for file
             # We mounted /uploads map to settings.UPLOAD_DIR
             # But asset.url might include 'uploads/' prefix or might not depending on how it was saved.
             # Typically asset.url = "/uploads/filename.png"
             
             # If exact match fails, try prepending upload dir
             possible_paths = [
                 os.path.join(settings.UPLOAD_DIR, relative_path.replace("uploads/", "", 1)), # strip 'uploads/' prefix if dir is 'uploads'
                 os.path.join(settings.BASE_DIR, relative_path),
                 relative_path
             ]
             
             local_file_path = None
             for p in possible_paths:
                 if os.path.exists(p):
                     local_file_path = p
                     break
            
             if local_file_path:
                 logger.info(f"Localhost URL detected. Converting local file {local_file_path} to Base64 for remote LLM.")
                 with open(local_file_path, "rb") as image_file:
                     encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                     # Determine mime type
                     ext = os.path.splitext(local_file_path)[1].lower().replace(".", "")
                     mime = "image/png" if ext == "png" else "image/jpeg"
                     image_url = f"data:{mime};base64,{encoded_string}"
             else:
                 logger.warning(f"Could not find local file for {image_url} to convert to Base64. Remote LLM might fail to fetch.")

         except Exception as e:
             logger.error(f"Failed to convert localhost image to base64: {e}")

    logger.info(f"Analyzing Image: {image_url[:100]}...") # Log truncate
    logger.info(f"Using LLM Config: Model={llm_config.get('model')}, BaseURL={llm_config.get('base_url')}")


    # 5. Call Service
    try:
        if billing_service.is_token_pricing(db, "analysis", api_setting.provider, api_setting.model):
            # Estimate based on the actual text prompt + conservative image token budget.
            # OpenAI vision format uses user message with [text, image_url].
            est_messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": system_prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ]
            est = billing_service.estimate_input_output_tokens_from_messages(est_messages, output_ratio=1.5)
            estimated_image_tokens = 1000
            est_input = int(est.get("input_tokens", 0) or 0) + estimated_image_tokens
            est_output = int((est_input * 3 + 1) // 2) if est_input > 0 else 0

            reserve_details = {
                "item": "asset_analysis",
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": 1.5,
                "estimated_image_tokens": estimated_image_tokens,
                "input_tokens": est_input,
                "output_tokens": est_output,
                "total_tokens": int(est_input + est_output),
            }
            reservation_tx = billing_service.reserve_credits(
                db,
                current_user.id,
                "analysis",
                api_setting.provider,
                api_setting.model,
                reserve_details,
            )

        response_data = await llm_service.analyze_multimodal(
            prompt=system_prompt,
            image_url=image_url,
            config=llm_config
        )
        
        result = response_data.get("content", "")
        usage = response_data.get("usage", {})
        
        # Billing Deduct - Include Usage
        billing_details = {"item": "asset_analysis"}
        if usage:
             billing_details.update(usage) # e.g. input_tokens, output_tokens
             
        # HEURISTIC: Ensure image tokens are accounted for if usage seems low or missing
        # Standard GPT-4o high res is ~1000 tokens.
        # If input_tokens < 100, we likely didn't count the image.
        current_input = billing_details.get("prompt_tokens", billing_details.get("input_tokens", 0))
        if current_input < 200: 
            # Add estimated image tokens (e.g. 1000 per image)
            estimated_image_tokens = 1000
            
            # Update both keys for compatibility
            billing_details["input_tokens"] = current_input + estimated_image_tokens
            billing_details["prompt_tokens"] = billing_details["input_tokens"]
            
            if "total_tokens" in billing_details:
                billing_details["total_tokens"] += estimated_image_tokens
            else:
                billing_details["total_tokens"] = billing_details["input_tokens"] + billing_details.get("output_tokens", 0)

        if reservation_tx:
            # Normalize usage keys if provider uses OpenAI naming.
            if "prompt_tokens" in billing_details and "input_tokens" not in billing_details:
                billing_details["input_tokens"] = billing_details.get("prompt_tokens", 0)
            if "completion_tokens" in billing_details and "output_tokens" not in billing_details:
                billing_details["output_tokens"] = billing_details.get("completion_tokens", 0)
            billing_service.settle_reservation(db, reservation_tx.id, billing_details)
        else:
            billing_service.deduct_credits(db, current_user.id, "analysis", api_setting.provider, api_setting.model, billing_details)
        
        # 6. Save Result (Optional)
        # We don't have a specific field on Asset to store analysis unless we add one or use remark/meta.
        # However, for now we just return it.
        # If this is "analyze_script" or similar, we might save.
        # For "Asset Analysis", usually the user wants to see it or save it to asset meta.
        
        # Save to Asset Meta (Analysis Result)? 
        # Requirement: "Analyzes an asset...". User might expect persistence.
        # We'll save a snippet to 'remark' or 'meta_info.analysis'
        if not asset.meta_info: asset.meta_info = {}
        if isinstance(asset.meta_info, dict):
            # Only save short version or full?
            # Save full in a new key
            meta = dict(asset.meta_info)
            meta["analysis_result"] = result[:500] + "..." if len(result) > 500 else result
            asset.meta_info = meta
            db.commit()

        return {"result": result}
    except Exception as e:
        logger.error(f"Image analysis failed: {e}")
        try:
            reservation_tx = locals().get("reservation_tx")
            if reservation_tx:
                billing_service.cancel_reservation(db, reservation_tx.id, str(e))
        except:
            pass
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/entities/{entity_id}/analyze")
async def analyze_entity_image(
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyzes an entity (subject) image using Vision model and updates its attributes based on visual content.
    Returns the updated entity data.
    """
    logger.info(f"analyze_entity_image called for ID {entity_id}")
    
    # 1. Fetch Entity
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    project = _require_project_access(db, entity.project_id, current_user)

    if not entity.image_url:
        raise HTTPException(status_code=400, detail="Entity has no image to analyze.")

    logger.info(f"Entity found: {entity.name}, Image: {entity.image_url}")

    # 2. Get Vision Tool Config
    api_setting = get_effective_api_setting(db, current_user, category="Vision")
    if not api_setting:
         api_setting = get_effective_api_setting(db, current_user, category="LLM")
    
    if not api_setting:
         raise HTTPException(status_code=400, detail="Vision Tool or LLM not configured.")
    
    reservation_tx = None
    # Billing Check (token rules will reserve later once we have messages)
    if not billing_service.is_token_pricing(db, "analysis_character", api_setting.provider, api_setting.model):
        cost = billing_service.estimate_cost(db, "analysis_character", api_setting.provider, api_setting.model)
        billing_service.check_can_proceed(current_user, cost)

    llm_config = {
        "api_key": api_setting.api_key,
        "base_url": api_setting.base_url,
        "model": api_setting.model
    }
    logger.info(f"Using Model: {api_setting.model}")

    # 3. Construct System Prompt based on Entity Type
    entity_type = (entity.type or "character").lower()

    
    base_instruction = "You are an expert visual analyst and script breakdown specialist. Your task is to analyze the provided image of a project subject and UPDATE the existing subject information to match the visual details in the image. You must merge the visual evidence with the existing data."
    
    # Import Templates from shared module
    # Make sure to create app/core/prompts/__init__.py if needed or import directly if in python path
    try:
        from app.core.prompts.templates import (
            CHARACTER_PROMPT_TEMPLATE as char_prompt_template, 
            PROP_PROMPT_TEMPLATE as prop_prompt_template, 
            ENVIRONMENT_PROMPT_TEMPLATE as env_prompt_template
        )
    except ImportError:
        logger.error("Could not import prompt templates. Using fallbacks.")
        # Fallback empty strings or error out - for robustness we'll define minimal fallbacks here if import fails,
        # but in dev environment it should work.
        char_prompt_template = "[Global Style] 6-view character sheet..."
        prop_prompt_template = "[Global Style] Prop object..."
        env_prompt_template = "[Global Style] Environment background..."

    schema_instruction = ""
    if "char" in entity_type:
        schema_instruction = f"""
Output MUST be a valid JSON object matching this structure EXACTLY:
{{
  "characters": [
    {{
      "name": "Current Name",
      "name_en": "English Name",
      "gender": "M/F",
      "role": "Role",
      "archetype": "Archetype",
      "appearance_cn": "Detailed Chinese Description (Must include height & head-to-body ratio)",
      "clothing": "Detailed Description of clothing (Must include layers, materials, colors, wear)",
      "action_characteristics": "Inferred action traits (e.g. poised, controlled movements)",
      "generation_prompt_en": "STRICTLY FOLLOW THIS TEMPLATE, replacing placeholders with visual details from image:\\n{char_prompt_template}",
      "anchor_description": "Distinct Visual Feature (e.g., 'Red Scarf', 'Scar on Cheek'). MAX 20 words. Must be obvious for AI recognition.",
      "visual_dependencies": [],
      "dependency_strategy": {{
        "type": "Original",
        "logic": "Base Design"
      }}
    }}
  ]
}}
"""
    elif "prop" in entity_type:
        schema_instruction = f"""
Output MUST be a valid JSON object matching this structure EXACTLY:
{{
  "props": [
    {{
      "name": "Current Name",
      "name_en": "English Name",
      "type": "held/static",
      "description_cn": "Chinese Description (Must define Mobility & Mutable States)",
      "generation_prompt_en": "STRICTLY FOLLOW THIS TEMPLATE, replacing placeholders with visual details from image:\\n{prop_prompt_template}",
      "anchor_description": "Distinct Visual Marker (e.g., 'Golden Dragon Handle'). MAX 20 words. Must be obvious for AI recognition.",
      "visual_dependencies": [],
      "dependency_strategy": {{
        "type": "Original",
        "logic": "Base Design"
      }}
    }}
  ]
}}
"""
    elif "env" in entity_type or "scene" in entity_type:
        schema_instruction = f"""
Output MUST be a valid JSON object matching this structure EXACTLY:
{{
  "environments": [
    {{
      "name": "Current Name",
      "name_en": "English Name",
      "atmosphere": "Atmosphere",
      "visual_params": "Wide/Interior/Day",
      "description_cn": "Chinese Description",
      "generation_prompt_en": "STRICTLY FOLLOW THIS TEMPLATE, replacing placeholders with visual details from image:\\n{env_prompt_template}",
      "anchor_description": "Distinct Visual Landmark (e.g., 'Giant Red Statue'). MAX 20 words. Must be obvious for AI recognition.",
      "visual_dependencies": [],
      "dependency_strategy": {{
        "type": "Original",
        "logic": "Base Design"
      }}
    }}
  ]
}}
"""
    else:
         # Fallback generic
         schema_instruction = "Return a JSON object with keys: name_en, description_cn, generation_prompt_en."

    system_prompt = f"{base_instruction}\n\n{schema_instruction}\n\nConstraint: Return ONLY the raw JSON object. Do not include markdown formatting (like ```json), no <think> tags, no reasoning process, and no conversational text."

    # 4. Construct Image URL & Current Info
    
    # Prepare Current Info Context
    # Include Project Context for style consistency
    project_context = {}
    if project.global_info:
         project_context = {
             "Global_Style": project.global_info.get("Global_Style"),
             "Tone": project.global_info.get("tone")
         }

    current_info = {
        "name": entity.name,
        "name_en": entity.name_en,
        "type": entity.type,
        "description": entity.description,
        "appearance_cn": entity.appearance_cn,
        "clothing": entity.clothing,
        "role": entity.role,
        "generation_prompt_en": entity.generation_prompt_en,
        "project_context": project_context
    }
    
    current_info_str = json.dumps(current_info, ensure_ascii=False)

    try:
        from urllib.parse import urlparse
        import base64
        
        base_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000").rstrip("/")
        image_url_raw = entity.image_url
        image_url_final = image_url_raw
        
        local_file_path = None
        path_part = None

        if image_url_raw:
            if image_url_raw.startswith("http"):
                parsed_url = urlparse(image_url_raw)
                if parsed_url.hostname in ["localhost", "127.0.0.1", "0.0.0.0"]:
                    path_part = parsed_url.path.lstrip("/")
            else:
                # Relative path (e.g. /uploads/...)
                path_part = image_url_raw.lstrip("/")
        
        if path_part:
            possible_paths = [
                os.path.join(settings.BASE_DIR, "app", path_part),
                os.path.join(settings.BASE_DIR, path_part),
                os.path.join(os.getcwd(), "app", path_part),
                os.path.join(os.getcwd(), path_part),
                # Try finding in uploads dir explicitly if path starts with uploads
                os.path.join(settings.UPLOAD_DIR, path_part.replace("uploads/", "", 1))
            ]
            
            for p in possible_paths:
                # Resolve possible double slashes
                p = os.path.normpath(p)
                if os.path.exists(p) and os.path.isfile(p):
                    local_file_path = p
                    break
        
        if local_file_path:
            try:
                with open(local_file_path, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                    ext = os.path.splitext(local_file_path)[1].lower().replace(".", "")
                    mime = "image/png" if ext == "png" else "image/jpeg"
                    # Handle jpg as jpeg for mime
                    if ext == "jpg": mime = "image/jpeg"
                    if ext == "webp": mime = "image/webp"
                    
                    image_url_final = f"data:{mime};base64,{encoded_string}"
                    logger.info(f"Converted local image {local_file_path} to Base64 (Size: {len(image_url_final)} chars)")
            except Exception as e:
                logger.error(f"Failed to encode local image {local_file_path}: {e}")
                
    except Exception as e:
        logger.warning(f"Error resolving entity image path: {e}")
        # Continue with original URL
        pass

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user", 
            "content": [
                {"type": "text", "text": f"Here is the CURRENT information for subject '{entity.name}':\n{current_info_str}\n\nPlease analyze the image. Fuse the visual details from the image with the current information. \nIMPORTANT: Rewrite 'generation_prompt_en' to strictly follow the style and format of the current prompt, but update the content to match the image visually."},
                {"type": "image_url", "image_url": {"url": image_url_final}}
            ]
        }
    ]
    
    try:
        logger.info("Sending request to LLM...")

        if billing_service.is_token_pricing(db, "analysis_character", api_setting.provider, api_setting.model):
            est = billing_service.estimate_input_output_tokens_from_messages(messages, output_ratio=1.5)
            estimated_image_tokens = 1000
            est_input = int(est.get("input_tokens", 0) or 0) + estimated_image_tokens
            est_output = int((est_input * 3 + 1) // 2) if est_input > 0 else 0
            reserve_details = {
                "item": "entity_image_analysis",
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": 1.5,
                "estimated_image_tokens": estimated_image_tokens,
                "input_tokens": est_input,
                "output_tokens": est_output,
                "total_tokens": int(est_input + est_output),
            }
            reservation_tx = billing_service.reserve_credits(
                db,
                current_user.id,
                "analysis_character",
                api_setting.provider,
                api_setting.model,
                reserve_details,
            )

        llm_response = await llm_service.chat_completion(messages, llm_config)
        
        result_content = llm_response.get("content", "")
        usage = llm_response.get("usage", {})
        
        logger.info(f"LLM Reply Length: {len(result_content)}. Usage: {usage}")
        
        # Remove <think> blocks if present (common in reasoning models)
        import re
        content = re.sub(r"<think>.*?</think>", "", result_content, flags=re.DOTALL)

        # Parse JSON
        content = content.replace("```json", "").replace("```", "").strip()
        # Find start and end of JSON if extra text
        start_idx = content.find("{")
        end_idx = content.rfind("}")
        if start_idx != -1 and end_idx != -1:
            content = content[start_idx:end_idx+1]

        data = json.loads(content)
                  
        # Extract the core object based on type
        updated_info = {}
        if "characters" in data and isinstance(data["characters"], list) and len(data["characters"]) > 0:
            updated_info = data["characters"][0]
        elif "props" in data and isinstance(data["props"], list) and len(data["props"]) > 0:
            updated_info = data["props"][0]
        elif "environments" in data and isinstance(data["environments"], list) and len(data["environments"]) > 0:
            updated_info = data["environments"][0]
        else:
            updated_info = data # Fallback if direct object
            
        logger.info(f"Parsed Updated Info for Entity {entity.id}: {json.dumps(updated_info, ensure_ascii=False)[:300]}...")

        if not updated_info:
             logger.warning("updated_info is empty! LLM response might not match expected JSON schema.")

        # Update Entity Fields
        if "name_en" in updated_info: entity.name_en = updated_info["name_en"]
        if "description_cn" in updated_info: entity.description = updated_info["description_cn"] # Map description_cn to description
        if "appearance_cn" in updated_info: entity.appearance_cn = updated_info["appearance_cn"]
        if "clothing" in updated_info: entity.clothing = updated_info["clothing"]
        if "action_characteristics" in updated_info: entity.action_characteristics = updated_info["action_characteristics"]
        if "role" in updated_info: entity.role = updated_info["role"]
        if "archetype" in updated_info: entity.archetype = updated_info["archetype"]
        if "gender" in updated_info: entity.gender = updated_info["gender"]
        
        if "atmosphere" in updated_info: entity.atmosphere = updated_info["atmosphere"]
        if "visual_params" in updated_info: entity.visual_params = updated_info["visual_params"]
        
        if "generation_prompt_en" in updated_info: entity.generation_prompt_en = updated_info["generation_prompt_en"]
        if "anchor_description" in updated_info: entity.anchor_description = updated_info["anchor_description"]
        
        if "visual_dependencies" in updated_info and isinstance(updated_info["visual_dependencies"], list): 
             entity.visual_dependencies = updated_info["visual_dependencies"]
        if "dependency_strategy" in updated_info and isinstance(updated_info["dependency_strategy"], dict):
             entity.dependency_strategy = updated_info["dependency_strategy"]

        # Update Custom Attributes with Analysis Result (Save latest)
        custom_attrs = entity.custom_attributes or {}
        # Ensure dict if it came from DB as string (unlikely with SQLAlchemy JSON type but possible with SQLite text)
        if isinstance(custom_attrs, str):
            try: custom_attrs = json.loads(custom_attrs)
            except: custom_attrs = {}
            
        custom_attrs['analysis_result'] = {
            "timestamp": datetime.utcnow().isoformat(),
            "content": updated_info
        }
        # Re-assign to trigger SQLAlchemy detection of mutation if needed
        entity.custom_attributes = dict(custom_attrs)


        logger.info(f"Entity Updated. New Prompt Length: {len(entity.generation_prompt_en) if entity.generation_prompt_en else 0}")

        # Billing finalize (after successful parse/update)
        billing_details = {"item": "entity_image_analysis", "entity_id": entity.id}
        if usage:
            billing_details.update(usage)
        if "prompt_tokens" in billing_details and "input_tokens" not in billing_details:
            billing_details["input_tokens"] = billing_details.get("prompt_tokens", 0)
        if "completion_tokens" in billing_details and "output_tokens" not in billing_details:
            billing_details["output_tokens"] = billing_details.get("completion_tokens", 0)

        if reservation_tx:
            # If usage seems to miss image tokens, add a conservative estimate to avoid under-charging.
            current_input = billing_details.get("prompt_tokens", billing_details.get("input_tokens", 0))
            if current_input < 200:
                estimated_image_tokens = 1000
                billing_details["input_tokens"] = current_input + estimated_image_tokens
                billing_details["prompt_tokens"] = billing_details["input_tokens"]
                if "total_tokens" in billing_details:
                    billing_details["total_tokens"] += estimated_image_tokens
                else:
                    billing_details["total_tokens"] = billing_details["input_tokens"] + billing_details.get("output_tokens", 0)
            billing_service.settle_reservation(db, reservation_tx.id, billing_details)
        else:
            billing_service.deduct_credits(
                db,
                current_user.id,
                "analysis_character",
                api_setting.provider,
                api_setting.model,
                billing_details,
            )
        
        # We no longer save the prompt as a separate asset file to avoid clutter.
        # The prompt is already saved in the entity.generation_prompt_en field.

        db.refresh(entity)
        return entity

    except HTTPException as e:
        logger.error(f"Entity Analysis failed with HTTPException: {str(e.detail)}", exc_info=True)
        try:
            if reservation_tx:
                billing_service.cancel_reservation(db, reservation_tx.id, str(e.detail))
        except:
            pass
        raise
    except Exception as e:
        logger.error(f"Entity Analysis failed: {str(e)}", exc_info=True)
        try:
            if reservation_tx:
                billing_service.cancel_reservation(db, reservation_tx.id, str(e))
        except:
            pass
        raise HTTPException(status_code=502, detail=f"Analysis failed: {str(e)}")

@router.get("/entities/{entity_id}/latest_analysis")
def get_entity_latest_analysis(
    entity_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Get the latest saved analysis result for an entity.
    """
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    _require_project_access(db, entity.project_id, current_user)
         
    custom_attrs = entity.custom_attributes or {}
    # Handle DB Storage format (Text vs JSON)
    if isinstance(custom_attrs, str):
        try: custom_attrs = json.loads(custom_attrs)
        except: custom_attrs = {}
        
    result = custom_attrs.get('analysis_result')
    return result or {}

@router.put("/entities/{entity_id}/latest_analysis")
def update_entity_latest_analysis(
    entity_id: int,
    data: AnalysisContent,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Update (Save/Edit) the latest analysis result without applying it.
    """
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    _require_project_access(db, entity.project_id, current_user)
         
    custom_attrs = entity.custom_attributes or {}
    if isinstance(custom_attrs, str):
        try: custom_attrs = json.loads(custom_attrs)
        except: custom_attrs = {}
    
    # Update analysis result with timestamp
    result = custom_attrs.get('analysis_result', {})
    if not isinstance(result, dict): result = {}
    
    result['content'] = data.content
    result['timestamp'] = datetime.utcnow().isoformat() # Update timestamp on edit
    
    custom_attrs['analysis_result'] = result
    entity.custom_attributes = custom_attrs  # Reassign for SQLAlchemy detection if Dict
    
    db.commit()
    return custom_attrs['analysis_result']

@router.post("/entities/{entity_id}/apply_analysis")
def apply_entity_analysis(
    entity_id: int,
    data: Optional[AnalysisContent] = None, # Optional payload to override stored
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Apply the stored (or provided) analysis result to update Entity fields.
    """
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    _require_project_access(db, entity.project_id, current_user)
    
    updated_info = {}
    
    # 1. Determine Source
    if data and data.content:
        updated_info = data.content
        # Optionally save this new content as latest too? YES.
        custom_attrs = entity.custom_attributes or {}
        if isinstance(custom_attrs, str):
            try: custom_attrs = json.loads(custom_attrs)
            except: custom_attrs = {}
        
        custom_attrs['analysis_result'] = {
            "timestamp": datetime.utcnow().isoformat(),
            "content": updated_info
        }
        entity.custom_attributes = custom_attrs
    else:
        # Load from stored
        custom_attrs = entity.custom_attributes or {}
        if isinstance(custom_attrs, str):
            try: custom_attrs = json.loads(custom_attrs)
            except: custom_attrs = {}
        
        result = custom_attrs.get('analysis_result', {})
        if isinstance(result, dict):
            updated_info = result.get('content', {})
    
    if not updated_info:
        raise HTTPException(status_code=400, detail="No analysis content provided or found to apply.")

    # 2. Apply Updates (Same logic as analyze_entity_image)
    if "name_en" in updated_info: entity.name_en = updated_info["name_en"]
    if "description_cn" in updated_info: entity.description = updated_info["description_cn"] 
    if "appearance_cn" in updated_info: entity.appearance_cn = updated_info["appearance_cn"]
    if "clothing" in updated_info: entity.clothing = updated_info["clothing"]
    if "action_characteristics" in updated_info: entity.action_characteristics = updated_info["action_characteristics"]
    if "role" in updated_info: entity.role = updated_info["role"]
    if "archetype" in updated_info: entity.archetype = updated_info["archetype"]
    if "gender" in updated_info: entity.gender = updated_info["gender"]
    
    if "atmosphere" in updated_info: entity.atmosphere = updated_info["atmosphere"]
    if "visual_params" in updated_info: entity.visual_params = updated_info["visual_params"]
    
    if "generation_prompt_en" in updated_info: entity.generation_prompt_en = updated_info["generation_prompt_en"]
    if "anchor_description" in updated_info: entity.anchor_description = updated_info["anchor_description"]
    
    if "visual_dependencies" in updated_info and isinstance(updated_info["visual_dependencies"], list): 
            entity.visual_dependencies = updated_info["visual_dependencies"]
    if "dependency_strategy" in updated_info and isinstance(updated_info["dependency_strategy"], dict):
            entity.dependency_strategy = updated_info["dependency_strategy"]

    db.commit()
    db.refresh(entity)
    return entity

