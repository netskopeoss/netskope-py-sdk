"""Events resource — query security events across all event types.

Example::

    # List application events
    for event in client.events.list("application"):
        print(f"{event.user} — {event.app} — {event.activity}")

    # Query network events with JQL
    events = client.events.list(
        "network",
        query='user eq "alice@example.com"',
        start_time=datetime(2026, 1, 1),
    )
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from netskope._pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.models.events import AuditEvent, Event, EventType, NetworkEvent, PageEvent
from netskope.resources._base import AsyncResource, SyncResource

_BASE = "/api/v2/events/datasearch"

_MODEL_MAP: dict[str, type[Event]] = {
    "network": NetworkEvent,
    "page": PageEvent,
    "audit": AuditEvent,
}


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


def _extract_events(body: dict[str, Any]) -> list[dict[str, Any]]:
    result = body.get("result", [])
    if isinstance(result, list):
        return result
    data = body.get("data", [])
    if isinstance(data, list):
        return data
    return []


class EventsResource(SyncResource):
    """Synchronous interface to ``/api/v2/events/datasearch/{type}``."""

    def list(
        self,
        event_type: str | EventType = EventType.APPLICATION,
        *,
        query: str | None = None,
        fields: list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        group_by: str | None = None,
        order_by: str | None = None,
        descending: bool = True,
        page_size: int = 100,
    ) -> SyncPaginatedResponse[Event]:
        """List events of a given type with optional JQL filtering.

        Args:
            event_type: The event category (e.g. ``"application"``,
                ``"network"``, ``"page"``, ``"alert"``).
            query: A JQL filter expression.
            fields: Specific fields to return.
            start_time: Start of the time range.
            end_time: End of the time range.
            group_by: Field to aggregate results by.
            order_by: Field to sort by.
            descending: Sort direction.
            page_size: Number of results per API call.

        Returns:
            A lazy paginated iterator of :class:`~netskope.models.events.Event`
            (or a type-specific subclass).
        """
        et = str(event_type)
        _valid = {e.value for e in EventType}
        if et not in _valid:
            from netskope.exceptions import ValidationError
            raise ValidationError(
                f"Invalid event_type: {et!r}. Must be one of {sorted(_valid)}"
            )
        model = _MODEL_MAP.get(et, Event)
        params = _build_params(query, fields, start_time, end_time, group_by, order_by, descending)
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=f"{_BASE}/{et}",
            params=params,
            model=model,
            page_size=page_size,
            extract=_extract_events,
        )


class AsyncEventsResource(AsyncResource):
    """Asynchronous interface to ``/api/v2/events/datasearch/{type}``."""

    def list(
        self,
        event_type: str | EventType = EventType.APPLICATION,
        *,
        query: str | None = None,
        fields: list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        group_by: str | None = None,
        order_by: str | None = None,
        descending: bool = True,
        page_size: int = 100,
    ) -> AsyncPaginatedResponse[Event]:
        """List events of a given type with optional JQL filtering."""
        et = str(event_type)
        _valid = {e.value for e in EventType}
        if et not in _valid:
            from netskope.exceptions import ValidationError
            raise ValidationError(
                f"Invalid event_type: {et!r}. Must be one of {sorted(_valid)}"
            )
        model = _MODEL_MAP.get(et, Event)
        params = _build_params(query, fields, start_time, end_time, group_by, order_by, descending)
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=f"{_BASE}/{et}",
            params=params,
            model=model,
            page_size=page_size,
            extract=_extract_events,
        )
