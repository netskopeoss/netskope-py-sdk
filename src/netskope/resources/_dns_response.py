"""Bounded DNS profile, inheritance-group, and reference operations."""

from __future__ import annotations

from typing import Any

from netskope.exceptions import ValidationError
from netskope.models.administration import OperationStatus
from netskope.models.dns import (
    DnsDeployment,
    DnsInheritanceGroup,
    DnsInheritanceGroupCreate,
    DnsInheritanceGroupDeployment,
    DnsInheritanceGroupPatch,
    DnsProfile,
    DnsProfileCreate,
    DnsProfilePatch,
    DnsReference,
)
from netskope.pagination import Page
from netskope.resources._admin_response import item, page, page_params, receipt, request_payload
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import validate_id
from netskope.response import ApiResponse


def _params(
    filter: str | None,
    limit: int | None,
    offset: int | None,
    sort_by: str | None = None,
    sort_order: str | None = None,
) -> dict[str, Any]:
    params = page_params(limit, offset, maximum=150)
    if filter is not None:
        params["filter"] = filter
    if sort_by is not None:
        params["sortby"] = sort_by
    if sort_order is not None:
        if sort_order not in ("asc", "desc"):
            raise ValidationError("sort_order must be 'asc' or 'desc'.")
        params["sortorder"] = sort_order
    return params


