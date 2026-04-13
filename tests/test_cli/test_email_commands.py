"""Tests for account_hub.cli.email_commands (list, unlink, device-code link)."""
from __future__ import annotations

import time
from contextlib import contextmanager
from unittest.mock import MagicMock

from account_hub.cli.main import app
from tests.test_cli.conftest import mock_response

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_EMAILS = [
    {
        "id": "em-1",
        "email_address": "alice@example.com",
        "provider": "google",
        "is_verified": True,
        "linked_at": "2025-06-01T12:00:00Z",
    },
    {
        "id": "em-2",
        "email_address": "bob@microsoft.com",
        "provider": "microsoft",
        "is_verified": False,
        "linked_at": "2025-07-15T09:30:00Z",
    },
]


def _patch_get_client(monkeypatch, mock_client):
    """Patch get_client in both helpers and email_commands modules."""
    import account_hub.cli.email_commands as email_mod
    import account_hub.cli.helpers as helpers

    @contextmanager
    def fake_client():
        yield mock_client

    monkeypatch.setattr(helpers, "get_client", fake_client)
    monkeypatch.setattr(email_mod, "get_client", fake_client)


def _make_dispatch_client(monkeypatch, responses: dict):
    """Build a mock client that dispatches by (method, path) and patch it in."""
    mock_client = MagicMock()

    def _dispatch(method):
        def handler(path, **kwargs):
            key = (method, path)
            if key in responses:
                return responses[key]
            # prefix match
            for (m, p), resp in responses.items():
                if m == method and path.startswith(p):
                    return resp
            return mock_response(500, {"detail": f"Unmocked: {method} {path}"})
        return handler

    mock_client.get = _dispatch("get")
    mock_client.post = _dispatch("post")
    mock_client.delete = _dispatch("delete")

    _patch_get_client(monkeypatch, mock_client)
    return mock_client


# ---------------------------------------------------------------------------
# email list
# ---------------------------------------------------------------------------

def test_list_emails_success(cli_runner, mock_creds, monkeypatch):
    _make_dispatch_client(monkeypatch, {
        ("get", "/emails"): mock_response(200, SAMPLE_EMAILS),
    })
    result = cli_runner.invoke(app, ["email", "list"])

    assert result.exit_code == 0
    assert "alice@example.com" in result.output
    assert "bob@microsoft.com" in result.output
    assert "google" in result.output
    assert "microsoft" in result.output


def test_list_emails_empty(cli_runner, mock_creds, monkeypatch):
    _make_dispatch_client(monkeypatch, {
        ("get", "/emails"): mock_response(200, []),
    })
    result = cli_runner.invoke(app, ["email", "list"])

    assert result.exit_code == 0
    assert "No linked emails" in result.output


def test_list_emails_error(cli_runner, mock_creds, monkeypatch):
    _make_dispatch_client(monkeypatch, {
        ("get", "/emails"): mock_response(500, None, text="Internal Server Error"),
    })
    result = cli_runner.invoke(app, ["email", "list"])

    assert result.exit_code != 0
    assert "500" in result.output


# ---------------------------------------------------------------------------
# email unlink
# ---------------------------------------------------------------------------

def test_unlink_success(cli_runner, mock_creds, monkeypatch):
    _make_dispatch_client(monkeypatch, {
        ("delete", "/emails/"): mock_response(204),
    })
    result = cli_runner.invoke(app, ["email", "unlink", "some-id"])

    assert result.exit_code == 0
    assert "unlinked" in result.output.lower()


def test_unlink_not_found(cli_runner, mock_creds, monkeypatch):
    _make_dispatch_client(monkeypatch, {
        ("delete", "/emails/"): mock_response(404),
    })
    result = cli_runner.invoke(app, ["email", "unlink", "bad-id"])

    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_unlink_server_error(cli_runner, mock_creds, monkeypatch):
    _make_dispatch_client(monkeypatch, {
        ("delete", "/emails/"): mock_response(500, None, text="Internal Server Error"),
    })
    result = cli_runner.invoke(app, ["email", "unlink", "some-id"])

    assert result.exit_code != 0
    assert "500" in result.output


# ---------------------------------------------------------------------------
# email link microsoft  (device-code flow)
# ---------------------------------------------------------------------------

INITIATE_DATA = {
    "user_code": "ABC123",
    "verification_uri": "https://example.com/device",
    "device_code": "dc_test",
    "interval": 1,
    "state": "st",
}


def test_device_code_flow_success(cli_runner, mock_creds, monkeypatch):
    """Initiate OK, first poll pending, second poll success."""
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    initiate_resp = mock_response(200, INITIATE_DATA)
    pending = mock_response(200, {"status": "pending"})
    success = mock_response(200, {
        "status": "complete",
        "email_address": "user@outlook.com",
    })
    poll_responses = [pending, success]

    mock_client = MagicMock()

    def _post(path, **kwargs):
        if "/oauth/initiate" in path:
            return initiate_resp
        if "/oauth/poll" in path:
            return poll_responses.pop(0)
        return mock_response(500, {"detail": f"Unmocked POST {path}"})

    mock_client.post = _post
    _patch_get_client(monkeypatch, mock_client)

    result = cli_runner.invoke(app, ["email", "link", "microsoft"])

    assert result.exit_code == 0
    assert "ABC123" in result.output
    assert "https://example.com/device" in result.output
    assert "user@outlook.com" in result.output
    assert "successfully" in result.output.lower()


def test_device_code_initiate_failure(cli_runner, mock_creds, monkeypatch):
    """Initiate returns 500 -> should surface error and exit."""
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    _make_dispatch_client(monkeypatch, {
        ("post", "/oauth/initiate"): mock_response(500, {"detail": "provider unavailable"}),
    })
    result = cli_runner.invoke(app, ["email", "link", "microsoft"])

    assert result.exit_code != 0
    assert "provider unavailable" in result.output.lower()


def test_device_code_poll_conflict(cli_runner, mock_creds, monkeypatch):
    """Initiate OK, poll returns 409 -> 'already linked' message."""
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    initiate_resp = mock_response(200, INITIATE_DATA)
    conflict = mock_response(409, {"detail": "Email already linked"})

    mock_client = MagicMock()

    def _post(path, **kwargs):
        if "/oauth/initiate" in path:
            return initiate_resp
        if "/oauth/poll" in path:
            return conflict
        return mock_response(500, {"detail": f"Unmocked POST {path}"})

    mock_client.post = _post
    _patch_get_client(monkeypatch, mock_client)

    result = cli_runner.invoke(app, ["email", "link", "microsoft"])

    assert result.exit_code == 0
    assert "already linked" in result.output.lower()
