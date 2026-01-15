from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.settings import CompanySettings, UserSettings
from app.schemas.settings import (
    CompanySettingsResponse,
    CompanySettingsUpdateRequest,
    UserSettingsResponse,
    UserSettingsUpdateRequest,
)
from app.security.auth import get_active_tenant_id, get_current_user
from app.security.rbac import require_permissions
from db import get_db
from models import Tenant, User

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/company", response_model=CompanySettingsResponse)
def get_company_settings(
    user: User = Depends(require_permissions("settings:company:read")),
    db: Session = Depends(get_db),
) -> CompanySettingsResponse:
    tenant_id = get_active_tenant_id(user)
    settings = db.scalar(
        select(CompanySettings).where(CompanySettings.tenant_id == tenant_id)
    )
    if not settings:
        tenant = db.get(Tenant, tenant_id)
        settings = CompanySettings(
            tenant_id=tenant_id,
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
    tenant_id = get_active_tenant_id(user)
    settings = db.scalar(
        select(CompanySettings).where(CompanySettings.tenant_id == tenant_id)
    )
    if not settings:
        tenant = db.get(Tenant, tenant_id)
        settings = CompanySettings(
            tenant_id=tenant_id,
            company_name=tenant.company_name if tenant else "",
        )
        db.add(settings)

    if payload.company_name is not None:
        settings.company_name = payload.company_name
    if payload.details_line1 is not None:
        settings.details_line1 = payload.details_line1
    if payload.details_line2 is not None:
        settings.details_line2 = payload.details_line2
    if payload.about_text is not None:
        settings.about_text = payload.about_text
    if payload.version is not None:
        settings.version = payload.version

    settings.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(settings)
    return settings


@router.post("/company/logo")
async def upload_company_logo(
    file: UploadFile = File(...),
    user: User = Depends(require_permissions("settings:company:write")),
    db: Session = Depends(get_db),
) -> dict:
    tenant_id = get_active_tenant_id(user)
    settings = db.scalar(
        select(CompanySettings).where(CompanySettings.tenant_id == tenant_id)
    )
    if not settings:
        tenant = db.get(Tenant, tenant_id)
        settings = CompanySettings(
            tenant_id=tenant_id,
            company_name=tenant.company_name if tenant else "",
        )
        db.add(settings)

    logo_bytes = await file.read()
    settings.logo_bytes = logo_bytes
    settings.logo_mime = file.content_type or "application/octet-stream"
    settings.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.get("/company/logo")
def get_company_logo(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    tenant_id = get_active_tenant_id(user)
    settings = db.scalar(
        select(CompanySettings).where(CompanySettings.tenant_id == tenant_id)
    )
    if not settings or not settings.logo_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Logo not found.",
        )
    media_type = settings.logo_mime or "application/octet-stream"
    return Response(content=settings.logo_bytes, media_type=media_type)


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
