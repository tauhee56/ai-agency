from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_membership
from app.models.employee import Employee
from app.models.user import User
from app.security.auth import get_current_user
from app.services.audit import write_audit
from app.services.soul import export_soul, import_soul, tidy_employee_soul

router = APIRouter(prefix="/companies/{company_id}/employees", tags=["soul"])


class SoulOut(BaseModel):
    employee_id: UUID
    markdown: str


class SoulPut(BaseModel):
    markdown: str = Field(min_length=1, max_length=20000)


@router.get("/{employee_id}/soul", response_model=SoulOut)
def get_soul(
    company_id: UUID,
    employee_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SoulOut:
    require_membership(db, company_id, user.id)
    emp = db.get(Employee, employee_id)
    if not emp or emp.company_id != company_id:
        raise HTTPException(status_code=404, detail="Employee not found")
    return SoulOut(employee_id=emp.id, markdown=export_soul(db, emp))


@router.put("/{employee_id}/soul", response_model=SoulOut)
def put_soul(
    company_id: UUID,
    employee_id: UUID,
    body: SoulPut,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SoulOut:
    require_membership(db, company_id, user.id)
    emp = db.get(Employee, employee_id)
    if not emp or emp.company_id != company_id:
        raise HTTPException(status_code=404, detail="Employee not found")
    meta = import_soul(db, emp, body.markdown)
    write_audit(
        db,
        action="employee.soul.update",
        actor_user_id=user.id,
        company_id=company_id,
        resource_type="employee",
        resource_id=emp.id,
        payload=meta,
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return SoulOut(employee_id=emp.id, markdown=export_soul(db, emp))


@router.post("/{employee_id}/soul/tidy")
def tidy_soul(
    company_id: UUID,
    employee_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    require_membership(db, company_id, user.id)
    emp = db.get(Employee, employee_id)
    if not emp or emp.company_id != company_id:
        raise HTTPException(status_code=404, detail="Employee not found")
    result = tidy_employee_soul(db, employee_id)
    db.commit()
    return result or {}
