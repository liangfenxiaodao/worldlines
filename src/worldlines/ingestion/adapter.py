"""Source adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from worldlines.ingestion.normalize import RawSourceItem


class SourceAdapter(ABC):
    """Abstract base class for source adapters.

    Every adapter knows how to fetch and parse items from a specific source
    type. The rest of the system is source-agnostic.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable adapter name."""

    @abstractmethod
    def fetch(self) -> list[RawSourceItem]:
        """Fetch new items from the source.

        Returns only items not previously seen. Adapters track their own
        position to avoid re-emitting items.
        """

    @abstractmethod
    def configure(self, config: dict) -> None:
        """Accept adapter-specific configuration."""
