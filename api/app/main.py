"""FastAPI entry point.  Run: uvicorn app.main:app --reload   then open /docs"""

import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import metrics
from app.config import settings
from app.db import get_session, init_db
from app.embeddings import LocalEmbedder
from app.llm import LLM, LLMError, get_llm
from app.models import AuditEvent, HelpRequest, KbChunk, MockTicket
from app.pipeline import process
from app.retrieval import PgRetriever
from app.schemas import ApproveIn, RejectIn, RequestIn, RequestOut, TicketIn, TicketOut
from app.service import DecisionError, approve, reject, save_outcome
from app.tickets import TicketClient, TicketError, create_mock_ticket, get_ticket_client


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="AI Helpdesk Agent", lifespan=lifespan)
_embedder = LocalEmbedder()


def llm_dependency() -> LLM:
    return get_llm()


def ticket_dependency(session: Session = Depends(get_session)) -> TicketClient:
    return get_ticket_client(session)


def require_internal_token(x_internal_token: str = Header(default="")) -> None:
    """Internal endpoints are only for n8n, which sends the shared secret."""
    if not secrets.compare_digest(x_internal_token, settings.internal_token):
        raise HTTPException(status_code=401, detail="Invalid internal token")


def _get_or_404(session: Session, request_id: int) -> HelpRequest:
    req = session.get(HelpRequest, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return req


@app.get("/health")
def health(session: Session = Depends(get_session)):
    chunks = session.scalar(select(func.count()).select_from(KbChunk))
    return {"status": "ok", "llm_provider": settings.llm_provider, "ticket_backend": settings.ticket_backend,
            "kb_chunks": chunks}


# --- Requests -------------------------------------------------------------

@app.post("/requests", response_model=RequestOut, status_code=201)
def create_request(body: RequestIn, session: Session = Depends(get_session), llm: LLM = Depends(llm_dependency)):
    try:
        outcome = process(body.text, llm, PgRetriever(session, _embedder))
    except LLMError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return save_outcome(session, outcome, body.channel, body.requester)


@app.get("/requests", response_model=list[RequestOut])
def list_requests(status: str | None = None, limit: int = 50, session: Session = Depends(get_session)):
    q = select(HelpRequest).order_by(HelpRequest.id.desc()).limit(min(limit, 200))
    if status:
        q = q.where(HelpRequest.status == status)
    return session.scalars(q).all()


@app.get("/requests/{request_id}", response_model=RequestOut)
def get_request(request_id: int, session: Session = Depends(get_session)):
    return _get_or_404(session, request_id)


@app.get("/requests/{request_id}/audit")
def get_audit(request_id: int, session: Session = Depends(get_session)):
    _get_or_404(session, request_id)
    events = session.scalars(select(AuditEvent).where(AuditEvent.request_id == request_id).order_by(AuditEvent.id))
    return [{"at": e.at, "step": e.step, "detail": e.detail} for e in events]


# --- Human approval -------------------------------------------------------

@app.post("/requests/{request_id}/approve", response_model=RequestOut)
def approve_request(
    request_id: int, body: ApproveIn, session: Session = Depends(get_session),
    tickets: TicketClient = Depends(ticket_dependency),
):
    req = _get_or_404(session, request_id)
    edits = body.model_dump(include={"title", "team", "priority"})
    try:
        return approve(session, req, body.approver, tickets, edits=edits, note=body.note)
    except DecisionError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except TicketError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.post("/requests/{request_id}/reject", response_model=RequestOut)
def reject_request(request_id: int, body: RejectIn, session: Session = Depends(get_session)):
    req = _get_or_404(session, request_id)
    try:
        return reject(session, req, body.approver, body.reason)
    except DecisionError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


# --- Dashboard ------------------------------------------------------------

@app.get("/metrics")
def get_metrics(days: int = 14, session: Session = Depends(get_session)):
    return metrics.compute(session, days=min(max(days, 1), 90))


# --- Mock ticket system (stands in for Jira / Trello) ----------------------

@app.post("/mock-tickets", status_code=201, dependencies=[Depends(require_internal_token)])
def create_ticket(body: TicketIn, session: Session = Depends(get_session)):
    ref = create_mock_ticket(session, body.model_dump())
    return {"key": ref.key, "url": ref.url}


@app.get("/mock-tickets", response_model=list[TicketOut])
def list_tickets(session: Session = Depends(get_session)):
    return session.scalars(select(MockTicket).order_by(MockTicket.id.desc()).limit(200)).all()


@app.get("/mock-tickets/{key}", response_model=TicketOut)
def get_ticket(key: str, session: Session = Depends(get_session)):
    ticket = session.scalar(select(MockTicket).where(MockTicket.key == key))
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket
