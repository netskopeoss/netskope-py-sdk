"""Publisher response access executes once and keeps typed results precise."""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.core.pagination import Page
from netskope.exceptions import ResponseValidationError, ValidationError
from netskope.models import Publisher
from netskope.response import ApiResponse

URL = "https://t.goskope.com/api/v2/infrastructure/publishers"


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_response_get_preserves_wire_values_and_validates_once(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    body = {"data": {"publisher_id": "42", "publisher_name": "Example"}, "status": "success"}
    route = respx.get(f"{URL}/42").mock(return_value=httpx.Response(200, json=body))
    result = (
        await aclient.publishers.with_response.get(42)
        if asynchronous
        else client.publishers.with_response.get(42)
    )
    assert isinstance(result, ApiResponse)
    publisher = result.parse()
    assert isinstance(publisher, Publisher)
    assert publisher.publisher_id == 42
    assert result.parse() is publisher
    assert result.json() == body
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_response_page_preserves_envelope_and_page_metadata(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    body = {
        "data": {
            "publishers": [{"publisher_id": n, "future": {"region": "east"}} for n in range(200)]
        },
        "total": 200,
        "status": "success",
    }
    route = respx.get(URL).mock(return_value=httpx.Response(200, json=body))
    result = (
        await aclient.publishers.with_response.list_page(limit=20)
        if asynchronous
        else client.publishers.with_response.list_page(limit=20)
    )
    page = result.parse()
    assert isinstance(page, Page)
    assert isinstance(page.items[0], Publisher)
    assert len(page.items) == 20
    assert page.total == 200
    assert page.has_more is True
    assert page.metadata == {"total": 200, "status": "success"}
    assert result.json() == body
    # ``getNPAPublishers`` declares only ``fields`` (npa_publishers.yaml:1024-1032),
    # so the window is applied locally and nothing is sent.
    assert not route.calls.last.request.url.params
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_created_response_can_be_inspected_after_invalid_model(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    body = {"data": {"publisher_id": {"secret": "response-secret"}}, "status": "success"}
    route = respx.post(URL).mock(
        return_value=httpx.Response(201, json=body, headers={"x-request-id": "created-42"})
    )
    result = (
        await aclient.publishers.with_response.create("Example")
        if asynchronous
        else client.publishers.with_response.create("Example")
    )
    for _ in range(2):
        with pytest.raises(ResponseValidationError) as caught:
            result.parse()
        assert caught.value.request_method == "POST"
        assert caught.value.request_id == "created-42"
        assert "response-secret" not in str(caught.value)
    assert result.json() == body
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_response_update_uses_patch_and_preserves_original(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    body = {"data": {"publisher_id": 42, "publisher_name": "Renamed"}, "status": "success"}
    route = respx.patch(f"{URL}/42").mock(return_value=httpx.Response(200, json=body))
    result = (
        await aclient.publishers.with_response.update(42, name="Renamed")
        if asynchronous
        else client.publishers.with_response.update(42, name="Renamed")
    )
    assert result.parse().publisher_name == "Renamed"
    assert result.json() == body
    assert route.calls.last.request.content == b'{"name":"Renamed"}'
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_response_page_windows_a_whole_collection_locally(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    """A body larger than the requested window is windowed, not refused.

    ``getNPAPublishers`` declares no ``limit`` (npa_publishers.yaml:1024-1032),
    so a collection longer than the caller's window is the operation's normal
    answer rather than a page that overran its request.
    """
    records = [{"publisher_id": n} for n in (1, 2, 3, 4)]
    body = {"data": {"publishers": records}, "total": 4}
    route = respx.get(URL).mock(return_value=httpx.Response(200, json=body))
    result = (
        await aclient.publishers.with_response.list_page(offset=1, limit=2)
        if asynchronous
        else client.publishers.with_response.list_page(offset=1, limit=2)
    )
    page = result.parse()
    assert [item.publisher_id for item in page.items] == [2, 3]
    assert (page.offset, page.limit, page.total, page.has_more) == (1, 2, 4, True)
    assert result.json() == body
    assert not route.calls.last.request.url.params
    assert route.call_count == 1


@pytest.mark.parametrize(
    ("method", "kwargs"),
    [
        ("get", {}),
        ("update", {"name": "renamed"}),
        ("list_apps", {}),
        ("create_registration_token", {}),
    ],
)
@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_publisher_id_is_validated_before_any_request(
    client: NetskopeClient,
    aclient: AsyncNetskopeClient,
    asynchronous: bool,
    method: str,
    kwargs: dict[str, object],
) -> None:
    """A traversal id must not reach the wire as an extra path segment."""
    catch_all = respx.route().mock(return_value=httpx.Response(200, json={}))
    resource = aclient.publishers.with_response if asynchronous else client.publishers.with_response
    traversal = "1/../../../api/v2/steering/apps/private"

    with pytest.raises(ValidationError, match="Invalid publisher_id format"):
        call = getattr(resource, method)(traversal, **kwargs)
        if asynchronous:
            await call
    assert catch_all.call_count == 0


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_publisher_id_rejects_a_negative_number(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    catch_all = respx.route().mock(return_value=httpx.Response(200, json={}))
    resource = aclient.publishers.with_response if asynchronous else client.publishers.with_response

    with pytest.raises(ValidationError, match="Invalid publisher_id format"):
        call = resource.get(-3)
        if asynchronous:
            await call
    assert catch_all.call_count == 0
