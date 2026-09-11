"""Digital Experience Management (DEM) resource — probes, alerts, query, and ADEM telemetry.

``client.dem`` groups the DEM surfaces under one namespace::

    client.dem.probes            # application probes  (dem/appprobes)
    client.dem.network_probes    # network probes      (dem/networkprobes)
    client.dem.alert_rules       # experience-alert rules (dem/alert/rules)
    client.dem.alerts            # triggered experience alerts (dem/alerts)
    client.dem.query             # privileged metric/entity/state/traceroute query
    client.dem.apps              # DEM-monitored applications
    client.dem.users             # ADEM per-user/per-device telemetry

Time arguments are accepted as a ``datetime`` or a bare ``int``, and the SDK
puts each endpoint's own shape on the wire:

* ``dem/query/getdata``, ``getdataset`` and ``gettraceroute`` send
  ``begin``/``end`` as ``{"absolute": "<RFC 3339>"}`` objects
  (``QueryInput.begin``/``.end``, dem-workbench-query.yaml:419-433).  A bare
  ``int`` is read as epoch **milliseconds** and converted for you.
* ``dem/query/getentities`` and **all** ADEM (``adem/users/*``) endpoints send
  epoch **seconds** in ``starttime``/``endtime``.  A bare ``int`` is passed
  through as-is.

A naive ``datetime`` is interpreted in the local timezone; pass an aware one to
be explicit.
"""

from __future__ import annotations

import asyncio
import builtins
import functools
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from netskope.exceptions import ValidationError
from netskope.models.dem import (
    DATA_QUERY_SOURCES,
    STATE_DATA_SOURCES,
    TRACEROUTE_DATA_SOURCES,
    AdemApplication,
    AdemDevice,
    AdemUserInfo,
    AggregationType,
    DemAlert,
    DemQueryResult,
    NetworkMetricType,
)
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import extract_item, extract_list, quote_id, validate_id

if TYPE_CHECKING:
    from netskope.resources._dem_response import (
        AsyncDemAlertResponses,
        AsyncDemAlertRuleResponses,
        AsyncDemAppResponses,
        AsyncDemNetworkProbeResponses,
        AsyncDemProbeResponses,
        AsyncDemQueryResponses,
        AsyncDemUserResponses,
        DemAlertResponses,
        DemAlertRuleResponses,
        DemAppResponses,
        DemNetworkProbeResponses,
        DemProbeResponses,
        DemQueryResponses,
        DemUserResponses,
    )

# --- Path constants -------------------------------------------------------

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

# --- Limits ---------------------------------------------------------------

_MAX_ENTITIES_WINDOW_SECONDS = 48 * 3600  # getentities window cap: 48 hours
_MAX_ENTITIES_LIMIT = 100
_MAX_QUERY_LIMIT = 50000


# --- Time helpers ---------------------------------------------------------


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


# --- Shared payload builders ----------------------------------------------


