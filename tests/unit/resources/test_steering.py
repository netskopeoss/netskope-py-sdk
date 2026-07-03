"""Tests for client.steering with mocked HTTP."""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.devices import Device
from netskope.models.infrastructure import IPSecTunnel, Pop
from tests.unit.resources.conftest import sent_json

_BASE = "https://t.goskope.com"
_CLIENTCONFIG_URL = f"{_BASE}/api/v2/steering/globalconfig/clientconfiguration"
_PUBLISHERS_CONFIG_URL = f"{_BASE}/api/v2/steering/globalconfig/publishers"
_POPS_URL = f"{_BASE}/api/v2/steering/ipsec/pops"
_TUNNELS_URL = f"{_BASE}/api/v2/steering/ipsec/tunnels"
_DEVICES_URL = f"{_BASE}/api/v2/steering/devices"

_TUNNEL = {
    "id": 42,
    "site": "NYC-Office",
    "status": "up",
    "bandwidth": 100,
}

_DEVICE = {
    "device_id": "d-1",
    "hostname": "laptop-01",
    "os": "macOS",
    "os_version": "15.5",
    "client_version": "120.0.0",
    "last_event": {"event": "Tunnel Up", "timestamp": 1700000000},
    "users": [{"username": "alice@example.com"}],
}


class TestSteeringConfigRouting:
    """Scope → endpoint routing for get_config/update_config (sync)."""

    @respx.mock
    def test_get_config_publishers_uses_globalconfig_publishers(
        self, client: NetskopeClient
    ) -> None:
        """The publishers scope must NOT route under clientconfiguration."""
        route = respx.get(_PUBLISHERS_CONFIG_URL).mock(
            return_value=httpx.Response(200, json={"data": {"flag_a": 1}})
        )
        config = client.steering.get_config("publishers")
        assert route.call_count == 1
        assert config.data == {"flag_a": 1}

    @respx.mock
    @pytest.mark.parametrize("scope", ["npa", "nsc", "ztna"])
    def test_get_config_client_scopes_use_clientconfiguration(
        self, client: NetskopeClient, scope: str
    ) -> None:
        route = respx.get(f"{_CLIENTCONFIG_URL}/{scope}").mock(
            return_value=httpx.Response(200, json={"data": {"flag": 0}})
        )
        client.steering.get_config(scope)
        assert route.call_count == 1

    @respx.mock
    def test_get_config_invalid_scope_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            client.steering.get_config("bogus")
        assert len(respx.calls) == 0

    @respx.mock
    def test_update_config_publishers_patches_globalconfig_publishers(
        self, client: NetskopeClient
    ) -> None:
        route = respx.patch(_PUBLISHERS_CONFIG_URL).mock(
            return_value=httpx.Response(200, json={"data": {"flag_a": 1}})
        )
        client.steering.update_config("publishers", settings={"flag_a": 1})
        assert route.call_count == 1
        assert sent_json(route) == {"flag_a": 1}

    @respx.mock
    def test_update_config_npa_patches_clientconfiguration(self, client: NetskopeClient) -> None:
        route = respx.patch(f"{_CLIENTCONFIG_URL}/npa").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        client.steering.update_config("npa", settings={"flag_name": 1})
        assert sent_json(route) == {"flag_name": 1}

    @respx.mock
    def test_update_config_invalid_scope_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            client.steering.update_config("clientconfig", settings={"x": 1})
        assert len(respx.calls) == 0


