import re

with open('backend/app/services/generation_task_queue.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_str = """
        except asyncio.CancelledError:
            if task:
                job_id = str(task.get("job_id") or "")
                await asyncio.to_thread(_finish_task, job_id, status="canceled", error="cancelled", only_if_running=True)
            break
        except Exception as exc:
            logger.exception("generation queue task failed | job_id=%s", (task or {}).get("job_id"))
            if task:
                job_id = str(task.get("job_id") or "")
                latest = await asyncio.to_thread(get_generation_task_status, job_id) or {}
                if str(latest.get("status") or "").strip().lower() != "canceled":
                    await asyncio.to_thread(_finish_task, job_id, status="failed", error=str(exc), only_if_running=True)
"""

new_str = """
        except asyncio.CancelledError:
            if task:
                job_id = str(task.get("job_id") or "")
                await asyncio.to_thread(_finish_task, job_id, status="canceled", error="cancelled", only_if_running=True)
            break
        except Exception as exc:
            logger.exception("generation queue task failed | job_id=%s", (task or {}).get("job_id"))
            if task:
                job_id = str(task.get("job_id") or "")
                latest = await asyncio.to_thread(get_generation_task_status, job_id) or {}
                if str(latest.get("status") or "").strip().lower() != "canceled":
                    await asyncio.to_thread(_finish_task, job_id, status="failed", error=str(exc), only_if_running=True)
            # CAUTION: we must continue, otherwise we exit the loop and the worker dies permanently
            continue
"""

if old_str.strip() in code:
    code = code.replace(old_str.strip(), new_str.strip())
    with open('backend/app/services/generation_task_queue.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print("Updated exception continue successfully.")
else:
    print("Could not find the exception block!")
