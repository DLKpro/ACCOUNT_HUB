"""Gravatar profile scanner.

Checks if an email has a Gravatar profile by querying the Gravatar API.
No API key required. A profile existing confirms the email is registered.
"""
from __future__ import annotations

import hashlib
from typing import List

import httpx

from account_hub.discovery.base import BaseScanner, DiscoveredAccountResult


class GravatarScanner(BaseScanner):

    @property
    def name(self) -> str:
        return "gravatar"

    def is_available(self) -> bool:
        return True  # No API key needed

    async def scan(self, email: str) -> List[DiscoveredAccountResult]:
        email_hash = hashlib.md5(email.strip().lower().encode()).hexdigest()
        url = f"https://gravatar.com/{email_hash}.json"

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url, timeout=10.0, follow_redirects=True)
            except httpx.HTTPError:
                return []

        if resp.status_code == 404:
            return []  # No profile
        if resp.status_code != 200:
            return []

        results: List[DiscoveredAccountResult] = [
            DiscoveredAccountResult(
                email_address=email,
                service_name="Gravatar",
                service_domain="gravatar.com",
                source="gravatar",
                confidence="confirmed",
            )
        ]

        # Parse linked accounts from the Gravatar profile
        try:
            data = resp.json()
            entries = data.get("entry", [])
            if entries:
                profile = entries[0]
                for account in profile.get("accounts", []):
                    results.append(
                        DiscoveredAccountResult(
                            email_address=email,
                            service_name=account.get("shortname", account.get("domain", "Unknown")),
                            service_domain=account.get("domain"),
                            source="gravatar",
                            confidence="confirmed",
                        )
                    )
        except (ValueError, KeyError):
            pass  # JSON parse failed, just return the base Gravatar result

        return results
