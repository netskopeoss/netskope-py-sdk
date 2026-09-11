"""DSPM (Data Security Posture Management) resource.

Query data-security posture resources (datastores, databases, schemas, tables,
columns, scans, policy violations, and more), retrieve analytics metrics, and
connect or scan datastores.

The legacy methods retain their raw response types and historical paths.
``list_page`` and ``with_response`` use verified public routes and return
endpoint-specific models; ``supported_resource_types`` names that surface.

Example::

    # List connected datastores, sorted by name
    body = client.dspm.list_resources(
        "connected_datastores",
        sort_by="name",
        sort_order="asc",
        limit=20,
    )

    # Retrieve an analytics metric
    summary = client.dspm.analytics("summary")
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any

from netskope.exceptions import ValidationError
from netskope.models.dspm import DspmRecord, DspmResourceType, SortOrder
from netskope.pagination import Page
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import quote_id

if TYPE_CHECKING:
    from netskope.resources._dspm_response import AsyncDspmResponses, DspmResponses

_BASE_PATH = "/api/v2/dspm"
_ANALYTICS_PATH = f"{_BASE_PATH}/analytics"
_CONNECTED_DATASTORES_PATH = f"{_BASE_PATH}/connected_datastores"
_SCANS_PATH = f"{_BASE_PATH}/scans"


def _validate_resource_type(resource_type: DspmResourceType | str) -> str:
    """Coerce *resource_type* to a known DSPM resource-type path segment.

    Raises:
        netskope.exceptions.ValidationError: If *resource_type* is not a
            member of :class:`~netskope.models.dspm.DspmResourceType`.
    """
    try:
        return DspmResourceType(resource_type).value
    except ValueError as exc:
        valid = ", ".join(rt.value for rt in DspmResourceType)
        raise ValidationError(
            f"Invalid DSPM resource_type {resource_type!r}. Must be one of: {valid}"
        ) from exc


def _build_list_params(
    filter_expr: str | None,
    sort_by: str | None,
    sort_order: SortOrder | str | None,
    limit: int | None,
    offset: int | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if filter_expr is not None:
        params["filter"] = filter_expr
    if sort_by is not None:
        params["sortby"] = sort_by
    if sort_order is not None:
        params["sortorder"] = SortOrder(sort_order).value
    if offset is not None:
        params["offset"] = offset
    if limit is not None:
        params["limit"] = limit
    return params


def _resource_path(resource_type: DspmResourceType | str) -> str:
    return f"{_BASE_PATH}/{_validate_resource_type(resource_type)}"


def _analytics_path(metric_type: str) -> str:
    return f"{_ANALYTICS_PATH}/{quote_id(metric_type)}"


def _ids_payload(ids: list[str]) -> dict[str, Any]:
    return {"ids": ids}


class DspmResource(SyncResource):
    """Synchronous interface to the DSPM API."""

    @functools.cached_property
    def with_response(self) -> DspmResponses:
        from netskope.resources._dspm_response import DspmResponses

        return DspmResponses(self._transport)

    @staticmethod
    def supported_resource_types() -> tuple[DspmResourceType, ...]:
        """Resource names with verified routes in the typed read surface."""
        from netskope.resources._dspm_response import supported_resource_types

        return supported_resource_types()

    def list_page(
        self,
        resource_type: DspmResourceType | str,
        *,
        filter_expr: str | None = None,
        sort_by: str | None = None,
        sort_order: SortOrder | str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Page[DspmRecord]:
        """Fetch exactly one typed page from a verified public DSPM resource."""
        return self.with_response.list_page(
            resource_type,
            filter_expr=filter_expr,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        ).parse()

    def start_scan(self, datastore_id: str) -> None:
        """Request a scan for one datastore. HTTP 202 does not mean it finished."""
        self.with_response.start_scan(datastore_id).parse()

    def list_resources(
        self,
        resource_type: DspmResourceType | str,
        *,
        filter_expr: str | None = None,
        sort_by: str | None = None,
        sort_order: SortOrder | str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List DSPM resources of the given type.

        Queries ``GET /api/v2/dspm/{resource_type}`` with optional filtering,
        sorting, and offset pagination.

        Args:
            resource_type: The DSPM resource type to query.  A
                :class:`~netskope.models.dspm.DspmResourceType` or its string
                value.
            filter_expr: DSPM filter expression, e.g. ``name eq 'prod-db'``.
            sort_by: Field name to sort by (e.g. ``name``).
            sort_order: ``"asc"`` or ``"desc"`` — only applies with *sort_by*.
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            The raw response body.

        Raises:
            netskope.exceptions.ValidationError: If *resource_type* is unknown.
        """
        params = _build_list_params(filter_expr, sort_by, sort_order, limit, offset)
        return self._get(_resource_path(resource_type), **params)

    def analytics(self, metric_type: str) -> dict[str, Any]:
        """Retrieve a DSPM analytics metric.

        Queries ``GET /api/v2/dspm/analytics/{metric_type}`` for aggregated
        statistics or trend data.  Available metric types depend on the
        tenant's DSPM configuration.

        Args:
            metric_type: The analytics metric to retrieve (e.g. ``summary``).

        Returns:
            The raw response body.
        """
        return self._get(_analytics_path(metric_type))

    def connect_datastores(self, ids: list[str]) -> dict[str, Any]:
        """Connect discovered datastores for DSPM monitoring.

        Sends ``POST /api/v2/dspm/connected_datastores`` with the given
        discovered-datastore ids.

        Args:
            ids: Discovered-datastore identifiers to connect.

        Returns:
            The raw response body.
        """
        return self._post(_CONNECTED_DATASTORES_PATH, json=_ids_payload(ids))

    def scan_datastores(self, ids: list[str]) -> dict[str, Any]:
        """Trigger classification scans on connected datastores.

        Sends ``POST /api/v2/dspm/scans`` with the given connected-datastore
        ids.

        Args:
            ids: Connected-datastore identifiers to scan.

        Returns:
            The raw response body.
        """
        return self._post(_SCANS_PATH, json=_ids_payload(ids))


