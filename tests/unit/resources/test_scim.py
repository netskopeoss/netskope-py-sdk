"""Tests for client.scim (users and groups) with mocked HTTP.

Covers the legacy dict-returning path in ``netskope.resources.scim.resource`` — the
outbound method, path, query and body of every public method, the ``Resources``
envelope decoding, the id validation it applies, and both SCIM paginators.
"""

from __future__ import annotations

from typing import ClassVar

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import PaginationError, ResponseValidationError, ValidationError
from netskope.models.scim import ScimGroup, ScimGroupPatch, ScimUser, ScimUserPatch
from netskope.resources.scim.decoder import (
    MAX_SCIM_PAGE_SIZE,
    AsyncScimGroupsResponses,
    AsyncScimUsersResponses,
    ScimGroupsResponses,
    ScimUsersResponses,
)
from netskope.resources.scim.resource import (
    AsyncScimGroupsResource,
    AsyncScimUsersResource,
    ScimGroupsResource,
    ScimUsersResource,
    _extract_scim,
)
from tests.unit.resources.conftest import CONTRACT_BASE, sent_json

_USERS_URL = "https://t.goskope.com/api/v2/scim/Users"
_GROUPS_URL = "https://t.goskope.com/api/v2/scim/Groups"

_USER = {
    "id": "8f2c4a1b",
    "userName": "alice@example.com",
    "displayName": "Alice Example",
    "active": True,
    "emails": [{"value": "alice@example.com", "primary": True, "type": "work"}],
    "name": {"givenName": "Alice", "familyName": "Example"},
    "externalId": "ext-77",
    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
}

_GROUP = {
    "id": "grp-1",
    "displayName": "Engineering",
    "members": [{"value": "8f2c4a1b", "display": "Alice Example"}],
    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
}


def _list_body(resources: list[dict[str, object]], *, start_index: int, total: int) -> dict:
    """An RFC 7644 ListResponse envelope."""
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": total,
        "startIndex": start_index,
        "itemsPerPage": len(resources),
        "Resources": resources,
    }


class TestExtractScim:
    """The module-level envelope reader used by both legacy paginators."""

    def test_prefers_the_resources_key(self) -> None:
        assert _extract_scim({"Resources": [_USER], "data": [_GROUP]}) == [_USER]

    def test_a_non_list_resources_value_falls_through_to_data(self) -> None:
        assert _extract_scim({"Resources": {"bad": 1}, "data": [_GROUP]}) == [_GROUP]

    def test_an_absent_resources_key_stops_before_the_data_fallback(self) -> None:
        """The ``[]`` default for ``Resources`` is itself a list, so ``data`` is skipped."""
        assert _extract_scim({"data": [_USER]}) == []

    def test_an_envelope_with_neither_key_yields_nothing(self) -> None:
        assert _extract_scim({"totalResults": 0}) == []

    def test_a_non_list_data_value_yields_nothing(self) -> None:
        assert _extract_scim({"Resources": None, "data": {"bad": 1}}) == []


class TestScimNamespace:
    """``client.scim`` exposes cached users and groups sub-resources."""

    def test_sync_namespaces(self, client: NetskopeClient) -> None:
        assert isinstance(client.scim.users, ScimUsersResource)
        assert isinstance(client.scim.groups, ScimGroupsResource)
        assert client.scim.users is client.scim.users
        assert client.scim.groups is client.scim.groups

    def test_async_namespaces(self, aclient: AsyncNetskopeClient) -> None:
        assert isinstance(aclient.scim.users, AsyncScimUsersResource)
        assert isinstance(aclient.scim.groups, AsyncScimGroupsResource)
        assert aclient.scim.users is aclient.scim.users
        assert aclient.scim.groups is aclient.scim.groups

    def test_response_accessors(self, client: NetskopeClient, aclient: AsyncNetskopeClient) -> None:
        assert isinstance(client.scim.users.with_response, ScimUsersResponses)
        assert isinstance(client.scim.groups.with_response, ScimGroupsResponses)
        assert isinstance(aclient.scim.users.with_response, AsyncScimUsersResponses)
        assert isinstance(aclient.scim.groups.with_response, AsyncScimGroupsResponses)


