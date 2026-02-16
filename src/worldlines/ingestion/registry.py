"""Adapter registry — maps type strings to adapter classes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from worldlines.ingestion.adapter import SourceAdapter

_REGISTRY: dict[str, type[SourceAdapter]] = {}


def register_adapter(type_name: str, cls: type[SourceAdapter]) -> None:
    """Register an adapter class for a given type name."""
    _REGISTRY[type_name] = cls


def get_adapter_class(type_name: str) -> type[SourceAdapter] | None:
    """Look up an adapter class by type name. Returns None if not found."""
    return _REGISTRY.get(type_name)


def registered_types() -> list[str]:
    """Return a sorted list of all registered adapter type names."""
    return sorted(_REGISTRY)