class TestSteeringTunnels:
    """Tunnel create/update/delete (sync)."""

    @respx.mock
    def test_create_tunnel_payload_defaults(self, client: NetskopeClient) -> None:
        route = respx.post(_TUNNELS_URL).mock(
            return_value=httpx.Response(200, json={"data": _TUNNEL})
        )
        tunnel = client.steering.create_tunnel(
            "NYC-Office", ["US-East1", "US-East2"], "s3cret", "vpn@example.com"
        )
        assert sent_json(route) == {
            "site": "NYC-Office",
            "pops": ["US-East1", "US-East2"],
            "psk": "s3cret",
            "srcidentity": "vpn@example.com",
            "bandwidth": 100,
            "encryption": "AES256-CBC",
            "enabled": True,
        }
        assert isinstance(tunnel, IPSecTunnel)
        assert tunnel.id == 42
        assert tunnel.site == "NYC-Office"

    @respx.mock
    def test_create_tunnel_payload_all_options(self, client: NetskopeClient) -> None:
        route = respx.post(_TUNNELS_URL).mock(
            return_value=httpx.Response(200, json={"data": _TUNNEL})
        )
        client.steering.create_tunnel(
            "Lab",
            ["US-West1"],
            "s3cret",
            "lab@example.com",
            bandwidth=250,
            encryption="AES256-GCM",
            enabled=False,
            vendor="Cisco",
            notes="Testing only",
        )
        assert sent_json(route) == {
            "site": "Lab",
            "pops": ["US-West1"],
            "psk": "s3cret",
            "srcidentity": "lab@example.com",
            "bandwidth": 250,
            "encryption": "AES256-GCM",
            "enabled": False,
            "vendor": "Cisco",
            "notes": "Testing only",
        }

    @respx.mock
    @pytest.mark.parametrize(
        "kwargs",
        [
            {"bandwidth": 75},
            {"bandwidth": 0},
            {"encryption": "AES512-CBC"},
            {"encryption": "aes256-cbc"},  # choices are case-sensitive
        ],
    )
    def test_create_tunnel_validation_no_http(
        self, client: NetskopeClient, kwargs: dict[str, object]
    ) -> None:
        with pytest.raises(ValidationError):
            client.steering.create_tunnel(
                "Site",
                ["US-East1"],
                "psk",
                "id@example.com",
                **kwargs,  # type: ignore[arg-type]
            )
        assert len(respx.calls) == 0

    @respx.mock
    def test_create_tunnel_empty_pops_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            client.steering.create_tunnel("Site", [], "psk", "id@example.com")
        assert len(respx.calls) == 0

    @respx.mock
    def test_update_tunnel_uses_patch_with_partial_body(self, client: NetskopeClient) -> None:
        route = respx.patch(f"{_TUNNELS_URL}/42").mock(
            return_value=httpx.Response(200, json={"data": {**_TUNNEL, "bandwidth": 250}})
        )
        tunnel = client.steering.update_tunnel(42, bandwidth=250, notes="Upgraded")
        assert route.calls.last.request.method == "PATCH"
        assert sent_json(route) == {"bandwidth": 250, "notes": "Upgraded"}
        assert tunnel.bandwidth == 250

    @respx.mock
    def test_update_tunnel_enabled_false_is_sent(self, client: NetskopeClient) -> None:
        """enabled=False must be sent (is-not-None check, not truthiness)."""
        route = respx.patch(f"{_TUNNELS_URL}/42").mock(
            return_value=httpx.Response(200, json={"data": _TUNNEL})
        )
        client.steering.update_tunnel(42, enabled=False)
        assert sent_json(route) == {"enabled": False}

    @respx.mock
    def test_update_tunnel_no_fields_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            client.steering.update_tunnel(42)
        assert len(respx.calls) == 0

    @respx.mock
    @pytest.mark.parametrize("kwargs", [{"bandwidth": 300}, {"encryption": "DES"}, {"pops": []}])
    def test_update_tunnel_validation_no_http(
        self, client: NetskopeClient, kwargs: dict[str, object]
    ) -> None:
        with pytest.raises(ValidationError):
            client.steering.update_tunnel(42, **kwargs)  # type: ignore[arg-type]
        assert len(respx.calls) == 0

    @respx.mock
    def test_delete_tunnel(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_TUNNELS_URL}/42").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        result = client.steering.delete_tunnel(42)
        assert result is None
        assert route.call_count == 1


class TestSteeringListFilters:
    """Filter params on list_pops / list_tunnels (sync)."""

    @respx.mock
    def test_list_pops_filter_params(self, client: NetskopeClient) -> None:
        route = respx.get(_POPS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {"pops": [{"name": "US-West1", "region": "US"}]},
                    "status": {"total": 1},
                },
            )
        )
        pops = list(client.steering.list_pops(name="US-West", region="US", country="US"))
        assert len(pops) == 1
        assert isinstance(pops[0], Pop)
        params = route.calls.last.request.url.params
        assert params["name"] == "US-West"
        assert params["region"] == "US"
        assert params["country"] == "US"
        assert params["limit"] == "100"
        assert params["offset"] == "0"

    @respx.mock
    def test_list_tunnels_filter_params(self, client: NetskopeClient) -> None:
        route = respx.get(_TUNNELS_URL).mock(
            return_value=httpx.Response(
                200, json={"data": {"tunnels": [_TUNNEL]}, "status": {"total": 1}}
            )
        )
        tunnels = list(client.steering.list_tunnels(status="UP", site="HQ", pop="US-West1"))
        assert len(tunnels) == 1
        params = route.calls.last.request.url.params
        assert params["status"] == "up"  # normalized to lowercase
        assert params["site"] == "HQ"
        assert params["pop"] == "US-West1"

    @respx.mock
    def test_list_tunnels_invalid_status_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            client.steering.list_tunnels(status="degraded")
        assert len(respx.calls) == 0

    @respx.mock
    def test_list_pops_no_filters_sends_only_pagination(self, client: NetskopeClient) -> None:
        route = respx.get(_POPS_URL).mock(
            return_value=httpx.Response(
                200, json={"data": {"pops": [{"name": "p"}]}, "status": {"total": 1}}
            )
        )
        list(client.steering.list_pops())
        assert set(route.calls.last.request.url.params.keys()) == {"limit", "offset"}


