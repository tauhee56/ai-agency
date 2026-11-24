from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent


def write_audit(
    db: Session,
    *,
    action: str,
    actor_user_id: UUID | None = None,
    company_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    payload: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        action=action,
        actor_user_id=actor_user_id,
        company_id=company_id,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=payload or {},
        ip=ip,
    )
    db.add(event)
    db.flush()
    return event
