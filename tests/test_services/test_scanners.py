"""Unit tests for discovery scanners."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
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


# ---------------------------------------------------------------------------
# Helper: build a mock async httpx client
# ---------------------------------------------------------------------------


def _make_mock_client(get_response):
    """Return (mock_context_manager, mock_client) for patching httpx.AsyncClient."""
    mock_client = AsyncMock()
    mock_client.get.return_value = get_response
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx, mock_client


def _make_response(status_code: int, json_body=None):
    """Create a lightweight mock httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    if json_body is not None:
        resp.json.return_value = json_body
    return resp


# --- GravatarScanner HTTP mocking ---


@pytest.mark.asyncio
async def test_gravatar_scan_found():
    from account_hub.discovery.gravatar import GravatarScanner

    response = _make_response(200, {"entry": [{"accounts": []}]})
    mock_ctx, _ = _make_mock_client(response)

    with patch("account_hub.discovery.gravatar.httpx.AsyncClient", return_value=mock_ctx):
        scanner = GravatarScanner()
        results = await scanner.scan("test@example.com")

    assert len(results) == 1
    assert results[0].service_name == "Gravatar"
    assert results[0].service_domain == "gravatar.com"
    assert results[0].source == "gravatar"
    assert results[0].confidence == "confirmed"
    assert results[0].email_address == "test@example.com"


@pytest.mark.asyncio
async def test_gravatar_scan_with_linked_accounts():
    from account_hub.discovery.gravatar import GravatarScanner

    response = _make_response(200, {
        "entry": [{
            "accounts": [
                {"shortname": "twitter", "domain": "twitter.com"},
            ],
        }],
    })
    mock_ctx, _ = _make_mock_client(response)

    with patch("account_hub.discovery.gravatar.httpx.AsyncClient", return_value=mock_ctx):
        scanner = GravatarScanner()
        results = await scanner.scan("test@example.com")

    assert len(results) == 2
    assert results[0].service_name == "Gravatar"
    assert results[1].service_name == "twitter"
    assert results[1].service_domain == "twitter.com"


@pytest.mark.asyncio
async def test_gravatar_scan_not_found():
    from account_hub.discovery.gravatar import GravatarScanner

    response = _make_response(404)
    mock_ctx, _ = _make_mock_client(response)

    with patch("account_hub.discovery.gravatar.httpx.AsyncClient", return_value=mock_ctx):
        scanner = GravatarScanner()
        results = await scanner.scan("nobody@example.com")

    assert results == []


@pytest.mark.asyncio
async def test_gravatar_scan_server_error():
    from account_hub.discovery.gravatar import GravatarScanner

    response = _make_response(500)
    mock_ctx, _ = _make_mock_client(response)

    with patch("account_hub.discovery.gravatar.httpx.AsyncClient", return_value=mock_ctx):
        scanner = GravatarScanner()
        results = await scanner.scan("test@example.com")

    assert results == []


@pytest.mark.asyncio
async def test_gravatar_scan_network_error():
    from account_hub.discovery.gravatar import GravatarScanner

    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.HTTPError("connection failed")
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("account_hub.discovery.gravatar.httpx.AsyncClient", return_value=mock_ctx):
        scanner = GravatarScanner()
        results = await scanner.scan("test@example.com")

    assert results == []


# --- HIBPBreachScanner HTTP mocking ---


async def _noop_sleep(_seconds):
    """No-op replacement for asyncio.sleep to avoid 6-second waits."""
    pass


@pytest.mark.asyncio
async def test_hibp_scan_breaches_found(monkeypatch):
    from account_hub.discovery.hibp import HIBPBreachScanner

    monkeypatch.setattr("account_hub.discovery.hibp.settings.hibp_api_key", "test-key")
    monkeypatch.setattr("account_hub.discovery.hibp._MIN_INTERVAL", 0)
    monkeypatch.setattr("asyncio.sleep", _noop_sleep)

    breach_list = [
        {
            "Name": "ExampleBreach",
            "Domain": "example.com",
            "BreachDate": "2021-01-01",
            "DataClasses": ["Email addresses", "Passwords"],
        },
    ]
    response = _make_response(200, breach_list)
    mock_ctx, _ = _make_mock_client(response)

    with patch("account_hub.discovery.hibp.httpx.AsyncClient", return_value=mock_ctx):
        scanner = HIBPBreachScanner()
        results = await scanner.scan("test@example.com")

    assert len(results) == 1
    assert results[0].service_name == "ExampleBreach"
    assert results[0].service_domain == "example.com"
    assert results[0].source == "hibp_breach"
    assert results[0].confidence == "confirmed"
    assert results[0].breach_date == "2021-01-01"


