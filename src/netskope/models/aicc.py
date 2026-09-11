"""AI Command Center query contracts and forward-compatible response models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, JsonValue, model_validator

from netskope.models.common import NetskopeModel


class AiccQuery(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, revalidate_instances="always"
    )


def _check_window(start_time: str, end_time: str) -> None:
    start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise ValueError("AICC requires an increasing, timezone-aware reporting window.")


class AiccWindow(AiccQuery):
    start_time: str
    end_time: str

    @model_validator(mode="after")
    def _ordered_window(self) -> Self:
        _check_window(self.start_time, self.end_time)
        return self


class AiccOptionalWindow(AiccQuery):
    """A reporting window for the operations whose gateway bounds are optional."""

    start_time: str | None = None
    end_time: str | None = None

    @model_validator(mode="after")
    def _ordered_window(self) -> Self:
        if self.start_time is not None and self.end_time is not None:
            _check_window(self.start_time, self.end_time)
        return self


class AiccSort(AiccQuery):
    field: str = Field(min_length=1)
    order: Literal["asc", "desc"] = "desc"


class AiccInventoryQuery(AiccWindow):
    search: str | None = Field(None, max_length=200)
    sort: AiccSort | None = None
    active_only: bool | None = None
    first_seen_after: str | None = None


class AiccApplicationQuery(AiccInventoryQuery):
    category: list[str] | None = Field(None, min_length=1)
    status: list[str] | None = Field(None, min_length=1)
    ccl: list[str] | None = Field(None, min_length=1)
    risk_level: list[str] | None = Field(
        None, min_length=1, serialization_alias="reconciled_risk_level"
    )
    """Sent as the API's ``reconciled_risk_level`` query parameter."""


class AiccMcpQuery(AiccInventoryQuery):
    category: list[str] | None = Field(None, min_length=1)
    ccl: list[str] | None = Field(None, min_length=1)
    risk_level: list[str] | None = Field(
        None, min_length=1, serialization_alias="reconciled_risk_level"
    )
    """Sent as the API's ``reconciled_risk_level`` query parameter."""


class AiccIdentityQuery(AiccInventoryQuery):
    type: Literal["user", "unknown"] | None = None
    user_group: list[str] | None = Field(None, min_length=1)
    ou: list[str] | None = Field(None, min_length=1)
    activity_level: list[str] | None = Field(None, min_length=1)
    risk_level: list[str] | None = Field(
        None, min_length=1, serialization_alias="reconciled_risk_level"
    )
    """Sent as the API's ``reconciled_risk_level`` query parameter."""


class AiccModelQuery(AiccInventoryQuery):
    deployment: list[str] | None = Field(None, min_length=1)
    provider: list[str] | None = Field(None, min_length=1)


class AiccAgentQuery(AiccInventoryQuery):
    category: list[str] | None = Field(None, min_length=1)
    framework: list[str] | None = Field(None, min_length=1)


class AiccRelatedQuery(AiccWindow):
    search: str | None = Field(None, max_length=256)
    sort_by: str | None = None
    sort_dir: Literal["asc", "desc"] | None = None


class AiccDeploymentQuery(AiccWindow):
    type: str = Field(min_length=1)
    search: str | None = Field(None, max_length=256)


class AiccExtensionQuery(AiccWindow):
    type: Literal["browser_extension", "editor_extension", "desktop_extension"] | None = None


class AiccExtensionRelatedQuery(AiccRelatedQuery):
    type: Literal["browser_extension", "editor_extension", "desktop_extension"] | None = None


class AiccViolationQuery(AiccWindow):
    status: Literal["current", "dismissed"] | None = None


class AiccProtectionQuery(AiccWindow):
    severity: list[Literal["critical", "high", "medium", "low"]] | None = Field(None, min_length=1)
    object_type: list[str] | None = Field(None, min_length=1)
    search: str | None = None
    user: str | None = None
    include_total: bool | None = None


class AiccTrendQuery(AiccWindow):
    timezone: str = "UTC"


