"""Orchestrate daily DB backup under a leader lock."""

from __future__ import annotations

import atexit
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.time_utils import now_bj
from app.jobs.db_backup import run_full_db_backup
from app.jobs.billing_reconcile import run_nightly_billing_reconcile

logger = logging.getLogger(__name__)

_MAINTENANCE_ADVISORY_LOCK_ID = 91420260719  # unique int for pg_try_advisory_lock
_MAINTENANCE_FILE_LOCK_PATH = str(
    (Path(settings.DB_BACKUP_DIR) / ".maintenance.lock").resolve()
)
_MAINTENANCE_STATE_PATH = Path(settings.DB_BACKUP_DIR) / "maintenance_state.json"

_LEADER_CONN = None
_FILE_LOCK_FD: Optional[int] = None


def _is_postgres() -> bool:
    return "postgresql" in str(settings.DATABASE_URL or "")


def _release_leader_lock() -> None:
    global _LEADER_CONN, _FILE_LOCK_FD
    conn = _LEADER_CONN
    lock_fd = _FILE_LOCK_FD
    _LEADER_CONN = None
    _FILE_LOCK_FD = None
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
    if lock_fd is not None:
        try:
            os.lseek(lock_fd, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock_fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except Exception:
            pass
        finally:
            try:
                os.close(lock_fd)
            except Exception:
                pass


atexit.register(_release_leader_lock)


def try_acquire_maintenance_lock() -> bool:
    """Acquire a process-wide leader lock for maintenance jobs."""
    global _LEADER_CONN, _FILE_LOCK_FD
    if not _is_postgres():
        if _FILE_LOCK_FD is not None:
            return True
        lock_fd = None
        try:
            lock_dir = os.path.dirname(_MAINTENANCE_FILE_LOCK_PATH) or "."
            os.makedirs(lock_dir, exist_ok=True)
            lock_fd = os.open(_MAINTENANCE_FILE_LOCK_PATH, os.O_RDWR | os.O_CREAT)
            os.lseek(lock_fd, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock_fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _FILE_LOCK_FD = lock_fd
            lock_fd = None
            return True
        except OSError:
            return False
        except Exception as exc:
            logger.warning("maintenance file lock failed: %s", exc)
            return False
        finally:
            if lock_fd is not None:
                try:
                    os.close(lock_fd)
                except Exception:
                    pass

    if _LEADER_CONN is not None:
        return True

    import psycopg2

    dsn = str(settings.DATABASE_URL or "").strip()
    if dsn.startswith("postgres://"):
        dsn = dsn.replace("postgres://", "postgresql://", 1)
    if dsn.startswith("postgresql+psycopg2://"):
        dsn = dsn.replace("postgresql+psycopg2://", "postgresql://", 1)

    conn = None
    try:
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", (_MAINTENANCE_ADVISORY_LOCK_ID,))
            row = cursor.fetchone()
            acquired = bool(row and row[0])
        finally:
            cursor.close()
        if acquired:
            _LEADER_CONN = conn
            conn = None
            return True
        return False
    except Exception as exc:
        logger.warning("maintenance advisory lock failed: %s", exc)
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _read_state() -> Dict[str, Any]:
    try:
        if _MAINTENANCE_STATE_PATH.exists():
            return json.loads(_MAINTENANCE_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _write_state(payload: Dict[str, Any]) -> None:
    try:
        _MAINTENANCE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _MAINTENANCE_STATE_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("Failed to write maintenance state: %s", exc)


def already_ran_today() -> bool:
    state = _read_state()
    return str(state.get("last_run_date") or "") == now_bj().strftime("%Y%m%d")


def run_daily_maintenance(*, force: bool = False) -> Dict[str, Any]:
    """
    Run full DB backup (circular overwrite) and nightly billing reconcile.

    Project retention is manual via admin UI and is not scheduled.
    When force=False, skips if already completed for today's Beijing date.
    """
    today = now_bj().strftime("%Y%m%d")
    if not force and already_ran_today():
        logger.info("Daily maintenance already completed for %s; skipping", today)
        return {"ok": True, "skipped": True, "reason": "already_ran_today", "date": today}

    if not try_acquire_maintenance_lock():
        logger.info("Daily maintenance skipped; another process holds the leader lock")
        return {"ok": True, "skipped": True, "reason": "lock_not_acquired", "date": today}

    result: Dict[str, Any] = {
        "ok": True,
        "skipped": False,
        "date": today,
        "started_at": now_bj().isoformat(timespec="seconds"),
    }
    try:
        result["db_backup"] = run_full_db_backup()
    except Exception as exc:
        logger.exception("Daily DB backup failed")
        result["ok"] = False
        result["db_backup"] = {"ok": False, "error": str(exc)}

    if getattr(settings, "BILLING_RECONCILE_ENABLED", True):
        try:
            result["billing_reconcile"] = run_nightly_billing_reconcile()
            if not result["billing_reconcile"].get("ok", True):
                result["ok"] = False
        except Exception as exc:
            logger.exception("Nightly billing reconcile failed")
            result["ok"] = False
            result["billing_reconcile"] = {"ok": False, "error": str(exc)}
    else:
        result["billing_reconcile"] = {"ok": True, "skipped": True, "reason": "disabled"}

    result["finished_at"] = now_bj().isoformat(timespec="seconds")
    if result.get("ok"):
        _write_state(
            {
                "last_run_date": today,
                "last_result": {
                    "ok": True,
                    "db_backup_created": (result.get("db_backup") or {}).get("created"),
                    "billing_reconciled_ok": (result.get("billing_reconcile") or {}).get("reconciled_ok"),
                    "finished_at": result["finished_at"],
                },
            }
        )
    logger.info(
        "Daily maintenance finished | ok=%s db_backup=%s billing_reconciled=%s",
        result.get("ok"),
        (result.get("db_backup") or {}).get("created"),
        (result.get("billing_reconcile") or {}).get("reconciled_ok"),
    )
    return result
