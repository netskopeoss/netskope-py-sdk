"""Tests for the HTTP transport and retry logic."""

from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import SecretStr

from netskope._config import NetskopeConfig
from netskope._transport import SyncTransport
from netskope.exceptions import (
    AuthenticationError,
    NotFoundError,
    ServerError,
)


@pytest.fixture
def transport_config() -> NetskopeConfig:
    return NetskopeConfig(
        tenant="test.goskope.com",
        api_token=SecretStr("test-token"),
        timeout=5.0,
        max_retries=2,
        backoff_factor=0.01,
    )


class TestSyncTransport:
    """Tests for SyncTransport request handling."""

    @respx.mock
    def test_successful_get(self, transport_config: NetskopeConfig) -> None:
        respx.get("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(200, json={"data": "ok"})
        )
        transport = SyncTransport(transport_config)
        resp = transport.request("GET", "/api/v2/test")
        assert resp.status_code == 200
        assert resp.json()["data"] == "ok"
        transport.close()

    @respx.mock
    def test_auth_header_sent(self, transport_config: NetskopeConfig) -> None:
        route = respx.get("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(200, json={})
        )
        transport = SyncTransport(transport_config)
        transport.request("GET", "/api/v2/test")
        assert route.calls[0].request.headers["netskope-api-token"] == "test-token"
        transport.close()

    @respx.mock
    def test_user_agent_header(self, transport_config: NetskopeConfig) -> None:
        route = respx.get("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(200, json={})
        )
        transport = SyncTransport(transport_config)
        transport.request("GET", "/api/v2/test")
        ua = route.calls[0].request.headers["user-agent"]
        assert "netskope-python-sdk" in ua
        transport.close()

    @respx.mock
    def test_401_raises_authentication_error(self, transport_config: NetskopeConfig) -> None:
        respx.get("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(401, json={"message": "Unauthorized"})
        )
        transport = SyncTransport(transport_config)
        with pytest.raises(AuthenticationError):
            transport.request("GET", "/api/v2/test")
        transport.close()

    @respx.mock
    def test_404_raises_not_found(self, transport_config: NetskopeConfig) -> None:
        respx.get("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(404, json={"message": "Not found"})
        )
        transport = SyncTransport(transport_config)
        with pytest.raises(NotFoundError):
            transport.request("GET", "/api/v2/test")
        transport.close()

    @respx.mock
    def test_retry_on_500(self, transport_config: NetskopeConfig) -> None:
        route = respx.get("https://test.goskope.com/api/v2/test")
        route.side_effect = [
            httpx.Response(500, json={"message": "Internal error"}),
            httpx.Response(500, json={"message": "Internal error"}),
            httpx.Response(200, json={"data": "ok"}),
        ]
        transport = SyncTransport(transport_config)
        resp = transport.request("GET", "/api/v2/test")
        assert resp.status_code == 200
        assert route.call_count == 3
        transport.close()

    @respx.mock
    def test_retry_exhausted_raises(self, transport_config: NetskopeConfig) -> None:
        respx.get("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(500, json={"message": "Error"})
        )
        transport = SyncTransport(transport_config)
        with pytest.raises(ServerError):
            transport.request("GET", "/api/v2/test")
        transport.close()

    @respx.mock
    def test_retry_on_429(self, transport_config: NetskopeConfig) -> None:
        route = respx.get("https://test.goskope.com/api/v2/test")
        route.side_effect = [
            httpx.Response(429, json={"message": "Rate limit"}, headers={"retry-after": "0"}),
            httpx.Response(200, json={"data": "ok"}),
        ]
        transport = SyncTransport(transport_config)
        resp = transport.request("GET", "/api/v2/test")
        assert resp.status_code == 200
        transport.close()

    @respx.mock
    def test_post_with_json(self, transport_config: NetskopeConfig) -> None:
        respx.post("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(200, json={"created": True})
        )
        transport = SyncTransport(transport_config)
        resp = transport.request("POST", "/api/v2/test", json={"name": "test"})
        assert resp.json()["created"] is True
        transport.close()

    @respx.mock
    def test_params_forwarded(self, transport_config: NetskopeConfig) -> None:
        route = respx.get("https://test.goskope.com/api/v2/test").mock(
            return_value=httpx.Response(200, json={})
        )
        transport = SyncTransport(transport_config)
        transport.request("GET", "/api/v2/test", params={"limit": 10, "offset": 0})
        assert "limit=10" in str(route.calls[0].request.url)
        transport.close()
