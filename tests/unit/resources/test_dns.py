"""Tests for the DNS Security profiles resource with mocked HTTP.

``client.dns`` is not wired into the clients yet, so the resources are
instantiated directly against the client transports.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.dns import DnsInheritanceGroup, DnsProfile
from netskope.resources.dns import AsyncDnsResource, DnsResource
from tests.unit.resources.conftest import sent_json

_URL = "https://t.goskope.com/api/v2/profiles/dns"
_GROUPS_URL = f"{_URL}/inheritancegroups"

# Live-verified: profile ids are UUID strings, log_traffic is a string enum.
_PROFILE_UUID = "7b3b9c98-7718-11f1-a1b2-c3d4e5f60789"
_PROFILE = {
    "id": _PROFILE_UUID,
    "name": "Default",
    "description": "Default profile",
    "log_traffic": "Blocked DNS",
}


class TestDnsResource:
    """Sync tests for the DNS profiles resource."""

    @respx.mock
    def test_list_url_params_and_profiles_envelope(self, client: NetskopeClient) -> None:
        """list() GETs the base path; live responses use a {"profiles": [...]} envelope."""
        empty = httpx.Response(200, json={"total": 1, "profiles": []})
        route = respx.get(_URL).mock(
            side_effect=[
                httpx.Response(200, json={"total": 1, "profiles": [_PROFILE]}),
                empty,
                empty,
            ]
        )
        dns = DnsResource(client._transport)
        profiles = list(dns.list(filter_expr="name eq 'Default'", sort_by="name", sort_order="asc"))

        assert len(profiles) == 1
        assert isinstance(profiles[0], DnsProfile)
        assert profiles[0].id == _PROFILE_UUID
        assert profiles[0].name == "Default"
        assert profiles[0].log_traffic == "Blocked DNS"

        params = route.calls[0].request.url.params
        assert params["filter"] == "name eq 'Default'"
        assert params["sortby"] == "name"
        assert params["sortorder"] == "asc"
        assert params["limit"] == "100"
        assert params["offset"] == "0"

    @respx.mock
    def test_list_clamps_page_size_to_100(self, client: NetskopeClient) -> None:
        """The API rejects limit > 150; oversized page sizes are clamped to 100."""
        route = respx.get(_URL).mock(
            return_value=httpx.Response(200, json={"total": 0, "profiles": []})
        )
        DnsResource(client._transport).list(page_size=500).to_list(max_items=5)
        assert route.calls.last.request.url.params["limit"] == "100"

    @respx.mock
    def test_list_data_envelope_still_supported(self, client: NetskopeClient) -> None:
        respx.get(_URL).mock(
            side_effect=[
                httpx.Response(200, json={"data": [_PROFILE]}),
                httpx.Response(200, json={"data": []}),
                httpx.Response(200, json={"data": []}),
            ]
        )
        profiles = list(DnsResource(client._transport).list())
        assert len(profiles) == 1
        assert profiles[0].id == _PROFILE_UUID

    @respx.mock
    def test_get_by_uuid_top_level_body(self, client: NetskopeClient) -> None:
        """get() accepts UUID string ids and tolerates envelope-less bodies."""
        respx.get(f"{_URL}/{_PROFILE_UUID}").mock(return_value=httpx.Response(200, json=_PROFILE))
        profile = DnsResource(client._transport).get(_PROFILE_UUID)
        assert profile.id == _PROFILE_UUID
        assert profile.name == "Default"

    @respx.mock
    def test_create_sends_name_body_and_parses_top_level_response(
        self, client: NetskopeClient
    ) -> None:
        """Create returns the profile at the TOP LEVEL (no envelope), with UUID id."""
        route = respx.post(_URL).mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": _PROFILE_UUID,
                    "name": "New Profile",
                    "log_traffic": "Blocked DNS",
                },
            )
        )
        profile = DnsResource(client._transport).create("New Profile")

        assert sent_json(route) == {"name": "New Profile"}
        assert profile.id == _PROFILE_UUID
        assert profile.name == "New Profile"
        assert profile.log_traffic == "Blocked DNS"

    @respx.mock
    def test_update_sends_only_set_fields(self, client: NetskopeClient) -> None:
        route = respx.patch(f"{_URL}/42").mock(
            return_value=httpx.Response(
                200, json={"data": {"id": 42, "name": "Corp", "description": "Updated"}}
            )
        )
        profile = DnsResource(client._transport).update(
            42, description="Updated", log_traffic=False
        )

        assert sent_json(route) == {"description": "Updated", "log_traffic": False}
        assert profile.description == "Updated"

    @respx.mock
    def test_update_no_fields_raises_without_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            DnsResource(client._transport).update(42)

    @respx.mock
    def test_delete(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_URL}/42").mock(return_value=httpx.Response(200, json={}))
        DnsResource(client._transport).delete(42)  # Should not raise
        assert route.called

    @respx.mock
    def test_deploy_all_payload(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_URL}/deploy").mock(
            return_value=httpx.Response(200, json={"status": "deployed"})
        )
        result = DnsResource(client._transport).deploy(all=True, change_note="CHG-1")

        assert sent_json(route) == {"all": True, "change_note": "CHG-1"}
        assert result["status"] == "deployed"

    @respx.mock
    def test_deploy_ids_payload(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_URL}/deploy").mock(
            return_value=httpx.Response(200, json={"status": "deployed"})
        )
        DnsResource(client._transport).deploy(ids=[1, 5, 12])

        assert sent_json(route) == {"ids": [1, 5, 12]}

    @respx.mock
    def test_deploy_xor_validation_no_http(self, client: NetskopeClient) -> None:
        """Neither or both of all/ids must raise before any HTTP request."""
        dns = DnsResource(client._transport)
        with pytest.raises(ValidationError):
            dns.deploy()
        with pytest.raises(ValidationError):
            dns.deploy(all=True, ids=[1])

    @respx.mock
    def test_reference_lookups(self, client: NetskopeClient) -> None:
        tunnels_route = respx.get(f"{_URL}/tunnels").mock(
            return_value=httpx.Response(200, json={"data": [{"name": "us-west"}]})
        )
        categories_route = respx.get(f"{_URL}/domaincategories").mock(
            return_value=httpx.Response(200, json={"data": [{"name": "Malware"}]})
        )
        record_types_route = respx.get(f"{_URL}/recordtypes").mock(
            return_value=httpx.Response(200, json={"data": [{"name": "MX"}]})
        )
        dns = DnsResource(client._transport)

        tunnels = dns.list_tunnels(filter_expr="name eq 'us-west'", limit=10, offset=5)
        assert tunnels["data"][0]["name"] == "us-west"
        params = tunnels_route.calls.last.request.url.params
        assert params["filter"] == "name eq 'us-west'"
        assert params["limit"] == "10"
        assert params["offset"] == "5"

        categories = dns.list_domain_categories(limit=20)
        assert categories["data"][0]["name"] == "Malware"
        assert categories_route.calls.last.request.url.params["limit"] == "20"

        record_types = dns.list_record_types()
        assert record_types["data"][0]["name"] == "MX"
        assert "limit" not in record_types_route.calls.last.request.url.params


class TestDnsInheritanceGroupsResource:
    """Sync tests for the inheritance groups sub-resource."""

    @respx.mock
    def test_list_url_and_inheritancegroups_envelope(self, client: NetskopeClient) -> None:
        """List responses use an {"inheritancegroups": [...]} envelope with UUID ids."""
        group_uuid = "647c581b-b779-4770-8b73-aeece0742252"
        empty = httpx.Response(200, json={"total": 1, "inheritancegroups": []})
        respx.get(_GROUPS_URL).mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "total": 1,
                        "inheritancegroups": [{"id": group_uuid, "name": "HQ Group"}],
                    },
                ),
                empty,
                empty,
            ]
        )
        groups = list(DnsResource(client._transport).inheritance_groups.list())
        assert len(groups) == 1
        assert isinstance(groups[0], DnsInheritanceGroup)
        assert groups[0].id == group_uuid
        assert groups[0].name == "HQ Group"

    @respx.mock
    def test_list_clamps_page_size_to_100(self, client: NetskopeClient) -> None:
        route = respx.get(_GROUPS_URL).mock(
            return_value=httpx.Response(200, json={"total": 0, "inheritancegroups": []})
        )
        DnsResource(client._transport).inheritance_groups.list(page_size=151).to_list(max_items=5)
        assert route.calls.last.request.url.params["limit"] == "100"

    @respx.mock
    def test_get(self, client: NetskopeClient) -> None:
        respx.get(f"{_GROUPS_URL}/7").mock(
            return_value=httpx.Response(200, json={"data": {"id": 7, "name": "EMEA"}})
        )
        group = DnsResource(client._transport).inheritance_groups.get(7)
        assert group.id == 7

    @respx.mock
    def test_create_sends_name_body(self, client: NetskopeClient) -> None:
        route = respx.post(_GROUPS_URL).mock(
            return_value=httpx.Response(201, json={"data": {"id": 9, "name": "Dev Team"}})
        )
        group = DnsResource(client._transport).inheritance_groups.create("Dev Team")
        assert sent_json(route) == {"name": "Dev Team"}
        assert group.id == 9

    @respx.mock
    def test_update_sends_only_set_fields(self, client: NetskopeClient) -> None:
        route = respx.patch(f"{_GROUPS_URL}/7").mock(
            return_value=httpx.Response(200, json={"data": {"id": 7, "name": "Renamed"}})
        )
        group = DnsResource(client._transport).inheritance_groups.update(7, name="Renamed")
        assert sent_json(route) == {"name": "Renamed"}
        assert group.name == "Renamed"

    @respx.mock
    def test_update_no_fields_raises_without_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            DnsResource(client._transport).inheritance_groups.update(7)

    @respx.mock
    def test_delete(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_GROUPS_URL}/7").mock(return_value=httpx.Response(200, json={}))
        DnsResource(client._transport).inheritance_groups.delete(7)
        assert route.called

    @respx.mock
    def test_deploy_payload_and_xor(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_GROUPS_URL}/deploy").mock(
            return_value=httpx.Response(200, json={"status": "deployed"})
        )
        groups = DnsResource(client._transport).inheritance_groups
        groups.deploy(ids=[2, 7], change_note="CHG-2")
        assert sent_json(route) == {"ids": [2, 7], "change_note": "CHG-2"}

        with pytest.raises(ValidationError):
            groups.deploy()
        with pytest.raises(ValidationError):
            groups.deploy(all=True, ids=[2])
        assert route.call_count == 1


class TestAsyncDnsResource:
    """Async tests mirroring the sync coverage."""

    @respx.mock
    async def test_list_url_params_and_extraction(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_URL).mock(
            return_value=httpx.Response(
                200,
                json={"profiles": [_PROFILE], "status": {"total": 1}},
            )
        )
        dns = AsyncDnsResource(aclient._transport)
        profiles = [p async for p in dns.list(sort_by="name", sort_order="desc")]

        assert len(profiles) == 1
        assert isinstance(profiles[0], DnsProfile)
        assert profiles[0].id == _PROFILE_UUID
        assert profiles[0].log_traffic == "Blocked DNS"
        params = route.calls.last.request.url.params
        assert params["sortby"] == "name"
        assert params["sortorder"] == "desc"

    @respx.mock
    async def test_list_clamps_page_size(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_URL).mock(
            return_value=httpx.Response(200, json={"total": 0, "profiles": []})
        )
        await AsyncDnsResource(aclient._transport).list(page_size=200).to_list(max_items=5)
        assert route.calls.last.request.url.params["limit"] == "100"

    @respx.mock
    async def test_get(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_URL}/{_PROFILE_UUID}").mock(return_value=httpx.Response(200, json=_PROFILE))
        profile = await AsyncDnsResource(aclient._transport).get(_PROFILE_UUID)
        assert profile.id == _PROFILE_UUID

    @respx.mock
    async def test_create_sends_name_body(self, aclient: AsyncNetskopeClient) -> None:
        """Create responses arrive at the top level with a UUID string id."""
        route = respx.post(_URL).mock(
            return_value=httpx.Response(
                201, json={"id": _PROFILE_UUID, "name": "New", "log_traffic": "All DNS"}
            )
        )
        profile = await AsyncDnsResource(aclient._transport).create("New")
        assert sent_json(route) == {"name": "New"}
        assert profile.id == _PROFILE_UUID
        assert profile.log_traffic == "All DNS"

    @respx.mock
    async def test_update_sends_only_set_fields(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.patch(f"{_URL}/42").mock(
            return_value=httpx.Response(200, json={"data": {"id": 42, "name": "Renamed"}})
        )
        await AsyncDnsResource(aclient._transport).update(42, name="Renamed")
        assert sent_json(route) == {"name": "Renamed"}

    @respx.mock
    async def test_delete(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(f"{_URL}/42").mock(return_value=httpx.Response(200, json={}))
        await AsyncDnsResource(aclient._transport).delete(42)
        assert route.called

    @respx.mock
    async def test_deploy_payload_and_xor_no_http(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(f"{_URL}/deploy").mock(
            return_value=httpx.Response(200, json={"status": "deployed"})
        )
        dns = AsyncDnsResource(aclient._transport)
        await dns.deploy(all=True)
        assert sent_json(route) == {"all": True}

        with pytest.raises(ValidationError):
            await dns.deploy()
        with pytest.raises(ValidationError):
            await dns.deploy(all=True, ids=[1])
        assert route.call_count == 1

    @respx.mock
    async def test_reference_lookups(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_URL}/tunnels").mock(return_value=httpx.Response(200, json={"data": []}))
        respx.get(f"{_URL}/domaincategories").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        respx.get(f"{_URL}/recordtypes").mock(return_value=httpx.Response(200, json={"data": []}))
        dns = AsyncDnsResource(aclient._transport)
        assert (await dns.list_tunnels())["data"] == []
        assert (await dns.list_domain_categories())["data"] == []
        assert (await dns.list_record_types())["data"] == []

    @respx.mock
    async def test_inheritance_groups_roundtrip(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_GROUPS_URL).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": 2, "name": "HQ"}], "status": {"total": 1}}
            )
        )
        respx.get(f"{_GROUPS_URL}/2").mock(
            return_value=httpx.Response(200, json={"data": {"id": 2, "name": "HQ"}})
        )
        create_route = respx.post(_GROUPS_URL).mock(
            return_value=httpx.Response(201, json={"data": {"id": 9, "name": "Dev"}})
        )
        update_route = respx.patch(f"{_GROUPS_URL}/9").mock(
            return_value=httpx.Response(200, json={"data": {"id": 9, "description": "x"}})
        )
        respx.delete(f"{_GROUPS_URL}/9").mock(return_value=httpx.Response(200, json={}))
        deploy_route = respx.post(f"{_GROUPS_URL}/deploy").mock(
            return_value=httpx.Response(200, json={"status": "deployed"})
        )

        groups = AsyncDnsResource(aclient._transport).inheritance_groups
        listed = [g async for g in groups.list()]
        assert isinstance(listed[0], DnsInheritanceGroup)
        assert (await groups.get(2)).id == 2

        created = await groups.create("Dev")
        assert sent_json(create_route) == {"name": "Dev"}
        assert created.id == 9

        await groups.update(9, description="x")
        assert sent_json(update_route) == {"description": "x"}
        with pytest.raises(ValidationError):
            await groups.update(9)

        await groups.delete(9)

        await groups.deploy(all=True)
        assert sent_json(deploy_route) == {"all": True}
        with pytest.raises(ValidationError):
            await groups.deploy()
