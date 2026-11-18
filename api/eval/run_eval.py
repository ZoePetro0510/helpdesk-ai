"""Evaluate the agent on the labeled request set.

    python -m eval.run_eval --retrieval-only        # retrieval quality, no LLM needed
    python -m eval.run_eval                         # + classification, urgency, routing, cost
    python -m eval.run_eval --judge                 # + answer groundedness (LLM-as-judge)
    python -m eval.run_eval --min-hit 0.9 --max-unsafe 0 --min-grounded 0.9   # quality gate (exit 1 on failure)
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from app import prompts
from app.config import settings
from app.db import SessionLocal
from app.embeddings import LocalEmbedder
from app.llm import LLM, get_llm
from app.pipeline import Outcome, process
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
        "k": k,
        "hit@1": round(sum(r == 1 for r in ranks) / n, 3),
        "hit@3": round(sum(bool(r and r <= 3) for r in ranks) / n, 3),
        "hit@k": round(sum(r is not None for r in ranks) / n, 3),
        "mrr": round(sum(1 / r for r in ranks if r) / n, 3),
    }


def judge(judge_llm: LLM, outcome: Outcome) -> dict:
    """Is every claim in the answer supported by the sources it was given?"""
    by_source = {h.source: h for h in outcome.hits}
    cited = [by_source[c["source"]] for c in outcome.answer.citations if c["source"] in by_source]
    sources = [(f"{h.doc_title} > {h.section}", h.content) for h in (cited or outcome.hits)]
    r = judge_llm.complete_json(prompts.JUDGE_SYSTEM, prompts.judge_user(sources, outcome.answer.text),
                                prompts.JUDGE_SCHEMA, effort="medium")
    return r.data


def pipeline_metrics(items: list[dict], retriever: PgRetriever, use_judge: bool) -> dict:
    llm = get_llm()
    correct = Counter()
    unsafe_auto = 0  # sent automatically although a person should have handled it
    tokens_in = tokens_out = 0
    judged = grounded = auto_judged = auto_grounded = 0
    examples = []
    for item in items:
        o = process(item["text"], llm, retriever)
        c = o.classification
        correct["category"] += c.category == item["category"]
        correct["urgency"] += c.urgency == item["urgency"]
        correct["route"] += o.route == item["route"]
        unsafe_auto += o.route == "auto_reply" and item["route"] == "draft_ticket"
        tokens_in += o.input_tokens
        tokens_out += o.output_tokens
        note = ""
        if use_judge and o.answer and o.answer.answerable and o.answer.text:
            verdict = judge(llm, o)
            judged += 1
            grounded += verdict["grounded"]
            if o.route == "auto_reply":
                auto_judged += 1
                auto_grounded += verdict["grounded"]
            if not verdict["grounded"]:
                note = f"  UNGROUNDED: {verdict['unsupported_claims'][:2]}"
                examples.append({"id": item["id"], "route": o.route, "unsupported": verdict["unsupported_claims"]})
        ok = "ok " if o.route == item["route"] else "ERR"
        print(f"  {ok} {item['id']} {c.category:<12} {c.urgency:<6} {o.route:<12} {item['text'][:44]}{note}")
    n = len(items)
    result = {
        "model": llm.name,
        "requests": n,
        "category_accuracy": round(correct["category"] / n, 3),
        "urgency_accuracy": round(correct["urgency"] / n, 3),
        "route_accuracy": round(correct["route"] / n, 3),
        "unsafe_auto_replies": unsafe_auto,
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
    }
    if use_judge:
        result |= {
            "answers_judged": judged,
            "groundedness": round(grounded / judged, 3) if judged else None,
            "auto_replies_judged": auto_judged,
            "auto_reply_groundedness": round(auto_grounded / auto_judged, 3) if auto_judged else None,
            "ungrounded_examples": examples,
        }
    return result


def gate(result: dict, args: argparse.Namespace) -> list[str]:
    failures = []
    hit = result["retrieval"]["hit@k"]
    if args.min_hit is not None and hit < args.min_hit:
        failures.append(f"retrieval hit@k {hit} < {args.min_hit}")
    p = result.get("pipeline")
    if p and args.max_unsafe is not None and p["unsafe_auto_replies"] > args.max_unsafe:
        failures.append(f"unsafe auto-replies {p['unsafe_auto_replies']} > {args.max_unsafe}")
    if p and args.min_grounded is not None and (p.get("auto_reply_groundedness") or 0) < args.min_grounded:
        failures.append(f"auto-reply groundedness {p.get('auto_reply_groundedness')} < {args.min_grounded}")
    return failures


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--retrieval-only", action="store_true")
    ap.add_argument("--judge", action="store_true", help="check answer groundedness with the LLM as judge")
    ap.add_argument("--k", type=int, default=settings.top_k)
    ap.add_argument("--out", type=Path, help="write the results as JSON")
    ap.add_argument("--min-hit", type=float)
    ap.add_argument("--max-unsafe", type=int)
    ap.add_argument("--min-grounded", type=float)
    args = ap.parse_args()

    items = load_items()
    with SessionLocal() as session:
        retriever = PgRetriever(session, LocalEmbedder())
        print("Retrieval")
        result = {"retrieval": retrieval_metrics(items, retriever, args.k)}
        if not args.retrieval_only:
            print("\nPipeline")
            result["pipeline"] = pipeline_metrics(items, retriever, args.judge)

    print(json.dumps(result, indent=2))
    if args.out:
        args.out.write_text(json.dumps(result, indent=2) + "\n")
    failures = gate(result, args)
    if failures:
        print("\nQUALITY GATE FAILED:\n  " + "\n  ".join(failures))
        sys.exit(1)


if __name__ == "__main__":
    main()
