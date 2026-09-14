"""Paths and payload builders shared by the events resource and its decoder.

Kept apart from both so the resource can import the decoder for its
``with_response`` accessor without the decoder importing the resource
back. This is the shape ``netskope/resources/shared/datasearch_query.py``
already uses.
"""

from __future__ import annotations

import builtins
from datetime import datetime
from typing import Any

from netskope.exceptions import ValidationError
from netskope.models.events import (
    AuditEvent,
    ClientStatusEvent,
    Event,
    EventQueryCapabilities,
    EventType,
    IncidentEvent,
    NetworkEvent,
    PageEvent,
)

_DATASEARCH_BASE = "/api/v2/events/datasearch"


_AUDIT_PATH = "/api/v2/events/data/audit"


_INFRASTRUCTURE_PATH = "/api/v2/events/data/infrastructure"


_TRANSACTION_PATH = "/api/v2/events/metrics/transactionevents"


_MODEL_MAP: dict[str, type[Event]] = {
    "network": NetworkEvent,
    "page": PageEvent,
    "audit": AuditEvent,
    "clientstatus": ClientStatusEvent,
    "incident": IncidentEvent,
}


_PATH_OVERRIDES: dict[str, str] = {
    EventType.AUDIT.value: _AUDIT_PATH,
    EventType.INFRASTRUCTURE.value: _INFRASTRUCTURE_PATH,
    EventType.TRANSACTION.value: _TRANSACTION_PATH,
}


_DATASEARCH_TYPES = frozenset(e.value for e in EventType) - set(_PATH_OVERRIDES)


_INSERTION_TIME_TYPES = frozenset({EventType.AUDIT.value, EventType.INFRASTRUCTURE.value})


_TRANSACTION_IS_METRICS = (
    "Transaction events are hourly metrics; use transaction_metrics(hours=...)."
)


def _event_path(event_type: str | EventType) -> str:
    """Resolve one event type's endpoint from the single path table."""
    return _PATH_OVERRIDES.get(str(event_type), f"{_DATASEARCH_BASE}/{event_type}")


def _event_model(event_type: str | EventType) -> type[Event]:
    return _MODEL_MAP.get(str(event_type), Event)


def event_capabilities(event_type: str | EventType) -> EventQueryCapabilities:
    """Return one event category's declared query capabilities and page ceiling."""
    if event_type in _DATASEARCH_TYPES:
        return EventQueryCapabilities(
            page_limit=10000,
            scannable=True,
            projection=True,
            grouping=True,
            ordering=True,
            jql=True,
        )
    if event_type == "infrastructure":
        return EventQueryCapabilities(
            page_limit=5000,
            scannable=False,
            projection=False,
            grouping=False,
            ordering=False,
            jql=True,
        )
    if event_type == "audit":
        # audit.yaml:12-18 declares the same `query` filter as every other
        # category; what it lacks is fields/groupbys/orderbys.
        return EventQueryCapabilities(
            page_limit=5000,
            scannable=False,
            projection=False,
            grouping=False,
            ordering=False,
            jql=True,
        )
    if event_type == "transaction":
        raise ValidationError(_TRANSACTION_IS_METRICS)
    raise ValidationError("Unknown event category.")


def _endpoint(
    event_type: str | EventType,
    fields: builtins.list[str] | None,
    order_by: str | None,
    group_by: str | builtins.list[str] | None = None,
    audit_type: str | None = None,
) -> tuple[str, type[Event], EventQueryCapabilities]:
    """Reject unsupported query features, then resolve the path and record model."""
    capabilities = event_capabilities(event_type)
    if audit_type is not None and str(event_type) != EventType.AUDIT.value:
        raise ValidationError(f"{event_type} events do not support the audit_type filter.")
    if not capabilities.projection and fields is not None:
        raise ValidationError(f"{event_type} events do not support server-side field projection.")
    if not capabilities.grouping and group_by is not None:
        raise ValidationError(f"{event_type} events do not support server-side grouping.")
    if not capabilities.ordering and order_by is not None:
        raise ValidationError(f"{event_type} events do not support server-side ordering.")
    return _event_path(event_type), _event_model(event_type), capabilities


def _within_page_limit(
    event_type: str | EventType, capabilities: EventQueryCapabilities, params: dict[str, Any]
) -> dict[str, Any]:
    """Refuse a page size above the ceiling the endpoint's own schema declares."""
    if params.get("limit", 0) > capabilities.page_limit:
        raise ValidationError(
            f"{event_type} events support a maximum limit of {capabilities.page_limit}."
        )
    return params


def audit_type_query(query: str | None, audit_type: str | None) -> str | None:
    """Fold the SDK's *audit_type* convenience into the endpoint's ``query``.

    ``/events/data/audit`` has no ``type`` parameter (events/audit.yaml:12-72);
    it filters through the same ``query`` expression every other category uses,
    so the audit type travels as a JQL clause.
    """
    if audit_type is None:
        return query
    if not isinstance(audit_type, str) or not audit_type.strip() or '"' in audit_type:
        raise ValidationError("audit_type must be a nonblank string without a double quote.")
    clause = f'type eq "{audit_type}"'
    return f"({query}) and {clause}" if query else clause


def _insertion_epoch(name: str, bound: datetime | int) -> int:
    """Convert one insertion-time bound the way the sibling time bounds convert.

    ``_AlertQuery._epoch`` rejects a naive datetime rather than guessing a zone:
    ``int(naive.timestamp())`` silently reads the caller's local time and sends
    a bound hours away from the one they wrote.  These two parameters are built
    outside that model, so the rule is restated rather than inherited.
    """
    if isinstance(bound, datetime):
        if bound.tzinfo is None or bound.utcoffset() is None:
            raise ValidationError(f"{name} must include a timezone.")
        return int(bound.timestamp())
    if isinstance(bound, bool) or not isinstance(bound, int):
        raise ValidationError(f"{name} must be an epoch integer or an aware datetime.")
    return bound


def _insertion_params(
    event_type: str,
    insertion_start_time: datetime | int | None,
    insertion_end_time: datetime | int | None,
) -> dict[str, Any]:
    supplied = insertion_start_time is not None or insertion_end_time is not None
    if supplied and event_type not in _INSERTION_TIME_TYPES:
        raise ValidationError(
            f"{event_type} events do not support insertion-time bounds; "
            f"they are declared only for {', '.join(sorted(_INSERTION_TIME_TYPES))}."
        )
    params: dict[str, Any] = {}
    for key, name, bound in (
        ("insertionstarttime", "insertion_start_time", insertion_start_time),
        ("insertionendtime", "insertion_end_time", insertion_end_time),
    ):
        if bound is not None:
            params[key] = _insertion_epoch(name, bound)
    return params
