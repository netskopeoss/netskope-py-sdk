"""Models for the Netskope Alerts API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator

from netskope.models.common import NetskopeModel, TimestampMixin


class AlertSeverity(StrEnum):
    """Alert severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class AlertType(StrEnum):
    """Known alert type categories."""

    DLP = "DLP"
    MALWARE = "malware"
    ANOMALY = "anomaly"
    COMPROMISED_CREDENTIAL = "Compromised Credential"
    POLICY = "policy"
    LEGAL_HOLD = "Legal Hold"
    QUARANTINE = "quarantine"
    REMEDIATION = "Remediation"
    SECURITY_ASSESSMENT = "Security Assessment"
    WATCHLIST = "watchlist"
    UBA = "uba"
    CTEP = "ctep"
    MALSITE = "malsite"


class Alert(NetskopeModel, TimestampMixin):
    """A Netskope security alert.

    Example::

        alert = client.alerts.get("abc-123")
        print(f"{alert.alert_name} — severity={alert.severity}")
    """

    id: str | None = Field(None, alias="_id")
    alert_name: str | None = None
    alert_type: str | None = None
    # severity_level, ccl, and site arrive as numbers on some tenants; the
    # datasearch Event model accepts both shapes and so must this one.
    severity: str | int | None = Field(None, alias="severity_level")
    user: str | None = None
    app: str | None = None
    activity: str | None = None
    object_name: str | None = Field(None, alias="object")
    policy_name: str | None = None
    action: str | None = None
    site: str | int | None = None
    category: str | None = None
    cci: int | None = None

    @field_validator("cci", mode="before")
    @classmethod
    def _coerce_cci(cls, v: Any) -> int | None:
        if v is None or v == "":
            return None
        return int(v)

    ccl: str | int | None = None
    access_method: str | None = None
    traffic_type: str | None = None
    count: int | None = None
    other_categories: list[str] | None = None
    insertion_epoch_timestamp: int | None = None

    @field_validator("other_categories", mode="before")
    @classmethod
    def _wrap_single_category(cls, v: Any) -> Any:
        """A row with one secondary category sends a bare string, not a list."""
        if isinstance(v, str):
            return [v] if v else None
        return v


class DatasearchBucket(NetskopeModel):
    """One grouped datasearch result, distinct from an individual alert.

    Dimension names are selected by the query. Either dimensions or count may
    be omitted by a projection; unknown aggregation fields remain available.
    """

    dimensions: dict[str, Any] | None = Field(None, alias="_id")
    count: int | None = None
