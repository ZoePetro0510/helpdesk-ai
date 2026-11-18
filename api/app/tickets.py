"""Ticketing: a mock ticket system, plus clients that create tickets directly or through n8n.

With n8n in between, switching from the mock to Jira or Trello is a change in the n8n workflow only.
"""

from dataclasses import dataclass
from typing import Protocol

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import MockTicket


@dataclass
class TicketRef:
    key: str
    url: str


class TicketError(RuntimeError):
    """The ticket system could not create the ticket."""


class TicketClient(Protocol):
    def create(self, payload: dict) -> TicketRef: ...


def create_mock_ticket(session: Session, payload: dict) -> TicketRef:
    """The mock ticket system itself (what Jira or Trello would do)."""
    next_number = (session.scalar(select(func.max(MockTicket.id))) or 0) + 101
    ticket = MockTicket(
        key=f"HD-{next_number}",
        request_id=payload.get("request_id"),
        title=payload["title"],
        team=payload["team"],
        priority=payload["priority"],
        description=payload["description"],
    )
    session.add(ticket)
    session.commit()
    return TicketRef(ticket.key, f"{settings.public_url}/mock-tickets/{ticket.key}")


class DirectTicketClient:
    def __init__(self, session: Session):
        self.session = session

    def create(self, payload: dict) -> TicketRef:
        return create_mock_ticket(self.session, payload)


class N8nTicketClient:
    def __init__(self, webhook_url: str = settings.n8n_ticket_webhook):
        self.webhook_url = webhook_url

    def create(self, payload: dict) -> TicketRef:
        try:
            r = httpx.post(
                self.webhook_url, json=payload, headers={"X-Internal-Token": settings.internal_token}, timeout=30
            )
            r.raise_for_status()
            data = r.json()
            return TicketRef(data["key"], data["url"])
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise TicketError(f"n8n could not create the ticket: {e}") from e


def get_ticket_client(session: Session) -> TicketClient:
    if settings.ticket_backend == "n8n":
        return N8nTicketClient()
    return DirectTicketClient(session)
