"""Tests for client.publishers with mocked HTTP."""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import NetskopeError, ValidationError
from netskope.models.publishers import (
    Publisher,
    PublisherAlertsConfiguration,
    PublisherRelease,
)
from tests.unit.resources.conftest import drain, sent_json

_URL = "https://t.goskope.com/api/v2/infrastructure/publishers"
_RELEASES_URL = f"{_URL}/releases"
_BULK_URL = f"{_URL}/bulk"
_ALERTS_CONFIG_URL = f"{_URL}/alertsconfiguration"

_LIST_BODY = {
    "data": {
        "publishers": [
            {"publisher_id": 1, "publisher_name": "Pub1", "status": "connected"},
        ]
    },
    "status": {"total": 1},
}

_RELEASES_BODY = {
    "data": {
        "releases": [
            {
                "version": "1.2.3",
                "docker_tag": "release-1.2.3",
                "release_type": "GA",
                "is_recommended": True,
            },
            {
                "version": "1.3.0",
                "docker_tag": "release-1.3.0",
                "release_type": "Beta",
                "is_recommended": False,
            },
        ]
    }
}

_APPS_BODY = {
    "data": {
        "apps": [
            {"app_name": "wiki", "app_id": 7, "host": "wiki.internal", "protocol": "tcp"},
        ]
    }
}

_ALERTS_CONFIG_BODY = {
    "data": {
        "adminUsers": ["admin@example.com"],
        "eventTypes": ["UPGRADE_FAILED", "CONNECTION_FAILED"],
    }
}


