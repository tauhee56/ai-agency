"""Playbook schedule tick (Orca M5) — disabled-by-default schedules."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.schedule import PlaybookSchedule
from app.models.work import Project, Task
from app.services.orchestrator import enqueue_task_run
from app.services.playbooks import get_playbook

logger = logging.getLogger("aicos.scheduler")


def _cron_due(cron: str | None, last: datetime | None, now: datetime) -> bool:
    """Minimal cron helper: supports '@hourly', '@daily', or 'every_N_min'."""
    if not cron:
        return False
    cron = cron.strip().lower()
    if last is None:
        return True
    if cron == "@hourly":
        return now - last >= timedelta(hours=1)
    if cron == "@daily":
        return now - last >= timedelta(days=1)
    if cron.startswith("every_") and cron.endswith("_min"):
        try:
            n = int(cron.split("_")[1])
            return now - last >= timedelta(minutes=max(n, 1))
        except ValueError:
            return False
    # Unsupported full cron → never auto-fire (manual run still works)
    return False


async def fire_schedule(db: Session, sched: PlaybookSchedule) -> dict[str, Any] | None:
    pb = get_playbook(sched.playbook_id)
    if not pb:
        sched.last_run_status = "missing_playbook"
        db.commit()
        return None
    if pb.get("requires_metagpt"):
        sched.last_run_status = "metagpt_disabled"
        db.commit()
        return None
    if sched.precheck:
        # Soft precheck: only allow known safe tokens
        if sched.precheck.strip() not in ("ok", "true", "1"):
            sched.last_run_status = "precheck_failed"
            db.commit()
            return {"status": "precheck_failed"}

    project = Project(
        company_id=sched.company_id,
        name=f"Scheduled: {sched.name}",
        description=f"Schedule {sched.id} playbook {sched.playbook_id}",
        status="active",
    )
    db.add(project)
    db.flush()
    task = Task(
        company_id=sched.company_id,
        project_id=project.id,
        title=sched.goal_template or f"Scheduled {pb['name']}",
        description=pb["description"],
        adapter=pb.get("adapter") or "crewai",
        input={"playbook_id": pb["id"], "schedule_id": str(sched.id)},
        status="backlog",
    )
    db.add(task)
    db.flush()
    try:
        run = await enqueue_task_run(db, task=task)
    except ValueError as exc:
        sched.last_run_status = f"blocked:{exc}"
        db.commit()
        return {"status": "blocked", "error": str(exc)}
    sched.last_run_at = datetime.now(UTC)
    sched.last_run_status = "queued"
    db.commit()
    return {"run_id": str(run.id), "schedule_id": str(sched.id)}


async def schedule_tick(db: Session) -> int:
    now = datetime.now(UTC)
    fired = 0
    rows = db.query(PlaybookSchedule).filter(PlaybookSchedule.enabled.is_(True)).all()
    for sched in rows:
        due = False
        if sched.trigger == "cron":
            due = _cron_due(sched.cron, sched.last_run_at, now)
        # task.failed / webhook triggers are event-driven (not tick)
        if due:
            try:
                await fire_schedule(db, sched)
                fired += 1
            except Exception:
                logger.exception("schedule fire failed %s", sched.id)
    return fired
