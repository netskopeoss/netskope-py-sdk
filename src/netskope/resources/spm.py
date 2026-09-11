"""SPM resource — SaaS Security Posture Management.

SPM assesses the security posture of connected SaaS applications: it scores
each app against posture rules, tracks configuration drift, and exposes an
inventory of discovered SaaS resources.  All methods return the raw JSON
response body as a ``dict`` (no typed models), so forward-compatible fields
are preserved verbatim.

Every method addresses an operation declared in the SPM gateway contract:

=========================  ==============================================
``inventory``              ``POST /inventory/getresources``
``list_apps``              ``POST /inventory/getresources`` (per instance)
``get_app``                ``POST /inventory/getresources`` (one app)
``posture_score``          ``POST /results/getposturescores``
``list_policy_rules``      ``GET  /rules/list``
``recent_changes``         ``POST /apps/recentchanges/getstats``
=========================  ==============================================

Example::

    apps = client.spm.list_apps()
    detail = client.spm.get_app("Microsoft 365")
    score = client.spm.posture_score()
    changes = client.spm.recent_changes(start=1758127874, end=1759127874)
"""

from __future__ import annotations

import functools
from datetime import datetime
from typing import TYPE_CHECKING, Any

from netskope.exceptions import ValidationError
from netskope.resources._base import AsyncResource, SyncResource

if TYPE_CHECKING:
    from netskope.resources._spm_response import AsyncSpmResponses, SpmResponses

_INVENTORY_PATH = "/api/v2/spm/inventory/getresources"
_POSTURE_SCORE_PATH = "/api/v2/spm/results/getposturescores"
_POLICY_RULES_PATH = "/api/v2/spm/rules/list"
_RECENT_CHANGES_PATH = "/api/v2/spm/apps/recentchanges/getstats"

# ``ResourceAggregationRequest.group_by`` (spm/inventory.yaml:322-330) and the
# fields each grouping accepts (the ``fields`` description, :286-299).
_GROUP_BY_FIELDS: dict[str, tuple[str, ...]] = {
    "instance_name": (
        "instance_name",
        "app_suite",
        "total_checked_rules",
        "passed_rules",
        "failed_rules",
        "failed_muted_rules",
        "failed_critical_rules",
        "failed_high_rules",
        "failed_medium_rules",
        "failed_low_rules",
        "unknown_rules",
    ),
    "resource_type": (
        "resource_type",
        "app_suite",
        "app_name",
        "total_resources",
        "total_checked_rules",
        "passed_rules",
        "failed_rules",
        "failed_muted_rules",
        "failed_critical_rules",
        "failed_high_rules",
        "failed_medium_rules",
        "failed_low_rules",
        "unknown_rules",
    ),
    "resource_name": (
        "resource_name",
        "resource_id",
        "app_suite",
        "app_name",
        "region_id",
        "region_name",
        "netskope_instance_name",
        "instance_name",
        "instance_id",
        "resource_type",
        "parent_res_type",
    ),
}

_POLICY_RULE_VIEWS = ("latest", "applied")
_SORT_ORDERS = ("asc", "desc")


def _epoch_seconds(value: datetime | int, name: str) -> int:
    """Return *value* as epoch **seconds**, converting an aware ``datetime``."""
    if isinstance(value, bool) or not isinstance(value, (datetime, int)):
        raise ValidationError(f"{name} must be epoch seconds or a datetime.")
    if isinstance(value, datetime):
        return int(value.timestamp())
    return value


def _positive_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{name} must be a nonnegative integer.")
    return value


def _inventory_body(
    *,
    fields: list[str] | None,
    group_by: str,
    limit: int,
    offset: int,
    filters: dict[str, Any] | None,
    ngl_query: str | None,
    sort: list[dict[str, Any]] | None,
    timestamp: int | None,
    past_view: bool | None,
) -> dict[str, Any]:
    """Build the ``ResourceAggregationRequest`` body (spm/inventory.yaml:284-386).

    ``offset``, ``fields``, ``limit`` and ``group_by`` are required by the
    schema, so they are always sent.  ``filters`` and ``ngl_query`` are
    mutually exclusive, and ``ngl_query`` works only with
    ``group_by="resource_name"``.
    """
    if group_by not in _GROUP_BY_FIELDS:
        valid = ", ".join(_GROUP_BY_FIELDS)
        raise ValidationError(f"Invalid group_by {group_by!r}. Must be one of: {valid}")
    if filters is not None and ngl_query is not None:
        raise ValidationError("filters and ngl_query are mutually exclusive.")
    if ngl_query is not None and group_by != "resource_name":
        raise ValidationError('ngl_query is supported only with group_by="resource_name".')
    selected = list(fields) if fields else list(_GROUP_BY_FIELDS[group_by])
    if not selected:
        raise ValidationError("fields must name at least one inventory column.")
    body: dict[str, Any] = {
        "fields": selected,
        "group_by": group_by,
        "limit": _positive_int(limit, "limit"),
        "offset": _positive_int(offset, "offset"),
    }
    if filters is not None:
        body["filters"] = filters
    if ngl_query is not None:
        body["ngl_query"] = ngl_query
    if sort is not None:
        body["sort"] = list(sort)
    if timestamp is not None:
        body["timestamp"] = timestamp
    if past_view is not None:
        body["past_view"] = past_view
    return body


