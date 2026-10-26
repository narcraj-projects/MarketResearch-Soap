"""Empty migration foundation. No credentials in INI files or log configuration."""
from alembic import context

from app.config import Settings
from app.db import Base, build_engine
from app import models  # noqa: F401 -- register domain metadata

target_metadata = Base.metadata

if context.is_offline_mode():
    settings = Settings()
    if settings.database_url is None:
        raise RuntimeError("database_not_configured")
    context.configure(
        url=settings.database_url.get_secret_value(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = build_engine(Settings())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
