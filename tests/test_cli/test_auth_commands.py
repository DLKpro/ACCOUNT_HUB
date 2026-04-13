"""Tests for CLI auth commands: register, login, me, logout."""
from __future__ import annotations

from unittest.mock import patch

from account_hub.cli.main import app
from tests.test_cli.conftest import mock_response, patched_client

# ── register ─────────────────────────────────────────────────────────


def test_register_success(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("post", "/auth/register"): mock_response(
            201,
            {
                "username": "testuser",
                "access_token": "tok-access",
                "refresh_token": "tok-refresh",
            },
        ),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(
            app,
            ["auth", "register"],
            input="testuser\npassword1\npassword1\n",
        )

    assert result.exit_code == 0
    assert "Account created" in result.output


def test_register_duplicate_409(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("post", "/auth/register"): mock_response(409),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(
            app,
            ["auth", "register"],
            input="testuser\npassword1\npassword1\n",
        )

    assert result.exit_code != 0
    assert "already taken" in result.output


def test_register_invalid_400(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("post", "/auth/register"): mock_response(
            400, {"detail": "Password must be at least 8 characters"}
        ),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(
            app,
            ["auth", "register"],
            input="testuser\nshort\nshort\n",
        )

    assert result.exit_code != 0
    assert "Password must be at least 8 characters" in result.output


def test_register_server_error(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("post", "/auth/register"): mock_response(500, text="Internal Server Error"),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(
            app,
            ["auth", "register"],
            input="testuser\npassword1\npassword1\n",
        )

    assert result.exit_code != 0
    assert "Error" in result.output


# ── login ────────────────────────────────────────────────────────────


def test_login_success(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("post", "/auth/login"): mock_response(
            200,
            {
                "username": "testuser",
                "access_token": "tok-access",
                "refresh_token": "tok-refresh",
            },
        ),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(
            app,
            ["auth", "login"],
            input="testuser\npassword1\n",
        )

    assert result.exit_code == 0
    assert "Logged in" in result.output


def test_login_wrong_password(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("post", "/auth/login"): mock_response(401),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(
            app,
            ["auth", "login"],
            input="testuser\nwrongpass\n",
        )

    assert result.exit_code != 0
    assert "Invalid" in result.output


def test_login_server_error(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("post", "/auth/login"): mock_response(500, text="Internal Server Error"),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(
            app,
            ["auth", "login"],
            input="testuser\npassword1\n",
        )

    assert result.exit_code != 0
    assert "Error" in result.output


# ── me ───────────────────────────────────────────────────────────────


def test_me_success(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("get", "/auth/me"): mock_response(
            200,
            {
                "username": "testuser",
                "id": "abc-123",
                "is_active": True,
                "created_at": "2025-01-01T00:00:00Z",
            },
        ),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["auth", "me"])

    assert result.exit_code == 0
    assert "testuser" in result.output
    assert "abc-123" in result.output
    assert "True" in result.output
    assert "2025-01-01" in result.output


def test_me_expired_session(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("get", "/auth/me"): mock_response(401),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["auth", "me"])

    assert result.exit_code != 0
    assert "Session expired" in result.output


def test_me_server_error(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("get", "/auth/me"): mock_response(500, text="Internal Server Error"),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["auth", "me"])

    assert result.exit_code != 0
    assert "Error" in result.output


# ── logout ───────────────────────────────────────────────────────────


def test_logout_clears(cli_runner, mock_creds, monkeypatch):
    with patch("account_hub.cli.auth_commands.clear_credentials") as mock_clear:
        result = cli_runner.invoke(app, ["auth", "logout"])

    assert result.exit_code == 0
    assert "Logged out" in result.output
    mock_clear.assert_called_once()
