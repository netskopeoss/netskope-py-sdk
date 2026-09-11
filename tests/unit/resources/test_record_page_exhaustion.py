"""Only supported bounded record queries use short-page exhaustion evidence."""

from __future__ import annotations

import pytest
import respx

BASE = "https://t.goskope.com"
RECORD_ROUTES = [
    ("alerts", None, "/api/v2/events/datasearch/alert"),
    ("events", "network", "/api/v2/events/datasearch/network"),
    ("events", "audit", "/api/v2/events/data/audit"),
    ("events", "infrastructure", "/api/v2/events/data/infrastructure"),
    ("incidents", None, "/api/v2/events/datasearch/incident"),
]


@pytest.mark.parametrize("namespace,event_type,path", RECORD_ROUTES)
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    "count,limit,total,offset,has_more",
    [
        (0, 5, None, 0, False),
        (1, 5, None, 0, False),
        (5, 5, None, 0, None),
        (1, None, None, 0, None),
        (0, None, None, 0, None),
        (1, 5, 10, 0, True),
        (1, 5, 1, 0, False),
        (1, 5, None, 4, False),
    ],
)
@respx.mock
async def test_record_page_continuation_is_endpoint_specific(
    client,
    aclient,
    asynchronous,
    namespace,
    event_type,
    path,
    count,
    limit,
    total,
    offset,
    has_more,
):
    body = {"result": [{} for _ in range(count)], "status": {"count": count}}
    if total is not None:
        body["total"] = total
    route = respx.get(BASE + path).respond(200, json=body)
    sdk = aclient if asynchronous else client
    operation = getattr(sdk, namespace).with_response.list_page
    options = {"limit": limit, "offset": offset}
    response = operation(event_type, **options) if event_type else operation(**options)
    if asynchronous:
        response = await response
    page = response.parse()
    assert page.has_more is has_more
    assert page.total == total and page.offset == offset and page.limit == limit
    assert len(page.items) == count and response.json() == body
    assert route.call_count == 1
    assert ("limit" in route.calls.last.request.url.params) is (limit is not None)


@pytest.mark.parametrize("namespace", ["alerts", "events", "incidents"])
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("limit", [None, 5])
@respx.mock
async def test_short_aggregate_is_not_record_exhaustion(
    client, aclient, asynchronous, namespace, limit
):
    event_type = {"alerts": "alert", "events": "network", "incidents": "incident"}[namespace]
    route = respx.get(f"{BASE}/api/v2/events/datasearch/{event_type}").respond(
        200, json={"result": [{"_id": {"app": "Box"}, "count": "4"}], "total": 1000}
    )
    sdk = aclient if asynchronous else client
    operation = getattr(sdk, namespace).with_response.aggregate_page
    options = {"group_by": "app", "limit": limit}
    response = operation(event_type, **options) if namespace == "events" else operation(**options)
    if asynchronous:
        response = await response
    page = response.parse()
    assert page.total is None and page.has_more is None
    assert len(page.items) == 1 and page.items[0].count == 4
    assert route.call_count == 1
