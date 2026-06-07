import json
import logging
import os
import asyncio
import contextlib

QUEUE_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "queue_config.json")
def _load_queue_config():
    config = {"queue_threads": 10, "callback_threads": 10}
    if os.path.exists(QUEUE_CONFIG_FILE):
        try:
            with open(QUEUE_CONFIG_FILE, "r") as f:
                d = json.load(f)
                if isinstance(d, dict):
                    config.update(d)
        except Exception:
            pass
    return config

_q_conf = _load_queue_config()

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
_QUEUE_ASYNC_STOP_EVENT = None  # asyncio.Event initialized when needed
_QUEUE_POLL_SECONDS = max(0.25, float(os.getenv("GENERATION_QUEUE_POLL_SECONDS", "1.0") or 1.0))
_QUEUE_RECLAIM_SECONDS = max(900.0, float(os.getenv("GENERATION_QUEUE_RECLAIM_SECONDS", "900") or 900.0))
_POOL_CAPACITY = max(1, int(DB_POOL_CAPACITY_EFFECTIVE or 0))
_WEB_CONCURRENCY = max(1, int(os.getenv("WEB_CONCURRENCY", "1") or 1))
_PER_PROCESS_POOL_BUDGET = max(1, _POOL_CAPACITY // _WEB_CONCURRENCY)
_DEFAULT_WORKER_THREADS = min(8, max(2, int(DB_POOL_SIZE_EFFECTIVE or 2)))
_REQUESTED_WORKER_THREADS = max(
    1,
    int(_q_conf.get("queue_threads", _DEFAULT_WORKER_THREADS) or _DEFAULT_WORKER_THREADS),
)
# Keep the default queue target at 20 for dedicated worker processes, while
# still degrading safely when the DB pool is smaller than that target.
_WORKER_THREAD_CAP = max(1, min(20, _PER_PROCESS_POOL_BUDGET // 2))
_QUEUE_WORKER_THREADS = max(1, min(_REQUESTED_WORKER_THREADS, _WORKER_THREAD_CAP))
_QUEUE_ADVISORY_LOCK_ID = int(os.getenv("GENERATION_QUEUE_ADVISORY_LOCK_ID", "918240157") or 918240157)
_QUEUE_LEADER_CONN = None

if _REQUESTED_WORKER_THREADS > _QUEUE_WORKER_THREADS:
    logger.warning(
        "generation queue workers capped to avoid DB pool starvation | requested=%s capped=%s pool_capacity=%s web_concurrency=%s per_process_pool_budget=%s",
        _REQUESTED_WORKER_THREADS,
        _QUEUE_WORKER_THREADS,
        _POOL_CAPACITY,
        _WEB_CONCURRENCY,
        _PER_PROCESS_POOL_BUDGET,
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
            "generation queue leader lock probe failed; skipping worker startup until next probe | err=%s",
            exc,
        )
        return False
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
            
            # Auto-migrate missing columns for older schemas
            columns = [
                ("kind", "TEXT NOT NULL DEFAULT 'video'"),
                ("user_id", "INTEGER NOT NULL DEFAULT 0"),
                ("payload_json", "TEXT NOT NULL DEFAULT '{}'"),
                ("status", "TEXT NOT NULL DEFAULT 'queued'"),
                ("attempt_count", "INTEGER NOT NULL DEFAULT 0"),
                ("worker_id", "TEXT NULL"),
                ("created_at", "REAL NOT NULL DEFAULT 0"),
                ("started_at", "REAL NULL"),
                ("finished_at", "REAL NULL"),
                ("last_heartbeat", "REAL NULL"),
                ("error", "TEXT NULL")
            ]
            for col_name, col_type in columns:
                try:
                    conn.execute(text(f"ALTER TABLE generation_task_queue ADD COLUMN {col_name} {col_type}"))
                except Exception:
                    pass
        _QUEUE_TABLE_READY = True


def list_generation_tasks(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    _ensure_queue_table_ready()
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT job_id, kind, user_id, status, attempt_count, worker_id, created_at, started_at, finished_at, last_heartbeat, error, payload_json
                FROM generation_task_queue
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"limit": limit, "offset": offset},
        ).mappings().all()
        import json
        res = []
        for row in rows:
            r = {k: row.get(k) for k in row.keys()}
            if r.get('payload_json'):
                try:
                    r['payload'] = json.loads(r['payload_json'])
                except:
                    r['payload'] = None
            res.append(r)
        return res
    finally:
        db.close()


def get_generation_queue_runtime_stats() -> Dict[str, Any]:
    _ensure_queue_table_ready()
    now = time.time()
    stale_heartbeat_cutoff = now - max(60.0, _QUEUE_RECLAIM_SECONDS / 2.0)
    live_cfg = _load_queue_config()
    configured_threads = max(
        1,
        int((live_cfg or {}).get("queue_threads", _DEFAULT_WORKER_THREADS) or _DEFAULT_WORKER_THREADS),
    )
    db = SessionLocal()
    try:
        status_rows = db.execute(
            text(
                """
                SELECT status, COUNT(*) AS cnt
                FROM generation_task_queue
                GROUP BY status
                """
            )
        ).mappings().all()
        kind_rows = db.execute(
            text(
                """
                SELECT kind, COUNT(*) AS cnt
                FROM generation_task_queue
                GROUP BY kind
                """
            )
        ).mappings().all()
        running_rows = db.execute(
            text(
                """
                SELECT worker_id, started_at, last_heartbeat
                FROM generation_task_queue
                WHERE status = 'running'
                """
            )
        ).mappings().all()
        queued_oldest_row = db.execute(
            text(
                """
                SELECT MIN(created_at) AS oldest_created_at
                FROM generation_task_queue
                WHERE status = 'queued'
                """
            )
        ).mappings().first()
        recent_completed_row = db.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM generation_task_queue
                WHERE finished_at IS NOT NULL
                  AND finished_at >= :cutoff
                  AND status IN ('completed', 'failed', 'canceled')
                """
            ),
            {"cutoff": now - 3600.0},
        ).mappings().first()

        status_counts: Dict[str, int] = {}
        for row in status_rows:
            key = str(row.get("status") or "unknown").strip().lower() or "unknown"
            status_counts[key] = int(row.get("cnt") or 0)

        kind_counts: Dict[str, int] = {}
        for row in kind_rows:
            key = str(row.get("kind") or "unknown").strip().lower() or "unknown"
            kind_counts[key] = int(row.get("cnt") or 0)

        active_workers = set()
        stale_running = 0
        oldest_running_seconds = 0
        for row in running_rows:
            worker_id = str(row.get("worker_id") or "").strip()
            if worker_id:
                active_workers.add(worker_id)
            last_heartbeat = float(row.get("last_heartbeat") or 0.0)
            started_at = float(row.get("started_at") or 0.0)
            if last_heartbeat and last_heartbeat < stale_heartbeat_cutoff:
                stale_running += 1
            if started_at:
                oldest_running_seconds = max(oldest_running_seconds, int(max(0.0, now - started_at)))

        queued_oldest_created_at = float((queued_oldest_row or {}).get("oldest_created_at") or 0.0)
        queued_oldest_wait_seconds = int(max(0.0, now - queued_oldest_created_at)) if queued_oldest_created_at else 0
        running_count = int(status_counts.get("running", 0))
        queued_count = int(status_counts.get("queued", 0))
        worker_slots_total = int(_QUEUE_WORKER_THREADS)
        worker_slots_in_use = max(0, min(worker_slots_total, running_count))
        worker_slots_available = max(0, worker_slots_total - worker_slots_in_use)

        return {
            "queue": {
                "status_counts": status_counts,
                "kind_counts": kind_counts,
                "active_count": int(queued_count + running_count),
                "running_count": running_count,
                "queued_count": queued_count,
                "worker_slots_total": worker_slots_total,
                "worker_slots_in_use": worker_slots_in_use,
                "worker_slots_available": worker_slots_available,
                "queued_oldest_wait_seconds": queued_oldest_wait_seconds,
                "finished_last_hour": int((recent_completed_row or {}).get("cnt") or 0),
            },
            "workers": {
                "configured_threads": int(configured_threads),
                "requested_threads": int(_REQUESTED_WORKER_THREADS),
                "effective_threads": int(_QUEUE_WORKER_THREADS),
                "thread_cap": int(_WORKER_THREAD_CAP),
                "restart_required_for_thread_change": bool(configured_threads != int(_REQUESTED_WORKER_THREADS)),
                "active_running_workers": len(active_workers),
                "slots_total": worker_slots_total,
                "slots_in_use": worker_slots_in_use,
                "slots_available": worker_slots_available,
                "stale_running_tasks": int(stale_running),
                "oldest_running_seconds": int(oldest_running_seconds),
                "queue_poll_seconds": float(_QUEUE_POLL_SECONDS),
                "queue_reclaim_seconds": float(_QUEUE_RECLAIM_SECONDS),
            },
        }
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


def mark_generation_task_status_external(
    job_id: str,
    *,
    status: str,
    error: Optional[str] = None,
    preserve_canceled: bool = True,
) -> bool:
    _ensure_queue_table_ready()
    now = time.time()
    normalized_status = str(status or "").strip().lower() or "running"
    terminal_statuses = {"completed", "failed", "canceled", "cancelled"}
    is_terminal = normalized_status in terminal_statuses
    where_sql = "WHERE job_id = :job_id"
    if preserve_canceled:
        where_sql += " AND status <> 'canceled'"

    db = SessionLocal()
    try:
        result = db.execute(
            text(
                """
                UPDATE generation_task_queue
                SET status = :status,
                    finished_at = :finished_at,
                    last_heartbeat = :last_heartbeat,
                    error = :error
                """
                + where_sql
            ),
            {
                "job_id": str(job_id),
                "status": normalized_status,
                "finished_at": now if is_terminal else None,
                "last_heartbeat": now,
                "error": str(error) if error else None,
            },
        )
        db.commit()
        return int(result.rowcount or 0) > 0
    finally:
        db.close()


def requeue_generation_task(job_id: str, *, reason: Optional[str] = None) -> bool:
    _ensure_queue_table_ready()
    db = SessionLocal()
    try:
        result = db.execute(
            text(
                """
                UPDATE generation_task_queue
                SET status = 'queued',
                    worker_id = NULL,
                    started_at = NULL,
                    finished_at = NULL,
                    last_heartbeat = NULL,
                    error = :error
                WHERE job_id = :job_id
                  AND status <> 'canceled'
                """
            ),
            {
                "job_id": str(job_id),
                "error": str(reason) if reason else None,
            },
        )
        db.commit()
        return int(result.rowcount or 0) > 0
    finally:
        db.close()


def get_generation_task_status(job_id: str) -> Optional[Dict[str, Any]]:
    _ensure_queue_table_ready()
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                SELECT job_id, kind, user_id, status, attempt_count, worker_id, created_at, started_at, finished_at, last_heartbeat, error, payload_json
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
                SELECT job_id, kind, user_id, payload_json, created_at
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
        created_at = row.get("created_at") or now
        is_expired = (now - created_at) > 3600.0

        result = db.execute(
            text(
                """
                UPDATE generation_task_queue
                SET status = :next_status,
                    worker_id = :worker_id,
                    started_at = COALESCE(started_at, :started_at),
                    last_heartbeat = :heartbeat,
                    finished_at = :finished_at,
                    error = :error,
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
                "next_status": 'failed' if is_expired else 'running',
                "finished_at": now if is_expired else None,
                "error": 'Task queued for over 60 minutes. Timed out.' if is_expired else None,
            },
        )
        db.commit()
        if (result.rowcount or 0) < 1:
            return None
        
        if is_expired:
            logger.warning("Claimed task %s but it was created > 30 mins ago. Marked as failed.", row["job_id"])
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


