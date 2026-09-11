"""Administrative operations use typed public contracts and one HTTP request."""

from __future__ import annotations

import inspect
import json
from typing import Any

import httpx
import pytest
import respx
from pydantic import ValidationError as ModelValidationError

from netskope import NetskopeClient
from netskope.exceptions import (
    APIError,
    PaginationError,
    ResponseValidationError,
    ValidationError,
)
from netskope.models.dns import (
    DnsDeployment,
    DnsInheritanceGroupCreate,
    DnsInheritanceGroupDeployment,
    DnsInheritanceGroupPatch,
    DnsProfileCreate,
    DnsProfilePatch,
)
from netskope.models.ips import IpsAllowlistPatch
from netskope.models.notifications import NotificationTemplateWrite
from netskope.models.scim import ScimGroupCreate, ScimGroupPatch, ScimUserCreate, ScimUserPatch
from netskope.models.tokens import ApiTokenGrant, ApiTokenWrite
from netskope.models.users import UserQuery

BASE = "https://t.goskope.com"
USER = {
    "id": "007",
    "emails": ["one@example.com"],
    "accounts": [{"active": "false"}],
    "future": {"value": "0009"},
}
PROFILE = {"id": "547c581b-b779-4770-8b73-aeece0742252", "name": "Policy", "log_traffic": "All DNS"}
SCIM_USER = {"id": "007", "userName": "one@example.com", "active": "false"}

