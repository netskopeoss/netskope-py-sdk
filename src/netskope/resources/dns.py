"""DNS Security profiles resource — profile CRUD, deployment, inheritance
groups, and reference data lookups (tunnels, domain categories, record types).

Example::

    for profile in client.dns.list():
        print(f"{profile.id}: {profile.name}")

    profile = client.dns.create("Corporate DNS Policy")
    client.dns.update(profile.id, description="Baseline policy")

    for group in client.dns.inheritance_groups.list():
        print(f"{group.id}: {group.name}")
"""

from __future__ import annotations

import builtins
import functools
from typing import Any

from netskope._pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.exceptions import ValidationError
from netskope.models.dns import DnsInheritanceGroup, DnsProfile
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import extract_item, extract_list, validate_id

_DNS_PATH = "/api/v2/profiles/dns"
_DEPLOY_PATH = f"{_DNS_PATH}/deploy"
_TUNNELS_PATH = f"{_DNS_PATH}/tunnels"
_DOMAIN_CATEGORIES_PATH = f"{_DNS_PATH}/domaincategories"
_RECORD_TYPES_PATH = f"{_DNS_PATH}/recordtypes"
_GROUPS_PATH = f"{_DNS_PATH}/inheritancegroups"
_GROUPS_DEPLOY_PATH = f"{_GROUPS_PATH}/deploy"

# The DNS API rejects list ``limit`` values above 150 with HTTP 400
# ("Limit value must be between 0 and 150"); the paginator clamps to a safe
# page size below that cap.
_MAX_PAGE_SIZE = 100


def _extract_profiles(body: dict[str, Any]) -> list[dict[str, Any]]:
    """List responses use a ``{"profiles": [...]}`` envelope."""
    return extract_list(body, "profiles")


def _extract_inheritance_groups(body: dict[str, Any]) -> list[dict[str, Any]]:
    """List responses use an ``{"inheritancegroups": [...]}`` envelope."""
    return extract_list(body, "inheritancegroups", "inheritance_groups", "groups")


