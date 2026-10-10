"""NOVA — Text Preprocessing for NLP Pipeline."""

from __future__ import annotations

import re
import unicodedata


# Common contractions expansion
_CONTRACTIONS = {
    "i'm": "i am", "i've": "i have", "i'll": "i will", "i'd": "i would",
    "you're": "you are", "you've": "you have", "you'll": "you will", "you'd": "you would",
    "he's": "he is", "she's": "she is", "it's": "it is",
    "we're": "we are", "we've": "we have", "we'll": "we will", "we'd": "we would",
    "they're": "they are", "they've": "they have", "they'll": "they will", "they'd": "they would",
    "that's": "that is", "who's": "who is", "what's": "what is", "where's": "where is",
    "when's": "when is", "why's": "why is", "how's": "how is",
    "isn't": "is not", "aren't": "are not", "wasn't": "was not", "weren't": "were not",
    "hasn't": "has not", "haven't": "have not", "hadn't": "had not",
    "won't": "will not", "wouldn't": "would not",
    "don't": "do not", "doesn't": "does not", "didn't": "did not",
    "can't": "cannot", "couldn't": "could not", "shouldn't": "should not",
    "mightn't": "might not", "mustn't": "must not",
    "let's": "let us", "there's": "there is",
}


def normalize_text(text: str) -> str:
    """Normalize text for NLP processing while preserving meaning."""
    if not text:
        return ""

    # Unicode normalization
    text = unicodedata.normalize("NFKC", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)

    return text


def expand_contractions(text: str) -> str:
    """Expand contractions in text."""
    words = text.split()
    result = []
    for word in words:
        lower = word.lower()
        if lower in _CONTRACTIONS:
            result.append(_CONTRACTIONS[lower])
        else:
            result.append(word)
    return " ".join(result)


def clean_for_intent(text: str) -> str:
    """Clean text specifically for intent classification."""
    text = normalize_text(text)
    text = expand_contractions(text)
    text = text.lower()
    # Remove punctuation except math operators and question marks
    text = re.sub(r"[^\w\s\+\-\*/\.\?\@\:\,]", "", text)
    return text.strip()


def extract_quoted_strings(text: str) -> list[str]:
    """Extract strings in quotes from text."""
    return re.findall(r'["\']([^"\']+)["\']', text)
