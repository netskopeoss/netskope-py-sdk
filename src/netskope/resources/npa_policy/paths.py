"""Paths and payload builders shared by the npa_policy resource and its decoder.

Kept apart from both so the resource can import the decoder for its
``with_response`` accessor without the decoder importing the resource
back. This is the shape ``netskope/resources/shared/datasearch_query.py``
already uses.
"""

from __future__ import annotations

import builtins
from typing import Any

from netskope.core.ids import validate_id

_RULES_PATH = "/api/v2/policy/npa/rules"


_GROUPS_PATH = "/api/v2/policy/npa/policygroups"


def _rule_path(rule_id: int) -> str:
    return f"{_RULES_PATH}/{validate_id(rule_id, 'rule_id')}"


def _group_path(group_id: int) -> str:
    return f"{_GROUPS_PATH}/{validate_id(group_id, 'group_id')}"


def _build_rules_list_params(
    filter_expr: str | None,
    fields: builtins.list[str] | None,
    sort_by: str | None,
    sort_order: str | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if filter_expr:
        params["filter"] = filter_expr
    if fields:
        params["fields"] = ",".join(fields)
    if sort_by:
        params["sortby"] = sort_by
    if sort_order:
        params["sortorder"] = sort_order
    return params
