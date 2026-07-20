from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from apps.api.app.core.config import settings
from apps.api.app.db import models  # noqa: F401
from apps.api.app.db.base import Base


# Alembic configuration created from apps/api/alembic.ini.
config = context.config


# Configure Alembic logging using alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# Importing models above registers all tables with Base.metadata.
target_metadata = Base.metadata


def get_database_url() -> str:
    """Return the synchronous PostgreSQL connection URL."""

    database_url = str(settings.database_url)

    # ConfigParser treats % as interpolation syntax, so escape it.
    return database_url.replace("%", "%%")


# Override the placeholder URL from alembic.ini with the application URL.
config.set_main_option("sqlalchemy.url", get_database_url())


def run_migrations_offline() -> None:
    """Run migrations without creating a live database connection."""

    context.configure(
        url=str(settings.database_url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using the configured PostgreSQL database."""

    configuration = config.get_section(config.config_ini_section) or {}

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()