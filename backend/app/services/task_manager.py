"""
In-memory async task manager for long-running LLM operations.

Endpoints submit work via `submit()`, which runs the callable in a background
thread and returns a task_id immediately.  The frontend then polls
`GET /tasks/{task_id}` until status is "completed" or "failed".

Completed results are kept for a limited TTL so memory doesn't grow unbounded.
"""

import asyncio
import logging
import threading
import time
import traceback
import uuid
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# How long (seconds) completed/failed results stay in memory before eviction.
_RESULT_TTL = 600  # 10 minutes

# Global task store  {task_id: _TaskRecord}
_tasks: Dict[str, "_TaskRecord"] = {}
_lock = threading.Lock()


class _TaskRecord:
    __slots__ = (
        "task_id", "status", "result", "error", "error_code", "created_at",
        "finished_at", "user_id", "kind",
    )

    def __init__(self, task_id: str, user_id: Optional[int], kind: str):
        self.task_id = task_id
        self.status = "pending"   # pending | running | completed | failed
        self.result: Any = None
        self.error: Optional[str] = None
        self.error_code: Optional[int] = None
        self.created_at = time.time()
        self.finished_at: Optional[float] = None
        self.user_id = user_id
        self.kind = kind


def _evict_stale():
    """Remove completed/failed tasks older than TTL.  Called under _lock."""
    now = time.time()
    stale = [
        tid for tid, rec in _tasks.items()
        if rec.finished_at and (now - rec.finished_at) > _RESULT_TTL
    ]
    for tid in stale:
        del _tasks[tid]


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

    def _worker():
        rec.status = "running"
        try:
            rec.result = fn()
            rec.status = "completed"
        except Exception as exc:
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

    t = threading.Thread(target=_worker, daemon=True, name=f"task-{task_id[:8]}")
    t.start()

    logger.info("Submitted task %s kind=%s user=%s", task_id, kind, user_id)
    return task_id


def get_status(task_id: str, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Return task status dict, or None if not found.
    If user_id is provided, only return if it matches the task owner.
    """
    with _lock:
        rec = _tasks.get(task_id)
    if rec is None:
        return None
    if user_id is not None and rec.user_id is not None and rec.user_id != user_id:
        return None

    info: Dict[str, Any] = {
        "task_id": rec.task_id,
        "status": rec.status,
        "kind": rec.kind,
    }
    if rec.status == "completed":
        info["result"] = rec.result
    elif rec.status == "failed":
        info["error"] = rec.error
        if rec.error_code:
            info["error_code"] = rec.error_code
    return info


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
