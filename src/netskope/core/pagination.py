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

import json
import logging
from collections.abc import AsyncIterator, Callable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

import httpx
from pydantic import BaseModel
from pydantic import ValidationError as ModelValidationError

from netskope.core.transport import AsyncTransport, SyncTransport
from netskope.exceptions import PaginationError, ResponseValidationError

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger("netskope")

_MAX_PAGES = 1000


class _RecordsPastTotalError(PaginationError):
    """Records that reach past the total the API stated for the collection.

    Callers see the :class:`PaginationError` they already handle. The legacy
    iterators catch this one case to stop, because they have already yielded
    rows by the time a shrinking total shows up. They carry the refused records
    so an iterator that has delivered nothing yet can keep them.
    """

    def __init__(
        self,
        message: str,
        *,
        offset: int,
        records: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, offset=offset)
        self.records: list[Any] = [] if records is None else records
        self.metadata: dict[str, Any] = {} if metadata is None else metadata


@dataclass
class Page(Generic[T]):
    """A single page of results.

    Attributes:
        items: The models on this page.
        total: The total number of items across all pages (if the API
            provides this; ``None`` otherwise).
        offset: The offset used to fetch this page.
        limit: The requested page size, or ``None`` when left to the API.
        metadata: Envelope metadata supplied by the resource decoder.
        has_more: Whether more items remain, established by the API's total
            or operation-specific continuation evidence. ``None`` means the
            response does not establish this. ``False`` does not account for
            records skipped by a nonzero offset.
        windowed_locally: Whether this page was cut from a full collection the
            client already holds, because the operation declares no paging
            parameters. When true the response body carries the whole
            collection and ``items`` is a slice of it, so a consumer comparing
            the two must apply ``offset`` and ``len(items)`` itself.
    """

    items: list[T]
    total: int | None
    offset: int
    limit: int | None
    metadata: dict[str, Any] = field(default_factory=dict)
    has_more: bool | None = None
    windowed_locally: bool = False


def coerce_total(value: Any) -> int | None:
    """Interpret one envelope field as a collection total.

    Integers and numeric strings are accepted. Booleans, floats, negative
    numbers, and unparsable values state no total rather than an error, so
    every decoder treats an unusable total the same way.
    """
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        total = int(value)
    except ValueError:
        return None
    return total if total >= 0 else None


def select_total(metadata: Mapping[str, Any]) -> int | None:
    """Return the first usable total among the documented envelope fields."""
    status = metadata.get("status")
    candidates = (
        status.get("total") if isinstance(status, dict) else None,
        metadata.get("total"),
        metadata.get("totalResults"),
    )
    for candidate in candidates:
        total = coerce_total(candidate)
        if total is not None:
            return total
    return None


def exceeds_total(count: int, total: int | None, offset: int) -> bool:
    """Whether a page's records reach past the total the API reported."""
    return count > 0 and total is not None and offset + count > total


def build_page(
    items: list[T],
    *,
    offset: int,
    limit: int | None,
    total: int | None,
    metadata: dict[str, Any] | None = None,
    echoed_offset: Any = None,
) -> Page[T]:
    """Build a page, rejecting records that contradict the request or the total.

    ``echoed_offset`` is the offset the envelope reported, as it was received,
    for the endpoints that report one; ``None`` means the envelope stated
    nothing. Anything that is not an integer equal to *offset* is rejected: an
    unusable echo cannot show which page these records came from.
    """
    if limit is not None and len(items) > limit:
        raise PaginationError("The response exceeded the requested page size.", offset=offset)
    if echoed_offset is not None and (
        isinstance(echoed_offset, bool)
        or not isinstance(echoed_offset, int)
        or echoed_offset != offset
    ):
        raise PaginationError(
            "The returned offset does not match the requested page.", offset=offset
        )
    if exceeds_total(len(items), total, offset):
        raise _RecordsPastTotalError(
            "The response returned more records than its stated total allows.",
            offset=offset,
            records=list(items),
            metadata=metadata,
        )
    return Page(
        items=items,
        total=total,
        offset=offset,
        limit=limit,
        metadata={} if metadata is None else metadata,
        has_more=None if total is None else offset + len(items) < total,
    )


