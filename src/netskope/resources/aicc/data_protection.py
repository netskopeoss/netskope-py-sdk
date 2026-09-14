"""The data protection sub-namespace of aicc."""

from __future__ import annotations

from netskope.core.transport import AsyncTransport, SyncTransport
from netskope.exceptions import ValidationError
from netskope.models.aicc import (
    AiccProtectionQuery,
    AiccProtectionSummary,
    AiccProtectionViolation,
    AiccWindow,
)
from netskope.resources.aicc._shared import (
    _BASE,
)
from netskope.resources.shared.aicc_endpoint import (
    AiccCollection,
    AiccEndpoint,
    AiccRead,
    AsyncAiccCollection,
    AsyncAiccRead,
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
