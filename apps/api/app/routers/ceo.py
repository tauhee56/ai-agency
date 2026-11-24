from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.company import Membership
from app.models.user import User
from app.schemas.ceo import CeoAdviseRequest, CeoAdviseResponse, CeoDirectRequest, CeoDirectResponse
from app.security.auth import get_current_user
from app.services.activity import activity_hub
from app.services.audit import write_audit
from app.services.ceo import advise
from app.services.ceo_direct import ceo_direct_company

router = APIRouter(prefix="/ceo", tags=["ceo"])


@router.post("/advise", response_model=CeoAdviseResponse)
async def ceo_advise(
    body: CeoAdviseRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CeoAdviseResponse:
    memberships = db.query(Membership).filter(Membership.user_id == user.id).all()
    if not memberships:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No company membership")

    if body.company_id:
        company_id = UUID(body.company_id)
        if not any(m.company_id == company_id for m in memberships):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    else:
        company_id = memberships[0].company_id

    try:
        result = await advise(db, company_id=company_id, message=body.message)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    write_audit(
        db,
        action="ceo.stub.invoke",
        actor_user_id=user.id,
        company_id=company_id,
        resource_type="ceo",
        payload={
            "stub": result["stub"],
            "model_used": result.get("model_used"),
            "message_len": len(body.message),
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()

    await activity_hub.publish(
        company_id,
        "ceo.advised",
        {
            "stub": result["stub"],
            "acknowledgment": result["acknowledgment"][:200],
        },
    )
    return CeoAdviseResponse(**result)


@router.post("/direct", response_model=CeoDirectResponse)
async def ceo_direct(
    body: CeoDirectRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CeoDirectResponse:
    """Founder talks to the AI CEO — CEO creates projects, tasks, and puts people to work."""
    memberships = db.query(Membership).filter(Membership.user_id == user.id).all()
    if not memberships:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No company membership")

    if body.company_id:
        company_id = UUID(body.company_id)
        if not any(m.company_id == company_id for m in memberships):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    else:
        company_id = memberships[0].company_id

    result = await ceo_direct_company(
        db, company_id=company_id, message=body.message, start_work=body.start_work
    )
    write_audit(
        db,
        action="ceo.direct",
        actor_user_id=user.id,
        company_id=company_id,
        resource_type="project",
        resource_id=UUID(result["project"]["id"]),
        payload={"tasks": len(result["tasks"]), "runs": len(result["runs_started"])},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return CeoDirectResponse(**result)
