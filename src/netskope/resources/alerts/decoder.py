"""Alert operations retaining their original, same-request HTTP response."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TypeVar

import httpx

from netskope.core.pagination import Page
from netskope.core.resource import AsyncResource, SyncResource
from netskope.core.transport import AsyncTransport, SyncTransport
from netskope.datasearch import (
    DATASEARCH_PAGE_CAP,
    DATASEARCH_TIMEOUT_DEFAULT,
    AsyncScanIterator,
    DatasearchWindow,
    ScanIterator,
    _ScanPage,
)
from netskope.exceptions import NotFoundError
from netskope.models.alerts import Alert, DatasearchBucket
from netskope.resources.shared.datasearch_query import (
    _PATH,
    _build_aggregate_params,
    _build_page_params,
    _build_scan_params,
    _extract_alerts,
    _matching_identity,
    _parse_aggregate_page,
    _parse_alerts_page,
    _single_record,
    _validate_alert_id,
)
from netskope.response import ApiResponse

T = TypeVar("T")


def _page_response(
    response: httpx.Response, offset: int | None, limit: int | None
) -> ApiResponse[Page[Alert]]:
    return ApiResponse(
        response,
        lambda raw: _parse_alerts_page(raw.json(), 0 if offset is None else offset, limit),
    )


def _parse_alert(response: httpx.Response, alert_id: str) -> Alert:
    """Decode a ``_id eq`` lookup, refusing a page that answers a different alert."""
    items = _extract_alerts(response.json())
    if not items:
        raise NotFoundError(
            f"Alert {alert_id!r} not found",
            status_code=404,
            request_method=response.request.method,
            request_path=response.request.url.path,
            request_id=response.headers.get("x-request-id"),
        )
    alert = Alert.model_validate(_single_record(items, "Alert"))
    _matching_identity(alert.id, alert_id, "Alert")
    return alert


def _scan_alerts(
    transport: SyncTransport,
    select: Callable[[ApiResponse[Page[Alert]]], T],
    *,
    window: DatasearchWindow,
    query: str | None = None,
    fields: list[str] | None = None,
    order_by: str | None = None,
    descending: bool | None = None,
    page_size: int = DATASEARCH_PAGE_CAP,
    max_records: int | None = None,
    max_pages: int = 1_000,
    timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
) -> ScanIterator[T]:
    params = _build_scan_params(window, query, fields, order_by, descending, timeout=timeout)

    def fetch(offset: int, limit: int) -> _ScanPage[T]:
        raw = transport.request("GET", _PATH, params={**params, "offset": offset, "limit": limit})
        response = _page_response(raw, offset, limit)
        page = response.parse()
        return _ScanPage(select(response), [item.id for item in page.items], page.total, response)

    return ScanIterator(
        fetch, window=window, page_size=page_size, max_records=max_records, max_pages=max_pages
    )


def _scan_alerts_async(
    transport: AsyncTransport,
    select: Callable[[ApiResponse[Page[Alert]]], T],
    *,
    window: DatasearchWindow,
    query: str | None = None,
    fields: list[str] | None = None,
    order_by: str | None = None,
    descending: bool | None = None,
    page_size: int = DATASEARCH_PAGE_CAP,
    max_records: int | None = None,
    max_pages: int = 1_000,
    timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
) -> AsyncScanIterator[T]:
    params = _build_scan_params(window, query, fields, order_by, descending, timeout=timeout)

    async def fetch(offset: int, limit: int) -> _ScanPage[T]:
        raw = await transport.request(
            "GET", _PATH, params={**params, "offset": offset, "limit": limit}
        )
        response = _page_response(raw, offset, limit)
        page = response.parse()
        return _ScanPage(select(response), [item.id for item in page.items], page.total, response)

    return AsyncScanIterator(
        fetch, window=window, page_size=page_size, max_records=max_records, max_pages=max_pages
    )


class AlertResponses(SyncResource):
    """Explicit same-request response access for synchronous alert queries."""

    def list_page(
        self,
        *,
        query: str | None = None,
        fields: list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        offset: int | None = None,
        limit: int | None = None,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> ApiResponse[Page[Alert]]:
        """Fetch exactly one record page; omitted request parameters stay omitted."""
        params = _build_page_params(
            query,
            fields,
            start_time,
            end_time,
            order_by,
            descending,
            offset,
            limit,
            timeout=timeout,
        )
        raw = self._transport.request("GET", _PATH, params=params or None)
        return _page_response(raw, offset, limit)

    def aggregate_page(
        self,
        *,
        group_by: str | list[str],
        query: str | None = None,
        fields: list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        limit: int | None = None,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> ApiResponse[Page[DatasearchBucket]]:
        """Fetch one grouped result page without implying source-event completeness."""
        params = _build_aggregate_params(
            group_by,
            query,
            fields,
            start_time,
            end_time,
            order_by,
            descending,
            limit,
            timeout=timeout,
        )
        raw = self._transport.request("GET", _PATH, params=params)
        return ApiResponse(raw, lambda response: _parse_aggregate_page(response.json(), limit))

    def get(
        self, alert_id: str, *, timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT
    ) -> ApiResponse[Alert]:
        """Look up an alert by its hex ID and retain the result envelope.

        ``limit`` defaults to 10000 on the endpoint (search_alert.yaml:340-345),
        so a one-record lookup states ``limit=1`` explicitly.
        """
        _validate_alert_id(alert_id)
        params = _build_page_params(
            f'_id eq "{alert_id}"', None, None, None, None, None, None, 1, timeout=timeout
        )
        raw = self._transport.request("GET", _PATH, params=params)
        return ApiResponse(raw, lambda response: _parse_alert(response, alert_id))

    def scan_pages(
        self,
        *,
        window: DatasearchWindow,
        query: str | None = None,
        fields: list[str] | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        page_size: int = DATASEARCH_PAGE_CAP,
        max_records: int | None = None,
        max_pages: int = 1_000,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> ScanIterator[ApiResponse[Page[Alert]]]:
        """Lazily scan a fixed interval, retaining one response per yielded page."""
        return _scan_alerts(
            self._transport,
            lambda response: response,
            window=window,
            query=query,
            fields=fields,
            order_by=order_by,
            descending=descending,
            page_size=page_size,
            max_records=max_records,
            max_pages=max_pages,
            timeout=timeout,
        )


class AsyncAlertResponses(AsyncResource):
    """Explicit same-request response access for asynchronous alert queries."""

    async def list_page(
        self,
        *,
        query: str | None = None,
        fields: list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        offset: int | None = None,
        limit: int | None = None,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> ApiResponse[Page[Alert]]:
        """Fetch exactly one record page; omitted request parameters stay omitted."""
        params = _build_page_params(
            query,
            fields,
            start_time,
            end_time,
            order_by,
            descending,
            offset,
            limit,
            timeout=timeout,
        )
        raw = await self._transport.request("GET", _PATH, params=params or None)
        return _page_response(raw, offset, limit)

    async def aggregate_page(
        self,
        *,
        group_by: str | list[str],
        query: str | None = None,
        fields: list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        limit: int | None = None,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> ApiResponse[Page[DatasearchBucket]]:
        """Fetch one grouped result page without implying source-event completeness."""
        params = _build_aggregate_params(
            group_by,
            query,
            fields,
            start_time,
            end_time,
            order_by,
            descending,
            limit,
            timeout=timeout,
        )
        raw = await self._transport.request("GET", _PATH, params=params)
        return ApiResponse(raw, lambda response: _parse_aggregate_page(response.json(), limit))

    async def get(
        self, alert_id: str, *, timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT
    ) -> ApiResponse[Alert]:
        """Look up an alert by its hex ID and retain the result envelope.

        ``limit`` defaults to 10000 on the endpoint (search_alert.yaml:340-345),
        so a one-record lookup states ``limit=1`` explicitly.
        """
        _validate_alert_id(alert_id)
        params = _build_page_params(
            f'_id eq "{alert_id}"', None, None, None, None, None, None, 1, timeout=timeout
        )
        raw = await self._transport.request("GET", _PATH, params=params)
        return ApiResponse(raw, lambda response: _parse_alert(response, alert_id))

    def scan_pages(
        self,
        *,
        window: DatasearchWindow,
        query: str | None = None,
        fields: list[str] | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        page_size: int = DATASEARCH_PAGE_CAP,
        max_records: int | None = None,
        max_pages: int = 1_000,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> AsyncScanIterator[ApiResponse[Page[Alert]]]:
        """Create a lazy async scan without sending a request until iteration."""
        return _scan_alerts_async(
            self._transport,
            lambda response: response,
            window=window,
            query=query,
            fields=fields,
            order_by=order_by,
            descending=descending,
            page_size=page_size,
            max_records=max_records,
            max_pages=max_pages,
            timeout=timeout,
        )