def _make_page(
    items: list[T],
    metadata: dict[str, Any],
    offset: int,
    limit: int | None,
) -> Page[T]:
    """Build an offset page using explicit total fields, never page counts."""
    return build_page(
        items,
        offset=offset,
        limit=limit,
        total=select_total(metadata),
        metadata=metadata,
    )


def local_page(
    items: list[T],
    metadata: dict[str, Any],
    offset: int,
    limit: int | None,
) -> Page[T]:
    """Window a whole-collection response locally, for operations declaring no paging.

    ``GET /infrastructure/publishers`` declares one query parameter, ``fields``
    (``infrastructure/npa_publishers.yaml:1024-1032``), and ``GET /policy/urllist``
    declares ``pending`` and ``field`` (``policy/urllist.yaml:132-156``): neither
    takes an ``offset`` or a ``limit``, so the request cannot carry a window and
    the response is the whole collection. The caller's window is therefore
    applied to the records already in hand, and the complete collection
    establishes ``has_more`` without needing a total.

    The stated ``total`` is reported as received, even when it disagrees with
    the number of records. ``npa_publishers.yaml:877`` declares it, and the
    client has no better information about how many records exist than the
    service that counted them; a disagreement means the service capped its own
    response, which is worth surfacing rather than hiding. ``has_more`` is
    derived from the records in hand, not from the total, so a wrong total
    cannot make the traversal skip anything.
    """
    total = select_total(metadata)
    window = items[offset:] if offset else items
    if limit is not None:
        window = window[:limit]
    # The page is built without the total so `build_page`'s records-past-total
    # guard does not fire: that guard protects a *traversal* from a shrinking
    # total, and there is no traversal here. The stated total is attached after.
    page = build_page(window, offset=offset, limit=limit, total=None, metadata=metadata)
    page.total = total
    page.has_more = offset + len(window) < len(items)
    page.windowed_locally = True
    return page


def _total_metadata(body: Any) -> dict[str, Any]:
    """Keep the envelope fields that state a total, without the records.

    Two documented shapes carry one: a ``status`` object holding the total, and
    a total stated beside the records; ``steering/npa_apps_private.yaml:27-30``,
    ``steering/npa_private_tag.yaml:315-317``, ``steering/ipsec.yaml:24-26``.
    Keeping only the first left every lazy iterator without the stated total its
    typed counterpart reads from the same body, so the traversal had no
    early stop and the page reported no continuation.
    """
    if not isinstance(body, dict):
        return {}
    metadata: dict[str, Any] = {}
    if isinstance(body.get("status"), dict):
        metadata["status"] = body["status"]
    for name in ("total", "totalResults"):
        if name in body:
            metadata[name] = body[name]
    return metadata


def _raw_records(
    body: Any,
    data_key: str,
    extract: Callable[[dict[str, Any]], list[dict[str, Any]]] | None,
) -> list[Any]:
    """Locate this envelope's records the way the legacy iterators always have."""
    if not isinstance(body, (dict, list)):
        raise ValueError("Expected a JSON object or array.")
    envelope: Any = body
    raw_items: Any
    if extract is not None:
        raw_items = extract(envelope)
    elif isinstance(envelope, list):
        raw_items = envelope
    else:
        raw_items = envelope.get(data_key, envelope.get("result", []))
        if isinstance(raw_items, dict):
            raw_items = raw_items.get("data", [])
    return raw_items if isinstance(raw_items, list) else []


def _scim_records(
    body: Any,
    extract: Callable[[dict[str, Any]], list[dict[str, Any]]] | None,
) -> list[Any]:
    """Locate a SCIM page's records; RFC 7644 states a ``ListResponse`` object."""
    if not isinstance(body, dict):
        raise ValueError("Expected a SCIM list response object.")
    raw_items = body.get("Resources", []) if extract is None else extract(body)
    return raw_items if isinstance(raw_items, list) else []


