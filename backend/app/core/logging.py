
import logging
import time
import re
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError
from app.core.config import settings

# Configure standard loggers to be less noisy
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.ERROR)
logging.getLogger("fastapi").setLevel(logging.WARNING)


class _SuppressUvicornAccessUploads(logging.Filter):
    _re = re.compile(r'"(GET|HEAD)\s+/uploads/[^\s]*\s+HTTP/')

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        return self._re.search(msg) is None


def configure_uvicorn_logging_noise_reduction() -> None:
    """Reduce meaningless uvicorn access log noise.

    Uvicorn may override logger levels via its own log_config after module import,
    so call this at app startup to ensure it takes effect.
    """
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.setLevel(logging.WARNING)

    if not any(isinstance(f, _SuppressUvicornAccessUploads) for f in access_logger.filters):
        access_logger.addFilter(_SuppressUvicornAccessUploads())

logger = logging.getLogger("functional_activity")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
logger.addHandler(handler)

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
    (r"GET /api/v1/billing/rules", "View Pricing Rules"),
    
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


def _resolve_project_id_for_logging(path: str, request: Request) -> Optional[int]:
    direct_project_id = _extract_first_int_by_regex(path, r"/projects/(\d+)")
    if direct_project_id:
        return direct_project_id

    query_project_id = _safe_int(request.query_params.get("project_id"))
    if query_project_id:
        return query_project_id

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

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # 1. Identify Function
        method = request.method
        path = request.url.path
        func_name = get_function_name(method, path)
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
        }
        is_noise = path in noise_exact or any(path.startswith(p) for p in noise_prefixes)
        
        # 2. Extract Client Info
        client_host = request.client.host if request.client else "unknown"
        
        # 3. Extract User (Best Effort)
        username = "Guest"
        user_id = None
        auth = request.headers.get("Authorization")
        if auth:
            user = get_user_from_token(auth)
            username = user.get("username") or "Guest"
            user_id = user.get("user_id")

        project_id = _resolve_project_id_for_logging(path, request)

        try:
            response = await call_next(request)
        except Exception as e:
            process_ms = int((time.time() - start_time) * 1000)
            if not is_noise:
                action = func_name or f"API Call: {method} {path}"
                logger.error(
                    f"API Result | UserID: {user_id} | Username: {username} | ProjectID: {project_id} | "
                    f"Action: {action} | Method: {method} | Path: {path} | "
                    f"Status: EXCEPTION | IP: {client_host} | Time: {process_ms}ms | Error: {type(e).__name__}: {str(e)[:200]}"
                )
            raise

        process_ms = int((time.time() - start_time) * 1000)

        # 4. Log every API endpoint call with key access factors and result status.
        # Skip noisy static /uploads requests.
        if not is_noise:
            action = func_name or f"API Call: {method} {path}"
            content_length = request.headers.get("content-length")
            size_part = f" | ReqBytes: {content_length}" if content_length else ""

            if 200 <= response.status_code < 400:
                logger.info(
                    f"API Result | UserID: {user_id} | Username: {username} | ProjectID: {project_id} | "
                    f"Action: {action} | Method: {method} | Path: {path} | "
                    f"Status: {response.status_code} | IP: {client_host} | Time: {process_ms}ms{size_part}"
                )
            elif 400 <= response.status_code < 500:
                logger.warning(
                    f"API Result | UserID: {user_id} | Username: {username} | ProjectID: {project_id} | "
                    f"Action: {action} | Method: {method} | Path: {path} | "
                    f"Status: {response.status_code} | IP: {client_host} | Time: {process_ms}ms{size_part}"
                )
            else:
                logger.error(
                    f"API Result | UserID: {user_id} | Username: {username} | ProjectID: {project_id} | "
                    f"Action: {action} | Method: {method} | Path: {path} | "
                    f"Status: {response.status_code} | IP: {client_host} | Time: {process_ms}ms{size_part}"
                )

        # 5. Fallback for non-API 5xxs (rare but useful)
        elif response.status_code >= 500 and (not is_noise):
            logger.error(
                f"System Error | UserID: {user_id} | Username: {username} | ProjectID: {project_id} | "
                f"Path: {method} {path} | Status: {response.status_code} | "
                f"IP: {client_host} | Time: {process_ms}ms"
            )

        return response
