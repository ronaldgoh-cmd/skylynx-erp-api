import os
from logging.config import fileConfig
from urllib.parse import quote_plus

from alembic import context
from sqlalchemy import engine_from_config, pool

from models import Base
import app.models.rbac  # noqa: F401
import app.models.settings  # noqa: F401
import app.models.employees  # noqa: F401
import app.models.holidays  # noqa: F401
import app.models.dropdowns  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _build_database_url() -> str:
    instance = os.getenv("INSTANCE_CONNECTION_NAME", "").strip()
    db_name = os.getenv("DB_NAME", "").strip()
    db_user = os.getenv("DB_USER", "").strip()
    db_pass = os.getenv("DB_PASS", "").strip()

    if instance and db_name and db_user and db_pass:
        safe_user = quote_plus(db_user)
        safe_pass = quote_plus(db_pass)
        return (
            f"postgresql+psycopg2://{safe_user}:{safe_pass}@/{db_name}"
            f"?host=/cloudsql/{instance}"
        )

    return "sqlite:///./local.db"


def _escape_for_alembic_config(url: str) -> str:
    # Alembic uses configparser interpolation: '%' is special.
    # URL-encoded passwords include '%xx', so escape '%' to '%%'.
    return url.replace("%", "%%")


def run_migrations_offline() -> None:
    url = _escape_for_alembic_config(_build_database_url())
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    db_url = _escape_for_alembic_config(_build_database_url())
    config.set_main_option("sqlalchemy.url", db_url)

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
