"""Paths and payload builders shared by the incidents resource and its decoder.

Kept apart from both so the resource can import the decoder for its
``with_response`` accessor without the decoder importing the resource
back. This is the shape ``netskope/resources/shared/datasearch_query.py``
already uses.
"""

from __future__ import annotations

import builtins
from datetime import UTC, datetime, timedelta
from typing import Any

from netskope.core.ids import quote_id
from netskope.exceptions import ValidationError

_SEARCH_PATH = "/api/v2/events/datasearch/incident"


_UPDATE_PATH = "/api/v2/incidents/update"


_DLP_INCIDENTS_PATH = "/api/v2/incidents/dlpincidents"


_UCI_PATH = "/api/v2/ubadatasvc/user/uci"


_ANOMALIES_PATH = "/api/v2/incidents/users/getanomalies"


_UCI_DEFAULT_WINDOW = timedelta(days=7)


def _build_uci_payload(username: str, from_time: datetime | int | None) -> dict[str, Any]:
    """Validate one UCI request before HTTP; epoch ``0`` remains a valid window."""
    if not isinstance(username, str) or not username.strip():
        raise ValidationError("username must be a nonblank string.")
    if isinstance(from_time, bool) or (
        from_time is not None and not isinstance(from_time, (datetime, int))
    ):
        raise ValidationError("from_time must be a datetime or epoch milliseconds.")
    if isinstance(from_time, datetime) and (
        from_time.tzinfo is None or from_time.utcoffset() is None
    ):
        raise ValidationError("from_time must include a timezone.")
    if from_time is None:
        from_time_ms = int((datetime.now(tz=UTC) - _UCI_DEFAULT_WINDOW).timestamp() * 1000)
    elif isinstance(from_time, datetime):
        from_time_ms = int(from_time.timestamp() * 1000)
    else:
        from_time_ms = from_time
    return {"user": username, "fromTime": from_time_ms}


def _build_anomalies_request(
    users: builtins.list[str],
    timeframe: int,
    severity: str | builtins.list[str] | None,
    limit: int,
    offset: int,
    sort_by: str,
    sort_order: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the verified anomaly search: users/timeframe body, paging in the query."""
    if severity is not None:
        raise ValidationError("Anomaly search does not support a server-side severity filter.")
    if (
        not isinstance(users, list)
        or not users
        or any(not isinstance(user, str) or not user.strip() for user in users)
    ):
        raise ValidationError("users must contain at least one nonempty username.")
    if isinstance(timeframe, bool) or not isinstance(timeframe, int) or timeframe < 1:
        # uba.yaml:608-615 declares no upper bound on timeframe, so the SDK
        # only rejects values the field cannot mean (unit is whole days).
        raise ValidationError(f"Invalid timeframe {timeframe!r}. Must be at least 1 day.")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10000:
        raise ValidationError(f"Invalid limit {limit!r}. Must be between 1 and 10000.")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValidationError(f"Invalid offset {offset!r}. Must be >= 0.")
    if not isinstance(sort_by, str) or not sort_by:
        raise ValidationError("sort_by must be a nonempty field name.")
    if sort_order not in ("asc", "desc"):
        raise ValidationError(f"Invalid sort_order {sort_order!r}. Must be 'asc' or 'desc'.")
    return (
        {"users": users, "timeframe": timeframe},
        {"limit": limit, "offset": offset, "sortby": sort_by, "sortorder": sort_order},
    )


def _notes_path(dlp_incident_id: str) -> str:
    return f"{_DLP_INCIDENTS_PATH}/{quote_id(dlp_incident_id)}/notes"
