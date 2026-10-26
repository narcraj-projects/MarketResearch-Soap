"""SQLAlchemy foundation. Connecting or migrating is an explicit later operation."""
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import Settings


class Base(DeclarativeBase):
    pass


def build_engine(settings: Settings) -> Engine:
    if settings.database_url is None:
        raise RuntimeError("database_not_configured")
    return create_engine(
        settings.database_url.get_secret_value(),
        echo=False,
        hide_parameters=True,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=10,
    )
