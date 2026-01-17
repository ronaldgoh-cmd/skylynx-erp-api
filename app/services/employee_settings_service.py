from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employees import EmployeeSettings


def ensure_employee_settings(
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


def build_employee_code(settings: EmployeeSettings) -> str:
    return f"{settings.id_prefix}{str(settings.next_sequence).zfill(settings.zero_padding)}"
