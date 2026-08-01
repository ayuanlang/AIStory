
import logging
import os
import time
import re
import json
import sys
import threading
from collections import Counter
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Dict, Optional
from fastapi import Request
from starlette.types import ASGIApp, Scope, Receive, Send
from jose import jwt, JWTError
from app.core.config import settings

# Successful estimate/video hits are noisy; log at most once per interval (kept for OOM debugging).
_BILLING_ESTIMATE_LOG_MIN_INTERVAL_SECONDS = max(
    5.0,
    float(os.getenv("BILLING_ESTIMATE_LOG_MIN_INTERVAL_SECONDS", "30") or 30),
)
_billing_estimate_log_state = {"last_at": 0.0, "suppressed": 0}

# Lightweight path traffic summary (explains gunicorn max-requests burn without API Result spam).
_REQUEST_TRAFFIC_LOG_ENABLED = os.getenv("REQUEST_TRAFFIC_LOG_ENABLED", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_REQUEST_TRAFFIC_LOG_INTERVAL_SECONDS = max(
    15.0,
    float(os.getenv("REQUEST_TRAFFIC_LOG_INTERVAL_SECONDS", "60") or 60),
)
_REQUEST_TRAFFIC_LOG_TOP = max(5, min(40, int(os.getenv("REQUEST_TRAFFIC_LOG_TOP", "15") or 15)))
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_HEX_TOKEN_RE = re.compile(r"/[0-9a-fA-F]{16,}(?=/|$)")
_NUMERIC_ID_RE = re.compile(r"/\d+(?=/|$)")
_traffic_lock = threading.Lock()
_traffic_window_paths: Counter = Counter()
_traffic_window_categories: Counter = Counter()
_traffic_lifetime_total = 0
_traffic_window_started_at = time.time()
_traffic_last_flush_at = time.time()

# Configure standard loggers to be less noisy
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.ERROR)
logging.getLogger("fastapi").setLevel(logging.WARNING)


class _SuppressUvicornAccessUploads(logging.Filter):
    _req_re = re.compile(r'"(GET|HEAD)\s+/uploads/[^\s]*\s+HTTP/')
    _status_re = re.compile(r'"\s+(\d{3})\s+')

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        # Keep non-upload traffic untouched.
        if self._req_re.search(msg) is None:
            return True

        # For /uploads access logs, suppress only successful 2xx lines.
        # Keep 3xx/4xx/5xx lines so image loading failures remain visible.
        status_match = self._status_re.search(msg)
        if not status_match:
            return True
        try:
            status_code = int(status_match.group(1))
        except Exception:
            return True
        return not (200 <= status_code < 300)


class _ResilientStreamHandler(logging.StreamHandler):
    """Best-effort console logging for debugger/Windows console environments.

    Some runtimes attach stream handlers whose underlying stream can be closed or
    use a code page that cannot encode log text. Logging should never crash a
    background worker because of that transport issue.
    """

    def emit(self, record: logging.LogRecord) -> None:
        message = None
        try:
            message = self.format(record) + self.terminator
            stream = self.stream
            if stream is not None and not getattr(stream, "closed", False):
                try:
                    stream.write(message)
                except UnicodeEncodeError:
                    buffer = getattr(stream, "buffer", None)
                    if buffer is None:
                        raise
                    buffer.write(message.encode("utf-8", errors="backslashreplace"))
                stream.flush()
                return

            fallback = getattr(sys, "__stderr__", None) or getattr(sys, "stderr", None)
            if fallback is None or getattr(fallback, "closed", False):
                return
            fallback_buffer = getattr(fallback, "buffer", None)
            if fallback_buffer is not None:
                fallback_buffer.write(message.encode("utf-8", errors="backslashreplace"))
                fallback_buffer.flush()
            else:
                fallback.write(message.encode("ascii", errors="backslashreplace").decode("ascii"))
                fallback.flush()
        except Exception:
            # Swallow logging transport failures entirely; background task health
            # is more important than emitting this one line to console.
            return


def _patch_logger_stream_handlers(target_logger: logging.Logger) -> None:
    for index, existing_handler in enumerate(list(target_logger.handlers)):
        if not isinstance(existing_handler, logging.StreamHandler):
            continue
        if isinstance(existing_handler, _ResilientStreamHandler):
            continue

        replacement = _ResilientStreamHandler(getattr(existing_handler, "stream", None))
        replacement.setLevel(existing_handler.level)
        replacement.setFormatter(existing_handler.formatter)
        for existing_filter in list(existing_handler.filters):
            replacement.addFilter(existing_filter)
        target_logger.handlers[index] = replacement


