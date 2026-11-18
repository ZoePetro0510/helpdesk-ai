"""Local text embeddings (fastembed / ONNX: no API cost, no PyTorch)."""

from functools import lru_cache
from typing import Protocol

from app.config import settings


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class LocalEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in _model().embed(texts)]


@lru_cache(maxsize=1)
def _model():
    # Loaded lazily so importing the app stays fast
    from fastembed import TextEmbedding

    return TextEmbedding(settings.embedding_model)
