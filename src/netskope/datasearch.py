"""Streaming datasearch scans with explicit termination evidence.

An exhausted fixed interval is not a transactional snapshot. Late ingestion
or changes to previously returned records can still affect offset traversal.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from hashlib import blake2b
from typing import Any, Generic, NoReturn, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from netskope.exceptions import PaginationError, ValidationError
from netskope.response import ApiResponse

T = TypeVar("T")

# The gateway contract states a `limit` default of 10000 and no maximum
# (events/search_alert.yaml:340-345). This ceiling is the SDK's own rail, not
# the endpoint's: it keeps one page inside the default the service is built
# around. The audit and infrastructure caps are different — those endpoints do
# declare `maximum: 5000` (events/audit.yaml:19-27,
# events/infrastructure.yaml:19-27) and are enforced per endpoint.
DATASEARCH_PAGE_CAP = 10_000

# `timeout` is a required query parameter on every /events/datasearch/* search
# with a default of 180 seconds (events/search_alert.yaml:313-319,
# search_app.yaml:344-350, search_network.yaml:219-225, search_page.yaml:284-290,
# search_incident.yaml:459-465, search_epdlp.yaml:174-180). The data/audit,
# data/infrastructure, and metrics/transactionevents endpoints do not declare it.
DATASEARCH_TIMEOUT_DEFAULT = 180


class DatasearchWindow(BaseModel):
    """Explicit epoch-second bounds, resolved before the first request."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    start_time: int
    end_time: int

    @model_validator(mode="after")
    def _ordered_bounds(self) -> Self:
        if self.end_time < self.start_time:
            raise ValueError("end_time must not precede start_time.")
        return self


class ScanStopReason(StrEnum):
    """Evidence that stopped a scan, rather than an implicit iterator limit."""

    SHORT_PAGE = "short_page"
    SERVER_TOTAL = "server_total"
    RECORD_LIMIT = "record_limit"
    PAGE_LIMIT = "page_limit"


