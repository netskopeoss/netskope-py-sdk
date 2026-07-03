"""RBAC resource — manage roles and list admin users.

Example::

    # List all roles
    for role in client.rbac.roles.list():
        print(f"{role.id}: {role.name}")

    # Create a custom role granting read access to an API group
    role = client.rbac.roles.create(
        "SOC-Analyst-ReadOnly",
        description="Read-only role for SOC analysts",
        api_groups=[{"apiGroupId": 1, "permission": "r"}],
    )

    # List admin users (SCIM)
    for admin in client.rbac.admins.list():
        print(f"{admin.user_name} active={admin.active}")
"""

from __future__ import annotations

import builtins
import functools
from typing import Any

from netskope._pagination import AsyncScimPaginatedResponse, SyncScimPaginatedResponse
from netskope.exceptions import ValidationError
from netskope.models.rbac import RbacRole
from netskope.models.scim import ScimUser
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import extract_item, extract_list, validate_id

_ROLES_PATH = "/api/v2/rbac/roles"

# Admin users are served by ms-platform via a SCIM endpoint — there is no
# /api/v2/rbac/admins route.
_ADMINS_PATH = "/api/v2/platform/administration/scim/Users"

_VALID_ROLE_TYPES = ("custom", "predefined")
_VALID_ROLE_SCOPES = ("limited", "no_limit")

# The list envelope is {"version": ..., "count": ..., "roles": [...]}.
_ROLES_LIST_KEY = "roles"


def _build_roles_list_params(
    role_type: str | None,
    scope: str | None,
    search: str | None,
    limit: int | None,
    offset: int | None,
) -> dict[str, Any]:
    if role_type is not None and role_type not in _VALID_ROLE_TYPES:
        raise ValidationError(
            f"Invalid role_type {role_type!r}. Must be one of: {', '.join(_VALID_ROLE_TYPES)}"
        )
    if scope is not None and scope not in _VALID_ROLE_SCOPES:
        raise ValidationError(
            f"Invalid scope {scope!r}. Must be one of: {', '.join(_VALID_ROLE_SCOPES)}"
        )
    params: dict[str, Any] = {}
    if role_type is not None:
        params["type"] = role_type
    if scope is not None:
        params["scope"] = scope
    if search:
        params["search"] = search
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    return params


