"""Paths and payload builders shared by the url_lists resource and its decoder.

Kept apart from both so the resource can import the decoder for its
``with_response`` accessor without the decoder importing the resource
back. This is the shape ``_alert_query.py`` already uses.
"""

from __future__ import annotations

import builtins
from typing import Any

from netskope.core.ids import validate_id
from netskope.exceptions import ResponseValidationError, ValidationError
from netskope.models.url_lists import UrlList

_PATH = "/api/v2/policy/urllist"


_DEPLOY_PATH = f"{_PATH}/deploy"


_LIST_FIELDS = ("id", "name", "data", "modify_type", "modify_time", "modify_by", "pending")


_RECORD_KEYS = frozenset({"id", "name", "urls", "type"})


_LIST_TYPES = ("exact", "regex")


_REQUIRED_ON_UPDATE = frozenset({"name", "urls", "type"})


def _flatten_url_list(item: dict[str, Any]) -> dict[str, Any]:
    """Flatten nested 'data' key into the top-level item dict."""
    if "data" in item and isinstance(item["data"], dict):
        flat = {**item}
        inner = flat.pop("data")
        flat.update(inner)
        return flat
    return item


def _single(items: builtins.list[Any]) -> dict[str, Any]:
    return items[0] if len(items) == 1 and isinstance(items[0], dict) else {}


def _is_record(candidate: dict[str, Any]) -> bool:
    """Whether a dict is a URL list itself rather than an envelope around one."""
    return bool(_RECORD_KEYS & candidate.keys())


def _as_record(candidate: dict[str, Any]) -> dict[str, Any]:
    """Flatten one candidate into a record, or state that it is not one."""
    flat = _flatten_url_list(candidate)
    return flat if _is_record(flat) else {}


def _extract_one(body: Any) -> dict[str, Any]:
    """Extract a single URL list item from any of the response shapes the API returns.

    POST returns ``[{...}]`` while GET/PUT return the bare record, ``{"data":
    {...}}``, ``{"data": [{...}]}``, or a ``urllists`` collection nested under
    ``data`` or at the top level.  :func:`_flatten_url_list` merges a record's
    nested payload up.  An empty dict means no single record was found;
    :func:`_require_record` turns that into an error.
    """
    if isinstance(body, list):
        return _as_record(_single(body))
    if not isinstance(body, dict):
        return {}
    if _is_record(body):
        return _as_record(body)
    data = body.get("data")
    if isinstance(data, list):
        return _as_record(_single(data))
    nested = data.get("urllists") if isinstance(data, dict) else None
    for collection in (nested, body.get("urllists")):
        if isinstance(collection, list):
            return _as_record(_single(collection))
    return _as_record(data) if isinstance(data, dict) else {}


def _require_record(
    body: Any,
    *,
    request_method: str | None = None,
    request_path: str | None = None,
) -> dict[str, Any]:
    """Return the single URL list in *body*, refusing an absent or ambiguous record."""
    record = _extract_one(body)
    if not record:
        raise ResponseValidationError(
            "The response did not contain exactly one URL list.",
            request_method=request_method,
            request_path=request_path,
        )
    return record


def _list_path(list_id: int) -> str:
    """Build the single-list path, rejecting an identifier that could alter it."""
    return f"{_PATH}/{validate_id(list_id, 'list_id')}"


def _merge_source(current: UrlList, list_id: int) -> UrlList:
    """Reject a read that cannot safely seed the full-body PUT ``update`` sends.

    ``UrlList.urls`` defaults to an empty list, so an unrecognized envelope would
    otherwise merge into a PUT that erases every URL in the list.
    """
    missing = _REQUIRED_ON_UPDATE - current.model_fields_set
    if missing:
        raise ResponseValidationError(
            f"The URL list read did not return {', '.join(sorted(missing))}; "
            "refusing to build an update from it.",
            request_method="GET",
            request_path=_list_path(list_id),
        )
    if str(current.id) != str(list_id):
        raise ResponseValidationError(
            "The URL list read identifies a different list.",
            request_method="GET",
            request_path=_list_path(list_id),
        )
    return current


def _payload(name: str, urls: builtins.list[str], list_type: str) -> dict[str, Any]:
    """Validate the caller's fields and build the body the API requires.

    ``name`` sits at the top level; ``urls`` and ``type`` are wrapped in ``data``.
    """
    if list_type not in _LIST_TYPES:
        raise ValidationError(f"list_type must be one of: {', '.join(_LIST_TYPES)}.")
    if (
        not isinstance(name, str)
        or not isinstance(urls, list)
        or any(not isinstance(url, str) for url in urls)
    ):
        raise ValidationError("URL lists require a name and a list of URL strings.")
    return {"name": name, "data": {"urls": list(urls), "type": list_type}}


def _build_list_params(pending: int | bool | None, field: str | None) -> dict[str, Any]:
    """Validate and build the two query parameters ``GET /urllist`` declares."""
    params: dict[str, Any] = {}
    if pending is not None:
        if isinstance(pending, bool):
            pending = int(pending)
        if pending not in (0, 1):
            raise ValidationError("pending must be 0 (applied) or 1 (pending).")
        params["pending"] = pending
    if field is not None:
        if field not in _LIST_FIELDS:
            raise ValidationError(f"field must be one of: {', '.join(_LIST_FIELDS)}.")
        params["field"] = field
    return params


def _update_fields(
    name: str | None,
    urls: builtins.list[str] | None,
    list_type: str | None,
) -> None:
    """Reject an update with nothing to change or with values the API refuses."""
    if name is None and urls is None and list_type is None:
        raise ValidationError("Provide name, urls, or list_type to update a URL list.")
    _payload(
        name if name is not None else "",
        urls if urls is not None else [],
        list_type if list_type is not None else "exact",
    )
