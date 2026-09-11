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

import builtins
import functools
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

from netskope._pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.datasearch import DATASEARCH_TIMEOUT_DEFAULT
from netskope.exceptions import NotFoundError, ValidationError
from netskope.models.alerts import DatasearchBucket
from netskope.models.events import (
    AuditEvent,
    ClientStatusEvent,
    Event,
    EventQueryCapabilities,
    EventType,
    IncidentEvent,
    NetworkEvent,
    PageEvent,
    TransactionMetrics,
)
from netskope.pagination import Page
from netskope.resources._alert_query import _build_params as _build_datasearch_params
from netskope.resources._alert_query import _validate_timeout
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import extract_list

if TYPE_CHECKING:
    from netskope.resources._event_response import AsyncEventResponses, EventResponses

_DATASEARCH_BASE = "/api/v2/events/datasearch"
_AUDIT_PATH = "/api/v2/events/data/audit"
_INFRASTRUCTURE_PATH = "/api/v2/events/data/infrastructure"
_TRANSACTION_PATH = "/api/v2/events/metrics/transactionevents"

_HEX_ID_RE = re.compile(r"^[a-fA-F0-9]+$")

# The single record-model table: the legacy iterator and the typed page share it,
# so one event type never decodes into two different models.
_MODEL_MAP: dict[str, type[Event]] = {
    "network": NetworkEvent,
    "page": PageEvent,
    "audit": AuditEvent,
    "clientstatus": ClientStatusEvent,
    "incident": IncidentEvent,
}

# Event types not served by /events/datasearch/{type}:
# - audit uses /events/data/audit, which takes query/limit/offset/starttime/
#   endtime/insertionstarttime/insertionendtime and nothing else
#   (events/audit.yaml:12-72);
# - infrastructure uses /events/data/infrastructure with the same parameter set
#   (events/infrastructure.yaml:12-72);
# - transaction uses /events/metrics/transactionevents, which takes only `hours`
#   and answers with a metrics object rather than records
#   (events/transaction_metrics.yaml:65-90).
_PATH_OVERRIDES: dict[str, str] = {
    EventType.AUDIT.value: _AUDIT_PATH,
    EventType.INFRASTRUCTURE.value: _INFRASTRUCTURE_PATH,
    EventType.TRANSACTION.value: _TRANSACTION_PATH,
}

_DATASEARCH_TYPES = frozenset(e.value for e in EventType) - set(_PATH_OVERRIDES)

# audit and infrastructure are the only endpoints that declare the insertion-time
# window (events/audit.yaml:51-72, events/infrastructure.yaml:51-72).
_INSERTION_TIME_TYPES = frozenset({EventType.AUDIT.value, EventType.INFRASTRUCTURE.value})

_TRANSACTION_IS_METRICS = (
    "Transaction events are hourly metrics; use transaction_metrics(hours=...)."
)


def _event_path(event_type: str | EventType) -> str:
    """Resolve one event type's endpoint from the single path table."""
    return _PATH_OVERRIDES.get(str(event_type), f"{_DATASEARCH_BASE}/{event_type}")


def _event_model(event_type: str | EventType) -> type[Event]:
    return _MODEL_MAP.get(str(event_type), Event)


def _validate_event_type(event_type: str | EventType) -> str:
    et = str(event_type)
    valid = {e.value for e in EventType}
    if et not in valid:
        raise ValidationError(f"Invalid event_type: {et!r}. Must be one of {sorted(valid)}")
    if et == EventType.TRANSACTION.value:
        raise ValidationError(_TRANSACTION_IS_METRICS)
    return et


def audit_type_query(query: str | None, audit_type: str | None) -> str | None:
    """Fold the SDK's *audit_type* convenience into the endpoint's ``query``.

    ``/events/data/audit`` has no ``type`` parameter (events/audit.yaml:12-72);
    it filters through the same ``query`` expression every other category uses,
    so the audit type travels as a JQL clause.
    """
    if audit_type is None:
        return query
    if not isinstance(audit_type, str) or not audit_type.strip() or '"' in audit_type:
        raise ValidationError("audit_type must be a nonblank string without a double quote.")
    clause = f'type eq "{audit_type}"'
    return f"({query}) and {clause}" if query else clause


