"""Background loop: pull adapter results + heartbeats from Redis."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from app.db import SessionLocal
from app.models.work import TaskRun
from app.services.activity import activity_hub
from app.services.orchestrator import apply_worker_result, append_event
from app.services.queue import RESULT_QUEUE, publish_run_event, redis_client
from app.services.scheduler import schedule_tick

logger = logging.getLogger("aicos.results")

HEARTBEAT_QUEUE = "aicos:heartbeats"


async def result_listener_loop(stop: asyncio.Event) -> None:
    client = redis_client()
    ticks = 0
    while not stop.is_set():
        try:
            # Heartbeats (non-blocking)
            hb = client.lpop(HEARTBEAT_QUEUE)
            if hb:
                data = json.loads(hb)
                db = SessionLocal()
                try:
                    run_id = UUID(data["run_id"])
                    run = db.get(TaskRun, run_id)
                    if run and not run.terminal_received:
                        run.heartbeat_at = datetime.now(UTC)
                        if run.status == "queued":
                            run.status = "running"
                            run.started_at = run.started_at or datetime.now(UTC)
                        append_event(
                            db,
                            run_id,
                            "run.heartbeat",
                            {
                                "dispatch_id": data.get("dispatch_id"),
                                "at": run.heartbeat_at.isoformat(),
                            },
                        )
                        db.commit()
                        publish_run_event(
                            run_id,
                            {"type": "run.heartbeat", "payload": {"dispatch_id": data.get("dispatch_id")}},
                        )
                finally:
                    db.close()

            item = await asyncio.to_thread(client.blpop, RESULT_QUEUE, 1)
            if item:
                _, raw = item
                result = json.loads(raw)
                # Drain pending heartbeats before terminal so v1.1 heartbeats are recorded
                while True:
                    hb2 = client.lpop(HEARTBEAT_QUEUE)
                    if not hb2:
                        break
                    try:
                        data = json.loads(hb2)
                        dbh = SessionLocal()
                        try:
                            rid = UUID(data["run_id"])
                            run_hb = dbh.get(TaskRun, rid)
                            if run_hb and not run_hb.terminal_received:
                                run_hb.heartbeat_at = datetime.now(UTC)
                                if run_hb.status == "queued":
                                    run_hb.status = "running"
                                    run_hb.started_at = run_hb.started_at or datetime.now(UTC)
                                append_event(
                                    dbh,
                                    rid,
                                    "run.heartbeat",
                                    {"dispatch_id": data.get("dispatch_id")},
                                )
                                dbh.commit()
                        finally:
                            dbh.close()
                    except Exception:
                        logger.exception("heartbeat drain error")

                db = SessionLocal()
                try:
                    run_id = UUID(result["run_id"])
                    run = db.get(TaskRun, run_id)
                    if run and run.status == "queued" and not run.terminal_received:
                        run.status = "running"
                        run.started_at = datetime.now(UTC)
                        append_event(
                            db,
                            run_id,
                            "run.started",
                            {
                                "dispatch_id": result.get("dispatch_id")
                                or (str(run.dispatch_id) if run.dispatch_id else None)
                            },
                        )
                        db.commit()
                    terminal_types = {
                        "run.finished",
                        "run.failed",
                        "run.cancelled",
                        "run.timed_out",
                        "run.succeeded",
                    }
                    for ev in result.get("events") or []:
                        et = ev.get("type") or "agent.message"
                        if et in terminal_types:
                            continue  # single terminal via apply_worker_result
                        if et == "run.heartbeat":
                            # also accept heartbeats embedded in result events
                            if run and not run.terminal_received:
                                run.heartbeat_at = datetime.now(UTC)
                        if not run or not run.terminal_received:
                            append_event(db, run_id, et, ev.get("payload") or {})
                            publish_run_event(run_id, ev)
                    # Ensure at least one heartbeat marker if worker sent heartbeat_at
                    if run and not run.terminal_received and result.get("heartbeat_at") and not run.heartbeat_at:
                        run.heartbeat_at = datetime.now(UTC)
                        append_event(
                            db,
                            run_id,
                            "run.heartbeat",
                            {"dispatch_id": result.get("dispatch_id"), "source": "result"},
                        )
                        db.commit()
                    apply_worker_result(db, result)
                    if run:
                        await activity_hub.publish(
                            run.company_id,
                            "run.finished",
                            {
                                "run_id": str(run_id),
                                "status": result.get("status"),
                                "dispatch_id": result.get("dispatch_id"),
                                "outcome": result.get("outcome") or result.get("status"),
                            },
                        )
                finally:
                    db.close()

            ticks += 1
            if ticks % 15 == 0:
                # ~every 15s when idle loops
                db = SessionLocal()
                try:
                    await schedule_tick(db)
                finally:
                    db.close()
        except Exception:
            logger.exception("result listener error")
            await asyncio.sleep(0.5)
