# -*- coding: utf-8 -*-
"""Knowledge-base RAG evaluation harness (P4)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.all_models import KbEvalCase
from app.services.kb_rag_service import search_kb


def run_kb_eval(
    db: Session,
    *,
    top_k: int = 8,
    mode: str = "hybrid",
    category: Optional[str] = None,
) -> Dict[str, Any]:
    q = db.query(KbEvalCase).filter(KbEvalCase.is_active.is_(True))
    if category:
        q = q.filter(KbEvalCase.category == category)
    cases = q.order_by(KbEvalCase.id.asc()).all()
    if not cases:
        return {
            "ok": True,
            "case_count": 0,
            "hit_at_k": None,
            "avg_reciprocal_rank": None,
            "results": [],
        }

    k = max(1, min(int(top_k or 8), 30))
    results: List[Dict[str, Any]] = []
    hit_count = 0
    rr_sum = 0.0

    for case in cases:
        expected_ids = [int(i) for i in (case.expected_entry_ids or []) if i is not None]
        expected_tags = [str(t).strip().lower() for t in (case.expected_tags or []) if str(t).strip()]
        search = search_kb(
            db,
            query=str(case.query or ""),
            category=str(case.category or "").strip() or None,
            top_k=k,
            mode=mode,
            is_superuser=False,
            include_restricted=False,
        )
        ranked_ids: List[int] = []
        ranked_tags: List[str] = []
        for hit in search.get("hits") or []:
            entry = hit.get("entry")
            if not entry:
                continue
            ranked_ids.append(int(entry.id))
            for tag in (getattr(entry, "tags", None) or []):
                ranked_tags.append(str(tag).strip().lower())

        matched_ids = [eid for eid in ranked_ids if eid in set(expected_ids)]
        tag_hit = False
        if expected_tags:
            tag_hit = any(t in set(ranked_tags) for t in expected_tags)

        hit = bool(matched_ids) or (bool(expected_tags) and tag_hit and not expected_ids)
        if hit:
            hit_count += 1

        rank = None
        for idx, eid in enumerate(ranked_ids, start=1):
            if eid in set(expected_ids):
                rank = idx
                break
        if rank is not None:
            rr_sum += 1.0 / float(rank)
        elif hit and not expected_ids:
            rr_sum += 1.0
            rank = 1

        results.append(
            {
                "case_id": case.id,
                "name": case.name,
                "query": case.query,
                "category": case.category,
                "expected_entry_ids": expected_ids,
                "ranked_entry_ids": ranked_ids,
                "matched_entry_ids": matched_ids,
                "hit": hit,
                "rank": rank,
                "tag_hit": tag_hit,
            }
        )

    n = len(cases)
    return {
        "ok": True,
        "case_count": n,
        "top_k": k,
        "mode": mode,
        "hit_at_k": round(hit_count / n, 4) if n else None,
        "avg_reciprocal_rank": round(rr_sum / n, 4) if n else None,
        "results": results,
    }
