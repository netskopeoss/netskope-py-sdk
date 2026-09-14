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
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from netskope.core.ids import extract_list
from netskope.core.pagination import AsyncPaginatedResponse, Page, SyncPaginatedResponse
from netskope.core.resource import AsyncResource, SyncResource
from netskope.datasearch import DATASEARCH_TIMEOUT_DEFAULT
from netskope.exceptions import NotFoundError, ResponseValidationError, ValidationError
from netskope.models.alerts import DatasearchBucket
from netskope.models.events import (
    Event,
    EventQueryCapabilities,
    EventType,
    TransactionMetrics,
)
from netskope.resources.events.decoder import AsyncEventResponses, EventResponses
from netskope.resources.events.paths import (
    _DATASEARCH_TYPES,
    _TRANSACTION_IS_METRICS,
    _endpoint,
    _event_model,
    _event_path,
    _insertion_params,
    _within_page_limit,
    audit_type_query,
    event_capabilities,
)
from netskope.resources.shared.datasearch_query import _build_params as _build_datasearch_params
from netskope.resources.shared.datasearch_query import (
    _matching_identity,
    _single_record,
    _validate_timeout,
)

_HEX_ID_RE = re.compile(r"^[a-fA-F0-9]+$")

# The single record-model table: the legacy iterator and the typed page share it,
# so one event type never decodes into two different models.

# Event types not served by /events/datasearch/{type}:
# - audit uses /events/data/audit, which takes query/limit/offset/starttime/
#   endtime/insertionstarttime/insertionendtime and nothing else
#   (events/audit.yaml:12-72);
# - infrastructure uses /events/data/infrastructure with the same parameter set
#   (events/infrastructure.yaml:12-72);
# - transaction uses /events/metrics/transactionevents, which takes only `hours`
#   and answers with a metrics object rather than records
#   (events/transaction_metrics.yaml:65-90).


# audit and infrastructure are the only endpoints that declare the insertion-time
# window (events/audit.yaml:51-72, events/infrastructure.yaml:51-72).


def _validate_event_type(event_type: str | EventType) -> str:
    et = str(event_type)
    valid = {e.value for e in EventType}
    if et not in valid:
        raise ValidationError(f"Invalid event_type: {et!r}. Must be one of {sorted(valid)}")
    if et == EventType.TRANSACTION.value:
        raise ValidationError(_TRANSACTION_IS_METRICS)
    return et


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
    declares_timeout: bool = True,
) -> dict[str, Any]:
    """Build datasearch query parameters; the alert builder owns the wire names."""
    return _build_datasearch_params(
        query,
        fields,
        start_time,
        end_time,
        group_by,
        order_by,
        descending,
        timeout=timeout,
        declares_timeout=declares_timeout,
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
    page_size: int | None = None,
) -> tuple[str, type[Event], dict[str, Any]]:
    """Resolve the endpoint path, model, and query params for a list() call.

    The capability gate and the page ceiling are the same ones the typed
    ``list_page`` surface applies, so ``audit`` and ``infrastructure`` reject
    projection, grouping, ordering, and a page size above
    ``maximum: 5000`` (events/audit.yaml:19-27,
    events/infrastructure.yaml:19-27) before any request is sent.
    """
    et = _validate_event_type(event_type)
    path, model, capabilities = _endpoint(et, fields, order_by, group_by, audit_type)
    if page_size is not None:
        _within_page_limit(et, capabilities, {"limit": page_size})
    params = _build_params(
        audit_type_query(query, audit_type),
        fields,
        start_time,
        end_time,
        group_by,
        order_by,
        descending,
        timeout=timeout,
        # Only /events/datasearch/* declares a query timeout.
        declares_timeout=et in _DATASEARCH_TYPES,
    )
    params.update(_insertion_params(et, insertion_start_time, insertion_end_time))
    return path, model, params


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
        params["timeout"] = _validate_timeout(timeout)
    return _event_path(et), _event_model(et), params


def _decode_one(body: Any, model: type[Event], event_id: str) -> Event:
    """Decode a one-record lookup with the guards the typed ``get`` already applies.

    A ``_id eq`` query that answers with several rows, or with a row carrying a
    different ``_id``, did not answer the question that was asked, so it is
    refused rather than silently returning the first record.
    """
    items = extract_list(body)
    if not items:
        raise NotFoundError(f"Event {event_id!r} not found", status_code=404)
    try:
        event = model.model_validate(_single_record(items, "Event"))
        _matching_identity(event.id, event_id, "Event")
    except PydanticValidationError:
        # A schema failure keeps reporting itself; only the two lookup guards
        # are translated, and they carry the wording the typed get() uses.
        raise
    except ValueError as exc:
        raise ResponseValidationError(f"The API response could not be decoded: {exc}") from exc
    return event


class EventsResource(SyncResource):
    """Synchronous interface to the ``/api/v2/events`` endpoints."""

    @functools.cached_property
    def with_response(self) -> EventResponses:
        """Retain the original response of one typed event operation."""

        return EventResponses(self._transport)

    def capabilities(
        self, event_type: str | EventType = EventType.APPLICATION
    ) -> EventQueryCapabilities:
        """Return verified capabilities without issuing a request."""
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
        timeout in seconds; it is ``required: true`` there with a declared
        default of 180, so ``None`` selects that default rather than omitting
        it. It is never sent to the ``audit``, ``infrastructure``, or
        transaction-metrics endpoints, which do not declare it.
        *insertion_start_time* / *insertion_end_time* bound ingestion time and
        are accepted only by ``audit`` and ``infrastructure``.
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
            page_size: Number of results per API call, up to 5000 for audit and
                infrastructure; the SDK caps datasearch pages at 10000.
            timeout: Datasearch query timeout in seconds. The parameter is
                required with a declared default of 180, so ``None`` selects
                that default. It is not sent to ``audit`` or
                ``infrastructure``, which do not declare it.
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
                does not accept one. Also raised if the page size exceeds the
                category's ceiling, or projection, grouping, or ordering is
                requested for audit or infrastructure events.
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
            page_size,
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
            timeout: Datasearch query timeout in seconds; ``None`` selects the
                endpoint's declared default of 180.

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
        return _decode_one(body, model, event_id)


class AsyncEventsResource(AsyncResource):
    """Asynchronous interface to the ``/api/v2/events`` endpoints."""

    @functools.cached_property
    def with_response(self) -> AsyncEventResponses:
        """Retain the original response of one typed event operation."""

        return AsyncEventResponses(self._transport)

    def capabilities(
        self, event_type: str | EventType = EventType.APPLICATION
    ) -> EventQueryCapabilities:
        """Return verified capabilities without issuing a request."""
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
            page_size,
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
        return _decode_one(body, model, event_id)
