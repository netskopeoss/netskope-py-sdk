"""Models for the Netskope Steering Configuration API."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from netskope.models.common import NetskopeModel


class SteeringConfig(NetskopeModel):
    """Global steering configuration for NPA or publishers."""

    data: dict[str, Any] = Field(default_factory=dict)
