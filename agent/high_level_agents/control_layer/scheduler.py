from typing import Any, Dict
import threading
import time


class Scheduler:
    """Simple in-memory scheduler to trigger campaigns.

    Replace with a persistent scheduler (cron, Airflow, or a message queue) for
    production.
    """

    def __init__(self):
        self.jobs = {}

    def schedule(self, name: str, interval_seconds: int, callback, *args, **kwargs):
        if name in self.jobs:
            raise RuntimeError('job already scheduled')

        def runner():
            while True:
                time.sleep(interval_seconds)
                callback(*args, **kwargs)

        t = threading.Thread(target=runner, daemon=True)
        t.start()
        self.jobs[name] = t


# TODOs for Scheduler
# - Persist scheduled jobs to a durable store for restarts
# - Add cron-style scheduling support and time-window constraints
# - Add unit tests for scheduling and job uniqueness