def _insertion_params(
    event_type: str,
    insertion_start_time: datetime | int | None,
    insertion_end_time: datetime | int | None,
) -> dict[str, Any]:
    supplied = insertion_start_time is not None or insertion_end_time is not None
    if supplied and event_type not in _INSERTION_TIME_TYPES:
        raise ValidationError(
            f"{event_type} events do not support insertion-time bounds; "
            f"they are declared only for {', '.join(sorted(_INSERTION_TIME_TYPES))}."
        )
    params: dict[str, Any] = {}
    for key, bound in (
        ("insertionstarttime", insertion_start_time),
        ("insertionendtime", insertion_end_time),
    ):
        if bound is not None:
            params[key] = int(bound.timestamp()) if isinstance(bound, datetime) else bound
    return params


def _build_params(
    query: str | None = None,
    fields: builtins.list[str] | None = None,
    start_time: datetime | int | None = None,
    end_time: datetime | int | None = None,
    group_by: str | builtins.list[str] | None = None,
    order_by: str | None = None,
    descending: bool = True,
    *,
    timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
) -> dict[str, Any]:
    """Build datasearch query parameters; the alert builder owns the wire names."""
    return _build_datasearch_params(
        query, fields, start_time, end_time, group_by, order_by, descending, timeout=timeout
    )


def _prepare_list(
    event_type: str | EventType,
    query: str | None,
    fields: builtins.list[str] | None,
    start_time: datetime | int | None,
    end_time: datetime | int | None,
    group_by: str | builtins.list[str] | None,
    order_by: str | None,
    descending: bool,
    audit_type: str | None,
    timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    insertion_start_time: datetime | int | None = None,
    insertion_end_time: datetime | int | None = None,
) -> tuple[str, type[Event], dict[str, Any]]:
    """Resolve the endpoint path, model, and query params for a list() call."""
    et = _validate_event_type(event_type)
    if audit_type is not None and et != EventType.AUDIT.value:
        raise ValidationError(f"{et} events do not support the audit_type filter.")
    params = _build_params(
        audit_type_query(query, audit_type),
        fields,
        start_time,
        end_time,
        group_by,
        order_by,
        descending,
        # Only /events/datasearch/* declares a query timeout.
        timeout=timeout if et in _DATASEARCH_TYPES else None,
    )
    params.update(_insertion_params(et, insertion_start_time, insertion_end_time))
    return _event_path(et), _event_model(et), params


def _prepare_get(
    event_id: str,
    event_type: str | EventType,
    timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
) -> tuple[str, type[Event], dict[str, Any]]:
    """Resolve the endpoint path, model, and params for a get() call."""
    et = _validate_event_type(event_type)
    if not _HEX_ID_RE.match(event_id):
        raise ValidationError(f"Invalid event_id format: {event_id!r}. Expected a hex string.")
    params: dict[str, Any] = {"query": f'_id eq "{event_id}"', "limit": 1}
    if et in _DATASEARCH_TYPES:
        resolved = _validate_timeout(timeout)
        if resolved is not None:
            params["timeout"] = resolved
    return _event_path(et), _event_model(et), params