class TestScimUsersResource:
    """Tests for client.scim.users (sync)."""

    @respx.mock
    def test_list_page_sends_scim_paging_params(self, client: NetskopeClient) -> None:
        route = respx.get(_USERS_URL).mock(
            return_value=httpx.Response(200, json=_list_body([_USER], start_index=11, total=42))
        )
        page = client.scim.users.list_page(
            filter_expr='userName eq "alice@example.com"', count=10, start_index=11
        )
        request = route.calls.last.request
        assert dict(request.url.params) == {
            "count": "10",
            "startIndex": "11",
            "filter": 'userName eq "alice@example.com"',
        }
        assert page.total == 42
        assert page.offset == 10
        assert page.limit == 10
        assert [user.user_name for user in page.items] == ["alice@example.com"]

    @respx.mock
    def test_list_paginates_until_the_total_is_reached(self, client: NetskopeClient) -> None:
        second = dict(_USER, id="c19d", userName="bob@example.com")
        route = respx.get(_USERS_URL).mock(
            side_effect=[
                httpx.Response(200, json=_list_body([_USER], start_index=1, total=2)),
                httpx.Response(200, json=_list_body([second], start_index=2, total=2)),
            ]
        )
        users = list(client.scim.users.list(page_size=1))
        assert [user.user_name for user in users] == ["alice@example.com", "bob@example.com"]
        assert [dict(call.request.url.params)["startIndex"] for call in route.calls] == ["1", "2"]
        assert all(isinstance(user, ScimUser) for user in users)

    @respx.mock
    def test_list_sends_the_filter_on_every_page(self, client: NetskopeClient) -> None:
        route = respx.get(_USERS_URL).mock(
            return_value=httpx.Response(200, json=_list_body([], start_index=1, total=0))
        )
        assert list(client.scim.users.list(filter_expr="active eq true")) == []
        assert dict(route.calls.last.request.url.params)["filter"] == "active eq true"

    def test_list_rejects_a_page_size_past_the_ceiling(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError, match="between 1 and 1000"):
            client.scim.users.list(page_size=1001)

    @respx.mock
    def test_get(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_USERS_URL}/8f2c4a1b").mock(
            return_value=httpx.Response(200, json=_USER)
        )
        user = client.scim.users.get("8f2c4a1b")
        assert route.calls.last.request.method == "GET"
        assert isinstance(user, ScimUser)
        assert user.display_name == "Alice Example"
        assert user.emails[0].value == "alice@example.com"

    @respx.mock
    def test_create_sends_the_scim_user_schema(self, client: NetskopeClient) -> None:
        route = respx.post(_USERS_URL).mock(return_value=httpx.Response(201, json=_USER))
        user = client.scim.users.create(
            "alice@example.com",
            "alice@example.com",
            display_name="Alice Example",
            given_name="Alice",
            family_name="Example",
        )
        assert sent_json(route) == {
            "userName": "alice@example.com",
            "active": True,
            "emails": [{"value": "alice@example.com", "primary": True}],
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "displayName": "Alice Example",
            "name": {"givenName": "Alice", "familyName": "Example"},
        }
        assert user.id == "8f2c4a1b"

    @respx.mock
    def test_create_omits_the_optional_blocks(self, client: NetskopeClient) -> None:
        route = respx.post(_USERS_URL).mock(return_value=httpx.Response(201, json=_USER))
        client.scim.users.create("bob@example.com", "bob@example.com", active=False)
        body = sent_json(route)
        assert body["active"] is False
        assert "displayName" not in body
        assert "name" not in body

    @pytest.mark.parametrize(
        "kwargs,expected",
        [
            ({"family_name": "Example"}, {"familyName": "Example"}),
            ({"given_name": "Bob"}, {"givenName": "Bob"}),
        ],
    )
    @respx.mock
    def test_create_sends_only_the_name_parts_it_was_given(
        self, client: NetskopeClient, kwargs: dict, expected: dict
    ) -> None:
        route = respx.post(_USERS_URL).mock(return_value=httpx.Response(201, json=_USER))
        client.scim.users.create("bob@example.com", "bob@example.com", **kwargs)
        assert sent_json(route)["name"] == expected

    @respx.mock
    def test_update_sends_one_path_scoped_operation_per_field(self, client: NetskopeClient) -> None:
        """Every PATCH /Users/{id} operation is path-scoped (scim-apis.yaml:1955-2015)."""
        route = respx.patch(f"{_USERS_URL}/8f2c4a1b").mock(
            return_value=httpx.Response(200, json=dict(_USER, active=False))
        )
        user = client.scim.users.update("8f2c4a1b", {"active": False, "userName": "a@b.example"})
        assert sent_json(route) == {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {"op": "replace", "path": "active", "value": False},
                {"op": "replace", "path": "userName", "value": "a@b.example"},
            ],
        }
        assert user is not None
        assert user.active is False

    @respx.mock
    def test_delete(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_USERS_URL}/8f2c4a1b").mock(return_value=httpx.Response(204))
        assert client.scim.users.delete("8f2c4a1b") is None
        assert route.calls.last.request.method == "DELETE"

    @pytest.mark.parametrize("method", ["get", "delete"])
    def test_a_rejected_id_never_reaches_the_wire(
        self, client: NetskopeClient, method: str
    ) -> None:
        with respx.mock:
            route = respx.route(host="t.goskope.com")
            with pytest.raises(ValidationError, match="Invalid id for URL path"):
                getattr(client.scim.users, method)("user 1")
            assert not route.called

    def test_update_rejects_an_unsafe_id(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError, match="Invalid id for URL path"):
            client.scim.users.update("user 1", {"active": False})


