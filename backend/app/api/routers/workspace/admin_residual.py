# -*- coding: utf-8 -*-
"""Workspace section routes — symbols pulled from shared module."""
from __future__ import annotations

from app.api.routers.workspace import shared as _shared

# Attach routes onto the same APIRouter instance and reuse helpers.
router = _shared.router
globals().update({k: v for k, v in vars(_shared).items() if k not in {"__name__", "__file__", "__package__", "__loader__", "__spec__", "__doc__", "__builtins__"}})


# --- Entities ---
# Entity schemas moved to app.schemas.entity
from app.schemas.entity import (  # noqa: E402,F401
    EntityCreate,
    EntityOut,
    _coerce_visual_dependencies,
    coerce_visual_dependencies,
)

# entities CRUD moved to app.api.routers.entities



# assets routes moved to app.api.routers.assets

@router.get("/admin/runtime-stats")
def get_runtime_stats(current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    image_job_stats = _snapshot_image_job_stats()
    with IMAGE_JOB_LOCK:
        image_task_count = len(IMAGE_JOB_TASKS)
    with VIDEO_JOB_LOCK:
        video_store_items = len(VIDEO_JOB_STORE)
        video_task_count = len(VIDEO_JOB_TASKS)

    gunicorn_max_requests_raw = os.getenv("GUNICORN_MAX_REQUESTS", "")
    gunicorn_max_requests_jitter_raw = os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "")

    def _safe_int_env(raw: Any, default: Optional[int] = None) -> Optional[int]:
        try:
            txt = str(raw or "").strip()
            if txt == "":
                return default
            return int(txt)
        except Exception:
            return default

    gunicorn_max_requests = _safe_int_env(gunicorn_max_requests_raw)
    gunicorn_max_requests_jitter = _safe_int_env(gunicorn_max_requests_jitter_raw)

    return {
        "service": "aistory-backend",
        "pid": os.getpid(),
        "timestamp": now_bj_iso(),
        "render": {
            "service_id": os.getenv("RENDER_SERVICE_ID", ""),
            "instance_id": os.getenv("RENDER_INSTANCE_ID", ""),
            "git_commit": os.getenv("RENDER_GIT_COMMIT", ""),
        },
        "runtime": {
            "python": {
                "version": sys.version,
                "active_threads": threading.active_count(),
            },
            "gunicorn": {
                "workers": os.getenv("WEB_CONCURRENCY", ""),
                "timeout": os.getenv("GUNICORN_TIMEOUT", ""),
                "graceful_timeout": os.getenv("GUNICORN_GRACEFUL_TIMEOUT", ""),
                "keepalive": os.getenv("GUNICORN_KEEPALIVE", ""),
                "max_requests": gunicorn_max_requests_raw,
                "max_requests_jitter": gunicorn_max_requests_jitter_raw,
                "request_limit_disabled": (gunicorn_max_requests == 0 and (gunicorn_max_requests_jitter or 0) == 0),
            },
            "async_jobs": {
                "image_store_items": image_job_stats.get("store_items", 0),
                "image_live_tasks": image_task_count,
                "video_store_items": video_store_items,
                "video_live_tasks": video_task_count,
            },
        },
        "image_jobs": image_job_stats,
    }


@router.get("/admin/upstream-diagnostics/grsai")
def admin_diagnose_grsai_connectivity(
    timeout_seconds: int = 5,
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    timeout_seconds = max(2, min(int(timeout_seconds or 5), 20))

    targets = [
        {
            "name": "primary",
            "base_url": "https://grsai.dakka.com.cn",
            "submit_path": "/v1/draw/nano-banana",
            "poll_path": "/v1/draw/result",
        },
        {
            "name": "fallback",
            "base_url": "https://grsaiapi.com",
            "submit_path": "/v1/draw/completions",
            "poll_path": "/v1/draw/result",
        },
    ]

    def _check_one(target: Dict[str, str]) -> Dict[str, Any]:
        base_url = target["base_url"].rstrip("/")
        parsed = urllib.parse.urlparse(base_url)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        result: Dict[str, Any] = {
            "name": target["name"],
            "host": host,
            "port": port,
            "base_url": base_url,
            "submit_url": f"{base_url}{target['submit_path']}",
            "poll_url": f"{base_url}{target['poll_path']}",
            "dns": {"ok": False, "ips": [], "error": None, "ms": None},
            "tcp": {"ok": False, "error": None, "ms": None},
            "http": {
                "ok": False,
                "status": None,
                "error": None,
                "ms": None,
                "note": "HTTP 200/401/403/404/405 are all considered reachable",
            },
        }

        dns_start = time.perf_counter()
        try:
            infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
            ips = sorted({info[4][0] for info in infos if info and len(info) >= 5 and info[4]})
            result["dns"]["ok"] = len(ips) > 0
            result["dns"]["ips"] = ips
        except Exception as exc:
            result["dns"]["error"] = str(exc)
        finally:
            result["dns"]["ms"] = int((time.perf_counter() - dns_start) * 1000)

        tcp_start = time.perf_counter()
        try:
            conn = socket.create_connection((host, port), timeout=timeout_seconds)
            conn.close()
            result["tcp"]["ok"] = True
        except Exception as exc:
            result["tcp"]["error"] = str(exc)
        finally:
            result["tcp"]["ms"] = int((time.perf_counter() - tcp_start) * 1000)

        http_start = time.perf_counter()
        try:
            resp = requests.get(
                result["submit_url"],
                timeout=(timeout_seconds, timeout_seconds),
                verify=False,
            )
            result["http"]["status"] = resp.status_code
            result["http"]["ok"] = resp.status_code in {200, 401, 403, 404, 405}
        except Exception as exc:
            result["http"]["error"] = str(exc)
        finally:
            result["http"]["ms"] = int((time.perf_counter() - http_start) * 1000)

        return result

    checks = [_check_one(target) for target in targets]
    overall_ok = any(item.get("http", {}).get("ok") for item in checks)

    return {
        "ok": overall_ok,
        "timeout_seconds": timeout_seconds,
        "proxy_env": {
            "HTTP_PROXY": os.getenv("HTTP_PROXY") or "",
            "HTTPS_PROXY": os.getenv("HTTPS_PROXY") or "",
            "NO_PROXY": os.getenv("NO_PROXY") or "",
        },
        "checks": checks,
    }



# billing routes moved to app.api.routers.billing


# generate routes moved to app.api.routers.generate



# batch-media routes moved to app.api.routers.generate


# montage routes moved to app.api.routers.generate


# assets/analyze moved to assets router


# entity analyze moved to entities router


# analyze_scene/stream moved to prompts_analyze


# residual routes moved to workspace_residual



# Refresh cross-router helpers after local definitions are complete.
