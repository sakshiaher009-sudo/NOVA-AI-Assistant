"""NOVA — Document Text Ingestion (PDF, DOCX, TXT, MD)."""

from __future__ import annotations

import os
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


async def extract_text(file_path: str) -> str:
    """Extract text content from a document file."""
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".txt" or ext == ".md":
        return _extract_text_file(path)
    elif ext == ".pdf":
        return _extract_pdf(path)
    elif ext == ".docx":
        return _extract_docx(path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _extract_text_file(path: Path) -> str:
    """Extract text from plain text or markdown files."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _extract_pdf(path: Path) -> str:
    """Extract text from PDF using PyMuPDF."""
    try:
        import fitz  # pymupdf

        text_parts = []
        with fitz.open(str(path)) as doc:
            for page in doc:
                text_parts.append(page.get_text())
        return "\n\n".join(text_parts)
    except ImportError:
        raise RuntimeError("PyMuPDF (fitz) is required for PDF processing. Install with: pip install pymupdf")


def _extract_docx(path: Path) -> str:
    """Extract text from DOCX files."""
    try:
        from docx import Document

        doc = Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except ImportError:
        raise RuntimeError("python-docx is required for DOCX processing. Install with: pip install python-docx")
