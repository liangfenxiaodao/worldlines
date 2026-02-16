"""Tests for worldlines.ingestion.registry — adapter registry."""

from __future__ import annotations

from worldlines.ingestion.adapter import SourceAdapter
from worldlines.ingestion.registry import (
    _REGISTRY,
    get_adapter_class,
    register_adapter,
    registered_types,
)


class _DummyAdapter(SourceAdapter):
    @property
    def name(self) -> str:
        return "dummy"

    def fetch(self):
        return []

    def configure(self, config: dict) -> None:
        pass


class TestRegistry:
    def setup_method(self):
        self._original = dict(_REGISTRY)

    def teardown_method(self):
        _REGISTRY.clear()
        _REGISTRY.update(self._original)

    def test_register_and_lookup(self):
        register_adapter("dummy", _DummyAdapter)
        assert get_adapter_class("dummy") is _DummyAdapter

    def test_lookup_unknown_returns_none(self):
        assert get_adapter_class("nonexistent") is None

    def test_registered_types_sorted(self):
        register_adapter("zzz", _DummyAdapter)
        register_adapter("aaa", _DummyAdapter)
        types = registered_types()
        assert types[0] == "aaa"
        assert "zzz" in types

    def test_rss_registered_by_default(self):
        assert get_adapter_class("rss") is not None
