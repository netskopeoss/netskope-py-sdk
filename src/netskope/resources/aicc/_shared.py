"""Helpers shared by the aicc sub-namespaces."""

from __future__ import annotations

from urllib.parse import quote

from netskope.exceptions import ValidationError

_BASE = "/api/v2/aicc"


def _name(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("An AICC entity name cannot be blank.")
    if value in (".", ".."):
        raise ValidationError("An AICC entity name cannot be a relative path segment.")
    return quote(value, safe="")