class ScanSummary(BaseModel):
    """Counts for a fully consumed scan; exhaustion does not imply a snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fetched: int = Field(ge=0)
    requests: int = Field(ge=0)
    stop_reason: ScanStopReason

    @property
    def exhausted(self) -> bool:
        """Whether endpoint evidence, rather than a caller limit, ended the scan."""
        return self.stop_reason in (ScanStopReason.SHORT_PAGE, ScanStopReason.SERVER_TOTAL)


@dataclass
class _ScanPage(Generic[T]):
    value: T
    identities: list[str | None]
    total: int | None
    response: ApiResponse[Any]


class _ScanState:
    """Shared sync/async transitions, retaining O(page_size + max_pages) hashes."""

    def __init__(self, *, page_size: int, max_records: int | None, max_pages: int) -> None:
        for name, value in (("page_size", page_size), ("max_pages", max_pages)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValidationError(f"{name} must be a positive integer.")
        if page_size > DATASEARCH_PAGE_CAP:
            raise ValidationError(f"page_size must not exceed {DATASEARCH_PAGE_CAP}.")
        if max_records is not None and (
            isinstance(max_records, bool) or not isinstance(max_records, int) or max_records < 1
        ):
            raise ValidationError("max_records must be a positive integer or None.")
        self.page_size = page_size
        self.max_records = max_records
        self.max_pages = max_pages
        self.fetched = 0
        self.requests = 0
        self.summary: ScanSummary | None = None
        self._stop_reason: ScanStopReason | None = None
        self._closed = False
        self._total: int | None = None
        self._previous_ids: set[bytes] = set()
        self._first_ids: set[bytes] = set()
        self._fingerprints: set[bytes] = set()

    def close(self) -> None:
        self._closed = True
        self._previous_ids.clear()
        self._first_ids.clear()
        self._fingerprints.clear()

    def next_request(self) -> tuple[int, int] | None:
        if self._closed:
            return None
        if self._stop_reason is not None:
            self.summary = ScanSummary(
                fetched=self.fetched, requests=self.requests, stop_reason=self._stop_reason
            )
            self.close()
            return None
        remaining = self.page_size if self.max_records is None else self.max_records - self.fetched
        return self.fetched, min(self.page_size, remaining)

    def accept(self, page: _ScanPage[Any], limit: int) -> None:
        def fail(message: str) -> NoReturn:
            raise PaginationError(
                message,
                request_method=page.response.request_method,
                request_path=page.response.request_path,
                request_id=page.response.request_id,
                offset=self.fetched,
            )

        count = len(page.identities)
        if count > limit:
            fail("The API returned more records than the requested scan limit.")
        ids: list[bytes] = []
        for identity in page.identities:
            if not isinstance(identity, str) or not identity.strip():
                fail("The API omitted a usable _id required for safe offset scanning.")
            ids.append(blake2b(identity.encode(), digest_size=16).digest())
        distinct = set(ids)
        if len(distinct) != count:
            fail("The API returned duplicate record identities within a scan page.")
        if ids:
            fingerprint = blake2b(b"".join(sorted(ids)), digest_size=16).digest()
            if (
                ids[0] in self._first_ids
                or fingerprint in self._fingerprints
                or distinct & self._previous_ids
            ):
                fail("The API repeated records across scan offsets; traversal is not trustworthy.")
            self._first_ids.add(ids[0])
            self._fingerprints.add(fingerprint)
        self._previous_ids = distinct

        if page.total is not None:
            if self._total is not None and page.total != self._total:
                fail("The API changed its stated total during the scan.")
            self._total = page.total
        end = self.fetched + count
        if self._total is not None:
            if end > self._total:
                fail("The API returned records beyond its stated total.")
            if count == 0 and end < self._total:
                fail("The API returned an empty page before its stated total was reached.")
        self.fetched = end
        self.requests += 1
        if self._total is not None and end == self._total:
            self._stop_reason = ScanStopReason.SERVER_TOTAL
        elif count < limit and self._total is None:
            self._stop_reason = ScanStopReason.SHORT_PAGE
        elif self.max_records is not None and end >= self.max_records:
            self._stop_reason = ScanStopReason.RECORD_LIMIT
        elif self.requests >= self.max_pages:
            self._stop_reason = ScanStopReason.PAGE_LIMIT


class ScanIterator(Iterator[T]):
    """A single-pass scan. ``summary`` stays absent until iteration finishes.

    Construct scans through a resource's ``scan_pages`` method. Every yielded
    value corresponds to one HTTP request, including an empty terminal page.
    """

    def __init__(
        self,
        fetch: Callable[[int, int], _ScanPage[T]],
        *,
        window: DatasearchWindow,
        page_size: int,
        max_records: int | None,
        max_pages: int,
    ) -> None:
        self._window = window
        self._fetch = fetch
        self._state = _ScanState(page_size=page_size, max_records=max_records, max_pages=max_pages)

    @property
    def window(self) -> DatasearchWindow:
        """The resolved epoch-second bounds every request in this scan uses."""
        return self._window

    @property
    def summary(self) -> ScanSummary | None:
        """The :class:`ScanSummary` once iteration has finished, otherwise ``None``."""
        return self._state.summary

    def __next__(self) -> T:
        request = self._state.next_request()
        if request is None:
            raise StopIteration
        offset, limit = request
        try:
            page = self._fetch(offset, limit)
            self._state.accept(page, limit)
        except BaseException:
            self.close()
            raise
        return page.value

    def close(self) -> None:
        """Abandon iteration without claiming exhaustion."""
        self._state.close()


class AsyncScanIterator(AsyncIterator[T]):
    """Asynchronous counterpart of :class:`ScanIterator`."""

    def __init__(
        self,
        fetch: Callable[[int, int], Awaitable[_ScanPage[T]]],
        *,
        window: DatasearchWindow,
        page_size: int,
        max_records: int | None,
        max_pages: int,
    ) -> None:
        self._window = window
        self._fetch = fetch
        self._state = _ScanState(page_size=page_size, max_records=max_records, max_pages=max_pages)

    @property
    def window(self) -> DatasearchWindow:
        """The resolved epoch-second bounds every request in this scan uses."""
        return self._window

    @property
    def summary(self) -> ScanSummary | None:
        """The :class:`ScanSummary` once iteration has finished, otherwise ``None``."""
        return self._state.summary

    async def __anext__(self) -> T:
        request = self._state.next_request()
        if request is None:
            raise StopAsyncIteration
        offset, limit = request
        try:
            page = await self._fetch(offset, limit)
            self._state.accept(page, limit)
        except BaseException:
            await self.aclose()
            raise
        return page.value

    async def aclose(self) -> None:
        """Abandon iteration without claiming exhaustion."""
        self._state.close()
