"""Persist pipeline outcomes and apply human decisions (approve / reject), with an audit trail."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import AuditEvent, HelpRequest
from app.pipeline import Outcome
from app.tickets import TicketClient


class DecisionError(ValueError):
    """The request is not in a state where this decision is allowed."""


def _draft(outcome: Outcome) -> dict:
    c = outcome.classification
    parts = [f"Employee request:\n{outcome.text_masked}"]
    if outcome.answer and outcome.answer.text:
        parts.append(f"Suggested answer from the agent:\n{outcome.answer.text}")
    if outcome.answer and outcome.answer.citations:
        parts.append("Sources:\n" + "\n".join(f"- {x['source']}" for x in outcome.answer.citations))
    parts.append(f"Why a person is needed: {outcome.route_reason}")
    return {"title": c.summary, "team": c.team, "priority": c.urgency, "description": "\n\n".join(parts)}


def save_outcome(session: Session, outcome: Outcome, channel: str, requester: str | None) -> HelpRequest:
    c = outcome.classification
    is_ticket = outcome.route == "draft_ticket"
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
        status="pending_approval" if is_ticket else "answered",
        answer=outcome.answer.text if outcome.answer else None,
        citations=outcome.answer.citations if outcome.answer else [],
        retrieval_score=outcome.top_score,
        model=outcome.model,
        input_tokens=outcome.input_tokens,
        output_tokens=outcome.output_tokens,
        latency_ms=outcome.latency_ms,
        refused=outcome.refused,
        ticket_draft=_draft(outcome) if is_ticket else None,
    )
    session.add(req)
    session.flush()  # assigns req.id for the audit rows
    session.add_all(AuditEvent(request_id=req.id, step=step, detail=detail) for step, detail in outcome.steps)
    session.commit()
    return req


def approve(
    session: Session, req: HelpRequest, approver: str, tickets: TicketClient, edits: dict | None = None,
    note: str | None = None,
) -> HelpRequest:
    """A person approves the drafted ticket (optionally edited). Only then is it created."""
    if req.status != "pending_approval":
        raise DecisionError(f"Request {req.id} is '{req.status}', not waiting for approval")
    final = {**(req.ticket_draft or {}), **{k: v for k, v in (edits or {}).items() if v}}
    payload = {**final, "request_id": req.id}

    ref = tickets.create(payload)  # raises TicketError: nothing is marked approved if this fails

    req.ticket_draft = final
    req.ticket_key, req.ticket_url = ref.key, ref.url
    req.status = "ticket_created"
    req.decided_by, req.decided_at, req.decision_note = approver, datetime.now(UTC), note
    session.add(AuditEvent(request_id=req.id, step="approved", detail={
        "by": approver, "edited": sorted(k for k, v in (edits or {}).items() if v), "ticket": ref.key,
    }))
    session.commit()
    return req


def reject(session: Session, req: HelpRequest, approver: str, reason: str) -> HelpRequest:
    if req.status != "pending_approval":
        raise DecisionError(f"Request {req.id} is '{req.status}', not waiting for approval")
    req.status = "rejected"
    req.decided_by, req.decided_at, req.decision_note = approver, datetime.now(UTC), reason
    session.add(AuditEvent(request_id=req.id, step="rejected", detail={"by": approver, "reason": reason}))
    session.commit()
    return req
