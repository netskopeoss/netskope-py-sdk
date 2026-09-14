"""Paths and payload builders shared by the dspm resource and its decoder.

Kept apart from both so the resource can import the decoder for its
``with_response`` accessor without the decoder importing the resource
back. This is the shape ``netskope/resources/shared/datasearch_query.py``
already uses.
"""

from __future__ import annotations

from typing import Any

from netskope.exceptions import ValidationError
from netskope.models.dspm import DspmResourceType, SortOrder


def _validate_resource_type(resource_type: DspmResourceType | str) -> str:
    """Coerce *resource_type* to a known DSPM resource-type path segment.

    Raises:
        netskope.exceptions.ValidationError: If *resource_type* is not a
            member of :class:`~netskope.models.dspm.DspmResourceType`.
    """
    try:
        return DspmResourceType(resource_type).value
    except ValueError as exc:
        valid = ", ".join(rt.value for rt in DspmResourceType)
        raise ValidationError(
            f"Invalid DSPM resource_type {resource_type!r}. Must be one of: {valid}"
        ) from exc


def _build_list_params(
    filter_expr: str | None,
    sort_by: str | None,
    sort_order: SortOrder | str | None,
    limit: int | None,
    offset: int | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if filter_expr is not None:
        params["filter"] = filter_expr
    if sort_by is not None:
        params["sortby"] = sort_by
    if sort_order is not None:
        try:
            params["sortorder"] = SortOrder(sort_order).value
        except ValueError as exc:
            valid = ", ".join(order.value for order in SortOrder)
            raise ValidationError(
                f"Invalid DSPM sort_order {sort_order!r}. Must be one of: {valid}"
            ) from exc
    if offset is not None:
        params["offset"] = offset
    if limit is not None:
        params["limit"] = limit
    return params
