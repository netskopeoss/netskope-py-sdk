"""Bounded RBAC reads preserve endpoint shapes and do not infer completeness."""

from __future__ import annotations

from typing import Any

import pytest
import respx
from pydantic import ValidationError as ModelValidationError

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope._pagination import AsyncScimPaginatedResponse, SyncScimPaginatedResponse
from netskope.exceptions import (
    NetskopeError,
    PaginationError,
    ResponseValidationError,
    ValidationError,
)
from netskope.models.rbac import (
    RbacRole,
    RbacRoleApiGroup,
    RbacRoleDetail,
    RbacRoleIpAllowList,
    RbacRoleScope,
    RbacRoleSummary,
)
from netskope.models.scim import ScimUser
from netskope.pagination import Page
from netskope.response import ApiResponse

ROLES_URL = "https://t.goskope.com/api/v2/rbac/roles"
ADMINS_URL = "https://t.goskope.com/api/v2/platform/administration/scim/Users"
EXTENSION = "urn:ietf:params:scim:schemas:netskope:2.0:user"
SUMMARY = {
    "roleId": "42",
    "name": "SOC-Analyst",
    "description": None,
    "type": 0,
    "scoped": False,
    "lastEdited": "2025-01-15T10:00:00Z",
    "userCount": 3,
    "future": {"regions": ["west"], "note": None},
}
DETAIL = {
    "version": "v3",
    "roleId": "42",
    "roleName": "SOC-Analyst",
    "roleDescription": None,
    "scopes": [{"scopeFieldId": 1, "scopeValue": "west", "future": ["extra"]}],
    "ipAllowList": {"enableIpAllowList": True, "ipList": ["192.0.2.1"], "future": None},
    "apiGroups": [{"apiGroupId": 1, "permission": "r", "future": {"audit": True}}],
}
ADMIN = {
    "id": "admin-1",
    "userName": "analyst@example.com",
    "active": True,
    EXTENSION: {"recordType": "SERVICE_ACCOUNT", "regions": ["west"], "future": None},
}


