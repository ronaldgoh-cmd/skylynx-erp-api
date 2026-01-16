from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.employees import (
    Employee,
    EmployeeSalaryHistory,
    EmployeeSettings,
    EmployeeWorkSchedule,
)
from app.models.holidays import HolidayGroup
from app.schemas.employees import (
    EmployeeCreateRequest,
    EmployeeIdFormatResponse,
    EmployeeIdFormatUpdateRequest,
    EmployeeResponse,
    EmployeeSalaryHistoryCreateRequest,
    EmployeeSalaryHistoryResponse,
    EmployeeUnlinkedUserResponse,
    EmployeeUpdateRequest,
    WorkScheduleResponse,
    WorkScheduleUpdateRequest,
)
from app.security.rbac import require_permissions
from db import get_db
from models import User

router = APIRouter(tags=["employees"])


def _ensure_employee_settings(
    db: Session, tenant_id: UUID, for_update: bool
) -> tuple[EmployeeSettings, bool]:
    stmt = select(EmployeeSettings).where(EmployeeSettings.tenant_id == tenant_id)
    if for_update:
        stmt = stmt.with_for_update()
    settings = db.scalar(stmt)
    created = False
    if not settings:
        settings = EmployeeSettings(
            tenant_id=tenant_id,
            id_prefix="EMP",
            zero_padding=5,
            next_sequence=1,
            updated_at=datetime.utcnow(),
        )
        db.add(settings)
        db.flush()
        created = True
    return settings, created


def _build_employee_code(settings: EmployeeSettings) -> str:
    return f"{settings.id_prefix}{str(settings.next_sequence).zfill(settings.zero_padding)}"


@router.get(
    "/employee/settings/id-format",
    response_model=EmployeeIdFormatResponse,
)
def get_employee_id_format(
    user: User = Depends(require_permissions("employee_settings:read")),
    db: Session = Depends(get_db),
) -> EmployeeIdFormatResponse:
    settings, created = _ensure_employee_settings(db, user.active_tenant_id, for_update=False)
    if created:
        db.commit()
        db.refresh(settings)
    preview = _build_employee_code(settings)
    return EmployeeIdFormatResponse(
        id_prefix=settings.id_prefix,
        zero_padding=settings.zero_padding,
        next_sequence=settings.next_sequence,
        preview_code=preview,
    )


@router.put(
    "/employee/settings/id-format",
    response_model=EmployeeIdFormatResponse,
)
def update_employee_id_format(
    payload: EmployeeIdFormatUpdateRequest,
    user: User = Depends(require_permissions("employee_settings:write")),
    db: Session = Depends(get_db),
) -> EmployeeIdFormatResponse:
    settings, _ = _ensure_employee_settings(db, user.active_tenant_id, for_update=True)
    if payload.id_prefix is not None:
        settings.id_prefix = payload.id_prefix
    if payload.zero_padding is not None:
        settings.zero_padding = payload.zero_padding
    if payload.next_sequence is not None:
        settings.next_sequence = payload.next_sequence
    settings.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(settings)
    preview = _build_employee_code(settings)
    return EmployeeIdFormatResponse(
        id_prefix=settings.id_prefix,
        zero_padding=settings.zero_padding,
        next_sequence=settings.next_sequence,
        preview_code=preview,
    )


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
    return employees


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

    settings, _ = _ensure_employee_settings(db, user.active_tenant_id, for_update=True)
    employee_code = _build_employee_code(settings)
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
    return employee


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
    return employee


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
    return employee


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
    response_model=WorkScheduleResponse,
)
def get_work_schedule(
    employee_id: UUID,
    user: User = Depends(require_permissions("employees:read")),
    db: Session = Depends(get_db),
) -> WorkScheduleResponse:
    employee = db.scalar(
        select(Employee.id).where(Employee.id == employee_id, Employee.tenant_id == user.active_tenant_id)
    )
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )

    entries = db.scalars(
        select(EmployeeWorkSchedule)
        .where(EmployeeWorkSchedule.employee_id == employee_id)
        .order_by(EmployeeWorkSchedule.day_of_week)
    ).all()
    return WorkScheduleResponse(
        entries=[{"day_of_week": entry.day_of_week, "day_type": entry.day_type} for entry in entries]
    )


@router.put(
    "/employees/{employee_id}/work-schedule",
    response_model=WorkScheduleResponse,
)
def update_work_schedule(
    employee_id: UUID,
    payload: WorkScheduleUpdateRequest,
    user: User = Depends(require_permissions("employees:write")),
    db: Session = Depends(get_db),
) -> WorkScheduleResponse:
    employee = db.scalar(
        select(Employee.id).where(Employee.id == employee_id, Employee.tenant_id == user.active_tenant_id)
    )
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )

    if len(payload.entries) != 7:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Work schedule must include 7 entries.",
        )
    days = [entry.day_of_week for entry in payload.entries]
    if sorted(days) != list(range(7)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Work schedule must include day_of_week 0-6 once each.",
        )

    db.execute(delete(EmployeeWorkSchedule).where(EmployeeWorkSchedule.employee_id == employee_id))
    db.add_all(
        [
            EmployeeWorkSchedule(
                employee_id=employee_id,
                day_of_week=entry.day_of_week,
                day_type=entry.day_type,
            )
            for entry in payload.entries
        ]
    )
    db.commit()
    return WorkScheduleResponse(entries=payload.entries)
