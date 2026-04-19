import json
import logging
import os
import asyncio
import threading
import time
import atexit
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import text

from app.core.config import settings
from app.db.session import (
    DB_POOL_CAPACITY_EFFECTIVE,
    DB_POOL_SIZE_EFFECTIVE,
    SessionLocal,
    engine,
)

logger = logging.getLogger(__name__)

_QUEUE_TABLE_READY = False
_JOB_STATE_TABLE_READY = False
_QUEUE_TABLE_LOCK = threading.Lock()
_JOB_STATE_TABLE_LOCK = threading.Lock()
_QUEUE_START_LOCK = threading.Lock()
_QUEUE_STARTED = False
_QUEUE_STOP_EVENT = threading.Event()
_QUEUE_POLL_SECONDS = max(0.25, float(os.getenv("GENERATION_QUEUE_POLL_SECONDS", "1.0") or 1.0))
_QUEUE_RECLAIM_SECONDS = max(900.0, float(os.getenv("GENERATION_QUEUE_RECLAIM_SECONDS", "900") or 900.0))
_POOL_CAPACITY = max(1, int(DB_POOL_CAPACITY_EFFECTIVE or 0))
_DEFAULT_WORKER_THREADS = min(8, max(2, int(DB_POOL_SIZE_EFFECTIVE or 2)))
_REQUESTED_WORKER_THREADS = max(1, int(os.getenv("GENERATION_QUEUE_WORKER_THREADS", str(_DEFAULT_WORKER_THREADS)) or _DEFAULT_WORKER_THREADS))
# Leave headroom for API requests and auth flows by capping queue workers.
_WORKER_THREAD_CAP = max(1, _POOL_CAPACITY // 2)
_QUEUE_WORKER_THREADS = max(1, min(_REQUESTED_WORKER_THREADS, _WORKER_THREAD_CAP))
_QUEUE_ADVISORY_LOCK_ID = int(os.getenv("GENERATION_QUEUE_ADVISORY_LOCK_ID", "918240157") or 918240157)
_QUEUE_LEADER_CONN = None

if _REQUESTED_WORKER_THREADS > _QUEUE_WORKER_THREADS:
    logger.warning(
        "generation queue workers capped to avoid DB pool starvation | requested=%s capped=%s pool_capacity=%s",
        _REQUESTED_WORKER_THREADS,
        _QUEUE_WORKER_THREADS,
        _POOL_CAPACITY,
    )


def _release_queue_leader_lock() -> None:
    global _QUEUE_LEADER_CONN
    conn = _QUEUE_LEADER_CONN
    _QUEUE_LEADER_CONN = None
    if conn is None:
        return
    try:
        conn.close()
    except Exception:
        pass


atexit.register(_release_queue_leader_lock)


def _is_postgres_engine() -> bool:
    try:
        return str(engine.url.get_backend_name() or "").strip().lower().startswith("postgres")
    except Exception:
        return False


def _try_acquire_queue_leader_lock() -> bool:
    global _QUEUE_LEADER_CONN
    if not _is_postgres_engine():
        return True
    if _QUEUE_LEADER_CONN is not None:
        return True

    def _open_dedicated_lock_connection():
        # Keep leader-lock connection outside SQLAlchemy pool so it does not
        # permanently consume one pooled API connection.
        import psycopg2

        dsn = str(settings.DATABASE_URL or "").strip()
        if dsn.startswith("postgres://"):
            dsn = dsn.replace("postgres://", "postgresql://", 1)
        if dsn.startswith("postgresql+psycopg2://"):
            dsn = dsn.replace("postgresql+psycopg2://", "postgresql://", 1)

        conn = psycopg2.connect(
            dsn,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5,
        )
        conn.autocommit = True
        return conn

    conn = None
    acquired = False
    try:
        conn = _open_dedicated_lock_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", (_QUEUE_ADVISORY_LOCK_ID,))
            row = cursor.fetchone()
            acquired = bool(row and row[0])
        finally:
            try:
                cursor.close()
            except Exception:
                pass
        if acquired:
            _QUEUE_LEADER_CONN = conn
            conn = None
            return True
        return False
    except Exception as exc:
        logger.warning(
            "generation queue leader lock probe failed; starting without cross-process guard | err=%s",
            exc,
        )
        return True
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _ensure_job_state_table_ready() -> None:
    global _JOB_STATE_TABLE_READY
    if _JOB_STATE_TABLE_READY:
        return
    with _JOB_STATE_TABLE_LOCK:
        if _JOB_STATE_TABLE_READY:
            return
        ddl = """
        CREATE TABLE IF NOT EXISTS generation_job_state (
            kind TEXT NOT NULL,
            job_id TEXT NOT NULL,
            user_id INTEGER NULL,
            status TEXT NULL,
            provider_callback_ticket TEXT NULL,
            payload_json TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (kind, job_id)
        )
        """
        status_index_ddl = "CREATE INDEX IF NOT EXISTS idx_generation_job_state_kind_status_updated_at ON generation_job_state(kind, status, updated_at)"
        callback_index_ddl = "CREATE INDEX IF NOT EXISTS idx_generation_job_state_kind_callback_ticket ON generation_job_state(kind, provider_callback_ticket)"
        with engine.begin() as conn:
            conn.execute(text(ddl))
            conn.execute(text(status_index_ddl))
            conn.execute(text(callback_index_ddl))
        _JOB_STATE_TABLE_READY = True


def upsert_generation_job_state(*, kind: str, job_id: str, payload: Dict[str, Any]) -> None:
    _ensure_job_state_table_ready()
    stable_payload = dict(payload or {})
    stable_payload["job_id"] = str(job_id)
    now = time.time()
    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                INSERT INTO generation_job_state (
                    kind, job_id, user_id, status, provider_callback_ticket, payload_json, updated_at
                ) VALUES (
                    :kind, :job_id, :user_id, :status, :provider_callback_ticket, :payload_json, :updated_at
                )
                ON CONFLICT(kind, job_id) DO UPDATE SET
                    user_id = excluded.user_id,
                    status = excluded.status,
                    provider_callback_ticket = excluded.provider_callback_ticket,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """
            ),
            {
                "kind": str(kind),
                "job_id": str(job_id),
                "user_id": stable_payload.get("user_id"),
                "status": str(stable_payload.get("status") or "").strip().lower() or None,
                "provider_callback_ticket": str(
                    stable_payload.get("provider_callback_ticket")
                    or stable_payload.get("callback_ticket")
                    or ""
                ).strip() or None,
                "payload_json": json.dumps(stable_payload, ensure_ascii=False, default=str),
                "updated_at": now,
            },
        )
        db.commit()
    finally:
        db.close()


def get_generation_job_state(*, kind: str, job_id: str) -> Optional[Dict[str, Any]]:
    _ensure_job_state_table_ready()
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                SELECT payload_json
                FROM generation_job_state
                WHERE kind = :kind AND job_id = :job_id
                """
            ),
            {
                "kind": str(kind),
                "job_id": str(job_id),
            },
        ).mappings().first()
        if not row:
            return None
        try:
            payload = json.loads(str(row.get("payload_json") or "{}"))
        except Exception:
            payload = None
        if not isinstance(payload, dict):
            return None
        payload["job_id"] = payload.get("job_id") or str(job_id)
        return payload
    finally:
        db.close()


