"""Bounded event reads with endpoint-specific capabilities and typed results."""

from __future__ import annotations

from datetime import datetime
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from netskope._pagination import _make_page
from netskope.datasearch import (
    DATASEARCH_PAGE_CAP,
    AsyncScanIterator,
    DatasearchWindow,
    ScanIterator,
    _ScanPage,
)
from netskope.exceptions import NotFoundError, ValidationError
from netskope.models.alerts import DatasearchBucket
from netskope.models.events import (
    Event,
    EventQueryCapabilities,
    EventType,
    TransactionMetrics,
)
from netskope.pagination import Page
from netskope.resources._alert_query import (
    _build_aggregate_params,
    _build_page_params,
    _build_scan_params,
    _extract_alerts,
    _metadata,
    _parse_aggregate_page,
    _validate_alert_id,
)
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources.events import _DATASEARCH_TYPES, _event_model, _event_path
from netskope.response import ApiResponse

M = TypeVar("M", bound=BaseModel)


def event_capabilities(event_type: str | EventType) -> EventQueryCapabilities:
    if event_type in _DATASEARCH_TYPES:
        return EventQueryCapabilities(
            page_limit=10000,
            scannable=True,
            projection=True,
            grouping=True,
            ordering=True,
            jql=True,
        )
    if event_type == "infrastructure":
        return EventQueryCapabilities(
            page_limit=5000,
            scannable=False,
            projection=False,
            grouping=False,
            ordering=False,
            jql=True,
        )
    if event_type == "audit":
        return EventQueryCapabilities(
            page_limit=5000,
            scannable=False,
            projection=False,
            grouping=False,
            ordering=False,
            jql=False,
        )
    if event_type == "transaction":
        raise ValidationError(
            "Transaction events are hourly metrics; use transaction_metrics(hours=...)."
        )
    raise ValidationError("Unknown event category.")


def _endpoint(
    event_type: str | EventType,
    query: str | None,
    fields: list[str] | None,
    order_by: str | None,
    group_by: str | list[str] | None = None,
    audit_type: str | None = None,
) -> tuple[str, type[Event], EventQueryCapabilities]:
    """Reject unsupported query features, then resolve the path and record model."""
    capabilities = event_capabilities(event_type)
    if not capabilities.jql and query is not None:
        raise ValidationError(
            "The audit event type does not support JQL queries; use audit_type to filter instead."
        )
    if capabilities.jql and audit_type is not None:
        raise ValidationError(f"{event_type} events do not support the audit_type filter.")
    if not capabilities.projection and fields is not None:
        raise ValidationError(f"{event_type} events do not support server-side field projection.")
    if not capabilities.grouping and group_by is not None:
        raise ValidationError(f"{event_type} events do not support server-side grouping.")
    if not capabilities.ordering and order_by is not None:
        raise ValidationError(f"{event_type} events do not support server-side ordering.")
    return _event_path(event_type), _event_model(event_type), capabilities


def _within_page_limit(
    event_type: str | EventType, capabilities: EventQueryCapabilities, params: dict[str, Any]
) -> dict[str, Any]:
    if params.get("limit", 0) > capabilities.page_limit:
        raise ValidationError(
            f"{event_type} events support a maximum limit of {capabilities.page_limit}."
        )
    return params


def _prepare(
    event_type: str | EventType,
    query: str | None,
    fields: list[str] | None,
    start_time: datetime | int | None,
    end_time: datetime | int | None,
    order_by: str | None,
    descending: bool | None,
    offset: int | None,
    limit: int | None,
    audit_type: str | None = None,
) -> tuple[str, type[Event], dict[str, Any]]:
    path, model, capabilities = _endpoint(event_type, query, fields, order_by, None, audit_type)
    params = _build_page_params(
        query, fields, start_time, end_time, order_by, descending, offset, limit
    )
    if audit_type is not None:
        params["type"] = audit_type
    return path, model, _within_page_limit(event_type, capabilities, params)


