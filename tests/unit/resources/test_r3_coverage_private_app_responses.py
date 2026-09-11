"""R3S-C7: the private-app typed accessors that no test executed.

Twelve methods on ``PrivateAppResponses`` / ``AsyncPrivateAppResponses`` shipped
without ever running under ``tests/unit``.  Each test here captures the outbound
request and decodes a plausible response, so the request shape and the decoder
are both exercised at least once.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.private_apps import (
    PrivateApp,
    PrivateAppDiscoverySettings,
    PrivateAppMutationResult,
    PrivateAppPolicyUsage,
)
from tests.unit.resources.conftest import sent_json

_BASE = "https://t.goskope.com"
_APPS_URL = f"{_BASE}/api/v2/steering/apps/private"
_PUBLISHERS_URL = f"{_APPS_URL}/publishers"
_DISCOVERY_URL = f"{_APPS_URL}/discoverysettings"
_POLICY_IN_USE_URL = f"{_APPS_URL}/getpolicyinuse"

_APP = {
    "app_id": 42,
    "app_name": "internal-dashboard",
    "host": "10.0.0.5",
    "port": "443",
    "clientless_access": True,
}

_ACK = {"status": "success", "message": "2 private apps deleted"}
_DISCOVERY = {
    "data": {
        "id": 3,
        "settings": {"enabled": True},
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
    }
}


class TestPrivateAppResponsesSync:
    """client.private_apps.with_response — the methods C7 listed."""

    @respx.mock
    def test_bulk_delete_sends_string_ids_and_decodes_the_acknowledgment(
        self, client: NetskopeClient
    ) -> None:
        route = respx.delete(_APPS_URL).mock(return_value=httpx.Response(200, json=_ACK))
        response = client.private_apps.with_response.bulk_delete([123, 456])
        assert sent_json(route) == {"private_app_ids": ["123", "456"]}
        result = response.parse()
        assert isinstance(result, PrivateAppMutationResult)
        assert result.status == "success"

    @respx.mock
    def test_bulk_delete_decodes_an_empty_body_as_none(self, client: NetskopeClient) -> None:
        respx.delete(_APPS_URL).mock(return_value=httpx.Response(204))
        assert client.private_apps.with_response.bulk_delete([1]).parse() is None

    def test_bulk_delete_rejects_an_unusable_id_before_the_request(
        self, client: NetskopeClient
    ) -> None:
        with respx.mock:
            route = respx.route(host="t.goskope.com")
            with pytest.raises(ValidationError):
                client.private_apps.with_response.bulk_delete(["../1"])
            assert not route.called

    @respx.mock
    def test_remove_publishers_deletes_the_association(self, client: NetskopeClient) -> None:
        route = respx.delete(_PUBLISHERS_URL).mock(return_value=httpx.Response(200, json=_ACK))
        result = client.private_apps.with_response.remove_publishers([42], [7, 8]).parse()
        assert sent_json(route) == {
            "private_app_ids": ["42"],
            "publisher_ids": ["7", "8"],
        }
        assert result is not None
        assert result.message == "2 private apps deleted"

    @respx.mock
    def test_remove_publishers_decodes_an_empty_body_as_none(self, client: NetskopeClient) -> None:
        respx.delete(_PUBLISHERS_URL).mock(return_value=httpx.Response(204))
        assert client.private_apps.with_response.remove_publishers([42], [7]).parse() is None

    @respx.mock
    def test_get(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_APPS_URL}/42").mock(
            return_value=httpx.Response(200, json={"data": _APP})
        )
        app = client.private_apps.with_response.get(42).parse()
        assert route.calls.last.request.method == "GET"
        assert isinstance(app, PrivateApp)
        assert app.app_name == "internal-dashboard"

    @respx.mock
    def test_get_policy_in_use_posts_string_ids(self, client: NetskopeClient) -> None:
        route = respx.post(_POLICY_IN_USE_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": [{"app_id": "42", "num_in_use": 1, "policies": ["p1"]}],
                },
            )
        )
        usage = client.private_apps.with_response.get_policy_in_use([42]).parse()
        assert sent_json(route) == {"ids": ["42"]}
        assert isinstance(usage, PrivateAppPolicyUsage)
        assert isinstance(usage.data, list)
        assert usage.data[0].policies == ["p1"]

    @respx.mock
    def test_get_discovery_settings(self, client: NetskopeClient) -> None:
        route = respx.get(_DISCOVERY_URL).mock(return_value=httpx.Response(200, json=_DISCOVERY))
        settings = client.private_apps.with_response.get_discovery_settings().parse()
        assert route.call_count == 1
        assert isinstance(settings, PrivateAppDiscoverySettings)
        assert settings.id == 3

    @respx.mock
    def test_replace_publishers_uses_put(self, client: NetskopeClient) -> None:
        route = respx.put(_PUBLISHERS_URL).mock(
            return_value=httpx.Response(200, json={"data": {"private_apps": [_APP]}})
        )
        apps = client.private_apps.with_response.replace_publishers([42], [7]).parse()
        assert route.calls.last.request.method == "PUT"
        assert sent_json(route) == {"private_app_ids": ["42"], "publisher_ids": ["7"]}
        assert [app.app_id for app in apps] == [42]


class TestPrivateAppResponsesAsync:
    """The async mirrors of the same twelve methods."""

    @respx.mock
    async def test_bulk_delete(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(_APPS_URL).mock(return_value=httpx.Response(200, json=_ACK))
        response = await aclient.private_apps.with_response.bulk_delete([123])
        assert sent_json(route) == {"private_app_ids": ["123"]}
        assert response.parse().status == "success"

    @respx.mock
    async def test_bulk_delete_decodes_an_empty_body_as_none(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        respx.delete(_APPS_URL).mock(return_value=httpx.Response(204))
        response = await aclient.private_apps.with_response.bulk_delete([1])
        assert response.parse() is None

    @respx.mock
    async def test_remove_publishers(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(_PUBLISHERS_URL).mock(return_value=httpx.Response(200, json=_ACK))
        response = await aclient.private_apps.with_response.remove_publishers([42], [7, 8])
        assert sent_json(route) == {"private_app_ids": ["42"], "publisher_ids": ["7", "8"]}
        assert response.parse().status == "success"

    @respx.mock
    async def test_remove_publishers_decodes_an_empty_body_as_none(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        respx.delete(_PUBLISHERS_URL).mock(return_value=httpx.Response(204))
        response = await aclient.private_apps.with_response.remove_publishers([42], [7])
        assert response.parse() is None

    @respx.mock
    async def test_get(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_APPS_URL}/42").mock(return_value=httpx.Response(200, json={"data": _APP}))
        response = await aclient.private_apps.with_response.get(42)
        assert response.parse().host == "10.0.0.5"

    @respx.mock
    async def test_get_policy_in_use(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_POLICY_IN_USE_URL).mock(
            return_value=httpx.Response(200, json={"status": "success", "data": {"42": ["p1"]}})
        )
        response = await aclient.private_apps.with_response.get_policy_in_use([42])
        assert sent_json(route) == {"ids": ["42"]}
        assert response.parse().data == {"42": ["p1"]}

    @respx.mock
    async def test_get_discovery_settings(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_DISCOVERY_URL).mock(return_value=httpx.Response(200, json=_DISCOVERY))
        response = await aclient.private_apps.with_response.get_discovery_settings()
        settings = response.parse()
        assert settings.settings is not None
        assert settings.updated_at == "2026-01-02T00:00:00Z"

    @respx.mock
    async def test_replace_publishers(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.put(_PUBLISHERS_URL).mock(
            return_value=httpx.Response(200, json={"data": {"private_apps": [_APP]}})
        )
        response = await aclient.private_apps.with_response.replace_publishers([42], [7])
        assert route.calls.last.request.method == "PUT"
        assert [app.app_id for app in response.parse()] == [42]