def _scim_page(items: list[T], body: Any, start_index: int, count: int) -> Page[T]:
    """Build a SCIM page under the checks every other page decoder applies.

    ``startIndex`` is one-based; the page reports the zero-based offset the rest
    of the SDK uses.
    """
    if isinstance(body, dict) and "startIndex" in body:
        echoed = body["startIndex"]
        if (
            isinstance(echoed, bool)
            or not isinstance(echoed, (int, str))
            or str(echoed) != str(start_index)
        ):
            raise PaginationError(
                "The SCIM response startIndex does not match the requested page.",
                offset=start_index - 1,
            )
    return build_page(
        items,
        offset=start_index - 1,
        limit=count,
        total=coerce_total(body.get("totalResults")) if isinstance(body, dict) else None,
    )


def _request_context(response: httpx.Response) -> tuple[str | None, str | None, str | None]:
    """Return the method, path and request id a page decoder cannot see."""
    try:
        method: str | None = response.request.method
        path: str | None = response.request.url.path
    except RuntimeError:
        method = path = None
    request_id: str | None = response.headers.get("x-request-id")
    return method, path, request_id


def _decode_failure(
    response: httpx.Response,
    message: str,
    field_errors: tuple[tuple[tuple[str | int, ...], str], ...] = (),
) -> ResponseValidationError:
    """Restate a decoding failure as an SDK error carrying the request context."""
    method, path, request_id = _request_context(response)
    return ResponseValidationError(
        message,
        request_method=method,
        request_path=path,
        request_id=request_id,
        field_errors=field_errors,
    )


def _model_failure(exc: ModelValidationError, response: httpx.Response) -> ResponseValidationError:
    return _decode_failure(
        response,
        "The API response does not match the expected schema.",
        tuple((tuple(error["loc"]), error["type"]) for error in exc.errors()),
    )


def _add_request_context(error: PaginationError, response: httpx.Response) -> None:
    """Supply the request context page validation has no access to."""
    for name, value in zip(
        ("request_method", "request_path", "request_id"), _request_context(response), strict=True
    ):
        if value is not None and getattr(error, name) is None:
            setattr(error, name, value)


def _decode_body(response: httpx.Response) -> Any:
    """Decode a page envelope, restating codec and JSON faults as SDK errors."""
    try:
        return response.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Codec and JSON errors quote the body around a byte position.
        raise _decode_failure(response, "The API response body is not valid JSON.") from None
    except ValueError as exc:
        raise _decode_failure(response, f"The API response could not be decoded: {exc}") from exc


def _log_stale_total(offset: int, dropped: int) -> None:
    logger.warning(
        "Stopping pagination at offset %d: the page reaches past the reported total; "
        "%d records from that page were dropped.",
        offset,
        dropped,
    )


def _rescued_page(exc: _RecordsPastTotalError, offset: int, limit: int | None) -> Page[Any]:
    """Keep a first page whose stated total cannot account for its own records.

    Before any page is delivered there is no traversal to protect: a total the
    very first records outrun is unusable, not evidence that a collection ended.
    """
    logger.warning(
        "The reported total cannot account for the first page at offset %d (%d records); "
        "continuing without a total.",
        offset,
        len(exc.records),
    )
    return Page(
        items=exc.records,
        total=None,
        offset=offset,
        limit=limit,
        metadata=exc.metadata,
        has_more=None,
    )


def _traversal_ended(page: Page[Any], page_size: int) -> bool:
    """Whether this page ends an offset traversal, resolving a contradictory total.

    A page shorter than the requested size ends it: the next offset would skip
    the records the API withheld. A total still claiming more records cannot be
    honoured, so the page is left stating nothing about continuation rather than
    a completeness the traversal cannot support.
    """
    if page.has_more is False:
        return True
    if len(page.items) >= page_size:
        return False
    if page.has_more:
        logger.warning(
            "Stopping pagination at offset %d: the API returned fewer records (%d) than the "
            "requested page size (%d) while reporting more remain; continuing would skip records.",
            page.offset,
            len(page.items),
            page_size,
        )
        page.has_more = None
    return True


