"""Typed CCI contracts without tenant requests or private transport mocks."""

from __future__ import annotations

import inspect

import pytest
import respx
from pydantic import ValidationError as ModelValidationError

from netskope.exceptions import (
    NetskopeError,
    PaginationError,
    ResponseValidationError,
    ValidationError,
)
from netskope.models.cci import CciAppQuery, CciTagCreate, CciTagPatch
from tests.unit.resources.conftest import sent_json

BASE = "https://t.goskope.com/api/v2/services/cci"


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_application_page_has_trusted_total_and_original_values(
    client, aclient, asynchronous
):
    body = {
        "data": [{"app_name": "Box", "id": "007", "cci": "087", "future": [None, True]}],
        "total_query_count": 4,
        "status": "Success",
    }
    route = respx.get(f"{BASE}/app").respond(200, json=body)
    response = (aclient if asynchronous else client).cci.with_response.list_page(
        CciAppQuery(apps=["Box"], limit=1, offset=0),
    )
    if inspect.isawaitable(response):
        response = await response
    page = response.parse()
    assert page.total == 4 and page.has_more is True
    assert page.items[0].id == 7 and page.items[0].cci == 87
    assert page.items[0].model_extra["future"] == [None, True]
    assert response.json() == body
    assert dict(route.calls[0].request.url.params) == {"apps": "Box", "limit": "1", "offset": "0"}
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_tag_names_and_memberships_are_different_typed_views(client, aclient, asynchronous):
    sdk = aclient if asynchronous else client
    respx.get(f"{BASE}/tags/all").respond(
        200, json={"data": {"tags": ["Finance", "Risk"], "tags_count": 2}}
    )
    memberships = respx.get(f"{BASE}/tags").respond(
        200,
        json={
            "data": {"Box": {"id": "007", "tags": ["Finance"], "future": {"x": 1}}},
        },
    )
    names = sdk.cci.tags.with_response.list_names_page()
    if inspect.isawaitable(names):
        names = await names
    assert [name.root for name in names.parse().items] == ["Finance", "Risk"]
    assert names.parse().total == 2
    result = sdk.cci.tags.with_response.list_by_apps(apps=["Box", "Dropbox"])
    if inspect.isawaitable(result):
        result = await result
    assert result.parse().root["Box"].id == 7
    assert result.parse().root["Box"].model_extra["future"] == {"x": 1}
    assert dict(memberships.calls[0].request.url.params) == {"apps": "Box;Dropbox"}


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_tag_detail_read_uses_supported_rules_query(client, aclient, asynchronous):
    route = respx.get(f"{BASE}/tags/rules").respond(
        200,
        json={
            "data": [
                {
                    "tag_name": "Finance [Approved]",
                    "applications_count": 4,
                    "rules": [{"attribute": "CCI", "condition": "gt", "value": ["50"]}],
                }
            ],
            "tags_count": 1,
        },
    )
    result = (aclient if asynchronous else client).cci.tags.with_response.list_rules_page(
        tag="Finance [Approved]"
    )
    if inspect.isawaitable(result):
        result = await result
    page = result.parse()
    assert page.items[0].rules[0].value == ["50"]
    # tags_count is this query's total, so a single returned rule exhausts it.
    assert page.total == 1
    assert page.has_more is False
    assert route.calls[0].request.url.params["tag"] == "Finance [Approved]"
    assert len(respx.calls) == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    "operation,method,path,payload",
    [
        ("create", "POST", "/tags", {"tag": "Finance", "apps": ["Box"]}),
        (
            "update",
            "PATCH",
            "/tags/Finance%20%5BApproved%5D",
            {"action": "remove", "apps": ["Box"]},
        ),
        ("delete", "DELETE", "/tags", None),
    ],
)
@respx.mock
async def test_named_tag_mutations_are_one_request(
    client, aclient, asynchronous, operation, method, path, payload
):
    route = respx.request(method, BASE + path).respond(
        202 if operation == "delete" else 200,
        json={"status": "Success", "message": "accepted"},
    )
    tags = (aclient if asynchronous else client).cci.tags.with_response
    if operation == "create":
        result = tags.create_request(CciTagCreate(name="Finance", apps=["Box"]))
    elif operation == "update":
        result = tags.update_request(
            "Finance [Approved]", CciTagPatch(action="remove", apps=["Box"])
        )
    else:
        result = tags.delete("Finance [Approved]")
    if inspect.isawaitable(result):
        result = await result
    assert result.parse().message == "accepted"
    assert len(respx.calls) == 1
    if payload is not None:
        assert sent_json(route) == payload
    else:
        assert route.calls[0].request.url.params["tags"] == "Finance [Approved]"


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_empty204_is_an_empty_typed_page(client, aclient, asynchronous):
    respx.get(f"{BASE}/app").respond(204)
    response = (aclient if asynchronous else client).cci.with_response.list_page(
        CciAppQuery(apps=["Box"])
    )
    if inspect.isawaitable(response):
        response = await response
    assert response.parse().items == []
    assert response.parse().total == 0


@pytest.mark.parametrize("body", [{"data": "bad"}, {"data": [{"app_name": "Box"}, "bad"]}])
@respx.mock
def test_malformed_page_is_not_silently_empty(client, body):
    respx.get(f"{BASE}/app").respond(200, json=body)
    response = client.cci.with_response.list_page(CciAppQuery(apps=["Box"]))
    with pytest.raises(ResponseValidationError):
        response.parse()


@pytest.mark.parametrize("total", [True, -1, "many", None])
@respx.mock
def test_unusable_total_states_no_total(client, total):
    respx.get(f"{BASE}/app").respond(
        200, json={"data": [{"app_name": "Box"}], "total_query_count": total}
    )
    page = client.cci.with_response.list_page(CciAppQuery(apps=["Box"])).parse()
    assert [app.app_name for app in page.items] == ["Box"]
    assert page.total is None
    assert page.has_more is None


