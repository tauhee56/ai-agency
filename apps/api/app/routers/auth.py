from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest, SignupRequest, UserOut
from app.security.auth import create_access_token, get_current_user, hash_password, verify_password
from app.services.audit import write_audit
from app.services.company import bootstrap_company

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse)
def signup(body: SignupRequest, request: Request, db: Annotated[Session, Depends(get_db)]) -> AuthResponse:
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=str(body.email).lower(), name=body.name, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()

    company = bootstrap_company(db, name=body.company_name, founder_user_id=user.id)
    write_audit(
        db,
        action="user.signup",
        actor_user_id=user.id,
        company_id=company.id,
        resource_type="user",
        resource_id=user.id,
        payload={"email": user.email},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email)
    return AuthResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, request: Request, db: Annotated[Session, Depends(get_db)]) -> AuthResponse:
    user = db.query(User).filter(User.email == str(body.email).lower()).first()
    if user is None or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    write_audit(
        db,
        action="user.login",
        actor_user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        payload={"email": user.email},
        ip=request.client.host if request.client else None,
    )
    db.commit()

    token = create_access_token(user.id, user.email)
    return AuthResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    return UserOut.model_validate(user)