def _apps_body(limit: int, offset: int) -> dict[str, Any]:
    """Aggregate the inventory by SaaS instance — one row per connected app."""
    return _inventory_body(
        fields=None,
        group_by="instance_name",
        limit=limit,
        offset=offset,
        filters=None,
        ngl_query=None,
        sort=None,
        timestamp=None,
        past_view=None,
    )


def _app_body(app_name: str, limit: int, offset: int) -> dict[str, Any]:
    """Aggregate one application's resources by type.

    ``app_name`` is a ``{operator, values}`` filter — the only form
    ``ResourceAggregationRequest.filters`` accepts (spm/inventory.yaml:300-321).
    """
    if not isinstance(app_name, str) or not app_name.strip():
        raise ValidationError("app_name must be a nonempty application name.")
    return _inventory_body(
        fields=None,
        group_by="resource_type",
        limit=limit,
        offset=offset,
        filters={"app_name": {"operator": "equal", "values": [app_name]}},
        ngl_query=None,
        sort=None,
        timestamp=None,
        past_view=None,
    )


def _posture_score_body(
    app_names: list[str] | None,
    appsuite_names: list[str] | None,
    instance_names: list[str] | None,
    posture_confidence_level: list[str] | None,
    timestamp: int | None,
) -> dict[str, Any]:
    """Build ``GetPostureScoresRequestBody`` (spm/saas_posture_score.yaml:26-46).

    Every field is optional; an empty object asks for the whole tenant.
    """
    filters: dict[str, Any] = {}
    for key, values in (
        ("app_names", app_names),
        ("appsuite_names", appsuite_names),
        ("instance_names", instance_names),
        ("posture_confidence_level", posture_confidence_level),
    ):
        if values is not None:
            filters[key] = list(values)
    body: dict[str, Any] = {}
    if filters:
        body["filters"] = filters
    if timestamp is not None:
        body["timestamp"] = timestamp
    return body


def _policy_rule_params(
    appsuite: str | None,
    filter: str | None,
    limit: int | None,
    view: str | None,
    sort_order: str | None,
    include_templates: bool | None,
    offset: int | None,
) -> dict[str, Any]:
    """Build the ``GET /rules/list`` query (spm/policy.yaml:2833-2905)."""
    if view is not None and view not in _POLICY_RULE_VIEWS:
        raise ValidationError(f"view must be one of: {', '.join(_POLICY_RULE_VIEWS)}")
    if sort_order is not None and sort_order not in _SORT_ORDERS:
        raise ValidationError(f"sort_order must be one of: {', '.join(_SORT_ORDERS)}")
    params: dict[str, Any] = {}
    if appsuite is not None:
        params["appsuite"] = appsuite
    if filter is not None:
        params["filter"] = filter
    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int) or not (limit == -1 or limit >= 0):
            raise ValidationError("limit must be a nonnegative integer, or -1 for every rule.")
        if limit > 1000:
            raise ValidationError("limit must not exceed 1000.")
        params["limit"] = limit
    if view is not None:
        params["view"] = view
    if sort_order is not None:
        params["sortorder"] = sort_order
    if include_templates is not None:
        params["include_templates"] = include_templates
    if offset is not None:
        params["offset"] = _positive_int(offset, "offset")
    return params


def _recent_changes_body(
    start: datetime | int | None,
    end: datetime | int | None,
    app_name: str | None,
    instance_name: str | None,
) -> dict[str, Any]:
    """Build ``RecentChangesRequest`` (spm/apps.yaml:616-649).

    ``time_range`` is required and both of its bounds are required, so a
    window must be supplied.
    """
    if start is None or end is None:
        raise ValidationError(
            "SPM recent changes requires a time range: pass start= and end= "
            "as epoch seconds or datetimes."
        )
    window = {"start": _epoch_seconds(start, "start"), "end": _epoch_seconds(end, "end")}
    if window["end"] < window["start"]:
        raise ValidationError("end must not precede start.")
    body: dict[str, Any] = {"time_range": window}
    filters: dict[str, Any] = {}
    if app_name is not None:
        filters["app_name"] = app_name
    if instance_name is not None:
        filters["instance_name"] = instance_name
    if filters:
        body["filters"] = filters
    return body


