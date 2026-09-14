"""The extensions sub-namespace of aicc."""

from __future__ import annotations

from netskope.core.transport import AsyncTransport, SyncTransport
from netskope.models.aicc import (
    AiccAssociatedIdentity,
    AiccDeployment,
    AiccDeploymentQuery,
    AiccDetail,
    AiccExtensionQuery,
    AiccExtensionRelatedQuery,
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
