"""Have I Been Pwned breach scanner.

Requires a paid HIBP API key ($3.50/mo). When the key is not configured,
is_available() returns False and the scanner is skipped.
"""
from __future__ import annotations

import asyncio
import json
from typing import List

import httpx

from account_hub.config import settings
from account_hub.discovery.base import BaseScanner, DiscoveredAccountResult

HIBP_API_URL = "https://haveibeenpwned.com/api/v3"
# HIBP rate limit: 10 requests per minute
_semaphore = asyncio.Semaphore(1)
_MIN_INTERVAL = 6.0  # seconds between requests


class HIBPBreachScanner(BaseScanner):

    @property
    def name(self) -> str:
        return "hibp_breach"

    def is_available(self) -> bool:
        return bool(settings.hibp_api_key)

    async def scan(self, email: str) -> List[DiscoveredAccountResult]:
        if not self.is_available():
            return []

        async with _semaphore:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{HIBP_API_URL}/breachedaccount/{email}",
                    params={"truncateResponse": "false"},
                    headers={
                        "hibp-api-key": settings.hibp_api_key,
                        "user-agent": "AccountHub",
                    },
                    timeout=15.0,
                )

            # Rate limit compliance
            await asyncio.sleep(_MIN_INTERVAL)

        if resp.status_code == 404:
            return []  # No breaches found

        if resp.status_code != 200:
            return []  # Fail silently — don't break the scan

        results: List[DiscoveredAccountResult] = []
        for breach in resp.json():
            results.append(
                DiscoveredAccountResult(
                    email_address=email,
                    service_name=breach.get("Name", "Unknown"),
                    service_domain=breach.get("Domain"),
                    source="hibp_breach",
                    source_detail=json.dumps({
                        "breach_name": breach.get("Name"),
                        "data_classes": breach.get("DataClasses", []),
                    }),
                    confidence="confirmed",
                    breach_date=breach.get("BreachDate"),
                )
            )

        return results
