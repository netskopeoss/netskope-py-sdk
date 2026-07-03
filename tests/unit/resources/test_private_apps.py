"""Tests for client.private_apps with mocked HTTP."""

from __future__ import annotations

import httpx
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.models.private_apps import PrivateApp, PrivateAppTag
from tests.unit.resources.conftest import sent_json

_BASE = "https://t.goskope.com"
_APPS_URL = f"{_BASE}/api/v2/steering/apps/private"
_TAGS_URL = f"{_APPS_URL}/tags"
_PUBLISHERS_URL = f"{_APPS_URL}/publishers"
_DISCOVERY_URL = f"{_APPS_URL}/discoverysettings"

_APP = {
    "app_id": 42,
    "app_name": "internal-dashboard",
    "host": "10.0.0.5",
    "port": "443",
    "clientless_access": True,
}

_TAG = {"tag_id": 7, "tag_name": "web"}


class TestPrivateAppsResource:
    """Tests for client.private_apps (sync)."""

    @respx.mock
    def test_list_extracts_nested_private_apps(self, client: NetskopeClient) -> None:
        respx.get(_APPS_URL).mock(
            return_value=httpx.Response(
                200,
                json={"data": {"private_apps": [_APP]}, "status": {"total": 1}},
            )
        )
        apps = list(client.private_apps.list())
        assert len(apps) == 1
        assert isinstance(apps[0], PrivateApp)
        assert apps[0].app_name == "internal-dashboard"

    @respx.mock
    def test_list_sends_cli_filter_params(self, client: NetskopeClient) -> None:
        route = respx.get(_APPS_URL).mock(
            return_value=httpx.Response(200, json={"data": [], "status": {"total": 0}})
        )
        list(
            client.private_apps.list(
                query="dash",
                app_name="internal-dashboard",
                publisher_name="pub-1",
                reachable=True,
                clientless_access=False,
                host="10.0.0.5",
                in_policy=True,
                protocol="tcp",
            )
        )
        params = route.calls.last.request.url.params
        assert params["query"] == "dash"
        assert params["app_name"] == "internal-dashboard"
        assert params["publisher_name"] == "pub-1"
        assert params["reachable"] == "true"
        assert params["clientless_access"] == "false"
        assert params["host"] == "10.0.0.5"
        assert params["in_policy"] == "true"
        assert params["protocol"] == "tcp"

    @respx.mock
    def test_list_omits_unset_params(self, client: NetskopeClient) -> None:
        route = respx.get(_APPS_URL).mock(
            return_value=httpx.Response(200, json={"data": [], "status": {"total": 0}})
        )
        list(client.private_apps.list())
        params = route.calls.last.request.url.params
        assert set(params) == {"limit", "offset"}

    @respx.mock
    def test_get(self, client: NetskopeClient) -> None:
        respx.get(f"{_APPS_URL}/42").mock(return_value=httpx.Response(200, json={"data": _APP}))
        app = client.private_apps.get(42)
        assert app.app_id == 42
        assert app.host == "10.0.0.5"

    @respx.mock
    def test_create_payload(self, client: NetskopeClient) -> None:
        route = respx.post(_APPS_URL).mock(return_value=httpx.Response(200, json={"data": _APP}))
        client.private_apps.create(
            "internal-dashboard",
            "10.0.0.5",
            "443",
            protocols=["TCP"],
            publisher_ids=[1, 2],
            extra_fields={"clientless_access": True},
        )
        assert sent_json(route) == {
            "app_name": "internal-dashboard",
            "host": "10.0.0.5",
            "port": "443",
            "protocols": ["TCP"],
            "publishers": [{"publisher_id": 1}, {"publisher_id": 2}],
            "clientless_access": True,
        }

    @respx.mock
    def test_update_uses_patch(self, client: NetskopeClient) -> None:
        """update() must send PATCH (partial update), not PUT."""
        route = respx.patch(f"{_APPS_URL}/42").mock(
            return_value=httpx.Response(200, json={"data": _APP})
        )
        app = client.private_apps.update(42, extra_fields={"app_name": "renamed"})
        assert route.calls.last.request.method == "PATCH"
        assert sent_json(route) == {"app_name": "renamed"}
        assert app.app_id == 42

    @respx.mock
    def test_replace_uses_put(self, client: NetskopeClient) -> None:
        route = respx.put(f"{_APPS_URL}/42").mock(
            return_value=httpx.Response(200, json={"data": _APP})
        )
        payload = {"app_name": "internal-dashboard", "host": "10.0.0.5", "port": "443"}
        app = client.private_apps.replace(42, payload)
        assert route.calls.last.request.method == "PUT"
        assert sent_json(route) == payload
        assert isinstance(app, PrivateApp)

    @respx.mock
    def test_delete(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_APPS_URL}/42").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        assert client.private_apps.delete(42) is None
        assert route.call_count == 1

    @respx.mock
    def test_bulk_delete_sends_body(self, client: NetskopeClient) -> None:
        """bulk_delete() sends DELETE on the base path with private_app_ids as ints."""
        route = respx.delete(_APPS_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        assert client.private_apps.bulk_delete([123, 456]) is None
        assert sent_json(route) == {"private_app_ids": [123, 456]}

    @respx.mock
    def test_get_policy_in_use(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_APPS_URL}/getpolicyinuse").mock(
            return_value=httpx.Response(200, json={"data": {"123": ["policy-1"]}})
        )
        body = client.private_apps.get_policy_in_use([123, 456])
        assert sent_json(route) == {"ids": [123, 456]}
        assert body["data"] == {"123": ["policy-1"]}

    @respx.mock
    def test_get_discovery_settings(self, client: NetskopeClient) -> None:
        route = respx.get(_DISCOVERY_URL).mock(
            return_value=httpx.Response(200, json={"data": {"enabled": True}})
        )
        body = client.private_apps.get_discovery_settings()
        assert route.call_count == 1
        assert body["data"]["enabled"] is True

    @respx.mock
    def test_update_discovery_settings_uses_post(self, client: NetskopeClient) -> None:
        """Discovery settings updates go through POST, not PUT."""
        route = respx.post(_DISCOVERY_URL).mock(
            return_value=httpx.Response(200, json={"data": {"enabled": False}})
        )
        settings = {"enabled": False, "networks": []}
        body = client.private_apps.update_discovery_settings(settings)
        assert route.calls.last.request.method == "POST"
        assert sent_json(route) == settings
        assert body["data"]["enabled"] is False

    @respx.mock
    def test_add_publishers_patch_body(self, client: NetskopeClient) -> None:
        route = respx.patch(_PUBLISHERS_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        client.private_apps.add_publishers([123, 456], [10, 20])
        assert sent_json(route) == {"private_app_ids": [123, 456], "publisher_ids": [10, 20]}

    @respx.mock
    def test_replace_publishers_put_body(self, client: NetskopeClient) -> None:
        route = respx.put(_PUBLISHERS_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        client.private_apps.replace_publishers([123], [30, 40])
        assert sent_json(route) == {"private_app_ids": [123], "publisher_ids": [30, 40]}

    @respx.mock
    def test_remove_publishers_delete_with_body(self, client: NetskopeClient) -> None:
        route = respx.delete(_PUBLISHERS_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        assert client.private_apps.remove_publishers([123], [10]) is None
        assert sent_json(route) == {"private_app_ids": [123], "publisher_ids": [10]}


class TestPrivateAppTagsResource:
    """Tests for client.private_apps.tags (sync)."""

    @respx.mock
    def test_list_returns_tags(self, client: NetskopeClient) -> None:
        respx.get(_TAGS_URL).mock(
            return_value=httpx.Response(200, json={"data": [_TAG], "status": {"total": 1}})
        )
        tags = list(client.private_apps.tags.list())
        assert len(tags) == 1
        assert isinstance(tags[0], PrivateAppTag)
        assert tags[0].tag_id == 7
        assert tags[0].tag_name == "web"

    @respx.mock
    def test_list_sends_query_param(self, client: NetskopeClient) -> None:
        route = respx.get(_TAGS_URL).mock(
            return_value=httpx.Response(200, json={"data": [], "status": {"total": 0}})
        )
        list(client.private_apps.tags.list(query="web"))
        assert route.calls.last.request.url.params["query"] == "web"

    @respx.mock
    def test_list_paginates_with_limit_and_offset(self, client: NetskopeClient) -> None:
        route = respx.get(_TAGS_URL).mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={"data": [{"tag_id": 1, "tag_name": "a"}], "status": {"total": 2}},
                ),
                httpx.Response(
                    200,
                    json={"data": [{"tag_id": 2, "tag_name": "b"}], "status": {"total": 2}},
                ),
            ]
        )
        tags = list(client.private_apps.tags.list(page_size=1))
        assert [t.tag_id for t in tags] == [1, 2]
        assert route.call_count == 2
        first, second = route.calls[0].request, route.calls[1].request
        assert first.url.params["limit"] == "1"
        assert first.url.params["offset"] == "0"
        assert second.url.params["offset"] == "1"

    @respx.mock
    def test_list_extracts_nested_tags_envelope(self, client: NetskopeClient) -> None:
        respx.get(_TAGS_URL).mock(
            return_value=httpx.Response(
                200, json={"data": {"tags": [_TAG]}, "status": {"total": 1}}
            )
        )
        tags = list(client.private_apps.tags.list())
        assert len(tags) == 1
        assert tags[0].tag_name == "web"

    @respx.mock
    def test_get(self, client: NetskopeClient) -> None:
        respx.get(f"{_TAGS_URL}/7").mock(return_value=httpx.Response(200, json={"data": _TAG}))
        tag = client.private_apps.tags.get(7)
        assert tag.tag_id == 7
        assert tag.tag_name == "web"

    @respx.mock
    def test_create_wraps_tag_names_and_stringifies_app_id(self, client: NetskopeClient) -> None:
        """create() body is {"id": "<app_id as str>", "tags": [{"tag_name": ...}]}."""
        route = respx.post(_TAGS_URL).mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"tag_id": 7, "tag_name": "web"}, {"tag_id": 8, "tag_name": "p"}]},
            )
        )
        tags = client.private_apps.tags.create(123, ["web", "p"])
        assert sent_json(route) == {
            "id": "123",
            "tags": [{"tag_name": "web"}, {"tag_name": "p"}],
        }
        assert [t.tag_name for t in tags] == ["web", "p"]

    @respx.mock
    def test_update_put_body(self, client: NetskopeClient) -> None:
        route = respx.put(f"{_TAGS_URL}/7").mock(
            return_value=httpx.Response(200, json={"data": {"tag_id": 7, "tag_name": "new"}})
        )
        tag = client.private_apps.tags.update(7, "new")
        assert route.calls.last.request.method == "PUT"
        assert sent_json(route) == {"tag_name": "new"}
        assert tag.tag_name == "new"

    @respx.mock
    def test_delete(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_TAGS_URL}/7").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        assert client.private_apps.tags.delete(7) is None
        assert route.call_count == 1

    @respx.mock
    def test_add_patch_body_ids_as_strings(self, client: NetskopeClient) -> None:
        """Bulk tag bodies send app ids as strings, tags as {"tag_name"} objects."""
        route = respx.patch(_TAGS_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        client.private_apps.tags.add([123, 456], ["web", "prod"])
        assert sent_json(route) == {
            "ids": ["123", "456"],
            "tags": [{"tag_name": "web"}, {"tag_name": "prod"}],
        }

    @respx.mock
    def test_replace_put_body_ids_as_strings(self, client: NetskopeClient) -> None:
        route = respx.put(_TAGS_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        client.private_apps.tags.replace(["123"], ["web"])
        assert sent_json(route) == {"ids": ["123"], "tags": [{"tag_name": "web"}]}

    @respx.mock
    def test_remove_delete_with_body(self, client: NetskopeClient) -> None:
        route = respx.delete(_TAGS_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        assert client.private_apps.tags.remove([123], ["old"]) is None
        assert sent_json(route) == {"ids": ["123"], "tags": [{"tag_name": "old"}]}

    @respx.mock
    def test_get_policy_in_use_ids_as_ints(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_TAGS_URL}/getpolicyinuse").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        client.private_apps.tags.get_policy_in_use([42, 99])
        assert sent_json(route) == {"ids": [42, 99]}


class TestAsyncPrivateAppsResource:
    """Tests for aclient.private_apps (async)."""

    @respx.mock
    async def test_list_sends_cli_filter_params(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_APPS_URL).mock(
            return_value=httpx.Response(
                200, json={"data": {"private_apps": [_APP]}, "status": {"total": 1}}
            )
        )
        apps = [app async for app in aclient.private_apps.list(app_name="dash", reachable=True)]
        assert len(apps) == 1
        assert isinstance(apps[0], PrivateApp)
        params = route.calls.last.request.url.params
        assert params["app_name"] == "dash"
        assert params["reachable"] == "true"

    @respx.mock
    async def test_update_uses_patch(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.patch(f"{_APPS_URL}/42").mock(
            return_value=httpx.Response(200, json={"data": _APP})
        )
        await aclient.private_apps.update(42, extra_fields={"host": "10.0.0.6"})
        assert route.calls.last.request.method == "PATCH"
        assert sent_json(route) == {"host": "10.0.0.6"}

    @respx.mock
    async def test_replace_uses_put(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.put(f"{_APPS_URL}/42").mock(
            return_value=httpx.Response(200, json={"data": _APP})
        )
        payload = {"app_name": "x", "host": "h", "port": "443"}
        await aclient.private_apps.replace(42, payload)
        assert sent_json(route) == payload

    @respx.mock
    async def test_bulk_delete_sends_body(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(_APPS_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        assert await aclient.private_apps.bulk_delete([1, 2, 3]) is None
        assert sent_json(route) == {"private_app_ids": [1, 2, 3]}

    @respx.mock
    async def test_get_policy_in_use(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(f"{_APPS_URL}/getpolicyinuse").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        await aclient.private_apps.get_policy_in_use([123])
        assert sent_json(route) == {"ids": [123]}

    @respx.mock
    async def test_discovery_settings_roundtrip(self, aclient: AsyncNetskopeClient) -> None:
        get_route = respx.get(_DISCOVERY_URL).mock(
            return_value=httpx.Response(200, json={"data": {"enabled": True}})
        )
        post_route = respx.post(_DISCOVERY_URL).mock(
            return_value=httpx.Response(200, json={"data": {"enabled": False}})
        )
        body = await aclient.private_apps.get_discovery_settings()
        assert body["data"]["enabled"] is True
        await aclient.private_apps.update_discovery_settings({"enabled": False})
        assert sent_json(post_route) == {"enabled": False}
        assert get_route.call_count == 1

    @respx.mock
    async def test_publisher_associations(self, aclient: AsyncNetskopeClient) -> None:
        expected = {"private_app_ids": [1], "publisher_ids": [2]}
        patch_route = respx.patch(_PUBLISHERS_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        put_route = respx.put(_PUBLISHERS_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        delete_route = respx.delete(_PUBLISHERS_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        await aclient.private_apps.add_publishers([1], [2])
        assert sent_json(patch_route) == expected
        await aclient.private_apps.replace_publishers([1], [2])
        assert sent_json(put_route) == expected
        assert await aclient.private_apps.remove_publishers([1], [2]) is None
        assert sent_json(delete_route) == expected


class TestAsyncPrivateAppTagsResource:
    """Tests for aclient.private_apps.tags (async)."""

    @respx.mock
    async def test_list_returns_tags(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_TAGS_URL).mock(
            return_value=httpx.Response(200, json={"data": [_TAG], "status": {"total": 1}})
        )
        tags = [tag async for tag in aclient.private_apps.tags.list(query="web")]
        assert len(tags) == 1
        assert isinstance(tags[0], PrivateAppTag)
        assert tags[0].tag_name == "web"

    @respx.mock
    async def test_get(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_TAGS_URL}/7").mock(return_value=httpx.Response(200, json={"data": _TAG}))
        tag = await aclient.private_apps.tags.get(7)
        assert tag.tag_id == 7

    @respx.mock
    async def test_create_body(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_TAGS_URL).mock(return_value=httpx.Response(200, json={"data": [_TAG]}))
        tags = await aclient.private_apps.tags.create("123", ["web"])
        assert sent_json(route) == {"id": "123", "tags": [{"tag_name": "web"}]}
        assert tags[0].tag_id == 7

    @respx.mock
    async def test_update_put_body(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.put(f"{_TAGS_URL}/7").mock(
            return_value=httpx.Response(200, json={"data": {"tag_id": 7, "tag_name": "new"}})
        )
        tag = await aclient.private_apps.tags.update(7, "new")
        assert sent_json(route) == {"tag_name": "new"}
        assert tag.tag_name == "new"

    @respx.mock
    async def test_delete(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(f"{_TAGS_URL}/7").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        assert await aclient.private_apps.tags.delete(7) is None
        assert route.call_count == 1

    @respx.mock
    async def test_bulk_bodies_ids_as_strings(self, aclient: AsyncNetskopeClient) -> None:
        expected = {"ids": ["1", "2"], "tags": [{"tag_name": "t"}]}
        patch_route = respx.patch(_TAGS_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        put_route = respx.put(_TAGS_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        delete_route = respx.delete(_TAGS_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        await aclient.private_apps.tags.add([1, 2], ["t"])
        assert sent_json(patch_route) == expected
        await aclient.private_apps.tags.replace([1, 2], ["t"])
        assert sent_json(put_route) == expected
        assert await aclient.private_apps.tags.remove([1, 2], ["t"]) is None
        assert sent_json(delete_route) == expected

    @respx.mock
    async def test_get_policy_in_use_ids_as_ints(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(f"{_TAGS_URL}/getpolicyinuse").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        await aclient.private_apps.tags.get_policy_in_use([42])
        assert sent_json(route) == {"ids": [42]}
