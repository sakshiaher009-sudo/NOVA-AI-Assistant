"""NOVA — Language Detection."""

from __future__ import annotations

import re

# Simple heuristic-based language detection.
# For a local-first app this avoids heavy dependencies.

# Common English words (high frequency)
_ENGLISH_MARKERS = {
    "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can",
    "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "into", "about", "like",
    "this", "that", "these", "those", "it", "its",
    "i", "you", "he", "she", "we", "they", "me", "him", "her", "us", "them",
    "my", "your", "his", "our", "their",
    "what", "which", "who", "when", "where", "why", "how",
    "not", "no", "yes", "all", "each", "every", "both",
    "if", "then", "else", "so", "because", "while", "after", "before",
}


def detect_language(text: str) -> str:
    """
    Detect language of text. Returns ISO 639-1 code.

    Currently optimized for English detection.
    Returns 'en' for English, 'unknown' otherwise.
    """
    if not text or len(text.strip()) < 2:
        return "unknown"

    words = set(re.findall(r"\b[a-zA-Z]+\b", text.lower()))

    if not words:
        return "unknown"

    english_count = len(words & _ENGLISH_MARKERS)
    ratio = english_count / len(words) if words else 0

    # If at least 20% of words are common English words, classify as English
    if ratio >= 0.2 or english_count >= 2:
        return "en"

    # Check for ASCII-heavy text (likely English or similar)
    ascii_ratio = sum(1 for c in text if ord(c) < 128) / len(text)
    if ascii_ratio > 0.9:
        return "en"

    return "unknown"
