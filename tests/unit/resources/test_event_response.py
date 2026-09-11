"""Bounded event contracts, including endpoint capabilities and safe scan evidence."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

from netskope.datasearch import DatasearchWindow, ScanStopReason
from netskope.exceptions import (
    NotFoundError,
    PaginationError,
    ResponseValidationError,
    ValidationError,
)
from netskope.models.events import AuditEvent, ClientStatusEvent, NetworkEvent, PageEvent

BASE = "https://t.goskope.com"


@pytest.mark.parametrize(
    "event_type,model",
    [
        ("application", None),
        ("network", NetworkEvent),
        ("page", PageEvent),
        ("clientstatus", ClientStatusEvent),
        ("epdlp", None),
        ("incident", None),
        ("alert", None),
        ("audit", AuditEvent),
        ("infrastructure", None),
    ],
)
@respx.mock
def test_one_request_preserves_original_and_omitted_params(client, event_type, model):
    family = "data" if event_type in ("audit", "infrastructure") else "datasearch"
    payload = {
        "result": [{"_id": "a", "timestamp": "1700000000", "future": {"x": "007"}}],
        "status": {"count": 1},
        "total": "8",
    }
    route = respx.get(f"{BASE}/api/v2/events/{family}/{event_type}").respond(200, json=payload)
    response = client.events.with_response.list_page(event_type)
    assert route.call_count == 1
    # The datasearch endpoints require `timeout` (search_alert.yaml:313-319);
    # data/audit and data/infrastructure declare no such parameter.
    expected = {} if family == "data" else {"timeout": "180"}
    assert dict(route.calls.last.request.url.params) == expected
    page = response.parse()
    assert route.call_count == 1 and len(page.items) == 1
    assert page.total == 8 and page.offset == 0 and page.limit is None and page.has_more is True
    assert page.metadata["status"] == {"count": 1}
    assert page.items[0].timestamp == datetime.fromtimestamp(1700000000, UTC)
    if model:
        assert isinstance(page.items[0], model)
    assert response.json() == payload


@pytest.mark.parametrize(
    "event_type", ["application", "network", "page", "clientstatus", "epdlp", "incident"]
)
@respx.mock
def test_projected_aggregates_and_ordering(client, event_type):
    route = respx.get(f"{BASE}/api/v2/events/datasearch/{event_type}").respond(
        200,
        json={"result": [{"_id": {"app": "Box"}, "count": "007"}], "total": 10000},
    )
    response = client.events.with_response.aggregate_page(
        event_type, group_by=["app"], fields=["app"], order_by="count", descending=True, limit=3
    )
    bucket = response.parse().items[0]
    assert bucket.count == 7 and bucket.dimensions == {"app": "Box"}
    assert response.json()["result"][0]["count"] == "007"
    assert dict(route.calls.last.request.url.params) == {
        "timeout": "180",
        "groupbys": "app",
        "fields": "app",
        "orderbys": "count DESC",
        "limit": "3",
    }
    assert response.parse().total is None


@pytest.mark.parametrize(
    "event_type,options",
    [
        ("audit", {"fields": ["user"]}),
        ("audit", {"order_by": "time"}),
        ("infrastructure", {"fields": ["user"]}),
        ("infrastructure", {"limit": 5001}),
        ("application", {"limit": True}),
        ("network", {"offset": -1}),
        ("network", {"limit": "2"}),
        ("transaction", {}),
        ("../../x", {}),
    ],
)
@respx.mock
def test_invalid_or_unsupported_request_fails_before_http(client, event_type, options):
    with pytest.raises(ValidationError):
        client.events.list_page(event_type, **options)
    assert not respx.calls


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"result": {}},
        {"result": [1]},
        {"result": [{"_id": "a", "dstport": []}]},
    ],
)
@respx.mock
def test_malformed_page_retains_raw_response(client, payload):
    path = "/api/v2/events/datasearch/network"
    respx.get(BASE + path).respond(200, json=payload, headers={"x-request-id": "event-request"})
    response = client.events.with_response.list_page("network", limit=2)
    with pytest.raises(ResponseValidationError) as caught:
        response.parse()
    assert caught.value.request_path == path
    assert caught.value.request_id == "event-request"
    assert response.json() == payload


@respx.mock
def test_page_past_its_stated_total_retains_raw_response(client):
    payload = {"result": [{"_id": "a"}, {"_id": "b"}], "total": 1}
    path = "/api/v2/events/datasearch/network"
    respx.get(BASE + path).respond(200, json=payload, headers={"x-request-id": "event-request"})
    response = client.events.with_response.list_page("network", limit=2)
    with pytest.raises(PaginationError) as caught:
        response.parse()
    assert caught.value.request_path == path
    assert caught.value.request_id == "event-request"
    assert caught.value.offset == 0
    assert response.json() == payload


@respx.mock
def test_response_cannot_exceed_requested_limit(client):
    respx.get(f"{BASE}/api/v2/events/datasearch/application").respond(
        200, json={"result": [{}, {}]}
    )
    with pytest.raises(PaginationError, match="exceeded the requested page size"):
        client.events.list_page(limit=1)


@respx.mock
def test_scan_uses_fixed_window_and_required_identity(client):
    def serve(request):
        offset = int(request.url.params["offset"])
        size = 2 if offset == 0 else 1
        return httpx.Response(
            200, json={"result": [{"_id": f"{offset + i:x}", "user": "u"} for i in range(size)]}
        )

    route = respx.get(f"{BASE}/api/v2/events/datasearch/network").mock(side_effect=serve)
    window = DatasearchWindow(start_time=1, end_time=2)
    scan = client.events.with_response.scan_pages(
        "network", window=window, fields=["user"], page_size=2
    )
    assert sum(len(response.parse().items) for response in scan) == 3
    assert scan.summary.exhausted and scan.summary.stop_reason == ScanStopReason.SHORT_PAGE
    assert [call.request.url.params["offset"] for call in route.calls] == ["0", "2"]
    for call in route.calls:
        assert call.request.url.params["fields"] == "user,_id"
        assert (
            call.request.url.params["starttime"] == "1"
            and call.request.url.params["endtime"] == "2"
        )


@pytest.mark.parametrize("rows", [[{"user": "u"}], [{"_id": "a"}]])
@respx.mock
def test_scan_fails_closed_on_missing_or_repeated_identity(client, rows):
    respx.get(f"{BASE}/api/v2/events/datasearch/network").respond(200, json={"result": rows})
    scan = client.events.with_response.scan_pages(
        "network", window=DatasearchWindow(start_time=1, end_time=2), page_size=1
    )
    with pytest.raises(PaginationError):
        list(scan)
    assert scan.summary is None
    assert list(scan) == []


@respx.mock
def test_scan_cannot_claim_exactness_for_unverified_endpoint(client):
    with pytest.raises(ValidationError):
        client.events.with_response.scan_pages(
            "audit", window=DatasearchWindow(start_time=1, end_time=2)
        )
    assert not respx.calls


@pytest.mark.parametrize(
    "payload,error",
    [({"result": []}, NotFoundError), ({"result": [{"_id": "b"}]}, ResponseValidationError)],
)
@respx.mock
def test_get_enforces_identity(client, payload, error):
    route = respx.get(f"{BASE}/api/v2/events/datasearch/network").respond(200, json=payload)
    with pytest.raises(error):
        client.events.with_response.get("a", event_type="network").parse()
    assert route.call_count == 1


@respx.mock
def test_transaction_is_metrics_not_records(client):
    payload = {
        "result": {
            "subscription/backlog_message_count": {"0": {"1": "007"}},
            "subscription/oldest_unacked_message_age": {},
            "future": True,
        }
    }
    route = respx.get(f"{BASE}/api/v2/events/metrics/transactionevents").respond(200, json=payload)
    response = client.events.with_response.transaction_metrics(hours=168)
    assert response.parse().backlog_message_count == {"0": {"1": "007"}}
    assert response.json() == payload
    assert dict(route.calls.last.request.url.params) == {"hours": "168"}


@pytest.mark.parametrize("hours", [0, 169, True, "24"])
@respx.mock
def test_transaction_hours_validation(client, hours):
    with pytest.raises(ValidationError):
        client.events.with_response.transaction_metrics(hours=hours)
    assert not respx.calls


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize(
    "options,expected",
    [
        ({"query": 'user eq "a@ex.com"'}, 'user eq "a@ex.com"'),
        ({"audit_type": "admin", "query": "x"}, '(x) and type eq "admin"'),
    ],
    ids=["query", "query-with-audit-type"],
)
@respx.mock
async def test_audit_page_accepts_jql(client, aclient, asynchronous, options, expected):
    """audit.yaml:13-18 declares `query`; the SDK no longer refuses it."""
    route = respx.get(f"{BASE}/api/v2/events/data/audit").respond(200, json={"result": []})
    resource = (aclient if asynchronous else client).events.with_response
    response = resource.list_page("audit", **options)
    if asynchronous:
        response = await response
    assert response.parse().items == []
    assert route.calls.last.request.url.params["query"] == expected


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@respx.mock
async def test_audit_lookup_by_id_uses_the_query_filter(client, aclient, asynchronous):
    """A lookup by `_id` is an ordinary audit.yaml:13-18 query expression."""
    route = respx.get(f"{BASE}/api/v2/events/data/audit").respond(
        200, json={"result": [{"_id": "deadbeef"}]}
    )
    resource = (aclient if asynchronous else client).events.with_response
    response = resource.get("deadbeef", event_type="audit")
    if asynchronous:
        response = await response
    assert response.parse().id == "deadbeef"
    params = route.calls.last.request.url.params
    assert params["query"] == '_id eq "deadbeef"' and "timeout" not in params


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@respx.mock
async def test_audit_page_sends_the_type_as_a_query_clause(client, aclient, asynchronous):
    """audit.yaml:12-72 lists no `type` parameter, so the filter travels in `query`."""
    route = respx.get(f"{BASE}/api/v2/events/data/audit").respond(
        200, json={"result": [{"_id": "a", "user": "admin"}]}
    )
    resource = (aclient if asynchronous else client).events
    page = resource.list_page("audit", audit_type="admin", limit=5)
    if asynchronous:
        page = await page
    assert isinstance(page.items[0], AuditEvent)
    assert dict(route.calls.last.request.url.params) == {
        "query": 'type eq "admin"',
        "limit": "5",
    }
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@respx.mock
async def test_audit_type_is_rejected_for_jql_endpoints(client, aclient, asynchronous):
    resource = (aclient if asynchronous else client).events.with_response
    with pytest.raises(ValidationError, match="audit_type"):
        response = resource.list_page("network", audit_type="admin")
        if asynchronous:
            await response
    assert not respx.calls


@pytest.mark.parametrize(
    "event_type,model",
    [("clientstatus", ClientStatusEvent), ("network", NetworkEvent), ("audit", AuditEvent)],
)
@respx.mock
def test_iterator_and_page_share_one_record_model(client, event_type, model):
    family = "data" if event_type == "audit" else "datasearch"
    route = respx.get(f"{BASE}/api/v2/events/{family}/{event_type}").respond(
        200, json={"result": [{"_id": "a"}], "status": {"total": 1}}
    )
    assert isinstance(next(iter(client.events.list(event_type))), model)
    assert isinstance(client.events.list_page(event_type).items[0], model)
    assert {call.request.url.path for call in route.calls} == {
        f"/api/v2/events/{family}/{event_type}"
    }


@respx.mock
async def test_async_page_aggregate_scan_and_metrics_parity(aclient):
    route = respx.get(f"{BASE}/api/v2/events/datasearch/network").respond(
        200, json={"result": [{"_id": "a", "dstport": "443"}]}
    )
    response = await aclient.events.with_response.list_page("network", limit=2)
    assert response.parse().items[0].dst_port == 443
    scan = aclient.events.with_response.scan_pages(
        "network", window=DatasearchWindow(start_time=1, end_time=2), page_size=2
    )
    pages = [page async for page in scan]
    assert len(pages) == 1 and scan.summary.exhausted
    route.respond(200, json={"result": [{"_id": {"app": "Box"}, "count": "2"}]})
    assert (await aclient.events.aggregate_page("network", group_by="app")).items[0].count == 2
    metrics = respx.get(f"{BASE}/api/v2/events/metrics/transactionevents").respond(
        200, json={"result": {}}
    )
    assert (await aclient.events.transaction_metrics()).backlog_message_count == {}
    assert metrics.calls.last.request.url.params["hours"] == "24"
