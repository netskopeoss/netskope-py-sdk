"""Typed alert records, grouped results, and explicit datasearch scans."""

from __future__ import annotations

import builtins
from datetime import datetime
from functools import cached_property

from netskope._pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.datasearch import (
    DATASEARCH_PAGE_CAP,
    DATASEARCH_TIMEOUT_DEFAULT,
    AsyncScanIterator,
    DatasearchWindow,
    ScanIterator,
)
from netskope.models.alerts import Alert, DatasearchBucket
from netskope.pagination import Page
from netskope.resources._alert_query import _PATH, _build_params, _extract_alerts
from netskope.resources._alert_response import (
    AlertResponses,
    AsyncAlertResponses,
    _scan_alerts,
    _scan_alerts_async,
)
from netskope.resources._base import AsyncResource, SyncResource


class AlertsResource(SyncResource):
    """Synchronous interface to /api/v2/events/datasearch/alert."""

    @cached_property
    def with_response(self) -> AlertResponses:
        """Opt into the original response alongside typed parsing."""
        return AlertResponses(self._transport)

    def list(
        self,
        *,
        query: str | None = None,
        fields: builtins.list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        group_by: str | builtins.list[str] | None = None,
        order_by: str | None = None,
        descending: bool = True,
        page_size: int = 100,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> SyncPaginatedResponse[Alert]:
        """Lazily list alert records with the legacy pagination contract.

        group_by remains accepted for compatibility, but object-valued
        grouped IDs do not fit Alert. Use aggregate_page for typed grouped
        results. Use scan_pages when completion evidence matters.
        """
        params = _build_params(
            query, fields, start_time, end_time, group_by, order_by, descending, timeout=timeout
        )
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_PATH,
            params=params,
            model=Alert,
            page_size=page_size,
            extract=_extract_alerts,
        )

    def list_page(
        self,
        *,
        query: str | None = None,
        fields: builtins.list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        offset: int | None = None,
        limit: int | None = None,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> Page[Alert]:
        """Fetch exactly one typed page, retaining envelope metadata.

        Omitted parameters stay omitted. order_by uses the endpoint's
        orderbys parameter; an omitted direction does not append DESC.
        """
        return self.with_response.list_page(
            query=query,
            fields=fields,
            start_time=start_time,
            end_time=end_time,
            order_by=order_by,
            descending=descending,
            offset=offset,
            limit=limit,
            timeout=timeout,
        ).parse()

    def aggregate_page(
        self,
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
        """Fetch one grouped page, without asserting source-event completeness."""
        return self.with_response.aggregate_page(
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

    def get(self, alert_id: str, *, timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT) -> Alert:
        """Get an alert by its hex ID, or raise NotFoundError."""
        return self.with_response.get(alert_id, timeout=timeout).parse()

    def scan_pages(
        self,
        *,
        window: DatasearchWindow,
        query: str | None = None,
        fields: builtins.list[str] | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        page_size: int = DATASEARCH_PAGE_CAP,
        max_records: int | None = None,
        max_pages: int = 1_000,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> ScanIterator[Page[Alert]]:
        """Lazily scan a fixed interval with explicit termination evidence.

        A narrowed projection includes _id for no-progress checks. Every
        response is validated before yielding, including identity checks.
        Exhaustion does not imply snapshot consistency under concurrent writes.
        """
        return _scan_alerts(
            self._transport,
            lambda response: response.parse(),
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


class AsyncAlertsResource(AsyncResource):
    """Asynchronous interface to /api/v2/events/datasearch/alert."""

    @cached_property
    def with_response(self) -> AsyncAlertResponses:
        """Opt into the original response alongside typed parsing."""
        return AsyncAlertResponses(self._transport)

    def list(
        self,
        *,
        query: str | None = None,
        fields: builtins.list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        group_by: str | builtins.list[str] | None = None,
        order_by: str | None = None,
        descending: bool = True,
        page_size: int = 100,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> AsyncPaginatedResponse[Alert]:
        """Lazily list records. Use aggregate_page for object-valued grouped IDs."""
        params = _build_params(
            query, fields, start_time, end_time, group_by, order_by, descending, timeout=timeout
        )
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_PATH,
            params=params,
            model=Alert,
            page_size=page_size,
            extract=_extract_alerts,
        )

    async def list_page(
        self,
        *,
        query: str | None = None,
        fields: builtins.list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        offset: int | None = None,
        limit: int | None = None,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> Page[Alert]:
        """Fetch one typed page using the endpoint's orderbys parameter."""
        response = await self.with_response.list_page(
            query=query,
            fields=fields,
            start_time=start_time,
            end_time=end_time,
            order_by=order_by,
            descending=descending,
            offset=offset,
            limit=limit,
            timeout=timeout,
        )
        return response.parse()

    async def aggregate_page(
        self,
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
        """Fetch one grouped page, without asserting source-event completeness."""
        response = await self.with_response.aggregate_page(
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
        return response.parse()

    async def get(
        self, alert_id: str, *, timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT
    ) -> Alert:
        """Get an alert by its hex ID, or raise NotFoundError."""
        response = await self.with_response.get(alert_id, timeout=timeout)
        return response.parse()

    def scan_pages(
        self,
        *,
        window: DatasearchWindow,
        query: str | None = None,
        fields: builtins.list[str] | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        page_size: int = DATASEARCH_PAGE_CAP,
        max_records: int | None = None,
        max_pages: int = 1_000,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> AsyncScanIterator[Page[Alert]]:
        """Create a lazy async scan with the same evidence as the synchronous API."""
        return _scan_alerts_async(
            self._transport,
            lambda response: response.parse(),
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