def find_generation_job_states_by_callback_ticket(*, kind: str, callback_ticket: str, limit: int = 20) -> List[Dict[str, Any]]:
    stable_ticket = str(callback_ticket or "").strip()
    if not stable_ticket:
        return []
    _ensure_job_state_table_ready()
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT payload_json
                FROM generation_job_state
                WHERE kind = :kind AND provider_callback_ticket = :provider_callback_ticket
                ORDER BY updated_at DESC
                LIMIT :limit
                """
            ),
            {
                "kind": str(kind),
                "provider_callback_ticket": stable_ticket,
                "limit": int(max(1, limit)),
            },
        ).mappings().all()
        matches: List[Dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(str(row.get("payload_json") or "{}"))
            except Exception:
                payload = None
            if isinstance(payload, dict):
                matches.append(payload)
        return matches
    finally:
        db.close()


def delete_generation_job_state(*, kind: str, job_id: str) -> None:
    _ensure_job_state_table_ready()
    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                DELETE FROM generation_job_state
                WHERE kind = :kind AND job_id = :job_id
                """
            ),
            {
                "kind": str(kind),
                "job_id": str(job_id),
            },
        )
        db.commit()
    finally:
        db.close()


def _ensure_queue_table_ready() -> None:
    global _QUEUE_TABLE_READY
    if _QUEUE_TABLE_READY:
        return
    with _QUEUE_TABLE_LOCK:
        if _QUEUE_TABLE_READY:
            return
        ddl = """
        CREATE TABLE IF NOT EXISTS generation_task_queue (
            job_id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            worker_id TEXT NULL,
            created_at REAL NOT NULL,
            started_at REAL NULL,
            finished_at REAL NULL,
            last_heartbeat REAL NULL,
            error TEXT NULL
        )
        """
        index_ddl = "CREATE INDEX IF NOT EXISTS idx_generation_task_queue_status_created_at ON generation_task_queue(status, created_at)"
        with engine.begin() as conn:
            conn.execute(text(ddl))
            conn.execute(text(index_ddl))
        _QUEUE_TABLE_READY = True


