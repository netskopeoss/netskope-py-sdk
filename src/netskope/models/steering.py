"""Models for the Netskope Steering Configuration API."""

from __future__ import annotations

from typing import Any, Self

from pydantic import ConfigDict, Field, RootModel, field_validator, model_validator

from netskope.models._npa_requests import NpaRequest
from netskope.models.common import NetskopeModel


class IPSecTunnelPatch(NpaRequest):
    """Supported IPsec changes. The request key is enable, not response enabled.

    ``ipsec_tunnel_request_patch`` (``steering/ipsec.yaml:185-234``) declares
    ``bandwidth`` as a bare integer (``:187-188``) and ``encryption`` as a bare
    string (``:191-192``) with no enum on either, so a tenant on a tier outside
    the usual set is not shut out.
    :data:`~netskope.resources.steering.TUNNEL_BANDWIDTHS` and
    :data:`~netskope.resources.steering.TUNNEL_ENCRYPTIONS` name the values
    Netskope commonly provisions.
    """

    site: str | None = None
    pops: list[str] | None = Field(None, min_length=1)
    psk: str | None = Field(None, min_length=1, repr=False)
    srcidentity: str | None = None
    bandwidth: int | None = Field(None, gt=0)
    encryption: str | None = Field(None, min_length=1)
    enabled: bool | None = Field(None, alias="enable")
    vendor: str | None = None
    notes: str | None = None

    @field_validator("bandwidth", mode="before")
    @classmethod
    def integer_bandwidth(cls, value: Any) -> Any:
        if value is not None and type(value) is not int:
            raise ValueError("bandwidth must be an integer.")
        return value

    @model_validator(mode="after")
    def require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one IPsec tunnel field is required.")
        return self


class IPSecTunnelCreate(IPSecTunnelPatch):
    site: str
    pops: list[str] = Field(min_length=1)
    psk: str = Field(min_length=1, repr=False)
    srcidentity: str


class SteeringConfig(NetskopeModel):
    """Global steering configuration for NPA or publishers."""

    data: dict[str, Any] = Field(default_factory=dict)


class SteeringSettings(RootModel[dict[str, str | int]]):
    """Dynamic steering flags, whose wire values must be 0 or 1."""

    model_config = ConfigDict(frozen=True, strict=True, revalidate_instances="always")

    @field_validator("root", mode="before")
    @classmethod
    def _flags(cls, value: Any) -> Any:
        if not isinstance(value, dict) or not value:
            raise ValueError("Provide at least one steering setting.")
        if any(
            type(flag) not in (str, int) or flag not in (0, 1, "0", "1") for flag in value.values()
        ):
            raise ValueError("Steering setting values must be 0 or 1.")
        return value
