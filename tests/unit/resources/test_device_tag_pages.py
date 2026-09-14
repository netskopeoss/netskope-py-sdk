"""Device-tag body pagination and retained response contracts."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import (
    NotFoundError,
    PaginationError,
    ResponseValidationError,
    ValidationError,
)

URL = "https://t.goskope.com/api/v2/devices/device/tags/gettags"
TAG = {
    "id": "7",
    "name": "prod",
    "description": "Production",
    "device_count": None,
    "future": {"x": 1},
}


def envelope(rows: list[dict[str, Any]], **paging: Any) -> dict[str, Any]:
    return {"success": True, "data": {"data": rows, **paging}, "version": "next"}


@respx.mock
def test_page_retains_metadata_and_original_values(client: NetskopeClient) -> None:
    body = envelope([TAG], total_count="8", offset=2, limit=20)
    route = respx.post(URL).respond(200, json=body, headers={"x-request-id": "tags-page"})
    response = client.devices.tags.with_response.list_page(name="prod", offset=2)
    page = response.parse()
    assert page is response.parse()
    assert page.items[0].id == 7
    assert page.items[0].device_count is None
    assert page.items[0].model_extra == {"future": {"x": 1}}
    assert (page.total, page.offset, page.limit, page.has_more) == (8, 2, 20, True)
    assert page.metadata == {
        "success": True,
        "version": "next",
        "data": {"total_count": "8", "offset": 2, "limit": 20},
    }
    assert response.json() == body
    assert response.request_id == "tags-page"
    assert route.call_count == 1
    request = route.calls[0].request
    assert not request.url.params
    assert json.loads(request.content) == {"offset": 2, "limit": 20, "name": "prod"}


@pytest.mark.parametrize("body", [[TAG], {"data": [TAG]}, {"result": [TAG]}, {"Resources": [TAG]}])
@respx.mock
def test_legacy_list_envelopes_stay_supported(client: NetskopeClient, body: Any) -> None:
    respx.post(URL).respond(200, json=body)
    page = client.devices.tags.list_page()
    assert page.items[0].id == 7
    assert page.total is None
    assert page.has_more is None


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"data": {}},
        envelope([{"id": "secret-invalid"}]),
        envelope([7]),
        envelope([], total_count=True),
    ],
)
@respx.mock
def test_malformed_page_keeps_original_response(client: NetskopeClient, body: Any) -> None:
    respx.post(URL).respond(200, json=body, headers={"x-request-id": "bad-page"})
    response = client.devices.tags.with_response.list_page()
    with pytest.raises(ResponseValidationError) as caught:
        response.parse()
    assert response.json() == body
    assert caught.value.request_id == "bad-page"
    assert caught.value.request_method == "POST"
    assert "secret-invalid" not in str(caught.value)


@pytest.mark.parametrize("rows", [[{"id": 8}], [{"name": "missing-id"}], [TAG, {"id": 8}]])
@respx.mock
def test_lookup_verifies_identity(client: NetskopeClient, rows: list[dict[str, Any]]) -> None:
    respx.post(URL).respond(200, json=envelope(rows))
    with pytest.raises(ResponseValidationError):
        client.devices.tags.get(7)


@respx.mock
def test_lookup_empty_has_request_context(client: NetskopeClient) -> None:
    respx.post(URL).respond(200, json=envelope([]), headers={"x-request-id": "missing-tag"})
    with pytest.raises(NotFoundError) as caught:
        client.devices.tags.get(7)
    assert caught.value.request_id == "missing-tag"
    assert caught.value.request_path == "/api/v2/devices/device/tags/gettags"


@pytest.mark.parametrize("server_cap", [100, 10])
@respx.mock
def test_traverses_203_tags_even_with_short_intermediate_pages(
    client: NetskopeClient, server_cap: int
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["name"] == "prod"
        assert payload["limit"] == 100
        assert not request.url.params
        offset = payload["offset"]
        records = [{"id": i} for i in range(offset, min(offset + server_cap, 203))]
        return httpx.Response(
            200, json=envelope(records, total_count=203, offset=offset, limit=server_cap)
        )

    route = respx.post(URL).mock(side_effect=respond)
    tags = list(client.devices.tags.iter_all(name="prod"))
    assert [tag.id for tag in tags] == list(range(203))
    assert [json.loads(call.request.content)["offset"] for call in route.calls] == list(
        range(0, 203, server_cap)
    )


@respx.mock
def test_unknown_total_requires_empty_page_and_advances_returned_count(
    client: NetskopeClient,
) -> None:
    route = respx.post(URL).mock(
        side_effect=[
            httpx.Response(200, json=envelope([{"id": 1}], offset=0)),
            httpx.Response(200, json=envelope([{"id": 2}], offset=1)),
            httpx.Response(200, json=envelope([], offset=2)),
        ]
    )
    pages = list(client.devices.tags.with_response.iter_pages())
    assert [len(response.parse().items) for response in pages] == [1, 1, 0]
    assert [json.loads(call.request.content)["offset"] for call in route.calls] == [0, 1, 2]


@pytest.mark.parametrize(
    "body",
    [
        envelope([], total_count=1),
        envelope([{"id": 1}], offset=20),
        envelope([{"id": 1}, {"id": 1}]),
        envelope([{"name": "missing"}]),
    ],
)
@respx.mock
def test_unsafe_pages_raise_instead_of_completing(client: NetskopeClient, body: Any) -> None:
    respx.post(URL).respond(200, json=body, headers={"x-request-id": "unsafe-page"})
    with pytest.raises(PaginationError) as caught:
        list(client.devices.tags.iter_pages())
    assert caught.value.request_id == "unsafe-page"
    assert caught.value.offset == 0


@respx.mock
def test_bounded_page_rejects_contradictory_total(client: NetskopeClient) -> None:
    respx.post(URL).respond(200, json=envelope([{"id": 1}], total_count=0))
    with pytest.raises(PaginationError):
        client.devices.tags.list_page()


@respx.mock
def test_bounded_page_rejects_more_tags_than_requested(client: NetskopeClient) -> None:
    route = respx.post(URL).respond(200, json=envelope([{"id": 1}, {"id": 2}], total_count=9))
    with pytest.raises(PaginationError, match="exceeded the requested page size") as caught:
        client.devices.tags.list_page(limit=1)
    assert caught.value.offset == 0
    assert json.loads(route.calls.last.request.content) == {"offset": 0, "limit": 1}


@respx.mock
def test_bounded_page_rejects_an_offset_the_service_ignored(client: NetskopeClient) -> None:
    respx.post(URL).respond(200, json=envelope([{"id": 1}], total_count=9, offset=0))
    with pytest.raises(PaginationError, match="offset does not match") as caught:
        client.devices.tags.list_page(offset=4)
    assert caught.value.offset == 4


@respx.mock
def test_cycle_a_b_a_is_rejected(client: NetskopeClient) -> None:
    route = respx.post(URL).mock(
        side_effect=[
            httpx.Response(200, json=envelope([{"id": 1}])),
            httpx.Response(200, json=envelope([{"id": 2}])),
            httpx.Response(200, json=envelope([{"id": 1}])),
        ]
    )
    with pytest.raises(PaginationError, match="repeated records"):
        list(client.devices.tags.iter_all())
    assert route.call_count == 3


@respx.mock
def test_page_limit_is_not_successful_completion(client: NetskopeClient) -> None:
    route = respx.post(URL).respond(200, json=envelope([{"id": 1}]))
    with pytest.raises(PaginationError, match="page limit"):
        list(client.devices.tags.iter_pages(max_pages=1))
    assert route.call_count == 1


@pytest.mark.parametrize("last_page", [envelope([]), envelope([], total_count=1)])
@respx.mock
def test_remembers_total_when_later_pages_omit_or_change_it(
    client: NetskopeClient, last_page: dict[str, Any]
) -> None:
    respx.post(URL).mock(
        side_effect=[
            httpx.Response(200, json=envelope([{"id": 1}], total_count=5)),
            httpx.Response(200, json=last_page),
        ]
    )
    with pytest.raises(PaginationError):
        list(client.devices.tags.iter_pages())


@respx.mock
def test_remembered_total_can_establish_completion(client: NetskopeClient) -> None:
    route = respx.post(URL).mock(
        side_effect=[
            httpx.Response(200, json=envelope([{"id": 1}], total_count=2)),
            httpx.Response(200, json=envelope([{"id": 2}])),
        ]
    )
    assert [tag.id for tag in client.devices.tags.iter_all()] == [1, 2]
    assert route.call_count == 2


@respx.mock
def test_page_limit_allows_verified_last_page(client: NetskopeClient) -> None:
    respx.post(URL).respond(200, json=envelope([{"id": 1}], total_count=1))
    assert len(list(client.devices.tags.iter_pages(max_pages=1))) == 1


@respx.mock
def test_offset_beyond_known_total_is_an_empty_result(client: NetskopeClient) -> None:
    respx.post(URL).respond(200, json=envelope([], total_count=5, offset=10))
    pages = list(client.devices.tags.iter_pages(offset=10))
    assert len(pages) == 1
    assert pages[0].items == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"offset": True},
        {"offset": 1.5},
        {"offset": -1},
        {"limit": True},
        {"limit": 1.5},
        {"limit": 101},
    ],
)
def test_page_rejects_invalid_bounds_without_http(
    client: NetskopeClient, kwargs: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        client.devices.tags.list_page(**kwargs)


@pytest.mark.parametrize("max_pages", [True, 1.5, 0, 1001])
def test_iterator_rejects_unbounded_history(client: NetskopeClient, max_pages: Any) -> None:
    with pytest.raises(ValidationError):
        list(client.devices.tags.iter_pages(max_pages=max_pages))


@respx.mock
async def test_async_paging_matches_sync_contract(aclient: AsyncNetskopeClient) -> None:
    route = respx.post(URL).mock(
        side_effect=[
            httpx.Response(200, json=envelope([{"id": 1}], total_count=2, offset=0)),
            httpx.Response(200, json=envelope([{"id": 2}], total_count=2, offset=1)),
        ]
    )
    assert [item.id async for item in aclient.devices.tags.iter_all()] == [1, 2]
    assert [json.loads(call.request.content)["offset"] for call in route.calls] == [0, 1]


@respx.mock
async def test_async_response_and_lookup_validation(aclient: AsyncNetskopeClient) -> None:
    route = respx.post(URL).respond(200, json=envelope([TAG]))
    response = await aclient.devices.tags.with_response.get(7)
    assert response.parse().id == 7
    assert response.json()["data"]["data"] == [TAG]
    assert json.loads(route.calls.last.request.content) == {"id": 7}
    with pytest.raises(ResponseValidationError):
        await aclient.devices.tags.get(8)


@respx.mock
async def test_async_repeated_page_is_an_error(aclient: AsyncNetskopeClient) -> None:
    respx.post(URL).respond(200, json=envelope([TAG]))
    with pytest.raises(PaginationError, match="repeated records"):
        _ = [page async for page in aclient.devices.tags.iter_pages()]