class EventsResource(SyncResource):
    """Synchronous interface to the ``/api/v2/events`` endpoints."""

    @functools.cached_property
    def with_response(self) -> EventResponses:
        """Retain the original response of one typed event operation."""
        from netskope.resources._event_response import EventResponses

        return EventResponses(self._transport)

    def capabilities(
        self, event_type: str | EventType = EventType.APPLICATION
    ) -> EventQueryCapabilities:
        """Return verified capabilities without issuing a request."""
        from netskope.resources._event_response import event_capabilities

        return event_capabilities(event_type)

    def list_page(
        self,
        event_type: str | EventType = EventType.APPLICATION,
        *,
        query: str | None = None,
        fields: builtins.list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        offset: int | None = None,
        limit: int | None = None,
        audit_type: str | None = None,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
        insertion_start_time: datetime | int | None = None,
        insertion_end_time: datetime | int | None = None,
    ) -> Page[Event]:
        """Fetch one validated page, preserving omitted request parameters.

        *audit_type* narrows ``audit`` events to one audit category and is
        rejected for every other event type. *timeout* is the datasearch query
        timeout in seconds (``None`` omits it); it is never sent to the
        ``audit``, ``infrastructure``, or transaction-metrics endpoints, which
        do not declare it. *insertion_start_time* / *insertion_end_time* bound
        ingestion time and are accepted only by ``audit`` and
        ``infrastructure``.
        """
        return self.with_response.list_page(
            event_type,
            query=query,
            fields=fields,
            start_time=start_time,
            end_time=end_time,
            order_by=order_by,
            descending=descending,
            offset=offset,
            limit=limit,
            audit_type=audit_type,
            timeout=timeout,
            insertion_start_time=insertion_start_time,
            insertion_end_time=insertion_end_time,
        ).parse()

    def aggregate_page(
        self,
        event_type: str | EventType = EventType.APPLICATION,
        *,
        group_by: str | builtins.list[str],
        query: str | None = None,
        fields: builtins.list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        limit: int | None = None,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> Page[DatasearchBucket]:
        """Fetch one aggregate page without claiming a source-event total."""
        return self.with_response.aggregate_page(
            event_type,
            group_by=group_by,
            query=query,
            fields=fields,
            start_time=start_time,
            end_time=end_time,
            order_by=order_by,
            descending=descending,
            limit=limit,
            timeout=timeout,
        ).parse()

    def transaction_metrics(self, *, hours: int = 24) -> TransactionMetrics:
        """Fetch hourly backlog metrics, not individual transaction events."""
        return self.with_response.transaction_metrics(hours=hours).parse()

    def list(
        self,
        event_type: str | EventType = EventType.APPLICATION,
        *,
        query: str | None = None,
        fields: builtins.list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        group_by: str | builtins.list[str] | None = None,
        order_by: str | None = None,
        descending: bool = True,
        audit_type: str | None = None,
        page_size: int = 100,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
        insertion_start_time: datetime | int | None = None,
        insertion_end_time: datetime | int | None = None,
    ) -> SyncPaginatedResponse[Event]:
        """List events of a given type with optional JQL filtering.

        Most event types query ``/api/v2/events/datasearch/{type}``.
        Exceptions:

        - ``audit`` queries ``/api/v2/events/data/audit``, which filters with
          the same ``query`` expression and accepts no field projection,
          grouping, or ordering;
        - ``infrastructure`` queries ``/api/v2/events/data/infrastructure``;
        - ``transaction`` is not a record endpoint at all — it is rejected
          here, and :meth:`transaction_metrics` serves its hourly metrics.

        Args:
            event_type: The event category (e.g. ``"application"``,
                ``"network"``, ``"page"``, ``"alert"``).
            query: A JQL filter expression.
            fields: Specific fields to return.
            start_time: Start of the time range.
            end_time: End of the time range.
            group_by: Field(s) to aggregate results by.
            order_by: Field to sort by.
            descending: Sort direction.
            audit_type: Audit category filter (``audit`` only), e.g.
                ``"admin"`` or ``"user"``. It is folded into *query* as
                ``type eq "<audit_type>"``.
            page_size: Number of results per API call.
            timeout: Datasearch query timeout in seconds; ``None`` omits it.
                It is not sent to ``audit`` or ``infrastructure``, which do
                not declare it.
            insertion_start_time: Lower ingestion-time bound (``audit`` and
                ``infrastructure`` only).
            insertion_end_time: Upper ingestion-time bound (same two types).

        Returns:
            A lazy paginated iterator of :class:`~netskope.models.events.Event`
            (or a type-specific subclass).

        Raises:
            netskope.exceptions.ValidationError: If *event_type* is unknown or
                ``"transaction"``, if *audit_type* is supplied for a non-audit
                type, or if an insertion-time bound is supplied for a type that
                does not accept one.
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
            timeout,
            insertion_start_time,
            insertion_end_time,
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
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> Event:
        """Get a single event by ID.

        Args:
            event_id: The ``_id`` of the event (a hex string).
            event_type: The event category to search in.
            timeout: Datasearch query timeout in seconds; ``None`` omits it.

        Returns:
            An :class:`~netskope.models.events.Event` (or type-specific
            subclass) instance.

        Raises:
            netskope.exceptions.NotFoundError: If the event does not exist.
            netskope.exceptions.ValidationError: If *event_id* is not a hex
                string, or *event_type* is ``"transaction"``, which serves
                hourly metrics rather than records.
        """
        path, model, params = _prepare_get(event_id, event_type, timeout)
        body = self._get(path, **params)
        items = extract_list(body)
        if not items:
            raise NotFoundError(f"Event {event_id!r} not found", status_code=404)
        return model.model_validate(items[0])


class AsyncEventsResource(AsyncResource):
    """Asynchronous interface to the ``/api/v2/events`` endpoints."""

    @functools.cached_property
    def with_response(self) -> AsyncEventResponses:
        """Retain the original response of one typed event operation."""
        from netskope.resources._event_response import AsyncEventResponses

        return AsyncEventResponses(self._transport)

    def capabilities(
        self, event_type: str | EventType = EventType.APPLICATION
    ) -> EventQueryCapabilities:
        """Return verified capabilities without issuing a request."""
        from netskope.resources._event_response import event_capabilities

        return event_capabilities(event_type)

    async def list_page(
        self,
        event_type: str | EventType = EventType.APPLICATION,
        *,
        query: str | None = None,
        fields: builtins.list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        offset: int | None = None,
        limit: int | None = None,
        audit_type: str | None = None,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
        insertion_start_time: datetime | int | None = None,
        insertion_end_time: datetime | int | None = None,
    ) -> Page[Event]:
        """Fetch one validated page. See :meth:`EventsResource.list_page`."""
        return (
            await self.with_response.list_page(
                event_type,
                query=query,
                fields=fields,
                start_time=start_time,
                end_time=end_time,
                order_by=order_by,
                descending=descending,
                offset=offset,
                limit=limit,
                audit_type=audit_type,
                timeout=timeout,
                insertion_start_time=insertion_start_time,
                insertion_end_time=insertion_end_time,
            )
        ).parse()

    async def aggregate_page(
        self,
        event_type: str | EventType = EventType.APPLICATION,
        *,
        group_by: str | builtins.list[str],
        query: str | None = None,
        fields: builtins.list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        limit: int | None = None,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> Page[DatasearchBucket]:
        """Fetch one aggregate page without claiming a source-event total."""
        return (
            await self.with_response.aggregate_page(
                event_type,
                group_by=group_by,
                query=query,
                fields=fields,
                start_time=start_time,
                end_time=end_time,
                order_by=order_by,
                descending=descending,
                limit=limit,
                timeout=timeout,
            )
        ).parse()

    async def transaction_metrics(self, *, hours: int = 24) -> TransactionMetrics:
        """Fetch hourly backlog metrics, not individual transaction events."""
        return (await self.with_response.transaction_metrics(hours=hours)).parse()

    def list(
        self,
        event_type: str | EventType = EventType.APPLICATION,
        *,
        query: str | None = None,
        fields: builtins.list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        group_by: str | builtins.list[str] | None = None,
        order_by: str | None = None,
        descending: bool = True,
        audit_type: str | None = None,
        page_size: int = 100,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
        insertion_start_time: datetime | int | None = None,
        insertion_end_time: datetime | int | None = None,
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
            timeout,
            insertion_start_time,
            insertion_end_time,
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
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> Event:
        """Get a single event by ID.

        See :meth:`EventsResource.get`.
        """
        path, model, params = _prepare_get(event_id, event_type, timeout)
        body = await self._get(path, **params)
        items = extract_list(body)
        if not items:
            raise NotFoundError(f"Event {event_id!r} not found", status_code=404)
        return model.model_validate(items[0])
