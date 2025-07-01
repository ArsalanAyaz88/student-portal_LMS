import os
import sys
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# Add the project root to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Load environment variables from .env file
load_dotenv()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models here
from sqlmodel import SQLModel
from src.app.models import (
    assignment,
    bank_account,
    certificate,
    course,
    course_feedback,
    course_progress,
    enrollment,
    notification,
    oauth,
    password_reset,
    payment,
    payment_proof,
    profile,
    quiz,
    quiz_audit_log,
    user,
    video,
    video_progress,
)

# Set the metadata for autogenerate support
target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = os.getenv("DATABASE_URL")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    config.set_main_option('sqlalchemy.url', os.getenv('DATABASE_URL'))
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration['sqlalchemy.url'] = os.getenv("DATABASE_URL")
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
