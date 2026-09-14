"""The identities sub-namespace of aicc."""

from __future__ import annotations

from netskope.core.transport import AsyncTransport, SyncTransport
from netskope.models.aicc import (
    AiccAgent,
    AiccIdentityDetail,
    AiccMcpServer,
    AiccModel,
    AiccRelatedQuery,
    AiccRiskTrend,
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


class AiccIdentityResource:
    """One identity's AICC inventory detail and the applications it reached."""

    def __init__(self, transport: SyncTransport, name: str) -> None:
        path = f"{_BASE}/inventory/identities/{_name(name)}"
        contract = "/inventory/identities/{identity_id}"
        self.details = AiccRead(
            transport, AiccEndpoint(path, contract, AiccIdentityDetail, AiccWindow)
        )
        self.agents = AiccCollection(
            transport,
            AiccEndpoint(f"{path}/agents", f"{contract}/agents", AiccAgent, AiccRelatedQuery),
        )
        self.models = AiccCollection(
            transport,
            AiccEndpoint(f"{path}/models", f"{contract}/models", AiccModel, AiccRelatedQuery),
        )
        self.mcp_servers = AiccCollection(
            transport,
            AiccEndpoint(
                f"{path}/mcp-servers", f"{contract}/mcp-servers", AiccMcpServer, AiccRelatedQuery
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
        self.risk_trend = AiccRead(
            transport,
            AiccEndpoint(f"{path}/risk-trend", f"{contract}/risk-trend", AiccRiskTrend, AiccWindow),
        )


class AsyncAiccIdentityResource:
    """One identity's AICC inventory detail and the applications it reached."""

    def __init__(self, transport: AsyncTransport, name: str) -> None:
        path = f"{_BASE}/inventory/identities/{_name(name)}"
        contract = "/inventory/identities/{identity_id}"
        self.details = AsyncAiccRead(
            transport, AiccEndpoint(path, contract, AiccIdentityDetail, AiccWindow)
        )
        self.agents = AsyncAiccCollection(
            transport,
            AiccEndpoint(f"{path}/agents", f"{contract}/agents", AiccAgent, AiccRelatedQuery),
        )
        self.models = AsyncAiccCollection(
            transport,
            AiccEndpoint(f"{path}/models", f"{contract}/models", AiccModel, AiccRelatedQuery),
        )
        self.mcp_servers = AsyncAiccCollection(
            transport,
            AiccEndpoint(
                f"{path}/mcp-servers", f"{contract}/mcp-servers", AiccMcpServer, AiccRelatedQuery
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
        self.risk_trend = AsyncAiccRead(
            transport,
            AiccEndpoint(f"{path}/risk-trend", f"{contract}/risk-trend", AiccRiskTrend, AiccWindow),
        )
