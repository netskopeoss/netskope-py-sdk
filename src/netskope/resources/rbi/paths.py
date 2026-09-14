"""Paths and payload builders shared by the rbi resource and its decoder.

Kept apart from both so the resource can import the decoder for its
``with_response`` accessor without the decoder importing the resource
back. This is the shape ``netskope/resources/shared/datasearch_query.py``
already uses.
"""

from __future__ import annotations

from netskope.core.ids import validate_id

_RBI_PATH = "/api/v2/rbi"


_APPLICATIONS_PATH = f"{_RBI_PATH}/applications"


_BROWSERS_PATH = f"{_RBI_PATH}/browsers/supported"


_CATEGORIES_PATH = f"{_RBI_PATH}/categories/default"


_TEMPLATES_PATH = f"{_RBI_PATH}/templates"


def _template_path(template_id: int | str) -> str:
    return f"{_TEMPLATES_PATH}/{validate_id(template_id, 'template_id')}"