def list_generation_tasks(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    _ensure_queue_table_ready()
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT job_id, kind, user_id, status, attempt_count, worker_id, created_at, started_at, finished_at, last_heartbeat, error
                FROM generation_task_queue
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"limit": limit, "offset": offset},
        ).mappings().all()
        return [{k: row.get(k) for k in row.keys()} for row in rows]
    finally:
        db.close()


def enqueue_generation_task(*, job_id: str, kind: str, user_id: int, payload: Dict[str, Any]) -> str:
    _ensure_queue_table_ready()
    now = time.time()
    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                INSERT INTO generation_task_queue (
                    job_id, kind, user_id, payload_json, status, attempt_count, worker_id, created_at, started_at, finished_at, last_heartbeat, error
                ) VALUES (
                    :job_id, :kind, :user_id, :payload_json, 'queued', 0, NULL, :created_at, NULL, NULL, NULL, NULL
                )
                ON CONFLICT(job_id) DO NOTHING
                """
            ),
            {
                "job_id": str(job_id),
                "kind": str(kind),
                "user_id": int(user_id),
                "payload_json": json.dumps(payload or {}, ensure_ascii=False, default=str),
                "created_at": now,
            },
        )
        db.commit()
    finally:
        db.close()
    return str(job_id)


def get_generation_task_status(job_id: str) -> Optional[Dict[str, Any]]:
    _ensure_queue_table_ready()
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                SELECT job_id, kind, user_id, status, attempt_count, worker_id, created_at, started_at, finished_at, last_heartbeat, error
                FROM generation_task_queue
                WHERE job_id = :job_id
                """
            ),
            {"job_id": str(job_id)},
        ).mappings().first()
        if not row:
            return None
        return {k: row.get(k) for k in row.keys()}
    finally:
        db.close()


def cancel_generation_task(job_id: str, *, reason: str = "Task canceled by user") -> Optional[Dict[str, Any]]:
    _ensure_queue_table_ready()
    now = time.time()
    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                UPDATE generation_task_queue
                SET status = 'canceled', finished_at = :finished_at, error = :error
                WHERE job_id = :job_id AND status IN ('queued', 'running')
                """
            ),
            {
                "job_id": str(job_id),
                "finished_at": now,
                "error": str(reason or "Task canceled by user"),
            },
        )
        db.commit()
    finally:
        db.close()
    return get_generation_task_status(job_id)


def cancel_generation_tasks(*, kind: Optional[str] = None, user_id: Optional[int] = None, reason: str = "Task canceled by stop-all") -> int:
    """Bulk-cancel active generation queue tasks and return affected row count."""
    _ensure_queue_table_ready()
    now = time.time()

    clauses = ["status IN ('queued', 'running')"]
    params: Dict[str, Any] = {
        "finished_at": now,
        "error": str(reason or "Task canceled by stop-all"),
    }
    if kind:
        clauses.append("kind = :kind")
        params["kind"] = str(kind)
    if user_id is not None:
        clauses.append("user_id = :user_id")
        params["user_id"] = int(user_id)

    where_sql = " AND ".join(clauses)
    db = SessionLocal()
    try:
        result = db.execute(
            text(
                f"""
                UPDATE generation_task_queue
                SET status = 'canceled',
                    finished_at = :finished_at,
                    error = :error
                WHERE {where_sql}
                """
            ),
            params,
        )
        db.commit()
        return int(result.rowcount or 0)
    finally:
        db.close()


def _claim_next_task(worker_id: str) -> Optional[Dict[str, Any]]:
    _ensure_queue_table_ready()
    cutoff = time.time() - _QUEUE_RECLAIM_SECONDS
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                SELECT job_id, kind, user_id, payload_json
                FROM generation_task_queue
                WHERE status = 'queued'
                   OR (status = 'running' AND COALESCE(last_heartbeat, 0) < :cutoff)
                ORDER BY created_at ASC
                LIMIT 1
                """
            ),
            {"cutoff": cutoff},
        ).mappings().first()
        if not row:
            return None

        now = time.time()
        result = db.execute(
            text(
                """
                UPDATE generation_task_queue
                SET status = 'running',
                    worker_id = :worker_id,
                    started_at = COALESCE(started_at, :started_at),
                    last_heartbeat = :heartbeat,
                    finished_at = NULL,
                    error = NULL,
                    attempt_count = attempt_count + 1
                WHERE job_id = :job_id
                  AND (status = 'queued' OR (status = 'running' AND COALESCE(last_heartbeat, 0) < :cutoff))
                """
            ),
            {
                "job_id": str(row["job_id"]),
                "worker_id": worker_id,
                "started_at": now,
                "heartbeat": now,
                "cutoff": cutoff,
            },
        )
        db.commit()
        if (result.rowcount or 0) < 1:
            return None
        try:
            payload = json.loads(str(row["payload_json"] or "{}"))
        except Exception:
            payload = {}
        return {
            "job_id": str(row["job_id"]),
            "kind": str(row["kind"]),
            "user_id": int(row["user_id"]),
            "payload": payload if isinstance(payload, dict) else {},
        }
    finally:
        db.close()


