"""The analytics sub-namespace of aicc."""

from __future__ import annotations

from netskope.core.transport import AsyncTransport, SyncTransport
from netskope.models.aicc import (
    AiccAlertMatrix,
    AiccAlertPolicies,
    AiccAlertQuery,
    AiccBreakdown,
    AiccBreakdownQuery,
    AiccCountQuery,
    AiccEntityCountQuery,
    AiccEntityCounts,
    AiccKpi,
    AiccSumQuery,
)
from netskope.resources.aicc._shared import (
    _BASE,
)
from netskope.resources.shared.aicc_endpoint import (
    AiccEndpoint,
    AiccRead,
    AsyncAiccRead,
)


class AiccAnalytics:
    """AICC analytics: counts, sums, entity breakdowns and alert matrices."""

    def __init__(self, transport: SyncTransport) -> None:
        self.counts = AiccRead(
            transport,
            AiccEndpoint(f"{_BASE}/analytics/counts", "/analytics/counts", AiccKpi, AiccCountQuery),
        )
        self.sums = AiccRead(
            transport,
            AiccEndpoint(f"{_BASE}/analytics/sums", "/analytics/sums", AiccKpi, AiccSumQuery),
        )
        self.entity_counts = AiccRead(
            transport,
            AiccEndpoint(
                f"{_BASE}/analytics/entity-counts",
                "/analytics/entity-counts",
                AiccEntityCounts,
                AiccEntityCountQuery,
            ),
        )
        self.breakdown_apps = AiccRead(
            transport,
            AiccEndpoint(
                f"{_BASE}/analytics/ai-applications",
                "/analytics/ai-applications",
                AiccBreakdown,
                AiccBreakdownQuery,
            ),
        )
        self.breakdown_mcp = AiccRead(
            transport,
            AiccEndpoint(
                f"{_BASE}/analytics/mcp-servers",
                "/analytics/mcp-servers",
                AiccBreakdown,
                AiccBreakdownQuery,
            ),
        )
        self.breakdown_identities = AiccRead(
            transport,
            AiccEndpoint(
                f"{_BASE}/analytics/identities",
                "/analytics/identities",
                AiccBreakdown,
                AiccBreakdownQuery,
            ),
        )
        self.breakdown_models = AiccRead(
            transport,
            AiccEndpoint(
                f"{_BASE}/analytics/models", "/analytics/models", AiccBreakdown, AiccBreakdownQuery
            ),
        )
        self.breakdown_agents = AiccRead(
            transport,
            AiccEndpoint(
                f"{_BASE}/analytics/agents", "/analytics/agents", AiccBreakdown, AiccBreakdownQuery
            ),
        )
        self.alerts_matrix = AiccRead(
            transport,
            AiccEndpoint(
                f"{_BASE}/analytics/alerts/matrix",
                "/analytics/alerts/matrix",
                AiccAlertMatrix,
                AiccAlertQuery,
            ),
        )
        self.alert_policies = AiccRead(
            transport,
            AiccEndpoint(
                f"{_BASE}/analytics/alerts/policies",
                "/analytics/alerts/policies",
                AiccAlertPolicies,
                AiccAlertQuery,
            ),
        )


class AsyncAiccAnalytics:
    """AICC analytics: counts, sums, entity breakdowns and alert matrices."""

    def __init__(self, transport: AsyncTransport) -> None:
        self.counts = AsyncAiccRead(
            transport,
            AiccEndpoint(f"{_BASE}/analytics/counts", "/analytics/counts", AiccKpi, AiccCountQuery),
        )
        self.sums = AsyncAiccRead(
            transport,
            AiccEndpoint(f"{_BASE}/analytics/sums", "/analytics/sums", AiccKpi, AiccSumQuery),
        )
        self.entity_counts = AsyncAiccRead(
            transport,
            AiccEndpoint(
                f"{_BASE}/analytics/entity-counts",
                "/analytics/entity-counts",
                AiccEntityCounts,
                AiccEntityCountQuery,
            ),
        )
        self.breakdown_apps = AsyncAiccRead(
            transport,
            AiccEndpoint(
                f"{_BASE}/analytics/ai-applications",
                "/analytics/ai-applications",
                AiccBreakdown,
                AiccBreakdownQuery,
            ),
        )
        self.breakdown_mcp = AsyncAiccRead(
            transport,
            AiccEndpoint(
                f"{_BASE}/analytics/mcp-servers",
                "/analytics/mcp-servers",
                AiccBreakdown,
                AiccBreakdownQuery,
            ),
        )
        self.breakdown_identities = AsyncAiccRead(
            transport,
            AiccEndpoint(
                f"{_BASE}/analytics/identities",
                "/analytics/identities",
                AiccBreakdown,
                AiccBreakdownQuery,
            ),
        )
        self.breakdown_models = AsyncAiccRead(
            transport,
            AiccEndpoint(
                f"{_BASE}/analytics/models", "/analytics/models", AiccBreakdown, AiccBreakdownQuery
            ),
        )
        self.breakdown_agents = AsyncAiccRead(
            transport,
            AiccEndpoint(
                f"{_BASE}/analytics/agents", "/analytics/agents", AiccBreakdown, AiccBreakdownQuery
            ),
        )
        self.alerts_matrix = AsyncAiccRead(
            transport,
            AiccEndpoint(
                f"{_BASE}/analytics/alerts/matrix",
                "/analytics/alerts/matrix",
                AiccAlertMatrix,
                AiccAlertQuery,
            ),
        )
        self.alert_policies = AsyncAiccRead(
            transport,
            AiccEndpoint(
                f"{_BASE}/analytics/alerts/policies",
                "/analytics/alerts/policies",
                AiccAlertPolicies,
                AiccAlertQuery,
            ),
        )
