from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas.profile import ChangePasswordRequest, ProfileResponse, ProfileUpdateRequest
from app.security.auth import get_current_user
from db import get_db
from models import User
from security import PasswordTooLongError, hash_password, verify_password

router = APIRouter(prefix="/profile", tags=["profile"])


def _build_full_name(first_name: str, last_name: str) -> str:
    parts = [first_name.strip(), last_name.strip()]
    return " ".join([part for part in parts if part])


@router.get("", response_model=ProfileResponse)
def get_profile(user: User = Depends(get_current_user)) -> ProfileResponse:
    return ProfileResponse(
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
    )


@router.put("", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    if payload.email and payload.email != user.email:
        existing = db.scalar(select(User).where(User.email == payload.email))
        if existing and existing.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered.",
            )
        user.email = payload.email

    user.first_name = payload.first_name
    user.last_name = payload.last_name
    user.full_name = _build_full_name(payload.first_name, payload.last_name)
    db.commit()
    db.refresh(user)
    return ProfileResponse(
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
    )


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if payload.new_password != payload.new_password_confirm:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password confirmation does not match.",
        )
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid current password.",
        )
    try:
        user.password_hash = hash_password(payload.new_password)
    except PasswordTooLongError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    user.must_change_password = False
    db.commit()
    return {"ok": True}
