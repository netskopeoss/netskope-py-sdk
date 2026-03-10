"""Tests for the NetskopeClient entry points."""

from __future__ import annotations

import pytest

from netskope import AsyncNetskopeClient, NetskopeClient, __version__
from netskope.exceptions import ValidationError
from netskope.resources.alerts import AlertsResource
from netskope.resources.events import EventsResource
from netskope.resources.incidents import IncidentsResource
from netskope.resources.private_apps import PrivateAppsResource
from netskope.resources.publishers import PublishersResource
from netskope.resources.scim import ScimResource
from netskope.resources.steering import SteeringResource
from netskope.resources.url_lists import UrlListsResource


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

    def test_repr(self) -> None:
        client = NetskopeClient(tenant="t.goskope.com", api_token="tok")
        assert "t.goskope.com" in repr(client)
        client.close()

    def test_missing_credentials_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NETSKOPE_TENANT", raising=False)
        monkeypatch.delenv("NETSKOPE_API_TOKEN", raising=False)
        with pytest.raises(ValidationError):
            NetskopeClient()


class TestAsyncNetskopeClient:
    """Tests for the async client."""

    def test_creation(self) -> None:
        client = AsyncNetskopeClient(tenant="t.goskope.com", api_token="tok")
        assert client.tenant == "t.goskope.com"
        assert client.version == __version__

    def test_repr(self) -> None:
        client = AsyncNetskopeClient(tenant="t.goskope.com", api_token="tok")
        assert "AsyncNetskopeClient" in repr(client)
