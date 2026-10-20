
import logging
import re as _re
import threading
import time as _time
import traceback
from collections import Counter

from sqlalchemy import create_engine, event
from sqlalchemy.exc import TimeoutError as SATimeoutError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from app.core.config import settings

_logger = logging.getLogger(__name__)

is_sqlite = "sqlite" in settings.DATABASE_URL
_is_postgres = "postgresql" in settings.DATABASE_URL

_effective_pool_size = int(settings.DB_POOL_SIZE or 0)
_effective_max_overflow = int(settings.DB_MAX_OVERFLOW or 0)
if not is_sqlite and _is_postgres:
    # Guard against legacy low pool values that frequently cause QueuePool timeouts
    # under moderate concurrency on Render.
    if _effective_pool_size < 8:
        _effective_pool_size = 8
    if _effective_max_overflow < 16:
        _effective_max_overflow = 16

# Export effective pool values so other modules can make decisions based on
# the real runtime pool configuration instead of raw env/config values.
DB_POOL_SIZE_EFFECTIVE = _effective_pool_size
DB_MAX_OVERFLOW_EFFECTIVE = _effective_max_overflow
DB_POOL_CAPACITY_EFFECTIVE = DB_POOL_SIZE_EFFECTIVE + DB_MAX_OVERFLOW_EFFECTIVE

# Raw psycopg2 opener used by the engine creator and by out-of-pool callers
# (e.g. startup advisory locks that must survive pool invalidation).
_connect_raw_postgres_impl = None

_pool_holders_lock = threading.Lock()
_pool_holders: dict[int, str] = {}
_pool_timeout_log_at = 0.0


def _checkout_caller_label() -> str:
    """First application frame that asked the pool for a connection."""
    stack = traceback.extract_stack(limit=28)
    for frame in reversed(stack[:-2]):
        path = str(frame.filename or "").replace("\\", "/")
        if "/site-packages/" in path or path.endswith("/app/db/session.py"):
            continue
        marker = "/backend/"
        idx = path.find(marker)
        short = path[idx + 1:] if idx >= 0 else path
        return f"{short}:{frame.lineno}:{frame.name}"
    return "unknown"


def _log_pool_holders(reason: str) -> None:
    with _pool_holders_lock:
        holders = list(_pool_holders.values())
    counts = Counter(holders)
    top = ", ".join(f"{label} x{count}" for label, count in counts.most_common(12))
    _logger.error(
        "DB pool %s | holders=%s unique=%s top=%s",
        reason,
        len(holders),
        len(counts),
        top or "-",
    )


class _DiagnosingQueuePool(QueuePool):
    """Log who still holds connections when a checkout times out."""

    def _do_get(self):
        global _pool_timeout_log_at
        try:
            return super()._do_get()
        except SATimeoutError:
            now = _time.time()
            if now - _pool_timeout_log_at >= 5:
                _pool_timeout_log_at = now
                _log_pool_holders("checkout_timeout")
            raise

engine_kwargs = {
    "connect_args": {"check_same_thread": False, "timeout": 30} if is_sqlite else {},
}

