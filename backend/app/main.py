
from contextlib import asynccontextmanager
from typing import Iterable, Tuple, Dict, Any, List
from datetime import datetime
import os
import json
import asyncio
import threading
import tracemalloc
from itertools import islice
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, Response
from app.core.config import settings
from app.api import endpoints, settings as settings_api, groups as groups_api, invoices as invoices_api, invoices as invoices_api
from app.db.session import engine, SessionLocal
from app.models.all_models import Base, User
from sqlalchemy import inspect, text
from app.core.logging import LoggingMiddleware, logger, configure_uvicorn_logging_noise_reduction
from app.db.init_db import check_and_migrate_tables, create_default_superuser, init_initial_data
from app.api.deps import warm_user_auth_cache_from_db
from app.services.system_api_runtime_cache import warm_system_api_cache
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from jose import JWTError, jwt
import time
import re

# ---------------------------------------------------------------------------
# Startup DB bootstrap — retry on transient DNS / connection failures so
# the process doesn't crash during Render's brief internal-DNS blips.
# ---------------------------------------------------------------------------
_DB_BOOT_MAX_RETRIES = 5
_DB_BOOT_RETRY_DELAY = 2  # seconds
_DB_BOOT_LOCK_KEY = int(os.getenv("DB_BOOT_LOCK_KEY", "481516234"))
_DB_BOOT_LOCK_WAIT_TIMEOUT = int(os.getenv("DB_BOOT_LOCK_WAIT_TIMEOUT", "240"))
_DB_BOOT_LOCK_POLL_DELAY = max(1, int(os.getenv("DB_BOOT_LOCK_POLL_DELAY", "2")))
_PROCESS_STARTED_UNIX_TS = time.time()


def _run_critical_db_bootstrap_steps() -> None:
    logger.info("DB bootstrap: create_all start")
    Base.metadata.create_all(bind=engine)
    logger.info("DB bootstrap: critical schema migration start")
    check_and_migrate_tables(critical_only=True)
    readiness_issue = _get_minimum_schema_readiness_issue()
    if readiness_issue:
        raise RuntimeError(f"Critical DB schema bootstrap finished but readiness probe still failed: {readiness_issue}")
    logger.info("DB bootstrap: default superuser check start")
    create_default_superuser()


def _get_minimum_schema_readiness_issue() -> str | None:
    try:
        inspector = inspect(engine)
        dialect_name = str(getattr(engine.dialect, "name", "") or "").lower()
        if not inspector.has_table("users"):
            return "users table missing"
        user_cols = {col["name"]: col for col in inspector.get_columns("users")}
        is_active_col = user_cols.get("is_active")
        if not is_active_col:
            return "users.is_active column missing"
        is_active_type = str(is_active_col.get("type") or "").lower()
        if "bool" in is_active_type:
            if dialect_name == "postgresql":
                return f"users.is_active still boolean ({is_active_type})"
            logger.warning(
                "DB bootstrap readiness: accepting users.is_active boolean for dialect=%s type=%s due compatible runtime coercion",
                dialect_name or "unknown",
                is_active_type,
            )

        if inspector.has_table("project_shares"):
            share_cols = {col["name"] for col in inspector.get_columns("project_shares")}
            if "role" not in share_cols or "permissions" not in share_cols:
                return "project_shares.role or project_shares.permissions missing"

        required_review_tables = (
            "project_asset_review_threads",
            "project_asset_review_rounds",
            "project_asset_review_messages",
        )
        for table_name in required_review_tables:
            if not inspector.has_table(table_name):
                return f"{table_name} table missing"
        return None
    except Exception as exc:
        logger.warning("DB bootstrap readiness probe failed: %s", exc)
        return str(exc)


def _is_minimum_schema_ready() -> bool:
    return _get_minimum_schema_readiness_issue() is None


def _wait_for_postgres_bootstrap_slot():
    deadline = time.monotonic() + _DB_BOOT_LOCK_WAIT_TIMEOUT
    waited = False

    while time.monotonic() < deadline:
        conn = None
        try:
            conn = engine.connect()
            acquired = bool(
                conn.execute(
                    text("SELECT pg_try_advisory_lock(:key)"),
                    {"key": _DB_BOOT_LOCK_KEY},
                ).scalar()
            )
            if acquired:
                if waited and _is_minimum_schema_ready():
                    conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _DB_BOOT_LOCK_KEY})
                    conn.close()
                    logger.info("DB bootstrap: another worker completed schema bootstrap")
                    return "ready", None

                logger.info(
                    "DB bootstrap: advisory lock acquired%s",
                    " after wait" if waited else "",
                )
                return "run", conn
        except Exception:
            if conn is not None:
                conn.close()
            raise

        if conn is not None:
            conn.close()

        if not waited:
            logger.info("DB bootstrap: another worker is running migrations; waiting for advisory lock")
            waited = True
        time.sleep(_DB_BOOT_LOCK_POLL_DELAY)

    return "timeout", None


def _release_postgres_bootstrap_lock(conn) -> None:
    if conn is None:
        return
    try:
        conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _DB_BOOT_LOCK_KEY})
    except Exception as exc:
        logger.warning("DB bootstrap: failed to release advisory lock cleanly: %s", exc)
    finally:
        conn.close()


