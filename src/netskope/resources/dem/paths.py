"""Paths and payload builders shared by the dem resource and its decoder.

Kept apart from both so the resource can import the decoder for its
``with_response`` accessor without the decoder importing the resource
back. This is the shape ``_alert_query.py`` already uses.
"""

from __future__ import annotations

import builtins
from datetime import UTC, datetime
from typing import Any

from netskope.exceptions import ValidationError
from netskope.models.dem import (
    ALERT_CATEGORIES,
    ALERT_SEVERITIES,
    ALERT_TYPES,
    DATA_QUERY_SOURCES,
    ENTITY_DEVICE_OS,
    ENTITY_MONITORING,
    PROBE_DEVICE_CLASSIFICATIONS,
    PROBE_OPERATING_SYSTEMS,
    SORT_ORDERS,
    STATE_DATA_SOURCES,
    TRACEROUTE_DATA_SOURCES,
)

_APPPROBES_PATH = "/api/v2/dem/appprobes"


_NETWORKPROBES_PATH = "/api/v2/dem/networkprobes"


_ALERT_RULES_PATH = "/api/v2/dem/alert/rules"


_ALERTS_PATH = "/api/v2/dem/alerts"


_GETALERTS_PATH = "/api/v2/dem/alerts/getalerts"


_APPS_PATH = "/api/v2/dem/apps"


_QUERY_GETDATA_PATH = "/api/v2/dem/query/getdata"


_QUERY_GETDATASET_PATH = "/api/v2/dem/query/getdataset"


_QUERY_GETENTITIES_PATH = "/api/v2/dem/query/getentities"


_QUERY_GETSTATES_PATH = "/api/v2/dem/query/getstates"


_QUERY_GETTRACEROUTE_PATH = "/api/v2/dem/query/gettraceroute"


_QUERY_DEFINITIONS_PATH = "/api/v2/dem/query/definitions"


_ADEM_USERS_PATH = "/api/v2/adem/users"


_QUERY_LIMIT_EXCLUSIVE_MAX = 10000


_QUERY_OFFSET_EXCLUSIVE_MAX = 100000


_MAX_ENTITIES_LIMIT = 100


_ENTITIES_OFFSET_EXCLUSIVE_MAX = 100000


_PROBE_LIMIT_RANGE: tuple[int, int | None] = (1, 1000)


_APP_LIMIT_RANGE: tuple[int, int | None] = (1, None)


def _bounded(name: str, value: int, minimum: int, maximum: int | None) -> int:
    """Return *value* when the declared bound allows it, else raise.

    The gateway rejects an out-of-range paging value, so the SDK reports it
    here instead of clamping silently or forwarding it.
    """
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
        or (maximum is not None and value > maximum)
    ):
        allowed = (
            f"between {minimum} and {maximum}" if maximum is not None else f"{minimum} or more"
        )
        raise ValidationError(f"{name} must be an integer {allowed}.")
    return value


def _enum_value(name: str, value: str, allowed: tuple[str, ...]) -> str:
    """Return *value* when the operation enumerates it, else raise."""
    if value not in allowed:
        raise ValidationError(f"{name} must be one of: {', '.join(allowed)}")
    return value


def _enum_values(
    name: str, values: builtins.list[str], allowed: tuple[str, ...]
) -> builtins.list[str]:
    """Return *values* when every entry is enumerated, else raise."""
    invalid = [value for value in values if value not in allowed]
    if invalid:
        raise ValidationError(
            f"Invalid {name} value(s): {', '.join(map(str, invalid))}. "
            f"Must be one of: {', '.join(allowed)}"
        )
    return builtins.list(values)


def _epoch_seconds(value: datetime | int) -> int:
    """Return *value* as epoch **seconds**.

    A :class:`~datetime.datetime` is converted; a bare ``int`` is passed
    through unchanged and is assumed to already be in epoch seconds.
    """
    if isinstance(value, datetime):
        return int(value.timestamp())
    return value


def _epoch_millis(value: datetime | int) -> int:
    """Return *value* as epoch **milliseconds**.

    A :class:`~datetime.datetime` is converted; a bare ``int`` is passed
    through unchanged and is assumed to already be in epoch milliseconds.
    """
    if isinstance(value, datetime):
        return int(value.timestamp() * 1000)
    return value


