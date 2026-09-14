"""URL-list reads must survive every envelope before update rewrites the list."""

from __future__ import annotations

import inspect

import pytest
import respx

from netskope.exceptions import ResponseValidationError, ValidationError
from netskope.models.url_lists import UrlList
from netskope.response import ApiResponse
from tests.unit.resources.conftest import sent_json

BASE = "https://t.goskope.com/api/v2/policy"
URL = f"{BASE}/urllist"

RECORD = {"id": 42, "name": "Block", "data": {"urls": ["bad.com"], "type": "regex"}}
FLAT_RECORD = {"id": 42, "name": "Block", "urls": ["bad.com"], "type": "regex"}
EMPTY_LIST = {"id": 42, "name": "Block", "data": {"urls": [], "type": "regex"}}

# Every envelope a URL-list read is known to arrive in.
ENVELOPES = [
    pytest.param(RECORD, id="record"),
    pytest.param([RECORD], id="single-item-list"),
    pytest.param({"data": FLAT_RECORD}, id="data-object"),
    pytest.param({"data": [FLAT_RECORD]}, id="data-list"),
    pytest.param({"data": {"urllists": [FLAT_RECORD]}}, id="data-urllists"),
    pytest.param({"data": {"urllists": [RECORD]}}, id="data-urllists-nested"),
    pytest.param({"urllists": [FLAT_RECORD]}, id="top-level-urllists"),
]

# Envelopes a merge cannot be built from without erasing the list.
UNUSABLE = [
    pytest.param({"data": {"urllists": []}}, id="no-records"),
    pytest.param({"data": {"urllists": [FLAT_RECORD, FLAT_RECORD]}}, id="two-records"),
    pytest.param({"id": 42, "name": "Block"}, id="missing-urls-and-type"),
    pytest.param({"id": 42, "name": "Block", "data": {}}, id="empty-record-data"),
    pytest.param({"data": "unrecognized"}, id="unrecognized"),
]

# Bodies that carry no single record, so no URL list can be decoded from them.
NO_RECORD = [
    pytest.param({"data": {}}, id="empty-data"),
    pytest.param({"data": {"urllists": []}}, id="no-records"),
    pytest.param([RECORD, RECORD], id="two-record-list"),
    pytest.param({"data": [FLAT_RECORD, FLAT_RECORD]}, id="two-record-data"),
    pytest.param({"urllists": [FLAT_RECORD, FLAT_RECORD]}, id="two-record-urllists"),
    pytest.param({"data": {"status": "ok"}}, id="acknowledgement"),
    pytest.param([{"status": "ok"}], id="acknowledgement-list"),
]

# Values rejected before a request is built, by the legacy and typed writes alike.
BAD_CREATE_ARGS = [
    pytest.param(("Block", ["bad.com"], "fuzzy"), id="unknown-list-type"),
    pytest.param(("Block", "bad.com", "exact"), id="urls-not-a-list"),
    pytest.param(("Block", [b"bad.com"], "exact"), id="url-not-a-string"),
    pytest.param((42, ["bad.com"], "exact"), id="name-not-a-string"),
]

BAD_UPDATE_KWARGS = [
    pytest.param({}, id="nothing-to-change"),
    pytest.param({"list_type": "fuzzy"}, id="unknown-list-type"),
    pytest.param({"urls": "bad.com"}, id="urls-not-a-list"),
    pytest.param({"urls": [b"bad.com"]}, id="url-not-a-string"),
    pytest.param({"name": 42}, id="name-not-a-string"),
]

TRAVERSAL_IDS = ["../deploy", "42/../../deploy"]


def url_lists(sdk, typed):
    return sdk.url_lists.with_response if typed else sdk.url_lists


def invoke(sdk, typed, **kwargs):
    return url_lists(sdk, typed).update(42, **kwargs)


async def resolve(result):
    return await result if inspect.isawaitable(result) else result


async def decode(result):
    result = await resolve(result)
    return result.parse() if isinstance(result, ApiResponse) else result


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("body", ENVELOPES)
@respx.mock
async def test_update_preserves_urls_from_every_read_envelope(
    client, aclient, asynchronous, typed, body
):
    respx.get(f"{URL}/42").respond(200, json=body)
    route = respx.put(f"{URL}/42").respond(200, json=RECORD)
    result = await resolve(invoke(aclient if asynchronous else client, typed, name="Renamed"))
    parsed = result.parse() if typed else result

    assert sent_json(route) == {
        "name": "Renamed",
        "data": {"urls": ["bad.com"], "type": "regex"},
    }
    assert isinstance(parsed, UrlList)
    assert parsed.urls == ["bad.com"]
    assert len(respx.calls) == 2


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("body", UNUSABLE)
@respx.mock
async def test_unusable_read_never_reaches_the_put(client, aclient, asynchronous, typed, body):
    read = respx.get(f"{URL}/42").respond(200, json=body)
    write = respx.put(f"{URL}/42").respond(200, json=RECORD)
    with pytest.raises(ResponseValidationError):
        await resolve(invoke(aclient if asynchronous else client, typed, name="Renamed"))
    assert read.call_count == 1
    assert write.call_count == 0


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_a_different_list_never_reaches_the_put(client, aclient, asynchronous, typed):
    read = respx.get(f"{URL}/42").respond(200, json={**FLAT_RECORD, "id": 7})
    write = respx.put(f"{URL}/42").respond(200, json=RECORD)
    with pytest.raises(ResponseValidationError, match="different list"):
        await resolve(invoke(aclient if asynchronous else client, typed, name="Renamed"))
    assert read.call_count == 1
    assert write.call_count == 0


