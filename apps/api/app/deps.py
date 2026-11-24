from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.company import Membership


def require_membership(db: Session, company_id: UUID, user_id: UUID) -> Membership:
    m = (
        db.query(Membership)
        .filter(Membership.company_id == company_id, Membership.user_id == user_id)
        .first()
    )
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return m
