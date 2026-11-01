# -*- coding: utf-8 -*-
"""Projects / episodes / scenes / shots workspace routes (P6-P8 remainder)."""
from __future__ import annotations
import logging
import os
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.time_utils import BEIJING_TZ, now_bj_iso
from app.db.session import SessionLocal, get_db
from app.models.all_models import *
# Star-import must not shadow the datetime class (all_models used to export the module).
from datetime import datetime, timedelta  # noqa: E402
from app.services.agent_service import agent_service
from app.services.billing_service import billing_service
from app.services.llm_service import llm_service
logger = logging.getLogger("api_logger")
router = APIRouter(tags=["projects-workspace"])

from app.services.soft_delete import (  # noqa: E402
    _active_episode_clause,
    _active_project_clause,
    _active_scene_clause,
    _active_shot_clause,
)


def _bind_endpoint_helpers(*, include_routers: bool = True) -> None:
    # Early call uses include_routers=False to avoid circular facade imports.
    from app.api.routers.helper_bind import bind_shared_helpers
    bind_shared_helpers(globals(), __name__, include_routers=include_routers)

_bind_endpoint_helpers(include_routers=False)

# --- Projects ---
from app.schemas.project import (  # noqa: E402
    ProjectCreate,
    ProjectOut,
    ProjectShareCreate,
    ProjectShareOut,
    ProjectUpdate,
)

from app.schemas.asset_review import (  # noqa: E402,F401
    ProjectAssetReviewMessageCreate,
    ProjectAssetReviewMessageOut,
    ProjectAssetReviewRoundCreate,
    ProjectAssetReviewRoundOut,
    ProjectAssetReviewThreadCreate,
    ProjectAssetReviewThreadOut,
    ProjectAssetReviewThreadReadUpdate,
    ProjectAssetReviewThreadStatusUpdate,
)


from app.services.project_access import (  # noqa: E402,F401
    _ASSET_REVIEW_DECISIONS,
    _ASSET_REVIEW_MESSAGE_TYPES,
    _ASSET_REVIEW_ROUND_STATUSES,
    _ASSET_REVIEW_SCOPE_TYPES,
    _ASSET_REVIEW_THREAD_STATUSES,
    _PROJECT_SHARE_PERMISSION_KEYS,
    _PROJECT_SHARE_ROLES,
)



# Project generation defaults (canonical: app.services.project_generation_defaults).
from app.services.project_generation_defaults import (  # noqa: E402,F401
    _PROJECT_LEVEL_GENERATION_DEFAULT_KEYS,
    _resolve_project_video_sound,
    _ensure_project_generation_defaults,
)


# Shared with billing estimate / other light callers (avoid duplicating tables).
from app.services.project_visual_resolution import (
    PROJECT_IMAGE_SIZE_LONG_EDGE_MAP as _PROJECT_IMAGE_SIZE_LONG_EDGE_MAP,
    PROJECT_IMAGE_SIZE_SQUARE_MAP as _PROJECT_IMAGE_SIZE_SQUARE_MAP,
    PROJECT_RESOLUTION_PRESETS as _PROJECT_RESOLUTION_PRESETS,
    infer_dims_from_video_resolution_tier as _infer_dims_from_video_resolution_tier,
    infer_project_resolution as _infer_project_resolution,
    normalize_project_image_size as _normalize_project_image_size,
    normalize_project_video_resolution as _normalize_project_video_resolution,
    parse_aspect_ratio_pair as _parse_aspect_ratio_pair,
    project_video_resolution_label as _project_video_resolution_label,
)



# Episode utils (canonical: app.services.project_episode_utils).
from app.services.project_episode_utils import (  # noqa: E402,F401
    _to_positive_int_or_none,
    _safe_json_dict,
    _episode_runtime_info_from_episode,
    _extract_episode_number_from_title,
    _resolve_episode_sort_number,
    _sort_project_episodes,
)


# Project share / review / access (canonical: app.services.project_access).
from app.services.project_access import (  # noqa: E402,F401
    ProjectAssetReviewThread,
    ProjectAssetReviewRound,
    ProjectAssetReviewMessage,
    ProjectAssetReviewThreadModel,
    ProjectAssetReviewRoundModel,
    ProjectAssetReviewMessageModel,
    _PROJECT_SHARE_ROLES,
    _PROJECT_SHARE_PERMISSION_KEYS,
    _ASSET_REVIEW_THREAD_STATUSES,
    _ASSET_REVIEW_SCOPE_TYPES,
    _ASSET_REVIEW_DECISIONS,
    _ASSET_REVIEW_ROUND_STATUSES,
    _ASSET_REVIEW_MESSAGE_TYPES,
    _is_project_shared_with_user,
    _get_project_share_record,
    _normalize_project_share_role,
    _normalize_project_share_permissions,
    _project_share_supports_mapped_field,
    _apply_project_share_access_fields,
    _build_project_share,
    _project_share_has_permission,
    _project_share_can_review_assets,
    _normalize_asset_review_scope_type,
    _normalize_asset_review_decision,
    _normalize_asset_review_message_type,
    _normalize_int_list,
    _PROJECT_GLOBAL_INFO_SHARE_USERS_KEY,
    _PROJECT_GLOBAL_INFO_REVIEWER_USERS_KEY,
    _normalize_user_identifier_list,
    _resolve_project_share_users,
    _sync_project_managed_shares,
    _serialize_project_share,
    _review_thread_has_unread,
    _mark_review_thread_read_for_user,
    _serialize_review_thread,
    _serialize_review_round,
    _serialize_review_message,
    _ensure_review_scope_has_dimension,
    _validate_review_target_ids_for_project,
    _resolve_thread_sender_role,
    _resolve_review_reviewer,
    _require_review_thread_access,
    _require_review_round_access,
    _require_project_access,
    _attach_project_flags,
)


