from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FlowType(str, Enum):  # noqa: UP042
    LOOPBACK = "loopback"
    DEVICE_CODE = "device_code"


@dataclass
class OAuthProviderConfig:
    name: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scopes: list[str]
    flow_type: FlowType
    client_id: str
    client_secret: str
    extra_authorize_params: dict[str, str] = field(default_factory=dict)
    extra_token_params: dict[str, str] = field(default_factory=dict)
    revoke_url: str | None = None
    # Microsoft device code flow
    device_code_url: str | None = None


_registry: dict[str, OAuthProviderConfig] = {}


def register_provider(config: OAuthProviderConfig) -> None:
    _registry[config.name] = config


def get_provider(name: str) -> OAuthProviderConfig:
    if name not in _registry:
        raise ValueError(f"Unknown OAuth provider: '{name}'. Available: {list(_registry.keys())}")
    return _registry[name]


def list_providers() -> list[str]:
    return list(_registry.keys())


def is_provider_configured(name: str) -> bool:
    """Check if a provider has its client credentials set (non-empty)."""
    if name not in _registry:
        return False
    p = _registry[name]
    return bool(p.client_id and p.client_secret)
