"""Models for the Netskope Infrastructure API (tunnels, PoPs, brokers)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

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