@pytest.mark.asyncio
async def test_hibp_scan_no_breaches(monkeypatch):
    from account_hub.discovery.hibp import HIBPBreachScanner

    monkeypatch.setattr("account_hub.discovery.hibp.settings.hibp_api_key", "test-key")
    monkeypatch.setattr("account_hub.discovery.hibp._MIN_INTERVAL", 0)
    monkeypatch.setattr("asyncio.sleep", _noop_sleep)

    response = _make_response(404)
    mock_ctx, _ = _make_mock_client(response)

    with patch("account_hub.discovery.hibp.httpx.AsyncClient", return_value=mock_ctx):
        scanner = HIBPBreachScanner()
        results = await scanner.scan("clean@example.com")

    assert results == []


@pytest.mark.asyncio
async def test_hibp_scan_server_error(monkeypatch):
    from account_hub.discovery.hibp import HIBPBreachScanner

    monkeypatch.setattr("account_hub.discovery.hibp.settings.hibp_api_key", "test-key")
    monkeypatch.setattr("account_hub.discovery.hibp._MIN_INTERVAL", 0)
    monkeypatch.setattr("asyncio.sleep", _noop_sleep)

    response = _make_response(500)
    mock_ctx, _ = _make_mock_client(response)

    with patch("account_hub.discovery.hibp.httpx.AsyncClient", return_value=mock_ctx):
        scanner = HIBPBreachScanner()
        results = await scanner.scan("test@example.com")

    assert results == []


@pytest.mark.asyncio
async def test_hibp_scan_correct_headers(monkeypatch):
    from account_hub.discovery.hibp import HIBPBreachScanner

    monkeypatch.setattr("account_hub.discovery.hibp.settings.hibp_api_key", "test-key")
    monkeypatch.setattr("account_hub.discovery.hibp._MIN_INTERVAL", 0)
    monkeypatch.setattr("asyncio.sleep", _noop_sleep)

    response = _make_response(404)
    mock_ctx, mock_client = _make_mock_client(response)

    with patch("account_hub.discovery.hibp.httpx.AsyncClient", return_value=mock_ctx):
        scanner = HIBPBreachScanner()
        await scanner.scan("test@example.com")

    # Verify the GET call included the correct headers
    call_kwargs = mock_client.get.call_args
    headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
    assert headers["hibp-api-key"] == "test-key"
    assert headers["user-agent"] == "AccountHub"


@pytest.mark.asyncio
async def test_hibp_scan_source_detail(monkeypatch):
    from account_hub.discovery.hibp import HIBPBreachScanner

    monkeypatch.setattr("account_hub.discovery.hibp.settings.hibp_api_key", "test-key")
    monkeypatch.setattr("account_hub.discovery.hibp._MIN_INTERVAL", 0)
    monkeypatch.setattr("asyncio.sleep", _noop_sleep)

    breach_list = [
        {
            "Name": "BigBreach",
            "Domain": "bigbreach.com",
            "BreachDate": "2022-06-15",
            "DataClasses": ["Passwords", "Usernames"],
        },
    ]
    response = _make_response(200, breach_list)
    mock_ctx, _ = _make_mock_client(response)

    with patch("account_hub.discovery.hibp.httpx.AsyncClient", return_value=mock_ctx):
        scanner = HIBPBreachScanner()
        results = await scanner.scan("test@example.com")

    assert len(results) == 1
    detail = json.loads(results[0].source_detail)
    assert detail["breach_name"] == "BigBreach"
    assert "Passwords" in detail["data_classes"]
    assert "Usernames" in detail["data_classes"]
