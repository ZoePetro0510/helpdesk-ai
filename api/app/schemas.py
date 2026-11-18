"""API request and response models."""

from datetime import datetime

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
