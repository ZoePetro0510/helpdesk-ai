"""Persist a pipeline outcome as a request plus its audit trail."""

from sqlalchemy.orm import Session

from app.models import AuditEvent, HelpRequest
from app.pipeline import Outcome


def save_outcome(session: Session, outcome: Outcome, channel: str, requester: str | None) -> HelpRequest:
    c = outcome.classification
    req = HelpRequest(
        channel=channel,
        requester=requester,
        text_masked=outcome.text_masked,
        pii_found=outcome.pii_found,
        category=c.category,
        urgency=c.urgency,
        team=c.team,
        summary=c.summary,
        route=outcome.route,
        route_reason=outcome.route_reason,
        status="answered" if outcome.route == "auto_reply" else "pending_approval",
        answer=outcome.answer.text if outcome.answer else None,
        citations=outcome.answer.citations if outcome.answer else [],
        retrieval_score=outcome.top_score,
        model=outcome.model,
        input_tokens=outcome.input_tokens,
        output_tokens=outcome.output_tokens,
        latency_ms=outcome.latency_ms,
        refused=outcome.refused,
    )
    session.add(req)
    session.flush()  # assigns req.id for the audit rows
    session.add_all(AuditEvent(request_id=req.id, step=step, detail=detail) for step, detail in outcome.steps)
    session.commit()
    return req