def _ensure_resilient_console_logging() -> None:
    for logger_name in (None, "uvicorn", "uvicorn.error", "uvicorn.access"):
        current_logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()
        _patch_logger_stream_handlers(current_logger)


def configure_uvicorn_logging_noise_reduction() -> None:
    """Reduce meaningless uvicorn access log noise.

    Uvicorn may override logger levels via its own log_config after module import,
    so call this at app startup to ensure it takes effect.
    """
    _ensure_resilient_console_logging()

    access_logger = logging.getLogger("uvicorn.access")
    access_logger.setLevel(logging.WARNING)

    if not any(isinstance(f, _SuppressUvicornAccessUploads) for f in access_logger.filters):
        access_logger.addFilter(_SuppressUvicornAccessUploads())

logger = logging.getLogger("functional_activity")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
logger.addHandler(handler)


def _ensure_runtime_info_file_logging() -> None:
    try:
        base_dir = Path(str(settings.BASE_DIR or ".")).resolve()
        log_dir = base_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = (log_dir / "app_info.log").resolve()

        root_logger = logging.getLogger()
        if int(root_logger.level or 0) > logging.INFO:
            root_logger.setLevel(logging.INFO)
        existing = [
            h for h in root_logger.handlers
            if isinstance(h, RotatingFileHandler)
            and str(getattr(h, "baseFilename", "")).replace("\\", "/").endswith("/app_info.log")
        ]
        if existing:
            return

        file_handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )
        root_logger.addHandler(file_handler)
    except Exception:
        # Never break request handling if log file setup fails.
        pass


_ensure_runtime_info_file_logging()

# Map Regex Patterns to Functional Names (Comprehensive)
FUNCTION_MAP = [
    # Auth
    (r"POST /api/v1/login.*", "User Login"),
    (r"POST /api/v1/register.*", "User Registration"),
    
    # Projects
    (r"GET /api/v1/projects$", "View Project List"),
    (r"POST /api/v1/projects$", "Create New Project"),
    (r"GET /api/v1/projects/\d+$", "View Project Details"),
    (r"PUT /api/v1/projects/\d+$", "Update Project"),
    (r"DELETE /api/v1/projects/\d+$", "Delete Project"),
    
    # Episodes & Script
    (r"GET /api/v1/projects/\d+/episodes", "View Episodes List"),
    (r"POST /api/v1/projects/\d+/episodes", "Create Episode"),
    (r"PUT /api/v1/episodes/\d+/segments", "Update Script Segments"),
    (r"GET /api/v1/episodes/\d+/scenes", "View Scenes List"),
    
    # AI Generation & Analysis
    (r"POST /api/v1/analyze_scene", "Function: AI Scene Analysis"),
    (r"POST /api/v1/scenes/\d+/ai_generate_visuals", "Function: AI Visual Generation"),
    (r"POST /api/v1/scenes/\d+/ai_generate_beats", "Function: AI Beat Generation"),
    (r"POST /api/v1/scenes/\d+/ai_generate_shots", "Function: AI Shot Generation"),
    (r"POST /api/v1/scenes/\d+/apply_ai_result", "Function: Apply AI Result"),
    
    # Agent
    (r"POST /api/v1/agent/command", "Function: Agent Command"),
    
    # Tools
    (r"POST /api/v1/tools/translate", "Tool: Translate"),
    (r"POST /api/v1/tools/refine_prompt", "Tool: Refine Prompt"),
    (r"POST /api/v1/tools/tune_shot_prompt", "Tool: Tune Shot Prompt"),
    
    # Assets
    (r"POST /api/v1/assets/upload", "Upload Asset"),
    (r"GET /api/v1/assets", "View Assets Library"),
    (r"DELETE /api/v1/assets/\d+", "Delete Asset"),
    
    # Users & Admin
    (r"GET /api/v1/users/me", "Get Current User Info"),
    (r"GET /api/v1/users$", "Admin: View All Users"),
    (r"PUT /api/v1/users/\d+/credits", "Admin: Update User Credits"),
    
    # Billing & Recharge - SPECIFIC REQUEST
    # (r"GET /api/v1/billing/recharge/status/.*", "Check Recharge Status"), # Removed to reduce log spam during polling
    (r"POST /api/v1/billing/recharge/create", "Initiate Recharge Order"),
    (r"POST /api/v1/billing/recharge/mock_pay/.*", "Mock Payment Execution"),
    (r"GET /api/v1/billing/recharge/plans", "View Recharge Plans"),
    (r"GET /api/v1/billing/transactions", "View Transaction History"),

    # System
    (r"GET /api/v1/system/logs", "Admin: View System Logs"),
    (r"GET /admin/payment-config", "Admin: View Payment Config"),
    (r"POST /admin/payment-config", "Admin: Update Payment Config"),
]

