"""Tests for client.npa.upgrade_profiles with mocked HTTP."""

from __future__ import annotations

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
