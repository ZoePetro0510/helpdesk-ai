"""Numbers for the manager dashboard, computed from the stored requests."""

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import HelpRequest


def _cost(model: str, tokens_in: int, tokens_out: int) -> float:
    price_in, price_out = settings.model_prices.get(model, (0.0, 0.0))
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000


def _percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    s = sorted(values)
    return s[min(len(s) - 1, int(round(p * (len(s) - 1))))]


def compute(session: Session, days: int = 14) -> dict:
    rows = session.scalars(select(HelpRequest)).all()
    total = len(rows)
    status = Counter(r.status for r in rows)
    answered = status["answered"]

    by_category: dict[str, dict[str, int]] = defaultdict(lambda: {"auto": 0, "person": 0})
    for r in rows:
        by_category[r.category]["auto" if r.route == "auto_reply" else "person"] += 1

    today = datetime.now(UTC).date()
    start = today - timedelta(days=days - 1)
    per_day = Counter(r.created_at.astimezone(UTC).date() for r in rows if r.created_at.date() >= start)

    pending = [r for r in rows if r.status == "pending_approval"]
    oldest_pending_min = (
        int((datetime.now(UTC) - min(r.created_at for r in pending)).total_seconds() // 60) if pending else 0
    )
    tokens_in = sum(r.input_tokens for r in rows)
    tokens_out = sum(r.output_tokens for r in rows)
    latencies = [r.latency_ms for r in rows]

    return {
        "total": total,
        "by_status": {k: status[k] for k in ("answered", "pending_approval", "ticket_created", "rejected")},
        "auto_resolve_rate": round(answered / total, 3) if total else 0.0,
        "minutes_saved": answered * settings.minutes_per_auto_answer,
        "minutes_per_auto_answer": settings.minutes_per_auto_answer,
        "pending": len(pending),
        "oldest_pending_minutes": oldest_pending_min,
        "latency_ms": {"avg": int(sum(latencies) / total) if total else 0, "p95": _percentile(latencies, 0.95)},
        "tokens": {"input": tokens_in, "output": tokens_out},
        "cost_usd": round(sum(_cost(r.model, r.input_tokens, r.output_tokens) for r in rows), 4),
        "models": sorted({r.model for r in rows}),
        "by_category": sorted(
            ({"category": c, **v} for c, v in by_category.items()), key=lambda x: -(x["auto"] + x["person"])
        ),
        "per_day": [
            {"date": (start + timedelta(days=i)).isoformat(), "count": per_day[start + timedelta(days=i)]}
            for i in range(days)
        ],
    }