def _bootstrap_db_schema() -> tuple[bool, bool]:
    """Run blocking schema/bootstrap work before serving requests."""
    is_postgres = engine.dialect.name == "postgresql"
    for _attempt in range(1, _DB_BOOT_MAX_RETRIES + 1):
        bootstrap_lock_conn = None
        try:
            if is_postgres:
                mode, bootstrap_lock_conn = _wait_for_postgres_bootstrap_slot()
                if mode == "ready":
                    return True, False
                if mode == "timeout":
                    raise TimeoutError(
                        f"timed out waiting {_DB_BOOT_LOCK_WAIT_TIMEOUT}s for DB bootstrap advisory lock"
                    )

            _run_critical_db_bootstrap_steps()
            return True, True
        except Exception as exc:
            if _attempt < _DB_BOOT_MAX_RETRIES:
                logger.warning(
                    "Critical DB bootstrap attempt %d/%d failed: %s — retrying in %ds",
                    _attempt, _DB_BOOT_MAX_RETRIES, exc, _DB_BOOT_RETRY_DELAY,
                )
                time.sleep(_DB_BOOT_RETRY_DELAY)
            else:
                logger.error("Critical DB bootstrap failed after %d attempts: %s",
                             _DB_BOOT_MAX_RETRIES, exc)
        finally:
            if is_postgres:
                _release_postgres_bootstrap_lock(bootstrap_lock_conn)
    return False, False


def _bootstrap_db_post_init() -> None:
    """Run non-critical seed/cache work after schema is ready."""
    try:
        logger.info("Post-init bootstrap: full schema migration start")
        check_and_migrate_tables()
        logger.info("Post-init bootstrap: full schema migration complete")
    except Exception as exc:
        logger.warning("Post-init full schema migration failed: %s", exc)

    try:
        init_initial_data()
    except Exception as exc:
        logger.warning("Post-init data bootstrap failed: %s", exc)

    try:
        _warm_runtime_caches()
    except Exception as exc:
        logger.warning("Runtime cache warm failed after bootstrap: %s", exc)


