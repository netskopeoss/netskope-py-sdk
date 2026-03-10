"""Models for the Netskope Publishers API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from netskope.models.common import NetskopeModel


class PublisherStatus(StrEnum):
    """Publisher connection status."""

    CONNECTED = "connected"
    NOT_CONNECTED = "not_connected"


class Publisher(NetskopeModel):
    """A Netskope Publisher (private-access gateway).

    Example::

        for pub in client.publishers.list():
            print(f"{pub.publisher_name} — {pub.status}")
    """

    publisher_id: int | None = None
    publisher_name: str | None = None
    status: str | None = None
    publisher_upgrade_request: bool | None = None
    lbroker_proxy: str | None = None
    apps_count: int | None = None
    common_name: str | None = None
    registered: bool | None = None
    assessment: dict[str, Any] | None = None
    sticky_ip_enabled: bool | None = None
    tags: list[dict[str, Any]] = Field(default_factory=list)