def _touch_task_heartbeat(job_id: str, worker_id: str) -> bool:
    _ensure_queue_table_ready()
    now = time.time()
    db = SessionLocal()
    try:
        result = db.execute(
            text(
                """
                UPDATE generation_task_queue
                SET last_heartbeat = :heartbeat
                WHERE job_id = :job_id
                  AND status = 'running'
                  AND worker_id = :worker_id
                """
            ),
            {
                "job_id": str(job_id),
                "worker_id": str(worker_id),
                "heartbeat": now,
            },
        )
        db.commit()
        return int(result.rowcount or 0) > 0
    finally:
        db.close()

_QUEUE_LAST_CLEANUP_TIME = 0.0
_QUEUE_LAST_TIMEOUT_SWEEP_TIME = 0.0

def _cleanup_old_tasks() -> None:
    global _QUEUE_LAST_CLEANUP_TIME, _QUEUE_LAST_TIMEOUT_SWEEP_TIME
    now = time.time()
    if now - _QUEUE_LAST_TIMEOUT_SWEEP_TIME < 60.0:
        return
    _QUEUE_LAST_TIMEOUT_SWEEP_TIME = now
    
    # We sweep for timeouts every minute, but full deletes only every hour.
    do_full_cleanup = False
    if now - _QUEUE_LAST_CLEANUP_TIME >= 3600.0:
        _QUEUE_LAST_CLEANUP_TIME = now
        do_full_cleanup = True
    cutoff = now - 86400.0  # 1 day cutoff
    timeout_cutoff = now - 3600.0 # 60 min timeout for running tasks
    db = SessionLocal()
    try:
        # Mark 30+ min long running tasks as failed
        r_timeout = db.execute(
            text(
                """
                UPDATE generation_task_queue 
                SET status = 'failed', 
                    error = 'Task running for over 60 minutes. Timed out.',
                    finished_at = :now
                WHERE status = 'running' 
                  AND COALESCE(started_at, created_at) < :timeout_cutoff
                """
            ),
            {"now": now, "timeout_cutoff": timeout_cutoff},
        )
        db.commit()
        if (r_timeout.rowcount or 0) > 0:
            logger.warning("generation queue sweep timed out %s running tasks (>60m)", r_timeout.rowcount)

        if do_full_cleanup:
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

