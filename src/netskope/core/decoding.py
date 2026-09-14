"""Shared decoding for operations with an explicitly selected envelope key."""

from __future__ import annotations

from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, TypeAdapter

from netskope.core.pagination import Page, build_page, coerce_total

T = TypeVar("T")
M = TypeVar("M", bound=BaseModel)


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
