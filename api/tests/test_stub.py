from app import prompts
from app.stub_llm import StubLLM


def test_stub_classifies_by_keywords():
    llm = StubLLM()
    r = llm.complete_json(prompts.CLASSIFY_SYSTEM, prompts.classify_user("My laptop was stolen last night"),
                          prompts.CLASSIFY_SCHEMA)
    assert r.data["category"] == "it_security"
    assert r.data["urgency"] == "high"
    assert r.data["needs_human_action"] is True


def test_stub_answers_from_source_one_with_a_citation():
    user = prompts.answer_user("When are we paid?", [(1, "Payroll > Pay date", "Salaries are paid on the 9th. More.")])
    r = StubLLM().complete_json(prompts.ANSWER_SYSTEM, user, prompts.ANSWER_SCHEMA)
    assert r.data == {"answerable": True, "answer": "Salaries are paid on the 9th. [1]", "citations": [1]}


def test_stub_judge_flags_claims_missing_from_sources():
    sources = [("Payroll > Pay date", "Salaries are paid on the 9th of each month.")]
    ok = StubLLM().complete_json(prompts.JUDGE_SYSTEM, prompts.judge_user(sources, "Salaries are paid on the 9th [1]."),
                                 prompts.JUDGE_SCHEMA)
    bad = StubLLM().complete_json(prompts.JUDGE_SYSTEM,
                                  prompts.judge_user(sources, "Salaries are paid on the 9th. Click New Request."),
                                  prompts.JUDGE_SCHEMA)
    assert ok.data["grounded"] is True
    assert bad.data["grounded"] is False
    assert bad.data["unsupported_claims"] == ["Click New Request."]