class TestSteeringDevices:
    """list_devices (sync)."""

    @respx.mock
    def test_list_devices_url_extract_and_params(self, client: NetskopeClient) -> None:
        route = respx.get(_DEVICES_URL).mock(
            return_value=httpx.Response(
                200, json={"data": {"devices": [_DEVICE]}, "status": {"total": 1}}
            )
        )
        devices = list(client.steering.list_devices(page_size=25))
        assert len(devices) == 1
        assert isinstance(devices[0], Device)
        assert devices[0].device_id == "d-1"
        assert devices[0].host_name == "laptop-01"
        assert devices[0].os == "macOS"
        assert devices[0].client_version == "120.0.0"
        assert devices[0].users == [{"username": "alice@example.com"}]
        params = route.calls.last.request.url.params
        assert params["limit"] == "25"
        assert params["offset"] == "0"

    @respx.mock
    def test_list_devices_pagination_advances_offset(self, client: NetskopeClient) -> None:
        route = respx.get(_DEVICES_URL).mock(
            return_value=httpx.Response(
                200, json={"data": {"devices": [_DEVICE, _DEVICE]}, "status": {"total": 4}}
            )
        )
        devices = list(client.steering.list_devices(page_size=2))
        assert len(devices) == 4
        assert route.call_count == 2
        offsets = [call.request.url.params["offset"] for call in route.calls]
        assert offsets == ["0", "2"]


class TestAsyncSteeringResource:
    """Tests for aclient.steering (async)."""

    @respx.mock
    async def test_get_config_publishers_routing(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_PUBLISHERS_CONFIG_URL).mock(
            return_value=httpx.Response(200, json={"data": {"flag_a": 1}})
        )
        config = await aclient.steering.get_config("publishers")
        assert route.call_count == 1
        assert config.data == {"flag_a": 1}

    @respx.mock
    async def test_get_config_npa_routing(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(f"{_CLIENTCONFIG_URL}/npa").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        await aclient.steering.get_config("npa")
        assert route.call_count == 1

    @respx.mock
    async def test_get_config_invalid_scope_no_http(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError):
            await aclient.steering.get_config("bogus")
        assert len(respx.calls) == 0

    @respx.mock
    async def test_create_tunnel_payload(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_TUNNELS_URL).mock(
            return_value=httpx.Response(200, json={"data": _TUNNEL})
        )
        tunnel = await aclient.steering.create_tunnel(
            "NYC-Office", ["US-East1"], "s3cret", "vpn@example.com"
        )
        assert sent_json(route) == {
            "site": "NYC-Office",
            "pops": ["US-East1"],
            "psk": "s3cret",
            "srcidentity": "vpn@example.com",
            "bandwidth": 100,
            "encryption": "AES256-CBC",
            "enabled": True,
        }
        assert tunnel.id == 42

    @respx.mock
    async def test_create_tunnel_validation_no_http(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError):
            await aclient.steering.create_tunnel(
                "Site", ["US-East1"], "psk", "id@example.com", bandwidth=999
            )
        assert len(respx.calls) == 0

    @respx.mock
    async def test_update_tunnel_patch_partial_body(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.patch(f"{_TUNNELS_URL}/42").mock(
            return_value=httpx.Response(200, json={"data": _TUNNEL})
        )
        await aclient.steering.update_tunnel(42, encryption="AES256-GCM")
        assert route.calls.last.request.method == "PATCH"
        assert sent_json(route) == {"encryption": "AES256-GCM"}

    @respx.mock
    async def test_update_tunnel_no_fields_no_http(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError):
            await aclient.steering.update_tunnel(42)
        assert len(respx.calls) == 0

    @respx.mock
    async def test_delete_tunnel(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(f"{_TUNNELS_URL}/7").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        result = await aclient.steering.delete_tunnel(7)
        assert result is None
        assert route.call_count == 1

    @respx.mock
    async def test_list_tunnels_filter_params(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_TUNNELS_URL).mock(
            return_value=httpx.Response(
                200, json={"data": {"tunnels": [_TUNNEL]}, "status": {"total": 1}}
            )
        )
        tunnels = [t async for t in aclient.steering.list_tunnels(status="down", site="HQ")]
        assert len(tunnels) == 1
        params = route.calls.last.request.url.params
        assert params["status"] == "down"
        assert params["site"] == "HQ"

    @respx.mock
    async def test_list_devices(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_DEVICES_URL).mock(
            return_value=httpx.Response(
                200, json={"data": {"devices": [_DEVICE]}, "status": {"total": 1}}
            )
        )
        devices = [d async for d in aclient.steering.list_devices(page_size=10)]
        assert len(devices) == 1
        assert devices[0].host_name == "laptop-01"
        assert route.calls.last.request.url.params["limit"] == "10"
