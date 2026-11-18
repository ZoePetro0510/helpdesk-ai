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
    # Columns added after Phase 1 (create_all does not alter existing tables)
    with engine.begin() as conn:
        for column, kind in [
            ("ticket_draft", "JSON"), ("ticket_key", "VARCHAR(40)"), ("ticket_url", "VARCHAR(300)"),
            ("decided_by", "VARCHAR(200)"), ("decided_at", "TIMESTAMPTZ"), ("decision_note", "TEXT"),
        ]:
            conn.execute(text(f"ALTER TABLE help_requests ADD COLUMN IF NOT EXISTS {column} {kind}"))


def get_session():
    """FastAPI dependency: one session per request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
