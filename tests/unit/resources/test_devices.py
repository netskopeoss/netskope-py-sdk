"""Tests for the Devices resource with mocked HTTP.

``client.devices`` is not wired into the clients yet, so tests instantiate
``DevicesResource`` / ``AsyncDevicesResource`` directly against the client
transport.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import NotFoundError, ValidationError
from netskope.models.devices import Device, DeviceTag
from netskope.resources.devices import AsyncDevicesResource, DevicesResource
from tests.unit.resources.conftest import sent_json

_DEVICES_URL = "https://t.goskope.com/api/v2/steering/devices"
_SUPPORTED_OS_URL = "https://t.goskope.com/api/v2/devices/supportedos"
_TAGS_URL = "https://t.goskope.com/api/v2/devices/device/tags"
_TAGS_QUERY_URL = f"{_TAGS_URL}/gettags"

_TAG_BODY = {
    "id": 7,
    "name": "Production Servers",
    "description": "Tags for production devices",
    "device_count": 5,
    "device_classification_count": 2,
}

_TAGS_LIST_ENVELOPE = {
    "success": True,
    "data": {"data": [_TAG_BODY], "total_count": 1, "offset": 0, "limit": 20},
}


def _devices(client: NetskopeClient) -> DevicesResource:
    return DevicesResource(client._transport)


def _adevices(aclient: AsyncNetskopeClient) -> AsyncDevicesResource:
    return AsyncDevicesResource(aclient._transport)


class TestDevicesList:
    """Tests for DevicesResource.list."""

    @respx.mock
    def test_list_paginates_and_extracts_devices_key(self, client: NetskopeClient) -> None:
        route = respx.get(_DEVICES_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "devices": [{"device_id": "d1", "hostname": "LAPTOP-1", "os": "Windows"}],
                    "status": {"total": 1},
                },
            )
        )
        devices = list(_devices(client).list(page_size=50))

        assert len(devices) == 1
        assert isinstance(devices[0], Device)
        assert devices[0].device_id == "d1"
        assert devices[0].host_name == "LAPTOP-1"
        request = route.calls[0].request
        assert request.method == "GET"
        assert dict(request.url.params) == {"limit": "50", "offset": "0"}

    @respx.mock
    def test_list_empty(self, client: NetskopeClient) -> None:
        respx.get(_DEVICES_URL).mock(return_value=httpx.Response(200, json={"devices": []}))
        assert list(_devices(client).list()) == []

    @respx.mock
    async def test_async_list(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_DEVICES_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "devices": [{"device_id": "d2", "hostname": "MAC-1"}],
                    "status": {"total": 1},
                },
            )
        )
        devices = [d async for d in _adevices(aclient).list()]
        assert [d.device_id for d in devices] == ["d2"]


class TestSupportedOs:
    """Tests for DevicesResource.supported_os."""

    @respx.mock
    def test_supported_os_returns_body(self, client: NetskopeClient) -> None:
        route = respx.get(_SUPPORTED_OS_URL).mock(
            return_value=httpx.Response(200, json={"available_os": ["windows", "mac", "linux"]})
        )
        result = _devices(client).supported_os()

        assert result == {"available_os": ["windows", "mac", "linux"]}
        request = route.calls.last.request
        assert request.method == "GET"
        assert dict(request.url.params) == {}

    @respx.mock
    async def test_async_supported_os(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_SUPPORTED_OS_URL).mock(
            return_value=httpx.Response(200, json={"available_os": ["ios"]})
        )
        assert await _adevices(aclient).supported_os() == {"available_os": ["ios"]}


class TestDeviceTagsList:
    """Tests for DeviceTagsResource.list."""

    @respx.mock
    def test_list_posts_gettags_with_paging_body(self, client: NetskopeClient) -> None:
        route = respx.post(_TAGS_QUERY_URL).mock(
            return_value=httpx.Response(200, json=_TAGS_LIST_ENVELOPE)
        )
        tags = _devices(client).tags.list()

        assert len(tags) == 1
        assert isinstance(tags[0], DeviceTag)
        assert tags[0].id == 7
        assert tags[0].name == "Production Servers"
        assert tags[0].device_count == 5
        assert sent_json(route) == {"offset": 0, "limit": 20}

    @respx.mock
    def test_list_sends_name_filter_and_custom_paging(self, client: NetskopeClient) -> None:
        route = respx.post(_TAGS_QUERY_URL).mock(
            return_value=httpx.Response(
                200, json={"success": True, "data": {"data": [], "total_count": 0}}
            )
        )
        _devices(client).tags.list(name="prod", offset=40, limit=100)

        assert sent_json(route) == {"offset": 40, "limit": 100, "name": "prod"}

    def test_list_rejects_out_of_range_limit(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            _devices(client).tags.list(limit=101)
        with pytest.raises(ValidationError):
            _devices(client).tags.list(limit=0)

    def test_list_rejects_negative_offset(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            _devices(client).tags.list(offset=-1)

    @respx.mock
    async def test_async_list(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_TAGS_QUERY_URL).mock(
            return_value=httpx.Response(200, json=_TAGS_LIST_ENVELOPE)
        )
        tags = await _adevices(aclient).tags.list(name="prod")

        assert [t.id for t in tags] == [7]
        assert sent_json(route) == {"offset": 0, "limit": 20, "name": "prod"}


class TestDeviceTagsGet:
    """Tests for DeviceTagsResource.get."""

    @respx.mock
    def test_get_queries_by_id(self, client: NetskopeClient) -> None:
        route = respx.post(_TAGS_QUERY_URL).mock(
            return_value=httpx.Response(200, json=_TAGS_LIST_ENVELOPE)
        )
        tag = _devices(client).tags.get(7)

        assert isinstance(tag, DeviceTag)
        assert tag.id == 7
        assert sent_json(route) == {"id": 7}

    @respx.mock
    def test_get_accepts_numeric_string(self, client: NetskopeClient) -> None:
        route = respx.post(_TAGS_QUERY_URL).mock(
            return_value=httpx.Response(200, json=_TAGS_LIST_ENVELOPE)
        )
        _devices(client).tags.get("7")

        assert sent_json(route) == {"id": 7}

    @respx.mock
    def test_get_raises_not_found_on_empty_result(self, client: NetskopeClient) -> None:
        respx.post(_TAGS_QUERY_URL).mock(
            return_value=httpx.Response(
                200, json={"success": True, "data": {"data": [], "total_count": 0}}
            )
        )
        with pytest.raises(NotFoundError):
            _devices(client).tags.get(999)

    def test_get_rejects_non_numeric_id_without_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            _devices(client).tags.get("not-a-number")

    @respx.mock
    async def test_async_get(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_TAGS_QUERY_URL).mock(
            return_value=httpx.Response(200, json=_TAGS_LIST_ENVELOPE)
        )
        tag = await _adevices(aclient).tags.get(7)

        assert tag.name == "Production Servers"
        assert sent_json(route) == {"id": 7}


class TestDeviceTagsCreate:
    """Tests for DeviceTagsResource.create."""

    @respx.mock
    def test_create_sends_name_only(self, client: NetskopeClient) -> None:
        route = respx.post(_TAGS_URL).mock(
            return_value=httpx.Response(201, json={"success": True, "data": _TAG_BODY})
        )
        tag = _devices(client).tags.create("Production Servers")

        assert isinstance(tag, DeviceTag)
        assert tag.id == 7
        assert sent_json(route) == {"name": "Production Servers"}

    @respx.mock
    def test_create_sends_description(self, client: NetskopeClient) -> None:
        route = respx.post(_TAGS_URL).mock(
            return_value=httpx.Response(201, json={"success": True, "data": _TAG_BODY})
        )
        _devices(client).tags.create("prod-2024", description="Tags for production devices")

        assert sent_json(route) == {
            "name": "prod-2024",
            "description": "Tags for production devices",
        }

    def test_create_rejects_invalid_name_without_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            _devices(client).tags.create("bad!name")

    def test_create_rejects_invalid_description_without_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            _devices(client).tags.create("good-name", description="bad_description!")

    @respx.mock
    async def test_async_create(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_TAGS_URL).mock(
            return_value=httpx.Response(201, json={"success": True, "data": _TAG_BODY})
        )
        tag = await _adevices(aclient).tags.create("Production Servers")

        assert tag.id == 7
        assert sent_json(route) == {"name": "Production Servers"}


class TestDeviceTagsUpdate:
    """Tests for DeviceTagsResource.update."""

    @respx.mock
    def test_update_patches_only_provided_fields(self, client: NetskopeClient) -> None:
        route = respx.patch(f"{_TAGS_URL}/7").mock(
            return_value=httpx.Response(200, json={"success": True, "data": _TAG_BODY})
        )
        tag = _devices(client).tags.update(7, name="New Name")

        assert isinstance(tag, DeviceTag)
        assert sent_json(route) == {"name": "New Name"}

    @respx.mock
    def test_update_sends_both_fields(self, client: NetskopeClient) -> None:
        route = respx.patch(f"{_TAGS_URL}/7").mock(
            return_value=httpx.Response(200, json={"success": True, "data": _TAG_BODY})
        )
        _devices(client).tags.update(7, name="New Name", description="New description")

        assert sent_json(route) == {"name": "New Name", "description": "New description"}

    def test_update_rejects_empty_change_without_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            _devices(client).tags.update(7)

    def test_update_rejects_non_numeric_id_without_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            _devices(client).tags.update("abc", name="New Name")

    @respx.mock
    async def test_async_update(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.patch(f"{_TAGS_URL}/7").mock(
            return_value=httpx.Response(200, json={"success": True, "data": _TAG_BODY})
        )
        tag = await _adevices(aclient).tags.update(7, description="Updated")

        assert tag.id == 7
        assert sent_json(route) == {"description": "Updated"}


class TestDeviceTagsDelete:
    """Tests for DeviceTagsResource.delete."""

    @respx.mock
    def test_delete(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_TAGS_URL}/7").mock(
            return_value=httpx.Response(200, json={"success": True, "data": None})
        )
        assert _devices(client).tags.delete(7) is None
        assert route.called

    def test_delete_rejects_non_numeric_id_without_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            _devices(client).tags.delete("7; DROP")

    @respx.mock
    async def test_async_delete(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(f"{_TAGS_URL}/7").mock(
            return_value=httpx.Response(200, json={"success": True, "data": None})
        )
        await _adevices(aclient).tags.delete(7)
        assert route.called


class TestTagsSubresourceCaching:
    """The .tags sub-resource is cached per parent resource instance."""

    def test_tags_property_is_cached(self, client: NetskopeClient) -> None:
        devices = _devices(client)
        assert devices.tags is devices.tags

    async def test_async_tags_property_is_cached(self, aclient: AsyncNetskopeClient) -> None:
        devices = _adevices(aclient)
        assert devices.tags is devices.tags
