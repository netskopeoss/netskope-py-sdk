"""Typed posture records, with tenant-specific fields retained as extras.

Field sets follow the SPM gateway contract:

* ``spm/inventory.yaml:286-386`` — ``ResourceAggregationRequest`` /
  ``ResourceAggregationResponse`` (``POST /inventory/getresources``).
* ``spm/saas_posture_score.yaml:26-231`` — ``GetPostureScoresRequestBody`` and
  ``PostureScoreResponse`` (``POST /results/getposturescores``).
* ``spm/policy.yaml:2833`` — ``RulesSummaryList`` / ``RuleSummary``
  (``GET /rules/list``).
* ``spm/apps.yaml:616-1722`` — ``RecentChangesRequest`` /
  ``RecentChangesResponse`` (``POST /apps/recentchanges/getstats``).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from netskope.models.common import NetskopeModel


class SpmInventoryRecord(NetskopeModel):
    """One row of ``ResourceAggregationResponse.data`` (inventory.yaml:389-452).

    The response items are declared as bare objects whose keys depend on the
    request's ``fields``/``group_by``, so every field here is optional.
    """

    resource_id: str | None = None
    resource_name: str | None = None
    resource_type: str | None = None
    parent_res_type: str | None = None
    app_name: str | None = None
    app_suite: str | None = None
    instance_id: str | None = None
    instance_name: str | None = None
    netskope_instance_name: str | None = None
    region_id: str | None = None
    region_name: str | None = None
    creation_time: datetime | None = None
    last_updated_time: datetime | None = None


class SpmApplication(SpmInventoryRecord):
    """An inventory row grouped by instance or resource type, with rule counters.

    The counter names are the ones ``ResourceAggregationRequest.fields``
    documents for ``group_by`` ``instance_name`` and ``resource_type``
    (inventory.yaml:286-299).
    """

    total_resources: int | None = None
    total_checked_rules: int | None = None
    passed_rules: int | None = None
    failed_rules: int | None = None
    failed_muted_rules: int | None = None
    failed_critical_rules: int | None = None
    failed_high_rules: int | None = None
    failed_medium_rules: int | None = None
    failed_low_rules: int | None = None
    unknown_rules: int | None = None


class SpmPostureScoreData(NetskopeModel):
    """``PostureScoreData`` (saas_posture_score.yaml:86-104)."""

    posture_confidence_index: int | None = None
    posture_confidence_level: str | None = None
    posture_risk_score: int | None = None


class SpmPostureApp(NetskopeModel):
    name: str | None = None
    score: SpmPostureScoreData | None = None


class SpmPostureInstance(NetskopeModel):
    name: str | None = None
    score: SpmPostureScoreData | None = None
    apps: list[SpmPostureApp] = Field(default_factory=list)


class SpmPostureAppSuite(NetskopeModel):
    name: str | None = None
    score: SpmPostureScoreData | None = None
    instances: list[SpmPostureInstance] = Field(default_factory=list)


class SpmPostureScore(NetskopeModel):
    """``PostureScoreResponse`` (saas_posture_score.yaml:105-142)."""

    score: SpmPostureScoreData | None = None
    app_suites: list[SpmPostureAppSuite] = Field(default_factory=list)


class SpmSubCategory(NetskopeModel):
    id: str | int | None = None
    name: str | None = None


class SpmPolicyRule(NetskopeModel):
    """``RuleSummary`` (policy.yaml, ``GET /rules/list`` 200 body).

    The schema declares no required properties, so a sparse rule row still
    decodes.
    """

    id: str | int | None = None
    name: str | None = None
    appsuite: str | None = None
    description: str | None = None
    ngl: str | None = None
    type: str | None = None
    subcategory_list: list[SpmSubCategory] = Field(default_factory=list)


class SpmInstanceScore(NetskopeModel):
    """One ``trends.samples[].posture_scores[]`` entry (spm/apps.yaml:678-690).

    ``RecentChangesResponse`` declares no ``required`` list at any level, so a
    sample that carries only one of the two keys still decodes.
    """

    id: str | None = None
    posture_score: int | None = None


class SpmTrendSample(NetskopeModel):
    """One ``trends.samples[]`` entry (spm/apps.yaml:656-690), nothing required."""

    timestamp: int | None = None
    posture_confidence_index: int | None = None
    posture_scores: list[SpmInstanceScore] = Field(default_factory=list)


class SpmTrends(NetskopeModel):
    samples: list[SpmTrendSample] = Field(default_factory=list)
    by_trajectory: dict[str, list[str]] = Field(default_factory=dict)


class SpmRecentChanges(NetskopeModel):
    trends: SpmTrends | None = None
    third_party_apps: dict[str, dict[str, int]] = Field(default_factory=dict)
    findings: dict[str, dict[str, int]] = Field(default_factory=dict)
