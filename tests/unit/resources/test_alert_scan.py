"""Alert scan completion, identity checks, and bounded request contracts."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx
from pydantic import ValidationError as PydanticValidationError

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.datasearch import DatasearchWindow, ScanStopReason
from netskope.exceptions import PaginationError, ResponseValidationError, ValidationError

_PATH = "/api/v2/events/datasearch/alert"
_URL = f"https://t.goskope.com{_PATH}"
_WINDOW = DatasearchWindow(start_time=1_700_000_000, end_time=1_700_086_400)


def _rows(start: int, count: int) -> list[dict[str, Any]]:
    return [{"_id": f"id-{i}", "cci": str(i)} for i in range(start, start + count)]


def _route_rows(count: int) -> respx.Route:
    def page(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        offset, limit = int(params["offset"]), int(params["limit"])
        return httpx.Response(200, json={"result": _rows(offset, min(limit, count - offset))})

    return respx.get(_URL).mock(side_effect=page)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start_time": 2, "end_time": 1},
        {"start_time": "1", "end_time": 2},
        {"start_time": True, "end_time": 2},
        {"start_time": 1},
        {"start_time": 1, "end_time": 2, "relative": "24h"},
    ],
)
def test_window_requires_explicit_integer_bounds(kwargs: dict[str, Any]) -> None:
    with pytest.raises(PydanticValidationError):
        DatasearchWindow.model_validate(kwargs)


@respx.mock
@pytest.mark.parametrize("count", [0, 1, 4, 5])
def test_short_page_and_exact_multiple_completion(client: NetskopeClient, count: int) -> None:
    route = _route_rows(count)
    scan = client.alerts.scan_pages(window=_WINDOW, page_size=2)
    assert route.call_count == 0 and scan.summary is None
    pages = list(scan)
    assert sum(len(page.items) for page in pages) == count
    assert scan.summary is not None
    assert scan.summary.fetched == count
    assert scan.summary.requests == count // 2 + 1
    assert scan.summary.stop_reason is ScanStopReason.SHORT_PAGE
    assert scan.summary.exhausted
    assert len(pages[-1].items) == count % 2
    assert route.call_count == len(pages)
    assert list(scan) == []


@respx.mock
def test_last_yield_does_not_establish_exhaustion_until_consumed(client: NetskopeClient) -> None:
    route = _route_rows(1)
    scan = client.alerts.scan_pages(window=_WINDOW, page_size=2)
    assert len(next(scan).items) == 1
    assert scan.summary is None
    with pytest.raises(StopIteration):
        next(scan)
    assert scan.summary is not None and scan.summary.exhausted
    assert route.call_count == 1


@respx.mock
def test_close_never_claims_completion(client: NetskopeClient) -> None:
    route = _route_rows(6)
    scan = client.alerts.scan_pages(window=_WINDOW, page_size=2)
    next(scan)
    scan.close()
    assert list(scan) == []
    assert scan.summary is None
    assert route.call_count == 1


@respx.mock
def test_record_ceiling_trims_request_and_remains_lower_bound(client: NetskopeClient) -> None:
    route = _route_rows(20)
    scan = client.alerts.scan_pages(window=_WINDOW, page_size=3, max_records=5)
    assert [len(page.items) for page in scan] == [3, 2]
    assert scan.summary is not None
    assert scan.summary.fetched == 5 and scan.summary.requests == 2
    assert scan.summary.stop_reason is ScanStopReason.RECORD_LIMIT
    assert not scan.summary.exhausted
    assert [
        (call.request.url.params["offset"], call.request.url.params["limit"])
        for call in route.calls
    ] == [("0", "3"), ("3", "2")]


@respx.mock
def test_page_budget_is_explicit(client: NetskopeClient) -> None:
    route = _route_rows(20)
    scan = client.alerts.scan_pages(window=_WINDOW, page_size=2, max_pages=2)
    list(scan)
    assert scan.summary is not None
    assert scan.summary.stop_reason is ScanStopReason.PAGE_LIMIT
    assert not scan.summary.exhausted
    assert scan.summary.fetched == 4 and route.call_count == 2


@respx.mock
def test_verified_total_can_prove_exhaustion_at_ceiling(client: NetskopeClient) -> None:
    respx.get(_URL).mock(
        return_value=httpx.Response(200, json={"result": _rows(0, 2), "status": {"total": 2}})
    )
    scan = client.alerts.scan_pages(window=_WINDOW, page_size=2, max_records=2)
    assert len(list(scan)) == 1
    assert scan.summary is not None
    assert scan.summary.stop_reason is ScanStopReason.SERVER_TOTAL
    assert scan.summary.exhausted


@respx.mock
def test_short_intermediate_page_does_not_override_known_total(client: NetskopeClient) -> None:
    route = respx.get(_URL).mock(
        side_effect=[
            httpx.Response(200, json={"result": _rows(0, 1), "status": {"total": 3}}),
            httpx.Response(200, json={"result": _rows(1, 2), "status": {"total": 3}}),
        ]
    )
    scan = client.alerts.scan_pages(window=_WINDOW, page_size=2)
    assert [len(page.items) for page in scan] == [1, 2]
    assert route.calls[1].request.url.params["offset"] == "1"
    assert scan.summary is not None and scan.summary.stop_reason is ScanStopReason.SERVER_TOTAL


@respx.mock
def test_window_and_projection_are_captured_once(client: NetskopeClient) -> None:
    route = _route_rows(3)
    fields = ["cci"]
    scan = client.alerts.with_response.scan_pages(
        window=_WINDOW,
        fields=fields,
        query='app eq "Box"',
        order_by="timestamp",
        descending=False,
        page_size=2,
    )
    fields.append("later_mutation")
    responses = list(scan)
    assert responses[0].parse().items[1].cci == 1
    assert responses[0].json()["result"][1]["cci"] == "1"
    for call in route.calls:
        params = call.request.url.params
        assert params["starttime"] == str(_WINDOW.start_time)
        assert params["endtime"] == str(_WINDOW.end_time)
        assert params["fields"] == "cci,_id"
        assert params["orderbys"] == "timestamp ASC"
        assert params["query"] == 'app eq "Box"'
    assert scan.summary is not None and scan.summary.fetched == 3
    assert route.call_count == 2


@respx.mock
@pytest.mark.parametrize("fields", [None, ["_id", "cci"]])
def test_identity_projection_is_not_duplicated(
    client: NetskopeClient, fields: list[str] | None
) -> None:
    route = _route_rows(0)
    list(client.alerts.scan_pages(window=_WINDOW, fields=fields))
    params = route.calls.last.request.url.params
    assert params.get("fields") == (None if fields is None else "_id,cci")


@respx.mock
@pytest.mark.parametrize(
    "pages",
    [
        [_rows(0, 2), _rows(0, 2)],
        [_rows(0, 2), _rows(2, 2), _rows(0, 2)],
        [_rows(0, 2), _rows(2, 2), list(reversed(_rows(0, 2)))],
        [_rows(0, 2), _rows(1, 2)],
        [[{"_id": "sensitive-duplicate"}, {"_id": "sensitive-duplicate"}]],
        [[{"cci": "2"}]],
        [[{"_id": ""}]],
        [[{"_id": "  "}]],
        [_rows(0, 3)],
    ],
)
def test_untrustworthy_pages_raise_with_source_metadata(
    client: NetskopeClient, pages: list[list[dict[str, Any]]]
) -> None:
    route = respx.get(_URL).mock(
        side_effect=[
            httpx.Response(200, json={"result": page}, headers={"x-request-id": f"request-{i}"})
            for i, page in enumerate(pages)
        ]
    )
    scan = client.alerts.scan_pages(window=_WINDOW, page_size=2)
    with pytest.raises(PaginationError) as exc:
        list(scan)
    assert exc.value.request_path == _PATH
    assert exc.value.request_method == "GET"
    assert exc.value.request_id == f"request-{len(pages) - 1}"
    assert exc.value.offset == (len(pages) - 1) * 2
    assert "sensitive-duplicate" not in str(exc.value)
    assert scan.summary is None
    assert list(scan) == []
    assert route.call_count == len(pages)


@respx.mock
@pytest.mark.parametrize(
    "bodies",
    [
        [{"result": _rows(0, 2), "status": {"total": 1}}],
        [
            {"result": _rows(0, 2), "status": {"total": 3}},
            {"result": [], "status": {"total": 3}},
        ],
        [
            {"result": _rows(0, 2), "status": {"total": 3}},
            {"result": _rows(2, 1), "status": {"total": 4}},
        ],
    ],
)
def test_contradictory_totals_are_errors(
    client: NetskopeClient, bodies: list[dict[str, Any]]
) -> None:
    respx.get(_URL).mock(side_effect=[httpx.Response(200, json=body) for body in bodies])
    scan = client.alerts.scan_pages(window=_WINDOW, page_size=2)
    with pytest.raises(PaginationError) as exc:
        list(scan)
    assert exc.value.request_path == _PATH
    assert exc.value.request_method == "GET"
    assert scan.summary is None


@respx.mock
@pytest.mark.parametrize(
    "kwargs",
    [
        {"page_size": 0},
        {"page_size": 10_001},
        {"page_size": True},
        {"max_records": 0},
        {"max_records": -1},
        {"max_records": True},
        {"max_pages": 0},
        {"max_pages": True},
    ],
)
def test_scan_limits_validate_before_http(client: NetskopeClient, kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        client.alerts.scan_pages(window=_WINDOW, **kwargs)
    assert not respx.calls


@respx.mock
def test_response_scan_validates_before_yielding(client: NetskopeClient) -> None:
    respx.get(_URL).mock(return_value=httpx.Response(200, json={"result": {"not": "a list"}}))
    scan = client.alerts.with_response.scan_pages(window=_WINDOW)
    with pytest.raises(ResponseValidationError):
        next(scan)
    assert scan.summary is None


@respx.mock
async def test_async_scans_match_sync_contracts(aclient: AsyncNetskopeClient) -> None:
    route = _route_rows(4)
    scan = aclient.alerts.with_response.scan_pages(window=_WINDOW, fields=["cci"], page_size=2)
    assert not route.calls and scan.summary is None
    pages = [response async for response in scan]
    assert [len(response.parse().items) for response in pages] == [2, 2, 0]
    assert pages[0].json()["result"][1]["cci"] == "1"
    assert scan.summary is not None
    assert scan.summary.stop_reason is ScanStopReason.SHORT_PAGE
    assert scan.summary.requests == 3 and scan.summary.exhausted
    assert all(call.request.url.params["fields"] == "cci,_id" for call in route.calls)


@respx.mock
async def test_async_normal_scan_budget_and_close(aclient: AsyncNetskopeClient) -> None:
    route = _route_rows(6)
    scan = aclient.alerts.scan_pages(window=_WINDOW, page_size=2, max_pages=1)
    pages = [page async for page in scan]
    assert [item.id for item in pages[0].items] == ["id-0", "id-1"]
    assert scan.summary is not None and scan.summary.stop_reason is ScanStopReason.PAGE_LIMIT
    assert not scan.summary.exhausted
    abandoned = aclient.alerts.scan_pages(window=_WINDOW)
    await abandoned.aclose()
    assert [page async for page in abandoned] == []
    assert abandoned.summary is None
    assert route.call_count == 1


@respx.mock
async def test_async_cycle_is_an_error(aclient: AsyncNetskopeClient) -> None:
    respx.get(_URL).mock(
        side_effect=[httpx.Response(200, json={"result": _rows(offset, 2)}) for offset in (0, 2, 0)]
    )
    scan = aclient.alerts.scan_pages(window=_WINDOW, page_size=2)
    with pytest.raises(PaginationError):
        _ = [page async for page in scan]
    assert scan.summary is None
