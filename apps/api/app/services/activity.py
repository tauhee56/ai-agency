"""In-memory activity fan-out for Phase 1 live feed stub."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Any
from uuid import UUID


class ActivityHub:
    def __init__(self, history_size: int = 50) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)
        self._history: dict[str, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=history_size)
        )
        self._lock = asyncio.Lock()

    def _key(self, company_id: UUID | str) -> str:
        return str(company_id)

    async def publish(self, company_id: UUID | str, event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {
            "type": event_type,
            "payload": payload or {},
            "at": datetime.now(UTC).isoformat(),
        }
        key = self._key(company_id)
        async with self._lock:
            self._history[key].append(event)
            queues = list(self._subscribers[key])
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass
        return event

    async def subscribe(self, company_id: UUID | str) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        key = self._key(company_id)
        async with self._lock:
            self._subscribers[key].add(q)
            for past in self._history[key]:
                try:
                    q.put_nowait(past)
                except asyncio.QueueFull:
                    break
        return q

    async def unsubscribe(self, company_id: UUID | str, q: asyncio.Queue[dict[str, Any]]) -> None:
        key = self._key(company_id)
        async with self._lock:
            self._subscribers[key].discard(q)


activity_hub = ActivityHub()
