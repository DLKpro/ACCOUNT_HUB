"""Unit tests for export_service — CSV generation."""
import csv
import io
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from account_hub.services.export_service import export_to_csv


def _mock_account(**kwargs):
    """Create a mock DiscoveredAccount with sensible defaults."""
    defaults = {
        "email_address": "user@gmail.com",
        "service_name": "TestService",
        "service_domain": "testservice.com",
        "source": "oauth_profile",
        "confidence": "confirmed",
        "breach_date": None,
        "discovered_at": datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc),
    }
    defaults.update(kwargs)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def test_export_empty_list():
    result = export_to_csv([])
    reader = csv.reader(io.StringIO(result))
    rows = list(reader)
    assert len(rows) == 1  # Header only
    assert rows[0][0] == "email_address"


def test_export_single_account():
    accounts = [_mock_account()]
    result = export_to_csv(accounts)
    reader = csv.reader(io.StringIO(result))
    rows = list(reader)
    assert len(rows) == 2
    assert rows[1][0] == "user@gmail.com"
    assert rows[1][1] == "TestService"
    assert rows[1][2] == "testservice.com"
    assert rows[1][3] == "oauth_profile"
    assert rows[1][4] == "confirmed"


def test_export_multiple_accounts():
    accounts = [
        _mock_account(email_address="a@gmail.com", service_name="ServiceA"),
        _mock_account(email_address="b@outlook.com", service_name="ServiceB"),
        _mock_account(email_address="a@gmail.com", service_name="ServiceC"),
    ]
    result = export_to_csv(accounts)
    reader = csv.reader(io.StringIO(result))
    rows = list(reader)
    assert len(rows) == 4  # Header + 3


def test_export_handles_missing_domain():
    accounts = [_mock_account(service_domain=None)]
    result = export_to_csv(accounts)
    reader = csv.reader(io.StringIO(result))
    rows = list(reader)
    assert rows[1][2] == ""  # Empty domain


def test_export_handles_breach_date():
    from datetime import date
    accounts = [_mock_account(breach_date=date(2023, 1, 15))]
    result = export_to_csv(accounts)
    reader = csv.reader(io.StringIO(result))
    rows = list(reader)
    assert rows[1][5] == "2023-01-15"


def test_export_csv_header_columns():
    result = export_to_csv([])
    reader = csv.reader(io.StringIO(result))
    header = next(reader)
    assert header == [
        "email_address", "service_name", "service_domain",
        "source", "confidence", "breach_date", "discovered_at",
    ]
