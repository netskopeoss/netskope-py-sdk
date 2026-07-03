"""Shared response-envelope extraction and ID-safety helpers for resources.

Netskope REST API v2 responses wrap their payloads in a variety of envelope
shapes (``{"result": [...]}``, ``{"data": [...]}``, ``{"data": {"urllists":
[...]}}``, SCIM's ``{"Resources": [...]}``, or a bare list).  Resource modules
should use :func:`extract_list` / :func:`extract_item` instead of hand-rolling
per-endpoint extractors, and :func:`validate_id` / :func:`quote_id` before
interpolating identifiers into URL paths.

Example::

    from netskope.resources._extract import extract_list, validate_id

    items = extract_list(body, "urllists")
    path = f"/api/v2/policy/urllist/{validate_id(list_id, 'list_id')}"
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

from netskope.exceptions import ValidationError

_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")

# Permissive-but-safe check used by quote_id: non-empty, no control characters,
# no whitespace, and not a dot-only segment (".", "..") that could alter paths.
_QUOTABLE_ID_RE = re.compile(r"^(?!\.+$)[^\s\x00-\x1f\x7f]+$")


def extract_list(body: dict[str, Any] | list[Any], *nested_keys: str) -> list[dict[str, Any]]:
    """Locate the list of items inside a response *body*, whatever the envelope.

    Shapes are tried in order:

    1. a bare list;
    2. ``{"result": [...]}``;
    3. ``{"data": [...]}``;
    4. ``{"data": {nested_key: [...]}}`` for each *nested_keys* entry;
    5. ``{nested_key: [...]}`` at the top level for each *nested_keys* entry;
    6. ``{"Resources": [...]}`` (SCIM);
    7. otherwise ``[]``.

    Non-dict entries are dropped so callers always receive ``list[dict]``.
    """
    if isinstance(body, list):
        return _only_dicts(body)

    result = body.get("result")
    if isinstance(result, list):
        return _only_dicts(result)

    data = body.get("data")
    if isinstance(data, list):
        return _only_dicts(data)
    if isinstance(data, dict):
        for key in nested_keys:
            nested = data.get(key)
            if isinstance(nested, list):
                return _only_dicts(nested)

    for key in nested_keys:
        top = body.get(key)
        if isinstance(top, list):
            return _only_dicts(top)

    resources = body.get("Resources")
    if isinstance(resources, list):
        return _only_dicts(resources)

    return []


def extract_item(body: dict[str, Any], *nested_keys: str) -> dict[str, Any]:
    """Locate a single item inside a response *body*.

    Returns ``body["data"]`` when it is a dict; when ``body["data"]`` is a
    single-item list of dicts, returns that item; otherwise returns *body*
    itself.  *nested_keys* are accepted for signature symmetry with
    :func:`extract_list` and tried inside a ``data`` dict before falling back
    to the ``data`` dict itself.
    """
    data = body.get("data")
    if isinstance(data, dict):
        for key in nested_keys:
            nested = data.get(key)
            if isinstance(nested, dict):
                return nested
        return data
    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
        return data[0]
    return body


def validate_id(value: str | int, name: str = "id") -> str:
    """Validate *value* for safe use in a URL path segment and return it as ``str``.

    Integers pass through unconditionally (stringified).  Strings must match
    ``^[a-zA-Z0-9_\\-]+$``.

    Raises:
        netskope.exceptions.ValidationError: If the value fails validation.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if not isinstance(value, str) or not _SAFE_ID_RE.match(value):
        raise ValidationError(f"Invalid {name} format: {value!r}")
    return value


def quote_id(value: str) -> str:
    """Percent-encode *value* for use as a single URL path segment.

    Applies a permissive-but-safe check (non-empty, no whitespace or control
    characters, not a dot-only segment) and then fully percent-encodes the
    value (``urllib.parse.quote`` with ``safe=""``), so ``/`` and other
    delimiters can never alter the request path.

    Raises:
        netskope.exceptions.ValidationError: If the value fails the check.
    """
    if not isinstance(value, str) or not _QUOTABLE_ID_RE.match(value):
        raise ValidationError(f"Invalid id for URL path: {value!r}")
    return urllib.parse.quote(value, safe="")


def _only_dicts(items: list[Any]) -> list[dict[str, Any]]:
    return [item for item in items if isinstance(item, dict)]
