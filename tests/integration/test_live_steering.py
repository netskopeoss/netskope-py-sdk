"""Live integration tests for the Steering API.

READ-ONLY by design: steering configuration and IPSec tunnels have
tenant-wide blast radius, so this module never creates, updates, or
deletes anything.  Tunnel write methods are covered by unit tests only.

Run with: pytest tests/integration/test_live_steering.py -m integration -v
"""

from __future__ import annotations

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError
from netskope.models.devices import Device
from netskope.models.infrastructure import IPSecTunnel, Pop
from netskope.models.steering import SteeringConfig

from .conftest import skip_if_unavailable


@pytest.mark.integration
class TestSteeringConfigIntegration:
    """Live read-only tests for the global steering configuration."""

    def test_get_config_npa(self, client: NetskopeClient) -> None:
        try:
            config = client.steering.get_config("npa")
        except APIError as e:
            skip_if_unavailable(e, "steering npa config")
        else:
            assert isinstance(config, SteeringConfig)
            assert isinstance(config.data, dict)

    def test_get_config_publishers(self, client: NetskopeClient) -> None:
        """publishers scope routes to /steering/globalconfig/publishers."""
        try:
            config = client.steering.get_config("publishers")
        except APIError as e:
            skip_if_unavailable(e, "steering publishers config")
        else:
            assert isinstance(config, SteeringConfig)
            assert isinstance(config.data, dict)


@pytest.mark.integration
class TestSteeringIpsecIntegration:
    """Live read-only tests for IPSec PoPs and tunnels."""

    def test_list_pops(self, client: NetskopeClient) -> None:
        try:
            pops = client.steering.list_pops(page_size=10).to_list(max_items=10)
        except APIError as e:
            skip_if_unavailable(e, "ipsec pops")
        else:
            assert isinstance(pops, list)
            if pops:
                assert isinstance(pops[0], Pop)

    def test_list_tunnels(self, client: NetskopeClient) -> None:
        try:
            tunnels = client.steering.list_tunnels(page_size=10).to_list(max_items=10)
        except APIError as e:
            skip_if_unavailable(e, "ipsec tunnels")
        else:
            assert isinstance(tunnels, list)
            if tunnels:
                assert isinstance(tunnels[0], IPSecTunnel)


@pytest.mark.integration
class TestSteeringDevicesIntegration:
    """Live read-only tests for the managed-devices list."""

    def test_list_devices_first_page(self, client: NetskopeClient) -> None:
        """Fetch only the first result — the endpoint 404s on some tenants."""
        try:
            device = client.steering.list_devices(page_size=5).first()
        except APIError as e:
            skip_if_unavailable(e, "steering devices")
        else:
            if device is not None:
                assert isinstance(device, Device)
