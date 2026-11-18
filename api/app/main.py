"""FastAPI entry point.  Run: uvicorn app.main:app --reload   then open /docs"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session, init_db
from app.embeddings import LocalEmbedder
from app.llm import LLM, LLMError, get_llm
from app.models import HelpRequest, KbChunk
from app.pipeline import process
from app.retrieval import PgRetriever
from app.schemas import RequestIn, RequestOut
from app.service import save_outcome


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="AI Helpdesk Agent", lifespan=lifespan)
_embedder = LocalEmbedder()


def llm_dependency() -> LLM:
    return get_llm()


@app.get("/health")
def health(session: Session = Depends(get_session)):
    chunks = session.scalar(select(func.count()).select_from(KbChunk))
    return {"status": "ok", "llm_provider": settings.llm_provider, "kb_chunks": chunks}


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
    req = session.get(HelpRequest, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return req
