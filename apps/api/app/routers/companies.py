from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models.company import Membership
from app.models.department import Department
from app.models.employee import Employee
from app.models.user import User
from app.models.work import Approval, Project, Task, TaskRun
from app.schemas.company import CompanyOut, MembershipOut
from app.security.auth import get_current_user

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/mine", response_model=list[MembershipOut])
def my_companies(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[MembershipOut]:
    rows = (
        db.query(Membership)
        .options(joinedload(Membership.company))
        .filter(Membership.user_id == user.id)
        .all()
    )
    return [MembershipOut.model_validate(r) for r in rows]


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(
    company_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CompanyOut:
    membership = (
        db.query(Membership)
        .options(joinedload(Membership.company))
        .filter(Membership.company_id == company_id, Membership.user_id == user.id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return CompanyOut.model_validate(membership.company)


@router.get("/{company_id}/overview")
def company_overview(
    company_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    membership = (
        db.query(Membership)
        .options(joinedload(Membership.company))
        .filter(Membership.company_id == company_id, Membership.user_id == user.id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    from app.models.model_config import ModelConfig

    models = db.query(ModelConfig).filter(ModelConfig.company_id == company_id).all()
    employees = db.query(Employee).filter(Employee.company_id == company_id).all()
    departments = db.query(Department).filter(Department.company_id == company_id).all()
    projects = (
        db.query(Project)
        .filter(Project.company_id == company_id, Project.status == "active")
        .order_by(Project.created_at.desc())
        .limit(8)
        .all()
    )
    needs_you = (
        db.query(Approval)
        .filter(Approval.company_id == company_id, Approval.status == "pending")
        .count()
    )
    active_runs = (
        db.query(TaskRun)
        .filter(TaskRun.company_id == company_id, TaskRun.status.in_(("queued", "running")))
        .count()
    )
    working = (
        db.query(Task)
        .filter(Task.company_id == company_id, Task.status.in_(("ready", "running")))
        .count()
    )
    ceo = next((e for e in employees if e.codename == "ceo"), None)
    default = next((m for m in models if m.is_default), models[0] if models else None)

    # Who is working on what
    floor: list[dict[str, Any]] = []
    for emp in employees:
        if emp.codename == "ceo":
            continue
        task = (
            db.query(Task)
            .filter(
                Task.company_id == company_id,
                Task.assignee_employee_id == emp.id,
                Task.status.in_(("ready", "running", "blocked")),
            )
            .order_by(Task.updated_at.desc())
            .first()
        )
        work_state = "idle"
        current = None
        if task:
            work_state = "working" if task.status in ("ready", "running") else "blocked"
            current = {"id": str(task.id), "title": task.title, "status": task.status}
        elif emp.status == "paused":
            work_state = "paused"
        floor.append(
            {
                "id": str(emp.id),
                "title": emp.title,
                "codename": emp.codename,
                "status": emp.status,
                "work_state": work_state,
                "current_task": current,
            }
        )

    return {
        "company": CompanyOut.model_validate(membership.company),
        "role": membership.rbac_role,
        "ceo": (
            {"id": str(ceo.id), "title": ceo.title, "status": ceo.status}
            if ceo
            else None
        ),
        "pulse": {
            "employees": len(employees),
            "departments": len(departments),
            "active_projects": len(projects),
            "needs_you": needs_you,
            "people_working": working,
            "active_workstreams": active_runs,
        },
        "projects": [
            {"id": str(p.id), "name": p.name, "description": (p.description or "")[:160]}
            for p in projects
        ],
        "departments": [{"id": str(d.id), "name": d.name} for d in departments],
        "floor": floor,
        "model_status": {
            "configured": len(models) > 0,
            "count": len(models),
            "default": (
                {
                    "id": str(default.id),
                    "name": default.name,
                    "provider": default.provider,
                    "model": default.model_name,
                }
                if default
                else None
            ),
        },
        "phase": 6,
    }
