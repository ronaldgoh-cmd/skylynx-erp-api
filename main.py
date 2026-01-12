import logging
import os

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.routers.rbac import router as rbac_router
from app.security.rbac import MissingPermissionsError
from app.services.rbac_service import create_default_roles_for_tenant
from db import engine, get_db
from models import Base, Tenant, User
from schemas import LoginRequest, RegisterRequest, TokenResponse
from security import (
    PasswordTooLongError,
    create_access_token,
    hash_password,
    verify_password,
)

logger = logging.getLogger("skylynx-api")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())


def _build_cors_origins() -> list[str]:
    required = {
        "https://app.skylynxdigitalsolutions.com",
        "https://www.skylynxdigitalsolutions.com",
        "http://localhost:3000",
    }
    extra = os.getenv("CORS_ORIGINS", "")
    if extra:
        for origin in extra.split(","):
            stripped = origin.strip()
            if stripped:
                required.add(stripped)
    return sorted(required)


app = FastAPI(title="Skylynx ERP API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_build_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rbac_router)


@app.exception_handler(MissingPermissionsError)
def handle_missing_permissions(
    request: Request, exc: MissingPermissionsError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "error": "forbidden",
            "missing_permissions": exc.missing_permissions,
        },
    )


def _should_create_schema() -> bool:
    """
    Safety switch. Keep OFF in Cloud Run.
    Only use for local/dev bootstrap.
    """
    return os.getenv("AUTO_CREATE_SCHEMA", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@app.on_event("startup")
def on_startup() -> None:
    if _should_create_schema():
        logger.warning("AUTO_CREATE_SCHEMA is enabled -> running Base.metadata.create_all()")
        Base.metadata.create_all(bind=engine)
    else:
        logger.info("AUTO_CREATE_SCHEMA is disabled -> NOT running create_all()")


@app.get("/")
def root() -> dict:
    return {"ok": True, "service": "skylynx-api", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> dict:
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
        )

    tenant = Tenant(company_name=payload.company_name)
    user = User(
        tenant=tenant,
        full_name=payload.full_name,
        email=payload.email,
        password_hash=password_hash,
    )
    db.add_all([tenant, user])
    try:
        db.flush()
        create_default_roles_for_tenant(db, tenant, user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to register user.",
        )
    except RuntimeError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return {"tenant_id": str(tenant.id), "user_id": str(user.id)}


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    token = create_access_token(subject=str(user.id), tenant_id=str(user.tenant_id))
    return TokenResponse(access_token=token)
