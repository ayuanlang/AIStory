import json
import re

def main():
    with open('backend/app/services/generation_task_queue.py', 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. Update _claim_next_task
    s1_old = '''                SELECT job_id, kind, user_id, payload_json
                FROM generation_task_queue'''
    s1_new = '''                SELECT job_id, kind, user_id, payload_json, created_at
                FROM generation_task_queue'''
    text = text.replace(s1_old, s1_new, 1)

    s2_old = '''        now = time.time()
        result = db.execute(
            text(
                """
                UPDATE generation_task_queue
                SET status = 'running',
                    worker_id = :worker_id,
                    started_at = COALESCE(started_at, :started_at),
                    last_heartbeat = :heartbeat,
                    finished_at = NULL,
                    error = NULL,
                    attempt_count = attempt_count + 1
                WHERE job_id = :job_id
                  AND (status = 'queued' OR (status = 'running' AND COALESCE(last_heartbeat, 0) < :cutoff))
                """
            ),
            {
                "job_id": str(row["job_id"]),
                "worker_id": worker_id,
                "started_at": now,
                "heartbeat": now,
                "cutoff": cutoff,
            },
        )
        db.commit()
        if result.rowcount == 0:
            return None'''

    s2_new = '''        now = time.time()
        created_at = row.get("created_at") or now
        is_expired = (now - created_at) > 1800.0

        result = db.execute(
            text(
                """
                UPDATE generation_task_queue
                SET status = :next_status,
                    worker_id = :worker_id,
                    started_at = COALESCE(started_at, :started_at),
                    last_heartbeat = :heartbeat,
                    finished_at = :finished_at,
                    error = :error,
                    attempt_count = attempt_count + 1
                WHERE job_id = :job_id
                  AND (status = 'queued' OR (status = 'running' AND COALESCE(last_heartbeat, 0) < :cutoff))
                """
            ),
            {
                "job_id": str(row["job_id"]),
                "worker_id": worker_id,
                "started_at": now,
                "heartbeat": now,
                "cutoff": cutoff,
                "next_status": "failed" if is_expired else "running",
                "finished_at": now if is_expired else None,
                "error": "Task queued for over 30 minutes. Timed out." if is_expired else None,
            },
        )
        db.commit()
        if result.rowcount == 0:
            return None
        
        if is_expired:
            import logging
            l2 = logging.getLogger(__name__)
            l2.warning("Claimed task %s but it was created > 30 mins ago. Marked as failed.", row["job_id"])
            return None'''
    text = text.replace(s2_old, s2_new, 1)

    # 2. Update _worker_loop_async
    s3_old = '''            result = processor(task["kind"], task["job_id"], task["user_id"], task["payload"])
            if asyncio.iscoroutine(result) or isinstance(result, asyncio.Task):
                await result
            elif asyncio.isfuture(result):
                await result'''

    s3_new = '''            result = processor(task["kind"], task["job_id"], task["user_id"], task["payload"])
            try:
                if asyncio.iscoroutine(result) or isinstance(result, asyncio.Task):
                    await asyncio.wait_for(result, timeout=1800.0)
                elif asyncio.isfuture(result):
                    await asyncio.wait_for(result, timeout=1800.0)
            except (asyncio.TimeoutError, TimeoutError):
                logger.warning("generation queue task timed out (exceeded 30 minutes) | job_id=%s", (task or {}).get("job_id"))
                job_id = str(task.get("job_id") or "")
                await asyncio.to_thread(_finish_task, job_id, "failed", "Task execution exceeded 30 minutes. Timed out.", True)
                continue'''
    text = text.replace(s3_old, s3_new, 1)

    # 3. Update _cleanup_old_tasks to timeout 30 min running tasks
    s4_old = '''    cutoff = now - 86400.0  # 1 day cutoff
    db = SessionLocal()
    try:
        result = db.execute(
            text(
                "DELETE FROM generation_task_queue WHERE status IN ('completed', 'failed', 'canceled') AND created_at < :cutoff"
            ),
            {"cutoff": cutoff},
        )
        db.commit()
        if (result.rowcount or 0) > 0:
            logger.info("generation queue cleanup deleted %s old tasks", result.rowcount)
    except Exception as exc:'''

    s4_new = '''    cutoff = now - 86400.0  # 1 day cutoff
    timeout_cutoff = now - 1800.0 # 30 min timeout for running tasks
    db = SessionLocal()
    try:
        # Mark 30+ min long running tasks as failed
        r_timeout = db.execute(
            text(
                """
                UPDATE generation_task_queue 
                SET status = 'failed', 
                    error = 'Task running for over 30 minutes. Timed out.',
                    finished_at = :now
                WHERE status = 'running' 
                  AND COALESCE(started_at, created_at) < :timeout_cutoff
                """
            ),
            {"now": now, "timeout_cutoff": timeout_cutoff},
        )
        db.commit()
        if (r_timeout.rowcount or 0) > 0:
            logger.warning("generation queue sweep timed out %s running tasks (>30m)", r_timeout.rowcount)

        result = db.execute(
            text(
                "DELETE FROM generation_task_queue WHERE status IN ('completed', 'failed', 'canceled') AND created_at < :cutoff"
            ),
            {"cutoff": cutoff},
        )
        db.commit()
        if (result.rowcount or 0) > 0:
            logger.info("generation queue cleanup deleted %s old tasks", result.rowcount)
    except Exception as exc:'''
    
    text = text.replace(s4_old, s4_new, 1)

    with open('backend/app/services/generation_task_queue.py', 'w', encoding='utf-8') as f:
        f.write(text)

if __name__ == '__main__':
    main()