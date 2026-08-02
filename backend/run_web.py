"""Render web entrypoint that always starts a single gunicorn worker.

Dashboard Start Command (paste exactly):
  cd backend; python run_web.py

This ignores a mistaken WEB_CONCURRENCY=2 / hardcoded --workers 2 in older
start commands, because those never invoke this file.
"""
from __future__ import annotations

import os
import sys


def _clamp_workers() -> int:
    raw = str(os.getenv("WEB_CONCURRENCY", "1") or "1").strip()
    try:
        workers = int(raw)
    except Exception:
        workers = 1
    if workers < 1:
        workers = 1
    # 4GB-class hosts: never allow multi-worker unless explicitly unlocked.
    force_single = str(os.getenv("FORCE_SINGLE_WEB_WORKER", "1") or "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if force_single and workers > 1:
        print(f"[boot] clamping WEB_CONCURRENCY={workers} -> 1 (FORCE_SINGLE_WEB_WORKER=1)", flush=True)
        workers = 1
    return workers


def main() -> int:
    # Keep cwd semantics identical to historical "cd backend; gunicorn ..."
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    port = str(os.getenv("PORT", "8000") or "8000").strip() or "8000"
    workers = _clamp_workers()
    os.environ["WEB_CONCURRENCY"] = str(workers)

    timeout = str(os.getenv("GUNICORN_TIMEOUT", "600") or "600")
    graceful = str(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "660") or "660")
    keep_alive = str(os.getenv("GUNICORN_KEEPALIVE", "15") or "15")
    # Single worker: recycling on max-requests drops all traffic during app reboot.
    # Default 0 unless explicitly configured; multi-worker keeps the old 300 default.
    if "GUNICORN_MAX_REQUESTS" in os.environ:
        max_requests = str(os.getenv("GUNICORN_MAX_REQUESTS") or "0")
    else:
        max_requests = "0" if workers <= 1 else "300"
    if "GUNICORN_MAX_REQUESTS_JITTER" in os.environ:
        max_requests_jitter = str(os.getenv("GUNICORN_MAX_REQUESTS_JITTER") or "0")
    else:
        max_requests_jitter = "0" if max_requests == "0" else "50"
    os.environ["GUNICORN_MAX_REQUESTS"] = max_requests
    os.environ["GUNICORN_MAX_REQUESTS_JITTER"] = max_requests_jitter

    print(
        f"[boot] starting gunicorn via run_web.py | port={port} workers={workers} "
        f"max_requests={max_requests}",
        flush=True,
    )

    # Prefer the shared shell entry when present (migrations + clamp).
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "start_web.sh")
    if os.path.isfile(script):
        os.environ["WEB_CONCURRENCY"] = str(workers)
        os.execvp("bash", ["bash", script])

    # Fallback: direct gunicorn (no migrations).
    args = [
        "gunicorn",
        "app.main:app",
        "-c",
        "gunicorn.conf.py",
        "-k",
        "uvicorn.workers.UvicornWorker",
        "--bind",
        f"0.0.0.0:{port}",
        "--workers",
        str(workers),
        "--timeout",
        timeout,
        "--graceful-timeout",
        graceful,
        "--keep-alive",
        keep_alive,
        "--access-logfile",
        "-",
        "--error-logfile",
        "-",
        "--max-requests",
        max_requests,
        "--max-requests-jitter",
        max_requests_jitter,
    ]
    os.execvp(args[0], args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
