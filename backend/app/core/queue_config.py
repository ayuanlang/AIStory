import json
import logging
import os
import tempfile
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Keep the JSON file outside the uvicorn --reload watch root (`backend/`).
# Writing into `backend/` truncates the file and can race the reloader, so the
# next process loads defaults (queue_threads=10) and the save appears lost.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
QUEUE_CONFIG_FILE = os.getenv("QUEUE_CONFIG_FILE", "").strip() or os.path.join(
    _PROJECT_ROOT,
    "data",
    "queue_config.json",
)

DEFAULT_QUEUE_CONFIG: Dict[str, Any] = {
    "queue_threads": 10,
    "callback_threads": 10,
    "pure_callback_mode_auto": True,
    "pure_callback_mode": False,
    "callback_loss_retry_enabled": True,
    "callback_loss_retry_after_seconds": 1200,
    "callback_loss_max_submit_retries": 1,
    "callback_compensation_scan_enabled": True,
    "callback_compensation_scan_interval_seconds": 60,
    "callback_compensation_scan_batch_size": 10,
    "callback_compensation_image_share_percent": 50,
    # After image/video running timeout: force N provider polls (even in pure callback mode)
    # as a callback-loss supplement before permanently failing.
    "timeout_poll_max_attempts": 3,
    "timeout_poll_interval_seconds": 30,
    # After intermediate running webhook: early provider poll in case terminal webhook is lost.
    "callback_followup_poll_delay_seconds": 90,
    "callback_followup_poll_max_attempts": 40,
    "callback_followup_poll_interval_seconds": 30,
}

_LEGACY_QUEUE_CONFIG_FILE = os.path.join(_BACKEND_DIR, "queue_config.json")


def default_queue_config() -> Dict[str, Any]:
    return dict(DEFAULT_QUEUE_CONFIG)


def _normalize_config(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    config = default_queue_config()
    if isinstance(payload, dict):
        config.update(payload)
    try:
        config["queue_threads"] = max(1, int(config.get("queue_threads") or DEFAULT_QUEUE_CONFIG["queue_threads"]))
    except Exception:
        config["queue_threads"] = int(DEFAULT_QUEUE_CONFIG["queue_threads"])
    try:
        config["callback_threads"] = max(1, int(config.get("callback_threads") or DEFAULT_QUEUE_CONFIG["callback_threads"]))
    except Exception:
        config["callback_threads"] = int(DEFAULT_QUEUE_CONFIG["callback_threads"])
    return config


def _load_config_from_file(path: str) -> Optional[Dict[str, Any]]:
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as file_obj:
            payload = json.load(file_obj)
        if isinstance(payload, dict):
            return payload
    except Exception as exc:
        logger.warning("Failed to load queue config file %s: %s", path, exc)
    return None


def _atomic_write_json(path: str, payload: Dict[str, Any]) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="queue_config_", suffix=".json.tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file_obj:
            json.dump(payload, file_obj, ensure_ascii=False, indent=2)
            file_obj.flush()
            os.fsync(file_obj.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        raise


def _load_config_from_db() -> Optional[Dict[str, Any]]:
    try:
        from app.db.session import SessionLocal
        from app.models.all_models import QueueSystemConfig
    except Exception:
        return None

    db = None
    try:
        db = SessionLocal()
        row = db.query(QueueSystemConfig).order_by(QueueSystemConfig.id.asc()).first()
        if row is None:
            return None
        payload = getattr(row, "config_json", None)
        if isinstance(payload, dict):
            return payload
    except Exception as exc:
        logger.debug("Queue config DB load skipped: %s", exc)
        return None
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass
    return None


def _ensure_queue_config_table() -> None:
    """Create queue_system_configs if missing (Render worker skips full DB bootstrap)."""
    try:
        from app.db.session import engine
        from app.models.all_models import QueueSystemConfig

        QueueSystemConfig.__table__.create(bind=engine, checkfirst=True)
    except Exception as exc:
        logger.debug("Queue config table ensure skipped: %s", exc)


def _save_config_to_db(config: Dict[str, Any]) -> bool:
    try:
        from app.core.time_utils import now_bj_iso
        from app.db.session import SessionLocal
        from app.models.all_models import QueueSystemConfig
    except Exception as exc:
        logger.warning("Queue config DB save unavailable: %s", exc)
        return False

    db = None
    try:
        _ensure_queue_config_table()
        db = SessionLocal()
        row = db.query(QueueSystemConfig).order_by(QueueSystemConfig.id.asc()).first()
        stamp = now_bj_iso()
        if row is None:
            row = QueueSystemConfig(config_json=dict(config), created_at=stamp, updated_at=stamp)
            db.add(row)
        else:
            row.config_json = dict(config)
            row.updated_at = stamp
        db.commit()
        return True
    except Exception as exc:
        logger.warning("Queue config DB save failed: %s", exc)
        if db is not None:
            try:
                db.rollback()
            except Exception:
                pass
        return False
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


def load_queue_config() -> Dict[str, Any]:
    """Load queue config: DB (preferred) → file → defaults."""
    db_payload = _load_config_from_db()
    if isinstance(db_payload, dict):
        return _normalize_config(db_payload)

    file_payload = _load_config_from_file(QUEUE_CONFIG_FILE)
    if file_payload is None:
        file_payload = _load_config_from_file(_LEGACY_QUEUE_CONFIG_FILE)
    if isinstance(file_payload, dict):
        config = _normalize_config(file_payload)
        # Best-effort migrate legacy/local file into DB once available.
        _save_config_to_db(config)
        return config

    config = default_queue_config()
    # Ops fallback when nothing has been saved yet (e.g. systemd Environment=).
    env_raw = str(os.getenv("GENERATION_QUEUE_WORKER_THREADS", "") or "").strip()
    if env_raw:
        try:
            config["queue_threads"] = max(1, int(env_raw))
        except Exception:
            pass
    return config


def save_queue_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Persist queue config to DB (source of truth) and atomic JSON backup."""
    config = _normalize_config(payload if isinstance(payload, dict) else None)
    db_ok = _save_config_to_db(config)
    try:
        _atomic_write_json(QUEUE_CONFIG_FILE, config)
    except Exception as exc:
        if not db_ok:
            raise
        logger.warning("Queue config file backup failed after DB save: %s", exc)
    if not db_ok:
        logger.warning("Queue config saved to file only; DB persistence unavailable")
    return config
