"""Models and enums for the Netskope Digital Experience Management (DEM) API.

DEM covers application/network probes, experience-alert rules, a privileged
metrics query surface, and ADEM (Advanced DEM) per-user/per-device telemetry
exposed in the CLI as ``dem users``.

Typed response accessors expose endpoint-specific graph, time-series, and
entity models. Query aliases remain dynamic columns inside a validated row
and metadata contract. Legacy raw-returning resource methods remain available.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

from netskope.models.common import NetskopeModel


def _parse_rfc3339(value: str) -> datetime:
    """Read one RFC 3339 query bound, rejecting anything the gateway would."""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        raise ValueError("A query bound must be an RFC 3339 timestamp.") from None


class QueryDataSource(StrEnum):
    """Data sources accepted by the DEM query surface (``dem/query/*``).

    Values mirror the CLI ``QUERY_DATA_SOURCES`` list.
    """

    UX_SCORE = "ux_score"
    RUM_STEERED = "rum_steered"
    RUM_BYPASSED = "rum_bypassed"
    TRACEROUTE_POP = "traceroute_pop"
    TRACEROUTE_BYPASSED = "traceroute_bypassed"
    TRACEROUTE_ALL = "traceroute_all"
    HTTP_STEERED = "http_steered"
    HTTP_BYPASSED = "http_bypassed"
    HTTP_ALL = "http_all"
    HTTP = "http"
    RUM_UX_SCORE_ALL = "rum_ux_score_all"
    RUM_UX_SCORE_STEERED = "rum_ux_score_steered"
    RUM_UX_SCORE_BYPASSED = "rum_ux_score_bypassed"
    NPA_GATEWAY = "npa_gateway"
    NPA_METRIC = "npa_metric"
    NPA_STITCHER = "npa_stitcher"
    AGENT_STATUS = "agent_status"
    CLIENT_STATUS = "client_status"


class AggregationType(StrEnum):
    """Aggregation types for ADEM ``device/getaggregatedscores``."""

    AVG = "avg"
    P95 = "p95"


class NetworkMetricType(StrEnum):
    """Metric types for ADEM ``metrics/getnetwork``."""

    ALL = "all"
    LATENCY = "latency"
    PACKET_LOSS = "packet_loss"
    JITTER = "jitter"


# Data sources valid for the stateless ``getstates`` query (no time window).
# ``StateQueryFrom`` (dem-workbench-query.yaml:516-521).
STATE_DATA_SOURCES: frozenset[str] = frozenset(
    {QueryDataSource.AGENT_STATUS, QueryDataSource.CLIENT_STATUS}
)

# Data sources valid for ``getdata``/``getdataset``. ``DataQueryFrom``
# (dem-workbench-query.yaml:15-33) is the 16-value set without ``agent_status``
# and ``client_status``, which belong to ``StateQueryFrom`` alone.
DATA_QUERY_SOURCES: frozenset[str] = frozenset(
    set(QueryDataSource) - {QueryDataSource.AGENT_STATUS, QueryDataSource.CLIENT_STATUS}
)

# Data sources valid for the ``gettraceroute`` query.
TRACEROUTE_DATA_SOURCES: frozenset[str] = frozenset(
    {QueryDataSource.TRACEROUTE_POP, QueryDataSource.TRACEROUTE_BYPASSED}
)


class DemAlert(NetskopeModel):
    """A triggered DEM experience alert instance."""

    id: str | None = Field(None, alias="_id")
    alert_category: str | None = Field(None, alias="alertCategory")
    alert_type: str | None = Field(None, alias="alertType")
    severity: str | None = None
    status: str | None = None
    open_time: int | None = Field(None, alias="openTime")


class AdemDevice(NetskopeModel):
    """An ADEM device summary (from ``dem users devices``)."""

    device_id: str | None = Field(None, alias="deviceId")
    device_name: str | None = Field(None, alias="deviceName")
    device_os: str | None = Field(None, alias="deviceOs")
    exp_score: float | None = Field(None, alias="expScore")


class AdemUserInfo(NetskopeModel):
    """An ADEM user info summary (from ``dem users info``)."""

    user: str | None = None
    exp_score: float | None = Field(None, alias="expScore")
    last_known_location: str | None = Field(None, alias="lastKnownLocation")
    organization_unit: str | None = Field(None, alias="organizationUnit")
    user_group: str | None = Field(None, alias="userGroup")


class AdemApplication(NetskopeModel):
    """An ADEM per-device application summary (from ``dem users applications``)."""

    app_name: str | None = Field(None, alias="appName")
    exp_score: float | None = Field(None, alias="expScore")


class NpaHost(NetskopeModel):
    """An ADEM NPA host summary (from ``dem users npa-hosts``)."""

    npa_host: str | None = Field(None, alias="npaHost")
    exp_score: float | None = Field(None, alias="expScore")
    npa_applications: list[str] = Field(default_factory=list, alias="npaApplications")


class DemQueryRow(RootModel[dict[str, Any]]):
    """One dynamic select/alias row. Column names are chosen by the caller."""

    model_config = ConfigDict(frozen=True)


class DemQueryMetadata(NetskopeModel):
    """Query execution information, not proof of complete pagination."""

    fields: list[str] = Field(default_factory=list)
    elapsed: float | None = None
    total: int | None = Field(default=None, ge=0)
    is_timeseries: bool | None = None
    sampling_enabled: bool | None = None
    extra_points: bool | None = None
    slot_size: int | None = None
    begin: str | int | None = None
    end: str | int | None = None
    call_date: str | None = None


class DemQueryResult(NetskopeModel):
    """A bounded query result with typed metadata and dynamic selected columns."""

    data: list[DemQueryRow]
    meta: DemQueryMetadata | None = None


class DemProbeEntity(NetskopeModel):
    """The users, groups and OUs a probe runs for (demconfig.yaml:2670-2684)."""

    user: list[str] = Field(default_factory=list)
    group: list[str] = Field(default_factory=list)
    ou: list[str] = Field(default_factory=list)


class DemProbe(NetskopeModel):
    """An app or network probe row.

    Fields follow ``AppProbeCreateUpdateResp`` (demconfig.yaml:2753-2811) plus
    the two collection flags ``NetworkProbeCreateUpdateResp`` adds
    (:2813-2870).  ``status`` is an integer (1 enabled, 0 disabled), not a
    boolean.
    """

    id: str | int | None = None
    name: str | None = None
    app_id: int | None = Field(default=None, alias="appID")
    app_name: str | None = Field(default=None, alias="appName")
    app_type: str | None = Field(default=None, alias="appType")
    app_domains: list[str] = Field(default_factory=list, alias="appDomains")
    frequency: int | None = None
    entity: DemProbeEntity | None = None
    os: list[str] = Field(default_factory=list)
    device_classification: list[str] = Field(default_factory=list, alias="deviceClassification")
    status: int | None = None
    priority: int | None = None
    network_path_device_health_collection: bool | None = Field(
        default=None, alias="networkPathDeviceHealthCollection"
    )
    process_info_collection: bool | None = Field(default=None, alias="processInfoCollection")
    modified_time: str | None = Field(default=None, alias="modifiedTime")
    created_time: str | None = Field(default=None, alias="createdTime")


class DemAlertRuleReceiver(NetskopeModel):
    id: str | None = None


class DemAlertRule(NetskopeModel):
    """An experience-alert rule.

    Fields follow ``AlertRuleResponse`` = ``PostAlertRuleRequest`` plus ``id``,
    ``lastUpdateTime`` and ``numOfAlerts`` (dem_alert.yaml:274-287, :441-467).
    The measured metric lives at ``criteria.condition.measure`` and its
    threshold at ``criteria.condition.thresholds``.
    """

    id: str | None = None
    name: str | None = None
    category: str | None = None
    type: str | None = None
    severity: str | None = None
    enabled: bool | None = None
    criteria: dict[str, Any] | None = None
    criteria_type: str | None = Field(default=None, alias="criteriaType")
    email_receiver: str | None = Field(default=None, alias="emailReceiver")
    webhook_receivers: list[DemAlertRuleReceiver] = Field(
        default_factory=list, alias="webhookReceivers"
    )
    last_update_time: int | None = Field(default=None, alias="lastUpdateTime")
    num_of_alerts: int | None = Field(default=None, alias="numOfAlerts")


class DemApp(NetskopeModel):
    id: str | int | None = None
    name: str | None = Field(default=None, alias="appName")
    type: str | None = Field(default=None, alias="appType")


class DemEntity(NetskopeModel):
    user: str | None = None
    user_id: str | None = None
    exp_score: float | None = None
    user_score: float | None = None
    location: str | None = None
    applications_count: int | None = Field(default=None, alias="applicationsCount")
    devices: list[AdemDevice] = Field(default_factory=list)
    user_groups: list[str] = Field(default_factory=list, alias="userGroups")


class DemDefinitionField(NetskopeModel):
    name: str
    description: str | None = None
    unit: str | None = None
    sources: list[str] | None = None


class DemDefinitionFunction(NetskopeModel):
    name: str
    valid_on_keys: bool | None = None


class DemDefinitionComparison(NetskopeModel):
    name: str
    type: str | None = None


class DemDefinitions(NetskopeModel):
    metrics: list[DemDefinitionField]
    keys: list[DemDefinitionField]
    functions: list[DemDefinitionFunction | str]
    comparisons: list[DemDefinitionComparison] = Field(default_factory=list)


class AdemLocation(NetskopeModel):
    city: str | None = None
    country: str | None = None
    region: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class AdemDeviceDetails(AdemDevice):
    client_status: str | None = Field(default=None, alias="clientStatus")
    client_version: str | None = Field(default=None, alias="clientVersion")
    classification: str | None = Field(default=None, alias="deviceClassification")
    device_score: float | None = Field(default=None, alias="deviceScore")
    cpu: str | None = None
    memory: str | None = None
    model: str | None = None
    geo: AdemLocation | None = None
    gateway: str | None = None
    pop: str | None = None
    private_ip: str | None = Field(default=None, alias="privateIp")
    public_ip: str | None = Field(default=None, alias="publicIp")
    last_activity: int | None = Field(default=None, alias="lastActivity")


class AdemScores(NetskopeModel):
    exp_score: float | None = Field(default=None, alias="expScore")
    device_score: float | None = Field(default=None, alias="deviceScore")
    network_score: float | None = Field(default=None, alias="networkScore")
    app_score: float | None = Field(default=None, alias="appScore")
    npa_host_score: float | None = Field(default=None, alias="npaHostScore")


class AdemAggregatedScores(NetskopeModel):
    aggregation_type: str | None = Field(default=None, alias="aggregationType")
    metrics: AdemScores


class AdemMetricPoint(NetskopeModel):
    timestamp: int | None = None
    exp_score: float | None = Field(default=None, alias="expScore")
    latency: float | None = None
    packet_loss: float | None = Field(default=None, alias="packetLoss")
    jitter: float | None = None
    pop: str | None = None


class AdemEvidence(NetskopeModel):
    key: str | None = None
    value: Any | None = None
    obs: dict[str, Any] = Field(default_factory=dict)


class AdemCause(NetskopeModel):
    name: str | None = None
    weight: float | None = None
    evidence: AdemEvidence | None = None
    caused_by: list[AdemCause] | None = Field(default=None, alias="causedBy")


class AdemRcaItem(NetskopeModel):
    starttime: int | None = None
    endtime: int | None = None
    root_cause: AdemCause | None = Field(default=None, alias="rootCause")
    score_summary: dict[str, float | None] = Field(default_factory=dict, alias="scoreSummary")


class AdemComponentScore(NetskopeModel):
    score: float | None = None
    utilization: float | None = None


class AdemRootCause(NetskopeModel):
    """Current RCA trees and older component-score responses."""

    items: list[AdemRcaItem] = Field(default_factory=list)
    cpu: AdemComponentScore | None = Field(default=None, alias="CPU_SCORE")
    memory: AdemComponentScore | None = Field(default=None, alias="MEMORY_SCORE")
    disk: AdemComponentScore | None = Field(default=None, alias="DISK_SCORE")


class AdemGraphNode(NetskopeModel):
    id: str | int
    name: str | None = None
    type: str | None = None
    hop_type: str | None = Field(default=None, alias="hopType")
    ip: str | None = None
    latency_ms: float | None = Field(default=None, alias="latencyms")
    packet_loss: float | None = Field(default=None, alias="packetLoss")
    npa_host_details: NpaHost | None = Field(default=None, alias="npaHostDetails")


class AdemGraphEdge(NetskopeModel):
    source: str | int
    destination: str | int
    average_latency: float | None = Field(default=None, alias="avgLatency")
    median_latency: float | None = Field(default=None, alias="medianLatency")
    sessions: int | None = Field(default=None, alias="noOfSessions")
    latency_ms: float | None = Field(default=None, alias="latencyms")


class AdemNetworkGraph(NetskopeModel):
    nodes: list[AdemGraphNode]
    edges: list[AdemGraphEdge]
    complete: bool | None = Field(default=None, alias="isComplete")
    device_to_pop_latency_ms: float | None = Field(default=None, alias="deviceToPopLatencyms")


class DemProbeMove(BaseModel):
    """``MoveProbeReqBody`` (demconfig.yaml:2494-2508); ``position`` is required
    for ``after``/``before``."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    operation: Literal["top", "bottom", "after", "before"]
    position: int | None = None

    @model_validator(mode="after")
    def _position_required(self) -> Self:
        if self.operation in ("after", "before") and self.position is None:
            raise ValueError("A move after or before another probe needs its 0-based position.")
        return self


class DemProbeCreate(BaseModel):
    """``AppProbeCreateRequest`` (demconfig.yaml:2744-2752).

    ``AppProbeUpdateCreateCommon`` requires ``name``, ``frequency``,
    ``entity``, ``os``, ``deviceClassification`` and ``status``; the ``oneOf``
    adds ``appName`` for a predefined app or ``appID`` for a custom one, and
    the create variant also requires ``move``.
    """

    model_config = ConfigDict(extra="allow", strict=True, frozen=True, populate_by_name=True)

    name: str = Field(min_length=1)
    frequency: int
    entity: dict[str, list[str]]
    os: list[Literal["windows", "mac"]] = Field(min_length=1)
    device_classification: list[Literal["managed", "unmanaged", "not configured"]] = Field(
        min_length=1, alias="deviceClassification"
    )
    status: int
    app_type: Literal["predefined", "custom"] = Field(alias="appType")
    app_name: str | None = Field(default=None, alias="appName")
    app_id: int | None = Field(default=None, alias="appID")
    move: DemProbeMove

    @model_validator(mode="after")
    def _app_selector(self) -> Self:
        if self.app_type == "predefined" and not self.app_name:
            raise ValueError("A predefined app probe requires appName.")
        if self.app_type == "custom" and self.app_id is None:
            raise ValueError("A custom app probe requires appID.")
        return self


class DemAlertRuleCreate(BaseModel):
    """``PostAlertRuleRequest`` (dem_alert.yaml:441-467).

    The schema lists no required properties, but a rule without a name or a
    measurable criterion cannot be acted on, so both are required here.
    """

    model_config = ConfigDict(extra="allow", strict=True, frozen=True, populate_by_name=True)

    name: str = Field(min_length=1)
    criteria: dict[str, Any]
    severity: Literal["info", "low", "medium", "high", "critical"] = "medium"
    enabled: bool = True
    category: str | None = None
    type: str | None = None
    criteria_type: str | None = Field(default=None, alias="criteriaType")
    email_receiver: str | None = Field(default=None, alias="emailReceiver")


class DemQueryRequest(BaseModel):
    """Native DEM query arguments; arbitrary select expressions remain dynamic."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, strict=True, frozen=True)

    data_source: str = Field(alias="from")
    select: list[Any] = Field(min_length=1)
    begin: dict[str, str] | None = None
    end: dict[str, str] | None = None
    where: Any | None = None
    group_by: list[str] | None = Field(default=None, alias="groupby")
    order_by: list[Any] | None = Field(default=None, alias="orderby")
    limit: int | None = Field(default=None, ge=0)
    offset: int | None = Field(default=None, ge=0)

    @field_validator("begin", "end")
    @classmethod
    def _query_bound(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        """``QueryInput.begin``/``.end`` accept one RFC 3339 bound.

        ``AbsoluteDate``/``RelativeDate`` (dem-workbench-query.yaml:5-14,
        :499-507) each carry exactly one key, and ``QueryInput`` sets
        ``additionalProperties: false`` (:420).
        """
        if value is None:
            return value
        if len(value) != 1 or next(iter(value)) not in ("absolute", "relative"):
            raise ValueError('A query bound is {"absolute": <RFC3339>} or {"relative": <RFC3339>}.')
        _parse_rfc3339(next(iter(value.values())))
        return value

    @model_validator(mode="after")
    def _ordered_window(self) -> Self:
        if self.begin is None or self.end is None:
            return self
        begin_key, end_key = next(iter(self.begin)), next(iter(self.end))
        if begin_key != end_key:
            raise ValueError("begin and end must both be absolute or both be relative.")
        if _parse_rfc3339(self.end[end_key]) <= _parse_rfc3339(self.begin[begin_key]):
            raise ValueError("end must be greater than begin.")
        return self


class AdemQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, strict=True, frozen=True)

    start_time: int = Field(alias="starttime", ge=0)
    end_time: int = Field(alias="endtime", ge=0)
    user: str | None = None
    device_id: str | None = Field(default=None, alias="deviceId")
    user_location: list[AdemLocation] | None = Field(default=None, alias="userLocation")
    aggregation_type: Literal["avg", "p95"] | None = Field(default=None, alias="aggregationType")
    metric_type: Literal["all", "latency", "packet_loss", "jitter"] | None = Field(
        default=None, alias="metricType"
    )
    npa_host: str | None = Field(default=None, alias="npaHost")

    @model_validator(mode="after")
    def _ordered_window(self) -> Self:
        if self.end_time < self.start_time:
            raise ValueError("end_time must not precede start_time.")
        return self
