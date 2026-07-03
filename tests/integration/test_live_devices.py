"""Live integration tests for the Devices API.

These tests require valid credentials and hit the real API.
Run with: pytest tests/integration/ -m integration -v

Credentials come from environment variables only (see conftest.py).
``client.devices`` is expected to be wired into ``NetskopeClient`` by the
time these run; access is via ``client.devices`` directly.

The device-inventory route (``GET /api/v2/steering/devices``) has no route
in the API gateway specs and returns 404 on many tenants — that test is
expected to skip there.
"""

from __future__ import annotations

import contextlib

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError, NotFoundError
from netskope.models.devices import DeviceTag

from .conftest import skip_if_unavailable, unique_name


@pytest.mark.integration
class TestDevicesIntegration:
    """Live read smokes for the Devices API."""

    def test_list_devices(self, client: NetskopeClient) -> None:
        """List devices; skip when the legacy inventory route is unrouted (404)."""
        try:
            devices = client.devices.list(page_size=5).to_list(max_items=5)
        except APIError as e:
            skip_if_unavailable(e, "devices list")
        else:
            assert isinstance(devices, list)

    def test_supported_os(self, client: NetskopeClient) -> None:
        """Fetch supported operating systems; skip when unavailable."""
        try:
            data = client.devices.supported_os()
        except APIError as e:
            skip_if_unavailable(e, "devices supported_os")
        else:
            assert isinstance(data, (dict, list))


@pytest.mark.integration
class TestDeviceTagWriteCycle:
    """Live create → get → update → delete cycle for a device tag."""

    def test_tag_write_cycle(self, client: NetskopeClient) -> None:
        name = unique_name("devtag")

        try:
            created = client.devices.tags.create(name, description="sdk integration test tag")
        except APIError as e:
            skip_if_unavailable(e, "device tag create")
            return  # unreachable; keeps type-checkers happy

        tag_id = created.id
        if tag_id is None:
            # Some tenants return a sparse create body — find the tag by name.
            with contextlib.suppress(APIError):
                for tag in client.devices.tags.list(name=name, limit=100):
                    if tag.name == name:
                        tag_id = tag.id
                        break

        try:
            assert tag_id is not None, f"Could not determine ID of created tag {name!r}"

            fetched = client.devices.tags.get(tag_id)
            assert isinstance(fetched, DeviceTag)
            assert fetched.name == name

            updated = client.devices.tags.update(tag_id, description="sdk inttest updated")
            assert isinstance(updated, DeviceTag)
        finally:
            if tag_id is not None:
                with contextlib.suppress(NotFoundError):
                    client.devices.tags.delete(tag_id)
