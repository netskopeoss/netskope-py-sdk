"""The agents sub-namespace of aicc."""

from __future__ import annotations

from netskope.core.transport import AsyncTransport, SyncTransport
from netskope.models.aicc import (
    AiccAssociatedIdentity,
    AiccDeployment,
    AiccDeploymentQuery,
    AiccDetail,
    AiccRelatedQuery,
    AiccTrafficTrend,
    AiccTrendQuery,
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


class AiccAgentResource:
    """One agent's AICC inventory detail and the identities that run it."""

    def __init__(self, transport: SyncTransport, name: str) -> None:
        path = f"{_BASE}/inventory/agents/{_name(name)}"
        contract = "/inventory/agents/{agent_name}"
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


class AsyncAiccAgentResource:
    """One agent's AICC inventory detail and the identities that run it."""

    def __init__(self, transport: AsyncTransport, name: str) -> None:
        path = f"{_BASE}/inventory/agents/{_name(name)}"
        contract = "/inventory/agents/{agent_name}"
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
