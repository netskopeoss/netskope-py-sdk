"""Tests for the RBAC namespace (roles + admins) with mocked HTTP.

``client.rbac`` is not wired into the client yet, so the resource is
instantiated directly against the client's transport.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.rbac import RbacRole
from netskope.models.scim import ScimUser
from netskope.resources.rbac import AsyncRbacResource, RbacResource
from tests.unit.resources.conftest import sent_json

_ROLES_URL = "https://t.goskope.com/api/v2/rbac/roles"
_ADMINS_URL = "https://t.goskope.com/api/v2/platform/administration/scim/Users"

# List endpoint item shape (RoleViewDto).
_ROLE_VIEW = {
    "roleId": 42,
    "name": "SOC-Analyst",
    "type": 0,
    "obfuscated": False,
    "scoped": False,
    "description": "Read-only analyst role",
    "lastEdited": "2025-01-15T10:00:00Z",
    "createdBy": "admin@example.com",
    "aliasName": "",
    "userCount": 3,
    "updatedBy": "admin@example.com",
}

# Envelope for GET /rbac/roles (GetRolesResponseDto).
_LIST_BODY = {"version": "v3", "count": 1, "roles": [_ROLE_VIEW]}

# Detail endpoint shape (GetRoleResponseDTO) — different field names.
_ROLE_DETAIL = {
    "version": "v3",
    "roleId": 42,
    "roleName": "SOC-Analyst",
    "roleDescription": "Read-only analyst role",
    "scopes": [],
    "ipAllowList": {"enableIpAllowList": False, "ipList": []},
    "apiGroups": [
        {
            "apiGroupId": 1,
            "apiGroupName": "alerts",
            "permission": "r",
            "obfuscations": [],
            "constraints": [],
            "obfuscationScope": {"scopeEnabled": False, "scopes": []},
        }
    ],
    "isAliasNameTaken": False,
}

_ADMIN_USER = {
    "id": "5e6aef97-64fc-4b49-913b-f3adf24d52e4",
    "userName": "admin@example.com",
    "active": True,
    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
}

_ADMINS_PAGE = {"totalResults": 1, "startIndex": 1, "Resources": [_ADMIN_USER]}


class TestRbacRolesResource:
    """Tests for rbac.roles (sync)."""

    @respx.mock
    def test_list_extracts_roles_envelope(self, client: NetskopeClient) -> None:
        route = respx.get(_ROLES_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        roles = RbacResource(client._transport).roles.list()
        assert route.called
        assert len(roles) == 1
        assert isinstance(roles[0], RbacRole)
        assert roles[0].id == 42
        assert roles[0].name == "SOC-Analyst"
        assert roles[0].description == "Read-only analyst role"
        assert roles[0].type == 0
        assert roles[0].user_count == 3

    @respx.mock
    def test_list_sends_filter_params(self, client: NetskopeClient) -> None:
        route = respx.get(_ROLES_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        RbacResource(client._transport).roles.list(
            role_type="custom", scope="limited", search="SOC", limit=50, offset=10
        )
        params = route.calls.last.request.url.params
        assert params["type"] == "custom"
        assert params["scope"] == "limited"
        assert params["search"] == "SOC"
        assert params["limit"] == "50"
        assert params["offset"] == "10"

    @respx.mock
    def test_list_invalid_role_type_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError, match="role_type"):
            RbacResource(client._transport).roles.list(role_type="builtin")
        assert len(respx.calls) == 0

    @respx.mock
    def test_list_invalid_scope_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError, match="scope"):
            RbacResource(client._transport).roles.list(scope="global")
        assert len(respx.calls) == 0

    @respx.mock
    def test_get_maps_detail_aliases(self, client: NetskopeClient) -> None:
        respx.get(f"{_ROLES_URL}/42").mock(return_value=httpx.Response(200, json=_ROLE_DETAIL))
        role = RbacResource(client._transport).roles.get(42)
        assert role.id == 42
        assert role.name == "SOC-Analyst"
        assert role.description == "Read-only analyst role"
        assert role.is_alias_name_taken is False
        assert len(role.api_groups) == 1
        assert role.api_groups[0].api_group_id == 1
        assert role.api_groups[0].api_group_name == "alerts"
        assert role.api_groups[0].permission == "r"

    @respx.mock
    def test_create_payload_and_follow_up_get(self, client: NetskopeClient) -> None:
        """create() must POST the gateway field names, then GET the new role."""
        post_route = respx.post(_ROLES_URL).mock(
            return_value=httpx.Response(200, json={"roleId": 42})
        )
        get_route = respx.get(f"{_ROLES_URL}/42").mock(
            return_value=httpx.Response(200, json=_ROLE_DETAIL)
        )
        role = RbacResource(client._transport).roles.create(
            "SOC-Analyst",
            description="Read-only analyst role",
            api_groups=[{"apiGroupId": 1, "permission": "r"}],
        )
        assert sent_json(post_route) == {
            "roleName": "SOC-Analyst",
            "roleDescription": "Read-only analyst role",
            "apiGroups": [{"apiGroupId": 1, "permission": "r"}],
        }
        assert get_route.called
        assert isinstance(role, RbacRole)
        assert role.id == 42

    @respx.mock
    def test_create_defaults_send_required_fields(self, client: NetskopeClient) -> None:
        """The API requires roleName, roleDescription, and apiGroups on POST."""
        post_route = respx.post(_ROLES_URL).mock(
            return_value=httpx.Response(200, json={"roleId": 42})
        )
        respx.get(f"{_ROLES_URL}/42").mock(return_value=httpx.Response(200, json=_ROLE_DETAIL))
        RbacResource(client._transport).roles.create("Minimal")
        assert sent_json(post_route) == {
            "roleName": "Minimal",
            "roleDescription": "",
            "apiGroups": [],
        }

    @respx.mock
    def test_update_patches_only_set_fields(self, client: NetskopeClient) -> None:
        patch_route = respx.patch(f"{_ROLES_URL}/42").mock(
            return_value=httpx.Response(200, json={"roleId": 42})
        )
        get_route = respx.get(f"{_ROLES_URL}/42").mock(
            return_value=httpx.Response(200, json=_ROLE_DETAIL)
        )
        role = RbacResource(client._transport).roles.update(42, name="Renamed")
        assert sent_json(patch_route) == {"roleName": "Renamed"}
        assert get_route.called
        assert role.id == 42

    @respx.mock
    def test_update_requires_a_field(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError, match="at least one field"):
            RbacResource(client._transport).roles.update(42)
        assert len(respx.calls) == 0

    @respx.mock
    def test_delete(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_ROLES_URL}/42").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        assert RbacResource(client._transport).roles.delete(42) is None
        assert route.called


class TestRbacAdminsResource:
    """Tests for rbac.admins (sync)."""

    @respx.mock
    def test_list_sends_scim_params(self, client: NetskopeClient) -> None:
        route = respx.get(_ADMINS_URL).mock(return_value=httpx.Response(200, json=_ADMINS_PAGE))
        admins = list(RbacResource(client._transport).admins.list(page_size=50))
        assert len(admins) == 1
        assert isinstance(admins[0], ScimUser)
        assert admins[0].user_name == "admin@example.com"
        params = route.calls.last.request.url.params
        assert params["count"] == "50"
        assert params["startIndex"] == "1"
        assert "filter" not in params

    @respx.mock
    def test_list_sends_filter(self, client: NetskopeClient) -> None:
        route = respx.get(_ADMINS_URL).mock(return_value=httpx.Response(200, json=_ADMINS_PAGE))
        filter_expr = (
            'urn:ietf:params:scim:schemas:netskope:2.0:user[recordType eq "SERVICE_ACCOUNT"]'
        )
        list(RbacResource(client._transport).admins.list(filter_expr=filter_expr))
        assert route.calls.last.request.url.params["filter"] == filter_expr

    @respx.mock
    def test_list_paginates_by_start_index(self, client: NetskopeClient) -> None:
        pages = [
            {"totalResults": 3, "Resources": [_ADMIN_USER, _ADMIN_USER]},
            {"totalResults": 3, "Resources": [_ADMIN_USER]},
        ]
        route = respx.get(_ADMINS_URL).mock(
            side_effect=[httpx.Response(200, json=page) for page in pages]
        )
        admins = list(RbacResource(client._transport).admins.list(page_size=2))
        assert len(admins) == 3
        assert route.calls[0].request.url.params["startIndex"] == "1"
        assert route.calls[1].request.url.params["startIndex"] == "3"


class TestAsyncRbacRolesResource:
    """Tests for rbac.roles (async)."""

    @respx.mock
    async def test_list(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_ROLES_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        roles = await AsyncRbacResource(aclient._transport).roles.list()
        assert len(roles) == 1
        assert isinstance(roles[0], RbacRole)
        assert roles[0].id == 42
        assert roles[0].name == "SOC-Analyst"

    @respx.mock
    async def test_list_sends_filter_params(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_ROLES_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        await AsyncRbacResource(aclient._transport).roles.list(role_type="predefined")
        assert route.calls.last.request.url.params["type"] == "predefined"

    @respx.mock
    async def test_get(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_ROLES_URL}/42").mock(return_value=httpx.Response(200, json=_ROLE_DETAIL))
        role = await AsyncRbacResource(aclient._transport).roles.get(42)
        assert role.id == 42
        assert role.name == "SOC-Analyst"
        assert role.api_groups[0].permission == "r"

    @respx.mock
    async def test_create_payload_and_follow_up_get(self, aclient: AsyncNetskopeClient) -> None:
        post_route = respx.post(_ROLES_URL).mock(
            return_value=httpx.Response(200, json={"roleId": 42})
        )
        get_route = respx.get(f"{_ROLES_URL}/42").mock(
            return_value=httpx.Response(200, json=_ROLE_DETAIL)
        )
        role = await AsyncRbacResource(aclient._transport).roles.create(
            "SOC-Analyst",
            description="Read-only analyst role",
            api_groups=[{"apiGroupId": 1, "permission": "r"}],
        )
        assert sent_json(post_route) == {
            "roleName": "SOC-Analyst",
            "roleDescription": "Read-only analyst role",
            "apiGroups": [{"apiGroupId": 1, "permission": "r"}],
        }
        assert get_route.called
        assert role.id == 42

    @respx.mock
    async def test_update_patches_only_set_fields(self, aclient: AsyncNetskopeClient) -> None:
        patch_route = respx.patch(f"{_ROLES_URL}/42").mock(
            return_value=httpx.Response(200, json={"roleId": 42})
        )
        respx.get(f"{_ROLES_URL}/42").mock(return_value=httpx.Response(200, json=_ROLE_DETAIL))
        role = await AsyncRbacResource(aclient._transport).roles.update(42, description="Updated")
        assert sent_json(patch_route) == {"roleDescription": "Updated"}
        assert role.id == 42

    @respx.mock
    async def test_update_requires_a_field(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError, match="at least one field"):
            await AsyncRbacResource(aclient._transport).roles.update(42)
        assert len(respx.calls) == 0

    @respx.mock
    async def test_delete(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(f"{_ROLES_URL}/42").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        await AsyncRbacResource(aclient._transport).roles.delete(42)
        assert route.called


class TestAsyncRbacAdminsResource:
    """Tests for rbac.admins (async)."""

    @respx.mock
    async def test_list_sends_scim_params(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_ADMINS_URL).mock(return_value=httpx.Response(200, json=_ADMINS_PAGE))
        paginated = AsyncRbacResource(aclient._transport).admins.list(
            filter_expr='userName eq "admin@example.com"', page_size=25
        )
        admins = [admin async for admin in paginated]
        assert len(admins) == 1
        assert isinstance(admins[0], ScimUser)
        params = route.calls.last.request.url.params
        assert params["count"] == "25"
        assert params["startIndex"] == "1"
        assert params["filter"] == 'userName eq "admin@example.com"'
