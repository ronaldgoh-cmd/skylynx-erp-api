import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _build_database_url() -> str:
    instance = os.getenv("INSTANCE_CONNECTION_NAME", "")
    db_name = os.getenv("DB_NAME", "")
    db_user = os.getenv("DB_USER", "")
    db_pass = os.getenv("DB_PASS", "")

    if not all([instance, db_name, db_user, db_pass]):
        missing = [
            name
            for name, value in [
                ("INSTANCE_CONNECTION_NAME", instance),
                ("DB_NAME", db_name),
                ("DB_USER", db_user),
                ("DB_PASS", db_pass),
            ]
            if not value
        ]
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    safe_user = quote_plus(db_user)
    safe_pass = quote_plus(db_pass)
    return (
        f"postgresql+psycopg2://{safe_user}:{safe_pass}@/{db_name}"
        f"?host=/cloudsql/{instance}"
    )


DATABASE_URL = _build_database_url()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
