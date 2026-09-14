"""Tests for client.steering with mocked HTTP."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx
from pydantic import ValidationError as PydanticValidationError

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.devices import Device
from netskope.models.infrastructure import IPSecTunnel, Pop
from netskope.models.steering import IPSecTunnelCreate, SteeringConfigStatus
from tests.unit.resources.conftest import CONTRACT_BASE, EXAMPLE_BASE, sent_json

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
    def test_get_config_npa_scope_uses_clientconfiguration(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_CLIENTCONFIG_URL}/npa").mock(
            return_value=httpx.Response(200, json={"data": {"flag": 0}})
        )
        client.steering.get_config("npa")
        assert route.call_count == 1

    @respx.mock
    @pytest.mark.parametrize("scope", ["nsc", "ztna"])
    def test_get_config_rejects_scopes_with_no_endpoint(
        self, client: NetskopeClient, scope: str
    ) -> None:
        """npa_global_config.yaml declares npa (:218) and publishers (:352), nothing else.

        ``clientconfiguration/nsc`` and ``clientconfiguration/ztna`` appear in
        no path in the file, so every call on them was a 404; the error names
        the scopes that do exist.
        """
        with pytest.raises(ValidationError, match="npa, publishers"):
            client.steering.get_config(scope)
        with pytest.raises(ValidationError, match="npa, publishers"):
            client.steering.update_config(scope, settings={"flag": 1})
        assert len(respx.calls) == 0

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
            "enable": True,
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
            "enable": False,
            "vendor": "Cisco",
            "notes": "Testing only",
        }

    @respx.mock
    @pytest.mark.parametrize(
        "kwargs",
        [
            {"bandwidth": 0},
            {"bandwidth": -1},
            {"encryption": ""},
            {"encryption": "   "},
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
        """enabled=False must be sent, under the API's ``enable`` request key."""
        route = respx.patch(f"{_TUNNELS_URL}/42").mock(
            return_value=httpx.Response(200, json={"data": _TUNNEL})
        )
        client.steering.update_tunnel(42, enabled=False)
        assert sent_json(route) == {"enable": False}

    @respx.mock
    def test_update_tunnel_no_fields_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            client.steering.update_tunnel(42)
        assert len(respx.calls) == 0

    @respx.mock
    @pytest.mark.parametrize("kwargs", [{"bandwidth": 0}, {"encryption": ""}, {"pops": []}])
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
            "enable": True,
        }
        assert tunnel.id == 42

    @respx.mock
    async def test_create_tunnel_validation_no_http(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError):
            await aclient.steering.create_tunnel(
                "Site", ["US-East1"], "psk", "id@example.com", bandwidth=0
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


# --- Gateway contract conformance -------------------------------------------------------------
#
# Folded in from the spec-conformance reviews: each test cites the
# production/endpoints file and line whose shape it pins.

_CONTRACT_TUNNELS_URL = f"{CONTRACT_BASE}/api/v2/steering/ipsec/tunnels"
_CONTRACT_POPS_URL = f"{CONTRACT_BASE}/api/v2/steering/ipsec/pops"
_NPA_CONFIG_URL = f"{CONTRACT_BASE}/api/v2/steering/globalconfig/clientconfiguration/npa"


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_steering_config_patch_returns_a_status_acknowledgment(
    contract_client: NetskopeClient, contract_aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    """The global-config PATCH 200 declares only ``status``.

    Spec: steering/npa_global_config.yaml:274-283 for
    ``/globalconfig/clientconfiguration/npa`` and :408-417 for
    ``/globalconfig/publishers``; neither echoes the stored flags, so the old
    return value was an all-default ``SteeringConfig``.
    """
    route = respx.patch(_NPA_CONFIG_URL).mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )
    client = contract_aclient if asynchronous else contract_client
    result = client.steering.update_config("npa", settings={"npa_ff": "1"})
    if asynchronous:
        result = await result

    assert isinstance(result, SteeringConfigStatus)
    assert result.status == "success"
    assert sent_json(route) == {"npa_ff": "1"}


@respx.mock
def test_typed_steering_config_patch_returns_the_acknowledgment(
    contract_client: NetskopeClient,
) -> None:
    """The typed accessor reports the same acknowledgment (:274-283)."""
    from netskope.models.steering import SteeringSettings

    respx.patch(_NPA_CONFIG_URL).mock(return_value=httpx.Response(200, json={"status": "success"}))
    parsed = contract_client.steering.with_response.update_config_request(
        "npa", SteeringSettings({"npa_ff": 1})
    ).parse()
    assert isinstance(parsed, SteeringConfigStatus)
    assert parsed.status == "success"


@pytest.mark.parametrize(
    "accessor,url",
    [("list_pops_page", _CONTRACT_POPS_URL), ("list_tunnels_page", _CONTRACT_TUNNELS_URL)],
)
@respx.mock
def test_ipsec_limit_admits_its_declared_range(
    contract_client: NetskopeClient, accessor: str, url: str
) -> None:
    """``limit`` declares ``minimum: 0, maximum: 100``.

    Spec: steering/ipsec.yaml:478-486 for ``GET /ipsec/pops`` and :672-680 for
    ``GET /ipsec/tunnels``; these are the only formal ``maximum:`` values in the
    slice.  An unbounded ``limit`` was spent on a round trip the gateway can
    only reject or silently clamp.
    """
    route = respx.get(url).mock(return_value=httpx.Response(200, json={"result": [], "total": 0}))
    method = getattr(contract_client.steering.with_response, accessor)

    for limit in (0, 100):
        method(limit=limit).parse()
    assert [dict(call.request.url.params)["limit"] for call in route.calls] == ["0", "100"]

    for limit in (101, 1000, -1):
        with pytest.raises(ValidationError, match="limit must be an integer"):
            method(limit=limit)
    assert route.call_count == 2


@pytest.mark.parametrize(
    "accessor,url",
    [("list_pops_page", _CONTRACT_POPS_URL), ("list_tunnels_page", _CONTRACT_TUNNELS_URL)],
)
@respx.mock
async def test_async_ipsec_limit_admits_its_declared_range(
    contract_aclient: AsyncNetskopeClient, accessor: str, url: str
) -> None:
    """The async accessors enforce the same bounds (ipsec.yaml:478-486, :672-680)."""
    route = respx.get(url).mock(return_value=httpx.Response(200, json={"result": [], "total": 0}))
    method = getattr(contract_aclient.steering.with_response, accessor)
    (await method(limit=100)).parse()
    with pytest.raises(ValidationError, match="limit must be an integer"):
        await method(limit=101)
    assert route.call_count == 1


@pytest.mark.parametrize("lister", ["list_pops", "list_tunnels"])
@pytest.mark.parametrize("page_size", [0, -1, True])
def test_ipsec_iterators_require_a_positive_page_size(
    contract_client: NetskopeClient, lister: str, page_size: Any
) -> None:
    """A page size of 0 is inside the declared ``limit`` range but cannot advance.

    ``limit`` declares ``minimum: 0`` (steering/ipsec.yaml:478-486), which a
    one-page accessor can honour; an offset traversal stepping by 0 would never
    reach the next page, so the iterator requires a positive stride.
    """
    with pytest.raises(ValidationError, match="page_size"):
        getattr(contract_client.steering, lister)(page_size=page_size)


@pytest.mark.parametrize(
    "lister,url", [("list_pops", _CONTRACT_POPS_URL), ("list_tunnels", _CONTRACT_TUNNELS_URL)]
)
@respx.mock
def test_ipsec_iterators_clamp_to_the_declared_maximum(
    contract_client: NetskopeClient, lister: str, url: str
) -> None:
    """A page size above ``maximum: 100`` is clamped rather than sent (:478-486, :672-680)."""
    route = respx.get(url).mock(return_value=httpx.Response(200, json={"result": []}))
    list(getattr(contract_client.steering, lister)(page_size=500))
    assert dict(route.calls.last.request.url.params)["limit"] == "100"


@pytest.mark.parametrize("value", ["yes", 2, "01", None, True])
@respx.mock
def test_legacy_steering_update_rejects_undeclared_flag_values(
    contract_client: NetskopeClient, value: Any
) -> None:
    """``global_config_data_request`` admits only ``0`` and ``1``.

    Spec: steering/npa_global_config.yaml:43-52 :
    ``additionalProperties: oneOf [{string, pattern ^[01]$}, {integer, enum [0, 1]}]``.
    The legacy path forwarded the mapping unchecked while the typed path
    validated it.
    """
    with pytest.raises(ValidationError, match=r"must be 0 or 1"):
        contract_client.steering.update_config("npa", settings={"npa_ff": value})
    assert len(respx.calls) == 0


@pytest.mark.parametrize("value", ["yes", 2])
@respx.mock
async def test_async_legacy_steering_update_rejects_undeclared_flag_values(
    contract_aclient: AsyncNetskopeClient, value: Any
) -> None:
    """The async mirror applies the same domain (npa_global_config.yaml:43-52)."""
    with pytest.raises(ValidationError, match=r"must be 0 or 1"):
        await contract_aclient.steering.update_config("npa", settings={"npa_ff": value})
    assert len(respx.calls) == 0


@pytest.mark.parametrize("value", [0, 1, "0", "1"])
@respx.mock
def test_legacy_steering_update_sends_the_declared_flag_values(
    contract_client: NetskopeClient, value: Any
) -> None:
    """Both declared spellings still reach the wire unchanged (:43-52)."""
    route = respx.patch(_NPA_CONFIG_URL).mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )
    contract_client.steering.update_config("npa", settings={"npa_ff": value})
    assert sent_json(route) == {"npa_ff": value}