def get_function_name(method: str, path: str):
    key = f"{method} {path}"
    for pattern, name in FUNCTION_MAP:
        if re.search(pattern, key):
            return name
    return None


def _is_polling_log_suppressed(method: str, path: str) -> bool:
    key = f"{method} {path}"
    suppressed_patterns = [
        r"^GET /api/v1/tasks/[^/]+$",
        r"^GET /api/v1/projects/\d+/shares/?$",
        r"^GET /api/v1/projects/\d+/episodes$",
        r"^GET /api/v1/episodes/\d+/shots$",
        r"^GET /api/v1/projects/\d+/script_generator/episodes/scripts/status$",
        r"^GET /api/v1/episodes/\d+/scenes/ai_shots/batch/status$",
        r"^GET /api/v1/admin/memory-stats$",
        r"^GET /api/v1/episodes/\d+/script_generator/scenes/status$",
        r"^GET /api/v1/episodes/\d+/shots/batch-media/status$",
        r"^GET /api/v1/billing/recharge/status/[^/]+$",
        r"^GET /api/v1/generate/image/jobs/[^/]+$",
        r"^GET /api/v1/generate/video/jobs/[^/]+$",
        r"^GET /api/v1/generate/jobs/pool$",
        r"^GET /api/v1/generate/callback/[^/]+$",
        r"^POST /api/v1/generate/callback/[^/]+$",
    ]
    return any(re.search(pattern, key) for pattern in suppressed_patterns)


def _safe_int(value) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(str(value).strip())
    except Exception:
        return None


def _extract_first_int_by_regex(path: str, pattern: str) -> Optional[int]:
    m = re.search(pattern, path or "")
    if not m:
        return None
    return _safe_int(m.group(1))


def _resolve_project_id_for_logging(path: str, request: Request, body_bytes: Optional[bytes] = None) -> Optional[int]:
    direct_project_id = _extract_first_int_by_regex(path, r"/projects/(\d+)")
    if direct_project_id:
        return direct_project_id

    query_project_id = _safe_int(request.query_params.get("project_id"))
    if query_project_id:
        return query_project_id

    if body_bytes:
        try:
            payload = json.loads(body_bytes.decode("utf-8", errors="ignore"))
            if isinstance(payload, dict):
                body_project_id = _safe_int(payload.get("project_id"))
                if body_project_id:
                    return body_project_id
                data_project_id = _safe_int((payload.get("data") or {}).get("project_id") if isinstance(payload.get("data"), dict) else None)
                if data_project_id:
                    return data_project_id
        except Exception:
            pass

    return None


def get_user_from_token(auth_header: str):
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"user_id": None, "username": "Guest"}
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = _safe_int(payload.get("uid") or payload.get("user_id") or payload.get("id"))
        username = str(
            payload.get("uname")
            or payload.get("username")
            or payload.get("sub")
            or "Guest"
        ).strip() or "Guest"
        return {"user_id": user_id, "username": username}
    except JWTError:
        return {"user_id": None, "username": "Guest"}


def _normalize_traffic_path(path: str) -> str:
    raw = str(path or "/").strip() or "/"
    if raw.startswith("/uploads/") or raw == "/uploads":
        return "/uploads/*"
    normalized = _UUID_RE.sub(":uuid", raw)
    normalized = _HEX_TOKEN_RE.sub("/:hex", normalized)
    normalized = _NUMERIC_ID_RE.sub("/:id", normalized)
    return normalized or "/"


def _traffic_category(method: str, path: str) -> str:
    if path in {"/healthz", "/version", "/"} or path.startswith("/docs") or path.startswith("/redoc"):
        return "health"
    if path.startswith("/uploads/") or path == "/uploads":
        return "uploads"
    if _is_polling_log_suppressed(method, path):
        return "polling"
    if path.startswith("/api/"):
        return "api"
    return "other"


def log_request_traffic_startup() -> None:
    if _REQUEST_TRAFFIC_LOG_ENABLED:
        logger.info(
            "Request traffic summary enabled | interval=%ss top=%s (look for request.traffic)",
            int(_REQUEST_TRAFFIC_LOG_INTERVAL_SECONDS),
            int(_REQUEST_TRAFFIC_LOG_TOP),
        )


