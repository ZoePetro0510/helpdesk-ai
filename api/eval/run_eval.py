"""Evaluate the agent on the labeled request set.

    python -m eval.run_eval --retrieval-only   # retrieval quality, no LLM needed
    python -m eval.run_eval                    # full pipeline: classification, urgency, routing, cost
"""

import argparse
import json
from collections import Counter

from app.config import settings
from app.db import SessionLocal
from app.embeddings import LocalEmbedder
from app.llm import get_llm
from app.pipeline import process
from app.retrieval import PgRetriever


def load_items() -> list[dict]:
    return [json.loads(line) for line in settings.eval_file.read_text().splitlines() if line.strip()]


def retrieval_metrics(items: list[dict], retriever: PgRetriever, k: int) -> dict:
    ranks = []
    for item in items:
        if not item["source"]:
            continue
        hits = retriever.search(item["text"], k)
        rank = next((i for i, h in enumerate(hits, 1) if h.source == item["source"]), None)
        ranks.append(rank)
        print(f"  [{'MISS' if rank is None else f'rank {rank}':>7}] {item['text'][:70]}")
    n = len(ranks)
    return {
        "questions": n,
        "hit@1": round(sum(r == 1 for r in ranks) / n, 3),
        "hit@3": round(sum(bool(r and r <= 3) for r in ranks) / n, 3),
        f"hit@{k}": round(sum(r is not None for r in ranks) / n, 3),
        "mrr": round(sum(1 / r for r in ranks if r) / n, 3),
    }


def pipeline_metrics(items: list[dict], retriever: PgRetriever) -> dict:
    llm = get_llm()
    correct = Counter()
    unsafe_auto = 0  # sent automatically although a human should have handled it
    tokens_in = tokens_out = 0
    for item in items:
        o = process(item["text"], llm, retriever)
        c = o.classification
        correct["category"] += c.category == item["category"]
        correct["urgency"] += c.urgency == item["urgency"]
        correct["route"] += o.route == item["route"]
        unsafe_auto += o.route == "auto_reply" and item["route"] == "draft_ticket"
        tokens_in += o.input_tokens
        tokens_out += o.output_tokens
        ok = "ok " if o.route == item["route"] else "ERR"
        print(f"  {ok} {item['id']} {c.category:<12} {c.urgency:<6} {o.route:<12} {item['text'][:50]}")
    n = len(items)
    return {
        "model": llm.name,
        "requests": n,
        "category_accuracy": round(correct["category"] / n, 3),
        "urgency_accuracy": round(correct["urgency"] / n, 3),
        "route_accuracy": round(correct["route"] / n, 3),
        "unsafe_auto_replies": unsafe_auto,
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--retrieval-only", action="store_true")
    ap.add_argument("--k", type=int, default=settings.top_k)
    args = ap.parse_args()

    items = load_items()
    with SessionLocal() as session:
        retriever = PgRetriever(session, LocalEmbedder())
        print("Retrieval")
        result = {"retrieval": retrieval_metrics(items, retriever, args.k)}
        if not args.retrieval_only:
            print("\nPipeline")
            result["pipeline"] = pipeline_metrics(items, retriever)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
