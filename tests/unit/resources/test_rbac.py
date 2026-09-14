"""Tests for the RBAC namespace (roles + admins) with mocked HTTP.

``client.rbac`` is not wired into the client yet, so the resource is
instantiated directly against the client's transport.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import NetskopeError, ResponseValidationError, ValidationError
from netskope.models.administration import AdminUser
from netskope.models.rbac import RbacRole
from netskope.models.scim import ScimUser
from netskope.resources.rbac.resource import AsyncRbacResource, RbacResource
from tests.unit.resources.conftest import CONTRACT_BASE, sent_json

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


# --- Gateway contract conformance -------------------------------------------------------------
#
# Folded in from the spec-conformance reviews: each test cites the
# production/endpoints file and line whose shape it pins.

_contract_mock = respx.mock(assert_all_mocked=True, assert_all_called=False)


@_contract_mock
def test_the_platform_admin_scim_route_keeps_plain_json(contract_client: NetskopeClient) -> None:
    """ms-platform.yaml's admin SCIM route is plain application/json."""
    route = _contract_mock.get(
        f"{CONTRACT_BASE}/api/v2/platform/administration/scim/Users"
    ).respond(200, json={"Resources": [], "totalResults": 0, "startIndex": 1})
    contract_client.rbac.admins.list_page(count=1)
    assert route.calls.last.request.headers["Accept"] == "application/json"


_ADMIN_RESOURCE = {
    "id": "5e6aef97-64fc-4b49-913b-f3adf24d52e4",
    "userName": "user1@netskope.com",
    "active": True,
    "externalId": None,
    "metadata": {
        "created": None,
        "lastModified": "2024-11-25T08:45:36Z",
        "location": (
            "https://example.netskope.com/api/v2/administration/scim/Users/"
            "5e6aef97-64fc-4b49-913b-f3adf24d52e4"
        ),
    },
    "urn:ietf:params:scim:schemas:netskope:2.0:User": {
        "lastLogin": "2024-11-22T05:10:58Z",
        "provisionedBy": "LOCAL",
        "recordType": "USER",
        "role": {"value": 1, "display": "Tenant Admin"},
        "isVerified": True,
        "isLocked": False,
        "samlAssertedRoleId": None,
        "authType": "API_KEY",
        "apiAccessToken": {
            "expiresOn": "2024-11-25T09:16:32.625000Z",
            "issuedOn": "2024-11-25T09:16:32.625000Z",
            "value": None,
        },
    },
    "schemas": [
        "urn:ietf:params:scim:schemas:core:2.0:User",
        "urn:ietf:params:scim:schemas:extension:netskope:2.0:User",
    ],
}