class AiccCountQuery(AiccTrendQuery):
    type: Literal["identities", "assets", "alerts"]


class AiccSumQuery(AiccTrendQuery):
    type: Literal["traffic", "sessions"]


class AiccEntityCountQuery(AiccWindow):
    active_only: bool | None = None


class AiccBreakdownQuery(AiccWindow):
    dimension: str
    metric: str | None = None
    category: list[str] | None = Field(None, min_length=1)
    status: list[str] | None = Field(None, min_length=1)
    ccl: list[str] | None = Field(None, min_length=1)
    reconciled_risk_level: list[str] | None = Field(None, min_length=1)
    auth_method: list[str] | None = Field(None, min_length=1)
    user_group: list[str] | None = Field(None, min_length=1)
    ou: list[str] | None = Field(None, min_length=1)
    activity_level: list[str] | None = Field(None, min_length=1)
    type: str | None = None
    active_only: bool | None = None


class AiccAlertQuery(AiccWindow):
    detection: str | None = None
    asset: Literal["AI App", "MCP Server"] | None = None


class AiccTimeRange(NetskopeModel):
    start: datetime = Field(validation_alias=AliasChoices("start", "start_time"))
    end: datetime = Field(validation_alias=AliasChoices("end", "end_time"))


class AiccRiskAssessment(NetskopeModel):
    risk_score: int | None = None
    risk_level: str | None = None
    reconciled_risk_level: str | None = None
    verdict: str | None = None
    verdict_confidence: str | None = None


class AiccFootprintInstance(NetskopeModel):
    type: str
    count: int
    display_label: str | None = None
    unit: str | None = None
    detail: str | None = None


class AiccFootprint(NetskopeModel):
    types: list[str]
    instances: list[AiccFootprintInstance]


class AiccUsage(NetskopeModel):
    bytes: int | None = None
    uploaded_bytes: int | None = None
    downloaded_bytes: int | None = None
    blocked_uploaded_bytes: int | None = None
    blocked_downloaded_bytes: int | None = None
    sessions: int | None = None
    identities: int | None = None
    transactions: int | None = None
    events: int | None = None
    users: int | None = None
    apps: int | None = None
    agents: int | None = None
    mcp_servers: int | None = None


class AiccApplication(AiccUsage):
    name: str
    display_name: str | None = None
    category: str | None = None
    display_category: str | None = None
    status: str | None = None
    ccl: str | None = None
    cci_score: int | None = None
    risk_assessment: AiccRiskAssessment | None = None
    footprint: AiccFootprint | None = None
    known_users: int | None = None
    unknown_users: int | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class AiccMcpServer(AiccUsage):
    name: str
    category: str | None = None
    ccl: str | None = None
    cci_score: int | None = None
    mcp_classification: str | None = None
    risk_assessment: AiccRiskAssessment | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class AiccIdentity(AiccUsage):
    user_id: str
    type: str
    display_name: str | None = None
    last_hostname: str | None = None
    user_groups: list[str] | None = None
    groups_count: int | None = None
    ou: str | None = None
    activity_level: str | None = None
    risk_assessment: AiccRiskAssessment | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class AiccModel(AiccUsage):
    name: str
    display_name: str | None = None
    provider: str | None = None
    footprint: AiccFootprint | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class AiccAgent(AiccUsage):
    name: str
    display_name: str | None = None
    resource_subtype: str | None = None
    category: str | None = None
    framework: str | None = None
    footprint: AiccFootprint | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class AiccAssociatedIdentity(AiccUsage):
    name: str
    type: str | None = None


class AiccDeployment(NetskopeModel):
    name: str
    type: str
    status: str | None = None
    provider: str | None = None
    host_id: str | None = None
    node: str | None = None
    user: str | None = None
    framework: str | None = None
    version: str | None = None
    tools_count: int | None = None
    last_seen: datetime | None = None


class AiccViolation(NetskopeModel):
    policy_name: str
    policy_id: str | None = None
    severity: str
    category: str | None = None
    detection_id: str | None = None
    action: str | None = None
    timestamp: datetime | None = None
    count: int | None = None