def flush_request_traffic_stats(*, reason: str = "interval", force: bool = False) -> Optional[Dict]:
    """Emit one aggregated traffic line and reset the window counters."""
    if not _REQUEST_TRAFFIC_LOG_ENABLED and not force:
        return None

    global _traffic_window_started_at, _traffic_last_flush_at, _traffic_lifetime_total
    now = time.time()
    with _traffic_lock:
        window_total = int(sum(_traffic_window_paths.values()))
        if window_total <= 0 and not force:
            _traffic_last_flush_at = now
            return None
        elapsed = max(0.001, now - float(_traffic_window_started_at or now))
        top = [
            {"key": key, "n": int(count)}
            for key, count in _traffic_window_paths.most_common(_REQUEST_TRAFFIC_LOG_TOP)
        ]
        categories = {k: int(v) for k, v in sorted(_traffic_window_categories.items())}
        lifetime = int(_traffic_lifetime_total)
        payload = {
            "reason": reason,
            "window_s": round(elapsed, 1),
            "window_total": window_total,
            "lifetime_total": lifetime,
            "rps": round(window_total / elapsed, 2),
            "categories": categories,
            "top": top,
        }
        _traffic_window_paths.clear()
        _traffic_window_categories.clear()
        _traffic_window_started_at = now
        _traffic_last_flush_at = now

    logger.info("request.traffic | %s", json.dumps(payload, ensure_ascii=False))
    return payload


def record_request_traffic(method: str, path: str) -> None:
    """Count one HTTP hit for max-requests diagnostics; periodically flush a summary."""
    if not _REQUEST_TRAFFIC_LOG_ENABLED:
        return
    method_u = str(method or "GET").upper()
    path_s = str(path or "/")
    key = f"{method_u} {_normalize_traffic_path(path_s)}"
    category = _traffic_category(method_u, path_s)
    should_flush = False
    now = time.time()
    global _traffic_lifetime_total
    with _traffic_lock:
        _traffic_window_paths[key] += 1
        _traffic_window_categories[category] += 1
        _traffic_lifetime_total += 1
        if (now - float(_traffic_last_flush_at or now)) >= _REQUEST_TRAFFIC_LOG_INTERVAL_SECONDS:
            should_flush = True
    if should_flush:
        flush_request_traffic_stats(reason="interval")


class LoggingMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path") or "")
        method = str(scope.get("method") or "GET").upper()
        # Count before early-return paths so /uploads and health checks are visible
        # in max-requests diagnostics (they are suppressed from API Result logs).
        try:
            record_request_traffic(method, path)
        except Exception:
            pass
        if path.startswith("/uploads/"):
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        method = str(scope.get("method") or "").upper()

        raw_headers = scope.get("headers") or []
        header_map = {}
        for key, value in raw_headers:
            try:
                header_map[str(key, "utf-8").lower()] = str(value, "utf-8")
            except Exception:
                continue

        content_type = str(header_map.get("content-type") or "").lower()
        content_length = _safe_int(header_map.get("content-length")) or 0
        should_buffer_json_body = (
            method in {"POST", "PUT", "PATCH"}
            and "application/json" in content_type
            and content_length > 0
            and content_length <= 512 * 1024
        )

        buffered_body = b""
        receive_for_app = receive
        if should_buffer_json_body:
            chunks = []
            more_body = True
            while more_body:
                message = await receive()
                if message.get("type") != "http.request":
                    continue
                body_part = message.get("body") or b""
                if body_part:
                    chunks.append(body_part)
                more_body = bool(message.get("more_body", False))

            buffered_body = b"".join(chunks)
            sent = False

            async def replay_receive():
                nonlocal sent, buffered_body
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": buffered_body, "more_body": False}
                # After body is replayed, delegate to the original receive so
                # Starlette's StreamingResponse disconnect-listener blocks
                # properly instead of busy-looping.
                return await receive()

            receive_for_app = replay_receive

        request = Request(scope, receive=receive_for_app)

        method = request.method
        path = request.url.path
        is_response_size_trace_target = bool(
            path == "/api/v1/admin/queue/stats"
            or path.startswith("/api/v1/generate/callback/")
        )
        func_name = get_function_name(method, path)
        is_polling_suppressed = _is_polling_log_suppressed(method, path)
        noise_prefixes = (
            "/uploads/",
            "/docs",
            "/redoc",
        )
        noise_exact = {
            "/",
            "/openapi.json",
            "/favicon.ico",
            "/healthz",
            "/api/v1/system_logs/actions",
            "/api/v1/system_logs/ui",
        }
        is_noise = path in noise_exact or any(path.startswith(p) for p in noise_prefixes)

        client = scope.get("client")
        client_host = client[0] if client and isinstance(client, tuple) else "unknown"

        username = "Guest"
        user_id = None
        auth = request.headers.get("Authorization")
        if auth:
            user = get_user_from_token(auth)
            username = user.get("username") or "Guest"
            user_id = user.get("user_id")

        project_id = _resolve_project_id_for_logging(path, request, buffered_body)
        response_status: Optional[int] = None
        response_content_length: Optional[str] = None
        response_content_encoding: Optional[str] = None

        async def send_wrapper(message):
            nonlocal response_status, response_content_length, response_content_encoding
            if message.get("type") == "http.response.start":
                response_status = int(message.get("status") or 0)
                for key, value in (message.get("headers") or []):
                    try:
                        header_key = str(key, "utf-8").lower()
                        header_value = str(value, "utf-8")
                    except Exception:
                        continue
                    if header_key == "content-length":
                        response_content_length = header_value
                    elif header_key == "content-encoding":
                        response_content_encoding = header_value
            await send(message)

        try:
            await self.app(scope, receive_for_app, send_wrapper)
        except Exception as e:
            process_ms = int((time.time() - start_time) * 1000)
            if is_polling_suppressed:
                raise
            if not is_noise:
                action = func_name or f"API Call: {method} {path}"
                logger.error(
                    f"API Result | UserID: {user_id} | Username: {username} | ProjectID: {project_id} | "
                    f"Action: {action} | Method: {method} | Path: {path} | "
                    f"Status: EXCEPTION | IP: {client_host} | Time: {process_ms}ms | Error: {type(e).__name__}: {str(e)[:200]}"
                )
            raise

        process_ms = int((time.time() - start_time) * 1000)
        status_code = response_status or 0

        if is_response_size_trace_target:
            trace_request_id = (
                request.headers.get("x-request-id")
                or request.headers.get("x-correlation-id")
                or request.headers.get("x-amzn-trace-id")
                or request.headers.get("traceparent")
                or "-"
            )
            logger.info(
                "HTTP Trace | Method: %s | Path: %s | Status: %s | Time: %sms | ReqBytes: %s | RespContentLength: %s | RespContentEncoding: %s | RequestID: %s | IP: %s",
                method,
                path,
                status_code,
                process_ms,
                request.headers.get("content-length") or "-",
                response_content_length or "-",
                response_content_encoding or "-",
                trace_request_id,
                client_host,
            )

        if not is_noise:
            if is_polling_suppressed:
                return

            action = func_name or f"API Call: {method} {path}"
            content_length = request.headers.get("content-length")
            size_part = f" | ReqBytes: {content_length}" if content_length else ""
            is_billing_estimate = (
                method == "POST"
                and path.rstrip("/").endswith("/billing/estimate/video")
            )

            if 200 <= status_code < 400:
                # Keep billing estimate hits visible (rate-limited); suppress other successful API noise.
                if is_billing_estimate:
                    now_ts = time.time()
                    last_at = float(_billing_estimate_log_state.get("last_at") or 0.0)
                    if (now_ts - last_at) < _BILLING_ESTIMATE_LOG_MIN_INTERVAL_SECONDS:
                        _billing_estimate_log_state["suppressed"] = int(
                            _billing_estimate_log_state.get("suppressed") or 0
                        ) + 1
                    else:
                        suppressed = int(_billing_estimate_log_state.get("suppressed") or 0)
                        _billing_estimate_log_state["last_at"] = now_ts
                        _billing_estimate_log_state["suppressed"] = 0
                        suppressed_part = f" | Suppressed={suppressed}" if suppressed > 0 else ""
                        logger.info(
                            f"API Result | UserID: {user_id} | Username: {username} | ProjectID: {project_id} | "
                            f"Action: {action} | Method: {method} | Path: {path} | "
                            f"Status: {status_code} | IP: {client_host} | Time: {process_ms}ms"
                            f"{size_part}{suppressed_part}"
                        )
            elif 400 <= status_code < 500:
                logger.warning(
                    f"API Result | UserID: {user_id} | Username: {username} | ProjectID: {project_id} | "
                    f"Action: {action} | Method: {method} | Path: {path} | "
                    f"Status: {status_code} | IP: {client_host} | Time: {process_ms}ms{size_part}"
                )
            else:
                logger.error(
                    f"API Result | UserID: {user_id} | Username: {username} | ProjectID: {project_id} | "
                    f"Action: {action} | Method: {method} | Path: {path} | "
                    f"Status: {status_code} | IP: {client_host} | Time: {process_ms}ms{size_part}"
                )
