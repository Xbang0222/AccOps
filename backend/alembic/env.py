"""Alembic environment configuration.

Reads DATABASE_URL from the project config module and uses
the ORM Base.metadata for autogenerate support.
"""
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Ensure the backend directory is on sys.path so that
# `config` and `models` can be imported when running
# alembic from any working directory.
_backend_dir = str(Path(__file__).resolve().parents[1])
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from config import DATABASE_URL  # noqa: E402
from models.orm import Base  # noqa: E402

# Alembic Config object — gives access to alembic.ini values.
alembic_cfg = context.config

# Override sqlalchemy.url from the application config so that
# the database URL is always consistent (env var > default).
alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)

# Set up Python logging from the .ini file.
if alembic_cfg.config_file_name is not None:
    fileConfig(alembic_cfg.config_file_name)

# MetaData for autogenerate support.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL (no Engine needed).
    Calls to context.execute() emit SQL to the script output.
    """
    url = alembic_cfg.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates an Engine and associates a connection with the context.
    """
    connectable = engine_from_config(
        alembic_cfg.get_section(alembic_cfg.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
