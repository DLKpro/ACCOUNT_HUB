"""Shared fixtures for CLI command tests.

CLI commands use synchronous httpx.Client via helpers.get_client() / get_anon_client().
We mock at the httpx boundary so tests are fast, synchronous, and don't need a real API.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner


@pytest.fixture()
def cli_runner():
    return CliRunner()


@pytest.fixture()
def mock_creds(tmp_path, monkeypatch):
    """Redirect credentials to tmp_path with a pre-written fake token."""
    import account_hub.cli.helpers as helpers

    creds_dir = tmp_path / ".accounthub"
    creds_dir.mkdir()
    creds_file = creds_dir / "credentials.json"
    creds_file.write_text(json.dumps({
        "api_url": "http://test:8000",
        "access_token": "fake-access-token",
        "refresh_token": "fake-refresh-token",
    }))
    creds_file.chmod(0o600)

    monkeypatch.setattr(helpers, "CREDENTIALS_DIR", creds_dir)
    monkeypatch.setattr(helpers, "CREDENTIALS_FILE", creds_file)
    return creds_file


def mock_response(status_code: int, json_data: dict | list | None = None, text: str = ""):
    """Create a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text or (json.dumps(json_data) if json_data else "")
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.return_value = {}
    return resp


@contextmanager
def patched_client(monkeypatch, responses: dict):
    """Patch get_client to return a mock client with pre-configured responses.

    responses: dict mapping (method, path) to mock responses.
    Example: {("get", "/emails"): mock_response(200, [...])}
    """
    import account_hub.cli.helpers as helpers

    mock_client = MagicMock()

    def _dispatch(method):
        def handler(path, **kwargs):
            key = (method, path)
            # Try exact match first, then prefix match
            if key in responses:
                return responses[key]
            for (m, p), resp in responses.items():
                if m == method and path.startswith(p):
                    return resp
            return mock_response(500, {"detail": f"Unmocked: {method} {path}"})
        return handler

    mock_client.get = _dispatch("get")
    mock_client.post = _dispatch("post")
    mock_client.delete = _dispatch("delete")
    mock_client.request = lambda method, path, **kw: _dispatch(method.lower())(path, **kw)

    @contextmanager
    def fake_client():
        yield mock_client

    @contextmanager
    def fake_anon_client():
        yield mock_client

    monkeypatch.setattr(helpers, "get_client", fake_client)
    monkeypatch.setattr(helpers, "get_anon_client", fake_anon_client)

    # Also patch the module-level references in each command module so that
    # `from account_hub.cli.helpers import get_client` bindings are replaced.
    import account_hub.cli.auth_commands as auth_mod
    import account_hub.cli.close_commands as close_mod
    import account_hub.cli.email_commands as email_mod
    import account_hub.cli.search_commands as search_mod

    for mod in (auth_mod, close_mod, email_mod, search_mod):
        if hasattr(mod, "get_client"):
            monkeypatch.setattr(mod, "get_client", fake_client)
        if hasattr(mod, "get_anon_client"):
            monkeypatch.setattr(mod, "get_anon_client", fake_anon_client)

    yield mock_client
