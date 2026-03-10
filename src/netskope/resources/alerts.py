"""Alerts resource — query and manage security alerts.

Example::

    # List all high-severity alerts from the last 24 hours
    for alert in client.alerts.list(query='severity eq "high"'):
        print(f"{alert.alert_name} — {alert.user}")

    # Get aggregate summary
    summary = client.alerts.summary(group_by="alert_type")
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from netskope._pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.models.alerts import Alert
from netskope.resources._base import AsyncResource, SyncResource

_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")

_PATH = "/api/v2/events/datasearch/alert"


def _build_params(
    query: str | None = None,
    fields: list[str] | None = None,
    start_time: datetime | int | None = None,
    end_time: datetime | int | None = None,
    group_by: str | None = None,
    order_by: str | None = None,
    descending: bool = True,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if query:
        params["query"] = query
    if fields:
        params["fields"] = ",".join(fields)
    if start_time:
        params["starttime"] = (
            int(start_time.timestamp()) if isinstance(start_time, datetime) else start_time
        )
    if end_time:
        params["endtime"] = (
            int(end_time.timestamp()) if isinstance(end_time, datetime) else end_time
        )
    if group_by:
        params["groupby"] = group_by
    if order_by:
        params["sortby"] = order_by
        params["sortorder"] = "desc" if descending else "asc"
    return params


def _extract_alerts(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract alert items from the datasearch response envelope."""
    result = body.get("result", [])
    if isinstance(result, list):
        return result
    data = body.get("data", [])
    if isinstance(data, list):
        return data
    return []


class AlertsResource(SyncResource):
    """Synchronous interface to ``/api/v2/events/datasearch/alert``."""

    def list(
        self,
        *,
        query: str | None = None,
        fields: list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        group_by: str | None = None,
        order_by: str | None = None,
        descending: bool = True,
        page_size: int = 100,
    ) -> SyncPaginatedResponse[Alert]:
        """List alerts with optional JQL filtering and pagination.

        Args:
            query: A JQL filter expression (e.g. ``'severity eq "high"'``).
            fields: Specific fields to return.
            start_time: Start of the time range (datetime or epoch int).
            end_time: End of the time range.
            group_by: Field to aggregate results by.
            order_by: Field to sort by.
            descending: Sort direction (default descending).
            page_size: Number of results per API call.

        Returns:
            A lazy paginated iterator of :class:`~netskope.models.alerts.Alert`.
        """
        params = _build_params(query, fields, start_time, end_time, group_by, order_by, descending)
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_PATH,
            params=params,
            model=Alert,
            page_size=page_size,
            extract=_extract_alerts,
        )

    def get(self, alert_id: str) -> Alert:
        """Get a single alert by ID.

        Args:
            alert_id: The ``_id`` of the alert.

        Returns:
            An :class:`~netskope.models.alerts.Alert` instance.

        Raises:
            netskope.exceptions.NotFoundError: If the alert does not exist.
            netskope.exceptions.ValidationError: If the alert_id format is invalid.
        """
        from netskope.exceptions import NotFoundError, ValidationError

        if not _SAFE_ID_RE.match(alert_id):
            raise ValidationError(f"Invalid alert_id format: {alert_id!r}")
        body = self._get(_PATH, query=f'_id eq "{alert_id}"')
        items = _extract_alerts(body)
        if not items:
            raise NotFoundError(
                f"Alert {alert_id!r} not found",
                status_code=404,
            )
        return Alert.model_validate(items[0])


class AsyncAlertsResource(AsyncResource):
    """Asynchronous interface to ``/api/v2/events/datasearch/alert``."""

    def list(
        self,
        *,
        query: str | None = None,
        fields: list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        group_by: str | None = None,
        order_by: str | None = None,
        descending: bool = True,
        page_size: int = 100,
    ) -> AsyncPaginatedResponse[Alert]:
        """List alerts with optional JQL filtering and pagination."""
        params = _build_params(query, fields, start_time, end_time, group_by, order_by, descending)
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_PATH,
            params=params,
            model=Alert,
            page_size=page_size,
            extract=_extract_alerts,
        )

    async def get(self, alert_id: str) -> Alert:
        """Get a single alert by ID."""
        from netskope.exceptions import NotFoundError, ValidationError

        if not _SAFE_ID_RE.match(alert_id):
            raise ValidationError(f"Invalid alert_id format: {alert_id!r}")
        body = await self._get(_PATH, query=f'_id eq "{alert_id}"')
        items = _extract_alerts(body)
        if not items:
            raise NotFoundError(
                f"Alert {alert_id!r} not found",
                status_code=404,
            )
        return Alert.model_validate(items[0])
