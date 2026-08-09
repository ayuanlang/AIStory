# -*- coding: utf-8 -*-
"""Platform knowledge-base routes (P0 CRUD + P1 RAG search)."""
from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.time_utils import now_bj_iso
from app.db.session import get_db
from app.models.all_models import KbChunk, KbEntry, KbEntryMedia, KbEvalCase, KbWork, Project, User
from app.schemas.knowledge_base import (
    KbEntryCreate,
    KbEntryQualityRequest,
    KbEntryReviewRequest,
    KbEntryUpdate,
    KbEvalCaseCreate,
    KbEvalCaseUpdate,
    KbEvalRunRequest,
    KbImportJsonRequest,
    KbIngestLlmRequest,
    KbIngestWebRequest,
    KbProjectCollectionUpdate,
    KbSearchRequest,
    KbWorkCreate,
    KbWorkUpdate,
)
from app.services.kb_eval_service import run_kb_eval
from app.services.kb_import_service import (
    build_csv_template,
    build_json_template,
    import_kb_entries,
    parse_import_payload,
)
from app.services.kb_ingest_service import ingest_from_text, ingest_from_web
from app.services.kb_rag_service import rebuild_entry_index, rebuild_entry_index_background, search_kb
from app.services.kb_vision_service import (
    KB_QUERY_PROMPT,
    caption_kb_media_background,
    describe_image_for_kb,
    file_bytes_to_data_url,
)
from app.services.oss_storage_service import oss_storage_service
from app.services.project_access import _require_project_access
from app.services.task_manager import submit_async_endpoint as _submit_async

logger = logging.getLogger("api_logger")
router = APIRouter(prefix="/kb", tags=["knowledge_base"])

KB_CATEGORIES = {"portrait", "costume", "scenery", "plot"}
PLOT_SUBTYPES = {"trope", "dialogue", "action"}
LICENSE_TIERS = {"public_domain", "reference_ok", "fair_use_ref", "restricted", "blocked"}
SOURCE_TYPES = {"upload", "manual", "web", "llm"}
REVIEW_STATUSES = {"pending", "approved", "rejected"}
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".webm"}


def _is_superuser(user: User) -> bool:
    return bool(getattr(user, "is_superuser", False))


