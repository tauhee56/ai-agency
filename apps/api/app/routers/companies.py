from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models.company import Membership
from app.models.employee import Employee
from app.models.user import User
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
) -> dict:
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
    ceo = (
        db.query(Employee)
        .filter(Employee.company_id == company_id, Employee.codename == "ceo")
        .first()
    )
    default = next((m for m in models if m.is_default), models[0] if models else None)
    return {
        "company": CompanyOut.model_validate(membership.company),
        "role": membership.rbac_role,
        "model_status": {
            "configured": len(models) > 0,
            "count": len(models),
            "default": (
                {"id": str(default.id), "name": default.name, "provider": default.provider, "model": default.model_name}
                if default
                else None
            ),
        },
        "ceo": (
            {"id": str(ceo.id), "title": ceo.title, "status": ceo.status}
            if ceo
            else None
        ),
        "phase": 1,
    }
