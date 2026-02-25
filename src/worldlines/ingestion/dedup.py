"""Deduplication hash computation for ingested items."""

from __future__ import annotations

import hashlib
import re
import unicodedata


def _normalize_text(text: str) -> str:
    """Normalize text for stable hashing.

    - Unicode NFC normalization
    - Lowercase
    - Collapse all whitespace (spaces, tabs, newlines) to single spaces
    - Strip leading/trailing whitespace
    """
    text = unicodedata.normalize("NFC", text)
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def compute_title_shingle_similarity(title1: str, title2: str, n: int = 4) -> float:
    """Compute character n-gram (shingling) Jaccard similarity between two titles.

    Returns a float in [0, 1]. Uses the same _normalize_text() normalization
    as the hash function.
    """
    def _shingles(text: str) -> frozenset[str]:
        normalized = _normalize_text(text)
        if len(normalized) < n:
            return frozenset({normalized}) if normalized else frozenset()
        return frozenset(normalized[i : i + n] for i in range(len(normalized) - n + 1))

    s1 = _shingles(title1)
    s2 = _shingles(title2)
    if not s1 or not s2:
        return 0.0
    intersection = len(s1 & s2)
    union = len(s1 | s2)
    return intersection / union


def compute_dedup_hash(title: str, source_name: str, content: str) -> str:
    """Compute a SHA-256 deduplication hash from title, source name, and content.

    Each field is normalized to be resilient to minor formatting differences
    (whitespace variations, unicode representation, case). Fields are joined
    with a null byte separator to avoid ambiguous concatenations.
    """
    parts = [
        _normalize_text(title),
        _normalize_text(source_name),
        _normalize_text(content),
    ]
    combined = "\0".join(parts)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
