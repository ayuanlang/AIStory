import logging
import os
import asyncio
import contextlib
import json
import socket

from app.core.queue_config import DEFAULT_QUEUE_CONFIG, load_queue_config

import threading
import time
import atexit
import tempfile
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
_LEADER_HEARTBEAT_TABLE_READY = False
_QUEUE_TABLE_LOCK = threading.Lock()
_JOB_STATE_TABLE_LOCK = threading.Lock()
_LEADER_HEARTBEAT_TABLE_LOCK = threading.Lock()
_QUEUE_START_LOCK = threading.Lock()
_QUEUE_STARTED = False
_ACTIVE_PROCESSOR: Optional[Callable[[str, str, int, Dict[str, Any]], Any]] = None
_QUEUE_STOP_EVENT = threading.Event()
_QUEUE_ASYNC_STOP_EVENT = None  # asyncio.Event initialized when needed
_QUEUE_POLL_SECONDS = max(0.25, float(os.getenv("GENERATION_QUEUE_POLL_SECONDS", "1.0") or 1.0))
_QUEUE_RECLAIM_SECONDS = max(900.0, float(os.getenv("GENERATION_QUEUE_RECLAIM_SECONDS", "900") or 900.0))
_LEADER_HEARTBEAT_STALE_SECONDS = max(
    30.0,
    float(os.getenv("GENERATION_QUEUE_LEADER_HEARTBEAT_STALE_SECONDS", "45") or 45.0),
)
_LEADER_HEARTBEAT_PULSE_SECONDS = max(
    5.0,
    min(30.0, float(os.getenv("GENERATION_QUEUE_LEADER_HEARTBEAT_PULSE_SECONDS", "10") or 10.0)),
)
_QUEUE_STANDBY_MODE = False
_POOL_CAPACITY = max(1, int(DB_POOL_CAPACITY_EFFECTIVE or 0))
_WEB_CONCURRENCY = max(1, int(os.getenv("WEB_CONCURRENCY", "1") or 1))
_PER_PROCESS_POOL_BUDGET = max(1, _POOL_CAPACITY // _WEB_CONCURRENCY)
_DEFAULT_WORKER_THREADS = min(8, max(2, int(DB_POOL_SIZE_EFFECTIVE or 2)))
# Cap queue concurrency well below pool capacity so HTTP/async/callback
# checkouts still have headroom (avoid 60/60 QueuePool saturation).
_WORKER_THREAD_CAP = max(1, min(12, _PER_PROCESS_POOL_BUDGET // 4))
_QUEUE_ADVISORY_LOCK_ID = int(os.getenv("GENERATION_QUEUE_ADVISORY_LOCK_ID", "918240157") or 918240157)
_QUEUE_LEADER_CONN = None
_QUEUE_FILE_LOCK_FD = None
_QUEUE_FILE_LOCK_PATH = os.getenv("GENERATION_QUEUE_LEADER_LOCK_FILE", "").strip() or os.path.join(
    tempfile.gettempdir(),
    "aistory_generation_queue.lock",
)

_q_conf: Dict[str, Any] = {}
_REQUESTED_WORKER_THREADS = 1
_QUEUE_WORKER_THREADS = 1


def _refresh_queue_worker_thread_settings(force_reload: bool = True) -> int:
    """Resolve worker thread count from live DB/file config (not stale import-time defaults)."""
    global _q_conf, _REQUESTED_WORKER_THREADS, _QUEUE_WORKER_THREADS
    if force_reload or not _q_conf:
        try:
            _q_conf = load_queue_config()
        except Exception:
            _q_conf = dict(DEFAULT_QUEUE_CONFIG)
    requested = max(
        1,
        int(
            (_q_conf or {}).get("queue_threads", DEFAULT_QUEUE_CONFIG["queue_threads"])
            or DEFAULT_QUEUE_CONFIG["queue_threads"]
        ),
    )
    effective = max(1, min(requested, _WORKER_THREAD_CAP))
    _REQUESTED_WORKER_THREADS = requested
    _QUEUE_WORKER_THREADS = effective
    if requested > effective:
        logger.warning(
            "generation queue workers capped to avoid DB pool starvation | requested=%s capped=%s pool_capacity=%s web_concurrency=%s per_process_pool_budget=%s",
            requested,
            effective,
            _POOL_CAPACITY,
            _WEB_CONCURRENCY,
            _PER_PROCESS_POOL_BUDGET,
        )
    return effective


_refresh_queue_worker_thread_settings(force_reload=True)


def _release_queue_leader_lock() -> None:
    global _QUEUE_LEADER_CONN
    global _QUEUE_FILE_LOCK_FD
    conn = _QUEUE_LEADER_CONN
    lock_fd = _QUEUE_FILE_LOCK_FD
    _QUEUE_LEADER_CONN = None
    _QUEUE_FILE_LOCK_FD = None
    if conn is None:
        pass
    else:
        try:
            conn.close()
        except Exception:
            pass
    if lock_fd is not None:
        try:
            os.lseek(lock_fd, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock_fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except Exception:
            pass
        finally:
            try:
                os.close(lock_fd)
            except Exception:
                pass


atexit.register(_release_queue_leader_lock)


def _is_postgres_engine() -> bool:
    try:
        return str(engine.url.get_backend_name() or "").strip().lower().startswith("postgres")
    except Exception:
        return False


def _leader_lock_connection_is_alive() -> bool:
    conn = _QUEUE_LEADER_CONN
    if conn is None:
        return False
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        return True
    except Exception:
        return False
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass


def _try_acquire_queue_leader_lock() -> bool:
    global _QUEUE_LEADER_CONN
    global _QUEUE_FILE_LOCK_FD
    if not _is_postgres_engine():
        if _QUEUE_FILE_LOCK_FD is not None:
            return True
        lock_fd = None
        try:
            lock_dir = os.path.dirname(_QUEUE_FILE_LOCK_PATH) or "."
            os.makedirs(lock_dir, exist_ok=True)
            lock_fd = os.open(_QUEUE_FILE_LOCK_PATH, os.O_RDWR | os.O_CREAT)
            try:
                os.lseek(lock_fd, 0, os.SEEK_SET)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(lock_fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return False
            _QUEUE_FILE_LOCK_FD = lock_fd
            lock_fd = None
            return True
        except Exception as exc:
            logger.warning(
                "generation queue file leader lock probe failed; skipping worker startup until next probe | path=%s err=%s",
                _QUEUE_FILE_LOCK_PATH,
                exc,
            )
            return False
        finally:
            if lock_fd is not None:
                try:
                    os.close(lock_fd)
                except Exception:
                    pass
    if _QUEUE_LEADER_CONN is not None:
        if _leader_lock_connection_is_alive():
            return True
        logger.warning("generation queue leader lock connection is dead; releasing stale handle")
        _release_queue_leader_lock()

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


def _ensure_leader_heartbeat_table_ready() -> None:
    global _LEADER_HEARTBEAT_TABLE_READY
    if _LEADER_HEARTBEAT_TABLE_READY:
        return
    with _LEADER_HEARTBEAT_TABLE_LOCK:
        if _LEADER_HEARTBEAT_TABLE_READY:
            return
        ddl = """
        CREATE TABLE IF NOT EXISTS generation_queue_leader_heartbeat (
            id INTEGER PRIMARY KEY,
            worker_id TEXT,
            heartbeat_at REAL NOT NULL,
            pid INTEGER,
            hostname TEXT,
            effective_threads INTEGER,
            mode TEXT
        )
        """
        with engine.begin() as conn:
            conn.execute(text(ddl))
        _LEADER_HEARTBEAT_TABLE_READY = True


def _pulse_queue_leader_heartbeat(worker_id: str = "leader") -> None:
    """Cluster-visible liveness signal from the process that currently consumes the queue."""
    try:
        _ensure_leader_heartbeat_table_ready()
    except Exception as exc:
        logger.debug("generation queue leader heartbeat table ensure skipped: %s", exc)
        return
    now = time.time()
    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = ""
    mode = "standby" if _QUEUE_STANDBY_MODE else "primary"
    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                INSERT INTO generation_queue_leader_heartbeat (
                    id, worker_id, heartbeat_at, pid, hostname, effective_threads, mode
                ) VALUES (
                    1, :worker_id, :heartbeat_at, :pid, :hostname, :effective_threads, :mode
                )
                ON CONFLICT(id) DO UPDATE SET
                    worker_id = excluded.worker_id,
                    heartbeat_at = excluded.heartbeat_at,
                    pid = excluded.pid,
                    hostname = excluded.hostname,
                    effective_threads = excluded.effective_threads,
                    mode = excluded.mode
                """
            ),
            {
                "worker_id": str(worker_id or "leader"),
                "heartbeat_at": now,
                "pid": int(os.getpid()),
                "hostname": str(hostname or "")[:200] or None,
                "effective_threads": int(_QUEUE_WORKER_THREADS or 0),
                "mode": mode,
            },
        )
        db.commit()
    except Exception as exc:
        logger.debug("generation queue leader heartbeat pulse failed: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def get_queue_leader_heartbeat() -> Dict[str, Any]:
    """Read cluster leader heartbeat (cross-process; safe to call from web)."""
    now = time.time()
    empty = {
        "alive": False,
        "stale": True,
        "heartbeat_at": None,
        "age_seconds": None,
        "stale_after_seconds": float(_LEADER_HEARTBEAT_STALE_SECONDS),
        "worker_id": None,
        "pid": None,
        "hostname": None,
        "effective_threads": None,
        "mode": None,
    }
    try:
        _ensure_leader_heartbeat_table_ready()
    except Exception:
        return empty
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                SELECT worker_id, heartbeat_at, pid, hostname, effective_threads, mode
                FROM generation_queue_leader_heartbeat
                WHERE id = 1
                """
            )
        ).mappings().first()
        if not row:
            return empty
        heartbeat_at = float(row.get("heartbeat_at") or 0.0)
        if heartbeat_at <= 0:
            return empty
        age = max(0.0, now - heartbeat_at)
        alive = age <= float(_LEADER_HEARTBEAT_STALE_SECONDS)
        return {
            "alive": bool(alive),
            "stale": not bool(alive),
            "heartbeat_at": heartbeat_at,
            "age_seconds": int(age),
            "stale_after_seconds": float(_LEADER_HEARTBEAT_STALE_SECONDS),
            "worker_id": str(row.get("worker_id") or "") or None,
            "pid": int(row.get("pid") or 0) or None,
            "hostname": str(row.get("hostname") or "") or None,
            "effective_threads": int(row.get("effective_threads") or 0) or None,
            "mode": str(row.get("mode") or "") or None,
        }
    except Exception as exc:
        logger.debug("generation queue leader heartbeat read failed: %s", exc)
        return empty
    finally:
        db.close()


def is_queue_leader_alive() -> bool:
    return bool(get_queue_leader_heartbeat().get("alive"))


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


def _payload_contains_shot_id(payload: Any, shot_id: str) -> bool:
    safe_shot_id = str(shot_id or "").strip()
    if not safe_shot_id or not isinstance(payload, dict):
        return False

    def _collect(src: Any, depth: int = 0) -> bool:
        if depth > 3 or not isinstance(src, dict):
            return False
        for key in ("shot_id", "ownerShotId", "owner_shot_id"):
            value = src.get(key)
            if value in (None, ""):
                continue
            if str(value).strip() == safe_shot_id:
                return True
        for nested_key in ("request", "payload", "metadata", "context", "combined_payload", "final_provider_payload", "result"):
            nested = src.get(nested_key)
            if isinstance(nested, dict) and _collect(nested, depth + 1):
                return True
            if nested_key == "result" and isinstance(nested, dict):
                meta = nested.get("metadata")
                if isinstance(meta, dict) and _collect(meta, depth + 1):
                    return True
        return False

    return _collect(payload)


def _shot_id_sql_like_patterns(shot_id: str) -> List[str]:
    safe = str(shot_id or "").strip()
    if not safe:
        return []
    # Match JSON number and string encodings of shot_id.
    return [
        f'%"shot_id": {safe}%',
        f'%"shot_id":{safe}%',
        f'%"shot_id": "{safe}"%',
        f'%"shot_id":"{safe}"%',
        f'%"ownerShotId": "{safe}"%',
        f'%"ownerShotId":"{safe}"%',
        f'%"owner_shot_id": "{safe}"%',
        f'%"owner_shot_id":"{safe}"%',
    ]


def find_generation_job_states_by_shot_id(
    *,
    kind: str,
    shot_id: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Find persisted generation job snapshots whose payload references shot_id."""
    safe_kind = str(kind or "").strip().lower()
    safe_shot_id = str(shot_id or "").strip()
    if not safe_kind or not safe_shot_id:
        return []
    patterns = _shot_id_sql_like_patterns(safe_shot_id)
    if not patterns:
        return []

    _ensure_job_state_table_ready()
    like_clauses = " OR ".join(f"payload_json LIKE :p{i}" for i in range(len(patterns)))
    params: Dict[str, Any] = {
        "kind": safe_kind,
        "limit": int(max(1, min(int(limit or 20), 100))),
    }
    for i, pattern in enumerate(patterns):
        params[f"p{i}"] = pattern

    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                f"""
                SELECT job_id, user_id, status, updated_at, payload_json
                FROM generation_job_state
                WHERE kind = :kind AND ({like_clauses})
                ORDER BY updated_at DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
        matches: List[Dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(str(row.get("payload_json") or "{}"))
            except Exception:
                payload = None
            if not isinstance(payload, dict):
                continue
            if not _payload_contains_shot_id(payload, safe_shot_id):
                continue
            payload["job_id"] = payload.get("job_id") or str(row.get("job_id") or "")
            if payload.get("user_id") in (None, "") and row.get("user_id") not in (None, ""):
                payload["user_id"] = row.get("user_id")
            if payload.get("status") in (None, "") and row.get("status") not in (None, ""):
                payload["status"] = row.get("status")
            if row.get("updated_at") not in (None, "") and payload.get("updated_at") in (None, ""):
                payload["updated_at"] = row.get("updated_at")
            matches.append(payload)
        return matches
    finally:
        db.close()


def find_generation_tasks_by_shot_id(
    *,
    kind: str,
    shot_id: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Find queue rows (including failed/completed) whose payload references shot_id."""
    safe_kind = str(kind or "").strip().lower()
    safe_shot_id = str(shot_id or "").strip()
    if not safe_kind or not safe_shot_id:
        return []
    patterns = _shot_id_sql_like_patterns(safe_shot_id)
    if not patterns:
        return []

    _ensure_queue_table_ready()
    like_clauses = " OR ".join(f"payload_json LIKE :p{i}" for i in range(len(patterns)))
    params: Dict[str, Any] = {
        "kind": safe_kind,
        "limit": int(max(1, min(int(limit or 20), 100))),
    }
    for i, pattern in enumerate(patterns):
        params[f"p{i}"] = pattern

    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                f"""
                SELECT job_id, kind, user_id, status, attempt_count, worker_id,
                       created_at, started_at, finished_at, last_heartbeat, error, payload_json
                FROM generation_task_queue
                WHERE kind = :kind AND ({like_clauses})
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
        matches: List[Dict[str, Any]] = []
        for row in rows:
            item = {k: row.get(k) for k in row.keys()}
            try:
                payload = json.loads(str(item.get("payload_json") or "{}"))
            except Exception:
                payload = None
            if not isinstance(payload, dict):
                continue
            if not _payload_contains_shot_id(payload, safe_shot_id):
                continue
            item["payload"] = payload
            matches.append(item)
        return matches
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
    live_cfg = load_queue_config()
    configured_threads = max(
        1,
        int((live_cfg or {}).get("queue_threads", _DEFAULT_WORKER_THREADS) or _DEFAULT_WORKER_THREADS),
    )
    requested_threads = max(1, int(_REQUESTED_WORKER_THREADS or configured_threads or _DEFAULT_WORKER_THREADS))
    # Keep runtime slot capacity aligned with effective queue workers; guard against
    # unexpected zero/invalid values so metrics never report 0 capacity while running.
    effective_threads = max(1, int(_QUEUE_WORKER_THREADS or 0))
    if effective_threads > int(_WORKER_THREAD_CAP):
        effective_threads = int(_WORKER_THREAD_CAP)
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
                SELECT status, worker_id, started_at, last_heartbeat
                FROM generation_task_queue
                WHERE status IN ('submit', 'running')
                """
            )
        ).mappings().all()
        waiting_callback_rows = db.execute(
            text(
                """
                SELECT worker_id, started_at, last_heartbeat
                FROM generation_task_queue
                WHERE status = 'waiting_callback'
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
        submit_count = int(status_counts.get("submit", 0))
        running_count = int(status_counts.get("running", 0))
        queued_count = int(status_counts.get("queued", 0))
        waiting_callback_count = int(status_counts.get("waiting_callback", 0))
        callback_processing_count = int(status_counts.get("callback_processing", 0))
        waiting_callback_with_worker = sum(
            1 for row in waiting_callback_rows if str(row.get("worker_id") or "").strip()
        )
        worker_slots_total = int(effective_threads)
        worker_slots_in_use = max(0, min(worker_slots_total, submit_count + running_count))
        worker_slots_available = max(0, worker_slots_total - worker_slots_in_use)
        leader_hb = get_queue_leader_heartbeat()
        cluster_effective = int(leader_hb.get("effective_threads") or 0) or int(effective_threads)
        # Prefer cluster leader capacity when a live consumer exists (web stats otherwise
        # report this process's idle defaults while the dedicated worker is the leader).
        if leader_hb.get("alive") and int(leader_hb.get("effective_threads") or 0) > 0:
            worker_slots_total = int(leader_hb.get("effective_threads") or cluster_effective)
            worker_slots_in_use = max(0, min(worker_slots_total, submit_count + running_count))
            worker_slots_available = max(0, worker_slots_total - worker_slots_in_use)

        return {
            "queue": {
                "status_counts": status_counts,
                "kind_counts": kind_counts,
                "active_count": int(queued_count + submit_count + running_count),
                "submit_count": submit_count,
                "running_count": running_count,
                "queued_count": queued_count,
                "waiting_callback_count": waiting_callback_count,
                "callback_processing_count": callback_processing_count,
                "waiting_callback_with_worker_count": int(waiting_callback_with_worker),
                "worker_slots_total": worker_slots_total,
                "worker_slots_in_use": worker_slots_in_use,
                "worker_slots_available": worker_slots_available,
                "queued_oldest_wait_seconds": queued_oldest_wait_seconds,
                "finished_last_hour": int((recent_completed_row or {}).get("cnt") or 0),
                "leader_alive": bool(leader_hb.get("alive")),
                "drain_stuck": bool(
                    queued_count > 0
                    and submit_count + running_count == 0
                    and not bool(leader_hb.get("alive"))
                ),
            },
            "workers": {
                "configured_threads": int(configured_threads),
                "requested_threads": int(requested_threads),
                "effective_threads": int(effective_threads),
                "thread_cap": int(_WORKER_THREAD_CAP),
                "restart_required_for_thread_change": bool(configured_threads != int(requested_threads)),
                "worker_thread_started": bool(_QUEUE_STARTED),
                "standby_mode": bool(_QUEUE_STANDBY_MODE),
                "leader_lock_held_by_process": (
                    bool(_QUEUE_LEADER_CONN is not None and _leader_lock_connection_is_alive())
                    if _is_postgres_engine()
                    else bool(_QUEUE_FILE_LOCK_FD is not None)
                ),
                "cluster_leader": leader_hb,
                "cluster_leader_alive": bool(leader_hb.get("alive")),
                "active_running_workers": len(active_workers),
                "slots_total": worker_slots_total,
                "slots_in_use": worker_slots_in_use,
                "slots_available": worker_slots_available,
                "waiting_callback_with_worker_count": int(waiting_callback_with_worker),
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
    try:
        if not is_queue_leader_alive():
            logger.error(
                "generation queue enqueue while cluster leader heartbeat is stale/missing | job_id=%s kind=%s user_id=%s "
                "(tasks will stay queued until aistory-generation-worker or a standby consumer acquires the leader lock)",
                job_id,
                kind,
                user_id,
            )
    except Exception:
        pass
    return str(job_id)


def patch_generation_task_payload(job_id: str, patch: Dict[str, Any]) -> bool:
    _ensure_queue_table_ready()
    if not isinstance(patch, dict) or not patch:
        return False

    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                SELECT payload_json
                FROM generation_task_queue
                WHERE job_id = :job_id
                """
            ),
            {"job_id": str(job_id)},
        ).mappings().first()
        if not row:
            return False
        try:
            payload = json.loads(str(row.get("payload_json") or "{}"))
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload.update(patch)
        result = db.execute(
            text(
                """
                UPDATE generation_task_queue
                SET payload_json = :payload_json,
                    last_heartbeat = COALESCE(last_heartbeat, :last_heartbeat)
                WHERE job_id = :job_id
                """
            ),
            {
                "job_id": str(job_id),
                "payload_json": json.dumps(payload, ensure_ascii=False, default=str),
                "last_heartbeat": time.time(),
            },
        )
        db.commit()
        return int(result.rowcount or 0) > 0
    finally:
        db.close()


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
    clear_worker = normalized_status not in {"submit", "running"}
    where_sql = "WHERE job_id = :job_id"
    if preserve_canceled:
        where_sql += " AND status <> 'canceled'"
    # Never leapfrog queued → waiting_callback (no provider submit happened yet).
    if normalized_status == "waiting_callback":
        where_sql += " AND status IN ('submit', 'running', 'waiting_callback', 'callback_processing')"
    elif normalized_status == "callback_processing":
        where_sql += " AND status IN ('submit', 'running', 'waiting_callback', 'callback_processing')"

    db = SessionLocal()
    try:
        result = db.execute(
            text(
                """
                UPDATE generation_task_queue
                SET status = :status,
                    worker_id = CASE WHEN :clear_worker THEN NULL ELSE worker_id END,
                    finished_at = :finished_at,
                    last_heartbeat = :last_heartbeat,
                    error = :error
                """
                + where_sql
            ),
            {
                "job_id": str(job_id),
                "status": normalized_status,
                "clear_worker": bool(clear_worker),
                "finished_at": now if is_terminal else None,
                "last_heartbeat": now,
                "error": str(error) if error else None,
            },
        )
        db.commit()
        updated = int(result.rowcount or 0) > 0
        if not updated and normalized_status in {"waiting_callback", "callback_processing"}:
            latest = get_generation_task_status(str(job_id)) or {}
            logger.warning(
                "generation queue refused status leap | job_id=%s requested=%s current=%s",
                job_id,
                normalized_status,
                latest.get("status"),
            )
        return updated
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


_ACTIVE_GENERATION_TASK_STATUSES = (
    "queued",
    "submit",
    "pending",
    "running",
    "waiting_callback",
    "callback_processing",
)


def count_active_generation_tasks_for_user(
    user_id: int,
    *,
    kinds: Optional[List[str]] = None,
) -> int:
    """Count in-flight generation queue tasks for one user (optionally by kind)."""
    _ensure_queue_table_ready()
    status_list = ", ".join(f"'{status}'" for status in _ACTIVE_GENERATION_TASK_STATUSES)
    clauses = [
        "user_id = :user_id",
        f"status IN ({status_list})",
    ]
    params: Dict[str, Any] = {"user_id": int(user_id)}
    if kinds:
        normalized_kinds = [str(kind or "").strip().lower() for kind in kinds if str(kind or "").strip()]
        if normalized_kinds:
            placeholders: List[str] = []
            for index, kind in enumerate(normalized_kinds):
                key = f"kind_{index}"
                placeholders.append(f":{key}")
                params[key] = kind
            clauses.append(f"kind IN ({', '.join(placeholders)})")

    db = SessionLocal()
    try:
        row = db.execute(
            text(
                f"""
                SELECT COUNT(*) AS cnt
                FROM generation_task_queue
                WHERE {' AND '.join(clauses)}
                """
            ),
            params,
        ).mappings().first()
        return int((row or {}).get("cnt") or 0)
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
                SET status = 'canceled',
                    worker_id = NULL,
                    finished_at = :finished_at,
                    error = :error
                WHERE job_id = :job_id AND status IN ('queued', 'submit', 'running', 'waiting_callback', 'callback_processing')
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
    """Bulk-cancel active generation queue tasks and return affected row count.

    Also best-effort syncs image/video runtime job stores so Cancel All cannot leave
    in-memory ``queued`` ghosts that keep blocking parallel submit (HTTP 429).
    """
    _ensure_queue_table_ready()
    now = time.time()
    reason_text = str(reason or "Task canceled by stop-all")

    clauses = ["status IN ('queued', 'submit', 'running', 'waiting_callback', 'callback_processing')"]
    params: Dict[str, Any] = {
        "finished_at": now,
        "error": reason_text,
    }
    if kind:
        clauses.append("kind = :kind")
        params["kind"] = str(kind)
    if user_id is not None:
        clauses.append("user_id = :user_id")
        params["user_id"] = int(user_id)

    where_sql = " AND ".join(clauses)
    db = SessionLocal()
    canceled_rows: List[Dict[str, Any]] = []
    try:
        result = db.execute(
            text(
                f"""
                UPDATE generation_task_queue
                SET status = 'canceled',
                    worker_id = NULL,
                    finished_at = :finished_at,
                    error = :error
                WHERE {where_sql}
                RETURNING job_id, kind, user_id
                """
            ),
            params,
        )
        canceled_rows = [dict(row) for row in result.mappings().all()]
        db.commit()
    finally:
        db.close()

    if canceled_rows:
        try:
            from app.core.time_utils import now_bj_iso
            from app.services.generation_runtime.job_store import (
                IMAGE_ACTIVE_SCOPE_STORE,
                IMAGE_JOB_LOCK,
                IMAGE_JOB_STORE,
                IMAGE_JOB_TASKS,
                VIDEO_ACTIVE_SCOPE_STORE,
                VIDEO_JOB_LOCK,
                VIDEO_JOB_STORE,
                VIDEO_JOB_TASKS,
                _set_image_job,
                _set_video_job,
            )

            finished_at = now_bj_iso()
            for row in canceled_rows:
                job_id = str(row.get("job_id") or "").strip()
                safe_kind = str(row.get("kind") or "").strip().lower()
                if not job_id:
                    continue
                if safe_kind == "image":
                    _set_image_job(
                        job_id,
                        status="canceled",
                        finished_at=finished_at,
                        error=reason_text,
                    )
                    with IMAGE_JOB_LOCK:
                        IMAGE_JOB_TASKS.pop(job_id, None)
                        scope_key = str((IMAGE_JOB_STORE.get(job_id) or {}).get("task_scope") or "").strip()
                        if scope_key and IMAGE_ACTIVE_SCOPE_STORE.get(scope_key) == job_id:
                            IMAGE_ACTIVE_SCOPE_STORE.pop(scope_key, None)
                elif safe_kind == "video":
                    _set_video_job(
                        job_id,
                        status="canceled",
                        finished_at=finished_at,
                        error=reason_text,
                    )
                    with VIDEO_JOB_LOCK:
                        VIDEO_JOB_TASKS.pop(job_id, None)
                        scope_key = str((VIDEO_JOB_STORE.get(job_id) or {}).get("task_scope") or "").strip()
                        if scope_key and VIDEO_ACTIVE_SCOPE_STORE.get(scope_key) == job_id:
                            VIDEO_ACTIVE_SCOPE_STORE.pop(scope_key, None)
        except Exception:
            logger.warning(
                "cancel_generation_tasks runtime store sync failed | canceled=%s",
                len(canceled_rows),
                exc_info=True,
            )

    return int(len(canceled_rows))


def _claim_next_task(worker_id: str) -> Optional[Dict[str, Any]]:
    _ensure_queue_table_ready()
    now = time.time()
    cutoff = now - _QUEUE_RECLAIM_SECONDS
    expire_before = now - 3600.0
    db = SessionLocal()
    try:
        if _is_postgres_engine():
            claim_sql = text(
                """
                WITH candidate AS (
                    SELECT job_id
                    FROM generation_task_queue
                    WHERE status = 'queued'
                             OR (status IN ('submit', 'running') AND COALESCE(last_heartbeat, 0) < :cutoff)
                    ORDER BY created_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE generation_task_queue q
                SET status = CASE
                        WHEN COALESCE(q.created_at, :now_ts) < :expire_before THEN 'failed'
                        ELSE 'submit'
                    END,
                    worker_id = :worker_id,
                    started_at = COALESCE(q.started_at, :now_ts),
                    last_heartbeat = :now_ts,
                    finished_at = CASE
                        WHEN COALESCE(q.created_at, :now_ts) < :expire_before THEN :now_ts
                        ELSE NULL
                    END,
                    error = CASE
                        WHEN COALESCE(q.created_at, :now_ts) < :expire_before THEN 'Task queued for over 60 minutes. Timed out.'
                        ELSE NULL
                    END,
                    attempt_count = q.attempt_count + 1
                FROM candidate
                WHERE q.job_id = candidate.job_id
                  AND (q.status = 'queued' OR (q.status IN ('submit', 'running') AND COALESCE(q.last_heartbeat, 0) < :cutoff))
                RETURNING q.job_id, q.kind, q.user_id, q.payload_json, q.status
                """
            )
        else:
            claim_sql = text(
                """
                UPDATE generation_task_queue
                SET status = CASE
                        WHEN COALESCE(created_at, :now_ts) < :expire_before THEN 'failed'
                        ELSE 'submit'
                    END,
                    worker_id = :worker_id,
                    started_at = COALESCE(started_at, :now_ts),
                    last_heartbeat = :now_ts,
                    finished_at = CASE
                        WHEN COALESCE(created_at, :now_ts) < :expire_before THEN :now_ts
                        ELSE NULL
                    END,
                    error = CASE
                        WHEN COALESCE(created_at, :now_ts) < :expire_before THEN 'Task queued for over 60 minutes. Timed out.'
                        ELSE NULL
                    END,
                    attempt_count = attempt_count + 1
                WHERE job_id = (
                    SELECT job_id
                    FROM generation_task_queue
                    WHERE status = 'queued'
                             OR (status IN ('submit', 'running') AND COALESCE(last_heartbeat, 0) < :cutoff)
                    ORDER BY created_at ASC
                    LIMIT 1
                )
                  AND (status = 'queued' OR (status IN ('submit', 'running') AND COALESCE(last_heartbeat, 0) < :cutoff))
                RETURNING job_id, kind, user_id, payload_json, status
                """
            )
        row = db.execute(
            claim_sql,
            {
                "worker_id": worker_id,
                "now_ts": now,
                "cutoff": cutoff,
                "expire_before": expire_before,
            },
        ).mappings().first()
        db.commit()
        if not row:
            return None

        if str(row.get("status") or "").strip().lower() == "failed":
            logger.warning("Claimed task %s but it was queued over 60 minutes. Marked as failed.", row["job_id"])
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
            where_clause += " AND status IN ('submit', 'running')"

        result = db.execute(
            text(
                """
                UPDATE generation_task_queue
                SET status = :status,
                    worker_id = NULL,
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
                                    AND status IN ('submit', 'running')
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


def _defer_task_to_waiting_callback(job_id: str, worker_id: str) -> bool:
    _ensure_queue_table_ready()
    now = time.time()
    db = SessionLocal()
    try:
        result = db.execute(
            text(
                """
                UPDATE generation_task_queue
                SET status = 'waiting_callback',
                    worker_id = NULL,
                    last_heartbeat = :heartbeat,
                    finished_at = NULL,
                    error = NULL
                WHERE job_id = :job_id
                                    AND status IN ('submit', 'running')
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
_QUEUE_LAST_CALLBACK_LEASE_REPAIR_TIME = 0.0


def _repair_waiting_callback_worker_leases() -> int:
    _ensure_queue_table_ready()
    db = SessionLocal()
    try:
        result = db.execute(
            text(
                """
                UPDATE generation_task_queue
                SET worker_id = NULL,
                    finished_at = NULL,
                    last_heartbeat = COALESCE(last_heartbeat, :heartbeat)
                WHERE status = 'waiting_callback'
                  AND (worker_id IS NOT NULL OR finished_at IS NOT NULL)
                """
            ),
            {"heartbeat": time.time()},
        )
        db.commit()
        return int(result.rowcount or 0)
    finally:
        db.close()

def _cleanup_old_tasks() -> None:
    global _QUEUE_LAST_CLEANUP_TIME, _QUEUE_LAST_TIMEOUT_SWEEP_TIME, _QUEUE_LAST_CALLBACK_LEASE_REPAIR_TIME
    now = time.time()
    if now - _QUEUE_LAST_CALLBACK_LEASE_REPAIR_TIME >= 60.0:
        _QUEUE_LAST_CALLBACK_LEASE_REPAIR_TIME = now
        try:
            repaired = _repair_waiting_callback_worker_leases()
            if repaired > 0:
                logger.warning(
                    "generation queue repaired %s waiting_callback tasks with stale worker leases",
                    repaired,
                )
        except Exception as exc:
            logger.warning("generation queue waiting_callback lease repair failed: %s", exc)

    if now - _QUEUE_LAST_TIMEOUT_SWEEP_TIME < 60.0:
        return
    _QUEUE_LAST_TIMEOUT_SWEEP_TIME = now
    
    # We sweep for timeouts every minute, but full deletes only every hour.
    do_full_cleanup = False
    if now - _QUEUE_LAST_CLEANUP_TIME >= 3600.0:
        _QUEUE_LAST_CLEANUP_TIME = now
        do_full_cleanup = True
    cutoff = now - 86400.0  # 1 day cutoff
    timeout_cutoff = now - 3600.0 # 60 min timeout for worker-owned tasks
    db = SessionLocal()
    try:
        # Mark long worker-owned tasks as failed.
        r_timeout = db.execute(
            text(
                """
                UPDATE generation_task_queue 
                SET status = 'failed', 
                    worker_id = NULL,
                    error = 'Task submit/running for over 60 minutes. Timed out.',
                    finished_at = :now
                WHERE status IN ('submit', 'running')
                  AND COALESCE(started_at, created_at) < :timeout_cutoff
                """
            ),
            {"now": now, "timeout_cutoff": timeout_cutoff},
        )
        db.commit()
        if (r_timeout.rowcount or 0) > 0:
            logger.warning("generation queue sweep timed out %s submit/running tasks (>60m)", r_timeout.rowcount)

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

            # Prefer hot-swapped processor so uvicorn StatReload can refresh
            # the generation runner without restarting the daemon queue thread.
            live_processor = _ACTIVE_PROCESSOR or processor
            processor_result: Any = None
            result = live_processor(task["kind"], task["job_id"], task["user_id"], task["payload"])
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
                await asyncio.to_thread(_defer_task_to_waiting_callback, str(task.get("job_id") or ""), worker_name)
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

    async def _leader_heartbeat_loop() -> None:
        while _QUEUE_ASYNC_STOP_EVENT is not None and not _QUEUE_ASYNC_STOP_EVENT.is_set():
            try:
                await asyncio.to_thread(_pulse_queue_leader_heartbeat, "generation-queue-leader")
            except Exception:
                pass
            try:
                await asyncio.sleep(_LEADER_HEARTBEAT_PULSE_SECONDS)
            except asyncio.CancelledError:
                break

    heartbeat_task = asyncio.create_task(_leader_heartbeat_loop())
    try:
        await asyncio.to_thread(_pulse_queue_leader_heartbeat, "generation-queue-leader")
        tasks = []
        for index in range(_QUEUE_WORKER_THREADS):
            worker_name = f"generation-queue-{index + 1}"
            tasks.append(asyncio.create_task(_worker_loop_async(worker_name, processor)))
        if tasks:
            await asyncio.gather(*tasks)
    except Exception as exc:
        logger.exception("generation queue async event loop failed")
    finally:
        if _QUEUE_ASYNC_STOP_EVENT is not None:
            _QUEUE_ASYNC_STOP_EVENT.set()
        heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task
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
                _defer_task_to_waiting_callback(str(task.get("job_id") or ""), worker_name)
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
            logger.info(
                "generation queue worker acquired leader lock, starting event loop | standby=%s threads=%s",
                _QUEUE_STANDBY_MODE,
                _QUEUE_WORKER_THREADS,
            )
            _ensure_queue_table_ready()
            asyncio.run(_async_event_loop(processor))
        except Exception as exc:
            logger.exception("generation queue event loop crashed | err=%s", exc)
            _QUEUE_STOP_EVENT.wait(15.0)
        finally:
            # Drop the advisory/file lock so a sibling web/worker process can fail over.
            _release_queue_leader_lock()
            if not _QUEUE_STOP_EVENT.is_set():
                logger.warning("generation queue event loop exited. Re-checking lock...")
                _QUEUE_STOP_EVENT.wait(5.0)

def start_generation_task_worker(
    processor: Callable[[str, str, int, Dict[str, Any]], None],
    *,
    standby: bool = False,
) -> None:
    """Start generation task workers using async event loop."""
    global _QUEUE_STARTED, _ACTIVE_PROCESSOR, _QUEUE_STANDBY_MODE
    # Always refresh processor so StatReload picks up fixed runners without a
    # full process restart (daemon queue thread survives module reloads).
    _ACTIVE_PROCESSOR = processor
    if standby:
        _QUEUE_STANDBY_MODE = True
    if _QUEUE_STARTED:
        logger.info("generation queue worker already running; processor hot-swapped | standby=%s", _QUEUE_STANDBY_MODE)
        return
    with _QUEUE_START_LOCK:
        _ACTIVE_PROCESSOR = processor
        if standby:
            _QUEUE_STANDBY_MODE = True
        if _QUEUE_STARTED:
            logger.info("generation queue worker already running; processor hot-swapped | standby=%s", _QUEUE_STANDBY_MODE)
            return

        # Re-read after DB bootstrap so admin-saved thread counts actually apply.
        effective_threads = _refresh_queue_worker_thread_settings(force_reload=True)

        try:
            repaired = _repair_waiting_callback_worker_leases()
            if repaired > 0:
                logger.warning(
                    "generation queue startup repaired %s waiting_callback tasks with stale worker leases",
                    repaired,
                )
        except Exception as exc:
            logger.warning("generation queue startup waiting_callback lease repair failed: %s", exc)

        thread = threading.Thread(
            target=_worker_thread_main,
            args=(processor,),
            daemon=True,
            name="generation-queue-event-loop",
        )
        thread.start()
        _QUEUE_STARTED = True
        logger.info(
            "generation queue async event loop thread started | standby=%s effective_threads=%s "
            "(waiting to become cluster leader)",
            _QUEUE_STANDBY_MODE,
            effective_threads,
        )
