"""The alerts sub-namespace of dem."""

from __future__ import annotations

import builtins
import functools
from typing import Any

from netskope.core.ids import extract_item, extract_list, quote_id
from netskope.core.resource import AsyncResource, SyncResource
from netskope.models.dem import (
    SORT_ORDERS,
    DemAlert,
)
from netskope.resources.dem.decoder import (
    AsyncDemAlertResponses,
    DemAlertResponses,
)
from netskope.resources.dem.paths import (
    _ALERTS_PATH,
    _GETALERTS_PATH,
    _enum_value,
    _getalerts_body,
)


class DemAlertsResource(SyncResource):
    """DEM experience alerts (triggered instances) — ``/api/v2/dem/alerts``."""

    @functools.cached_property
    def with_response(self) -> DemAlertResponses:
        """Inspect one completed request together with its typed result."""

        return DemAlertResponses(self._transport)

    def search(
        self,
        *,
        alert_category: builtins.list[str] | None = None,
        alert_type: builtins.list[str] | None = None,
        severity: builtins.list[str] | None = None,
        open_time: int | None = None,
        sort_field: str | None = None,
        sort_desc: bool = True,
        limit: int = 10,
        offset: int | None = None,
    ) -> builtins.list[DemAlert]:
        """Search triggered experience alerts (``getalerts``)."""
        body = _getalerts_body(
            alert_category, alert_type, severity, open_time, sort_field, sort_desc, limit, offset
        )
        resp = self._post(_GETALERTS_PATH, json=body, retry_safe=True)
        return [DemAlert.model_validate(item) for item in extract_list(resp, "alerts")]

    def get(self, alert_id: str) -> DemAlert:
        """Get a single experience alert by ID."""
        resp = self._get(f"{_ALERTS_PATH}/{quote_id(alert_id)}")
        return DemAlert.model_validate(extract_item(resp))

    def entities(
        self,
        alert_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> dict[str, Any]:
        """List the entities impacted by an alert.

        Rows are ``ImpactEntity`` objects; pops, publishers, services, sites
        and tunnels (dem_alert.yaml:342-381), not users or devices.
        """
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if sort_by:
            params["sortby"] = sort_by
        if sort_order:
            params["sortorder"] = _enum_value("sort_order", sort_order, SORT_ORDERS)
        return self._get(f"{_ALERTS_PATH}/{quote_id(alert_id)}/entities", **params)


class AsyncDemAlertsResource(AsyncResource):
    """Async DEM experience alerts."""

    @functools.cached_property
    def with_response(self) -> AsyncDemAlertResponses:
        """Inspect one completed request together with its typed result."""

        return AsyncDemAlertResponses(self._transport)

    async def search(
        self,
        *,
        alert_category: builtins.list[str] | None = None,
        alert_type: builtins.list[str] | None = None,
        severity: builtins.list[str] | None = None,
        open_time: int | None = None,
        sort_field: str | None = None,
        sort_desc: bool = True,
        limit: int = 10,
        offset: int | None = None,
    ) -> builtins.list[DemAlert]:
        """See :meth:`DemAlertsResource.search`."""
        body = _getalerts_body(
            alert_category, alert_type, severity, open_time, sort_field, sort_desc, limit, offset
        )
        resp = await self._post(_GETALERTS_PATH, json=body, retry_safe=True)
        return [DemAlert.model_validate(item) for item in extract_list(resp, "alerts")]

    async def get(self, alert_id: str) -> DemAlert:
        """See :meth:`DemAlertsResource.get`."""
        resp = await self._get(f"{_ALERTS_PATH}/{quote_id(alert_id)}")
        return DemAlert.model_validate(extract_item(resp))

    async def entities(
        self,
        alert_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> dict[str, Any]:
        """See :meth:`DemAlertsResource.entities`."""
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if sort_by:
            params["sortby"] = sort_by
        if sort_order:
            params["sortorder"] = _enum_value("sort_order", sort_order, SORT_ORDERS)
        return await self._get(f"{_ALERTS_PATH}/{quote_id(alert_id)}/entities", **params)
