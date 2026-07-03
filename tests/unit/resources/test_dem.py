"""Tests for client.dem (probes, network probes, alert rules, query, alerts, apps)."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.dem import DemAlert
from netskope.resources.dem import AsyncDemResource, DemResource
from tests.unit.resources.conftest import sent_json

_BASE = "https://t.goskope.com"
_APPPROBES = f"{_BASE}/api/v2/dem/appprobes"
_NETWORKPROBES = f"{_BASE}/api/v2/dem/networkprobes"
_ALERT_RULES = f"{_BASE}/api/v2/dem/alert/rules"
_ALERTS = f"{_BASE}/api/v2/dem/alerts"
_GETALERTS = f"{_BASE}/api/v2/dem/alerts/getalerts"
_APPS = f"{_BASE}/api/v2/dem/apps"
_GETDATA = f"{_BASE}/api/v2/dem/query/getdata"
_GETENTITIES = f"{_BASE}/api/v2/dem/query/getentities"
_GETSTATES = f"{_BASE}/api/v2/dem/query/getstates"
_GETTRACEROUTE = f"{_BASE}/api/v2/dem/query/gettraceroute"
_DEFINITIONS = f"{_BASE}/api/v2/dem/query/definitions"

# Fixed datetimes — never call datetime.now() in tests.
_BEGIN = datetime(2026, 1, 1, tzinfo=UTC)
_END = datetime(2026, 1, 2, tzinfo=UTC)  # +24h (inside the 48h getentities window)
_END_72H = datetime(2026, 1, 4, tzinfo=UTC)  # +72h (outside the window)
_BEGIN_MS = int(_BEGIN.timestamp() * 1000)
_END_MS = int(_END.timestamp() * 1000)
_BEGIN_S = int(_BEGIN.timestamp())
_END_S = int(_END.timestamp())


def _dem(client: NetskopeClient) -> DemResource:
    return DemResource(client._transport)


def _adem(aclient: AsyncNetskopeClient) -> AsyncDemResource:
    return AsyncDemResource(aclient._transport)


# --- Probes ---------------------------------------------------------------


class TestDemProbes:
    @respx.mock
    def test_list_sends_params(self, client: NetskopeClient) -> None:
        route = respx.get(_APPPROBES).mock(
            return_value=httpx.Response(200, json={"totalCount": 0, "data": []})
        )
        _dem(client).probes.list(limit=10, offset=5)
        assert dict(route.calls.last.request.url.params) == {"limit": "10", "offset": "5"}

    @respx.mock
    def test_create_wraps_in_data(self, client: NetskopeClient) -> None:
        route = respx.post(_APPPROBES).mock(return_value=httpx.Response(201, json={"id": 1}))
        _dem(client).probes.create("p1", "https://app.example.com", interval=300)
        assert sent_json(route) == {
            "data": {
                "name": "p1",
                "target": "https://app.example.com",
                "protocol": "https",
                "interval": 300,
            }
        }

    @respx.mock
    def test_create_additional_fields_merge(self, client: NetskopeClient) -> None:
        route = respx.post(_APPPROBES).mock(return_value=httpx.Response(201, json={}))
        _dem(client).probes.create(
            "p1", "t", additional_fields={"frequency": 60, "os": ["windows"]}
        )
        assert sent_json(route)["data"] == {
            "name": "p1",
            "target": "t",
            "protocol": "https",
            "frequency": 60,
            "os": ["windows"],
        }

    @respx.mock
    def test_get_update_delete(self, client: NetskopeClient) -> None:
        get_route = respx.get(f"{_APPPROBES}/42").mock(
            return_value=httpx.Response(200, json={"id": 42})
        )
        put_route = respx.put(f"{_APPPROBES}/42").mock(return_value=httpx.Response(200, json={}))
        del_route = respx.delete(f"{_APPPROBES}/42").mock(return_value=httpx.Response(204))
        probes = _dem(client).probes
        probes.get(42)
        probes.update(42, {"frequency": 120})
        probes.delete(42)
        assert get_route.called
        assert sent_json(put_route) == {"frequency": 120}
        assert del_route.called


class TestDemNetworkProbes:
    @respx.mock
    def test_list(self, client: NetskopeClient) -> None:
        route = respx.get(_NETWORKPROBES).mock(
            return_value=httpx.Response(200, json={"totalCount": 0, "data": []})
        )
        _dem(client).network_probes.list()
        assert route.called

    @respx.mock
    def test_delete(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_NETWORKPROBES}/7").mock(return_value=httpx.Response(204))
        _dem(client).network_probes.delete(7)
        assert route.called


# --- Alert rules ----------------------------------------------------------


class TestDemAlertRules:
    @respx.mock
    def test_list(self, client: NetskopeClient) -> None:
        route = respx.get(_ALERT_RULES).mock(
            return_value=httpx.Response(200, json={"rules": [], "totalCount": 0})
        )
        _dem(client).alert_rules.list()
        assert route.called

    @respx.mock
    def test_create_wraps_in_data(self, client: NetskopeClient) -> None:
        route = respx.post(_ALERT_RULES).mock(return_value=httpx.Response(201, json={"id": "r1"}))
        _dem(client).alert_rules.create(
            "rule1", "response_time", 2000.0, severity="high", probe_id="probe-1"
        )
        assert sent_json(route) == {
            "data": {
                "name": "rule1",
                "metric": "response_time",
                "threshold": 2000.0,
                "severity": "high",
                "probe_id": "probe-1",
            }
        }

    @respx.mock
    def test_delete(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_ALERT_RULES}/r1").mock(return_value=httpx.Response(204))
        _dem(client).alert_rules.delete("r1")
        assert route.called


# --- Query ----------------------------------------------------------------


class TestDemQueryGetData:
    @respx.mock
    def test_body_shape_and_ms_conversion(self, client: NetskopeClient) -> None:
        route = respx.post(_GETDATA).mock(return_value=httpx.Response(200, json={"data": []}))
        _dem(client).query.get_data(
            "ux_score",
            ["user_id", {"avg_score": ["avg", "score"]}],
            begin=_BEGIN,
            end=_END,
            group_by=["user_id"],
            where=["=", "user_id", ["$", "a@b.com"]],
            limit=100,
            offset=10,
        )
        body = sent_json(route)
        assert body["from"] == "ux_score"
        assert body["select"] == ["user_id", {"avg_score": ["avg", "score"]}]
        assert body["begin"] == _BEGIN_MS
        assert body["end"] == _END_MS
        assert body["groupby"] == ["user_id"]
        assert body["where"] == ["=", "user_id", ["$", "a@b.com"]]
        assert body["limit"] == 100
        assert body["offset"] == 10

    @respx.mock
    def test_int_begin_end_passthrough(self, client: NetskopeClient) -> None:
        route = respx.post(_GETDATA).mock(return_value=httpx.Response(200, json={}))
        _dem(client).query.get_data("http", ["user_id"], begin=1711929600000, end=1712016000000)
        body = sent_json(route)
        assert body["begin"] == 1711929600000
        assert body["end"] == 1712016000000

    @respx.mock
    def test_limit_capped_at_50000(self, client: NetskopeClient) -> None:
        route = respx.post(_GETDATA).mock(return_value=httpx.Response(200, json={}))
        _dem(client).query.get_data("http", ["x"], begin=1, end=2, limit=99999)
        assert sent_json(route)["limit"] == 50000

    @respx.mock
    def test_invalid_data_source_no_http(self, client: NetskopeClient) -> None:
        route = respx.post(_GETDATA).mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError):
            _dem(client).query.get_data("bogus", ["x"], begin=1, end=2)
        assert not route.called


class TestDemQueryGetEntities:
    @respx.mock
    def test_body_seconds_and_query_params(self, client: NetskopeClient) -> None:
        route = respx.post(_GETENTITIES).mock(return_value=httpx.Response(200, json={"users": []}))
        _dem(client).query.get_entities(
            start_time=_BEGIN,
            end_time=_END,
            user="a@b.com",
            applications=["Gmail"],
            limit=250,
            offset=5,
            sort_order="desc",
        )
        body = sent_json(route)
        assert body["starttime"] == _BEGIN_S
        assert body["endtime"] == _END_S
        assert body["user"] == "a@b.com"
        assert body["applications"] == ["Gmail"]
        params = dict(route.calls.last.request.url.params)
        # limit is capped at 100 and pagination goes in query params.
        assert params == {"limit": "100", "offset": "5", "sortorder": "desc"}

    @respx.mock
    def test_window_over_48h_no_http(self, client: NetskopeClient) -> None:
        route = respx.post(_GETENTITIES).mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError):
            _dem(client).query.get_entities(start_time=_BEGIN, end_time=_END_72H)
        assert not route.called


class TestDemQueryGetStates:
    @respx.mock
    def test_no_time_params(self, client: NetskopeClient) -> None:
        route = respx.post(_GETSTATES).mock(return_value=httpx.Response(200, json={"data": []}))
        _dem(client).query.get_states("agent_status", ["user_id", "status"])
        body = sent_json(route)
        assert body == {"from": "agent_status", "select": ["user_id", "status"]}
        assert "begin" not in body and "starttime" not in body

    @respx.mock
    def test_invalid_state_source_no_http(self, client: NetskopeClient) -> None:
        route = respx.post(_GETSTATES).mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError):
            _dem(client).query.get_states("ux_score", ["x"])
        assert not route.called


class TestDemQueryTraceroute:
    @respx.mock
    def test_body_ms_no_limit(self, client: NetskopeClient) -> None:
        route = respx.post(_GETTRACEROUTE).mock(return_value=httpx.Response(200, json={}))
        _dem(client).query.get_traceroute("traceroute_pop", begin=_BEGIN, end=_END)
        body = sent_json(route)
        assert body == {"from": "traceroute_pop", "begin": _BEGIN_MS, "end": _END_MS}
        assert "limit" not in body

    @respx.mock
    def test_invalid_traceroute_source_no_http(self, client: NetskopeClient) -> None:
        route = respx.post(_GETTRACEROUTE).mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError):
            _dem(client).query.get_traceroute("ux_score", begin=1, end=2)
        assert not route.called


class TestDemQueryDefinitions:
    @respx.mock
    def test_get_with_source(self, client: NetskopeClient) -> None:
        route = respx.get(_DEFINITIONS).mock(return_value=httpx.Response(200, json={}))
        _dem(client).query.definitions(source="rum_steered")
        assert dict(route.calls.last.request.url.params) == {"source": "rum_steered"}


# --- Experience alerts ----------------------------------------------------


class TestDemAlerts:
    @respx.mock
    def test_search_body_and_sortby_shape(self, client: NetskopeClient) -> None:
        route = respx.post(_GETALERTS).mock(
            return_value=httpx.Response(
                200,
                json={"alerts": [{"_id": "a1", "alertCategory": "Network", "severity": "high"}]},
            )
        )
        alerts = _dem(client).alerts.search(
            alert_category=["Network"],
            severity=["high", "critical"],
            open_time=1710000000,
            sort_field="openTime",
        )
        body = sent_json(route)
        assert body["alertCategory"] == ["Network"]
        assert body["severity"] == ["high", "critical"]
        assert body["openTime"] == 1710000000
        assert body["limit"] == 10  # default
        assert body["sortBy"] == {"field": "openTime", "desc": True}
        assert len(alerts) == 1
        assert isinstance(alerts[0], DemAlert)
        assert alerts[0].id == "a1"
        assert alerts[0].alert_category == "Network"

    @respx.mock
    def test_search_sort_asc(self, client: NetskopeClient) -> None:
        route = respx.post(_GETALERTS).mock(return_value=httpx.Response(200, json={"alerts": []}))
        _dem(client).alerts.search(sort_field="severity", sort_desc=False)
        assert sent_json(route)["sortBy"] == {"field": "severity", "desc": False}

    @respx.mock
    def test_get_quotes_alert_id(self, client: NetskopeClient) -> None:
        # A colon in the id must be percent-encoded into the path.
        route = respx.get(f"{_ALERTS}/id%3Av1").mock(
            return_value=httpx.Response(200, json={"_id": "id:v1", "severity": "low"})
        )
        alert = _dem(client).alerts.get("id:v1")
        assert route.called
        assert isinstance(alert, DemAlert)
        assert alert.id == "id:v1"

    @respx.mock
    def test_entities_query_params(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_ALERTS}/a1/entities").mock(return_value=httpx.Response(200, json={}))
        _dem(client).alerts.entities("a1", limit=25, offset=0, sort_by="user", sort_order="asc")
        assert dict(route.calls.last.request.url.params) == {
            "limit": "25",
            "offset": "0",
            "sortby": "user",
            "sortorder": "asc",
        }


# --- Apps -----------------------------------------------------------------


class TestDemApps:
    @respx.mock
    def test_list_params(self, client: NetskopeClient) -> None:
        route = respx.get(_APPS).mock(
            return_value=httpx.Response(200, json={"totalCount": 0, "data": []})
        )
        _dem(client).apps.list(app_type="predefined", name="Gmail", limit=50)
        assert dict(route.calls.last.request.url.params) == {
            "type": "predefined",
            "name": "Gmail",
            "limit": "50",
        }


# --- Async smoke ----------------------------------------------------------


class TestDemAsync:
    @respx.mock
    async def test_async_probe_create(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_APPPROBES).mock(return_value=httpx.Response(201, json={}))
        await _adem(aclient).probes.create("p", "t")
        assert sent_json(route) == {"data": {"name": "p", "target": "t", "protocol": "https"}}

    @respx.mock
    async def test_async_getdata_ms(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_GETDATA).mock(return_value=httpx.Response(200, json={}))
        await _adem(aclient).query.get_data("http", ["x"], begin=_BEGIN, end=_END)
        body = sent_json(route)
        assert body["begin"] == _BEGIN_MS and body["end"] == _END_MS

    @respx.mock
    async def test_async_invalid_source_no_http(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_GETSTATES).mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError):
            await _adem(aclient).query.get_states("bogus", ["x"])
        assert not route.called

    @respx.mock
    async def test_async_alert_search(self, aclient: AsyncNetskopeClient) -> None:
        respx.post(_GETALERTS).mock(
            return_value=httpx.Response(200, json={"alerts": [{"_id": "a1"}]})
        )
        alerts = await _adem(aclient).alerts.search()
        assert len(alerts) == 1 and alerts[0].id == "a1"