class AiccProtectionViolation(NetskopeModel):
    severity: str
    violation: str
    object_type: str | None = None
    user: str | None = None
    resource: str | None = None
    status: str | None = None
    timestamp: datetime | None = None


class AiccNamedMetadata(NetskopeModel):
    name: str
    display_name: str | None = None
    category: str | None = None
    status: str | None = None
    ccl: str | None = None
    cci_score: int | None = None
    domains: list[str] | None = None
    tags: list[str] | None = None
    provider: str | None = None
    framework: str | None = None
    resource_subtype: str | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class AiccDetail(NetskopeModel):
    metadata: AiccNamedMetadata
    usage_summary: AiccUsage | None = None
    associated_identities: list[AiccAssociatedIdentity] | None = None
    identities_total_count: int | None = None
    time_range: AiccTimeRange | None = None


class AiccIdentityDetail(NetskopeModel):
    metadata: AiccIdentity
    usage_summary: AiccUsage | None = None
    associated_apps: list[AiccApplication] | None = None
    associated_mcp_servers: list[AiccMcpServer] | None = None
    associated_agents: list[AiccAgent] | None = None
    associated_models: list[AiccModel] | None = None
    time_range: AiccTimeRange | None = None


class AiccTimeBucket(NetskopeModel):
    start: datetime
    end: datetime
    value: int


class AiccTrafficBucket(NetskopeModel):
    start: datetime
    end: datetime
    uploaded_bytes: int | None = None
    downloaded_bytes: int | None = None
    sessions: int | None = None
    events: int | None = None


class AiccIdentityBucket(NetskopeModel):
    start: datetime
    end: datetime
    users: int
    unknown_users: int
    user_bytes: int | None = None
    unknown_bytes: int | None = None
    user_sessions: int | None = None


class AiccRiskPoint(NetskopeModel):
    timestamp: datetime
    risk_score: int


class AiccKpi(NetskopeModel):
    value: int
    previous_value: int | None = None
    trend: float | None = None
    resolution: str | None = None
    data: list[AiccTimeBucket]
    time_range: AiccTimeRange | None = None


class AiccTrafficTrend(NetskopeModel):
    resolution: str
    data: list[AiccTrafficBucket]
    time_range: AiccTimeRange | None = None


class AiccIdentityTrend(NetskopeModel):
    resolution: str
    data: list[AiccIdentityBucket]
    time_range: AiccTimeRange | None = None


class AiccRiskTrend(NetskopeModel):
    data: list[AiccRiskPoint]
    time_range: AiccTimeRange | None = None


class AiccSegment(NetskopeModel):
    label: str
    value: int
    display_label: str | None = None
    group_by: str | None = None


class AiccBreakdown(NetskopeModel):
    segments: list[AiccSegment]
    time_range: AiccTimeRange | None = None


class AiccEntityCounts(NetskopeModel):
    applications: int
    users: int
    unknown: int
    mcp_servers: int | None = None
    time_range: AiccTimeRange | None = None


class AiccDataCoverage(NetskopeModel):
    data_available_since: datetime | None


class AiccAlertMatrixItem(NetskopeModel):
    asset: str
    detection: str
    count: int


class AiccAlertMatrix(NetskopeModel):
    items: list[AiccAlertMatrixItem]
    time_range: AiccTimeRange | None = None


class AiccAlertPolicy(NetskopeModel):
    policy: str
    policy_id: str | None = None
    severity: str
    count: int


class AiccAlertPolicies(NetskopeModel):
    items: list[AiccAlertPolicy]
    total_alerts: int | None = None
    others: dict[str, JsonValue] | None = None
    time_range: AiccTimeRange | None = None


class AiccProtectionBreakdown(NetskopeModel):
    object_type: str
    critical: int
    high: int
    medium: int
    low: int


class AiccProtectionSummary(NetskopeModel):
    breakdown: list[AiccProtectionBreakdown]
    time_range: AiccTimeRange | None = None
