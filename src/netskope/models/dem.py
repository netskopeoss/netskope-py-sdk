"""Models and enums for the Netskope Digital Experience Management (DEM) API.

DEM covers application/network probes, experience-alert rules, a privileged
metrics query surface, and ADEM (Advanced DEM) per-user/per-device telemetry
exposed in the CLI as ``dem users``.

Most DEM/ADEM responses are deeply nested, endpoint-specific graph or
time-series structures with no stable public schema, so the resource layer
returns raw ``dict``/``list`` payloads for those.  The typed models below cover
only the handful of list-shaped, stable responses (experience alerts and the
common ADEM entity summaries).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from netskope.models.common import NetskopeModel


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
STATE_DATA_SOURCES: frozenset[str] = frozenset(
    {QueryDataSource.AGENT_STATUS, QueryDataSource.CLIENT_STATUS}
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
