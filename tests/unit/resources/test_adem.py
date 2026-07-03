"""Tests for client.dem.users (ADEM per-user/per-device telemetry) with mocked HTTP."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.models.dem import AdemApplication, AdemDevice, AdemUserInfo
from netskope.resources.dem import AsyncDemResource, DemResource
from tests.unit.resources.conftest import sent_json

_BASE = "https://t.goskope.com"
_U = f"{_BASE}/api/v2/adem/users"

_START = datetime(2026, 1, 1, tzinfo=UTC)
_END = datetime(2026, 1, 2, tzinfo=UTC)
_START_S = int(_START.timestamp())
_END_S = int(_END.timestamp())


def _dem(client: NetskopeClient) -> DemResource:
    return DemResource(client._transport)


def _adem(aclient: AsyncNetskopeClient) -> AsyncDemResource:
    return AsyncDemResource(aclient._transport)


class TestAdemDevices:
    @respx.mock
    def test_devices_body_and_bare_list(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_U}/device/getlist").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"deviceId": "d1", "deviceName": "Laptop", "deviceOs": "MacOS", "expScore": 88}
                ],
            )
        )
        devices = _dem(client).users.devices("a@b.com", start_time=_START, end_time=_END)
        # Body carries userLocation:[] and epoch-seconds time keys.
        assert sent_json(route) == {
            "starttime": _START_S,
            "endtime": _END_S,
            "user": "a@b.com",
            "userLocation": [],
        }
        assert len(devices) == 1
        assert isinstance(devices[0], AdemDevice)
        assert devices[0].device_id == "d1"
        assert devices[0].exp_score == 88

    @respx.mock
    def test_devices_data_envelope(self, client: NetskopeClient) -> None:
        respx.post(f"{_U}/device/getlist").mock(
            return_value=httpx.Response(200, json={"data": [{"deviceId": "d2"}]})
        )
        devices = _dem(client).users.devices("a@b.com", start_time=_START, end_time=_END)
        assert [d.device_id for d in devices] == ["d2"]

    @respx.mock
    def test_devices_devices_envelope(self, client: NetskopeClient) -> None:
        respx.post(f"{_U}/device/getlist").mock(
            return_value=httpx.Response(200, json={"devices": [{"deviceId": "d3"}]})
        )
        devices = _dem(client).users.devices("a@b.com", start_time=_START, end_time=_END)
        assert [d.device_id for d in devices] == ["d3"]

    @respx.mock
    def test_int_passthrough_seconds(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_U}/device/getlist").mock(return_value=httpx.Response(200, json=[]))
        _dem(client).users.devices("a@b.com", start_time=1710000000, end_time=1710086400)
        body = sent_json(route)
        assert body["starttime"] == 1710000000
        assert body["endtime"] == 1710086400


class TestAdemSimpleEndpoints:
    @respx.mock
    def test_device_details(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_U}/device/getdetails").mock(
            return_value=httpx.Response(200, json={"deviceName": "Laptop"})
        )
        result = _dem(client).users.device_details(
            "a@b.com", "d1", start_time=_START, end_time=_END
        )
        assert sent_json(route) == {
            "starttime": _START_S,
            "endtime": _END_S,
            "user": "a@b.com",
            "deviceId": "d1",
        }
        assert result == {"deviceName": "Laptop"}

    @respx.mock
    def test_info_returns_model(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_U}/getinfo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "user": "a@b.com",
                    "expScore": 72,
                    "lastKnownLocation": "NYC",
                    "organizationUnit": "Eng",
                    "userGroup": "Admins",
                },
            )
        )
        info = _dem(client).users.info("a@b.com", start_time=_START, end_time=_END)
        # No deviceId / userLocation on getinfo.
        assert sent_json(route) == {
            "starttime": _START_S,
            "endtime": _END_S,
            "user": "a@b.com",
        }
        assert isinstance(info, AdemUserInfo)
        assert info.exp_score == 72
        assert info.last_known_location == "NYC"
        assert info.organization_unit == "Eng"
        assert info.user_group == "Admins"

    @respx.mock
    def test_applications_envelope(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_U}/getapplications").mock(
            return_value=httpx.Response(
                200,
                json={
                    "applications": [{"appName": "Gmail", "expScore": 55}],
                    "totalCount": 1,
                },
            )
        )
        apps = _dem(client).users.applications("a@b.com", "d1", start_time=_START, end_time=_END)
        assert sent_json(route)["deviceId"] == "d1"
        assert len(apps) == 1
        assert isinstance(apps[0], AdemApplication)
        assert apps[0].app_name == "Gmail"
        assert apps[0].exp_score == 55

    @respx.mock
    def test_locations_body(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_U}/getlocations").mock(
            return_value=httpx.Response(200, json={"userLocations": []})
        )
        _dem(client).users.locations(start_time=_START, end_time=_END)
        assert sent_json(route) == {"starttime": _START_S, "endtime": _END_S}

    @respx.mock
    def test_aggregated_scores_extra_key(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_U}/device/getaggregatedscores").mock(
            return_value=httpx.Response(200, json={})
        )
        _dem(client).users.aggregated_scores(
            "a@b.com", "d1", start_time=_START, end_time=_END, aggregation_type="p95"
        )
        assert sent_json(route)["aggregationType"] == "p95"

    @respx.mock
    def test_network_metrics_extra_key(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_U}/metrics/getnetwork").mock(
            return_value=httpx.Response(200, json=[])
        )
        _dem(client).users.network_metrics(
            "a@b.com", "d1", start_time=_START, end_time=_END, metric_type="latency"
        )
        assert sent_json(route)["metricType"] == "latency"

    @respx.mock
    def test_exp_score_and_rca_paths(self, client: NetskopeClient) -> None:
        exp = respx.post(f"{_U}/metrics/getexpscore").mock(
            return_value=httpx.Response(200, json=[])
        )
        rca = respx.post(f"{_U}/device/getrca").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        users = _dem(client).users
        users.exp_score("a@b.com", "d1", start_time=_START, end_time=_END)
        users.rca("a@b.com", "d1", start_time=_START, end_time=_END)
        assert exp.called and rca.called

    @respx.mock
    def test_npa_hosts_and_paths(self, client: NetskopeClient) -> None:
        hosts = respx.post(f"{_U}/npa/getnpahosts").mock(
            return_value=httpx.Response(200, json={"npaHosts": []})
        )
        paths = respx.post(f"{_U}/npa/getnetworkpaths").mock(
            return_value=httpx.Response(200, json={"nodes": [], "edges": []})
        )
        users = _dem(client).users
        users.npa_hosts("a@b.com", "d1", start_time=_START, end_time=_END)
        users.npa_network_paths("a@b.com", "d1", "10.0.0.1", start_time=_START, end_time=_END)
        assert hosts.called
        assert sent_json(paths)["npaHost"] == "10.0.0.1"

    @respx.mock
    def test_traceroute_endpoints(self, client: NetskopeClient) -> None:
        ts = respx.post(f"{_U}/device/gettraceroutetimestamps").mock(
            return_value=httpx.Response(200, json=[])
        )
        tr = respx.post(f"{_U}/device/gettraceroute").mock(
            return_value=httpx.Response(200, json={})
        )
        users = _dem(client).users
        users.traceroute_timestamps("a@b.com", "d1", start_time=_START, end_time=_END)
        users.traceroute("a@b.com", "d1", start_time=_START, end_time=_END)
        assert ts.called and tr.called


class TestAdemDiagnose:
    @respx.mock
    def test_diagnose_composition_with_failure(self, client: NetskopeClient) -> None:
        respx.post(f"{_U}/getinfo").mock(
            return_value=httpx.Response(200, json={"user": "a@b.com", "expScore": 70})
        )
        respx.post(f"{_U}/device/getlist").mock(
            return_value=httpx.Response(200, json=[{"deviceId": "d1"}])
        )
        respx.post(f"{_U}/device/getdetails").mock(
            return_value=httpx.Response(200, json={"deviceName": "Laptop"})
        )
        respx.post(f"{_U}/getapplications").mock(
            return_value=httpx.Response(200, json={"applications": [{"appName": "Gmail"}]})
        )
        respx.post(f"{_U}/device/getaggregatedscores").mock(
            return_value=httpx.Response(200, json={"metrics": {"expScore": 70}})
        )
        # This endpoint fails with an HTTP-200 error envelope (transport raises).
        respx.post(f"{_U}/device/getrca").mock(
            return_value=httpx.Response(200, json={"status": "error", "message": "rca boom"})
        )
        diag = _dem(client).users.diagnose("a@b.com", start_time=_START, end_time=_END)

        assert isinstance(diag["user_info"], AdemUserInfo)
        assert diag["user_info"].exp_score == 70
        assert len(diag["devices"]) == 1
        dev = diag["devices"][0]
        assert dev["device_id"] == "d1"
        assert dev["details"] == {"deviceName": "Laptop"}
        assert dev["rca"] is None  # failed call stored as None
        # The failing endpoint is recorded in the errors list.
        assert any(e["endpoint"] == "device/getrca" for e in diag["errors"])

    @respx.mock
    def test_diagnose_application_filter(self, client: NetskopeClient) -> None:
        respx.post(f"{_U}/getinfo").mock(return_value=httpx.Response(200, json={}))
        respx.post(f"{_U}/device/getdetails").mock(return_value=httpx.Response(200, json={}))
        respx.post(f"{_U}/getapplications").mock(
            return_value=httpx.Response(
                200,
                json={"applications": [{"appName": "Gmail"}, {"appName": "Slack"}]},
            )
        )
        respx.post(f"{_U}/device/getaggregatedscores").mock(
            return_value=httpx.Response(200, json={})
        )
        respx.post(f"{_U}/device/getrca").mock(return_value=httpx.Response(200, json={}))
        diag = _dem(client).users.diagnose(
            "a@b.com",
            start_time=_START,
            end_time=_END,
            device_id="d1",
            application="gmail",
        )
        apps = diag["devices"][0]["applications"]
        assert [a.app_name for a in apps] == ["Gmail"]


class TestAdemAsync:
    @respx.mock
    async def test_async_devices(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(f"{_U}/device/getlist").mock(
            return_value=httpx.Response(200, json=[{"deviceId": "d1"}])
        )
        devices = await _adem(aclient).users.devices("a@b.com", start_time=_START, end_time=_END)
        assert sent_json(route)["userLocation"] == []
        assert [d.device_id for d in devices] == ["d1"]

    @respx.mock
    async def test_async_diagnose_gathers_and_records_error(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        respx.post(f"{_U}/getinfo").mock(return_value=httpx.Response(200, json={"user": "a@b.com"}))
        respx.post(f"{_U}/device/getdetails").mock(return_value=httpx.Response(200, json={}))
        respx.post(f"{_U}/getapplications").mock(
            return_value=httpx.Response(200, json={"applications": []})
        )
        respx.post(f"{_U}/device/getaggregatedscores").mock(
            return_value=httpx.Response(200, json={})
        )
        respx.post(f"{_U}/device/getrca").mock(
            return_value=httpx.Response(200, json={"status": "error", "message": "boom"})
        )
        diag = await _adem(aclient).users.diagnose(
            "a@b.com", start_time=_START, end_time=_END, device_id="d1"
        )
        assert diag["devices"][0]["rca"] is None
        assert any(e["endpoint"] == "device/getrca" for e in diag["errors"])