class TestPublishersResource:
    """Tests for client.publishers (sync)."""

    @respx.mock
    def test_list(self, client: NetskopeClient) -> None:
        respx.get(_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        pubs = list(client.publishers.list())
        assert len(pubs) == 1
        assert isinstance(pubs[0], Publisher)
        assert pubs[0].publisher_name == "Pub1"

    @respx.mock
    def test_list_sends_filter_and_fields(self, client: NetskopeClient) -> None:
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        list(
            client.publishers.list(
                filter_expr="status eq 'connected'",
                fields=["publisher_id", "publisher_name"],
            )
        )
        params = route.calls.last.request.url.params
        assert params["filter"] == "status eq 'connected'"
        assert params["fields"] == "publisher_id,publisher_name"

    @respx.mock
    def test_get(self, client: NetskopeClient) -> None:
        respx.get(f"{_URL}/42").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"publisher_id": 42, "publisher_name": "Pub42"}},
            )
        )
        pub = client.publishers.get(42)
        assert pub.publisher_id == 42
        assert pub.publisher_name == "Pub42"

    @respx.mock
    def test_create_sends_name_not_publisher_name(self, client: NetskopeClient) -> None:
        """create() must send {"name": ...} — the API rejects publisher_name on write."""
        route = respx.post(_URL).mock(
            return_value=httpx.Response(
                200,
                json={"data": {"publisher_id": 99, "publisher_name": "NewPub"}},
            )
        )
        pub = client.publishers.create(name="NewPub")
        assert pub.publisher_id == 99
        assert sent_json(route) == {"name": "NewPub", "lbroker_connect": False}

    @respx.mock
    def test_create_with_lbroker_connect(self, client: NetskopeClient) -> None:
        route = respx.post(_URL).mock(
            return_value=httpx.Response(200, json={"data": {"publisher_id": 100}})
        )
        client.publishers.create(name="DC-Primary", lbroker_connect=True)
        assert sent_json(route) == {"name": "DC-Primary", "lbroker_connect": True}

    @respx.mock
    def test_update_uses_patch_and_name_key(self, client: NetskopeClient) -> None:
        """update() must PATCH (not PUT) and send {"name": ...}."""
        route = respx.patch(f"{_URL}/42").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"publisher_id": 42, "publisher_name": "Renamed"}},
            )
        )
        pub = client.publishers.update(42, name="Renamed")
        assert pub.publisher_name == "Renamed"
        assert sent_json(route) == {"name": "Renamed"}

    @respx.mock
    def test_delete(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_URL}/42").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        client.publishers.delete(42)
        assert route.called

    @respx.mock
    def test_list_apps(self, client: NetskopeClient) -> None:
        respx.get(f"{_URL}/42/apps").mock(return_value=httpx.Response(200, json=_APPS_BODY))
        apps = client.publishers.list_apps(42)
        assert apps == _APPS_BODY["data"]["apps"]

    @respx.mock
    def test_create_registration_token(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_URL}/42/registration_token").mock(
            return_value=httpx.Response(200, json={"data": {"token": "abc123"}})
        )
        token = client.publishers.create_registration_token(42)
        assert token == "abc123"
        assert route.called

    @respx.mock
    def test_create_registration_token_top_level_fallback(self, client: NetskopeClient) -> None:
        respx.post(f"{_URL}/42/registration_token").mock(
            return_value=httpx.Response(200, json={"token": 987654})
        )
        assert client.publishers.create_registration_token(42) == "987654"

    @respx.mock
    def test_create_registration_token_missing_raises(self, client: NetskopeClient) -> None:
        respx.post(f"{_URL}/42/registration_token").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        with pytest.raises(NetskopeError, match="token"):
            client.publishers.create_registration_token(42)

    @respx.mock
    def test_list_releases(self, client: NetskopeClient) -> None:
        route = respx.get(_RELEASES_URL).mock(return_value=httpx.Response(200, json=_RELEASES_BODY))
        releases = client.publishers.list_releases()
        assert route.called
        assert len(releases) == 2
        assert isinstance(releases[0], PublisherRelease)
        assert releases[0].version == "1.2.3"
        assert releases[0].docker_tag == "release-1.2.3"
        assert releases[0].release_type == "GA"
        assert releases[0].is_recommended is True
        assert releases[1].is_recommended is False

    @respx.mock
    def test_bulk_upgrade_body_shape(self, client: NetskopeClient) -> None:
        route = respx.put(_BULK_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        result = client.publishers.bulk_upgrade([1, 2, 3])
        assert result == {"status": "success"}
        assert sent_json(route) == {
            "publishers": {
                "apply": {"upgrade_request": True},
                "id": [1, 2, 3],
            }
        }

    @respx.mock
    def test_get_alerts_configuration(self, client: NetskopeClient) -> None:
        respx.get(_ALERTS_CONFIG_URL).mock(
            return_value=httpx.Response(200, json=_ALERTS_CONFIG_BODY)
        )
        config = client.publishers.get_alerts_configuration()
        assert isinstance(config, PublisherAlertsConfiguration)
        assert config.admin_users == ["admin@example.com"]
        assert config.event_types == ["UPGRADE_FAILED", "CONNECTION_FAILED"]

    @respx.mock
    def test_update_alerts_configuration_sends_camelcase(self, client: NetskopeClient) -> None:
        route = respx.put(_ALERTS_CONFIG_URL).mock(
            return_value=httpx.Response(200, json=_ALERTS_CONFIG_BODY)
        )
        config = client.publishers.update_alerts_configuration(
            admin_users=["admin@example.com"],
            event_types=["UPGRADE_FAILED", "CONNECTION_FAILED"],
        )
        assert config.admin_users == ["admin@example.com"]
        assert sent_json(route) == {
            "adminUsers": ["admin@example.com"],
            "eventTypes": ["UPGRADE_FAILED", "CONNECTION_FAILED"],
        }

    @respx.mock
    def test_update_alerts_configuration_invalid_event_type_no_http(
        self, client: NetskopeClient
    ) -> None:
        with pytest.raises(ValidationError, match="UPGRADE_EXPLODED"):
            client.publishers.update_alerts_configuration(event_types=["UPGRADE_EXPLODED"])
        assert len(respx.calls) == 0


class TestAsyncPublishersResource:
    """Tests for aclient.publishers (async)."""

    @respx.mock
    async def test_list(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        pubs = await drain(aclient.publishers.list())
        assert len(pubs) == 1
        assert isinstance(pubs[0], Publisher)
        assert pubs[0].publisher_name == "Pub1"

    @respx.mock
    async def test_list_sends_filter_and_fields(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        await drain(
            aclient.publishers.list(
                filter_expr="status eq 'connected'",
                fields=["publisher_id", "publisher_name"],
            )
        )
        params = route.calls.last.request.url.params
        assert params["filter"] == "status eq 'connected'"
        assert params["fields"] == "publisher_id,publisher_name"

    @respx.mock
    async def test_get(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_URL}/42").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"publisher_id": 42, "publisher_name": "Pub42"}},
            )
        )
        pub = await aclient.publishers.get(42)
        assert pub.publisher_id == 42

    @respx.mock
    async def test_create_sends_name_not_publisher_name(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_URL).mock(
            return_value=httpx.Response(200, json={"data": {"publisher_id": 99}})
        )
        pub = await aclient.publishers.create(name="NewPub", lbroker_connect=True)
        assert pub.publisher_id == 99
        assert sent_json(route) == {"name": "NewPub", "lbroker_connect": True}

    @respx.mock
    async def test_update_uses_patch_and_name_key(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.patch(f"{_URL}/42").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"publisher_id": 42, "publisher_name": "Renamed"}},
            )
        )
        pub = await aclient.publishers.update(42, name="Renamed")
        assert pub.publisher_name == "Renamed"
        assert sent_json(route) == {"name": "Renamed"}

    @respx.mock
    async def test_delete(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(f"{_URL}/42").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        await aclient.publishers.delete(42)
        assert route.called

    @respx.mock
    async def test_list_apps(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_URL}/42/apps").mock(return_value=httpx.Response(200, json=_APPS_BODY))
        apps = await aclient.publishers.list_apps(42)
        assert apps == _APPS_BODY["data"]["apps"]

    @respx.mock
    async def test_create_registration_token(self, aclient: AsyncNetskopeClient) -> None:
        respx.post(f"{_URL}/42/registration_token").mock(
            return_value=httpx.Response(200, json={"data": {"token": "abc123"}})
        )
        assert await aclient.publishers.create_registration_token(42) == "abc123"

    @respx.mock
    async def test_create_registration_token_missing_raises(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        respx.post(f"{_URL}/42/registration_token").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        with pytest.raises(NetskopeError, match="token"):
            await aclient.publishers.create_registration_token(42)

    @respx.mock
    async def test_list_releases(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_RELEASES_URL).mock(return_value=httpx.Response(200, json=_RELEASES_BODY))
        releases = await aclient.publishers.list_releases()
        assert len(releases) == 2
        assert isinstance(releases[0], PublisherRelease)
        assert releases[0].version == "1.2.3"

    @respx.mock
    async def test_bulk_upgrade_body_shape(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.put(_BULK_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        result = await aclient.publishers.bulk_upgrade([7])
        assert result == {"status": "success"}
        assert sent_json(route) == {
            "publishers": {
                "apply": {"upgrade_request": True},
                "id": [7],
            }
        }

    @respx.mock
    async def test_get_alerts_configuration(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_ALERTS_CONFIG_URL).mock(
            return_value=httpx.Response(200, json=_ALERTS_CONFIG_BODY)
        )
        config = await aclient.publishers.get_alerts_configuration()
        assert config.admin_users == ["admin@example.com"]
        assert config.event_types == ["UPGRADE_FAILED", "CONNECTION_FAILED"]

    @respx.mock
    async def test_update_alerts_configuration_sends_camelcase(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        route = respx.put(_ALERTS_CONFIG_URL).mock(
            return_value=httpx.Response(200, json=_ALERTS_CONFIG_BODY)
        )
        await aclient.publishers.update_alerts_configuration(
            admin_users=["admin@example.com"],
            event_types=["UPGRADE_FAILED"],
        )
        assert sent_json(route) == {
            "adminUsers": ["admin@example.com"],
            "eventTypes": ["UPGRADE_FAILED"],
        }

    @respx.mock
    async def test_update_alerts_configuration_invalid_event_type_no_http(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with pytest.raises(ValidationError, match="UPGRADE_EXPLODED"):
            await aclient.publishers.update_alerts_configuration(event_types=["UPGRADE_EXPLODED"])
        assert len(respx.calls) == 0
