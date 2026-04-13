"""Unit tests for discovery scanners."""
import pytest

from account_hub.discovery.base import BaseScanner, DiscoveredAccountResult
from account_hub.discovery.oauth_profile import OAuthProfileScanner


# --- OAuthProfileScanner ---


@pytest.mark.asyncio
async def test_oauth_profile_scanner_google():
    scanner = OAuthProfileScanner("google")
    results = await scanner.scan("user@gmail.com")
    assert len(results) == 1
    assert results[0].service_name == "Google Account"
    assert results[0].service_domain == "google.com"
    assert results[0].source == "oauth_profile"
    assert results[0].confidence == "confirmed"
    assert results[0].email_address == "user@gmail.com"


@pytest.mark.asyncio
async def test_oauth_profile_scanner_microsoft():
    scanner = OAuthProfileScanner("microsoft")
    results = await scanner.scan("user@outlook.com")
    assert len(results) == 1
    assert results[0].service_name == "Microsoft Account"
    assert results[0].service_domain == "microsoft.com"


@pytest.mark.asyncio
async def test_oauth_profile_scanner_apple():
    scanner = OAuthProfileScanner("apple")
    results = await scanner.scan("user@icloud.com")
    assert results[0].service_name == "Apple ID"
    assert results[0].service_domain == "apple.com"


@pytest.mark.asyncio
async def test_oauth_profile_scanner_meta():
    scanner = OAuthProfileScanner("meta")
    results = await scanner.scan("user@facebook.com")
    assert results[0].service_name == "Facebook"
    assert results[0].service_domain == "facebook.com"


def test_oauth_profile_scanner_is_available():
    scanner = OAuthProfileScanner("google")
    assert scanner.is_available() is True


def test_oauth_profile_scanner_name():
    scanner = OAuthProfileScanner("google")
    assert scanner.name == "oauth_profile_google"


# --- GravatarScanner ---


def test_gravatar_scanner_is_available():
    from account_hub.discovery.gravatar import GravatarScanner

    scanner = GravatarScanner()
    assert scanner.is_available() is True
    assert scanner.name == "gravatar"


# --- HIBPBreachScanner (availability check only — no real API calls) ---


def test_hibp_scanner_not_available_without_key(monkeypatch):
    from account_hub.discovery.hibp import HIBPBreachScanner

    monkeypatch.setattr("account_hub.discovery.hibp.settings.hibp_api_key", "")
    scanner = HIBPBreachScanner()
    assert scanner.is_available() is False
    assert scanner.name == "hibp_breach"


@pytest.mark.asyncio
async def test_hibp_scanner_returns_empty_when_unavailable(monkeypatch):
    from account_hub.discovery.hibp import HIBPBreachScanner

    monkeypatch.setattr("account_hub.discovery.hibp.settings.hibp_api_key", "")
    scanner = HIBPBreachScanner()
    results = await scanner.scan("test@example.com")
    assert results == []


# --- BaseScanner abstract interface ---


def test_base_scanner_is_abstract():
    with pytest.raises(TypeError):
        BaseScanner()


def test_discovered_account_result_defaults():
    r = DiscoveredAccountResult(
        email_address="test@test.com",
        service_name="TestService",
        source="test",
    )
    assert r.confidence == "confirmed"
    assert r.service_domain is None
    assert r.source_detail is None
    assert r.breach_date is None