# The endpoint and request assertions are deliberately independent of SDK constants.
CASES = [
    (
        "users.with_response.list_page",
        (UserQuery(limit=2, offset=3),),
        {},
        "POST",
        "/api/v2/users/getusers",
        {"query": {"paging": {"limit": 2, "offset": 3}}},
        {},
        {"counts": {"totalResults": 10}, "data": [USER]},
        200,
    ),
    (
        "users.with_response.get_page",
        ("one@example.com",),
        {},
        "POST",
        "/api/v2/users/getusers",
        {
            "query": {
                "paging": {"limit": 1, "offset": 0},
                "filter": {"and": [{"emails": {"eq": "one@example.com"}}]},
            }
        },
        {},
        {"data": [USER]},
        200,
    ),
    (
        "users.groups.with_response.get_page",
        ("Engineering",),
        {},
        "POST",
        "/api/v2/users/getgroups",
        {
            "query": {
                "paging": {"limit": 1, "offset": 0},
                "filter": {"displayName": {"eq": "Engineering"}},
            }
        },
        {},
        {"data": [{"id": "g1", "userCount": "007"}]},
        200,
    ),
    (
        "users.groups.with_response.members_page",
        ("Engineering",),
        {"limit": 5, "offset": 2},
        "POST",
        "/api/v2/users/getusers",
        {
            "query": {
                "paging": {"limit": 5, "offset": 2},
                "filter": {"accounts.parentGroups": {"in": ["Engineering"]}},
            }
        },
        {},
        {"data": [USER]},
        200,
    ),
    (
        "scim.users.with_response.create",
        (ScimUserCreate(user_name="one@example.com", email="one@example.com", active=False),),
        {},
        "POST",
        "/api/v2/scim/Users",
        {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "one@example.com",
            "active": False,
            "emails": [{"value": "one@example.com", "primary": True}],
        },
        {},
        SCIM_USER,
        201,
    ),
    (
        "scim.users.with_response.patch",
        ("a/b", ScimUserPatch(fields={"active": False, "title": "007"})),
        {},
        "PATCH",
        "/api/v2/scim/Users/a%2Fb",
        {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {"op": "replace", "path": "active", "value": False},
                {"op": "replace", "path": "title", "value": "007"},
            ],
        },
        {},
        None,
        204,
    ),
    (
        "scim.groups.with_response.create",
        (ScimGroupCreate(display_name="Engineering", member_ids=[]),),
        {},
        "POST",
        "/api/v2/scim/Groups",
        {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "displayName": "Engineering",
            "members": [],
        },
        {},
        {"id": "g1", "displayName": "Engineering"},
        201,
    ),
    (
        "scim.groups.with_response.patch",
        ("g1", ScimGroupPatch(member_ids=[])),
        {},
        "PATCH",
        "/api/v2/scim/Groups/g1",
        {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [{"op": "replace", "path": "members", "value": []}],
        },
        {},
        None,
        204,
    ),
    (
        "tokens.with_response.list",
        (),
        {},
        "GET",
        "/api/v2/auth/tokens",
        None,
        {},
        [{"id": "007", "expires": "9999999999", "endpoints": []}],
        200,
    ),
    (
        "tokens.with_response.get",
        ("007",),
        {},
        "GET",
        "/api/v2/auth/tokens/007",
        None,
        {},
        {"id": "007", "name": "read-only"},
        200,
    ),
    (
        "notifications.with_response.list_templates",
        (),
        {},
        "GET",
        "/api/v2/notifications/user/templates",
        None,
        {},
        {"result": [{"id": "001", "title": "Blocked"}], "totalCount": 1},
        200,
    ),
    (
        "notifications.with_response.get_template",
        ("001",),
        {},
        "GET",
        "/api/v2/notifications/user/templates/001",
        None,
        {},
        {"id": "001", "title": "Blocked"},
        200,
    ),
    (
        "notifications.with_response.delivery_settings",
        (),
        {},
        "GET",
        "/api/v2/notifications/user/deliverysettings",
        None,
        {},
        {
            "cloudAppsDeliveryMethod": "client",
            "webTrafficDeliveryMethod": "browser",
            "notificationTimeout": "60",
        },
        200,
    ),
    (
        "enrollment.with_response.list_token_sets",
        (),
        {},
        "GET",
        "/api/v2/enrollment/tokenset",
        None,
        {},
        [{"tsid": 7, "auth_token": "one-time-secret"}],
        200,
    ),
    (
        "enrollment.with_response.create_token_set",
        (),
        {},
        "POST",
        "/api/v2/enrollment/tokenset",
        None,
        {},
        {"tsid": 7, "auth_token": "one-time-secret"},
        201,
    ),
    (
        "ips.with_response.status",
        (),
        {},
        "GET",
        "/api/v2/ips/status",
        None,
        {},
        {"data": {"web": True, "nonweb": False, "npa": True}},
        200,
    ),
    (
        "ips.with_response.list_allowlist",
        (),
        {},
        "GET",
        "/api/v2/ips/allowlist",
        None,
        {},
        {"data": {"src_ids": ["007"], "domain": ["example.test"], "dst_ids": []}},
        200,
    ),
    (
        "ips.with_response.list_signatures",
        (),
        {"limit": 2, "offset": 3, "reference": "cve"},
        "GET",
        "/api/v2/ips/signaturereferencelist",
        None,
        {"limit": "2", "offset": "3", "reference": "cve"},
        {"data": ["cve:2026-0001"]},
        200,
    ),
    (
        "devices.with_response.list_page",
        (),
        {"limit": 2, "offset": 3},
        "GET",
        "/api/v2/steering/devices",
        None,
        {"limit": "2", "offset": "3"},
        {"devices": [{"device_id": "007", "host_name": "workstation"}], "total": 10},
        200,
    ),
    (
        "devices.with_response.supported_os",
        (),
        {},
        "GET",
        "/api/v2/devices/supportedos",
        None,
        {},
        {"available_os": ["Windows", "macOS"]},
        200,
    ),
    (
        "dns.with_response.list_page",
        (),
        {
            "filter": "name eq Policy",
            "limit": 2,
            "offset": 3,
            "sort_by": "name",
            "sort_order": "desc",
        },
        "GET",
        "/api/v2/profiles/dns",
        None,
        {
            "filter": "name eq Policy",
            "limit": "2",
            "offset": "3",
            "sortby": "name",
            "sortorder": "desc",
        },
        {"profiles": [PROFILE], "total": 10},
        200,
    ),
    (
        "dns.with_response.get",
        (PROFILE["id"],),
        {},
        "GET",
        f"/api/v2/profiles/dns/{PROFILE['id']}",
        None,
        {},
        PROFILE,
        200,
    ),
    (
        "dns.with_response.create",
        (DnsProfileCreate(name="Policy"),),
        {},
        "POST",
        "/api/v2/profiles/dns",
        {"name": "Policy"},
        {"interactive": "true"},
        PROFILE,
        201,
    ),
    (
        "dns.with_response.update",
        (PROFILE["id"], DnsProfilePatch(description="", log_traffic="Blocked DNS")),
        {},
        "PATCH",
        f"/api/v2/profiles/dns/{PROFILE['id']}",
        {"description": "", "log_traffic": "Blocked DNS"},
        {"interactive": "true"},
        PROFILE,
        200,
    ),
    (
        "dns.with_response.delete",
        (PROFILE["id"],),
        {},
        "DELETE",
        f"/api/v2/profiles/dns/{PROFILE['id']}",
        None,
        {},
        {"status": "success"},
        200,
    ),
    (
        "dns.with_response.deploy",
        (DnsDeployment(ids=[PROFILE["id"]], change_note="Approved"),),
        {},
        "POST",
        "/api/v2/profiles/dns/deploy",
        {"ids": [PROFILE["id"]], "change_note": "Approved"},
        {},
        {"status": "success"},
        200,
    ),
    (
        "dns.inheritance_groups.with_response.list_page",
        (),
        {"limit": 1, "offset": 0},
        "GET",
        "/api/v2/profiles/dns/inheritancegroups",
        None,
        {"limit": "1", "offset": "0"},
        {"inheritancegroups": [{"id": "g1", "name": "Group"}], "total": 2},
        200,
    ),
    (
        "dns.inheritance_groups.with_response.get",
        ("g1",),
        {},
        "GET",
        "/api/v2/profiles/dns/inheritancegroups/g1",
        None,
        {},
        {"id": "g1", "name": "Group"},
        200,
    ),
    (
        "dns.inheritance_groups.with_response.create",
        (DnsInheritanceGroupCreate(name="Group"),),
        {},
        "POST",
        "/api/v2/profiles/dns/inheritancegroups",
        {"name": "Group"},
        {"interactive": "true"},
        {"id": "g1", "name": "Group"},
        201,
    ),
    (
        "dns.inheritance_groups.with_response.update",
        ("g1", DnsInheritanceGroupPatch(description="")),
        {},
        "PATCH",
        "/api/v2/profiles/dns/inheritancegroups/g1",
        {"description": ""},
        {"interactive": "true"},
        {"id": "g1", "name": "Group"},
        200,
    ),
    (
        "dns.inheritance_groups.with_response.delete",
        ("g1",),
        {},
        "DELETE",
        "/api/v2/profiles/dns/inheritancegroups/g1",
        None,
        {},
        None,
        204,
    ),
    (
        "dns.inheritance_groups.with_response.deploy",
        (DnsInheritanceGroupDeployment(ids=["g1"]),),
        {},
        "POST",
        "/api/v2/profiles/dns/inheritancegroups/deploy",
        {"ids": ["g1"]},
        {},
        {"status": "success"},
        200,
    ),
    *[
        (
            f"dns.with_response.{method}",
            (),
            {"limit": 2},
            "GET",
            f"/api/v2/profiles/dns/{key}",
            None,
            {"limit": "2"},
            {key: [{"id": "007", "name": "Reference"}], "total": 1},
            200,
        )
        for method, key in [
            ("list_tunnels", "tunnels"),
            ("list_domain_categories", "domaincategories"),
            ("list_record_types", "recordtypes"),
        ]
    ],
]


