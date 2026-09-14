"""DEM/ADEM response shapes, native units, and single-request parity."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, ClassVar

import httpx
import pytest
import respx
from pydantic import BaseModel

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import APIError, ResponseValidationError, ValidationError
from netskope.models.dem import (
    AdemGraphEdge,
    AdemNetworkGraph,
    DemAlertRule,
    DemProbe,
    DemQueryRequest,
)
from netskope.resources.dem.namespace import DemResource
from tests.unit.resources.conftest import contract_router

BASE = "https://t.goskope.com"
WINDOW = {"start_time": 1000, "end_time": 2000}
QUERY = {"begin": 1000000, "end": 2000000}
# QueryInput.begin/.end are AbsoluteDate objects, not epoch integers
# (dem-workbench-query.yaml:419-433); the ints above are epoch milliseconds.
QUERY_BOUNDS = {
    "begin": {"absolute": "1970-01-01T00:16:40Z"},
    "end": {"absolute": "1970-01-01T00:33:20Z"},
}
# The minimum an app probe needs (AppProbeUpdateCreateCommon, demconfig.yaml:2666-2707).
PROBE_ARGS = {
    "app_name": "Slack",
    "frequency": 5,
    "entity": {"user": ["user1"]},
    "os": ["windows"],
    "device_classification": ["managed"],
}
CASES = [
    (
        "probes",
        "list",
        (),
        {},
        "GET",
        "/api/v2/dem/appprobes",
        {"data": [{"id": "p", "frequency": 60}]},
        None,
    ),
    (
        "network_probes",
        "list",
        (),
        {},
        "GET",
        "/api/v2/dem/networkprobes",
        {"probes": [{"id": "n"}]},
        None,
    ),
    (
        "alert_rules",
        "list",
        (),
        {},
        "GET",
        "/api/v2/dem/alert/rules",
        {"remainingQuota": 7, "rules": [{"id": "r", "severity": "high"}]},
        None,
    ),
    (
        "apps",
        "list",
        (),
        {"limit": 3, "offset": 1},
        "GET",
        "/api/v2/dem/apps",
        {"apps": [{"appName": "Box"}]},
        None,
    ),
    (
        "query",
        "get_data",
        ("ux_score", ["user"]),
        QUERY,
        "POST",
        "/api/v2/dem/query/getdata",
        {
            "data": [{"user": "u", "score_alias": "007"}],
            "meta": {"total": "1", "sampling_enabled": "false"},
        },
        {"from": "ux_score", "select": ["user"], **QUERY_BOUNDS},
    ),
    (
        "query",
        "get_dataset",
        ("http_all", ["user"]),
        QUERY,
        "POST",
        "/api/v2/dem/query/getdataset",
        {"data": [{"user": "u"}]},
        {"from": "http_all", "select": ["user"], **QUERY_BOUNDS},
    ),
    (
        "query",
        "get_entities",
        (),
        WINDOW,
        "POST",
        "/api/v2/dem/query/getentities",
        {"users": [{"user": "u", "exp_score": "90"}], "totalUsersCount": 1},
        {"starttime": 1000, "endtime": 2000},
    ),
    (
        "query",
        "get_states",
        ("client_status", ["user"]),
        {},
        "POST",
        "/api/v2/dem/query/getstates",
        {"data": [{"user": "u"}]},
        {"from": "client_status", "select": ["user"]},
    ),
    (
        "query",
        "get_traceroute",
        ("traceroute_pop",),
        QUERY,
        "POST",
        "/api/v2/dem/query/gettraceroute",
        {"nodes": [{"id": "a"}], "edges": []},
        {"from": "traceroute_pop", **QUERY_BOUNDS},
    ),
    (
        "query",
        "definitions",
        (),
        {},
        "GET",
        "/api/v2/dem/query/definitions",
        {
            "metrics": [{"name": "rtt"}],
            "keys": [{"name": "user"}],
            "functions": [{"name": "avg", "valid_on_keys": True}],
        },
        None,
    ),
    (
        "alerts",
        "search",
        (),
        {},
        "POST",
        "/api/v2/dem/alerts/getalerts",
        {"alerts": [{"_id": "a", "openTime": "1000"}]},
        {"limit": 10},
    ),
    (
        "alerts",
        "get",
        ("a",),
        {},
        "GET",
        "/api/v2/dem/alerts/a",
        {"data": {"_id": "a", "openTime": "1000"}},
        None,
    ),
    (
        "alerts",
        "entities",
        ("a",),
        {"limit": 2, "sort_by": "user", "sort_order": "desc"},
        "GET",
        "/api/v2/dem/alerts/a/entities",
        {
            "entities": [
                {
                    "name": "SJC1",
                    "impactType": "pop",
                    "metricType": "popLatency_p95",
                    "metricValues": [{"timestamp": 1700000000, "value": 42}],
                    "pop": "SJC1",
                    "sourceIP": "203.0.113.9",
                    "status": "triggered",
                }
            ],
            "limit": 5,
            "offset": 0,
            "totalCount": 1,
        },
        None,
    ),
    (
        "users",
        "devices",
        ("u",),
        WINDOW,
        "POST",
        "/api/v2/adem/users/device/getlist",
        [{"deviceId": "d", "expScore": "90.5"}],
        {"starttime": 1000, "endtime": 2000, "user": "u", "userLocation": []},
    ),
    (
        "users",
        "device_details",
        ("u", "d"),
        WINDOW,
        "POST",
        "/api/v2/adem/users/device/getdetails",
        {"deviceId": "d", "deviceName": "laptop"},
        None,
    ),
    (
        "users",
        "info",
        ("u",),
        WINDOW,
        "POST",
        "/api/v2/adem/users/getinfo",
        {"user": "u", "expScore": "7"},
        None,
    ),
    (
        "users",
        "applications",
        ("u", "d"),
        WINDOW,
        "POST",
        "/api/v2/adem/users/getapplications",
        {"applications": [{"appName": "Box", "expScore": "8"}], "totalCount": 1},
        None,
    ),
    (
        "users",
        "locations",
        (),
        WINDOW,
        "POST",
        "/api/v2/adem/users/getlocations",
        {"userLocations": [{"city": "Boston"}]},
        None,
    ),
    (
        "users",
        "aggregated_scores",
        ("u", "d"),
        WINDOW,
        "POST",
        "/api/v2/adem/users/device/getaggregatedscores",
        {"aggregationType": "avg", "metrics": {"expScore": "8.5"}},
        None,
    ),
    (
        "users",
        "exp_score",
        ("u", "d"),
        WINDOW,
        "POST",
        "/api/v2/adem/users/metrics/getexpscore",
        [{"timestamp": "1000", "expScore": "8"}],
        None,
    ),
    (
        "users",
        "rca",
        ("u", "d"),
        WINDOW,
        "POST",
        "/api/v2/adem/users/device/getrca",
        {
            "items": [
                {
                    "starttime": 1000,
                    "endtime": 2000,
                    "rootCause": {
                        "name": "cpu",
                        "weight": 1,
                        "evidence": {"key": "cpu", "value": "high"},
                        "causedBy": [],
                    },
                }
            ]
        },
        None,
    ),
    (
        "users",
        "network_metrics",
        ("u", "d"),
        WINDOW,
        "POST",
        "/api/v2/adem/users/metrics/getnetwork",
        [{"timestamp": "1000", "latency": "8"}],
        None,
    ),
    (
        "users",
        "npa_hosts",
        ("u", "d"),
        WINDOW,
        "POST",
        "/api/v2/adem/users/npa/getnpahosts",
        {"npaHosts": [{"npaHost": "internal", "expScore": "8"}]},
        None,
    ),
    (
        "users",
        "npa_network_paths",
        ("u", "d", "internal"),
        WINDOW,
        "POST",
        "/api/v2/adem/users/npa/getnetworkpaths",
        {"nodes": [{"id": "a"}, {"id": "b"}], "edges": [{"source": "a", "destination": "b"}]},
        None,
    ),
    (
        "users",
        "traceroute_timestamps",
        ("u", "d"),
        WINDOW,
        "POST",
        "/api/v2/adem/users/device/gettraceroutetimestamps",
        [{"timestamp": "1000"}],
        None,
    ),
    (
        "users",
        "traceroute",
        ("u", "d"),
        WINDOW,
        "POST",
        "/api/v2/adem/users/device/gettraceroute",
        {"nodes": [], "edges": []},
        None,
    ),
]


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("group,method,args,kwargs,http_method,path,payload,expected_body", CASES)
@respx.mock
async def test_read_contracts(
    client,
    aclient,
    asynchronous,
    group,
    method,
    args,
    kwargs,
    http_method,
    path,
    payload,
    expected_body,
):
    route = respx.route(method=http_method, url=BASE + path).respond(200, json=payload)
    resource = getattr((aclient if asynchronous else client).dem, group)
    response = getattr(resource.with_response, method)(*args, **kwargs)
    if asynchronous:
        response = await response
    parsed = response.parse()
    assert isinstance(parsed, BaseModel) or all(isinstance(item, BaseModel) for item in parsed)
    assert response.json() == payload and route.call_count == 1
    if expected_body is not None:
        assert json.loads(route.calls.last.request.content) == expected_body


@respx.mock
def test_dynamic_query_rows_have_a_typed_envelope_without_coercing_aliases(client):
    payload = {
        "data": [{"my_percentile": "007", "dimension": {"future": True}}],
        "meta": {"total": "1", "elapsed": "2.5", "sampling_enabled": "false"},
    }
    respx.post(f"{BASE}/api/v2/dem/query/getdata").respond(200, json=payload)
    response = client.dem.query.with_response.get_data("ux_score", ["my_percentile"], **QUERY)
    result = response.parse()
    assert (
        result.meta.total == 1
        and result.meta.elapsed == 2.5
        and result.meta.sampling_enabled is False
    )
    assert result.data[0].root == payload["data"][0]
    assert response.json() == payload


@pytest.mark.parametrize(
    "group,method,args,kwargs",
    [
        ("query", "get_data", ("ux_score", []), QUERY),
        ("query", "get_data", ("ux_score", ["u"]), {**QUERY, "limit": "2"}),
        ("query", "get_data", ("ux_score", ["u"]), {**QUERY, "begin": True}),
        ("query", "get_dataset", ("ux_score", ["u"]), QUERY),
        ("query", "get_dataset", ("http_all", ["u"]), {"begin": 0, "end": 49 * 3600 * 1000}),
        ("query", "get_entities", (), {"start_time": 2000, "end_time": 1000}),
        ("query", "get_entities", (), {**WINDOW, "sort_order": "wrong"}),
        ("query", "get_traceroute", ("traceroute_pop",), {"begin": 2000, "end": 1000}),
        ("users", "devices", ("u",), {"start_time": 2000, "end_time": 1000}),
        ("users", "devices", ("u",), {"start_time": datetime(2026, 1, 1), "end_time": 2000}),
        ("users", "aggregated_scores", ("u", "d"), {**WINDOW, "aggregation_type": "wrong"}),
        (
            "probes",
            "create",
            ("p", "https://example.com"),
            {"additional_fields": {"interval": "bad"}},
        ),
    ],
)
@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_invalid_inputs_fail_before_http(
    client, aclient, asynchronous, group, method, args, kwargs
):
    resource = getattr((aclient if asynchronous else client).dem, group)
    with pytest.raises(ValidationError):
        result = getattr(resource.with_response, method)(*args, **kwargs)
        if asynchronous:
            await result
    assert not respx.calls


@respx.mock
def test_declared_query_bounds_are_sent_verbatim(client):
    """``QueryInput``/``DataSetQueryInput`` accept ``limit`` up to 9999 and
    ``offset`` up to 99999 (dem-workbench-query.yaml:447-461, :73-87), and
    ``/query/getentities`` accepts ``limit`` up to 100 (:1212-1220).  The
    largest accepted value goes on the wire unchanged."""
    metrics = respx.post(f"{BASE}/api/v2/dem/query/getdata").respond(200, json={"data": []})
    dataset = respx.post(f"{BASE}/api/v2/dem/query/getdataset").respond(200, json={"data": []})
    entities = respx.post(f"{BASE}/api/v2/dem/query/getentities").respond(200, json={"users": []})
    client.dem.query.with_response.get_data(
        "ux_score", ["u"], **QUERY, limit=9999, offset=99999
    ).parse()
    client.dem.query.get_dataset("http_all", ["u"], **QUERY, limit=9999)
    client.dem.query.with_response.get_entities(**WINDOW, limit=100).parse()
    assert json.loads(metrics.calls.last.request.content)["limit"] == 9999
    assert json.loads(metrics.calls.last.request.content)["offset"] == 99999
    assert json.loads(dataset.calls.last.request.content)["limit"] == 9999
    assert entities.calls.last.request.url.params["limit"] == "100"


@pytest.mark.parametrize(
    "method,args,kwargs",
    [
        ("get_data", ("ux_score", ["u"]), {**QUERY, "limit": 10000}),
        ("get_data", ("ux_score", ["u"]), {**QUERY, "offset": 100000}),
        ("get_dataset", ("http_all", ["u"]), {**QUERY, "limit": 10000}),
        ("get_dataset", ("http_all", ["u"]), {**QUERY, "offset": 100000}),
        ("get_states", ("client_status", ["u"]), {"limit": 10000}),
        ("get_states", ("client_status", ["u"]), {"offset": 100000}),
        ("get_entities", (), {**WINDOW, "limit": 101}),
        ("get_entities", (), {**WINDOW, "offset": 100000}),
    ],
)
@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_out_of_range_query_bounds_are_rejected(
    client, aclient, asynchronous, method, args, kwargs
):
    """Both maxima are exclusive in ``QueryInput``, ``DataSetQueryInput`` and
    ``StateQueryInput`` (dem-workbench-query.yaml:447-461, :73-87, :534-548),
    and ``/query/getentities`` caps ``limit`` at 100 (:1212-1220); the SDK
    reports the value instead of clamping it."""
    query = (aclient if asynchronous else client).dem.query
    with pytest.raises(ValidationError):
        result = getattr(query.with_response, method)(*args, **kwargs)
        if asynchronous:
            await result
    assert not respx.calls


@pytest.mark.parametrize(
    "payload", [{}, {"data": {}}, {"data": ["bad"]}, {"data": [], "meta": {"total": "bad"}}]
)
@respx.mock
def test_malformed_query_retains_same_request(client, payload):
    path = "/api/v2/dem/query/getdataset"
    respx.post(BASE + path).respond(200, json=payload, headers={"x-request-id": "dem-response"})
    response = client.dem.query.with_response.get_dataset("http_all", ["u"], **QUERY)
    with pytest.raises(ResponseValidationError) as error:
        response.parse()
    assert error.value.request_path == path and error.value.request_id == "dem-response"
    assert response.json() == payload


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    "group,args,kwargs,path,payload",
    [
        (
            "probes",
            ("probe",),
            PROBE_ARGS,
            "/api/v2/dem/appprobes",
            {"id": "p", "frequency": 5},
        ),
        (
            "alert_rules",
            ("rule", "userDemScore", 20.0),
            {},
            "/api/v2/dem/alert/rules",
            {"id": "r", "severity": "medium"},
        ),
    ],
)
@respx.mock
async def test_mutations_are_typed_and_not_replayed(
    client, aclient, asynchronous, group, args, kwargs, path, payload
):
    route = respx.post(BASE + path).respond(201, json=payload)
    method = getattr((aclient if asynchronous else client).dem, group).with_response.create
    response = method(*args, **kwargs)
    if asynchronous:
        response = await response
    assert isinstance(response.parse(), BaseModel) and response.json() == payload
    assert route.call_count == 1
    route.respond(503, json={"message": "unavailable"})
    with pytest.raises(APIError):
        result = method(*args, **kwargs)
        if asynchronous:
            await result
    assert route.call_count == 2


# --- Gateway contract conformance -------------------------------------------------------------
#
# Folded in from the spec-conformance reviews: each test cites the
# production/endpoints file and line whose shape it pins.


class TestAlertEntitiesDecode:
    _BODY: ClassVar[dict[str, Any]] = {
        "entities": [
            {
                "name": "pop-sjc1",
                "impactType": "latency",
                "metricType": "popLatency_p95",
                "metricValues": [{"timestamp": 1700000000, "value": 42}],
                "pop": "SJC1",
                "publisher": "pub-1",
                "resource": "res-1",
                "service": "svc-1",
                "site": "site-1",
                "sourceIP": "203.0.113.9",
                "status": "triggered",
            }
        ],
        "limit": 5,
        "offset": 0,
        "totalCount": 1,
    }

    def test_sync_maps_every_declared_property(self, contract_client: NetskopeClient) -> None:
        """``GET /alerts/{id}/entities`` returns ``AlertEntityDetail``
        (dem_alert.yaml:87-105) whose items are ``ImpactEntity`` (:342-381),
        with ``metricValues`` items ``MetricValue`` (:382-391)."""
        with contract_router() as mock:
            mock.get("/api/v2/dem/alerts/a1/entities").mock(
                return_value=httpx.Response(200, json=self._BODY)
            )
            rows = contract_client.dem.alerts.with_response.entities("a1").parse()
        entity = rows[0]
        assert entity.name == "pop-sjc1"
        assert entity.impact_type == "latency" and entity.metric_type == "popLatency_p95"
        assert entity.metric_values[0].timestamp == 1700000000
        assert entity.metric_values[0].value == 42
        assert entity.source_ip == "203.0.113.9" and entity.status == "triggered"
        assert (entity.pop, entity.publisher, entity.resource) == ("SJC1", "pub-1", "res-1")
        assert (entity.service, entity.site) == ("svc-1", "site-1")
        assert not entity.model_extra

    async def test_async_decodes_the_same_rows(self, contract_aclient: AsyncNetskopeClient) -> None:
        with contract_router() as mock:
            mock.get("/api/v2/dem/alerts/a1/entities").mock(
                return_value=httpx.Response(200, json=self._BODY)
            )
            response = await contract_aclient.dem.alerts.with_response.entities("a1")
        assert response.parse()[0].pop == "SJC1"

    def test_sortorder_is_enumerated_on_both_surfaces(
        self, contract_client: NetskopeClient
    ) -> None:
        """``sortorder`` on ``/alerts/{id}/entities`` enumerates asc|desc
        (dem_alert.yaml:1813-1822)."""
        with contract_router() as mock:
            route = mock.get("/api/v2/dem/alerts/a1/entities").mock(
                return_value=httpx.Response(200, json={"entities": []})
            )
            with pytest.raises(ValidationError, match="sort_order must be one of"):
                contract_client.dem.alerts.entities("a1", sort_order="sideways")
            with pytest.raises(ValidationError, match="sort_order must be one of"):
                contract_client.dem.alerts.with_response.entities("a1", sort_order="sideways")
            assert route.call_count == 0


class TestNetworkGraphsAreSparse:
    def test_models_follow_the_looser_of_the_two_operations(self) -> None:
        """``TracerData`` (adem_backend_api.yaml:1767-1782) requires neither
        ``nodes`` nor ``edges``, and ``NetworkEdge`` (:1315-1331) requires
        neither ``source`` nor ``destination``; ``NetworkNode`` (:1277-1314)
        requires nothing at all."""
        graph = AdemNetworkGraph.model_validate({"nodes": [{"id": "1", "hopType": "device"}]})
        assert graph.edges == [] and graph.nodes[0].hop_type == "device"
        edge = AdemGraphEdge.model_validate({"noOfSessions": 3, "avgLatency": 11})
        assert edge.source is None and edge.destination is None and edge.sessions == 3

    def test_traceroute_parses_a_nodes_only_body(self, contract_client: NetskopeClient) -> None:
        with contract_router() as mock:
            mock.post("/api/v2/adem/users/device/gettraceroute").mock(
                return_value=httpx.Response(
                    200, json={"nodes": [{"id": "1", "hopType": "device"}], "isComplete": True}
                )
            )
            graph = contract_client.dem.users.with_response.traceroute(
                "u@example.com", "device-1", start_time=1700000000, end_time=1700003600
            ).parse()
        assert graph.complete is True and graph.edges == []

    async def test_async_network_paths_parse_edges_without_endpoints(
        self, contract_aclient: AsyncNetskopeClient
    ) -> None:
        with contract_router() as mock:
            mock.post("/api/v2/adem/users/npa/getnetworkpaths").mock(
                return_value=httpx.Response(
                    200, json={"nodes": [], "edges": [{"noOfSessions": 3, "avgLatency": 11}]}
                )
            )
            response = await contract_aclient.dem.users.with_response.npa_network_paths(
                "u@example.com", "device-1", "host-1", start_time=1700000000, end_time=1700003600
            )
        assert response.parse().edges[0].sessions == 3


class TestDemQueryBounds:
    _WINDOW: ClassVar[dict[str, int]] = {
        "start_time": 1700000000,
        "end_time": 1700000000 + 72 * 3600,
    }

    async def test_getentities_window_is_not_capped(
        self, contract_aclient: AsyncNetskopeClient
    ) -> None:
        """``GetEntitiesQueryInput`` types ``starttime``/``endtime`` as plain
        integers with no bound (dem-workbench-query.yaml:296-366) and
        ``/query/getentities`` (:1208) documents no range cap; only
        ``/query/getdataset`` does (:918)."""
        with contract_router() as mock:
            route = mock.post("/api/v2/dem/query/getentities").mock(
                return_value=httpx.Response(200, json={"users": [], "totalUsersCount": 0})
            )
            await contract_aclient.dem.query.get_entities(**self._WINDOW)
            response = await contract_aclient.dem.query.with_response.get_entities(**self._WINDOW)
        response.parse()
        assert route.call_count == 2

    def test_getdataset_keeps_the_documented_two_day_cap(
        self, contract_client: NetskopeClient
    ) -> None:
        """``/query/getdataset`` states "Maximum allowed range: 2 days"
        (dem-workbench-query.yaml:918, in the operation
        description that starts at :893)."""
        with contract_router() as mock:
            route = mock.post("/api/v2/dem/query/getdataset").mock(
                return_value=httpx.Response(200, json={"data": []})
            )
            with pytest.raises(ValidationError, match="must not exceed 48 hours"):
                contract_client.dem.query.with_response.get_dataset(
                    "http_all", ["user"], begin=0, end=49 * 3600 * 1000
                )
            assert route.call_count == 0

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"limit": 10000}, "limit must be an integer between 0 and 9999"),
            ({"offset": 100000}, "offset must be an integer between 0 and 99999"),
        ],
    )
    def test_legacy_getstates_applies_the_state_query_bounds(
        self, contract_client: NetskopeClient, kwargs: dict[str, int], message: str
    ) -> None:
        """``StateQueryInput.limit`` is ``exclusiveMaximum: 10000`` and
        ``.offset`` ``exclusiveMaximum: 100000``
        (dem-workbench-query.yaml:534-548)."""
        with contract_router() as mock:
            route = mock.post("/api/v2/dem/query/getstates").mock(
                return_value=httpx.Response(200, json={"data": []})
            )
            with pytest.raises(ValidationError, match=message):
                contract_client.dem.query.get_states("client_status", ["user"], **kwargs)
            assert route.call_count == 0

    def test_legacy_getstates_sends_the_boundary_values(
        self, contract_client: NetskopeClient
    ) -> None:
        with contract_router() as mock:
            route = mock.post("/api/v2/dem/query/getstates").mock(
                return_value=httpx.Response(200, json={"data": []})
            )
            contract_client.dem.query.get_states(
                "client_status", ["user"], limit=9999, offset=99999
            )
        body = json.loads(route.calls.last.request.content)
        assert body["limit"] == 9999 and body["offset"] == 99999

    async def test_async_legacy_getdata_rejects_an_out_of_range_limit(
        self, contract_aclient: AsyncNetskopeClient
    ) -> None:
        with contract_router() as mock:
            route = mock.post("/api/v2/dem/query/getdata").mock(
                return_value=httpx.Response(200, json={"data": []})
            )
            message = "limit must be an integer between 0 and 9999"
            with pytest.raises(ValidationError, match=message):
                await contract_aclient.dem.query.get_data(
                    "http", ["x"], begin=1, end=2, limit=123456
                )
            assert route.call_count == 0


class TestDemQueryWindowRules:
    _BOUND: ClassVar[dict[str, str]] = {"absolute": "2024-01-01T00:00:00Z"}

    def test_equal_and_mixed_bounds_are_accepted(self) -> None:
        """``QueryInput`` types ``begin`` and ``end`` as independent
        ``anyOf[AbsoluteDate, RelativeDate, null]`` values
        (dem-workbench-query.yaml:422-433): no ordering rule, and no rule that
        both use the same mode."""
        equal = DemQueryRequest.model_validate(
            {"from": "http", "select": ["u"], "begin": self._BOUND, "end": self._BOUND}
        )
        assert equal.begin == equal.end
        mixed = DemQueryRequest.model_validate(
            {
                "from": "http",
                "select": ["u"],
                "begin": {"relative": "2024-01-01T00:00:00Z"},
                "end": self._BOUND,
            }
        )
        assert mixed.begin == {"relative": "2024-01-01T00:00:00Z"}

    def test_an_inverted_same_mode_window_is_still_rejected(self) -> None:
        with pytest.raises(Exception, match="end must not precede begin"):
            DemQueryRequest.model_validate(
                {
                    "from": "http",
                    "select": ["u"],
                    "begin": {"absolute": "2024-01-02T00:00:00Z"},
                    "end": self._BOUND,
                }
            )

    def test_relative_bounds_are_timestamps(self) -> None:
        """``RelativeDate.relative`` is a ``format: date-time`` string
        (dem-workbench-query.yaml:498-507), not an offset expression."""
        with pytest.raises(Exception, match="RFC 3339"):
            DemQueryRequest.model_validate(
                {"from": "http", "select": ["u"], "begin": {"relative": "-24h"}}
            )

    def test_the_typed_surface_sends_an_equal_window(self, contract_client: NetskopeClient) -> None:
        with contract_router() as mock:
            route = mock.post("/api/v2/dem/query/getdata").mock(
                return_value=httpx.Response(200, json={"data": []})
            )
            contract_client.dem.query.with_response.get_data(
                "rum_steered", ["country"], begin=1704067200000, end=1704067200000
            ).parse()
        body = json.loads(route.calls.last.request.content)
        assert body["begin"] == body["end"] == {"absolute": "2024-01-01T00:00:00Z"}


class TestDemListPagingBounds:
    @pytest.mark.parametrize("limit", [0, 1001])
    def test_probe_lists_reject_out_of_range_limits(
        self, contract_client: NetskopeClient, limit: int
    ) -> None:
        """``GET /appprobes`` (demconfig.yaml:625-631) and ``GET /networkprobes``
        (:1560-1566) declare ``limit`` as ``minimum: 1, maximum: 1000``."""
        with contract_router() as mock:
            route = mock.route(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
            for call in (
                lambda: contract_client.dem.probes.list(limit=limit),
                lambda: contract_client.dem.probes.with_response.list(limit=limit),
                lambda: contract_client.dem.network_probes.list(limit=limit),
                lambda: contract_client.dem.network_probes.with_response.list(limit=limit),
            ):
                with pytest.raises(ValidationError, match="limit must be an integer between 1"):
                    call()
            assert route.call_count == 0

    @pytest.mark.parametrize("limit", [1, 1000])
    def test_probe_lists_send_the_boundary_limits(
        self, contract_client: NetskopeClient, limit: int
    ) -> None:
        with contract_router() as mock:
            route = mock.get("/api/v2/dem/appprobes").mock(
                return_value=httpx.Response(200, json={"totalCount": 0, "probes": []})
            )
            contract_client.dem.probes.list(limit=limit, offset=0)
            contract_client.dem.probes.with_response.list(limit=limit, offset=0).parse()
        assert dict(route.calls.last.request.url.params) == {"limit": str(limit), "offset": "0"}

    def test_app_list_requires_at_least_one_row(self, contract_client: NetskopeClient) -> None:
        """``GET /apps`` declares ``limit`` ``minimum: 1`` with no maximum
        (demconfig.yaml:110-116)."""
        with contract_router() as mock:
            route = mock.get("/api/v2/dem/apps").mock(
                return_value=httpx.Response(200, json={"apps": []})
            )
            with pytest.raises(ValidationError, match="limit must be an integer 1 or more"):
                contract_client.dem.apps.list(limit=0)
            with pytest.raises(ValidationError, match="limit must be an integer 1 or more"):
                contract_client.dem.apps.with_response.list(limit=0)
            contract_client.dem.apps.list(limit=5000)
            assert route.calls.last.request.url.params["limit"] == "5000"

    async def test_async_probe_lists_apply_the_same_bounds(
        self, contract_aclient: AsyncNetskopeClient
    ) -> None:
        with contract_router() as mock:
            route = mock.route(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
            with pytest.raises(ValidationError, match="limit must be an integer between 1"):
                await contract_aclient.dem.probes.list(limit=5000)
            with pytest.raises(ValidationError, match="limit must be an integer between 1"):
                await contract_aclient.dem.network_probes.with_response.list(limit=0)
            with pytest.raises(ValidationError, match="offset must be an integer 0 or more"):
                await contract_aclient.dem.probes.list(offset=-1)
            assert route.call_count == 0


class TestDemRequestEnums:
    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"category": "Nope"}, "category must be one of"),
            ({"type": "Nope"}, "type must be one of"),
            ({"severity": "apocalyptic"}, "severity must be one of"),
        ],
    )
    def test_alert_rule_filters_are_enumerated(
        self, contract_client: NetskopeClient, kwargs: dict[str, str], message: str
    ) -> None:
        """``GET /alert/rules`` filters by ``AlertCategory`` (dem_alert.yaml:79-86),
        ``AlertType`` (:304-314) and ``AlertSeverity`` (:288-296)."""
        with contract_router() as mock:
            route = mock.get("/api/v2/dem/alert/rules").mock(
                return_value=httpx.Response(200, json={"rules": []})
            )
            with pytest.raises(ValidationError, match=message):
                contract_client.dem.alert_rules.list(**kwargs)
            assert route.call_count == 0

    def test_declared_alert_rule_filters_are_sent(self, contract_client: NetskopeClient) -> None:
        with contract_router() as mock:
            route = mock.get("/api/v2/dem/alert/rules").mock(
                return_value=httpx.Response(200, json={"rules": []})
            )
            contract_client.dem.alert_rules.list(
                category="User Experience", type="Experience Score", severity="high", enabled=True
            )
        assert dict(route.calls.last.request.url.params) == {
            "category": "User Experience",
            "type": "Experience Score",
            "severity": "high",
            "enabled": "true",
        }

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"alert_category": ["Nope"]}, "Invalid alert_category value"),
            ({"alert_type": ["Nope"]}, "Invalid alert_type value"),
            ({"severity": ["apocalyptic"]}, "Invalid severity value"),
        ],
    )
    def test_getalerts_lists_are_enumerated(
        self, contract_client: NetskopeClient, kwargs: dict[str, list[str]], message: str
    ) -> None:
        """``AlertQuery`` types ``alertCategory``, ``alertType`` and ``severity``
        as arrays of those same enumerations (dem_alert.yaml:138-173)."""
        with contract_router() as mock:
            route = mock.post("/api/v2/dem/alerts/getalerts").mock(
                return_value=httpx.Response(200, json={"alerts": []})
            )
            with pytest.raises(ValidationError, match=message):
                contract_client.dem.alerts.search(**kwargs)
            with pytest.raises(ValidationError, match=message):
                contract_client.dem.alerts.with_response.search(**kwargs)
            assert route.call_count == 0

    def test_alert_rule_create_enumerations(self, contract_client: NetskopeClient) -> None:
        """``PostAlertRuleRequest`` refers to the same three enumerations
        (dem_alert.yaml:441-462)."""
        with contract_router() as mock:
            route = mock.post("/api/v2/dem/alert/rules").mock(
                return_value=httpx.Response(200, json={"id": "1"})
            )
            with pytest.raises(ValidationError, match="severity must be one of"):
                contract_client.dem.alert_rules.create(
                    "r", "userDemScore", 80.0, severity="apocalyptic", criteria={"condition": {}}
                )
            with pytest.raises(ValidationError, match="category must be one of"):
                contract_client.dem.alert_rules.create(
                    "r", "userDemScore", 80.0, category="Nope", criteria={"condition": {}}
                )
            assert route.call_count == 0

    def test_probe_create_enumerations(self, contract_client: NetskopeClient) -> None:
        """``AppProbeUpdateCreateCommon`` enumerates ``os`` (windows|mac) and
        ``deviceClassification`` (managed|unmanaged|not configured)
        (demconfig.yaml:2690-2704)."""
        with contract_router() as mock:
            route = mock.post("/api/v2/dem/appprobes").mock(
                return_value=httpx.Response(200, json={"id": 1})
            )
            with pytest.raises(ValidationError, match="Invalid os value"):
                contract_client.dem.probes.create(
                    "p",
                    app_name="Slack",
                    frequency=5,
                    entity={"user": ["u"]},
                    os=["plan9"],
                    device_classification=["managed"],
                )
            with pytest.raises(ValidationError, match="Invalid device_classification value"):
                contract_client.dem.probes.create(
                    "p",
                    app_name="Slack",
                    frequency=5,
                    entity={"user": ["u"]},
                    os=["windows"],
                    device_classification=["unknown"],
                )
            assert route.call_count == 0

    async def test_async_surfaces_apply_the_same_enumerations(
        self, contract_aclient: AsyncNetskopeClient
    ) -> None:
        with contract_router() as mock:
            route = mock.route(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
            with pytest.raises(ValidationError, match="category must be one of"):
                await contract_aclient.dem.alert_rules.list(category="Nope")
            with pytest.raises(ValidationError, match="Invalid severity value"):
                await contract_aclient.dem.alerts.search(severity=["apocalyptic"])
            with pytest.raises(ValidationError, match="monitoring must be one of"):
                await contract_aclient.dem.query.get_entities(
                    start_time=1700000000, end_time=1700003600, monitoring="telepathy"
                )
            assert route.call_count == 0


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("bounds", [(0, 1), (1, 0), (-1, 1)])
async def test_entity_queries_require_positive_epoch_bounds(
    contract_client: NetskopeClient,
    contract_aclient: AsyncNetskopeClient,
    asynchronous: bool,
    typed: bool,
    bounds: tuple[int, int],
) -> None:
    """dem-workbench-query.yaml:324-327,350-353 require epochs > 0."""
    query = (contract_aclient if asynchronous else contract_client).dem.query
    accessor = query.with_response if typed else query
    with contract_router() as mock:
        with pytest.raises(ValidationError):
            if asynchronous:
                await accessor.get_entities(start_time=bounds[0], end_time=bounds[1])
            else:
                accessor.get_entities(start_time=bounds[0], end_time=bounds[1])
        assert not mock.calls


class TestDemProbeAndAlertRuleRecords:
    """``demconfig.yaml`` and ``dem_alert.yaml`` response shapes decode in full."""

    @respx.mock
    def test_app_probe_row_from_the_spec_example(self, client: NetskopeClient) -> None:
        """``AppProbeGetResp`` (demconfig.yaml:2812), "full result" example (:597-627)."""
        body = {
            "totalCount": 1,
            "data": [
                {
                    "id": 1,
                    "name": "app probe 1",
                    "appID": 1,
                    "appName": "app 1",
                    "appType": "custom",
                    "appDomains": ["domain.com"],
                    "frequency": 10,
                    "priority": 1,
                    "entity": {"user": ["user1"], "group": ["group1"], "ou": ["ou1"]},
                    "os": ["windows", "mac"],
                    "deviceClassification": ["managed", "unmanaged"],
                    "status": 0,
                    "modifiedTime": "2024-05-22T06:45:07.022000Z",
                    "createdTime": "2024-05-22T06:45:07.022000Z",
                }
            ],
        }
        respx.get(f"{BASE}/api/v2/dem/appprobes").mock(return_value=httpx.Response(200, json=body))

        probes = DemResource(client._transport).probes.with_response.list().parse()

        assert len(probes) == 1
        probe = probes[0]
        assert (probe.app_id, probe.app_name, probe.app_type) == (1, "app 1", "custom")
        assert probe.app_domains == ["domain.com"]
        assert probe.frequency == 10
        assert probe.priority == 1
        assert probe.entity is not None and probe.entity.user == ["user1"]
        assert probe.device_classification == ["managed", "unmanaged"]
        assert probe.status == 0
        # Nothing had to fall through to `extra` to survive.
        assert probe.model_extra == {}

    @respx.mock
    def test_network_probe_collection_flags_decode(self, client: NetskopeClient) -> None:
        """``NetworkProbeCreateUpdateResp`` adds two collection flags (demconfig.yaml:2813)."""
        body = {
            "totalCount": 1,
            "data": [
                {
                    "id": 4,
                    "name": "network probe",
                    "networkPathDeviceHealthCollection": True,
                    "processInfoCollection": False,
                    "frequency": 5,
                    "os": ["windows"],
                    "deviceClassification": ["not configured"],
                    "status": 1,
                }
            ],
        }
        respx.get(f"{BASE}/api/v2/dem/networkprobes").mock(
            return_value=httpx.Response(200, json=body)
        )

        probes = DemResource(client._transport).network_probes.with_response.list().parse()

        assert probes[0].network_path_device_health_collection is True
        assert probes[0].process_info_collection is False
        assert probes[0].model_extra == {}

    @respx.mock
    def test_alert_rules_envelope_carries_remaining_quota(self, client: NetskopeClient) -> None:
        """``GET /alert/rules`` answers ``{remainingQuota, rules, totalCount}``
        (dem_alert.yaml:1289-1330), and a rule keeps its criteria."""
        criteria = {
            "condition": {
                "measure": "userDemScore",
                "thresholds": {"threshold": {"le": {"score": 50}}},
                "window": 300,
            },
            "duration": 600,
        }
        body = {
            "remainingQuota": 9,
            "totalCount": 1,
            "rules": [
                {
                    "id": "rule-1",
                    "name": "Experience drop",
                    "category": "User Experience",
                    "type": "Experience Score",
                    "criteria": criteria,
                    "criteriaType": "event",
                    "emailReceiver": "ops@example.test",
                    "enabled": True,
                    "severity": "high",
                    "webhookReceivers": [{"id": "recv-1"}],
                    "lastUpdateTime": 1722052800,
                    "numOfAlerts": 2,
                }
            ],
        }
        route = respx.get(f"{BASE}/api/v2/dem/alert/rules").mock(
            return_value=httpx.Response(200, json=body)
        )

        response = DemResource(client._transport).alert_rules.with_response.list()
        rules = response.parse()

        assert response.json()["remainingQuota"] == 9
        assert len(rules) == 1
        rule = rules[0]
        assert rule.criteria == criteria
        assert rule.criteria_type == "event"
        assert rule.email_receiver == "ops@example.test"
        assert rule.webhook_receivers[0].id == "recv-1"
        assert rule.last_update_time == 1722052800
        assert rule.num_of_alerts == 2
        assert rule.model_extra == {}
        assert not route.calls.last.request.url.params

    def test_models_no_longer_declare_fields_the_api_never_returns(self) -> None:
        """The retired fields are gone, so a caller cannot read a permanent ``None``."""
        assert not {"target", "protocol", "interval"} & set(DemProbe.model_fields)
        assert not {"metric", "threshold", "probe_id"} & set(DemAlertRule.model_fields)
