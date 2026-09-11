"""Typed posture records, with tenant-specific fields retained as extras."""

from __future__ import annotations

from pydantic import Field

from netskope.models.common import NetskopeModel


class SpmApplication(NetskopeModel):
    name: str
    posture_score: int | None = None
    app_suite: str | None = None
    instance_name: str | None = None


class SpmInventoryRecord(NetskopeModel):
    resource_id: str | None = None
    resource_name: str | None = None
    resource_type: str | None = None
    app_name: str | None = None
    app_suite: str | None = None
    instance_id: str | None = None
    instance_name: str | None = None


class SpmPostureScore(NetskopeModel):
    posture_score: int


class SpmPolicyRule(NetskopeModel):
    name: str
    id: str | int | None = None
    severity: str | None = None
    enabled: bool | None = None


class SpmInstanceScore(NetskopeModel):
    id: str
    posture_score: int


class SpmTrendSample(NetskopeModel):
    timestamp: int
    posture_confidence_index: int | None = None
    posture_scores: list[SpmInstanceScore] = Field(default_factory=list)


class SpmTrends(NetskopeModel):
    samples: list[SpmTrendSample] = Field(default_factory=list)
    by_trajectory: dict[str, list[str]] = Field(default_factory=dict)


class SpmRecentChanges(NetskopeModel):
    trends: SpmTrends | None = None
    third_party_apps: dict[str, dict[str, int]] = Field(default_factory=dict)
    findings: dict[str, dict[str, int]] = Field(default_factory=dict)