async def _worker_loop_async(worker_name: str, processor: Callable[[str, str, int, Dict[str, Any]], Any]) -> None:
    logger.info("generation queue async worker started | worker=%s", worker_name)
    heartbeat_interval_seconds = max(15.0, min(60.0, _QUEUE_RECLAIM_SECONDS / 3.0))
    while True:
        task = None
        heartbeat_task = None
        heartbeat_stop = None
        try:
            if _QUEUE_ASYNC_STOP_EVENT and _QUEUE_ASYNC_STOP_EVENT.is_set():
                break
            if worker_name.endswith("-1"):
                await asyncio.to_thread(_cleanup_old_tasks)
            task = await asyncio.to_thread(_claim_next_task, worker_name)
            if not task:
                await asyncio.sleep(_QUEUE_POLL_SECONDS)
                continue

            async def _heartbeat_loop() -> None:
                while heartbeat_stop and not heartbeat_stop.is_set():
                    await asyncio.sleep(heartbeat_interval_seconds)
                    if heartbeat_stop.is_set():
                        break
                    await asyncio.to_thread(_touch_task_heartbeat, str(task.get("job_id") or ""), worker_name)

            heartbeat_stop = asyncio.Event()
            heartbeat_task = asyncio.create_task(_heartbeat_loop())

            processor_result: Any = None
            result = processor(task["kind"], task["job_id"], task["user_id"], task["payload"])
            try:
                if asyncio.iscoroutine(result) or isinstance(result, asyncio.Task):
                    processor_result = await asyncio.wait_for(result, timeout=3600.0)
                elif asyncio.isfuture(result):
                    processor_result = await asyncio.wait_for(result, timeout=3600.0)
                else:
                    processor_result = result
            except (asyncio.TimeoutError, TimeoutError):
                logger.warning("generation queue task timed out (exceeded 60 minutes) | job_id=%s", (task or {}).get("job_id"))
                job_id = str(task.get("job_id") or "")
                await asyncio.to_thread(_finish_task, job_id, status="failed", error="Task execution exceeded 60 minutes. Timed out.", only_if_running=True)
                continue
            defer_completion = bool(
                isinstance(processor_result, dict)
                and bool(processor_result.get("defer_completion"))
            )
            if defer_completion:
                await asyncio.to_thread(_touch_task_heartbeat, str(task.get("job_id") or ""), worker_name)
                continue
            finalized = await asyncio.to_thread(_finish_task, task["job_id"], status="completed", only_if_running=True)
            if not finalized:
                latest = await asyncio.to_thread(get_generation_task_status, str(task.get("job_id") or "")) or {}
                logger.info(
                    "generation queue completion skipped; job_id=%s kind=%s current_status=%s",
                    (task or {}).get("job_id"),
                    (task or {}).get("kind"),
                    latest.get("status"),
                )
        except asyncio.CancelledError:
            if task:
                job_id = str(task.get("job_id") or "")
                await asyncio.to_thread(_finish_task, job_id, status="canceled", error="cancelled", only_if_running=True)
            break
        except Exception as exc:
            logger.exception("generation queue task failed | job_id=%s", (task or {}).get("job_id"))
            if task:
                job_id = str(task.get("job_id") or "")
                latest = await asyncio.to_thread(get_generation_task_status, job_id) or {}
                if str(latest.get("status") or "").strip().lower() != "canceled":
                    await asyncio.to_thread(_finish_task, job_id, status="failed", error=str(exc), only_if_running=True)
            continue
        finally:
            if heartbeat_stop is not None:
                heartbeat_stop.set()
            if heartbeat_task is not None:
                heartbeat_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat_task


