# -*- coding: utf-8 -*-
"""Knowledge-base batch import from CSV / JSON templates (ops)."""
from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.time_utils import now_bj_iso
from app.models.all_models import KbEntry, KbWork, User
from app.services.kb_ingest_service import _find_or_create_work, _normalize_list
from app.services.kb_rag_service import rebuild_entry_index

KB_CATEGORIES = {"portrait", "costume", "scenery", "plot"}
PLOT_SUBTYPES = {"trope", "dialogue", "action"}
LICENSE_TIERS = {"public_domain", "reference_ok", "fair_use_ref", "restricted", "blocked"}

TEMPLATE_COLUMNS = [
    "category",
    "title",
    "summary",
    "body_text",
    "tags",
    "style_keywords",
    "plot_subtype",
    "work_title",
    "work_year",
    "license_tier",
    "copyright_note",
    "source_url",
    "quality_score",
    "is_eval_gold",
]

TEMPLATE_SAMPLE_ROWS = [
    {
        "category": "portrait",
        "title": "冷静女主近景定妆参考",
        "summary": "都市权谋女主的冷感近景造型参考",
        "body_text": "高对比侧光；利落短发；哑光妆面；眼神克制；西装剪裁肩线清晰。",
        "tags": "都市,权谋,女主,定妆",
        "style_keywords": "冷感,克制,近景",
        "plot_subtype": "",
        "work_title": "示例作品A",
        "work_year": "2020",
        "license_tier": "reference_ok",
        "copyright_note": "风格参考，非角色复刻",
        "source_url": "https://example.com/ref",
        "quality_score": "4",
        "is_eval_gold": "false",
    },
    {
        "category": "plot",
        "title": "雨夜对峙经典桥段",
        "summary": "双人雨夜对峙的节奏与正反打参考",
        "body_text": "开场环境雨点建立；OTS 对峙；短句交锋；反打读反应；收束于沉默停顿。",
        "tags": "对峙,雨夜,正反打",
        "style_keywords": "紧张,留白",
        "plot_subtype": "trope",
        "work_title": "示例作品B",
        "work_year": "2018",
        "license_tier": "fair_use_ref",
        "copyright_note": "结构参考",
        "source_url": "",
        "quality_score": "3.5",
        "is_eval_gold": "true",
    },
]


def build_csv_template() -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TEMPLATE_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in TEMPLATE_SAMPLE_ROWS:
        writer.writerow(row)
    return buf.getvalue()


def build_json_template() -> Dict[str, Any]:
    entries = []
    for row in TEMPLATE_SAMPLE_ROWS:
        entries.append(
            {
                "category": row["category"],
                "title": row["title"],
                "summary": row["summary"],
                "body_text": row["body_text"],
                "tags": [p.strip() for p in str(row["tags"]).split(",") if p.strip()],
                "style_keywords": [p.strip() for p in str(row["style_keywords"]).split(",") if p.strip()],
                "plot_subtype": row["plot_subtype"] or None,
                "work_title": row["work_title"] or None,
                "work_year": row["work_year"] or None,
                "license_tier": row["license_tier"],
                "copyright_note": row["copyright_note"] or None,
                "source_url": row["source_url"] or None,
                "quality_score": float(row["quality_score"]),
                "is_eval_gold": str(row["is_eval_gold"]).lower() in {"1", "true", "yes"},
            }
        )
    return {
        "format": "aistory_kb_import_v1",
        "entries": entries,
    }


def _split_list_field(value: Any) -> List[str]:
    if isinstance(value, list):
        return _normalize_list(value)
    text = str(value or "").strip()
    if not text:
        return []
    return _normalize_list([p for p in text.replace("；", ",").replace(";", ",").replace("|", ",").split(",")])


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y", "on"}


def _clamp_quality(value: Any, default: float = 3.0) -> float:
    try:
        score = float(value)
    except Exception:
        score = default
    return max(0.0, min(score, 5.0))


