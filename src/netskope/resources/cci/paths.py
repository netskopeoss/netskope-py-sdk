"""Paths and payload builders shared by the cci resource and its decoder.

Kept apart from both so the resource can import the decoder for its
``with_response`` accessor without the decoder importing the resource
back. This is the shape ``netskope/resources/shared/datasearch_query.py``
already uses.
"""

from __future__ import annotations

import builtins
import re
import urllib.parse
from typing import Any

from netskope.exceptions import ValidationError
from netskope.models.cci import CciAppQuery

_APP_PATH = "/api/v2/services/cci/app"


_TAGS_PATH = "/api/v2/services/cci/tags"


_TAGS_ALL_PATH = "/api/v2/services/cci/tags/all"


_TAGS_RULES_PATH = "/api/v2/services/cci/tags/rules"


_APPS_SEPARATOR = ";"


def _app_query_params(query: CciAppQuery) -> dict[str, Any]:
    """Render one validated ``GET /cci/app`` query.

    ``apps`` and ``ids`` go on the wire as ``;``-separated lists
    (services/cci.yaml:2891-2958).
    """
    params = query.model_dump(exclude_unset=True)
    for key in ("apps", "ids"):
        if key in params:
            params[key] = _APPS_SEPARATOR.join(str(value) for value in params[key])
    return params


def _build_tag_list_params(
    apps: builtins.list[str] | None,
    ids: builtins.list[int | str] | None,
) -> dict[str, Any] | None:
    """Return query params for ``GET /cci/tags``, or ``None`` for ``/tags/all``."""
    if apps and ids:
        raise ValidationError("apps and ids are mutually exclusive.")
    if apps:
        return {"apps": _APPS_SEPARATOR.join(apps)}
    if ids:
        return {"ids": _APPS_SEPARATOR.join(str(i) for i in ids)}
    return None


_TAG_NAME_RE = re.compile(r"^(?!\.+$)[^\x00-\x1f\x7f]+$")


def _tag_path(tag: str) -> str:
    if not isinstance(tag, str) or not _TAG_NAME_RE.match(tag):
        raise ValidationError(f"Invalid tag name for URL path: {tag!r}")
    return f"{_TAGS_PATH}/{urllib.parse.quote(tag, safe='')}"
