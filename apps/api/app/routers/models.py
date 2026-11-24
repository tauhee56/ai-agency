from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.company import Membership
from app.models.model_config import ModelConfig
from app.models.user import User
from app.schemas.models import ModelConfigCreate, ModelConfigOut, ModelConfigUpdate
from app.security.auth import get_current_user
from app.security.crypto import encrypt_secret
from app.services.activity import activity_hub
from app.services.audit import write_audit

router = APIRouter(prefix="/companies/{company_id}/models", tags=["models"])


def _require_membership(db: Session, company_id: UUID, user_id: UUID) -> Membership:
    m = (
        db.query(Membership)
        .filter(Membership.company_id == company_id, Membership.user_id == user_id)
        .first()
    )
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return m


def _to_out(row: ModelConfig) -> ModelConfigOut:
    return ModelConfigOut(
        id=row.id,
        company_id=row.company_id,
        name=row.name,
        provider=row.provider,
        model_name=row.model_name,
        base_url=row.base_url,
        is_default=row.is_default,
        has_api_key=bool(row.api_key_encrypted),
        extra=row.extra or {},
    )


@router.get("", response_model=list[ModelConfigOut])
def list_models(
    company_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ModelConfigOut]:
    _require_membership(db, company_id, user.id)
    rows = db.query(ModelConfig).filter(ModelConfig.company_id == company_id).order_by(ModelConfig.created_at).all()
    return [_to_out(r) for r in rows]


@router.post("", response_model=ModelConfigOut, status_code=201)
async def create_model(
    company_id: UUID,
    body: ModelConfigCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ModelConfigOut:
    _require_membership(db, company_id, user.id)

    if body.is_default:
        db.execute(
            update(ModelConfig).where(ModelConfig.company_id == company_id).values(is_default=False)
        )

    # First model becomes default automatically
    existing_count = db.query(ModelConfig).filter(ModelConfig.company_id == company_id).count()
    is_default = body.is_default or existing_count == 0

    row = ModelConfig(
        company_id=company_id,
        name=body.name,
        provider=body.provider,
        model_name=body.model_name,
        base_url=body.base_url,
        api_key_encrypted=encrypt_secret(body.api_key) if body.api_key else None,
        is_default=is_default,
        extra=body.extra or {},
    )
    db.add(row)
    db.flush()
    write_audit(
        db,
        action="model.create",
        actor_user_id=user.id,
        company_id=company_id,
        resource_type="model_config",
        resource_id=row.id,
        payload={"provider": row.provider, "model_name": row.model_name, "name": row.name},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(row)
    await activity_hub.publish(
        company_id,
        "model.created",
        {"name": row.name, "provider": row.provider, "model": row.model_name},
    )
    return _to_out(row)


@router.patch("/{model_id}", response_model=ModelConfigOut)
async def update_model(
    company_id: UUID,
    model_id: UUID,
    body: ModelConfigUpdate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ModelConfigOut:
    _require_membership(db, company_id, user.id)
    row = (
        db.query(ModelConfig)
        .filter(ModelConfig.id == model_id, ModelConfig.company_id == company_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model config not found")

    data = body.model_dump(exclude_unset=True)
    api_key = data.pop("api_key", None)
    if body.is_default:
        db.execute(
            update(ModelConfig).where(ModelConfig.company_id == company_id).values(is_default=False)
        )
    for k, v in data.items():
        setattr(row, k, v)
    if api_key is not None:
        row.api_key_encrypted = encrypt_secret(api_key) if api_key else None

    write_audit(
        db,
        action="model.update",
        actor_user_id=user.id,
        company_id=company_id,
        resource_type="model_config",
        resource_id=row.id,
        payload={"fields": list(data.keys()) + (["api_key"] if api_key is not None else [])},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(row)
    await activity_hub.publish(company_id, "model.updated", {"name": row.name})
    return _to_out(row)


@router.delete("/{model_id}", status_code=204)
async def delete_model(
    company_id: UUID,
    model_id: UUID,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    _require_membership(db, company_id, user.id)
    row = (
        db.query(ModelConfig)
        .filter(ModelConfig.id == model_id, ModelConfig.company_id == company_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model config not found")
    was_default = row.is_default
    write_audit(
        db,
        action="model.delete",
        actor_user_id=user.id,
        company_id=company_id,
        resource_type="model_config",
        resource_id=row.id,
        payload={"name": row.name},
        ip=request.client.host if request.client else None,
    )
    db.delete(row)
    db.flush()
    if was_default:
        nxt = db.query(ModelConfig).filter(ModelConfig.company_id == company_id).first()
        if nxt:
            nxt.is_default = True
    db.commit()
    await activity_hub.publish(company_id, "model.deleted", {"id": str(model_id)})
