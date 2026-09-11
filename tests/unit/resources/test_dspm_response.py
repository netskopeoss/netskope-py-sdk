"""Verified DSPM inventory routes and single-datastore scan acknowledgements."""

from __future__ import annotations

import json

import pytest
import respx

from netskope.exceptions import (
    APIError,
    PaginationError,
    ResponseValidationError,
    ValidationError,
)
from netskope.models.dspm import DspmClassificationFile, DspmDatastore, DspmRecord

BASE = "https://t.goskope.com/api/v2/dspm"
ROUTES = {
    "connected_datastores": "/datastores/connected",
    "discovered_datastores": "/datastores/discovered",
    "archived_datastores": "/datastores/archived",
    "databases": "/datastores/connected/databases",
    "schemas": "/datastores/connected/schemas",
    "tables": "/datastores/connected/tables",
    "classification_columns": "/classificationmanagement/columns",
    "classification_files": "/classificationmanagement/files",
    "data_tags": "/classificationmanagement/datatags",
    "data_tag_categories": "/classificationmanagement/datatagcategories",
    "sensitive_data_types": "/classificationmanagement/sensitivedatatypes",
    "sensitive_data_type_categories": "/classificationmanagement/sensitivedatatypecategories",
    "sensitivity_levels": "/classificationmanagement/sensitivedatatypes/sensitivitylevels",
    "sidecar_pools": "/administration/sidecarpools",
    "infrastructure_connections": "/administration/infrastructureconnections",
    "infrastructure_platforms": "/administration/infrastructureconnections/platforms",
}


@pytest.mark.parametrize("resource,path", ROUTES.items())
@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_verified_inventory_routes_are_single_typed_requests(
    client, aclient, asynchronous, resource, path
):
    body = {
        "success": True,
        "data": {"total": "8", "results": [{"id": "001", "name": "Production"}], "future": "x"},
        "request_id": "server-id",
    }
    route = respx.get(BASE + path).respond(200, json=body)
    response = (aclient if asynchronous else client).dspm.with_response.list_page(resource)
    if asynchronous:
        response = await response
    page = response.parse()
    assert isinstance(page.items[0], DspmRecord)
    assert page.items[0].id == "001"
    assert (page.total, page.offset, page.limit, page.has_more) == (8, 0, None, True)
    assert page.metadata == {
        "success": True,
        "request_id": "server-id",
        "data": {"total": "8", "future": "x"},
    }
    assert response.json() == body
    assert dict(route.calls.last.request.url.params) == {}
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_params_and_endpoint_models_share_sync_async_decode(client, aclient, asynchronous):
    route = respx.get(BASE + "/datastores/connected").respond(
        200,
        json={
            "success": True,
            "data": {"total": 3, "results": [{"id": "1", "table_count": "007", "unknown": True}]},
        },
    )
    sdk = aclient if asynchronous else client
    response = sdk.dspm.with_response.list_page(
        "connected_datastores",
        filter_expr="name eq 'prod'",
        sort_by="name",
        sort_order="desc",
        limit=1,
        offset=2,
    )
    if asynchronous:
        response = await response
    page = response.parse()
    assert isinstance(page.items[0], DspmDatastore)
    assert page.items[0].table_count == 7
    assert page.items[0].model_extra == {"unknown": True}
    assert response.json()["data"]["results"][0]["table_count"] == "007"
    assert page.has_more is False
    assert dict(route.calls.last.request.url.params) == {
        "filter": "name eq 'prod'",
        "sortby": "name",
        "sortorder": "desc",
        "limit": "1",
        "offset": "2",
    }


