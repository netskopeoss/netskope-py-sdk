"""Models for the Netskope Incidents API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from netskope.models.common import NetskopeModel, TimestampMixin


class IncidentStatus(StrEnum):
    """Incident workflow status."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class Incident(NetskopeModel, TimestampMixin):
    """A Netskope security incident."""

    id: str | None = Field(None, alias="_id")
    incident_id: str | int | float | None = None
    user: str | None = None
    # The same rows reach IncidentEvent through the datasearch endpoint, where
    # these fields are already known to arrive as numbers on some tenants.
    severity: str | int | None = Field(None, alias="severity_level")
    status: str | int | None = None
    alert_type: str | None = None
    alert_name: str | None = None
    app: str | None = None
    activity: str | None = None
    object_name: str | None = Field(None, alias="object")
    # Incident rows reach IncidentEvent through the same datasearch endpoint,
    # where the matched policy is `policy` (search_alert.yaml:175-177,
    # search_app.yaml:169-170); search_incident.yaml declares `policy` only
    # inside the nested dlp object (:154-155), so this alias mirrors the
    # sibling model rather than narrowing what a row may carry.
    policy_name: str | None = Field(None, validation_alias=AliasChoices("policy_name", "policy"))
    action: str | None = None
    assignee: str | int | None = None
    dlp_profile: str | int | None = None
    dlp_rule: str | int | None = None


class Anomaly(NetskopeModel, TimestampMixin):
    """A UBA (User Behavior Analytics) anomaly."""

    id: str | None = Field(None, alias="_id", validation_alias=AliasChoices("_id", "anomalyId"))
    user: str | None = None
    anomaly_type: str | None = None
    risk_level: str | None = None
    description: str | None = None
    app: str | None = None
    event_id: str | None = Field(None, alias="eventId")
    time: int | None = None
    score: int | None = None
    severity: str | int | None = None
    rule_id: str | None = Field(None, alias="ruleId")
    window_id: int | None = Field(None, alias="windowId")
    activity: str | None = None
    alert_id: str | None = Field(None, alias="alertId")
    alert_name: str | None = Field(None, alias="alertName")
    source_ip: str | None = Field(None, alias="sourceIp")
    destination_ip: str | None = Field(None, alias="destinationIp")


class IncidentNote(NetskopeModel):
    """A free-text note attached to a DLP incident.

    Notes record investigation findings, handoff context, or remediation
    steps.  Each incident can hold at most 25 notes, and each note must be
    under 512 characters.
    """

    note_id: str | None = None
    user: str | None = None
    timestamp: int | None = None
    content: str | None = None
    dlp_incident_id: int | None = None


class ConfidencePoint(NetskopeModel):
    """One UCI observation; ``start`` uses epoch milliseconds.

    ubadatasvc.yaml:52-60 declares both fields without a ``required`` list, so
    a point that carries only one of them must still decode.
    """

    start: int | None = None
    confidence_score: int | None = Field(None, alias="confidenceScore")


class UserConfidenceIndex(NetskopeModel):
    """User Confidence Index (UCI) time series for one user.

    ubadatasvc.yaml:61-69 defines the response as ``confidences`` plus
    ``userId`` and nothing else, so there is no aggregate score field to read.
    The latest point in *confidences* carries the current score.

    Example::

        uci = client.incidents.get_uci("user@example.com")
        latest = (uci.confidences or [])[-1:]
        for point in latest:
            print(f"Risk score: {point.confidence_score}")
    """

    user_id: str | None = Field(None, alias="userId")
    confidences: list[ConfidencePoint] | None = None


class IncidentForensics(NetskopeModel):
    """DLP evidence returned by the incident forensics operation."""

    meta: str | None = None
    content: str | None = None
    preview_image: str | None = None


class IncidentUpdateRequest(BaseModel):
    """One update target, separate from the legacy object-ID-only SDK method.

    A numeric incident ID addresses one incident. An object ID plus old value
    can match several incidents. The service does not report affected rows.
    """

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    incident_id: int | None = Field(None, ge=0)
    object_id: str | None = Field(None, min_length=1)
    field: Literal["status", "assignee", "severity"]
    new_value: str
    user: str = Field(min_length=1)
    old_value: str | None = None

    @model_validator(mode="after")
    def validate_target(self) -> Self:
        if (self.incident_id is None) == (self.object_id is None):
            raise ValueError("Specify exactly one incident_id or object_id.")
        if self.object_id is not None and self.old_value is None:
            raise ValueError("An object_id update requires old_value.")
        if self.incident_id is not None and self.old_value is not None:
            raise ValueError("An incident_id update does not support old_value.")
        return self


class IncidentUpdateOutcome(NetskopeModel):
    """Acceptance of one payload entry, not a count of changed incidents.

    ``ok`` is the success flag. ``result`` is whatever the service reported
    alongside it: an entry count, a numeric count as a string, a message such
    as ``"Update Successful"``, or nothing at all.

    ``incident_update_200_response_item`` (incidents/incident_update.yaml:8-14)
    declares ``{ok: integer, result: string}`` with no ``required`` list and no
    ``enum``/``minimum``/``maximum`` on ``ok``, so both properties are optional
    and ``ok`` is an unbounded integer. Only ``ok == 1`` counts as acceptance :
    see :attr:`IncidentUpdateResult.accepted`.
    """

    ok: int | None = None
    result: int | str | None = None

    @field_validator("ok", mode="before")
    @classmethod
    def _reject_boolean_flag(cls, value: Any) -> Any:
        """``ok`` is declared ``type: integer``; JSON ``true`` is not one."""
        if isinstance(value, bool):
            raise ValueError("The ok flag must be an integer.")
        return value

    @field_validator("result", mode="before")
    @classmethod
    def _decimal_result(cls, value: Any) -> Any:
        return int(value) if isinstance(value, str) and value.isdecimal() else value

    @property
    def count(self) -> int | None:
        """The reported entry count, or ``None`` when only a message was returned."""
        return self.result if isinstance(self.result, int) else None


class IncidentUpdateResult(NetskopeModel):
    """Validated outcomes from the single write request."""

    outcomes: list[IncidentUpdateOutcome]

    @property
    def accepted_entries(self) -> int:
        """Sum of the reported counts; message-only outcomes contribute nothing."""
        return sum(outcome.count or 0 for outcome in self.outcomes if outcome.ok == 1)

    @property
    def accepted(self) -> bool:
        """Whether every entry reported success through its ``ok`` flag.

        incident_update.yaml:8-14 types the entry as ``{ok, result}`` with
        ``result`` a string, and the documented success body is
        ``{"result": [{"ok": 1, "result": "Update Successful"}]}``
        (incident_update.yaml:69-75) — so ``ok`` is the acceptance signal and a
        message carries no count. A reported count of zero still contradicts
        acceptance; read :attr:`accepted_entries` for the count itself. An
        absent ``ok``, or any value other than ``1``, is not acceptance.
        """
        return bool(self.outcomes) and all(
            outcome.ok == 1 and (outcome.count is None or outcome.count > 0)
            for outcome in self.outcomes
        )


class IncidentNoteCreate(BaseModel):
    """Validated note text. The service owns the per-incident note limit."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    content: str = Field(max_length=511)
