"""Tests for client.dem (probes, network probes, alert rules, query, alerts, apps)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.dem import DATA_QUERY_SOURCES, DemAlert, DemQueryResult, QueryDataSource
from netskope.resources.dem.namespace import (
    AsyncDemResource,
    DemResource,
)
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
_END = datetime(2026, 1, 2, tzinfo=UTC)  # +24h
_END_72H = datetime(2026, 1, 4, tzinfo=UTC)  # +72h
_BEGIN_MS = int(_BEGIN.timestamp() * 1000)
_END_MS = int(_END.timestamp() * 1000)
_BEGIN_S = int(_BEGIN.timestamp())
_END_S = int(_END.timestamp())
# QueryInput.begin/.end are AbsoluteDate objects (dem-workbench-query.yaml:419-433).
_BEGIN_ABS = {"absolute": "2026-01-01T00:00:00Z"}
_END_ABS = {"absolute": "2026-01-02T00:00:00Z"}

# The minimum an app probe needs (AppProbeUpdateCreateCommon, demconfig.yaml:2666-2707).
_PROBE_REQUIRED = {
    "frequency": 5,
    "entity": {"user": ["user1"], "group": [], "ou": []},
    "os": ["windows", "mac"],
    "device_classification": ["managed"],
}


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
    def test_create_sends_a_bare_spec_body(self, client: NetskopeClient) -> None:
        """``POST /appprobes`` takes the object itself, never a ``data`` wrapper."""
        route = respx.post(_APPPROBES).mock(return_value=httpx.Response(201, json={"id": 1}))
        _dem(client).probes.create("p1", app_name="Slack", **_PROBE_REQUIRED)
        assert sent_json(route) == {
            "name": "p1",
            "frequency": 5,
            "entity": {"user": ["user1"], "group": [], "ou": []},
            "os": ["windows", "mac"],
            "deviceClassification": ["managed"],
            "status": 1,
            "appType": "predefined",
            "move": {"operation": "bottom"},
            "appName": "Slack",
        }

    @respx.mock
    def test_create_custom_app_and_explicit_move(self, client: NetskopeClient) -> None:
        route = respx.post(_APPPROBES).mock(return_value=httpx.Response(201, json={}))
        _dem(client).probes.create(
            "p1",
            app_id=2,
            status=0,
            move={"operation": "after", "position": 0},
            **_PROBE_REQUIRED,
        )
        body = sent_json(route)
        assert body["appType"] == "custom"
        assert body["appID"] == 2
        assert body["status"] == 0
        assert body["move"] == {"operation": "after", "position": 0}

    @respx.mock
    def test_create_additional_fields_merge(self, client: NetskopeClient) -> None:
        route = respx.post(_APPPROBES).mock(return_value=httpx.Response(201, json={}))
        _dem(client).probes.create(
            "p1", app_name="Slack", additional_fields={"tenantTag": "x"}, **_PROBE_REQUIRED
        )
        assert sent_json(route)["tenantTag"] == "x"

    @respx.mock
    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"target": "https://x.example.com"}, "does not define target"),
            ({"protocol": "tcp"}, "does not define protocol"),
            ({"interval": 300}, "does not define interval"),
        ],
    )
    def test_retired_arguments_are_rejected(
        self, client: NetskopeClient, kwargs: dict[str, object], message: str
    ) -> None:
        route = respx.post(url__regex=r".*").mock(return_value=httpx.Response(201, json={}))
        with pytest.raises(ValidationError, match=message):
            _dem(client).probes.create("p1", app_name="Slack", **_PROBE_REQUIRED, **kwargs)
        assert route.call_count == 0

    @respx.mock
    def test_missing_required_fields_are_rejected(self, client: NetskopeClient) -> None:
        route = respx.post(url__regex=r".*").mock(return_value=httpx.Response(201, json={}))
        with pytest.raises(ValidationError, match="requires frequency"):
            _dem(client).probes.create("p1", app_name="Slack")
        assert route.call_count == 0

    @respx.mock
    def test_ambiguous_app_selector_is_rejected(self, client: NetskopeClient) -> None:
        route = respx.post(url__regex=r".*").mock(return_value=httpx.Response(201, json={}))
        with pytest.raises(ValidationError, match="Name exactly one app"):
            _dem(client).probes.create("p1", app_name="Slack", app_id=2, **_PROBE_REQUIRED)
        assert route.call_count == 0

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
    def test_create_nests_the_measure_under_criteria(self, client: NetskopeClient) -> None:
        """``PostAlertRuleRequest`` has no flat metric/threshold (dem_alert.yaml:441-467)."""
        route = respx.post(_ALERT_RULES).mock(return_value=httpx.Response(201, json={"id": "r1"}))
        _dem(client).alert_rules.create(
            "rule1",
            "userDemScore",
            2000.0,
            severity="high",
            category="User Experience",
            type="Experience Score",
            email_receiver="ops@example.test",
            criteria_type="event",
            window=300,
            duration=600,
        )
        assert sent_json(route) == {
            "name": "rule1",
            "severity": "high",
            "enabled": True,
            "criteria": {
                "condition": {
                    "measure": "userDemScore",
                    "thresholds": {"threshold": 2000.0},
                    "window": 300,
                },
                "duration": 600,
            },
            "category": "User Experience",
            "type": "Experience Score",
            "criteriaType": "event",
            "emailReceiver": "ops@example.test",
        }

    @respx.mock
    def test_create_rejects_probe_id(self, client: NetskopeClient) -> None:
        route = respx.post(url__regex=r".*").mock(return_value=httpx.Response(201, json={}))
        with pytest.raises(ValidationError, match="no probe_id"):
            _dem(client).alert_rules.create("r", "userCount", 1.0, probe_id="probe-1")
        assert route.call_count == 0

    @respx.mock
    def test_list_sends_only_declared_filters_and_slices_locally(
        self, client: NetskopeClient
    ) -> None:
        """``findAlertRules`` declares category/type/enabled/severity only."""
        body = {"remainingQuota": 7, "rules": [{"id": str(i)} for i in range(4)]}
        route = respx.get(_ALERT_RULES).mock(return_value=httpx.Response(200, json=body))

        result = _dem(client).alert_rules.list(
            category="Network",
            type="Tunnel Status",
            enabled=True,
            severity="high",
            limit=2,
            offset=1,
        )

        assert dict(route.calls.last.request.url.params) == {
            "category": "Network",
            "type": "Tunnel Status",
            "enabled": "true",
            "severity": "high",
        }
        assert result == {"remainingQuota": 7, "rules": [{"id": "1"}, {"id": "2"}]}

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
        assert body["begin"] == _BEGIN_ABS
        assert body["end"] == _END_ABS
        assert body["groupby"] == ["user_id"]
        assert body["where"] == ["=", "user_id", ["$", "a@b.com"]]
        assert body["limit"] == 100
        assert body["offset"] == 10

    @respx.mock
    def test_int_begin_end_convert_from_epoch_millis(self, client: NetskopeClient) -> None:
        route = respx.post(_GETDATA).mock(return_value=httpx.Response(200, json={}))
        _dem(client).query.get_data("http", ["user_id"], begin=1711929600000, end=1712016000000)
        body = sent_json(route)
        assert body["begin"] == {"absolute": "2024-04-01T00:00:00Z"}
        assert body["end"] == {"absolute": "2024-04-02T00:00:00Z"}

    @respx.mock
    @pytest.mark.parametrize("source", ["agent_status", "client_status"])
    def test_state_sources_are_rejected(self, client: NetskopeClient, source: str) -> None:
        """``DataQueryFrom`` excludes the two ``StateQueryFrom`` values."""
        route = respx.post(_GETDATA).mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError, match="get_states"):
            _dem(client).query.get_data(source, ["x"], begin=1, end=2)
        assert not route.called

    @respx.mock
    def test_limit_and_offset_accept_the_declared_maximum(self, client: NetskopeClient) -> None:
        """``QueryInput`` sets ``limit`` ``exclusiveMaximum: 10000`` and ``offset``
        ``exclusiveMaximum: 100000`` (dem-workbench-query.yaml:447-461)."""
        route = respx.post(_GETDATA).mock(return_value=httpx.Response(200, json={}))
        _dem(client).query.get_data("http", ["x"], begin=1, end=2, limit=9999, offset=99999)
        body = sent_json(route)
        assert body["limit"] == 9999
        assert body["offset"] == 99999

    @respx.mock
    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"limit": 10000}, "limit must be an integer between 0 and 9999"),
            ({"limit": -1}, "limit must be an integer between 0 and 9999"),
            ({"offset": 100000}, "offset must be an integer between 0 and 99999"),
        ],
    )
    def test_out_of_range_paging_is_rejected(
        self, client: NetskopeClient, kwargs: dict[str, int], message: str
    ) -> None:
        """The bounds are exclusive maxima, so 10000 and 100000 are out of range
        (dem-workbench-query.yaml:447-461); nothing is clamped."""
        route = respx.post(_GETDATA).mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError, match=message):
            _dem(client).query.get_data("http", ["x"], begin=1, end=2, **kwargs)
        assert not route.called

    @respx.mock
    def test_zero_limit_and_offset_are_sent(self, client: NetskopeClient) -> None:
        """Both bounds declare ``minimum: 0`` (dem-workbench-query.yaml:450, :458)."""
        route = respx.post(_GETDATA).mock(return_value=httpx.Response(200, json={}))
        _dem(client).query.get_data("http", ["x"], begin=1, end=2, limit=0, offset=0)
        body = sent_json(route)
        assert body["limit"] == 0 and body["offset"] == 0

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
            limit=100,
            offset=5,
            sort_order="desc",
        )
        body = sent_json(route)
        assert body["starttime"] == _BEGIN_S
        assert body["endtime"] == _END_S
        assert body["user"] == "a@b.com"
        assert body["applications"] == ["Gmail"]
        params = dict(route.calls.last.request.url.params)
        # Pagination goes in query params; limit's declared maximum is 100.
        assert params == {"limit": "100", "offset": "5", "sortorder": "desc"}

    @respx.mock
    def test_window_longer_than_two_days_is_sent(self, client: NetskopeClient) -> None:
        """``GetEntitiesQueryInput`` types ``starttime``/``endtime`` as plain
        integers with no range cap (dem-workbench-query.yaml:296-366) and the
        operation (:1208) documents none, so a 72-hour window reaches the
        gateway."""
        route = respx.post(_GETENTITIES).mock(return_value=httpx.Response(200, json={"users": []}))
        _dem(client).query.get_entities(start_time=_BEGIN, end_time=_END_72H)
        body = sent_json(route)
        assert body == {"starttime": _BEGIN_S, "endtime": int(_END_72H.timestamp())}

    @respx.mock
    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"limit": 101}, "limit must be an integer between 0 and 100"),
            ({"offset": 100000}, "offset must be an integer between 0 and 99999"),
            ({"sort_order": "sideways"}, "sort_order must be one of: asc, desc"),
            ({"monitoring": "telepathy"}, "monitoring must be one of: all, synthetic, proactive"),
            ({"device_os": ["Plan9"]}, "Invalid device_os value"),
        ],
    )
    def test_out_of_range_and_unenumerated_inputs_are_rejected(
        self, client: NetskopeClient, kwargs: dict[str, Any], message: str
    ) -> None:
        """``limit`` is ``maximum: 100`` and ``offset`` ``exclusiveMaximum: 100000``
        (dem-workbench-query.yaml:1212-1229); ``sortorder`` (:1237-1246),
        ``monitoring`` (:334-341) and ``deviceOs`` (:309-321) are enumerated."""
        route = respx.post(_GETENTITIES).mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError, match=message):
            _dem(client).query.get_entities(start_time=_BEGIN, end_time=_END, **kwargs)
        assert not route.called

    @respx.mock
    def test_limit_zero_and_boundary_offset_are_sent(self, client: NetskopeClient) -> None:
        """``limit`` declares ``minimum: 0`` and ``offset`` accepts 99999
        (dem-workbench-query.yaml:1212-1229)."""
        route = respx.post(_GETENTITIES).mock(return_value=httpx.Response(200, json={"users": []}))
        _dem(client).query.get_entities(start_time=_BEGIN, end_time=_END, limit=0, offset=99999)
        assert dict(route.calls.last.request.url.params) == {"limit": "0", "offset": "99999"}


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
        assert body == {"from": "traceroute_pop", "begin": _BEGIN_ABS, "end": _END_ABS}
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
        await _adem(aclient).probes.create("p", app_name="Slack", **_PROBE_REQUIRED)
        body = sent_json(route)
        assert "data" not in body
        assert body["appName"] == "Slack"

    @respx.mock
    async def test_async_getdata_ms(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_GETDATA).mock(return_value=httpx.Response(200, json={}))
        await _adem(aclient).query.get_data("http", ["x"], begin=_BEGIN, end=_END)
        body = sent_json(route)
        assert body["begin"] == _BEGIN_ABS and body["end"] == _END_ABS

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


# --- Gateway contract conformance -------------------------------------------------------------
#
# Folded in from the spec-conformance reviews: each test cites the
# production/endpoints file and line whose shape it pins.

_GETDATASET = f"{_BASE}/api/v2/dem/query/getdataset"
_ADEM = f"{_BASE}/api/v2/adem/users"
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
    async def test_list_sends_only_declared_filters(self, aclient: AsyncNetskopeClient) -> None:
        """``findAlertRules`` (dem_alert.yaml:1289) has no limit/offset parameters."""
        body = {"remainingQuota": 3, "rules": [{"id": "r1"}, {"id": "r2"}, {"id": "r3"}]}
        route = respx.get(_ALERT_RULES).mock(return_value=httpx.Response(200, json=body))
        result = await aclient.dem.alert_rules.list(severity="high", limit=1, offset=1)
        assert dict(route.calls.last.request.url.params) == {"severity": "high"}
        assert result == {"remainingQuota": 3, "rules": [{"id": "r2"}]}

    @respx.mock
    async def test_create_sends_a_bare_criteria_body(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_ALERT_RULES).mock(return_value=httpx.Response(201, json=_RULE))
        await aclient.dem.alert_rules.create("latency-rule", "popLatency_p95", 200, severity="high")
        assert sent_json(route) == {
            "name": "latency-rule",
            "severity": "high",
            "enabled": True,
            "criteria": {
                "condition": {"measure": "popLatency_p95", "thresholds": {"threshold": 200}}
            },
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
            "begin": _BEGIN_ABS,
            "end": _END_ABS,
        }
        assert isinstance(result, DemQueryResult)
        assert result.data[0].root == {"user": "a@b.com"}

    @respx.mock
    async def test_get_traceroute_sends_absolute_bounds(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_GETTRACEROUTE).mock(return_value=httpx.Response(200, json={}))
        await aclient.dem.query.get_traceroute("traceroute_pop", begin=_BEGIN, end=_END)
        body = sent_json(route)
        assert body == {"from": "traceroute_pop", "begin": _BEGIN_ABS, "end": _END_ABS}
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


class TestDemQueryInputs:
    def test_data_query_sources_exclude_the_state_sources(self) -> None:
        """``DataQueryFrom`` is the 16-value set (dem-workbench-query.yaml:15-33);
        ``agent_status``/``client_status`` belong to ``StateQueryFrom`` (:516-521)."""
        assert len(DATA_QUERY_SOURCES) == 16
        assert QueryDataSource.AGENT_STATUS not in DATA_QUERY_SOURCES
        assert QueryDataSource.CLIENT_STATUS not in DATA_QUERY_SOURCES

    @respx.mock
    def test_get_entities_sends_sortby_and_user_location(self, client: NetskopeClient) -> None:
        """``/query/getentities`` declares ``sortby`` (dem-workbench-query.yaml:1229-1236)
        and its body accepts ``userLocation`` (:1260-1263)."""
        route = respx.post(f"{_BASE}/api/v2/dem/query/getentities").mock(
            return_value=httpx.Response(200, json={"users": []})
        )

        DemResource(client._transport).query.get_entities(
            start_time=1689490800,
            end_time=1689577200,
            user_location=[{"city": "San Francisco", "country": "USA", "region": "CA"}],
            sort_by="user_score",
            sort_order="asc",
            limit=10,
        )

        assert dict(route.calls.last.request.url.params) == {
            "limit": "10",
            "sortby": "user_score",
            "sortorder": "asc",
        }
        assert sent_json(route)["userLocation"] == [
            {"city": "San Francisco", "country": "USA", "region": "CA"}
        ]

    @respx.mock
    async def test_get_entities_sortby_async(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(f"{_BASE}/api/v2/dem/query/getentities").mock(
            return_value=httpx.Response(200, json={"users": []})
        )

        await AsyncDemResource(aclient._transport).query.get_entities(
            start_time=1689490800, end_time=1689577200, sort_by="user_score"
        )

        assert dict(route.calls.last.request.url.params) == {"sortby": "user_score"}


class TestAlertRuleWindowIsValidated:
    """A local window is refused, not applied from the wrong end.

    ``findAlertRules`` returns every match, so ``limit``/``offset`` slice the
    decoded ``rules`` collection instead of travelling as query parameters. A
    slice cannot fail the way a rejected query value does: ``rules[-3:]`` is the
    last three rules, not "page -3". The typed accessor already bounds the
    window through ``_paging``; these pin that the untyped one agrees, and that
    both refuse before the request rather than after.
    """

    @respx.mock
    @pytest.mark.parametrize(
        "window", [{"offset": -3}, {"limit": -2}], ids=["negative-offset", "negative-limit"]
    )
    def test_a_negative_window_is_refused_before_the_request(
        self, client: NetskopeClient, window: dict[str, int]
    ) -> None:
        with pytest.raises(ValidationError):
            client.dem.alert_rules.list(**window)
        assert len(respx.calls) == 0

    @respx.mock
    async def test_async_negative_window_is_refused_before_the_request(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with pytest.raises(ValidationError):
            await aclient.dem.alert_rules.list(offset=-3)
        assert len(respx.calls) == 0

    @respx.mock
    def test_the_untyped_and_typed_surfaces_refuse_with_the_same_message(
        self, client: NetskopeClient
    ) -> None:
        with pytest.raises(ValidationError) as untyped:
            client.dem.alert_rules.list(offset=-3)
        with pytest.raises(ValidationError) as typed:
            client.dem.alert_rules.with_response.list(offset=-3)
        assert str(untyped.value) == str(typed.value)
