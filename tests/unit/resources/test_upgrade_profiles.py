"""Tests for client.npa.upgrade_profiles with mocked HTTP."""

from __future__ import annotations

import inspect

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.infrastructure import PublisherUpgradeProfile
from tests.unit.resources.conftest import sent_json

_URL = "https://t.goskope.com/api/v2/infrastructure/publisherupgradeprofiles"
_BULK_URL = f"{_URL}/bulk"

_PROFILE = {
    "id": 1,
    "external_id": 5,
    "name": "Weekly Latest",
    "docker_tag": "8691",
    "enabled": True,
    "frequency": "0 0 1 * SAT",
    "timezone": "US/Eastern",
    "timezone_id": 1,
    "release_type": "Latest",
    "num_associated_publisher": 2,
    "next_update_time": 1722052800,
    "upgrading_stage": 1,
    "will_start": False,
    "created_at": "2024-07-23T14:06:32.070000Z",
    "updated_at": "2024-07-23T14:06:32.070000Z",
}

_LIST_BODY = {
    "data": {"upgrade_profiles": [_PROFILE]},
    "status": "success",
    "total": 1,
}

_GET_BODY = {"data": _PROFILE, "status": "success"}


class TestUpgradeProfilesResource:
    """Tests for client.npa.upgrade_profiles (sync)."""

    @respx.mock
    def test_list_extracts_nested_envelope(self, client: NetskopeClient) -> None:
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        profiles = client.npa.upgrade_profiles.list()
        assert route.called
        assert len(profiles) == 1
        assert isinstance(profiles[0], PublisherUpgradeProfile)
        assert profiles[0].name == "Weekly Latest"
        assert profiles[0].external_id == 5
        assert profiles[0].next_update_time == 1722052800

    @respx.mock
    def test_get(self, client: NetskopeClient) -> None:
        respx.get(f"{_URL}/5").mock(return_value=httpx.Response(200, json=_GET_BODY))
        profile = client.npa.upgrade_profiles.get(5)
        assert profile.external_id == 5
        assert profile.docker_tag == "8691"

    @respx.mock
    def test_create_payload(self, client: NetskopeClient) -> None:
        route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_GET_BODY))
        profile = client.npa.upgrade_profiles.create(
            "Weekly Latest",
            docker_tag="8691",
            frequency="0 0 1 * SAT",
            timezone="US/Eastern",
            release_type="Latest",
        )
        assert isinstance(profile, PublisherUpgradeProfile)
        assert sent_json(route) == {
            "name": "Weekly Latest",
            "enabled": True,
            "docker_tag": "8691",
            "frequency": "0 0 1 * SAT",
            "timezone": "US/Eastern",
            "release_type": "Latest",
        }

    @respx.mock
    def test_create_disabled(self, client: NetskopeClient) -> None:
        route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_GET_BODY))
        client.npa.upgrade_profiles.create(
            "Off",
            docker_tag="8691",
            frequency="0 3 * * *",
            timezone="US/Pacific",
            release_type="Latest-1",
            enabled=False,
        )
        body = sent_json(route)
        assert body["enabled"] is False
        assert body["release_type"] == "Latest-1"

    @respx.mock
    def test_create_invalid_release_type_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError, match="Stable"):
            client.npa.upgrade_profiles.create(
                "Bad",
                docker_tag="8691",
                frequency="0 3 * * *",
                timezone="US/Pacific",
                release_type="Stable",
            )
        assert len(respx.calls) == 0

    @respx.mock
    def test_update_merges_current_profile(self, client: NetskopeClient) -> None:
        """update() must GET the profile first and PUT the full merged body."""
        get_route = respx.get(f"{_URL}/5").mock(return_value=httpx.Response(200, json=_GET_BODY))
        put_route = respx.put(f"{_URL}/5").mock(return_value=httpx.Response(200, json=_GET_BODY))
        client.npa.upgrade_profiles.update(5, name="Renamed", enabled=False)
        assert get_route.called
        assert sent_json(put_route) == {
            "id": 5,
            "name": "Renamed",
            "enabled": False,
            "docker_tag": "8691",
            "frequency": "0 0 1 * SAT",
            "timezone": "US/Eastern",
            "release_type": "Latest",
        }

    @respx.mock
    def test_update_invalid_release_type_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError, match="release_type"):
            client.npa.upgrade_profiles.update(5, release_type="GA")
        assert len(respx.calls) == 0

    @respx.mock
    def test_delete(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_URL}/5").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        assert client.npa.upgrade_profiles.delete(5) is None
        assert route.called

    @respx.mock
    def test_assign_sends_string_ids(self, client: NetskopeClient) -> None:
        """assign() must stringify the profile id and every publisher id."""
        route = respx.put(_BULK_URL).mock(
            return_value=httpx.Response(200, json={"status": "success", "total": 3})
        )
        result = client.npa.upgrade_profiles.assign(5, [10, 20, 30])
        assert result == {"status": "success", "total": 3}
        assert sent_json(route) == {
            "publishers": {
                "apply": {"publisher_upgrade_profiles_id": "5"},
                "id": ["10", "20", "30"],
            }
        }