def _ceiling_reached(method: str, path: str, offset: int) -> PaginationError:
    """The traversal hit the page ceiling without the collection ending."""
    return PaginationError(
        f"Pagination stopped at the {_MAX_PAGES}-page safety limit at offset {offset}: "
        "the collection did not end. Narrow the query or raise the page size.",
        request_method=method,
        request_path=path,
        offset=offset,
    )


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
        parse_page: Callable[[Any, int, int | None], Page[T]] | None = None,
        paginated: bool = True,
    ) -> None:
        self._transport = transport
        self._method = method
        self._path = path
        self._params = dict(params)
        self._model = model
        self._page_size = page_size
        self._data_key = data_key
        self._extract = extract
        self._parse_page = parse_page
        self._paginated = paginated

    def _fetch_page(self, offset: int, delivered: int) -> Page[T] | None:
        """Fetch one page, or ``None`` when a stated total ends the traversal.

        *delivered* counts the pages already yielded: records past a stated
        total are evidence of a total that moved only once rows have shipped.
        """
        params = dict(self._params)
        if self._paginated:
            params.update({"limit": self._page_size, "offset": offset})
        # An unpaginated operation answers with its whole collection, which no
        # requested page size bounds.
        limit = self._page_size if self._paginated else None
        response = self._transport.request(self._method, self._path, params=params)
        body = _decode_body(response)

        try:
            if self._parse_page is not None:
                return self._parse_page(body, offset, limit)
            items = [
                self._model.model_validate(item)
                for item in _raw_records(body, self._data_key, self._extract)
            ]
            return _make_page(items, _total_metadata(body), offset, limit)
        except ModelValidationError as exc:
            raise _model_failure(exc, response) from None
        except _RecordsPastTotalError as exc:
            if delivered == 0:
                return _rescued_page(exc, offset, self._page_size)
            _log_stale_total(offset, len(exc.records))
            return None
        except PaginationError as exc:
            _add_request_context(exc, response)
            raise
        except ValueError as exc:
            raise _decode_failure(
                response, f"The API response could not be decoded: {exc}"
            ) from exc

    def pages(self) -> Iterator[Page[T]]:
        """Yield one :class:`Page` per API call.

        A page that contradicts its own request — more records than the page
        size, an offset echo naming another page — raises
        :class:`~netskope.exceptions.PaginationError` mid-iteration, after
        earlier pages have already been yielded. So does a traversal that
        reaches the page ceiling without the collection ending.

        An unpaginated operation (``paginated=False``) declares no ``offset`` or
        ``limit``, so there is no second page to ask for: its whole collection
        is fetched once, yielded as one page, and the iteration ends. Asking
        again with the same parameters would only re-deliver the same records.
        """
        if not self._paginated:
            page = self._fetch_page(0, 0)
            if page is not None:
                if page.total is not None and page.total > len(page.items):
                    raise PaginationError(
                        "The unpaginated response is incomplete.",
                        request_method=self._method,
                        request_path=self._path,
                        offset=0,
                    )
                page.has_more = False
                if page.items:
                    yield page
            return
        offset = 0
        consecutive_empty = 0
        delivered = 0
        for _ in range(_MAX_PAGES):
            page = self._fetch_page(offset, delivered)
            if page is None:
                return
            if not page.items:
                consecutive_empty += 1
                if consecutive_empty >= 2 or page.has_more is False:
                    return
                offset += self._page_size
                continue
            consecutive_empty = 0
            delivered += 1
            ended = _traversal_ended(page, self._page_size)
            yield page
            if ended:
                return
            offset += self._page_size
        raise _ceiling_reached(self._method, self._path, offset)

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
        parse_page: Callable[[Any, int, int | None], Page[T]] | None = None,
        paginated: bool = True,
    ) -> None:
        self._transport = transport
        self._method = method
        self._path = path
        self._params = dict(params)
        self._model = model
        self._page_size = page_size
        self._data_key = data_key
        self._extract = extract
        self._parse_page = parse_page
        self._paginated = paginated

    async def _fetch_page(self, offset: int, delivered: int) -> Page[T] | None:
        """Fetch one page, or ``None`` when a stated total ends the traversal.

        *delivered* counts the pages already yielded: records past a stated
        total are evidence of a total that moved only once rows have shipped.
        """
        params = dict(self._params)
        if self._paginated:
            params.update({"limit": self._page_size, "offset": offset})
        # An unpaginated operation answers with its whole collection, which no
        # requested page size bounds.
        limit = self._page_size if self._paginated else None
        response = await self._transport.request(self._method, self._path, params=params)
        body = _decode_body(response)

        try:
            if self._parse_page is not None:
                return self._parse_page(body, offset, limit)
            items = [
                self._model.model_validate(item)
                for item in _raw_records(body, self._data_key, self._extract)
            ]
            return _make_page(items, _total_metadata(body), offset, limit)
        except ModelValidationError as exc:
            raise _model_failure(exc, response) from None
        except _RecordsPastTotalError as exc:
            if delivered == 0:
                return _rescued_page(exc, offset, self._page_size)
            _log_stale_total(offset, len(exc.records))
            return None
        except PaginationError as exc:
            _add_request_context(exc, response)
            raise
        except ValueError as exc:
            raise _decode_failure(
                response, f"The API response could not be decoded: {exc}"
            ) from exc

    async def pages(self) -> AsyncIterator[Page[T]]:
        """Yield one :class:`Page` per API call.

        A page that contradicts its own request — more records than the page
        size, an offset echo naming another page — raises
        :class:`~netskope.exceptions.PaginationError` mid-iteration, after
        earlier pages have already been yielded. So does a traversal that
        reaches the page ceiling without the collection ending.

        An unpaginated operation (``paginated=False``) declares no ``offset`` or
        ``limit``, so there is no second page to ask for: its whole collection
        is fetched once, yielded as one page, and the iteration ends. Asking
        again with the same parameters would only re-deliver the same records.
        """
        if not self._paginated:
            page = await self._fetch_page(0, 0)
            if page is not None:
                if page.total is not None and page.total > len(page.items):
                    raise PaginationError(
                        "The unpaginated response is incomplete.",
                        request_method=self._method,
                        request_path=self._path,
                        offset=0,
                    )
                page.has_more = False
                if page.items:
                    yield page
            return
        offset = 0
        consecutive_empty = 0
        delivered = 0
        for _ in range(_MAX_PAGES):
            page = await self._fetch_page(offset, delivered)
            if page is None:
                return
            if not page.items:
                consecutive_empty += 1
                if consecutive_empty >= 2 or page.has_more is False:
                    return
                offset += self._page_size
                continue
            consecutive_empty = 0
            delivered += 1
            ended = _traversal_ended(page, self._page_size)
            yield page
            if ended:
                return
            offset += self._page_size
        raise _ceiling_reached(self._method, self._path, offset)

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


