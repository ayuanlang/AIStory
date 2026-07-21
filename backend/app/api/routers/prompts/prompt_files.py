# -*- coding: utf-8 -*-
"""Prompts/analyze section routes — symbols pulled from shared module."""
from __future__ import annotations

from app.api.routers.prompts import shared as _shared

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


@router.get("/projects/{project_id}/subject_inventory_prompt")
async def get_project_subject_inventory_prompt(
    project_id: int,
    episode_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        _require_project_access(db, project_id, current_user)
        scoped_episode_id = None
        try:
            if episode_id is not None and int(episode_id) > 0:
                scoped_episode_id = int(episode_id)
        except Exception:
            scoped_episode_id = None
        if not scoped_episode_id:
            # Asset injection must stay episode-scoped; refuse project-wide inventory.
            return {
                "inventory_block": "",
                "inventory_guidance": "",
                "inventory_system_guard": "",
                "episode_id": None,
                "scoped": False,
                "detail": "episode_id is required; inventory injection is episode-scoped only.",
            }
        episode_row = db.query(Episode).filter(
            Episode.id == int(scoped_episode_id),
            Episode.project_id == int(project_id),
            _active_episode_clause(),
        ).first()
        if not episode_row:
            raise HTTPException(status_code=404, detail="Episode not found in this project")
        inventory = _build_project_subject_inventory(
            db,
            project_id,
            limit_per_type=80,
            episode_id=scoped_episode_id,
        )
        
        inventory_block = _format_project_subject_inventory_block(inventory)
        inventory_system_guard = (
            "\n\n"
            "[Existing Subjects Reuse Guard - High Priority]\n"
            "The injected Existing Subject Index contains authoritative reusable subjects for THIS episode only.\n"
            "You MUST reuse these existing subjects first whenever they match the script.\n"
            "Do NOT rename, redefine, replace, overwrite, or regenerate them as new entities.\n"
            "Only create a new subject when the script clearly requires an entity that is not already present in the inventory.\n"
            "If the injected inventory is empty, you must still treat it as an explicit empty baseline rather than as a missing section.\n"
            "If you output entity JSON, existing inventory subjects must be reused by reference and MUST NOT be duplicated as newly generated entities."
        )
        inventory_guidance = (
            "Episode Existing Subject Index reuse rules:\n"
            "- Treat the above Subject Index as authoritative identifiers for the current episode only.\n"
            "- Do not reuse or invent subjects from other episodes.\n"
            "- This inventory block is always present, even when all categories are empty.\n"
            "- Extract and reuse the Entities as your baselines. Do not duplicate existing inventory subjects in newly generated entity outputs."
        )

        return {
            "inventory_block": inventory_block,
            "inventory_guidance": inventory_guidance,
            "inventory_system_guard": inventory_system_guard,
            "episode_id": scoped_episode_id,
            "scoped": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch subject inventory prompt: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})



@router.get("/prompts/{filename:path}")
async def get_prompt_content(filename: str, current_user: User = Depends(get_current_user)):
    """Retrieve content of a prompt file."""
    normalized = str(filename or "").strip().strip("/")

    if normalized == "skills":
        return await list_prompt_skills(current_user)

    if normalized.startswith("skills/"):
        skill_id = normalized.split("/", 1)[1].strip()
        if skill_id and "/" not in skill_id and not skill_id.endswith(('.md', '.txt', '.json')):
            return await get_prompt_skill_detail(skill_id, current_user)

    debug_info = _build_prompt_resolution_debug(filename)

    try:
        content = _resolve_prompt_text(filename)
        logger.info(
            "Prompt content loaded: filename=%s alias=%s content_len=%s",
            filename,
            debug_info.get("alias"),
            len(content or ""),
        )
        return {
            "content": content,
            "debug": {
                "prompt_ref": debug_info.get("prompt_ref"),
                "alias": debug_info.get("alias"),
                "content_len": len(content or ""),
            },
        }
    except FileNotFoundError as exc:
        logger.error(
            "Prompt file not found: filename=%s err=%s debug=%s",
            filename,
            exc,
            json.dumps(debug_info, ensure_ascii=False, default=str),
        )
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"Prompt file '{filename}' not found.",
                "prompt": filename,
                "debug": debug_info,
            },
        )
    except Exception as exc:
        logger.exception(
            "Prompt file load failed: filename=%s debug=%s",
            filename,
            json.dumps(debug_info, ensure_ascii=False, default=str),
        )
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Failed to load prompt file '{filename}'.",
                "prompt": filename,
                "error_type": exc.__class__.__name__,
                "error": str(exc),
                "debug": debug_info,
            },
        )



@router.put("/prompts/{filename:path}")
async def update_prompt_content(
    filename: str,
    payload: PromptContentUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    if not bool(getattr(current_user, "is_superuser", False) or getattr(current_user, "is_system", False)):
        raise HTTPException(status_code=403, detail="Only system/admin users can update prompt files")

    prompt_path = _resolve_prompt_file_path(filename)
    content = str(getattr(payload, "content", "") or "")
    prompt_path.write_text(content, encoding="utf-8")
    logger.info(
        "Prompt content updated: filename=%s path=%s user_id=%s content_len=%s",
        filename,
        str(prompt_path),
        getattr(current_user, "id", None),
        len(content),
    )
    return {
        "ok": True,
        "prompt": filename,
        "path": str(prompt_path),
        "content_len": len(content),
        "updated_at": now_bj_iso(),
    }




