"""Redis job queue for adapter workers (Adapter Protocol v1)."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import redis

from app.config import get_settings

JOB_QUEUE = "aicos:jobs"
OPENHANDS_JOB_QUEUE = "aicos:jobs:openhands"
RESULT_QUEUE = "aicos:results"
EVENTS_CHANNEL_PREFIX = "aicos:run:"


def redis_client() -> redis.Redis:
    return redis.from_url(get_settings().redis_url, decode_responses=True)


def enqueue_job(job: dict[str, Any]) -> None:
    client = redis_client()
    queue = OPENHANDS_JOB_QUEUE if job.get("adapter") == "openhands" else JOB_QUEUE
    client.rpush(queue, json.dumps(job))


def publish_run_event(run_id: UUID | str, event: dict[str, Any]) -> None:
    client = redis_client()
    client.publish(f"{EVENTS_CHANNEL_PREFIX}{run_id}", json.dumps(event))


def budget_blocked_key(company_id: UUID | str) -> str:
    return f"aicos:budget_block:{company_id}"


def set_budget_block(company_id: UUID | str, blocked: bool) -> None:
    client = redis_client()
    key = budget_blocked_key(company_id)
    if blocked:
        client.set(key, "1")
    else:
        client.delete(key)


def is_budget_blocked(company_id: UUID | str) -> bool:
    client = redis_client()
    return client.get(budget_blocked_key(company_id)) == "1"