class TestScimGroupsResource:
    """Tests for client.scim.groups (sync)."""

    @respx.mock
    def test_list_page_sends_scim_paging_params(self, client: NetskopeClient) -> None:
        route = respx.get(_GROUPS_URL).mock(
            return_value=httpx.Response(200, json=_list_body([_GROUP], start_index=1, total=1))
        )
        page = client.scim.groups.list_page(filter_expr='displayName eq "Engineering"')
        assert dict(route.calls.last.request.url.params) == {
            "count": "100",
            "startIndex": "1",
            "filter": 'displayName eq "Engineering"',
        }
        assert page.total == 1
        assert page.items[0].display_name == "Engineering"

    @respx.mock
    def test_list_decodes_the_resources_envelope(self, client: NetskopeClient) -> None:
        respx.get(_GROUPS_URL).mock(
            return_value=httpx.Response(200, json=_list_body([_GROUP], start_index=1, total=1))
        )
        groups = list(client.scim.groups.list())
        assert len(groups) == 1
        assert isinstance(groups[0], ScimGroup)
        assert groups[0].members[0].value == "8f2c4a1b"

    @respx.mock
    def test_list_reads_the_data_key_only_when_resources_is_unusable(
        self, client: NetskopeClient
    ) -> None:
        """``_extract_scim`` reaches ``data`` only past a non-list ``Resources``."""
        respx.get(_GROUPS_URL).mock(
            return_value=httpx.Response(
                200, json={"Resources": None, "data": [_GROUP], "totalResults": 1}
            )
        )
        assert [group.id for group in client.scim.groups.list()] == ["grp-1"]

    @respx.mock
    def test_list_sends_the_filter(self, client: NetskopeClient) -> None:
        route = respx.get(_GROUPS_URL).mock(
            return_value=httpx.Response(200, json=_list_body([], start_index=1, total=0))
        )
        assert list(client.scim.groups.list(filter_expr='displayName eq "Engineering"')) == []
        assert dict(route.calls.last.request.url.params)["filter"] == 'displayName eq "Engineering"'

    def test_list_rejects_a_page_size_past_the_ceiling(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError, match="between 1 and 1000"):
            client.scim.groups.list(page_size=0)

    @respx.mock
    def test_get(self, client: NetskopeClient) -> None:
        respx.get(f"{_GROUPS_URL}/grp-1").mock(return_value=httpx.Response(200, json=_GROUP))
        group = client.scim.groups.get("grp-1")
        assert isinstance(group, ScimGroup)
        assert group.display_name == "Engineering"

    @respx.mock
    def test_create_sends_members_when_given(self, client: NetskopeClient) -> None:
        route = respx.post(_GROUPS_URL).mock(return_value=httpx.Response(201, json=_GROUP))
        group = client.scim.groups.create("Engineering", member_ids=["8f2c4a1b"])
        assert sent_json(route) == {
            "displayName": "Engineering",
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "members": [{"value": "8f2c4a1b"}],
        }
        assert group.id == "grp-1"

    @respx.mock
    def test_create_omits_an_empty_member_list(self, client: NetskopeClient) -> None:
        route = respx.post(_GROUPS_URL).mock(return_value=httpx.Response(201, json=_GROUP))
        client.scim.groups.create("Engineering", member_ids=[])
        assert "members" not in sent_json(route)

    @respx.mock
    def test_update_replaces_the_group_with_put(self, client: NetskopeClient) -> None:
        route = respx.put(f"{_GROUPS_URL}/grp-1").mock(
            return_value=httpx.Response(200, json=_GROUP)
        )
        group = client.scim.groups.update("grp-1", display_name="Engineering", member_ids=[])
        # PUT is a replacement: an explicit empty list must be sent, not dropped.
        assert sent_json(route) == {
            "displayName": "Engineering",
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "members": [],
        }
        assert group.display_name == "Engineering"

    @respx.mock
    def test_update_without_members_leaves_the_membership_untouched(
        self, client: NetskopeClient
    ) -> None:
        route = respx.put(f"{_GROUPS_URL}/grp-1").mock(
            return_value=httpx.Response(200, json=_GROUP)
        )
        client.scim.groups.update("grp-1", display_name="Platform")
        assert "members" not in sent_json(route)

    @respx.mock
    def test_delete(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_GROUPS_URL}/grp-1").mock(return_value=httpx.Response(204))
        assert client.scim.groups.delete("grp-1") is None
        assert route.calls.last.request.method == "DELETE"

    @pytest.mark.parametrize("method", ["get", "delete"])
    def test_a_rejected_id_never_reaches_the_wire(
        self, client: NetskopeClient, method: str
    ) -> None:
        with respx.mock:
            route = respx.route(host="t.goskope.com")
            with pytest.raises(ValidationError, match="Invalid id for URL path"):
                getattr(client.scim.groups, method)("grp 1")
            assert not route.called

    def test_update_rejects_an_unsafe_id(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError, match="Invalid id for URL path"):
            client.scim.groups.update("", display_name="Engineering")