_RUN_DB_BOOTSTRAP_ON_START = os.getenv("RUN_DB_BOOTSTRAP_ON_START", "1").strip().lower() in {"1", "true", "yes", "on"}
_RUN_GENERATION_QUEUE_WORKER_ON_START = os.getenv("RUN_GENERATION_QUEUE_WORKER_ON_START", "1").strip().lower() in {"1", "true", "yes", "on"}
_RUNTIME_DIAG_LOG_ENABLED = os.getenv("RUNTIME_DIAG_LOG_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
_RUNTIME_DIAG_HEARTBEAT_ENABLED = os.getenv("RUNTIME_DIAG_HEARTBEAT_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
_RUNTIME_DIAG_LOG_INTERVAL_SECONDS = max(15, int(os.getenv("RUNTIME_DIAG_LOG_INTERVAL_SECONDS", "60") or 60))
_RUNTIME_DIAG_HIGH_WATERMARK_MB = max(256, int(os.getenv("RUNTIME_DIAG_HIGH_WATERMARK_MB", "1400") or 1400))
_RUNTIME_DIAG_HIGH_WATERMARK_COOLDOWN_SECONDS = max(30, int(os.getenv("RUNTIME_DIAG_HIGH_WATERMARK_COOLDOWN_SECONDS", "180") or 180))
_RUNTIME_DIAG_STORE_SAMPLE_ITEMS = max(8, int(os.getenv("RUNTIME_DIAG_STORE_SAMPLE_ITEMS", "24") or 24))
_RUNTIME_DIAG_TRACEMALLOC_ENABLED = os.getenv("RUNTIME_DIAG_TRACEMALLOC_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
_RUNTIME_DIAG_TRACEMALLOC_FRAMES = max(5, int(os.getenv("RUNTIME_DIAG_TRACEMALLOC_FRAMES", "15") or 15))
_RUNTIME_DIAG_TRACEMALLOC_TOP = max(3, int(os.getenv("RUNTIME_DIAG_TRACEMALLOC_TOP", "8") or 8))


def _log_runtime_startup_profile() -> None:
    logger.info(
        "Runtime startup profile | pid=%s web_concurrency=%s gunicorn_timeout=%s gunicorn_graceful_timeout=%s gunicorn_keepalive=%s gunicorn_max_requests=%s gunicorn_max_requests_jitter=%s run_db_bootstrap=%s run_generation_queue_worker=%s generation_queue_worker_threads=%s runtime_diag_enabled=%s runtime_diag_interval_seconds=%s runtime_diag_high_watermark_mb=%s runtime_diag_high_watermark_cooldown_seconds=%s runtime_diag_store_sample_items=%s runtime_diag_tracemalloc_enabled=%s runtime_diag_tracemalloc_frames=%s runtime_diag_tracemalloc_top=%s",
        os.getpid(),
        os.getenv("WEB_CONCURRENCY", ""),
        os.getenv("GUNICORN_TIMEOUT", ""),
        os.getenv("GUNICORN_GRACEFUL_TIMEOUT", ""),
        os.getenv("GUNICORN_KEEPALIVE", ""),
        os.getenv("GUNICORN_MAX_REQUESTS", ""),
        os.getenv("GUNICORN_MAX_REQUESTS_JITTER", ""),
        _RUN_DB_BOOTSTRAP_ON_START,
        _RUN_GENERATION_QUEUE_WORKER_ON_START,
        os.getenv("GENERATION_QUEUE_WORKER_THREADS", ""),
        _RUNTIME_DIAG_LOG_ENABLED,
        _RUNTIME_DIAG_LOG_INTERVAL_SECONDS,
        _RUNTIME_DIAG_HIGH_WATERMARK_MB,
        _RUNTIME_DIAG_HIGH_WATERMARK_COOLDOWN_SECONDS,
        _RUNTIME_DIAG_STORE_SAMPLE_ITEMS,
        _RUNTIME_DIAG_TRACEMALLOC_ENABLED,
        _RUNTIME_DIAG_TRACEMALLOC_FRAMES,
        _RUNTIME_DIAG_TRACEMALLOC_TOP,
    )


def _read_linux_proc_status_metrics() -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    status_path = "/proc/self/status"
    if not os.path.exists(status_path):
        return metrics
    try:
        with open(status_path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    metrics["vmrss_kb"] = int(parts[1]) if len(parts) >= 2 else None
                elif line.startswith("VmSize:"):
                    parts = line.split()
                    metrics["vmsize_kb"] = int(parts[1]) if len(parts) >= 2 else None
                elif line.startswith("Threads:"):
                    parts = line.split()
                    metrics["proc_threads"] = int(parts[1]) if len(parts) >= 2 else None
        return metrics
    except Exception:
        return metrics


def _read_open_fd_count() -> int | None:
    fd_dir = "/proc/self/fd"
    if not os.path.isdir(fd_dir):
        return None
    try:
        return len(os.listdir(fd_dir))
    except Exception:
        return None


def _read_cgroup_memory_metrics() -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "cgroup_memory_current_bytes": None,
        "cgroup_memory_max_bytes": None,
        "cgroup_memory_events": {},
    }

    # Prefer cgroup v2 paths used by most modern container runtimes.
    memory_current_path = "/sys/fs/cgroup/memory.current"
    memory_max_path = "/sys/fs/cgroup/memory.max"
    memory_events_path = "/sys/fs/cgroup/memory.events"

    try:
        if os.path.exists(memory_current_path):
            raw = str(Path(memory_current_path).read_text(encoding="utf-8", errors="ignore") or "").strip()
            if raw and raw.isdigit():
                metrics["cgroup_memory_current_bytes"] = int(raw)
    except Exception:
        pass

    try:
        if os.path.exists(memory_max_path):
            raw = str(Path(memory_max_path).read_text(encoding="utf-8", errors="ignore") or "").strip()
            if raw and raw.lower() != "max" and raw.isdigit():
                metrics["cgroup_memory_max_bytes"] = int(raw)
            elif raw.lower() == "max":
                metrics["cgroup_memory_max_bytes"] = None
    except Exception:
        pass

    try:
        if os.path.exists(memory_events_path):
            events: Dict[str, int] = {}
            lines = Path(memory_events_path).read_text(encoding="utf-8", errors="ignore").splitlines()
            for line in lines:
                parts = str(line or "").strip().split()
                if len(parts) != 2:
                    continue
                key, raw_val = parts[0], parts[1]
                try:
                    events[str(key)] = int(raw_val)
                except Exception:
                    continue
            metrics["cgroup_memory_events"] = events
    except Exception:
        pass

    return metrics


def _read_generation_queue_snapshot() -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {
        "queued": 0,
        "running": 0,
        "failed": 0,
        "completed": 0,
        "canceled": 0,
        "oldest_queued_age_seconds": None,
    }
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT status, COUNT(*) AS cnt
                FROM generation_task_queue
                GROUP BY status
                """
            )
        ).mappings().all()
        for row in rows:
            status = str(row.get("status") or "").strip().lower()
            count = int(row.get("cnt") or 0)
            if status in snapshot:
                snapshot[status] = count

        oldest_queued_created_at = db.execute(
            text(
                """
                SELECT MIN(created_at) AS min_created_at
                FROM generation_task_queue
                WHERE status = 'queued'
                """
            )
        ).scalar()
        if oldest_queued_created_at is not None:
            snapshot["oldest_queued_age_seconds"] = max(
                0,
                int(time.time() - float(oldest_queued_created_at)),
            )
    except Exception:
        # Keep diagnostic logger non-intrusive if queue table is unavailable.
        pass
    finally:
        db.close()
    return snapshot


def _estimate_json_bytes(value: Any) -> int:
    try:
        payload = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        payload = str(value)
    return len(payload.encode("utf-8", errors="ignore"))


def _snapshot_dict_footprint(name: str, store: Any, lock: Any = None) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "name": str(name),
        "items": 0,
        "sample_items": 0,
        "sample_bytes": 0,
        "approx_total_bytes": 0,
    }

    try:
        if lock is not None:
            with lock:
                items = int(len(store)) if hasattr(store, "__len__") else 0
                sample_values = list(islice(getattr(store, "values")(), _RUNTIME_DIAG_STORE_SAMPLE_ITEMS)) if hasattr(store, "values") else []
        else:
            items = int(len(store)) if hasattr(store, "__len__") else 0
            sample_values = list(islice(getattr(store, "values")(), _RUNTIME_DIAG_STORE_SAMPLE_ITEMS)) if hasattr(store, "values") else []
    except Exception:
        return info

    sample_bytes = 0
    for value in sample_values:
        sample_bytes += _estimate_json_bytes(value)

    sample_count = len(sample_values)
    avg_bytes = int(sample_bytes / sample_count) if sample_count > 0 else 0
    approx_total = int(avg_bytes * items) if avg_bytes > 0 else 0
    info.update({
        "items": items,
        "sample_items": sample_count,
        "sample_bytes": sample_bytes,
        "approx_total_bytes": approx_total,
    })
    return info


def _collect_endpoint_store_footprints() -> List[Dict[str, Any]]:
    footprints: List[Dict[str, Any]] = []
    candidates = [
        ("image_job_store", getattr(endpoints, "IMAGE_JOB_STORE", None), getattr(endpoints, "IMAGE_JOB_LOCK", None)),
        ("video_job_store", getattr(endpoints, "VIDEO_JOB_STORE", None), getattr(endpoints, "VIDEO_JOB_LOCK", None)),
        ("generation_callback_store", getattr(endpoints, "GENERATION_CALLBACK_STORE", None), getattr(endpoints, "GENERATION_CALLBACK_LOCK", None)),
        ("generation_callback_async_inflight", getattr(endpoints, "GENERATION_CALLBACK_ASYNC_INFLIGHT", None), getattr(endpoints, "GENERATION_CALLBACK_ASYNC_INFLIGHT_LOCK", None)),
        ("generation_callback_no_match_cache", getattr(endpoints, "GENERATION_CALLBACK_NO_MATCH_LOG_CACHE", None), getattr(endpoints, "GENERATION_CALLBACK_NO_MATCH_LOG_LOCK", None)),
        ("webhook_replay_store", getattr(endpoints, "WEBHOOK_REPLAY_STORE", None), getattr(endpoints, "WEBHOOK_REPLAY_LOCK", None)),
        ("generation_job_pool_cache", getattr(endpoints, "_GENERATION_JOB_POOL_CACHE", None), getattr(endpoints, "_GENERATION_JOB_POOL_CACHE_LOCK", None)),
        ("analyze_scene_recent_tasks", getattr(endpoints, "_ANALYZE_SCENE_RECENT_TASKS", None), getattr(endpoints, "_ANALYZE_SCENE_RECENT_TASKS_LOCK", None)),
    ]

    for name, store, lock in candidates:
        if not isinstance(store, dict):
            continue
        footprints.append(_snapshot_dict_footprint(name, store, lock))

    footprints.sort(key=lambda item: int(item.get("approx_total_bytes") or 0), reverse=True)
    return footprints


def _collect_tracemalloc_top() -> List[Dict[str, Any]]:
    if not tracemalloc.is_tracing():
        return []
    try:
        snapshot = tracemalloc.take_snapshot()
        stats = snapshot.statistics("lineno")[:_RUNTIME_DIAG_TRACEMALLOC_TOP]
        out: List[Dict[str, Any]] = []
        for stat in stats:
            frame = stat.traceback[0] if stat.traceback else None
            out.append(
                {
                    "location": f"{getattr(frame, 'filename', '')}:{getattr(frame, 'lineno', 0)}" if frame else "",
                    "size_bytes": int(getattr(stat, "size", 0) or 0),
                    "count": int(getattr(stat, "count", 0) or 0),
                }
            )
        return out
    except Exception:
        return []


def _collect_high_memory_report(base_payload: Dict[str, Any]) -> Dict[str, Any]:
    report = {
        "pid": base_payload.get("pid"),
        "render_instance_id": base_payload.get("render_instance_id"),
        "process_started_unix_ts": base_payload.get("process_started_unix_ts"),
        "uptime_seconds": base_payload.get("uptime_seconds"),
        "vmrss_kb": base_payload.get("vmrss_kb"),
        "vmsize_kb": base_payload.get("vmsize_kb"),
        "open_fd": base_payload.get("open_fd"),
        "threads_active": base_payload.get("threads_active"),
        "cgroup_memory_current_bytes": base_payload.get("cgroup_memory_current_bytes"),
        "cgroup_memory_max_bytes": base_payload.get("cgroup_memory_max_bytes"),
        "cgroup_memory_events": base_payload.get("cgroup_memory_events") or {},
        "queue": base_payload.get("queue") or {},
        "store_footprints": _collect_endpoint_store_footprints(),
    }
    if _RUNTIME_DIAG_TRACEMALLOC_ENABLED:
        report["tracemalloc_top"] = _collect_tracemalloc_top()
    return report


def _collect_runtime_diag_payload() -> Dict[str, Any]:
    proc_metrics = _read_linux_proc_status_metrics()
    fd_count = _read_open_fd_count()
    queue_snapshot = _read_generation_queue_snapshot()
    cgroup_metrics = _read_cgroup_memory_metrics()
    now_ts = time.time()
    return {
        "pid": os.getpid(),
        "render_instance_id": str(os.getenv("RENDER_INSTANCE_ID") or ""),
        "process_started_unix_ts": int(_PROCESS_STARTED_UNIX_TS),
        "uptime_seconds": max(0, int(now_ts - _PROCESS_STARTED_UNIX_TS)),
        "threads_active": threading.active_count(),
        "proc_threads": proc_metrics.get("proc_threads"),
        "vmrss_kb": proc_metrics.get("vmrss_kb"),
        "vmsize_kb": proc_metrics.get("vmsize_kb"),
        "open_fd": fd_count,
        "cgroup_memory_current_bytes": cgroup_metrics.get("cgroup_memory_current_bytes"),
        "cgroup_memory_max_bytes": cgroup_metrics.get("cgroup_memory_max_bytes"),
        "cgroup_memory_events": cgroup_metrics.get("cgroup_memory_events") or {},
        "queue": queue_snapshot,
    }


async def _runtime_diag_log_loop(stop_event: asyncio.Event) -> None:
    last_high_watermark_log_at = 0.0
    watermark_kb = max(1, _RUNTIME_DIAG_HIGH_WATERMARK_MB) * 1024
    while not stop_event.is_set():
        try:
            payload = _collect_runtime_diag_payload()
            if _RUNTIME_DIAG_HEARTBEAT_ENABLED:
                logger.info("runtime.diag | %s", json.dumps(payload, ensure_ascii=False, default=str))

            vmrss_kb = int(payload.get("vmrss_kb") or 0)
            now_ts = time.time()
            if (
                vmrss_kb >= watermark_kb
                and (now_ts - last_high_watermark_log_at) >= _RUNTIME_DIAG_HIGH_WATERMARK_COOLDOWN_SECONDS
            ):
                high_report = _collect_high_memory_report(payload)
                logger.warning("runtime.diag.high | %s", json.dumps(high_report, ensure_ascii=False, default=str))
                last_high_watermark_log_at = now_ts
        except Exception as exc:
            logger.warning("runtime.diag collection failed: %s", exc)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=_RUNTIME_DIAG_LOG_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue


def _warm_runtime_caches() -> None:
    """Pre-read hot user/system-api rows into memory for faster first-hit routing."""
    try:
        user_count = warm_user_auth_cache_from_db()
        logger.info("Warm user auth cache done | users=%s", user_count)
    except Exception as exc:
        logger.warning("Warm user auth cache failed: %s", exc)

    try:
        api_count = warm_system_api_cache()
        logger.info("Warm system api cache done | rows=%s", api_count)
    except Exception as exc:
        logger.warning("Warm system api cache failed: %s", exc)

limiter = Limiter(key_func=get_remote_address)


class SelectiveGZipMiddleware(GZipMiddleware):
    def __init__(
        self,
        app,
        *args,
        excluded_path_prefixes: Iterable[str] = (),
        **kwargs,
    ):
        super().__init__(app, *args, **kwargs)
        self.excluded_path_prefixes: Tuple[str, ...] = tuple(excluded_path_prefixes or ())

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            path = str(scope.get("path") or "")
            if any(path.startswith(prefix) for prefix in self.excluded_path_prefixes):
                await self.app(scope, receive, send)
                return

            headers = {k.lower(): v for k, v in (scope.get("headers") or [])}
            if b"range" in headers:
                await self.app(scope, receive, send)
                return

        await super().__call__(scope, receive, send)


class UploadCacheControlMiddleware:
    def __init__(
        self,
        app,
        *,
        path_prefix: str = "/uploads/",
        cache_control: str = "",
    ):
        self.app = app
        self.path_prefix = str(path_prefix or "/uploads/")
        self.cache_control = str(cache_control or "").strip()

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method") or "").upper()
        path = str(scope.get("path") or "")
        if method not in {"GET", "HEAD"} or not path.startswith(self.path_prefix):
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers") or [])
                has_cache_control = any(k.lower() == b"cache-control" for k, _ in headers)
                has_accept_ranges = any(k.lower() == b"accept-ranges" for k, _ in headers)
                if self.cache_control and not has_cache_control:
                    headers.append((b"cache-control", self.cache_control.encode("latin-1", errors="ignore")))
                if not has_accept_ranges:
                    headers.append((b"accept-ranges", b"bytes"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_uvicorn_logging_noise_reduction()
    if _RUNTIME_DIAG_TRACEMALLOC_ENABLED and not tracemalloc.is_tracing():
        try:
            tracemalloc.start(_RUNTIME_DIAG_TRACEMALLOC_FRAMES)
            logger.info("Runtime diag tracemalloc enabled | frames=%s top=%s", _RUNTIME_DIAG_TRACEMALLOC_FRAMES, _RUNTIME_DIAG_TRACEMALLOC_TOP)
        except Exception as exc:
            logger.warning("Runtime diag tracemalloc enable failed: %s", exc)
    _log_runtime_startup_profile()
    runtime_diag_stop_event: asyncio.Event | None = None
    runtime_diag_task: asyncio.Task | None = None
    if _RUNTIME_DIAG_LOG_ENABLED:
        runtime_diag_stop_event = asyncio.Event()
        runtime_diag_task = asyncio.create_task(_runtime_diag_log_loop(runtime_diag_stop_event))
        logger.info("Runtime diag logger enabled | interval=%ss", _RUNTIME_DIAG_LOG_INTERVAL_SECONDS)
    else:
        logger.info("Runtime diag logger disabled")
    if _RUN_DB_BOOTSTRAP_ON_START:
        logger.info("Application startup: critical DB bootstrap enabled")
        schema_ready, should_run_post_init = await asyncio.to_thread(_bootstrap_db_schema)
        if not schema_ready:
            logger.error("Critical DB schema bootstrap did not complete successfully before serving requests")
            raise RuntimeError("Critical DB schema bootstrap failed")
        if should_run_post_init:
            asyncio.create_task(asyncio.to_thread(_bootstrap_db_post_init))
        logger.info("Application startup: critical DB bootstrap complete")
    else:
        logger.warning("RUN_DB_BOOTSTRAP_ON_START is disabled; skipping startup DB bootstrap")
    if _RUN_GENERATION_QUEUE_WORKER_ON_START:
        logger.info("Application startup: generation queue worker enabled in web process")
        await asyncio.to_thread(endpoints.start_generation_queue_worker)
    else:
        logger.info("Application startup: generation queue worker disabled in web process")
    try:
        yield
    finally:
        if runtime_diag_stop_event is not None:
            runtime_diag_stop_event.set()
        if runtime_diag_task is not None:
            try:
                await asyncio.wait_for(runtime_diag_task, timeout=3)
            except Exception:
                runtime_diag_task.cancel()
                try:
                    await runtime_diag_task
                except Exception:
                    pass


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(LoggingMiddleware)
app.add_middleware(
    SelectiveGZipMiddleware,
    minimum_size=settings.GZIP_MINIMUM_SIZE,
    excluded_path_prefixes=("/uploads", "/api/v1/agent/command/stream", "/api/v1/agent/system-management/command/stream"),
)
app.add_middleware(
    UploadCacheControlMiddleware,
    path_prefix="/uploads/",
    cache_control=settings.UPLOAD_CACHE_CONTROL,
)

# Ensure upload dir exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation Error: {exc.errors()}")
    try:
        raw_body = await request.body()
        logger.error(f"Body (truncated): {raw_body[:2048]}")
    except Exception:
        logger.error("Body: <unavailable>")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

# Global exception handler: ensure unhandled errors still carry CORS headers
# (Without this, RuntimeError etc. bypass CORSMiddleware and the browser blocks the response.)
@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    resp = JSONResponse(status_code=500, content={"detail": "Internal server error"})
    # CORSMiddleware may not reliably wrap exception-handler responses;
    # apply CORS headers explicitly so the browser can read the 500.
    origin = str(request.headers.get("origin") or "").strip()
    if origin:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Credentials"] = "true"
    return resp

# CORS configuration
origins = [item.strip() for item in (settings.CORS_ORIGINS or "").split(",") if item.strip()]
frontend_origin = (settings.FRONTEND_BASE_URL or "").strip()
if frontend_origin and frontend_origin not in origins:
    origins.append(frontend_origin)
render_frontend_origin = os.getenv("RENDER_FRONTEND_URL", "").strip()
if render_frontend_origin and render_frontend_origin not in origins:
    origins.append(render_frontend_origin)
default_render_frontend_origin = "https://aistory-frontend.onrender.com"
if default_render_frontend_origin not in origins:
    origins.append(default_render_frontend_origin)

for default_origin in ["https://www.woola.fun", "https://woola.fun"]:
    if default_origin not in origins:
        origins.append(default_origin)

if os.getenv("RENDER_EXTERNAL_URL"):
    render_origin = os.getenv("RENDER_EXTERNAL_URL").strip()
    if render_origin and render_origin not in origins:
        origins.append(render_origin)
if not origins:
    origins = ["http://localhost:3000", "http://localhost:5173"]

origin_regex = (settings.CORS_ALLOW_ORIGIN_REGEX or "").strip() or None
compiled_origin_regex = re.compile(origin_regex) if origin_regex else None

allow_credentials = True
if "*" in origins:
    allow_credentials = False

logger.info(
    "CORS initialized | allow_origins=%s allow_origin_regex=%s allow_credentials=%s",
    origins,
    origin_regex,
    allow_credentials,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=origin_regex,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


class _PrivateNetworkAccessMiddleware:
    """Wrap CORSMiddleware to handle Chrome Private Network Access (PNA) preflights.

    Chrome sends `Access-Control-Request-Private-Network: true` on cross-origin
    requests to IP spaces it considers private/unknown (Render falls into this).
    The server must echo `Access-Control-Allow-Private-Network: true` or Chrome
    blocks the request with ERR_FAILED / ERR_HTTP2_PROTOCOL_ERROR.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        pna_requested = (headers.get(b"access-control-request-private-network", b"") == b"true")

        if not pna_requested:
            await self.app(scope, receive, send)
            return

        async def send_with_pna(message):
            if message["type"] == "http.response.start":
                raw_headers = list(message.get("headers") or [])
                raw_headers.append((b"access-control-allow-private-network", b"true"))
                message = {**message, "headers": raw_headers}
            await send(message)

        await self.app(scope, receive, send_with_pna)


app.add_middleware(_PrivateNetworkAccessMiddleware)


def _origin_is_cors_allowed(origin: str) -> bool:
    candidate = str(origin or "").strip()
    if not candidate:
        return False
    if candidate in origins:
        return True
    if candidate.lower().startswith("https://") and candidate.lower().endswith(".onrender.com"):
        return True
    if compiled_origin_regex and compiled_origin_regex.match(candidate):
        return True
    return False


def _apply_cors_headers_to_response(request: Request, response: Response) -> Response:
    origin = str(request.headers.get("origin") or "").strip()
    if not _origin_is_cors_allowed(origin):
        return response

    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Credentials"] = "true" if allow_credentials else "false"
    response.headers["Access-Control-Allow-Methods"] = "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT"

    requested_headers = str(request.headers.get("access-control-request-headers") or "").strip()
    if requested_headers:
        response.headers["Access-Control-Allow-Headers"] = requested_headers
    else:
        response.headers["Access-Control-Allow-Headers"] = "*"

    if request.headers.get("access-control-request-private-network"):
        response.headers["Access-Control-Allow-Private-Network"] = "true"

    return response


class _CorsPreflightMiddleware:
    """Answer allowed CORS preflight requests before deeper middleware/auth layers.

    Some runtime error paths and outer ASGI middleware can still cause browsers to
    see missing CORS headers on OPTIONS. Short-circuiting valid preflights here
    keeps authenticated polling endpoints reachable from the frontend.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method") or "").upper()
        if method != "OPTIONS":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        origin = str(request.headers.get("origin") or "").strip()
        requested_method = str(request.headers.get("access-control-request-method") or "").strip()

        if not origin or not requested_method or not _origin_is_cors_allowed(origin):
            await self.app(scope, receive, send)
            return

        response = Response(status_code=204)
        response = _apply_cors_headers_to_response(request, response)
        await response(scope, receive, send)
        return


_MAINTENANCE_CATEGORY = "System_Maintenance"
_MAINTENANCE_PROVIDER = "maintenance_mode"
_MAINTENANCE_INTERCEPT_ENABLED = os.getenv("MAINTENANCE_INTERCEPT_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
_MAINTENANCE_CACHE_TTL_SECONDS = 5
_MAINTENANCE_DB_FAILURE_COOLDOWN_SECONDS = 60
_MAINTENANCE_DB_FAILURE_CIRCUIT_THRESHOLD = 2
_MAINTENANCE_DB_FAILURE_CIRCUIT_OPEN_SECONDS = 600
_maintenance_cache = {
    "checked_at": 0.0,
    "last_read_failed": False,
    "consecutive_failures": 0,
    "circuit_open_until": 0.0,
    "status": {
        "enabled": False,
        "is_active": False,
        "ends_at": None,
        "message": "系统正在维护",
    },
}


def _parse_iso_datetime_safe(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        normalized = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is not None:
            return dt.astimezone().replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _read_maintenance_status_from_db():
    try:
        with SessionLocal() as db:
            row = db.execute(text("""
                SELECT config
                FROM system_api_settings
                WHERE category = :category
                  AND provider = :provider
                ORDER BY id DESC
                LIMIT 1
            """), {
                "category": _MAINTENANCE_CATEGORY,
                "provider": _MAINTENANCE_PROVIDER,
            }).mappings().first()

            cfg_raw = row.get("config") if row else None
            if isinstance(cfg_raw, dict):
                cfg = dict(cfg_raw)
            elif isinstance(cfg_raw, str) and cfg_raw.strip():
                try:
                    parsed = json.loads(cfg_raw)
                    cfg = dict(parsed) if isinstance(parsed, dict) else {}
                except Exception:
                    cfg = {}
            else:
                cfg = {}

            enabled = bool(cfg.get("enabled", False))
            ends_at = str(cfg.get("ends_at") or "").strip() or None
            message = str(cfg.get("message") or "").strip() or "系统正在维护"

            ends_at_dt = _parse_iso_datetime_safe(ends_at)
            is_active = bool(enabled and (not ends_at_dt or datetime.utcnow() < ends_at_dt))

            return {
                "enabled": enabled,
                "is_active": is_active,
                "ends_at": ends_at,
                "message": message,
            }, False
    except Exception as e:
        logger.warning("Failed to read maintenance status: %s", e)
        return {
            "enabled": False,
            "is_active": False,
            "ends_at": None,
            "message": "系统正在维护",
        }, True


def _get_maintenance_status_cached(force: bool = False):
    now = time.time()
    if not force and now < float(_maintenance_cache.get("circuit_open_until", 0.0)):
        return _maintenance_cache["status"]

    cached_ttl = (
        _MAINTENANCE_DB_FAILURE_COOLDOWN_SECONDS
        if bool(_maintenance_cache.get("last_read_failed", False))
        else _MAINTENANCE_CACHE_TTL_SECONDS
    )
    if force or (now - float(_maintenance_cache.get("checked_at", 0.0))) > cached_ttl:
        status, read_failed = _read_maintenance_status_from_db()
        _maintenance_cache["status"] = status
        _maintenance_cache["last_read_failed"] = read_failed
        if read_failed:
            failures = int(_maintenance_cache.get("consecutive_failures", 0)) + 1
            _maintenance_cache["consecutive_failures"] = failures
            if failures >= _MAINTENANCE_DB_FAILURE_CIRCUIT_THRESHOLD:
                _maintenance_cache["circuit_open_until"] = now + _MAINTENANCE_DB_FAILURE_CIRCUIT_OPEN_SECONDS
        else:
            _maintenance_cache["consecutive_failures"] = 0
            _maintenance_cache["circuit_open_until"] = 0.0
        _maintenance_cache["checked_at"] = now
    return _maintenance_cache["status"]


def _is_superuser_request(request: Request) -> bool:
    auth = str(request.headers.get("authorization") or "")
    if not auth.lower().startswith("bearer "):
        return False

    token = auth.split(" ", 1)[1].strip()
    if not token:
        return False

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return False

    if bool(payload.get("is_superuser") or payload.get("superuser")):
        return True

    uid = payload.get("uid")
    username = str(payload.get("uname") or payload.get("sub") or "").strip()

    try:
        with SessionLocal() as db:
            user = None
            if uid is not None:
                try:
                    user = db.query(User).filter(User.id == int(uid)).first()
                except Exception:
                    user = None
            if not user and username:
                user = db.query(User).filter(User.username == username).first()
            return bool(user and bool(getattr(user, "is_superuser", False)))
    except Exception:
        return False


class _MaintenanceModeMiddleware:
    """Pure ASGI middleware for maintenance mode (replaces @app.middleware('http') to avoid
    BaseHTTPMiddleware deadlock with SSE StreamingResponse)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        if not _MAINTENANCE_INTERCEPT_ENABLED:
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path") or "")
        method = str(scope.get("method") or "").upper()

        # OPTIONS bypass
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        api_prefix = str(settings.API_V1_STR or "")
        exempt_paths = {
            "/",
            "/healthz",
            f"{api_prefix}/admin/maintenance-status",
            f"{api_prefix}/admin/maintenance-config",
            f"{api_prefix}/login",
            f"{api_prefix}/login/access-token",
        }

        if path in exempt_paths:
            await self.app(scope, receive, send)
            return

        status = _get_maintenance_status_cached()
        if not bool(status.get("is_active", False)):
            await self.app(scope, receive, send)
            return

        # Check superuser from token in headers
        raw_headers = dict(scope.get("headers") or [])
        auth_header = raw_headers.get(b"authorization", b"")
        if isinstance(auth_header, bytes):
            auth_header = auth_header.decode("utf-8", errors="replace")
        request = Request(scope, receive=receive)
        if auth_header and _is_superuser_request(request):
            await self.app(scope, receive, send)
            return

        # Block with 503
        detail = str(status.get("message") or "系统正在维护")
        import json as _json
        body = _json.dumps({
            "detail": detail,
            "maintenance": {
                "enabled": bool(status.get("enabled", False)),
                "is_active": True,
                "ends_at": status.get("ends_at"),
            },
        }, ensure_ascii=False).encode("utf-8")

        # Build CORS headers
        origin = ""
        raw_origin = raw_headers.get(b"origin", b"")
        if isinstance(raw_origin, bytes):
            origin = raw_origin.decode("utf-8", errors="replace")
        resp_headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ]
        if origin and _origin_is_cors_allowed(origin):
            resp_headers.append((b"access-control-allow-origin", origin.encode()))
            resp_headers.append((b"vary", b"Origin"))
            resp_headers.append((b"access-control-allow-credentials", b"true" if allow_credentials else b"false"))

        await send({"type": "http.response.start", "status": 503, "headers": resp_headers})
        await send({"type": "http.response.body", "body": body})


class _SecurityHeadersMiddleware:
    """Pure ASGI middleware for security headers (replaces @app.middleware('http') to avoid
    BaseHTTPMiddleware deadlock with SSE StreamingResponse)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or not settings.SECURITY_HEADERS_ENABLED:
            await self.app(scope, receive, send)
            return

        is_https = (scope.get("scheme") == "https")

        async def send_with_security_headers(message):
            if message.get("type") == "http.response.start":
                raw_headers = list(message.get("headers") or [])
                raw_headers.append((b"x-content-type-options", b"nosniff"))
                raw_headers.append((b"x-frame-options", b"DENY"))
                raw_headers.append((b"referrer-policy", b"strict-origin-when-cross-origin"))
                raw_headers.append((b"permissions-policy", b"camera=(), microphone=(), geolocation=()"))
                if is_https:
                    raw_headers.append((b"strict-transport-security",
                                        f"max-age={settings.SECURITY_HSTS_SECONDS}; includeSubDomains".encode()))
                message = {**message, "headers": raw_headers}
            await send(message)

        await self.app(scope, receive, send_with_security_headers)


if _MAINTENANCE_INTERCEPT_ENABLED:
    app.add_middleware(_MaintenanceModeMiddleware)
else:
    logger.warning("MAINTENANCE_INTERCEPT_ENABLED is disabled; skipping maintenance interception")
app.add_middleware(_SecurityHeadersMiddleware)
app.add_middleware(_CorsPreflightMiddleware)

import os
from fastapi.responses import FileResponse, HTMLResponse

app.include_router(endpoints.router, prefix=settings.API_V1_STR)
app.include_router(settings_api.router, prefix=settings.API_V1_STR)
app.include_router(groups_api.router, prefix=settings.API_V1_STR)
app.include_router(invoices_api.router, prefix=settings.API_V1_STR + "/invoices", tags=["invoices"])
app.include_router(invoices_api.router, prefix=settings.API_V1_STR + "/invoices", tags=["invoices"])

# --- 静态 SPA (React Vite) 前端挂载配置 ---
# Vite 建立的 Dist 目录通常在这个路径（基于 Dockerfile 第阶段配置）
_FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")

if os.path.isdir(_FRONTEND_DIST):
    # 挂载除 API 外的所有静态资源 (js, css, assets 等)
    app.mount("/assets", StaticFiles(directory=os.path.join(_FRONTEND_DIST, "assets")), name="frontend-assets")
    
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa_frontend(full_path: str):
        # 排除对 /api/v1/ 的前端拦截，将它留给正经的 API Router 处理
        if full_path.startswith(settings.API_V1_STR.lstrip('/')):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
            
        file_path = os.path.join(_FRONTEND_DIST, full_path)
        # 如果命中了具体的静态文件诸如 favicon.ico，则返回它
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
            
        # 否则所有的前端路由（/about, /user）全部还给 React 的 index.html 自己去识别
        index_file = os.path.join(_FRONTEND_DIST, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file)
        return HTMLResponse("<h1>Frontend dist/index.html not found!</h1>", status_code=404)
else:
    @app.get("/")
    def root():
        return {"message": "Welcome to AI Story API (Frontend Not Built)"}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post(f"{settings.API_V1_STR}/diag/post-ping")
async def diag_post_ping(request: Request):
    body = await request.body()
    content_type = str(request.headers.get("content-type") or "").strip() or None
    user_agent = str(request.headers.get("user-agent") or "").strip() or None
    preview = body[:120].decode("utf-8", errors="replace") if body else ""
    logger.info(
        "diag.post_ping | content_type=%s body_len=%s preview=%s",
        content_type,
        len(body),
        preview.replace("\n", "\\n"),
    )
    return {
        "ok": True,
        "content_type": content_type,
        "body_len": len(body),
        "body_preview": preview,
        "user_agent": user_agent,
    }

if __name__ == "__main__":
    import uvicorn
    # Use import string to enable reload
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