class SyncScimPaginatedResponse(Generic[T]):
    """SCIM-aware paginator using ``startIndex`` (1-based) and ``count`` per RFC 7644."""

    def __init__(
        self,
        transport: SyncTransport,
        method: str,
        path: str,
        params: dict[str, Any],
        model: type[T],
        page_size: int,
        extract: Callable[[dict[str, Any]], list[dict[str, Any]]] | None = None,
    ) -> None:
        self._transport = transport
        self._method = method
        self._path = path
        self._params = dict(params)
        self._model = model
        self._page_size = page_size
        self._extract = extract

    def _fetch_page(self, start_index: int, delivered: int) -> Page[T] | None:
        """Fetch one SCIM page, or ``None`` when a stated total ends the traversal."""
        params = {**self._params, "count": self._page_size, "startIndex": start_index}
        response = self._transport.request(self._method, self._path, params=params)
        body = _decode_body(response)

        try:
            items = [
                self._model.model_validate(item) for item in _scim_records(body, self._extract)
            ]
            return _scim_page(items, body, start_index, self._page_size)
        except ModelValidationError as exc:
            raise _model_failure(exc, response) from None
        except _RecordsPastTotalError as exc:
            if delivered == 0:
                return _rescued_page(exc, start_index - 1, self._page_size)
            _log_stale_total(start_index - 1, len(exc.records))
            return None
        except PaginationError as exc:
            _add_request_context(exc, response)
            raise
        except ValueError as exc:
            raise _decode_failure(
                response, f"The API response could not be decoded: {exc}"
            ) from exc

    def pages(self) -> Iterator[Page[T]]:
        """Yield one :class:`Page` per API call.

        A page that contradicts its own request — more records than ``count``, a
        ``startIndex`` naming another page — raises
        :class:`~netskope.exceptions.PaginationError` mid-iteration, after
        earlier pages have already been yielded. So does a traversal that
        reaches the page ceiling without the collection ending.
        """
        start_index = 1
        # Every iteration but the last yields a page, so the index counts them.
        for delivered in range(_MAX_PAGES):
            page = self._fetch_page(start_index, delivered)
            if page is None or not page.items:
                return
            ended = _traversal_ended(page, self._page_size)
            yield page
            if ended:
                return
            start_index += self._page_size
        raise _ceiling_reached(self._method, self._path, start_index - 1)

    def __iter__(self) -> Iterator[T]:
        for page in self.pages():
            yield from page.items

    def to_list(self, max_items: int = 10_000) -> list[T]:
        results: list[T] = []
        for item in self:
            results.append(item)
            if len(results) >= max_items:
                break
        return results

    def first(self) -> T | None:
        for item in self:
            return item
        return None


