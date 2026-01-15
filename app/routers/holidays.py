import csv
from datetime import datetime
from io import StringIO
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.holidays import Holiday, HolidayGroup
from app.schemas.holidays import (
    HolidayCreateRequest,
    HolidayGroupCreateRequest,
    HolidayGroupResponse,
    HolidayImportRequest,
    HolidayImportResponse,
    HolidayResponse,
)
from app.security.rbac import require_permissions
from db import get_db
from models import User

router = APIRouter(prefix="/holidays", tags=["holidays"])


@router.get(
    "/groups",
    response_model=list[HolidayGroupResponse],
)
def list_holiday_groups(
    user: User = Depends(require_permissions("holidays:read")),
    db: Session = Depends(get_db),
) -> list[HolidayGroupResponse]:
    groups = db.scalars(
        select(HolidayGroup)
        .where(HolidayGroup.tenant_id == user.active_tenant_id)
        .order_by(HolidayGroup.name)
    ).all()
    return groups


@router.post(
    "/groups",
    response_model=HolidayGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_holiday_group(
    payload: HolidayGroupCreateRequest,
    user: User = Depends(require_permissions("holidays:write")),
    db: Session = Depends(get_db),
) -> HolidayGroupResponse:
    group = HolidayGroup(tenant_id=user.active_tenant_id, name=payload.name)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.delete(
    "/groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_holiday_group(
    group_id: UUID,
    user: User = Depends(require_permissions("holidays:write")),
    db: Session = Depends(get_db),
) -> None:
    group = db.scalar(
        select(HolidayGroup).where(
            HolidayGroup.id == group_id, HolidayGroup.tenant_id == user.active_tenant_id
        )
    )
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Holiday group not found.",
        )
    db.delete(group)
    db.commit()


@router.get(
    "",
    response_model=list[HolidayResponse],
)
def list_holidays(
    holiday_group_id: UUID | None = None,
    user: User = Depends(require_permissions("holidays:read")),
    db: Session = Depends(get_db),
) -> list[HolidayResponse]:
    stmt = select(Holiday).where(Holiday.tenant_id == user.active_tenant_id)
    if holiday_group_id:
        group = db.scalar(
            select(HolidayGroup.id).where(
                HolidayGroup.id == holiday_group_id,
                HolidayGroup.tenant_id == user.active_tenant_id,
            )
        )
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Holiday group not found.",
            )
        stmt = stmt.where(Holiday.holiday_group_id == holiday_group_id)
    holidays = db.scalars(stmt.order_by(Holiday.date)).all()
    return holidays


@router.post(
    "",
    response_model=HolidayResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_holiday(
    payload: HolidayCreateRequest,
    user: User = Depends(require_permissions("holidays:write")),
    db: Session = Depends(get_db),
) -> HolidayResponse:
    if payload.holiday_group_id:
        group = db.scalar(
            select(HolidayGroup.id).where(
                HolidayGroup.id == payload.holiday_group_id,
                HolidayGroup.tenant_id == user.active_tenant_id,
            )
        )
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Holiday group not found.",
            )

    holiday = Holiday(
        tenant_id=user.active_tenant_id,
        holiday_group_id=payload.holiday_group_id,
        name=payload.name,
        date=payload.date,
    )
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    return holiday


@router.delete(
    "/{holiday_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_holiday(
    holiday_id: UUID,
    user: User = Depends(require_permissions("holidays:write")),
    db: Session = Depends(get_db),
) -> None:
    holiday = db.scalar(
        select(Holiday).where(Holiday.id == holiday_id, Holiday.tenant_id == user.active_tenant_id)
    )
    if not holiday:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Holiday not found.",
        )
    db.delete(holiday)
    db.commit()


@router.get("/template")
def holiday_template(
    user: User = Depends(require_permissions("holidays:read")),
) -> Response:
    template = "name,date\nPublic Holiday,25-12-2026\n"
    return Response(content=template, media_type="text/csv")


@router.post(
    "/import-csv",
    response_model=HolidayImportResponse,
)
def import_holidays(
    payload: HolidayImportRequest,
    user: User = Depends(require_permissions("holidays:write")),
    db: Session = Depends(get_db),
) -> HolidayImportResponse:
    group_id = payload.holiday_group_id
    if group_id:
        group = db.scalar(
            select(HolidayGroup.id).where(
                HolidayGroup.id == group_id,
                HolidayGroup.tenant_id == user.active_tenant_id,
            )
        )
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Holiday group not found.",
            )

    inserted = 0
    skipped = 0
    reader = csv.reader(StringIO(payload.csv_text))
    for row in reader:
        if not row or len(row) < 2:
            continue
        name = row[0].strip()
        date_str = row[1].strip()
        if not name or not date_str:
            skipped += 1
            continue
        if name.lower() == "name" and date_str.lower() == "date":
            continue
        try:
            parsed_date = datetime.strptime(date_str, "%d-%m-%Y").date()
        except ValueError:
            skipped += 1
            continue

        db.add(
            Holiday(
                tenant_id=user.active_tenant_id,
                holiday_group_id=group_id,
                name=name,
                date=parsed_date,
            )
        )
        inserted += 1

    db.commit()
    return HolidayImportResponse(inserted=inserted, skipped_invalid=skipped)
