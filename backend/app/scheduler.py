"""
KredoBook - Background Scheduler

Runs the monthly reminder job automatically on the 1st of every month at 9:00 AM IST.
Uses APScheduler with a background thread scheduler embedded in the FastAPI process.
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("loantracker.scheduler")

# Single global scheduler instance
_scheduler: BackgroundScheduler | None = None


def _run_monthly_reminders() -> None:
    """
    Job function that APScheduler calls on the 1st of every month.
    Opens its own DB session so it is safe to run in a background thread.
    """
    from app.database import SessionLocal
    from app.services.reminder_service import send_monthly_reminders_for_all

    logger.info("[Scheduler] Monthly reminder job started.")
    db = SessionLocal()
    try:
        result = send_monthly_reminders_for_all(db=db)
        logger.info(
            f"[Scheduler] Monthly reminders done: "
            f"sent={result.get('sent', 0)}, "
            f"skipped={result.get('skipped', 0)}, "
            f"failed={result.get('failed', 0)}"
        )
    except Exception as e:
        logger.error(f"[Scheduler] Monthly reminder job failed: {e}")
    finally:
        db.close()


def start_scheduler() -> None:
    """Start the APScheduler background scheduler."""
    global _scheduler

    if _scheduler and _scheduler.running:
        logger.warning("[Scheduler] Scheduler already running, skipping start.")
        return

    _scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

    # Fire on the 1st of every month at 09:00 AM IST
    _scheduler.add_job(
        func=_run_monthly_reminders,
        trigger=CronTrigger(day=1, hour=9, minute=0, timezone="Asia/Kolkata"),
        id="monthly_reminders",
        name="KredoBook Monthly Payment Reminders",
        replace_existing=True,
        misfire_grace_time=3600,  # Allow up to 1 hour late start
    )

    _scheduler.start()
    logger.info(
        "[Scheduler] Started. Monthly reminders will fire on the 1st of every month at 09:00 AM IST."
    )


def stop_scheduler() -> None:
    """Gracefully stop the scheduler on app shutdown."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Stopped.")


def get_scheduler_status() -> dict:
    """Return current scheduler status and next scheduled run info."""
    if not _scheduler or not _scheduler.running:
        return {"running": False, "jobs": []}

    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else "Not scheduled",
        })

    return {"running": True, "jobs": jobs}
