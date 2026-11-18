"""End-to-end API test against the real database and embeddings, with a scripted LLM.

Runs inside Docker:  docker compose exec api pytest
"""

import os

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("RUN_INTEGRATION"), reason="needs the database (run inside Docker)")


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.llm import FakeLLM
    from app.main import app, llm_dependency

    llm = FakeLLM()
    app.dependency_overrides[llm_dependency] = lambda: llm
    with TestClient(app) as c:
        c.llm = llm
        yield c
    app.dependency_overrides.clear()


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