CASES.extend(
    [
        (
            "scim.users.with_response.list_page",
            (),
            {"count": 1, "start_index": 2},
            "GET",
            "/api/v2/scim/Users",
            None,
            {"count": "1", "startIndex": "2"},
            {"Resources": [SCIM_USER], "totalResults": 10, "startIndex": 2},
            200,
        ),
        (
            "scim.groups.with_response.list_page",
            (),
            {"count": 0},
            "GET",
            "/api/v2/scim/Groups",
            None,
            {"count": "0", "startIndex": "1"},
            {"Resources": [], "totalResults": 10, "startIndex": 1},
            200,
        ),
        (
            "tokens.with_response.create",
            (
                ApiTokenWrite(
                    name="Token",
                    expires=9999999999,
                    endpoints=[ApiTokenGrant(endpoint="/api/v2/events", permissions="r")],
                ),
            ),
            {},
            "POST",
            "/api/v2/auth/tokens",
            {
                "name": "Token",
                "expires": 9999999999,
                "endpoints": [{"endpoint": "/api/v2/events", "permissions": "r"}],
            },
            {},
            {"id": "007", "token": "one-time-secret"},
            201,
        ),
        (
            "tokens.with_response.update",
            (
                "007",
                ApiTokenWrite(
                    name="Token",
                    expires=9999999999,
                    endpoints=[ApiTokenGrant(endpoint="/api/v2/events", permissions="rw")],
                ),
            ),
            {},
            "PATCH",
            "/api/v2/auth/tokens/007",
            {
                "name": "Token",
                "expires": 9999999999,
                "endpoints": [{"endpoint": "/api/v2/events", "permissions": "rw"}],
            },
            {},
            {"id": "007", "name": "Token"},
            200,
        ),
        (
            "notifications.with_response.create_template",
            (
                NotificationTemplateWrite(
                    name="Blocked", title="Denied", message="No access", ack_button_text="OK"
                ),
            ),
            {},
            "POST",
            "/api/v2/notifications/user/templates",
            {"name": "Blocked", "title": "Denied", "message": "No access", "ackButtonText": "OK"},
            {},
            {"id": "007", "title": "Denied"},
            201,
        ),
        (
            "notifications.with_response.update_template",
            (
                "007",
                NotificationTemplateWrite(
                    name="Alert",
                    title="Continue?",
                    message="Policy alert",
                    action_type="useralert",
                    proceed_button_text="Yes",
                    stop_button_text="No",
                ),
            ),
            {},
            "PATCH",
            "/api/v2/notifications/user/templates/007",
            {
                "name": "Alert",
                "title": "Continue?",
                "message": "Policy alert",
                "templateActionType": "useralert",
                "proceedButtonText": "Yes",
                "stopButtonText": "No",
            },
            {},
            {"id": "007", "title": "Continue?"},
            200,
        ),
        (
            "ips.with_response.update_allowlist",
            (IpsAllowlistPatch(src_ids=[]),),
            {},
            "PATCH",
            "/api/v2/ips/allowlist",
            {"src_ids": []},
            {},
            {"status": "Success", "data": {"src_ids": [], "dst_ids": ["007"], "domain": []}},
            200,
        ),
    ]
)


