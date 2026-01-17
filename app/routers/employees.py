from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.employees import Employee, EmployeeSalaryHistory, EmployeeWorkSchedule
from app.models.holidays import HolidayGroup
from app.models.leave import EmployeeLeaveEntitlement, LeaveDefaultEntitlement
from app.models.work_schedules import WorkScheduleGroup, WorkScheduleGroupDay
from app.schemas.employees import (
    EmployeeCreateRequest,
    EmployeeResponse,
    EmployeeSalaryHistoryCreateRequest,
    EmployeeSalaryHistoryResponse,
    EmployeeUnlinkedUserResponse,
    EmployeeUpdateRequest,
)
from app.schemas.leave import EmployeeLeaveEntitlementResponse, LeaveEntitlementsLoadResponse
from app.schemas.work_schedules import (
    EmployeeWorkScheduleResponse,
    EmployeeWorkScheduleUpdateRequest,
    WorkScheduleEntry,
)
from app.security.rbac import require_permissions
from app.services.employee_settings_service import build_employee_code, ensure_employee_settings
from app.services.work_schedule_service import normalize_week_entries, validate_week_entries
from db import get_db
from models import User

router = APIRouter(tags=["employees"])


def _resolve_work_schedule_mode(employee: Employee) -> str:
    return "group" if employee.work_schedule_group_id else "custom"


def _build_schedule_entries(
    rows: list[EmployeeWorkSchedule] | list[WorkScheduleGroupDay],
) -> list[WorkScheduleEntry]:
    entries = [
        WorkScheduleEntry(day_of_week=row.day_of_week, day_type=row.day_type)
        for row in rows
    ]
    return normalize_week_entries(entries)


def _build_employee_response(
    db: Session, employee: Employee
) -> EmployeeResponse:
    mode = _resolve_work_schedule_mode(employee)
    if mode == "group":
        rows = db.scalars(
            select(WorkScheduleGroupDay).where(
                WorkScheduleGroupDay.group_id == employee.work_schedule_group_id
            )
        ).all()
    else:
        rows = db.scalars(
            select(EmployeeWorkSchedule).where(
                EmployeeWorkSchedule.employee_id == employee.id
            )
        ).all()
    schedule_days = _build_schedule_entries(rows)
    response = EmployeeResponse.model_validate(employee, from_attributes=True)
    return response.model_copy(
        update={
            "work_schedule_mode": mode,
            "work_schedule_group_id": employee.work_schedule_group_id if mode == "group" else None,
            "work_schedule_days": schedule_days,
        }
    )


def _build_employee_responses(
    db: Session, employees: list[Employee]
) -> list[EmployeeResponse]:
    if not employees:
        return []
    custom_employee_ids = [emp.id for emp in employees if not emp.work_schedule_group_id]
    group_ids = {emp.work_schedule_group_id for emp in employees if emp.work_schedule_group_id}

    custom_rows: list[EmployeeWorkSchedule] = []
    if custom_employee_ids:
        custom_rows = db.scalars(
            select(EmployeeWorkSchedule).where(
                EmployeeWorkSchedule.employee_id.in_(custom_employee_ids)
            )
        ).all()
    group_rows: list[WorkScheduleGroupDay] = []
    if group_ids:
        group_rows = db.scalars(
            select(WorkScheduleGroupDay).where(
                WorkScheduleGroupDay.group_id.in_(group_ids)
            )
        ).all()

    custom_map: dict[UUID, list[EmployeeWorkSchedule]] = {}
    for row in custom_rows:
        custom_map.setdefault(row.employee_id, []).append(row)
    group_map: dict[UUID, list[WorkScheduleGroupDay]] = {}
    for row in group_rows:
        group_map.setdefault(row.group_id, []).append(row)

    responses: list[EmployeeResponse] = []
    for employee in employees:
        mode = _resolve_work_schedule_mode(employee)
        if mode == "group":
            rows = group_map.get(employee.work_schedule_group_id, [])
        else:
            rows = custom_map.get(employee.id, [])
        schedule_days = _build_schedule_entries(rows)
        response = EmployeeResponse.model_validate(employee, from_attributes=True)
        responses.append(
            response.model_copy(
                update={
                    "work_schedule_mode": mode,
                    "work_schedule_group_id": employee.work_schedule_group_id
                    if mode == "group"
                    else None,
                    "work_schedule_days": schedule_days,
                }
            )
        )
    return responses