@respx.mock
async def test_async_typed_reads_and_writes_use_one_request_each(aclient):
    listing = respx.get(URL).respond(
        200,
        json={
            "data": {"urllists": [{**FLAT_RECORD, "id": n} for n in (42, 43, 44)]},
            "status": {"total": 3},
        },
    )
    page = (await aclient.url_lists.with_response.list_page(limit=1, offset=0)).parse()
    assert [item.urls for item in page.items] == [["bad.com"]]
    assert page.total == 3 and page.has_more is True
    # ``GET /urllist`` declares only ``pending`` and ``field``
    # (policy/urllist.yaml:132-156), so the window is applied locally.
    assert not listing.calls[0].request.url.params

    respx.get(f"{URL}/42").respond(200, json=RECORD)
    assert (await aclient.url_lists.with_response.get(42)).parse().type == "regex"

    created = respx.post(URL).respond(201, json=[RECORD])
    response = await aclient.url_lists.with_response.create("Block", ["bad.com"], list_type="regex")
    assert response.parse().id == 42
    assert sent_json(created) == {"name": "Block", "data": {"urls": ["bad.com"], "type": "regex"}}

    # The one deploy operation the spec declares is POST /urllist/deploy
    # (policy/urllist.yaml:201-227), and it answers with the lists it applied
    # (:209-217).
    deployed = respx.post(f"{URL}/deploy").respond(200, json=[RECORD])
    parsed = (await aclient.url_lists.with_response.deploy()).parse()
    assert deployed.call_count == 1
    assert [item.id for item in parsed.urllists] == [42]
    assert parsed.status is None

    respx.delete(f"{URL}/42").respond(204)
    assert (await aclient.url_lists.with_response.delete(42)).parse() is None


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_an_empty_url_list_round_trips_as_an_empty_list(client, aclient, asynchronous, typed):
    """A list that legitimately holds no URLs is a record, not a failed read."""
    respx.get(f"{URL}/42").respond(200, json=EMPTY_LIST)
    result = await decode(url_lists(aclient if asynchronous else client, typed).get(42))
    assert result.urls == []
    assert (result.id, result.name, result.type) == (42, "Block", "regex")


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_a_record_whose_data_is_empty_keeps_its_identity(
    client, aclient, asynchronous, typed
):
    """``data: {}`` leaves a record without urls or type, not an all-None list."""
    respx.get(f"{URL}/42").respond(200, json={"id": 42, "name": "Block", "data": {}})
    result = await decode(url_lists(aclient if asynchronous else client, typed).get(42))
    assert (result.id, result.name) == (42, "Block")
    assert result.type is None and result.urls == []


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("body", NO_RECORD)
@respx.mock
async def test_a_read_without_one_record_is_an_error_not_an_empty_list(
    client, aclient, asynchronous, typed, body
):
    respx.get(f"{URL}/42").respond(200, json=body)
    with pytest.raises(ResponseValidationError) as caught:
        await decode(url_lists(aclient if asynchronous else client, typed).get(42))
    assert caught.value.request_method == "GET"
    assert caught.value.request_path == "/api/v2/policy/urllist/42"


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("body", NO_RECORD)
@respx.mock
async def test_a_create_without_one_record_is_an_error_not_an_empty_list(
    client, aclient, asynchronous, typed, body
):
    respx.post(URL).respond(201, json=body)
    with pytest.raises(ResponseValidationError) as caught:
        await decode(
            url_lists(aclient if asynchronous else client, typed).create("Block", ["a.com"])
        )
    assert caught.value.request_method == "POST"
    assert caught.value.request_path == "/api/v2/policy/urllist"


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_a_top_level_urllists_envelope_decodes_like_a_nested_one(
    client, aclient, asynchronous, typed
):
    respx.post(URL).respond(201, json={"urllists": [FLAT_RECORD]})
    result = await decode(
        url_lists(aclient if asynchronous else client, typed).create("Block", ["bad.com"])
    )
    assert result.id == 42 and result.urls == ["bad.com"]


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("operation", ["get", "update", "delete"])
@pytest.mark.parametrize("list_id", TRAVERSAL_IDS)
@respx.mock
async def test_an_unsafe_identifier_never_reaches_the_path(
    client, aclient, asynchronous, typed, operation, list_id
):
    resource = url_lists(aclient if asynchronous else client, typed)
    kwargs = {"name": "Renamed"} if operation == "update" else {}
    with pytest.raises(ValidationError):
        await resolve(getattr(resource, operation)(list_id, **kwargs))
    assert not respx.calls


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("args", BAD_CREATE_ARGS)
@respx.mock
async def test_create_rejects_unusable_fields_before_http(
    client, aclient, asynchronous, typed, args
):
    name, urls, list_type = args
    resource = url_lists(aclient if asynchronous else client, typed)
    with pytest.raises(ValidationError):
        await resolve(resource.create(name, urls, list_type=list_type))
    assert not respx.calls


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("kwargs", BAD_UPDATE_KWARGS)
@respx.mock
async def test_update_rejects_unusable_fields_before_http(
    client, aclient, asynchronous, typed, kwargs
):
    with pytest.raises(ValidationError):
        await resolve(invoke(aclient if asynchronous else client, typed, **kwargs))
    assert not respx.calls


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_an_empty_url_list_still_seeds_the_update(client, aclient, asynchronous, typed):
    """An emptied list is a usable merge source, unlike a read that lost its urls."""
    respx.get(f"{URL}/42").respond(200, json=EMPTY_LIST)
    route = respx.put(f"{URL}/42").respond(200, json=EMPTY_LIST)
    result = await decode(invoke(aclient if asynchronous else client, typed, name="Renamed"))
    assert sent_json(route) == {"name": "Renamed", "data": {"urls": [], "type": "regex"}}
    assert result.urls == []