if not is_sqlite:
    _connect_args = {}
    # TCP keepalive for PostgreSQL to detect dead connections faster
    if "postgresql" in settings.DATABASE_URL:
        _connect_args.update({
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
            # Bound TCP connect. The creator runs while an overflow slot is
            # already reserved; an unbounded connect pins that slot and the
            # next checkout raises QueuePool timeout (size+overflow reached).
            "connect_timeout": 5,
        })
    engine_kwargs.update({
        "pool_pre_ping": settings.DB_POOL_PRE_PING,
        "pool_size": _effective_pool_size,
        "max_overflow": _effective_max_overflow,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_recycle": settings.DB_POOL_RECYCLE,
        "pool_use_lifo": True,
        "pool_reset_on_return": "rollback",
        "connect_args": _connect_args,
    })

    # Retry connection creation on transient errors (DNS failures, connection refused)
    # Falls back to external DB URL if internal DNS keeps failing.
    if "postgresql" in settings.DATABASE_URL:
        import psycopg2 as _psycopg2
        from urllib.parse import urlparse as _urlparse, urlunparse as _urlunparse

        # Build DSN usable by psycopg2 (strip SQLAlchemy dialect suffix)
        _raw_dsn = _re.sub(
            r"^postgres(ql)?(\+psycopg2)?://", "postgresql://", settings.DATABASE_URL
        )

        # Build external fallback DSN: explicit env var or auto-derive from internal
        _ext_fallbacks = []
        if settings.DATABASE_URL_EXTERNAL:
            _ext_fallbacks = [_re.sub(
                r"^postgres(ql)?(\+psycopg2)?://", "postgresql://",
                settings.DATABASE_URL_EXTERNAL,
            )]
        else:
            # Auto-derive: Render internal hostnames like "dpg-xxx-a" become
            # "dpg-xxx-a.region-postgres.render.com" externally.
            _parsed = _urlparse(_raw_dsn)
            _host = _parsed.hostname or ""
            if _re.match(r"^dpg-[a-z0-9]+-[a-z]$", _host):
                _RENDER_REGIONS = ["oregon", "ohio", "frankfurt", "singapore"]
                _ext_fallbacks = [
                    _urlunparse(_parsed._replace(
                        netloc=_parsed.netloc.replace(_host, f"{_host}.{r}-postgres.render.com", 1)
                    ))
                    for r in _RENDER_REGIONS
                ]
                _logger.info("Auto-derived %d external DB URL candidates from internal host %s",
                             len(_ext_fallbacks), _host)

        _MAX_CONNECT_RETRIES = 2
        _CONNECT_RETRY_DELAYS = [0.4]

        def _is_dns_connect_error(exc: BaseException) -> bool:
            text = str(exc or "").lower()
            return any(
                needle in text
                for needle in (
                    "could not translate host",
                    "name or service not known",
                    "nodename nor servname",
                    "temporary failure in name resolution",
                    "getaddrinfo failed",
                )
            )

        def _connect_with_retry():
            last_err = None
            for _attempt in range(_MAX_CONNECT_RETRIES):
                try:
                    return _psycopg2.connect(_raw_dsn, **_connect_args)
                except _psycopg2.OperationalError as exc:
                    last_err = exc
                    if _attempt < _MAX_CONNECT_RETRIES - 1 and _is_dns_connect_error(exc):
                        delay = _CONNECT_RETRY_DELAYS[_attempt]
                        _logger.warning(
                            "DB connect attempt %d/%d failed: %s — retrying in %ss",
                            _attempt + 1, _MAX_CONNECT_RETRIES, exc, delay,
                        )
                        _time.sleep(delay)
                        continue
                    break

            # External URL only for internal DNS failure. Other errors (too many
            # connections, refused, timeout) must release the overflow slot now.
            if last_err is not None and _is_dns_connect_error(last_err):
                for _ext_url in _ext_fallbacks:
                    try:
                        _logger.warning(
                            "Internal DB DNS failed, trying external URL fallback",
                        )
                        return _psycopg2.connect(_ext_url, **_connect_args)
                    except _psycopg2.OperationalError as exc:
                        last_err = exc
                        if not _is_dns_connect_error(exc):
                            break
                        continue
            raise last_err

        _connect_raw_postgres_impl = _connect_with_retry
        engine_kwargs["creator"] = _connect_with_retry
        engine_kwargs["poolclass"] = _DiagnosingQueuePool
        # connect_args already baked into the creator; remove to avoid confusion
        engine_kwargs.pop("connect_args", None)

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)


def connect_raw_postgres():
    """Open a psycopg2 connection outside the SQLAlchemy pool.

    Use this for session-level advisory locks held across unrelated pool work.
    Pool invalidation must not close the lock-holding connection.
    """
    if _connect_raw_postgres_impl is None:
        raise RuntimeError("connect_raw_postgres requires a postgresql DATABASE_URL")
    return _connect_raw_postgres_impl()

