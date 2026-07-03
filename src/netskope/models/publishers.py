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


class PublisherAlertEventType(StrEnum):
    """Event types that can trigger publisher alert notifications."""

    UPGRADE_WILL_START = "UPGRADE_WILL_START"
    UPGRADE_STARTED = "UPGRADE_STARTED"
    UPGRADE_SUCCEEDED = "UPGRADE_SUCCEEDED"
    UPGRADE_FAILED = "UPGRADE_FAILED"
    CONNECTION_FAILED = "CONNECTION_FAILED"


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


class PublisherRelease(NetskopeModel):
    """An available publisher software release.

    Example::

        for release in client.publishers.list_releases():
            print(f"{release.version} ({release.release_type})")
    """

    version: str | None = None
    docker_tag: str | None = None
    release_type: str | None = Field(None, alias="name")
    is_recommended: bool | None = None


class PublisherAlertsConfiguration(NetskopeModel):
    """Alert notification configuration for publishers.

    The API uses camelCase keys (``adminUsers``, ``eventTypes``); this model
    exposes them under Pythonic names via field aliases.
    """

    admin_users: list[str] = Field(default_factory=list, alias="adminUsers")
    event_types: list[str] = Field(default_factory=list, alias="eventTypes")