def _build_role_payload(
    name: str | None,
    description: str | None,
    api_groups: builtins.list[dict[str, Any]] | None,
    scope: dict[str, Any] | None,
    ip_allow_list: dict[str, Any] | None,
    labels: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a role create/update body using the gateway field names.

    The API uses ``roleName`` / ``roleDescription`` / ``apiGroups`` — only
    fields that were actually provided are included, so this serves both the
    full-body POST and the partial-body PATCH.
    """
    payload: dict[str, Any] = {}
    if name is not None:
        payload["roleName"] = name
    if description is not None:
        payload["roleDescription"] = description
    if api_groups is not None:
        payload["apiGroups"] = api_groups
    if scope is not None:
        payload["scope"] = scope
    if ip_allow_list is not None:
        payload["ipAllowList"] = ip_allow_list
    if labels is not None:
        payload["labels"] = labels
    return payload


def _build_admins_params(filter_expr: str | None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if filter_expr:
        params["filter"] = filter_expr
    return params


class RbacRolesResource(SyncResource):
    """Synchronous interface to ``/api/v2/rbac/roles``."""

    def list(
        self,
        *,
        role_type: str | None = None,
        scope: str | None = None,
        search: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> builtins.list[RbacRole]:
        """List RBAC roles.

        Args:
            role_type: Filter by role type — ``"custom"`` or ``"predefined"``.
            scope: Filter by scope — ``"limited"`` or ``"no_limit"``.
            search: Substring to search for in role names.
            limit: Maximum number of roles to return (1-1000).
            offset: Offset of the first role to return.

        Raises:
            netskope.exceptions.ValidationError: If *role_type* or *scope*
                is not a supported value.
        """
        params = _build_roles_list_params(role_type, scope, search, limit, offset)
        body = self._get(_ROLES_PATH, **params)
        return [RbacRole.model_validate(item) for item in extract_list(body, _ROLES_LIST_KEY)]

    def get(self, role_id: int) -> RbacRole:
        """Get an RBAC role by ID.

        Args:
            role_id: The numeric role identifier.
        """
        rid = validate_id(role_id, "role_id")
        body = self._get(f"{_ROLES_PATH}/{rid}")
        return RbacRole.model_validate(extract_item(body))

    def create(
        self,
        name: str,
        *,
        description: str = "",
        api_groups: builtins.list[dict[str, Any]] | None = None,
        scope: dict[str, Any] | None = None,
        ip_allow_list: dict[str, Any] | None = None,
        labels: dict[str, Any] | None = None,
    ) -> RbacRole:
        """Create a new custom RBAC role.

        The API requires ``roleName``, ``roleDescription``, and ``apiGroups``
        on create; the create response contains only the new ``roleId``, so
        the full role is fetched afterwards and returned.

        Args:
            name: Role name (must be unique within the tenant).
            description: Role description.
            api_groups: Per-API-group permissions, e.g.
                ``[{"apiGroupId": 1, "permission": "r"}]``.  Valid permission
                levels are ``none``, ``r``, ``rw``, and ``rwa``.  Defaults to
                an empty list (a role with no API-group permissions).
            scope: Scope restriction mapping, e.g.
                ``{"email": {"in": ["a@example.com"]}}``.
            ip_allow_list: IP allow-list object, e.g.
                ``{"enableIpAllowList": True, "ipList": ["1.2.3.4"]}``.
            labels: Label assignment object, e.g.
                ``{"assignedLabels": [{"id": "...", "permission": "r"}]}``.
        """
        payload = _build_role_payload(
            name,
            description,
            api_groups if api_groups is not None else [],
            scope,
            ip_allow_list,
            labels,
        )
        body = self._post(_ROLES_PATH, json=payload)
        role_id = body.get("roleId")
        if role_id is None:
            return RbacRole.model_validate(extract_item(body))
        return self.get(int(role_id))

    def update(
        self,
        role_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        api_groups: builtins.list[dict[str, Any]] | None = None,
        scope: dict[str, Any] | None = None,
        ip_allow_list: dict[str, Any] | None = None,
        labels: dict[str, Any] | None = None,
    ) -> RbacRole:
        """Partially update a custom RBAC role (PATCH — only set fields are sent).

        The update response contains only the ``roleId``, so the full role is
        fetched afterwards and returned.

        Args:
            role_id: The numeric role identifier.
            name: New role name.
            description: New role description.
            api_groups: Replacement per-API-group permissions (fully replaces
                the entries it names; see :meth:`create` for the shape).
            scope: New scope restriction mapping.
            ip_allow_list: New IP allow-list object.
            labels: New label assignment object.

        Raises:
            netskope.exceptions.ValidationError: If no fields are provided.
        """
        rid = validate_id(role_id, "role_id")
        payload = _build_role_payload(name, description, api_groups, scope, ip_allow_list, labels)
        if not payload:
            raise ValidationError("update() requires at least one field to change")
        self._patch(f"{_ROLES_PATH}/{rid}", json=payload)
        return self.get(role_id)

    def delete(self, role_id: int) -> None:
        """Delete a custom RBAC role.  Built-in roles cannot be deleted.

        Args:
            role_id: The numeric role identifier.
        """
        rid = validate_id(role_id, "role_id")
        self._delete(f"{_ROLES_PATH}/{rid}")


class RbacAdminsResource(SyncResource):
    """Synchronous interface to admin users (SCIM, served by ms-platform)."""

    def list(
        self,
        *,
        filter_expr: str | None = None,
        page_size: int = 100,
    ) -> SyncScimPaginatedResponse[ScimUser]:
        """List admin users.

        Args:
            filter_expr: SCIM filter, e.g.
                ``'urn:ietf:params:scim:schemas:netskope:2.0:user'``
                ``'[recordType eq "SERVICE_ACCOUNT"]'``.
            page_size: Results per page (SCIM ``count``).
        """
        return SyncScimPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_ADMINS_PATH,
            params=_build_admins_params(filter_expr),
            model=ScimUser,
            page_size=page_size,
        )


class RbacResource(SyncResource):
    """Top-level RBAC namespace: ``client.rbac.roles`` / ``client.rbac.admins``."""

    @functools.cached_property
    def roles(self) -> RbacRolesResource:
        """Access the RBAC Roles API."""
        return RbacRolesResource(self._transport)

    @functools.cached_property
    def admins(self) -> RbacAdminsResource:
        """Access the admin users (SCIM) API."""
        return RbacAdminsResource(self._transport)


# --- Async counterparts ---


class AsyncRbacRolesResource(AsyncResource):
    """Asynchronous interface to ``/api/v2/rbac/roles``."""

    async def list(
        self,
        *,
        role_type: str | None = None,
        scope: str | None = None,
        search: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> builtins.list[RbacRole]:
        """List RBAC roles.  See :meth:`RbacRolesResource.list`."""
        params = _build_roles_list_params(role_type, scope, search, limit, offset)
        body = await self._get(_ROLES_PATH, **params)
        return [RbacRole.model_validate(item) for item in extract_list(body, _ROLES_LIST_KEY)]

    async def get(self, role_id: int) -> RbacRole:
        """Get an RBAC role by ID."""
        rid = validate_id(role_id, "role_id")
        body = await self._get(f"{_ROLES_PATH}/{rid}")
        return RbacRole.model_validate(extract_item(body))

    async def create(
        self,
        name: str,
        *,
        description: str = "",
        api_groups: builtins.list[dict[str, Any]] | None = None,
        scope: dict[str, Any] | None = None,
        ip_allow_list: dict[str, Any] | None = None,
        labels: dict[str, Any] | None = None,
    ) -> RbacRole:
        """Create a new custom RBAC role.  See :meth:`RbacRolesResource.create`."""
        payload = _build_role_payload(
            name,
            description,
            api_groups if api_groups is not None else [],
            scope,
            ip_allow_list,
            labels,
        )
        body = await self._post(_ROLES_PATH, json=payload)
        role_id = body.get("roleId")
        if role_id is None:
            return RbacRole.model_validate(extract_item(body))
        return await self.get(int(role_id))

    async def update(
        self,
        role_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        api_groups: builtins.list[dict[str, Any]] | None = None,
        scope: dict[str, Any] | None = None,
        ip_allow_list: dict[str, Any] | None = None,
        labels: dict[str, Any] | None = None,
    ) -> RbacRole:
        """Partially update a custom RBAC role.  See :meth:`RbacRolesResource.update`."""
        rid = validate_id(role_id, "role_id")
        payload = _build_role_payload(name, description, api_groups, scope, ip_allow_list, labels)
        if not payload:
            raise ValidationError("update() requires at least one field to change")
        await self._patch(f"{_ROLES_PATH}/{rid}", json=payload)
        return await self.get(role_id)

    async def delete(self, role_id: int) -> None:
        """Delete a custom RBAC role."""
        rid = validate_id(role_id, "role_id")
        await self._delete(f"{_ROLES_PATH}/{rid}")


class AsyncRbacAdminsResource(AsyncResource):
    """Async admin users (SCIM)."""

    def list(
        self,
        *,
        filter_expr: str | None = None,
        page_size: int = 100,
    ) -> AsyncScimPaginatedResponse[ScimUser]:
        """List admin users.  See :meth:`RbacAdminsResource.list`."""
        return AsyncScimPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_ADMINS_PATH,
            params=_build_admins_params(filter_expr),
            model=ScimUser,
            page_size=page_size,
        )


class AsyncRbacResource(AsyncResource):
    """Async top-level RBAC namespace."""

    @functools.cached_property
    def roles(self) -> AsyncRbacRolesResource:
        """Access the RBAC Roles API."""
        return AsyncRbacRolesResource(self._transport)

    @functools.cached_property
    def admins(self) -> AsyncRbacAdminsResource:
        """Access the admin users (SCIM) API."""
        return AsyncRbacAdminsResource(self._transport)
