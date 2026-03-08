
from contextlib import asynccontextmanager
from typing import Iterable, Tuple
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, Response
from app.core.config import settings
from app.api import endpoints, settings as settings_api
from app.db.session import engine, SessionLocal
from app.models.all_models import Base, SystemAPISetting, User
from app.core.logging import LoggingMiddleware, logger, configure_uvicorn_logging_noise_reduction
from app.db.init_db import check_and_migrate_tables, create_default_superuser, init_initial_data
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


def _bootstrap_db():
    """Run DB schema creation, migrations and seed data with retry."""
    for _attempt in range(1, _DB_BOOT_MAX_RETRIES + 1):
        try:
            Base.metadata.create_all(bind=engine)
            check_and_migrate_tables()
            create_default_superuser()
            init_initial_data()
            return  # success
        except Exception as exc:
            if _attempt < _DB_BOOT_MAX_RETRIES:
                logger.warning(
                    "DB bootstrap attempt %d/%d failed: %s — retrying in %ds",
                    _attempt, _DB_BOOT_MAX_RETRIES, exc, _DB_BOOT_RETRY_DELAY,
                )
                time.sleep(_DB_BOOT_RETRY_DELAY)
            else:
                logger.error("DB bootstrap failed after %d attempts, starting anyway: %s",
                             _DB_BOOT_MAX_RETRIES, exc)


_bootstrap_db()

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_uvicorn_logging_noise_reduction()
    yield


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(LoggingMiddleware)
app.add_middleware(
    SelectiveGZipMiddleware,
    minimum_size=settings.GZIP_MINIMUM_SIZE,
    excluded_path_prefixes=("/uploads", "/api/v1/agent/command/stream", "/api/v1/agent/system-management/command/stream"),
)

# Ensure upload dir exists
import os
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


_MAINTENANCE_CATEGORY = "System_Maintenance"
_MAINTENANCE_PROVIDER = "maintenance_mode"
_MAINTENANCE_CACHE_TTL_SECONDS = 5
_maintenance_cache = {
    "checked_at": 0.0,
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
            row = db.query(SystemAPISetting).filter(
                SystemAPISetting.category == _MAINTENANCE_CATEGORY,
                SystemAPISetting.provider == _MAINTENANCE_PROVIDER,
            ).order_by(SystemAPISetting.id.desc()).first()
            cfg = dict(row.config or {}) if row else {}

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
            }
    except Exception as e:
        logger.warning("Failed to read maintenance status: %s", e)
        return {
            "enabled": False,
            "is_active": False,
            "ends_at": None,
            "message": "系统正在维护",
        }


def _get_maintenance_status_cached(force: bool = False):
    now = time.time()
    if force or (now - float(_maintenance_cache.get("checked_at", 0.0))) > _MAINTENANCE_CACHE_TTL_SECONDS:
        _maintenance_cache["status"] = _read_maintenance_status_from_db()
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


app.add_middleware(_MaintenanceModeMiddleware)
app.add_middleware(_SecurityHeadersMiddleware)

app.include_router(endpoints.router, prefix=settings.API_V1_STR)
app.include_router(settings_api.router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": "Welcome to AI Story API"}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    # Use import string to enable reload
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