@respx.mock
def test_total_smaller_than_its_records_is_rejected(client):
    body = {"data": [{"app_name": "Box"}, {"app_name": "Dropbox"}], "total_query_count": 1}
    respx.get(f"{BASE}/app").respond(200, json=body)
    response = client.cci.with_response.list_page(CciAppQuery(apps=["Box"]))
    with pytest.raises(PaginationError):
        response.parse()
    assert response.json() == body


@pytest.mark.parametrize(
    "model,values",
    [
        (CciAppQuery, {}),
        (CciAppQuery, {"apps": ["Box"], "ccl": "high"}),
        (CciAppQuery, {"connector": "api"}),
        (CciAppQuery, {"discovered": False}),
        (CciAppQuery, {"discovered": 1}),
        (CciAppQuery, {"apps": ["Box"], "limit": True}),
        (CciAppQuery, {"apps": ["Box;Dropbox"]}),
        (CciTagCreate, {"tag": "Finance"}),
        (CciTagCreate, {"tag_name": "Finance", "apps": ["Box"]}),
        (CciTagCreate, {"tag": "Finance", "apps": ["Box"], "ids": ["1"]}),
        (CciTagCreate, {"tag": "Bad,Name", "apps": ["Box"]}),
        (CciTagPatch, {"apps": ["Box"]}),
        (CciTagPatch, {"action": "replace", "apps": ["Box"]}),
    ],
)
def test_invalid_requests_fail_at_model_boundary(model, values):
    with pytest.raises(ModelValidationError):
        model.model_validate(values)


@respx.mock
def test_mutated_request_is_revalidated_before_http(client):
    request = CciTagPatch(action="append", apps=["Box"])
    request.apps.clear()
    with pytest.raises(ValidationError):
        client.cci.tags.with_response.update_request("Finance", request)
    assert len(respx.calls) == 0


@respx.mock
def test_comma_in_single_delete_name_cannot_target_multiple_tags(client):
    with pytest.raises(ValidationError):
        client.cci.tags.with_response.delete("Finance,Risk")
    assert len(respx.calls) == 0


@respx.mock
def test_failed_tag_mutation_is_not_replayed(client):
    route = respx.post(f"{BASE}/tags").respond(503, json={"message": "declined"})
    with pytest.raises(NetskopeError):
        client.cci.tags.with_response.create_request(CciTagCreate(name="Finance", apps=["Box"]))
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_a_page_larger_than_requested_is_rejected(client, aclient, asynchronous):
    body = {"data": [{"app_name": "Box"}, {"app_name": "Dropbox"}], "total_query_count": 9}
    respx.get(f"{BASE}/app").respond(200, json=body)
    response = (aclient if asynchronous else client).cci.with_response.list_page(
        CciAppQuery(apps=["Box"], limit=1)
    )
    if inspect.isawaitable(response):
        response = await response
    with pytest.raises(PaginationError):
        response.parse()
    assert response.json() == body


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_a_page_served_from_another_offset_is_rejected(client, aclient, asynchronous):
    body = {"data": [{"app_name": "Box"}], "total_query_count": 9, "offset": 0}
    respx.get(f"{BASE}/app").respond(200, json=body)
    response = (aclient if asynchronous else client).cci.with_response.list_page(
        CciAppQuery(apps=["Box"], limit=1, offset=5)
    )
    if inspect.isawaitable(response):
        response = await response
    with pytest.raises(PaginationError) as caught:
        response.parse()
    assert caught.value.offset == 5
    assert caught.value.request_path == "/api/v2/services/cci/app"


@respx.mock
def test_a_page_that_echoes_the_requested_offset_is_kept(client):
    body = {"data": [{"app_name": "Box"}], "total_query_count": 9, "offset": 5}
    respx.get(f"{BASE}/app").respond(200, json=body)
    page = client.cci.with_response.list_page(CciAppQuery(apps=["Box"], limit=1, offset=5)).parse()
    assert [app.app_name for app in page.items] == ["Box"]
    assert (page.offset, page.total) == (5, 9)


@pytest.mark.parametrize("echoed", ["5", True, 1.5, "unusable"])
@respx.mock
def test_an_offset_the_page_cannot_be_compared_against_is_rejected(client, echoed):
    """An echoed offset is read the same way here as in every other typed page."""
    respx.get(f"{BASE}/app").respond(
        200, json={"data": [{"app_name": "Box"}], "total_query_count": 9, "offset": echoed}
    )
    response = client.cci.with_response.list_page(CciAppQuery(apps=["Box"], limit=1, offset=5))
    with pytest.raises(PaginationError):
        response.parse()


@pytest.mark.parametrize("count", [True, "many", 1.5, None])
@respx.mock
def test_an_unusable_tag_count_does_not_contradict_the_catalog(client, count):
    respx.get(f"{BASE}/tags/all").respond(
        200, json={"data": {"tags": ["Finance", "Risk"], "tags_count": count}}
    )
    page = client.cci.tags.with_response.list_names_page().parse()
    assert [name.root for name in page.items] == ["Finance", "Risk"]
    assert page.total == 2


@pytest.mark.parametrize("count", [3, "3"])
@respx.mock
def test_a_usable_tag_count_that_disagrees_is_rejected(client, count):
    body = {"data": {"tags": ["Finance", "Risk"], "tags_count": count}}
    respx.get(f"{BASE}/tags/all").respond(200, json=body)
    response = client.cci.tags.with_response.list_names_page()
    with pytest.raises(PaginationError):
        response.parse()
    assert response.json() == body
