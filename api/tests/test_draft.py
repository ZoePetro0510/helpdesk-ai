from app.pipeline import Answer, Classification, Outcome
from app.service import _draft


def test_ticket_draft_contains_request_answer_sources_and_reason():
    outcome = Outcome(
        text_masked="My laptop screen cracked, call [PHONE]",
        pii_found=["phone"],
        classification=Classification("it_hardware", "high", True, "Cracked laptop screen"),
        hits=[],
        answer=Answer(True, "IT repairs it within 2 days [1].",
                      [{"n": 1, "source": "it/hardware-requests#Laptop replacement", "title": "t", "section": "s"}]),
        route="draft_ticket",
        route_reason="High urgency: a person follows up directly.",
        model="fake",
    )
    d = _draft(outcome)
    assert d["title"] == "Cracked laptop screen"
    assert d["team"] == "IT" and d["priority"] == "high"
    assert "[PHONE]" in d["description"]  # only masked text reaches the ticket
    assert "it/hardware-requests#Laptop replacement" in d["description"]
    assert "High urgency" in d["description"]
