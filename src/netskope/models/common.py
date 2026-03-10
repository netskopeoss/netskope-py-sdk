"""Shared base models, mixins, and utility types used across all resources."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


class NetskopeModel(BaseModel):
    """Base model for all Netskope API response objects.

    Configures Pydantic to:
    - Populate fields by attribute name *and* alias.
    - Ignore unknown fields (forward-compatible with new API fields).
    - Forbid mutation (responses are read-only value objects).
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
        frozen=True,
    )


class TimestampMixin(BaseModel):
    """Mixin that parses Unix-epoch timestamps into :class:`datetime`."""

    timestamp: datetime | int | None = None

    @field_validator("timestamp", mode="before")
    @classmethod
    def _parse_epoch(cls, v: Any) -> datetime | None:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v, tz=UTC)
        if isinstance(v, datetime):
            return v
        return None


class PaginatedResponse(BaseModel, Generic[T]):
    """Envelope for paginated API responses."""

    data: list[T] = Field(default_factory=list)
    status: dict[str, Any] = Field(default_factory=dict)

    @property
    def total(self) -> int | None:
        return self.status.get("total")

    @property
    def count(self) -> int:
        return len(self.data)
