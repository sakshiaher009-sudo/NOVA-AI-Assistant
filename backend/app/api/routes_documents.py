"""NOVA — Document Routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File

from app.database.database import get_db_session
from app.database.repositories import DocumentRepo
from app.services.document_service import upload_and_index, delete_document, reindex_document
from app.schemas.documents import DocumentOut

router = APIRouter(tags=["documents"])


@router.post("/api/documents/upload", response_model=dict)
async def upload_document(file: UploadFile = File(...)):
    """Upload and index a document."""
    try:
        content = await file.read()
        result = await upload_and_index(content, file.filename or "document.txt")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/api/documents", response_model=list[DocumentOut])
async def list_documents():
    """List all uploaded documents."""
    async with get_db_session() as session:
        docs = await DocumentRepo.list_all(session)
        return [DocumentOut.model_validate(d) for d in docs]


@router.get("/api/documents/{doc_id}", response_model=DocumentOut)
async def get_document(doc_id: str):
    """Get document details."""
    async with get_db_session() as session:
        doc = await DocumentRepo.get(session, doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return DocumentOut.model_validate(doc)


@router.delete("/api/documents/{doc_id}")
async def remove_document(doc_id: str):
    """Delete a document."""
    deleted = await delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted"}


@router.post("/api/documents/{doc_id}/reindex")
async def reindex(doc_id: str):
    """Re-index an existing document."""
    try:
        result = await reindex_document(doc_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
