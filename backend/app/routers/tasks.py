"""Run the notification scheduler when an outside service (e.g. UptimeRobot) calls a
secret URL every few minutes. This is more punctual than GitHub's scheduled jobs, and
the same visits keep the free web server awake."""

import logging
import secrets
import threading

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from ..config import get_settings
from ..db import SessionLocal

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
log = logging.getLogger("wordpop.tasks")
_running = threading.Lock()


def _run_scheduler() -> None:
    from ..scheduler import run_once  # imported here to avoid a circular import

    if not _running.acquire(blocking=False):
        return  # a run is already in progress
    try:
        with SessionLocal() as db:
            log.info("Scheduler run: %s", run_once(db))
    except Exception:
        log.exception("Scheduler run failed")
    finally:
        _running.release()


@router.api_route("/send-notifications", methods=["GET", "HEAD", "POST"])
def send_notifications(key: str, background: BackgroundTasks):
    expected = get_settings().cron_secret
    if not expected or not secrets.compare_digest(key, expected):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    background.add_task(_run_scheduler)
    return {"ok": True}