class AsyncScimPaginatedResponse(Generic[T]):
    """Async SCIM-aware paginator using ``startIndex`` (1-based) and ``count`` per RFC 7644."""

    def __init__(
        self,
        transport: AsyncTransport,
        method: str,
        path: str,
        params: dict[str, Any],
        model: type[T],
        page_size: int,
        extract: Callable[[dict[str, Any]], list[dict[str, Any]]] | None = None,
    ) -> None:
        self._transport = transport
        self._method = method
        self._path = path
        self._params = dict(params)
        self._model = model
        self._page_size = page_size
        self._extract = extract

    async def _fetch_page(self, start_index: int, delivered: int) -> Page[T] | None:
        """Fetch one SCIM page, or ``None`` when a stated total ends the traversal."""
        params = {**self._params, "count": self._page_size, "startIndex": start_index}
        response = await self._transport.request(self._method, self._path, params=params)
        body = _decode_body(response)

        try:
            items = [
                self._model.model_validate(item) for item in _scim_records(body, self._extract)
            ]
            return _scim_page(items, body, start_index, self._page_size)
        except ModelValidationError as exc:
            raise _model_failure(exc, response) from None
        except _RecordsPastTotalError as exc:
            if delivered == 0:
                return _rescued_page(exc, start_index - 1, self._page_size)
            _log_stale_total(start_index - 1, len(exc.records))
            return None
        except PaginationError as exc:
            _add_request_context(exc, response)
            raise
        except ValueError as exc:
            raise _decode_failure(
                response, f"The API response could not be decoded: {exc}"
            ) from exc

    async def pages(self) -> AsyncIterator[Page[T]]:
        """Yield one :class:`Page` per API call.

        A page that contradicts its own request — more records than ``count``, a
        ``startIndex`` naming another page — raises
        :class:`~netskope.exceptions.PaginationError` mid-iteration, after
        earlier pages have already been yielded. So does a traversal that
        reaches the page ceiling without the collection ending.
        """
        start_index = 1
        # Every iteration but the last yields a page, so the index counts them.
        for delivered in range(_MAX_PAGES):
            page = await self._fetch_page(start_index, delivered)
            if page is None or not page.items:
                return
            ended = _traversal_ended(page, self._page_size)
            yield page
            if ended:
                return
            start_index += self._page_size
        raise _ceiling_reached(self._method, self._path, start_index - 1)

    async def __aiter__(self) -> AsyncIterator[T]:
        async for page in self.pages():
            for item in page.items:
                yield item

    async def to_list(self, max_items: int = 10_000) -> list[T]:
        results: list[T] = []
        async for item in self:
            results.append(item)
            if len(results) >= max_items:
                break
        return results

    async def first(self) -> T | None:
        async for item in self:
            return item
        return None