@respx.mock
def test_get_tunnel_reads_the_result_envelope(example_client: NetskopeClient) -> None:
    """steering/ipsec.yaml:305-317 keys the single-tunnel read under `result`.

    The create (:90-101) and patch (:3-14) responses use `data`; both must decode.
    """
    respx.get(f"{EXAMPLE_BASE}/api/v2/steering/ipsec/tunnels/5").mock(
        return_value=httpx.Response(
            200, json={"result": [{"id": 5, "site": "NYC"}], "status": "success", "total": 1}
        )
    )
    assert example_client.steering.get_tunnel(5).site == "NYC"

    respx.get(f"{EXAMPLE_BASE}/api/v2/steering/ipsec/tunnels/6").mock(
        return_value=httpx.Response(200, json={"data": {"id": 6, "site": "SFO"}})
    )
    assert example_client.steering.get_tunnel(6).site == "SFO"


_GLOBALCONFIG_URL = f"{EXAMPLE_BASE}/api/v2/steering/globalconfig"


@respx.mock
@pytest.mark.parametrize("scope", ["nsc", "ztna"])
def test_steering_rejects_scopes_the_spec_has_no_path_for(
    example_client: NetskopeClient, scope: str
) -> None:
    """npa_global_config.yaml declares six paths, none of them nsc or ztna.

    Spec: /globalconfig (:80), /globalconfig/metadata (:172),
    /globalconfig/clientconfiguration/npa (:218) and its metadata (:307),
    /globalconfig/publishers (:352) and its metadata (:441).
    """
    with pytest.raises(ValidationError, match="npa, publishers"):
        example_client.steering.with_response.get_config(scope)
    assert len(respx.calls) == 0