def _absolute_bound(value: datetime | int) -> dict[str, str]:
    """Return *value* as an ``AbsoluteDate`` (dem-workbench-query.yaml:5-14).

    ``QueryInput`` sets ``additionalProperties: false`` and types ``begin`` and
    ``end`` as ``{"absolute": <RFC 3339>}`` or ``{"relative": <RFC 3339>}``, so
    an epoch integer is never accepted on the wire.  Bare ``int`` arguments
    stay in this surface's historical unit — epoch milliseconds — and are
    converted here.
    """
    moment = datetime.fromtimestamp(_epoch_millis(value) / 1000, tz=UTC)
    return {"absolute": moment.isoformat().replace("+00:00", "Z")}


_RETIRED_PROBE_FIELDS = {
    "target": "the probe follows an app, named by appName (predefined) or appID (custom)",
    "protocol": "the app probe schema has no protocol",
    "interval": "use frequency (minutes)",
}


def _probe_create_body(
    name: str,
    *,
    frequency: int | None,
    entity: dict[str, builtins.list[str]] | None,
    os: builtins.list[str] | None,
    device_classification: builtins.list[str] | None,
    status: int,
    app_name: str | None,
    app_id: int | None,
    move: dict[str, Any] | None,
    retired: dict[str, Any],
    additional_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the bare ``AppProbeCreateRequest`` body (demconfig.yaml:2744-2752).

    ``POST /appprobes`` takes the object itself, never a ``data`` wrapper.
    """
    supplied = [key for key, value in retired.items() if value is not None]
    if supplied:
        detail = "; ".join(f"{key} — {_RETIRED_PROBE_FIELDS[key]}" for key in supplied)
        raise ValidationError(
            f"POST /dem/appprobes does not define {', '.join(supplied)}: {detail}. "
            "Required fields are name, frequency, entity, os, deviceClassification, "
            "status, appType with appName or appID, and move."
        )
    missing = [
        label
        for label, value in (
            ("frequency", frequency),
            ("entity", entity),
            ("os", os),
            ("device_classification", device_classification),
        )
        if value is None
    ]
    if missing:
        raise ValidationError(
            f"An application probe requires {', '.join(missing)}. See "
            "AppProbeUpdateCreateCommon: name, frequency, entity, os, "
            "deviceClassification and status are all required."
        )
    if (app_name is None) == (app_id is None):
        raise ValidationError(
            "Name exactly one app: app_name for a predefined app, or app_id for a custom one."
        )
    body: dict[str, Any] = {
        "name": name,
        "frequency": frequency,
        "entity": entity,
        "os": _enum_values("os", list(os or ()), PROBE_OPERATING_SYSTEMS),
        "deviceClassification": _enum_values(
            "device_classification",
            list(device_classification or ()),
            PROBE_DEVICE_CLASSIFICATIONS,
        ),
        "status": status,
        "appType": "predefined" if app_name is not None else "custom",
        "move": dict(move) if move else {"operation": "bottom"},
    }
    if app_name is not None:
        body["appName"] = app_name
    else:
        body["appID"] = app_id
    if additional_fields:
        body.update(additional_fields)
    return body


def _alert_rule_create_body(
    name: str,
    metric: str,
    threshold: float,
    severity: str,
    probe_id: str | None,
    *,
    category: str | None = None,
    alert_type: str | None = None,
    enabled: bool = True,
    email_receiver: str | None = None,
    criteria_type: str | None = None,
    window: int | None = None,
    filter: dict[str, Any] | None = None,
    duration: int | None = None,
    criteria: dict[str, Any] | None = None,
    additional_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the bare ``PostAlertRuleRequest`` body (dem_alert.yaml:441-467).

    The measurement is ``criteria.condition.measure`` and its threshold is
    ``criteria.condition.thresholds``; there is no flat ``metric``/``threshold``
    pair, no ``probe_id``, and no ``data`` wrapper.
    """
    if probe_id is not None:
        raise ValidationError(
            "POST /dem/alert/rules has no probe_id. Scope a rule with "
            "criteria.condition.filter.scopeEntity instead."
        )
    if criteria is None:
        condition: dict[str, Any] = {"measure": metric, "thresholds": {"threshold": threshold}}
        if window is not None:
            condition["window"] = window
        if filter is not None:
            condition["filter"] = filter
        criteria = {"condition": condition}
        if duration is not None:
            criteria["duration"] = duration
    body: dict[str, Any] = {
        "name": name,
        "severity": _enum_value("severity", severity, ALERT_SEVERITIES),
        "enabled": enabled,
        "criteria": criteria,
    }
    if category is not None:
        body["category"] = _enum_value("category", category, ALERT_CATEGORIES)
    if alert_type is not None:
        body["type"] = _enum_value("type", alert_type, ALERT_TYPES)
    for key, value in (
        ("criteriaType", criteria_type),
        ("emailReceiver", email_receiver),
    ):
        if value is not None:
            body[key] = value
    if additional_fields:
        body.update(additional_fields)
    return body


def _getdata_body(
    data_source: str,
    select: builtins.list[Any],
    begin: datetime | int,
    end: datetime | int,
    where: Any | None,
    group_by: builtins.list[str] | None,
    order_by: Any | None,
    limit: int | None,
    offset: int | None,
) -> dict[str, Any]:
    if data_source in STATE_DATA_SOURCES:
        raise ValidationError(
            f"{data_source!r} is a state source, not a data source. "
            "Read current agent and client state with get_states."
        )
    if data_source not in DATA_QUERY_SOURCES:
        valid = ", ".join(sorted(DATA_QUERY_SOURCES))
        raise ValidationError(f"Invalid data_source {data_source!r}. Must be one of: {valid}")
    body: dict[str, Any] = {"from": data_source, "select": select}
    if group_by:
        body["groupby"] = group_by
    if where is not None:
        body["where"] = where
    if order_by is not None:
        body["orderby"] = order_by
    body["begin"] = _absolute_bound(begin)
    body["end"] = _absolute_bound(end)
    if limit is not None:
        body["limit"] = _bounded("limit", limit, 0, _QUERY_LIMIT_EXCLUSIVE_MAX - 1)
    if offset is not None:
        body["offset"] = _bounded("offset", offset, 0, _QUERY_OFFSET_EXCLUSIVE_MAX - 1)
    return body


def _getentities_body(
    start_time: datetime | int,
    end_time: datetime | int,
    user: str | None,
    application: str | None,
    applications: builtins.list[str] | None,
    device_os: builtins.list[str] | None,
    monitoring: str | None,
    exp_score: builtins.list[str] | None,
    pop: builtins.list[str] | None,
    source_ip: str | None,
    user_location: builtins.list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    # ``GetEntitiesQueryInput`` (dem-workbench-query.yaml:296-366) types
    # ``starttime``/``endtime`` as plain integers with no range cap, and the
    # operation (:1208) documents none, so the window is the gateway's call.
    # The documented two-day cap belongs to ``/query/getdataset`` alone.
    body: dict[str, Any] = {
        "starttime": _bounded("start_time", _epoch_seconds(start_time), 1, None),
        "endtime": _bounded("end_time", _epoch_seconds(end_time), 1, None),
    }
    if user is not None:
        body["user"] = user
    if application is not None:
        body["application"] = application
    if applications is not None:
        body["applications"] = applications
    if device_os is not None:
        body["deviceOs"] = _enum_values("device_os", device_os, ENTITY_DEVICE_OS)
    if monitoring is not None:
        body["monitoring"] = _enum_value("monitoring", monitoring, ENTITY_MONITORING)
    if exp_score is not None:
        body["expScore"] = exp_score
    if pop is not None:
        body["pop"] = pop
    if source_ip is not None:
        body["sourceIp"] = source_ip
    if user_location is not None:
        body["userLocation"] = [dict(entry) for entry in user_location]
    return body


def _getentities_params(
    limit: int | None,
    offset: int | None,
    sort_order: str | None,
    sort_by: str | None = None,
) -> dict[str, Any]:
    """Build the ``/query/getentities`` query (dem-workbench-query.yaml:1211-1246).

    ``limit`` is bounded to ``[0, 100]`` and ``offset`` to ``[0, 100000)``;
    ``sortby`` is a free string there, while ``sortorder`` is enumerated.
    """
    params: dict[str, Any] = {}
    if limit is not None:
        params["limit"] = _bounded("limit", limit, 0, _MAX_ENTITIES_LIMIT)
    if offset is not None:
        params["offset"] = _bounded("offset", offset, 0, _ENTITIES_OFFSET_EXCLUSIVE_MAX - 1)
    if sort_by is not None:
        params["sortby"] = sort_by
    if sort_order is not None:
        params["sortorder"] = _enum_value("sort_order", sort_order, SORT_ORDERS)
    return params


def _getstates_body(
    data_source: str,
    select: builtins.list[Any],
    where: Any | None,
    group_by: builtins.list[str] | None,
    order_by: Any | None,
    limit: int | None,
    offset: int | None,
) -> dict[str, Any]:
    if data_source not in STATE_DATA_SOURCES:
        valid = ", ".join(sorted(STATE_DATA_SOURCES))
        raise ValidationError(
            f"Invalid data_source {data_source!r} for get_states. Must be one of: {valid}"
        )
    body: dict[str, Any] = {"from": data_source, "select": select}
    if group_by:
        body["groupby"] = group_by
    if where is not None:
        body["where"] = where
    if order_by is not None:
        body["orderby"] = order_by
    if limit is not None:
        body["limit"] = _bounded("limit", limit, 0, _QUERY_LIMIT_EXCLUSIVE_MAX - 1)
    if offset is not None:
        body["offset"] = _bounded("offset", offset, 0, _QUERY_OFFSET_EXCLUSIVE_MAX - 1)
    return body


def _gettraceroute_body(
    data_source: str,
    begin: datetime | int,
    end: datetime | int,
    where: Any | None,
    order_by: Any | None,
) -> dict[str, Any]:
    if data_source not in TRACEROUTE_DATA_SOURCES:
        valid = ", ".join(sorted(TRACEROUTE_DATA_SOURCES))
        raise ValidationError(
            f"Invalid data_source {data_source!r} for get_traceroute. Must be one of: {valid}"
        )
    body: dict[str, Any] = {
        "from": data_source,
        "begin": _absolute_bound(begin),
        "end": _absolute_bound(end),
    }
    if where is not None:
        body["where"] = where
    if order_by is not None:
        body["orderby"] = order_by
    return body


def _alert_rule_params(
    category: str | None,
    alert_type: str | None,
    enabled: bool | None,
    severity: str | None,
) -> dict[str, Any]:
    """Build the ``GET /alert/rules`` query (dem_alert.yaml:1289-1316).

    The operation declares ``category``, ``type``, ``enabled`` and ``severity``
    only — there is no ``limit`` or ``offset``.
    """
    params: dict[str, Any] = {}
    if category is not None:
        params["category"] = _enum_value("category", category, ALERT_CATEGORIES)
    if alert_type is not None:
        params["type"] = _enum_value("type", alert_type, ALERT_TYPES)
    if enabled is not None:
        params["enabled"] = enabled
    if severity is not None:
        params["severity"] = _enum_value("severity", severity, ALERT_SEVERITIES)
    return params


def validate_window(limit: int | None, offset: int | None) -> None:
    """Reject a local paging window before the request that would feed it.

    A slice cannot fail the way a rejected query parameter does: ``rules[-3:]``
    is the last three rules, not "page -3". The bounds match the ones the typed
    accessor applies through ``_paging``, so both surfaces refuse the same value
    with the same message.
    """
    if limit is not None:
        _bounded("limit", limit, 0, None)
    if offset is not None:
        _bounded("offset", offset, 0, None)


def _slice_rules(body: Any, limit: int | None, offset: int | None) -> Any:
    """Apply an SDK-side slice to an unpaginated ``{remainingQuota, rules}`` body.

    ``findAlertRules`` returns every matching rule, so *limit*/*offset* are
    honoured here rather than sent as query parameters the operation would
    ignore.
    """
    if (limit is None and offset is None) or not isinstance(body, dict):
        return body
    rules = body.get("rules")
    if not isinstance(rules, list):
        return body
    start = offset or 0
    return {**body, "rules": rules[start : None if limit is None else start + limit]}


def _getalerts_body(
    alert_category: builtins.list[str] | None,
    alert_type: builtins.list[str] | None,
    severity: builtins.list[str] | None,
    open_time: int | None,
    sort_field: str | None,
    sort_desc: bool,
    limit: int,
    offset: int | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if alert_category:
        body["alertCategory"] = _enum_values("alert_category", alert_category, ALERT_CATEGORIES)
    if alert_type:
        body["alertType"] = _enum_values("alert_type", alert_type, ALERT_TYPES)
    if severity:
        body["severity"] = _enum_values("severity", severity, ALERT_SEVERITIES)
    body["limit"] = limit
    if offset is not None:
        body["offset"] = offset
    if open_time is not None:
        body["openTime"] = open_time
    if sort_field:
        body["sortBy"] = {"field": sort_field, "desc": sort_desc}
    return body


def _adem_body(
    start_time: datetime | int,
    end_time: datetime | int,
    *,
    user: str | None = None,
    device_id: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build the common ADEM request body (epoch **seconds**)."""
    body: dict[str, Any] = {
        "starttime": _epoch_seconds(start_time),
        "endtime": _epoch_seconds(end_time),
    }
    if user is not None:
        body["user"] = user
    if device_id is not None:
        body["deviceId"] = device_id
    body.update(extra)
    return body
