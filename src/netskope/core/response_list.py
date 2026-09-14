"""Validated collection extraction for typed response accessors."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_ENVELOPE_KEYS = ("result", "data", "Resources")


def _declared_lists(body: dict[str, Any], nested_keys: tuple[str, ...]) -> dict[str, list[Any]]:
    """Locate each declared record key, preferring one nested inside ``data``."""
    nested = body.get("data")
    found: dict[str, list[Any]] = {}
    for key in nested_keys:
        if isinstance(nested, dict) and isinstance(nested.get(key), list):
            found[f"data.{key}"] = nested[key]
        elif isinstance(body.get(key), list):
            found[key] = body[key]
    return found


def _envelope_lists(body: dict[str, Any]) -> dict[str, list[Any]]:
    return {key: body[key] for key in _ENVELOPE_KEYS if isinstance(body.get(key), list)}


def _select(body: dict[str, Any], nested_keys: tuple[str, ...]) -> Any:
    """Return the single collection this envelope offers, or ``None``.

    A declared record key wins over the generic ``result``/``data`` envelope, so
    an unrelated empty collection cannot shadow the operation's own records.
    Two collections the operation cannot choose between are rejected instead.
    """
    candidates = _declared_lists(body, nested_keys) if nested_keys else {}
    if not candidates:
        candidates = _envelope_lists(body)
    if len(candidates) > 1:
        names = ", ".join(sorted(candidates))
        raise ValueError(
            f"Ambiguous API response: competing collections ({names}). "
            "The operation cannot establish which records were returned."
        )
    return next(iter(candidates.values()), None)


def extract_response_list(body: Any, *nested_keys: str) -> list[dict[str, Any]]:
    """Extract a supported list envelope without dropping malformed records."""
    records: Any = None
    if isinstance(body, list):
        records = body
    elif isinstance(body, dict):
        records = _select(body, nested_keys)
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise ValueError("Invalid API response: expected a collection of objects.")
    return records


def parse_response_list(body: Any, model: type[T], *nested_keys: str) -> list[T]:
    """Validate every record in a collection using its resource model."""
    return [model.model_validate(item) for item in extract_response_list(body, *nested_keys)]