# Scene no utils (canonical: app.services.scene_no_utils).
from app.services.scene_no_utils import (  # noqa: E402,F401
    _scene_no_sort_key,
    _sort_scenes_by_scene_no,
    _canonicalize_scene_no,
    _scene_no_lookup_keys,
    _find_active_scene_by_scene_no,
)

# _active_shot_clause -> soft_delete



# Deletion / soft-delete ops (canonical: app.services.deletion_ops).
from app.services.deletion_ops import (  # noqa: E402,F401
    _active_entity_clause,
    _active_asset_clause,
    _resolve_record_episode_id,
    _assert_episode_scoped_delete,
    _is_soft_deleted,
    _restore_soft_deleted_record,
    _DELETION_RESOURCE_MODELS,
    _DELETION_RESTORE_ORDER,
    _start_deletion_batch,
    _track_deletion_batch_items,
    _finalize_deletion_batch,
    _require_project_owner_any_state,
    _serialize_deletion_batch,
    _restore_deletion_batch,
    _soft_delete_shots,
    _hard_purge_episode_scenes,
    _purge_episode_scene_progress,
    _soft_delete_scenes,
    _soft_delete_assets,
    _soft_delete_entities,
    _soft_delete_episode_children,
    _soft_delete_project_children,
)




def get_project_cover_image(db: Session, project_id: int) -> Optional[str]:
    # 0. 优先使用 named cover 或 type cover 相关的
    poster_entities = db.query(Entity).filter(
        Entity.project_id == project_id,
        _active_entity_clause(),
        or_(
            Entity.name.in_(["封面海报", "海报", "封面", "cover", "poster"]),
            Entity.name.ilike("%海报%"),
            Entity.name.ilike("%封面%"),
            Entity.name.ilike("%cover%"),
            Entity.name.ilike("%poster%"),
            Entity.type.in_(["poster", "posters", "cover", "project_cover", "cover_image"]),
            Entity.type.ilike("%poster%"),
            Entity.type.ilike("%cover%")
        ),
        Entity.image_url != None,
        Entity.image_url != ""
    ).all()
    
    poster_entity = None
    for p in poster_entities:
        if p.name == "封面海报":
            poster_entity = p
            break
        if not poster_entity:
            poster_entity = p

    if poster_entity:
        return _refresh_managed_media_url(poster_entity.image_url, db)

    project = db.query(Project).filter(Project.id == project_id).first()
    if project and isinstance(project.global_info, dict):
        configured_cover = str(project.global_info.get("cover_image") or project.global_info.get("coverImage") or "").strip()
        if configured_cover:
            return _refresh_managed_media_url(configured_cover, db)

    # 1. Try to find first valid image in Shots
    # Check if project_id is populated in shots first (optimization)
    shot = db.query(Shot).filter(Shot.project_id == project_id, Shot.image_url != None, Shot.image_url != "").first()
    if shot:
        return _refresh_managed_media_url(shot.image_url, db)
        
    # If project_id not reliable in shots, try join (fallback)
    shot = db.query(Shot).join(Scene).join(Episode).filter(Episode.project_id == project_id, Shot.image_url != None, Shot.image_url != "").first()
    if shot:
        return _refresh_managed_media_url(shot.image_url, db)

    # 2. Try Scenes? (Scene logic currently undefined as no direct image column, skip to Entities)
    
    # 3. Try Entities (Subjects)
    entity = db.query(Entity).filter(Entity.project_id == project_id, Entity.image_url != None, Entity.image_url != "").first()
    if entity:
        return _refresh_managed_media_url(entity.image_url, db)
        
    # 4. Try Assets? (Maybe, but user said Shots, Scenes, Subjects)
    
    return None



# Markdown section helper (canonical: app.services.markdown_generation).
from app.services.markdown_generation import (  # noqa: E402,F401
    _extract_md_section,
)


# Shared with script_analysis_flow (must not live only in this megamodule).
from app.services.llm_markdown_sanitize import (
    sanitize_llm_markdown_output,
    sanitize_subject_index_text,
)



# Shot markdown helpers (canonical: app.services.shot_markdown).
from app.services.shot_markdown import (  # noqa: E402,F401
    _is_provider_moderation_block_response,
    _split_markdown_row_escaped,
    _is_markdown_table_separator,
    _find_shot_pipe_merge_column_indices,
    _reconcile_shot_markdown_row_cells,
    _normalize_markdown_table_cells,
    _looks_like_markdown_table_row_for_shots,
    _is_shot_markdown_header_row,
    _is_placeholder_shot_row,
    _REAL_SHOT_ID_RE,
    _shot_id_cell_looks_real,
    _extract_shot_markdown_table_blocks,
    _score_shot_markdown_table_block,
    sanitize_shots_markdown_table_text,
    parse_shots_markdown_table,
    SHOT_MARKDOWN_COLUMN_WHITELIST,
    _normalize_shot_markdown_col_key,
    _SHOT_MARKDOWN_DEFAULT_HEADERS,
    _SHOT_REQUIRED_ROW_FIELDS,
    _coerce_shot_row_associated_entities_or_default,
    _SHOT_REQUIRED_ROW_FIELD_GROUPS,
    _shot_row_technical_notes_dict,
    _pick_shot_cell,
    _pick_shot_video_prompt_cell,
    _collect_missing_shot_required_fields,
    _normalize_shot_business_id,
    _extract_shot_row_business_id,
    _shot_record_db_id,
    _shot_record_scene_id,
    _shot_record_business_key,
    _dedupe_shot_rows_for_import,
    _dedupe_active_shot_records_for_display,
    _soft_delete_duplicate_active_shots_in_db,
    _find_active_shot_by_business_id,
    _escape_shot_markdown_cell,
    _collect_shot_markdown_headers,
    _serialize_shot_rows_to_markdown,
    _coerce_shot_row_duration_or_default,
    _validate_shot_rows_or_raise,
    _validate_shot_rows_for_apply_with_tolerance,
    collect_shot_generation_completeness_errors,
    format_shot_generation_incomplete_detail,
    SHOT_GENERATION_INCOMPLETE_CODE,
    _resolve_shots_data_for_apply,
    _parse_shot_markdown_or_raise,
    _validate_shot_rows_roundtrip_or_raise,
)



