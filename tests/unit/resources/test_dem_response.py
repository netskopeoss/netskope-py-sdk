"""DEM/ADEM response shapes, native units, and single-request parity."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
import respx
from pydantic import BaseModel

from netskope.exceptions import APIError, ResponseValidationError, ValidationError

BASE = "https://t.goskope.com"
WINDOW = {"start_time": 1000, "end_time": 2000}
QUERY = {"begin": 1000000, "end": 2000000}
CASES = [
    (
        "probes",
        "list",
        (),
        {},
        "GET",
        "/api/v2/dem/appprobes",
        {"data": [{"id": "p", "interval": "60"}]},
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
        {"rules": [{"id": "r", "threshold": "7.5"}]},
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
        {"from": "ux_score", "select": ["user"], "begin": 1000000, "end": 2000000},
    ),
    (
        "query",
        "get_dataset",
        ("http_all", ["user"]),
        QUERY,
        "POST",
        "/api/v2/dem/query/getdataset",
        {"data": [{"user": "u"}]},
        {"from": "http_all", "select": ["user"], "begin": 1000000, "end": 2000000},
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
        {"from": "traceroute_pop", "begin": 1000000, "end": 2000000},
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
        {"entities": [{"user": "u"}]},
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
def test_native_query_caps_are_preserved(client):
    metrics = respx.post(f"{BASE}/api/v2/dem/query/getdata").respond(200, json={"data": []})
    dataset = respx.post(f"{BASE}/api/v2/dem/query/getdataset").respond(200, json={"data": []})
    entities = respx.post(f"{BASE}/api/v2/dem/query/getentities").respond(200, json={"users": []})
    client.dem.query.with_response.get_data("ux_score", ["u"], **QUERY, limit=100000).parse()
    client.dem.query.get_dataset("http_all", ["u"], **QUERY, limit=100000)
    client.dem.query.with_response.get_entities(**WINDOW, limit=100000).parse()
    assert json.loads(metrics.calls.last.request.content)["limit"] == 50000
    assert json.loads(dataset.calls.last.request.content)["limit"] == 9999
    assert entities.calls.last.request.url.params["limit"] == "100"


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
    "group,args,path,payload",
    [
        (
            "probes",
            ("probe", "https://example.com"),
            "/api/v2/dem/appprobes",
            {"id": "p", "interval": "60"},
        ),
        (
            "alert_rules",
            ("rule", "latency", 20.0),
            "/api/v2/dem/alert/rules",
            {"id": "r", "threshold": "20"},
        ),
    ],
)
@respx.mock
async def test_mutations_are_typed_and_not_replayed(
    client, aclient, asynchronous, group, args, path, payload
):
    route = respx.post(BASE + path).respond(201, json=payload)
    method = getattr((aclient if asynchronous else client).dem, group).with_response.create
    response = method(*args)
    if asynchronous:
        response = await response
    assert isinstance(response.parse(), BaseModel) and response.json() == payload
    assert route.call_count == 1
    route.respond(503, json={"message": "unavailable"})
    with pytest.raises(APIError):
        result = method(*args)
        if asynchronous:
            await result
    assert route.call_count == 2