class AsyncDspmResource(AsyncResource):
    """Asynchronous interface to the DSPM API."""

    @functools.cached_property
    def with_response(self) -> AsyncDspmResponses:
        from netskope.resources._dspm_response import AsyncDspmResponses

        return AsyncDspmResponses(self._transport)

    @staticmethod
    def supported_resource_types() -> tuple[DspmResourceType, ...]:
        """Resource names with verified routes in the typed read surface."""
        return DspmResource.supported_resource_types()

    async def list_page(
        self,
        resource_type: DspmResourceType | str,
        *,
        filter_expr: str | None = None,
        sort_by: str | None = None,
        sort_order: SortOrder | str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Page[DspmRecord]:
        """Fetch exactly one typed page from a verified public DSPM resource."""
        return (
            await self.with_response.list_page(
                resource_type,
                filter_expr=filter_expr,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
                offset=offset,
            )
        ).parse()

    async def start_scan(self, datastore_id: str) -> None:
        """Request a scan for one datastore. HTTP 202 does not mean it finished."""
        (await self.with_response.start_scan(datastore_id)).parse()

    async def list_resources(
        self,
        resource_type: DspmResourceType | str,
        *,
        filter_expr: str | None = None,
        sort_by: str | None = None,
        sort_order: SortOrder | str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List DSPM resources of the given type.

        See :meth:`DspmResource.list_resources`.
        """
        params = _build_list_params(filter_expr, sort_by, sort_order, limit, offset)
        return await self._get(_resource_path(resource_type), **params)

    async def analytics(self, metric_type: str) -> dict[str, Any]:
        """Retrieve a DSPM analytics metric.

        See :meth:`DspmResource.analytics`.
        """
        return await self._get(_analytics_path(metric_type))

    async def connect_datastores(self, ids: list[str]) -> dict[str, Any]:
        """Connect discovered datastores for DSPM monitoring.

        See :meth:`DspmResource.connect_datastores`.
        """
        return await self._post(_CONNECTED_DATASTORES_PATH, json=_ids_payload(ids))

    async def scan_datastores(self, ids: list[str]) -> dict[str, Any]:
        """Trigger classification scans on connected datastores.

        See :meth:`DspmResource.scan_datastores`.
        """
        return await self._post(_SCANS_PATH, json=_ids_payload(ids))
