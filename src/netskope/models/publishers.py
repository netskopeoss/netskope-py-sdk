"""Models for the Netskope Publishers API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

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
    """Publisher connection status.

    The gateway spells the disconnected state ``"not registered"`` — with a
    space — in every schema that declares it (``npa_publishers.yaml:827-832``
    list, ``:504-509`` single, ``:225-230`` bulk, ``npa_generic.yaml:152-156``).
    """

    CONNECTED = "connected"
    NOT_REGISTERED = "not registered"


class PublisherAlertEventType(StrEnum):
    """Event types that can trigger publisher alert notifications."""

    UPGRADE_WILL_START = "UPGRADE_WILL_START"
    UPGRADE_STARTED = "UPGRADE_STARTED"
    UPGRADE_SUCCEEDED = "UPGRADE_SUCCEEDED"
    UPGRADE_FAILED = "UPGRADE_FAILED"
    CONNECTION_FAILED = "CONNECTION_FAILED"


class Publisher(NetskopeModel):
    """A Netskope Publisher (private-access gateway).

    The list envelope names the record ``publisher_id`` / ``publisher_name``
    (``npa_publishers.yaml:812-818``) while every single-object envelope names
    it ``id`` / ``name`` (``:477-496`` for get/create/update, ``:198``/``:214``
    for the bulk item, ``npa_upgrade_profiles.yaml:88``/``:95``).  Both spellings
    populate the same two attributes, so a created publisher carries its id.

    Example::

        for pub in client.publishers.list():
            print(f"{pub.publisher_name} — {pub.status}")
    """

    publisher_id: int | None = Field(None, validation_alias=AliasChoices("publisher_id", "id"))
    publisher_name: str | None = Field(
        None, validation_alias=AliasChoices("publisher_name", "name")
    )
    status: str | None = None
    upgrade_request: bool | None = None
    lbrokerconnect: bool | None = None
    apps_count: int | None = None
    common_name: str | None = None
    registered: bool | None = None
    assessment: dict[str, Any] | None = None
    tags: list[dict[str, Any]] = Field(default_factory=list)


class PublisherApp(NetskopeModel):
    """A private application associated with a publisher.

    ``publishers_private_apps_response.data[]`` (``npa_publishers.yaml:3-94``)
    names the record ``id`` (``:33``), ``name`` (``:40``) and
    ``private_app_protocol`` (``:44``); those spellings populate ``app_id``,
    ``app_name`` and ``protocol``.
    """

    app_id: int | None = Field(None, validation_alias=AliasChoices("app_id", "id"))
    app_name: str | None = Field(None, validation_alias=AliasChoices("app_name", "name"))
    host: str | None = None
    protocol: str | None = Field(
        None, validation_alias=AliasChoices("private_app_protocol", "protocol")
    )
    protocols: list[Any] | None = None


class PublisherActionResult(NetskopeModel):
    """The acknowledgment returned by a bulk publisher action."""

    status: str | None = None
    message: str | None = None


class PublisherRelease(NetskopeModel):
    """An available publisher software release.

    ``release_item`` (``npa_publishers.yaml:950-961``) declares exactly
    ``docker_tag``, ``name`` and ``version``; ``name`` is the release channel.

    Example::

        for release in client.publishers.list_releases():
            print(f"{release.version} ({release.release_type})")
    """

    version: str | None = None
    docker_tag: str | None = None
    release_type: str | None = Field(None, alias="name")


class PublisherAlertsConfigurationPatch(NpaRequest):
    """Explicit alert configuration changes; omitted fields are not sent.

    ``publishers_alert_put_request`` (``npa_publishers.yaml:589-629``) declares
    ``adminUsers``, ``eventTypes`` and ``selectedUsers`` required, and bounds
    ``eventTypes`` to 1..5 entries (``:624-625``).  This model enforces the
    bound and can send all three keys; it still permits a partial body, which
    the gateway may reject.
    """

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
    ) = Field(None, alias="eventTypes", min_length=1, max_length=5)
    selected_users: str | None = Field(None, alias="selectedUsers")

    @model_validator(mode="after")
    def require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one alert configuration field is required.")
        return self


class PublisherAlertsConfiguration(NetskopeModel):
    """Alert notification configuration for publishers.

    The API uses camelCase keys (``adminUsers``, ``eventTypes``,
    ``selectedUsers``); this model exposes them under Pythonic names via field
    aliases.  ``selectedUsers`` is a comma-joined string
    (``npa_publishers.yaml:580-582``).
    """

    admin_users: list[str] = Field(default_factory=list, alias="adminUsers")
    event_types: list[str] = Field(default_factory=list, alias="eventTypes")
    selected_users: str | None = Field(None, alias="selectedUsers")
