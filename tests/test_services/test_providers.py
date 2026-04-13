"""Unit tests for the OAuth provider registry."""
import pytest

from account_hub.oauth.providers import (
    FlowType,
    OAuthProviderConfig,
    _registry,
    get_provider,
    is_provider_configured,
    list_providers,
    register_provider,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear the provider registry before each test."""
    saved = dict(_registry)
    _registry.clear()
    yield
    _registry.clear()
    _registry.update(saved)


def _make_config(name="testprov", client_id="cid", client_secret="csec", **kwargs):
    return OAuthProviderConfig(
        name=name,
        authorize_url="https://example.com/auth",
        token_url="https://example.com/token",
        userinfo_url="https://example.com/userinfo",
        scopes=["email"],
        flow_type=FlowType.LOOPBACK,
        client_id=client_id,
        client_secret=client_secret,
        **kwargs,
    )


def test_register_and_get_provider():
    register_provider(_make_config("myprov"))
    p = get_provider("myprov")
    assert p.name == "myprov"
    assert p.client_id == "cid"


def test_get_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown OAuth provider"):
        get_provider("nonexistent")


def test_list_providers_empty():
    assert list_providers() == []


def test_list_providers():
    register_provider(_make_config("a"))
    register_provider(_make_config("b"))
    assert set(list_providers()) == {"a", "b"}


def test_is_provider_configured_true():
    register_provider(_make_config("configured", client_id="id", client_secret="sec"))
    assert is_provider_configured("configured") is True


def test_is_provider_configured_false_empty_creds():
    register_provider(_make_config("unconfigured", client_id="", client_secret=""))
    assert is_provider_configured("unconfigured") is False


def test_is_provider_configured_false_unknown():
    assert is_provider_configured("ghost") is False


def test_flow_type_enum():
    assert FlowType.LOOPBACK == "loopback"
    assert FlowType.DEVICE_CODE == "device_code"


def test_provider_extra_params():
    p = _make_config(extra_authorize_params={"access_type": "offline"})
    assert p.extra_authorize_params == {"access_type": "offline"}
