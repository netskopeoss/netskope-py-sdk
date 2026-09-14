"""Shared decoding for the explicit NPA response accessors."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from netskope.core.pagination import Page, _make_page
from netskope.core.response_list import parse_response_list
from netskope.exceptions import ValidationError

T = TypeVar("T", bound=BaseModel)


def page_params(
    limit: int | None,
    offset: int | None,
    *,
    limit_minimum: int = 1,
    limit_maximum: int | None = None,
) -> dict[str, Any]:
    """Build the ``limit``/``offset`` query, refusing values the operation rejects.

    The defaults suit the NPA operations that put no formal bound on ``limit``.
    Pass *limit_minimum* / *limit_maximum* where the contract declares them :
    the two IPsec list operations declare ``minimum: 0, maximum: 100``
    (``steering/ipsec.yaml:478-486`` for pops, ``:672-680`` for tunnels); so an
    out-of-range value is refused here instead of being spent on a round trip
    the gateway can only reject or silently clamp.
    """
    params: dict[str, Any] = {}
    for name, value, minimum in (("limit", limit, limit_minimum), ("offset", offset, 0)):
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise ValidationError(
                    f"{name} must be an integer greater than or equal to {minimum}."
                )
            if name == "limit" and limit_maximum is not None and value > limit_maximum:
                raise ValidationError(
                    f"limit must be an integer between {minimum} and {limit_maximum}."
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
