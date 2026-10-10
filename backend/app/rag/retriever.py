"""NOVA — RAG Retriever."""

from __future__ import annotations

from typing import Optional

import structlog

from app.config import get_settings
from app.rag import embeddings, vector_store

logger = structlog.get_logger(__name__)


async def search_documents(
    query: str,
    n_results: int | None = None,
    document_id: Optional[str] = None,
) -> list[dict]:
    """
    Search uploaded documents using vector similarity.

    Returns list of dicts with: document_name, document_id, content, score, chunk_id.
    """
    settings = get_settings()
    n = n_results or settings.max_rag_results

    # Generate query embedding
    query_embedding = embeddings.embed_query(query)

    # Search with optional document filter
    where = {"document_id": document_id} if document_id else None
    results = vector_store.search(query_embedding, n_results=n, where=where)

    # Format results
    formatted = []
    for r in results:
        metadata = r.get("metadata", {})
        formatted.append({
            "document_name": metadata.get("document_name", "Unknown"),
            "document_id": metadata.get("document_id", ""),
            "chunk_id": r.get("chunk_id", ""),
            "chunk_index": metadata.get("chunk_index", 0),
            "content": r.get("content", ""),
            "score": r.get("score", 0.0),
        })

    logger.info("rag_search_complete", query_len=len(query), results=len(formatted))
    return formatted
