"""Tests for CLI close commands: list, request, complete, info, delete-account."""
from __future__ import annotations

from unittest.mock import patch

from account_hub.cli.main import app
from tests.test_cli.conftest import mock_response, patched_client

CLOSURE_REQUESTS = [
    {
        "id": "cr-11111111-2222-3333-4444-555555555555",
        "service_name": "GitHub",
        "method": "web",
        "status": "pending",
        "deletion_url": "https://github.com/settings/admin",
    },
    {
        "id": "cr-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "service_name": "Spotify",
        "method": "email",
        "status": "requested",
        "deletion_url": None,
    },
]


# -- close list ---------------------------------------------------------------


def test_list_closure_requests(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("get", "/accounts/close-requests"): mock_response(200, CLOSURE_REQUESTS),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["close", "list"])

    assert result.exit_code == 0
    assert "Closure Requests" in result.output
    assert "GitHub" in result.output
    assert "Spotify" in result.output


def test_list_closure_empty(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("get", "/accounts/close-requests"): mock_response(200, []),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["close", "list"])

    assert result.exit_code == 0
    assert "No closure requests" in result.output


def test_list_closure_error(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("get", "/accounts/close-requests"): mock_response(
            500, text="Internal Server Error"
        ),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["close", "list"])

    assert result.exit_code != 0
    assert "Error" in result.output


# -- close request ------------------------------------------------------------


def test_request_closure_success(cli_runner, mock_creds, monkeypatch):
    """method=web but no deletion_url -> browser prompt should NOT appear."""
    responses = {
        ("post", "/accounts/close"): mock_response(
            201,
            {
                "service_name": "Notion",
                "method": "web",
                "status": "pending",
                "deletion_url": None,
                "notes": "Check your email for confirmation.",
            },
        ),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["close", "request", "acct-123"])

    assert result.exit_code == 0
    assert "Closure requested for Notion" in result.output
    assert "Method: web" in result.output
    assert "Notes: Check your email" in result.output
    # No browser prompt because deletion_url is None
    assert "Open deletion page" not in result.output


def test_request_closure_not_found(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("post", "/accounts/close"): mock_response(404),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["close", "request", "bad-id"])

    assert result.exit_code != 0
    assert "not found" in result.output


# -- close complete -----------------------------------------------------------


def test_complete_success(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("post", "/accounts/close/complete"): mock_response(
            200, {"service_name": "GitHub", "status": "closed"}
        ),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["close", "complete", "cr-1234"])

    assert result.exit_code == 0
    assert "GitHub" in result.output
    assert "marked as closed" in result.output


def test_complete_not_found(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("post", "/accounts/close/complete"): mock_response(404),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["close", "complete", "bad-id"])

    assert result.exit_code != 0
    assert "not found" in result.output


# -- close info ---------------------------------------------------------------


def test_closure_info_success(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("get", "/accounts/close-info/GitHub"): mock_response(
            200,
            {
                "service_name": "GitHub",
                "difficulty": "easy",
                "method": "web",
                "deletion_url": "https://github.com/settings/admin",
                "notes": "Navigate to account settings.",
            },
        ),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["close", "info", "GitHub"])

    assert result.exit_code == 0
    assert "GitHub" in result.output
    assert "Difficulty: easy" in result.output
    assert "Method:     web" in result.output
    assert "URL:" in result.output
    assert "Notes:" in result.output


def test_closure_info_error(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("get", "/accounts/close-info/UnknownService"): mock_response(
            500, text="Internal Server Error"
        ),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["close", "info", "UnknownService"])

    assert result.exit_code != 0
    assert "Error" in result.output


# -- close delete-account -----------------------------------------------------


def test_delete_account_success(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("delete", "/auth/account"): mock_response(204),
    }
    with patched_client(monkeypatch, responses):
        with patch("account_hub.cli.close_commands.clear_credentials") as mock_clear:
            result = cli_runner.invoke(
                app, ["close", "delete-account"], input="testpass1\ny\n"
            )

    assert result.exit_code == 0
    assert "deleted" in result.output.lower()
    mock_clear.assert_called_once()


def test_delete_account_cancelled(cli_runner, mock_creds, monkeypatch):
    # No API call expected -- user declines the confirmation prompt.
    responses = {}
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(
            app, ["close", "delete-account"], input="testpass1\nn\n"
        )

    assert result.exit_code == 0
    assert "Cancelled" in result.output


def test_delete_account_wrong_pw(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("delete", "/auth/account"): mock_response(403),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(
            app, ["close", "delete-account"], input="wrongpass\ny\n"
        )

    assert result.exit_code != 0
    assert "Incorrect password" in result.output