@respx.mock
def test_steering_keeps_the_two_scopes_the_spec_declares(example_client: NetskopeClient) -> None:
    """npa routes under clientconfiguration (:218); publishers does not (:352)."""
    npa = respx.get(f"{_GLOBALCONFIG_URL}/clientconfiguration/npa").mock(
        return_value=httpx.Response(200, json={"data": {"flag": 1}})
    )
    publishers = respx.get(f"{_GLOBALCONFIG_URL}/publishers").mock(
        return_value=httpx.Response(200, json={"data": {"flag": 0}})
    )
    example_client.steering.get_config("npa")
    example_client.steering.get_config("publishers")

    assert (npa.call_count, publishers.call_count) == (1, 1)


@respx.mock
def test_ipsec_create_accepts_a_bandwidth_outside_the_usual_tiers(
    example_client: NetskopeClient,
) -> None:
    """ipsec_tunnel_request_post puts no enum on bandwidth or encryption.

    Spec: steering/ipsec.yaml:237-238 (``bandwidth: integer``) and :241-242
    (``encryption: string``).  A tenant on a tier outside the usual set could
    not use the SDK at all.
    """
    route = respx.post(f"{EXAMPLE_BASE}/api/v2/steering/ipsec/tunnels").mock(
        return_value=httpx.Response(200, json={"result": {"id": 1, "site": "IPSec site1"}})
    )
    example_client.steering.create_tunnel(
        "IPSec site1",
        ["stl1"],
        "psk",
        "5.NE_2_59f18ccc",
        bandwidth=500,
        encryption="AES192-GCM",
    )

    body = sent_json(route)
    assert body["bandwidth"] == 500
    assert body["encryption"] == "AES192-GCM"
    # The request key is ``enable`` (steering/ipsec.yaml:239-240).
    assert body["enable"] is True