class DnsResponses(SyncResource):
    def list_page(
        self,
        *,
        filter: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> ApiResponse[Page[DnsProfile]]:
        params = _params(filter, limit, offset, sort_by, sort_order)
        response = self._transport.request("GET", "/api/v2/profiles/dns", params=params or None)
        return ApiResponse(
            response, lambda raw: page(raw, DnsProfile, "profiles", offset=offset or 0, limit=limit)
        )

    def get(self, profile_id: str | int) -> ApiResponse[DnsProfile]:
        path = f"/api/v2/profiles/dns/{validate_id(profile_id, 'profile_id')}"
        response = self._transport.request("GET", path)
        return ApiResponse(response, lambda raw: item(raw, DnsProfile))

    def create(self, request: DnsProfileCreate) -> ApiResponse[DnsProfile]:
        response = self._transport.request(
            "POST", "/api/v2/profiles/dns", json=request_payload(request, DnsProfileCreate)
        )
        return ApiResponse(response, lambda raw: item(raw, DnsProfile))

    def update(self, profile_id: str | int, request: DnsProfilePatch) -> ApiResponse[DnsProfile]:
        path = f"/api/v2/profiles/dns/{validate_id(profile_id, 'profile_id')}"
        response = self._transport.request(
            "PATCH", path, json=request_payload(request, DnsProfilePatch)
        )
        return ApiResponse(response, lambda raw: item(raw, DnsProfile))

    def delete(self, profile_id: str | int) -> ApiResponse[OperationStatus | None]:
        path = f"/api/v2/profiles/dns/{validate_id(profile_id, 'profile_id')}"
        return ApiResponse(self._transport.request("DELETE", path), receipt)

    def deploy(self, request: DnsDeployment) -> ApiResponse[OperationStatus | None]:
        response = self._transport.request(
            "POST", "/api/v2/profiles/dns/deploy", json=request_payload(request, DnsDeployment)
        )
        return ApiResponse(response, receipt)

    def list_tunnels(
        self, *, filter: str | None = None, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[Page[DnsReference]]:
        response = self._transport.request(
            "GET", "/api/v2/profiles/dns/tunnels", params=_params(filter, limit, offset) or None
        )
        return ApiResponse(
            response,
            lambda raw: page(raw, DnsReference, "tunnels", offset=offset or 0, limit=limit),
        )

    def list_domain_categories(
        self, *, filter: str | None = None, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[Page[DnsReference]]:
        response = self._transport.request(
            "GET",
            "/api/v2/profiles/dns/domaincategories",
            params=_params(filter, limit, offset) or None,
        )
        return ApiResponse(
            response,
            lambda raw: page(
                raw, DnsReference, "domaincategories", offset=offset or 0, limit=limit
            ),
        )

    def list_record_types(
        self, *, filter: str | None = None, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[Page[DnsReference]]:
        response = self._transport.request(
            "GET", "/api/v2/profiles/dns/recordtypes", params=_params(filter, limit, offset) or None
        )
        return ApiResponse(
            response,
            lambda raw: page(raw, DnsReference, "recordtypes", offset=offset or 0, limit=limit),
        )


class DnsInheritanceGroupsResponses(SyncResource):
    def list_page(
        self, *, filter: str | None = None, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[Page[DnsInheritanceGroup]]:
        response = self._transport.request(
            "GET",
            "/api/v2/profiles/dns/inheritancegroups",
            params=_params(filter, limit, offset) or None,
        )
        return ApiResponse(
            response,
            lambda raw: page(
                raw, DnsInheritanceGroup, "inheritancegroups", offset=offset or 0, limit=limit
            ),
        )

    def get(self, group_id: str | int) -> ApiResponse[DnsInheritanceGroup]:
        path = f"/api/v2/profiles/dns/inheritancegroups/{validate_id(group_id, 'group_id')}"
        response = self._transport.request("GET", path)
        return ApiResponse(response, lambda raw: item(raw, DnsInheritanceGroup))

    def create(self, request: DnsInheritanceGroupCreate) -> ApiResponse[DnsInheritanceGroup]:
        response = self._transport.request(
            "POST",
            "/api/v2/profiles/dns/inheritancegroups",
            json=request_payload(request, DnsInheritanceGroupCreate),
        )
        return ApiResponse(response, lambda raw: item(raw, DnsInheritanceGroup))

    def update(
        self, group_id: str | int, request: DnsInheritanceGroupPatch
    ) -> ApiResponse[DnsInheritanceGroup]:
        path = f"/api/v2/profiles/dns/inheritancegroups/{validate_id(group_id, 'group_id')}"
        response = self._transport.request(
            "PATCH", path, json=request_payload(request, DnsInheritanceGroupPatch)
        )
        return ApiResponse(response, lambda raw: item(raw, DnsInheritanceGroup))

    def delete(self, group_id: str | int) -> ApiResponse[OperationStatus | None]:
        path = f"/api/v2/profiles/dns/inheritancegroups/{validate_id(group_id, 'group_id')}"
        return ApiResponse(self._transport.request("DELETE", path), receipt)

    def deploy(self, request: DnsInheritanceGroupDeployment) -> ApiResponse[OperationStatus | None]:
        response = self._transport.request(
            "POST",
            "/api/v2/profiles/dns/inheritancegroups/deploy",
            json=request_payload(request, DnsInheritanceGroupDeployment),
        )
        return ApiResponse(response, receipt)


class AsyncDnsResponses(AsyncResource):
    async def list_page(
        self,
        *,
        filter: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> ApiResponse[Page[DnsProfile]]:
        params = _params(filter, limit, offset, sort_by, sort_order)
        response = await self._transport.request(
            "GET", "/api/v2/profiles/dns", params=params or None
        )
        return ApiResponse(
            response, lambda raw: page(raw, DnsProfile, "profiles", offset=offset or 0, limit=limit)
        )

    async def get(self, profile_id: str | int) -> ApiResponse[DnsProfile]:
        path = f"/api/v2/profiles/dns/{validate_id(profile_id, 'profile_id')}"
        response = await self._transport.request("GET", path)
        return ApiResponse(response, lambda raw: item(raw, DnsProfile))

    async def create(self, request: DnsProfileCreate) -> ApiResponse[DnsProfile]:
        response = await self._transport.request(
            "POST", "/api/v2/profiles/dns", json=request_payload(request, DnsProfileCreate)
        )
        return ApiResponse(response, lambda raw: item(raw, DnsProfile))

    async def update(
        self, profile_id: str | int, request: DnsProfilePatch
    ) -> ApiResponse[DnsProfile]:
        path = f"/api/v2/profiles/dns/{validate_id(profile_id, 'profile_id')}"
        response = await self._transport.request(
            "PATCH", path, json=request_payload(request, DnsProfilePatch)
        )
        return ApiResponse(response, lambda raw: item(raw, DnsProfile))

    async def delete(self, profile_id: str | int) -> ApiResponse[OperationStatus | None]:
        path = f"/api/v2/profiles/dns/{validate_id(profile_id, 'profile_id')}"
        return ApiResponse(await self._transport.request("DELETE", path), receipt)

    async def deploy(self, request: DnsDeployment) -> ApiResponse[OperationStatus | None]:
        response = await self._transport.request(
            "POST", "/api/v2/profiles/dns/deploy", json=request_payload(request, DnsDeployment)
        )
        return ApiResponse(response, receipt)

    async def list_tunnels(
        self, *, filter: str | None = None, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[Page[DnsReference]]:
        response = await self._transport.request(
            "GET", "/api/v2/profiles/dns/tunnels", params=_params(filter, limit, offset) or None
        )
        return ApiResponse(
            response,
            lambda raw: page(raw, DnsReference, "tunnels", offset=offset or 0, limit=limit),
        )

    async def list_domain_categories(
        self, *, filter: str | None = None, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[Page[DnsReference]]:
        response = await self._transport.request(
            "GET",
            "/api/v2/profiles/dns/domaincategories",
            params=_params(filter, limit, offset) or None,
        )
        return ApiResponse(
            response,
            lambda raw: page(
                raw, DnsReference, "domaincategories", offset=offset or 0, limit=limit
            ),
        )

    async def list_record_types(
        self, *, filter: str | None = None, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[Page[DnsReference]]:
        response = await self._transport.request(
            "GET", "/api/v2/profiles/dns/recordtypes", params=_params(filter, limit, offset) or None
        )
        return ApiResponse(
            response,
            lambda raw: page(raw, DnsReference, "recordtypes", offset=offset or 0, limit=limit),
        )


class AsyncDnsInheritanceGroupsResponses(AsyncResource):
    async def list_page(
        self, *, filter: str | None = None, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[Page[DnsInheritanceGroup]]:
        response = await self._transport.request(
            "GET",
            "/api/v2/profiles/dns/inheritancegroups",
            params=_params(filter, limit, offset) or None,
        )
        return ApiResponse(
            response,
            lambda raw: page(
                raw, DnsInheritanceGroup, "inheritancegroups", offset=offset or 0, limit=limit
            ),
        )

    async def get(self, group_id: str | int) -> ApiResponse[DnsInheritanceGroup]:
        path = f"/api/v2/profiles/dns/inheritancegroups/{validate_id(group_id, 'group_id')}"
        response = await self._transport.request("GET", path)
        return ApiResponse(response, lambda raw: item(raw, DnsInheritanceGroup))

    async def create(self, request: DnsInheritanceGroupCreate) -> ApiResponse[DnsInheritanceGroup]:
        response = await self._transport.request(
            "POST",
            "/api/v2/profiles/dns/inheritancegroups",
            json=request_payload(request, DnsInheritanceGroupCreate),
        )
        return ApiResponse(response, lambda raw: item(raw, DnsInheritanceGroup))

    async def update(
        self, group_id: str | int, request: DnsInheritanceGroupPatch
    ) -> ApiResponse[DnsInheritanceGroup]:
        path = f"/api/v2/profiles/dns/inheritancegroups/{validate_id(group_id, 'group_id')}"
        response = await self._transport.request(
            "PATCH", path, json=request_payload(request, DnsInheritanceGroupPatch)
        )
        return ApiResponse(response, lambda raw: item(raw, DnsInheritanceGroup))

    async def delete(self, group_id: str | int) -> ApiResponse[OperationStatus | None]:
        path = f"/api/v2/profiles/dns/inheritancegroups/{validate_id(group_id, 'group_id')}"
        return ApiResponse(await self._transport.request("DELETE", path), receipt)

    async def deploy(
        self, request: DnsInheritanceGroupDeployment
    ) -> ApiResponse[OperationStatus | None]:
        response = await self._transport.request(
            "POST",
            "/api/v2/profiles/dns/inheritancegroups/deploy",
            json=request_payload(request, DnsInheritanceGroupDeployment),
        )
        return ApiResponse(response, receipt)
