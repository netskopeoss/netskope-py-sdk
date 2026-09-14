"""Paths and payload builders shared by the private_apps resource and its decoder.

Kept apart from both so the resource can import the decoder for its
``with_response`` accessor without the decoder importing the resource
back. This is the shape ``netskope/resources/shared/datasearch_query.py``
already uses.
"""

from __future__ import annotations

import builtins
import re
from typing import Any

from netskope.core.ids import id_strings, validate_id
from netskope.exceptions import ValidationError

_PATH = "/api/v2/steering/apps/private"


_TAGS_PATH = f"{_PATH}/tags"


_PUBLISHERS_PATH = f"{_PATH}/publishers"


_DISCOVERY_PATH = f"{_PATH}/discoverysettings"


_POLICY_IN_USE_PATH = f"{_PATH}/getpolicyinuse"


_TAGS_POLICY_IN_USE_PATH = f"{_TAGS_PATH}/getpolicyinuse"


# Whitespace ends a term and a quote would open one; `npa_generic.yaml:495-504`
# documents the operators and value spellings but no quoting or escaping.
_UNRENDERABLE = re.compile(r"[\s\"']")


def _query_term(name: str, operator: str, value: Any) -> str:
    """Render one ``<column> <operator> <value>`` term of a query expression.

    A value carrying whitespace or a quote is refused rather than interpolated.
    The expression has no documented quoting, so there is no spelling that
    means "match this literal value": ``name sw My App`` is a different filter
    from the one the caller asked for, and a value containing `` and `` adds a
    term outright.  Callers needing such a value can write the whole expression
    themselves through ``query``.
    """
    if isinstance(value, str) and _UNRENDERABLE.search(value):
        raise ValidationError(
            f"Invalid {name} filter {value!r}: the query expression has no documented "
            "quoting, so a value containing whitespace or quotes cannot be rendered as "
            "a term. Pass the full expression through `query` instead."
        )
    return f"{name} {operator} {value}"


def _filter_terms(
    app_name: str | None,
    publisher_name: str | None,
    reachable: bool | None,
    clientless_access: bool | None,
    host: str | None,
    in_policy: bool | None,
    protocol: str | None,
) -> builtins.list[str]:
    """Translate the convenience filters into the query terms the API names.

    ``listNPAPrivateApps`` declares exactly ``fields``, ``query``, ``offset``
    and ``limit`` (npa_apps_private.yaml:490-524); every attribute below is a
    *term inside* ``query``, with the operators and value spellings documented
    in npa_generic.yaml:495-504 — ``yes``/``no`` for ``reachable`` and
    ``in_policy``, ``true``/``false`` for ``clientless_access``.  Sent as bare
    parameters they were dropped on arrival and the caller silently got an
    unfiltered collection.
    """
    terms: builtins.list[str] = []
    if app_name is not None:
        terms.append(_query_term("name", "sw", app_name))
    if publisher_name is not None:
        terms.append(_query_term("publisher_name", "eq", publisher_name))
    if host is not None:
        terms.append(_query_term("host", "eq", host))
    if protocol is not None:
        terms.append(_query_term("private_app_protocol", "eq", protocol))
    if reachable is not None:
        terms.append(_query_term("reachable", "eq", "yes" if reachable else "no"))
    if in_policy is not None:
        terms.append(_query_term("in_policy", "eq", "yes" if in_policy else "no"))
    if clientless_access is not None:
        terms.append(
            _query_term("clientless_access", "eq", "true" if clientless_access else "false")
        )
    return terms


def _build_list_params(
    query: str | None,
    app_name: str | None,
    publisher_name: str | None,
    reachable: bool | None,
    clientless_access: bool | None,
    host: str | None,
    in_policy: bool | None,
    protocol: str | None,
    filter_expr: str | None,
    fields: builtins.list[str] | None,
) -> dict[str, Any]:
    """Build the four query parameters the private-apps list endpoint declares.

    A caller's own *query* and *filter_expr* expressions lead, in that order,
    and the convenience filters are appended as further ``and`` terms.
    """
    expressions = [expression for expression in (query, filter_expr) if expression] + _filter_terms(
        app_name, publisher_name, reachable, clientless_access, host, in_policy, protocol
    )
    params: dict[str, Any] = {}
    if expressions:
        params["query"] = " and ".join(expressions)
    if fields:
        params["fields"] = ",".join(fields)
    return params


def _publisher_assoc_payload(
    app_ids: builtins.list[int],
    publisher_ids: builtins.list[int],
) -> dict[str, builtins.list[str]]:
    return {
        "private_app_ids": id_strings(app_ids, "app_ids"),
        "publisher_ids": id_strings(publisher_ids, "publisher_ids"),
    }


def _tag_objects(tag_names: builtins.list[str]) -> list[dict[str, str]]:
    """Name at least one tag, so a write cannot ask the API to do nothing."""
    if not tag_names:
        raise ValidationError("tag_names must not be empty.")
    if any(not isinstance(tag, str) or not tag.strip() for tag in tag_names):
        raise ValidationError("Every tag name must be a nonempty string.")
    return [{"tag_name": tag} for tag in tag_names]


def _tag_bulk_payload(
    app_ids: builtins.list[int | str],
    tag_names: builtins.list[str],
) -> dict[str, Any]:
    # The tags bulk endpoints expect app IDs as strings.
    return {"ids": id_strings(app_ids, "app_ids"), "tags": _tag_objects(tag_names)}


def _tag_create_payload(app_id: int | str, tag_names: builtins.list[str]) -> dict[str, Any]:
    # The tag create endpoint expects the app ID as a string.
    return {"id": validate_id(app_id, "app_id"), "tags": _tag_objects(tag_names)}
