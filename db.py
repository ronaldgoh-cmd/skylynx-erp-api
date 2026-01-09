import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _build_database_url() -> str:
    """
    Production (Cloud Run):
      Uses Cloud SQL Unix socket when these env vars exist:
        INSTANCE_CONNECTION_NAME, DB_NAME, DB_USER, DB_PASS

    Local development (no env vars set):
      Falls back to a local SQLite database file: ./local.db
    """
    instance = os.getenv("INSTANCE_CONNECTION_NAME", "").strip()
    db_name = os.getenv("DB_NAME", "").strip()
    db_user = os.getenv("DB_USER", "").strip()
    db_pass = os.getenv("DB_PASS", "").strip()

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

# SQLite needs this for FastAPI dev server (threaded environment).
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
