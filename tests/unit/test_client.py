"""Tests for the NetskopeClient entry points."""

from __future__ import annotations

import json

import httpx
import pytest

from netskope import AsyncNetskopeClient, NetskopeClient, __version__
from netskope.exceptions import ClientClosedError, ValidationError
from netskope.resources.alerts.resource import AlertsResource
from netskope.resources.events.resource import EventsResource
from netskope.resources.incidents.resource import IncidentsResource
from netskope.resources.private_apps.resource import PrivateAppsResource
from netskope.resources.publishers.resource import PublishersResource
from netskope.resources.scim.resource import ScimResource
from netskope.resources.steering.resource import SteeringResource
from netskope.resources.url_lists.resource import UrlListsResource


class TestNetskopeClient:
    """Tests for the synchronous client."""

    def test_creation(self) -> None:
        client = NetskopeClient(tenant="t.goskope.com", api_token="tok")
        assert client.tenant == "t.goskope.com"
        assert client.base_url == "https://t.goskope.com"
        assert client.version == __version__
        client.close()

    def test_resource_namespaces(self) -> None:
        client = NetskopeClient(tenant="t.goskope.com", api_token="tok")
        assert isinstance(client.alerts, AlertsResource)
        assert isinstance(client.events, EventsResource)
        assert isinstance(client.url_lists, UrlListsResource)
        assert isinstance(client.publishers, PublishersResource)
        assert isinstance(client.private_apps, PrivateAppsResource)
        assert isinstance(client.scim, ScimResource)
        assert isinstance(client.incidents, IncidentsResource)
        assert isinstance(client.steering, SteeringResource)
        client.close()

    def test_context_manager(self) -> None:
        with NetskopeClient(tenant="t.goskope.com", api_token="tok") as client:
            assert client.tenant == "t.goskope.com"
            assert not client.closed
        assert client.closed

    def test_public_request_with_borrowed_client(self) -> None:
        requests: list[httpx.Request] = []

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={"new_endpoint": True})

        with httpx.Client(transport=httpx.MockTransport(respond)) as http_client:
            with NetskopeClient(
                tenant="t.goskope.com", ci_session="cookie", http_client=http_client
            ) as client:
                response = client.request("POST", "/api/v2/new", json={"enabled": False})
                assert response.json() == {"new_endpoint": True}
            assert not http_client.is_closed
            client.close()
            assert client.closed
            with pytest.raises(ClientClosedError, match="closed"):
                client.request("GET", "/api/v2/new")

        assert requests[0].url == "https://t.goskope.com/api/v2/new"
        assert requests[0].headers["cookie"] == "ci_session=cookie"
        assert "netskope-api-token" not in requests[0].headers
        assert json.loads(requests[0].content) == {"enabled": False}

    def test_repr(self) -> None:
        client = NetskopeClient(tenant="t.goskope.com", api_token="tok")
        assert "t.goskope.com" in repr(client)
        client.close()

    def test_missing_credentials_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NETSKOPE_TENANT", raising=False)
        monkeypatch.delenv("NETSKOPE_API_TOKEN", raising=False)
        with pytest.raises(ValidationError):
            NetskopeClient()

    def test_verify_false_reflected_in_config(self) -> None:
        client = NetskopeClient(tenant="t.goskope.com", api_token="tok", verify=False)
        assert client._config.verify is False
        client.close()

    def test_allow_custom_tenant_reaches_the_config(self) -> None:
        client = NetskopeClient(
            tenant="netskope.internal.example", api_token="tok", allow_custom_tenant=True
        )
        assert client.tenant == "netskope.internal.example"
        assert client.base_url == "https://netskope.internal.example"
        client.close()

    def test_custom_tenant_is_rejected_without_the_opt_in(self) -> None:
        with pytest.raises(ValidationError, match="allow_custom_tenant"):
            NetskopeClient(tenant="netskope.internal.example", api_token="tok")

    def test_verify_defaults_to_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in ("NETSKOPE_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE", "CURL_CA_BUNDLE"):
            monkeypatch.delenv(var, raising=False)
        client = NetskopeClient(tenant="t.goskope.com", api_token="tok")
        assert client._config.verify is True
        client.close()


class TestAsyncNetskopeClient:
    """Tests for the async client."""

    def test_creation(self) -> None:
        client = AsyncNetskopeClient(tenant="t.goskope.com", api_token="tok")
        assert client.tenant == "t.goskope.com"
        assert client.version == __version__

    def test_repr(self) -> None:
        client = AsyncNetskopeClient(tenant="t.goskope.com", api_token="tok")
        assert "AsyncNetskopeClient" in repr(client)

    def test_verify_false_reflected_in_config(self) -> None:
        client = AsyncNetskopeClient(tenant="t.goskope.com", api_token="tok", verify=False)
        assert client._config.verify is False

    def test_allow_custom_tenant_reaches_the_config(self) -> None:
        client = AsyncNetskopeClient(
            tenant="netskope.internal.example", api_token="tok", allow_custom_tenant=True
        )
        assert client.tenant == "netskope.internal.example"

    def test_custom_tenant_is_rejected_without_the_opt_in(self) -> None:
        with pytest.raises(ValidationError, match="allow_custom_tenant"):
            AsyncNetskopeClient(tenant="netskope.internal.example", api_token="tok")

    async def test_context_manager_closes_owned_client(self) -> None:
        async with AsyncNetskopeClient(tenant="t.goskope.com", api_token="tok") as client:
            assert not client.closed
        assert client.closed

    async def test_public_request_with_borrowed_client(self) -> None:
        requests: list[httpx.Request] = []

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={"new_endpoint": True})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
            async with AsyncNetskopeClient(
                tenant="t.goskope.com", ci_session="cookie", http_client=http_client
            ) as client:
                response = await client.request("GET", "/api/v2/new", params={"limit": 3})
                assert response.json() == {"new_endpoint": True}
            assert not http_client.is_closed
            await client.close()
            assert client.closed
            with pytest.raises(ClientClosedError, match="closed"):
                await client.request("GET", "/api/v2/new")

        assert requests[0].url == "https://t.goskope.com/api/v2/new?limit=3"
        assert requests[0].headers["cookie"] == "ci_session=cookie"
        assert "netskope-api-token" not in requests[0].headers
