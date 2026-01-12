import os
from urllib.parse import quote_plus

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def _is_cloud_run() -> bool:
    # Cloud Run sets K_SERVICE and PORT.
    return bool(os.getenv("K_SERVICE") or os.getenv("PORT"))


def _build_database_url() -> str:
    """
    Production (Cloud Run):
      Uses Cloud SQL Unix socket when these env vars exist:
        INSTANCE_CONNECTION_NAME, DB_NAME, DB_USER, DB_PASS

    Local development:
      Falls back to SQLite ./local.db
    """
    instance = os.getenv("INSTANCE_CONNECTION_NAME", "").strip()
    db_name = os.getenv("DB_NAME", "").strip()
    db_user = os.getenv("DB_USER", "").strip()
    db_pass = os.getenv("DB_PASS", "").strip()

    # If running in Cloud Run, fail fast if required vars are missing.
    if _is_cloud_run():
        missing = [k for k, v in {
            "INSTANCE_CONNECTION_NAME": instance,
            "DB_NAME": db_name,
            "DB_USER": db_user,
            "DB_PASS": db_pass,
        }.items() if not v]
        if missing:
            raise RuntimeError(f"Missing required DB env vars in Cloud Run: {', '.join(missing)}")

    # If all Cloud SQL env vars are present, build the Cloud SQL socket URL.
    if instance and db_name and db_user and db_pass:
        safe_user = quote_plus(db_user)
        safe_pass = quote_plus(db_pass)
        return (
            f"postgresql+psycopg2://{safe_user}:{safe_pass}@/{db_name}"
            f"?host=/cloudsql/{instance}"
        )

    # Otherwise, local dev fallback.
    return "sqlite:///./local.db"


DATABASE_URL = _build_database_url()

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
