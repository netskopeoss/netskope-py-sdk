"""Models for the Netskope Events API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

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
    event_type: str | None = None
    user: str | None = None
    app: str | None = None
    activity: str | None = None
    action: str | None = None
    site: str | None = None
    category: str | None = None
    severity: str | None = Field(None, alias="severity_level")
    object_name: str | None = Field(None, alias="object")
    policy_name: str | None = None
    traffic_type: str | None = None
    access_method: str | None = None
    src_country: str | None = None
    dst_country: str | None = None
    src_location: str | None = None
    dst_location: str | None = None
    insertion_epoch_timestamp: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict, exclude=True)


class NetworkEvent(Event):
    """A network-layer event with additional networking fields."""

    src_ip: str | None = None
    dst_ip: str | None = None
    src_port: int | None = None
    dst_port: int | None = None
    protocol: str | None = None
    num_bytes: int | None = Field(None, alias="numbytes")
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
