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
from typing import Any

from netskope.core.resource import AsyncResource, SyncResource
from netskope.resources.spm.decoder import AsyncSpmResponses, SpmResponses
from netskope.resources.spm.paths import (
    _INVENTORY_PATH,
    _POLICY_RULES_PATH,
    _POSTURE_SCORE_PATH,
    _RECENT_CHANGES_PATH,
    _app_body,
    _apps_body,
    _inventory_body,
    _ngl_search,
    _policy_rule_params,
    _posture_score_body,
    _recent_changes_body,
)

# ``ResourceAggregationRequest.group_by`` (spm/inventory.yaml:322-330) and the
# fields each grouping accepts (the ``fields`` description, :286-299).


class SpmResource(SyncResource):
    """Synchronous interface to the SaaS Security Posture Management API."""

    @functools.cached_property
    def with_response(self) -> SpmResponses:

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
            netskope.exceptions.ValidationError: If *group_by* is unknown, if
                both a filter object and an NGL query are supplied, or if
                *ngl_query* is given together with its deprecated alias
                *filter*.
        """
        body = _inventory_body(
            fields=fields,
            group_by=group_by,
            limit=limit,
            offset=offset,
            filters=filters,
            ngl_query=_ngl_search(filter, ngl_query),
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
            ngl_query=_ngl_search(filter, ngl_query),
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