@router.get(
    "/employees",
    response_model=list[EmployeeResponse],
)
def list_employees(
    q: str | None = None,
    employment_status: str | None = None,
    position: str | None = None,
    user: User = Depends(require_permissions("employees:read")),
    db: Session = Depends(get_db),
) -> list[EmployeeResponse]:
    stmt = select(Employee).where(Employee.tenant_id == user.active_tenant_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Employee.full_name.ilike(like),
                Employee.employee_code.ilike(like),
                Employee.email.ilike(like),
            )
        )
    if employment_status:
        stmt = stmt.where(Employee.employment_status == employment_status)
    if position:
        stmt = stmt.where(Employee.position == position)
    employees = db.scalars(stmt.order_by(Employee.created_at.desc())).all()
    return _build_employee_responses(db, employees)


@router.get(
    "/employees/unlinked-users",
    response_model=list[EmployeeUnlinkedUserResponse],
)
def list_unlinked_employees(
    user: User = Depends(require_permissions("employees:read")),
    db: Session = Depends(get_db),
) -> list[EmployeeUnlinkedUserResponse]:
    employees = db.scalars(
        select(Employee)
        .where(Employee.tenant_id == user.active_tenant_id, Employee.user_id.is_(None))
        .order_by(Employee.full_name)
    ).all()
    return [
        EmployeeUnlinkedUserResponse(
            id=employee.id,
            full_name=employee.full_name,
            employee_code=employee.employee_code,
        )
        for employee in employees
    ]


@router.post(
    "/employees",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_employee(
    payload: EmployeeCreateRequest,
    user: User = Depends(require_permissions("employees:write")),
    db: Session = Depends(get_db),
) -> EmployeeResponse:
    linked_user_id = payload.user_id
    if linked_user_id:
        linked_user = db.scalar(
            select(User).where(User.id == linked_user_id, User.tenant_id == user.active_tenant_id)
        )
        if not linked_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

    holiday_group_id = payload.holiday_group_id
    if holiday_group_id:
        group = db.scalar(
            select(HolidayGroup).where(
                HolidayGroup.id == holiday_group_id,
                HolidayGroup.tenant_id == user.active_tenant_id,
            )
        )
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Holiday group not found.",
            )

    settings, _ = ensure_employee_settings(db, user.active_tenant_id, for_update=True)
    employee_code = build_employee_code(settings)
    settings.next_sequence += 1
    settings.updated_at = datetime.utcnow()

    employee = Employee(
        tenant_id=user.active_tenant_id,
        employee_code=employee_code,
        user_id=linked_user_id,
        full_name=payload.full_name,
        email=payload.email,
        contact_number=payload.contact_number,
        address=payload.address,
        id_type=payload.id_type,
        id_number=payload.id_number,
        gender=payload.gender,
        date_of_birth=payload.date_of_birth,
        race=payload.race,
        country=payload.country,
        residency=payload.residency,
        pr_date=payload.pr_date,
        employment_status=payload.employment_status,
        employment_pass=payload.employment_pass,
        work_permit_number=payload.work_permit_number,
        position=payload.position,
        department=payload.department,
        employment_type=payload.employment_type,
        join_date=payload.join_date,
        exit_date=payload.exit_date,
        holiday_group_id=payload.holiday_group_id,
        bank_name=payload.bank_name,
        bank_account_number=payload.bank_account_number,
        payment_method=payload.payment_method,
        incentives=payload.incentives,
        bonus=payload.bonus,
        allowance=payload.allowance,
        overtime_rate=payload.overtime_rate,
        part_time_rate=payload.part_time_rate,
        levy=payload.levy,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(employee)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee code conflict.",
        ) from exc

    db.refresh(employee)
    return _build_employee_response(db, employee)


@router.get(
    "/employees/{employee_id}",
    response_model=EmployeeResponse,
)
def get_employee(
    employee_id: UUID,
    user: User = Depends(require_permissions("employees:read")),
    db: Session = Depends(get_db),
) -> EmployeeResponse:
    employee = db.scalar(
        select(Employee).where(Employee.id == employee_id, Employee.tenant_id == user.active_tenant_id)
    )
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )
    return _build_employee_response(db, employee)


@router.patch(
    "/employees/{employee_id}",
    response_model=EmployeeResponse,
)
@router.put(
    "/employees/{employee_id}",
    response_model=EmployeeResponse,
)
def update_employee(
    employee_id: UUID,
    payload: EmployeeUpdateRequest,
    user: User = Depends(require_permissions("employees:write")),
    db: Session = Depends(get_db),
) -> EmployeeResponse:
    employee = db.scalar(
        select(Employee).where(Employee.id == employee_id, Employee.tenant_id == user.active_tenant_id)
    )
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )

    if payload.user_id is not None:
        linked_user = db.scalar(
            select(User).where(User.id == payload.user_id, User.tenant_id == user.active_tenant_id)
        )
        if not linked_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )
        employee.user_id = payload.user_id

    if payload.holiday_group_id is not None:
        group = db.scalar(
            select(HolidayGroup).where(
                HolidayGroup.id == payload.holiday_group_id,
                HolidayGroup.tenant_id == user.active_tenant_id,
            )
        )
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Holiday group not found.",
            )
        employee.holiday_group_id = payload.holiday_group_id

    for field, value in payload.model_dump(exclude_unset=True).items():
        if field in {"user_id", "holiday_group_id"}:
            continue
        setattr(employee, field, value)

    employee.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(employee)
    return _build_employee_response(db, employee)