@respx.mock
def test_nested_classification_models_keep_canonical_aliases(client):
    respx.get(BASE + "/classificationmanagement/files").respond(
        200,
        json={
            "data": {
                "results": [
                    {
                        "id": "f",
                        "fileName": "file.csv",
                        "sensitiveDataTypes": [{"occurenceCount": "007", "dataType": {"id": 1}}],
                    }
                ]
            }
        },
    )
    page = client.dspm.list_page("classification_files")
    item = page.items[0]
    assert isinstance(item, DspmClassificationFile)
    assert item.file_name == "file.csv" and item.sensitive_data_types[0].occurrence_count == 7
    assert page.total is None and page.has_more is None


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    "resource,options",
    [
        ("columns", {}),
        ("scans", {}),
        ("policy_violations", {}),
        ("assessment_summary", {}),
        ("supported_data_types", {}),
        ("not-real", {}),
        ("tables", {"limit": -1}),
        ("tables", {"offset": True}),
        ("tables", {"limit": "2"}),
        ("tables", {"filter_expr": []}),
        ("tables", {"sort_order": "desc"}),
        ("tables", {"sort_by": "name", "sort_order": "up"}),
    ],
)
@respx.mock
async def test_unsupported_or_invalid_reads_fail_before_http(
    client, aclient, asynchronous, resource, options
):
    sdk = aclient if asynchronous else client
    with pytest.raises(ValidationError):
        result = sdk.dspm.with_response.list_page(resource, **options)
        if asynchronous:
            await result
    assert not respx.calls


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"data": []},
        {"data": {}},
        {"data": {"results": "bad"}},
        {"data": {"results": [None]}},
        {"data": {"results": [{"table_count": "wrong"}]}},
    ],
)
@respx.mock
def test_malformed_pages_fail_with_request_context_and_retained_json(client, body):
    route = respx.get(BASE + "/datastores/connected").respond(
        200, json=body, headers={"x-request-id": "dspm-read"}
    )
    response = client.dspm.with_response.list_page("connected_datastores", limit=1)
    with pytest.raises(ResponseValidationError) as caught:
        response.parse()
    assert caught.value.request_path == "/api/v2/dspm/datastores/connected"
    assert caught.value.request_id == "dspm-read"
    assert response.json() == body and route.call_count == 1


@pytest.mark.parametrize(
    "body",
    [
        {"data": {"results": [{"id": "a"}], "total": 0}},
        {"data": {"results": [{"id": "a"}, {"id": "b"}]}},
    ],
)
@respx.mock
def test_unsafe_pages_fail_with_request_context_and_retained_json(client, body):
    route = respx.get(BASE + "/datastores/connected").respond(
        200, json=body, headers={"x-request-id": "dspm-read"}
    )
    response = client.dspm.with_response.list_page("connected_datastores", limit=1)
    with pytest.raises(PaginationError) as caught:
        response.parse()
    assert caught.value.request_path == "/api/v2/dspm/datastores/connected"
    assert caught.value.request_id == "dspm-read"
    assert caught.value.offset == 0
    assert response.json() == body and route.call_count == 1


@respx.mock
def test_empty_page_beyond_total_is_not_a_contradiction(client):
    respx.get(BASE + "/datastores/connected").respond(
        200, json={"data": {"results": [], "total": 1}}
    )
    page = client.dspm.list_page("connected_datastores", offset=5, limit=0)
    assert page.items == [] and page.has_more is False


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_single_scan_has_exact_payload_and_no_followup(client, aclient, asynchronous):
    route = respx.post(BASE + "/datastores/connected/startscan").respond(202)
    sdk = aclient if asynchronous else client
    response = sdk.dspm.with_response.start_scan("ds-01")
    if asynchronous:
        response = await response
    assert response.parse() is None and response.content == b""
    assert json.loads(route.calls.last.request.content) == {"id": "ds-01"}
    assert route.call_count == 1 and len(respx.calls) == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("identifier", [None, 1, True, "", " ", ["a", "b"]])
@respx.mock
async def test_invalid_scan_ids_fail_before_http(client, aclient, asynchronous, identifier):
    with pytest.raises(ValidationError):
        response = (aclient if asynchronous else client).dspm.with_response.start_scan(identifier)
        if asynchronous:
            await response
    assert not respx.calls


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_scan_transient_failure_is_not_replayed(client, aclient, asynchronous):
    route = respx.post(BASE + "/datastores/connected/startscan").respond(
        503, json={"message": "unavailable"}
    )
    with pytest.raises(APIError):
        response = (aclient if asynchronous else client).dspm.with_response.start_scan("ds-01")
        if asynchronous:
            await response
    assert route.call_count == 1


@respx.mock
def test_unexpected_scan_success_is_unusable_not_replayed(client):
    body = {"success": True, "future": "ack"}
    route = respx.post(BASE + "/datastores/connected/startscan").respond(200, json=body)
    response = client.dspm.with_response.start_scan("ds-01")
    with pytest.raises(ResponseValidationError) as caught:
        response.parse()
    assert caught.value.request_method == "POST"
    assert response.json() == body and route.call_count == 1


def test_supported_names_do_not_promote_unverified_legacy_routes(client):
    assert {str(value) for value in client.dspm.supported_resource_types()} == set(ROUTES)


@pytest.mark.parametrize("total", [True, 1.5, "1.5", -1, "many", None])
@respx.mock
def test_an_unusable_total_states_no_total_instead_of_failing(client, total):
    """Every decoder reads a total the same way: unusable means the API stated none."""
    respx.get(BASE + "/datastores/connected").respond(
        200, json={"data": {"results": [{"id": "a"}], "total": total}}
    )
    page = client.dspm.with_response.list_page("connected_datastores", limit=1).parse()
    assert [record.id for record in page.items] == ["a"]
    assert page.total is None and page.has_more is None
