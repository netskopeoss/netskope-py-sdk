"""SCIM resource — user and group provisioning.

Example::

    # List users
    for user in client.scim.users.list():
        print(f"{user.user_name} active={user.active}")

    # Create a user
    user = client.scim.users.create(
        user_name="alice@example.com",
        email="alice@example.com",
    )

    # List groups
    for group in client.scim.groups.list():
        print(f"{group.display_name}: {len(group.members)} members")
"""

from __future__ import annotations

import builtins
import functools
import re
from typing import Any

from netskope._pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.models.scim import ScimGroup, ScimUser
from netskope.resources._base import AsyncResource, SyncResource

_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


def _validate_id(value: str, name: str) -> None:
    if not _SAFE_ID_RE.match(value):
        from netskope.exceptions import ValidationError

        raise ValidationError(f"Invalid {name} format: {value!r}")

_USERS_PATH = "/api/v2/scim/Users"
_GROUPS_PATH = "/api/v2/scim/Groups"


def _extract_scim(body: dict[str, Any]) -> list[dict[str, Any]]:
    """SCIM responses use ``Resources`` as the data key."""
    resources = body.get("Resources", [])
    if isinstance(resources, list):
        return resources
    data = body.get("data", [])
    if isinstance(data, list):
        return data
    return []


class ScimUsersResource(SyncResource):
    """Synchronous interface to ``/api/v2/scim/Users``."""

    def list(
        self,
        *,
        filter_expr: str | None = None,
        page_size: int = 100,
    ) -> SyncPaginatedResponse[ScimUser]:
        """List SCIM users.

        Args:
            filter_expr: SCIM filter (e.g. ``'userName eq "alice@example.com"'``).
            page_size: Results per page.
        """
        params: dict[str, Any] = {}
        if filter_expr:
            params["filter"] = filter_expr
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_USERS_PATH,
            params=params,
            model=ScimUser,
            page_size=page_size,
            extract=_extract_scim,
        )

    def get(self, user_id: str) -> ScimUser:
        """Get a SCIM user by ID."""
        _validate_id(user_id, "user_id")
        body = self._get(f"{_USERS_PATH}/{user_id}")
        return ScimUser.model_validate(body)

    def create(
        self,
        user_name: str,
        email: str,
        *,
        active: bool = True,
        display_name: str | None = None,
        given_name: str | None = None,
        family_name: str | None = None,
    ) -> ScimUser:
        """Provision a new SCIM user.

        Args:
            user_name: The username (typically an email).
            email: Primary email address.
            active: Whether the account is active.
            display_name: Display name.
            given_name: First name.
            family_name: Last name.
        """
        payload: dict[str, Any] = {
            "userName": user_name,
            "active": active,
            "emails": [{"value": email, "primary": True}],
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        }
        if display_name:
            payload["displayName"] = display_name
        if given_name or family_name:
            payload["name"] = {}
            if given_name:
                payload["name"]["givenName"] = given_name
            if family_name:
                payload["name"]["familyName"] = family_name
        body = self._post(_USERS_PATH, json=payload)
        return ScimUser.model_validate(body)

    def update(self, user_id: str, fields: dict[str, Any]) -> ScimUser:
        """Partial-update a SCIM user (PATCH).

        Args:
            user_id: The SCIM user ID.
            fields: Key-value pairs to update.
        """
        operations = [{"op": "replace", "value": fields}]
        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": operations,
        }
        _validate_id(user_id, "user_id")
        body = self._patch(f"{_USERS_PATH}/{user_id}", json=payload)
        return ScimUser.model_validate(body)

    def delete(self, user_id: str) -> None:
        """Delete a SCIM user."""
        _validate_id(user_id, "user_id")
        self._delete(f"{_USERS_PATH}/{user_id}")


class ScimGroupsResource(SyncResource):
    """Synchronous interface to ``/api/v2/scim/Groups``."""

    def list(
        self,
        *,
        filter_expr: str | None = None,
        page_size: int = 100,
    ) -> SyncPaginatedResponse[ScimGroup]:
        """List SCIM groups."""
        params: dict[str, Any] = {}
        if filter_expr:
            params["filter"] = filter_expr
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_GROUPS_PATH,
            params=params,
            model=ScimGroup,
            page_size=page_size,
            extract=_extract_scim,
        )

    def get(self, group_id: str) -> ScimGroup:
        """Get a SCIM group by ID."""
        _validate_id(group_id, "group_id")
        body = self._get(f"{_GROUPS_PATH}/{group_id}")
        return ScimGroup.model_validate(body)

    def create(
        self,
        display_name: str,
        *,
        member_ids: builtins.list[str] | None = None,
    ) -> ScimGroup:
        """Create a SCIM group.

        Args:
            display_name: Group display name.
            member_ids: Optional list of user IDs to add as members.
        """
        payload: dict[str, Any] = {
            "displayName": display_name,
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
        }
        if member_ids:
            payload["members"] = [{"value": mid} for mid in member_ids]
        body = self._post(_GROUPS_PATH, json=payload)
        return ScimGroup.model_validate(body)

    def update(
        self,
        group_id: str,
        *,
        display_name: str,
        member_ids: builtins.list[str] | None = None,
    ) -> ScimGroup:
        """Replace a SCIM group (PUT).

        Args:
            group_id: The SCIM group ID.
            display_name: Group display name.
            member_ids: Optional list of user IDs for group members.
        """
        payload: dict[str, Any] = {
            "displayName": display_name,
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
        }
        if member_ids is not None:
            payload["members"] = [{"value": mid} for mid in member_ids]
        _validate_id(group_id, "group_id")
        body = self._put(f"{_GROUPS_PATH}/{group_id}", json=payload)
        return ScimGroup.model_validate(body)

    def delete(self, group_id: str) -> None:
        """Delete a SCIM group."""
        _validate_id(group_id, "group_id")
        self._delete(f"{_GROUPS_PATH}/{group_id}")


