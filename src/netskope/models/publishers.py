"""Models for the Netskope Publishers API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from netskope.models._npa_requests import NpaRequest
from netskope.models.common import NetskopeModel


class PublisherCreate(BaseModel):
    """The modeled settings accepted when creating a publisher.

    Resource methods accept additional settings through ``extra_fields``.
    """

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    name: str
    lbroker_connect: bool = False


class PublisherUpdate(BaseModel):
    """A partial publisher update; omitted fields are not sent."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    name: str | None = None


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


class PublisherApp(NetskopeModel):
    """A private application associated with a publisher."""

    app_id: int | None = None
    app_name: str | None = None
    host: str | None = None
    protocol: str | None = None


class PublisherActionResult(NetskopeModel):
    """The acknowledgment returned by a bulk publisher action."""

    status: str | None = None
    message: str | None = None


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


class PublisherAlertsConfigurationPatch(NpaRequest):
    """Explicit alert configuration changes; omitted fields are not sent."""

    admin_users: list[str] | None = Field(None, alias="adminUsers")
    event_types: (
        list[
            Literal[
                "UPGRADE_WILL_START",
                "UPGRADE_STARTED",
                "UPGRADE_SUCCEEDED",
                "UPGRADE_FAILED",
                "CONNECTION_FAILED",
            ]
        ]
        | None
    ) = Field(None, alias="eventTypes")

    @model_validator(mode="after")
    def require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one alert configuration field is required.")
        return self


class PublisherAlertsConfiguration(NetskopeModel):
    """Alert notification configuration for publishers.

    The API uses camelCase keys (``adminUsers``, ``eventTypes``); this model
    exposes them under Pythonic names via field aliases.
    """

    admin_users: list[str] = Field(default_factory=list, alias="adminUsers")
    event_types: list[str] = Field(default_factory=list, alias="eventTypes")