def _prepare_lookup(
    event_type: str | EventType, event_id: str
) -> tuple[str, type[Event], dict[str, Any]]:
    _validate_alert_id(event_id)
    if not event_capabilities(event_type).jql:
        raise ValidationError(
            f"Event type {str(event_type)!r} does not support lookup by ID (no JQL support)."
        )
    return _prepare(event_type, f'_id eq "{event_id}"', None, None, None, None, None, None, 1)


def _parse_page(body: Any, model: type[M], offset: int, limit: int | None) -> Page[M]:
    items = [model.model_validate(row) for row in _extract_alerts(body)]
    page = _make_page(items, _metadata(body), offset, limit)
    if page.total is None and limit is not None and len(items) < limit:
        page.has_more = False
    return page


def _page_response(
    raw: httpx.Response, model: type[M], offset: int | None, limit: int | None
) -> ApiResponse[Page[M]]:
    return ApiResponse(
        raw, lambda response: _parse_page(response.json(), model, offset or 0, limit)
    )


def _get_response(raw: httpx.Response, model: type[Event], event_id: str) -> ApiResponse[Event]:
    def parse(response: httpx.Response) -> Event:
        records = _extract_alerts(response.json())
        if not records:
            raise NotFoundError(
                "Event not found.",
                status_code=404,
                request_method=response.request.method,
                request_path=response.request.url.path,
                request_id=response.headers.get("x-request-id"),
            )
        if len(records) != 1:
            raise ValueError("Event lookup did not return exactly one record.")
        event = model.model_validate(records[0])
        if event.id != event_id:
            raise ValueError("Event lookup returned an unexpected identity.")
        return event

    return ApiResponse(raw, parse)


def _metrics_response(raw: httpx.Response) -> ApiResponse[TransactionMetrics]:
    def parse(response: httpx.Response) -> TransactionMetrics:
        body = response.json()
        if not isinstance(body, dict) or not isinstance(body.get("result"), dict):
            raise ValueError("Expected a transaction-metrics result object.")
        return TransactionMetrics.model_validate(body["result"])

    return ApiResponse(raw, parse)


class EventResponses(SyncResource):
    def list_page(
        self,
        event_type: str | EventType = EventType.APPLICATION,
        *,
        query: str | None = None,
        fields: list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        offset: int | None = None,
        limit: int | None = None,
        audit_type: str | None = None,
    ) -> ApiResponse[Page[Event]]:
        path, model, params = _prepare(
            event_type,
            query,
            fields,
            start_time,
            end_time,
            order_by,
            descending,
            offset,
            limit,
            audit_type,
        )
        raw = self._transport.request("GET", path, params=params or None)
        return _page_response(raw, model, offset, limit)

    def aggregate_page(
        self,
        event_type: str | EventType = EventType.APPLICATION,
        *,
        group_by: str | list[str],
        query: str | None = None,
        fields: list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        limit: int | None = None,
    ) -> ApiResponse[Page[DatasearchBucket]]:
        path, _, capabilities = _endpoint(event_type, query, fields, order_by, group_by)
        params = _within_page_limit(
            event_type,
            capabilities,
            _build_aggregate_params(
                group_by, query, fields, start_time, end_time, order_by, descending, limit
            ),
        )
        raw = self._transport.request("GET", path, params=params)
        return ApiResponse(raw, lambda response: _parse_aggregate_page(response.json(), limit))

    def get(
        self, event_id: str, *, event_type: str | EventType = EventType.APPLICATION
    ) -> ApiResponse[Event]:
        path, model, params = _prepare_lookup(event_type, event_id)
        raw = self._transport.request("GET", path, params=params)
        return _get_response(raw, model, event_id)

    def transaction_metrics(self, *, hours: int = 24) -> ApiResponse[TransactionMetrics]:
        if isinstance(hours, bool) or not isinstance(hours, int) or not 1 <= hours <= 168:
            raise ValidationError("hours must be an integer between 1 and 168.")
        raw = self._transport.request(
            "GET", "/api/v2/events/metrics/transactionevents", params={"hours": hours}
        )
        return _metrics_response(raw)

    def scan_pages(
        self,
        event_type: str | EventType = EventType.APPLICATION,
        *,
        window: DatasearchWindow,
        query: str | None = None,
        fields: list[str] | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        page_size: int = DATASEARCH_PAGE_CAP,
        max_records: int | None = None,
        max_pages: int = 1000,
    ) -> ScanIterator[ApiResponse[Page[Event]]]:
        if not event_capabilities(event_type).scannable:
            raise ValidationError(f"Exact scans are not established for {event_type} events.")
        params = _build_scan_params(window, query, fields, order_by, descending)
        path, model, _ = _endpoint(event_type, query, fields, order_by)

        def fetch(offset: int, limit: int) -> _ScanPage[ApiResponse[Page[Event]]]:
            raw = self._transport.request(
                "GET", path, params={**params, "offset": offset, "limit": limit}
            )
            response = _page_response(raw, model, offset, limit)
            page = response.parse()
            return _ScanPage(response, [item.id for item in page.items], page.total, response)

        return ScanIterator(
            fetch, window=window, page_size=page_size, max_records=max_records, max_pages=max_pages
        )