# Arguments the old ``{"data": {...}}`` probe body carried that ``AppProbeCreateRequest``
# (demconfig.yaml:2744) does not define, with the spec field to use instead.
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
        "os": list(os or ()),
        "deviceClassification": list(device_classification or ()),
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
        "severity": severity,
        "enabled": enabled,
        "criteria": criteria,
    }
    for key, value in (
        ("category", category),
        ("type", alert_type),
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
        body["limit"] = min(limit, _MAX_QUERY_LIMIT)
    if offset is not None:
        body["offset"] = offset
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
    start = _epoch_seconds(start_time)
    end = _epoch_seconds(end_time)
    window = end - start
    if window > _MAX_ENTITIES_WINDOW_SECONDS:
        raise ValidationError(f"Time range too large: {window / 3600:.1f} hours (max 48 hours).")
    body: dict[str, Any] = {"starttime": start, "endtime": end}
    if user is not None:
        body["user"] = user
    if application is not None:
        body["application"] = application
    if applications is not None:
        body["applications"] = applications
    if device_os is not None:
        body["deviceOs"] = device_os
    if monitoring is not None:
        body["monitoring"] = monitoring
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
    """Build the ``/query/getentities`` query (dem-workbench-query.yaml:1208-1253)."""
    params: dict[str, Any] = {}
    if limit is not None:
        params["limit"] = min(limit, _MAX_ENTITIES_LIMIT)
    if offset is not None:
        params["offset"] = offset
    if sort_by is not None:
        params["sortby"] = sort_by
    if sort_order is not None:
        params["sortorder"] = sort_order
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
        body["limit"] = limit
    if offset is not None:
        body["offset"] = offset
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
    for key, value in (
        ("category", category),
        ("type", alert_type),
        ("enabled", enabled),
        ("severity", severity),
    ):
        if value is not None:
            params[key] = value
    return params


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
        body["alertCategory"] = alert_category
    if alert_type:
        body["alertType"] = alert_type
    if severity:
        body["severity"] = severity
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


def _normalize_device_list(body: Any) -> builtins.list[dict[str, Any]]:
    """Normalize a getlist response: bare list vs ``{"data": [...]}`` / ``{"devices": [...]}``."""
    if isinstance(body, list):
        return [d for d in body if isinstance(d, dict)]
    return extract_list(body, "devices")


# =========================================================================
# Application probes
# =========================================================================


class DemProbesResource(SyncResource):
    """DEM application probes — ``/api/v2/dem/appprobes``."""

    @functools.cached_property
    def with_response(self) -> DemProbeResponses:
        """Inspect one completed request together with its typed result."""
        from netskope.resources._dem_response import DemProbeResponses

        return DemProbeResponses(self._transport)

    def list(self, *, limit: int | None = None, offset: int | None = None) -> dict[str, Any]:
        """List configured application probes."""
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return self._get(_APPPROBES_PATH, **params)

    def create(
        self,
        name: str,
        target: str | None = None,
        *,
        frequency: int | None = None,
        entity: dict[str, builtins.list[str]] | None = None,
        os: builtins.list[str] | None = None,
        device_classification: builtins.list[str] | None = None,
        status: int = 1,
        app_name: str | None = None,
        app_id: int | None = None,
        move: dict[str, Any] | None = None,
        protocol: str | None = None,
        interval: int | None = None,
        additional_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create an application probe.

        ``POST /api/v2/dem/appprobes`` takes the probe object itself — no
        ``data`` wrapper.  ``name``, ``frequency``, ``entity``, ``os``,
        ``device_classification`` and ``status`` are all required, along with
        exactly one of *app_name* (a predefined app) or *app_id* (a custom
        one), and a ``move`` that places the probe in the priority list.

        Args:
            name: Probe name.
            target: Retired — the schema has no target; an app probe follows
                an app named by *app_name* or *app_id*.  Supplying it raises.
            frequency: Probe interval in minutes.
            entity: ``{"user": [...], "group": [...], "ou": [...]}``.
            os: ``"windows"`` and/or ``"mac"``.
            device_classification: ``"managed"``, ``"unmanaged"`` and/or
                ``"not configured"``.
            status: ``1`` to enable the probe, ``0`` to create it disabled.
            app_name: Name of a predefined app (``appType="predefined"``).
            app_id: ID of a custom app (``appType="custom"``).
            move: ``{"operation": "top"|"bottom"|"after"|"before"[, "position": n]}``.
                Defaults to ``{"operation": "bottom"}``.
            protocol: Retired — the schema has no protocol.  Supplying it raises.
            interval: Retired — use *frequency* (minutes).  Supplying it raises.
            additional_fields: Extra top-level body fields, merged last.

        Raises:
            netskope.exceptions.ValidationError: If a retired argument is
                supplied, a required field is missing, or the app selector is
                ambiguous.
        """
        body = _probe_create_body(
            name,
            frequency=frequency,
            entity=entity,
            os=os,
            device_classification=device_classification,
            status=status,
            app_name=app_name,
            app_id=app_id,
            move=move,
            retired={"target": target, "protocol": protocol, "interval": interval},
            additional_fields=additional_fields,
        )
        return self._post(_APPPROBES_PATH, json=body)

    def get(self, probe_id: str | int) -> dict[str, Any]:
        """Get a single application probe by ID."""
        return self._get(f"{_APPPROBES_PATH}/{validate_id(probe_id, 'probe_id')}")

    def update(self, probe_id: str | int, data: dict[str, Any]) -> dict[str, Any]:
        """Update an application probe (PUT).  *data* is sent as the raw body."""
        return self._put(f"{_APPPROBES_PATH}/{validate_id(probe_id, 'probe_id')}", json=data)

    def delete(self, probe_id: str | int) -> None:
        """Delete an application probe.  Irreversible."""
        self._delete(f"{_APPPROBES_PATH}/{validate_id(probe_id, 'probe_id')}")


class AsyncDemProbesResource(AsyncResource):
    """Async DEM application probes."""

    @functools.cached_property
    def with_response(self) -> AsyncDemProbeResponses:
        """Inspect one completed request together with its typed result."""
        from netskope.resources._dem_response import AsyncDemProbeResponses

        return AsyncDemProbeResponses(self._transport)

    async def list(self, *, limit: int | None = None, offset: int | None = None) -> dict[str, Any]:
        """List configured application probes."""
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return await self._get(_APPPROBES_PATH, **params)

    async def create(
        self,
        name: str,
        target: str | None = None,
        *,
        frequency: int | None = None,
        entity: dict[str, builtins.list[str]] | None = None,
        os: builtins.list[str] | None = None,
        device_classification: builtins.list[str] | None = None,
        status: int = 1,
        app_name: str | None = None,
        app_id: int | None = None,
        move: dict[str, Any] | None = None,
        protocol: str | None = None,
        interval: int | None = None,
        additional_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """See :meth:`DemProbesResource.create`."""
        body = _probe_create_body(
            name,
            frequency=frequency,
            entity=entity,
            os=os,
            device_classification=device_classification,
            status=status,
            app_name=app_name,
            app_id=app_id,
            move=move,
            retired={"target": target, "protocol": protocol, "interval": interval},
            additional_fields=additional_fields,
        )
        return await self._post(_APPPROBES_PATH, json=body)

    async def get(self, probe_id: str | int) -> dict[str, Any]:
        """See :meth:`DemProbesResource.get`."""
        return await self._get(f"{_APPPROBES_PATH}/{validate_id(probe_id, 'probe_id')}")

    async def update(self, probe_id: str | int, data: dict[str, Any]) -> dict[str, Any]:
        """See :meth:`DemProbesResource.update`."""
        return await self._put(f"{_APPPROBES_PATH}/{validate_id(probe_id, 'probe_id')}", json=data)

    async def delete(self, probe_id: str | int) -> None:
        """See :meth:`DemProbesResource.delete`."""
        await self._delete(f"{_APPPROBES_PATH}/{validate_id(probe_id, 'probe_id')}")


# =========================================================================
# Network probes
# =========================================================================


class DemNetworkProbesResource(SyncResource):
    """DEM network probes — ``/api/v2/dem/networkprobes``."""

    @functools.cached_property
    def with_response(self) -> DemNetworkProbeResponses:
        """Inspect one completed request together with its typed result."""
        from netskope.resources._dem_response import DemNetworkProbeResponses

        return DemNetworkProbeResponses(self._transport)

    def list(self, *, limit: int | None = None, offset: int | None = None) -> dict[str, Any]:
        """List configured network probes."""
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return self._get(_NETWORKPROBES_PATH, **params)

    def get(self, probe_id: str | int) -> dict[str, Any]:
        """Get a single network probe by ID."""
        return self._get(f"{_NETWORKPROBES_PATH}/{validate_id(probe_id, 'probe_id')}")

    def update(self, probe_id: str | int, data: dict[str, Any]) -> dict[str, Any]:
        """Update a network probe (PUT).  *data* is sent as the raw body."""
        return self._put(f"{_NETWORKPROBES_PATH}/{validate_id(probe_id, 'probe_id')}", json=data)

    def delete(self, probe_id: str | int) -> None:
        """Delete a network probe.  Irreversible."""
        self._delete(f"{_NETWORKPROBES_PATH}/{validate_id(probe_id, 'probe_id')}")


class AsyncDemNetworkProbesResource(AsyncResource):
    """Async DEM network probes."""

    @functools.cached_property
    def with_response(self) -> AsyncDemNetworkProbeResponses:
        """Inspect one completed request together with its typed result."""
        from netskope.resources._dem_response import AsyncDemNetworkProbeResponses

        return AsyncDemNetworkProbeResponses(self._transport)

    async def list(self, *, limit: int | None = None, offset: int | None = None) -> dict[str, Any]:
        """List configured network probes."""
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return await self._get(_NETWORKPROBES_PATH, **params)

    async def get(self, probe_id: str | int) -> dict[str, Any]:
        """See :meth:`DemNetworkProbesResource.get`."""
        return await self._get(f"{_NETWORKPROBES_PATH}/{validate_id(probe_id, 'probe_id')}")

    async def update(self, probe_id: str | int, data: dict[str, Any]) -> dict[str, Any]:
        """See :meth:`DemNetworkProbesResource.update`."""
        return await self._put(
            f"{_NETWORKPROBES_PATH}/{validate_id(probe_id, 'probe_id')}", json=data
        )

    async def delete(self, probe_id: str | int) -> None:
        """See :meth:`DemNetworkProbesResource.delete`."""
        await self._delete(f"{_NETWORKPROBES_PATH}/{validate_id(probe_id, 'probe_id')}")


# =========================================================================
# Alert rules
# =========================================================================


class DemAlertRulesResource(SyncResource):
    """DEM experience-alert rules — ``/api/v2/dem/alert/rules``."""

    @functools.cached_property
    def with_response(self) -> DemAlertRuleResponses:
        """Inspect one completed request together with its typed result."""
        from netskope.resources._dem_response import DemAlertRuleResponses

        return DemAlertRuleResponses(self._transport)

    def list(
        self,
        *,
        category: str | None = None,
        type: str | None = None,
        enabled: bool | None = None,
        severity: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List configured DEM alert rules.

        ``GET /api/v2/dem/alert/rules`` declares only the four filters below
        and returns every match, so *limit* and *offset* slice the decoded
        ``rules`` collection on the client rather than travelling as query
        parameters.

        Args:
            category: ``"Network"``, ``"Platform"``, ``"Private Apps"``,
                ``"User Experience"`` or ``"Site"``.
            type: An ``AlertType`` value, e.g. ``"Experience Score"``.
            enabled: Restrict to enabled or disabled rules.
            severity: ``"info"``, ``"low"``, ``"medium"``, ``"high"`` or
                ``"critical"``.
            limit: Rules to keep, applied by the SDK after decoding.
            offset: Rules to skip, applied by the SDK after decoding.
        """
        params = _alert_rule_params(category, type, enabled, severity)
        body = self._get(_ALERT_RULES_PATH, **params)
        return cast(dict[str, Any], _slice_rules(body, limit, offset))

    def create(
        self,
        name: str,
        metric: str,
        threshold: float,
        *,
        severity: str = "medium",
        probe_id: str | None = None,
        category: str | None = None,
        type: str | None = None,
        enabled: bool = True,
        email_receiver: str | None = None,
        criteria_type: str | None = None,
        window: int | None = None,
        filter: dict[str, Any] | None = None,
        duration: int | None = None,
        criteria: dict[str, Any] | None = None,
        additional_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a DEM alert rule.

        ``POST /api/v2/dem/alert/rules`` takes the rule object itself.  The
        measurement and its threshold live inside ``criteria``:
        ``{"condition": {"measure": <metric>, "thresholds": {"threshold":
        <threshold>}}}``.

        Args:
            name: Rule name.
            metric: An ``AlertRuleMeasure`` value (e.g. ``"userDemScore"``,
                ``"popLatency_p95"``), sent as ``criteria.condition.measure``.
            threshold: Sent as ``criteria.condition.thresholds.threshold``.
            severity: ``"info"``, ``"low"``, ``"medium"``, ``"high"`` or
                ``"critical"``.
            probe_id: Retired — the schema has no probe_id.  Supplying it
                raises; scope a rule with ``criteria.condition.filter``.
            category: An ``AlertCategory`` value.
            type: An ``AlertType`` value.
            enabled: Whether the rule is active.
            email_receiver: Address to notify.
            criteria_type: ``criteriaType``; the API supports ``"event"``.
            window: Aggregation window in seconds, inside ``criteria.condition``.
            filter: ``criteria.condition.filter`` scope expression.
            duration: Seconds the threshold must stay violated.
            criteria: A complete ``criteria`` object, replacing the one built
                from *metric*/*threshold*/*window*/*filter*/*duration*.
            additional_fields: Extra top-level body fields, merged last.

        Raises:
            netskope.exceptions.ValidationError: If *probe_id* is supplied.
        """
        body = _alert_rule_create_body(
            name,
            metric,
            threshold,
            severity,
            probe_id,
            category=category,
            alert_type=type,
            enabled=enabled,
            email_receiver=email_receiver,
            criteria_type=criteria_type,
            window=window,
            filter=filter,
            duration=duration,
            criteria=criteria,
            additional_fields=additional_fields,
        )
        return self._post(_ALERT_RULES_PATH, json=body)

    def get(self, rule_id: str) -> dict[str, Any]:
        """Get a single alert rule by ID."""
        return self._get(f"{_ALERT_RULES_PATH}/{quote_id(rule_id)}")

    def update(self, rule_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an alert rule (PUT).  *data* is sent as the raw body."""
        return self._put(f"{_ALERT_RULES_PATH}/{quote_id(rule_id)}", json=data)

    def delete(self, rule_id: str) -> None:
        """Delete an alert rule.  Irreversible."""
        self._delete(f"{_ALERT_RULES_PATH}/{quote_id(rule_id)}")


class AsyncDemAlertRulesResource(AsyncResource):
    """Async DEM experience-alert rules."""

    @functools.cached_property
    def with_response(self) -> AsyncDemAlertRuleResponses:
        """Inspect one completed request together with its typed result."""
        from netskope.resources._dem_response import AsyncDemAlertRuleResponses

        return AsyncDemAlertRuleResponses(self._transport)

    async def list(
        self,
        *,
        category: str | None = None,
        type: str | None = None,
        enabled: bool | None = None,
        severity: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """See :meth:`DemAlertRulesResource.list`."""
        params = _alert_rule_params(category, type, enabled, severity)
        body = await self._get(_ALERT_RULES_PATH, **params)
        return cast(dict[str, Any], _slice_rules(body, limit, offset))

    async def create(
        self,
        name: str,
        metric: str,
        threshold: float,
        *,
        severity: str = "medium",
        probe_id: str | None = None,
        category: str | None = None,
        type: str | None = None,
        enabled: bool = True,
        email_receiver: str | None = None,
        criteria_type: str | None = None,
        window: int | None = None,
        filter: dict[str, Any] | None = None,
        duration: int | None = None,
        criteria: dict[str, Any] | None = None,
        additional_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """See :meth:`DemAlertRulesResource.create`."""
        body = _alert_rule_create_body(
            name,
            metric,
            threshold,
            severity,
            probe_id,
            category=category,
            alert_type=type,
            enabled=enabled,
            email_receiver=email_receiver,
            criteria_type=criteria_type,
            window=window,
            filter=filter,
            duration=duration,
            criteria=criteria,
            additional_fields=additional_fields,
        )
        return await self._post(_ALERT_RULES_PATH, json=body)

    async def get(self, rule_id: str) -> dict[str, Any]:
        """See :meth:`DemAlertRulesResource.get`."""
        return await self._get(f"{_ALERT_RULES_PATH}/{quote_id(rule_id)}")

    async def update(self, rule_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """See :meth:`DemAlertRulesResource.update`."""
        return await self._put(f"{_ALERT_RULES_PATH}/{quote_id(rule_id)}", json=data)

    async def delete(self, rule_id: str) -> None:
        """See :meth:`DemAlertRulesResource.delete`."""
        await self._delete(f"{_ALERT_RULES_PATH}/{quote_id(rule_id)}")


# =========================================================================
# Query (PRIVILEGED)
# =========================================================================


class DemQueryResource(SyncResource):
    """DEM metric/entity/state/traceroute query surface.

    PRIVILEGED: these endpoints are internal and are not part of the public,
    documented API.  Scoped API tokens may receive HTTP 403.
    """

    def get_dataset(
        self,
        data_source: str,
        select: builtins.list[Any],
        *,
        begin: datetime | int,
        end: datetime | int,
        where: Any | None = None,
        group_by: builtins.list[str] | None = None,
        order_by: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> DemQueryResult:
        """Query one bounded dataset result, in native epoch milliseconds.

        RUM, HTTP and traceroute sources only; at most 48 hours and 9999 rows.
        Sampling metadata is retained and does not imply complete coverage.
        """
        response = self.with_response.get_dataset(
            data_source,
            select,
            begin=begin,
            end=end,
            where=where,
            group_by=group_by,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        return response.parse()

    @functools.cached_property
    def with_response(self) -> DemQueryResponses:
        """Inspect one completed request together with its typed result."""
        from netskope.resources._dem_response import DemQueryResponses

        return DemQueryResponses(self._transport)

    def get_data(
        self,
        data_source: str,
        select: builtins.list[Any],
        *,
        begin: datetime | int,
        end: datetime | int,
        where: Any | None = None,
        group_by: builtins.list[str] | None = None,
        order_by: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Query experience metrics (``getdata``).  ``begin``/``end`` are epoch **ms**."""
        body = _getdata_body(
            data_source, select, begin, end, where, group_by, order_by, limit, offset
        )
        return self._post(_QUERY_GETDATA_PATH, json=body, retry_safe=True)

    def get_entities(
        self,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        user: str | None = None,
        application: str | None = None,
        applications: builtins.list[str] | None = None,
        device_os: builtins.list[str] | None = None,
        monitoring: str | None = None,
        exp_score: builtins.list[str] | None = None,
        pop: builtins.list[str] | None = None,
        source_ip: str | None = None,
        user_location: builtins.list[dict[str, str]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> dict[str, Any]:
        """List user/device entities (``getentities``).

        ``start_time``/``end_time`` are epoch **seconds** and the window must
        be at most 48 hours.  ``limit`` (capped at 100), ``offset``,
        ``sort_by`` (API default ``user_score``) and ``sort_order`` are sent as
        query parameters; all other filters, ``user_location`` included, go in
        the JSON body as ``userLocation``
        (``[{"city": ..., "country": ..., "region": ...}]``).
        """
        body = _getentities_body(
            start_time,
            end_time,
            user,
            application,
            applications,
            device_os,
            monitoring,
            exp_score,
            pop,
            source_ip,
            user_location,
        )
        params = _getentities_params(limit, offset, sort_order, sort_by)
        return self._post(_QUERY_GETENTITIES_PATH, json=body, retry_safe=True, **params)

    def get_states(
        self,
        data_source: str,
        select: builtins.list[Any],
        *,
        where: Any | None = None,
        group_by: builtins.list[str] | None = None,
        order_by: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Query current agent/client states (``getstates``).  No time window."""
        body = _getstates_body(data_source, select, where, group_by, order_by, limit, offset)
        return self._post(_QUERY_GETSTATES_PATH, json=body, retry_safe=True)

    def get_traceroute(
        self,
        data_source: str,
        *,
        begin: datetime | int,
        end: datetime | int,
        where: Any | None = None,
        order_by: Any | None = None,
    ) -> dict[str, Any]:
        """Query traceroute path data (``gettraceroute``).  ``begin``/``end`` epoch **ms**.

        Note: this endpoint does not support a ``limit`` parameter.
        """
        body = _gettraceroute_body(data_source, begin, end, where, order_by)
        return self._post(_QUERY_GETTRACEROUTE_PATH, json=body, retry_safe=True)

    def definitions(self, *, source: str | None = None) -> dict[str, Any]:
        """List DEM field definitions for query building (``definitions``)."""
        params: dict[str, Any] = {}
        if source:
            params["source"] = source
        return self._get(_QUERY_DEFINITIONS_PATH, **params)


class AsyncDemQueryResource(AsyncResource):
    """Async DEM query surface.  PRIVILEGED — scoped tokens may 403."""

    async def get_dataset(
        self,
        data_source: str,
        select: builtins.list[Any],
        *,
        begin: datetime | int,
        end: datetime | int,
        where: Any | None = None,
        group_by: builtins.list[str] | None = None,
        order_by: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> DemQueryResult:
        """Query one bounded dataset result, in native epoch milliseconds.

        RUM, HTTP and traceroute sources only; at most 48 hours and 9999 rows.
        Sampling metadata is retained and does not imply complete coverage.
        """
        response = await self.with_response.get_dataset(
            data_source,
            select,
            begin=begin,
            end=end,
            where=where,
            group_by=group_by,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        return response.parse()

    @functools.cached_property
    def with_response(self) -> AsyncDemQueryResponses:
        """Inspect one completed request together with its typed result."""
        from netskope.resources._dem_response import AsyncDemQueryResponses

        return AsyncDemQueryResponses(self._transport)

    async def get_data(
        self,
        data_source: str,
        select: builtins.list[Any],
        *,
        begin: datetime | int,
        end: datetime | int,
        where: Any | None = None,
        group_by: builtins.list[str] | None = None,
        order_by: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """See :meth:`DemQueryResource.get_data`."""
        body = _getdata_body(
            data_source, select, begin, end, where, group_by, order_by, limit, offset
        )
        return await self._post(_QUERY_GETDATA_PATH, json=body, retry_safe=True)

    async def get_entities(
        self,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        user: str | None = None,
        application: str | None = None,
        applications: builtins.list[str] | None = None,
        device_os: builtins.list[str] | None = None,
        monitoring: str | None = None,
        exp_score: builtins.list[str] | None = None,
        pop: builtins.list[str] | None = None,
        source_ip: str | None = None,
        user_location: builtins.list[dict[str, str]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> dict[str, Any]:
        """See :meth:`DemQueryResource.get_entities`."""
        body = _getentities_body(
            start_time,
            end_time,
            user,
            application,
            applications,
            device_os,
            monitoring,
            exp_score,
            pop,
            source_ip,
            user_location,
        )
        params = _getentities_params(limit, offset, sort_order, sort_by)
        return await self._post(_QUERY_GETENTITIES_PATH, json=body, retry_safe=True, **params)

    async def get_states(
        self,
        data_source: str,
        select: builtins.list[Any],
        *,
        where: Any | None = None,
        group_by: builtins.list[str] | None = None,
        order_by: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """See :meth:`DemQueryResource.get_states`."""
        body = _getstates_body(data_source, select, where, group_by, order_by, limit, offset)
        return await self._post(_QUERY_GETSTATES_PATH, json=body, retry_safe=True)

    async def get_traceroute(
        self,
        data_source: str,
        *,
        begin: datetime | int,
        end: datetime | int,
        where: Any | None = None,
        order_by: Any | None = None,
    ) -> dict[str, Any]:
        """See :meth:`DemQueryResource.get_traceroute`."""
        body = _gettraceroute_body(data_source, begin, end, where, order_by)
        return await self._post(_QUERY_GETTRACEROUTE_PATH, json=body, retry_safe=True)

    async def definitions(self, *, source: str | None = None) -> dict[str, Any]:
        """See :meth:`DemQueryResource.definitions`."""
        params: dict[str, Any] = {}
        if source:
            params["source"] = source
        return await self._get(_QUERY_DEFINITIONS_PATH, **params)


# =========================================================================
# Experience alerts (triggered instances)
# =========================================================================


class DemAlertsResource(SyncResource):
    """DEM experience alerts (triggered instances) — ``/api/v2/dem/alerts``."""

    @functools.cached_property
    def with_response(self) -> DemAlertResponses:
        """Inspect one completed request together with its typed result."""
        from netskope.resources._dem_response import DemAlertResponses

        return DemAlertResponses(self._transport)

    def search(
        self,
        *,
        alert_category: builtins.list[str] | None = None,
        alert_type: builtins.list[str] | None = None,
        severity: builtins.list[str] | None = None,
        open_time: int | None = None,
        sort_field: str | None = None,
        sort_desc: bool = True,
        limit: int = 10,
        offset: int | None = None,
    ) -> builtins.list[DemAlert]:
        """Search triggered experience alerts (``getalerts``)."""
        body = _getalerts_body(
            alert_category, alert_type, severity, open_time, sort_field, sort_desc, limit, offset
        )
        resp = self._post(_GETALERTS_PATH, json=body, retry_safe=True)
        return [DemAlert.model_validate(item) for item in extract_list(resp, "alerts")]

    def get(self, alert_id: str) -> DemAlert:
        """Get a single experience alert by ID."""
        resp = self._get(f"{_ALERTS_PATH}/{quote_id(alert_id)}")
        return DemAlert.model_validate(extract_item(resp))

    def entities(
        self,
        alert_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> dict[str, Any]:
        """List users/devices impacted by an alert."""
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if sort_by:
            params["sortby"] = sort_by
        if sort_order:
            params["sortorder"] = sort_order
        return self._get(f"{_ALERTS_PATH}/{quote_id(alert_id)}/entities", **params)


class AsyncDemAlertsResource(AsyncResource):
    """Async DEM experience alerts."""

    @functools.cached_property
    def with_response(self) -> AsyncDemAlertResponses:
        """Inspect one completed request together with its typed result."""
        from netskope.resources._dem_response import AsyncDemAlertResponses

        return AsyncDemAlertResponses(self._transport)

    async def search(
        self,
        *,
        alert_category: builtins.list[str] | None = None,
        alert_type: builtins.list[str] | None = None,
        severity: builtins.list[str] | None = None,
        open_time: int | None = None,
        sort_field: str | None = None,
        sort_desc: bool = True,
        limit: int = 10,
        offset: int | None = None,
    ) -> builtins.list[DemAlert]:
        """See :meth:`DemAlertsResource.search`."""
        body = _getalerts_body(
            alert_category, alert_type, severity, open_time, sort_field, sort_desc, limit, offset
        )
        resp = await self._post(_GETALERTS_PATH, json=body, retry_safe=True)
        return [DemAlert.model_validate(item) for item in extract_list(resp, "alerts")]

    async def get(self, alert_id: str) -> DemAlert:
        """See :meth:`DemAlertsResource.get`."""
        resp = await self._get(f"{_ALERTS_PATH}/{quote_id(alert_id)}")
        return DemAlert.model_validate(extract_item(resp))

    async def entities(
        self,
        alert_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> dict[str, Any]:
        """See :meth:`DemAlertsResource.entities`."""
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if sort_by:
            params["sortby"] = sort_by
        if sort_order:
            params["sortorder"] = sort_order
        return await self._get(f"{_ALERTS_PATH}/{quote_id(alert_id)}/entities", **params)


# =========================================================================
# Monitored apps
# =========================================================================


class DemAppsResource(SyncResource):
    """DEM-monitored applications — ``/api/v2/dem/apps``."""

    @functools.cached_property
    def with_response(self) -> DemAppResponses:
        """Inspect one completed request together with its typed result."""
        from netskope.resources._dem_response import DemAppResponses

        return DemAppResponses(self._transport)

    def list(
        self,
        *,
        app_type: str | None = None,
        name: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List DEM-monitored applications.  ``app_type`` is ``custom`` or ``predefined``."""
        params: dict[str, Any] = {}
        if app_type:
            params["type"] = app_type
        if name:
            params["name"] = name
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return self._get(_APPS_PATH, **params)


class AsyncDemAppsResource(AsyncResource):
    """Async DEM-monitored applications."""

    @functools.cached_property
    def with_response(self) -> AsyncDemAppResponses:
        """Inspect one completed request together with its typed result."""
        from netskope.resources._dem_response import AsyncDemAppResponses

        return AsyncDemAppResponses(self._transport)

    async def list(
        self,
        *,
        app_type: str | None = None,
        name: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List DEM-monitored applications.  ``app_type`` is ``custom`` or ``predefined``."""
        params: dict[str, Any] = {}
        if app_type:
            params["type"] = app_type
        if name:
            params["name"] = name
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return await self._get(_APPS_PATH, **params)


# =========================================================================
# ADEM users (dem users)
# =========================================================================


class DemUsersResource(SyncResource):
    """ADEM per-user/per-device telemetry — ``/api/v2/adem/users`` (all POST, epoch **seconds**)."""

    @functools.cached_property
    def with_response(self) -> DemUserResponses:
        """Inspect one completed request together with its typed result."""
        from netskope.resources._dem_response import DemUserResponses

        return DemUserResponses(self._transport)

    def devices(
        self, user: str, *, start_time: datetime | int, end_time: datetime | int
    ) -> builtins.list[AdemDevice]:
        """List devices for a user with experience scores.

        The request body must include ``"userLocation": []`` for the API to
        return the full device list.
        """
        body = _adem_body(start_time, end_time, user=user, userLocation=[])
        resp = self._post(f"{_ADEM_USERS_PATH}/device/getlist", json=body, retry_safe=True)
        return [AdemDevice.model_validate(d) for d in _normalize_device_list(resp)]

    def device_details(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """Get detailed device information (hardware, software, location)."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return self._post(f"{_ADEM_USERS_PATH}/device/getdetails", json=body, retry_safe=True)

    def info(
        self, user: str, *, start_time: datetime | int, end_time: datetime | int
    ) -> AdemUserInfo:
        """Get the user info summary (experience score and location)."""
        body = _adem_body(start_time, end_time, user=user)
        resp = self._post(f"{_ADEM_USERS_PATH}/getinfo", json=body, retry_safe=True)
        return AdemUserInfo.model_validate(extract_item(resp))

    def applications(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> builtins.list[AdemApplication]:
        """List applications on a device with per-app experience scores.

        ``device_id`` is required: without it the API silently returns only a
        1-2 app subset instead of the full per-device list.
        """
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        resp = self._post(f"{_ADEM_USERS_PATH}/getapplications", json=body, retry_safe=True)
        return [AdemApplication.model_validate(a) for a in extract_list(resp, "applications")]

    def locations(self, *, start_time: datetime | int, end_time: datetime | int) -> dict[str, Any]:
        """Get all user locations."""
        body = _adem_body(start_time, end_time)
        return self._post(f"{_ADEM_USERS_PATH}/getlocations", json=body, retry_safe=True)

    def aggregated_scores(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        aggregation_type: str = AggregationType.AVG,
    ) -> dict[str, Any]:
        """Get aggregated experience scores for a device."""
        body = _adem_body(
            start_time,
            end_time,
            user=user,
            device_id=device_id,
            aggregationType=aggregation_type,
        )
        return self._post(
            f"{_ADEM_USERS_PATH}/device/getaggregatedscores", json=body, retry_safe=True
        )

    def exp_score(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """Get the experience-score time series for a device."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return self._post(f"{_ADEM_USERS_PATH}/metrics/getexpscore", json=body, retry_safe=True)

    def rca(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """Get the root-cause-analysis tree and per-component scores for a device."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return self._post(f"{_ADEM_USERS_PATH}/device/getrca", json=body, retry_safe=True)

    def network_metrics(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        metric_type: str = NetworkMetricType.ALL,
    ) -> dict[str, Any]:
        """Get the network-metrics time series (latency/packet loss/jitter) for a device."""
        body = _adem_body(
            start_time, end_time, user=user, device_id=device_id, metricType=metric_type
        )
        return self._post(f"{_ADEM_USERS_PATH}/metrics/getnetwork", json=body, retry_safe=True)

    def npa_hosts(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """Get NPA hosts (with scores/applications) for a user and device."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return self._post(f"{_ADEM_USERS_PATH}/npa/getnpahosts", json=body, retry_safe=True)

    def npa_network_paths(
        self,
        user: str,
        device_id: str,
        npa_host: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """Get the NPA network-path graph between a device and an NPA host."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id, npaHost=npa_host)
        return self._post(f"{_ADEM_USERS_PATH}/npa/getnetworkpaths", json=body, retry_safe=True)

    def traceroute_timestamps(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """List available traceroute timestamps for a device.

        PRIVILEGED: internal endpoint; scoped tokens may receive 403.
        """
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return self._post(
            f"{_ADEM_USERS_PATH}/device/gettraceroutetimestamps", json=body, retry_safe=True
        )

    def traceroute(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """Get detailed traceroute path data for a device.

        PRIVILEGED: internal endpoint; scoped tokens may receive 403.  Pass a
        single timestamp (from :meth:`traceroute_timestamps`) as both
        ``start_time`` and ``end_time``.
        """
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return self._post(f"{_ADEM_USERS_PATH}/device/gettraceroute", json=body, retry_safe=True)

    def diagnose(
        self,
        user: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        device_id: str | None = None,
        application: str | None = None,
        include_npa: bool = False,
    ) -> dict[str, Any]:
        """One-shot digital-experience diagnostic for a user.

        Composes several ADEM calls: user ``info``; the device list (or the
        single ``device_id`` when given); then per-device ``device_details``,
        ``applications``, ``aggregated_scores`` (avg) and ``rca``; and, when
        ``include_npa`` is set, ``npa_hosts`` plus per-host
        ``npa_network_paths``.

        Every sub-call is guarded: a failing endpoint stores ``None`` for that
        slice and appends ``{"endpoint": ..., "error": ...}`` to the returned
        ``"errors"`` list rather than raising.  When ``application`` is given,
        each device's application list is filtered to case-insensitive name
        matches.

        Returns a dict with ``"user_info"``, ``"devices"`` (each with
        ``device_id``, ``details``, ``applications``, ``scores``, ``rca`` and,
        when requested, ``npa``) and ``"errors"``.
        """
        errors: builtins.list[dict[str, Any]] = []
        user_info = self._safe(
            errors, "getinfo", lambda: self.info(user, start_time=start_time, end_time=end_time)
        )
        device_ids = self._resolve_device_ids(user, start_time, end_time, device_id, errors)
        devices = [
            self._diagnose_device(user, did, start_time, end_time, include_npa, application, errors)
            for did in device_ids
        ]
        return {"user_info": user_info, "devices": devices, "errors": errors}

    def _resolve_device_ids(
        self,
        user: str,
        start_time: datetime | int,
        end_time: datetime | int,
        device_id: str | None,
        errors: builtins.list[dict[str, Any]],
    ) -> builtins.list[str]:
        if device_id is not None:
            return [device_id]
        devices = self._safe(
            errors,
            "device/getlist",
            lambda: self.devices(user, start_time=start_time, end_time=end_time),
        )
        return [d.device_id for d in devices or [] if d.device_id]

    def _diagnose_device(
        self,
        user: str,
        did: str,
        start_time: datetime | int,
        end_time: datetime | int,
        include_npa: bool,
        application: str | None,
        errors: builtins.list[dict[str, Any]],
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {"device_id": did}
        entry["details"] = self._safe(
            errors,
            "device/getdetails",
            lambda: self.device_details(user, did, start_time=start_time, end_time=end_time),
        )
        apps = self._safe(
            errors,
            "getapplications",
            lambda: self.applications(user, did, start_time=start_time, end_time=end_time),
        )
        entry["applications"] = _filter_apps(apps, application)
        entry["scores"] = self._safe(
            errors,
            "device/getaggregatedscores",
            lambda: self.aggregated_scores(user, did, start_time=start_time, end_time=end_time),
        )
        entry["rca"] = self._safe(
            errors,
            "device/getrca",
            lambda: self.rca(user, did, start_time=start_time, end_time=end_time),
        )
        if include_npa:
            entry["npa"] = self._diagnose_npa(user, did, start_time, end_time, errors)
        return entry

    def _diagnose_npa(
        self,
        user: str,
        did: str,
        start_time: datetime | int,
        end_time: datetime | int,
        errors: builtins.list[dict[str, Any]],
    ) -> dict[str, Any]:
        hosts = self._safe(
            errors,
            "npa/getnpahosts",
            lambda: self.npa_hosts(user, did, start_time=start_time, end_time=end_time),
        )
        paths = []
        for host_ip in _npa_host_ips(hosts):
            path = self._safe(
                errors,
                f"npa/getnetworkpaths ({host_ip})",
                lambda h=host_ip: self.npa_network_paths(
                    user, did, h, start_time=start_time, end_time=end_time
                ),
            )
            if path is not None:
                paths.append({"npaHost": host_ip, "path": path})
        return {"hosts": hosts, "network_paths": paths}

    @staticmethod
    def _safe(errors: builtins.list[dict[str, Any]], endpoint: str, call: Any) -> Any:
        from netskope.exceptions import APIError

        try:
            return call()
        except APIError as exc:
            errors.append({"endpoint": endpoint, "error": str(exc)})
            return None


class AsyncDemUsersResource(AsyncResource):
    """Async ADEM per-user/per-device telemetry."""

    @functools.cached_property
    def with_response(self) -> AsyncDemUserResponses:
        """Inspect one completed request together with its typed result."""
        from netskope.resources._dem_response import AsyncDemUserResponses

        return AsyncDemUserResponses(self._transport)

    async def devices(
        self, user: str, *, start_time: datetime | int, end_time: datetime | int
    ) -> builtins.list[AdemDevice]:
        """See :meth:`DemUsersResource.devices`."""
        body = _adem_body(start_time, end_time, user=user, userLocation=[])
        resp = await self._post(f"{_ADEM_USERS_PATH}/device/getlist", json=body, retry_safe=True)
        return [AdemDevice.model_validate(d) for d in _normalize_device_list(resp)]

    async def device_details(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.device_details`."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return await self._post(f"{_ADEM_USERS_PATH}/device/getdetails", json=body, retry_safe=True)

    async def info(
        self, user: str, *, start_time: datetime | int, end_time: datetime | int
    ) -> AdemUserInfo:
        """See :meth:`DemUsersResource.info`."""
        body = _adem_body(start_time, end_time, user=user)
        resp = await self._post(f"{_ADEM_USERS_PATH}/getinfo", json=body, retry_safe=True)
        return AdemUserInfo.model_validate(extract_item(resp))

    async def applications(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> builtins.list[AdemApplication]:
        """See :meth:`DemUsersResource.applications`."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        resp = await self._post(f"{_ADEM_USERS_PATH}/getapplications", json=body, retry_safe=True)
        return [AdemApplication.model_validate(a) for a in extract_list(resp, "applications")]

    async def locations(
        self, *, start_time: datetime | int, end_time: datetime | int
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.locations`."""
        body = _adem_body(start_time, end_time)
        return await self._post(f"{_ADEM_USERS_PATH}/getlocations", json=body, retry_safe=True)

    async def aggregated_scores(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        aggregation_type: str = AggregationType.AVG,
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.aggregated_scores`."""
        body = _adem_body(
            start_time,
            end_time,
            user=user,
            device_id=device_id,
            aggregationType=aggregation_type,
        )
        return await self._post(
            f"{_ADEM_USERS_PATH}/device/getaggregatedscores", json=body, retry_safe=True
        )

    async def exp_score(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.exp_score`."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return await self._post(
            f"{_ADEM_USERS_PATH}/metrics/getexpscore", json=body, retry_safe=True
        )

    async def rca(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.rca`."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return await self._post(f"{_ADEM_USERS_PATH}/device/getrca", json=body, retry_safe=True)

    async def network_metrics(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        metric_type: str = NetworkMetricType.ALL,
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.network_metrics`."""
        body = _adem_body(
            start_time, end_time, user=user, device_id=device_id, metricType=metric_type
        )
        return await self._post(
            f"{_ADEM_USERS_PATH}/metrics/getnetwork", json=body, retry_safe=True
        )

    async def npa_hosts(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.npa_hosts`."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return await self._post(f"{_ADEM_USERS_PATH}/npa/getnpahosts", json=body, retry_safe=True)

    async def npa_network_paths(
        self,
        user: str,
        device_id: str,
        npa_host: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.npa_network_paths`."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id, npaHost=npa_host)
        return await self._post(
            f"{_ADEM_USERS_PATH}/npa/getnetworkpaths", json=body, retry_safe=True
        )

    async def traceroute_timestamps(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.traceroute_timestamps`.  PRIVILEGED."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return await self._post(
            f"{_ADEM_USERS_PATH}/device/gettraceroutetimestamps", json=body, retry_safe=True
        )

    async def traceroute(
        self,
        user: str,
        device_id: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.traceroute`.  PRIVILEGED."""
        body = _adem_body(start_time, end_time, user=user, device_id=device_id)
        return await self._post(
            f"{_ADEM_USERS_PATH}/device/gettraceroute", json=body, retry_safe=True
        )

    async def diagnose(
        self,
        user: str,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        device_id: str | None = None,
        application: str | None = None,
        include_npa: bool = False,
    ) -> dict[str, Any]:
        """See :meth:`DemUsersResource.diagnose`.  Per-device calls run concurrently."""
        errors: builtins.list[dict[str, Any]] = []
        user_info = await self._safe(
            errors, "getinfo", self.info(user, start_time=start_time, end_time=end_time)
        )
        if device_id is not None:
            device_ids = [device_id]
        else:
            devices = await self._safe(
                errors,
                "device/getlist",
                self.devices(user, start_time=start_time, end_time=end_time),
            )
            device_ids = [d.device_id for d in devices or [] if d.device_id]
        devices_out = await asyncio.gather(
            *(
                self._diagnose_device(
                    user, did, start_time, end_time, include_npa, application, errors
                )
                for did in device_ids
            )
        )
        return {"user_info": user_info, "devices": list(devices_out), "errors": errors}

    async def _diagnose_device(
        self,
        user: str,
        did: str,
        start_time: datetime | int,
        end_time: datetime | int,
        include_npa: bool,
        application: str | None,
        errors: builtins.list[dict[str, Any]],
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {"device_id": did}
        entry["details"] = await self._safe(
            errors,
            "device/getdetails",
            self.device_details(user, did, start_time=start_time, end_time=end_time),
        )
        apps = await self._safe(
            errors,
            "getapplications",
            self.applications(user, did, start_time=start_time, end_time=end_time),
        )
        entry["applications"] = _filter_apps(apps, application)
        entry["scores"] = await self._safe(
            errors,
            "device/getaggregatedscores",
            self.aggregated_scores(user, did, start_time=start_time, end_time=end_time),
        )
        entry["rca"] = await self._safe(
            errors,
            "device/getrca",
            self.rca(user, did, start_time=start_time, end_time=end_time),
        )
        if include_npa:
            entry["npa"] = await self._diagnose_npa(user, did, start_time, end_time, errors)
        return entry

    async def _diagnose_npa(
        self,
        user: str,
        did: str,
        start_time: datetime | int,
        end_time: datetime | int,
        errors: builtins.list[dict[str, Any]],
    ) -> dict[str, Any]:
        hosts = await self._safe(
            errors,
            "npa/getnpahosts",
            self.npa_hosts(user, did, start_time=start_time, end_time=end_time),
        )
        paths = []
        for host_ip in _npa_host_ips(hosts):
            path = await self._safe(
                errors,
                f"npa/getnetworkpaths ({host_ip})",
                self.npa_network_paths(
                    user, did, host_ip, start_time=start_time, end_time=end_time
                ),
            )
            if path is not None:
                paths.append({"npaHost": host_ip, "path": path})
        return {"hosts": hosts, "network_paths": paths}

    @staticmethod
    async def _safe(errors: builtins.list[dict[str, Any]], endpoint: str, coro: Any) -> Any:
        from netskope.exceptions import APIError

        try:
            return await coro
        except APIError as exc:
            errors.append({"endpoint": endpoint, "error": str(exc)})
            return None


def _filter_apps(
    apps: builtins.list[AdemApplication] | None, application: str | None
) -> builtins.list[AdemApplication] | None:
    if apps is None or not application:
        return apps
    needle = application.lower()
    return [a for a in apps if needle in (a.app_name or "").lower()]


def _npa_host_ips(hosts: dict[str, Any] | None) -> builtins.list[str]:
    if not isinstance(hosts, dict):
        return []
    host_list = hosts.get("npaHosts")
    if not isinstance(host_list, list):
        data = hosts.get("data")
        host_list = data if isinstance(data, list) else []
    ips = []
    for h in host_list:
        if isinstance(h, dict) and h.get("npaHost"):
            ips.append(h["npaHost"])
    return ips


# =========================================================================
# Top-level namespace
# =========================================================================


class DemResource(SyncResource):
    """Top-level DEM namespace: ``client.dem.<sub-resource>``."""

    @functools.cached_property
    def probes(self) -> DemProbesResource:
        """Application probes."""
        return DemProbesResource(self._transport)

    @functools.cached_property
    def network_probes(self) -> DemNetworkProbesResource:
        """Network probes."""
        return DemNetworkProbesResource(self._transport)

    @functools.cached_property
    def alert_rules(self) -> DemAlertRulesResource:
        """Experience-alert rules."""
        return DemAlertRulesResource(self._transport)

    @functools.cached_property
    def alerts(self) -> DemAlertsResource:
        """Triggered experience alerts."""
        return DemAlertsResource(self._transport)

    @functools.cached_property
    def query(self) -> DemQueryResource:
        """Privileged metric/entity/state/traceroute query surface."""
        return DemQueryResource(self._transport)

    @functools.cached_property
    def apps(self) -> DemAppsResource:
        """DEM-monitored applications."""
        return DemAppsResource(self._transport)

    @functools.cached_property
    def users(self) -> DemUsersResource:
        """ADEM per-user/per-device telemetry."""
        return DemUsersResource(self._transport)


class AsyncDemResource(AsyncResource):
    """Async top-level DEM namespace."""

    @functools.cached_property
    def probes(self) -> AsyncDemProbesResource:
        """Application probes."""
        return AsyncDemProbesResource(self._transport)

    @functools.cached_property
    def network_probes(self) -> AsyncDemNetworkProbesResource:
        """Network probes."""
        return AsyncDemNetworkProbesResource(self._transport)

    @functools.cached_property
    def alert_rules(self) -> AsyncDemAlertRulesResource:
        """Experience-alert rules."""
        return AsyncDemAlertRulesResource(self._transport)

    @functools.cached_property
    def alerts(self) -> AsyncDemAlertsResource:
        """Triggered experience alerts."""
        return AsyncDemAlertsResource(self._transport)

    @functools.cached_property
    def query(self) -> AsyncDemQueryResource:
        """Privileged metric/entity/state/traceroute query surface."""
        return AsyncDemQueryResource(self._transport)

    @functools.cached_property
    def apps(self) -> AsyncDemAppsResource:
        """DEM-monitored applications."""
        return AsyncDemAppsResource(self._transport)

    @functools.cached_property
    def users(self) -> AsyncDemUsersResource:
        """ADEM per-user/per-device telemetry."""
        return AsyncDemUsersResource(self._transport)
