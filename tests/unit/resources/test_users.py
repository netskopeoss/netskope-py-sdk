"""Tests for the User Management (read) resource with mocked HTTP."""

from __future__ import annotations

import httpx
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.models.users import UmGroup, UmUser
from netskope.resources.users import AsyncUsersResource, UsersResource
from tests.unit.resources.conftest import sent_json

_BASE = "https://t.goskope.com"
_GET_USERS_URL = f"{_BASE}/api/v2/users/getusers"
_GET_GROUPS_URL = f"{_BASE}/api/v2/users/getgroups"

_USER_RECORD = {
    "id": "alice@example.com",
    "givenName": "Alice",
    "familyName": "Anderson",
    "emails": [{"value": "alice@example.com", "primary": True}],
    "accounts": [
        {
            "scimId": "086dcf00-2d58-43de-a207-a3f66106acac",
            "userName": "alice@example.com",
            "active": True,
            "deleted": False,
            "parentGroups": ["Engineering"],
            "ou": "example.local/OU1",
            "provisioner": "AD",
        }
    ],
}

_GROUP_RECORD = {
    "id": "Engineering",
    "scimId": "82d72d9e-807a-41b9-8b70-c86bfc15abf3",
    "displayName": "Engineering",
    "userCount": 42,
    "provisioner": "AD",
    "deleted": False,
}

_USERS_ENVELOPE = {
    "counts": {"totalResults": 1, "offset": 0, "itemsPerPage": 100},
    "data": [_USER_RECORD],
}

_GROUPS_ENVELOPE = {
    "counts": {"totalResults": 1, "offset": 0, "itemsPerPage": 100},
    "data": [_GROUP_RECORD],
}

_EMPTY_ENVELOPE = {
    "counts": {"totalResults": 0, "offset": 0, "itemsPerPage": 1},
    "data": [],
}


class TestUsersResource:
    """Tests for UsersResource (sync)."""

    @respx.mock
    def test_list_sends_paging_only_body(self, client: NetskopeClient) -> None:
        """list() without a filter must omit the filter key entirely."""
        route = respx.post(_GET_USERS_URL).mock(
            return_value=httpx.Response(200, json=_USERS_ENVELOPE)
        )
        users = UsersResource(client._transport).list()
        assert sent_json(route) == {"query": {"paging": {"offset": 0, "limit": 100}}}
        assert len(users) == 1
        assert isinstance(users[0], UmUser)
        assert users[0].given_name == "Alice"
        assert users[0].accounts[0].parent_groups == ["Engineering"]
        assert users[0].primary_email == "alice@example.com"

    @respx.mock
    def test_list_with_filter_and_paging(self, client: NetskopeClient) -> None:
        route = respx.post(_GET_USERS_URL).mock(
            return_value=httpx.Response(200, json=_USERS_ENVELOPE)
        )
        UsersResource(client._transport).list(
            filter={"accounts.active": {"eq": True}}, limit=50, offset=100
        )
        assert sent_json(route) == {
            "query": {
                "filter": {"accounts.active": {"eq": True}},
                "paging": {"offset": 100, "limit": 50},
            }
        }

    @respx.mock
    def test_list_extracts_users_key_envelope(self, client: NetskopeClient) -> None:
        """The {"users": [...]} envelope variant is tolerated."""
        respx.post(_GET_USERS_URL).mock(
            return_value=httpx.Response(200, json={"users": [_USER_RECORD]})
        )
        users = UsersResource(client._transport).list()
        assert len(users) == 1
        assert users[0].id == "alice@example.com"

    @respx.mock
    def test_get_autodetects_email(self, client: NetskopeClient) -> None:
        """Identifiers containing '@' are looked up via the emails filter."""
        route = respx.post(_GET_USERS_URL).mock(
            return_value=httpx.Response(200, json=_USERS_ENVELOPE)
        )
        user = UsersResource(client._transport).get("alice@example.com")
        assert sent_json(route) == {
            "query": {
                "filter": {"and": [{"emails": {"eq": "alice@example.com"}}]},
                "paging": {"offset": 0, "limit": 1},
            }
        }
        assert user is not None
        assert user.id == "alice@example.com"

    @respx.mock
    def test_get_autodetects_username(self, client: NetskopeClient) -> None:
        """Identifiers without '@' are looked up via the userName filter."""
        route = respx.post(_GET_USERS_URL).mock(
            return_value=httpx.Response(200, json=_USERS_ENVELOPE)
        )
        UsersResource(client._transport).get("alice")
        assert sent_json(route) == {
            "query": {
                "filter": {"and": [{"userName": {"eq": "alice"}}]},
                "paging": {"offset": 0, "limit": 1},
            }
        }

    @respx.mock
    def test_get_by_username_overrides_autodetect(self, client: NetskopeClient) -> None:
        """by='username' forces a userName lookup even for '@' identifiers."""
        route = respx.post(_GET_USERS_URL).mock(
            return_value=httpx.Response(200, json=_USERS_ENVELOPE)
        )
        UsersResource(client._transport).get("alice@example.com", by="username")
        assert sent_json(route)["query"]["filter"] == {
            "and": [{"userName": {"eq": "alice@example.com"}}]
        }

    @respx.mock
    def test_get_by_email_overrides_autodetect(self, client: NetskopeClient) -> None:
        route = respx.post(_GET_USERS_URL).mock(
            return_value=httpx.Response(200, json=_USERS_ENVELOPE)
        )
        UsersResource(client._transport).get("alice", by="email")
        assert sent_json(route)["query"]["filter"] == {"and": [{"emails": {"eq": "alice"}}]}

    @respx.mock
    def test_get_returns_none_on_empty(self, client: NetskopeClient) -> None:
        respx.post(_GET_USERS_URL).mock(return_value=httpx.Response(200, json=_EMPTY_ENVELOPE))
        assert UsersResource(client._transport).get("nobody@example.com") is None


