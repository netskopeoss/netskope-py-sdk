"""DSPM (Data Security Posture Management) resource.

Query data-security posture resources (datastores, databases, schemas, tables,
columns, classification metadata, sidecar pools and infrastructure
connections), read the two connected-datastore analytics reports, and start
classification scans.

``list_resources`` and ``list_page`` address the same verified public routes
(``_dspm_response._ROUTES``); ``list_resources`` returns the raw body and
``list_page`` returns typed records.  ``supported_resource_types`` names that
surface.

Example::

    # List connected datastores, sorted by name
    body = client.dspm.list_resources(
        "connected_datastores",
        sort_by="name",
        sort_order="asc",
        limit=20,
    )

    # Retrieve an analytics report
    distribution = client.dspm.analytics("sensitivity_score_distribution")
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any

from netskope.exceptions import ValidationError
from netskope.models.dspm import DspmRecord, DspmResourceType, SortOrder
from netskope.pagination import Page
from netskope.resources._base import AsyncResource, SyncResource

if TYPE_CHECKING:
    from netskope.resources._dspm_response import AsyncDspmResponses, DspmResponses

_BASE_PATH = "/api/v2/dspm"
_CONNECTED_DATASTORES_PATH = f"{_BASE_PATH}/datastores/connected"

# The only two connected-datastore analytics reports the gateway declares
# (dspm_external.yaml:6508 and :8039).  There is no /analytics path family.
_ANALYTICS_ROUTES: dict[str, str] = {
    "sensitivity_score_distribution": f"{_CONNECTED_DATASTORES_PATH}/sensitivityscoresdistribution",
    "privilege_risks": f"{_CONNECTED_DATASTORES_PATH}/privilegerisks",
}


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


def _analytics_path(metric_type: str) -> str:
    """Resolve a DSPM analytics report name to its declared path."""
    path = _ANALYTICS_ROUTES.get(metric_type)
    if path is None:
        valid = ", ".join(sorted(_ANALYTICS_ROUTES))
        raise ValidationError(
            f"Unknown DSPM analytics report {metric_type!r}. Must be one of: {valid}"
        )
    return path


def _connect_unsupported() -> ValidationError:
    """The gateway offers no bulk connect-by-id operation."""
    return ValidationError(
        "DSPM has no bulk connect-by-id operation. Connect one datastore at a time with "
        "connect_datastore(request), whose body is a DataStoreRequest "
        "(service_id, name, endpoint, authentication_method, and its credentials)."
    )


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

        Queries the route the gateway declares for *resource_type* (e.g.
        ``connected_datastores`` reads ``GET /api/v2/dspm/datastores/connected``),
        with optional filtering, sorting and offset pagination.  The route
        table is shared with :meth:`list_page`.

        Args:
            resource_type: The DSPM resource type to query.  A
                :class:`~netskope.models.dspm.DspmResourceType` or its string
                value.  ``supported_resource_types()`` lists the names with a
                declared route.
            filter_expr: DSPM filter expression, e.g. ``name eq 'prod-db'``.
            sort_by: Field name to sort by (e.g. ``name``).
            sort_order: ``"asc"`` or ``"desc"`` — only applies with *sort_by*.
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            The raw ``{"success": ..., "data": {"total": ..., "results": [...]}}``
            body.

        Raises:
            netskope.exceptions.ValidationError: If *resource_type* is unknown
                or has no declared route.
        """
        from netskope.resources._dspm_response import _prepare

        path, _model, params = _prepare(
            resource_type, filter_expr, sort_by, sort_order, limit, offset
        )
        return self._get(path, **params)

    def analytics(
        self,
        metric_type: str,
        *,
        filter_expr: str | None = None,
        sort_by: str | None = None,
        sort_order: SortOrder | str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Read a connected-datastore analytics report.

        Two reports are declared:

        ``"sensitivity_score_distribution"``
            ``GET /api/v2/dspm/datastores/connected/sensitivityscoresdistribution``
            — takes no parameters.
        ``"privilege_risks"``
            ``GET /api/v2/dspm/datastores/connected/privilegerisks`` — takes
            ``filter``, ``sortby``, ``sortorder``, ``limit`` and ``offset``.

        Args:
            metric_type: The report name, one of the two above.
            filter_expr: Filter expression (``privilege_risks`` only).
            sort_by: Field to sort by (``privilege_risks`` only).
            sort_order: ``"asc"`` or ``"desc"`` (``privilege_risks`` only).
            limit: Maximum number of records (``privilege_risks`` only).
            offset: Records to skip (``privilege_risks`` only).

        Raises:
            netskope.exceptions.ValidationError: If *metric_type* is not one of
                the declared reports, or a parameter is passed to the report
                that does not accept it.
        """
        path = _analytics_path(metric_type)
        params = _build_list_params(filter_expr, sort_by, sort_order, limit, offset)
        if params and metric_type != "privilege_risks":
            raise ValidationError(f"The DSPM {metric_type} report takes no query parameters.")
        return self._get(path, **params)

    def connect_datastore(self, request: dict[str, Any]) -> dict[str, Any]:
        """Connect one discovered datastore for DSPM monitoring.

        Sends ``POST /api/v2/dspm/datastores/connected`` with *request* as the
        ``DataStoreRequest`` body (``service_id``, ``name``, ``endpoint``,
        ``authentication_method`` and the credentials the method needs).  The
        body is passed through unchanged so tenant-specific fields survive.

        Args:
            request: The ``DataStoreRequest`` body.
        """
        if not isinstance(request, dict) or not request:
            raise ValidationError("connect_datastore requires a DataStoreRequest body.")
        return self._post(_CONNECTED_DATASTORES_PATH, json=request)

    def connect_datastores(self, ids: list[str]) -> dict[str, Any]:
        """Not available — DSPM has no bulk connect-by-id operation.

        Raises:
            netskope.exceptions.ValidationError: Always.  Use
                :meth:`connect_datastore` with a ``DataStoreRequest`` body.
        """
        raise _connect_unsupported()

    def scan_datastores(self, ids: list[str]) -> None:
        """Start a classification scan on each connected datastore in *ids*.

        The gateway's start-scan operation takes exactly one datastore, so this
        issues one ``POST /api/v2/dspm/datastores/connected/startscan`` per id,
        in order, and stops at the first failure.  HTTP 202 acknowledges the
        request; it does not mean the scan finished.

        Args:
            ids: Connected-datastore identifiers to scan.
        """
        for datastore_id in ids:
            self.start_scan(datastore_id)


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
        from netskope.resources._dspm_response import _prepare

        path, _model, params = _prepare(
            resource_type, filter_expr, sort_by, sort_order, limit, offset
        )
        return await self._get(path, **params)

    async def analytics(
        self,
        metric_type: str,
        *,
        filter_expr: str | None = None,
        sort_by: str | None = None,
        sort_order: SortOrder | str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Read a connected-datastore analytics report.

        See :meth:`DspmResource.analytics`.
        """
        path = _analytics_path(metric_type)
        params = _build_list_params(filter_expr, sort_by, sort_order, limit, offset)
        if params and metric_type != "privilege_risks":
            raise ValidationError(f"The DSPM {metric_type} report takes no query parameters.")
        return await self._get(path, **params)

    async def connect_datastore(self, request: dict[str, Any]) -> dict[str, Any]:
        """Connect one discovered datastore for DSPM monitoring.

        See :meth:`DspmResource.connect_datastore`.
        """
        if not isinstance(request, dict) or not request:
            raise ValidationError("connect_datastore requires a DataStoreRequest body.")
        return await self._post(_CONNECTED_DATASTORES_PATH, json=request)

    async def connect_datastores(self, ids: list[str]) -> dict[str, Any]:
        """Not available — DSPM has no bulk connect-by-id operation.

        See :meth:`DspmResource.connect_datastores`.
        """
        raise _connect_unsupported()

    async def scan_datastores(self, ids: list[str]) -> None:
        """Start a classification scan on each connected datastore in *ids*.

        See :meth:`DspmResource.scan_datastores`.
        """
        for datastore_id in ids:
            await self.start_scan(datastore_id)
