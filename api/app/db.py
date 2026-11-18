"""Database engine, session factory and schema setup."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Enable pgvector and create tables (idempotent)."""
    from app import models  # noqa: F401  (registers the tables on Base)

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)


def get_session():
    """FastAPI dependency: one session per request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