@router.delete(
    "/employees/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_employee(
    employee_id: UUID,
    user: User = Depends(require_permissions("employees:write")),
    db: Session = Depends(get_db),
) -> None:
    employee = db.scalar(
        select(Employee).where(Employee.id == employee_id, Employee.tenant_id == user.active_tenant_id)
    )
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )

    db.delete(employee)
    db.commit()


@router.get(
    "/employees/{employee_id}/salary-history",
    response_model=list[EmployeeSalaryHistoryResponse],
)
def list_salary_history(
    employee_id: UUID,
    user: User = Depends(require_permissions("employees:read")),
    db: Session = Depends(get_db),
) -> list[EmployeeSalaryHistoryResponse]:
    employee = db.scalar(
        select(Employee.id).where(Employee.id == employee_id, Employee.tenant_id == user.active_tenant_id)
    )
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )

    history = db.scalars(
        select(EmployeeSalaryHistory)
        .where(EmployeeSalaryHistory.employee_id == employee_id)
        .order_by(EmployeeSalaryHistory.start_date.desc())
    ).all()
    return history


@router.post(
    "/employees/{employee_id}/salary-history",
    response_model=EmployeeSalaryHistoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_salary_history(
    employee_id: UUID,
    payload: EmployeeSalaryHistoryCreateRequest,
    user: User = Depends(require_permissions("employees:write")),
    db: Session = Depends(get_db),
) -> EmployeeSalaryHistoryResponse:
    employee = db.scalar(
        select(Employee.id).where(Employee.id == employee_id, Employee.tenant_id == user.active_tenant_id)
    )
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )

    history = EmployeeSalaryHistory(
        employee_id=employee_id,
        amount=payload.amount,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return history


@router.delete(
    "/employees/{employee_id}/salary-history/{row_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_salary_history(
    employee_id: UUID,
    row_id: UUID,
    user: User = Depends(require_permissions("employees:write")),
    db: Session = Depends(get_db),
) -> None:
    history = db.scalar(
        select(EmployeeSalaryHistory)
        .join(Employee, Employee.id == EmployeeSalaryHistory.employee_id)
        .where(
            EmployeeSalaryHistory.id == row_id,
            EmployeeSalaryHistory.employee_id == employee_id,
            Employee.tenant_id == user.active_tenant_id,
        )
    )
    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Salary history not found.",
        )

    db.delete(history)
    db.commit()


@router.get(
    "/employees/{employee_id}/work-schedule",
    response_model=EmployeeWorkScheduleResponse,
)
def get_work_schedule(
    employee_id: UUID,
    user: User = Depends(require_permissions("employees:read")),
    db: Session = Depends(get_db),
) -> EmployeeWorkScheduleResponse:
    employee = db.scalar(
        select(Employee).where(
            Employee.id == employee_id, Employee.tenant_id == user.active_tenant_id
        )
    )
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )

    mode = _resolve_work_schedule_mode(employee)
    if mode == "group":
        rows = db.scalars(
            select(WorkScheduleGroupDay)
            .where(WorkScheduleGroupDay.group_id == employee.work_schedule_group_id)
            .order_by(WorkScheduleGroupDay.day_of_week)
        ).all()
    else:
        rows = db.scalars(
            select(EmployeeWorkSchedule)
            .where(EmployeeWorkSchedule.employee_id == employee_id)
            .order_by(EmployeeWorkSchedule.day_of_week)
        ).all()
    schedule_days = _build_schedule_entries(rows)
    return EmployeeWorkScheduleResponse(
        mode=mode,
        work_schedule_group_id=employee.work_schedule_group_id if mode == "group" else None,
        days=schedule_days,
    )