class ScimResource(SyncResource):
    """Top-level SCIM namespace: ``client.scim.users`` / ``client.scim.groups``."""

    @functools.cached_property
    def users(self) -> ScimUsersResource:
        """Access the SCIM Users API."""
        return ScimUsersResource(self._transport)

    @functools.cached_property
    def groups(self) -> ScimGroupsResource:
        """Access the SCIM Groups API."""
        return ScimGroupsResource(self._transport)


# --- Async counterparts ---


class AsyncScimUsersResource(AsyncResource):
    """Async SCIM Users."""

    def list(
        self, *, filter_expr: str | None = None, page_size: int = 100
    ) -> AsyncPaginatedResponse[ScimUser]:
        params: dict[str, Any] = {}
        if filter_expr:
            params["filter"] = filter_expr
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_USERS_PATH,
            params=params,
            model=ScimUser,
            page_size=page_size,
            extract=_extract_scim,
        )

    async def get(self, user_id: str) -> ScimUser:
        _validate_id(user_id, "user_id")
        body = await self._get(f"{_USERS_PATH}/{user_id}")
        return ScimUser.model_validate(body)

    async def create(
        self,
        user_name: str,
        email: str,
        *,
        active: bool = True,
        display_name: str | None = None,
        given_name: str | None = None,
        family_name: str | None = None,
    ) -> ScimUser:
        payload: dict[str, Any] = {
            "userName": user_name,
            "active": active,
            "emails": [{"value": email, "primary": True}],
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        }
        if display_name:
            payload["displayName"] = display_name
        if given_name or family_name:
            payload["name"] = {}
            if given_name:
                payload["name"]["givenName"] = given_name
            if family_name:
                payload["name"]["familyName"] = family_name
        body = await self._post(_USERS_PATH, json=payload)
        return ScimUser.model_validate(body)

    async def update(self, user_id: str, fields: dict[str, Any]) -> ScimUser:
        _validate_id(user_id, "user_id")
        operations = [{"op": "replace", "value": fields}]
        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": operations,
        }
        body = await self._patch(f"{_USERS_PATH}/{user_id}", json=payload)
        return ScimUser.model_validate(body)

    async def delete(self, user_id: str) -> None:
        _validate_id(user_id, "user_id")
        await self._delete(f"{_USERS_PATH}/{user_id}")


class AsyncScimGroupsResource(AsyncResource):
    """Async SCIM Groups."""

    def list(
        self, *, filter_expr: str | None = None, page_size: int = 100
    ) -> AsyncPaginatedResponse[ScimGroup]:
        params: dict[str, Any] = {}
        if filter_expr:
            params["filter"] = filter_expr
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_GROUPS_PATH,
            params=params,
            model=ScimGroup,
            page_size=page_size,
            extract=_extract_scim,
        )

    async def get(self, group_id: str) -> ScimGroup:
        _validate_id(group_id, "group_id")
        body = await self._get(f"{_GROUPS_PATH}/{group_id}")
        return ScimGroup.model_validate(body)

    async def create(
        self, display_name: str, *, member_ids: builtins.list[str] | None = None
    ) -> ScimGroup:
        payload: dict[str, Any] = {
            "displayName": display_name,
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
        }
        if member_ids:
            payload["members"] = [{"value": mid} for mid in member_ids]
        body = await self._post(_GROUPS_PATH, json=payload)
        return ScimGroup.model_validate(body)

    async def update(
        self,
        group_id: str,
        *,
        display_name: str,
        member_ids: builtins.list[str] | None = None,
    ) -> ScimGroup:
        _validate_id(group_id, "group_id")
        payload: dict[str, Any] = {
            "displayName": display_name,
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
        }
        if member_ids is not None:
            payload["members"] = [{"value": mid} for mid in member_ids]
        body = await self._put(f"{_GROUPS_PATH}/{group_id}", json=payload)
        return ScimGroup.model_validate(body)

    async def delete(self, group_id: str) -> None:
        _validate_id(group_id, "group_id")
        await self._delete(f"{_GROUPS_PATH}/{group_id}")


class AsyncScimResource(AsyncResource):
    """Async top-level SCIM namespace."""

    @functools.cached_property
    def users(self) -> AsyncScimUsersResource:
        return AsyncScimUsersResource(self._transport)

    @functools.cached_property
    def groups(self) -> AsyncScimGroupsResource:
        return AsyncScimGroupsResource(self._transport)
