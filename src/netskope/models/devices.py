"""Models for the Netskope Device Management API."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from netskope.models.common import NetskopeModel


class DeviceTag(NetskopeModel):
    """A device tag from the device classification system.

    Matches the gateway ``TagResponseDto`` schema
    (``api-gateway-endpoints/production/endpoints/devices/tag.yaml``):
    ``id``, ``name``, and ``description``, plus ``device_count`` /
    ``device_classification_count`` which the API populates only for
    general (unfiltered) and name-filtered tag queries and returns as
    ``null`` otherwise.
    """

    id: int | None = None
    name: str | None = None
    description: str | None = None
    device_count: int | None = None
    device_classification_count: int | None = None


class Device(NetskopeModel):
    """A managed device enrolled in the tenant (Netskope Client endpoint).

    The devices API nests most details under an ``attributes`` object with
    a ``host_info`` sub-object; the fields declared here cover the common
    top-level attributes, and ``extra="allow"`` preserves everything else.
    """

    device_id: str | None = None
    host_name: str | None = Field(default=None, alias="hostname")
    os: str | None = None
    os_version: str | None = None
    client_version: str | None = None
    last_event: dict[str, Any] | None = None
    users: list[dict[str, Any]] = Field(default_factory=list)
