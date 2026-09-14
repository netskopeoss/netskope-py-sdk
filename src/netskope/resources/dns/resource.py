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
from typing import Any, Final, Literal, cast

import httpx

from netskope.core.ids import extract_item, extract_list, id_strings, validate_id
from netskope.core.pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.core.resource import AsyncResource, SyncResource
from netskope.exceptions import ValidationError
from netskope.models.dns import DnsInheritanceGroup, DnsProfile
from netskope.resources.dns.decoder import (
    AsyncDnsInheritanceGroupsResponses,
    AsyncDnsResponses,
    DnsInheritanceGroupsResponses,
    DnsResponses,
    _interactive,
)

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


def _body(response: httpx.Response) -> dict[str, Any]:
    """Decode a JSON response body for the writes that also send query parameters."""
    return cast(dict[str, Any], response.json())


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


# ``DNSProfileRequest.log_traffic`` (profiles/dns.yaml:560-565) and
# ``DNSProfileUpdateRequest.log_traffic`` (:852-856) are a two-value string
# enum, not a boolean.
LogTraffic = Literal["Blocked DNS", "All DNS"]
_LOG_TRAFFIC_VALUES: Final[tuple[str, ...]] = ("Blocked DNS", "All DNS")


def _build_update_payload(
    name: str | None,
    description: str | None,
    log_traffic: LogTraffic | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if log_traffic is not None:
        if log_traffic not in _LOG_TRAFFIC_VALUES:
            raise ValidationError(f"log_traffic must be one of: {', '.join(_LOG_TRAFFIC_VALUES)}.")
        payload["log_traffic"] = log_traffic
    if not payload:
        raise ValidationError("At least one field to update must be provided.")
    return payload


def _deploy_request(
    deploy_all: bool,
    ids: builtins.list[int | str] | None,
    change_note: str | None,
    *,
    require_change_note: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a deploy into the query it takes and the body it takes.

    ``all`` is a query parameter on both deploy endpoints — ``/dns/deploy``
    (profiles/dns.yaml:1874-1883) and ``/dns/inheritancegroups/deploy``
    (:2367-2376) — and putting it in the body both misses the flag and sends a
    body missing its required keys.  Those bodies are ``DNSDeployRequest``
    (``required: [change_note, ids]``, :1328-1332) and
    ``InheritanceGroupDeployRequest`` (``required: [ids]``, :1345-1348); their
    ``ids`` are strings.
    """
    if deploy_all == (ids is not None):
        raise ValidationError("Provide exactly one of all=True or ids=[...].")
    params: dict[str, Any] = {}
    body: dict[str, Any] = {}
    if deploy_all:
        params["all"] = True
    else:
        body["ids"] = id_strings(builtins.list(ids or []), "ids")
        if change_note is None and require_change_note:
            raise ValidationError("change_note is required when deploying named DNS profiles.")
    if change_note is not None:
        body["change_note"] = change_note
    return params, body


class DnsInheritanceGroupsResource(SyncResource):
    """Synchronous interface to ``/api/v2/profiles/dns/inheritancegroups``."""

    @functools.cached_property
    def with_response(self) -> DnsInheritanceGroupsResponses:
        return DnsInheritanceGroupsResponses(self._transport)

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

    def create(self, name: str, *, interactive: bool = True) -> DnsInheritanceGroup:
        """Create a DNS inheritance group.

        Note:
            *interactive* is sent as the ``interactive`` query parameter.  The
            gateway defaults it to ``false``, which deploys the write to the
            live tenant immediately; the SDK defaults it to ``True`` so the
            change waits in a ``Pending-*`` state until :meth:`deploy` applies
            it.  Pass ``interactive=False`` for the gateway's deploy-on-write
            behaviour.

        Args:
            name: Group name (must be unique within the tenant).
            interactive: Leave the new group pending instead of deploying it
                (``profiles/dns.yaml:2055-2064``).
        """
        body = self._post(_GROUPS_PATH, json={"name": name}, interactive=interactive)
        return DnsInheritanceGroup.model_validate(extract_item(body))

    def update(
        self,
        group_id: int | str,
        *,
        name: str | None = None,
        description: str | None = None,
        interactive: bool = True,
    ) -> DnsInheritanceGroup:
        """Partial-update a DNS inheritance group (PATCH); only set fields are sent.

        Note:
            *interactive* is sent as the ``interactive`` query parameter.  The
            gateway defaults it to ``false``, which deploys the write to the
            live tenant immediately; the SDK defaults it to ``True`` so the
            change waits in a ``Pending-*`` state until :meth:`deploy` applies
            it.  Pass ``interactive=False`` for the gateway's deploy-on-write
            behaviour.

        Args:
            group_id: The inheritance group ID.
            name: New group name.
            description: New group description.
            interactive: Leave the change pending instead of deploying it
                (``profiles/dns.yaml:2223-2232``).

        Raises:
            netskope.exceptions.ValidationError: If no fields are provided.
        """
        payload = _build_update_payload(name, description)
        path = f"{_GROUPS_PATH}/{validate_id(group_id, 'group_id')}"
        response = self._transport.request(
            "PATCH", path, json=payload, params={"interactive": interactive}
        )
        return DnsInheritanceGroup.model_validate(extract_item(_body(response)))

    def delete(self, group_id: int | str, *, interactive: bool = False) -> None:
        """Delete a DNS inheritance group.  Irreversible.

        Args:
            group_id: The inheritance group ID.
            interactive: ``True`` leaves the group in ``Pending-delete`` until
                :meth:`deploy` applies it; ``False``; the gateway's own default
                (``profiles/dns.yaml:2302-2311``) and the SDK's, so the call is
                unchanged for existing callers; deletes and deploys in one
                step.
        """
        path = f"{_GROUPS_PATH}/{validate_id(group_id, 'group_id')}"
        self._transport.request("DELETE", path, params=_interactive(interactive))

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
        params, body = _deploy_request(all, ids, change_note, require_change_note=False)
        return self._post(_GROUPS_DEPLOY_PATH, json=body, **params)


class DnsResource(SyncResource):
    """Synchronous interface to the DNS Security profiles API."""

    @functools.cached_property
    def with_response(self) -> DnsResponses:
        return DnsResponses(self._transport)

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

    def create(self, name: str, *, interactive: bool = True) -> DnsProfile:
        """Create a DNS Security profile.

        Note:
            *interactive* is sent as the ``interactive`` query parameter.  The
            gateway defaults it to ``false``, which deploys the write to the
            live tenant immediately; the SDK defaults it to ``True`` so the
            change waits in a ``Pending-*`` state until :meth:`deploy` applies
            it.  Pass ``interactive=False`` for the gateway's deploy-on-write
            behaviour.

        Args:
            name: Profile name (must be unique within the tenant).
            interactive: Leave the new profile pending instead of deploying it
                (``profiles/dns.yaml:1504-1513``).
        """
        body = self._post(_DNS_PATH, json={"name": name}, interactive=interactive)
        return DnsProfile.model_validate(extract_item(body))

    def update(
        self,
        profile_id: int | str,
        *,
        name: str | None = None,
        description: str | None = None,
        log_traffic: LogTraffic | None = None,
        interactive: bool = True,
    ) -> DnsProfile:
        """Partial-update a DNS profile (PATCH); only set fields are sent.

        Note:
            *interactive* is sent as the ``interactive`` query parameter.  The
            gateway defaults it to ``false``, which deploys the write to the
            live tenant immediately; the SDK defaults it to ``True`` so the
            change waits in a ``Pending-*`` state until :meth:`deploy` applies
            it.  Pass ``interactive=False`` for the gateway's deploy-on-write
            behaviour.

        Args:
            profile_id: The DNS profile ID.
            name: New profile name.
            description: New profile description.
            log_traffic: Which queries to log — ``"Blocked DNS"`` or
                ``"All DNS"``.  The gateway models a mode, not a boolean
                (``profiles/dns.yaml:852-856``).
            interactive: Leave the change pending instead of deploying it
                (``profiles/dns.yaml:1732-1741``).

        Raises:
            netskope.exceptions.ValidationError: If no fields are provided, or
                *log_traffic* is not one of the two logging modes.
        """
        payload = _build_update_payload(name, description, log_traffic)
        path = f"{_DNS_PATH}/{validate_id(profile_id, 'profile_id')}"
        response = self._transport.request(
            "PATCH", path, json=payload, params={"interactive": interactive}
        )
        return DnsProfile.model_validate(extract_item(_body(response)))

    def delete(self, profile_id: int | str, *, interactive: bool = False) -> None:
        """Delete a DNS profile.  Irreversible.

        Args:
            profile_id: The DNS profile ID.
            interactive: ``True`` leaves the profile in ``Pending-delete`` until
                :meth:`deploy` applies it; ``False``; the gateway's own default
                (``profiles/dns.yaml:1811-1820``) and the SDK's, so the call is
                unchanged for existing callers; deletes and deploys in one
                step.
        """
        path = f"{_DNS_PATH}/{validate_id(profile_id, 'profile_id')}"
        self._transport.request("DELETE", path, params=_interactive(interactive))

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
            all: Deploy all pending DNS profile changes (sent as the ``all``
                query parameter, ``profiles/dns.yaml:1874-1883``).
            ids: Deploy changes for these profile IDs only.
            change_note: Audit-log note describing the deployment.  Required
                alongside *ids*: ``DNSDeployRequest`` declares
                ``required: [change_note, ids]`` (``:1328-1332``).

        Raises:
            netskope.exceptions.ValidationError: Unless exactly one of
                *all* / *ids* is provided, or *ids* arrives without a
                *change_note*.
        """
        params, body = _deploy_request(all, ids, change_note, require_change_note=True)
        return self._post(_DEPLOY_PATH, json=body, **params)

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

    @functools.cached_property
    def with_response(self) -> AsyncDnsInheritanceGroupsResponses:
        return AsyncDnsInheritanceGroupsResponses(self._transport)

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

    async def create(self, name: str, *, interactive: bool = True) -> DnsInheritanceGroup:
        """Create a DNS inheritance group.

        See :meth:`DnsInheritanceGroupsResource.create`.
        """
        body = await self._post(_GROUPS_PATH, json={"name": name}, interactive=interactive)
        return DnsInheritanceGroup.model_validate(extract_item(body))

    async def update(
        self,
        group_id: int | str,
        *,
        name: str | None = None,
        description: str | None = None,
        interactive: bool = True,
    ) -> DnsInheritanceGroup:
        """Partial-update a DNS inheritance group (PATCH).

        See :meth:`DnsInheritanceGroupsResource.update`.
        """
        payload = _build_update_payload(name, description)
        path = f"{_GROUPS_PATH}/{validate_id(group_id, 'group_id')}"
        response = await self._transport.request(
            "PATCH", path, json=payload, params={"interactive": interactive}
        )
        return DnsInheritanceGroup.model_validate(extract_item(_body(response)))

    async def delete(self, group_id: int | str, *, interactive: bool = False) -> None:
        """Delete a DNS inheritance group.  Irreversible.

        See :meth:`DnsInheritanceGroupsResource.delete`.
        """
        path = f"{_GROUPS_PATH}/{validate_id(group_id, 'group_id')}"
        await self._transport.request("DELETE", path, params=_interactive(interactive))

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
        params, body = _deploy_request(all, ids, change_note, require_change_note=False)
        return await self._post(_GROUPS_DEPLOY_PATH, json=body, **params)


class AsyncDnsResource(AsyncResource):
    """Asynchronous interface to the DNS Security profiles API."""

    @functools.cached_property
    def with_response(self) -> AsyncDnsResponses:
        return AsyncDnsResponses(self._transport)

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

    async def create(self, name: str, *, interactive: bool = True) -> DnsProfile:
        """Create a DNS Security profile.  See :meth:`DnsResource.create`."""
        body = await self._post(_DNS_PATH, json={"name": name}, interactive=interactive)
        return DnsProfile.model_validate(extract_item(body))

    async def update(
        self,
        profile_id: int | str,
        *,
        name: str | None = None,
        description: str | None = None,
        log_traffic: LogTraffic | None = None,
        interactive: bool = True,
    ) -> DnsProfile:
        """Partial-update a DNS profile (PATCH).

        See :meth:`DnsResource.update`.
        """
        payload = _build_update_payload(name, description, log_traffic)
        path = f"{_DNS_PATH}/{validate_id(profile_id, 'profile_id')}"
        response = await self._transport.request(
            "PATCH", path, json=payload, params={"interactive": interactive}
        )
        return DnsProfile.model_validate(extract_item(_body(response)))

    async def delete(self, profile_id: int | str, *, interactive: bool = False) -> None:
        """Delete a DNS profile.  Irreversible.  See :meth:`DnsResource.delete`."""
        path = f"{_DNS_PATH}/{validate_id(profile_id, 'profile_id')}"
        await self._transport.request("DELETE", path, params=_interactive(interactive))

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
        params, body = _deploy_request(all, ids, change_note, require_change_note=True)
        return await self._post(_DEPLOY_PATH, json=body, **params)

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