def operation(client: Any, name: str) -> Any:
    target = client
    for part in name.split("."):
        target = getattr(target, part)
    return target


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    "name,args,kwargs,method,path,payload,params,body,status",
    CASES,
    ids=[case[0] for case in CASES],
)
@respx.mock
async def test_admin_response_wire_contract(
    client,
    aclient,
    asynchronous,
    name,
    args,
    kwargs,
    method,
    path,
    payload,
    params,
    body,
    status,
):
    route = respx.route(method=method, url=BASE + path).respond(
        status, **({"json": body} if body is not None else {})
    )
    result = operation(aclient if asynchronous else client, name)(*args, **kwargs)
    if inspect.isawaitable(result):
        result = await result
    parsed = result.parse()
    assert route.call_count == 1
    request = route.calls[0].request
    assert dict(request.url.params) == params
    assert (json.loads(request.content) if request.content else None) == payload
    assert "retry_safe" not in request.url.params
    if body is not None:
        assert result.json() == body
        assert result.parse() is parsed
    else:
        assert parsed is None


@pytest.mark.parametrize(
    "model,payload",
    [
        (UserQuery, {"limit": True}),
        (UserQuery, {"limit": 1001}),
        (UserQuery, {"offset": -1}),
        (UserQuery, {"filter": []}),
        (ScimUserCreate, {"user_name": "one", "email": "one", "active": "false"}),
        (ScimUserPatch, {"fields": {}}),
        (ScimUserPatch, {"fields": {"": True}}),
        (ScimGroupPatch, {}),
        (ScimGroupPatch, {"member_ids": None}),
        (DnsProfilePatch, {}),
        (DnsProfilePatch, {"description": None}),
        (DnsProfilePatch, {"log_traffic": False}),
        (DnsProfilePatch, {"future": "secret"}),
        (DnsDeployment, {"ids": ["g1"]}),
        (DnsDeployment, {"ids": [], "change_note": ""}),
        (DnsInheritanceGroupDeployment, {"ids": [1]}),
    ],
)
def test_invalid_request_models_fail_locally(model, payload):
    with pytest.raises(ModelValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize(
    "model,payload",
    [
        (ApiTokenWrite, {"name": "Token", "endpoints": []}),
        (ApiTokenWrite, {"name": "Token", "expires": True, "endpoints": []}),
        (ApiTokenGrant, {"endpoint": "/api/v2/events", "permissions": "read"}),
        (NotificationTemplateWrite, {"name": "Blocked", "title": "Denied", "message": "No access"}),
        (
            NotificationTemplateWrite,
            {
                "name": "Blocked",
                "title": "Denied",
                "message": "No access",
                "ack_button_text": "OK",
                "stop_button_text": "No",
            },
        ),
        (
            NotificationTemplateWrite,
            {
                "name": "Alert",
                "title": "Continue?",
                "message": "Access",
                "action_type": "useralert",
                "proceed_button_text": "Yes",
            },
        ),
        (IpsAllowlistPatch, {}),
        (IpsAllowlistPatch, {"domain": None}),
        (IpsAllowlistPatch, {"src_ids": [1]}),
        (IpsAllowlistPatch, {"ip": "192.0.2.1"}),
    ],
)
def test_corrected_write_contracts_reject_legacy_payloads(model, payload):
    with pytest.raises(ModelValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("namespace", ["users", "groups"])
@respx.mock
async def test_scim_dashboard_page_preserves_known_total(client, aclient, asynchronous, namespace):
    rows = [SCIM_USER] if namespace == "users" else [{"id": "g1", "displayName": "Group"}]
    route = respx.get(BASE + f"/api/v2/scim/{namespace.title()}").respond(
        200,
        json={"Resources": rows, "totalResults": 250, "startIndex": 1},
    )
    result = getattr((aclient if asynchronous else client).scim, namespace).list_page(count=1)
    if inspect.isawaitable(result):
        result = await result
    assert result.total == 250 and result.has_more is True and result.offset == 0
    assert route.call_count == 1


@respx.mock
def test_scim_page_rejects_more_rows_than_requested(client):
    route = respx.get(BASE + "/api/v2/scim/Users").respond(
        200, json={"Resources": [SCIM_USER] * 5, "totalResults": 250, "startIndex": 1}
    )
    with pytest.raises(PaginationError, match="exceeded the requested page size"):
        client.scim.users.list_page(count=2)
    assert route.call_count == 1


@pytest.mark.parametrize("count", [1001, -1, True])
@respx.mock
def test_scim_count_bounds_reject_before_http(client, count):
    with pytest.raises(ValidationError):
        client.scim.users.list_page(count=count)
    assert len(respx.calls) == 0


@pytest.mark.parametrize("namespace", ["users", "groups"])
@pytest.mark.parametrize("page_size", [0, 1001, -1, True])
@respx.mock
def test_scim_iterator_page_size_is_bounded_before_http(client, namespace, page_size):
    with pytest.raises(ValidationError, match="page_size must be an integer between 1 and 1000"):
        getattr(client.scim, namespace).list(page_size=page_size)
    assert len(respx.calls) == 0


@pytest.mark.parametrize("total", [True, -1, "bogus", 1.5])
@respx.mock
def test_scim_unusable_total_leaves_completeness_unknown(client, total):
    """An unusable totalResults states no total rather than failing the page."""
    route = respx.get(BASE + "/api/v2/scim/Users").respond(
        200, json={"Resources": [SCIM_USER], "totalResults": total, "startIndex": 1}
    )
    page = client.scim.users.list_page(count=1)
    assert page.total is None and page.has_more is None
    assert len(page.items) == 1 and route.call_count == 1


@pytest.mark.parametrize(
    "body",
    [
        {"Resources": [SCIM_USER], "totalResults": 0},
        {"Resources": [SCIM_USER], "totalResults": 10, "startIndex": 2},
    ],
)
@respx.mock
def test_scim_contradictory_page_metadata_fails(client, body):
    respx.get(BASE + "/api/v2/scim/Users").respond(200, json=body)
    with pytest.raises(PaginationError) as caught:
        client.scim.users.list_page(count=1)
    assert caught.value.offset == 0


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({"data": "secret"}, ResponseValidationError),
        ({"data": [1]}, ResponseValidationError),
        ({"counts": {}, "users": {}}, ResponseValidationError),
        ({"data": [USER], "counts": {"totalResults": 0}}, PaginationError),
    ],
)
@respx.mock
def test_invalid_user_envelope_carries_safe_metadata(client, body, expected):
    respx.post(BASE + "/api/v2/users/getusers").respond(
        200, json=body, headers={"x-request-id": "request-7"}
    )
    response = client.users.with_response.list_page()
    with pytest.raises(expected) as error:
        response.parse()
    assert error.value.request_method == "POST"
    assert error.value.request_path == "/api/v2/users/getusers"
    assert error.value.request_id == "request-7"
    assert "secret" not in str(error.value)


