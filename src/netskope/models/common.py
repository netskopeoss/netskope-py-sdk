"""Shared base models, mixins, and utility types used across all resources."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator
from pydantic import ValidationError as PydanticValidationError

T = TypeVar("T")

_DATETIME_ADAPTER: TypeAdapter[datetime] = TypeAdapter(datetime)


class NetskopeModel(BaseModel):
    """Base model for all Netskope API response objects.

    Configures Pydantic to:
    - Populate fields by attribute name *and* alias.
    - Preserve unknown fields (forward-compatible with new API fields).
    - Forbid mutation (responses are read-only value objects).
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
        frozen=True,
    )


class TimestampMixin(BaseModel):
    """Mixin that parses Unix-epoch timestamps into a UTC-aware :class:`datetime`."""

    timestamp: datetime | int | None = None

    @field_validator("timestamp", mode="before")
    @classmethod
    def _parse_epoch(cls, v: Any) -> Any:
        """Read epoch numbers and datetime strings; treat anything else as absent.

        Datasearch rows carry ``""`` for a missing timestamp, and these models
        decode whole pages, so one unreadable value must not reject the record
        it sits in (and with it the rest of the page).
        """
        if v is None or isinstance(v, datetime):
            return v
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            try:
                return datetime.fromtimestamp(v, tz=UTC)
            except (OverflowError, OSError, ValueError):
                return None
        if isinstance(v, str):
            try:
                return _DATETIME_ADAPTER.validate_python(v)
            except PydanticValidationError:
                return None
        return None

    @field_validator("timestamp", mode="after")
    @classmethod
    def _assume_utc(cls, v: datetime | int | None) -> datetime | int | None:
        """Netskope reports UTC, so a string without an offset is a UTC reading.

        Without this, epoch rows and string rows in the same page would produce
        aware and naive values that cannot be compared with each other.
        """
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


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