class TestUserGroupsResource:
    """Tests for UsersResource.groups (sync)."""

    @respx.mock
    def test_list_sends_paging_only_body(self, client: NetskopeClient) -> None:
        route = respx.post(_GET_GROUPS_URL).mock(
            return_value=httpx.Response(200, json=_GROUPS_ENVELOPE)
        )
        groups = UsersResource(client._transport).groups.list()
        assert sent_json(route) == {"query": {"paging": {"offset": 0, "limit": 100}}}
        assert len(groups) == 1
        assert isinstance(groups[0], UmGroup)
        assert groups[0].display_name == "Engineering"
        assert groups[0].user_count == 42

    @respx.mock
    def test_list_with_filter(self, client: NetskopeClient) -> None:
        route = respx.post(_GET_GROUPS_URL).mock(
            return_value=httpx.Response(200, json=_GROUPS_ENVELOPE)
        )
        UsersResource(client._transport).groups.list(
            filter={"deleted": {"eq": False}}, limit=10, offset=20
        )
        assert sent_json(route) == {
            "query": {
                "filter": {"deleted": {"eq": False}},
                "paging": {"offset": 20, "limit": 10},
            }
        }

    @respx.mock
    def test_get_uses_bare_display_name_filter(self, client: NetskopeClient) -> None:
        """groups.get() uses a bare displayName filter (not "and"-wrapped)."""
        route = respx.post(_GET_GROUPS_URL).mock(
            return_value=httpx.Response(200, json=_GROUPS_ENVELOPE)
        )
        group = UsersResource(client._transport).groups.get("Engineering")
        assert sent_json(route) == {
            "query": {
                "filter": {"displayName": {"eq": "Engineering"}},
                "paging": {"offset": 0, "limit": 1},
            }
        }
        assert group is not None
        assert group.scim_id == "82d72d9e-807a-41b9-8b70-c86bfc15abf3"

    @respx.mock
    def test_get_returns_none_on_empty(self, client: NetskopeClient) -> None:
        respx.post(_GET_GROUPS_URL).mock(return_value=httpx.Response(200, json=_EMPTY_ENVELOPE))
        assert UsersResource(client._transport).groups.get("Nonexistent") is None

    @respx.mock
    def test_members_sends_parent_groups_filter(self, client: NetskopeClient) -> None:
        """members() queries getusers with an accounts.parentGroups filter."""
        route = respx.post(_GET_USERS_URL).mock(
            return_value=httpx.Response(200, json=_USERS_ENVELOPE)
        )
        members = UsersResource(client._transport).groups.members("Engineering", limit=25)
        assert sent_json(route) == {
            "query": {
                "filter": {"accounts.parentGroups": {"in": ["Engineering"]}},
                "paging": {"offset": 0, "limit": 25},
            }
        }
        assert len(members) == 1
        assert isinstance(members[0], UmUser)


