"""End-to-end API test against the real database and embeddings, with a scripted LLM.

Runs inside Docker:  docker compose exec api pytest
"""

import os

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("RUN_INTEGRATION"), reason="needs the database (run inside Docker)")


@pytest.fixture(scope="module", autouse=True)
def fresh_test_database():
    """Empty tables and a fresh knowledge-base index in the test database."""
    from sqlalchemy import text

    from app.config import settings
    from app.db import SessionLocal, engine, init_db
    from app.embeddings import LocalEmbedder
    from app.kb import rebuild_index

    assert engine.url.database == "helpdesk_test"  # never touch the demo database
    init_db()
    with SessionLocal() as session:
        session.execute(text("TRUNCATE audit_events, help_requests, mock_tickets RESTART IDENTITY"))
        session.commit()
        rebuild_index(session, settings.kb_dir, LocalEmbedder())


@pytest.fixture
def client():
    from fastapi import Depends
    from fastapi.testclient import TestClient

    from app.db import get_session
    from app.llm import FakeLLM
    from app.main import app, llm_dependency, ticket_dependency
    from app.tickets import DirectTicketClient

    llm = FakeLLM()
    app.dependency_overrides[llm_dependency] = lambda: llm
    # Tickets go straight to the mock system here; the n8n path is checked end to end in Docker
    app.dependency_overrides[ticket_dependency] = lambda session=Depends(get_session): DirectTicketClient(session)
    with TestClient(app) as c:
        c.llm = llm
        yield c
    app.dependency_overrides.clear()


def _pending_request(client) -> dict:
    client.llm.responses = [
        {"category": "it_hardware", "urgency": "high", "needs_human_action": True, "summary": "Cracked laptop screen"},
        {"answerable": True, "answer": "IT repairs it or gives a loaner within 2 days [1].", "citations": [1]},
    ]
    body = client.post("/requests", json={"text": "My laptop screen cracked and half of it is black"}).json()
    assert body["status"] == "pending_approval"
    assert body["ticket_draft"]["team"] == "IT"
    return body


def test_health_reports_indexed_kb(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["kb_chunks"] >= 40


def test_payroll_question_end_to_end(client):
    client.llm.responses = [
        {"category": "hr_payroll", "urgency": "low", "needs_human_action": False, "summary": "Pay date"},
        {"answerable": True, "answer": "Salaries are paid on the 9th of each month [1].", "citations": [1]},
    ]
    r = client.post("/requests", json={"text": "On which day of the month are salaries paid?"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["citations"][0]["source"] == "hr/payroll#Pay date"
    assert body["route"] == "auto_reply"
    assert body["status"] == "answered"

    again = client.get(f"/requests/{body['id']}").json()
    assert again["id"] == body["id"]


def test_pii_is_not_stored(client):
    client.llm.responses = [
        {"category": "hr_payroll", "urgency": "medium", "needs_human_action": True, "summary": "Bank change"},
        {"answerable": True, "answer": "Update it in the HR portal [1].", "citations": [1]},
    ]
    r = client.post("/requests", json={"text": "Please change my bank, my email is dana@orbit.com"})
    body = r.json()
    assert "dana@orbit.com" not in body["text_masked"]
    assert body["status"] == "pending_approval"


def test_approve_creates_the_ticket_with_edits(client):
    req = _pending_request(client)
    r = client.post(f"/requests/{req['id']}/approve", json={"approver": "Noa (IT)", "priority": "medium"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ticket_created"
    assert body["ticket_key"].startswith("HD-")
    assert body["decided_by"] == "Noa (IT)"

    ticket = client.get(f"/mock-tickets/{body['ticket_key']}").json()
    assert ticket["priority"] == "medium"  # the approver's edit, not the draft's "high"
    assert ticket["request_id"] == req["id"]
    assert "Suggested answer" in ticket["description"]

    steps = [e["step"] for e in client.get(f"/requests/{req['id']}/audit").json()]
    assert steps[-1] == "approved"


def test_cannot_decide_twice(client):
    req = _pending_request(client)
    rejected = client.post(f"/requests/{req['id']}/reject", json={"approver": "Noa", "reason": "Duplicate"})
    assert rejected.status_code == 200
    again = client.post(f"/requests/{req['id']}/approve", json={"approver": "Noa"})
    assert again.status_code == 409


def test_auto_replied_request_cannot_be_approved(client):
    client.llm.responses = [
        {"category": "hr_payroll", "urgency": "low", "needs_human_action": False, "summary": "Pay date"},
        {"answerable": True, "answer": "On the 9th [1].", "citations": [1]},
    ]
    req = client.post("/requests", json={"text": "On which day of the month are salaries paid?"}).json()
    assert client.post(f"/requests/{req['id']}/approve", json={"approver": "Noa"}).status_code == 409


def test_ticket_failure_keeps_the_request_pending(client):
    from app.main import app, ticket_dependency
    from app.tickets import TicketError

    class Down:
        def create(self, payload):
            raise TicketError("ticket system unavailable")

    req = _pending_request(client)
    app.dependency_overrides[ticket_dependency] = lambda: Down()
    r = client.post(f"/requests/{req['id']}/approve", json={"approver": "Noa"})
    assert r.status_code == 502
    assert client.get(f"/requests/{req['id']}").json()["status"] == "pending_approval"


def test_mock_ticket_endpoint_needs_the_internal_token(client):
    payload = {"title": "x", "team": "IT", "priority": "low", "description": "y"}
    assert client.post("/mock-tickets", json=payload).status_code == 401
    assert client.post("/mock-tickets", json=payload, headers={"X-Internal-Token": "wrong"}).status_code == 401