def _normalize_tags(value: Optional[List[str]]) -> List[str]:
    if not value:
        return []
    out: List[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def _serialize_media(row: KbEntryMedia) -> Dict[str, Any]:
    return {
        "id": row.id,
        "entry_id": row.entry_id,
        "url": row.url,
        "media_type": row.media_type,
        "filename": row.filename,
        "caption": row.caption,
        "sort_order": int(row.sort_order or 0),
        "meta_info": row.meta_info or {},
        "created_at": row.created_at,
    }


def _serialize_work(row: KbWork) -> Dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "title_en": row.title_en,
        "year": row.year,
        "genre": row.genre,
        "region": row.region,
        "description": row.description,
        "created_by_user_id": row.created_by_user_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _serialize_entry(row: KbEntry, *, include_media: bool = True) -> Dict[str, Any]:
    media_rows = []
    if include_media:
        media_rows = [
            m for m in (row.media or [])
            if not bool(getattr(m, "is_deleted", False))
        ]
        media_rows.sort(key=lambda m: (int(m.sort_order or 0), int(m.id or 0)))
    work = row.work if row.work_id else None
    return {
        "id": row.id,
        "work_id": row.work_id,
        "work": _serialize_work(work) if work and not work.is_deleted else None,
        "category": row.category,
        "plot_subtype": row.plot_subtype,
        "title": row.title,
        "summary": row.summary,
        "body_text": row.body_text,
        "tags": row.tags or [],
        "style_keywords": row.style_keywords or [],
        "license_tier": row.license_tier or "reference_ok",
        "copyright_note": row.copyright_note,
        "source_type": row.source_type or "manual",
        "source_url": row.source_url,
        "source_meta": getattr(row, "source_meta", None) or {},
        "review_status": row.review_status or "pending",
        "review_note": row.review_note,
        "reviewed_by_user_id": row.reviewed_by_user_id,
        "reviewed_at": row.reviewed_at,
        "cover_url": row.cover_url,
        "quality_score": float(getattr(row, "quality_score", None) or 3.0),
        "quality_notes": getattr(row, "quality_notes", None),
        "is_eval_gold": bool(getattr(row, "is_eval_gold", False)),
        "inject_count": int(getattr(row, "inject_count", 0) or 0),
        "index_status": getattr(row, "index_status", None) or "none",
        "indexed_at": getattr(row, "indexed_at", None),
        "index_error": getattr(row, "index_error", None),
        "created_by_user_id": row.created_by_user_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "media": [_serialize_media(m) for m in media_rows] if include_media else [],
    }


def _clamp_quality(value: Any, default: float = 3.0) -> float:
    try:
        score = float(value)
    except Exception:
        score = default
    return max(0.0, min(score, 5.0))


def _serialize_eval_case(row: KbEvalCase) -> Dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "query": row.query,
        "category": row.category,
        "expected_entry_ids": row.expected_entry_ids or [],
        "expected_tags": row.expected_tags or [],
        "notes": row.notes,
        "is_active": bool(row.is_active),
        "created_by_user_id": row.created_by_user_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _can_view_entry(user: User, row: KbEntry) -> bool:
    if _is_superuser(user):
        return True
    status = str(row.review_status or "pending")
    if status == "approved":
        return True
    return int(row.created_by_user_id or 0) == int(user.id)


def _can_edit_entry(user: User, row: KbEntry) -> bool:
    if _is_superuser(user):
        return True
    if int(row.created_by_user_id or 0) != int(user.id):
        return False
    return str(row.review_status or "pending") in {"pending", "rejected"}


def _validate_category(category: str) -> str:
    value = str(category or "").strip().lower()
    if value not in KB_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    return value


def _validate_plot_subtype(category: str, plot_subtype: Optional[str]) -> Optional[str]:
    if category != "plot":
        return None
    value = str(plot_subtype or "").strip().lower() or None
    if value and value not in PLOT_SUBTYPES:
        raise HTTPException(status_code=400, detail=f"Invalid plot_subtype: {plot_subtype}")
    return value


def _require_entry(db: Session, entry_id: int) -> KbEntry:
    row = (
        db.query(KbEntry)
        .options(joinedload(KbEntry.media), joinedload(KbEntry.work))
        .filter(KbEntry.id == entry_id, KbEntry.is_deleted.is_(False))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    return row


@router.get("/works")
def list_works(
    q: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(KbWork).filter(KbWork.is_deleted.is_(False))
    text = str(q or "").strip()
    if text:
        like = f"%{text}%"
        query = query.filter(or_(KbWork.title.ilike(like), KbWork.title_en.ilike(like)))
    rows = query.order_by(KbWork.updated_at.desc(), KbWork.id.desc()).offset(offset).limit(limit).all()
    return {"items": [_serialize_work(r) for r in rows], "total": len(rows)}


@router.post("/works")
def create_work(
    payload: KbWorkCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    title = str(payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    now = now_bj_iso()
    row = KbWork(
        title=title,
        title_en=(str(payload.title_en).strip() if payload.title_en else None),
        year=(str(payload.year).strip() if payload.year else None),
        genre=(str(payload.genre).strip() if payload.genre else None),
        region=(str(payload.region).strip() if payload.region else None),
        description=(str(payload.description).strip() if payload.description else None),
        created_by_user_id=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_work(row)


@router.put("/works/{work_id}")
def update_work(
    work_id: int,
    payload: KbWorkUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(KbWork).filter(KbWork.id == work_id, KbWork.is_deleted.is_(False)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Work not found")
    if not _is_superuser(current_user) and int(row.created_by_user_id or 0) != int(current_user.id):
        raise HTTPException(status_code=403, detail="Not allowed to edit this work")
    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(row, key, value)
    row.updated_at = now_bj_iso()
    db.commit()
    db.refresh(row)
    return _serialize_work(row)


@router.get("/entries")
def list_entries(
    category: Optional[str] = Query(None),
    plot_subtype: Optional[str] = Query(None),
    review_status: Optional[str] = Query(None),
    work_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = [KbEntry.is_deleted.is_(False)]
    if category:
        filters.append(KbEntry.category == _validate_category(category))
    if plot_subtype:
        subtype = str(plot_subtype).strip().lower()
        if subtype not in PLOT_SUBTYPES:
            raise HTTPException(status_code=400, detail=f"Invalid plot_subtype: {plot_subtype}")
        filters.append(KbEntry.plot_subtype == subtype)
    if work_id:
        filters.append(KbEntry.work_id == int(work_id))
    if review_status:
        status = str(review_status).strip().lower()
        if status not in REVIEW_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid review_status: {review_status}")
        filters.append(KbEntry.review_status == status)
    text = str(q or "").strip()
    if text:
        like = f"%{text}%"
        filters.append(
            or_(
                KbEntry.title.ilike(like),
                KbEntry.summary.ilike(like),
                KbEntry.body_text.ilike(like),
            )
        )

    if not _is_superuser(current_user):
        filters.append(
            or_(
                KbEntry.review_status == "approved",
                KbEntry.created_by_user_id == current_user.id,
            )
        )

    total = db.query(KbEntry).filter(*filters).count()
    rows = (
        db.query(KbEntry)
        .options(joinedload(KbEntry.media), joinedload(KbEntry.work))
        .filter(*filters)
        .order_by(KbEntry.updated_at.desc(), KbEntry.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "items": [_serialize_entry(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "is_superuser": _is_superuser(current_user),
    }


@router.get("/entries/{entry_id}")
def get_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _require_entry(db, entry_id)
    if not _can_view_entry(current_user, row):
        raise HTTPException(status_code=403, detail="Not allowed to view this entry")
    return _serialize_entry(row)


@router.post("/entries")
def create_entry(
    payload: KbEntryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    category = _validate_category(payload.category)
    title = str(payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    plot_subtype = _validate_plot_subtype(category, payload.plot_subtype)
    license_tier = str(payload.license_tier or "reference_ok").strip().lower()
    if license_tier not in LICENSE_TIERS:
        raise HTTPException(status_code=400, detail=f"Invalid license_tier: {payload.license_tier}")
    source_type = str(payload.source_type or "manual").strip().lower()
    if source_type not in SOURCE_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid source_type: {payload.source_type}")

    work_id = payload.work_id
    if not work_id and payload.work_title:
        work_title = str(payload.work_title).strip()
        if work_title:
            now = now_bj_iso()
            work = KbWork(
                title=work_title,
                year=(str(payload.work_year).strip() if payload.work_year else None),
                created_by_user_id=current_user.id,
                created_at=now,
                updated_at=now,
            )
            db.add(work)
            db.flush()
            work_id = work.id
    elif work_id:
        work = db.query(KbWork).filter(KbWork.id == work_id, KbWork.is_deleted.is_(False)).first()
        if not work:
            raise HTTPException(status_code=404, detail="Work not found")

    now = now_bj_iso()
    row = KbEntry(
        work_id=work_id,
        category=category,
        plot_subtype=plot_subtype,
        title=title,
        summary=(str(payload.summary).strip() if payload.summary else None),
        body_text=(str(payload.body_text).strip() if payload.body_text else None),
        tags=_normalize_tags(payload.tags),
        style_keywords=_normalize_tags(payload.style_keywords),
        license_tier=license_tier,
        copyright_note=(str(payload.copyright_note).strip() if payload.copyright_note else None),
        source_type=source_type,
        source_url=(str(payload.source_url).strip() if payload.source_url else None),
        quality_score=_clamp_quality(payload.quality_score, 3.0),
        quality_notes=(str(payload.quality_notes).strip() if payload.quality_notes else None),
        is_eval_gold=bool(payload.is_eval_gold) if payload.is_eval_gold is not None else False,
        review_status="pending",
        created_by_user_id=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    row = _require_entry(db, row.id)
    return _serialize_entry(row)


@router.put("/entries/{entry_id}")
def update_entry(
    entry_id: int,
    payload: KbEntryUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _require_entry(db, entry_id)
    if not _can_edit_entry(current_user, row):
        raise HTTPException(status_code=403, detail="Not allowed to edit this entry")

    data = payload.dict(exclude_unset=True)
    if "category" in data and data["category"] is not None:
        data["category"] = _validate_category(data["category"])
    category = data.get("category") or row.category
    if "plot_subtype" in data or "category" in data:
        data["plot_subtype"] = _validate_plot_subtype(category, data.get("plot_subtype", row.plot_subtype))
    if "license_tier" in data and data["license_tier"] is not None:
        license_tier = str(data["license_tier"]).strip().lower()
        if license_tier not in LICENSE_TIERS:
            raise HTTPException(status_code=400, detail=f"Invalid license_tier: {data['license_tier']}")
        data["license_tier"] = license_tier
    if "source_type" in data and data["source_type"] is not None:
        source_type = str(data["source_type"]).strip().lower()
        if source_type not in SOURCE_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid source_type: {data['source_type']}")
        data["source_type"] = source_type
    if "tags" in data:
        data["tags"] = _normalize_tags(data["tags"])
    if "style_keywords" in data:
        data["style_keywords"] = _normalize_tags(data["style_keywords"])
    if "quality_score" in data and data["quality_score"] is not None:
        data["quality_score"] = _clamp_quality(data["quality_score"], float(getattr(row, "quality_score", 3.0) or 3.0))
    if "is_eval_gold" in data and data["is_eval_gold"] is not None:
        data["is_eval_gold"] = bool(data["is_eval_gold"])
    if "work_id" in data and data["work_id"]:
        work = db.query(KbWork).filter(KbWork.id == int(data["work_id"]), KbWork.is_deleted.is_(False)).first()
        if not work:
            raise HTTPException(status_code=404, detail="Work not found")

    for key, value in data.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(row, key, value)

    # Non-superuser edits reset to pending
    if not _is_superuser(current_user) and str(row.review_status) == "approved":
        row.review_status = "pending"
        row.reviewed_at = None
        row.reviewed_by_user_id = None
        row.review_note = None
        row.index_status = "none"
        row.indexed_at = None
        db.query(KbChunk).filter(KbChunk.entry_id == entry_id).delete(synchronize_session=False)

    row.updated_at = now_bj_iso()
    should_reindex = str(row.review_status or "") == "approved"
    if should_reindex:
        row.index_status = "pending"
        row.index_error = None
    db.commit()
    if should_reindex:
        background_tasks.add_task(rebuild_entry_index_background, entry_id)
    row = _require_entry(db, entry_id)
    return _serialize_entry(row)


@router.delete("/entries/{entry_id}")
def delete_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _require_entry(db, entry_id)
    if not _can_edit_entry(current_user, row) and not _is_superuser(current_user):
        raise HTTPException(status_code=403, detail="Not allowed to delete this entry")
    now = now_bj_iso()
    row.is_deleted = True
    row.updated_at = now
    row.index_status = "none"
    for media in row.media or []:
        media.is_deleted = True
    db.query(KbChunk).filter(KbChunk.entry_id == entry_id).delete(synchronize_session=False)
    db.commit()
    return {"ok": True, "id": entry_id}


@router.post("/entries/{entry_id}/review")
def review_entry(
    entry_id: int,
    payload: KbEntryReviewRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_superuser(current_user):
        raise HTTPException(status_code=403, detail="Only superuser can review knowledge entries")
    row = _require_entry(db, entry_id)
    action = str(payload.action or "").strip().lower()
    if action not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="action must be approve or reject")
    row.review_status = "approved" if action == "approve" else "rejected"
    row.review_note = (str(payload.note).strip() if payload.note else None)
    row.reviewed_by_user_id = current_user.id
    row.reviewed_at = now_bj_iso()
    row.updated_at = now_bj_iso()
    if action == "approve":
        row.index_status = "pending"
        row.index_error = None
    else:
        row.index_status = "none"
        row.indexed_at = None
        row.index_error = None
        db.query(KbChunk).filter(KbChunk.entry_id == entry_id).delete(synchronize_session=False)
    db.commit()
    if action == "approve":
        background_tasks.add_task(rebuild_entry_index_background, entry_id)
    row = _require_entry(db, entry_id)
    return _serialize_entry(row)


@router.post("/entries/{entry_id}/media/upload")
def upload_entry_media(
    entry_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    auto_caption: str = Form("true"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _require_entry(db, entry_id)
    if not _can_edit_entry(current_user, row) and not _is_superuser(current_user):
        raise HTTPException(status_code=403, detail="Not allowed to upload media for this entry")

    max_upload_bytes = max(int(getattr(settings, "MAX_ASSET_UPLOAD_MB", None) or 100), 1) * 1024 * 1024
    ext = (os.path.splitext(file.filename or "")[1] or "").lower()
    if ext not in (ALLOWED_IMAGE_EXT | ALLOWED_VIDEO_EXT):
        raise HTTPException(status_code=400, detail="Unsupported file extension")

    content_type = (file.content_type or "").lower()
    media_type = "video" if ext in ALLOWED_VIDEO_EXT else "image"
    if media_type == "video" and content_type and not content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="File content type does not match video extension")
    if media_type == "image" and content_type and not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File content type does not match image extension")

    upload_dir = os.path.join(settings.UPLOAD_DIR, "kb", str(current_user.id))
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(upload_dir, filename)

    bytes_written = 0
    try:
        with open(file_path, "wb") as buffer:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_upload_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large (max {getattr(settings, 'MAX_ASSET_UPLOAD_MB', 100)}MB)",
                    )
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

    meta_info: Dict[str, Any] = {
        "source": "kb_upload",
        "size_bytes": bytes_written,
        "original_filename": file.filename,
    }
    base_url = settings.RENDER_EXTERNAL_URL.rstrip("/") if settings.RENDER_EXTERNAL_URL else ""
    url = f"{base_url}/uploads/kb/{current_user.id}/{filename}"

    if oss_storage_service.is_enabled(db):
        try:
            oss_res = oss_storage_service.upload_file(
                file_path,
                user_id=current_user.id,
                filename=file.filename,
                content_type=file.content_type,
                category="kb",
            )
            if oss_res and oss_res.get("url"):
                url = oss_res.get("url")
                meta_info["oss"] = {
                    "provider": oss_res.get("provider"),
                    "bucket": oss_res.get("bucket"),
                    "key": oss_res.get("key"),
                }
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception:
                    pass
        except Exception as exc:
            logger.warning("OSS upload failed for kb media: %s", exc)

    existing_count = (
        db.query(KbEntryMedia)
        .filter(KbEntryMedia.entry_id == entry_id, KbEntryMedia.is_deleted.is_(False))
        .count()
    )
    media = KbEntryMedia(
        entry_id=entry_id,
        url=url,
        media_type=media_type,
        filename=file.filename or filename,
        caption=(str(caption).strip() if caption else None),
        sort_order=existing_count,
        meta_info=meta_info,
        created_by_user_id=current_user.id,
        created_at=now_bj_iso(),
    )
    db.add(media)
    if not row.cover_url and media_type == "image":
        row.cover_url = url
    row.updated_at = now_bj_iso()
    if not _is_superuser(current_user) and str(row.review_status) == "approved":
        row.review_status = "pending"
        row.reviewed_at = None
        row.reviewed_by_user_id = None
    db.commit()
    db.refresh(media)
    should_auto_caption = (
        media_type == "image"
        and not str(media.caption or "").strip()
        and str(auto_caption or "true").strip().lower() in {"1", "true", "yes", "y", "on"}
    )
    if should_auto_caption:
        background_tasks.add_task(caption_kb_media_background, int(media.id), int(current_user.id), force=False)
    elif media_type == "image" and str(media.caption or "").strip() and str(row.review_status) == "approved":
        background_tasks.add_task(rebuild_entry_index_background, entry_id)
    return {
        "media": _serialize_media(media),
        "entry": _serialize_entry(_require_entry(db, entry_id)),
        "auto_caption_queued": should_auto_caption,
    }


@router.delete("/entries/{entry_id}/media/{media_id}")
def delete_entry_media(
    entry_id: int,
    media_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _require_entry(db, entry_id)
    if not _can_edit_entry(current_user, row) and not _is_superuser(current_user):
        raise HTTPException(status_code=403, detail="Not allowed to delete media for this entry")
    media = (
        db.query(KbEntryMedia)
        .filter(
            KbEntryMedia.id == media_id,
            KbEntryMedia.entry_id == entry_id,
            KbEntryMedia.is_deleted.is_(False),
        )
        .first()
    )
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    media.is_deleted = True
    if row.cover_url and row.cover_url == media.url:
        next_cover = (
            db.query(KbEntryMedia)
            .filter(
                KbEntryMedia.entry_id == entry_id,
                KbEntryMedia.is_deleted.is_(False),
                KbEntryMedia.id != media_id,
                KbEntryMedia.media_type == "image",
            )
            .order_by(KbEntryMedia.sort_order.asc(), KbEntryMedia.id.asc())
            .first()
        )
        row.cover_url = next_cover.url if next_cover else None
    row.updated_at = now_bj_iso()
    db.commit()
    return {"ok": True, "entry": _serialize_entry(_require_entry(db, entry_id))}


def _serialize_ingest_result(db: Session, result: Dict[str, Any]) -> Dict[str, Any]:
    entry_ids = [int(i) for i in (result.get("entry_ids") or []) if i]
    entries = []
    if entry_ids:
        rows = (
            db.query(KbEntry)
            .options(joinedload(KbEntry.media), joinedload(KbEntry.work))
            .filter(KbEntry.id.in_(entry_ids), KbEntry.is_deleted.is_(False))
            .all()
        )
        by_id = {int(r.id): r for r in rows}
        for eid in entry_ids:
            row = by_id.get(eid)
            if row:
                entries.append(_serialize_entry(row))
    payload = dict(result or {})
    payload["entries"] = entries
    return payload


@router.post("/ingest/web")
async def ingest_web_entries(
    payload: KbIngestWebRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(
            ingest_web_entries,
            user_id=current_user.id,
            kind="kb_ingest_web",
            payload=payload,
            async_mode="0",
        )
        return JSONResponse({"task_id": tid, "async": True})
    result = await ingest_from_web(
        db,
        current_user=current_user,
        category=payload.category,
        topic=payload.topic,
        work_title=payload.work_title,
        work_year=payload.work_year,
        language=payload.language or "zh",
        max_entries=max(1, min(int(payload.max_entries or 6), 12)),
        system_api_id=payload.system_api_id,
    )
    return _serialize_ingest_result(db, result)


@router.post("/ingest/llm")
async def ingest_llm_entries(
    payload: KbIngestLlmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(
            ingest_llm_entries,
            user_id=current_user.id,
            kind="kb_ingest_llm",
            payload=payload,
            async_mode="0",
        )
        return JSONResponse({"task_id": tid, "async": True})
    result = await ingest_from_text(
        db,
        current_user=current_user,
        category=payload.category,
        source_text=payload.source_text,
        work_title=payload.work_title,
        work_year=payload.work_year,
        language=payload.language or "zh",
        max_entries=max(1, min(int(payload.max_entries or 6), 12)),
        system_api_id=payload.system_api_id,
    )
    return _serialize_ingest_result(db, result)


def _serialize_search_result(
    result: Dict[str, Any],
    *,
    current_user: User,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    items = []
    for hit in result.get("hits") or []:
        entry = hit.get("entry")
        if not entry:
            continue
        payload_item = _serialize_entry(entry)
        payload_item["score"] = hit.get("score")
        payload_item["semantic_score"] = hit.get("semantic_score")
        payload_item["keyword_score"] = hit.get("keyword_score")
        payload_item["quality_score"] = hit.get("quality_score")
        payload_item["snippet"] = hit.get("snippet")
        payload_item["matched_chunk_id"] = hit.get("matched_chunk_id")
        payload_item["matched_chunk_kind"] = hit.get("matched_chunk_kind")
        payload_item["matched_media_id"] = hit.get("matched_media_id")
        items.append(payload_item)
    payload = {
        "items": items,
        "total": len(items),
        "mode": result.get("mode"),
        "embedding_model": result.get("embedding_model"),
        "is_superuser": _is_superuser(current_user),
    }
    if extra:
        payload.update(extra)
    return payload


@router.post("/search")
def search_entries(
    payload: KbSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = str(payload.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    category = _validate_category(payload.category) if payload.category else None
    plot_subtype = None
    if payload.plot_subtype:
        plot_subtype = str(payload.plot_subtype).strip().lower()
        if plot_subtype not in PLOT_SUBTYPES:
            raise HTTPException(status_code=400, detail=f"Invalid plot_subtype: {payload.plot_subtype}")
    result = search_kb(
        db,
        query=query,
        category=category,
        plot_subtype=plot_subtype,
        top_k=max(1, min(int(payload.top_k or 12), 50)),
        mode=str(payload.mode or "hybrid"),
        include_pending_for_user_id=current_user.id,
        is_superuser=_is_superuser(current_user),
        entry_ids=payload.entry_ids,
        include_restricted=bool(payload.include_restricted) or _is_superuser(current_user),
    )
    return _serialize_search_result(result, current_user=current_user)


@router.post("/search/image")
async def search_entries_by_image(
    file: UploadFile = File(...),
    query: str = Form(""),
    category: Optional[str] = Form(None),
    plot_subtype: Optional[str] = Form(None),
    top_k: int = Form(12),
    mode: str = Form("hybrid"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Multimodal retrieval: vision describes the query image, then hybrid text search."""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")
    ext = (os.path.splitext(file.filename or "")[1] or "").lower()
    if ext and ext not in ALLOWED_IMAGE_EXT:
        raise HTTPException(status_code=400, detail="Unsupported image extension")
    data_url = file_bytes_to_data_url(raw, filename=file.filename or "query.jpg")
    vision_text, vision_meta = await describe_image_for_kb(
        db,
        current_user=current_user,
        image_url=data_url,
        prompt=KB_QUERY_PROMPT,
        billing_item="kb_search_image",
    )
    extra_q = str(query or "").strip()
    final_query = f"{extra_q}\n{vision_text}".strip() if extra_q else vision_text

    cat = _validate_category(category) if category else None
    subtype = None
    if plot_subtype:
        subtype = str(plot_subtype).strip().lower()
        if subtype not in PLOT_SUBTYPES:
            raise HTTPException(status_code=400, detail=f"Invalid plot_subtype: {plot_subtype}")

    result = search_kb(
        db,
        query=final_query,
        category=cat,
        plot_subtype=subtype,
        top_k=max(1, min(int(top_k or 12), 50)),
        mode=str(mode or "hybrid"),
        include_pending_for_user_id=current_user.id,
        is_superuser=_is_superuser(current_user),
        include_restricted=_is_superuser(current_user),
    )
    return _serialize_search_result(
        result,
        current_user=current_user,
        extra={
            "query_text": final_query,
            "vision_query": vision_text,
            "vision_model": vision_meta.get("model"),
            "search_type": "image",
        },
    )


@router.post("/entries/{entry_id}/media/{media_id}/caption")
async def caption_entry_media(
    entry_id: int,
    media_id: int,
    force: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.kb_vision_service import caption_kb_media

    row = _require_entry(db, entry_id)
    if not _can_edit_entry(current_user, row) and not _is_superuser(current_user):
        raise HTTPException(status_code=403, detail="Not allowed to caption media for this entry")
    media = (
        db.query(KbEntryMedia)
        .filter(
            KbEntryMedia.id == media_id,
            KbEntryMedia.entry_id == entry_id,
            KbEntryMedia.is_deleted.is_(False),
        )
        .first()
    )
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    if str(media.media_type or "") != "image":
        raise HTTPException(status_code=400, detail="Only image media can be captioned")
    text = await caption_kb_media(db, current_user=current_user, media=media, force=bool(force))
    if str(row.review_status or "") == "approved":
        rebuild_entry_index(db, entry_id)
    return {
        "ok": True,
        "caption": text,
        "media": _serialize_media(media),
        "entry": _serialize_entry(_require_entry(db, entry_id)),
    }


@router.post("/entries/{entry_id}/reindex")
def reindex_entry(
    entry_id: int,
    background_tasks: BackgroundTasks,
    sync: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_superuser(current_user):
        raise HTTPException(status_code=403, detail="Only superuser can reindex knowledge entries")
    row = _require_entry(db, entry_id)
    if str(row.review_status or "") != "approved":
        raise HTTPException(status_code=400, detail="Only approved entries can be indexed")
    row.index_status = "pending"
    row.index_error = None
    row.updated_at = now_bj_iso()
    db.commit()
    if sync:
        result = rebuild_entry_index(db, entry_id)
        return {"ok": bool(result.get("ok")), **result, "entry": _serialize_entry(_require_entry(db, entry_id))}
    background_tasks.add_task(rebuild_entry_index_background, entry_id)
    return {"ok": True, "queued": True, "entry": _serialize_entry(_require_entry(db, entry_id))}


@router.post("/entries/{entry_id}/quality")
def update_entry_quality(
    entry_id: int,
    payload: KbEntryQualityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _require_entry(db, entry_id)
    if not _is_superuser(current_user) and not _can_edit_entry(current_user, row):
        raise HTTPException(status_code=403, detail="Not allowed to update quality")
    row.quality_score = _clamp_quality(payload.quality_score)
    if payload.quality_notes is not None:
        row.quality_notes = str(payload.quality_notes).strip() or None
    if payload.is_eval_gold is not None:
        if not _is_superuser(current_user):
            raise HTTPException(status_code=403, detail="Only superuser can mark eval gold")
        row.is_eval_gold = bool(payload.is_eval_gold)
    row.updated_at = now_bj_iso()
    db.commit()
    return _serialize_entry(_require_entry(db, entry_id))


@router.get("/eval/cases")
def list_eval_cases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_superuser(current_user):
        raise HTTPException(status_code=403, detail="Only superuser can manage eval cases")
    rows = db.query(KbEvalCase).order_by(KbEvalCase.id.desc()).limit(500).all()
    return {"items": [_serialize_eval_case(r) for r in rows], "total": len(rows)}


@router.post("/eval/cases")
def create_eval_case(
    payload: KbEvalCaseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_superuser(current_user):
        raise HTTPException(status_code=403, detail="Only superuser can manage eval cases")
    query = str(payload.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    now = now_bj_iso()
    row = KbEvalCase(
        name=(str(payload.name).strip() if payload.name else None),
        query=query,
        category=_validate_category(payload.category) if payload.category else None,
        expected_entry_ids=[int(i) for i in (payload.expected_entry_ids or []) if i is not None],
        expected_tags=_normalize_tags(payload.expected_tags),
        notes=(str(payload.notes).strip() if payload.notes else None),
        is_active=bool(payload.is_active),
        created_by_user_id=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_eval_case(row)


@router.put("/eval/cases/{case_id}")
def update_eval_case(
    case_id: int,
    payload: KbEvalCaseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_superuser(current_user):
        raise HTTPException(status_code=403, detail="Only superuser can manage eval cases")
    row = db.query(KbEvalCase).filter(KbEvalCase.id == case_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Eval case not found")
    data = payload.dict(exclude_unset=True)
    if "category" in data and data["category"]:
        data["category"] = _validate_category(data["category"])
    if "expected_entry_ids" in data and data["expected_entry_ids"] is not None:
        data["expected_entry_ids"] = [int(i) for i in data["expected_entry_ids"] if i is not None]
    if "expected_tags" in data and data["expected_tags"] is not None:
        data["expected_tags"] = _normalize_tags(data["expected_tags"])
    for key, value in data.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(row, key, value)
    row.updated_at = now_bj_iso()
    db.commit()
    db.refresh(row)
    return _serialize_eval_case(row)


@router.delete("/eval/cases/{case_id}")
def delete_eval_case(
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_superuser(current_user):
        raise HTTPException(status_code=403, detail="Only superuser can manage eval cases")
    row = db.query(KbEvalCase).filter(KbEvalCase.id == case_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Eval case not found")
    db.delete(row)
    db.commit()
    return {"ok": True, "id": case_id}


@router.post("/eval/run")
def run_eval(
    payload: KbEvalRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_superuser(current_user):
        raise HTTPException(status_code=403, detail="Only superuser can run KB eval")
    category = _validate_category(payload.category) if payload.category else None
    return run_kb_eval(
        db,
        top_k=max(1, min(int(payload.top_k or 8), 30)),
        mode=str(payload.mode or "hybrid"),
        category=category,
    )


@router.get("/projects/{project_id}/collection")
def get_project_kb_collection(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _require_project_access(db, project_id, current_user)
    gi = project.global_info if isinstance(project.global_info, dict) else {}
    entry_ids = [int(i) for i in (gi.get("kb_collection_ids") or []) if i is not None]
    entries = []
    if entry_ids:
        rows = (
            db.query(KbEntry)
            .options(joinedload(KbEntry.work), joinedload(KbEntry.media))
            .filter(KbEntry.id.in_(entry_ids), KbEntry.is_deleted.is_(False))
            .all()
        )
        by_id = {int(r.id): r for r in rows}
        entries = [_serialize_entry(by_id[i]) for i in entry_ids if i in by_id]
    return {
        "project_id": project_id,
        "kb_enabled": bool(gi.get("kb_enabled")),
        "collection_only": bool(gi.get("kb_collection_only")),
        "entry_ids": entry_ids,
        "entries": entries,
    }


@router.get("/import/template.csv")
def download_import_template_csv(current_user: User = Depends(get_current_user)):
    content = build_csv_template()
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="kb_import_template.csv"'},
    )


@router.get("/import/template.json")
def download_import_template_json(current_user: User = Depends(get_current_user)):
    return build_json_template()


def _form_flag(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off", ""}:
        return False
    return default


@router.post("/import")
async def import_kb_file(
    file: UploadFile = File(...),
    dry_run: str = Form("false"),
    auto_approve: str = Form("false"),
    reindex_approved: str = Form("true"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        text = raw.decode("utf-8-sig")
    except Exception:
        try:
            text = raw.decode("gbk")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Unable to decode file: {exc}") from exc
    rows = parse_import_payload(content=text, filename=file.filename or "")
    is_dry = _form_flag(dry_run, False)
    result = import_kb_entries(
        db,
        current_user=current_user,
        rows=rows,
        dry_run=is_dry,
        auto_approve=_form_flag(auto_approve, False),
        reindex_approved=_form_flag(reindex_approved, True),
    )
    return _serialize_ingest_result(db, result) if not result.get("dry_run") else result

@router.post("/import/json")
def import_kb_json(
    payload: KbImportJsonRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = parse_import_payload(
        content=json.dumps({"entries": payload.entries or []}, ensure_ascii=False),
        filename="payload.json",
    )
    result = import_kb_entries(
        db,
        current_user=current_user,
        rows=rows,
        dry_run=bool(payload.dry_run),
        auto_approve=bool(payload.auto_approve),
        reindex_approved=bool(payload.reindex_approved),
    )
    return _serialize_ingest_result(db, result) if not result.get("dry_run") else result


@router.put("/projects/{project_id}/collection")
def update_project_kb_collection(
    project_id: int,
    payload: KbProjectCollectionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _require_project_access(db, project_id, current_user)
    gi = dict(project.global_info) if isinstance(project.global_info, dict) else {}
    entry_ids = []
    for raw in payload.entry_ids or []:
        try:
            eid = int(raw)
        except Exception:
            continue
        if eid > 0 and eid not in entry_ids:
            entry_ids.append(eid)
    if entry_ids:
        existing = {
            int(r.id)
            for r in db.query(KbEntry.id)
            .filter(KbEntry.id.in_(entry_ids), KbEntry.is_deleted.is_(False))
            .all()
        }
        entry_ids = [i for i in entry_ids if i in existing]
    gi["kb_collection_ids"] = entry_ids
    gi["kb_collection_only"] = bool(payload.collection_only)
    project.global_info = gi
    db.commit()
    db.refresh(project)
    return {
        "ok": True,
        "project_id": project_id,
        "entry_ids": entry_ids,
        "collection_only": bool(payload.collection_only),
    }
