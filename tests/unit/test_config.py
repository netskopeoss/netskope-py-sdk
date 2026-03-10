"""Tests for configuration and credential resolution."""

from __future__ import annotations

import dataclasses

import pytest
from pydantic import SecretStr

from netskope._config import NetskopeConfig
from netskope.exceptions import ValidationError


class TestNetskopeConfig:
    """Tests for NetskopeConfig.resolve()."""

    def test_explicit_params(self) -> None:
        config = NetskopeConfig.resolve(tenant="test.goskope.com", api_token="tok")
        assert config.tenant == "test.goskope.com"
        assert config.api_token.get_secret_value() == "tok"
        assert config.base_url == "https://test.goskope.com"

    def test_env_var_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NETSKOPE_TENANT", "env.goskope.com")
        monkeypatch.setenv("NETSKOPE_API_TOKEN", "env-token")
        config = NetskopeConfig.resolve()
        assert config.tenant == "env.goskope.com"
        assert config.api_token.get_secret_value() == "env-token"

    def test_explicit_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NETSKOPE_TENANT", "env.goskope.com")
        monkeypatch.setenv("NETSKOPE_API_TOKEN", "env-token")
        config = NetskopeConfig.resolve(tenant="explicit.goskope.com", api_token="explicit-tok")
        assert config.tenant == "explicit.goskope.com"
        assert config.api_token.get_secret_value() == "explicit-tok"

    def test_missing_tenant_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NETSKOPE_TENANT", raising=False)
        monkeypatch.delenv("NETSKOPE_API_TOKEN", raising=False)
        with pytest.raises(ValidationError, match="tenant is required"):
            NetskopeConfig.resolve(api_token="tok")

    def test_missing_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NETSKOPE_API_TOKEN", raising=False)
        with pytest.raises(ValidationError, match="API token is required"):
            NetskopeConfig.resolve(tenant="test.goskope.com")

    def test_base_url_with_https_prefix(self) -> None:
        config = NetskopeConfig(tenant="https://test.goskope.com", api_token=SecretStr("tok"))
        assert config.base_url == "https://test.goskope.com"

    def test_base_url_strips_trailing_slash(self) -> None:
        config = NetskopeConfig(tenant="test.goskope.com/", api_token=SecretStr("tok"))
        assert config.base_url == "https://test.goskope.com"

    def test_defaults(self) -> None:
        config = NetskopeConfig.resolve(tenant="t.goskope.com", api_token="tok")
        assert config.timeout == 30.0
        assert config.max_retries == 3
        assert config.backoff_factor == 0.5
        assert 429 in config.retry_on_status
        assert 500 in config.retry_on_status

    def test_custom_retry_settings(self) -> None:
        config = NetskopeConfig.resolve(
            tenant="t.goskope.com",
            api_token="tok",
            timeout=60.0,
            max_retries=5,
            backoff_factor=1.0,
            retry_on_status=frozenset({429, 503}),
        )
        assert config.timeout == 60.0
        assert config.max_retries == 5
        assert config.retry_on_status == frozenset({429, 503})

    def test_rejects_unrecognized_domain(self) -> None:
        with pytest.raises(ValidationError, match="not a recognized Netskope domain"):
            NetskopeConfig.resolve(tenant="evil.example.com", api_token="tok")

    def test_rejects_private_ip(self) -> None:
        with pytest.raises(ValidationError, match="private/link-local IP"):
            NetskopeConfig.resolve(tenant="169.254.169.254", api_token="tok")

    def test_rejects_public_ip(self) -> None:
        with pytest.raises(ValidationError, match="not an IP address"):
            NetskopeConfig.resolve(tenant="8.8.8.8", api_token="tok")

    def test_rejects_loopback_ip(self) -> None:
        with pytest.raises(ValidationError, match="private/link-local IP"):
            NetskopeConfig.resolve(tenant="127.0.0.1", api_token="tok")

    def test_allows_custom_tenant_escape_hatch(self) -> None:
        config = NetskopeConfig.resolve(
            tenant="custom.internal.corp",
            api_token="tok",
            allow_custom_tenant=True,
        )
        assert config.tenant == "custom.internal.corp"

    def test_accepts_goskope_domain(self) -> None:
        config = NetskopeConfig.resolve(tenant="myco.goskope.com", api_token="tok")
        assert config.tenant == "myco.goskope.com"

    def test_accepts_netskope_domain(self) -> None:
        config = NetskopeConfig.resolve(tenant="myco.netskope.com", api_token="tok")
        assert config.tenant == "myco.netskope.com"

    def test_accepts_boomskope_domain(self) -> None:
        config = NetskopeConfig.resolve(tenant="myco.boomskope.com", api_token="tok")
        assert config.tenant == "myco.boomskope.com"

    def test_token_type_is_secret_str(self) -> None:
        config = NetskopeConfig.resolve(tenant="t.goskope.com", api_token="secret-tok")
        assert isinstance(config.api_token, SecretStr)
        assert "secret-tok" not in str(config.api_token)
        assert config.api_token.get_secret_value() == "secret-tok"

    def test_token_not_leaked_by_asdict(self) -> None:
        config = NetskopeConfig.resolve(tenant="t.goskope.com", api_token="secret-tok")
        d = dataclasses.asdict(config)
        assert "secret-tok" not in str(d)
        assert "secret-tok" not in repr(d)

    def test_token_not_leaked_by_repr(self) -> None:
        config = NetskopeConfig.resolve(tenant="t.goskope.com", api_token="secret-tok")
        assert "secret-tok" not in repr(config)

    def test_frozen(self) -> None:
        config = NetskopeConfig(tenant="t", api_token=SecretStr("tok"))
        with pytest.raises(AttributeError):
            config.tenant = "new"  # type: ignore[misc]
