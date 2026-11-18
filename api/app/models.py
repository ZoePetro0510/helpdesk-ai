"""Database tables."""

from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.config import settings
from app.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class KbChunk(Base):
    """One section of a knowledge-base document, with its embedding."""

    __tablename__ = "kb_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    doc_id: Mapped[str] = mapped_column(String(200), index=True)  # e.g. "hr/payroll"
    doc_title: Mapped[str] = mapped_column(String(300))
    section: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim))


class HelpRequest(Base):
    """An employee request and every decision the agent made about it."""

    __tablename__ = "help_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    channel: Mapped[str] = mapped_column(String(30), default="web")
    requester: Mapped[str | None] = mapped_column(String(200))
    # Only the PII-masked text is stored
    text_masked: Mapped[str] = mapped_column(Text)
    pii_found: Mapped[list] = mapped_column(JSON, default=list)

    category: Mapped[str] = mapped_column(String(40))
    urgency: Mapped[str] = mapped_column(String(10))
    team: Mapped[str] = mapped_column(String(10))
    summary: Mapped[str] = mapped_column(Text)

    route: Mapped[str] = mapped_column(String(20))  # auto_reply | draft_ticket
    route_reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30))  # answered | pending_approval
    answer: Mapped[str | None] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    retrieval_score: Mapped[float] = mapped_column(Float, default=0.0)

    model: Mapped[str] = mapped_column(String(80))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    refused: Mapped[bool] = mapped_column(Boolean, default=False)

    # Human-in-the-loop: the drafted ticket and what a person decided
    ticket_draft: Mapped[dict | None] = mapped_column(JSON)
    ticket_key: Mapped[str | None] = mapped_column(String(40))
    ticket_url: Mapped[str | None] = mapped_column(String(300))
    decided_by: Mapped[str | None] = mapped_column(String(200))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)


class MockTicket(Base):
    """A minimal stand-in for Jira / Trello, so the full flow runs without an external account."""

    __tablename__ = "mock_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(20), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    request_id: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    team: Mapped[str] = mapped_column(String(10))
    priority: Mapped[str] = mapped_column(String(10))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")


class AuditEvent(Base):
    """Append-only log of every step, for troubleshooting and review."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("help_requests.id"), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    step: Mapped[str] = mapped_column(String(40))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