class SpmResource(SyncResource):
    """Synchronous interface to the SaaS Security Posture Management API."""

    @functools.cached_property
    def with_response(self) -> SpmResponses:
        from netskope.resources._spm_response import SpmResponses

        return SpmResponses(self._transport)

    def list_apps(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """List the SaaS instances SPM monitors, with their rule counters.

        Sends ``POST /api/v2/spm/inventory/getresources`` grouped by
        ``instance_name``.  SPM has no ``/apps`` collection; the inventory
        aggregation is the surface that enumerates connected instances.

        Args:
            limit: Maximum number of rows to return (schema default 50).
            offset: Rows to skip before collecting the result set.

        Returns:
            The raw ``ResourceAggregationResponse`` body — ``data``,
            ``next_offset``, and ``total_count`` when *offset* is 0.
        """
        return self._post(_INVENTORY_PATH, json=_apps_body(limit, offset), retry_safe=True)

    def get_app(self, app_name: str, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """Get one application's resources, aggregated by resource type.

        Sends ``POST /api/v2/spm/inventory/getresources`` with
        ``filters={"app_name": {"operator": "equal", "values": [app_name]}}``.

        Args:
            app_name: The application name exactly as it appears in the SPM
                dashboard (e.g. ``"Microsoft 365"``, ``"Salesforce"``).
            limit: Maximum number of rows to return.
            offset: Rows to skip before collecting the result set.
        """
        return self._post(_INVENTORY_PATH, json=_app_body(app_name, limit, offset), retry_safe=True)

    def inventory(
        self,
        *,
        filter: str | None = None,
        fields: list[str] | None = None,
        group_by: str = "resource_name",
        limit: int = 50,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
        ngl_query: str | None = None,
        sort: list[dict[str, Any]] | None = None,
        timestamp: int | None = None,
        past_view: bool | None = None,
    ) -> dict[str, Any]:
        """Query the SaaS resource inventory.

        Sends ``POST /api/v2/spm/inventory/getresources``.  The schema requires
        ``fields``, ``group_by``, ``limit`` and ``offset``, so all four are
        always sent; *fields* defaults to the column set the chosen *group_by*
        documents.

        Args:
            filter: Deprecated alias for *ngl_query* — the only free-text
                search the operation offers.  It requires the default
                ``group_by="resource_name"``.
            fields: Columns to return.  Defaults to the documented set for
                *group_by*.
            group_by: ``"instance_name"``, ``"resource_type"``, or
                ``"resource_name"`` (default).
            limit: Maximum number of rows to return.
            offset: Rows to skip before collecting the result set.
            filters: Column filters as ``{column: {"operator": ..., "values":
                [...]}}``.  Mutually exclusive with *ngl_query*/*filter*.
            ngl_query: NGL search string; ``group_by`` must be
                ``"resource_name"``.
            sort: ``[{"column": ..., "sort_order": "asc"|"desc"}]``.
            timestamp: Epoch time for an as-of-date view.
            past_view: Ask for a past view (requires *timestamp*).

        Raises:
            netskope.exceptions.ValidationError: If *group_by* is unknown, or
                both a filter object and an NGL query are supplied.
        """
        body = _inventory_body(
            fields=fields,
            group_by=group_by,
            limit=limit,
            offset=offset,
            filters=filters,
            ngl_query=ngl_query if filter is None else filter,
            sort=sort,
            timestamp=timestamp,
            past_view=past_view,
        )
        return self._post(_INVENTORY_PATH, json=body, retry_safe=True)

    def posture_score(
        self,
        *,
        app_names: list[str] | None = None,
        appsuite_names: list[str] | None = None,
        instance_names: list[str] | None = None,
        posture_confidence_level: list[str] | None = None,
        timestamp: int | None = None,
    ) -> dict[str, Any]:
        """Get SaaS posture scores for the tenant and its app suites.

        Sends ``POST /api/v2/spm/results/getposturescores``.  Every filter is
        optional; with none, the whole tenant is scored.

        Args:
            app_names: Restrict to these application names.
            appsuite_names: Restrict to these app suites.
            instance_names: Restrict to these instances.
            posture_confidence_level: Restrict to these confidence levels.
            timestamp: UTC **milliseconds** up to which the score is computed.
        """
        body = _posture_score_body(
            app_names, appsuite_names, instance_names, posture_confidence_level, timestamp
        )
        return self._post(_POSTURE_SCORE_PATH, json=body, retry_safe=True)

    def list_policy_rules(
        self,
        *,
        appsuite: str | None = None,
        filter: str | None = None,
        limit: int | None = None,
        view: str | None = None,
        sort_order: str | None = None,
        include_templates: bool | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List posture policy rules with minimal detail.

        Sends ``GET /api/v2/spm/rules/list``.

        Args:
            appsuite: Restrict to one application suite.
            filter: Search string matched against rule names.
            limit: Rules per page (API default 100, max 1000; ``-1`` for all).
            view: ``"latest"`` or ``"applied"`` (API default ``"applied"``).
            sort_order: ``"asc"`` or ``"desc"``.
            include_templates: Include template rules in the response.
            offset: Rules to skip before collecting the result set.

        Returns:
            The raw ``RulesSummaryList`` body — ``rules`` and ``next_offset``.
        """
        params = _policy_rule_params(
            appsuite, filter, limit, view, sort_order, include_templates, offset
        )
        return self._get(_POLICY_RULES_PATH, **params)

    def recent_changes(
        self,
        *,
        start: datetime | int | None = None,
        end: datetime | int | None = None,
        app_name: str | None = None,
        instance_name: str | None = None,
    ) -> dict[str, Any]:
        """Get statistics on recent SaaS configuration changes.

        Sends ``POST /api/v2/spm/apps/recentchanges/getstats``.  The operation
        requires a ``time_range``, so *start* and *end* must both be supplied.

        Args:
            start: Window start, epoch **seconds** or an aware ``datetime``.
            end: Window end, epoch **seconds** or an aware ``datetime``.
            app_name: Narrow the statistics to one SaaS app suite.
            instance_name: Narrow the statistics to one instance.

        Raises:
            netskope.exceptions.ValidationError: If the time range is missing
                or inverted.
        """
        body = _recent_changes_body(start, end, app_name, instance_name)
        return self._post(_RECENT_CHANGES_PATH, json=body, retry_safe=True)


class AsyncSpmResource(AsyncResource):
    """Asynchronous interface to the SaaS Security Posture Management API."""

    @functools.cached_property
    def with_response(self) -> AsyncSpmResponses:
        from netskope.resources._spm_response import AsyncSpmResponses

        return AsyncSpmResponses(self._transport)

    async def list_apps(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """List the SaaS instances SPM monitors.

        See :meth:`SpmResource.list_apps`.
        """
        return await self._post(_INVENTORY_PATH, json=_apps_body(limit, offset), retry_safe=True)

    async def get_app(self, app_name: str, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """Get one application's resources, aggregated by resource type.

        See :meth:`SpmResource.get_app`.
        """
        return await self._post(
            _INVENTORY_PATH, json=_app_body(app_name, limit, offset), retry_safe=True
        )

    async def inventory(
        self,
        *,
        filter: str | None = None,
        fields: list[str] | None = None,
        group_by: str = "resource_name",
        limit: int = 50,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
        ngl_query: str | None = None,
        sort: list[dict[str, Any]] | None = None,
        timestamp: int | None = None,
        past_view: bool | None = None,
    ) -> dict[str, Any]:
        """Query the SaaS resource inventory.

        See :meth:`SpmResource.inventory`.
        """
        body = _inventory_body(
            fields=fields,
            group_by=group_by,
            limit=limit,
            offset=offset,
            filters=filters,
            ngl_query=ngl_query if filter is None else filter,
            sort=sort,
            timestamp=timestamp,
            past_view=past_view,
        )
        return await self._post(_INVENTORY_PATH, json=body, retry_safe=True)

    async def posture_score(
        self,
        *,
        app_names: list[str] | None = None,
        appsuite_names: list[str] | None = None,
        instance_names: list[str] | None = None,
        posture_confidence_level: list[str] | None = None,
        timestamp: int | None = None,
    ) -> dict[str, Any]:
        """Get SaaS posture scores for the tenant and its app suites.

        See :meth:`SpmResource.posture_score`.
        """
        body = _posture_score_body(
            app_names, appsuite_names, instance_names, posture_confidence_level, timestamp
        )
        return await self._post(_POSTURE_SCORE_PATH, json=body, retry_safe=True)

    async def list_policy_rules(
        self,
        *,
        appsuite: str | None = None,
        filter: str | None = None,
        limit: int | None = None,
        view: str | None = None,
        sort_order: str | None = None,
        include_templates: bool | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List posture policy rules with minimal detail.

        See :meth:`SpmResource.list_policy_rules`.
        """
        params = _policy_rule_params(
            appsuite, filter, limit, view, sort_order, include_templates, offset
        )
        return await self._get(_POLICY_RULES_PATH, **params)

    async def recent_changes(
        self,
        *,
        start: datetime | int | None = None,
        end: datetime | int | None = None,
        app_name: str | None = None,
        instance_name: str | None = None,
    ) -> dict[str, Any]:
        """Get statistics on recent SaaS configuration changes.

        See :meth:`SpmResource.recent_changes`.
        """
        body = _recent_changes_body(start, end, app_name, instance_name)
        return await self._post(_RECENT_CHANGES_PATH, json=body, retry_safe=True)
