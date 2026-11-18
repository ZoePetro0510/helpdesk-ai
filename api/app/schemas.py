"""API request and response models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RequestIn(BaseModel):
    text: str = Field(min_length=3, max_length=4000)
    channel: str = Field(default="web", pattern="^(web|email|slack)$")
    requester: str | None = Field(default=None, max_length=200)


class Citation(BaseModel):
    n: int
    source: str
    title: str
    section: str


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    channel: str
    text_masked: str
    pii_found: list[str]
    category: str
    urgency: str
    team: str
    summary: str
    route: str
    route_reason: str
    status: str
    answer: str | None
    citations: list[Citation]
    retrieval_score: float
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    ticket_draft: dict | None = None
    ticket_key: str | None = None
    ticket_url: str | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None
    decision_note: str | None = None


Priority = Literal["low", "medium", "high"]
Team = Literal["IT", "HR", "OPS"]


class ApproveIn(BaseModel):
    approver: str = Field(min_length=2, max_length=200)
    # Optional edits to the drafted ticket
    title: str | None = Field(default=None, max_length=300)
    team: Team | None = None
    priority: Priority | None = None
    note: str | None = Field(default=None, max_length=2000)


class RejectIn(BaseModel):
    approver: str = Field(min_length=2, max_length=200)
    reason: str = Field(min_length=3, max_length=2000)


class TicketIn(BaseModel):
    title: str = Field(max_length=300)
    team: Team
    priority: Priority
    description: str
    request_id: int | None = None


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    created_at: datetime
    request_id: int | None
    title: str
    team: str
    priority: str
    description: str
    status: str
