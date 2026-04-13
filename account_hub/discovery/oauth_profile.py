"""Scanner that creates a discovered account entry for each linked OAuth provider.

When you link an email via Google/Microsoft/Apple/Meta, we know for certain
that the email has an account on that provider. This scanner surfaces that.
"""
from __future__ import annotations

from typing import List

from account_hub.discovery.base import BaseScanner, DiscoveredAccountResult

PROVIDER_DOMAINS = {
    "google": "google.com",
    "microsoft": "microsoft.com",
    "apple": "apple.com",
    "meta": "facebook.com",
}

PROVIDER_NAMES = {
    "google": "Google Account",
    "microsoft": "Microsoft Account",
    "apple": "Apple ID",
    "meta": "Facebook",
}


class OAuthProfileScanner(BaseScanner):
    """Produces a confirmed account entry for the OAuth provider itself."""

    def __init__(self, provider: str):
        self._provider = provider

    @property
    def name(self) -> str:
        return f"oauth_profile_{self._provider}"

    def is_available(self) -> bool:
        return True  # Always available for linked emails

    async def scan(self, email: str) -> List[DiscoveredAccountResult]:
        return [
            DiscoveredAccountResult(
                email_address=email,
                service_name=PROVIDER_NAMES.get(self._provider, self._provider),
                service_domain=PROVIDER_DOMAINS.get(self._provider),
                source="oauth_profile",
                confidence="confirmed",
            )
        ]