def _finish_task(job_id: str, *, status: str, error: Optional[str] = None, only_if_running: bool = False) -> bool:
    _ensure_queue_table_ready()
    now = time.time()
    db = SessionLocal()
    try:
        where_clause = "WHERE job_id = :job_id"
        if only_if_running:
            where_clause += " AND status = 'running'"

        result = db.execute(
            text(
                """
                UPDATE generation_task_queue
                SET status = :status,
                    finished_at = :finished_at,
                    last_heartbeat = :last_heartbeat,
                    error = :error
                """
                + where_clause +
                """
                """
            ),
            {
                "job_id": str(job_id),
                "status": str(status),
                "finished_at": now,
                "last_heartbeat": now,
                "error": str(error) if error else None,
            },
        )
        db.commit()
        return int(result.rowcount or 0) > 0
    finally:
        db.close()

_QUEUE_LAST_CLEANUP_TIME = 0.0

def _cleanup_old_tasks() -> None:
    global _QUEUE_LAST_CLEANUP_TIME
    now = time.time()
    if now - _QUEUE_LAST_CLEANUP_TIME < 3600.0:
        return
    _QUEUE_LAST_CLEANUP_TIME = now
    cutoff = now - 86400.0  # 1 day cutoff
    db = SessionLocal()
    try:
        result = db.execute(
            text(
                "DELETE FROM generation_task_queue WHERE status IN ('completed', 'failed', 'canceled') AND created_at < :cutoff"
            ),
            {"cutoff": cutoff},
        )
        db.commit()
        if (result.rowcount or 0) > 0:
            logger.info("generation queue cleanup deleted %s old tasks", result.rowcount)
    except Exception as exc:
        logger.warning("generation queue cleanup failed: %s", exc)
    finally:
        db.close()

def _worker_loop(worker_name: str, processor: Callable[[str, str, int, Dict[str, Any]], None]) -> None:
    logger.info("generation queue worker started | worker=%s poll=%ss reclaim=%ss", worker_name, _QUEUE_POLL_SECONDS, _QUEUE_RECLAIM_SECONDS)
    while not _QUEUE_STOP_EVENT.is_set():
        task = None
        try:
            if worker_name.endswith("-1"):  # Only the first worker tries to clean up
                _cleanup_old_tasks()
            task = _claim_next_task(worker_name)
            if not task:
                _QUEUE_STOP_EVENT.wait(_QUEUE_POLL_SECONDS)
                continue
            processor(task["kind"], task["job_id"], task["user_id"], task["payload"])
            finalized = _finish_task(task["job_id"], status="completed", only_if_running=True)
            if not finalized:
                latest = get_generation_task_status(str(task.get("job_id") or "")) or {}
                logger.info(
                    "generation queue completion skipped; task state changed externally | worker=%s job_id=%s kind=%s current_status=%s",
                    worker_name,
                    (task or {}).get("job_id"),
                    (task or {}).get("kind"),
                    latest.get("status"),
                )
        except Exception as exc:
            logger.exception("generation queue task failed | worker=%s job_id=%s kind=%s", worker_name, (task or {}).get("job_id"), (task or {}).get("kind"))
            if task:
                job_id = str(task.get("job_id") or "")
                if isinstance(exc, asyncio.CancelledError):
                    _finish_task(job_id, status="canceled", error="Task canceled by user", only_if_running=True)
                    continue
                latest = get_generation_task_status(job_id) or {}
                latest_status = str(latest.get("status") or "").strip().lower()
                if latest_status == "canceled":
                    logger.info(
                        "generation queue failure ignored because task already canceled | worker=%s job_id=%s kind=%s",
                        worker_name,
                        job_id,
                        (task or {}).get("kind"),
                    )
                    continue
                _finish_task(job_id, status="failed", error=str(exc), only_if_running=True)


def start_generation_task_worker(processor: Callable[[str, str, int, Dict[str, Any]], None]) -> None:
    global _QUEUE_STARTED
    if _QUEUE_STARTED:
        return
    with _QUEUE_START_LOCK:
        if _QUEUE_STARTED:
            return
        if not _try_acquire_queue_leader_lock():
            logger.info(
                "generation queue worker startup skipped in this process; advisory lock %s is held by another process",
                _QUEUE_ADVISORY_LOCK_ID,
            )
            return
        _ensure_queue_table_ready()
        for index in range(_QUEUE_WORKER_THREADS):
            worker_name = f"generation-queue-{index + 1}"
            thread = threading.Thread(
                target=_worker_loop,
                args=(worker_name, processor),
                daemon=True,
                name=worker_name,
            )
            thread.start()
        _QUEUE_STARTED = True