def test_summary_and_detail_have_distinct_aliases_and_typed_nested_fields() -> None:
    summary = RbacRoleSummary.model_validate(SUMMARY)
    detail = RbacRoleDetail.model_validate(DETAIL)
    assert summary.id == detail.id == 42
    assert summary.name == detail.name == "SOC-Analyst"
    assert summary.description is detail.description is None
    summary_json = summary.model_dump(mode="json", by_alias=True, exclude_unset=True)
    detail_json = detail.model_dump(mode="json", by_alias=True, exclude_unset=True)
    assert summary_json["name"] == detail_json["roleName"]
    assert "roleName" not in summary_json
    assert "name" not in detail_json
    assert summary_json["description"] is detail_json["roleDescription"] is None
    assert summary_json["future"] == SUMMARY["future"]
    assert isinstance(detail.scopes[0], RbacRoleScope)
    assert isinstance(detail.api_groups[0], RbacRoleApiGroup)
    assert isinstance(detail.ip_allow_list, RbacRoleIpAllowList)
    assert detail.ip_allow_list.enabled is True
    assert detail.ip_allow_list.ip_list == ["192.0.2.1"]
    assert detail_json["apiGroups"] == DETAIL["apiGroups"]
    assert detail_json["ipAllowList"] == DETAIL["ipAllowList"]
    assert "apiGroups" not in RbacRoleDetail(roleId=1).model_dump(by_alias=True, exclude_unset=True)
    with pytest.raises(ModelValidationError, match="frozen"):
        summary.name = "Changed"


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_roles_response_page_is_bounded_and_count_is_only_metadata(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    body = {"version": "v3", "count": 999, "roles": [SUMMARY]}
    route = respx.get(ROLES_URL).respond(200, json=body)
    params = {"role_type": "custom", "scope": "limited", "search": "SOC", "limit": 2, "offset": 40}
    response = (
        await aclient.rbac.roles.with_response.list_page(**params)
        if asynchronous
        else client.rbac.roles.with_response.list_page(**params)
    )
    assert isinstance(response, ApiResponse)
    page = response.parse()
    assert isinstance(page, Page)
    assert type(page.items[0]) is RbacRoleSummary
    assert page.items[0].id == 42
    assert page.offset == 40
    assert page.limit == 2
    assert page.total is page.has_more is None
    assert page.metadata == {"version": "v3", "count": 999}
    assert response.parse() is page
    assert response.json() == body
    assert dict(route.calls.last.request.url.params) == {
        "type": "custom",
        "scope": "limited",
        "search": "SOC",
        "limit": "2",
        "offset": "40",
    }
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_role_response_detail_keeps_original_envelope_and_values(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    body = {"data": DETAIL, "status": "success"}
    route = respx.get(f"{ROLES_URL}/42").respond(200, json=body)
    response = (
        await aclient.rbac.roles.with_response.get_detail(42)
        if asynchronous
        else client.rbac.roles.with_response.get_detail(42)
    )
    detail = response.parse()
    assert type(detail) is RbacRoleDetail
    assert detail.id == 42
    assert detail.api_groups[0].permission == "r"
    assert response.json() == body
    assert response.parse() is detail
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_normal_role_reads_keep_legacy_types_and_add_endpoint_specific_types(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    list_route = respx.get(ROLES_URL).respond(
        200, json={"version": "v3", "count": 1, "roles": [SUMMARY]}
    )
    get_route = respx.get(f"{ROLES_URL}/42").respond(200, json=DETAIL)
    if asynchronous:
        roles = await aclient.rbac.roles.list()
        role = await aclient.rbac.roles.get(42)
        page = await aclient.rbac.roles.list_page()
        detail = await aclient.rbac.roles.get_detail(42)
    else:
        roles = client.rbac.roles.list()
        role = client.rbac.roles.get(42)
        page = client.rbac.roles.list_page()
        detail = client.rbac.roles.get_detail(42)
    assert type(roles) is list
    assert type(roles[0]) is type(role) is RbacRole
    assert type(page.items[0]) is RbacRoleSummary
    assert type(detail) is RbacRoleDetail
    assert isinstance(role.ip_allow_list, dict)
    assert isinstance(detail.ip_allow_list, RbacRoleIpAllowList)
    assert page.offset == 0
    assert page.limit is None
    assert list_route.call_count == get_route.call_count == 2
    assert all(not call.request.url.params for call in list_route.calls)


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_admin_response_page_matches_requested_index_and_preserves_extensions(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    body = {"totalResults": 99, "startIndex": 41, "itemsPerPage": 1, "Resources": [ADMIN]}
    route = respx.get(ADMINS_URL).respond(200, json=body)
    filter_expr = f'{EXTENSION}[recordType eq "SERVICE_ACCOUNT"]'
    response = (
        await aclient.rbac.admins.with_response.list_page(
            count=2, start_index=41, filter_expr=filter_expr
        )
        if asynchronous
        else client.rbac.admins.with_response.list_page(
            count=2, start_index=41, filter_expr=filter_expr
        )
    )
    page = response.parse()
    assert type(page.items[0]) is ScimUser
    assert page.items[0].user_name == "analyst@example.com"
    assert page.items[0].model_dump(by_alias=True, exclude_unset=True) == ADMIN
    assert page.offset == 40
    assert page.limit == 2
    assert page.total == 99
    assert page.has_more is True
    assert page.metadata == {"totalResults": 99, "startIndex": 41, "itemsPerPage": 1}
    assert response.json() == body
    assert response.parse() is page
    assert dict(route.calls.last.request.url.params) == {
        "count": "2",
        "startIndex": "41",
        "filter": filter_expr,
    }
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("total", [None, 0])
@respx.mock
async def test_admin_empty_pages_preserve_unknown_and_zero_totals(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool, total: int | None
) -> None:
    body: dict[str, Any] = {"Resources": []}
    if total is not None:
        body["totalResults"] = total
    route = respx.get(ADMINS_URL).respond(200, json=body)
    page = (
        await aclient.rbac.admins.list_page(start_index=41, count=0)
        if asynchronous
        else client.rbac.admins.list_page(start_index=41, count=0)
    )
    assert page.items == []
    assert page.total == total
    assert page.has_more is (None if total is None else False)
    assert page.offset == 40
    assert page.limit == 0
    assert dict(route.calls.last.request.url.params) == {"count": "0", "startIndex": "41"}
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_admin_page_defaults_are_bounded_and_legacy_list_remains_lazy(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    route = respx.get(ADMINS_URL).respond(200, json={"Resources": [ADMIN], "totalResults": 999})
    if asynchronous:
        assert isinstance(aclient.rbac.admins.list(), AsyncScimPaginatedResponse)
        page = await aclient.rbac.admins.list_page()
    else:
        assert isinstance(client.rbac.admins.list(), SyncScimPaginatedResponse)
        page = client.rbac.admins.list_page()
    assert page.total == 999
    assert page.has_more is True
    assert dict(route.calls.last.request.url.params) == {"count": "100", "startIndex": "1"}
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    "operation,body,expected",
    [
        ("roles", {"count": 5}, ResponseValidationError),
        ("roles", {"roles": [SUMMARY, None]}, ResponseValidationError),
        ("roles", {"roles": [{"roleId": {"secret": "response-secret"}}]}, ResponseValidationError),
        ("detail", [], ResponseValidationError),
        ("detail", {"data": []}, ResponseValidationError),
        ("detail", {"data": {}}, ResponseValidationError),
        ("detail", {"roleId": {"secret": "response-secret"}}, ResponseValidationError),
        ("admins", {"Resources": [None]}, ResponseValidationError),
        ("admins", {"Resources": [], "startIndex": 0}, PaginationError),
        ("admins", {"Resources": [], "startIndex": 2}, PaginationError),
    ],
)
@respx.mock
async def test_malformed_response_is_safe_and_remains_inspectable(
    client: NetskopeClient,
    aclient: AsyncNetskopeClient,
    asynchronous: bool,
    operation: str,
    body: Any,
    expected: type[NetskopeError],
) -> None:
    url = (
        ADMINS_URL
        if operation == "admins"
        else f"{ROLES_URL}/42"
        if operation == "detail"
        else ROLES_URL
    )
    route = respx.get(url).respond(200, json=body, headers={"x-request-id": "rbac-response"})
    if operation == "roles":
        response = (
            await aclient.rbac.roles.with_response.list_page()
            if asynchronous
            else client.rbac.roles.with_response.list_page()
        )
    elif operation == "detail":
        response = (
            await aclient.rbac.roles.with_response.get_detail(42)
            if asynchronous
            else client.rbac.roles.with_response.get_detail(42)
        )
    else:
        response = (
            await aclient.rbac.admins.with_response.list_page()
            if asynchronous
            else client.rbac.admins.with_response.list_page()
        )
    with pytest.raises(expected) as caught:
        response.parse()
    assert caught.value.request_method == "GET"
    assert caught.value.request_path == route.calls.last.request.url.path
    assert caught.value.request_id == "rbac-response"
    assert "response-secret" not in str(caught.value)
    assert response.json() == body
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("params", [{"count": -1}, {"count": True}, {"start_index": 0}])
@respx.mock
async def test_invalid_admin_page_params_fail_before_http(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool, params: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        if asynchronous:
            await aclient.rbac.admins.list_page(**params)
        else:
            client.rbac.admins.list_page(**params)
    assert len(respx.calls) == 0


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("params", [{"role_type": "builtin"}, {"scope": "global"}])
@respx.mock
async def test_invalid_role_page_filters_fail_before_http(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool, params: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        if asynchronous:
            await aclient.rbac.roles.list_page(**params)
        else:
            client.rbac.roles.list_page(**params)
    assert len(respx.calls) == 0


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 1001},
        {"limit": True},
        {"limit": 1.5},
        {"limit": "2"},
        {"offset": -1},
        {"offset": False},
        {"offset": 1.5},
        {"offset": "2"},
    ],
)
@respx.mock
async def test_bounded_role_reads_reject_invalid_pagination_before_http(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool, params: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        if asynchronous:
            await aclient.rbac.roles.list_page(**params)
        else:
            client.rbac.roles.list_page(**params)
    assert len(respx.calls) == 0


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("body", [{"roleName": "Missing identity"}, {"roleId": 43}])
@respx.mock
async def test_detail_identity_is_checked_without_changing_legacy_get(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool, body: dict[str, Any]
) -> None:
    route = respx.get(f"{ROLES_URL}/42").respond(200, json=body)
    response = (
        await aclient.rbac.roles.with_response.get_detail(42)
        if asynchronous
        else client.rbac.roles.with_response.get_detail(42)
    )
    with pytest.raises(ResponseValidationError):
        response.parse()
    assert response.json() == body
    assert route.call_count == 1
    legacy = await aclient.rbac.roles.get(42) if asynchronous else client.rbac.roles.get(42)
    assert type(legacy) is RbacRole


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_legacy_role_list_retains_its_original_pagination_behavior(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    route = respx.get(ROLES_URL).respond(200, json={"roles": []})
    if asynchronous:
        assert await aclient.rbac.roles.list(limit=0, offset=-1) == []
    else:
        assert client.rbac.roles.list(limit=0, offset=-1) == []
    assert dict(route.calls.last.request.url.params) == {"limit": "0", "offset": "-1"}


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_detail_identity_cannot_coerce_true_to_role_one(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    route = respx.get(f"{ROLES_URL}/1").respond(200, json={"roleId": True})
    with pytest.raises(ResponseValidationError):
        if asynchronous:
            await aclient.rbac.roles.get_detail(1)
        else:
            client.rbac.roles.get_detail(1)
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_admin_page_rejects_a_start_index_the_server_ignored(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    route = respx.get(ADMINS_URL).respond(
        200,
        json={"Resources": [ADMIN], "startIndex": 1, "totalResults": 200},
        headers={"x-request-id": "ignored-start-index"},
    )
    with pytest.raises(PaginationError) as caught:
        if asynchronous:
            await aclient.rbac.admins.list_page(start_index=101)
        else:
            client.rbac.admins.list_page(start_index=101)
    assert "startIndex does not match the requested page" in str(caught.value)
    assert caught.value.request_id == "ignored-start-index"
    assert caught.value.offset == 100
    assert dict(route.calls.last.request.url.params) == {"count": "100", "startIndex": "101"}
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_admin_page_rejects_more_rows_than_requested(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    respx.get(ADMINS_URL).respond(
        200, json={"Resources": [ADMIN] * 5, "startIndex": 1, "totalResults": 200}
    )
    with pytest.raises(PaginationError, match="exceeded the requested page size"):
        if asynchronous:
            await aclient.rbac.admins.list_page(count=2)
        else:
            client.rbac.admins.list_page(count=2)


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_admin_page_rejects_contradictory_total(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    respx.get(ADMINS_URL).respond(
        200,
        json={"Resources": [ADMIN], "startIndex": 41, "totalResults": 40},
        headers={"x-request-id": "bad-admin-total"},
    )
    with pytest.raises(PaginationError) as caught:
        if asynchronous:
            await aclient.rbac.admins.list_page(start_index=41)
        else:
            client.rbac.admins.list_page(start_index=41)
    assert caught.value.request_id == "bad-admin-total"
    assert caught.value.offset == 40


@pytest.mark.parametrize("total", [True, -1, "bogus", 1.5])
@respx.mock
def test_admin_page_treats_an_unusable_total_as_no_total(
    client: NetskopeClient, total: Any
) -> None:
    """A total the SDK cannot use leaves completeness unknown; it is not a failure."""
    route = respx.get(ADMINS_URL).respond(
        200, json={"Resources": [ADMIN], "startIndex": 1, "totalResults": total}
    )
    page = client.rbac.admins.list_page(count=1)
    assert page.total is None and page.has_more is None
    assert len(page.items) == 1 and route.call_count == 1


@pytest.mark.parametrize("count", [1001, 5000])
@respx.mock
def test_admin_count_above_the_scim_maximum_is_rejected_before_http(
    client: NetskopeClient, count: int
) -> None:
    with pytest.raises(ValidationError, match="maximum SCIM page size is 1000"):
        client.rbac.admins.list_page(count=count)
    assert len(respx.calls) == 0


@pytest.mark.parametrize("page_size", [0, 1001, True])
@respx.mock
def test_admin_iterator_page_size_is_bounded_before_http(
    client: NetskopeClient, page_size: int
) -> None:
    with pytest.raises(ValidationError, match="page_size must be an integer between 1 and 1000"):
        client.rbac.admins.list(page_size=page_size)
    assert len(respx.calls) == 0
