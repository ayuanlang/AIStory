# -*- coding: utf-8 -*-
"""Knowledge-base RAG: chunking, embeddings, hybrid search (P1)."""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import httpx
import numpy as np
from sqlalchemy.orm import Session, joinedload

from app.core.time_utils import now_bj_iso
from app.models.all_models import KbChunk, KbEntry, KbEntryMedia, SystemAPISetting
from app.services.system_default_api_service import get_task_default_system_setting

logger = logging.getLogger("api_logger")

LOCAL_EMBED_MODEL = "local_hash_v1"
LOCAL_EMBED_DIM = 384
DEFAULT_CHUNK_SIZE = 420
DEFAULT_CHUNK_OVERLAP = 80
_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+", re.UNICODE)


def _tokenize(text: str) -> List[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(str(text or ""))]


def chunk_text(text: str, *, size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> List[str]:
    raw = re.sub(r"\s+", " ", str(text or "").strip())
    if not raw:
        return []
    if len(raw) <= size:
        return [raw]
    step = max(size - overlap, 1)
    chunks: List[str] = []
    start = 0
    while start < len(raw):
        end = min(len(raw), start + size)
        piece = raw[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(raw):
            break
        start += step
    return chunks


def build_entry_source_text(entry: KbEntry) -> str:
    parts: List[str] = []
    title = str(getattr(entry, "title", "") or "").strip()
    if title:
        parts.append(f"标题：{title}")
    summary = str(getattr(entry, "summary", "") or "").strip()
    if summary:
        parts.append(f"摘要：{summary}")
    body = str(getattr(entry, "body_text", "") or "").strip()
    if body:
        parts.append(body)
    tags = getattr(entry, "tags", None) or []
    if tags:
        parts.append("标签：" + "、".join(str(t).strip() for t in tags if str(t).strip()))
    styles = getattr(entry, "style_keywords", None) or []
    if styles:
        parts.append("风格：" + "、".join(str(t).strip() for t in styles if str(t).strip()))
    work = getattr(entry, "work", None)
    if work and getattr(work, "title", None):
        year = str(getattr(work, "year", "") or "").strip()
        parts.append(f"作品：{work.title}" + (f"（{year}）" if year else ""))
    return "\n".join(parts).strip()


def _l2_normalize(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    if norm <= 1e-12:
        return vec
    return vec / norm


def local_hash_embed(text: str, *, dim: int = LOCAL_EMBED_DIM) -> List[float]:
    tokens = _tokenize(text)
    vec = np.zeros(dim, dtype=np.float32)
    if not tokens:
        return vec.tolist()
    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        # two signed hashed features per token
        for offset in (0, 8):
            idx = int.from_bytes(digest[offset:offset + 4], "little") % dim
            sign = 1.0 if (digest[offset + 4] & 1) == 0 else -1.0
            vec[idx] += sign
    return _l2_normalize(vec).tolist()


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom <= 1e-12:
        return 0.0
    return float(np.dot(va, vb) / denom)


def keyword_score(query: str, text: str) -> float:
    q_tokens = set(_tokenize(query))
    if not q_tokens:
        return 0.0
    t_tokens = set(_tokenize(text))
    if not t_tokens:
        return 0.0
    overlap = len(q_tokens & t_tokens)
    return overlap / max(len(q_tokens), 1)


def _pick_api_key(raw: Optional[str]) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    for part in re.split(r"[,;\s]+", text):
        key = part.strip()
        if key:
            return key
    return ""


def resolve_embedding_setting(db: Session) -> Optional[SystemAPISetting]:
    row = get_task_default_system_setting(db, "Embeddings")
    if row and _pick_api_key(getattr(row, "api_key", None)):
        return row

    # Prefer explicit embedding models/categories.
    candidates = (
        db.query(SystemAPISetting)
        .order_by(SystemAPISetting.id.desc())
        .limit(200)
        .all()
    )
    for item in candidates:
        category = str(getattr(item, "category", "") or "").lower()
        model = str(getattr(item, "model", "") or "").lower()
        name = str(getattr(item, "name", "") or "").lower()
        if not _pick_api_key(getattr(item, "api_key", None)):
            continue
        if "embed" in category or "embed" in model or "embed" in name:
            return item
    return None


def _embeddings_url(base_url: str) -> str:
    root = str(base_url or "").strip().rstrip("/")
    if not root:
        return "https://api.openai.com/v1/embeddings"
    if root.endswith("/embeddings"):
        return root
    if root.endswith("/v1"):
        return f"{root}/embeddings"
    if "/v1/" in root:
        return root.rstrip("/")
    return f"{root}/v1/embeddings"


def embed_texts_remote(
    texts: List[str],
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout: float = 60.0,
) -> List[List[float]]:
    url = _embeddings_url(base_url)
    payload = {"model": model, "input": texts}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    items = data.get("data") or []
    items_sorted = sorted(items, key=lambda x: int(x.get("index") or 0))
    vectors: List[List[float]] = []
    for item in items_sorted:
        emb = item.get("embedding") or []
        vectors.append([float(v) for v in emb])
    if len(vectors) != len(texts):
        raise RuntimeError(f"Embedding count mismatch: got {len(vectors)} for {len(texts)} texts")
    return vectors


def embed_texts(db: Session, texts: List[str]) -> Tuple[List[List[float]], str]:
    cleaned = [str(t or "").strip() or " " for t in texts]
    setting = resolve_embedding_setting(db)
    if setting:
        api_key = _pick_api_key(getattr(setting, "api_key", None))
        model = str(getattr(setting, "model", "") or "").strip()
        base_url = str(getattr(setting, "base_url", "") or "").strip()
        if api_key and model:
            try:
                vectors = embed_texts_remote(cleaned, api_key=api_key, base_url=base_url, model=model)
                return vectors, model
            except Exception as exc:
                logger.warning("Remote embedding failed, fallback to local: %s", exc)
    return [local_hash_embed(t) for t in cleaned], LOCAL_EMBED_MODEL


def clear_entry_chunks(db: Session, entry_id: int) -> None:
    db.query(KbChunk).filter(KbChunk.entry_id == int(entry_id)).delete(synchronize_session=False)


def _collect_index_pieces(entry: KbEntry) -> List[Tuple[str, Dict[str, Any]]]:
    """Return (chunk_text, meta) pairs including image-caption chunks for multimodal search."""
    pieces: List[Tuple[str, Dict[str, Any]]] = []
    source = build_entry_source_text(entry)
    for piece in chunk_text(source):
        pieces.append(
            (
                piece,
                {
                    "kind": "text",
                    "category": entry.category,
                    "plot_subtype": entry.plot_subtype,
                    "title": entry.title,
                },
            )
        )

    media_rows = [
        m
        for m in (getattr(entry, "media", None) or [])
        if (not bool(getattr(m, "is_deleted", False)))
        and str(getattr(m, "media_type", "") or "") == "image"
        and str(getattr(m, "caption", "") or "").strip()
    ]
    media_rows.sort(key=lambda m: (int(getattr(m, "sort_order", 0) or 0), int(getattr(m, "id", 0) or 0)))
    for media in media_rows:
        caption = str(media.caption or "").strip()
        text = f"图像描述：{caption}"
        pieces.append(
            (
                text,
                {
                    "kind": "image",
                    "media_id": int(media.id),
                    "category": entry.category,
                    "plot_subtype": entry.plot_subtype,
                    "title": entry.title,
                },
            )
        )

    if not pieces:
        pieces.append(
            (
                str(entry.title or "untitled"),
                {
                    "kind": "text",
                    "category": entry.category,
                    "plot_subtype": entry.plot_subtype,
                    "title": entry.title,
                },
            )
        )
    return pieces


def rebuild_entry_index(db: Session, entry_id: int) -> Dict[str, Any]:
    entry = (
        db.query(KbEntry)
        .options(joinedload(KbEntry.work), joinedload(KbEntry.media))
        .filter(KbEntry.id == int(entry_id), KbEntry.is_deleted.is_(False))
        .first()
    )
    if not entry:
        return {"ok": False, "error": "entry_not_found"}

    if str(entry.review_status or "") != "approved":
        clear_entry_chunks(db, entry.id)
        entry.index_status = "none"
        entry.indexed_at = None
        entry.index_error = None
        entry.updated_at = now_bj_iso()
        db.commit()
        return {"ok": True, "entry_id": entry.id, "chunk_count": 0, "index_status": "none"}

    entry.index_status = "pending"
    entry.index_error = None
    entry.updated_at = now_bj_iso()
    db.commit()

    try:
        piece_rows = _collect_index_pieces(entry)
        texts = [p[0] for p in piece_rows]
        vectors, model_name = embed_texts(db, texts)
        clear_entry_chunks(db, entry.id)
        now = now_bj_iso()
        image_chunk_count = 0
        for idx, ((piece, meta), vector) in enumerate(zip(piece_rows, vectors)):
            if str(meta.get("kind") or "") == "image":
                image_chunk_count += 1
            db.add(
                KbChunk(
                    entry_id=entry.id,
                    chunk_index=idx,
                    chunk_text=piece,
                    embedding=vector,
                    embedding_model=model_name,
                    embedding_dim=len(vector),
                    meta_info=meta,
                    created_at=now,
                    updated_at=now,
                )
            )
        entry.index_status = "ready"
        entry.indexed_at = now
        entry.index_error = None
        entry.updated_at = now
        db.commit()
        return {
            "ok": True,
            "entry_id": entry.id,
            "chunk_count": len(piece_rows),
            "image_chunk_count": image_chunk_count,
            "embedding_model": model_name,
            "index_status": "ready",
        }
    except Exception as exc:
        logger.exception("Failed to rebuild KB index for entry %s", entry_id)
        entry.index_status = "failed"
        entry.index_error = str(exc)[:800]
        entry.updated_at = now_bj_iso()
        db.commit()
        return {"ok": False, "entry_id": entry_id, "error": str(exc), "index_status": "failed"}


def rebuild_entry_index_background(entry_id: int) -> None:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        rebuild_entry_index(db, entry_id)
    finally:
        db.close()


def _truthy_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y", "on", "enabled"}


def resolve_kb_rag_categories(
    *,
    is_script_optimization_stage: bool = False,
    is_entity_design_phase: bool = False,
    prompt_file: Any = "",
    explicit_categories: Optional[Sequence[str]] = None,
) -> List[str]:
    if explicit_categories:
        out = []
        for item in explicit_categories:
            cat = str(item or "").strip().lower()
            if cat in {"portrait", "costume", "scenery", "plot"} and cat not in out:
                out.append(cat)
        if out:
            return out

    prompt_lower = str(prompt_file or "").strip().lower()
    if is_script_optimization_stage:
        return ["plot", "scenery"]
    if is_entity_design_phase:
        if "character" in prompt_lower:
            return ["portrait", "costume"]
        if "prop" in prompt_lower:
            return ["costume"]
        if "environment" in prompt_lower or "poster" in prompt_lower:
            return ["scenery"]
        return ["portrait", "costume", "scenery"]
    return []


def _build_kb_query_text(
    *,
    request_text: str,
    project_metadata: Optional[Dict[str, Any]] = None,
    category: str,
) -> str:
    meta = project_metadata if isinstance(project_metadata, dict) else {}
    hints = [
        str(meta.get("type") or "").strip(),
        str(meta.get("Global_Style") or meta.get("global_style") or "").strip(),
        str(meta.get("base_positioning") or "").strip(),
        str(meta.get("tone") or "").strip(),
        str(meta.get("era") or "").strip(),
    ]
    category_hint = {
        "portrait": "角色肖像 定妆 造型",
        "costume": "服饰 戏服 材质 配饰",
        "scenery": "场景 美景 空镜 氛围",
        "plot": "经典桥段 对白 动作 名场面",
    }.get(category, "")
    body = re.sub(r"\s+", " ", str(request_text or "")).strip()
    if len(body) > 900:
        body = body[:900]
    parts = [p for p in [category_hint, body, " ".join([h for h in hints if h])] if p]
    return " ".join(parts).strip() or category_hint or "经典流行作品参考"


def format_kb_rag_injection_block(hits_by_category: Dict[str, List[Dict[str, Any]]]) -> str:
    from app.core.prompt_injection import wrap_injection_section

    sections: List[str] = []
    label_map = {
        "portrait": "肖像参考",
        "costume": "服饰参考",
        "scenery": "美景参考",
        "plot": "剧情参考",
    }
    for category, hits in (hits_by_category or {}).items():
        if not hits:
            continue
        lines = [f"## {label_map.get(category, category)}"]
        for idx, hit in enumerate(hits, start=1):
            title = str(hit.get("title") or "").strip() or f"entry-{idx}"
            work = hit.get("work") if isinstance(hit.get("work"), dict) else None
            work_title = str((work or {}).get("title") or "").strip()
            summary = str(hit.get("summary") or hit.get("snippet") or "").strip()
            body = str(hit.get("body_text") or "").strip()
            if len(body) > 360:
                body = body[:360] + "…"
            tags = hit.get("tags") or []
            styles = hit.get("style_keywords") or []
            lines.append(f"{idx}. {title}" + (f"（作品：{work_title}）" if work_title else ""))
            if summary:
                lines.append(f"   摘要：{summary}")
            if body:
                lines.append(f"   要点：{body}")
            if tags or styles:
                lines.append(
                    "   标签："
                    + "、".join([str(x).strip() for x in list(tags)[:8] if str(x).strip()])
                    + (("；风格：" + "、".join([str(x).strip() for x in list(styles)[:8] if str(x).strip()])) if styles else "")
                )
        sections.append("\n".join(lines))

    if not sections:
        return ""

    body = (
        "Platform Knowledge Base References (OPTIONAL inspiration only):\n"
        "HARD RULES:\n"
        "1) These are style/structure references from classic/popular works. They are NOT facts about the current script.\n"
        "2) Do NOT invent, rename, merge, translate, or invent Subject Index / CHAR / ENV / PROP entity names from these references.\n"
        "3) Subject Index name lock remains absolute. Never put KB titles into CHAR:/ENV:/PROP: brackets unless the exact name already exists in Subject Index.\n"
        "4) Prefer transferring visual style, costume language, spatial atmosphere, or plot rhythm — never overwrite user script dialogue/action coverage.\n"
        "5) If a reference conflicts with the current script or Index, IGNORE the reference.\n\n"
        + "\n\n".join(sections)
    )
    return wrap_injection_section("知识库参考", body)


def build_kb_rag_injection_for_analyze(
    db: Session,
    *,
    project_metadata: Optional[Dict[str, Any]],
    request_text: str,
    is_script_optimization_stage: bool = False,
    is_entity_design_phase: bool = False,
    prompt_file: Any = "",
    top_k_per_category: int = 3,
) -> Dict[str, Any]:
    meta = project_metadata if isinstance(project_metadata, dict) else {}
    if not _truthy_flag(meta.get("kb_enabled")):
        return {"enabled": False, "block": "", "hit_count": 0}

    categories = resolve_kb_rag_categories(
        is_script_optimization_stage=is_script_optimization_stage,
        is_entity_design_phase=is_entity_design_phase,
        prompt_file=prompt_file,
        explicit_categories=meta.get("kb_categories") if isinstance(meta.get("kb_categories"), list) else None,
    )
    if not categories:
        return {"enabled": True, "block": "", "hit_count": 0, "categories": []}

    try:
        top_k = int(meta.get("kb_top_k") or top_k_per_category)
    except Exception:
        top_k = top_k_per_category
    top_k = max(1, min(top_k, 6))

    collection_ids: Optional[List[int]] = None
    raw_collection = meta.get("kb_collection_ids")
    if isinstance(raw_collection, list):
        collection_ids = [int(i) for i in raw_collection if str(i).strip().isdigit() or isinstance(i, int)]
        if not collection_ids:
            collection_ids = None
    collection_only = _truthy_flag(meta.get("kb_collection_only"))
    entry_ids_filter = collection_ids if (collection_only and collection_ids) else None

    hits_by_category: Dict[str, List[Dict[str, Any]]] = {}
    total_hits = 0
    used_entry_ids: List[int] = []
    for category in categories:
        query = _build_kb_query_text(
            request_text=request_text,
            project_metadata=meta,
            category=category,
        )
        try:
            result = search_kb(
                db,
                query=query,
                category=category,
                top_k=top_k,
                mode="hybrid",
                is_superuser=False,
                entry_ids=entry_ids_filter,
                allowed_license_tiers=list(INJECTABLE_LICENSE_TIERS),
            )
        except Exception as exc:
            logger.warning("KB RAG search failed category=%s: %s", category, exc)
            continue

        # Soft-boost collection favorites when not in collection-only mode.
        hits = list(result.get("hits") or [])
        if collection_ids and not collection_only:
            fav = set(collection_ids)
            hits.sort(
                key=lambda h: (
                    1 if int(getattr(h.get("entry"), "id", 0) or 0) in fav else 0,
                    float(h.get("score") or 0),
                ),
                reverse=True,
            )

        approved_hits = []
        for hit in hits[:top_k]:
            entry = hit.get("entry")
            if not entry or str(getattr(entry, "review_status", "") or "") != "approved":
                continue
            used_entry_ids.append(int(entry.id))
            approved_hits.append(
                {
                    "title": getattr(entry, "title", None),
                    "summary": getattr(entry, "summary", None),
                    "body_text": getattr(entry, "body_text", None),
                    "tags": getattr(entry, "tags", None) or [],
                    "style_keywords": getattr(entry, "style_keywords", None) or [],
                    "work": {
                        "title": getattr(getattr(entry, "work", None), "title", None),
                        "year": getattr(getattr(entry, "work", None), "year", None),
                    }
                    if getattr(entry, "work", None)
                    else None,
                    "snippet": hit.get("snippet"),
                    "score": hit.get("score"),
                    "quality_score": getattr(entry, "quality_score", None),
                    "license_tier": getattr(entry, "license_tier", None),
                }
            )
        if approved_hits:
            hits_by_category[category] = approved_hits
            total_hits += len(approved_hits)

    if used_entry_ids:
        try:
            for eid in sorted(set(used_entry_ids)):
                row = db.query(KbEntry).filter(KbEntry.id == eid).first()
                if row:
                    row.inject_count = int(getattr(row, "inject_count", 0) or 0) + 1
            db.commit()
        except Exception as exc:
            logger.warning("Failed to bump KB inject_count: %s", exc)
            try:
                db.rollback()
            except Exception:
                pass

    block = format_kb_rag_injection_block(hits_by_category)
    return {
        "enabled": True,
        "block": block,
        "hit_count": total_hits,
        "categories": categories,
        "collection_only": collection_only,
        "collection_size": len(collection_ids or []),
    }


INJECTABLE_LICENSE_TIERS = {"public_domain", "reference_ok", "fair_use_ref"}
BLOCKED_LICENSE_TIERS = {"blocked"}


def search_kb(
    db: Session,
    *,
    query: str,
    category: Optional[str] = None,
    plot_subtype: Optional[str] = None,
    top_k: int = 12,
    mode: str = "hybrid",
    include_pending_for_user_id: Optional[int] = None,
    is_superuser: bool = False,
    entry_ids: Optional[Sequence[int]] = None,
    include_restricted: bool = False,
    allowed_license_tiers: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    q = str(query or "").strip()
    if not q:
        return {"hits": [], "total": 0, "mode": mode, "embedding_model": None}

    mode_norm = str(mode or "hybrid").strip().lower()
    if mode_norm not in {"hybrid", "semantic", "keyword"}:
        mode_norm = "hybrid"

    entry_q = db.query(KbEntry).filter(KbEntry.is_deleted.is_(False))
    if category:
        entry_q = entry_q.filter(KbEntry.category == category)
    if plot_subtype:
        entry_q = entry_q.filter(KbEntry.plot_subtype == plot_subtype)
    if entry_ids:
        id_list = [int(i) for i in entry_ids if i is not None]
        if not id_list:
            return {"hits": [], "total": 0, "mode": mode_norm, "embedding_model": None}
        entry_q = entry_q.filter(KbEntry.id.in_(id_list))

    # License governance
    if allowed_license_tiers:
        tiers = [str(t).strip().lower() for t in allowed_license_tiers if str(t).strip()]
        if tiers:
            entry_q = entry_q.filter(KbEntry.license_tier.in_(tiers))
    else:
        entry_q = entry_q.filter(~KbEntry.license_tier.in_(list(BLOCKED_LICENSE_TIERS)))
        if not include_restricted:
            entry_q = entry_q.filter(KbEntry.license_tier != "restricted")

    if not is_superuser:
        if include_pending_for_user_id:
            from sqlalchemy import or_

            entry_q = entry_q.filter(
                or_(
                    KbEntry.review_status == "approved",
                    KbEntry.created_by_user_id == int(include_pending_for_user_id),
                )
            )
        else:
            entry_q = entry_q.filter(KbEntry.review_status == "approved")

    candidate_rows = entry_q.all()
    allowed_ids = {int(r.id) for r in candidate_rows}
    quality_by_id = {
        int(r.id): float(getattr(r, "quality_score", None) or 3.0)
        for r in candidate_rows
    }
    if not allowed_ids:
        return {"hits": [], "total": 0, "mode": mode_norm, "embedding_model": None}

    query_vec: Optional[List[float]] = None
    embed_model = None
    if mode_norm in {"hybrid", "semantic"}:
        vectors, embed_model = embed_texts(db, [q])
        query_vec = vectors[0]

    chunks = (
        db.query(KbChunk)
        .filter(KbChunk.entry_id.in_(list(allowed_ids)))
        .all()
    )

    scored: Dict[int, Dict[str, Any]] = {}
    for chunk in chunks:
        entry_id = int(chunk.entry_id)
        semantic = 0.0
        if query_vec and chunk.embedding:
            if len(chunk.embedding) == len(query_vec):
                semantic = cosine_similarity(query_vec, chunk.embedding)
        kw = keyword_score(q, chunk.chunk_text or "")
        if mode_norm == "semantic":
            base = semantic
        elif mode_norm == "keyword":
            base = kw
        else:
            base = 0.72 * semantic + 0.28 * kw
        quality = max(0.0, min(float(quality_by_id.get(entry_id, 3.0)), 5.0))
        score = base * (0.85 + 0.15 * (quality / 5.0))
        meta = chunk.meta_info if isinstance(chunk.meta_info, dict) else {}
        prev = scored.get(entry_id)
        if not prev or score > float(prev["score"]):
            scored[entry_id] = {
                "entry_id": entry_id,
                "score": float(score),
                "semantic_score": float(semantic),
                "keyword_score": float(kw),
                "quality_score": quality,
                "snippet": (chunk.chunk_text or "")[:280],
                "chunk_id": chunk.id,
                "chunk_kind": str(meta.get("kind") or "text"),
                "media_id": meta.get("media_id"),
            }

    if mode_norm in {"hybrid", "keyword"}:
        for entry in candidate_rows:
            blob = " ".join(
                [
                    str(entry.title or ""),
                    str(entry.summary or ""),
                    str(entry.body_text or ""),
                    " ".join(entry.tags or []),
                    " ".join(entry.style_keywords or []),
                ]
            )
            kw = keyword_score(q, blob)
            if kw <= 0:
                continue
            prev = scored.get(int(entry.id))
            quality = max(0.0, min(float(getattr(entry, "quality_score", None) or 3.0), 5.0))
            base = kw if mode_norm == "keyword" else (0.28 * kw)
            score = base * (0.85 + 0.15 * (quality / 5.0))
            if not prev or score > float(prev["score"]):
                scored[int(entry.id)] = {
                    "entry_id": int(entry.id),
                    "score": float(max(score, float(prev["score"]) if prev else 0.0)),
                    "semantic_score": float(prev["semantic_score"]) if prev else 0.0,
                    "keyword_score": float(kw),
                    "quality_score": quality,
                    "snippet": (entry.summary or entry.body_text or entry.title or "")[:280],
                    "chunk_id": prev.get("chunk_id") if prev else None,
                    "chunk_kind": prev.get("chunk_kind") if prev else "text",
                    "media_id": prev.get("media_id") if prev else None,
                }

    ranked = sorted(scored.values(), key=lambda x: (x["score"], x.get("quality_score", 0)), reverse=True)
    ranked = [item for item in ranked if float(item["score"]) > 0.02][: max(int(top_k or 12), 1)]
    if not ranked:
        return {"hits": [], "total": 0, "mode": mode_norm, "embedding_model": embed_model}

    ids = [int(item["entry_id"]) for item in ranked]
    entries = (
        db.query(KbEntry)
        .options(joinedload(KbEntry.media), joinedload(KbEntry.work))
        .filter(KbEntry.id.in_(ids))
        .all()
    )
    by_id = {int(e.id): e for e in entries}

    hits = []
    for item in ranked:
        entry = by_id.get(int(item["entry_id"]))
        if not entry:
            continue
        hits.append(
            {
                "entry": entry,
                "score": round(float(item["score"]), 4),
                "semantic_score": round(float(item["semantic_score"]), 4),
                "keyword_score": round(float(item["keyword_score"]), 4),
                "quality_score": round(float(item.get("quality_score") or 0), 2),
                "snippet": item.get("snippet"),
                "matched_chunk_id": item.get("chunk_id"),
                "matched_chunk_kind": item.get("chunk_kind") or "text",
                "matched_media_id": item.get("media_id"),
            }
        )

    return {
        "hits": hits,
        "total": len(hits),
        "mode": mode_norm,
        "embedding_model": embed_model,
    }
