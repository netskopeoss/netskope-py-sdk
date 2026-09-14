"""Models for the Netskope Device Management API."""

from __future__ import annotations

from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from netskope.models.common import NetskopeModel


class SupportedOperatingSystems(NetskopeModel):
    """The operating-system families returned by the client support service.

    ``AvailableOsFamily`` (devices/provisioner-core.yaml:320-333) declares no
    required properties, so a response that omits the key yields an empty list
    rather than a validation error.
    """

    available_os: list[str] = Field(default_factory=list)


_TagText = Annotated[str, Field(pattern=r"^[0-9a-zA-Z\-\s]+$")]


class _DeviceTagRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    @field_validator("name", "description", mode="before", check_fields=False)
    @classmethod
    def _reject_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("Omit unchanged fields; clearing a device-tag field is not supported.")
        return value


class DeviceTagCreate(_DeviceTagRequest):
    """Validated settings for creating a device tag.

    The gateway schema permits alphanumerics, hyphens, and whitespace.
    Description may be omitted, but explicit null and empty strings are not
    documented values. Serialize with exclude_unset=True to retain omission.
    """

    name: _TagText
    description: _TagText | None = None


class DeviceTagPatch(_DeviceTagRequest):
    """A nonempty partial tag update, with no inferred field-clearing operation."""

    name: _TagText | None = None
    description: _TagText | None = None

    @model_validator(mode="after")
    def _require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Nothing to update. Provide name and/or description.")
        return self


class DeviceTag(NetskopeModel):
    """A device tag from the device classification system.

    Matches the gateway ``TagResponseDto`` schema for device tags:
    ``id``, ``name``, and ``description``, plus ``device_count`` /
    ``device_classification_count`` which the API populates only for
    general (unfiltered) and name-filtered tag queries and returns as
    ``null`` otherwise.

    ``TagResponseDto`` declares ``id`` (devices/tag.yaml:738-741),
    ``device_count`` (:749-753) and ``device_classification_count`` (:754-758)
    as `type: number`, which admits a fraction, so none is narrowed to int.
    """

    id: int | float | None = None
    name: str | None = None
    description: str | None = None
    device_count: int | float | None = None
    device_classification_count: int | float | None = None


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