if not is_sqlite:
    _logger.info(
        "DB pool configured | size=%s overflow=%s timeout=%ss recycle=%ss pre_ping=%s lifo=%s",
        _effective_pool_size,
        _effective_max_overflow,
        settings.DB_POOL_TIMEOUT,
        settings.DB_POOL_RECYCLE,
        settings.DB_POOL_PRE_PING,
        True,
    )
    if _effective_pool_size != int(settings.DB_POOL_SIZE or 0) or _effective_max_overflow != int(settings.DB_MAX_OVERFLOW or 0):
        _logger.warning(
            "DB pool values auto-adjusted for stability | configured_size=%s configured_overflow=%s effective_size=%s effective_overflow=%s",
            settings.DB_POOL_SIZE,
            settings.DB_MAX_OVERFLOW,
            _effective_pool_size,
            _effective_max_overflow,
        )
    if _effective_pool_size <= 5:
        _logger.warning(
            "DB_POOL_SIZE=%s is low for concurrent traffic and may cause QueuePool timeouts",
            _effective_pool_size,
        )

_pool_stats_lock = threading.Lock()
_pool_checked_out = 0
_pool_last_warn_at = 0.0


def get_pool_checkout_stats() -> dict:
    """Best-effort pool occupancy snapshot for ops / diagnostics."""
    stats = {
        "checked_out_estimate": _pool_checked_out,
        "pool_size": _effective_pool_size,
        "max_overflow": _effective_max_overflow,
        "capacity": DB_POOL_CAPACITY_EFFECTIVE,
        "pool_status": None,
    }
    if is_sqlite:
        return stats
    try:
        stats["pool_status"] = engine.pool.status()
        checkedout = getattr(engine.pool, "checkedout", None)
        if callable(checkedout):
            stats["pool_checkedout"] = int(checkedout())
        overflow = getattr(engine.pool, "overflow", None)
        if callable(overflow):
            stats["pool_overflow"] = int(overflow())
    except Exception as exc:
        stats["pool_status_error"] = str(exc)
    return stats


# Enable WAL mode for SQLite to allow concurrent read/write access.
# Without WAL, a long-lived read transaction (e.g. streaming SSE) holds a
# SHARED lock that blocks ALL write operations from other connections.
if is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_wal(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

# SQLAlchemy 2.0: disconnects invalidate via is_disconnect / invalidate_pool_on_disconnect
# (ExceptionContext has no invalidate_connection attribute).
@event.listens_for(engine, "handle_error")
def _handle_db_error(context):
    if context.is_disconnect:
        context.invalidate_pool_on_disconnect = True


@event.listens_for(engine.pool, "checkout")
def _on_pool_checkout(dbapi_con, con_record, con_proxy):
    global _pool_checked_out, _pool_last_warn_at
    if is_sqlite:
        return

    now = _time.time()
    caller = _checkout_caller_label()
    with _pool_holders_lock:
        _pool_holders[id(con_record)] = caller
    with _pool_stats_lock:
        _pool_checked_out += 1
        checked_out = _pool_checked_out

    high_watermark = _effective_pool_size + _effective_max_overflow - 2
    if high_watermark > 0 and checked_out >= high_watermark and now - _pool_last_warn_at >= 10:
        _pool_last_warn_at = now
        pool_status = None
        try:
            pool_status = engine.pool.status()
        except Exception:
            pool_status = None
        with _pool_holders_lock:
            holder_counts = Counter(_pool_holders.values())
        top = ", ".join(f"{label} x{count}" for label, count in holder_counts.most_common(8))
        _logger.warning(
            "DB pool near capacity | checked_out=%s threshold=%s size=%s overflow=%s capacity=%s pool_status=%s "
            "| holders=%s | tip=hold sessions only for SQL; release before LLM/OSS/network waits",
            checked_out,
            high_watermark,
            _effective_pool_size,
            _effective_max_overflow,
            DB_POOL_CAPACITY_EFFECTIVE,
            pool_status,
            top or "-",
        )


@event.listens_for(engine.pool, "checkin")
def _on_pool_checkin(dbapi_con, con_record):
    global _pool_checked_out
    if is_sqlite:
        return

    with _pool_holders_lock:
        _pool_holders.pop(id(con_record), None)
    with _pool_stats_lock:
        _pool_checked_out = max(0, _pool_checked_out - 1)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
