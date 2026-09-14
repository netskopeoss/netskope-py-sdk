"""Typed IPS configuration and allowlist contracts."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from netskope.models.administration import AdminRequest
from netskope.models.common import NetskopeModel


class IpsAllowlistPatch(AdminRequest):
    """Replace supplied allowlist fields. Omission preserves a field; [] clears it."""

    src_ids: list[str] | None = None
    domain: list[str] | None = None
    dst_ids: list[str] | None = None

    @model_validator(mode="after")
    def _require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Supply source IDs, destination IDs, or domains.")
        return self


class IpsStatus(NetskopeModel):
    web: bool | None = None
    nonweb: bool | None = None
    npa: bool | None = None


class IpsAllowlist(NetskopeModel):
    """Network-location IDs and domains, not literal IP-address entries."""

    src_ids: list[str] = Field(default_factory=list)
    domain: list[str] = Field(default_factory=list)
    dst_ids: list[str] = Field(default_factory=list)
