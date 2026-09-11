"""Shared decoding for the explicit NPA response accessors."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from netskope._pagination import _make_page
from netskope.exceptions import ValidationError
from netskope.pagination import Page
from netskope.resources._response_list import parse_response_list

T = TypeVar("T", bound=BaseModel)


def page_params(limit: int | None, offset: int | None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for name, value, minimum in (("limit", limit, 1), ("offset", offset, 0)):
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise ValidationError(
                    f"{name} must be an integer greater than or equal to {minimum}."
                )
            params[name] = value
    return params


def parse_page(
    body: Any, model: type[T], limit: int | None, offset: int | None, *keys: str
) -> Page[T]:
    items = parse_response_list(body, model, *keys)
    metadata = (
        {key: value for key, value in body.items() if key not in ("data", "result", *keys)}
        if isinstance(body, dict)
        else {}
    )
    if isinstance(body, dict) and isinstance(body.get("data"), dict):
        nested = body["data"]
        for name in ("total", "totalResults"):
            if name not in metadata and name in nested:
                metadata[name] = nested[name]
    return _make_page(items, metadata, offset or 0, limit)


def parse_item(body: Any, model: type[T]) -> T:
    if isinstance(body, dict):
        for key in ("data", "result"):
            if key in body:
                body = body[key]
                break
    if isinstance(body, list):
        if len(body) != 1:
            raise ValueError("Expected exactly one resource in the response.")
        body = body[0]
    if not isinstance(body, dict):
        raise ValueError("Expected a resource object in the response.")
    return model.model_validate(body)