class TestScimIdValidation:
    """The legacy resources share ``quote_id`` with the typed accessors.

    An id is percent-encoded into its path segment, so delimiters can never
    alter the request path; only empty, whitespace-bearing, control-character
    or dot-only ids are rejected, and they are rejected before any request.
    """

    @pytest.mark.parametrize("user_id", ["8f2c4a1b", "user_1", "user-1", "A1"])
    @respx.mock
    def test_accepted_ids_reach_the_path_verbatim(
        self, client: NetskopeClient, user_id: str
    ) -> None:
        route = respx.get(f"{_USERS_URL}/{user_id}").mock(
            return_value=httpx.Response(200, json=_USER)
        )
        client.scim.users.get(user_id)
        assert route.calls.last.request.url.path == f"/api/v2/scim/Users/{user_id}"

    @pytest.mark.parametrize(
        ("user_id", "encoded"),
        [
            ("user@example.com", "user%40example.com"),
            ("b3f2-1a.9", "b3f2-1a.9"),
            ("../../admin", "..%2F..%2Fadmin"),
            ("a/b", "a%2Fb"),
        ],
    )
    @respx.mock
    def test_delimiters_are_percent_encoded_into_one_segment(
        self, client: NetskopeClient, user_id: str, encoded: str
    ) -> None:
        route = respx.route(host="t.goskope.com", method="GET").mock(
            return_value=httpx.Response(200, json=_USER)
        )
        client.scim.users.get(user_id)
        assert route.called
        assert route.calls.last.request.url.raw_path == f"/api/v2/scim/Users/{encoded}".encode()

    @pytest.mark.parametrize("user_id", ["user 1", "", "8f2c4a1b\n", ".", ".."])
    def test_rejected_ids(self, client: NetskopeClient, user_id: str) -> None:
        with respx.mock:
            route = respx.route(host="t.goskope.com")
            with pytest.raises(ValidationError, match="Invalid id for URL path"):
                client.scim.users.get(user_id)
            assert not route.called


