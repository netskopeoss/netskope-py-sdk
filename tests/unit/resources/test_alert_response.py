"""Typed alert page contracts and original-response compatibility."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import respx
from pydantic import ValidationError as PydanticValidationError

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import (
    NotFoundError,
    PaginationError,
    ResponseValidationError,
    ValidationError,
)
from netskope.models.alerts import Alert, DatasearchBucket

_PATH = "/api/v2/events/datasearch/alert"
_URL = f"https://t.goskope.com{_PATH}"


@respx.mock
@pytest.mark.parametrize("key", ["result", "data"])
def test_page_retains_metadata_and_original_values(client: NetskopeClient, key: str) -> None:
    body = {
        key: [{"_id": "a1", "timestamp": 1_700_000_000, "cci": "42", "new_field": {"n": 2}}],
        "status": {"total": "12", "count": 1},
        "execution": "COMPLETE",
    }
    route = respx.get(_URL).mock(
        return_value=httpx.Response(200, json=body, headers={"x-request-id": "alert-request"})
    )
    response = client.alerts.with_response.list_page(offset=5, limit=3)
    page = response.parse()
    assert page is response.parse()
    assert (page.offset, page.limit, page.total, page.has_more) == (5, 3, 12, True)
    assert page.metadata == {"status": {"total": "12", "count": 1}, "execution": "COMPLETE"}
    alert = page.items[0]
    assert alert.cci == 42
    assert alert.timestamp == datetime.fromtimestamp(1_700_000_000, UTC)
    assert alert.model_extra == {"new_field": {"n": 2}}
    assert response.json() == body
    assert response.request_id == "alert-request"
    assert response.request_path == _PATH
    assert route.call_count == 1


@respx.mock
def test_default_page_omits_parameters(client: NetskopeClient) -> None:
    """Only the spec-required timeout is sent; search_alert.yaml:313-319."""
    route = respx.get(_URL).mock(
        return_value=httpx.Response(200, json={"result": [{"alert_name": "projected"}]})
    )
    page = client.alerts.list_page()
    assert dict(route.calls.last.request.url.params) == {"timeout": "180"}
    assert (page.offset, page.limit, page.total, page.has_more) == (0, None, None, None)
    assert page.items[0].id is None
    assert page.items[0].model_fields_set == {"alert_name"}
    assert route.call_count == 1


@respx.mock
def test_page_count_is_not_a_total(client: NetskopeClient) -> None:
    respx.get(_URL).mock(
        return_value=httpx.Response(200, json={"result": [{"_id": "a"}], "status": {"count": 1}})
    )
    page = client.alerts.list_page(limit=1)
    assert page.total is None
    assert page.has_more is None
    assert page.metadata == {"status": {"count": 1}}


@respx.mock
@pytest.mark.parametrize(("offset", "total"), [(0, 0), (0, 1), (1, 2), (5, 6)])
def test_nonempty_page_rejects_contradictory_total(
    client: NetskopeClient, offset: int, total: int
) -> None:
    body = {"result": [{"_id": "a1"}, {"_id": "a2"}], "status": {"total": total}}
    respx.get(_URL).mock(
        return_value=httpx.Response(200, json=body, headers={"x-request-id": "bad-total"})
    )
    response = client.alerts.with_response.list_page(offset=offset, limit=2)
    with pytest.raises(PaginationError) as exc:
        response.parse()
    assert exc.value.request_path == _PATH
    assert exc.value.request_method == "GET"
    assert exc.value.request_id == "bad-total"
    assert exc.value.offset == offset
    assert response.json() == body


@respx.mock
def test_empty_page_beyond_total_is_valid(client: NetskopeClient) -> None:
    respx.get(_URL).mock(
        return_value=httpx.Response(200, json={"data": [], "status": {"total": 2}})
    )
    page = client.alerts.list_page(offset=5, limit=2)
    assert page.items == []
    assert (page.offset, page.total, page.has_more) == (5, 2, False)


@respx.mock
@pytest.mark.parametrize(
    ("descending", "expected"),
    [(None, "timestamp"), (True, "timestamp DESC"), (False, "timestamp ASC")],
)
def test_page_uses_canonical_orderbys(
    client: NetskopeClient, descending: bool | None, expected: str
) -> None:
    route = respx.get(_URL).mock(return_value=httpx.Response(200, json={"result": []}))
    client.alerts.list_page(
        query='alert_type eq "DLP"',
        fields=["_id", "timestamp"],
        start_time=datetime(2024, 1, 1, tzinfo=UTC),
        end_time=1_704_153_600,
        order_by="timestamp",
        descending=descending,
        offset=0,
        limit=10_000,
    )
    params = dict(route.calls.last.request.url.params)
    assert params == {
        "timeout": "180",
        "query": 'alert_type eq "DLP"',
        "fields": "_id,timestamp",
        "starttime": "1704067200",
        "endtime": "1704153600",
        "orderbys": expected,
        "offset": "0",
        "limit": "10000",
    }


@respx.mock
@pytest.mark.parametrize(
    "kwargs",
    [
        {"offset": -1},
        {"offset": True},
        {"limit": 0},
        {"limit": 10_001},
        {"limit": "10"},
        {"start_time": datetime(2024, 1, 1)},
        {"start_time": True},
        {"start_time": 2, "end_time": 1},
        {"fields": [2]},
    ],
)
def test_page_validates_before_http(client: NetskopeClient, kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        client.alerts.with_response.list_page(**kwargs)
    assert not respx.calls


@respx.mock
@pytest.mark.parametrize(
    "body", [None, [], {}, {"result": {}}, {"data": None}, {"result": ["secret-value"]}]
)
def test_malformed_envelopes_retain_original_json(client: NetskopeClient, body: Any) -> None:
    respx.get(_URL).mock(
        return_value=httpx.Response(
            200, content=json.dumps(body), headers={"x-request-id": "malformed-alert"}
        )
    )
    response = client.alerts.with_response.list_page()
    with pytest.raises(ResponseValidationError) as exc:
        response.parse()
    assert exc.value.request_path == _PATH
    assert exc.value.request_method == "GET"
    assert exc.value.request_id == "malformed-alert"
    assert "secret-value" not in str(exc.value)
    assert response.json() == body
    assert len(respx.calls) == 1


@respx.mock
def test_nonempty_aggregates_are_not_alerts(client: NetskopeClient) -> None:
    body = {
        "data": [
            {"_id": {"alert_type": "DLP", "user": None}, "count": "7", "metric": 3.5},
            {"_id": {"alert_type": "Malware"}},
        ],
        "status": {"total": 1_000, "count": 2},
    }
    route = respx.get(_URL).mock(return_value=httpx.Response(200, json=body))
    response = client.alerts.with_response.aggregate_page(
        group_by=["alert_type", "user"], fields=["_id", "count"], limit=3
    )
    page = response.parse()
    assert isinstance(page.items[0], DatasearchBucket)
    assert page.items[0].dimensions == {"alert_type": "DLP", "user": None}
    assert page.items[0].count == 7
    assert page.items[0].model_extra == {"metric": 3.5}
    assert page.items[1].count is None
    assert page.total is None and page.has_more is None
    assert page.metadata == {"status": {"total": 1_000, "count": 2}}
    assert response.json() == body
    assert dict(route.calls.last.request.url.params) == {
        "timeout": "180",
        "groupbys": "alert_type,user",
        "fields": "_id,count",
        "limit": "3",
    }
    assert route.call_count == 1
    with pytest.raises(PydanticValidationError):
        Alert.model_validate(body["data"][0])


@respx.mock
def test_projected_bucket_and_normal_aggregate(client: NetskopeClient) -> None:
    route = respx.get(_URL).mock(return_value=httpx.Response(200, json={"result": [{"count": 2}]}))
    page = client.alerts.aggregate_page(group_by="app", fields=["count"])
    assert page.items[0].dimensions is None
    assert page.items[0].count == 2
    assert route.call_count == 1


@respx.mock
@pytest.mark.parametrize("group_by", ["", []])
def test_empty_grouping_fails_before_http(
    client: NetskopeClient, group_by: str | list[str]
) -> None:
    with pytest.raises(ValidationError):
        client.alerts.aggregate_page(group_by=group_by)
    assert not respx.calls


@respx.mock
def test_aggregate_rejects_record_shaped_id(client: NetskopeClient) -> None:
    body = {"result": [{"_id": "a1", "count": 1}]}
    respx.get(_URL).mock(return_value=httpx.Response(200, json=body))
    response = client.alerts.with_response.aggregate_page(group_by="app")
    with pytest.raises(ResponseValidationError):
        response.parse()
    assert response.json() == body


@respx.mock
def test_get_retains_original_envelope_and_not_found_metadata(client: NetskopeClient) -> None:
    route = respx.get(_URL).mock(
        side_effect=[
            httpx.Response(200, json={"data": [{"_id": "a1", "cci": "8"}]}),
            httpx.Response(200, json={"result": []}, headers={"x-request-id": "missing"}),
        ]
    )
    response = client.alerts.with_response.get("a1")
    assert response.parse().cci == 8
    assert response.json() == {"data": [{"_id": "a1", "cci": "8"}]}
    assert dict(route.calls[0].request.url.params) == {
        "timeout": "180",
        "query": '_id eq "a1"',
        # search_alert.yaml:340-345 defaults `limit` to 10000 (SPEC2-EV-4).
        "limit": "1",
    }
    assert route.call_count == 1
    missing = client.alerts.with_response.get("b2")
    with pytest.raises(NotFoundError) as exc:
        missing.parse()
    assert exc.value.request_path == _PATH
    assert exc.value.request_id == "missing"
    assert missing.json() == {"result": []}


@respx.mock
def test_legacy_list_accepts_data_envelope_and_stays_lazy(client: NetskopeClient) -> None:
    route = respx.get(_URL).mock(
        return_value=httpx.Response(200, json={"data": [{"_id": "a1"}], "status": {"total": 1}})
    )
    pending = client.alerts.list()
    assert route.call_count == 0
    assert [alert.id for alert in pending] == ["a1"]
    assert route.call_count == 1


@pytest.mark.parametrize("value", ["unrecognized-secret-timestamp", "", {}, [], True, 10**100])
def test_unreadable_timestamps_become_none_without_rejecting_the_record(value: Any) -> None:
    alert = Alert.model_validate({"_id": "a1", "timestamp": value})
    assert alert.timestamp is None
    assert alert.id == "a1"


def test_iso_timestamp_is_supported_and_missing_is_distinct() -> None:
    alert = Alert.model_validate({"timestamp": "2024-01-01T00:00:00Z"})
    assert alert.timestamp == datetime(2024, 1, 1, tzinfo=UTC)
    assert Alert.model_validate({}).timestamp is None
    assert "timestamp" not in Alert.model_validate({}).model_fields_set
    assert "timestamp" in Alert.model_validate({"timestamp": None}).model_fields_set


@respx.mock
def test_bad_field_error_is_payload_free(client: NetskopeClient) -> None:
    body = {"result": [{"_id": "a1", "count": "secret-invalid-value"}]}
    respx.get(_URL).mock(return_value=httpx.Response(200, json=body))
    response = client.alerts.with_response.list_page()
    with pytest.raises(ResponseValidationError) as exc:
        response.parse()
    assert "secret-invalid-value" not in str(exc.value)
    assert exc.value.field_errors
    assert response.json() == body


@respx.mock
async def test_async_pages_aggregate_and_get(aclient: AsyncNetskopeClient) -> None:
    route = respx.get(_URL).mock(
        side_effect=[
            httpx.Response(200, json={"data": [{"_id": "a1", "cci": "4"}]}),
            httpx.Response(200, json={"result": [{"_id": {"app": "Box"}, "count": 2}]}),
            httpx.Response(200, json={"result": [{"_id": "a1"}]}),
        ]
    )
    response = await aclient.alerts.with_response.list_page(
        order_by="timestamp", descending=False, offset=2, limit=1
    )
    assert response.parse().items[0].cci == 4
    assert response.json()["data"][0]["cci"] == "4"
    assert route.calls[0].request.url.params["orderbys"] == "timestamp ASC"
    grouped = await aclient.alerts.aggregate_page(group_by="app")
    assert grouped.items[0].dimensions == {"app": "Box"}
    assert (await aclient.alerts.get("a1")).id == "a1"
    assert route.call_count == 3


@respx.mock
async def test_async_malformed_response(aclient: AsyncNetskopeClient) -> None:
    respx.get(_URL).mock(return_value=httpx.Response(200, json={"data": {"secret": "value"}}))
    response = await aclient.alerts.with_response.list_page()
    with pytest.raises(ResponseValidationError) as exc:
        response.parse()
    assert exc.value.request_path == _PATH
    assert response.json() == {"data": {"secret": "value"}}


@respx.mock
async def test_async_contradictory_total_is_rejected(aclient: AsyncNetskopeClient) -> None:
    respx.get(_URL).mock(
        return_value=httpx.Response(200, json={"data": [{"_id": "a1"}], "total": 0})
    )
    with pytest.raises(PaginationError) as exc:
        await aclient.alerts.list_page()
    assert exc.value.request_path == _PATH


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_page_rejects_more_rows_than_the_requested_limit(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    body = {"result": [{"_id": f"a{index}"} for index in range(5)], "status": {"total": 100}}
    route = respx.get(_URL).mock(
        return_value=httpx.Response(200, json=body, headers={"x-request-id": "oversized-page"})
    )
    with pytest.raises(PaginationError, match="exceeded the requested page size") as caught:
        if asynchronous:
            await aclient.alerts.list_page(offset=10, limit=2)
        else:
            client.alerts.list_page(offset=10, limit=2)
    assert caught.value.offset == 10
    assert caught.value.request_path == _PATH
    assert caught.value.request_id == "oversized-page"
    assert route.call_count == 1
