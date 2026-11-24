"""Phase 6 lightweight hardening: rate limit + request id logging."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit: int = 120, window: int = 60) -> None:
        super().__init__(app)
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip websockets / health
        if request.url.path.startswith("/ws/") or request.url.path == "/health":
            return await call_next(request)
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        q = self._hits[ip]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        q.append(now)
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