def _build_list_params(
    filter_expr: str | None,
    sort_by: str | None = None,
    sort_order: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if filter_expr is not None:
        params["filter"] = filter_expr
    if sort_by is not None:
        params["sortby"] = sort_by
    if sort_order is not None:
        params["sortorder"] = sort_order
    return params


def _build_reference_params(
    filter_expr: str | None,
    limit: int | None,
    offset: int | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if filter_expr is not None:
        params["filter"] = filter_expr
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    return params


def _build_update_payload(
    name: str | None,
    description: str | None,
    log_traffic: bool | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if log_traffic is not None:
        payload["log_traffic"] = log_traffic
    if not payload:
        raise ValidationError("At least one field to update must be provided.")
    return payload


def _build_deploy_payload(
    deploy_all: bool,
    ids: builtins.list[int | str] | None,
    change_note: str | None,
) -> dict[str, Any]:
    if deploy_all == (ids is not None):
        raise ValidationError("Provide exactly one of all=True or ids=[...].")
    body: dict[str, Any] = {"all": True} if deploy_all else {"ids": builtins.list(ids or [])}
    if change_note is not None:
        body["change_note"] = change_note
    return body


class DnsInheritanceGroupsResource(SyncResource):
    """Synchronous interface to ``/api/v2/profiles/dns/inheritancegroups``."""

    def list(
        self,
        *,
        filter_expr: str | None = None,
        page_size: int = 100,
    ) -> SyncPaginatedResponse[DnsInheritanceGroup]:
        """List DNS inheritance groups.

        Args:
            filter_expr: Server-side filter expression.
            page_size: Results per page.  The API caps ``limit`` at 150;
                values above 100 are clamped to 100.
        """
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_GROUPS_PATH,
            params=_build_list_params(filter_expr),
            model=DnsInheritanceGroup,
            page_size=min(page_size, _MAX_PAGE_SIZE),
            extract=_extract_inheritance_groups,
        )

    def get(self, group_id: int | str) -> DnsInheritanceGroup:
        """Get a DNS inheritance group by ID."""
        body = self._get(f"{_GROUPS_PATH}/{validate_id(group_id, 'group_id')}")
        return DnsInheritanceGroup.model_validate(extract_item(body))

    def create(self, name: str) -> DnsInheritanceGroup:
        """Create a DNS inheritance group.

        Args:
            name: Group name (must be unique within the tenant).
        """
        body = self._post(_GROUPS_PATH, json={"name": name})
        return DnsInheritanceGroup.model_validate(extract_item(body))

    def update(
        self,
        group_id: int | str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> DnsInheritanceGroup:
        """Partial-update a DNS inheritance group (PATCH); only set fields are sent.

        Args:
            group_id: The inheritance group ID.
            name: New group name.
            description: New group description.

        Raises:
            netskope.exceptions.ValidationError: If no fields are provided.
        """
        payload = _build_update_payload(name, description)
        body = self._patch(f"{_GROUPS_PATH}/{validate_id(group_id, 'group_id')}", json=payload)
        return DnsInheritanceGroup.model_validate(extract_item(body))

    def delete(self, group_id: int | str) -> None:
        """Delete a DNS inheritance group.  Irreversible."""
        self._delete(f"{_GROUPS_PATH}/{validate_id(group_id, 'group_id')}")

    def deploy(
        self,
        *,
        all: bool = False,
        ids: builtins.list[int | str] | None = None,
        change_note: str | None = None,
    ) -> dict[str, Any]:
        """Deploy pending inheritance group changes to the live tenant.

        .. warning:: This deploys configuration changes tenant-wide — use
            with care.

        Args:
            all: Deploy all pending inheritance group changes.
            ids: Deploy changes for these group IDs only.
            change_note: Audit-log note describing the deployment.

        Raises:
            netskope.exceptions.ValidationError: Unless exactly one of
                *all* / *ids* is provided.
        """
        return self._post(_GROUPS_DEPLOY_PATH, json=_build_deploy_payload(all, ids, change_note))


class DnsResource(SyncResource):
    """Synchronous interface to the DNS Security profiles API."""

    def list(
        self,
        *,
        filter_expr: str | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
        page_size: int = 100,
    ) -> SyncPaginatedResponse[DnsProfile]:
        """List DNS Security profiles.

        Responses use a ``{"profiles": [...]}`` envelope with UUID string
        ``id`` values.

        Args:
            filter_expr: Server-side filter expression.
            sort_by: Field to sort by (e.g. ``"name"``).
            sort_order: ``"asc"`` or ``"desc"``.
            page_size: Results per page.  The API caps ``limit`` at 150;
                values above 100 are clamped to 100.
        """
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_DNS_PATH,
            params=_build_list_params(filter_expr, sort_by, sort_order),
            model=DnsProfile,
            page_size=min(page_size, _MAX_PAGE_SIZE),
            extract=_extract_profiles,
        )

    def get(self, profile_id: int | str) -> DnsProfile:
        """Get a DNS profile by ID."""
        body = self._get(f"{_DNS_PATH}/{validate_id(profile_id, 'profile_id')}")
        return DnsProfile.model_validate(extract_item(body))

    def create(self, name: str) -> DnsProfile:
        """Create a DNS Security profile.

        Args:
            name: Profile name (must be unique within the tenant).
        """
        body = self._post(_DNS_PATH, json={"name": name})
        return DnsProfile.model_validate(extract_item(body))

    def update(
        self,
        profile_id: int | str,
        *,
        name: str | None = None,
        description: str | None = None,
        log_traffic: bool | None = None,
    ) -> DnsProfile:
        """Partial-update a DNS profile (PATCH); only set fields are sent.

        Args:
            profile_id: The DNS profile ID.
            name: New profile name.
            description: New profile description.
            log_traffic: Enable or disable traffic logging.

        Raises:
            netskope.exceptions.ValidationError: If no fields are provided.
        """
        payload = _build_update_payload(name, description, log_traffic)
        body = self._patch(f"{_DNS_PATH}/{validate_id(profile_id, 'profile_id')}", json=payload)
        return DnsProfile.model_validate(extract_item(body))

    def delete(self, profile_id: int | str) -> None:
        """Delete a DNS profile.  Irreversible."""
        self._delete(f"{_DNS_PATH}/{validate_id(profile_id, 'profile_id')}")

    def deploy(
        self,
        *,
        all: bool = False,
        ids: builtins.list[int | str] | None = None,
        change_note: str | None = None,
    ) -> dict[str, Any]:
        """Deploy pending DNS profile changes to the live tenant.

        .. warning:: This deploys configuration changes tenant-wide — use
            with care.

        Args:
            all: Deploy all pending DNS profile changes.
            ids: Deploy changes for these profile IDs only.
            change_note: Audit-log note describing the deployment.

        Raises:
            netskope.exceptions.ValidationError: Unless exactly one of
                *all* / *ids* is provided.
        """
        return self._post(_DEPLOY_PATH, json=_build_deploy_payload(all, ids, change_note))

    def list_tunnels(
        self,
        *,
        filter_expr: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List DNS tunnels available for DNS Security profiles.

        Args:
            filter_expr: Server-side filter expression.
            limit: Maximum number of tunnels to return.
            offset: Number of tunnels to skip (pagination).
        """
        return self._get(_TUNNELS_PATH, **_build_reference_params(filter_expr, limit, offset))

    def list_domain_categories(
        self,
        *,
        filter_expr: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """List domain categories available for DNS Security rules.

        Args:
            filter_expr: Server-side filter expression.
            limit: Maximum number of categories to return.
        """
        return self._get(_DOMAIN_CATEGORIES_PATH, **_build_reference_params(filter_expr, limit))

    def list_record_types(
        self,
        *,
        filter_expr: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """List DNS record types available for DNS Security rules.

        Args:
            filter_expr: Server-side filter expression.
            limit: Maximum number of record types to return.
        """
        return self._get(_RECORD_TYPES_PATH, **_build_reference_params(filter_expr, limit))

    @functools.cached_property
    def inheritance_groups(self) -> DnsInheritanceGroupsResource:
        """Access the DNS inheritance groups API."""
        return DnsInheritanceGroupsResource(self._transport)


# --- Async counterparts ---


class AsyncDnsInheritanceGroupsResource(AsyncResource):
    """Async interface to ``/api/v2/profiles/dns/inheritancegroups``."""

    def list(
        self,
        *,
        filter_expr: str | None = None,
        page_size: int = 100,
    ) -> AsyncPaginatedResponse[DnsInheritanceGroup]:
        """List DNS inheritance groups.  See :meth:`DnsInheritanceGroupsResource.list`."""
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_GROUPS_PATH,
            params=_build_list_params(filter_expr),
            model=DnsInheritanceGroup,
            page_size=min(page_size, _MAX_PAGE_SIZE),
            extract=_extract_inheritance_groups,
        )

    async def get(self, group_id: int | str) -> DnsInheritanceGroup:
        """Get a DNS inheritance group by ID."""
        body = await self._get(f"{_GROUPS_PATH}/{validate_id(group_id, 'group_id')}")
        return DnsInheritanceGroup.model_validate(extract_item(body))

    async def create(self, name: str) -> DnsInheritanceGroup:
        """Create a DNS inheritance group."""
        body = await self._post(_GROUPS_PATH, json={"name": name})
        return DnsInheritanceGroup.model_validate(extract_item(body))

    async def update(
        self,
        group_id: int | str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> DnsInheritanceGroup:
        """Partial-update a DNS inheritance group (PATCH).

        See :meth:`DnsInheritanceGroupsResource.update`.
        """
        payload = _build_update_payload(name, description)
        body = await self._patch(
            f"{_GROUPS_PATH}/{validate_id(group_id, 'group_id')}", json=payload
        )
        return DnsInheritanceGroup.model_validate(extract_item(body))

    async def delete(self, group_id: int | str) -> None:
        """Delete a DNS inheritance group.  Irreversible."""
        await self._delete(f"{_GROUPS_PATH}/{validate_id(group_id, 'group_id')}")

    async def deploy(
        self,
        *,
        all: bool = False,
        ids: builtins.list[int | str] | None = None,
        change_note: str | None = None,
    ) -> dict[str, Any]:
        """Deploy pending inheritance group changes tenant-wide — use with care.

        See :meth:`DnsInheritanceGroupsResource.deploy`.
        """
        return await self._post(
            _GROUPS_DEPLOY_PATH, json=_build_deploy_payload(all, ids, change_note)
        )


class AsyncDnsResource(AsyncResource):
    """Asynchronous interface to the DNS Security profiles API."""

    def list(
        self,
        *,
        filter_expr: str | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
        page_size: int = 100,
    ) -> AsyncPaginatedResponse[DnsProfile]:
        """List DNS Security profiles.  See :meth:`DnsResource.list`."""
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_DNS_PATH,
            params=_build_list_params(filter_expr, sort_by, sort_order),
            model=DnsProfile,
            page_size=min(page_size, _MAX_PAGE_SIZE),
            extract=_extract_profiles,
        )

    async def get(self, profile_id: int | str) -> DnsProfile:
        """Get a DNS profile by ID."""
        body = await self._get(f"{_DNS_PATH}/{validate_id(profile_id, 'profile_id')}")
        return DnsProfile.model_validate(extract_item(body))

    async def create(self, name: str) -> DnsProfile:
        """Create a DNS Security profile."""
        body = await self._post(_DNS_PATH, json={"name": name})
        return DnsProfile.model_validate(extract_item(body))

    async def update(
        self,
        profile_id: int | str,
        *,
        name: str | None = None,
        description: str | None = None,
        log_traffic: bool | None = None,
    ) -> DnsProfile:
        """Partial-update a DNS profile (PATCH).

        See :meth:`DnsResource.update`.
        """
        payload = _build_update_payload(name, description, log_traffic)
        body = await self._patch(
            f"{_DNS_PATH}/{validate_id(profile_id, 'profile_id')}", json=payload
        )
        return DnsProfile.model_validate(extract_item(body))

    async def delete(self, profile_id: int | str) -> None:
        """Delete a DNS profile.  Irreversible."""
        await self._delete(f"{_DNS_PATH}/{validate_id(profile_id, 'profile_id')}")

    async def deploy(
        self,
        *,
        all: bool = False,
        ids: builtins.list[int | str] | None = None,
        change_note: str | None = None,
    ) -> dict[str, Any]:
        """Deploy pending DNS profile changes tenant-wide — use with care.

        See :meth:`DnsResource.deploy`.
        """
        return await self._post(_DEPLOY_PATH, json=_build_deploy_payload(all, ids, change_note))

    async def list_tunnels(
        self,
        *,
        filter_expr: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List DNS tunnels available for DNS Security profiles."""
        return await self._get(_TUNNELS_PATH, **_build_reference_params(filter_expr, limit, offset))

    async def list_domain_categories(
        self,
        *,
        filter_expr: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """List domain categories available for DNS Security rules."""
        return await self._get(
            _DOMAIN_CATEGORIES_PATH, **_build_reference_params(filter_expr, limit)
        )

    async def list_record_types(
        self,
        *,
        filter_expr: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """List DNS record types available for DNS Security rules."""
        return await self._get(_RECORD_TYPES_PATH, **_build_reference_params(filter_expr, limit))

    @functools.cached_property
    def inheritance_groups(self) -> AsyncDnsInheritanceGroupsResource:
        """Access the DNS inheritance groups API."""
        return AsyncDnsInheritanceGroupsResource(self._transport)
