"""Tests for worldlines.ingestion.dedup — deduplication hash function."""

from __future__ import annotations

from worldlines.ingestion.dedup import compute_dedup_hash, _normalize_text


# --- Normalization ---


class TestNormalizeText:
    def test_lowercases(self):
        assert _normalize_text("Hello World") == "hello world"

    def test_collapses_whitespace(self):
        assert _normalize_text("hello   world") == "hello world"

    def test_collapses_newlines_and_tabs(self):
        assert _normalize_text("hello\n\n\tworld") == "hello world"

    def test_strips_leading_trailing(self):
        assert _normalize_text("  hello  ") == "hello"

    def test_unicode_nfc_normalization(self):
        # e + combining acute accent vs precomposed e-acute
        decomposed = "caf\u0065\u0301"  # e + combining acute
        precomposed = "caf\u00e9"  # precomposed e-acute
        assert _normalize_text(decomposed) == _normalize_text(precomposed)

    def test_empty_string(self):
        assert _normalize_text("") == ""

    def test_only_whitespace(self):
        assert _normalize_text("   \n\t  ") == ""


# --- Hash computation ---


class TestComputeDedupHash:
    def test_deterministic(self):
        h1 = compute_dedup_hash("Title", "Source", "Content body")
        h2 = compute_dedup_hash("Title", "Source", "Content body")
        assert h1 == h2

    def test_returns_hex_string(self):
        h = compute_dedup_hash("Title", "Source", "Content")
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest
        assert all(c in "0123456789abcdef" for c in h)

    def test_different_titles_produce_different_hashes(self):
        h1 = compute_dedup_hash("Title A", "Source", "Content")
        h2 = compute_dedup_hash("Title B", "Source", "Content")
        assert h1 != h2

    def test_different_sources_produce_different_hashes(self):
        h1 = compute_dedup_hash("Title", "Source A", "Content")
        h2 = compute_dedup_hash("Title", "Source B", "Content")
        assert h1 != h2

    def test_different_content_produces_different_hashes(self):
        h1 = compute_dedup_hash("Title", "Source", "Content A")
        h2 = compute_dedup_hash("Title", "Source", "Content B")
        assert h1 != h2

    def test_whitespace_variations_same_hash(self):
        h1 = compute_dedup_hash("Title", "Source", "Hello world")
        h2 = compute_dedup_hash("Title", "Source", "Hello   world")
        assert h1 == h2

    def test_newline_variations_same_hash(self):
        h1 = compute_dedup_hash("Title", "Source", "line one line two")
        h2 = compute_dedup_hash("Title", "Source", "line one\nline two")
        assert h1 == h2

    def test_case_insensitive(self):
        h1 = compute_dedup_hash("Title", "Source", "Hello World")
        h2 = compute_dedup_hash("TITLE", "SOURCE", "HELLO WORLD")
        assert h1 == h2

    def test_leading_trailing_whitespace_same_hash(self):
        h1 = compute_dedup_hash("Title", "Source", "Content")
        h2 = compute_dedup_hash("  Title  ", "  Source  ", "  Content  ")
        assert h1 == h2

    def test_unicode_normalization_same_hash(self):
        h1 = compute_dedup_hash("caf\u00e9", "Source", "Content")
        h2 = compute_dedup_hash("caf\u0065\u0301", "Source", "Content")
        assert h1 == h2

    def test_field_boundary_not_ambiguous(self):
        # "title" + "source" + "content" != "titlesource" + "" + "content"
        # The null byte separator prevents this.
        h1 = compute_dedup_hash("ab", "cd", "ef")
        h2 = compute_dedup_hash("abcd", "", "ef")
        assert h1 != h2

    def test_empty_fields(self):
        # Should not raise, even with empty strings
        h = compute_dedup_hash("", "", "")
        assert isinstance(h, str)
        assert len(h) == 64
