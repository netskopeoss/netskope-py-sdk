"""Models for the Netskope Infrastructure API (tunnels, PoPs, brokers)."""

from __future__ import annotations

from enum import StrEnum
from ipaddress import IPv4Address
from typing import Any, Literal, Self

from pydantic import Field, field_validator, model_validator

from netskope.models._npa_requests import NpaRequest
from netskope.models.common import NetskopeModel


class ReleaseType(StrEnum):
    """Publisher release channel for upgrade profiles."""

    BETA = "Beta"
    LATEST = "Latest"
    LATEST_1 = "Latest-1"
    LATEST_2 = "Latest-2"


class BrokerPublicIpAccess(StrEnum):
    """Access policy for reaching a local broker via its public IP."""

    NONE = "NONE"
    OFF_PREM = "OFF_PREM"
    ON_PREM = "ON_PREM"
    ON_OFF_PREM = "ON_OFF_PREM"


class Pop(NetskopeModel):
    """A Netskope Point of Presence (PoP)."""

    name: str | None = None
    region: str | None = None
    country: str | None = None
    ip_addresses: list[str] = Field(default_factory=list)
    gateway: str | None = None


class IPSecTunnel(NetskopeModel):
    """An IPSec VPN tunnel."""

    id: int | None = None
    name: str | None = None
    source_ip: str | None = None
    destination_ip: str | None = None
    status: str | None = None
    site: str | None = None
    pop: str | None = None
    proto: str | None = None
    bandwidth: int | None = None


class LocalBroker(NetskopeModel):
    """A Local Broker for publisher connectivity."""

    id: int | None = None
    name: str | None = None
    status: str | None = None
    publisher_id: int | None = None
    common_name: str | None = None
    registered: bool | None = None
    city_name: str | None = None
    region_name: str | None = None
    country_name: str | None = None
    country_code: str | None = None
    location_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    discovered_public_ip: str | None = None
    discovered_private_ip: str | None = None
    custom_public_ip: str | None = None
    custom_private_ip: str | None = None
    labels: list[dict[str, Any]] = Field(default_factory=list)


class LocalBrokerConfig(NetskopeModel):
    """Tenant-wide local broker configuration."""

    hostname: str | None = None


class PublisherUpgradeProfile(NetskopeModel):
    """A publisher upgrade profile."""

    id: int | None = None
    name: str | None = None
    docker_tag: str | None = None
    frequency: str | None = None
    timezone: str | None = None
    timezone_id: int | None = None
    enabled: bool | None = None
    release_type: str | None = None
    num_associated_publisher: int | None = None
    external_id: int | None = None
    next_update_time: int | None = None
    upgrading_stage: int | None = None
    will_start: bool | None = None
    created_at: str | None = None
    updated_at: str | None = None


class LocalBrokerPatch(NpaRequest):
    """Local-broker changes, using the gateway's location field names."""

    city: str | None = Field(None, alias="city_name")
    region: str | None = Field(None, alias="region_name")
    country: str | None = Field(None, alias="country_name")
    country_code: str | None = None
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    custom_public_ip: str | None = None
    custom_private_ip: str | None = None
    label_ids: list[str] | None = None
    access_via_public_ip: Literal["NONE", "OFF_PREM", "ON_PREM", "ON_OFF_PREM"] | None = None

    @field_validator("custom_public_ip", "custom_private_ip")
    @classmethod
    def _ipv4(cls, value: str | None) -> str | None:
        if value is not None:
            IPv4Address(value)
        return value

    @model_validator(mode="after")
    def _not_empty(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Provide at least one local-broker field.")
        return self


class LocalBrokerCreate(LocalBrokerPatch):
    name: str


class UpgradeProfileCreate(NpaRequest):
    name: str
    docker_tag: str
    frequency: str
    timezone: str
    release_type: Literal["Beta", "Latest", "Latest-1", "Latest-2"]
    enabled: bool
    timezone_id: int | None = None


class UpgradeProfileUpdate(UpgradeProfileCreate):
    """A complete replacement profile, without an implicit pre-write read."""

    id: int


class UpgradeProfileAssignment(NetskopeModel):
    status: str | None = None
    message: str | None = None
    updated: bool | None = None
