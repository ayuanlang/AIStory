import signal
import threading
import time

from app.api import endpoints
from app.core.logging import configure_uvicorn_logging_noise_reduction, logger


def _load_bootstrap_hooks():
    # Lazy import avoids circular startup edge-cases when app.main imports API modules.
    from app.main import _RUN_DB_BOOTSTRAP_ON_START, _bootstrap_db_post_init, _bootstrap_db_schema, _runtime_version_info

    return _RUN_DB_BOOTSTRAP_ON_START, _bootstrap_db_post_init, _bootstrap_db_schema, _runtime_version_info


_STOP_EVENT = threading.Event()


def _handle_signal(signum, frame):
    logger.info("Generation worker shutting down | signal=%s", signum)
    _STOP_EVENT.set()


def main() -> None:
    configure_uvicorn_logging_noise_reduction()
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    _RUN_DB_BOOTSTRAP_ON_START, _bootstrap_db_post_init, _bootstrap_db_schema, _runtime_version_info = _load_bootstrap_hooks()
    logger.info("Generation worker version | %s", _runtime_version_info())

    if _RUN_DB_BOOTSTRAP_ON_START:
        logger.info("Generation worker startup: critical DB bootstrap enabled")
        schema_ready, should_run_post_init = _bootstrap_db_schema()
        if not schema_ready:
            raise RuntimeError("Critical DB schema bootstrap failed in generation worker")
        if should_run_post_init:
            _bootstrap_db_post_init()
        logger.info("Generation worker startup: critical DB bootstrap complete")
    else:
        logger.warning("Generation worker startup: RUN_DB_BOOTSTRAP_ON_START disabled")

    endpoints.start_generation_queue_worker()
    logger.info("Generation worker consuming queue")

    while not _STOP_EVENT.is_set():
        _STOP_EVENT.wait(30.0)


if __name__ == "__main__":
    main()