class TestUmUserModel:
    """Tests for UmUser convenience behavior."""

    def test_primary_email_prefers_primary_dict(self) -> None:
        user = UmUser.model_validate(
            {
                "emails": [
                    {"value": "old@example.com", "primary": False},
                    {"value": "new@example.com", "primary": True},
                ]
            }
        )
        assert user.primary_email == "new@example.com"

    def test_primary_email_falls_back_to_first(self) -> None:
        user = UmUser.model_validate({"emails": [{"value": "only@example.com"}]})
        assert user.primary_email == "only@example.com"

    def test_primary_email_handles_string_entries(self) -> None:
        """The gateway spec returns emails as plain strings."""
        user = UmUser.model_validate({"emails": ["plain@example.com"]})
        assert user.primary_email == "plain@example.com"

    def test_primary_email_none_when_empty(self) -> None:
        assert UmUser.model_validate({}).primary_email is None


class TestAsyncUsersResource:
    """Tests for AsyncUsersResource."""

    @respx.mock
    async def test_list_sends_paging_only_body(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_GET_USERS_URL).mock(
            return_value=httpx.Response(200, json=_USERS_ENVELOPE)
        )
        users = await AsyncUsersResource(aclient._transport).list()
        assert sent_json(route) == {"query": {"paging": {"offset": 0, "limit": 100}}}
        assert len(users) == 1
        assert isinstance(users[0], UmUser)

    @respx.mock
    async def test_list_with_filter(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_GET_USERS_URL).mock(
            return_value=httpx.Response(200, json={"users": [_USER_RECORD]})
        )
        users = await AsyncUsersResource(aclient._transport).list(
            filter={"accounts.active": {"eq": True}}, limit=5, offset=10
        )
        assert sent_json(route) == {
            "query": {
                "filter": {"accounts.active": {"eq": True}},
                "paging": {"offset": 10, "limit": 5},
            }
        }
        assert len(users) == 1

    @respx.mock
    async def test_get_autodetects_email(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_GET_USERS_URL).mock(
            return_value=httpx.Response(200, json=_USERS_ENVELOPE)
        )
        user = await AsyncUsersResource(aclient._transport).get("alice@example.com")
        assert sent_json(route) == {
            "query": {
                "filter": {"and": [{"emails": {"eq": "alice@example.com"}}]},
                "paging": {"offset": 0, "limit": 1},
            }
        }
        assert user is not None

    @respx.mock
    async def test_get_autodetects_username(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_GET_USERS_URL).mock(
            return_value=httpx.Response(200, json=_USERS_ENVELOPE)
        )
        await AsyncUsersResource(aclient._transport).get("alice")
        assert sent_json(route)["query"]["filter"] == {"and": [{"userName": {"eq": "alice"}}]}

    @respx.mock
    async def test_get_returns_none_on_empty(self, aclient: AsyncNetskopeClient) -> None:
        respx.post(_GET_USERS_URL).mock(return_value=httpx.Response(200, json=_EMPTY_ENVELOPE))
        assert await AsyncUsersResource(aclient._transport).get("nobody@example.com") is None

    @respx.mock
    async def test_groups_list_and_get(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_GET_GROUPS_URL).mock(
            return_value=httpx.Response(200, json=_GROUPS_ENVELOPE)
        )
        resource = AsyncUsersResource(aclient._transport)
        groups = await resource.groups.list(limit=10)
        assert sent_json(route) == {"query": {"paging": {"offset": 0, "limit": 10}}}
        assert len(groups) == 1
        assert isinstance(groups[0], UmGroup)

        group = await resource.groups.get("Engineering")
        assert sent_json(route) == {
            "query": {
                "filter": {"displayName": {"eq": "Engineering"}},
                "paging": {"offset": 0, "limit": 1},
            }
        }
        assert group is not None
        assert group.display_name == "Engineering"

    @respx.mock
    async def test_groups_members(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_GET_USERS_URL).mock(
            return_value=httpx.Response(200, json=_USERS_ENVELOPE)
        )
        members = await AsyncUsersResource(aclient._transport).groups.members("Engineering")
        assert sent_json(route) == {
            "query": {
                "filter": {"accounts.parentGroups": {"in": ["Engineering"]}},
                "paging": {"offset": 0, "limit": 100},
            }
        }
        assert len(members) == 1
