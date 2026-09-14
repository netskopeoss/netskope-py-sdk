"""Device-tag response decoding and POST-body continuation."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from typing import Any, NoReturn

import httpx

from netskope.core.pagination import Page, build_page, coerce_total
from netskope.core.resource import AsyncResource, SyncResource
from netskope.core.response_list import extract_response_list
from netskope.exceptions import NotFoundError, PaginationError, ValidationError
from netskope.models.devices import DeviceTag
from netskope.resources.devices.paths import (
    _TAGS_DEFAULT_LIMIT,
    _TAGS_MAX_LIMIT,
    _TAGS_PATH,
    _TAGS_QUERY_PATH,
    _build_create_payload,
    _build_tags_query,
    _build_update_payload,
    _coerce_tag_id,
)
from netskope.response import ApiResponse


def _page_number(value: Any) -> int | None:
    """Read one tag paging field; a present but unusable value is an error, not silence."""
    if value is None:
        return None
    number = coerce_total(value)
    if number is None:
        raise ValueError("Invalid tag pagination metadata.")
    return number


def _parse_page(body: Any, offset: int, limit: int) -> Page[DeviceTag]:
    records = extract_response_list(body, "data")
    metadata = {}
    paging = {}
    if isinstance(body, dict):
        metadata = {
            key: value for key, value in body.items() if key not in {"data", "result", "Resources"}
        }
        data = body.get("data")
        if isinstance(data, dict):
            paging = {key: value for key, value in data.items() if key != "data"}
            metadata["data"] = paging
        else:
            paging = metadata
    total = _page_number(paging.get("total_count"))
    echoed_offset = _page_number(paging.get("offset"))
    _page_number(paging.get("limit"))
    return build_page(
        [DeviceTag.model_validate(record) for record in records],
        offset=offset,
        limit=limit,
        total=total,
        metadata=metadata,
        echoed_offset=echoed_offset,
    )


def _parse_tag(response: httpx.Response, tag_id: int) -> DeviceTag:
    body = response.json()
    records = extract_response_list(body, "data")
    if not records:
        raise NotFoundError(
            f"Device tag {tag_id} not found",
            status_code=404,
            body=body if isinstance(body, dict) else None,
            request_method=response.request.method,
            request_path=response.request.url.path,
            request_id=response.headers.get("x-request-id"),
        )
    if len(records) != 1:
        raise ValueError("Device tag lookup did not return exactly one record.")
    tag = DeviceTag.model_validate(records[0])
    if tag.id != tag_id:
        raise ValueError("Device tag lookup returned an unexpected identity.")
    return tag


def _parse_mutated_tag(body: Any, tag_id: int | None = None) -> DeviceTag:
    if not isinstance(body, dict):
        raise ValueError("Expected a device-tag object or response envelope.")
    record = body
    if "id" not in body:
        for key in ("data", "result"):
            if key in body:
                record = body[key]
                break
    if not isinstance(record, dict):
        raise ValueError("The device-tag mutation did not return a tag object.")
    if isinstance(record.get("id"), bool):
        raise ValueError("The device-tag mutation did not return a numeric identity.")
    tag = DeviceTag.model_validate(record)
    if tag.id is None:
        raise ValueError("The device-tag mutation did not return a tag identity.")
    if tag_id is not None and tag.id != tag_id:
        raise ValueError("The device-tag mutation returned an unexpected identity.")
    return tag


@dataclass
class _TagTraversal:
    offset: int
    page_size: int
    max_pages: int
    # TagResponseDto.id is `type: number` (devices/tag.yaml:738-741).
    seen_ids: set[int | float] = field(default_factory=set)
    total: int | None = None

    def __post_init__(self) -> None:
        _build_tags_query(None, self.offset, self.page_size)
        if (
            isinstance(self.max_pages, bool)
            or not isinstance(self.max_pages, int)
            or not 1 <= self.max_pages <= 1_000
        ):
            raise ValidationError("max_pages must be an integer between 1 and 1000.")

    def fail(self, response: ApiResponse[Page[DeviceTag]], message: str) -> NoReturn:
        raise PaginationError(
            message,
            request_method=response.request_method,
            request_path=response.request_path,
            request_id=response.request_id,
            offset=response.parse().offset,
        )

    def advance(self, response: ApiResponse[Page[DeviceTag]]) -> bool:
        page = response.parse()
        paging = page.metadata.get("data", page.metadata)
        returned_offset = _page_number(paging.get("offset"))
        if returned_offset is not None and returned_offset != self.offset:
            self.fail(response, "The device-tag API did not honor the requested offset.")
        size = len(page.items)
        if size > self.page_size:
            self.fail(response, "The device-tag API returned more records than requested.")
        if page.total is not None:
            if self.total is not None and page.total != self.total:
                self.fail(response, "The device-tag API changed its total during traversal.")
            self.total = page.total
        if self.total is not None:
            if size and self.offset + size > self.total:
                self.fail(response, "The device-tag page contradicts its reported total.")
            if not size and self.offset < self.total:
                self.fail(response, "The device-tag API returned an empty page before its total.")
        ids: set[int | float] = set()
        for item in page.items:
            if item.id is None:
                self.fail(
                    response, "The device-tag page lacks identities required for safe traversal."
                )
            if item.id in ids or item.id in self.seen_ids:
                self.fail(response, "The device-tag API repeated records during traversal.")
            ids.add(item.id)
        # At most 100 records per page and 1000 pages bounds the identity history.
        self.seen_ids.update(ids)
        self.offset += size
        return size == 0 or (self.total is not None and self.offset >= self.total)


class DeviceTagResponses(SyncResource):
    """Same-request response access for synchronous tag operations."""

    def create(self, name: str, *, description: str | None = None) -> ApiResponse[DeviceTag]:
        """Create a tag in one non-retried write and retain its original response."""
        payload = _build_create_payload(name, description)
        response = self._transport.request("POST", _TAGS_PATH, json=payload, retry_safe=False)
        return ApiResponse(response, lambda raw: _parse_mutated_tag(raw.json()))

    def update(
        self,
        tag_id: int | str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> ApiResponse[DeviceTag]:
        """Patch supplied fields; None means omitted, not cleared."""
        coerced = _coerce_tag_id(tag_id)
        payload = _build_update_payload(name, description)
        response = self._transport.request(
            "PATCH", f"{_TAGS_PATH}/{coerced}", json=payload, retry_safe=False
        )
        return ApiResponse(response, lambda raw: _parse_mutated_tag(raw.json(), coerced))

    def list_page(
        self,
        *,
        name: str | None = None,
        offset: int = 0,
        limit: int = _TAGS_DEFAULT_LIMIT,
    ) -> ApiResponse[Page[DeviceTag]]:
        response = self._transport.request(
            "POST",
            _TAGS_QUERY_PATH,
            json=_build_tags_query(name, offset, limit),
            retry_safe=True,
        )
        return ApiResponse(response, lambda raw: _parse_page(raw.json(), offset, limit))

    def get(self, tag_id: int | str) -> ApiResponse[DeviceTag]:
        coerced = _coerce_tag_id(tag_id)
        response = self._transport.request(
            "POST", _TAGS_QUERY_PATH, json={"id": coerced}, retry_safe=True
        )
        return ApiResponse(response, lambda raw: _parse_tag(raw, coerced))

    def iter_pages(
        self,
        *,
        name: str | None = None,
        offset: int = 0,
        page_size: int = _TAGS_MAX_LIMIT,
        max_pages: int = 1_000,
    ) -> Iterator[ApiResponse[Page[DeviceTag]]]:
        """Retain each page response; incomplete or repeated pages raise."""
        state = _TagTraversal(offset, page_size, max_pages)
        for _ in range(max_pages):
            response = self.list_page(name=name, offset=state.offset, limit=page_size)
            done = state.advance(response)
            yield response
            if done:
                return
        state.fail(response, "Device-tag traversal reached its page limit before completion.")


class AsyncDeviceTagResponses(AsyncResource):
    """Same-request response access for asynchronous tag operations."""

    async def create(self, name: str, *, description: str | None = None) -> ApiResponse[DeviceTag]:
        """Create a tag in one non-retried write and retain its original response."""
        payload = _build_create_payload(name, description)
        response = await self._transport.request("POST", _TAGS_PATH, json=payload, retry_safe=False)
        return ApiResponse(response, lambda raw: _parse_mutated_tag(raw.json()))

    async def update(
        self,
        tag_id: int | str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> ApiResponse[DeviceTag]:
        """Patch supplied fields; None means omitted, not cleared."""
        coerced = _coerce_tag_id(tag_id)
        payload = _build_update_payload(name, description)
        response = await self._transport.request(
            "PATCH", f"{_TAGS_PATH}/{coerced}", json=payload, retry_safe=False
        )
        return ApiResponse(response, lambda raw: _parse_mutated_tag(raw.json(), coerced))

    async def list_page(
        self,
        *,
        name: str | None = None,
        offset: int = 0,
        limit: int = _TAGS_DEFAULT_LIMIT,
    ) -> ApiResponse[Page[DeviceTag]]:
        response = await self._transport.request(
            "POST",
            _TAGS_QUERY_PATH,
            json=_build_tags_query(name, offset, limit),
            retry_safe=True,
        )
        return ApiResponse(response, lambda raw: _parse_page(raw.json(), offset, limit))

    async def get(self, tag_id: int | str) -> ApiResponse[DeviceTag]:
        coerced = _coerce_tag_id(tag_id)
        response = await self._transport.request(
            "POST", _TAGS_QUERY_PATH, json={"id": coerced}, retry_safe=True
        )
        return ApiResponse(response, lambda raw: _parse_tag(raw, coerced))

    async def iter_pages(
        self,
        *,
        name: str | None = None,
        offset: int = 0,
        page_size: int = _TAGS_MAX_LIMIT,
        max_pages: int = 1_000,
    ) -> AsyncIterator[ApiResponse[Page[DeviceTag]]]:
        """Retain each page response; see :meth:`DeviceTagResponses.iter_pages`."""
        state = _TagTraversal(offset, page_size, max_pages)
        for _ in range(max_pages):
            response = await self.list_page(name=name, offset=state.offset, limit=page_size)
            done = state.advance(response)
            yield response
            if done:
                return
        state.fail(response, "Device-tag traversal reached its page limit before completion.")
