from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_membership
from app.models.schedule import PlaybookSchedule
from app.models.user import User
from app.security.auth import get_current_user
from app.services.audit import write_audit
from app.services.playbooks import get_playbook
from app.services.scheduler import fire_schedule

router = APIRouter(prefix="/companies/{company_id}/schedules", tags=["schedules"])


class ScheduleCreate(BaseModel):
    playbook_id: str
    name: str = Field(min_length=1, max_length=160)
    cron: str | None = "@hourly"
    trigger: str = "cron"
    goal_template: str = ""
    precheck: str | None = None
    enabled: bool = False  # disabled-by-default


class ScheduleUpdate(BaseModel):
    name: str | None = None
    cron: str | None = None
    trigger: str | None = None
    goal_template: str | None = None
    precheck: str | None = None
    enabled: bool | None = None


class ScheduleOut(BaseModel):
    id: UUID
    company_id: UUID
    playbook_id: str
    name: str
    cron: str | None
    trigger: str
    enabled: bool
    goal_template: str
    precheck: str | None
    last_run_at: Any | None
    last_run_status: str | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[ScheduleOut])
def list_schedules(
    company_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ScheduleOut]:
    require_membership(db, company_id, user.id)
    rows = (
        db.query(PlaybookSchedule)
        .filter(PlaybookSchedule.company_id == company_id)
        .order_by(PlaybookSchedule.created_at.desc())
        .all()
    )
    return [ScheduleOut.model_validate(r) for r in rows]


@router.post("", response_model=ScheduleOut, status_code=201)
def create_schedule(
    company_id: UUID,
    body: ScheduleCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ScheduleOut:
    require_membership(db, company_id, user.id)
    if not get_playbook(body.playbook_id):
        raise HTTPException(status_code=404, detail="Playbook not found")
    if body.trigger not in ("cron", "task.failed", "webhook"):
        raise HTTPException(status_code=400, detail="Invalid trigger")
    row = PlaybookSchedule(
        company_id=company_id,
        playbook_id=body.playbook_id,
        name=body.name,
        cron=body.cron,
        trigger=body.trigger,
        enabled=False,  # always disabled-by-default; enable via PATCH
        goal_template=body.goal_template,
        precheck=body.precheck,
    )
    db.add(row)
    db.flush()
    write_audit(
        db,
        action="schedule.create",
        actor_user_id=user.id,
        company_id=company_id,
        resource_type="playbook_schedule",
        resource_id=row.id,
        payload={"playbook_id": row.playbook_id, "enabled": row.enabled},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(row)
    return ScheduleOut.model_validate(row)


@router.patch("/{schedule_id}", response_model=ScheduleOut)
def update_schedule(
    company_id: UUID,
    schedule_id: UUID,
    body: ScheduleUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ScheduleOut:
    require_membership(db, company_id, user.id)
    row = db.get(PlaybookSchedule, schedule_id)
    if not row or row.company_id != company_id:
        raise HTTPException(status_code=404, detail="Schedule not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return ScheduleOut.model_validate(row)


@router.post("/{schedule_id}/run")
async def run_schedule_now(
    company_id: UUID,
    schedule_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    require_membership(db, company_id, user.id)
    row = db.get(PlaybookSchedule, schedule_id)
    if not row or row.company_id != company_id:
        raise HTTPException(status_code=404, detail="Schedule not found")
    result = await fire_schedule(db, row)
    if not result:
        raise HTTPException(status_code=400, detail=row.last_run_status or "Failed to fire")
    if result.get("status") == "blocked":
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(
    company_id: UUID,
    schedule_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    require_membership(db, company_id, user.id)
    row = db.get(PlaybookSchedule, schedule_id)
    if not row or row.company_id != company_id:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(row)
    db.commit()
