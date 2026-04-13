from account_hub.config import Settings


def test_default_settings():
    s = Settings()
    assert s.api_host == "127.0.0.1"
    assert s.api_port == 8000
    assert s.access_token_expire_minutes == 30
    assert s.refresh_token_expire_days == 7


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("API_PORT", "9000")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-testing")
    s = Settings()
    assert s.api_port == 9000
    assert s.secret_key == "test-secret-key-for-testing"


def test_oauth_defaults_empty():
    s = Settings(_env_file=None)
    assert s.google_client_id == ""
    assert s.microsoft_client_id == ""
    assert s.apple_client_id == ""
    assert s.meta_client_id == ""
    assert s.hibp_api_key == ""
