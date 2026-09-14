"""Shared decoding for operations with an explicitly selected envelope key."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, TypeAdapter

from netskope.core.pagination import Page, build_page, coerce_total
from netskope.exceptions import ResponseValidationError

T = TypeVar("T")
M = TypeVar("M", bound=BaseModel)


@contextmanager
def decoded(request_method: str, request_path: str) -> Iterator[None]:
    """Restate a decoder's ``ValueError`` as a ``ResponseValidationError``.

    Every typed accessor gets this conversion from :meth:`ApiResponse.parse`.
    The legacy methods that call a decoder directly on a ``_get`` body have no
    such boundary, so without this a caller's documented ``except
    NetskopeError`` misses the failure and sees a bare ``ValueError`` instead.
    """
    try:
        yield
    except ValueError as exc:
        raise ResponseValidationError(
            f"The API response could not be decoded: {exc}",
            request_method=request_method,
            request_path=request_path,
        ) from exc


def decode_body(
    response: httpx.Response, adapter: TypeAdapter[T], *, envelope: str | None = None
) -> T:
    payload = response.json()
    if envelope is not None and isinstance(payload, dict) and envelope in payload:
        payload = payload[envelope]
    return adapter.validate_python(payload)


def parse_object_page(
    payload: Any,
    model: type[M],
    *,
    records_key: str,
    total_key: str,
    offset: int,
    limit: int | None,
) -> Page[M]:
    """Decode only the collection/total keys selected by the endpoint owner."""
    if not isinstance(payload, dict) or not isinstance(payload.get(records_key), list):
        raise ValueError("Expected an object containing the documented record collection.")
    records = payload[records_key]
    if any(not isinstance(record, dict) for record in records):
        raise ValueError("The record collection must contain objects.")
    return build_page(
        [model.model_validate(record) for record in records],
        offset=offset,
        limit=limit,
        total=coerce_total(payload.get(total_key)),
        metadata={key: value for key, value in payload.items() if key != records_key},
        echoed_offset=payload.get("offset"),
    )
