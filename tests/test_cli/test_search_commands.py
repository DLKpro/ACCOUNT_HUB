"""Tests for CLI search commands: run, results, history, export."""
from __future__ import annotations

from account_hub.cli.main import app
from tests.test_cli.conftest import mock_response, patched_client

SESSION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

SCAN_DETAIL = {
    "id": SESSION_ID,
    "status": "completed",
    "emails_scanned": 3,
    "accounts_found": 2,
    "results": [
        {
            "email_address": "user@example.com",
            "service_name": "GitHub",
            "service_domain": "github.com",
            "source": "oauth",
            "confidence": "high",
        },
        {
            "email_address": "user@example.com",
            "service_name": "Spotify",
            "service_domain": "spotify.com",
            "source": "email_header",
            "confidence": "medium",
        },
    ],
}

HISTORY_ENTRIES = [
    {
        "id": SESSION_ID,
        "status": "completed",
        "emails_scanned": 3,
        "accounts_found": 2,
        "created_at": "2025-06-01T12:00:00Z",
    },
    {
        "id": "22222222-3333-4444-5555-666666666666",
        "status": "completed",
        "emails_scanned": 1,
        "accounts_found": 0,
        "created_at": "2025-05-15T08:00:00Z",
    },
]


# -- search run ---------------------------------------------------------------


def test_run_search_completed(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("post", "/search"): mock_response(
            201, {"scan_session_id": SESSION_ID, "status": "completed"}
        ),
        ("get", f"/search/{SESSION_ID}"): mock_response(200, SCAN_DETAIL),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["search", "run"])

    assert result.exit_code == 0
    assert "GitHub" in result.output
    assert "Spotify" in result.output
    assert "Accounts found" in result.output


def test_run_search_running(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("post", "/search"): mock_response(
            201, {"scan_session_id": SESSION_ID, "status": "running"}
        ),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["search", "run"])

    assert result.exit_code == 0
    assert "is running" in result.output


def test_run_search_error(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("post", "/search"): mock_response(500, text="Internal Server Error"),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["search", "run"])

    assert result.exit_code != 0
    assert "Error" in result.output


# -- search results -----------------------------------------------------------


def test_results_with_session_id(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("get", f"/search/{SESSION_ID}"): mock_response(200, SCAN_DETAIL),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["search", "results", SESSION_ID])

    assert result.exit_code == 0
    assert "GitHub" in result.output
    assert "Spotify" in result.output
    assert "user@example.com" in result.output


def test_results_default_latest(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("get", "/search/history"): mock_response(200, [HISTORY_ENTRIES[0]]),
        ("get", f"/search/{SESSION_ID}"): mock_response(200, SCAN_DETAIL),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["search", "results"])

    assert result.exit_code == 0
    assert "GitHub" in result.output


def test_results_no_scans(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("get", "/search/history"): mock_response(200, []),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["search", "results"])

    assert result.exit_code != 0
    assert "No scans found" in result.output


# -- search history -----------------------------------------------------------


def test_history_success(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("get", "/search/history"): mock_response(200, HISTORY_ENTRIES),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["search", "history"])

    assert result.exit_code == 0
    assert "Scan History" in result.output
    assert "completed" in result.output
    assert "2025-06-01" in result.output


def test_history_empty(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("get", "/search/history"): mock_response(200, []),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["search", "history"])

    assert result.exit_code == 0
    assert "No scans found" in result.output


# -- search export ------------------------------------------------------------


def test_export_success(cli_runner, mock_creds, monkeypatch, tmp_path):
    csv_text = "email,service,domain\nuser@example.com,GitHub,github.com\n"
    out_file = tmp_path / "export.csv"
    responses = {
        ("get", "/search/history"): mock_response(200, [HISTORY_ENTRIES[0]]),
        ("get", f"/search/{SESSION_ID}/export"): mock_response(
            200, text=csv_text
        ),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(
            app, ["search", "export", "--output", str(out_file)]
        )

    assert result.exit_code == 0
    assert "Exported" in result.output
    assert out_file.read_text() == csv_text


def test_export_no_scans(cli_runner, mock_creds, monkeypatch):
    responses = {
        ("get", "/search/history"): mock_response(200, []),
    }
    with patched_client(monkeypatch, responses):
        result = cli_runner.invoke(app, ["search", "export"])

    assert result.exit_code != 0
    assert "No scans found" in result.output
