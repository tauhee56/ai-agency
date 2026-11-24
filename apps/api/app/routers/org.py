from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_membership
from app.models.department import Department
from app.models.employee import Employee
from app.models.user import User
from app.schemas.org import (
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
    EmployeeCreate,
    EmployeeOut,
    EmployeeUpdate,
    OrgSnapshot,
    SeedTemplateRequest,
)
from app.security.auth import get_current_user
from app.services.activity import activity_hub
from app.services.audit import write_audit
from app.services.org import build_org_chart, seed_startup_default

router = APIRouter(prefix="/companies/{company_id}", tags=["org"])


@router.get("/org", response_model=OrgSnapshot)
def get_org(
    company_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> OrgSnapshot:
    require_membership(db, company_id, user.id)
    departments = (
        db.query(Department).filter(Department.company_id == company_id).order_by(Department.name).all()
    )
    employees = db.query(Employee).filter(Employee.company_id == company_id).order_by(Employee.title).all()
    ceo = next((e for e in employees if e.codename == "ceo"), None)
    return OrgSnapshot(
        departments=[DepartmentOut.model_validate(d) for d in departments],
        employees=[EmployeeOut.model_validate(e) for e in employees],
        chart=build_org_chart(employees),
        ceo=EmployeeOut.model_validate(ceo) if ceo else None,
    )


@router.post("/org/seed", response_model=OrgSnapshot)
async def seed_org(
    company_id: UUID,
    body: SeedTemplateRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> OrgSnapshot:
    require_membership(db, company_id, user.id)
    if body.template != "startup_default":
        raise HTTPException(status_code=400, detail="Unknown template")
    result = seed_startup_default(db, company_id)
    write_audit(
        db,
        action="org.seed",
        actor_user_id=user.id,
        company_id=company_id,
        resource_type="company",
        resource_id=company_id,
        payload=result,
        ip=request.client.host if request.client else None,
    )
    db.commit()
    await activity_hub.publish(company_id, "org.seeded", result)
    return get_org(company_id, user, db)


@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(
    company_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[DepartmentOut]:
    require_membership(db, company_id, user.id)
    rows = db.query(Department).filter(Department.company_id == company_id).order_by(Department.name).all()
    return [DepartmentOut.model_validate(r) for r in rows]


@router.post("/departments", response_model=DepartmentOut, status_code=201)
async def create_department(
    company_id: UUID,
    body: DepartmentCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DepartmentOut:
    require_membership(db, company_id, user.id)
    row = Department(
        company_id=company_id,
        name=body.name,
        description=body.description,
        parent_department_id=body.parent_department_id,
        lead_employee_id=body.lead_employee_id,
    )
    db.add(row)
    db.flush()
    write_audit(
        db,
        action="department.create",
        actor_user_id=user.id,
        company_id=company_id,
        resource_type="department",
        resource_id=row.id,
        payload={"name": row.name},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(row)
    await activity_hub.publish(company_id, "department.created", {"name": row.name})
    return DepartmentOut.model_validate(row)


@router.patch("/departments/{department_id}", response_model=DepartmentOut)
async def update_department(
    company_id: UUID,
    department_id: UUID,
    body: DepartmentUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DepartmentOut:
    require_membership(db, company_id, user.id)
    row = (
        db.query(Department)
        .filter(Department.id == department_id, Department.company_id == company_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Department not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    await activity_hub.publish(company_id, "department.updated", {"name": row.name})
    return DepartmentOut.model_validate(row)


@router.delete("/departments/{department_id}", status_code=204)
async def delete_department(
    company_id: UUID,
    department_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    require_membership(db, company_id, user.id)
    row = (
        db.query(Department)
        .filter(Department.id == department_id, Department.company_id == company_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Department not found")
    db.query(Employee).filter(Employee.department_id == department_id).update({"department_id": None})
    db.delete(row)
    db.commit()
    await activity_hub.publish(company_id, "department.deleted", {"id": str(department_id)})


@router.get("/employees", response_model=list[EmployeeOut])
def list_employees(
    company_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[EmployeeOut]:
    require_membership(db, company_id, user.id)
    rows = db.query(Employee).filter(Employee.company_id == company_id).order_by(Employee.title).all()
    return [EmployeeOut.model_validate(r) for r in rows]


@router.post("/employees", response_model=EmployeeOut, status_code=201)
async def create_employee(
    company_id: UUID,
    body: EmployeeCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> EmployeeOut:
    require_membership(db, company_id, user.id)
    if db.query(Employee).filter(Employee.company_id == company_id, Employee.codename == body.codename).first():
        raise HTTPException(status_code=409, detail="Codename already exists")
    ceo = (
        db.query(Employee)
        .filter(Employee.company_id == company_id, Employee.codename == "ceo")
        .first()
    )
    manager_id = body.manager_employee_id
    if manager_id is None and ceo and body.codename != "ceo":
        manager_id = ceo.id
    row = Employee(
        company_id=company_id,
        title=body.title,
        codename=body.codename,
        role_prompt=body.role_prompt,
        department_id=body.department_id,
        manager_employee_id=manager_id,
        model_config_id=body.model_config_id,
        adapter_pref=body.adapter_pref,
        status=body.status,
        capabilities=body.capabilities or {},
    )
    db.add(row)
    db.flush()
    write_audit(
        db,
        action="employee.create",
        actor_user_id=user.id,
        company_id=company_id,
        resource_type="employee",
        resource_id=row.id,
        payload={"codename": row.codename, "title": row.title},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(row)
    await activity_hub.publish(company_id, "employee.created", {"codename": row.codename})
    return EmployeeOut.model_validate(row)


@router.patch("/employees/{employee_id}", response_model=EmployeeOut)
async def update_employee(
    company_id: UUID,
    employee_id: UUID,
    body: EmployeeUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> EmployeeOut:
    require_membership(db, company_id, user.id)
    row = (
        db.query(Employee)
        .filter(Employee.id == employee_id, Employee.company_id == company_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Employee not found")
    data = body.model_dump(exclude_unset=True)
    if "manager_employee_id" in data and data["manager_employee_id"] == row.id:
        raise HTTPException(status_code=400, detail="Employee cannot manage themselves")
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    await activity_hub.publish(company_id, "employee.updated", {"codename": row.codename, "status": row.status})
    return EmployeeOut.model_validate(row)


@router.delete("/employees/{employee_id}", status_code=204)
async def delete_employee(
    company_id: UUID,
    employee_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    require_membership(db, company_id, user.id)
    row = (
        db.query(Employee)
        .filter(Employee.id == employee_id, Employee.company_id == company_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Employee not found")
    if row.codename == "ceo":
        raise HTTPException(status_code=400, detail="Cannot delete AI CEO root employee")
    db.query(Employee).filter(Employee.manager_employee_id == employee_id).update(
        {"manager_employee_id": row.manager_employee_id}
    )
    db.query(Department).filter(Department.lead_employee_id == employee_id).update(
        {"lead_employee_id": None}
    )
    db.delete(row)
    db.commit()
    await activity_hub.publish(company_id, "employee.deleted", {"id": str(employee_id)})
