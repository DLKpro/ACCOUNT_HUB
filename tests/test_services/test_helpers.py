"""Unit tests for CLI helpers — credential file I/O."""
import json
import os
from pathlib import Path

import pytest

from account_hub.cli.helpers import clear_credentials, load_credentials, save_credentials


@pytest.fixture
def cred_dir(tmp_path, monkeypatch):
    """Redirect credential storage to a temp directory."""
    import account_hub.cli.helpers as helpers

    fake_dir = tmp_path / ".accounthub"
    monkeypatch.setattr(helpers, "CREDENTIALS_DIR", fake_dir)
    monkeypatch.setattr(helpers, "CREDENTIALS_FILE", fake_dir / "credentials.json")
    return fake_dir


def test_save_creates_directory(cred_dir):
    assert not cred_dir.exists()
    save_credentials("at", "rt")
    assert cred_dir.exists()


def test_save_creates_file_with_correct_content(cred_dir):
    save_credentials("access-123", "refresh-456")
    cred_file = cred_dir / "credentials.json"
    assert cred_file.exists()

    data = json.loads(cred_file.read_text())
    assert data["access_token"] == "access-123"
    assert data["refresh_token"] == "refresh-456"
    assert "api_url" in data
    assert "saved_at" in data


def test_save_file_has_secure_permissions(cred_dir):
    save_credentials("at", "rt")
    cred_file = cred_dir / "credentials.json"
    mode = cred_file.stat().st_mode & 0o777
    assert mode == 0o600


def test_load_returns_none_when_no_file(cred_dir):
    assert load_credentials() is None


def test_load_returns_saved_data(cred_dir):
    save_credentials("my-access", "my-refresh")
    data = load_credentials()
    assert data is not None
    assert data["access_token"] == "my-access"
    assert data["refresh_token"] == "my-refresh"


def test_clear_removes_file(cred_dir):
    save_credentials("at", "rt")
    cred_file = cred_dir / "credentials.json"
    assert cred_file.exists()

    clear_credentials()
    assert not cred_file.exists()


def test_clear_does_nothing_when_no_file(cred_dir):
    clear_credentials()  # should not raise


def test_save_overwrites_existing(cred_dir):
    save_credentials("old-access", "old-refresh")
    save_credentials("new-access", "new-refresh")
    data = load_credentials()
    assert data["access_token"] == "new-access"
    assert data["refresh_token"] == "new-refresh"
