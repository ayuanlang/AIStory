"""
In-memory async task manager for long-running LLM operations.

Endpoints submit work via `submit()`, which runs the callable in a background
thread and returns a task_id immediately.  The frontend then polls
`GET /tasks/{task_id}` until status is "completed", "failed", or "canceled".

Completed results are kept for a limited TTL so memory doesn't grow unbounded.
"""

import asyncio
import logging
import threading
import time
import traceback
import uuid
import json
import os
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# How long (seconds) completed/failed results stay in memory before eviction.
_RESULT_TTL = 600  # 10 minutes
_RUNNING_TASK_MAX_AGE_SECONDS = max(300, int(os.getenv("ASYNC_TASK_MAX_AGE_SECONDS", "1200")))
_RESULT_MAX_BYTES = max(16 * 1024, int(os.getenv("ASYNC_TASK_RESULT_MAX_BYTES", str(256 * 1024)) or (256 * 1024)))
_RESULT_PREVIEW_MAX_CHARS = max(512, int(os.getenv("ASYNC_TASK_RESULT_PREVIEW_MAX_CHARS", "4096") or 4096))

# Global task store  {task_id: _TaskRecord}
_tasks: Dict[str, "_TaskRecord"] = {}
_lock = threading.Lock()

_DB_TABLE_READY = False
_DB_TABLE_LOCK = threading.Lock()


def _ensure_db_table_ready() -> None:
    global _DB_TABLE_READY
    if _DB_TABLE_READY:
        return
    with _DB_TABLE_LOCK:
        if _DB_TABLE_READY:
            return
        try:
            from sqlalchemy import text
            from app.db.session import engine

            ddl = """
            CREATE TABLE IF NOT EXISTS async_tasks (
                task_id TEXT PRIMARY KEY,
                user_id INTEGER NULL,
                kind TEXT NULL,
                status TEXT NOT NULL,
                result_json TEXT NULL,
                error TEXT NULL,
                error_code INTEGER NULL,
                created_at REAL NOT NULL,
                finished_at REAL NULL
            )
            """
            with engine.begin() as conn:
                conn.execute(text(ddl))
            _DB_TABLE_READY = True
        except Exception as exc:
            logger.warning("async task DB table init failed (fallback to memory only): %s", exc)


def _serialize_for_db(value: Any) -> Optional[str]:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps(str(value), ensure_ascii=False)


def _compact_task_result(value: Any) -> Any:
    if value is None:
        return None

    serialized = _serialize_for_db(value)
    if not serialized:
        return None

    payload_size = len(serialized.encode("utf-8", errors="ignore"))
    if payload_size <= _RESULT_MAX_BYTES:
        return value

    compact: Dict[str, Any] = {
        "result_truncated": True,
        "result_size_bytes": payload_size,
    }

    if isinstance(value, dict):
        for key in ("status", "kind", "task_id", "job_id", "provider", "model", "url", "error", "detail", "message"):
            if key in value and value.get(key) not in (None, "", []):
                compact[key] = value.get(key)

    compact["result_preview"] = serialized[:_RESULT_PREVIEW_MAX_CHARS]
    return compact


def _save_task_to_db(rec: "_TaskRecord") -> None:
    try:
        _ensure_db_table_ready()
        if not _DB_TABLE_READY:
            return
        from sqlalchemy import text
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            sql = text(
                """
                INSERT INTO async_tasks (
                    task_id, user_id, kind, status, result_json, error, error_code, created_at, finished_at
                ) VALUES (
                    :task_id, :user_id, :kind, :status, :result_json, :error, :error_code, :created_at, :finished_at
                )
                ON CONFLICT(task_id) DO UPDATE SET
                    user_id=excluded.user_id,
                    kind=excluded.kind,
                    status=excluded.status,
                    result_json=excluded.result_json,
                    error=excluded.error,
                    error_code=excluded.error_code,
                    created_at=excluded.created_at,
                    finished_at=excluded.finished_at
                """
            )
            db.execute(
                sql,
                {
                    "task_id": rec.task_id,
                    "user_id": rec.user_id,
                    "kind": rec.kind,
                    "status": rec.status,
                    "result_json": _serialize_for_db(rec.result) if rec.result is not None else None,
                    "error": rec.error,
                    "error_code": rec.error_code,
                    "created_at": rec.created_at,
                    "finished_at": rec.finished_at,
                },
            )
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.warning("async task DB save failed task_id=%s: %s", rec.task_id, exc)


