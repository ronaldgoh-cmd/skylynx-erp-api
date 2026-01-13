from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dropdowns import DropdownOption
from app.schemas.dropdowns import DropdownOptionCreateRequest, DropdownOptionResponse
from app.security.rbac import require_permissions
from db import get_db
from models import User

router = APIRouter(tags=["dropdowns"])


@router.get(
    "/dropdown-options",
    response_model=list[DropdownOptionResponse],
)
def list_dropdown_options(
    category: str | None = None,
    user: User = Depends(require_permissions("dropdowns:read")),
    db: Session = Depends(get_db),
) -> list[DropdownOptionResponse]:
    stmt = select(DropdownOption).where(DropdownOption.tenant_id == user.tenant_id)
    if category:
        stmt = stmt.where(DropdownOption.category == category)
    options = db.scalars(
        stmt.order_by(DropdownOption.category, DropdownOption.sort_order, DropdownOption.value)
    ).all()
    return options


@router.post(
    "/dropdown-options",
    response_model=DropdownOptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_dropdown_option(
    payload: DropdownOptionCreateRequest,
    user: User = Depends(require_permissions("dropdowns:write")),
    db: Session = Depends(get_db),
) -> DropdownOptionResponse:
    option = DropdownOption(
        tenant_id=user.tenant_id,
        category=payload.category,
        value=payload.value,
        sort_order=payload.sort_order,
    )
    db.add(option)
    db.commit()
    db.refresh(option)
    return option


@router.delete(
    "/dropdown-options/{option_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_dropdown_option(
    option_id: UUID,
    user: User = Depends(require_permissions("dropdowns:write")),
    db: Session = Depends(get_db),
) -> None:
    option = db.scalar(
        select(DropdownOption).where(
            DropdownOption.id == option_id, DropdownOption.tenant_id == user.tenant_id
        )
    )
    if not option:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dropdown option not found.",
        )
    db.delete(option)
    db.commit()