@respx.mock
def test_user_page_rejects_more_rows_than_requested(client):
    route = respx.post(BASE + "/api/v2/users/getusers").respond(
        200, json={"users": [USER, USER], "counts": {"totalResults": 10}}
    )
    response = client.users.with_response.list_page(UserQuery(limit=1))
    with pytest.raises(PaginationError, match="exceeded the requested page size") as caught:
        response.parse()
    assert caught.value.offset == 0 and route.call_count == 1


@respx.mock
def test_user_page_rejects_an_offset_the_service_ignored(client):
    respx.post(BASE + "/api/v2/users/getusers").respond(
        200, json={"users": [USER], "counts": {"totalResults": 10, "offset": 0}}
    )
    response = client.users.with_response.list_page(UserQuery(limit=5, offset=5))
    with pytest.raises(PaginationError, match="offset does not match") as caught:
        response.parse()
    assert caught.value.offset == 5


@respx.mock
def test_user_page_accepts_the_offset_it_asked_for(client):
    respx.post(BASE + "/api/v2/users/getusers").respond(
        200, json={"users": [USER], "counts": {"totalResults": 10, "offset": 5}}
    )
    page = client.users.with_response.list_page(UserQuery(limit=5, offset=5)).parse()
    assert (page.offset, page.total, page.has_more) == (5, 10, True)


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_user_page_selects_its_own_record_key(client, aclient, asynchronous):
    body = {
        "users": [USER],
        "groups": [{"id": "g1", "displayName": "Group"}],
        "counts": {"totalResults": 1},
    }
    route = respx.post(BASE + "/api/v2/users/getusers").respond(200, json=body)
    result = (aclient if asynchronous else client).users.with_response.list_page()
    if inspect.isawaitable(result):
        result = await result
    page = result.parse()
    assert [user.id for user in page.items] == ["007"]
    assert page.metadata == {
        "groups": [{"id": "g1", "displayName": "Group"}],
        "counts": {"totalResults": 1},
    }
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_group_page_selects_its_own_record_key(client, aclient, asynchronous):
    body = {"users": [USER], "groups": [{"id": "g1", "displayName": "Group"}]}
    route = respx.post(BASE + "/api/v2/users/getgroups").respond(200, json=body)
    result = (aclient if asynchronous else client).users.groups.with_response.list_page()
    if inspect.isawaitable(result):
        result = await result
    page = result.parse()
    assert [group.id for group in page.items] == ["g1"]
    assert route.call_count == 1


