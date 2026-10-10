"""NOVA — Document Text Chunking."""

from __future__ import annotations

from app.config import get_settings


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    """
    Split text into overlapping chunks for embedding.

    Uses recursive splitting on paragraph/sentence boundaries.
    """
    settings = get_settings()
    size = chunk_size or settings.chunk_size
    overlap = chunk_overlap or settings.chunk_overlap

    if not text or not text.strip():
        return []

    # Clean the text
    text = text.strip()

    # If text is shorter than chunk size, return as single chunk
    if len(text) <= size:
        return [text]

    chunks: list[str] = []

    # Split by paragraphs first
    paragraphs = text.split("\n\n")

    current_chunk = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) + 2 <= size:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
        else:
            # If current chunk is non-empty, save it
            if current_chunk:
                chunks.append(current_chunk.strip())
                # Start new chunk with overlap
                if overlap > 0 and len(current_chunk) > overlap:
                    current_chunk = current_chunk[-overlap:] + "\n\n" + para
                else:
                    current_chunk = para
            else:
                # Paragraph itself is larger than chunk size — split by sentences
                sentences = _split_sentences(para)
                for sent in sentences:
                    if len(current_chunk) + len(sent) + 1 <= size:
                        current_chunk = (current_chunk + " " + sent).strip()
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sent

    if current_chunk and current_chunk.strip():
        chunks.append(current_chunk.strip())

    # Filter out very short chunks
    chunks = [c for c in chunks if len(c) >= 20]

    return chunks


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    import re
    # Split on sentence-ending punctuation followed by space
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]
