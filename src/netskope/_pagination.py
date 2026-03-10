"""Transparent pagination — the single highest-impact DX feature.

Provides :class:`SyncPage` and :class:`AsyncPage` iterators that handle
offset-based pagination automatically, yielding typed model instances one
at a time.  Callers never write pagination loops::

    for alert in client.alerts.list(severity="high"):
        process(alert)

For page-level access::

    for page in client.alerts.list(severity="high").pages():
        print(f"{len(page.items)} items, {page.total} total")
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from netskope._transport import AsyncTransport, SyncTransport

T = TypeVar("T", bound=BaseModel)

_MAX_PAGES = 1000


@dataclass
class Page(Generic[T]):
    """A single page of results.

    Attributes:
        items: The models on this page.
        total: The total number of items across all pages (if the API
            provides this; ``None`` otherwise).
        offset: The offset used to fetch this page.
        limit: The page size.
    """

    items: list[T]
    total: int | None
    offset: int
    limit: int


class SyncPaginatedResponse(Generic[T]):
    """A lazy, iterable result set that fetches pages on demand.

    Iterating yields individual *T* model instances; calling
    :meth:`pages` yields :class:`Page` objects instead.
    """

    def __init__(
        self,
        transport: SyncTransport,
        method: str,
        path: str,
        params: dict[str, Any],
        model: type[T],
        page_size: int,
        data_key: str = "data",
        extract: Callable[[dict[str, Any]], list[dict[str, Any]]] | None = None,
    ) -> None:
        self._transport = transport
        self._method = method
        self._path = path
        self._params = dict(params)
        self._model = model
        self._page_size = page_size
        self._data_key = data_key
        self._extract = extract

    def _fetch_page(self, offset: int) -> Page[T]:
        params = {**self._params, "limit": self._page_size, "offset": offset}
        response = self._transport.request(self._method, self._path, params=params)
        body = response.json()

        if self._extract is not None:
            raw_items = self._extract(body)
        elif isinstance(body, list):
            raw_items = body
        else:
            raw_items = body.get(self._data_key, body.get("result", []))
            if isinstance(raw_items, dict):
                raw_items = raw_items.get("data", [])

        if not isinstance(raw_items, list):
            raw_items = []

        items = [self._model.model_validate(item) for item in raw_items]

        total = None
        if isinstance(body, dict):
            status = body.get("status")
            if isinstance(status, dict):
                total = status.get("total")

        return Page(items=items, total=total, offset=offset, limit=self._page_size)

    def pages(self) -> Iterator[Page[T]]:
        """Yield one :class:`Page` per API call."""
        offset = 0
        for _ in range(_MAX_PAGES):
            page = self._fetch_page(offset)
            if not page.items:
                break
            yield page
            if page.total is not None and offset + self._page_size >= page.total:
                break
            offset += self._page_size

    def __iter__(self) -> Iterator[T]:
        """Yield individual model instances across all pages."""
        for page in self.pages():
            yield from page.items

    def to_list(self, max_items: int = 10_000) -> list[T]:
        """Collect up to *max_items* results eagerly into a list.

        This is a convenience for scripts that need all results in memory.
        For large result sets, prefer iterating lazily.
        """
        results: list[T] = []
        for item in self:
            results.append(item)
            if len(results) >= max_items:
                break
        return results

    def first(self) -> T | None:
        """Return the first result, or ``None`` if empty."""
        for item in self:
            return item
        return None


class AsyncPaginatedResponse(Generic[T]):
    """Async counterpart of :class:`SyncPaginatedResponse`."""

    def __init__(
        self,
        transport: AsyncTransport,
        method: str,
        path: str,
        params: dict[str, Any],
        model: type[T],
        page_size: int,
        data_key: str = "data",
        extract: Callable[[dict[str, Any]], list[dict[str, Any]]] | None = None,
    ) -> None:
        self._transport = transport
        self._method = method
        self._path = path
        self._params = dict(params)
        self._model = model
        self._page_size = page_size
        self._data_key = data_key
        self._extract = extract

    async def _fetch_page(self, offset: int) -> Page[T]:
        params = {**self._params, "limit": self._page_size, "offset": offset}
        response = await self._transport.request(self._method, self._path, params=params)
        body = response.json()

        if self._extract is not None:
            raw_items = self._extract(body)
        elif isinstance(body, list):
            raw_items = body
        else:
            raw_items = body.get(self._data_key, body.get("result", []))
            if isinstance(raw_items, dict):
                raw_items = raw_items.get("data", [])

        if not isinstance(raw_items, list):
            raw_items = []

        items = [self._model.model_validate(item) for item in raw_items]

        total = None
        if isinstance(body, dict):
            status = body.get("status")
            if isinstance(status, dict):
                total = status.get("total")

        return Page(items=items, total=total, offset=offset, limit=self._page_size)

    async def pages(self) -> AsyncIterator[Page[T]]:
        """Yield one :class:`Page` per API call."""
        offset = 0
        for _ in range(_MAX_PAGES):
            page = await self._fetch_page(offset)
            if not page.items:
                break
            yield page
            if page.total is not None and offset + self._page_size >= page.total:
                break
            offset += self._page_size

    async def __aiter__(self) -> AsyncIterator[T]:
        """Yield individual model instances across all pages."""
        async for page in self.pages():
            for item in page.items:
                yield item

    async def to_list(self, max_items: int = 10_000) -> list[T]:
        """Collect up to *max_items* results eagerly into a list."""
        results: list[T] = []
        async for item in self:
            results.append(item)
            if len(results) >= max_items:
                break
        return results

    async def first(self) -> T | None:
        """Return the first result, or ``None`` if empty."""
        async for item in self:
            return item
        return None