async def _async_event_loop(processor: Callable[[str, str, int, Dict[str, Any]], Any]) -> None:
    global _QUEUE_ASYNC_STOP_EVENT
    _QUEUE_ASYNC_STOP_EVENT = asyncio.Event()
    logger.info("generation queue async event loop started with %s concurrent workers", _QUEUE_WORKER_THREADS)
    try:
        tasks = []
        for index in range(_QUEUE_WORKER_THREADS):
            worker_name = f"generation-queue-{index + 1}"
            tasks.append(asyncio.create_task(_worker_loop_async(worker_name, processor)))
        if tasks:
            await asyncio.gather(*tasks)
    except Exception as exc:
        logger.exception("generation queue async event loop failed")
    finally:
        logger.info("generation queue async event loop stopped")


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
            processor_result = processor(task["kind"], task["job_id"], task["user_id"], task["payload"])
            defer_completion = bool(
                isinstance(processor_result, dict)
                and bool(processor_result.get("defer_completion"))
            )
            if defer_completion:
                _touch_task_heartbeat(str(task.get("job_id") or ""), worker_name)
                continue
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


def _worker_thread_main(processor: Callable[[str, str, int, Dict[str, Any]], None]) -> None:
    """Continuously tries to acquire leader lock and run generation tasks."""
    while not _QUEUE_STOP_EVENT.is_set():
        if not _try_acquire_queue_leader_lock():
            _QUEUE_STOP_EVENT.wait(15.0)
            continue
            
        try:
            logger.info("generation queue worker acquired leader lock, starting event loop...")
            _ensure_queue_table_ready()
            asyncio.run(_async_event_loop(processor))
        except Exception as exc:
            logger.exception("generation queue event loop crashed | err=%s", exc)
            _QUEUE_STOP_EVENT.wait(15.0)
        finally:
            if not _QUEUE_STOP_EVENT.is_set():
                logger.warning("generation queue event loop exited. Re-checking lock...")
                _QUEUE_STOP_EVENT.wait(5.0)

def start_generation_task_worker(processor: Callable[[str, str, int, Dict[str, Any]], None]) -> None:
    """Start generation task workers using async event loop."""
    global _QUEUE_STARTED
    if _QUEUE_STARTED:
        return
    with _QUEUE_START_LOCK:
        if _QUEUE_STARTED:
            return
            
        thread = threading.Thread(
            target=_worker_thread_main,
            args=(processor,),
            daemon=True,
            name="generation-queue-event-loop",
        )
        thread.start()
        _QUEUE_STARTED = True
        logger.info(
            "generation queue async event loop thread started, waiting for %s concurrent workers to become leader",
            _QUEUE_WORKER_THREADS,
        )