def _normalize_row(raw: Dict[str, Any], *, row_no: int) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"row {row_no}: expected object")
    # tolerate Chinese headers via alias map
    aliases = {
        "栏目": "category",
        "标题": "title",
        "摘要": "summary",
        "正文": "body_text",
        "标签": "tags",
        "风格词": "style_keywords",
        "剧情子类": "plot_subtype",
        "作品名": "work_title",
        "年份": "work_year",
        "版权层级": "license_tier",
        "版权备注": "copyright_note",
        "来源": "source_url",
        "质量分": "quality_score",
        "评测金标": "is_eval_gold",
    }
    normalized: Dict[str, Any] = {}
    for key, value in raw.items():
        k = str(key or "").strip()
        k = aliases.get(k, k)
        normalized[k] = value

    category = str(normalized.get("category") or "").strip().lower()
    title = str(normalized.get("title") or "").strip()
    if category not in KB_CATEGORIES:
        raise ValueError(f"row {row_no}: invalid category '{category}'")
    if not title:
        raise ValueError(f"row {row_no}: title is required")

    plot_subtype = str(normalized.get("plot_subtype") or "").strip().lower() or None
    if category == "plot":
        if plot_subtype and plot_subtype not in PLOT_SUBTYPES:
            raise ValueError(f"row {row_no}: invalid plot_subtype '{plot_subtype}'")
        plot_subtype = plot_subtype or "trope"
    else:
        plot_subtype = None

    license_tier = str(normalized.get("license_tier") or "reference_ok").strip().lower()
    if license_tier not in LICENSE_TIERS:
        raise ValueError(f"row {row_no}: invalid license_tier '{license_tier}'")

    return {
        "category": category,
        "title": title,
        "summary": (str(normalized.get("summary") or "").strip() or None),
        "body_text": (str(normalized.get("body_text") or "").strip() or None),
        "tags": _split_list_field(normalized.get("tags")),
        "style_keywords": _split_list_field(normalized.get("style_keywords")),
        "plot_subtype": plot_subtype,
        "work_title": (str(normalized.get("work_title") or "").strip() or None),
        "work_year": (str(normalized.get("work_year") or "").strip() or None),
        "license_tier": license_tier,
        "copyright_note": (str(normalized.get("copyright_note") or "").strip() or None),
        "source_url": (str(normalized.get("source_url") or "").strip() or None),
        "quality_score": _clamp_quality(normalized.get("quality_score"), 3.0),
        "is_eval_gold": _to_bool(normalized.get("is_eval_gold")),
    }


def parse_import_payload(
    *,
    content: str,
    filename: str = "",
) -> List[Dict[str, Any]]:
    text = str(content or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty import file")

    name = str(filename or "").lower()
    rows_raw: List[Any] = []

    if name.endswith(".json") or text.startswith("{") or text.startswith("["):
        try:
            data = json.loads(text)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc
        if isinstance(data, dict):
            rows_raw = data.get("entries") if isinstance(data.get("entries"), list) else [data]
        elif isinstance(data, list):
            rows_raw = data
        else:
            raise HTTPException(status_code=400, detail="JSON must be an array or {entries:[...]}")
    else:
        # CSV (utf-8 / utf-8-sig)
        try:
            reader = csv.DictReader(io.StringIO(text))
            rows_raw = list(reader)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid CSV: {exc}") from exc
        if not rows_raw:
            raise HTTPException(status_code=400, detail="CSV has no data rows")

    normalized: List[Dict[str, Any]] = []
    errors: List[str] = []
    for idx, raw in enumerate(rows_raw, start=1):
        try:
            normalized.append(_normalize_row(raw, row_no=idx))
        except Exception as exc:
            errors.append(str(exc))
    if errors:
        raise HTTPException(status_code=400, detail={"message": "Import validation failed", "errors": errors[:30]})
    if not normalized:
        raise HTTPException(status_code=400, detail="No valid rows to import")
    return normalized


def import_kb_entries(
    db: Session,
    *,
    current_user: User,
    rows: List[Dict[str, Any]],
    dry_run: bool = False,
    auto_approve: bool = False,
    reindex_approved: bool = True,
    max_rows: int = 200,
) -> Dict[str, Any]:
    limited = rows[: max(1, min(int(max_rows or 200), 500))]
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "parsed_count": len(rows),
            "will_import": len(limited),
            "preview": limited[:5],
        }

    created_ids: List[int] = []
    now = now_bj_iso()
    approve = bool(auto_approve) and bool(getattr(current_user, "is_superuser", False))

    for raw in limited:
        work_id = _find_or_create_work(
            db,
            title=raw.get("work_title"),
            year=raw.get("work_year"),
            user_id=int(current_user.id),
        )
        entry = KbEntry(
            work_id=work_id,
            category=raw["category"],
            plot_subtype=raw.get("plot_subtype"),
            title=raw["title"],
            summary=raw.get("summary"),
            body_text=raw.get("body_text"),
            tags=raw.get("tags") or [],
            style_keywords=raw.get("style_keywords") or [],
            license_tier=raw.get("license_tier") or "reference_ok",
            copyright_note=raw.get("copyright_note"),
            source_type="upload",
            source_url=raw.get("source_url"),
            source_meta={"ingest_mode": "batch_import"},
            quality_score=float(raw.get("quality_score") or 3.0),
            is_eval_gold=bool(raw.get("is_eval_gold")),
            review_status="approved" if approve else "pending",
            reviewed_by_user_id=current_user.id if approve else None,
            reviewed_at=now if approve else None,
            index_status="pending" if approve else "none",
            created_by_user_id=current_user.id,
            created_at=now,
            updated_at=now,
        )
        db.add(entry)
        db.flush()
        created_ids.append(int(entry.id))

    db.commit()

    indexed = 0
    if approve and reindex_approved:
        for eid in created_ids:
            try:
                result = rebuild_entry_index(db, eid)
                if result.get("ok") and result.get("index_status") == "ready":
                    indexed += 1
            except Exception:
                continue

    return {
        "ok": True,
        "dry_run": False,
        "created_count": len(created_ids),
        "entry_ids": created_ids,
        "auto_approved": approve,
        "indexed_count": indexed,
    }
