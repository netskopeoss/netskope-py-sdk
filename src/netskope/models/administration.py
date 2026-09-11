"""Shared request rules and acknowledgments for administrative operations."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from netskope.models.common import NetskopeModel


class AdminRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        populate_by_name=True,
        revalidate_instances="always",
    )

    @model_validator(mode="after")
    def _omit_nulls(self) -> Self:
        if any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Omit optional fields instead of supplying null.")
        return self


class OperationStatus(NetskopeModel):
    """A write acknowledgment, without implying a follow-up detail read."""

    status: str | None = None
