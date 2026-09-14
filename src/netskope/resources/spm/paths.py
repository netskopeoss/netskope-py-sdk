"""Paths and payload builders shared by the spm resource and its decoder.

Kept apart from both so the resource can import the decoder for its
``with_response`` accessor without the decoder importing the resource
back. This is the shape ``_alert_query.py`` already uses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from netskope.exceptions import ValidationError

_INVENTORY_PATH = "/api/v2/spm/inventory/getresources"


_POSTURE_SCORE_PATH = "/api/v2/spm/results/getposturescores"


_POLICY_RULES_PATH = "/api/v2/spm/rules/list"


_RECENT_CHANGES_PATH = "/api/v2/spm/apps/recentchanges/getstats"


_GROUP_BY_FIELDS: dict[str, tuple[str, ...]] = {
    "instance_name": (
        "instance_name",
        "app_suite",
        "total_checked_rules",
        "passed_rules",
        "failed_rules",
        "failed_muted_rules",
        "failed_critical_rules",
        "failed_high_rules",
        "failed_medium_rules",
        "failed_low_rules",
        "unknown_rules",
    ),
    "resource_type": (
        "resource_type",
        "app_suite",
        "app_name",
        "total_resources",
        "total_checked_rules",
        "passed_rules",
        "failed_rules",
        "failed_muted_rules",
        "failed_critical_rules",
        "failed_high_rules",
        "failed_medium_rules",
        "failed_low_rules",
        "unknown_rules",
    ),
    "resource_name": (
        "resource_name",
        "resource_id",
        "app_suite",
        "app_name",
        "region_id",
        "region_name",
        "netskope_instance_name",
        "instance_name",
        "instance_id",
        "resource_type",
        "parent_res_type",
    ),
}


_POLICY_RULE_VIEWS = ("latest", "applied")


_SORT_ORDERS = ("asc", "desc")


def _epoch_seconds(value: datetime | int, name: str) -> int:
    """Return *value* as epoch **seconds**, converting an aware ``datetime``."""
    if isinstance(value, bool) or not isinstance(value, (datetime, int)):
        raise ValidationError(f"{name} must be epoch seconds or a datetime.")
    if isinstance(value, datetime):
        return int(value.timestamp())
    return value


def _positive_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{name} must be a nonnegative integer.")
    return value


def _inventory_body(
    *,
    fields: list[str] | None,
    group_by: str,
    limit: int,
    offset: int,
    filters: dict[str, Any] | None,
    ngl_query: str | None,
    sort: list[dict[str, Any]] | None,
    timestamp: int | None,
    past_view: bool | None,
) -> dict[str, Any]:
    """Build the ``ResourceAggregationRequest`` body (spm/inventory.yaml:284-386).

    ``offset``, ``fields``, ``limit`` and ``group_by`` are required by the
    schema, so they are always sent.  ``filters`` and ``ngl_query`` are
    mutually exclusive, and ``ngl_query`` works only with
    ``group_by="resource_name"``.
    """
    if group_by not in _GROUP_BY_FIELDS:
        valid = ", ".join(_GROUP_BY_FIELDS)
        raise ValidationError(f"Invalid group_by {group_by!r}. Must be one of: {valid}")
    if filters is not None and ngl_query is not None:
        raise ValidationError("filters and ngl_query are mutually exclusive.")
    if ngl_query is not None and group_by != "resource_name":
        raise ValidationError('ngl_query is supported only with group_by="resource_name".')
    if past_view and timestamp is None:
        # "If past_view is set to true, timestamp is required."
        # (spm/inventory.yaml:343-352 and :371-379)
        raise ValidationError("past_view=True requires timestamp (epoch seconds).")
    selected = list(fields) if fields else list(_GROUP_BY_FIELDS[group_by])
    if not selected:
        raise ValidationError("fields must name at least one inventory column.")
    body: dict[str, Any] = {
        "fields": selected,
        "group_by": group_by,
        "limit": _positive_int(limit, "limit"),
        "offset": _positive_int(offset, "offset"),
    }
    if filters is not None:
        body["filters"] = filters
    if ngl_query is not None:
        body["ngl_query"] = ngl_query
    if sort is not None:
        body["sort"] = list(sort)
    if timestamp is not None:
        body["timestamp"] = timestamp
    if past_view is not None:
        body["past_view"] = past_view
    return body


def _apps_body(limit: int, offset: int) -> dict[str, Any]:
    """Aggregate the inventory by SaaS instance — one row per connected app."""
    return _inventory_body(
        fields=None,
        group_by="instance_name",
        limit=limit,
        offset=offset,
        filters=None,
        ngl_query=None,
        sort=None,
        timestamp=None,
        past_view=None,
    )


def _app_body(app_name: str, limit: int, offset: int) -> dict[str, Any]:
    """Aggregate one application's resources by type.

    ``app_name`` is a ``{operator, values}`` filter — the only form
    ``ResourceAggregationRequest.filters`` accepts (spm/inventory.yaml:300-321).
    """
    if not isinstance(app_name, str) or not app_name.strip():
        raise ValidationError("app_name must be a nonempty application name.")
    return _inventory_body(
        fields=None,
        group_by="resource_type",
        limit=limit,
        offset=offset,
        filters={"app_name": {"operator": "equal", "values": [app_name]}},
        ngl_query=None,
        sort=None,
        timestamp=None,
        past_view=None,
    )


def _posture_score_body(
    app_names: list[str] | None,
    appsuite_names: list[str] | None,
    instance_names: list[str] | None,
    posture_confidence_level: list[str] | None,
    timestamp: int | None,
) -> dict[str, Any]:
    """Build ``GetPostureScoresRequestBody`` (spm/saas_posture_score.yaml:26-46).

    Every field is optional; an empty object asks for the whole tenant.
    """
    filters: dict[str, Any] = {}
    for key, values in (
        ("app_names", app_names),
        ("appsuite_names", appsuite_names),
        ("instance_names", instance_names),
        ("posture_confidence_level", posture_confidence_level),
    ):
        if values is not None:
            filters[key] = list(values)
    body: dict[str, Any] = {}
    if filters:
        body["filters"] = filters
    if timestamp is not None:
        body["timestamp"] = timestamp
    return body


def _policy_rule_params(
    appsuite: str | None,
    filter: str | None,
    limit: int | None,
    view: str | None,
    sort_order: str | None,
    include_templates: bool | None,
    offset: int | None,
) -> dict[str, Any]:
    """Build the ``GET /rules/list`` query (spm/policy.yaml:2833-2905)."""
    if view is not None and view not in _POLICY_RULE_VIEWS:
        raise ValidationError(f"view must be one of: {', '.join(_POLICY_RULE_VIEWS)}")
    if sort_order is not None and sort_order not in _SORT_ORDERS:
        raise ValidationError(f"sort_order must be one of: {', '.join(_SORT_ORDERS)}")
    params: dict[str, Any] = {}
    if appsuite is not None:
        params["appsuite"] = appsuite
    if filter is not None:
        params["filter"] = filter
    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int) or not (limit == -1 or limit >= 0):
            raise ValidationError("limit must be a nonnegative integer, or -1 for every rule.")
        if limit > 1000:
            raise ValidationError("limit must not exceed 1000.")
        params["limit"] = limit
    if view is not None:
        params["view"] = view
    if sort_order is not None:
        params["sortorder"] = sort_order
    if include_templates is not None:
        params["include_templates"] = include_templates
    if offset is not None:
        params["offset"] = _positive_int(offset, "offset")
    return params


def _recent_changes_body(
    start: datetime | int | None,
    end: datetime | int | None,
    app_name: str | None,
    instance_name: str | None,
) -> dict[str, Any]:
    """Build ``RecentChangesRequest`` (spm/apps.yaml:616-649).

    ``time_range`` is required and both of its bounds are required, so a
    window must be supplied.
    """
    if start is None or end is None:
        raise ValidationError(
            "SPM recent changes requires a time range: pass start= and end= "
            "as epoch seconds or datetimes."
        )
    window = {"start": _epoch_seconds(start, "start"), "end": _epoch_seconds(end, "end")}
    if window["end"] < window["start"]:
        raise ValidationError("end must not precede start.")
    body: dict[str, Any] = {"time_range": window}
    filters: dict[str, Any] = {}
    if app_name is not None:
        filters["app_name"] = app_name
    if instance_name is not None:
        filters["instance_name"] = instance_name
    if filters:
        body["filters"] = filters
    return body
