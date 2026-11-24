import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.models.company import Membership
from app.models.user import User
from app.security.auth import get_current_user
from app.services.activity import activity_hub

router = APIRouter(tags=["activity"])


def _membership_or_404(db: Session, company_id: UUID, user_id: UUID) -> None:
    m = (
        db.query(Membership)
        .filter(Membership.company_id == company_id, Membership.user_id == user_id)
        .first()
    )
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")


@router.get("/companies/{company_id}/activity/stream")
async def activity_sse(
    company_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> StreamingResponse:
    _membership_or_404(db, company_id, user.id)
    queue = await activity_hub.subscribe(company_id)

    async def event_gen():
        try:
            yield "event: connected\ndata: {\"ok\": true}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25)
                    import json

                    yield f"event: activity\ndata: {json.dumps(event)}\n\n"
                except TimeoutError:
                    yield "event: ping\ndata: {}\n\n"
        finally:
            await activity_hub.unsubscribe(company_id, queue)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.websocket("/ws/activity/{company_id}")
async def activity_ws(websocket: WebSocket, company_id: UUID) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return

    from app.config import get_settings
    import jwt

    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = UUID(payload["sub"])
    except Exception:
        await websocket.close(code=4401)
        return

    db = SessionLocal()
    try:
        m = (
            db.query(Membership)
            .filter(Membership.company_id == company_id, Membership.user_id == user_id)
            .first()
        )
        if not m:
            await websocket.close(code=4403)
            return
    finally:
        db.close()

    await websocket.accept()
    queue = await activity_hub.subscribe(company_id)
    try:
        await websocket.send_json({"type": "connected", "payload": {"ok": True}})
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=25)
                await websocket.send_json(event)
            except TimeoutError:
                await websocket.send_json({"type": "ping", "payload": {}})
                # Also drain any client messages to detect disconnect
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
                except TimeoutError:
                    pass
    except WebSocketDisconnect:
        pass
    finally:
        await activity_hub.unsubscribe(company_id, queue)