class TestLegacyAndTypedIdPoliciesAgree:
    """Both SCIM paths percent-encode the same id the same way."""

    @respx.mock
    def test_both_paths_send_the_same_encoded_id(self, client: NetskopeClient) -> None:
        legacy = respx.get(f"{_USERS_URL}/user%40example.com").mock(
            return_value=httpx.Response(200, json=_USER)
        )
        typed = respx.delete(f"{_USERS_URL}/user%40example.com").mock(
            return_value=httpx.Response(204)
        )
        client.scim.users.get("user@example.com")
        client.scim.users.with_response.delete("user@example.com")
        assert legacy.called and typed.called
        for route in (legacy, typed):
            assert route.calls.last.request.url.raw_path.endswith(b"/user%40example.com")


class TestAsyncScimUsersResource:
    """Tests for client.scim.users (async)."""

    @respx.mock
    async def test_list_page(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_USERS_URL).mock(
            return_value=httpx.Response(200, json=_list_body([_USER], start_index=1, total=1))
        )
        page = await aclient.scim.users.list_page(count=25)
        assert dict(route.calls.last.request.url.params) == {"count": "25", "startIndex": "1"}
        assert page.items[0].user_name == "alice@example.com"
        assert page.total == 1

    @respx.mock
    async def test_list_paginates_until_the_total_is_reached(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        second = dict(_USER, id="c19d", userName="bob@example.com")
        route = respx.get(_USERS_URL).mock(
            side_effect=[
                httpx.Response(200, json=_list_body([_USER], start_index=1, total=2)),
                httpx.Response(200, json=_list_body([second], start_index=2, total=2)),
            ]
        )
        users = [user async for user in aclient.scim.users.list(page_size=1)]
        assert [user.user_name for user in users] == ["alice@example.com", "bob@example.com"]
        assert [dict(call.request.url.params)["startIndex"] for call in route.calls] == ["1", "2"]

    @respx.mock
    async def test_list_sends_the_filter(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_USERS_URL).mock(
            return_value=httpx.Response(200, json=_list_body([], start_index=1, total=0))
        )
        assert [user async for user in aclient.scim.users.list(filter_expr="active eq true")] == []
        assert dict(route.calls.last.request.url.params)["filter"] == "active eq true"

    def test_list_rejects_a_page_size_past_the_ceiling(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError, match="between 1 and 1000"):
            aclient.scim.users.list(page_size=1001)

    @respx.mock
    async def test_get(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_USERS_URL}/8f2c4a1b").mock(return_value=httpx.Response(200, json=_USER))
        user = await aclient.scim.users.get("8f2c4a1b")
        assert isinstance(user, ScimUser)
        assert user.external_id == "ext-77"

    @respx.mock
    async def test_create(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_USERS_URL).mock(return_value=httpx.Response(201, json=_USER))
        user = await aclient.scim.users.create(
            "alice@example.com",
            "alice@example.com",
            display_name="Alice Example",
            given_name="Alice",
        )
        assert sent_json(route) == {
            "userName": "alice@example.com",
            "active": True,
            "emails": [{"value": "alice@example.com", "primary": True}],
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "displayName": "Alice Example",
            "name": {"givenName": "Alice"},
        }
        assert user.active is True

    @respx.mock
    async def test_create_sends_only_the_family_name_it_was_given(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        route = respx.post(_USERS_URL).mock(return_value=httpx.Response(201, json=_USER))
        await aclient.scim.users.create("bob@example.com", "bob@example.com", family_name="Example")
        assert sent_json(route)["name"] == {"familyName": "Example"}

    @respx.mock
    async def test_create_without_any_name_parts_omits_the_name_block(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        route = respx.post(_USERS_URL).mock(return_value=httpx.Response(201, json=_USER))
        await aclient.scim.users.create("bob@example.com", "bob@example.com", active=False)
        body = sent_json(route)
        assert body["active"] is False
        assert "name" not in body
        assert "displayName" not in body

    @respx.mock
    async def test_update(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.patch(f"{_USERS_URL}/8f2c4a1b").mock(
            return_value=httpx.Response(200, json=dict(_USER, displayName="Alice E"))
        )
        user = await aclient.scim.users.update("8f2c4a1b", {"displayName": "Alice E"})
        assert sent_json(route)["Operations"] == [
            {"op": "replace", "path": "displayName", "value": "Alice E"}
        ]
        assert user is not None
        assert user.display_name == "Alice E"

    @respx.mock
    async def test_delete(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(f"{_USERS_URL}/8f2c4a1b").mock(return_value=httpx.Response(204))
        assert await aclient.scim.users.delete("8f2c4a1b") is None
        assert route.called

    @respx.mock
    async def test_an_unsafe_id_never_reaches_the_wire(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.route(host="t.goskope.com")
        for call in (
            aclient.scim.users.get("user 1"),
            aclient.scim.users.update("user 1", {"active": False}),
            aclient.scim.users.delete("user 1"),
        ):
            with pytest.raises(ValidationError, match="Invalid id for URL path"):
                await call
        assert not route.called


class TestAsyncScimGroupsResource:
    """Tests for client.scim.groups (async)."""

    @respx.mock
    async def test_list_page(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_GROUPS_URL).mock(
            return_value=httpx.Response(200, json=_list_body([_GROUP], start_index=1, total=1))
        )
        page = await aclient.scim.groups.list_page(count=5, start_index=1)
        assert dict(route.calls.last.request.url.params) == {"count": "5", "startIndex": "1"}
        assert page.items[0].id == "grp-1"

    @respx.mock
    async def test_list_paginates_until_a_short_page(self, aclient: AsyncNetskopeClient) -> None:
        second = dict(_GROUP, id="grp-2", displayName="Platform")
        route = respx.get(_GROUPS_URL).mock(
            side_effect=[
                httpx.Response(200, json={"Resources": [_GROUP, second], "startIndex": 1}),
                httpx.Response(200, json={"Resources": [], "startIndex": 3}),
            ]
        )
        groups = [group async for group in aclient.scim.groups.list(page_size=2)]
        assert [group.display_name for group in groups] == ["Engineering", "Platform"]
        assert [dict(call.request.url.params)["startIndex"] for call in route.calls] == ["1", "3"]

    @respx.mock
    async def test_list_sends_the_filter(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_GROUPS_URL).mock(
            return_value=httpx.Response(200, json=_list_body([], start_index=1, total=0))
        )
        groups = aclient.scim.groups.list(filter_expr='displayName eq "Platform"')
        assert [group async for group in groups] == []
        assert dict(route.calls.last.request.url.params)["filter"] == 'displayName eq "Platform"'

    def test_list_rejects_a_page_size_past_the_ceiling(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError, match="between 1 and 1000"):
            aclient.scim.groups.list(page_size=-1)

    @respx.mock
    async def test_get(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_GROUPS_URL}/grp-1").mock(return_value=httpx.Response(200, json=_GROUP))
        group = await aclient.scim.groups.get("grp-1")
        assert group.members[0].display == "Alice Example"

    @respx.mock
    async def test_create(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_GROUPS_URL).mock(return_value=httpx.Response(201, json=_GROUP))
        group = await aclient.scim.groups.create("Engineering", member_ids=["8f2c4a1b"])
        assert sent_json(route)["members"] == [{"value": "8f2c4a1b"}]
        assert group.display_name == "Engineering"

    @respx.mock
    async def test_create_omits_an_empty_member_list(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_GROUPS_URL).mock(return_value=httpx.Response(201, json=_GROUP))
        await aclient.scim.groups.create("Engineering")
        assert "members" not in sent_json(route)

    @respx.mock
    async def test_update(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.put(f"{_GROUPS_URL}/grp-1").mock(
            return_value=httpx.Response(200, json=_GROUP)
        )
        group = await aclient.scim.groups.update(
            "grp-1", display_name="Engineering", member_ids=["8f2c4a1b"]
        )
        assert sent_json(route) == {
            "displayName": "Engineering",
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "members": [{"value": "8f2c4a1b"}],
        }
        assert group.id == "grp-1"

    @respx.mock
    async def test_update_without_members_leaves_the_membership_untouched(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        route = respx.put(f"{_GROUPS_URL}/grp-1").mock(
            return_value=httpx.Response(200, json=_GROUP)
        )
        await aclient.scim.groups.update("grp-1", display_name="Platform")
        assert "members" not in sent_json(route)

    @respx.mock
    async def test_delete(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(f"{_GROUPS_URL}/grp-1").mock(return_value=httpx.Response(204))
        assert await aclient.scim.groups.delete("grp-1") is None
        assert route.called

    @respx.mock
    async def test_an_unsafe_id_never_reaches_the_wire(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.route(host="t.goskope.com")
        for call in (
            aclient.scim.groups.get("grp 1"),
            aclient.scim.groups.update("grp 1", display_name="Engineering"),
            aclient.scim.groups.delete("grp 1"),
        ):
            with pytest.raises(ValidationError, match="Invalid id for URL path"):
                await call
        assert not route.called


# --- Gateway contract conformance -------------------------------------------------------------
#
# Folded in from the spec-conformance reviews: each test cites the
# production/endpoints file and line whose shape it pins.


class TestScimResponseDeletes:
    @respx.mock
    def test_groups_delete(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_GROUPS_URL}/grp-1").mock(return_value=httpx.Response(204))
        assert client.scim.groups.with_response.delete("grp-1") is None
        assert route.calls.last.request.method == "DELETE"

    @respx.mock
    def test_groups_delete_percent_encodes_the_id(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_GROUPS_URL}/eng%2Fweb").mock(return_value=httpx.Response(204))
        client.scim.groups.with_response.delete("eng/web")
        assert route.calls.last.request.url.raw_path.endswith(b"/eng%2Fweb")

    def test_groups_delete_rejects_an_id_with_whitespace(self, client: NetskopeClient) -> None:
        with respx.mock:
            route = respx.route(host="t.goskope.com")
            with pytest.raises(ValidationError, match="Invalid id for URL path"):
                client.scim.groups.with_response.delete("grp 1")
            assert not route.called

    @respx.mock
    async def test_async_users_delete(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(f"{_USERS_URL}/8f2c4a1b").mock(return_value=httpx.Response(204))
        assert await aclient.scim.users.with_response.delete("8f2c4a1b") is None
        assert route.called

    @respx.mock
    async def test_async_users_delete_percent_encodes_the_id(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        route = respx.delete(f"{_USERS_URL}/user%40example.com").mock(
            return_value=httpx.Response(204)
        )
        await aclient.scim.users.with_response.delete("user@example.com")
        assert route.calls.last.request.url.raw_path.endswith(b"/user%40example.com")

    @respx.mock
    async def test_async_groups_delete(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(f"{_GROUPS_URL}/grp-1").mock(return_value=httpx.Response(204))
        assert await aclient.scim.groups.with_response.delete("grp-1") is None
        assert route.called


_SCIM_USERS_URL = f"{CONTRACT_BASE}/api/v2/scim/Users"
_contract_mock = respx.mock(assert_all_mocked=True, assert_all_called=False)
_SCIM_ACCEPT = "application/scim+json;charset=utf-8, application/json"


@_contract_mock
def test_scim_accept_lists_both_documented_media_types(contract_client: NetskopeClient) -> None:
    route = _contract_mock.get(_SCIM_USERS_URL).respond(
        200, json={"Resources": [], "totalResults": 0, "startIndex": 1}
    )
    contract_client.scim.users.list_page(count=1)
    assert route.calls.last.request.headers["Accept"] == _SCIM_ACCEPT


@_contract_mock
def test_scim_content_type_remains_the_bare_scim_type(contract_client: NetskopeClient) -> None:
    route = _contract_mock.post(_SCIM_USERS_URL).respond(
        201, json={"id": "u1", "userName": "a@b.c", "active": True}
    )
    contract_client.scim.users.create("a@b.c", email="a@b.c")
    headers = route.calls.last.request.headers
    assert headers["Content-Type"] == "application/scim+json;charset=utf-8"
    assert headers["Accept"] == _SCIM_ACCEPT


_PATCH_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:PatchOp"


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


class TestAnEmptyListResponseDecodes:
    """A SCIM search that matched nothing is a page, not a decode failure.

    RFC 7644 3.4.2 makes ``Resources`` REQUIRED only when ``totalResults`` is
    non-zero, and the gateway's SCIM schema never lists it in a ``required:``
    block. The SDK's own lazy iterator already agrees: ``_scim_records`` reads
    ``body.get("Resources", [])``, so the same empty search succeeded through
    ``.list()`` and failed through ``.list_page()``.
    """

    _EMPTY: ClassVar[dict[str, object]] = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": 0,
        "startIndex": 1,
        "itemsPerPage": 0,
    }

    @respx.mock
    def test_users_list_page_returns_an_empty_page(self, client: NetskopeClient) -> None:
        respx.get(_USERS_URL).mock(return_value=httpx.Response(200, json=self._EMPTY))
        page = client.scim.users.list_page()
        assert page.items == []
        assert page.total == 0

    @respx.mock
    def test_groups_list_page_returns_an_empty_page(self, client: NetskopeClient) -> None:
        respx.get(_GROUPS_URL).mock(return_value=httpx.Response(200, json=self._EMPTY))
        page = client.scim.groups.list_page()
        assert page.items == []

    @respx.mock
    async def test_async_users_list_page_returns_an_empty_page(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        respx.get(_USERS_URL).mock(return_value=httpx.Response(200, json=self._EMPTY))
        page = await aclient.scim.users.list_page()
        assert page.items == []

    @respx.mock
    def test_a_nonzero_total_without_records_is_still_refused(self, client: NetskopeClient) -> None:
        """RFC 7644 requires Resources once totalResults is non-zero."""
        respx.get(_USERS_URL).mock(
            return_value=httpx.Response(200, json={**self._EMPTY, "totalResults": 3})
        )
        with pytest.raises((ResponseValidationError, PaginationError)):
            client.scim.users.list_page()
