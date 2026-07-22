"""Gunicorn hooks for AIStory web workers."""

import os


def post_fork(server, worker):
    # Gunicorn worker ids are 1-based; worker 1 is the preferred DB bootstrap leader.
    wid = getattr(worker, "wid", None)
    os.environ["GUNICORN_WORKER_ID"] = str(wid if wid is not None else "")
