"""The request pipeline: mask PII -> classify -> retrieve -> answer -> route.

Pure logic with injected dependencies (LLM, retriever), so it can be tested without a database.
"""

import re
import time
from dataclasses import dataclass, field

from app import prompts
from app.config import settings
from app.llm import LLM, LLMRefusal
from app.pii import mask
from app.retrieval import Hit, Retriever


@dataclass
class Classification:
    category: str
    urgency: str
    needs_human_action: bool
    summary: str

    @property
    def team(self) -> str:
        return prompts.team_for(self.category)


@dataclass
class Answer:
    answerable: bool
    text: str
    citations: list[dict]  # [{"n", "source", "title", "section"}]


@dataclass
class Outcome:
    text_masked: str
    pii_found: list[str]
    classification: Classification
    hits: list[Hit]
    answer: Answer | None
    route: str  # auto_reply | draft_ticket
    route_reason: str
    model: str
    refused: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    steps: list[tuple[str, dict]] = field(default_factory=list)  # for the audit log

    @property
    def top_score(self) -> float:
        return self.hits[0].score if self.hits else 0.0


# Bracketed text that is not a citation like [1] or [1, 2]: "[insert link]", "[EMAIL]", "[TBD]"...
_PLACEHOLDER = re.compile(r"\[(?!\s*\d+(?:\s*,\s*\d+)*\s*\])[^\]]*\]")


def decide_route(c: Classification, top_score: float, answer: Answer | None, refused: bool) -> tuple[str, str]:
    """Return (route, reason). A human sees anything risky, urgent or uncertain."""
    if refused:
        return "draft_ticket", "The model declined this request, so a person handles it."
    if c.category == "it_security":
        return "draft_ticket", "Possible security incident: the security team must handle it."
    if c.urgency == "high":
        return "draft_ticket", "High urgency: a person follows up directly."
    if c.needs_human_action:
        return "draft_ticket", "Needs an action or approval, not only an answer."
    if top_score < settings.min_retrieval_score:
        return "draft_ticket", "No relevant knowledge-base article."
    if answer is None or not answer.answerable or not answer.citations:
        return "draft_ticket", "The knowledge base does not fully answer this."
    if _PLACEHOLDER.search(answer.text):
        return "draft_ticket", "The answer contains a placeholder instead of a real value."
    if top_score < settings.auto_reply_score:
        return "draft_ticket", f"Low confidence (retrieval score {top_score:.2f})."
    return "auto_reply", f"Answered from the knowledge base (retrieval score {top_score:.2f})."


def _fallback_classification(text: str) -> Classification:
    return Classification("other", "medium", True, text[:120])


def process(text: str, llm: LLM, retriever: Retriever) -> Outcome:
    started = time.perf_counter()
    masked, pii_found = mask(text)
    steps: list[tuple[str, dict]] = [("pii_mask", {"found": pii_found})]
    tokens_in = tokens_out = 0
    refused = False

    # 1. Classify
    try:
        r = llm.complete_json(prompts.CLASSIFY_SYSTEM, prompts.classify_user(masked), prompts.CLASSIFY_SCHEMA,
                              effort=settings.classify_effort)
        tokens_in, tokens_out = r.input_tokens, r.output_tokens
        c = Classification(**{k: r.data[k] for k in ("category", "urgency", "needs_human_action", "summary")})
        if c.category not in prompts.CATEGORIES:
            c.category = "other"
        steps.append(("classify", r.data))
    except LLMRefusal:
        refused = True
        c = _fallback_classification(masked)
        steps.append(("classify", {"refused": True}))

    # 2. Retrieve
    hits = retriever.search(masked, settings.top_k)
    steps.append(("retrieve", {"sources": [h.source for h in hits], "scores": [h.score for h in hits]}))

    # 3. Answer (skipped when nothing relevant was found: saves tokens)
    answer = None
    top = hits[0].score if hits else 0.0
    if not refused and top >= settings.min_retrieval_score:
        relevant = [h for h in hits if h.score >= settings.min_retrieval_score]
        numbered = [(i, f"{h.doc_title} > {h.section}", h.content) for i, h in enumerate(relevant, 1)]
        try:
            r = llm.complete_json(prompts.ANSWER_SYSTEM, prompts.answer_user(masked, numbered), prompts.ANSWER_SCHEMA,
                                  effort=settings.answer_effort)
            tokens_in += r.input_tokens
            tokens_out += r.output_tokens
            cited = sorted({n for n in r.data.get("citations", []) if 1 <= n <= len(relevant)})
            answer = Answer(
                answerable=bool(r.data.get("answerable")),
                text=r.data.get("answer", "").strip(),
                citations=[
                    {"n": n, "source": relevant[n - 1].source, "title": relevant[n - 1].doc_title,
                     "section": relevant[n - 1].section}
                    for n in cited
                ],
            )
            steps.append(("answer", {"answerable": answer.answerable, "citations": cited}))
        except LLMRefusal:
            refused = True
            steps.append(("answer", {"refused": True}))
    else:
        steps.append(("answer", {"skipped": "refused" if refused else "no relevant source"}))

    # 4. Route
    route, reason = decide_route(c, top, answer, refused)
    steps.append(("route", {"route": route, "reason": reason}))

    return Outcome(
        text_masked=masked, pii_found=pii_found, classification=c, hits=hits, answer=answer,
        route=route, route_reason=reason, model=llm.name, refused=refused,
        input_tokens=tokens_in, output_tokens=tokens_out,
        latency_ms=int((time.perf_counter() - started) * 1000), steps=steps,
    )
