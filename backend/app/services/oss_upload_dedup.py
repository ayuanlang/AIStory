# -*- coding: utf-8 -*-
"""Cross-process OSS upload claim/wait helpers (Postgres/SQLite).

Process-local threading dedup cannot coordinate gunicorn workers or the
generation worker. This table lets only one process upload a given object key;
others wait and reuse the winner's result (or head_object after release).
"""
from __future__ import annotations

import json
import logging
import os
import socket
import threading
import time
import uuid
from typing import Any, Dict, Optional

from sqlalchemy import text

from app.db.session import SessionLocal, engine

logger = logging.getLogger(__name__)

_OSS_CROSS_DEDUP_ENABLED = str(os.getenv("OSS_UPLOAD_CROSS_PROCESS_DEDUP", "1") or "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_OSS_CROSS_LOCK_TTL_SECONDS = max(
    60,
    int(os.getenv("OSS_UPLOAD_CROSS_PROCESS_LOCK_TTL_SECONDS", "180") or 180),
)
_OSS_CROSS_WAIT_SECONDS = max(
    5,
    int(os.getenv("OSS_UPLOAD_CROSS_PROCESS_WAIT_SECONDS", "20") or 20),
)
_OSS_CROSS_POLL_SECONDS = max(
    0.2,
    float(os.getenv("OSS_UPLOAD_CROSS_PROCESS_POLL_SECONDS", "1.0") or 1.0),
)
_OSS_CROSS_DONE_KEEP_SECONDS = max(
    5,
    int(os.getenv("OSS_UPLOAD_CROSS_PROCESS_DONE_KEEP_SECONDS", "45") or 45),
)
_OSS_CROSS_PRUNE_INTERVAL_SECONDS = max(
    30,
    int(os.getenv("OSS_UPLOAD_CROSS_PROCESS_PRUNE_INTERVAL_SECONDS", "120") or 120),
)

_TABLE_READY = False
_TABLE_LOCK = threading.Lock()
_LAST_PRUNE_TS = 0.0
_PRUNE_LOCK = threading.Lock()
_OWNER_ID = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


def is_oss_cross_process_dedup_enabled() -> bool:
    return bool(_OSS_CROSS_DEDUP_ENABLED)


def _ensure_table_ready() -> None:
    global _TABLE_READY
    if _TABLE_READY:
        return
    with _TABLE_LOCK:
        if _TABLE_READY:
            return
        ddl = """
        CREATE TABLE IF NOT EXISTS oss_upload_inflight (
            object_key TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            status TEXT NOT NULL,
            result_json TEXT,
            updated_at REAL NOT NULL
        )
        """
        index_ddl = """
        CREATE INDEX IF NOT EXISTS idx_oss_upload_inflight_updated_at
        ON oss_upload_inflight (updated_at)
        """
        with engine.begin() as conn:
            conn.execute(text(ddl))
            conn.execute(text(index_ddl))
        _TABLE_READY = True


def _prune_stale_rows(now_ts: float) -> None:
    global _LAST_PRUNE_TS
    with _PRUNE_LOCK:
        if (float(now_ts) - float(_LAST_PRUNE_TS)) < float(_OSS_CROSS_PRUNE_INTERVAL_SECONDS):
            return
        _LAST_PRUNE_TS = float(now_ts)

    uploading_cutoff = float(now_ts) - float(_OSS_CROSS_LOCK_TTL_SECONDS)
    done_cutoff = float(now_ts) - float(_OSS_CROSS_DONE_KEEP_SECONDS)
    db = SessionLocal()
    try:
        result = db.execute(
            text(
                """
                DELETE FROM oss_upload_inflight
                WHERE (status = 'uploading' AND updated_at < :uploading_cutoff)
                   OR (status = 'done' AND updated_at < :done_cutoff)
                """
            ),
            {
                "uploading_cutoff": uploading_cutoff,
                "done_cutoff": done_cutoff,
            },
        )
        db.commit()
        pruned = int(result.rowcount or 0)
        if pruned > 0:
            logger.info("[OSSUploadCrossDedup] pruned rows=%s", pruned)
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("[OSSUploadCrossDedup] prune failed err=%s", exc)
    finally:
        db.close()


