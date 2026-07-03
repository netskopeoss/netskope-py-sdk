"""Tests for client.npa.local_brokers with mocked HTTP."""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import NetskopeError, ValidationError
from netskope.models.infrastructure import LocalBroker, LocalBrokerConfig
from tests.unit.resources.conftest import sent_json

_URL = "https://t.goskope.com/api/v2/infrastructure/lbrokers"
_CONFIG_URL = f"{_URL}/brokerconfig"

_BROKER = {
    "id": 10,
    "name": "dc1-broker",
    "common_name": "e2eabac9e9f715ff",
    "registered": True,
    "city_name": "Cupertino",
    "region_name": "CA",
    "country_name": "United States of America",
    "country_code": "US",
    "location_id": "loc-1",
    "latitude": 37.323,
    "longitude": -122.032,
    "discovered_public_ip": "203.0.113.42",
    "discovered_private_ip": "192.168.19.119",
    "custom_public_ip": "203.0.113.43",
    "custom_private_ip": "192.168.19.120",
    "labels": [{"label_id": "867422fb", "permission": "rw"}],
}

# Per the gateway spec, the list envelope is {"data": [...]} — a bare list,
# not a nested "lbrokers" key.
_LIST_BODY = {"data": [_BROKER], "status": "success", "total": 1}

_GET_BODY = {"data": _BROKER, "status": "success"}


class TestLocalBrokersResource:
    """Tests for client.npa.local_brokers (sync)."""

    @respx.mock
    def test_list_extracts_data_list_envelope(self, client: NetskopeClient) -> None:
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        brokers = client.npa.local_brokers.list()
        assert route.called
        assert len(brokers) == 1
        assert isinstance(brokers[0], LocalBroker)
        assert brokers[0].name == "dc1-broker"
        assert brokers[0].city_name == "Cupertino"
        assert brokers[0].latitude == pytest.approx(37.323)

    @respx.mock
    def test_get(self, client: NetskopeClient) -> None:
        respx.get(f"{_URL}/10").mock(return_value=httpx.Response(200, json=_GET_BODY))
        broker = client.npa.local_brokers.get(10)
        assert broker.id == 10
        assert broker.registered is True

    @respx.mock
    def test_create_sends_spec_field_names(self, client: NetskopeClient) -> None:
        """create() must send city_name/region_name/country_name, not city/region/country."""
        route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_GET_BODY))
        broker = client.npa.local_brokers.create(
            "dc1-broker",
            city="Cupertino",
            region="CA",
            country="United States of America",
            country_code="US",
            latitude=37.323,
            longitude=-122.032,
            custom_public_ip="203.0.113.43",
            custom_private_ip="192.168.19.120",
            access_via_public_ip="ON_OFF_PREM",
        )
        assert isinstance(broker, LocalBroker)
        assert sent_json(route) == {
            "name": "dc1-broker",
            "city_name": "Cupertino",
            "region_name": "CA",
            "country_name": "United States of America",
            "country_code": "US",
            "latitude": 37.323,
            "longitude": -122.032,
            "custom_public_ip": "203.0.113.43",
            "custom_private_ip": "192.168.19.120",
            "access_via_public_ip": "ON_OFF_PREM",
        }

    @respx.mock
    def test_create_name_only_sends_sparse_payload(self, client: NetskopeClient) -> None:
        route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_GET_BODY))
        client.npa.local_brokers.create("dc1-broker")
        assert sent_json(route) == {"name": "dc1-broker"}

    @respx.mock
    def test_create_invalid_access_via_public_ip_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError, match="EVERYWHERE"):
            client.npa.local_brokers.create("bad", access_via_public_ip="EVERYWHERE")
        assert len(respx.calls) == 0

    @respx.mock
    def test_update_payload(self, client: NetskopeClient) -> None:
        route = respx.put(f"{_URL}/10").mock(return_value=httpx.Response(200, json=_GET_BODY))
        broker = client.npa.local_brokers.update(
            10, city="Chicago", region="IL", access_via_public_ip="NONE"
        )
        assert isinstance(broker, LocalBroker)
        assert sent_json(route) == {
            "city_name": "Chicago",
            "region_name": "IL",
            "access_via_public_ip": "NONE",
        }

    @respx.mock
    def test_update_invalid_access_via_public_ip_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError, match="access_via_public_ip"):
            client.npa.local_brokers.update(10, access_via_public_ip="on_prem")
        assert len(respx.calls) == 0

    @respx.mock
    def test_delete(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_URL}/10").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        assert client.npa.local_brokers.delete(10) is None
        assert route.called

    @respx.mock
    def test_get_config(self, client: NetskopeClient) -> None:
        respx.get(_CONFIG_URL).mock(
            return_value=httpx.Response(
                200, json={"data": {"hostname": "broker.example.com"}, "status": "success"}
            )
        )
        config = client.npa.local_brokers.get_config()
        assert isinstance(config, LocalBrokerConfig)
        assert config.hostname == "broker.example.com"

    @respx.mock
    def test_update_config_payload(self, client: NetskopeClient) -> None:
        route = respx.put(_CONFIG_URL).mock(
            return_value=httpx.Response(
                200, json={"data": {"hostname": "broker.example.com"}, "status": "success"}
            )
        )
        config = client.npa.local_brokers.update_config("broker.example.com")
        assert config.hostname == "broker.example.com"
        assert sent_json(route) == {"hostname": "broker.example.com"}

    @respx.mock
    def test_create_registration_token(self, client: NetskopeClient) -> None:
        """Token endpoint path has no underscore: .../{id}/registrationtoken."""
        route = respx.post(f"{_URL}/10/registrationtoken").mock(
            return_value=httpx.Response(
                200, json={"data": {"token": "reg-abc123"}, "status": "success"}
            )
        )
        token = client.npa.local_brokers.create_registration_token(10)
        assert token == "reg-abc123"
        assert route.called

    @respx.mock
    def test_create_registration_token_missing_raises(self, client: NetskopeClient) -> None:
        respx.post(f"{_URL}/10/registrationtoken").mock(
            return_value=httpx.Response(200, json={"data": {}, "status": "success"})
        )
        with pytest.raises(NetskopeError, match="token"):
            client.npa.local_brokers.create_registration_token(10)


