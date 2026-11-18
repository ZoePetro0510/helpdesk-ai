"""Mask personal data before text reaches the LLM or the database."""

import re

# Order matters: longer, more specific patterns first
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{1,4}){3,8}\b")),
    ("credit_card", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("national_id", re.compile(r"(?<!\w)\d{9}(?!\w)")),  # before phone: a bare 9-digit number is an ID
    ("phone", re.compile(r"(?<!\w)(?:\+\d{1,3}[ -]?)?(?:\(?\d{2,3}\)?[ -]?)\d{3}[ -]?\d{4}(?!\w)")),
]


def mask(text: str) -> tuple[str, list[str]]:
    """Return (masked_text, kinds_found). Kinds are listed once each, in pattern order."""
    found: list[str] = []
    for kind, pattern in _PATTERNS:
        text, n = pattern.subn(f"[{kind.upper()}]", text)
        if n:
            found.append(kind)
    return text, found
