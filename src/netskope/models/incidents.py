"""Models for the Netskope Incidents API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from netskope.models.common import NetskopeModel, TimestampMixin


class IncidentStatus(StrEnum):
    """Incident workflow status."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class Incident(NetskopeModel, TimestampMixin):
    """A Netskope security incident."""

    id: str | None = Field(None, alias="_id")
    incident_id: str | None = None
    user: str | None = None
    severity: str | None = Field(None, alias="severity_level")
    status: str | None = None
    alert_type: str | None = None
    alert_name: str | None = None
    app: str | None = None
    activity: str | None = None
    object_name: str | None = Field(None, alias="object")
    policy_name: str | None = None
    action: str | None = None
    assignee: str | None = None
    dlp_profile: str | None = None
    dlp_rule: str | None = None


class Anomaly(NetskopeModel, TimestampMixin):
    """A UBA (User Behavior Analytics) anomaly."""

    id: str | None = Field(None, alias="_id")
    user: str | None = None
    anomaly_type: str | None = None
    risk_level: str | None = None
    description: str | None = None
    app: str | None = None


class UserConfidenceIndex(NetskopeModel):
    """User Confidence Index (UCI) risk score.

    Example::

        uci = client.incidents.get_uci("user@example.com")
        print(f"Risk score: {uci.score}")
    """

    user: str | None = None
    score: float | None = None
    severity: str | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
