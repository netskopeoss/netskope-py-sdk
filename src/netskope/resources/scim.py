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
        print(group.display_name)

    # Group members are excluded unless asked for by name
    group = client.scim.groups.get("grp-1", attributes="members")
    print(f"{group.display_name}: {len(group.members)} members")
"""

from __future__ import annotations

import builtins
import functools
from typing import Any

from netskope._pagination import (
    AsyncScimPaginatedResponse,
    SyncScimPaginatedResponse,
)
from netskope.models.scim import ScimGroup, ScimUser
from netskope.pagination import Page
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import quote_id
from netskope.resources._scim_response import (
    AsyncScimGroupsResponses,
    AsyncScimUsersResponses,
    ScimGroupsResponses,
    ScimUsersResponses,
    patch_result,
    user_patch_operations,
    validate_page_size,
)

_USERS_PATH = "/api/v2/scim/Users"
_GROUPS_PATH = "/api/v2/scim/Groups"


def _attribute_params(attributes: str | None, excluded_attributes: str | None) -> dict[str, str]:
    """Build the ``attributes`` / ``excludedAttributes`` query for a group read."""
    params: dict[str, str] = {}
    if attributes is not None:
        params["attributes"] = attributes
    if excluded_attributes is not None:
        params["excludedAttributes"] = excluded_attributes
    return params


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

    @functools.cached_property
    def with_response(self) -> ScimUsersResponses:
        """Opt into typed SCIM user responses, which percent-encode the id in the path."""
        return ScimUsersResponses(self._transport)

    def list_page(
        self, *, filter_expr: str | None = None, count: int = 100, start_index: int = 1
    ) -> Page[ScimUser]:
        """Fetch one SCIM page. Missing totalResults does not establish completeness."""
        response = self.with_response.list_page(
            filter_expr=filter_expr, count=count, start_index=start_index
        )
        return response.parse()

    def list(
        self,
        *,
        filter_expr: str | None = None,
        page_size: int = 100,
    ) -> SyncScimPaginatedResponse[ScimUser]:
        """List SCIM users.

        Args:
            filter_expr: SCIM filter (e.g. ``'userName eq "alice@example.com"'``).
            page_size: Results per page (1-1000).
        """
        params: dict[str, Any] = {}
        if filter_expr:
            params["filter"] = filter_expr
        return SyncScimPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_USERS_PATH,
            params=params,
            model=ScimUser,
            page_size=validate_page_size(page_size),
            extract=_extract_scim,
        )

    def get(self, user_id: str) -> ScimUser:
        """Get a SCIM user by ID."""
        body = self._get(f"{_USERS_PATH}/{quote_id(user_id)}")
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

    def update(self, user_id: str, fields: dict[str, Any]) -> ScimUser | None:
        """Partial-update a SCIM user (PATCH), one replace operation per field.

        Args:
            user_id: The SCIM user ID.
            fields: Attribute paths to replace, e.g. ``{"active": False}``.

        Returns:
            ``None`` on the documented success, which is ``204`` with an empty
            body (scim-apis.yaml:2265-2266); the decoded user when a tenant
            answers with one anyway.
        """
        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": user_patch_operations(fields),
        }
        response = self._transport.request(
            "PATCH", f"{_USERS_PATH}/{quote_id(user_id)}", json=payload
        )
        return patch_result(response, ScimUser)

    def delete(self, user_id: str) -> None:
        """Delete a SCIM user."""
        self._delete(f"{_USERS_PATH}/{quote_id(user_id)}")


class ScimGroupsResource(SyncResource):
    """Synchronous interface to ``/api/v2/scim/Groups``."""

    @functools.cached_property
    def with_response(self) -> ScimGroupsResponses:
        """Opt into typed SCIM group responses, which percent-encode the id in the path."""
        return ScimGroupsResponses(self._transport)

    def list_page(
        self, *, filter_expr: str | None = None, count: int = 100, start_index: int = 1
    ) -> Page[ScimGroup]:
        """Fetch one SCIM page. Missing totalResults does not establish completeness."""
        response = self.with_response.list_page(
            filter_expr=filter_expr, count=count, start_index=start_index
        )
        return response.parse()

    def list(
        self,
        *,
        filter_expr: str | None = None,
        page_size: int = 100,
    ) -> SyncScimPaginatedResponse[ScimGroup]:
        """List SCIM groups."""
        params: dict[str, Any] = {}
        if filter_expr:
            params["filter"] = filter_expr
        return SyncScimPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_GROUPS_PATH,
            params=params,
            model=ScimGroup,
            page_size=validate_page_size(page_size),
            extract=_extract_scim,
        )

    def get(
        self,
        group_id: str,
        *,
        attributes: str | None = None,
        excluded_attributes: str | None = None,
    ) -> ScimGroup:
        """Get a SCIM group by ID.

        Members are excluded by default; pass ``attributes="members"`` to
        include them (scim-apis.yaml:462, with the two query parameters at
        :464-479).

        Args:
            group_id: The SCIM group ID.
            attributes: Attributes to include, e.g. ``"members"``.
            excluded_attributes: Attributes to leave out of the response.
        """
        body = self._get(
            f"{_GROUPS_PATH}/{quote_id(group_id)}",
            **_attribute_params(attributes, excluded_attributes),
        )
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
        body = self._put(f"{_GROUPS_PATH}/{quote_id(group_id)}", json=payload)
        return ScimGroup.model_validate(body)

    def delete(self, group_id: str) -> None:
        """Delete a SCIM group."""
        self._delete(f"{_GROUPS_PATH}/{quote_id(group_id)}")


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

    @functools.cached_property
    def with_response(self) -> AsyncScimUsersResponses:
        """Opt into typed SCIM user responses, which percent-encode the id in the path."""
        return AsyncScimUsersResponses(self._transport)

    async def list_page(
        self, *, filter_expr: str | None = None, count: int = 100, start_index: int = 1
    ) -> Page[ScimUser]:
        """Fetch one SCIM page. Missing totalResults does not establish completeness."""
        response = await self.with_response.list_page(
            filter_expr=filter_expr, count=count, start_index=start_index
        )
        return response.parse()

    def list(
        self, *, filter_expr: str | None = None, page_size: int = 100
    ) -> AsyncScimPaginatedResponse[ScimUser]:
        """Iterate SCIM users lazily; *page_size* must be between 1 and 1000.

        Args:
            filter_expr: SCIM filter (e.g. ``'userName eq "alice@example.com"'``).
            page_size: Results per page (1-1000).
        """
        params: dict[str, Any] = {}
        if filter_expr:
            params["filter"] = filter_expr
        return AsyncScimPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_USERS_PATH,
            params=params,
            model=ScimUser,
            page_size=validate_page_size(page_size),
            extract=_extract_scim,
        )

    async def get(self, user_id: str) -> ScimUser:
        """Get a SCIM user by ID."""
        body = await self._get(f"{_USERS_PATH}/{quote_id(user_id)}")
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
        """Provision a new SCIM user.  See :meth:`ScimUsersResource.create`."""
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

    async def update(self, user_id: str, fields: dict[str, Any]) -> ScimUser | None:
        """Partial-update a SCIM user (PATCH).  See :meth:`ScimUsersResource.update`."""
        payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": user_patch_operations(fields),
        }
        response = await self._transport.request(
            "PATCH", f"{_USERS_PATH}/{quote_id(user_id)}", json=payload
        )
        return patch_result(response, ScimUser)

    async def delete(self, user_id: str) -> None:
        """Delete a SCIM user."""
        await self._delete(f"{_USERS_PATH}/{quote_id(user_id)}")


class AsyncScimGroupsResource(AsyncResource):
    """Async SCIM Groups."""

    @functools.cached_property
    def with_response(self) -> AsyncScimGroupsResponses:
        """Opt into typed SCIM group responses, which percent-encode the id in the path."""
        return AsyncScimGroupsResponses(self._transport)

    async def list_page(
        self, *, filter_expr: str | None = None, count: int = 100, start_index: int = 1
    ) -> Page[ScimGroup]:
        """Fetch one SCIM page. Missing totalResults does not establish completeness."""
        response = await self.with_response.list_page(
            filter_expr=filter_expr, count=count, start_index=start_index
        )
        return response.parse()

    def list(
        self, *, filter_expr: str | None = None, page_size: int = 100
    ) -> AsyncScimPaginatedResponse[ScimGroup]:
        """Iterate SCIM groups lazily; *page_size* must be between 1 and 1000."""
        params: dict[str, Any] = {}
        if filter_expr:
            params["filter"] = filter_expr
        return AsyncScimPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_GROUPS_PATH,
            params=params,
            model=ScimGroup,
            page_size=validate_page_size(page_size),
            extract=_extract_scim,
        )

    async def get(
        self,
        group_id: str,
        *,
        attributes: str | None = None,
        excluded_attributes: str | None = None,
    ) -> ScimGroup:
        """Get a SCIM group by ID.  See :meth:`ScimGroupsResource.get`."""
        body = await self._get(
            f"{_GROUPS_PATH}/{quote_id(group_id)}",
            **_attribute_params(attributes, excluded_attributes),
        )
        return ScimGroup.model_validate(body)

    async def create(
        self, display_name: str, *, member_ids: builtins.list[str] | None = None
    ) -> ScimGroup:
        """Create a SCIM group.  See :meth:`ScimGroupsResource.create`."""
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
        """Replace a SCIM group (PUT).  See :meth:`ScimGroupsResource.update`."""
        payload: dict[str, Any] = {
            "displayName": display_name,
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
        }
        if member_ids is not None:
            payload["members"] = [{"value": mid} for mid in member_ids]
        body = await self._put(f"{_GROUPS_PATH}/{quote_id(group_id)}", json=payload)
        return ScimGroup.model_validate(body)

    async def delete(self, group_id: str) -> None:
        """Delete a SCIM group."""
        await self._delete(f"{_GROUPS_PATH}/{quote_id(group_id)}")


class AsyncScimResource(AsyncResource):
    """Async top-level SCIM namespace."""

    @functools.cached_property
    def users(self) -> AsyncScimUsersResource:
        """Access the SCIM Users API."""
        return AsyncScimUsersResource(self._transport)

    @functools.cached_property
    def groups(self) -> AsyncScimGroupsResource:
        """Access the SCIM Groups API."""
        return AsyncScimGroupsResource(self._transport)
