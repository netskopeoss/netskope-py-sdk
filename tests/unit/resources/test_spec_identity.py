"""Identity-slice conformance against the API gateway specs.

Every test here pins one request or one decoded body against
``production/endpoints/<area>/*.yaml`` in the api-gateway-endpoints repo and
cites the lines it was read from.  Fixtures are the spec's own examples.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.models.administration import AdminUser
from netskope.models.devices import SupportedOperatingSystems
from netskope.models.scim import ScimGroup, ScimGroupPatch, ScimUser, ScimUserPatch
from netskope.resources.scim.decoder import MAX_SCIM_PAGE_SIZE
from tests.unit.resources.conftest import sent_json

_USERS_URL = "https://t.goskope.com/api/v2/scim/Users"
_GROUPS_URL = "https://t.goskope.com/api/v2/scim/Groups"
_ADMINS_URL = "https://t.goskope.com/api/v2/platform/administration/scim/Users"
_ROLES_URL = "https://t.goskope.com/api/v2/rbac/roles"
_TOKENSET_URL = "https://t.goskope.com/api/v2/enrollment/tokenset"
_TOKENS_URL = "https://t.goskope.com/api/v2/auth/tokens"
_GET_USERS_URL = "https://t.goskope.com/api/v2/users/getusers"

_PATCH_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:PatchOp"

# platform/ms-platform.yaml:586-611 — one Resources entry of SCIMUsersPageDTO.
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

# enrollment/enrollment-service-configuration.yaml:744-773 — TokenSetResponse.
_TOKEN_SET = {
    "tsid": 4,
    "created_date": "2024-10-15T06:09:52.449Z",
    "auth_token": "vault:v1:Dta+itEEzx6aMalndfi2ZC1wH4+mjSYriEYScvBvYJnTGJYvuz5GyvmGeYVdyZ+t",
    "encrypt_token": "",
    "valid_till": None,
    "enforce_status": 0,
}

# rbac/ms-rbac.yaml:1618-1687 — GetRolesResponseDto wrapping one RoleViewDto.
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


class TestScimPatchAcknowledgments:
    """SPEC-I1: PATCH /Users/{id} and /Groups/{id} answer 204 with no body."""

    @respx.mock
    def test_legacy_user_update_returns_none_on_204(self, client: NetskopeClient) -> None:
        """scim-apis.yaml:2265-2266 declares 204 "Empty response" as the only success."""
        respx.patch(f"{_USERS_URL}/8f2c4a1b").mock(return_value=httpx.Response(204))
        assert client.scim.users.update("8f2c4a1b", {"active": False}) is None

    @respx.mock
    def test_legacy_user_update_still_decodes_a_body(self, client: NetskopeClient) -> None:
        """A tenant that answers 200 with a user is decoded rather than discarded."""
        respx.patch(f"{_USERS_URL}/8f2c4a1b").mock(
            return_value=httpx.Response(200, json={"id": "8f2c4a1b", "userName": "a@b.example"})
        )
        user = client.scim.users.update("8f2c4a1b", {"active": False})
        assert isinstance(user, ScimUser)
        assert user.user_name == "a@b.example"

    @respx.mock
    async def test_async_legacy_user_update_returns_none_on_204(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        respx.patch(f"{_USERS_URL}/8f2c4a1b").mock(return_value=httpx.Response(204))
        assert await aclient.scim.users.update("8f2c4a1b", {"active": False}) is None

    @respx.mock
    def test_typed_user_patch_returns_none_on_204(self, client: NetskopeClient) -> None:
        respx.patch(f"{_USERS_URL}/8f2c4a1b").mock(return_value=httpx.Response(204))
        response = client.scim.users.with_response.patch(
            "8f2c4a1b", ScimUserPatch(fields={"active": False})
        )
        assert response.parse() is None

    @respx.mock
    def test_typed_group_patch_returns_none_on_204(self, client: NetskopeClient) -> None:
        """scim-apis.yaml:700-701 declares the same empty response for groups."""
        respx.patch(f"{_GROUPS_URL}/grp-1").mock(return_value=httpx.Response(204))
        response = client.scim.groups.with_response.patch(
            "grp-1", ScimGroupPatch(display_name="new_group_name")
        )
        assert response.parse() is None

    @respx.mock
    async def test_async_typed_group_patch_returns_none_on_204(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        respx.patch(f"{_GROUPS_URL}/grp-1").mock(return_value=httpx.Response(204))
        response = await aclient.scim.groups.with_response.patch(
            "grp-1", ScimGroupPatch(display_name="new_group_name")
        )
        assert response.parse() is None


class TestScimPatchOperations:
    """SPEC-I2 / SPEC-I3: operations are path-scoped, with the spec's own path names."""

    @respx.mock
    def test_group_display_name_uses_the_lowercase_path(self, client: NetskopeClient) -> None:
        """The group path enum is members|externalid|displayname (scim-apis.yaml:610-616)."""
        route = respx.patch(f"{_GROUPS_URL}/grp-1").mock(return_value=httpx.Response(204))
        client.scim.groups.with_response.patch(
            "grp-1", ScimGroupPatch(display_name="new_group_name")
        )
        # The replaceDisplayName example, verbatim (scim-apis.yaml:658-666).
        assert sent_json(route) == {
            "schemas": [_PATCH_SCHEMA],
            "Operations": [{"op": "replace", "path": "displayname", "value": "new_group_name"}],
        }

    @respx.mock
    def test_group_members_keeps_the_lowercase_members_path(self, client: NetskopeClient) -> None:
        """``members`` is already the enum spelling (scim-apis.yaml:612, example :644-647)."""
        route = respx.patch(f"{_GROUPS_URL}/grp-1").mock(return_value=httpx.Response(204))
        client.scim.groups.with_response.patch("grp-1", ScimGroupPatch(member_ids=["u-1"]))
        assert sent_json(route)["Operations"] == [
            {"op": "replace", "path": "members", "value": [{"value": "u-1"}]}
        ]

    @respx.mock
    def test_group_patch_sends_one_operation_per_attribute(self, client: NetskopeClient) -> None:
        """The multipleOperations example lists one entry per attribute (:684-697)."""
        route = respx.patch(f"{_GROUPS_URL}/grp-1").mock(return_value=httpx.Response(204))
        client.scim.groups.with_response.patch(
            "grp-1", ScimGroupPatch(display_name="updated_group_name", member_ids=["u-1"])
        )
        assert [op["path"] for op in sent_json(route)["Operations"]] == [
            "displayname",
            "members",
        ]

    @respx.mock
    def test_legacy_user_update_is_path_scoped(self, client: NetskopeClient) -> None:
        """Every documented user operation carries a path (scim-apis.yaml:1950-1973)."""
        route = respx.patch(f"{_USERS_URL}/8f2c4a1b").mock(return_value=httpx.Response(204))
        client.scim.users.update("8f2c4a1b", {"active": False})
        # The replaceActiveStatus example, verbatim (scim-apis.yaml:2013-2021).
        assert sent_json(route) == {
            "schemas": [_PATCH_SCHEMA],
            "Operations": [{"op": "replace", "path": "active", "value": False}],
        }

    @respx.mock
    async def test_async_legacy_user_update_is_path_scoped(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        route = respx.patch(f"{_USERS_URL}/8f2c4a1b").mock(return_value=httpx.Response(204))
        await aclient.scim.users.update("8f2c4a1b", {"userName": "newuser@example.com"})
        # The replaceUserName example, verbatim (scim-apis.yaml:2004-2012).
        assert sent_json(route)["Operations"] == [
            {"op": "replace", "path": "userName", "value": "newuser@example.com"}
        ]

    @respx.mock
    def test_typed_user_patch_is_path_scoped(self, client: NetskopeClient) -> None:
        route = respx.patch(f"{_USERS_URL}/8f2c4a1b").mock(return_value=httpx.Response(204))
        client.scim.users.with_response.patch(
            "8f2c4a1b", ScimUserPatch(fields={"externalid": "external-user-123"})
        )
        assert sent_json(route)["Operations"] == [
            {"op": "replace", "path": "externalid", "value": "external-user-123"}
        ]


class TestScimGroupMembers:
    """SPEC-I7: members are excluded from a group read unless asked for."""

    @respx.mock
    def test_group_get_sends_no_attributes_by_default(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_GROUPS_URL}/grp-1").mock(
            return_value=httpx.Response(200, json={"id": "grp-1", "displayName": "sample_group1"})
        )
        client.scim.groups.get("grp-1")
        assert route.calls.last.request.url.params == httpx.QueryParams()

    @respx.mock
    def test_group_get_can_ask_for_members(self, client: NetskopeClient) -> None:
        """scim-apis.yaml:462 documents ``attributes=members``; the param is at :464-473."""
        route = respx.get(f"{_GROUPS_URL}/grp-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "grp-1",
                    "displayName": "sample_group1",
                    "members": [{"value": "u-1", "display": "User One"}],
                },
            )
        )
        group = client.scim.groups.get("grp-1", attributes="members")
        assert dict(route.calls.last.request.url.params) == {"attributes": "members"}
        assert isinstance(group, ScimGroup)
        assert [member.value for member in group.members] == ["u-1"]

    @respx.mock
    async def test_async_group_get_can_exclude_attributes(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        """``excludedAttributes`` is the companion parameter (scim-apis.yaml:474-479)."""
        route = respx.get(f"{_GROUPS_URL}/grp-1").mock(
            return_value=httpx.Response(200, json={"id": "grp-1"})
        )
        await aclient.scim.groups.get("grp-1", excluded_attributes="members")
        assert dict(route.calls.last.request.url.params) == {"excludedAttributes": "members"}


class TestScimPageSizeRail:
    """SPEC-I12: the page-size ceiling is an SDK rail, not a gateway rule."""

    @respx.mock
    def test_a_count_above_the_published_maxresults_is_accepted(
        self, client: NetskopeClient
    ) -> None:
        """``count`` is a plain integer with no bounds (scim-apis.yaml:1014-1025)."""
        route = respx.get(_USERS_URL).mock(
            return_value=httpx.Response(
                200, json={"totalResults": 0, "startIndex": 1, "Resources": []}
            )
        )
        client.scim.users.list_page(count=MAX_SCIM_PAGE_SIZE)
        assert dict(route.calls.last.request.url.params)["count"] == str(MAX_SCIM_PAGE_SIZE)

    def test_the_sdk_rail_stops_an_unbounded_page(self, client: NetskopeClient) -> None:
        from netskope.exceptions import ValidationError

        with pytest.raises(ValidationError):
            client.scim.users.list(page_size=MAX_SCIM_PAGE_SIZE + 1)


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


class TestSupportedOperatingSystems:
    """SPEC-I5: AvailableOsFamily has no required properties."""

    def test_a_missing_available_os_is_an_empty_list(self) -> None:
        """devices/provisioner-core.yaml:320-333 declares no ``required:`` list."""
        assert SupportedOperatingSystems.model_validate({}).available_os == []

    def test_the_documented_example_parses(self) -> None:
        families = ["windows", "mac", "android", "ios", "chromeos", "linux"]
        assert (
            SupportedOperatingSystems.model_validate({"available_os": families}).available_os
            == families
        )

    @respx.mock
    def test_typed_supported_os_tolerates_an_empty_body(self, client: NetskopeClient) -> None:
        respx.get("https://t.goskope.com/api/v2/devices/supportedos").mock(
            return_value=httpx.Response(200, json={})
        )
        assert client.devices.with_response.supported_os().parse().available_os == []


class TestUserLookupFilter:
    """SPEC-I6: userName belongs to EnterpriseAccount, not EnterpriseUser."""

    @respx.mock
    def test_username_lookup_is_account_scoped(self, client: NetskopeClient) -> None:
        """The spec's own getusers example filters on accounts.userName (:358-359)."""
        route = respx.post(_GET_USERS_URL).mock(
            return_value=httpx.Response(200, json={"counts": {"totalResults": 0}, "data": []})
        )
        client.users.get("itadmin", by="username")
        assert sent_json(route)["query"]["filter"] == {
            "and": [{"accounts.userName": {"eq": "itadmin"}}]
        }

    @respx.mock
    def test_email_lookup_stays_on_the_user_property(self, client: NetskopeClient) -> None:
        """``emails`` is a genuine EnterpriseUser property (usermanager.yaml:992-995)."""
        route = respx.post(_GET_USERS_URL).mock(
            return_value=httpx.Response(200, json={"counts": {"totalResults": 0}, "data": []})
        )
        client.users.get("test@netskope.local")
        assert sent_json(route)["query"]["filter"] == {
            "and": [{"emails": {"eq": "test@netskope.local"}}]
        }

    @respx.mock
    async def test_async_typed_username_page_is_account_scoped(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        route = respx.post(_GET_USERS_URL).mock(
            return_value=httpx.Response(200, json={"counts": {"totalResults": 0}, "data": []})
        )
        await aclient.users.with_response.get_page("itadmin", by="username")
        assert sent_json(route)["query"]["filter"] == {
            "and": [{"accounts.userName": {"eq": "itadmin"}}]
        }


class TestEnrollmentTokenSets:
    """SPEC-I8 / SPEC-I9: the token-set operations declare no body and no parameters."""

    @respx.mock
    def test_create_sends_no_body(self, client: NetskopeClient) -> None:
        """TokensetController_createTokenSet has no requestBody (:12-49)."""
        route = respx.post(_TOKENSET_URL).mock(return_value=httpx.Response(200, json=_TOKEN_SET))
        created = client.enrollment.create_token_set()
        request = route.calls.last.request
        assert request.content == b""
        assert "content-type" not in request.headers
        assert created.id == 4
        assert created.enforce_status == 0

    @respx.mock
    def test_list_sends_no_query(self, client: NetskopeClient) -> None:
        """TokensetController_getTokenSets has no parameters; its 200 is a bare array (:50-83)."""
        route = respx.get(_TOKENSET_URL).mock(return_value=httpx.Response(200, json=[_TOKEN_SET]))
        token_sets = client.enrollment.list_token_sets()
        assert route.calls.last.request.url.params == httpx.QueryParams()
        assert [ts.id for ts in token_sets] == [4]

    @respx.mock
    async def test_async_create_sends_no_body(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_TOKENSET_URL).mock(return_value=httpx.Response(200, json=_TOKEN_SET))
        await aclient.enrollment.create_token_set()
        assert route.calls.last.request.content == b""


class TestApiTokenRevoke:
    """SPEC-I16: revoke is a PATCH operation, distinct from DELETE."""

    @respx.mock
    def test_revoke_patches_the_operation(self, client: NetskopeClient) -> None:
        """ApiTokenUpdateRequest.operation is [reissue, revoke] (auth/api-tokens.yaml:86-94)."""
        route = respx.patch(f"{_TOKENS_URL}/tok-1").mock(
            return_value=httpx.Response(200, json={"id": "tok-1", "name": "ci-token"})
        )
        token = client.tokens.revoke("tok-1")
        assert route.calls.last.request.method == "PATCH"
        # "other fields ("name","expires" and "endpoints") are not allowed" (:87-90).
        assert sent_json(route) == {"operation": "revoke"}
        assert token.id == "tok-1"

    @respx.mock
    def test_delete_remains_the_delete_operation(self, client: NetskopeClient) -> None:
        """DELETE /tokens/{id} is its own operation (auth/api-tokens.yaml:212-226)."""
        route = respx.delete(f"{_TOKENS_URL}/tok-1").mock(
            return_value=httpx.Response(200, json={"id": "tok-1", "name": "ci-token"})
        )
        assert client.tokens.delete("tok-1") is None
        assert route.calls.last.request.method == "DELETE"

    @respx.mock
    async def test_async_revoke_patches_the_operation(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.patch(f"{_TOKENS_URL}/tok-1").mock(
            return_value=httpx.Response(200, json={"id": "tok-1", "name": "ci-token"})
        )
        await aclient.tokens.revoke("tok-1")
        assert sent_json(route) == {"operation": "revoke"}
