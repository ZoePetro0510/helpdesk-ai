"""Rebuild the knowledge-base index.   Usage: python -m scripts.ingest_kb"""

from app.config import settings
from app.db import SessionLocal, init_db
from app.embeddings import LocalEmbedder
from app.kb import rebuild_index


def main() -> None:
    init_db()
    with SessionLocal() as session:
        n = rebuild_index(session, settings.kb_dir, LocalEmbedder())
    print(f"Indexed {n} sections from {settings.kb_dir}")


if __name__ == "__main__":
    main()
