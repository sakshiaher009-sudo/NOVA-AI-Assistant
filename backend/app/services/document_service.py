"""NOVA — Document Service."""

from __future__ import annotations

import os
from pathlib import Path

import structlog

from app.config import get_settings
from app.database.database import get_db_session
from app.database.repositories import ChunkRepo, DocumentRepo, new_id
from app.rag import vector_store
from app.rag.chunking import chunk_text
from app.rag.embeddings import embed_texts
from app.rag.ingestion import extract_text

logger = structlog.get_logger(__name__)


async def upload_and_index(
    file_content: bytes,
    original_filename: str,
    user_id: str = "default_user",
) -> dict:
    """Upload, extract, chunk, embed, and index a document for a specific user."""
    settings = get_settings()

    # Validate extension
    ext = Path(original_filename).suffix.lower().lstrip(".")
    if ext not in settings.allowed_extension_list:
        raise ValueError(f"Unsupported file type: .{ext}. Allowed: {settings.allowed_extensions}")

    # Validate size
    if len(file_content) > settings.max_upload_bytes:
        raise ValueError(f"File too large. Maximum: {settings.max_upload_mb}MB")

    # Sanitize and save file
    safe_filename = f"{new_id()}.{ext}"
    doc_dir = settings.data_dir / "documents"
    doc_dir.mkdir(parents=True, exist_ok=True)
    file_path = doc_dir / safe_filename

    with open(file_path, "wb") as f:
        f.write(file_content)

    # Create DB record with user ownership
    async with get_db_session() as session:
        doc = await DocumentRepo.create(
            session,
            filename=safe_filename,
            original_filename=original_filename,
            file_extension=ext,
            file_size_bytes=len(file_content),
            user_id=user_id,
        )
        doc_id = doc.id

    # Process in background
    try:
        await _index_document(doc_id, str(file_path), original_filename, user_id=user_id)
    except Exception as e:
        logger.error("document_indexing_failed", doc_id=doc_id, error=str(e))
        async with get_db_session() as session:
            await DocumentRepo.update_status(session, doc_id, "error", error_message=str(e), user_id=user_id)

    return {"id": doc_id, "filename": original_filename, "status": "indexed"}


async def _index_document(
    doc_id: str,
    file_path: str,
    original_filename: str,
    user_id: str = "default_user",
) -> None:
    """Extract text, chunk, embed, and store in vector DB with user ownership."""
    async with get_db_session() as session:
        await DocumentRepo.update_status(session, doc_id, "processing", user_id=user_id)

    # Extract text
    text = await extract_text(file_path)
    if not text or not text.strip():
        async with get_db_session() as session:
            await DocumentRepo.update_status(session, doc_id, "error", error_message="No text extracted", user_id=user_id)
        return

    # Chunk
    chunks = chunk_text(text)
    if not chunks:
        async with get_db_session() as session:
            await DocumentRepo.update_status(session, doc_id, "error", error_message="No chunks generated", user_id=user_id)
        return

    # Save chunks to DB with user ownership
    async with get_db_session() as session:
        chunk_records = await ChunkRepo.create_many(session, doc_id, chunks, user_id=user_id)
        chunk_ids = [c.id for c in chunk_records]

    # Generate embeddings
    chunk_embeddings = embed_texts(chunks)

    # Store in vector DB with user_id in metadata
    metadatas = [
        {
            "document_id": doc_id,
            "document_name": original_filename,
            "chunk_index": i,
            "user_id": user_id,
        }
        for i in range(len(chunks))
    ]
    vector_store.add_chunks(chunk_ids, chunks, chunk_embeddings, metadatas)

    # Update status
    async with get_db_session() as session:
        await DocumentRepo.update_status(
            session, doc_id, "indexed", chunk_count=len(chunks), user_id=user_id
        )

    logger.info("document_indexed", doc_id=doc_id, user_id=user_id, chunks=len(chunks))


async def delete_document(doc_id: str, user_id: str | None = None) -> bool:
    """Delete a document and its vectors after verifying ownership."""
    settings = get_settings()

    async with get_db_session() as session:
        doc = await DocumentRepo.get(session, doc_id, user_id=user_id)
        if not doc:
            return False

        # Delete from vector store
        vector_store.delete_by_document(doc_id)

        # Delete file
        file_path = settings.data_dir / "documents" / doc.filename
        if file_path.exists():
            try:
                os.unlink(file_path)
            except OSError:
                pass

        # Delete from DB
        await ChunkRepo.delete_by_document(session, doc_id, user_id=user_id)
        await DocumentRepo.delete(session, doc_id, user_id=user_id)

    return True


async def reindex_document(doc_id: str, user_id: str | None = None) -> dict:
    """Re-index an existing document after verifying ownership."""
    settings = get_settings()

    async with get_db_session() as session:
        doc = await DocumentRepo.get(session, doc_id, user_id=user_id)
        if not doc:
            raise ValueError("Document not found")

        doc_filename = doc.filename
        original_filename = doc.original_filename
        doc_user_id = doc.user_id

        # Delete old vectors
        vector_store.delete_by_document(doc_id)
        await ChunkRepo.delete_by_document(session, doc_id, user_id=doc_user_id)

    # Re-index
    file_path = settings.data_dir / "documents" / doc_filename
    await _index_document(doc_id, str(file_path), original_filename, user_id=doc_user_id)

    return {"id": doc_id, "status": "reindexed"}