def _get_row(db, object_key: str) -> Optional[Dict[str, Any]]:
    row = (
        db.execute(
            text(
                """
                SELECT object_key, owner, status, result_json, updated_at
                FROM oss_upload_inflight
                WHERE object_key = :object_key
                """
            ),
            {"object_key": str(object_key)},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def _parse_result(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    if str(row.get("status") or "").strip().lower() != "done":
        return None
    raw = row.get("result_json")
    if not raw:
        return None
    try:
        parsed = json.loads(str(raw))
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) and parsed.get("url") else None


def try_claim_oss_upload(object_key: str) -> bool:
    """Return True when this process owns the cross-process upload slot."""
    if not _OSS_CROSS_DEDUP_ENABLED:
        return True
    key = str(object_key or "").strip()
    if not key:
        return True

    try:
        _ensure_table_ready()
    except Exception as exc:
        logger.warning("[OSSUploadCrossDedup] table ensure failed; allowing upload | err=%s", exc)
        return True

    now_ts = time.time()
    _prune_stale_rows(now_ts)

    db = SessionLocal()
    try:
        existing = _get_row(db, key)
        parsed = _parse_result(existing)
        if parsed is not None:
            return False

        if existing and str(existing.get("status") or "") == "uploading":
            age = now_ts - float(existing.get("updated_at") or 0.0)
            if age <= float(_OSS_CROSS_LOCK_TTL_SECONDS):
                return False
            db.execute(
                text(
                    """
                    DELETE FROM oss_upload_inflight
                    WHERE object_key = :object_key
                      AND status = 'uploading'
                      AND updated_at < :cutoff
                    """
                ),
                {"object_key": key, "cutoff": now_ts - float(_OSS_CROSS_LOCK_TTL_SECONDS)},
            )
            db.commit()

        result = db.execute(
            text(
                """
                INSERT INTO oss_upload_inflight (object_key, owner, status, result_json, updated_at)
                VALUES (:object_key, :owner, 'uploading', NULL, :updated_at)
                ON CONFLICT(object_key) DO NOTHING
                """
            ),
            {
                "object_key": key,
                "owner": _OWNER_ID,
                "updated_at": now_ts,
            },
        )
        db.commit()
        claimed = int(result.rowcount or 0) > 0
        if claimed:
            logger.info("[OSSUploadCrossDedup] claimed | key=%s owner=%s", key, _OWNER_ID)
        return claimed
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("[OSSUploadCrossDedup] claim failed; allowing upload | key=%s err=%s", key, exc)
        return True
    finally:
        db.close()


def wait_for_oss_upload_peer(object_key: str, wait_seconds: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """Wait for another process to finish uploading this key; return its result if any."""
    if not _OSS_CROSS_DEDUP_ENABLED:
        return None
    key = str(object_key or "").strip()
    if not key:
        return None

    try:
        _ensure_table_ready()
    except Exception:
        return None

    timeout = float(_OSS_CROSS_WAIT_SECONDS if wait_seconds is None else wait_seconds)
    deadline = time.time() + max(1.0, timeout)
    while time.time() < deadline:
        now_ts = time.time()
        db = SessionLocal()
        try:
            row = _get_row(db, key)
            parsed = _parse_result(row)
            if parsed is not None:
                logger.info(
                    "[OSSUploadCrossDedup] reused peer result | key=%s url=%s",
                    key,
                    parsed.get("url"),
                )
                return parsed
            if row is None:
                return None
            if str(row.get("status") or "") == "uploading":
                age = now_ts - float(row.get("updated_at") or 0.0)
                if age > float(_OSS_CROSS_LOCK_TTL_SECONDS):
                    db.execute(
                        text(
                            """
                            DELETE FROM oss_upload_inflight
                            WHERE object_key = :object_key
                              AND status = 'uploading'
                              AND updated_at < :cutoff
                            """
                        ),
                        {
                            "object_key": key,
                            "cutoff": now_ts - float(_OSS_CROSS_LOCK_TTL_SECONDS),
                        },
                    )
                    db.commit()
                    return None
        except Exception as exc:
            try:
                db.rollback()
            except Exception:
                pass
            logger.warning("[OSSUploadCrossDedup] wait poll failed | key=%s err=%s", key, exc)
            return None
        finally:
            db.close()
        time.sleep(_OSS_CROSS_POLL_SECONDS)
    logger.warning("[OSSUploadCrossDedup] wait timed out | key=%s", key)
    return None


def complete_oss_upload_claim(object_key: str, result: Optional[Dict[str, Any]]) -> None:
    """Mark claim done with result payload so waiters can reuse it."""
    if not _OSS_CROSS_DEDUP_ENABLED:
        return
    key = str(object_key or "").strip()
    if not key:
        return
    try:
        _ensure_table_ready()
    except Exception:
        return

    payload = None
    if isinstance(result, dict) and result.get("url"):
        try:
            payload = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            payload = None

    db = SessionLocal()
    try:
        if payload:
            db.execute(
                text(
                    """
                    INSERT INTO oss_upload_inflight (object_key, owner, status, result_json, updated_at)
                    VALUES (:object_key, :owner, 'done', :result_json, :updated_at)
                    ON CONFLICT(object_key) DO UPDATE SET
                        owner = excluded.owner,
                        status = 'done',
                        result_json = excluded.result_json,
                        updated_at = excluded.updated_at
                    """
                ),
                {
                    "object_key": key,
                    "owner": _OWNER_ID,
                    "result_json": payload,
                    "updated_at": time.time(),
                },
            )
        else:
            db.execute(
                text("DELETE FROM oss_upload_inflight WHERE object_key = :object_key"),
                {"object_key": key},
            )
        db.commit()
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("[OSSUploadCrossDedup] complete failed | key=%s err=%s", key, exc)
    finally:
        db.close()


def release_oss_upload_claim(object_key: str) -> None:
    """Drop an uploading claim (failure / abandoned). Keeps done rows for waiters."""
    if not _OSS_CROSS_DEDUP_ENABLED:
        return
    key = str(object_key or "").strip()
    if not key:
        return
    try:
        _ensure_table_ready()
    except Exception:
        return

    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                DELETE FROM oss_upload_inflight
                WHERE object_key = :object_key
                  AND status = 'uploading'
                  AND owner = :owner
                """
            ),
            {"object_key": key, "owner": _OWNER_ID},
        )
        db.commit()
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("[OSSUploadCrossDedup] release failed | key=%s err=%s", key, exc)
    finally:
        db.close()


def steal_oss_upload_claim(object_key: str) -> bool:
    """Take over an uploading claim when the peer looks dead and the object is missing."""
    if not _OSS_CROSS_DEDUP_ENABLED:
        return True
    key = str(object_key or "").strip()
    if not key:
        return True

    try:
        _ensure_table_ready()
    except Exception as exc:
        logger.warning("[OSSUploadCrossDedup] table ensure failed; allowing steal | err=%s", exc)
        return True

    now_ts = time.time()
    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                DELETE FROM oss_upload_inflight
                WHERE object_key = :object_key
                  AND status = 'uploading'
                """
            ),
            {"object_key": key},
        )
        db.commit()
        result = db.execute(
            text(
                """
                INSERT INTO oss_upload_inflight (object_key, owner, status, result_json, updated_at)
                VALUES (:object_key, :owner, 'uploading', NULL, :updated_at)
                ON CONFLICT(object_key) DO NOTHING
                """
            ),
            {
                "object_key": key,
                "owner": _OWNER_ID,
                "updated_at": now_ts,
            },
        )
        db.commit()
        claimed = int(result.rowcount or 0) > 0
        if claimed:
            logger.info("[OSSUploadCrossDedup] stole claim | key=%s owner=%s", key, _OWNER_ID)
        return claimed
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("[OSSUploadCrossDedup] steal failed; allowing upload | key=%s err=%s", key, exc)
        return True
    finally:
        db.close()
