"""Typed AICC operations with bounded, checked SDK-owned pagination."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

import httpx
from pydantic import TypeAdapter
from pydantic import ValidationError as ModelValidationError

from netskope._transport import AsyncTransport, SyncTransport
from netskope.exceptions import PaginationError, ValidationError
from netskope.models.aicc import AiccQuery, AiccSort
from netskope.models.common import NetskopeModel
from netskope.pagination import Page
from netskope.resources._aicc_contract import QUERY_RULES
from netskope.resources._typed_response import decode_body, parse_object_page
from netskope.response import ApiResponse

T = TypeVar("T", bound=NetskopeModel)
Q = TypeVar("Q", bound=AiccQuery)


@dataclass(frozen=True)
class AiccEndpoint(Generic[T, Q]):
    path: str
    contract: str
    model: type[T]
    query_type: type[Q]
    records_key: str = "items"
    identity_field: str | None = None

    def params(self, query: Q) -> dict[str, Any]:
        try:
            checked = self.query_type.model_validate(query)
        except ModelValidationError as exc:
            raise ValidationError(
                "Invalid AICC query. Check its fields and reporting window."
            ) from exc
        params = checked.model_dump(mode="json", by_alias=True, exclude_none=True)
        sort = getattr(checked, "sort", None)
        if isinstance(sort, AiccSort):
            params["sort"] = sort.model_dump_json()
        rules = QUERY_RULES[self.contract]
        allowed = {name for name, *_ in rules}
        if unsupported := params.keys() - allowed:
            raise ValidationError(
                f"This AICC operation does not support: {', '.join(sorted(unsupported))}."
            )
        for name, required, _, choices in rules:
            if required and name not in params:
                raise ValidationError(f"This AICC operation requires {name}.")
            if choices and name in params and params[name] not in choices:
                raise ValidationError(f"Invalid AICC {name}; expected one of {', '.join(choices)}.")
        return params

    @property
    def supports_pagination(self) -> bool:
        return any(name == "offset" for name, *_ in QUERY_RULES[self.contract])

    def page_params(self, query: Q, limit: int | None, offset: int | None) -> dict[str, Any]:
        params = self.params(query)
        if not self.supports_pagination:
            if limit is not None or offset is not None:
                raise ValidationError("This AICC operation does not support limit or offset.")
            return params
        maximum = next(
            maximum for name, _, maximum, _ in QUERY_RULES[self.contract] if name == "limit"
        )
        if limit is not None:
            if (
                isinstance(limit, bool)
                or not isinstance(limit, int)
                or not 1 <= limit <= (maximum or 200)
            ):
                raise ValidationError(f"AICC limit must be between 1 and {maximum or 200}.")
            params["limit"] = limit
        if offset is not None:
            if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
                raise ValidationError("AICC offset must be a nonnegative integer.")
            params["offset"] = offset
        return params

    def decode_page(
        self,
        response: httpx.Response,
        limit: int | None,
        offset: int | None,
        *,
        trust_total: bool = True,
    ) -> Page[T]:
        payload = response.json()
        if isinstance(payload, dict) and "data" in payload:
            payload = payload["data"]
        if not trust_total and isinstance(payload, dict):
            # include_total=false returns a page-local count, not a collection total.
            payload = {name: value for name, value in payload.items() if name != "total"}
        return parse_object_page(
            payload,
            self.model,
            records_key=self.records_key,
            total_key="total",
            offset=offset or 0,
            limit=limit,
        )


@dataclass
class _Continuation:
    max_pages: int
    max_records: int
    path: str
    identity_field: str | None
    pages: int = 0
    records: int = 0
    total: int | None = None
    fingerprints: set[bytes] = field(default_factory=set)
    identities: set[str] = field(default_factory=set)

    def fail(self, message: str, offset: int) -> None:
        raise PaginationError(message, request_method="GET", request_path=self.path, offset=offset)

    def check(self, page: Page[T], limit: int, stop_after: int | None = None) -> bool:
        self.pages += 1
        if self.total is not None and page.total is not None and self.total != page.total:
            self.fail(
                "AICC total changed during pagination; the export is incomplete.", page.offset
            )
        if page.total is not None:
            self.total = page.total
        if self.total is not None and page.items and page.offset + len(page.items) > self.total:
            self.fail("AICC page extends beyond its earlier reported total.", page.offset)
        if not page.items:
            if self.total is not None and page.offset < self.total:
                self.fail("AICC returned an empty page before its reported total.", page.offset)
            return False
        digest = hashlib.sha256()
        for item in page.items:
            digest.update(item.model_dump_json().encode())
            digest.update(b"\n")
            if self.identity_field:
                identity = str(getattr(item, self.identity_field))
                if identity in self.identities:
                    self.fail("AICC repeated a record during pagination.", page.offset)
                self.identities.add(identity)
        fingerprint = digest.digest()
        if fingerprint in self.fingerprints:
            self.fail("AICC repeated a page during pagination.", page.offset)
        self.fingerprints.add(fingerprint)
        self.records += len(page.items)
        more = (
            page.offset + len(page.items) < self.total
            if self.total is not None
            else len(page.items) == limit
        )
        more = more and (stop_after is None or self.records < stop_after)
        if more and (self.pages >= self.max_pages or self.records >= self.max_records):
            self.fail(
                "AICC scan reached its safety limit; narrow the query before exporting.",
                page.offset,
            )
        return more


def _positive(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationError(f"{name} must be a positive integer.")


def _scan_limits(page_size: int, max_pages: int, max_records: int, stop_after: int | None) -> None:
    _positive("page_size", page_size)
    _positive("max_pages", max_pages)
    _positive("max_records", max_records)
    if stop_after is not None:
        _positive("stop_after", stop_after)
        if stop_after > max_records:
            raise ValidationError("stop_after cannot exceed max_records.")


class AiccReadResponses(Generic[T, Q]):
    def __init__(self, transport: SyncTransport, endpoint: AiccEndpoint[T, Q]) -> None:
        self._transport = transport
        self._endpoint = endpoint

    def get(self, query: Q) -> ApiResponse[T]:
        response = self._transport.request(
            "GET", self._endpoint.path, params=self._endpoint.params(query)
        )
        adapter = TypeAdapter(self._endpoint.model)
        return ApiResponse(response, lambda raw: decode_body(raw, adapter, envelope="data"))


class AiccRead(Generic[T, Q]):
    def __init__(self, transport: SyncTransport, endpoint: AiccEndpoint[T, Q]) -> None:
        self.with_response = AiccReadResponses(transport, endpoint)
        self.query_type = endpoint.query_type

    def get(self, query: Q) -> T:
        return self.with_response.get(query).parse()


class AiccCollectionResponses(Generic[T, Q]):
    def __init__(self, transport: SyncTransport, endpoint: AiccEndpoint[T, Q]) -> None:
        self._transport = transport
        self._endpoint = endpoint

    def list_page(
        self, query: Q, *, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[Page[T]]:
        params = self._endpoint.page_params(query, limit, offset)
        response = self._transport.request("GET", self._endpoint.path, params=params)
        return ApiResponse(
            response,
            lambda raw: self._endpoint.decode_page(
                raw, limit, offset, trust_total=params.get("include_total") is not False
            ),
        )

    def iter_pages(
        self,
        query: Q,
        *,
        page_size: int = 100,
        max_pages: int = 1000,
        max_records: int = 100000,
        stop_after: int | None = None,
    ) -> Iterator[ApiResponse[Page[T]]]:
        _scan_limits(page_size, max_pages, max_records, stop_after)
        if not self._endpoint.supports_pagination:
            if stop_after is not None:
                raise ValidationError("This AICC operation does not support a bounded prefix.")
            response = self.list_page(query)
            page = response.parse()
            if len(page.items) > max_records or page.has_more:
                raise PaginationError(
                    "This unpaginated AICC response cannot establish a complete export."
                )
            yield response
            return
        state = _Continuation(
            max_pages, max_records, self._endpoint.path, self._endpoint.identity_field
        )
        offset = 0
        while True:
            limit = min(page_size, (stop_after or max_records) - state.records)
            response = self.list_page(query, limit=limit, offset=offset)
            page = response.parse()
            more = state.check(page, limit, stop_after)
            yield response
            if not more:
                return
            offset += len(page.items)


class AiccCollection(Generic[T, Q]):
    def __init__(self, transport: SyncTransport, endpoint: AiccEndpoint[T, Q]) -> None:
        self.with_response = AiccCollectionResponses(transport, endpoint)
        self.query_type = endpoint.query_type
        self.supports_pagination = endpoint.supports_pagination
        self.records_key = endpoint.records_key

    def list_page(
        self, query: Q, *, limit: int | None = None, offset: int | None = None
    ) -> Page[T]:
        return self.with_response.list_page(query, limit=limit, offset=offset).parse()

    def iter_pages(
        self,
        query: Q,
        *,
        page_size: int = 100,
        max_pages: int = 1000,
        max_records: int = 100000,
        stop_after: int | None = None,
    ) -> Iterator[Page[T]]:
        for response in self.with_response.iter_pages(
            query,
            page_size=page_size,
            max_pages=max_pages,
            max_records=max_records,
            stop_after=stop_after,
        ):
            yield response.parse()


class AsyncAiccReadResponses(Generic[T, Q]):
    def __init__(self, transport: AsyncTransport, endpoint: AiccEndpoint[T, Q]) -> None:
        self._transport = transport
        self._endpoint = endpoint

    async def get(self, query: Q) -> ApiResponse[T]:
        response = await self._transport.request(
            "GET", self._endpoint.path, params=self._endpoint.params(query)
        )
        adapter = TypeAdapter(self._endpoint.model)
        return ApiResponse(response, lambda raw: decode_body(raw, adapter, envelope="data"))


class AsyncAiccRead(Generic[T, Q]):
    def __init__(self, transport: AsyncTransport, endpoint: AiccEndpoint[T, Q]) -> None:
        self.with_response = AsyncAiccReadResponses(transport, endpoint)
        self.query_type = endpoint.query_type

    async def get(self, query: Q) -> T:
        return (await self.with_response.get(query)).parse()


class AsyncAiccCollectionResponses(Generic[T, Q]):
    def __init__(self, transport: AsyncTransport, endpoint: AiccEndpoint[T, Q]) -> None:
        self._transport = transport
        self._endpoint = endpoint

    async def list_page(
        self, query: Q, *, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[Page[T]]:
        params = self._endpoint.page_params(query, limit, offset)
        response = await self._transport.request("GET", self._endpoint.path, params=params)
        return ApiResponse(
            response,
            lambda raw: self._endpoint.decode_page(
                raw, limit, offset, trust_total=params.get("include_total") is not False
            ),
        )

    async def iter_pages(
        self,
        query: Q,
        *,
        page_size: int = 100,
        max_pages: int = 1000,
        max_records: int = 100000,
        stop_after: int | None = None,
    ) -> AsyncIterator[ApiResponse[Page[T]]]:
        _scan_limits(page_size, max_pages, max_records, stop_after)
        if not self._endpoint.supports_pagination:
            if stop_after is not None:
                raise ValidationError("This AICC operation does not support a bounded prefix.")
            response = await self.list_page(query)
            page = response.parse()
            if len(page.items) > max_records or page.has_more:
                raise PaginationError(
                    "This unpaginated AICC response cannot establish a complete export."
                )
            yield response
            return
        state = _Continuation(
            max_pages, max_records, self._endpoint.path, self._endpoint.identity_field
        )
        offset = 0
        while True:
            limit = min(page_size, (stop_after or max_records) - state.records)
            response = await self.list_page(query, limit=limit, offset=offset)
            page = response.parse()
            more = state.check(page, limit, stop_after)
            yield response
            if not more:
                return
            offset += len(page.items)


class AsyncAiccCollection(Generic[T, Q]):
    def __init__(self, transport: AsyncTransport, endpoint: AiccEndpoint[T, Q]) -> None:
        self.with_response = AsyncAiccCollectionResponses(transport, endpoint)
        self.query_type = endpoint.query_type
        self.supports_pagination = endpoint.supports_pagination
        self.records_key = endpoint.records_key

    async def list_page(
        self, query: Q, *, limit: int | None = None, offset: int | None = None
    ) -> Page[T]:
        return (await self.with_response.list_page(query, limit=limit, offset=offset)).parse()

    async def iter_pages(
        self,
        query: Q,
        *,
        page_size: int = 100,
        max_pages: int = 1000,
        max_records: int = 100000,
        stop_after: int | None = None,
    ) -> AsyncIterator[Page[T]]:
        async for response in self.with_response.iter_pages(
            query,
            page_size=page_size,
            max_pages=max_pages,
            max_records=max_records,
            stop_after=stop_after,
        ):
            yield response.parse()
