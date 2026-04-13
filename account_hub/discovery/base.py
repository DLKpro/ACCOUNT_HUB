from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DiscoveredAccountResult:
    email_address: str
    service_name: str
    service_domain: str | None = None
    source: str = ""
    source_detail: str | None = None
    confidence: str = "confirmed"
    breach_date: str | None = None  # ISO date string


class BaseScanner(ABC):
    """Abstract base class for account discovery scanners."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this scanner."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this scanner has the required config (API keys, etc.)."""
        ...

    @abstractmethod
    async def scan(self, email: str) -> list[DiscoveredAccountResult]:
        """Scan for accounts associated with the given email address."""
        ...