class TestAsyncLocalBrokersResource:
    """Tests for aclient.npa.local_brokers (async)."""

    @respx.mock
    async def test_list(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        brokers = await aclient.npa.local_brokers.list()
        assert len(brokers) == 1
        assert isinstance(brokers[0], LocalBroker)
        assert brokers[0].country_code == "US"

    @respx.mock
    async def test_get(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_URL}/10").mock(return_value=httpx.Response(200, json=_GET_BODY))
        broker = await aclient.npa.local_brokers.get(10)
        assert broker.id == 10

    @respx.mock
    async def test_create_sends_spec_field_names(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_GET_BODY))
        await aclient.npa.local_brokers.create(
            "dc1-broker", city="Cupertino", access_via_public_ip="OFF_PREM"
        )
        assert sent_json(route) == {
            "name": "dc1-broker",
            "city_name": "Cupertino",
            "access_via_public_ip": "OFF_PREM",
        }

    @respx.mock
    async def test_create_invalid_access_via_public_ip_no_http(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with pytest.raises(ValidationError, match="access_via_public_ip"):
            await aclient.npa.local_brokers.create("bad", access_via_public_ip="ALWAYS")
        assert len(respx.calls) == 0

    @respx.mock
    async def test_update_payload(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.put(f"{_URL}/10").mock(return_value=httpx.Response(200, json=_GET_BODY))
        await aclient.npa.local_brokers.update(10, country_code="GB")
        assert sent_json(route) == {"country_code": "GB"}

    @respx.mock
    async def test_delete(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(f"{_URL}/10").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        await aclient.npa.local_brokers.delete(10)
        assert route.called

    @respx.mock
    async def test_get_config(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_CONFIG_URL).mock(
            return_value=httpx.Response(
                200, json={"data": {"hostname": "broker.example.com"}, "status": "success"}
            )
        )
        config = await aclient.npa.local_brokers.get_config()
        assert config.hostname == "broker.example.com"

    @respx.mock
    async def test_update_config_payload(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.put(_CONFIG_URL).mock(
            return_value=httpx.Response(
                200, json={"data": {"hostname": "new.example.com"}, "status": "success"}
            )
        )
        await aclient.npa.local_brokers.update_config("new.example.com")
        assert sent_json(route) == {"hostname": "new.example.com"}

    @respx.mock
    async def test_create_registration_token(self, aclient: AsyncNetskopeClient) -> None:
        respx.post(f"{_URL}/10/registrationtoken").mock(
            return_value=httpx.Response(
                200, json={"data": {"token": "reg-abc123"}, "status": "success"}
            )
        )
        assert await aclient.npa.local_brokers.create_registration_token(10) == "reg-abc123"

    @respx.mock
    async def test_create_registration_token_missing_raises(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        respx.post(f"{_URL}/10/registrationtoken").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        with pytest.raises(NetskopeError, match="token"):
            await aclient.npa.local_brokers.create_registration_token(10)
