import re

def main():
    with open('backend/app/services/generation_task_queue.py', 'r', encoding='utf-8') as f:
        text = f.read()

    s1_old = '''_QUEUE_LAST_CLEANUP_TIME = 0.0

def _cleanup_old_tasks() -> None:
    global _QUEUE_LAST_CLEANUP_TIME
    now = time.time()
    if now - _QUEUE_LAST_CLEANUP_TIME < 3600.0:
        return
    _QUEUE_LAST_CLEANUP_TIME = now'''

    s1_new = '''_QUEUE_LAST_CLEANUP_TIME = 0.0
_QUEUE_LAST_TIMEOUT_SWEEP_TIME = 0.0

def _cleanup_old_tasks() -> None:
    global _QUEUE_LAST_CLEANUP_TIME, _QUEUE_LAST_TIMEOUT_SWEEP_TIME
    now = time.time()
    if now - _QUEUE_LAST_TIMEOUT_SWEEP_TIME < 60.0:
        return
    _QUEUE_LAST_TIMEOUT_SWEEP_TIME = now
    
    # We sweep for timeouts every minute, but full deletes only every hour.
    do_full_cleanup = False
    if now - _QUEUE_LAST_CLEANUP_TIME >= 3600.0:
        _QUEUE_LAST_CLEANUP_TIME = now
        do_full_cleanup = True'''

    text = text.replace(s1_old, s1_new, 1)

    s2_old = '''        if (r_timeout.rowcount or 0) > 0:
            logger.warning("generation queue sweep timed out %s running tasks (>30m)", r_timeout.rowcount)

        result = db.execute(
            text(
                "DELETE FROM generation_task_queue WHERE status IN ('completed', 'failed', 'canceled') AND created_at < :cutoff"
            ),
            {"cutoff": cutoff},
        )
        db.commit()
        if (result.rowcount or 0) > 0:
            logger.info("generation queue cleanup deleted %s old tasks", result.rowcount)'''

    s2_new = '''        if (r_timeout.rowcount or 0) > 0:
            logger.warning("generation queue sweep timed out %s running tasks (>30m)", r_timeout.rowcount)

        if do_full_cleanup:
            result = db.execute(
                text(
                    "DELETE FROM generation_task_queue WHERE status IN ('completed', 'failed', 'canceled') AND created_at < :cutoff"
                ),
                {"cutoff": cutoff},
            )
            db.commit()
            if (result.rowcount or 0) > 0:
                logger.info("generation queue cleanup deleted %s old tasks", result.rowcount)'''
    text = text.replace(s2_old, s2_new, 1)

    with open('backend/app/services/generation_task_queue.py', 'w', encoding='utf-8') as f:
        f.write(text)

if __name__ == '__main__':
    main()