class TestAsyncUpgradeProfilesResource:
    """Tests for aclient.npa.upgrade_profiles (async)."""

    @respx.mock
    async def test_list(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        profiles = await aclient.npa.upgrade_profiles.list()
        assert len(profiles) == 1
        assert isinstance(profiles[0], PublisherUpgradeProfile)
        assert profiles[0].release_type == "Latest"

    @respx.mock
    async def test_get(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_URL}/5").mock(return_value=httpx.Response(200, json=_GET_BODY))
        profile = await aclient.npa.upgrade_profiles.get(5)
        assert profile.external_id == 5

    @respx.mock
    async def test_create_payload(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_GET_BODY))
        await aclient.npa.upgrade_profiles.create(
            "Weekly Latest",
            docker_tag="8691",
            frequency="0 0 1 * SAT",
            timezone="US/Eastern",
            release_type="Latest",
        )
        assert sent_json(route) == {
            "name": "Weekly Latest",
            "enabled": True,
            "docker_tag": "8691",
            "frequency": "0 0 1 * SAT",
            "timezone": "US/Eastern",
            "release_type": "Latest",
        }

    @respx.mock
    async def test_create_invalid_release_type_no_http(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError, match="release_type"):
            await aclient.npa.upgrade_profiles.create(
                "Bad",
                docker_tag="8691",
                frequency="0 3 * * *",
                timezone="US/Pacific",
                release_type="nightly",
            )
        assert len(respx.calls) == 0

    @respx.mock
    async def test_update_merges_current_profile(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_URL}/5").mock(return_value=httpx.Response(200, json=_GET_BODY))
        put_route = respx.put(f"{_URL}/5").mock(return_value=httpx.Response(200, json=_GET_BODY))
        await aclient.npa.upgrade_profiles.update(5, docker_tag="8700")
        assert sent_json(put_route) == {
            "id": 5,
            "name": "Weekly Latest",
            "enabled": True,
            "docker_tag": "8700",
            "frequency": "0 0 1 * SAT",
            "timezone": "US/Eastern",
            "release_type": "Latest",
        }

    @respx.mock
    async def test_delete(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(f"{_URL}/5").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        await aclient.npa.upgrade_profiles.delete(5)
        assert route.called

    @respx.mock
    async def test_assign_sends_string_ids(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.put(_BULK_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        await aclient.npa.upgrade_profiles.assign(7, [1])
        assert sent_json(route) == {
            "publishers": {
                "apply": {"publisher_upgrade_profiles_id": "7"},
                "id": ["1"],
            }
        }


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_typed_assign_reads_the_declared_envelope(
    client: NetskopeClient,
    aclient: AsyncNetskopeClient,
    asynchronous: bool,
) -> None:
    """``publisher_upgrade_profile_bulk_response`` is ``{data.publishers, status, total}``.

    Spec: npa_upgrade_profiles.yaml:186-205, whose ``data.publishers`` items are
    ``upgrade_publisher_response`` (:11-147).  Descending into ``data`` before
    validating put the publisher records out of reach of the declared type.
    """
    body = {
        "data": {"publishers": [{"id": 10, "name": "pub10"}, {"id": 20, "name": "pub20"}]},
        "status": "success",
        "total": 2,
    }
    route = respx.put(_BULK_URL).mock(return_value=httpx.Response(200, json=body))
    profiles = (aclient if asynchronous else client).npa.upgrade_profiles.with_response
    response = profiles.assign(5, [10])
    if inspect.isawaitable(response):
        response = await response
    assignment = response.parse()

    assert (assignment.status, assignment.total) == ("success", 2)
    assert [pub.publisher_id for pub in assignment.publishers] == [10, 20]
    assert [pub.publisher_name for pub in assignment.publishers] == ["pub10", "pub20"]
    assert response.json() == body
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_typed_assign_accepts_a_status_only_envelope(
    client: NetskopeClient,
    aclient: AsyncNetskopeClient,
    asynchronous: bool,
) -> None:
    """Every property of the envelope is optional, so a bare status still parses."""
    route = respx.put(_BULK_URL).mock(return_value=httpx.Response(200, json={"status": "success"}))
    profiles = (aclient if asynchronous else client).npa.upgrade_profiles.with_response
    response = profiles.assign(5, [10])
    if inspect.isawaitable(response):
        response = await response
    assignment = response.parse()

    assert assignment.status == "success"
    assert assignment.publishers == []
    assert assignment.total is None
    assert route.call_count == 1


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    "profile_id,publisher_ids",
    [(5, []), (5, ["../bulk"]), ("../bulk", [10])],
    ids=["no-publishers", "unsafe-publisher", "unsafe-profile"],
)
@respx.mock
async def test_assign_rejects_empty_or_unsafe_identifiers(
    client: NetskopeClient,
    aclient: AsyncNetskopeClient,
    asynchronous: bool,
    typed: bool,
    profile_id,
    publisher_ids,
) -> None:
    sdk = aclient if asynchronous else client
    profiles = sdk.npa.upgrade_profiles
    resource = profiles.with_response if typed else profiles
    with pytest.raises(ValidationError):
        result = resource.assign(profile_id, publisher_ids)
        if inspect.isawaitable(result):
            await result
    assert len(respx.calls) == 0
