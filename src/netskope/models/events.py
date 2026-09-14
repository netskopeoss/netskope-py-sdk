"""Models for the Netskope Events API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import AliasChoices, AliasPath, Field, field_validator

from netskope.models.common import NetskopeModel, TimestampMixin


class EventType(StrEnum):
    """Supported event data-search types."""

    ALERT = "alert"
    APPLICATION = "application"
    NETWORK = "network"
    PAGE = "page"
    INCIDENT = "incident"
    AUDIT = "audit"
    INFRASTRUCTURE = "infrastructure"
    CLIENT_STATUS = "clientstatus"
    ENDPOINT_DLP = "epdlp"
    TRANSACTION = "transaction"


class Event(NetskopeModel, TimestampMixin):
    """A generic Netskope event (base class).

    The Netskope events API returns a wide variety of fields depending on
    the event type.  This model captures common fields; type-specific
    subclasses add further structure.
    """

    id: str | None = Field(None, alias="_id")

    @field_validator("id", mode="before")
    @classmethod
    def _string_identity(cls, v: Any) -> Any:
        """A declared-numeric record id must not reject the page it arrives in.

        search_app.yaml:123-125 types the record's `id` as `number` (example
        29) while search_incident.yaml:224-226 types the same-named field as
        `string`. ``populate_by_name`` makes `id` a second accepted input key
        beside the `_id` alias, and pydantic never coerces int to str, so the
        stringifying happens here instead.
        """
        return str(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v

    # No search_*.yaml record declares `event_type`; every one of them names the
    # field `type` (search_alert.yaml:223-225, search_app.yaml:251-253,
    # search_network.yaml:157-159, search_page.yaml:211-213,
    # search_incident.yaml:387-389). dataexport.yaml:141-142 spells it
    # `event_type`, so both resolve here.
    event_type: str | None = Field(None, validation_alias=AliasChoices("event_type", "type"))
    user: str | None = None
    app: str | None = None
    activity: str | None = None
    action: str | None = None
    site: str | int | None = None
    category: str | None = None
    severity: str | int | None = Field(None, alias="severity_level")
    object_name: str | None = Field(None, alias="object")
    # The matched policy is `policy` in search_app.yaml:169,
    # search_network.yaml:94 and search_alert.yaml:175; only
    # search_epdlp.yaml:88 spells it `policy_name`, so both resolve here.
    policy_name: str | None = Field(None, validation_alias=AliasChoices("policy_name", "policy"))
    traffic_type: str | None = None
    access_method: str | None = None
    src_country: str | None = None
    dst_country: str | None = None
    src_location: str | None = None
    dst_location: str | None = None
    # search_incident.yaml:265-267 spells the ingestion time
    # `ns_insertion_epoch_timestamp` and admits fractional numbers.
    insertion_epoch_timestamp: int | float | None = Field(
        None,
        validation_alias=AliasChoices("insertion_epoch_timestamp", "ns_insertion_epoch_timestamp"),
    )


class NetworkEvent(Event):
    """A network-layer event with additional networking fields."""

    src_ip: str | None = Field(None, validation_alias=AliasChoices("srcip", "src_ip"))
    dst_ip: str | None = Field(None, validation_alias=AliasChoices("dstip", "dst_ip"))
    # search_network.yaml:139-141, :73-75 and :88-90 declare srcport, dstport
    # and numbytes as `type: number`, which admits a fraction, so none of the
    # three is narrowed to int.
    src_port: int | float | None = Field(None, validation_alias=AliasChoices("srcport", "src_port"))
    dst_port: int | float | None = Field(None, validation_alias=AliasChoices("dstport", "dst_port"))
    # search_network.yaml:82-84 names the transport protocol ip_protocol.
    protocol: str | None = Field(None, validation_alias=AliasChoices("protocol", "ip_protocol"))
    num_bytes: int | float | None = Field(None, alias="numbytes")
    domain: str | None = None


class PageEvent(Event):
    """A web-page access event."""

    url: str | None = None
    domain: str | None = None
    page_id: int | None = None
    page_duration: float | None = None
    referer: str | None = None
    browser: str | None = None
    os: str | None = None
    device: str | None = None


class AuditEvent(Event):
    """An admin audit-trail event."""

    audit_log_event: str | None = None
    audit_category: str | None = None
    supporting_data: dict[str, Any] | None = None
    organization_unit: str | None = None


class ClientStatusEvent(Event):
    """One client-status record.

    search_clientstatus.yaml:37-196 nests the host and last-event fields:
    ``hostname`` and ``os`` live under ``host_info`` (:90-92, :110-112) and
    ``status`` under ``last_seen_device_event`` (:143-145). The flat names stay
    accepted so a tenant that already returns them keeps working.

    The record declares no top-level ``timestamp``. Its ``ts`` (:157-159) and
    ``last_event_timestamp`` (:125-127) have no stated unit, so both remain raw
    numbers. The inherited ``timestamp`` field retains its compatibility behavior.
    """

    ts: int | None = None
    last_event_timestamp: int | float | None = None
    """The declared ``last_event_timestamp`` verbatim; its unit is unstated."""

    # Client identity and version fields arrive as numbers on some tenants.
    device_id: str | int | None = None
    hostname: str | int | None = Field(
        None, validation_alias=AliasChoices(AliasPath("host_info", "hostname"), "hostname")
    )
    client_version: str | int | None = None
    os: str | int | None = Field(
        None, validation_alias=AliasChoices(AliasPath("host_info", "os"), "os")
    )
    status: str | int | None = Field(
        None,
        validation_alias=AliasChoices(AliasPath("last_seen_device_event", "status"), "status"),
    )


class IncidentEvent(Event):
    incident_id: str | int | float | None = None
    status: str | int | None = None
    assignee: str | int | None = None
    dlp_profile: str | int | None = None
    dlp_rule: str | int | None = None


class EventQueryCapabilities(NetskopeModel):
    """Verified one-page and scan capabilities for an event category.

    ``jql`` covers both filter expressions and lookup by ``_id``. Every record
    endpoint declares a ``query`` parameter — audit and infrastructure included
    (events/audit.yaml:12-18, events/infrastructure.yaml:12-18) — so it is
    ``True`` throughout and defaults to supported. What separates those two is
    ``projection``, ``grouping``, and ``ordering``, which they do not declare.
    """

    page_limit: int
    scannable: bool
    projection: bool
    grouping: bool
    ordering: bool
    jql: bool = True


class TransactionMetrics(NetskopeModel):
    """Hourly PubSub backlog metrics, keyed by partition inside each metric."""

    backlog_message_count: dict[str, Any] = Field(
        default_factory=dict, alias="subscription/backlog_message_count"
    )
    oldest_unacked_message_age: dict[str, Any] = Field(
        default_factory=dict, alias="subscription/oldest_unacked_message_age"
    )
