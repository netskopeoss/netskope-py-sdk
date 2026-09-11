"""R3S-C7: the DEM methods that no test executed.

Thirty public methods on ``netskope.resources.dem`` — mostly async mirrors of
tested sync ones, plus four sync probe/alert-rule methods — shipped without
running under ``tests/unit``.  Payload shapes mirror the sync tests in
``test_dem.py`` and ``test_adem.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.models.dem import DemAlert, DemQueryResult
from tests.unit.resources.conftest import sent_json

_BASE = "https://t.goskope.com"
_APPPROBES = f"{_BASE}/api/v2/dem/appprobes"
_NETWORKPROBES = f"{_BASE}/api/v2/dem/networkprobes"
_ALERT_RULES = f"{_BASE}/api/v2/dem/alert/rules"
_ALERTS = f"{_BASE}/api/v2/dem/alerts"
_APPS = f"{_BASE}/api/v2/dem/apps"
_GETDATASET = f"{_BASE}/api/v2/dem/query/getdataset"
_GETTRACEROUTE = f"{_BASE}/api/v2/dem/query/gettraceroute"
_DEFINITIONS = f"{_BASE}/api/v2/dem/query/definitions"
_ADEM = f"{_BASE}/api/v2/adem/users"

# Fixed datetimes — never call datetime.now() in tests.
_BEGIN = datetime(2026, 1, 1, tzinfo=UTC)
_END = datetime(2026, 1, 2, tzinfo=UTC)
_BEGIN_MS = int(_BEGIN.timestamp() * 1000)
_END_MS = int(_END.timestamp() * 1000)
_BEGIN_S = int(_BEGIN.timestamp())
_END_S = int(_END.timestamp())

_PROBE = {"data": {"id": "p1", "name": "probe-1", "target": "https://example.com"}}
_RULE = {"data": {"id": "r1", "name": "latency-rule", "metric": "latency", "threshold": 200}}


class TestSyncProbeAndRuleReadsWrites:
    """The four sync methods C7 listed, all id-in-path operations."""

    @respx.mock
    def test_network_probe_get(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_NETWORKPROBES}/7").mock(return_value=httpx.Response(200, json=_PROBE))
        assert client.dem.network_probes.get(7) == _PROBE
        assert route.calls.last.request.url.path == "/api/v2/dem/networkprobes/7"

    @respx.mock
    def test_network_probe_update_sends_the_raw_body(self, client: NetskopeClient) -> None:
        route = respx.put(f"{_NETWORKPROBES}/7").mock(return_value=httpx.Response(200, json=_PROBE))
        client.dem.network_probes.update(7, {"enabled": False})
        assert route.calls.last.request.method == "PUT"
        assert sent_json(route) == {"enabled": False}

    @respx.mock
    def test_alert_rule_get_quotes_the_id(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_ALERT_RULES}/id%3Av1").mock(
            return_value=httpx.Response(200, json=_RULE)
        )
        assert client.dem.alert_rules.get("id:v1") == _RULE
        assert route.calls.last.request.url.raw_path.endswith(b"/id%3Av1")

    @respx.mock
    def test_alert_rule_update_sends_the_raw_body(self, client: NetskopeClient) -> None:
        route = respx.put(f"{_ALERT_RULES}/r1").mock(return_value=httpx.Response(200, json=_RULE))
        client.dem.alert_rules.update("r1", {"threshold": 300})
        assert sent_json(route) == {"threshold": 300}


class TestAsyncProbes:
    @respx.mock
    async def test_list_sends_params(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_APPPROBES).mock(
            return_value=httpx.Response(200, json={"totalCount": 0, "data": []})
        )
        await aclient.dem.probes.list(limit=10, offset=5)
        assert dict(route.calls.last.request.url.params) == {"limit": "10", "offset": "5"}

    @respx.mock
    async def test_list_without_params(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_APPPROBES).mock(return_value=httpx.Response(200, json={"data": []}))
        await aclient.dem.probes.list()
        assert not route.calls.last.request.url.params

    @respx.mock
    async def test_get(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_APPPROBES}/p1").mock(return_value=httpx.Response(200, json=_PROBE))
        assert await aclient.dem.probes.get("p1") == _PROBE

    @respx.mock
    async def test_update(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.put(f"{_APPPROBES}/p1").mock(return_value=httpx.Response(200, json=_PROBE))
        await aclient.dem.probes.update("p1", {"interval": 60})
        assert sent_json(route) == {"interval": 60}

    @respx.mock
    async def test_delete(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(f"{_APPPROBES}/p1").mock(return_value=httpx.Response(204))
        assert await aclient.dem.probes.delete("p1") is None
        assert route.called


class TestAsyncNetworkProbes:
    @respx.mock
    async def test_list_sends_params(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_NETWORKPROBES).mock(return_value=httpx.Response(200, json={"data": []}))
        await aclient.dem.network_probes.list(limit=2, offset=0)
        assert dict(route.calls.last.request.url.params) == {"limit": "2", "offset": "0"}

    @respx.mock
    async def test_get(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_NETWORKPROBES}/7").mock(return_value=httpx.Response(200, json=_PROBE))
        assert await aclient.dem.network_probes.get(7) == _PROBE

    @respx.mock
    async def test_update(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.put(f"{_NETWORKPROBES}/7").mock(return_value=httpx.Response(200, json=_PROBE))
        await aclient.dem.network_probes.update(7, {"enabled": True})
        assert sent_json(route) == {"enabled": True}

    @respx.mock
    async def test_delete(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(f"{_NETWORKPROBES}/7").mock(return_value=httpx.Response(204))
        assert await aclient.dem.network_probes.delete(7) is None
        assert route.called


class TestAsyncAlertRules:
    @respx.mock
    async def test_list_sends_params(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_ALERT_RULES).mock(return_value=httpx.Response(200, json={"data": []}))
        await aclient.dem.alert_rules.list(limit=5, offset=10)
        assert dict(route.calls.last.request.url.params) == {"limit": "5", "offset": "10"}

    @respx.mock
    async def test_create_wraps_the_body_in_data(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_ALERT_RULES).mock(return_value=httpx.Response(201, json=_RULE))
        await aclient.dem.alert_rules.create(
            "latency-rule", "latency", 200, severity="high", probe_id="p1"
        )
        assert sent_json(route) == {
            "data": {
                "name": "latency-rule",
                "metric": "latency",
                "threshold": 200,
                "severity": "high",
                "probe_id": "p1",
            }
        }

    @respx.mock
    async def test_get(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_ALERT_RULES}/r1").mock(return_value=httpx.Response(200, json=_RULE))
        assert await aclient.dem.alert_rules.get("r1") == _RULE

    @respx.mock
    async def test_update(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.put(f"{_ALERT_RULES}/r1").mock(return_value=httpx.Response(200, json=_RULE))
        await aclient.dem.alert_rules.update("r1", {"severity": "low"})
        assert sent_json(route) == {"severity": "low"}

    @respx.mock
    async def test_delete(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(f"{_ALERT_RULES}/r1").mock(return_value=httpx.Response(204))
        assert await aclient.dem.alert_rules.delete("r1") is None
        assert route.called


class TestAsyncQuery:
    @respx.mock
    async def test_get_dataset_parses_the_typed_result(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_GETDATASET).mock(
            return_value=httpx.Response(200, json={"data": [{"user": "a@b.com"}]})
        )
        result = await aclient.dem.query.get_dataset("http_all", ["user"], begin=_BEGIN, end=_END)
        assert sent_json(route) == {
            "from": "http_all",
            "select": ["user"],
            "begin": _BEGIN_MS,
            "end": _END_MS,
        }
        assert isinstance(result, DemQueryResult)
        assert result.data[0].root == {"user": "a@b.com"}

    @respx.mock
    async def test_get_traceroute_sends_epoch_milliseconds(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        route = respx.post(_GETTRACEROUTE).mock(return_value=httpx.Response(200, json={}))
        await aclient.dem.query.get_traceroute("traceroute_pop", begin=_BEGIN, end=_END)
        body = sent_json(route)
        assert body == {"from": "traceroute_pop", "begin": _BEGIN_MS, "end": _END_MS}
        assert "limit" not in body

    @respx.mock
    async def test_definitions_with_and_without_a_source(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        route = respx.get(_DEFINITIONS).mock(return_value=httpx.Response(200, json={}))
        await aclient.dem.query.definitions(source="rum_steered")
        assert dict(route.calls.last.request.url.params) == {"source": "rum_steered"}
        await aclient.dem.query.definitions()
        assert not route.calls.last.request.url.params


class TestAsyncAlerts:
    @respx.mock
    async def test_get_quotes_the_alert_id(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(f"{_ALERTS}/id%3Av1").mock(
            return_value=httpx.Response(200, json={"_id": "id:v1", "severity": "low"})
        )
        alert = await aclient.dem.alerts.get("id:v1")
        assert route.called
        assert isinstance(alert, DemAlert)
        assert alert.id == "id:v1"

    @respx.mock
    async def test_entities_query_params(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(f"{_ALERTS}/a1/entities").mock(return_value=httpx.Response(200, json={}))
        await aclient.dem.alerts.entities(
            "a1", limit=25, offset=0, sort_by="user", sort_order="asc"
        )
        assert dict(route.calls.last.request.url.params) == {
            "limit": "25",
            "offset": "0",
            "sortby": "user",
            "sortorder": "asc",
        }


class TestAsyncApps:
    @respx.mock
    async def test_list_sends_type_and_name(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_APPS).mock(
            return_value=httpx.Response(200, json={"totalCount": 0, "data": []})
        )
        await aclient.dem.apps.list(app_type="custom", name="crm", limit=10, offset=0)
        assert dict(route.calls.last.request.url.params) == {
            "type": "custom",
            "name": "crm",
            "limit": "10",
            "offset": "0",
        }

    @respx.mock
    async def test_list_without_filters(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_APPS).mock(return_value=httpx.Response(200, json={"data": []}))
        await aclient.dem.apps.list()
        assert not route.calls.last.request.url.params


class TestAsyncAdemUsers:
    """The ADEM async mirrors; all bodies carry epoch-second time keys."""

    @respx.mock
    async def test_locations(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(f"{_ADEM}/getlocations").mock(
            return_value=httpx.Response(200, json={"userLocations": []})
        )
        await aclient.dem.users.locations(start_time=_BEGIN, end_time=_END)
        assert sent_json(route) == {"starttime": _BEGIN_S, "endtime": _END_S}

    @respx.mock
    async def test_exp_score(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(f"{_ADEM}/metrics/getexpscore").mock(
            return_value=httpx.Response(200, json=[])
        )
        await aclient.dem.users.exp_score("a@b.com", "d1", start_time=_BEGIN, end_time=_END)
        assert sent_json(route) == {
            "starttime": _BEGIN_S,
            "endtime": _END_S,
            "user": "a@b.com",
            "deviceId": "d1",
        }

    @respx.mock
    async def test_network_metrics_carries_the_metric_type(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        route = respx.post(f"{_ADEM}/metrics/getnetwork").mock(
            return_value=httpx.Response(200, json=[])
        )
        await aclient.dem.users.network_metrics(
            "a@b.com", "d1", start_time=_BEGIN, end_time=_END, metric_type="latency"
        )
        assert sent_json(route)["metricType"] == "latency"

    @respx.mock
    async def test_npa_hosts(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(f"{_ADEM}/npa/getnpahosts").mock(
            return_value=httpx.Response(200, json={"npaHosts": []})
        )
        await aclient.dem.users.npa_hosts("a@b.com", "d1", start_time=_BEGIN, end_time=_END)
        assert route.called

    @respx.mock
    async def test_npa_network_paths_carries_the_host(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(f"{_ADEM}/npa/getnetworkpaths").mock(
            return_value=httpx.Response(200, json={"nodes": [], "edges": []})
        )
        await aclient.dem.users.npa_network_paths(
            "a@b.com", "d1", "10.0.0.1", start_time=_BEGIN, end_time=_END
        )
        assert sent_json(route)["npaHost"] == "10.0.0.1"

    @respx.mock
    async def test_traceroute_endpoints(self, aclient: AsyncNetskopeClient) -> None:
        timestamps = respx.post(f"{_ADEM}/device/gettraceroutetimestamps").mock(
            return_value=httpx.Response(200, json=[])
        )
        traceroute = respx.post(f"{_ADEM}/device/gettraceroute").mock(
            return_value=httpx.Response(200, json={})
        )
        users = aclient.dem.users
        await users.traceroute_timestamps("a@b.com", "d1", start_time=_BEGIN, end_time=_END)
        await users.traceroute("a@b.com", "d1", start_time=_BEGIN, end_time=_END)
        assert timestamps.called and traceroute.called
