"""NOVA — Embedding Generation (sentence-transformers)."""

from __future__ import annotations

from typing import Optional

import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)

_model = None


def _get_model():
    """Lazy-load the embedding model."""
    global _model
    if _model is None:
        settings = get_settings()
        try:
            from sentence_transformers import SentenceTransformer

            logger.info("loading_embedding_model", model=settings.embedding_model)
            _model = SentenceTransformer(settings.embedding_model)
            logger.info("embedding_model_loaded", model=settings.embedding_model)
        except ImportError:
            raise RuntimeError(
                "sentence-transformers is required. Install with: pip install sentence-transformers"
            )
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts."""
    if not texts:
        return []
    model = _get_model()
    embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    """Generate embedding for a single query."""
    model = _get_model()
    embedding = model.encode(query, normalize_embeddings=True)
    return embedding.tolist()


def is_available() -> bool:
    """Check if embedding model can be loaded."""
    try:
        _get_model()
        return True
    except Exception:
        return False
