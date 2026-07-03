"""Tests for configuration and credential resolution."""

from __future__ import annotations

import dataclasses
import itertools
from pathlib import Path

import pytest
from pydantic import SecretStr

from netskope._config import NetskopeConfig, find_netskope_ca_cert
from netskope.exceptions import ValidationError

_CA_BUNDLE_ENV_VARS = (
    "NETSKOPE_CA_BUNDLE",
    "REQUESTS_CA_BUNDLE",
    "SSL_CERT_FILE",
    "CURL_CA_BUNDLE",
)


@pytest.fixture
def no_ca_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear all CA-bundle environment variables."""
    for var in _CA_BUNDLE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


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


@pytest.mark.usefixtures("no_ca_env")
class TestVerifyResolution:
    """Tests for SSL verify / CA-bundle resolution in NetskopeConfig.resolve()."""

    @staticmethod
    def _make_cert(tmp_path: Path, name: str) -> str:
        cert = tmp_path / name
        cert.write_text("dummy cert\n")
        return str(cert)

    def test_default_is_true(self) -> None:
        config = NetskopeConfig.resolve(tenant="t.goskope.com", api_token="tok")
        assert config.verify is True

    def test_explicit_false(self) -> None:
        config = NetskopeConfig.resolve(tenant="t.goskope.com", api_token="tok", verify=False)
        assert config.verify is False

    def test_explicit_path(self, tmp_path: Path) -> None:
        cert = self._make_cert(tmp_path, "explicit.pem")
        config = NetskopeConfig.resolve(tenant="t.goskope.com", api_token="tok", verify=cert)
        assert config.verify == cert

    def test_explicit_path_beats_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        explicit = self._make_cert(tmp_path, "explicit.pem")
        env_cert = self._make_cert(tmp_path, "env.pem")
        monkeypatch.setenv("NETSKOPE_CA_BUNDLE", env_cert)
        config = NetskopeConfig.resolve(tenant="t.goskope.com", api_token="tok", verify=explicit)
        assert config.verify == explicit

    def test_explicit_false_beats_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("NETSKOPE_CA_BUNDLE", self._make_cert(tmp_path, "env.pem"))
        config = NetskopeConfig.resolve(tenant="t.goskope.com", api_token="tok", verify=False)
        assert config.verify is False

    def test_env_netskope_ca_bundle(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        cert = self._make_cert(tmp_path, "ns.pem")
        monkeypatch.setenv("NETSKOPE_CA_BUNDLE", cert)
        config = NetskopeConfig.resolve(tenant="t.goskope.com", api_token="tok")
        assert config.verify == cert

    def test_env_chain_precedence(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        certs = {
            var: self._make_cert(tmp_path, f"{var.lower()}.pem") for var in _CA_BUNDLE_ENV_VARS
        }
        for var, path in certs.items():
            monkeypatch.setenv(var, path)
        # NETSKOPE_CA_BUNDLE beats all others.
        config = NetskopeConfig.resolve(tenant="t.goskope.com", api_token="tok")
        assert config.verify == certs["NETSKOPE_CA_BUNDLE"]
        # Then REQUESTS_CA_BUNDLE, SSL_CERT_FILE, CURL_CA_BUNDLE in order.
        for var, next_var in itertools.pairwise(_CA_BUNDLE_ENV_VARS):
            monkeypatch.delenv(var)
            config = NetskopeConfig.resolve(tenant="t.goskope.com", api_token="tok")
            assert config.verify == certs[next_var]

    def test_empty_env_value_skipped(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        cert = self._make_cert(tmp_path, "requests.pem")
        monkeypatch.setenv("NETSKOPE_CA_BUNDLE", "")
        monkeypatch.setenv("REQUESTS_CA_BUNDLE", cert)
        config = NetskopeConfig.resolve(tenant="t.goskope.com", api_token="tok")
        assert config.verify == cert

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        missing = str(tmp_path / "nope.pem")
        with pytest.raises(ValidationError, match="CA bundle file not found"):
            NetskopeConfig.resolve(tenant="t.goskope.com", api_token="tok", verify=missing)

    def test_missing_file_error_mentions_helper(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match="find_netskope_ca_cert"):
            NetskopeConfig.resolve(
                tenant="t.goskope.com", api_token="tok", verify=str(tmp_path / "nope.pem")
            )

    def test_missing_env_file_raises(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("NETSKOPE_CA_BUNDLE", str(tmp_path / "nope.pem"))
        with pytest.raises(ValidationError, match="CA bundle file not found"):
            NetskopeConfig.resolve(tenant="t.goskope.com", api_token="tok")


class TestFindNetskopeCaCert:
    """Tests for find_netskope_ca_cert()."""

    def test_returns_none_when_no_paths_exist(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("netskope._config.os.path.isfile", lambda _path: False)
        assert find_netskope_ca_cert() is None

    def test_returns_first_existing_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        target = "/opt/netskope/stagent/nsca/nscacert.pem"
        monkeypatch.setattr("netskope._config.os.path.isfile", lambda path: path == target)
        assert find_netskope_ca_cert() == target
