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

    # List admin users (SCIM, served by ms-platform)
    for admin in client.rbac.admins.list():
        print(f"{admin.user_name} {admin.record_type} role={admin.role}")
"""

from __future__ import annotations

import builtins
import functools
from typing import Any

from netskope.core.ids import extract_item
from netskope.core.pagination import (
    AsyncScimPaginatedResponse,
    Page,
    SyncScimPaginatedResponse,
)
from netskope.core.resource import AsyncResource, SyncResource
from netskope.exceptions import ValidationError
from netskope.models.administration import AdminUser
from netskope.models.rbac import (
    RbacRole,
    RbacRoleDetail,
    RbacRoleSummary,
    RoleCreate,
    RoleMutationReceipt,
    RolePatch,
)
from netskope.resources.rbac.decoder import (
    AsyncRbacAdminsResponses,
    AsyncRbacRolesResponses,
    RbacAdminsResponses,
    RbacRolesResponses,
)
from netskope.resources.rbac.paths import (
    _ADMINS_PATH,
    _ROLES_PATH,
    _build_admins_params,
    _build_roles_params,
    _parse_role,
    _parse_roles_page,
    _role_path_id,
)
from netskope.resources.scim.decoder import validate_page_size

# Admin users are served by ms-platform via a SCIM endpoint — there is no
# /api/v2/rbac/admins route.


# The list envelope is {"version": ..., "count": ..., "roles": [...]}.


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


class RbacRolesResource(SyncResource):
    """Synchronous interface to ``/api/v2/rbac/roles``."""

    @functools.cached_property
    def with_response(self) -> RbacRolesResponses:
        """Access a completed role response and its typed interpretation."""

        return RbacRolesResponses(self._transport)

    def list_page(
        self,
        *,
        role_type: str | None = None,
        scope: str | None = None,
        search: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Page[RbacRoleSummary]:
        """Fetch one role page. Its envelope count is metadata, not a total.

        Filters and pagination parameters match :meth:`list`. This method
        never fetches an additional page automatically.
        """
        return self.with_response.list_page(
            role_type=role_type, scope=scope, search=search, limit=limit, offset=offset
        ).parse()

    def get_detail(self, role_id: int | float) -> RbacRoleDetail:
        """Fetch one role detail using endpoint-specific aliases and nested models."""
        return self.with_response.get_detail(role_id).parse()

    def create_receipt(self, request: RoleCreate) -> RoleMutationReceipt:
        """Create a role with one POST and return its acknowledgment, without a GET."""
        return self.with_response.create_receipt(request).parse()

    def update_receipt(self, role_id: int | float, request: RolePatch) -> RoleMutationReceipt:
        """Send one PATCH and return its acknowledgment, without a follow-up GET."""
        return self.with_response.update_receipt(role_id, request).parse()

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
            netskope.exceptions.ValidationError: If *role_type* or *scope* is
                not a supported value, or if *limit* or *offset* falls outside
                the bounds the operation declares (ms-rbac.yaml:986-997).
        """
        params = _build_roles_params(role_type, scope, search, limit, offset)
        body = self._get(_ROLES_PATH, **params)
        return _parse_roles_page(body, RbacRole, offset or 0, limit).items

    def get(self, role_id: int | float) -> RbacRole:
        """Get an RBAC role by ID.

        Args:
            role_id: The numeric role identifier.
        """
        rid = _role_path_id(role_id)
        body = self._get(f"{_ROLES_PATH}/{rid}")
        return _parse_role(body, RbacRole)

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
        return self.get(role_id)

    def update(
        self,
        role_id: int | float,
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
        rid = _role_path_id(role_id)
        payload = _build_role_payload(name, description, api_groups, scope, ip_allow_list, labels)
        if not payload:
            raise ValidationError("update() requires at least one field to change")
        self._patch(f"{_ROLES_PATH}/{rid}", json=payload)
        return self.get(role_id)

    def delete(self, role_id: int | float) -> None:
        """Delete a custom RBAC role.  Built-in roles cannot be deleted.

        Args:
            role_id: The numeric role identifier.
        """
        rid = _role_path_id(role_id)
        self._delete(f"{_ROLES_PATH}/{rid}")


class RbacAdminsResource(SyncResource):
    """Synchronous interface to admin users (SCIM, served by ms-platform)."""

    @functools.cached_property
    def with_response(self) -> RbacAdminsResponses:
        """Access a completed admin response and its typed interpretation."""

        return RbacAdminsResponses(self._transport)

    def list_page(
        self,
        *,
        filter_expr: str | None = None,
        count: int = 100,
        start_index: int = 1,
    ) -> Page[AdminUser]:
        """Fetch one SCIM page, without traversing subsequent pages.

        ``count`` is the requested page size and may be zero for a total-only
        query. ``start_index`` is one-based; the returned page offset is
        zero-based. Missing ``totalResults`` leaves the total unknown.
        """
        return self.with_response.list_page(
            filter_expr=filter_expr, count=count, start_index=start_index
        ).parse()

    def list(
        self,
        *,
        filter_expr: str | None = None,
        page_size: int = 100,
    ) -> SyncScimPaginatedResponse[AdminUser]:
        """List admin users.

        Args:
            filter_expr: SCIM filter, e.g.
                ``'urn:ietf:params:scim:schemas:netskope:2.0:user'``
                ``'[recordType eq "SERVICE_ACCOUNT"]'``.
            page_size: Results per page (SCIM ``count``, 1-1000).
        """
        return SyncScimPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_ADMINS_PATH,
            params=_build_admins_params(filter_expr),
            model=AdminUser,
            page_size=validate_page_size(page_size),
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

    @functools.cached_property
    def with_response(self) -> AsyncRbacRolesResponses:
        """Access a completed role response and its typed interpretation."""

        return AsyncRbacRolesResponses(self._transport)

    async def list_page(
        self,
        *,
        role_type: str | None = None,
        scope: str | None = None,
        search: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Page[RbacRoleSummary]:
        """Fetch one role page. See :meth:`RbacRolesResource.list_page`."""
        response = await self.with_response.list_page(
            role_type=role_type, scope=scope, search=search, limit=limit, offset=offset
        )
        return response.parse()

    async def get_detail(self, role_id: int | float) -> RbacRoleDetail:
        """Fetch one role detail. See :meth:`RbacRolesResource.get_detail`."""
        return (await self.with_response.get_detail(role_id)).parse()

    async def create_receipt(self, request: RoleCreate) -> RoleMutationReceipt:
        """Create a role with one POST. See :meth:`RbacRolesResource.create_receipt`."""
        return (await self.with_response.create_receipt(request)).parse()

    async def update_receipt(self, role_id: int | float, request: RolePatch) -> RoleMutationReceipt:
        """Send one PATCH. See :meth:`RbacRolesResource.update_receipt`."""
        return (await self.with_response.update_receipt(role_id, request)).parse()

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
        params = _build_roles_params(role_type, scope, search, limit, offset)
        body = await self._get(_ROLES_PATH, **params)
        return _parse_roles_page(body, RbacRole, offset or 0, limit).items

    async def get(self, role_id: int | float) -> RbacRole:
        """Get an RBAC role by ID."""
        rid = _role_path_id(role_id)
        body = await self._get(f"{_ROLES_PATH}/{rid}")
        return _parse_role(body, RbacRole)

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
        return await self.get(role_id)

    async def update(
        self,
        role_id: int | float,
        *,
        name: str | None = None,
        description: str | None = None,
        api_groups: builtins.list[dict[str, Any]] | None = None,
        scope: dict[str, Any] | None = None,
        ip_allow_list: dict[str, Any] | None = None,
        labels: dict[str, Any] | None = None,
    ) -> RbacRole:
        """Partially update a custom RBAC role.  See :meth:`RbacRolesResource.update`."""
        rid = _role_path_id(role_id)
        payload = _build_role_payload(name, description, api_groups, scope, ip_allow_list, labels)
        if not payload:
            raise ValidationError("update() requires at least one field to change")
        await self._patch(f"{_ROLES_PATH}/{rid}", json=payload)
        return await self.get(role_id)

    async def delete(self, role_id: int | float) -> None:
        """Delete a custom RBAC role."""
        rid = _role_path_id(role_id)
        await self._delete(f"{_ROLES_PATH}/{rid}")


class AsyncRbacAdminsResource(AsyncResource):
    """Async admin users (SCIM)."""

    @functools.cached_property
    def with_response(self) -> AsyncRbacAdminsResponses:
        """Access a completed admin response and its typed interpretation."""

        return AsyncRbacAdminsResponses(self._transport)

    async def list_page(
        self,
        *,
        filter_expr: str | None = None,
        count: int = 100,
        start_index: int = 1,
    ) -> Page[AdminUser]:
        """Fetch one SCIM page. See :meth:`RbacAdminsResource.list_page`."""
        response = await self.with_response.list_page(
            filter_expr=filter_expr, count=count, start_index=start_index
        )
        return response.parse()

    def list(
        self,
        *,
        filter_expr: str | None = None,
        page_size: int = 100,
    ) -> AsyncScimPaginatedResponse[AdminUser]:
        """List admin users.  See :meth:`RbacAdminsResource.list`."""
        return AsyncScimPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_ADMINS_PATH,
            params=_build_admins_params(filter_expr),
            model=AdminUser,
            page_size=validate_page_size(page_size),
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