@pytest.mark.parametrize("total", [None, True, -1, 1.5, "invalid"])
@respx.mock
def test_unknown_dns_total_does_not_establish_completeness(client, total):
    respx.get(BASE + "/api/v2/profiles/dns").respond(
        200, json={"profiles": [PROFILE], "total": total}
    )
    result = client.dns.with_response.list_page().parse()
    assert result.total is None
    assert result.has_more is None


@pytest.mark.parametrize("limit,offset", [(151, 0), (True, 0), (1, -1)])
@respx.mock
def test_dns_bounds_reject_before_http(client, limit, offset):
    with pytest.raises(ValidationError):
        client.dns.with_response.list_page(limit=limit, offset=offset)
    assert not respx.calls


@pytest.mark.parametrize(
    "method,path,call",
    [
        (
            "POST",
            "/api/v2/scim/Users",
            lambda c: c.scim.users.with_response.create(
                ScimUserCreate(user_name="one", email="one")
            ),
        ),
        (
            "PATCH",
            "/api/v2/scim/Groups/g1",
            lambda c: c.scim.groups.with_response.patch("g1", ScimGroupPatch(member_ids=[])),
        ),
        ("DELETE", "/api/v2/scim/Users/u1", lambda c: c.scim.users.with_response.delete("u1")),
        (
            "POST",
            "/api/v2/profiles/dns/deploy",
            lambda c: c.dns.with_response.deploy(DnsDeployment(ids=["p1"], change_note="Approved")),
        ),
        (
            "PATCH",
            "/api/v2/profiles/dns/p1",
            lambda c: c.dns.with_response.update("p1", DnsProfilePatch(description="")),
        ),
        (
            "POST",
            "/api/v2/enrollment/tokenset",
            lambda c: c.enrollment.with_response.create_token_set(),
        ),
    ],
)
@respx.mock
def test_mutations_are_not_replayed(client, method, path, call):
    route = respx.route(method=method, url=BASE + path).respond(503, json={"message": "Try later"})
    with pytest.raises(APIError):
        call(client)
    assert route.call_count == 1


@respx.mock
def test_read_only_user_post_can_retry_without_query_leakage():
    route = respx.post(BASE + "/api/v2/users/getusers").mock(
        side_effect=[
            httpx.Response(503, json={"message": "Busy"}),
            httpx.Response(200, json={"data": [USER]}),
        ]
    )
    with NetskopeClient(tenant="t.goskope.com", api_token="tok", backoff_factor=0) as client:
        assert client.users.with_response.list_page().parse().items[0].id == "007"
    assert route.call_count == 2
    assert all(not call.request.url.params for call in route.calls)
