"""NOVA — ChromaDB Vector Store."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)

_client = None
_collection = None


def _get_collection():
    """Lazy-initialize ChromaDB collection."""
    global _client, _collection
    if _collection is None:
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            settings = get_settings()
            persist_dir = str(Path(settings.vector_db_path).resolve())
            Path(persist_dir).mkdir(parents=True, exist_ok=True)

            _client = chromadb.PersistentClient(
                path=persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            # --- Multi-worker / Client-Server ChromaDB alternative: ---
            # When deploying with multiple uvicorn workers, run Chroma as a standalone service:
            #   $ chroma run --path ./data/chroma --port 8001
            # and replace chromadb.PersistentClient above with:
            #   _client = chromadb.HttpClient(
            #       host=getattr(settings, "chroma_host", "127.0.0.1"),
            #       port=getattr(settings, "chroma_port", 8001),
            #       settings=ChromaSettings(anonymized_telemetry=False),
            #   )
            # ----------------------------------------------------------
            _collection = _client.get_or_create_collection(
                name="nova_documents",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("vector_store_initialized", path=persist_dir)
        except ImportError:
            raise RuntimeError("chromadb is required. Install with: pip install chromadb")
    return _collection


def add_chunks(
    chunk_ids: list[str],
    texts: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict],
) -> None:
    """Add document chunks to the vector store."""
    collection = _get_collection()
    collection.add(
        ids=chunk_ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    logger.info("chunks_added_to_vector_store", count=len(chunk_ids))


def search(
    query_embedding: list[float],
    n_results: int = 5,
    where: Optional[dict] = None,
) -> list[dict]:
    """Search for similar chunks."""
    collection = _get_collection()
    kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": n_results,
    }
    if where:
        kwargs["where"] = where

    try:
        results = collection.query(**kwargs)
    except Exception as e:
        logger.error("vector_search_failed", error=str(e))
        return []

    items = []
    if results and results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            items.append({
                "chunk_id": doc_id,
                "content": results["documents"][0][i] if results["documents"] else "",
                "score": 1 - results["distances"][0][i] if results["distances"] else 0,
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
            })
    return items


def delete_by_document(document_id: str) -> None:
    """Delete all chunks for a specific document."""
    collection = _get_collection()
    try:
        collection.delete(where={"document_id": document_id})
        logger.info("chunks_deleted_from_vector_store", document_id=document_id)
    except Exception as e:
        logger.warning("vector_delete_failed", error=str(e))


def count() -> int:
    """Return total number of vectors stored."""
    try:
        collection = _get_collection()
        return collection.count()
    except Exception:
        return 0


def is_available() -> bool:
    """Check if vector store is accessible."""
    try:
        _get_collection()
        return True
    except Exception:
        return False
