"""Base interface for a keyword/trend source."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrendingTerm:
    term: str
    source: str
    score: float = 0.0  # 0-100
    raw: dict[str, Any] = field(default_factory=dict)


class KeywordSource(ABC):
    """Base class. Each subclass fetches trending terms for a niche/seed."""

    name: str = "base"

    @abstractmethod
    def fetch(self, seed: str, limit: int = 20) -> list[TrendingTerm]:
        """Return up to `limit` trending terms for the given seed/niche."""
