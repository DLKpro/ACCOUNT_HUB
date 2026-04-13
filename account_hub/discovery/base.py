from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DiscoveredAccountResult:
    email_address: str
    service_name: str
    service_domain: Optional[str] = None
    source: str = ""
    source_detail: Optional[str] = None
    confidence: str = "confirmed"
    breach_date: Optional[str] = None  # ISO date string


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
    async def scan(self, email: str) -> List[DiscoveredAccountResult]:
        """Scan for accounts associated with the given email address."""
        ...
