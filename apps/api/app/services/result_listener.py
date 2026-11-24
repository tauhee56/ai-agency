"""Background loop: pull adapter results from Redis and apply to DB."""

from __future__ import annotations

import asyncio
import json
import logging

from app.db import SessionLocal
from app.services.activity import activity_hub
from app.services.orchestrator import apply_worker_result, append_event
from app.services.queue import RESULT_QUEUE, publish_run_event, redis_client
from app.models.work import TaskRun
from datetime import UTC, datetime
from uuid import UUID

logger = logging.getLogger("aicos.results")


async def result_listener_loop(stop: asyncio.Event) -> None:
    client = redis_client()
    while not stop.is_set():
        try:
            item = await asyncio.to_thread(client.blpop, RESULT_QUEUE, 1)
            if not item:
                continue
            _, raw = item
            result = json.loads(raw)
            db = SessionLocal()
            try:
                # mark started if still queued
                run_id = UUID(result["run_id"])
                run = db.get(TaskRun, run_id)
                if run and run.status == "queued":
                    run.status = "running"
                    run.started_at = datetime.now(UTC)
                    append_event(db, run_id, "run.started", {})
                    db.commit()
                for ev in result.get("events") or []:
                    append_event(db, run_id, ev.get("type") or "agent.message", ev.get("payload") or {})
                    publish_run_event(run_id, ev)
                apply_worker_result(db, result)
                if run:
                    await activity_hub.publish(
                        run.company_id,
                        "run.finished",
                        {"run_id": str(run_id), "status": result.get("status")},
                    )
            finally:
                db.close()
        except Exception:
            logger.exception("result listener error")
            await asyncio.sleep(0.5)
