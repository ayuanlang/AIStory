
import logging
import re as _re
import time as _time

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

_logger = logging.getLogger(__name__)

is_sqlite = "sqlite" in settings.DATABASE_URL

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
        })
    engine_kwargs.update({
        "pool_pre_ping": settings.DB_POOL_PRE_PING,
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_recycle": settings.DB_POOL_RECYCLE,
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

        _MAX_CONNECT_RETRIES = 6
        _CONNECT_RETRY_DELAYS = [1, 2, 3, 4, 5]  # total ~15s

        def _connect_with_retry():
            last_err = None
            for _attempt in range(_MAX_CONNECT_RETRIES):
                try:
                    return _psycopg2.connect(_raw_dsn, **_connect_args)
                except _psycopg2.OperationalError as exc:
                    last_err = exc
                    if _attempt < _MAX_CONNECT_RETRIES - 1:
                        delay = _CONNECT_RETRY_DELAYS[_attempt]
                        _logger.warning(
                            "DB connect attempt %d/%d failed: %s — retrying in %ds",
                            _attempt + 1, _MAX_CONNECT_RETRIES, exc, delay,
                        )
                        _time.sleep(delay)

            # All internal retries exhausted — try external URL(s) as fallback
            for _ext_url in _ext_fallbacks:
                try:
                    _logger.warning("Internal DB DNS failed %d times, trying external URL fallback",
                                    _MAX_CONNECT_RETRIES)
                    return _psycopg2.connect(_ext_url, **_connect_args)
                except _psycopg2.OperationalError:
                    continue
            raise last_err

        engine_kwargs["creator"] = _connect_with_retry
        # connect_args already baked into the creator; remove to avoid confusion
        engine_kwargs.pop("connect_args", None)

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

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

# Invalidate connections on disconnect errors so the pool discards them
@event.listens_for(engine, "handle_error")
def _handle_db_error(context):
    if context.connection is not None and context.is_disconnect:
        context.invalidate_connection = True
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
