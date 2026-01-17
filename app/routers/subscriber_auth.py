from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.schemas.auth import SubscriberLoginRequest, SubscriberRegisterRequest
from app.services.rbac_service import create_default_roles_for_tenant
from db import get_db
from models import Tenant, User, UserWorkspace
from schemas import TokenResponse
from security import (
    PasswordTooLongError,
    create_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/subscriber", tags=["subscriber"])


def _token_ttl(remember_me: bool | None) -> timedelta:
    if remember_me:
        return timedelta(days=7)
    return timedelta(hours=12)


def _build_full_name(first_name: str, last_name: str) -> str:
    parts = [first_name.strip(), last_name.strip()]
    return " ".join([part for part in parts if part])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def subscriber_register(
    payload: SubscriberRegisterRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered.",
        )

    try:
        password_hash = hash_password(payload.password)
    except PasswordTooLongError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    tenant = Tenant(company_name=payload.company_name)
    user = User(
        tenant=tenant,
        first_name=payload.first_name,
        last_name=payload.last_name,
        full_name=_build_full_name(payload.first_name, payload.last_name),
        email=payload.email,
        account_type="subscriber",
        password_hash=password_hash,
    )
    db.add_all([tenant, user])
    try:
        db.flush()
        db.add(UserWorkspace(user_id=user.id, tenant_id=tenant.id, is_owner=True))
        create_default_roles_for_tenant(db, tenant, user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to register user.",
        ) from exc
    except RuntimeError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    token = create_access_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id),
        expires_in=_token_ttl(payload.remember_me),
    )
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def subscriber_login(
    payload: SubscriberLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if (
        not user
        or user.account_type != "subscriber"
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    token = create_access_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id),
        expires_in=_token_ttl(payload.remember_me),
    )
    return TokenResponse(access_token=token)
