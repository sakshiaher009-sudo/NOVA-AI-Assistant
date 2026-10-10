"""NOVA — Pydantic Schemas for Documents."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: str
    filename: str
    original_filename: str
    file_extension: str
    file_size_bytes: int
    chunk_count: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentSearchResult(BaseModel):
    document_id: str
    document_name: str
    chunk_id: str
    chunk_index: int
    content: str
    relevance_score: float


class DocumentSearchResponse(BaseModel):
    query: str
    results: list[DocumentSearchResult]
    total: int