# Markdown generation helpers (canonical: app.services.markdown_generation).
from app.services.markdown_generation import (  # noqa: E402,F401
    is_valid_markdown_output,
    _parse_episode_heading_from_markdown,
    generate_markdown_with_retry,
)

@router.post("/projects/", response_model=ProjectOut)
def create_project(
    project: ProjectCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if str(getattr(project, "kind", "") or "").strip().lower() == "promo":
        from app.models.all_models import PromoProject
        from app.services.promo_planner import (
            bind_promo_catalog,
            persist_promo_project_extra_info,
            serialize_promo_project,
        )

        title = str(project.title or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="title is required")
        extra_info = persist_promo_project_extra_info(
            dict(project.global_info or {}),
            title=title,
            description=project.description or "",
            require_aspect_ratio=True,
            require_type=True,
        )
        row = PromoProject(
            title=title,
            description=(project.description or "").strip() or None,
            extra_info=extra_info,
            owner_id=current_user.id,
        )
        db.add(row)
        db.flush()
        bind_promo_catalog(
            db,
            row,
            current_user,
            enterprise_id=getattr(project, "enterprise_id", None),
            brand_id=getattr(project, "brand_id", None),
            product_id=getattr(project, "product_id", None),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return JSONResponse(serialize_promo_project(db, row, current_user))

    if not project.global_info:
        project.global_info = {}

    description = (project.description or "").strip()
    if description:
        project.global_info["notes"] = description

    # If aspectRatio is provided, merge it into global_info
    if project.aspectRatio:
        project.global_info['aspectRatio'] = project.aspectRatio

    project.global_info = _ensure_project_generation_defaults(project.global_info)
        
    db_project = Project(title=project.title, global_info=project.global_info, owner_id=current_user.id) 
    try:
        db.add(db_project)
        db.flush()
        _sync_project_managed_shares(
            db,
            db_project,
            current_user,
            share_users=project.share_users,
            reviewer_users=project.reviewer_users,
        )
        try:
            _recompute_and_persist_project_cost_estimation(db, int(db_project.id))
        except Exception as cost_exc:
            logger.warning("create_project cost recompute skipped | project_id=%s err=%s", getattr(db_project, "id", None), cost_exc)
        db.commit()
    except SQLAlchemyTimeoutError:
        db.rollback()
        logger.warning(
            "create_project DB pool timeout | user_id=%s title=%s",
            current_user.id,
            (project.title or "")[:80],
        )
        raise HTTPException(
            status_code=503,
            detail="数据库连接繁忙，请稍后重试",
        )
    db.refresh(db_project)
    # New project has no images
    db_project.cover_image = None
    # Extract aspectRatio for response from global_info
    db_project.aspectRatio = db_project.global_info.get('aspectRatio') if db_project.global_info else None
    db_project.description = (db_project.global_info or {}).get("notes")
    db_project.is_owner = True
    return db_project



_CARD_POSTER_NAMES = ("封面海报", "海报", "封面", "cover", "poster")
_CARD_POSTER_TYPES = ("poster", "posters", "cover", "project_cover", "cover_image")


def _json_text_truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _json_text_present(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text not in {"", "none", "null", "0", "false"}


def _clean_json_text(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower() in {"", "none", "null"}:
        return ""
    return text


def _refresh_media_url_cached(url: Any, db: Session, cache: Dict[str, str]) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    cached = cache.get(raw)
    if cached is not None:
        return cached
    refreshed = _refresh_managed_media_url(raw, db)
    cache[raw] = refreshed or ""
    return cache[raw]


def _query_project_cards(session: Session, current_user: User, skip: int, limit: int) -> List[Any]:
    """Project homepage cards.

    The full ``global_info`` document holds scripts, reports, and canon data.
    Selecting it for every card makes the list wait on a large JSON transfer,
    which is much slower against the remote production database.
    """
    from types import SimpleNamespace

    shared_project_ids = [
        row[0]
        for row in session.query(ProjectShare.project_id).filter(ProjectShare.user_id == current_user.id).all()
    ]
    notes_col = Project.global_info["notes"].as_string()
    aspect_col = Project.global_info["aspectRatio"].as_string()
    stage_col = Project.global_info["workflow_stage"].as_string()
    hidden_col = Project.global_info["hidden_from_list"].as_string()
    promo_source_col = Project.global_info["source_promo_project_id"].as_string()

    rows = (
        session.query(
            Project.id,
            Project.title,
            Project.owner_id,
            Project.created_at,
            Project.updated_at,
            notes_col.label("notes"),
            aspect_col.label("aspect_ratio"),
            stage_col.label("workflow_stage"),
            hidden_col.label("hidden_from_list"),
            promo_source_col.label("source_promo_project_id"),
        )
        .filter(
            _active_project_clause(),
            or_(
                Project.owner_id == current_user.id,
                *([Project.id.in_(shared_project_ids)] if shared_project_ids else []),
            ),
        )
        .order_by(Project.updated_at.desc(), Project.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    if not rows:
        return []

    visible_rows = []
    for row in rows:
        if _json_text_truthy(row.hidden_from_list) or _json_text_present(row.source_promo_project_id):
            continue
        visible_rows.append(row)
    if not visible_rows:
        return []

    p_ids = [row.id for row in visible_rows]
    share_counts = {
        project_id: int(count or 0)
        for project_id, count in (
            session.query(ProjectShare.project_id, func.count(ProjectShare.id))
            .filter(ProjectShare.project_id.in_(p_ids))
            .group_by(ProjectShare.project_id)
            .all()
        )
    }

    shared_set = set(shared_project_ids)
    is_superuser = bool(getattr(current_user, "is_superuser", False))
    is_root = is_superuser and str(getattr(current_user, "username", "")).strip().lower() == "ylsystem"
    cards: List[Any] = []
    for row in visible_rows:
        notes = _clean_json_text(row.notes)
        aspect = _clean_json_text(row.aspect_ratio)
        stage = _clean_json_text(row.workflow_stage) or "script"
        is_owner = row.owner_id == current_user.id
        is_shared = (not is_owner) and row.id in shared_set
        cards.append(SimpleNamespace(
            id=row.id,
            title=row.title,
            description=notes or None,
            owner_id=row.owner_id,
            global_info={
                "notes": notes,
                "aspectRatio": aspect or None,
                "workflow_stage": stage,
            },
            aspectRatio=aspect or None,
            cover_image=None,
            cover_images=[],
            is_owner=is_owner,
            is_temp_view=bool(is_superuser and not is_owner and not is_shared and not is_root),
            can_edit=bool(is_owner or is_shared or is_root),
            share_count=share_counts.get(row.id, 0),
            list_summary=True,
            generation_seed=None,
            seed_initialized=False,
            missing_basic_fields=None,
            has_missing_basic_info=False,
            created_at=row.created_at,
            updated_at=row.updated_at,
        ))
    return cards


@router.get("/projects/", response_model=List[ProjectOut])
def read_projects(
    skip: int = 0, 
    limit: int = 100,
    summary: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    def _query_with(session: Session):
        if summary:
            return _query_project_cards(session, current_user, skip, limit)
        return _query_project_list_full(session)

    def _query_project_list_full(session: Session) -> List[Project]:
        shared_project_ids = [
            row[0]
            for row in session.query(ProjectShare.project_id).filter(ProjectShare.user_id == current_user.id).all()
        ]
        result = (
            session.query(Project.id, Project, func.count(ProjectShare.id).label("share_count"))
            .outerjoin(ProjectShare, Project.id == ProjectShare.project_id)
            .filter(
                _active_project_clause(),
                or_(
                    Project.owner_id == current_user.id,
                    Project.id.in_(shared_project_ids),
                )
            )
            .group_by(Project.id)
            .order_by(Project.updated_at.desc(), Project.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        if not result:
            return []
        
        # Batch preload cover images for the retrieved projects
        p_ids = [row[0] for row in result]
        
        poster_map, cover_images_map, shot_map, entity_map = {}, {}, {}, {}
        # Poster entities (project-level + per-episode covers)
        posters = session.query(
            Entity.project_id, Entity.episode_id, Entity.image_url, Entity.name
        ).filter(
            Entity.project_id.in_(p_ids),
            _active_entity_clause(),
            or_(
                Entity.name.in_(["封面海报", "海报", "封面", "cover", "poster"]),
                Entity.name.ilike("%海报%"),
                Entity.name.ilike("%封面%"),
                Entity.name.ilike("%cover%"),
                Entity.name.ilike("%poster%"),
                Entity.type.in_(["poster", "posters", "cover", "project_cover", "cover_image"]),
                Entity.type.ilike("%poster%"),
                Entity.type.ilike("%cover%")
            ),
            Entity.image_url != None,
            Entity.image_url != ""
        ).all()
        
        _temp_poster_map = {}
        _temp_episode_poster_map = {}
        for p_id, episode_id, image_url, name in posters:
            is_exact = (name == "封面海报")
            if p_id not in _temp_poster_map:
                _temp_poster_map[p_id] = {"url": image_url, "exact": is_exact}
            elif is_exact and not _temp_poster_map[p_id]["exact"]:
                _temp_poster_map[p_id] = {"url": image_url, "exact": is_exact}

            ep_key = (p_id, episode_id)
            if ep_key not in _temp_episode_poster_map:
                _temp_episode_poster_map[ep_key] = {"url": image_url, "exact": is_exact}
            elif is_exact and not _temp_episode_poster_map[ep_key]["exact"]:
                _temp_episode_poster_map[ep_key] = {"url": image_url, "exact": is_exact}
                
        for p_id, data in _temp_poster_map.items():
            poster_map[p_id] = _refresh_managed_media_url(data["url"], session)

        # Prefer exact「封面海报」per episode; order by episode_id (nulls last).
        for p_id, episode_id in sorted(
            _temp_episode_poster_map.keys(),
            key=lambda item: (item[1] is None, item[1] or 0, item[0]),
        ):
            refreshed = _refresh_managed_media_url(
                _temp_episode_poster_map[(p_id, episode_id)]["url"], session
            )
            if not refreshed:
                continue
            bucket = cover_images_map.setdefault(p_id, [])
            if refreshed not in bucket:
                bucket.append(refreshed)
            
        # First valid shot images (optimized using first() equivalent query or just aggregating)
        shot_subq = session.query(
            Shot.project_id,
            func.min(Shot.id).label("min_img_shot_id")
        ).filter(
            Shot.project_id.in_(p_ids),
            Shot.image_url != None,
            Shot.image_url != ""
        ).group_by(Shot.project_id).subquery()

        shots = session.query(Shot.project_id, Shot.image_url).join(
            shot_subq, (Shot.id == shot_subq.c.min_img_shot_id)
        ).all()
        for p_id, image_url in shots:
            if p_id not in shot_map:
                shot_map[p_id] = _refresh_managed_media_url(image_url, session)
                
        # First valid entities
        entity_subq = session.query(
            Entity.project_id,
            func.min(Entity.id).label("min_img_entity_id")
        ).filter(
            Entity.project_id.in_(p_ids),
            Entity.image_url != None,
            Entity.image_url != ""
        ).group_by(Entity.project_id).subquery()

        entities = session.query(Entity.project_id, Entity.image_url).join(
            entity_subq, (Entity.id == entity_subq.c.min_img_entity_id)
        ).all()
        for p_id, image_url in entities:
            if p_id not in entity_map:
                entity_map[p_id] = _refresh_managed_media_url(image_url, session)

        ret = []
        for row in result:
            p = row[1]
            hidden_info = p.global_info if isinstance(p.global_info, dict) else {}
            if hidden_info.get("hidden_from_list") or hidden_info.get("source_promo_project_id"):
                continue
            p.share_count = row[2]
            
            # Determine cover image
            cover_image = poster_map.get(p.id)
            if not cover_image and isinstance(p.global_info, dict):
                configured_cover = str(p.global_info.get("cover_image") or p.global_info.get("coverImage") or "").strip()
                if configured_cover:
                    cover_image = configured_cover
            if not cover_image:
                cover_image = shot_map.get(p.id)
            if not cover_image:
                cover_image = entity_map.get(p.id)

            cover_images = list(cover_images_map.get(p.id) or [])
            if cover_image and cover_image not in cover_images:
                # Keep configured/fallback cover in the rotation pool when no per-ep posters.
                cover_images.insert(0, cover_image)
                
            p.cover_image = cover_image
            p.cover_images = cover_images
            _attach_project_flags(p, current_user, session)
            if p.global_info:
                p.aspectRatio = p.global_info.get('aspectRatio')
            p.description = (p.global_info or {}).get("notes")
            ret.append(p)
            
        return ret

    try:
        return _query_with(db)
    except OperationalError as e:
        logger.warning("[read_projects] transient db OperationalError, retrying once: %s", e)
        try:
            db.rollback()
        except Exception:
            pass

        retry_db = SessionLocal()
        try:
            return _query_with(retry_db)
        finally:
            retry_db.close()


def _parse_card_cover_ids(raw: str, cap: int = 100) -> List[int]:
    parsed: List[int] = []
    seen = set()
    for part in str(raw or "").split(","):
        text = part.strip()
        if not text:
            continue
        try:
            value = int(text)
        except Exception:
            continue
        if value <= 0 or value in seen:
            continue
        seen.add(value)
        parsed.append(value)
        if len(parsed) >= cap:
            break
    return parsed


def _resolve_story_card_covers(session: Session, project_ids: List[int]) -> List[Dict[str, Any]]:
    if not project_ids:
        return []
    cover_col = Project.global_info["cover_image"].as_string()
    cover_alt_col = Project.global_info["coverImage"].as_string()
    rows = (
        session.query(
            Project.id,
            cover_col.label("cover_image"),
            cover_alt_col.label("cover_image_alt"),
        )
        .filter(Project.id.in_(project_ids), _active_project_clause())
        .all()
    )
    if not rows:
        return []

    row_ids = [row.id for row in rows]
    poster_name = func.lower(func.trim(Entity.name))
    poster_type = func.lower(func.trim(Entity.type))
    posters = session.query(
        Entity.project_id, Entity.episode_id, Entity.image_url, Entity.name
    ).filter(
        Entity.project_id.in_(row_ids),
        _active_entity_clause(),
        or_(
            poster_name.in_(list(_CARD_POSTER_NAMES)),
            poster_type.in_(list(_CARD_POSTER_TYPES)),
        ),
        Entity.image_url.isnot(None),
        Entity.image_url != "",
    ).all()

    refreshed_urls: Dict[str, str] = {}
    poster_map: Dict[int, str] = {}
    cover_images_map: Dict[int, List[str]] = {}
    episode_posters: Dict[Tuple[int, Any], Dict[str, Any]] = {}
    for p_id, episode_id, image_url, name in posters:
        is_exact = str(name or "").strip() == "封面海报"
        current = poster_map.get(p_id)
        if current is None or is_exact:
            poster_map[p_id] = image_url
        ep_key = (p_id, episode_id)
        previous = episode_posters.get(ep_key)
        if previous is None or (is_exact and not previous.get("exact")):
            episode_posters[ep_key] = {"url": image_url, "exact": is_exact}

    for p_id, raw_url in list(poster_map.items()):
        poster_map[p_id] = _refresh_media_url_cached(raw_url, session, refreshed_urls)

    for p_id, episode_id in sorted(
        episode_posters.keys(),
        key=lambda item: (item[1] is None, item[1] or 0, item[0]),
    ):
        refreshed = _refresh_media_url_cached(episode_posters[(p_id, episode_id)]["url"], session, refreshed_urls)
        if not refreshed:
            continue
        bucket = cover_images_map.setdefault(p_id, [])
        if refreshed not in bucket:
            bucket.append(refreshed)

    missing_cover_ids = []
    configured_map: Dict[int, str] = {}
    for row in rows:
        configured = _clean_json_text(row.cover_image) or _clean_json_text(row.cover_image_alt)
        if configured:
            configured_map[row.id] = _refresh_media_url_cached(configured, session, refreshed_urls)
        if not poster_map.get(row.id) and row.id not in configured_map:
            missing_cover_ids.append(row.id)

    shot_map: Dict[int, str] = {}
    entity_map: Dict[int, str] = {}
    if missing_cover_ids:
        shot_subq = session.query(
            Shot.project_id,
            func.min(Shot.id).label("min_img_shot_id"),
        ).filter(
            Shot.project_id.in_(missing_cover_ids),
            Shot.image_url.isnot(None),
            Shot.image_url != "",
        ).group_by(Shot.project_id).subquery()
        for p_id, image_url in session.query(Shot.project_id, Shot.image_url).join(
            shot_subq, Shot.id == shot_subq.c.min_img_shot_id
        ).all():
            shot_map[p_id] = _refresh_media_url_cached(image_url, session, refreshed_urls)

        still_missing = [p_id for p_id in missing_cover_ids if p_id not in shot_map]
        if still_missing:
            entity_subq = session.query(
                Entity.project_id,
                func.min(Entity.id).label("min_img_entity_id"),
            ).filter(
                Entity.project_id.in_(still_missing),
                Entity.image_url.isnot(None),
                Entity.image_url != "",
            ).group_by(Entity.project_id).subquery()
            for p_id, image_url in session.query(Entity.project_id, Entity.image_url).join(
                entity_subq, Entity.id == entity_subq.c.min_img_entity_id
            ).all():
                entity_map[p_id] = _refresh_media_url_cached(image_url, session, refreshed_urls)

    items: List[Dict[str, Any]] = []
    for row in rows:
        cover_image = poster_map.get(row.id) or configured_map.get(row.id) or shot_map.get(row.id) or entity_map.get(row.id) or None
        cover_images = list(cover_images_map.get(row.id) or [])
        if cover_image and cover_image not in cover_images:
            cover_images.insert(0, cover_image)
        if not cover_image and not cover_images:
            continue
        items.append({
            "id": row.id,
            "kind": "story",
            "cover_image": cover_image,
            "cover_images": cover_images,
        })
    return items


def _resolve_promo_card_covers(session: Session, promo_ids: List[int]) -> List[Dict[str, Any]]:
    if not promo_ids:
        return []
    refreshed_urls: Dict[str, str] = {}
    cover_map: Dict[int, str] = {}
    asset_rows = (
        session.query(PromoImageAsset.promo_project_id, PromoImageAsset.img_url)
        .filter(PromoImageAsset.promo_project_id.in_(promo_ids))
        .order_by(PromoImageAsset.id.asc())
        .all()
    )
    for promo_id, image_url in asset_rows:
        if promo_id in cover_map:
            continue
        refreshed = _refresh_media_url_cached(image_url, session, refreshed_urls)
        if refreshed:
            cover_map[promo_id] = refreshed

    missing = [promo_id for promo_id in promo_ids if promo_id not in cover_map]
    if missing:
        planner_rows = (
            session.query(PromoPlannerInput.promo_project_id, PromoPlannerInput.enterprise_info)
            .filter(PromoPlannerInput.promo_project_id.in_(missing))
            .all()
        )
        for promo_id, enterprise_info in planner_rows:
            assets = enterprise_info.get("image_assets") if isinstance(enterprise_info, dict) else None
            if not isinstance(assets, list):
                continue
            for asset in assets:
                raw_url = ""
                if isinstance(asset, dict):
                    raw_url = str(asset.get("img_url") or asset.get("file_url") or "").strip()
                if not raw_url:
                    continue
                refreshed = _refresh_media_url_cached(raw_url, session, refreshed_urls)
                if refreshed:
                    cover_map[promo_id] = refreshed
                    break

    return [
        {
            "id": promo_id,
            "kind": "promo",
            "cover_image": cover_map[promo_id],
            "cover_images": [cover_map[promo_id]],
        }
        for promo_id in promo_ids
        if cover_map.get(promo_id)
    ]


@router.get("/projects/card_covers")
def read_project_card_covers(
    ids: str = Query(""),
    promo_ids: str = Query(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cover art for cards already on screen. The project list does not wait for this."""
    story_ids = _parse_card_cover_ids(ids)
    promo_ids_parsed = _parse_card_cover_ids(promo_ids)
    items: List[Dict[str, Any]] = []
    if story_ids:
        shared_project_ids = [
            row[0]
            for row in db.query(ProjectShare.project_id).filter(
                ProjectShare.user_id == current_user.id,
                ProjectShare.project_id.in_(story_ids),
            ).all()
        ]
        membership = [Project.owner_id == current_user.id]
        if shared_project_ids:
            membership.append(Project.id.in_(shared_project_ids))
        allowed_ids = [
            row[0]
            for row in db.query(Project.id).filter(
                Project.id.in_(story_ids),
                _active_project_clause(),
                or_(*membership),
            ).all()
        ]
        items.extend(_resolve_story_card_covers(db, allowed_ids))
    if promo_ids_parsed:
        allowed_promo_ids = [
            row[0]
            for row in db.query(PromoProject.id).filter(
                PromoProject.id.in_(promo_ids_parsed),
                PromoProject.owner_id == current_user.id,
                PromoProject.is_deleted.is_(False),
            ).all()
        ]
        items.extend(_resolve_promo_card_covers(db, allowed_promo_ids))
    return {"items": items}


@router.get("/projects/{project_id}", response_model=ProjectOut)
def read_project(
    project_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = _require_project_access(db, project_id, current_user)

    raw_info = project.global_info
    if isinstance(raw_info, dict):
        global_info = dict(raw_info)
    elif isinstance(raw_info, str):
        try:
            parsed = json.loads(raw_info)
            global_info = parsed if isinstance(parsed, dict) else {}
        except Exception:
            global_info = {}
    else:
        global_info = {}

    existing_seed = _normalize_seed_value(
        global_info.get("generation_seed")
        or global_info.get("seed")
        or ((global_info.get("generation") or {}).get("seed") if isinstance(global_info.get("generation"), dict) else None)
    )
    resolved_seed = _ensure_project_generation_seed(db, project_id, current_user)
    seed_initialized = bool(resolved_seed and not existing_seed)

    basic_info = global_info.get("basic_info") if isinstance(global_info.get("basic_info"), dict) else {}
    e_global_info = global_info.get("e_global_info") if isinstance(global_info.get("e_global_info"), dict) else {}
    story_input = global_info.get("story_generator_global_input") if isinstance(global_info.get("story_generator_global_input"), dict) else {}

    def _pick_non_empty_text(*values: Any) -> str:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return ""

    type_value = _pick_non_empty_text(
        global_info.get("type"),
        basic_info.get("type"),
        e_global_info.get("type"),
        story_input.get("type"),
    )
    country_region_value = _pick_non_empty_text(
        global_info.get("country_region"),
        basic_info.get("country_region"),
        e_global_info.get("country_region"),
        story_input.get("country_region"),
    )
    language_value = _pick_non_empty_text(
        global_info.get("language"),
        basic_info.get("language"),
        e_global_info.get("language"),
        story_input.get("language"),
    )

    missing_basic_fields: List[str] = []
    if not type_value:
        missing_basic_fields.append("type")
    if not country_region_value:
        missing_basic_fields.append("country_region")
    if not language_value:
        missing_basic_fields.append("language")
    
    project.cover_image = get_project_cover_image(db, project.id)
    if project.global_info:
        project.global_info = _ensure_project_generation_defaults(
            dict(project.global_info) if isinstance(project.global_info, dict) else {}
        )
        project.aspectRatio = project.global_info.get('aspectRatio')
    project.description = (project.global_info or {}).get("notes")
    project.generation_seed = resolved_seed
    project.seed_initialized = seed_initialized
    project.missing_basic_fields = missing_basic_fields
    project.has_missing_basic_info = bool(missing_basic_fields)
    _attach_project_flags(project, current_user, db)
    return project


@router.get("/projects/{project_id}/superuser-peek", response_model=ProjectOut)
def superuser_peek_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Superuser-only: load a project by id for temporary read-only viewing on the project cards page."""
    if not bool(getattr(current_user, "is_superuser", False)):
        raise HTTPException(status_code=403, detail="Only superuser can peek projects")

    project = db.query(Project).filter(Project.id == project_id, _active_project_clause()).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Owners / existing shares should open via normal membership, not temp peek.
    is_owner = project.owner_id == current_user.id
    is_shared = (not is_owner) and _is_project_shared_with_user(db, project.id, current_user.id)
    if is_owner or is_shared:
        project.cover_image = get_project_cover_image(db, project.id)
        if project.global_info:
            project.aspectRatio = (project.global_info or {}).get("aspectRatio")
        project.description = (project.global_info or {}).get("notes")
        _attach_project_flags(project, current_user, db)
        return project

    project.cover_image = get_project_cover_image(db, project.id)
    cover_images = []
    if project.cover_image:
        cover_images.append(project.cover_image)
    project.cover_images = cover_images
    if project.global_info:
        project.aspectRatio = (project.global_info or {}).get("aspectRatio")
    project.description = (project.global_info or {}).get("notes")
    project.share_count = int(
        db.query(func.count(ProjectShare.id)).filter(ProjectShare.project_id == project.id).scalar() or 0
    )
    _attach_project_flags(project, current_user, db)
    # Force temp-view markers for peek entry even if flags change later.
    project.is_temp_view = True
    project.can_edit = False
    project.is_owner = False
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

    if project_in.description is not None:
        current_info = dict(project.global_info) if project.global_info else {}
        current_info['notes'] = project_in.description
        project.global_info = current_info

    if project_in.cover_image is not None:
        current_info = dict(project.global_info) if project.global_info else {}
        cover_image = str(project_in.cover_image or "").strip()
        if cover_image:
            current_info['cover_image'] = cover_image
        else:
            current_info.pop('cover_image', None)
            current_info.pop('coverImage', None)
        project.global_info = current_info

    _sync_project_managed_shares(
        db,
        project,
        current_user,
        share_users=project_in.share_users,
        reviewer_users=project_in.reviewer_users,
    )

    # Normalize and persist generation defaults for consistent downstream billing inputs.
    project.global_info = _ensure_project_generation_defaults(project.global_info)
    try:
        _recompute_and_persist_project_cost_estimation(db, int(project.id))
    except Exception as cost_exc:
        logger.warning("update_project cost recompute skipped | project_id=%s err=%s", project.id, cost_exc)
    
    db.commit()
    db.refresh(project)
    project.cover_image = get_project_cover_image(db, project.id)
    if project.global_info:
        project.aspectRatio = project.global_info.get('aspectRatio')
    project.description = (project.global_info or {}).get("notes")
    _attach_project_flags(project, current_user, db)
    return project


@router.get("/projects/{project_id}/cost_estimation", response_model=Dict[str, Any])
def get_project_cost_estimation(
    project_id: int,
    refresh: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user)
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    existing = (project.global_info or {}).get("cost_estimation") if isinstance(project.global_info, dict) else None
    if refresh or not isinstance(existing, dict):
        snapshot = _recompute_and_persist_project_cost_estimation(db, project_id)
        db.commit()
        return snapshot
    return existing


@router.post("/projects/{project_id}/cost_estimation/recompute", response_model=Dict[str, Any])
def recompute_project_cost_estimation(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user)
    snapshot = _recompute_and_persist_project_cost_estimation(db, project_id)
    db.commit()
    return snapshot


@router.post("/projects/{project_id}/episodes/{episode_id}/cost_estimation/recompute", response_model=Dict[str, Any])
def recompute_episode_cost_estimation(
    project_id: int,
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recompute cost estimation scoped to a single episode, then persist full project snapshot."""
    _require_project_access(db, project_id, current_user)
    episode = db.query(Episode).filter(
        Episode.id == episode_id,
        Episode.project_id == project_id,
        _active_episode_clause(),
    ).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    snapshot = _recompute_and_persist_project_cost_estimation(db, project_id)
    db.commit()
    # Extract episode-specific slice from snapshot for a focused response
    ep_costs = [ep for ep in (snapshot.get("episode_costs") or []) if ep.get("episode_id") == episode_id]
    sc_costs = [sc for sc in (snapshot.get("scene_costs") or []) if sc.get("episode_id") == episode_id]
    return {
        "project_id": project_id,
        "episode_id": episode_id,
        "episode_cost": ep_costs[0] if ep_costs else None,
        "scene_costs": sc_costs,
        "summary": snapshot.get("summary"),
        "computed_at": snapshot.get("computed_at"),
    }


@router.post("/projects/{project_id}/scenes/{scene_id}/cost_estimation/recompute", response_model=Dict[str, Any])
def recompute_scene_cost_estimation(
    project_id: int,
    scene_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recompute cost estimation for a specific scene, persist full project snapshot, return scene slice."""
    _require_project_access(db, project_id, current_user)
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    # Verify scene belongs to this project via episode
    episode = db.query(Episode).filter(
        Episode.id == scene.episode_id,
        Episode.project_id == project_id,
        _active_episode_clause(),
    ).first()
    if not episode:
        raise HTTPException(status_code=403, detail="Scene does not belong to this project")
    snapshot = _recompute_and_persist_project_cost_estimation(db, project_id)
    db.commit()
    # Return the scene-level slice
    scene_cost = next((sc for sc in (snapshot.get("scene_costs") or []) if sc.get("scene_id") == scene_id), None)
    return {
        "project_id": project_id,
        "scene_id": scene_id,
        "episode_id": int(scene.episode_id),
        "scene_cost": scene_cost,
        "summary": snapshot.get("summary"),
        "computed_at": snapshot.get("computed_at"),
    }


@router.get("/deletion-batches")
def list_deletion_batches(
    project_id: Optional[int] = None,
    include_restored: bool = False,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if DeletionBatch is None:
        return []
    if project_id is not None:
        _require_project_owner_any_state(db, int(project_id), current_user)
    query = db.query(DeletionBatch).filter(DeletionBatch.user_id == current_user.id)
    if project_id is not None:
        query = query.filter(DeletionBatch.project_id == int(project_id))
    if not include_restored:
        query = query.filter(DeletionBatch.restored_at.is_(None))
    safe_skip = max(int(skip or 0), 0)
    safe_limit = max(1, min(int(limit or 50), 200))
    batches = (
        query.order_by(DeletionBatch.created_at.desc(), DeletionBatch.id.desc())
        .offset(safe_skip)
        .limit(safe_limit)
        .all()
    )
    return [_serialize_deletion_batch(batch, db) for batch in batches]


@router.get("/deletion-batches/{batch_id}")
def get_deletion_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if DeletionBatch is None:
        raise HTTPException(status_code=503, detail="Deletion batch is unavailable")
    batch = db.query(DeletionBatch).filter(DeletionBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Deletion batch not found")
    if int(batch.user_id) != int(current_user.id):
        _require_project_owner_any_state(db, int(batch.project_id), current_user)
    return _serialize_deletion_batch(batch, db)


@router.post("/deletion-batches/{batch_id}/restore")
def restore_deletion_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = _restore_deletion_batch(db, batch_id, current_user)
    db.commit()
    return result


@router.delete("/projects/{project_id}", status_code=200)
def delete_project(
    project_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = _require_project_access(db, project_id, current_user, owner_only=True)
    if _is_soft_deleted(project):
        return {"status": "deleted", "batch_id": None}

    now = now_bj_iso()
    batch_id = _start_deletion_batch(
        db,
        user_id=current_user.id,
        project_id=project_id,
        action_type="project",
        label=str(project.title or f"Project {project_id}"),
    )
    episode_ids = [
        row[0]
        for row in db.query(Episode.id).filter(
            Episode.project_id == project_id,
            _active_episode_clause(),
        ).all()
    ]
    _track_deletion_batch_items(db, batch_id, "project", [project_id])
    _track_deletion_batch_items(db, batch_id, "episode", episode_ids)

    project.is_deleted = True
    project.deleted_at = now
    project.updated_at = now
    if episode_ids:
        db.query(Episode).filter(Episode.id.in_(episode_ids)).update(
            {Episode.is_deleted: True, Episode.deleted_at: now},
            synchronize_session=False,
        )
    _soft_delete_project_children(db, project_id, now=now, batch_id=batch_id)
    _finalize_deletion_batch(db, batch_id)
    db.add(project)
    db.commit()
    return {"status": "deleted", "batch_id": batch_id}

