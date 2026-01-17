from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.leave import LeaveDefaultEntitlement, LeaveType
from app.models.work_schedules import WorkScheduleGroup, WorkScheduleGroupDay
from app.schemas.employees import EmployeeIdFormatResponse, EmployeeIdFormatUpdateRequest
from app.schemas.leave import (
    LeaveDefaultBulkUpdateRequest,
    LeaveDefaultEntitlementResponse,
    LeaveTypeCreateRequest,
    LeaveTypeResponse,
    LeaveTypeUpdateRequest,
)
from app.schemas.work_schedules import (
    WorkScheduleEntriesResponse,
    WorkScheduleEntry,
    WorkScheduleGroupCreateRequest,
    WorkScheduleGroupResponse,
    WorkScheduleGroupUpdateRequest,
)
from app.security.rbac import require_permissions
from app.services.employee_settings_service import build_employee_code, ensure_employee_settings
from app.services.work_schedule_service import normalize_week_entries, validate_week_entries
from db import get_db
from models import User

router = APIRouter(prefix="/employee/settings", tags=["employee-settings"])


@router.get("/id-format", response_model=EmployeeIdFormatResponse)
def get_employee_id_format(
    user: User = Depends(require_permissions("employee_settings:read")),
    db: Session = Depends(get_db),
) -> EmployeeIdFormatResponse:
    settings, created = ensure_employee_settings(
        db, user.active_tenant_id, for_update=False
    )
    if created:
        db.commit()
        db.refresh(settings)
    preview = build_employee_code(settings)
    return EmployeeIdFormatResponse(
        id_prefix=settings.id_prefix,
        zero_padding=settings.zero_padding,
        next_sequence=settings.next_sequence,
        preview_code=preview,
    )


@router.put("/id-format", response_model=EmployeeIdFormatResponse)
def update_employee_id_format(
    payload: EmployeeIdFormatUpdateRequest,
    user: User = Depends(require_permissions("employee_settings:write")),
    db: Session = Depends(get_db),
) -> EmployeeIdFormatResponse:
    settings, _ = ensure_employee_settings(db, user.active_tenant_id, for_update=True)
    if payload.id_prefix is not None:
        settings.id_prefix = payload.id_prefix
    if payload.zero_padding is not None:
        settings.zero_padding = payload.zero_padding
    if payload.next_sequence is not None:
        settings.next_sequence = payload.next_sequence
    settings.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(settings)
    preview = build_employee_code(settings)
    return EmployeeIdFormatResponse(
        id_prefix=settings.id_prefix,
        zero_padding=settings.zero_padding,
        next_sequence=settings.next_sequence,
        preview_code=preview,
    )


@router.get(
    "/work-schedule-groups",
    response_model=list[WorkScheduleGroupResponse],
)
def list_work_schedule_groups(
    user: User = Depends(require_permissions("work_schedule_groups:read")),
    db: Session = Depends(get_db),
) -> list[WorkScheduleGroupResponse]:
    groups = db.scalars(
        select(WorkScheduleGroup)
        .where(WorkScheduleGroup.tenant_id == user.active_tenant_id)
        .order_by(WorkScheduleGroup.name)
    ).all()
    return groups


@router.post(
    "/work-schedule-groups",
    response_model=WorkScheduleGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_work_schedule_group(
    payload: WorkScheduleGroupCreateRequest,
    user: User = Depends(require_permissions("work_schedule_groups:write")),
    db: Session = Depends(get_db),
) -> WorkScheduleGroupResponse:
    group = WorkScheduleGroup(
        tenant_id=user.active_tenant_id,
        name=payload.name,
        description=payload.description,
        created_at=datetime.utcnow(),
    )
    db.add(group)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Work schedule group name already exists.",
        ) from exc
    db.refresh(group)
    return group