def _load_task_from_db(task_id: str) -> Optional["_TaskRecord"]:
    try:
        _ensure_db_table_ready()
        if not _DB_TABLE_READY:
            return None
        from sqlalchemy import text
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            row = db.execute(
                text(
                    """
                    SELECT task_id, user_id, kind, status, result_json, error, error_code, created_at, finished_at
                    FROM async_tasks
                    WHERE task_id = :task_id
                    """
                ),
                {"task_id": task_id},
            ).mappings().first()
            if not row:
                return None

            rec = _TaskRecord(str(row["task_id"]), row["user_id"], str(row["kind"] or "llm"))
            rec.status = str(row["status"] or "pending")
            raw_result = row["result_json"]
            if raw_result:
                try:
                    rec.result = json.loads(raw_result)
                except Exception:
                    rec.result = raw_result
            rec.error = row["error"]
            rec.error_code = row["error_code"]
            rec.created_at = float(row["created_at"] or time.time())
            rec.finished_at = float(row["finished_at"]) if row["finished_at"] is not None else None
            return rec
        finally:
            db.close()
    except Exception as exc:
        logger.warning("async task DB load failed task_id=%s: %s", task_id, exc)
        return None


class _TaskRecord:
    __slots__ = (
        "task_id", "status", "result", "error", "error_code", "created_at",
        "finished_at", "user_id", "kind", "cancel_requested", "cancel_reason",
    )

    def __init__(self, task_id: str, user_id: Optional[int], kind: str):
        self.task_id = task_id
        self.status = "pending"   # pending | running | completed | failed | canceled
        self.result: Any = None
        self.error: Optional[str] = None
        self.error_code: Optional[int] = None
        self.created_at = time.time()
        self.finished_at: Optional[float] = None
        self.user_id = user_id
        self.kind = kind
        self.cancel_requested = False
        self.cancel_reason = ""


def _get_or_load_task_record(task_id: str) -> Optional["_TaskRecord"]:
    with _lock:
        rec = _tasks.get(task_id)
    if rec is None:
        rec = _load_task_from_db(task_id)
        if rec is not None:
            with _lock:
                _tasks[task_id] = rec
    return rec


def create_task_record(*, task_id: Optional[str] = None, user_id: Optional[int] = None, kind: str = "llm", status: str = "pending") -> str:
    stable_task_id = str(task_id or uuid.uuid4().hex)
    rec = _TaskRecord(stable_task_id, user_id, kind)
    rec.status = str(status or "pending").strip().lower() or "pending"
    if rec.status in {"completed", "failed", "canceled"}:
        rec.finished_at = time.time()

    with _lock:
        _evict_stale()
        _tasks[stable_task_id] = rec
    _save_task_to_db(rec)
    return stable_task_id


