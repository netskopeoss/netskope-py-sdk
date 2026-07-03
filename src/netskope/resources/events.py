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

import re
from datetime import datetime
from typing import Any

from netskope._pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.exceptions import NotFoundError, ValidationError
from netskope.models.events import AuditEvent, Event, EventType, NetworkEvent, PageEvent
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import extract_list

_DATASEARCH_BASE = "/api/v2/events/datasearch"
_AUDIT_PATH = "/api/v2/events/data/audit"
_INFRASTRUCTURE_PATH = "/api/v2/events/data/infrastructure"
_TRANSACTION_PATH = "/api/v2/events/metrics/transactionevents"

_HEX_ID_RE = re.compile(r"^[a-fA-F0-9]+$")

_MODEL_MAP: dict[str, type[Event]] = {
    "network": NetworkEvent,
    "page": PageEvent,
    "audit": AuditEvent,
}

# Event types not served by /events/datasearch/{type}:
# - audit uses /events/data/audit with a ``type`` filter instead of JQL;
# - infrastructure uses /events/data/infrastructure (same params as datasearch);
# - transaction uses /events/metrics/transactionevents (aggregated metrics only —
#   individual transaction events are delivered via PubSub streaming, not REST).
_PATH_OVERRIDES: dict[str, str] = {
    EventType.AUDIT.value: _AUDIT_PATH,
    EventType.INFRASTRUCTURE.value: _INFRASTRUCTURE_PATH,
    EventType.TRANSACTION.value: _TRANSACTION_PATH,
}


def _validate_event_type(event_type: str | EventType) -> str:
    et = str(event_type)
    valid = {e.value for e in EventType}
    if et not in valid:
        raise ValidationError(f"Invalid event_type: {et!r}. Must be one of {sorted(valid)}")
    return et


