"""A deterministic, rule-based stand-in for the LLM.

Used by CI and the end-to-end tests, where there is no model to call: the same input always gives
the same output, so tests are stable and free. It is not meant to be smart, only predictable.
"""

import re

from app.llm import LLMResult

_CATEGORY_WORDS = [
    ("it_security", ("phishing", "clicked a link", "stolen", "suspicious", "never installed", "hacked")),
    ("it_access", ("password", "locked", "authenticator", "mfa", "sign in", "log in")),
    ("it_network", ("vpn", "wifi", "wi-fi", "network")),
    ("it_hardware", ("laptop", "monitor", "screen", "keyboard", "headset", "equipment")),
    ("it_software", ("install", "license", "software", "app ", "chatgpt")),
    ("hr_payroll", ("salary", "payslip", "paid", "bank", "tax", "bonus")),
    ("hr_leave", ("vacation", "sick", "parental", "leave", "days off")),
    ("hr_benefits", ("pension", "insurance", "gym", "learning budget", "conference", "meal")),
    ("hr_policy", ("office", "remote", "abroad", "expense", "receipt", "hybrid")),
]
_HIGH = ("stolen", "clicked a link", "cannot work", "can't work", "cracked", "lower than usual", "lost my phone")
_ACTION = ("approve", "replace", "broken", "cracked", "stolen", "disconnects", "not in self service", "months",
           "get a new one", "very slow", "extremely slow")


def _request_text(user: str) -> str:
    m = re.search(r"<request>\n(.*?)\n</request>", user, re.S)
    return (m.group(1) if m else user).lower()


def _classify(text: str) -> dict:
    category = next((c for c, words in _CATEGORY_WORDS if any(w in text for w in words)), "other")
    return {
        "category": category,
        "urgency": "high" if any(w in text for w in _HIGH) else "low",
        "needs_human_action": any(w in text for w in _ACTION) or category == "other",
        "summary": " ".join(text.split()[:8]).capitalize(),
    }


def _answer(user: str) -> dict:
    # The first sentence of source [1], cited
    m = re.search(r"\[1\] [^\n]*\n(.+?(?:\.|$))", user, re.S)
    if not m:
        return {"answerable": False, "answer": "", "citations": []}
    return {"answerable": True, "answer": f"{m.group(1).strip()} [1]", "citations": [1]}


def _judge(user: str) -> dict:
    # Grounded if every sentence of the answer (minus citations) appears in the sources
    sources = re.search(r"<sources>(.*?)</sources>", user, re.S)
    answer = re.search(r"<answer>(.*?)</answer>", user, re.S)
    if not sources or not answer:
        return {"grounded": False, "unsupported_claims": ["missing sources or answer"]}
    src = " ".join(sources.group(1).split()).lower()
    sentences = [s.strip() for s in re.split(r"(?<=\.)\s", re.sub(r"\s*\[\d+(?:,\s*\d+)*\]", "", answer.group(1)))]
    missing = [s for s in sentences if s and " ".join(s.split()).lower().rstrip(".") not in src]
    return {"grounded": not missing, "unsupported_claims": missing}


class StubLLM:
    name = "stub"

    def complete_json(self, system: str, user: str, schema: dict, effort: str = "low") -> LLMResult:
        props = schema.get("properties", {})
        if "category" in props:
            data = _classify(_request_text(user))
        elif "answerable" in props:
            data = _answer(user)
        elif "grounded" in props:
            data = _judge(user)
        else:
            raise ValueError("StubLLM does not know this schema")
        return LLMResult(data=data, model=self.name, input_tokens=0, output_tokens=0)
