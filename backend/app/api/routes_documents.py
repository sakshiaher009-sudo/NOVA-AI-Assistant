"""NOVA — Document Routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.database.database import get_db_session
from app.database.repositories import DocumentRepo
from app.dependencies.auth import get_current_user_id
from app.schemas.documents import DocumentOut
from app.services.document_service import delete_document, reindex_document, upload_and_index

router = APIRouter(tags=["documents"])


@router.post("/api/documents/upload", response_model=dict)
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """Upload and index a document owned by the authenticated user."""
    try:
        content = await file.read()
        result = await upload_and_index(content, file.filename or "document.txt", user_id=user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/api/documents", response_model=list[DocumentOut])
async def list_documents(user_id: str = Depends(get_current_user_id)):
    """List all uploaded documents for the authenticated user."""
    async with get_db_session() as session:
        docs = await DocumentRepo.list_all(session, user_id=user_id)
        return [DocumentOut.model_validate(d) for d in docs]


@router.get("/api/documents/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get document details after verifying user ownership."""
    async with get_db_session() as session:
        doc = await DocumentRepo.get(session, doc_id, user_id=user_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return DocumentOut.model_validate(doc)


@router.delete("/api/documents/{doc_id}")
async def remove_document(
    doc_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a document after verifying user ownership."""
    deleted = await delete_document(doc_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted"}


@router.post("/api/documents/{doc_id}/reindex")
async def reindex(
    doc_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Re-index an existing document after verifying user ownership."""
    try:
        result = await reindex_document(doc_id, user_id=user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
