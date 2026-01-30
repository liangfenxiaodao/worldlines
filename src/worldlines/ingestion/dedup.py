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
