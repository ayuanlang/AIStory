import re

with open('backend/app/services/generation_task_queue.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_func_regex = r'def start_generation_task_worker\(processor: Callable\[\[str, str, int, Dict\[str, Any\]\], None\]\) -> None:.*?_QUEUE_WORKER_THREADS,\n\s*\)'

new_str = '''def _worker_thread_main(processor: Callable[[str, str, int, Dict[str, Any]], None]) -> None:
    """Continuously tries to acquire leader lock and run generation tasks."""
    while not _QUEUE_STOP_EVENT.is_set():
        if not _try_acquire_queue_leader_lock():
            _QUEUE_STOP_EVENT.wait(15.0)
            continue
            
        try:
            logger.info("generation queue worker acquired leader lock, starting event loop...")
            _ensure_queue_table_ready()
            asyncio.run(_async_event_loop(processor))
        except Exception as exc:
            logger.exception("generation queue event loop crashed | err=%s", exc)
            _QUEUE_STOP_EVENT.wait(15.0)
        finally:
            if not _QUEUE_STOP_EVENT.is_set():
                logger.warning("generation queue event loop exited. Re-checking lock...")
                _QUEUE_STOP_EVENT.wait(5.0)

def start_generation_task_worker(processor: Callable[[str, str, int, Dict[str, Any]], None]) -> None:
    """Start generation task workers using async event loop."""
    global _QUEUE_STARTED
    if _QUEUE_STARTED:
        return
    with _QUEUE_START_LOCK:
        if _QUEUE_STARTED:
            return
            
        thread = threading.Thread(
            target=_worker_thread_main,
            args=(processor,),
            daemon=True,
            name="generation-queue-event-loop",
        )
        thread.start()
        _QUEUE_STARTED = True
        logger.info(
            "generation queue async event loop thread started, waiting for %s concurrent workers to become leader",
            _QUEUE_WORKER_THREADS,
        )'''

old_str_match = re.search(old_func_regex, code, flags=re.DOTALL)
if old_str_match:
    old_str = old_str_match.group(0)
    code = code.replace(old_str, new_str)
    with open('backend/app/services/generation_task_queue.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print('Updated successfully.')
else:
    print('Could not find match for old logic.')
