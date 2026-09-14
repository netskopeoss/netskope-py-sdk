"""Internal validation for bounded administrative response contracts."""

from __future__ import annotations

from typing import Any, TypeVar

import httpx
from pydantic import BaseModel
from pydantic import ValidationError as ModelValidationError

from netskope.core.pagination import Page, build_page, coerce_total
from netskope.core.response_list import extract_response_list
from netskope.exceptions import ValidationError
from netskope.models.administration import OperationStatus

T = TypeVar("T", bound=BaseModel)


def request_payload(request: T, model: type[T]) -> dict[str, Any]:
    try:
        validated = model.model_validate(request)
    except ModelValidationError as exc:
        locations = ", ".join(
            ".".join(map(str, error["loc"])) or "request" for error in exc.errors()
        )
        raise ValidationError(f"Invalid administrative request fields: {locations}.") from None
    return validated.model_dump(mode="json", by_alias=True, exclude_unset=True)


def page_params(
    limit: int | None, offset: int | None, *, maximum: int | None = None
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if limit is not None:
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit < 0
            or (maximum is not None and limit > maximum)
        ):
            raise ValidationError(
                "limit must be a nonnegative integer"
                + (f" no greater than {maximum}." if maximum else ".")
            )
        params["limit"] = limit
    if offset is not None:
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValidationError("offset must be a nonnegative integer.")
        params["offset"] = offset
    return params


def item(response: httpx.Response, model: type[T]) -> T:
    body = response.json()
    if isinstance(body, dict):
        for key in ("data", "result"):
            if key in body:
                body = body[key]
                break
    if not isinstance(body, dict):
        raise ValueError("Expected an administrative resource object.")
    return model.model_validate(body)


def receipt(response: httpx.Response) -> OperationStatus | None:
    if not response.content and response.status_code == 204:
        return None
    return item(response, OperationStatus)


def _carries_records(body: dict[str, Any], key: str) -> bool:
    """Whether the envelope holds a record array at either level it may use."""
    for name in (key, "data", "result"):
        value = body.get(name)
        if isinstance(value, list):
            return True
        if isinstance(value, dict) and isinstance(value.get(key), list):
            return True
    return False


def page(
    response: httpx.Response,
    model: type[T],
    key: str,
    *,
    offset: int = 0,
    limit: int | None = None,
    total_key: str = "total",
    allow_missing: bool = False,
) -> Page[T]:
    """Decode a paged collection.

    ``allow_missing`` is for operations whose schema marks the record array
    optional, where an acknowledgement carrying no collection is legal and must
    not be refused.
    """
    body = response.json()
    if allow_missing and isinstance(body, dict) and not _carries_records(body, key):
        rows: list[dict[str, Any]] = []
    else:
        rows = extract_response_list(body, key)
    metadata = dict(body) if isinstance(body, dict) else {}
    nested = metadata.get("data")
    for records_key in ("data", "result", key):
        metadata.pop(records_key, None)
    if isinstance(nested, dict):
        # A nested ``data`` envelope carries the paging fields for its own records.
        for name in (total_key, "offset"):
            if name not in metadata and name in nested:
                metadata[name] = nested[name]
    return build_page(
        [model.model_validate(row) for row in rows],
        offset=offset,
        limit=limit,
        total=coerce_total(metadata.get(total_key)),
        metadata=metadata,
        # The echo is passed as received: an unusable one cannot identify the
        # page, where an unusable total merely states nothing.
        echoed_offset=metadata.get("offset"),
    )