_ROLES_BODY = {
    "version": "v3",
    "count": 7,
    "roles": [
        {
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
    ],
}


class TestRbacRolesTotal:
    """SPEC-I10: GetRolesResponseDto.count is the total, not opaque metadata."""

    @respx.mock
    def test_roles_page_keeps_count_as_the_total(self, client: NetskopeClient) -> None:
        """count is "Total number of roles fitting search criteria" (ms-rbac.yaml:1676-1678)."""
        respx.get(_ROLES_URL).mock(return_value=httpx.Response(200, json=_ROLES_BODY))
        page = client.rbac.roles.list_page(limit=1, offset=0)
        assert page.total == 7
        assert page.has_more is True

    @respx.mock
    async def test_async_roles_last_page_reports_no_more(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        body = {**_ROLES_BODY, "count": 1}
        respx.get(_ROLES_URL).mock(return_value=httpx.Response(200, json=body))
        page = await aclient.rbac.roles.list_page(limit=1, offset=0)
        assert page.total == 1
        assert page.has_more is False


class TestRbacAdmins:
    """SPEC-I14: admins are SCIMUserDTO records, not core SCIM users."""

    @respx.mock
    def test_admin_page_types_the_netskope_extension(self, client: NetskopeClient) -> None:
        """SCIMUserDTO carries role, recordType, provisionedBy (ms-platform.yaml:533-565)."""
        respx.get(_ADMINS_URL).mock(
            return_value=httpx.Response(
                200,
                json={"totalResults": 1, "startIndex": 1, "Resources": [_ADMIN_RESOURCE]},
            )
        )
        admin = client.rbac.admins.list_page(count=1).items[0]
        assert isinstance(admin, AdminUser)
        assert admin.record_type == "USER"
        assert admin.provisioned_by == "LOCAL"
        assert admin.role is not None
        assert (admin.role.value, admin.role.display) == (1, "Tenant Admin")
        assert admin.netskope_user is not None
        assert admin.netskope_user.auth_type == "API_KEY"
        assert admin.netskope_user.last_login is not None
        assert admin.metadata is not None
        assert admin.metadata.location.endswith("5e6aef97-64fc-4b49-913b-f3adf24d52e4")

    @respx.mock
    async def test_async_admin_iterator_yields_admin_users(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        respx.get(_ADMINS_URL).mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={"totalResults": 1, "startIndex": 1, "Resources": [_ADMIN_RESOURCE]},
                ),
                httpx.Response(200, json={"totalResults": 1, "startIndex": 2, "Resources": []}),
            ]
        )
        admins = [admin async for admin in aclient.rbac.admins.list(page_size=1)]
        assert [type(admin) for admin in admins] == [AdminUser]
        assert admins[0].user_name == "user1@netskope.com"

    def test_an_admin_has_no_core_scim_display_fields(self) -> None:
        """SCIMUserDTO declares no displayName, emails, name, or groups."""
        admin = AdminUser.model_validate(_ADMIN_RESOURCE)
        assert admin.display_name is None
        assert admin.name is None
        assert admin.emails == []
        assert admin.groups == []


class TestLegacyDecodeFailuresStayNetskopeErrors:
    """An unreadable 200 body still raises a NetskopeError on the untyped path.

    ``ApiResponse.parse`` restates a decoder's ``ValueError`` as
    ``ResponseValidationError`` (response.py:107-113), which is what every typed
    accessor relies on. ``roles.list()`` and ``roles.get()`` call the decoder
    directly on a ``_get`` body, so without an equivalent boundary the caller's
    documented ``except NetskopeError`` misses the failure entirely.
    """

    @respx.mock
    @pytest.mark.parametrize(
        "body",
        [
            pytest.param({"count": 0}, id="no-recognised-collection"),
            pytest.param({"data": [], "result": []}, id="competing-collections"),
        ],
    )
    def test_an_unreadable_roles_envelope_raises_a_netskope_error(
        self, client: NetskopeClient, body: dict[str, object]
    ) -> None:
        respx.get(_ROLES_URL).mock(return_value=httpx.Response(200, json=body))
        with pytest.raises(ResponseValidationError) as caught:
            RbacResource(client._transport).roles.list()
        assert isinstance(caught.value, NetskopeError)
        assert caught.value.request_method == "GET"

    @respx.mock
    async def test_async_unreadable_roles_envelope_raises_a_netskope_error(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        respx.get(_ROLES_URL).mock(return_value=httpx.Response(200, json={"count": 0}))
        with pytest.raises(ResponseValidationError):
            await AsyncRbacResource(aclient._transport).roles.list()

    @respx.mock
    def test_an_unreadable_role_body_raises_a_netskope_error(self, client: NetskopeClient) -> None:
        respx.get(f"{_ROLES_URL}/42").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ResponseValidationError) as caught:
            RbacResource(client._transport).roles.get(42)
        assert isinstance(caught.value, NetskopeError)

    @respx.mock
    async def test_async_unreadable_role_body_raises_a_netskope_error(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        respx.get(f"{_ROLES_URL}/42").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ResponseValidationError):
            await AsyncRbacResource(aclient._transport).roles.get(42)
