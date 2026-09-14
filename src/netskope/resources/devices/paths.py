"""Paths and payload builders shared by the devices resource and its decoder.

Kept apart from both so the resource can import the decoder for its
``with_response`` accessor without the decoder importing the resource
back. This is the shape ``_alert_query.py`` already uses.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError as PydanticValidationError

from netskope.core.ids import validate_id
from netskope.exceptions import ValidationError
from netskope.models.devices import DeviceTagCreate, DeviceTagPatch

_TAGS_PATH = "/api/v2/devices/device/tags"


_TAGS_QUERY_PATH = f"{_TAGS_PATH}/gettags"


_TAGS_DEFAULT_LIMIT = 20


_TAGS_MAX_LIMIT = 100


def _coerce_tag_id(tag_id: int | str) -> int:
    """Validate *tag_id* and return it as an ``int`` (tag IDs are numeric)."""
    validated = validate_id(tag_id, "tag_id")
    if not validated.isdigit():
        raise ValidationError(f"Invalid tag_id: {tag_id!r} (device tag IDs are numeric)")
    return int(validated)


def _build_tags_query(name: str | None, offset: int, limit: int) -> dict[str, Any]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _TAGS_MAX_LIMIT:
        raise ValidationError(f"Invalid limit {limit!r}. Must be between 1 and {_TAGS_MAX_LIMIT}.")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValidationError(f"Invalid offset {offset!r}. Must be >= 0.")
    payload: dict[str, Any] = {"offset": offset, "limit": limit}
    if name is not None:
        payload["name"] = name
    return payload


def _build_create_payload(name: str, description: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": name}
    if description is not None:
        payload["description"] = description
    return _validate_tag_payload(DeviceTagCreate, payload)


def _build_update_payload(name: str | None, description: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if not payload:
        raise ValidationError("Nothing to update. Provide name and/or description.")
    return _validate_tag_payload(DeviceTagPatch, payload)


def _validate_tag_payload(
    model: type[DeviceTagCreate] | type[DeviceTagPatch], payload: dict[str, Any]
) -> dict[str, Any]:
    try:
        request = model.model_validate(payload)
    except PydanticValidationError as exc:
        fields = ", ".join(".".join(map(str, error["loc"])) for error in exc.errors())
        raise ValidationError(
            f"Invalid device-tag fields: {fields}. "
            "Use nonempty strings containing alphanumeric characters, hyphens, and whitespace."
        ) from None
    return request.model_dump(exclude_unset=True)
