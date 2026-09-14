"""Models for the Netskope Alerts API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import AliasChoices, Field, field_validator

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
    # search_alert.yaml:175-177 names the matched policy `policy`; only
    # search_epdlp.yaml:88 spells it `policy_name`, so both resolve here.
    policy_name: str | None = Field(None, validation_alias=AliasChoices("policy_name", "policy"))
    action: str | None = None
    site: str | int | None = None
    category: str | None = None
    # search_alert.yaml:48-50 and :54-56 declare cci and count as `type: number`,
    # which admits a fraction, so neither is narrowed to int and neither is
    # rounded: a contract-legal 1.5 decodes as 1.5.
    #
    # search_app.yaml:332 types the same field as `string`, so a non-numeric
    # value is arguably contract-legal and SPEC2-MD-3 proposed tolerating it.
    # That is NOT done here: netskope-cli asserts a malformed numeric field
    # fails before output so an unvalidated value can never be printed
    # (tests/unit/test_sdk_alerts.py::test_malformed_typed_fields_fail_before_
    # output_with_safe_metadata). Resolving the two needs a spec correction,
    # not a unilateral widening.
    cci: int | float | None = None

    @field_validator("cci", mode="before")
    @classmethod
    def _blank_cci_is_absent(cls, v: Any) -> Any:
        """A row with no confidence index sends an empty string, not null."""
        return None if v == "" else v

    ccl: str | int | None = None
    access_method: str | None = None
    traffic_type: str | None = None
    count: int | float | None = None
    # search_alert.yaml:168-171 types the entries as objects and
    # dataexport.yaml:255-257 leaves them untyped, so a row carrying
    # ``[{"name": "Cloud Storage"}]`` must not reject the page it sits in.
    other_categories: list[str | dict[str, Any]] | None = None
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
