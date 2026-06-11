import json
import os
from typing import Any, Dict

QUEUE_CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
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
}


def default_queue_config() -> Dict[str, Any]:
    return dict(DEFAULT_QUEUE_CONFIG)


def load_queue_config() -> Dict[str, Any]:
    config = default_queue_config()
    if os.path.exists(QUEUE_CONFIG_FILE):
        try:
            with open(QUEUE_CONFIG_FILE, "r", encoding="utf-8") as file_obj:
                payload = json.load(file_obj)
            if isinstance(payload, dict):
                config.update(payload)
        except Exception:
            pass
    return config


def save_queue_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    config = default_queue_config()
    if isinstance(payload, dict):
        config.update(payload)
    with open(QUEUE_CONFIG_FILE, "w", encoding="utf-8") as file_obj:
        json.dump(config, file_obj, ensure_ascii=False, indent=2)
    return config