@router.patch(
    "/work-schedule-groups/{group_id}",
    response_model=WorkScheduleGroupResponse,
)
def update_work_schedule_group(
    group_id: UUID,
    payload: WorkScheduleGroupUpdateRequest,
    user: User = Depends(require_permissions("work_schedule_groups:write")),
    db: Session = Depends(get_db),
) -> WorkScheduleGroupResponse:
    group = db.scalar(
        select(WorkScheduleGroup).where(
            WorkScheduleGroup.id == group_id,
            WorkScheduleGroup.tenant_id == user.active_tenant_id,
        )
    )
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Work schedule group not found.",
        )
    if payload.name is not None:
        group.name = payload.name
    if payload.description is not None:
        group.description = payload.description
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Work schedule group name already exists.",
        ) from exc
    db.refresh(group)
    return group


@router.delete(
    "/work-schedule-groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_work_schedule_group(
    group_id: UUID,
    user: User = Depends(require_permissions("work_schedule_groups:write")),
    db: Session = Depends(get_db),
) -> None:
    group = db.scalar(
        select(WorkScheduleGroup).where(
            WorkScheduleGroup.id == group_id,
            WorkScheduleGroup.tenant_id == user.active_tenant_id,
        )
    )
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Work schedule group not found.",
        )
    db.delete(group)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Work schedule group is in use.",
        ) from exc


@router.get(
    "/work-schedule-groups/{group_id}/schedule",
    response_model=WorkScheduleEntriesResponse,
)
def get_work_schedule_group_schedule(
    group_id: UUID,
    user: User = Depends(require_permissions("work_schedule_groups:read")),
    db: Session = Depends(get_db),
) -> WorkScheduleEntriesResponse:
    group = db.scalar(
        select(WorkScheduleGroup.id).where(
            WorkScheduleGroup.id == group_id,
            WorkScheduleGroup.tenant_id == user.active_tenant_id,
        )
    )
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Work schedule group not found.",
        )
    rows = db.scalars(
        select(WorkScheduleGroupDay)
        .where(WorkScheduleGroupDay.group_id == group_id)
        .order_by(WorkScheduleGroupDay.day_of_week)
    ).all()
    entries = [
        WorkScheduleEntry(day_of_week=row.day_of_week, day_type=row.day_type)
        for row in rows
    ]
    normalized = normalize_week_entries(entries)
    return WorkScheduleEntriesResponse(entries=normalized)


@router.put(
    "/work-schedule-groups/{group_id}/schedule",
    response_model=WorkScheduleEntriesResponse,
)
def update_work_schedule_group_schedule(
    group_id: UUID,
    payload: list[WorkScheduleEntry],
    user: User = Depends(require_permissions("work_schedule_groups:write")),
    db: Session = Depends(get_db),
) -> WorkScheduleEntriesResponse:
    group = db.scalar(
        select(WorkScheduleGroup.id).where(
            WorkScheduleGroup.id == group_id,
            WorkScheduleGroup.tenant_id == user.active_tenant_id,
        )
    )
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Work schedule group not found.",
        )
    try:
        validate_week_entries(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    db.execute(
        delete(WorkScheduleGroupDay).where(WorkScheduleGroupDay.group_id == group_id)
    )
    db.add_all(
        [
            WorkScheduleGroupDay(
                group_id=group_id,
                day_of_week=entry.day_of_week,
                day_type=entry.day_type,
            )
            for entry in payload
        ]
    )
    db.commit()
    normalized = normalize_week_entries(payload)
    return WorkScheduleEntriesResponse(entries=normalized)


@router.get(
    "/leave-types",
    response_model=list[LeaveTypeResponse],
)
def list_leave_types(
    user: User = Depends(require_permissions("leave_types:read")),
    db: Session = Depends(get_db),
) -> list[LeaveTypeResponse]:
    leave_types = db.scalars(
        select(LeaveType)
        .where(LeaveType.tenant_id == user.active_tenant_id)
        .order_by(LeaveType.name)
    ).all()
    return leave_types


@router.post(
    "/leave-types",
    response_model=LeaveTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_leave_type(
    payload: LeaveTypeCreateRequest,
    user: User = Depends(require_permissions("leave_types:write")),
    db: Session = Depends(get_db),
) -> LeaveTypeResponse:
    leave_type = LeaveType(
        tenant_id=user.active_tenant_id,
        name=payload.name,
        code=payload.code,
        description=payload.description,
        is_prorated=payload.is_prorated,
        is_annual_reset=payload.is_annual_reset,
        created_at=datetime.utcnow(),
    )
    db.add(leave_type)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Leave type already exists.",
        ) from exc
    db.refresh(leave_type)
    return leave_type


@router.patch(
    "/leave-types/{leave_type_id}",
    response_model=LeaveTypeResponse,
)
def update_leave_type(
    leave_type_id: UUID,
    payload: LeaveTypeUpdateRequest,
    user: User = Depends(require_permissions("leave_types:write")),
    db: Session = Depends(get_db),
) -> LeaveTypeResponse:
    leave_type = db.scalar(
        select(LeaveType).where(
            LeaveType.id == leave_type_id,
            LeaveType.tenant_id == user.active_tenant_id,
        )
    )
    if not leave_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave type not found.",
        )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(leave_type, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Leave type already exists.",
        ) from exc
    db.refresh(leave_type)
    return leave_type