def _build_params(
    query: str | None = None,
    fields: list[str] | None = None,
    start_time: datetime | int | None = None,
    end_time: datetime | int | None = None,
    group_by: str | list[str] | None = None,
    order_by: str | None = None,
    descending: bool = True,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if query:
        params["query"] = query
    if fields:
        params["fields"] = ",".join(fields)
    if start_time is not None:
        params["starttime"] = (
            int(start_time.timestamp()) if isinstance(start_time, datetime) else start_time
        )
    if end_time is not None:
        params["endtime"] = (
            int(end_time.timestamp()) if isinstance(end_time, datetime) else end_time
        )
    if group_by:
        params["groupbys"] = group_by if isinstance(group_by, str) else ",".join(group_by)
    if order_by:
        params["sortby"] = f"{order_by} {'DESC' if descending else 'ASC'}"
    return params


def _prepare_list(
    event_type: str | EventType,
    query: str | None,
    fields: list[str] | None,
    start_time: datetime | int | None,
    end_time: datetime | int | None,
    group_by: str | list[str] | None,
    order_by: str | None,
    descending: bool,
    audit_type: str | None,
) -> tuple[str, type[Event], dict[str, Any]]:
    """Resolve the endpoint path, model, and query params for a list() call."""
    et = _validate_event_type(event_type)
    if et == EventType.AUDIT.value:
        if query is not None:
            raise ValidationError(
                "The audit event type does not support JQL queries; "
                "use audit_type to filter instead."
            )
        params = _build_params(None, fields, start_time, end_time, group_by, order_by, descending)
        if audit_type is not None:
            params["type"] = audit_type
    else:
        params = _build_params(query, fields, start_time, end_time, group_by, order_by, descending)
    path = _PATH_OVERRIDES.get(et, f"{_DATASEARCH_BASE}/{et}")
    return path, _MODEL_MAP.get(et, Event), params


def _prepare_get(event_id: str, event_type: str | EventType) -> tuple[str, type[Event]]:
    """Resolve the endpoint path and model for a get() call, validating inputs."""
    et = _validate_event_type(event_type)
    if et in (EventType.AUDIT.value, EventType.TRANSACTION.value):
        raise ValidationError(f"Event type {et!r} does not support lookup by ID (no JQL support).")
    if not _HEX_ID_RE.match(event_id):
        raise ValidationError(f"Invalid event_id format: {event_id!r}. Expected a hex string.")
    return f"{_DATASEARCH_BASE}/{et}", _MODEL_MAP.get(et, Event)


class EventsResource(SyncResource):
    """Synchronous interface to the ``/api/v2/events`` endpoints."""

    def list(
        self,
        event_type: str | EventType = EventType.APPLICATION,
        *,
        query: str | None = None,
        fields: list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        group_by: str | list[str] | None = None,
        order_by: str | None = None,
        descending: bool = True,
        audit_type: str | None = None,
        page_size: int = 100,
    ) -> SyncPaginatedResponse[Event]:
        """List events of a given type with optional JQL filtering.

        Most event types query ``/api/v2/events/datasearch/{type}``.
        Exceptions:

        - ``audit`` queries ``/api/v2/events/data/audit`` and filters with
          *audit_type* (the endpoint's ``type`` param) instead of *query*;
        - ``infrastructure`` queries ``/api/v2/events/data/infrastructure``;
        - ``transaction`` queries ``/api/v2/events/metrics/transactionevents``,
          which returns aggregated metrics only (individual transaction
          events are delivered via PubSub streaming, not REST).

        Args:
            event_type: The event category (e.g. ``"application"``,
                ``"network"``, ``"page"``, ``"alert"``).
            query: A JQL filter expression (not supported for ``audit``).
            fields: Specific fields to return.
            start_time: Start of the time range.
            end_time: End of the time range.
            group_by: Field(s) to aggregate results by.
            order_by: Field to sort by.
            descending: Sort direction.
            audit_type: Audit event type filter (``audit`` only), e.g.
                ``"admin"`` or ``"user"``.
            page_size: Number of results per API call.

        Returns:
            A lazy paginated iterator of :class:`~netskope.models.events.Event`
            (or a type-specific subclass).

        Raises:
            netskope.exceptions.ValidationError: If *event_type* is unknown,
                or if *query* is supplied for the ``audit`` event type.
        """
        path, model, params = _prepare_list(
            event_type,
            query,
            fields,
            start_time,
            end_time,
            group_by,
            order_by,
            descending,
            audit_type,
        )
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=path,
            params=params,
            model=model,
            page_size=page_size,
            extract=extract_list,
        )

    def get(
        self,
        event_id: str,
        *,
        event_type: str | EventType = EventType.APPLICATION,
    ) -> Event:
        """Get a single event by ID.

        Args:
            event_id: The ``_id`` of the event (a hex string).
            event_type: The event category to search in.

        Returns:
            An :class:`~netskope.models.events.Event` (or type-specific
            subclass) instance.

        Raises:
            netskope.exceptions.NotFoundError: If the event does not exist.
            netskope.exceptions.ValidationError: If *event_id* is not a hex
                string, or *event_type* is ``audit``/``transaction`` (which
                do not support JQL lookup by ID).
        """
        path, model = _prepare_get(event_id, event_type)
        body = self._get(path, query=f'_id eq "{event_id}"', limit=1)
        items = extract_list(body)
        if not items:
            raise NotFoundError(f"Event {event_id!r} not found", status_code=404)
        return model.model_validate(items[0])


class AsyncEventsResource(AsyncResource):
    """Asynchronous interface to the ``/api/v2/events`` endpoints."""

    def list(
        self,
        event_type: str | EventType = EventType.APPLICATION,
        *,
        query: str | None = None,
        fields: list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        group_by: str | list[str] | None = None,
        order_by: str | None = None,
        descending: bool = True,
        audit_type: str | None = None,
        page_size: int = 100,
    ) -> AsyncPaginatedResponse[Event]:
        """List events of a given type with optional JQL filtering.

        See :meth:`EventsResource.list` for endpoint routing details.
        """
        path, model, params = _prepare_list(
            event_type,
            query,
            fields,
            start_time,
            end_time,
            group_by,
            order_by,
            descending,
            audit_type,
        )
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=path,
            params=params,
            model=model,
            page_size=page_size,
            extract=extract_list,
        )

    async def get(
        self,
        event_id: str,
        *,
        event_type: str | EventType = EventType.APPLICATION,
    ) -> Event:
        """Get a single event by ID.

        See :meth:`EventsResource.get`.
        """
        path, model = _prepare_get(event_id, event_type)
        body = await self._get(path, query=f'_id eq "{event_id}"', limit=1)
        items = extract_list(body)
        if not items:
            raise NotFoundError(f"Event {event_id!r} not found", status_code=404)
        return model.model_validate(items[0])
