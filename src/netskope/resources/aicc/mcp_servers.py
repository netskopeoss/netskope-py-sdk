"""The mcp servers sub-namespace of aicc."""

from __future__ import annotations

from netskope.core.transport import AsyncTransport, SyncTransport
from netskope.models.aicc import (
    AiccAssociatedIdentity,
    AiccDeployment,
    AiccDeploymentQuery,
    AiccDetail,
    AiccIdentityTrend,
    AiccRelatedQuery,
    AiccRiskTrend,
    AiccTrafficTrend,
    AiccTrendQuery,
    AiccViolation,
    AiccViolationQuery,
    AiccWindow,
)
from netskope.resources.aicc._shared import (
    _BASE,
    _name,
)
from netskope.resources.shared.aicc_endpoint import (
    AiccCollection,
    AiccEndpoint,
    AiccRead,
    AsyncAiccCollection,
    AsyncAiccRead,
)


class AiccMcpServerResource:
    """One MCP server's AICC inventory detail, identities and deployments."""

    def __init__(self, transport: SyncTransport, name: str) -> None:
        path = f"{_BASE}/inventory/mcp-servers/{_name(name)}"
        contract = "/inventory/mcp-servers/{server_name}"
        self.details = AiccRead(transport, AiccEndpoint(path, contract, AiccDetail, AiccWindow))
        self.identities = AiccCollection(
            transport,
            AiccEndpoint(
                f"{path}/identities",
                f"{contract}/identities",
                AiccAssociatedIdentity,
                AiccRelatedQuery,
            ),
        )
        self.deployments = AiccCollection(
            transport,
            AiccEndpoint(
                f"{path}/deployments",
                f"{contract}/deployments",
                AiccDeployment,
                AiccDeploymentQuery,
            ),
        )
        self.traffic_trend = AiccRead(
            transport,
            AiccEndpoint(
                f"{path}/traffic-trend",
                f"{contract}/traffic-trend",
                AiccTrafficTrend,
                AiccTrendQuery,
            ),
        )
        self.identity_trend = AiccRead(
            transport,
            AiccEndpoint(
                f"{path}/identity-trend",
                f"{contract}/identity-trend",
                AiccIdentityTrend,
                AiccTrendQuery,
            ),
        )
        self.risk_trend = AiccRead(
            transport,
            AiccEndpoint(f"{path}/risk-trend", f"{contract}/risk-trend", AiccRiskTrend, AiccWindow),
        )
        self.violations = AiccCollection(
            transport,
            AiccEndpoint(
                f"{path}/violations", f"{contract}/violations", AiccViolation, AiccViolationQuery
            ),
        )


class AsyncAiccMcpServerResource:
    """One MCP server's AICC inventory detail, identities and deployments."""

    def __init__(self, transport: AsyncTransport, name: str) -> None:
        path = f"{_BASE}/inventory/mcp-servers/{_name(name)}"
        contract = "/inventory/mcp-servers/{server_name}"
        self.details = AsyncAiccRead(
            transport, AiccEndpoint(path, contract, AiccDetail, AiccWindow)
        )
        self.identities = AsyncAiccCollection(
            transport,
            AiccEndpoint(
                f"{path}/identities",
                f"{contract}/identities",
                AiccAssociatedIdentity,
                AiccRelatedQuery,
            ),
        )
        self.deployments = AsyncAiccCollection(
            transport,
            AiccEndpoint(
                f"{path}/deployments",
                f"{contract}/deployments",
                AiccDeployment,
                AiccDeploymentQuery,
            ),
        )
        self.traffic_trend = AsyncAiccRead(
            transport,
            AiccEndpoint(
                f"{path}/traffic-trend",
                f"{contract}/traffic-trend",
                AiccTrafficTrend,
                AiccTrendQuery,
            ),
        )
        self.identity_trend = AsyncAiccRead(
            transport,
            AiccEndpoint(
                f"{path}/identity-trend",
                f"{contract}/identity-trend",
                AiccIdentityTrend,
                AiccTrendQuery,
            ),
        )
        self.risk_trend = AsyncAiccRead(
            transport,
            AiccEndpoint(f"{path}/risk-trend", f"{contract}/risk-trend", AiccRiskTrend, AiccWindow),
        )
        self.violations = AsyncAiccCollection(
            transport,
            AiccEndpoint(
                f"{path}/violations", f"{contract}/violations", AiccViolation, AiccViolationQuery
            ),
        )
