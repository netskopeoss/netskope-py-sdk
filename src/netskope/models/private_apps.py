"""Models for the Netskope Private Apps (NPA) API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from netskope.models.common import NetskopeModel


class PrivateAppProtocol(StrEnum):
    """Supported private-app protocols."""

    TCP = "TCP"
    UDP = "UDP"
    TCP_UDP = "TCP/UDP"


class PrivateApp(NetskopeModel):
    """A Netskope Private Application (ZTNA).

    Example::

        for app in client.private_apps.list():
            print(f"{app.app_name} → {app.host}:{app.port}")
    """

    app_id: int | None = None
    app_name: str | None = None
    host: str | None = None
    port: str | None = None
    protocols: list[Any] | None = None
    publishers: list[dict[str, Any]] | None = None
    use_publisher_dns: bool | None = None
    clientless_access: bool | None = None
    trust_self_signed_certs: bool | None = None
    tags: list[dict[str, Any]] | None = Field(default_factory=list)
    service_publisher_assignment: str | None = None
    reachability: Any | None = None
