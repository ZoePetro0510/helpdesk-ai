"""Semantic search over the knowledge base (pgvector, cosine similarity)."""

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings import Embedder
from app.models import KbChunk


@dataclass
class Hit:
    doc_id: str
    doc_title: str
    section: str
    content: str
    score: float  # cosine similarity, higher is better

    @property
    def source(self) -> str:
        return f"{self.doc_id}#{self.section}"


class Retriever(Protocol):
    def search(self, query: str, k: int) -> list[Hit]: ...


class PgRetriever:
    def __init__(self, session: Session, embedder: Embedder):
        self.session = session
        self.embedder = embedder

    def search(self, query: str, k: int) -> list[Hit]:
        [vector] = self.embedder.embed([query])
        distance = KbChunk.embedding.cosine_distance(vector)
        rows = self.session.execute(select(KbChunk, distance.label("d")).order_by(distance).limit(k)).all()
        return [
            Hit(c.doc_id, c.doc_title, c.section, c.content, round(1 - float(d), 4)) for c, d in rows
        ]
