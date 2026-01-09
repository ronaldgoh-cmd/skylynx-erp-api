import os
from typing import Generator

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import SessionLocal, engine
from models import Base, Tenant, User
from schemas import LoginRequest, RegisterRequest, TokenResponse
from security import create_access_token, hash_password, verify_password


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _build_cors_origins() -> list[str]:
    required = {
        "https://app.skylynxdigitalsolutions.com",
        "https://www.skylynxdigitalsolutions.com",
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


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/")
def root() -> dict:
    return {
        "ok": True,
        "service": "skylynx-api",
        "docs": "/docs",
        "health": "/health",
    }


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

    tenant = Tenant(company_name=payload.company_name)
    user = User(
        tenant=tenant,
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add_all([tenant, user])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to register user.",
        )

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
