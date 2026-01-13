from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.settings import CompanySettings, UserSettings
from app.schemas.settings import (
    CompanySettingsResponse,
    CompanySettingsUpdateRequest,
    UserSettingsResponse,
    UserSettingsUpdateRequest,
)
from app.security.auth import get_current_user
from app.security.rbac import require_permissions
from db import get_db
from models import Tenant, User

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/company", response_model=CompanySettingsResponse)
def get_company_settings(
    user: User = Depends(require_permissions("settings:company:read")),
    db: Session = Depends(get_db),
) -> CompanySettingsResponse:
    settings = db.scalar(
        select(CompanySettings).where(CompanySettings.tenant_id == user.tenant_id)
    )
    if not settings:
        tenant = db.get(Tenant, user.tenant_id)
        settings = CompanySettings(
            tenant_id=user.tenant_id,
            company_name=tenant.company_name if tenant else "",
            updated_at=datetime.utcnow(),
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.put("/company", response_model=CompanySettingsResponse)
def update_company_settings(
    payload: CompanySettingsUpdateRequest,
    user: User = Depends(require_permissions("settings:company:write")),
    db: Session = Depends(get_db),
) -> CompanySettingsResponse:
    settings = db.scalar(
        select(CompanySettings).where(CompanySettings.tenant_id == user.tenant_id)
    )
    if not settings:
        tenant = db.get(Tenant, user.tenant_id)
        settings = CompanySettings(
            tenant_id=user.tenant_id,
            company_name=tenant.company_name if tenant else "",
        )
        db.add(settings)

    if payload.company_name is not None:
        settings.company_name = payload.company_name
    if payload.details_line1 is not None:
        settings.details_line1 = payload.details_line1
    if payload.details_line2 is not None:
        settings.details_line2 = payload.details_line2
    if payload.logo_url is not None:
        settings.logo_url = payload.logo_url
    if payload.about_text is not None:
        settings.about_text = payload.about_text
    if payload.version is not None:
        settings.version = payload.version

    settings.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(settings)
    return settings


@router.get("/user", response_model=UserSettingsResponse)
def get_user_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserSettingsResponse:
    settings = db.get(UserSettings, user.id)
    if not settings:
        settings = UserSettings(user_id=user.id, updated_at=datetime.utcnow())
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.put("/user", response_model=UserSettingsResponse)
def update_user_settings(
    payload: UserSettingsUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserSettingsResponse:
    settings = db.get(UserSettings, user.id)
    if not settings:
        settings = UserSettings(user_id=user.id)
        db.add(settings)

    if payload.timezone is not None:
        settings.timezone = payload.timezone
    if payload.theme is not None:
        settings.theme = payload.theme
    settings.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(settings)
    return settings
