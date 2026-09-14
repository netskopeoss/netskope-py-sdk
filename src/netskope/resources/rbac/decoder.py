"""RBAC operations retaining their original HTTP responses."""

from __future__ import annotations

from netskope.core.pagination import Page
from netskope.core.resource import AsyncResource, SyncResource
from netskope.models.administration import AdminUser
from netskope.models.rbac import (
    RbacRoleDetail,
    RbacRoleSummary,
    RoleCreate,
    RoleMutationReceipt,
    RolePatch,
)
from netskope.resources.rbac.paths import (
    _ADMINS_PATH,
    _ROLES_PATH,
    _build_admins_page_params,
    _build_role_request,
    _build_roles_params,
    _parse_admins_page,
    _parse_role_detail,
    _parse_role_receipt,
    _parse_roles_page,
    _role_path_id,
)
from netskope.response import ApiResponse


class RbacRolesResponses(SyncResource):
    """Response access for synchronous role operations, one request per method."""

    def list_page(
        self,
        *,
        role_type: str | None = None,
        scope: str | None = None,
        search: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[Page[RbacRoleSummary]]:
        params = _build_roles_params(role_type, scope, search, limit, offset)
        response = self._transport.request("GET", _ROLES_PATH, params=params or None)
        return ApiResponse(
            response,
            lambda raw: _parse_roles_page(raw.json(), RbacRoleSummary, offset or 0, limit),
        )

    def get_detail(self, role_id: int | float) -> ApiResponse[RbacRoleDetail]:
        rid = _role_path_id(role_id)
        response = self._transport.request("GET", f"{_ROLES_PATH}/{rid}")
        return ApiResponse(response, lambda raw: _parse_role_detail(raw.json(), role_id))

    def create_receipt(self, request: RoleCreate) -> ApiResponse[RoleMutationReceipt]:
        payload = _build_role_request(request, RoleCreate)
        response = self._transport.request("POST", _ROLES_PATH, json=payload)
        return ApiResponse(response, lambda raw: _parse_role_receipt(raw.json()))

    def update_receipt(
        self, role_id: int | float, request: RolePatch
    ) -> ApiResponse[RoleMutationReceipt]:
        rid = _role_path_id(role_id)
        payload = _build_role_request(request, RolePatch)
        response = self._transport.request("PATCH", f"{_ROLES_PATH}/{rid}", json=payload)
        return ApiResponse(response, lambda raw: _parse_role_receipt(raw.json(), role_id))


class RbacAdminsResponses(SyncResource):
    """Response access for synchronous bounded SCIM admin reads."""

    def list_page(
        self,
        *,
        filter_expr: str | None = None,
        count: int = 100,
        start_index: int = 1,
    ) -> ApiResponse[Page[AdminUser]]:
        params = _build_admins_page_params(filter_expr, count, start_index)
        response = self._transport.request("GET", _ADMINS_PATH, params=params)
        return ApiResponse(response, lambda raw: _parse_admins_page(raw.json(), start_index, count))


class AsyncRbacRolesResponses(AsyncResource):
    """Response access for asynchronous role operations, one request per method."""

    async def list_page(
        self,
        *,
        role_type: str | None = None,
        scope: str | None = None,
        search: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[Page[RbacRoleSummary]]:
        params = _build_roles_params(role_type, scope, search, limit, offset)
        response = await self._transport.request("GET", _ROLES_PATH, params=params or None)
        return ApiResponse(
            response,
            lambda raw: _parse_roles_page(raw.json(), RbacRoleSummary, offset or 0, limit),
        )

    async def get_detail(self, role_id: int | float) -> ApiResponse[RbacRoleDetail]:
        rid = _role_path_id(role_id)
        response = await self._transport.request("GET", f"{_ROLES_PATH}/{rid}")
        return ApiResponse(response, lambda raw: _parse_role_detail(raw.json(), role_id))

    async def create_receipt(self, request: RoleCreate) -> ApiResponse[RoleMutationReceipt]:
        payload = _build_role_request(request, RoleCreate)
        response = await self._transport.request("POST", _ROLES_PATH, json=payload)
        return ApiResponse(response, lambda raw: _parse_role_receipt(raw.json()))

    async def update_receipt(
        self, role_id: int | float, request: RolePatch
    ) -> ApiResponse[RoleMutationReceipt]:
        rid = _role_path_id(role_id)
        payload = _build_role_request(request, RolePatch)
        response = await self._transport.request("PATCH", f"{_ROLES_PATH}/{rid}", json=payload)
        return ApiResponse(response, lambda raw: _parse_role_receipt(raw.json(), role_id))


class AsyncRbacAdminsResponses(AsyncResource):
    """Response access for asynchronous bounded SCIM admin reads."""

    async def list_page(
        self,
        *,
        filter_expr: str | None = None,
        count: int = 100,
        start_index: int = 1,
    ) -> ApiResponse[Page[AdminUser]]:
        params = _build_admins_page_params(filter_expr, count, start_index)
        response = await self._transport.request("GET", _ADMINS_PATH, params=params)
        return ApiResponse(response, lambda raw: _parse_admins_page(raw.json(), start_index, count))
