# AI Helpdesk Agent

An AI agent for an internal IT & HR helpdesk. It reads an employee's request, classifies it, answers from the company knowledge base with citations when it is safe to, and drafts a ticket for a person when it is not.

> **Data:** a fictional company ("Orbit") with synthetic IT and HR policies. No real employee data.

**Stack:** Python · FastAPI · PostgreSQL + pgvector · local embeddings (fastembed) · Claude or a local Ollama model · Docker Compose

## Status

| Phase | Scope | Status |
|---|---|---|
| 1 | Core agent: classification, RAG with citations, routing, audit log | ✅ Done |
| 2 | Self-hosted n8n intake, ticket creation, human approval queue | Planned |
| 3 | React + TypeScript web app and manager dashboard | Planned |
| 4 | Evals report, Playwright, GitHub Actions, live demo | Planned |

## How a request flows

```
request ─► mask PII ─► classify ─► search KB ─► answer with [n] citations ─► route
                       (category,     (pgvector)    (only if a relevant           │
                        urgency,                     source exists)              ├─► auto_reply
                        action?)                                                 └─► draft_ticket (a person approves)
every step ─► audit_events table
```

**Routing rules** (`app/pipeline.py:decide_route`). A request goes to a person when any of these is true:

- it is a possible security incident, or urgency is high
- it needs an action or approval, not just an answer
- no knowledge-base section is relevant, or the answer has no valid citation
- the best match is below the auto-reply confidence threshold
- the model declined the request

## Run it

Requirements: Docker. For a free local model, install [Ollama](https://ollama.com) and run `ollama pull llama3.2`.

```bash
cp .env.example .env            # choose LLM_PROVIDER: ollama or anthropic
docker compose up --build       # db + api; the knowledge base is indexed on start
```

API docs: http://localhost:8000/docs

```bash
curl -X POST localhost:8000/requests -H 'content-type: application/json' \
  -d '{"text": "How many vacation days can I carry over to next year?"}'
```

## Quality

```bash
docker compose exec api pytest                          # unit + integration tests
docker compose exec api python -m eval.run_eval --retrieval-only   # retrieval hit@k, MRR (no LLM)
docker compose exec api python -m eval.run_eval         # classification, urgency, routing, token cost
```

The eval set (`data/eval/requests.jsonl`) has 46 labeled requests, each with the expected category, urgency, route and source section. It includes a prompt-injection attempt and a request outside IT/HR.

### Results (Phase 1, local model `llama3.2` via Ollama)

| Metric | Result |
|---|---|
| Retrieval hit@1 / hit@4 / MRR (44 questions) | 0.82 / 0.93 / 0.87 |
| Routing accuracy (auto-reply vs. ticket) | 0.87 |
| **Unsafe auto-replies** (sent without a person when one was needed) | **0** |
| Category accuracy | 0.80 |
| Urgency accuracy | 0.70 |
| Tokens for all 46 requests | 35.4K in / 4.5K out (free locally) |

Every routing error is on the safe side: a question that could have been answered automatically became a ticket. The prompt-injection request was classified and sent to a person, not acted on. These numbers come from a small local 3B model; Phase 4 repeats the eval with Claude.

## Cost

- Embeddings run locally, so indexing and search cost nothing.
- Ollama is used for day-to-day development: no API cost.
- With Claude, classification runs at low effort and answers at medium effort. The answer call is skipped when no relevant source exists. Every request stores its input and output tokens.

## Security and privacy

- Emails, phone numbers, card numbers, IBANs and ID numbers are masked before the text reaches the model or the database.
- Request text and sources are passed as data inside tags; the prompts tell the model not to follow instructions in them.
- Nothing is sent automatically for security incidents, urgent requests or anything that needs an approval.
- Every step is written to an append-only audit table.
- Secrets live only in `.env` (ignored by git and Docker).

## Project structure

```
api/app/
  pipeline.py    mask -> classify -> retrieve -> answer -> route (pure logic, unit-tested)
  prompts.py     prompts and JSON schemas
  llm.py         provider-independent layer: Ollama, Claude, fake (tests)
  retrieval.py   pgvector cosine search
  kb.py          Markdown knowledge base -> one chunk per section
  pii.py         personal-data masking
  main.py        FastAPI endpoints
api/eval/        evaluation runner
api/tests/       pytest suite
data/kb/         synthetic IT & HR policies
data/eval/       labeled requests
```
