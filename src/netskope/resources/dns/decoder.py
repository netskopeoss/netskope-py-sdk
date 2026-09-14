"""Bounded DNS profile, inheritance-group, and reference operations."""

from __future__ import annotations

from typing import Any

from netskope.core.ids import validate_id
from netskope.core.pagination import Page
from netskope.core.resource import AsyncResource, SyncResource
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
from netskope.resources.shared.admin import item, page, page_params, receipt, request_payload
from netskope.response import ApiResponse


# ``interactive`` is a query parameter on every DNS write: POST /dns
# (profiles/dns.yaml:1504-1513), PATCH /dns/{id} (:1732-1741), POST
# /dns/inheritancegroups (:2055-2064) and PATCH /dns/inheritancegroups/{id}
# (:2223-2232).  The gateway defaults it to false, which deploys the write
# immediately; the SDK defaults it to true so a write waits for ``deploy()``.
def _interactive(interactive: bool) -> dict[str, Any]:
    """The ``interactive`` query the DNS write endpoints take."""
    return {"interactive": interactive}


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

    def create(
        self, request: DnsProfileCreate, *, interactive: bool = True
    ) -> ApiResponse[DnsProfile]:
        response = self._transport.request(
            "POST",
            "/api/v2/profiles/dns",
            json=request_payload(request, DnsProfileCreate),
            params=_interactive(interactive),
        )
        return ApiResponse(response, lambda raw: item(raw, DnsProfile))

    def update(
        self, profile_id: str | int, request: DnsProfilePatch, *, interactive: bool = True
    ) -> ApiResponse[DnsProfile]:
        path = f"/api/v2/profiles/dns/{validate_id(profile_id, 'profile_id')}"
        response = self._transport.request(
            "PATCH",
            path,
            json=request_payload(request, DnsProfilePatch),
            params=_interactive(interactive),
        )
        return ApiResponse(response, lambda raw: item(raw, DnsProfile))

    def delete(
        self, profile_id: str | int, *, interactive: bool = False
    ) -> ApiResponse[OperationStatus | None]:
        """Delete a DNS profile; parses the ``SuccessResponse`` acknowledgment.

        ``interactive`` is declared on this DELETE too
        (``profiles/dns.yaml:1811-1820``, ``default: false``): ``True`` leaves
        the profile in ``Pending-delete`` (202) for :meth:`deploy`, ``False``
        deletes and deploys in one step (200).
        """
        path = f"/api/v2/profiles/dns/{validate_id(profile_id, 'profile_id')}"
        response = self._transport.request("DELETE", path, params=_interactive(interactive))
        return ApiResponse(response, receipt)

    def deploy(self, request: DnsDeployment) -> ApiResponse[Page[DnsProfile]]:
        """Deploy pending DNS profiles; parses the profiles the deploy applied.

         ``POST /dns/deploy`` declares its 200 as ``DNSProfileList``
         (``profiles/dns.yaml:1891-1896`` → ``:217-226``); ``{total, profiles}``
        ; not a status acknowledgment, so the applied profiles and the total
         both reach the caller.
        """
        response = self._transport.request(
            "POST", "/api/v2/profiles/dns/deploy", json=request_payload(request, DnsDeployment)
        )
        return ApiResponse(
            response, lambda raw: page(raw, DnsProfile, "profiles", allow_missing=True)
        )

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

    def create(
        self, request: DnsInheritanceGroupCreate, *, interactive: bool = True
    ) -> ApiResponse[DnsInheritanceGroup]:
        response = self._transport.request(
            "POST",
            "/api/v2/profiles/dns/inheritancegroups",
            json=request_payload(request, DnsInheritanceGroupCreate),
            params=_interactive(interactive),
        )
        return ApiResponse(response, lambda raw: item(raw, DnsInheritanceGroup))

    def update(
        self,
        group_id: str | int,
        request: DnsInheritanceGroupPatch,
        *,
        interactive: bool = True,
    ) -> ApiResponse[DnsInheritanceGroup]:
        path = f"/api/v2/profiles/dns/inheritancegroups/{validate_id(group_id, 'group_id')}"
        response = self._transport.request(
            "PATCH",
            path,
            json=request_payload(request, DnsInheritanceGroupPatch),
            params=_interactive(interactive),
        )
        return ApiResponse(response, lambda raw: item(raw, DnsInheritanceGroup))

    def delete(
        self, group_id: str | int, *, interactive: bool = False
    ) -> ApiResponse[OperationStatus | None]:
        """Delete an inheritance group; parses the ``SuccessResponse`` acknowledgment.

        ``interactive`` is declared on this DELETE too
        (``profiles/dns.yaml:2302-2311``, ``default: false``).
        """
        path = f"/api/v2/profiles/dns/inheritancegroups/{validate_id(group_id, 'group_id')}"
        response = self._transport.request("DELETE", path, params=_interactive(interactive))
        return ApiResponse(response, receipt)

    def deploy(
        self, request: DnsInheritanceGroupDeployment
    ) -> ApiResponse[Page[DnsInheritanceGroup]]:
        """Deploy pending inheritance groups; parses the groups the deploy applied.

         ``POST /dns/inheritancegroups/deploy`` declares its 200 as
         ``InheritanceGroupList`` (``profiles/dns.yaml:2384-2389`` → ``:1135-1144``)
        ; ``{total, inheritancegroups}``; not a status acknowledgment.
        """
        response = self._transport.request(
            "POST",
            "/api/v2/profiles/dns/inheritancegroups/deploy",
            json=request_payload(request, DnsInheritanceGroupDeployment),
        )
        return ApiResponse(
            response,
            lambda raw: page(raw, DnsInheritanceGroup, "inheritancegroups", allow_missing=True),
        )


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

    async def create(
        self, request: DnsProfileCreate, *, interactive: bool = True
    ) -> ApiResponse[DnsProfile]:
        response = await self._transport.request(
            "POST",
            "/api/v2/profiles/dns",
            json=request_payload(request, DnsProfileCreate),
            params=_interactive(interactive),
        )
        return ApiResponse(response, lambda raw: item(raw, DnsProfile))

    async def update(
        self, profile_id: str | int, request: DnsProfilePatch, *, interactive: bool = True
    ) -> ApiResponse[DnsProfile]:
        path = f"/api/v2/profiles/dns/{validate_id(profile_id, 'profile_id')}"
        response = await self._transport.request(
            "PATCH",
            path,
            json=request_payload(request, DnsProfilePatch),
            params=_interactive(interactive),
        )
        return ApiResponse(response, lambda raw: item(raw, DnsProfile))

    async def delete(
        self, profile_id: str | int, *, interactive: bool = False
    ) -> ApiResponse[OperationStatus | None]:
        """Delete a DNS profile.  See :meth:`DnsResponses.delete`."""
        path = f"/api/v2/profiles/dns/{validate_id(profile_id, 'profile_id')}"
        response = await self._transport.request("DELETE", path, params=_interactive(interactive))
        return ApiResponse(response, receipt)

    async def deploy(self, request: DnsDeployment) -> ApiResponse[Page[DnsProfile]]:
        """Deploy pending DNS profiles.  See :meth:`DnsResponses.deploy`."""
        response = await self._transport.request(
            "POST", "/api/v2/profiles/dns/deploy", json=request_payload(request, DnsDeployment)
        )
        return ApiResponse(
            response, lambda raw: page(raw, DnsProfile, "profiles", allow_missing=True)
        )

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

    async def create(
        self, request: DnsInheritanceGroupCreate, *, interactive: bool = True
    ) -> ApiResponse[DnsInheritanceGroup]:
        response = await self._transport.request(
            "POST",
            "/api/v2/profiles/dns/inheritancegroups",
            json=request_payload(request, DnsInheritanceGroupCreate),
            params=_interactive(interactive),
        )
        return ApiResponse(response, lambda raw: item(raw, DnsInheritanceGroup))

    async def update(
        self,
        group_id: str | int,
        request: DnsInheritanceGroupPatch,
        *,
        interactive: bool = True,
    ) -> ApiResponse[DnsInheritanceGroup]:
        path = f"/api/v2/profiles/dns/inheritancegroups/{validate_id(group_id, 'group_id')}"
        response = await self._transport.request(
            "PATCH",
            path,
            json=request_payload(request, DnsInheritanceGroupPatch),
            params=_interactive(interactive),
        )
        return ApiResponse(response, lambda raw: item(raw, DnsInheritanceGroup))

    async def delete(
        self, group_id: str | int, *, interactive: bool = False
    ) -> ApiResponse[OperationStatus | None]:
        """Delete an inheritance group.  See :meth:`DnsInheritanceGroupsResponses.delete`."""
        path = f"/api/v2/profiles/dns/inheritancegroups/{validate_id(group_id, 'group_id')}"
        response = await self._transport.request("DELETE", path, params=_interactive(interactive))
        return ApiResponse(response, receipt)

    async def deploy(
        self, request: DnsInheritanceGroupDeployment
    ) -> ApiResponse[Page[DnsInheritanceGroup]]:
        """Deploy pending inheritance groups.

        See :meth:`DnsInheritanceGroupsResponses.deploy`.
        """
        response = await self._transport.request(
            "POST",
            "/api/v2/profiles/dns/inheritancegroups/deploy",
            json=request_payload(request, DnsInheritanceGroupDeployment),
        )
        return ApiResponse(
            response,
            lambda raw: page(raw, DnsInheritanceGroup, "inheritancegroups", allow_missing=True),
        )
