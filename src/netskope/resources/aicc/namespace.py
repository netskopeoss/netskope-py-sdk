"""The namespace sub-namespace of aicc."""

from __future__ import annotations

from netskope.core.transport import AsyncTransport, SyncTransport
from netskope.models.aicc import (
    AiccAgent,
    AiccAgentQuery,
    AiccApplication,
    AiccApplicationQuery,
    AiccDataCoverage,
    AiccIdentity,
    AiccIdentityQuery,
    AiccMcpQuery,
    AiccMcpServer,
    AiccModel,
    AiccModelQuery,
    AiccQuery,
)
from netskope.resources.aicc._shared import (
    _BASE,
)
from netskope.resources.aicc.agents import (
    AiccAgentResource,
    AsyncAiccAgentResource,
)
from netskope.resources.aicc.ai_models import (
    AiccModelResource,
    AsyncAiccModelResource,
)
from netskope.resources.aicc.analytics import (
    AiccAnalytics,
    AsyncAiccAnalytics,
)
from netskope.resources.aicc.applications import (
    AiccApplicationResource,
    AsyncAiccApplicationResource,
)
from netskope.resources.aicc.data_protection import (
    AiccDataProtection,
    AsyncAiccDataProtection,
)
from netskope.resources.aicc.extensions import (
    AiccExtensionResource,
    AsyncAiccExtensionResource,
)
from netskope.resources.aicc.identities import (
    AiccIdentityResource,
    AsyncAiccIdentityResource,
)
from netskope.resources.aicc.mcp_servers import (
    AiccMcpServerResource,
    AsyncAiccMcpServerResource,
)
from netskope.resources.shared.aicc_endpoint import (
    AiccCollection,
    AiccEndpoint,
    AiccRead,
    AsyncAiccCollection,
    AsyncAiccRead,
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