@router.put(
    "/employees/{employee_id}/work-schedule",
    response_model=EmployeeWorkScheduleResponse,
)
def update_work_schedule(
    employee_id: UUID,
    payload: EmployeeWorkScheduleUpdateRequest,
    user: User = Depends(require_permissions("employees:write")),
    db: Session = Depends(get_db),
) -> EmployeeWorkScheduleResponse:
    employee = db.scalar(
        select(Employee).where(
            Employee.id == employee_id, Employee.tenant_id == user.active_tenant_id
        )
    )
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )

    if payload.mode == "group":
        if not payload.work_schedule_group_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="work_schedule_group_id is required for group schedules.",
            )
        group = db.scalar(
            select(WorkScheduleGroup).where(
                WorkScheduleGroup.id == payload.work_schedule_group_id,
                WorkScheduleGroup.tenant_id == user.active_tenant_id,
            )
        )
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work schedule group not found.",
            )
        employee.work_schedule_group_id = payload.work_schedule_group_id
        employee.work_schedule_mode = "group"
        employee.updated_at = datetime.utcnow()
        db.execute(
            delete(EmployeeWorkSchedule).where(
                EmployeeWorkSchedule.employee_id == employee_id
            )
        )
        db.commit()
        rows = db.scalars(
            select(WorkScheduleGroupDay)
            .where(WorkScheduleGroupDay.group_id == payload.work_schedule_group_id)
            .order_by(WorkScheduleGroupDay.day_of_week)
        ).all()
        schedule_days = _build_schedule_entries(rows)
        return EmployeeWorkScheduleResponse(
            mode="group",
            work_schedule_group_id=payload.work_schedule_group_id,
            days=schedule_days,
        )

    if not payload.custom_days:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="custom_days is required for custom schedules.",
        )
    try:
        validate_week_entries(payload.custom_days)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    employee.work_schedule_group_id = None
    employee.work_schedule_mode = "custom"
    employee.updated_at = datetime.utcnow()
    db.execute(
        delete(EmployeeWorkSchedule).where(EmployeeWorkSchedule.employee_id == employee_id)
    )
    db.add_all(
        [
            EmployeeWorkSchedule(
                employee_id=employee_id,
                day_of_week=entry.day_of_week,
                day_type=entry.day_type,
            )
            for entry in payload.custom_days
        ]
    )
    db.commit()
    schedule_days = normalize_week_entries(payload.custom_days)
    return EmployeeWorkScheduleResponse(
        mode="custom",
        work_schedule_group_id=None,
        days=schedule_days,
    )


@router.get(
    "/employees/{employee_id}/leave-entitlements",
    response_model=list[EmployeeLeaveEntitlementResponse],
)
def list_leave_entitlements(
    employee_id: UUID,
    user: User = Depends(require_permissions("leave_entitlements:read")),
    db: Session = Depends(get_db),
) -> list[EmployeeLeaveEntitlementResponse]:
    employee = db.scalar(
        select(Employee.id).where(
            Employee.id == employee_id, Employee.tenant_id == user.active_tenant_id
        )
    )
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )
    rows = db.scalars(
        select(EmployeeLeaveEntitlement)
        .where(EmployeeLeaveEntitlement.employee_id == employee_id)
        .order_by(
            EmployeeLeaveEntitlement.leave_type_id,
            EmployeeLeaveEntitlement.service_year,
        )
    ).all()
    return rows


@router.post(
    "/employees/{employee_id}/leave-entitlements/load-defaults",
    response_model=LeaveEntitlementsLoadResponse,
)
def load_leave_entitlements_defaults(
    employee_id: UUID,
    user: User = Depends(require_permissions("leave_entitlements:write")),
    db: Session = Depends(get_db),
) -> LeaveEntitlementsLoadResponse:
    employee = db.scalar(
        select(Employee.id).where(
            Employee.id == employee_id, Employee.tenant_id == user.active_tenant_id
        )
    )
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )
    defaults = db.scalars(
        select(LeaveDefaultEntitlement).where(
            LeaveDefaultEntitlement.tenant_id == user.active_tenant_id
        )
    ).all()
    desired = {
        (row.leave_type_id, row.service_year): row
        for row in defaults
    }
    existing_rows = db.scalars(
        select(EmployeeLeaveEntitlement).where(
            EmployeeLeaveEntitlement.employee_id == employee_id
        )
    ).all()
    existing = {
        (row.leave_type_id, row.service_year): row
        for row in existing_rows
    }

    created = 0
    updated = 0
    for key, default in desired.items():
        entitlement = existing.get(key)
        if entitlement:
            entitlement.entitlement_days = default.days
            entitlement.used_days = Decimal("0")
            entitlement.adjusted_days = Decimal("0")
            updated += 1
            continue
        db.add(
            EmployeeLeaveEntitlement(
                employee_id=employee_id,
                leave_type_id=default.leave_type_id,
                service_year=default.service_year,
                entitlement_days=default.days,
                used_days=Decimal("0"),
                adjusted_days=Decimal("0"),
            )
        )
        created += 1

    for key, entitlement in existing.items():
        if key not in desired:
            db.delete(entitlement)

    db.commit()
    return LeaveEntitlementsLoadResponse(created=created, updated=updated)
