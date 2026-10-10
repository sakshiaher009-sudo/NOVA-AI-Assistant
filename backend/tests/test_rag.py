"""NOVA — Backend Tests: RAG Chunking."""

import pytest
from app.rag.chunking import chunk_text


class TestChunking:
    def test_short_text(self):
        chunks = chunk_text("Hello world.", chunk_size=100)
        assert len(chunks) == 1
        assert chunks[0] == "Hello world."

    def test_empty_text(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_paragraph_splitting(self):
        text = "First paragraph which is fairly long.\n\nSecond paragraph which is also fairly long.\n\nThird paragraph with enough text."
        chunks = chunk_text(text, chunk_size=50, chunk_overlap=0)
        assert len(chunks) >= 2

    def test_long_text_chunked(self):
        # Build multi-paragraph text that will be split across chunks
        para = ("word " * 40).strip()  # ~200 chars per paragraph
        text = "\n\n".join([para] * 10)  # 10 paragraphs, ~2000 chars total
        chunks = chunk_text(text, chunk_size=250, chunk_overlap=20)
        assert len(chunks) > 1
        # Each chunk should be reasonable size
        for c in chunks:
            assert len(c) >= 20

    def test_overlap(self):
        text = "A " * 300 + "\n\n" + "B " * 300
        chunks = chunk_text(text, chunk_size=200, chunk_overlap=50)
        assert len(chunks) >= 2

    def test_very_short_chunks_filtered(self):
        text = "OK.\n\n\n\nThis is a longer paragraph that should be kept."
        chunks = chunk_text(text, chunk_size=1000)
        for c in chunks:
            assert len(c) >= 20
