"""User Management resource — query users and groups (read-only).

The User Management API (``/api/v2/users/``) is the modern read API for
users and groups.  It returns richer data than SCIM — group membership
(``parentGroups``), user counts, and provisioner info — via POST-with-body
query endpoints supporting structured filters (operators: ``eq``, ``ne``,
``in``, ``nin``, ``sw``, ``ew``, ``co``, ``lt``, ``gt``, ``le``, ``ge``,
``pr``, combinable with ``and``/``or``).

For provisioning CRUD (create/update/delete users and groups), use the SCIM
namespace (``client.scim``) instead — see
:class:`netskope.resources.scim.ScimResource`.

Example::

    users = UsersResource(client._transport)

    # List users
    for user in users.list(limit=50):
        print(f"{user.id}: {user.primary_email}")

    # Look up a single user
    user = users.get("alice@example.com")

    # Groups and membership
    for group in users.groups.list():
        print(f"{group.display_name}: {group.user_count} users")
    members = users.groups.members("Engineering")
"""

from __future__ import annotations

import builtins
import functools
from typing import Any, Literal

from netskope.models.users import UmGroup, UmUser
from netskope.resources._base import AsyncResource, SyncResource

_GET_USERS_PATH = "/api/v2/users/getusers"
_GET_GROUPS_PATH = "/api/v2/users/getgroups"