@router.delete(
    "/leave-types/{leave_type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_leave_type(
    leave_type_id: UUID,
    user: User = Depends(require_permissions("leave_types:write")),
    db: Session = Depends(get_db),
) -> None:
    leave_type = db.scalar(
        select(LeaveType).where(
            LeaveType.id == leave_type_id,
            LeaveType.tenant_id == user.active_tenant_id,
        )
    )
    if not leave_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave type not found.",
        )
    db.delete(leave_type)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Leave type is in use.",
        ) from exc


@router.get(
    "/leave-defaults",
    response_model=list[LeaveDefaultEntitlementResponse],
)
def list_leave_defaults(
    leave_type_id: UUID | None = None,
    user: User = Depends(require_permissions("leave_defaults:read")),
    db: Session = Depends(get_db),
) -> list[LeaveDefaultEntitlementResponse]:
    stmt = select(LeaveDefaultEntitlement).where(
        LeaveDefaultEntitlement.tenant_id == user.active_tenant_id
    )
    if leave_type_id:
        leave_type = db.scalar(
            select(LeaveType.id).where(
                LeaveType.id == leave_type_id,
                LeaveType.tenant_id == user.active_tenant_id,
            )
        )
        if not leave_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Leave type not found.",
            )
        stmt = stmt.where(LeaveDefaultEntitlement.leave_type_id == leave_type_id)
    rows = db.scalars(
        stmt.order_by(
            LeaveDefaultEntitlement.leave_type_id,
            LeaveDefaultEntitlement.service_year,
        )
    ).all()
    return rows


@router.put(
    "/leave-defaults",
    response_model=list[LeaveDefaultEntitlementResponse],
)
def replace_leave_defaults(
    payload: LeaveDefaultBulkUpdateRequest,
    user: User = Depends(require_permissions("leave_defaults:write")),
    db: Session = Depends(get_db),
) -> list[LeaveDefaultEntitlementResponse]:
    leave_type = db.scalar(
        select(LeaveType).where(
            LeaveType.id == payload.leave_type_id,
            LeaveType.tenant_id == user.active_tenant_id,
        )
    )
    if not leave_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave type not found.",
        )
    service_years = [row.service_year for row in payload.rows]
    if len(set(service_years)) != len(service_years):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Duplicate service_year values are not allowed.",
        )

    db.execute(
        delete(LeaveDefaultEntitlement).where(
            LeaveDefaultEntitlement.tenant_id == user.active_tenant_id,
            LeaveDefaultEntitlement.leave_type_id == payload.leave_type_id,
        )
    )
    rows = [
        LeaveDefaultEntitlement(
            tenant_id=user.active_tenant_id,
            leave_type_id=payload.leave_type_id,
            service_year=row.service_year,
            days=row.days,
        )
        for row in payload.rows
    ]
    db.add_all(rows)
    db.commit()
    return rows