def test_ipsec_request_model_accepts_the_same_range() -> None:
    """The typed path matches the untyped one (steering/ipsec.yaml:237-242)."""
    request = IPSecTunnelCreate(
        site="IPSec site1",
        pops=["stl1"],
        psk="psk",
        srcidentity="5.NE_2_59f18ccc",
        bandwidth=500,
        encryption="AES192-GCM",
    )
    assert (request.bandwidth, request.encryption) == (500, "AES192-GCM")
    with pytest.raises(PydanticValidationError, match="greater than 0"):
        IPSecTunnelCreate(
            site="s", pops=["p"], psk="k", srcidentity="i", bandwidth=0, encryption="x"
        )


def test_ipsec_tunnel_model_reads_the_result_item() -> None:
    """ipsec_tunnel_result_item declares enabled and an array of pop objects.

    Spec: steering/ipsec.yaml:318-379, with pops (:355-358) referencing
    ipsec_tunnel_pop_result_item (:158-183).  The SDK declared name, source_ip,
    destination_ip, status, pop and proto, none of which appear there.
    """
    tunnel = IPSecTunnel.model_validate(
        {
            "bandwidth": 50,
            "enabled": True,
            "encryption": "AES128-CBC",
            "id": 1,
            "notes": "Customer managed site",
            "pops": [{"gateway": "163.116.247.38", "name": "stl1", "primary": True}],
            "site": "IPSec site1",
            "srcidentity": "5.NE_2_59f18ccc",
            "vendor": "Default",
            "version": 2,
        }
    )
    assert (tunnel.id, tunnel.site, tunnel.enabled) == (1, "IPSec site1", True)
    assert tunnel.pops is not None and tunnel.pops[0]["name"] == "stl1"
    for absent in ("name", "source_ip", "destination_ip", "status", "pop", "proto"):
        assert absent not in IPSecTunnel.model_fields


def test_pop_model_reads_the_pop_result_item() -> None:
    """ipsec_pop_result_item has no country and no address list.

    Spec: steering/ipsec.yaml:28-81; ``country`` exists only as a query
    parameter on GET /ipsec/pops (:408-415).
    """
    pop = Pop.model_validate(
        {
            "acceptingtunnels": True,
            "bandwidth": "1000",
            "gateway": "163.116.247.38",
            "id": "1",
            "location": "Saint Louis",
            "name": "stl1",
            "probeip": "10.137.22.216",
            "region": "US",
        }
    )
    assert (pop.name, pop.region, pop.gateway) == ("stl1", "US", "163.116.247.38")
    assert "country" not in Pop.model_fields
    assert "ip_addresses" not in Pop.model_fields
