"""The applications sub-namespace of aicc."""

from __future__ import annotations

from netskope.core.transport import AsyncTransport, SyncTransport
from netskope.models.aicc import (
    AiccApplication,
    AiccAssociatedIdentity,
    AiccDeployment,
    AiccDeploymentQuery,
    AiccDetail,
    AiccIdentityTrend,
    AiccOptionalWindow,
    AiccRelatedQuery,
    AiccRiskTrend,
    AiccTrafficTrend,
    AiccTrendQuery,
    AiccViolation,
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


class AiccApplicationResource:
    """One AI application's AICC detail, identities, deployments, trends and violations."""

    def __init__(self, transport: SyncTransport, name: str) -> None:
        path = f"{_BASE}/inventory/ai-applications/{_name(name)}"
        contract = "/inventory/ai-applications/{app_name}"
        self.details = AiccRead(transport, AiccEndpoint(path, contract, AiccDetail, AiccWindow))
        self.status = AiccRead(
            transport,
            AiccEndpoint(
                f"{path}/status", f"{contract}/status", AiccApplication, AiccOptionalWindow
            ),
        )
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
            AiccEndpoint(f"{path}/violations", f"{contract}/violations", AiccViolation, AiccWindow),
        )


class AsyncAiccApplicationResource:
    """One AI application's AICC detail, identities, deployments, trends and violations."""

    def __init__(self, transport: AsyncTransport, name: str) -> None:
        path = f"{_BASE}/inventory/ai-applications/{_name(name)}"
        contract = "/inventory/ai-applications/{app_name}"
        self.details = AsyncAiccRead(
            transport, AiccEndpoint(path, contract, AiccDetail, AiccWindow)
        )
        self.status = AsyncAiccRead(
            transport,
            AiccEndpoint(
                f"{path}/status", f"{contract}/status", AiccApplication, AiccOptionalWindow
            ),
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
            AiccEndpoint(f"{path}/violations", f"{contract}/violations", AiccViolation, AiccWindow),
        )
