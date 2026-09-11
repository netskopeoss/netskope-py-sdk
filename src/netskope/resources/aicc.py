"""AI Command Center resources. Paths, query serialization and pagination live here."""

from __future__ import annotations

from urllib.parse import quote

from netskope._transport import AsyncTransport, SyncTransport
from netskope.exceptions import ValidationError
from netskope.models.aicc import (
    AiccAgent,
    AiccAgentQuery,
    AiccAlertMatrix,
    AiccAlertPolicies,
    AiccAlertQuery,
    AiccApplication,
    AiccApplicationQuery,
    AiccAssociatedIdentity,
    AiccBreakdown,
    AiccBreakdownQuery,
    AiccCountQuery,
    AiccDataCoverage,
    AiccDeployment,
    AiccDeploymentQuery,
    AiccDetail,
    AiccEntityCountQuery,
    AiccEntityCounts,
    AiccExtensionQuery,
    AiccExtensionRelatedQuery,
    AiccIdentity,
    AiccIdentityDetail,
    AiccIdentityQuery,
    AiccIdentityTrend,
    AiccKpi,
    AiccMcpQuery,
    AiccMcpServer,
    AiccModel,
    AiccModelQuery,
    AiccOptionalWindow,
    AiccProtectionQuery,
    AiccProtectionSummary,
    AiccProtectionViolation,
    AiccQuery,
    AiccRelatedQuery,
    AiccRiskTrend,
    AiccSumQuery,
    AiccTrafficTrend,
    AiccTrendQuery,
    AiccViolation,
    AiccViolationQuery,
    AiccWindow,
)
from netskope.resources._aicc_endpoint import (
    AiccCollection,
    AiccEndpoint,
    AiccRead,
    AsyncAiccCollection,
    AsyncAiccRead,
)

_BASE = "/api/v2/aicc"


