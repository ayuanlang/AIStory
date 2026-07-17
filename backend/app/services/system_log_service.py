import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Mapping, Optional

from sqlalchemy.orm import Session
from app.models.all_models import SystemLog
from app.core.config import settings
from app.core.time_utils import now_bj_iso
from app.db.session import SessionLocal

logger = logging.getLogger("api_logger")

_UI_SYSTEM_LOG_NAME = "user_system.log"
_UI_SYSTEM_LOG_MAX_LINES = 100
_ui_system_file_lock = threading.Lock()

_UI_LEVEL_MAP = {
    "debug": "DEBUG",
    "info": "INFO",
    "success": "INFO",
    "warn": "WARNING",
    "warning": "WARNING",
    "error": "ERROR",
}


def log_action(db: Session, user_id: int, user_name: str, action: str, details: str = None, ip_address: str = None):
    try:
        new_log = SystemLog(
            user_id=user_id,
            user_name=user_name,
            action=action,
            details=details,
            ip_address=ip_address,
            timestamp=now_bj_iso()
        )
        
        # We always use a new session to avoid breaking the caller's transaction
        # and prevent nested commit()s of half-finished states.
        with SessionLocal() as log_db:
            log_db.add(new_log)
            log_db.commit()
            
    except Exception as e:
        logger.exception(
            "Failed to write system log | user_id=%s user_name=%s action=%s error=%s",
            user_id,
            user_name,
            action,
            e,
        )


def get_ui_system_log_dir() -> Path:
    log_dir = Path(str(settings.BASE_DIR or ".")).resolve() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_ui_system_log_path() -> Path:
    return get_ui_system_log_dir() / _UI_SYSTEM_LOG_NAME


def _read_log_lines(path: Path) -> List[str]:
    if not path.exists() or not path.is_file():
        return []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            return [line.rstrip("\n") for line in f if line.strip()]
    except Exception:
        return []


def _write_log_lines(path: Path, lines: List[str]) -> None:
    capped = lines[-_UI_SYSTEM_LOG_MAX_LINES:]
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for line in capped:
            f.write(line.rstrip("\n") + "\n")


def append_ui_system_logs(
    entries: Iterable[Mapping],
    *,
    user_id: Optional[int] = None,
    user_name: str = "anonymous",
) -> int:
    """Append frontend「系统日志」entries to local file; keep at most 100 lines."""
    safe_user = str(user_name or "anonymous").strip() or "anonymous"
    new_lines: List[str] = []

    for entry in entries or []:
        if not isinstance(entry, Mapping):
            continue
        message = str(entry.get("message") or "").strip()
        if not message:
            continue
        if len(message) > 8000:
            message = message[:8000]

        level_name = str(entry.get("type") or entry.get("level") or "info").strip().lower() or "info"
        level = _UI_LEVEL_MAP.get(level_name, "INFO")
        client_time = str(entry.get("client_time") or "").strip()
        time_part = f" client_time={client_time}" if client_time else ""
        user_part = f"user_id={user_id} user={safe_user}" if user_id is not None else f"user={safe_user}"
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        new_lines.append(f"{stamp} | {level} | {user_part} |{time_part} {message}")

    if not new_lines:
        return 0

    log_path = get_ui_system_log_path()
    with _ui_system_file_lock:
        try:
            existing = _read_log_lines(log_path)
            merged = (existing + new_lines)[-_UI_SYSTEM_LOG_MAX_LINES:]
            _write_log_lines(log_path, merged)
            return len(new_lines)
        except Exception:
            # Persistence must never break request handling.
            return 0
