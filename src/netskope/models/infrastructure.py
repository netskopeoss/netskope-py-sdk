"""Models for the Netskope Infrastructure API (tunnels, PoPs, brokers)."""

from __future__ import annotations

from pydantic import Field

from netskope.models.common import NetskopeModel


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


class PublisherUpgradeProfile(NetskopeModel):
    """A publisher upgrade profile."""

    id: int | None = None
    name: str | None = None
    docker_tag: str | None = None
    frequency: str | None = None
    timezone: str | None = None
    enabled: bool | None = None
    release_type: str | None = None
    num_associated_publisher: int | None = None
    external_id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None