def _build_query_body(
    filter: dict[str, Any] | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    """Build the POST body for User Management query endpoints.

    Returns ``{"query": {"filter": ..., "paging": {"offset": n, "limit": n}}}``
    with ``filter`` omitted when ``None``.
    """
    query: dict[str, Any] = {"paging": {"offset": offset, "limit": limit}}
    if filter is not None:
        query["filter"] = filter
    return {"query": query}


def _user_lookup_filter(
    identifier: str,
    by: Literal["email", "username"] | None,
) -> dict[str, Any]:
    """Build the filter for a single-user lookup.

    When *by* is ``None``, identifiers containing ``"@"`` are treated as
    emails and everything else as usernames.
    """
    if by == "email" or (by is None and "@" in identifier):
        return {"and": [{"emails": {"eq": identifier}}]}
    return {"and": [{"userName": {"eq": identifier}}]}


def _extract_records(body: dict[str, Any]) -> builtins.list[dict[str, Any]]:
    """Locate the record list in a User Management response.

    The real envelope is ``{"counts": ..., "data": [...]}``; ``users`` and
    ``groups`` keys are tolerated for compatibility.
    """
    for key in ("data", "users", "groups"):
        value = body.get(key)
        if isinstance(value, list):
            return value
    return []


class UserGroupsResource(SyncResource):
    """Synchronous interface to ``/api/v2/users/getgroups`` (read-only).

    For group provisioning CRUD, use ``client.scim.groups`` — see
    :class:`netskope.resources.scim.ScimGroupsResource`.
    """

    def list(
        self,
        *,
        filter: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> builtins.list[UmGroup]:
        """List groups with rich metadata (user counts, provisioner).

        Args:
            filter: Structured filter dict (operators: eq, in, sw, co).
                Filterable fields include ``id``, ``scimId``, ``deleted``,
                ``collectionId``, ``parentGroups``, ``idps``.
                Example: ``{"deleted": {"eq": False}}``.
            limit: Maximum records to return (max 1000).
            offset: 0-based pagination offset.
        """
        body = self._post(_GET_GROUPS_PATH, json=_build_query_body(filter, limit, offset))
        return [UmGroup.model_validate(item) for item in _extract_records(body)]

    def get(self, name: str) -> UmGroup | None:
        """Look up a single group by display name.

        Args:
            name: The group display name (e.g. ``"Engineering"``).

        Returns:
            The matching :class:`~netskope.models.users.UmGroup`, or
            ``None`` when no group matches.
        """
        filter: dict[str, Any] = {"displayName": {"eq": name}}
        body = self._post(_GET_GROUPS_PATH, json=_build_query_body(filter, 1, 0))
        records = _extract_records(body)
        return UmGroup.model_validate(records[0]) if records else None

    def members(
        self,
        group_name: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> builtins.list[UmUser]:
        """List all users that are members of a group.

        Queries ``getusers`` with an ``accounts.parentGroups`` filter.

        Args:
            group_name: Display name of the group.
            limit: Maximum records to return (max 1000).
            offset: 0-based pagination offset.
        """
        filter: dict[str, Any] = {"accounts.parentGroups": {"in": [group_name]}}
        body = self._post(_GET_USERS_PATH, json=_build_query_body(filter, limit, offset))
        return [UmUser.model_validate(item) for item in _extract_records(body)]


class UsersResource(SyncResource):
    """Synchronous interface to the User Management query API (read-only).

    Returns richer data than SCIM, including group membership per account.
    For user provisioning CRUD, use ``client.scim.users`` — see
    :class:`netskope.resources.scim.ScimUsersResource`.
    """

    def list(
        self,
        *,
        filter: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> builtins.list[UmUser]:
        """List users with group membership data.

        Args:
            filter: Structured filter dict (operators: eq, in, sw, co).
                Filterable fields include ``userName``, ``emails``,
                ``accounts.deleted``, ``accounts.active``,
                ``accounts.parentGroups``, ``accounts.ou``.
                Example: ``{"accounts.active": {"eq": True}}``.
            limit: Maximum records to return (max 1000).
            offset: 0-based pagination offset.
        """
        body = self._post(_GET_USERS_PATH, json=_build_query_body(filter, limit, offset))
        return [UmUser.model_validate(item) for item in _extract_records(body)]

    def get(
        self,
        identifier: str,
        *,
        by: Literal["email", "username"] | None = None,
    ) -> UmUser | None:
        """Look up a single user by email or username.

        Args:
            identifier: Email address or username.  When *by* is ``None``,
                values containing ``"@"`` are treated as emails; otherwise
                as usernames.
            by: Force the lookup field (``"email"`` or ``"username"``).

        Returns:
            The matching :class:`~netskope.models.users.UmUser`, or
            ``None`` when no user matches.
        """
        filter = _user_lookup_filter(identifier, by)
        body = self._post(_GET_USERS_PATH, json=_build_query_body(filter, 1, 0))
        records = _extract_records(body)
        return UmUser.model_validate(records[0]) if records else None

    @functools.cached_property
    def groups(self) -> UserGroupsResource:
        """Access the group query API (``users.groups``)."""
        return UserGroupsResource(self._transport)


# --- Async counterparts ---


class AsyncUserGroupsResource(AsyncResource):
    """Async interface to ``/api/v2/users/getgroups`` (read-only).

    For group provisioning CRUD, use ``client.scim.groups``.
    """

    async def list(
        self,
        *,
        filter: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> builtins.list[UmGroup]:
        """List groups.  See :meth:`UserGroupsResource.list`."""
        body = await self._post(_GET_GROUPS_PATH, json=_build_query_body(filter, limit, offset))
        return [UmGroup.model_validate(item) for item in _extract_records(body)]

    async def get(self, name: str) -> UmGroup | None:
        """Look up a group by display name.  See :meth:`UserGroupsResource.get`."""
        filter: dict[str, Any] = {"displayName": {"eq": name}}
        body = await self._post(_GET_GROUPS_PATH, json=_build_query_body(filter, 1, 0))
        records = _extract_records(body)
        return UmGroup.model_validate(records[0]) if records else None

    async def members(
        self,
        group_name: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> builtins.list[UmUser]:
        """List group members.  See :meth:`UserGroupsResource.members`."""
        filter: dict[str, Any] = {"accounts.parentGroups": {"in": [group_name]}}
        body = await self._post(_GET_USERS_PATH, json=_build_query_body(filter, limit, offset))
        return [UmUser.model_validate(item) for item in _extract_records(body)]


class AsyncUsersResource(AsyncResource):
    """Async interface to the User Management query API (read-only).

    For user provisioning CRUD, use ``client.scim.users``.
    """

    async def list(
        self,
        *,
        filter: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> builtins.list[UmUser]:
        """List users.  See :meth:`UsersResource.list`."""
        body = await self._post(_GET_USERS_PATH, json=_build_query_body(filter, limit, offset))
        return [UmUser.model_validate(item) for item in _extract_records(body)]

    async def get(
        self,
        identifier: str,
        *,
        by: Literal["email", "username"] | None = None,
    ) -> UmUser | None:
        """Look up a single user.  See :meth:`UsersResource.get`."""
        filter = _user_lookup_filter(identifier, by)
        body = await self._post(_GET_USERS_PATH, json=_build_query_body(filter, 1, 0))
        records = _extract_records(body)
        return UmUser.model_validate(records[0]) if records else None

    @functools.cached_property
    def groups(self) -> AsyncUserGroupsResource:
        """Access the group query API (``users.groups``)."""
        return AsyncUserGroupsResource(self._transport)