def set_task_status(
    task_id: str,
    *,
    status: str,
    result: Any = None,
    error: Optional[str] = None,
    error_code: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    rec = _get_or_load_task_record(str(task_id))
    if rec is None:
        return None

    stable_status = str(status or "pending").strip().lower() or "pending"
    rec.status = stable_status
    rec.result = _compact_task_result(result) if stable_status == "completed" else None
    rec.error = str(error) if error else None
    rec.error_code = error_code
    if stable_status in {"completed", "failed", "canceled"}:
        rec.finished_at = time.time()
    else:
        rec.finished_at = None
    _save_task_to_db(rec)
    return get_status(rec.task_id, user_id=rec.user_id)


def _evict_stale():
    """Remove completed/failed tasks older than TTL.  Called under _lock."""
    now = time.time()
    stale = [
        tid for tid, rec in _tasks.items()
        if rec.finished_at and (now - rec.finished_at) > _RESULT_TTL
    ]
    for tid in stale:
        del _tasks[tid]

    try:
        _ensure_db_table_ready()
        if _DB_TABLE_READY:
            from sqlalchemy import text
            from app.db.session import SessionLocal

            db = SessionLocal()
            try:
                cutoff = now - _RESULT_TTL
                db.execute(
                    text(
                        "DELETE FROM async_tasks WHERE finished_at IS NOT NULL AND finished_at < :cutoff"
                    ),
                    {"cutoff": cutoff},
                )
                db.commit()
            finally:
                db.close()
    except Exception as exc:
        logger.debug("async task DB eviction skipped: %s", exc)


def submit(fn: Callable[[], Any], *, user_id: Optional[int] = None, kind: str = "llm") -> str:
    """
    Submit a zero-arg callable to run in a background thread.
    Returns a task_id string for polling.
    """
    task_id = uuid.uuid4().hex
    rec = _TaskRecord(task_id, user_id, kind)

    with _lock:
        _evict_stale()
        _tasks[task_id] = rec
    _save_task_to_db(rec)

    def _worker():
        rec.status = "running"
        _save_task_to_db(rec)
        try:
            if rec.cancel_requested:
                rec.status = "canceled"
                rec.error = rec.cancel_reason or "Task canceled by user"
                rec.error_code = 499
                return
            rec.result = _compact_task_result(fn())
            if rec.cancel_requested:
                rec.status = "canceled"
                rec.error = rec.cancel_reason or "Task canceled by user"
                rec.error_code = 499
            else:
                rec.status = "completed"
        except Exception as exc:
            if rec.cancel_requested:
                rec.status = "canceled"
                rec.error = rec.cancel_reason or "Task canceled by user"
                rec.error_code = 499
            else:
                rec.status = "failed"
                # HTTPException from FastAPI endpoints
                if hasattr(exc, 'status_code') and hasattr(exc, 'detail'):
                    rec.error = exc.detail
                    rec.error_code = exc.status_code
                else:
                    rec.error = str(exc)
                logger.error("Task %s (%s) failed: %s\n%s", task_id, kind, exc, traceback.format_exc())
        finally:
            rec.finished_at = time.time()
            _save_task_to_db(rec)

    t = threading.Thread(target=_worker, daemon=True, name=f"task-{task_id[:8]}")
    t.start()

    logger.info("Submitted task %s kind=%s user=%s", task_id, kind, user_id)
    return task_id


def get_status(task_id: str, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Return task status dict, or None if not found.
    If user_id is provided, only return if it matches the task owner.
    """
    rec = _get_or_load_task_record(task_id)
    if rec is None:
        return None
    if user_id is not None and rec.user_id is not None and rec.user_id != user_id:
        return None

    if rec.status in {"pending", "running"}:
        now_ts = time.time()
        created_at = float(rec.created_at or now_ts)
        if (now_ts - created_at) > _RUNNING_TASK_MAX_AGE_SECONDS:
            rec.status = "failed"
            rec.error_code = 504
            rec.error = f"Task timed out after {_RUNNING_TASK_MAX_AGE_SECONDS}s"
            rec.finished_at = now_ts
            _save_task_to_db(rec)
            logger.warning(
                "Task %s timed out and was marked failed | kind=%s user=%s age_s=%s limit_s=%s",
                rec.task_id,
                rec.kind,
                rec.user_id,
                int(max(0, now_ts - created_at)),
                _RUNNING_TASK_MAX_AGE_SECONDS,
            )

    info: Dict[str, Any] = {
        "task_id": rec.task_id,
        "status": rec.status,
        "kind": rec.kind,
    }
    if rec.status == "completed":
        info["result"] = rec.result
    elif rec.status == "canceled":
        info["error"] = rec.error or "Task canceled by user"
        info["error_code"] = rec.error_code or 499
    elif rec.status == "failed":
        info["error"] = rec.error
        if rec.error_code:
            info["error_code"] = rec.error_code
    return info


def cancel(task_id: str, user_id: Optional[int] = None, reason: str = "Task canceled by user") -> Optional[Dict[str, Any]]:
    """
    Mark a task as canceled. This is cooperative cancellation: running work may
    still finish in the background, but polling immediately returns canceled.
    """
    rec = _get_or_load_task_record(task_id)
    if rec is None:
        return None
    if user_id is not None and rec.user_id is not None and rec.user_id != user_id:
        return None

    if rec.status in {"completed", "failed", "canceled"}:
        return get_status(task_id, user_id=user_id)

    rec.cancel_requested = True
    rec.cancel_reason = str(reason or "Task canceled by user").strip() or "Task canceled by user"
    rec.status = "canceled"
    rec.error = rec.cancel_reason
    rec.error_code = 499
    rec.finished_at = time.time()
    _save_task_to_db(rec)
    return get_status(task_id, user_id=user_id)


# ---------------------------------------------------------------------------
# High-level helper: submit an async FastAPI endpoint to run in background
# ---------------------------------------------------------------------------

def _serialize_result(result: Any) -> Any:
    """Make endpoint return values JSON-serializable for task storage."""
    if result is None or isinstance(result, (dict, list, str, int, float, bool)):
        return result
    # FastAPI JSONResponse — extract body
    if hasattr(result, 'body'):
        import json as _json
        try:
            return _json.loads(result.body)
        except Exception:
            pass
    # Pydantic model
    if hasattr(result, 'dict') and callable(result.dict):
        return result.dict()
    # SQLAlchemy ORM model
    if hasattr(result, '__table__'):
        from fastapi.encoders import jsonable_encoder
        return jsonable_encoder(result)
    return result


def submit_async_endpoint(fn, *, user_id: int, kind: str, **fn_kwargs) -> str:
    """
    Submit an *async def* FastAPI endpoint function to run in a background
    thread.  A fresh DB session and User are created inside the thread;
    ``db`` and ``current_user`` must NOT be included in *fn_kwargs*.

    Returns a task_id for polling via ``get_status()``.
    """

    def _work():
        from app.db.session import SessionLocal
        from app.models.all_models import User

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    fn(db=db, current_user=user, **fn_kwargs)
                )
                return _serialize_result(result)
            finally:
                loop.close()
        finally:
            db.close()

    return submit(_work, user_id=user_id, kind=kind)
