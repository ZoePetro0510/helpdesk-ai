"""Fill the database with demo traffic: every labeled eval request goes through the real pipeline.

    python -m scripts.seed_demo            # uses the configured LLM (Ollama by default)

Created times are spread over the last 10 days so the dashboard has a trend to show.
"""

import json
import random
from datetime import UTC, datetime, timedelta

from app.config import settings
from app.db import SessionLocal, init_db
from app.embeddings import LocalEmbedder
from app.llm import get_llm
from app.pipeline import process
from app.retrieval import PgRetriever
from app.service import save_outcome

CHANNELS = ["web", "web", "email", "slack"]


def main() -> None:
    init_db()
    rng = random.Random(7)
    items = [json.loads(line) for line in settings.eval_file.read_text().splitlines() if line.strip()]
    llm = get_llm()
    with SessionLocal() as session:
        retriever = PgRetriever(session, LocalEmbedder())
        for i, item in enumerate(items, 1):
            outcome = process(item["text"], llm, retriever)
            req = save_outcome(session, outcome, rng.choice(CHANNELS), None)
            req.created_at = datetime.now(UTC) - timedelta(days=rng.randint(0, 9), minutes=rng.randint(0, 600))
            session.commit()
            print(f"{i:>2}/{len(items)} {req.route:<12} {item['text'][:60]}")


if __name__ == "__main__":
    main()
