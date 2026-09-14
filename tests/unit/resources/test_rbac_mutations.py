"""Typed role writes validate requests and return one-write acknowledgments."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx
from pydantic import ValidationError as ModelValidationError

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import APIError, ResponseValidationError, TimeoutError, ValidationError
from netskope.models.rbac import (
    ApiGroupGrant,
    RbacRole,
    RbacRoleDetail,
    RbacRoleIpAddress,
    RoleCreate,
    RoleMutationReceipt,
    RolePatch,
)

URL = "https://t.goskope.com/api/v2/rbac/roles"
PAYLOAD = {
    "roleName": "Analyst",
    "roleDescription": "Read access",
    "apiGroups": [
        {
            "apiGroupId": 1,
            "permission": "r",
            "constraints": [{"constraintId": 2, "constraintValues": ["header-group"]}],
            "obfuscation": {
                "properties": ["user"],
                "enableScope": True,
                "scope": {"email": {"in": ["analyst@example.com"]}},
            },
        }
    ],
    "scope": {"groupname": {"!in": ["admins"]}},
    "ipAllowList": {"enableIpAllowList": True, "ipList": ["192.0.2.1", "192.0.2.2 - 192.0.2.5"]},
    "labels": {"assignedLabels": [{"id": "label-1", "permission": "rw"}], "readAll": False},
}


def test_request_aliases_and_omission_follow_gateway_contract() -> None:
    request = RoleCreate.model_validate(PAYLOAD)
    assert request.model_dump(mode="json", by_alias=True, exclude_unset=True) == PAYLOAD
    assert request.api_groups[0].permission == "r"
    assert RolePatch(description="").model_dump(by_alias=True, exclude_unset=True) == {
        "roleDescription": ""
    }
    assert RoleCreate(name="No grants", description="", api_groups=[]).model_dump(
        by_alias=True, exclude_unset=True
    ) == {"roleName": "No grants", "roleDescription": "", "apiGroups": []}
    assert RolePatch(api_groups=[ApiGroupGrant(api_group_id=1, permission="none")]).model_dump(
        by_alias=True, exclude_unset=True
    ) == {"apiGroups": [{"apiGroupId": 1, "permission": "none"}]}


@pytest.mark.parametrize(
    "model,payload",
    [
        (RoleCreate, {"roleName": "Analyst"}),
        (RoleCreate, {**PAYLOAD, "roleName": "  "}),
        (RoleCreate, {**PAYLOAD, "future": "secret-input"}),
        (RoleCreate, {**PAYLOAD, "apiGroups": [{"apiGroupId": "1", "permission": "r"}]}),
        (RoleCreate, {**PAYLOAD, "apiGroups": [{"apiGroupId": True, "permission": "r"}]}),
        (RoleCreate, {**PAYLOAD, "apiGroups": [{"apiGroupId": 1, "permission": "read"}]}),
        (
            RoleCreate,
            {**PAYLOAD, "apiGroups": [{"apiGroupId": 1, "permission": "r", "extra": True}]},
        ),
        (RoleCreate, {**PAYLOAD, "scope": {"email": {"equals": ["a@example.com"]}}}),
        (
            RoleCreate,
            {
                **PAYLOAD,
                "ipAllowList": {"enableIpAllowList": True, "ipList": [{"ipAddress": "192.0.2.1"}]},
            },
        ),
        (RoleCreate, {**PAYLOAD, "labels": {"assignedLabels": [], "unknown": True}}),
        (RolePatch, {}),
        (RolePatch, {"roleName": None}),
        (RolePatch, {"apiGroups": None}),
        (RolePatch, {"apiGroups": []}),
        (RolePatch, {"apiGroups": [{"apiGroupId": 1}]}),
        (RolePatch, {"apiGroups": [{"apiGroupId": 1, "permission": "r"}] * 2}),
    ],
)
def test_invalid_request_models_reject_ambiguous_or_unknown_fields(
    model: type[RoleCreate] | type[RolePatch], payload: dict[str, Any]
) -> None:
    with pytest.raises(ModelValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("operation", ["create", "update"])
@respx.mock
async def test_receipt_accessor_has_one_write_and_keeps_original_response(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool, operation: str
) -> None:
    body = {"data": {"roleId": "42", "future": {"audit": ["changed"]}}, "status": "success"}
    method = "POST" if operation == "create" else "PATCH"
    route = respx.request(method, URL if operation == "create" else f"{URL}/42").respond(
        200, json=body
    )
    if operation == "create":
        request = RoleCreate.model_validate(PAYLOAD)
        response = (
            await aclient.rbac.roles.with_response.create_receipt(request)
            if asynchronous
            else client.rbac.roles.with_response.create_receipt(request)
        )
        expected = PAYLOAD
    else:
        patch = RolePatch(description="")
        response = (
            await aclient.rbac.roles.with_response.update_receipt(42, patch)
            if asynchronous
            else client.rbac.roles.with_response.update_receipt(42, patch)
        )
        expected = {"roleDescription": ""}
    receipt = response.parse()
    assert type(receipt) is RoleMutationReceipt
    assert receipt.id == 42
    assert response.parse() is receipt
    assert response.json() == body
    assert json.loads(route.calls.last.request.content) == expected
    assert route.call_count == len(respx.calls) == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_normal_receipt_methods_do_not_fetch_details(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    post = respx.post(URL).respond(200, json={"roleId": 42})
    patch = respx.patch(f"{URL}/42").respond(200, json={"roleId": 42})
    request = RoleCreate(name="Analyst", description="", api_groups=[])
    update = RolePatch(name="Renamed")
    if asynchronous:
        created = await aclient.rbac.roles.create_receipt(request)
        updated = await aclient.rbac.roles.update_receipt(42, update)
    else:
        created = client.rbac.roles.create_receipt(request)
        updated = client.rbac.roles.update_receipt(42, update)
    assert type(created) is type(updated) is RoleMutationReceipt
    assert created.id == updated.id == 42
    assert post.call_count == patch.call_count == 1
    assert len(respx.calls) == 2


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("operation", ["create", "update"])
@respx.mock
async def test_mutated_typed_grant_lists_are_revalidated_before_sending(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool, operation: str
) -> None:
    grant = ApiGroupGrant(api_group_id=1, permission="r")
    if operation == "create":
        request = RoleCreate(name="Analyst", description="", api_groups=[grant])
        request.api_groups.append(grant)
        with pytest.raises(ValidationError, match="unique"):
            if asynchronous:
                await aclient.rbac.roles.create_receipt(request)
            else:
                client.rbac.roles.create_receipt(request)
    else:
        patch = RolePatch(api_groups=[grant])
        assert patch.api_groups is not None
        patch.api_groups.append(grant)
        with pytest.raises(ValidationError, match="unique"):
            if asynchronous:
                await aclient.rbac.roles.update_receipt(42, patch)
            else:
                client.rbac.roles.update_receipt(42, patch)
    assert len(respx.calls) == 0


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_mutated_nested_request_values_are_revalidated(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    request = RoleCreate.model_validate(PAYLOAD)
    assert request.ip_allow_list is not None
    request.ip_allow_list.ip_list.append(42)  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match=r"ip_list\.2"):
        if asynchronous:
            await aclient.rbac.roles.create_receipt(request)
        else:
            client.rbac.roles.create_receipt(request)
    assert len(respx.calls) == 0


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"roleId": None},
        {"roleId": True},
        {"roleId": {"secret": "response-secret"}},
        {"data": []},
        {"roleId": 99},
    ],
)
@respx.mock
async def test_invalid_or_mismatched_receipts_keep_request_evidence_without_replay(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool, body: dict[str, Any]
) -> None:
    route = respx.patch(f"{URL}/42").respond(200, json=body, headers={"x-request-id": "write-42"})
    response = (
        await aclient.rbac.roles.with_response.update_receipt(42, RolePatch(name="Renamed"))
        if asynchronous
        else client.rbac.roles.with_response.update_receipt(42, RolePatch(name="Renamed"))
    )
    with pytest.raises(ResponseValidationError) as caught:
        response.parse()
    assert caught.value.request_id == "write-42"
    assert caught.value.request_method == "PATCH"
    assert caught.value.request_path == "/api/v2/rbac/roles/42"
    assert "response-secret" not in str(caught.value)
    assert response.json() == body
    assert route.call_count == len(respx.calls) == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("operation", ["create", "update", "delete"])
@pytest.mark.parametrize("failure", ["server", "timeout"])
@respx.mock
async def test_writes_are_not_retried_even_when_transport_would_retry_reads(
    client: NetskopeClient,
    aclient: AsyncNetskopeClient,
    asynchronous: bool,
    operation: str,
    failure: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("netskope.core.retry._sleep_duration", lambda *args: 0)
    method = {"create": "POST", "update": "PATCH", "delete": "DELETE"}[operation]
    route = respx.request(method, URL if operation == "create" else f"{URL}/42")
    if failure == "server":
        route.respond(503, json={"message": "Unavailable"})
    else:
        route.mock(side_effect=httpx.ReadTimeout("Timeout"))
    with pytest.raises(APIError if failure == "server" else TimeoutError):
        if operation == "create":
            request = RoleCreate(name="Analyst", description="", api_groups=[])
            if asynchronous:
                await aclient.rbac.roles.create_receipt(request)
            else:
                client.rbac.roles.create_receipt(request)
        elif operation == "update":
            if asynchronous:
                await aclient.rbac.roles.update_receipt(42, RolePatch(name="Renamed"))
            else:
                client.rbac.roles.update_receipt(42, RolePatch(name="Renamed"))
        elif asynchronous:
            await aclient.rbac.roles.delete(42)
        else:
            client.rbac.roles.delete(42)
    assert route.call_count == len(respx.calls) == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_legacy_writes_keep_permissive_inputs_and_detail_return_types(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    post = respx.post(URL).respond(200, json={"roleId": 42})
    patch = respx.patch(f"{URL}/42").respond(200, json={"roleId": 42})
    get = respx.get(f"{URL}/42").respond(200, json={"roleId": 42, "roleName": "Analyst"})
    groups = [{"apiGroupId": 1, "permission": "future-level", "future": True}]
    if asynchronous:
        created = await aclient.rbac.roles.create("Analyst", api_groups=groups)
        updated = await aclient.rbac.roles.update(42, api_groups=[])
    else:
        created = client.rbac.roles.create("Analyst", api_groups=groups)
        updated = client.rbac.roles.update(42, api_groups=[])
    assert type(created) is type(updated) is RbacRole
    assert json.loads(post.calls.last.request.content)["apiGroups"] == groups
    assert json.loads(patch.calls.last.request.content) == {"apiGroups": []}
    assert get.call_count == 2


def test_detail_ip_entries_accept_gateway_objects_and_legacy_strings() -> None:
    detail = RbacRoleDetail.model_validate(
        {
            "roleId": 42,
            "ipAllowList": {
                "enableIpAllowList": True,
                "ipList": [
                    "192.0.2.1",
                    {"ipAddress": "192.0.2.2", "createdAt": "2025-01-15T10:00:00Z", "future": [1]},
                ],
            },
        }
    )
    assert detail.ip_allow_list is not None
    assert detail.ip_allow_list.ip_list[0] == "192.0.2.1"
    entry = detail.ip_allow_list.ip_list[1]
    assert isinstance(entry, RbacRoleIpAddress)
    assert entry.ip_address == "192.0.2.2"
    assert entry.created_at is not None
    assert entry.model_dump(by_alias=True, exclude_unset=True)["future"] == [1]