def _name(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("An AICC entity name cannot be blank.")
    if value in (".", ".."):
        raise ValidationError("An AICC entity name cannot be a relative path segment.")
    return quote(value, safe="")


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


class AiccModelResource:
    """One model's AICC inventory detail and the applications that call it."""

    def __init__(self, transport: SyncTransport, name: str) -> None:
        path = f"{_BASE}/inventory/models/{_name(name)}"
        contract = "/inventory/models/{model_name}"
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


class AiccExtensionResource:
    """One browser extension's AICC inventory detail and deployments."""

    def __init__(self, transport: SyncTransport, name: str) -> None:
        path = f"{_BASE}/inventory/extensions/{_name(name)}"
        contract = "/inventory/extensions/{extension_name}"
        self.details = AiccRead(
            transport, AiccEndpoint(path, contract, AiccDetail, AiccExtensionQuery)
        )
        self.identities = AiccCollection(
            transport,
            AiccEndpoint(
                f"{path}/identities",
                f"{contract}/identities",
                AiccAssociatedIdentity,
                AiccExtensionRelatedQuery,
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


class AiccDataProtection:
    """One provider's AICC data-protection summary and violations."""

    def __init__(self, transport: SyncTransport, provider: str) -> None:
        if provider not in ("anthropic", "mscopilot", "chatgpt"):
            raise ValidationError("Unsupported AICC data-protection provider.")
        path = f"{_BASE}/provider/{provider}/data-protection"
        contract = "/provider/{provider}/data-protection"
        self.summary = AiccRead(
            transport,
            AiccEndpoint(
                f"{path}/summary", f"{contract}/summary", AiccProtectionSummary, AiccWindow
            ),
        )
        self.violations = AiccCollection(
            transport,
            AiccEndpoint(
                f"{path}/violations",
                f"{contract}/violations",
                AiccProtectionViolation,
                AiccProtectionQuery,
                records_key="violations",
            ),
        )


class AiccResource:
    """Synchronous interface to the AI Command Center (AICC) inventory and analytics.

    The per-entity accessors below URL-quote the name they are given into the
    request path and reject a blank name or a relative path segment with
    :class:`~netskope.exceptions.ValidationError`.
    """

    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport
        self.analytics = AiccAnalytics(transport)
        self.data_coverage = AiccRead(
            transport,
            AiccEndpoint(f"{_BASE}/data-coverage", "/data-coverage", AiccDataCoverage, AiccQuery),
        )
        self.applications = AiccCollection(
            transport,
            AiccEndpoint(
                f"{_BASE}/inventory/ai-applications",
                "/inventory/ai-applications",
                AiccApplication,
                AiccApplicationQuery,
                identity_field="name",
            ),
        )
        self.mcp_servers = AiccCollection(
            transport,
            AiccEndpoint(
                f"{_BASE}/inventory/mcp-servers",
                "/inventory/mcp-servers",
                AiccMcpServer,
                AiccMcpQuery,
                identity_field="name",
            ),
        )
        self.identities = AiccCollection(
            transport,
            AiccEndpoint(
                f"{_BASE}/inventory/identities",
                "/inventory/identities",
                AiccIdentity,
                AiccIdentityQuery,
                identity_field="user_id",
            ),
        )
        self.models = AiccCollection(
            transport,
            AiccEndpoint(
                f"{_BASE}/inventory/models",
                "/inventory/models",
                AiccModel,
                AiccModelQuery,
                identity_field="name",
            ),
        )
        self.agents = AiccCollection(
            transport,
            AiccEndpoint(
                f"{_BASE}/inventory/agents",
                "/inventory/agents",
                AiccAgent,
                AiccAgentQuery,
                identity_field="name",
            ),
        )

    def application(self, name: str) -> AiccApplicationResource:
        """Return the sub-resource for one AI application, addressed by *name*."""
        return AiccApplicationResource(self._transport, name)

    def mcp_server(self, name: str) -> AiccMcpServerResource:
        """Return the sub-resource for one MCP server, addressed by *name*."""
        return AiccMcpServerResource(self._transport, name)

    def identity(self, name: str) -> AiccIdentityResource:
        """Return the sub-resource for one identity, addressed by *name*."""
        return AiccIdentityResource(self._transport, name)

    def model(self, name: str) -> AiccModelResource:
        """Return the sub-resource for one AI model, addressed by *name*."""
        return AiccModelResource(self._transport, name)

    def agent(self, name: str) -> AiccAgentResource:
        """Return the sub-resource for one AI agent, addressed by *name*."""
        return AiccAgentResource(self._transport, name)

    def extension(self, name: str) -> AiccExtensionResource:
        """Return the sub-resource for one browser extension, addressed by *name*."""
        return AiccExtensionResource(self._transport, name)

    def data_protection(self, provider: str) -> AiccDataProtection:
        """Return the data-protection sub-resource for one provider."""
        return AiccDataProtection(self._transport, provider)


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


class AsyncAiccModelResource:
    """One model's AICC inventory detail and the applications that call it."""

    def __init__(self, transport: AsyncTransport, name: str) -> None:
        path = f"{_BASE}/inventory/models/{_name(name)}"
        contract = "/inventory/models/{model_name}"
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


class AsyncAiccExtensionResource:
    """One browser extension's AICC inventory detail and deployments."""

    def __init__(self, transport: AsyncTransport, name: str) -> None:
        path = f"{_BASE}/inventory/extensions/{_name(name)}"
        contract = "/inventory/extensions/{extension_name}"
        self.details = AsyncAiccRead(
            transport, AiccEndpoint(path, contract, AiccDetail, AiccExtensionQuery)
        )
        self.identities = AsyncAiccCollection(
            transport,
            AiccEndpoint(
                f"{path}/identities",
                f"{contract}/identities",
                AiccAssociatedIdentity,
                AiccExtensionRelatedQuery,
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


class AsyncAiccDataProtection:
    """One provider's AICC data-protection summary and violations."""

    def __init__(self, transport: AsyncTransport, provider: str) -> None:
        if provider not in ("anthropic", "mscopilot", "chatgpt"):
            raise ValidationError("Unsupported AICC data-protection provider.")
        path = f"{_BASE}/provider/{provider}/data-protection"
        contract = "/provider/{provider}/data-protection"
        self.summary = AsyncAiccRead(
            transport,
            AiccEndpoint(
                f"{path}/summary", f"{contract}/summary", AiccProtectionSummary, AiccWindow
            ),
        )
        self.violations = AsyncAiccCollection(
            transport,
            AiccEndpoint(
                f"{path}/violations",
                f"{contract}/violations",
                AiccProtectionViolation,
                AiccProtectionQuery,
                records_key="violations",
            ),
        )


class AsyncAiccResource:
    """Asynchronous interface to the AI Command Center (AICC) inventory and analytics.

    The per-entity accessors below URL-quote the name they are given into the
    request path and reject a blank name or a relative path segment with
    :class:`~netskope.exceptions.ValidationError`.
    """

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport
        self.analytics = AsyncAiccAnalytics(transport)
        self.data_coverage = AsyncAiccRead(
            transport,
            AiccEndpoint(f"{_BASE}/data-coverage", "/data-coverage", AiccDataCoverage, AiccQuery),
        )
        self.applications = AsyncAiccCollection(
            transport,
            AiccEndpoint(
                f"{_BASE}/inventory/ai-applications",
                "/inventory/ai-applications",
                AiccApplication,
                AiccApplicationQuery,
                identity_field="name",
            ),
        )
        self.mcp_servers = AsyncAiccCollection(
            transport,
            AiccEndpoint(
                f"{_BASE}/inventory/mcp-servers",
                "/inventory/mcp-servers",
                AiccMcpServer,
                AiccMcpQuery,
                identity_field="name",
            ),
        )
        self.identities = AsyncAiccCollection(
            transport,
            AiccEndpoint(
                f"{_BASE}/inventory/identities",
                "/inventory/identities",
                AiccIdentity,
                AiccIdentityQuery,
                identity_field="user_id",
            ),
        )
        self.models = AsyncAiccCollection(
            transport,
            AiccEndpoint(
                f"{_BASE}/inventory/models",
                "/inventory/models",
                AiccModel,
                AiccModelQuery,
                identity_field="name",
            ),
        )
        self.agents = AsyncAiccCollection(
            transport,
            AiccEndpoint(
                f"{_BASE}/inventory/agents",
                "/inventory/agents",
                AiccAgent,
                AiccAgentQuery,
                identity_field="name",
            ),
        )

    def application(self, name: str) -> AsyncAiccApplicationResource:
        """Return the asynchronous sub-resource for one AI application, addressed by *name*."""
        return AsyncAiccApplicationResource(self._transport, name)

    def mcp_server(self, name: str) -> AsyncAiccMcpServerResource:
        """Return the asynchronous sub-resource for one MCP server, addressed by *name*."""
        return AsyncAiccMcpServerResource(self._transport, name)

    def identity(self, name: str) -> AsyncAiccIdentityResource:
        """Return the asynchronous sub-resource for one identity, addressed by *name*."""
        return AsyncAiccIdentityResource(self._transport, name)

    def model(self, name: str) -> AsyncAiccModelResource:
        """Return the asynchronous sub-resource for one AI model, addressed by *name*."""
        return AsyncAiccModelResource(self._transport, name)

    def agent(self, name: str) -> AsyncAiccAgentResource:
        """Return the asynchronous sub-resource for one AI agent, addressed by *name*."""
        return AsyncAiccAgentResource(self._transport, name)

    def extension(self, name: str) -> AsyncAiccExtensionResource:
        """Return the asynchronous sub-resource for one browser extension, addressed by *name*."""
        return AsyncAiccExtensionResource(self._transport, name)

    def data_protection(self, provider: str) -> AsyncAiccDataProtection:
        """Return the asynchronous data-protection sub-resource for one provider."""
        return AsyncAiccDataProtection(self._transport, provider)