class AsyncEventResponses(AsyncResource):
    async def list_page(
        self,
        event_type: str | EventType = EventType.APPLICATION,
        *,
        query: str | None = None,
        fields: list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        offset: int | None = None,
        limit: int | None = None,
        audit_type: str | None = None,
    ) -> ApiResponse[Page[Event]]:
        path, model, params = _prepare(
            event_type,
            query,
            fields,
            start_time,
            end_time,
            order_by,
            descending,
            offset,
            limit,
            audit_type,
        )
        raw = await self._transport.request("GET", path, params=params or None)
        return _page_response(raw, model, offset, limit)

    async def aggregate_page(
        self,
        event_type: str | EventType = EventType.APPLICATION,
        *,
        group_by: str | list[str],
        query: str | None = None,
        fields: list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        limit: int | None = None,
    ) -> ApiResponse[Page[DatasearchBucket]]:
        path, _, capabilities = _endpoint(event_type, query, fields, order_by, group_by)
        params = _within_page_limit(
            event_type,
            capabilities,
            _build_aggregate_params(
                group_by, query, fields, start_time, end_time, order_by, descending, limit
            ),
        )
        raw = await self._transport.request("GET", path, params=params)
        return ApiResponse(raw, lambda response: _parse_aggregate_page(response.json(), limit))

    async def get(
        self, event_id: str, *, event_type: str | EventType = EventType.APPLICATION
    ) -> ApiResponse[Event]:
        path, model, params = _prepare_lookup(event_type, event_id)
        raw = await self._transport.request("GET", path, params=params)
        return _get_response(raw, model, event_id)

    async def transaction_metrics(self, *, hours: int = 24) -> ApiResponse[TransactionMetrics]:
        if isinstance(hours, bool) or not isinstance(hours, int) or not 1 <= hours <= 168:
            raise ValidationError("hours must be an integer between 1 and 168.")
        raw = await self._transport.request(
            "GET", "/api/v2/events/metrics/transactionevents", params={"hours": hours}
        )
        return _metrics_response(raw)

    def scan_pages(
        self,
        event_type: str | EventType = EventType.APPLICATION,
        *,
        window: DatasearchWindow,
        query: str | None = None,
        fields: list[str] | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        page_size: int = DATASEARCH_PAGE_CAP,
        max_records: int | None = None,
        max_pages: int = 1000,
    ) -> AsyncScanIterator[ApiResponse[Page[Event]]]:
        if not event_capabilities(event_type).scannable:
            raise ValidationError(f"Exact scans are not established for {event_type} events.")
        params = _build_scan_params(window, query, fields, order_by, descending)
        path, model, _ = _endpoint(event_type, query, fields, order_by)

        async def fetch(offset: int, limit: int) -> _ScanPage[ApiResponse[Page[Event]]]:
            raw = await self._transport.request(
                "GET", path, params={**params, "offset": offset, "limit": limit}
            )
            response = _page_response(raw, model, offset, limit)
            page = response.parse()
            return _ScanPage(response, [item.id for item in page.items], page.total, response)

        return AsyncScanIterator(
            fetch, window=window, page_size=page_size, max_records=max_records, max_pages=max_pages
        )
