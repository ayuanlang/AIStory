
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
    "connect_args": {"check_same_thread": False} if is_sqlite else {},
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
    if "postgresql" in settings.DATABASE_URL:
        import psycopg2 as _psycopg2

        # Build DSN usable by psycopg2 (strip SQLAlchemy dialect suffix)
        _raw_dsn = _re.sub(
            r"^postgres(ql)?(\+psycopg2)?://", "postgresql://", settings.DATABASE_URL
        )
        _MAX_CONNECT_RETRIES = 5
        _CONNECT_RETRY_DELAY = 2.0  # seconds

        def _connect_with_retry():
            last_err = None
            for _attempt in range(_MAX_CONNECT_RETRIES):
                try:
                    return _psycopg2.connect(_raw_dsn, **_connect_args)
                except _psycopg2.OperationalError as exc:
                    last_err = exc
                    if _attempt < _MAX_CONNECT_RETRIES - 1:
                        _logger.warning(
                            "DB connect attempt %d/%d failed: %s — retrying in %.1fs",
                            _attempt + 1, _MAX_CONNECT_RETRIES, exc,
                            _CONNECT_RETRY_DELAY,
                        )
                        _time.sleep(_CONNECT_RETRY_DELAY)
            raise last_err

        engine_kwargs["creator"] = _connect_with_retry
        # connect_args already baked into the creator; remove to avoid confusion
        engine_kwargs.pop("connect_args", None)

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

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
