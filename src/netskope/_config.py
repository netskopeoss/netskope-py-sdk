"""Configuration and credential resolution for the Netskope SDK.

Credentials are resolved in priority order (boto3-style credential chain):

1. Explicit constructor parameters
2. Environment variables (``NETSKOPE_TENANT``, ``NETSKOPE_API_TOKEN``)
3. No implicit file-based config (explicit is better than implicit)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

_DEFAULT_TIMEOUT = 30.0
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BACKOFF_FACTOR = 0.5
_DEFAULT_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class NetskopeConfig:
    """Immutable configuration for a Netskope SDK client.

    Args:
        tenant: The Netskope tenant hostname (e.g. ``"mycompany.goskope.com"``).
            Falls back to the ``NETSKOPE_TENANT`` environment variable.
        api_token: A Netskope REST API v2 token. Falls back to the
            ``NETSKOPE_API_TOKEN`` environment variable.
        timeout: HTTP request timeout in seconds.
        max_retries: Maximum number of automatic retries for transient errors.
        backoff_factor: Base multiplier for exponential backoff between retries.
        retry_on_status: HTTP status codes that trigger an automatic retry.

    Raises:
        netskope.exceptions.ValidationError: If *tenant* or *api_token*
            cannot be resolved from any source.
    """

    tenant: str
    api_token: str
    timeout: float = _DEFAULT_TIMEOUT
    max_retries: int = _DEFAULT_MAX_RETRIES
    backoff_factor: float = _DEFAULT_BACKOFF_FACTOR
    retry_on_status: frozenset[int] = field(default=_DEFAULT_RETRY_STATUSES)

    def __repr__(self) -> str:
        return (
            f"NetskopeConfig(tenant={self.tenant!r}, api_token='***', "
            f"timeout={self.timeout}, max_retries={self.max_retries})"
        )

    @property
    def base_url(self) -> str:
        """The fully-qualified API base URL for this tenant."""
        host = self.tenant
        if not host.startswith("https://"):
            host = f"https://{host}"
        return host.rstrip("/")

    @classmethod
    def resolve(
        cls,
        *,
        tenant: str | None = None,
        api_token: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        backoff_factor: float = _DEFAULT_BACKOFF_FACTOR,
        retry_on_status: frozenset[int] | None = None,
    ) -> NetskopeConfig:
        """Build a config by merging explicit values with environment fallbacks.

        Raises:
            netskope.exceptions.ValidationError: If a required value is
                missing from all sources.
        """
        from netskope.exceptions import ValidationError

        resolved_tenant = tenant or os.environ.get("NETSKOPE_TENANT")
        resolved_token = api_token or os.environ.get("NETSKOPE_API_TOKEN")

        if not resolved_tenant:
            raise ValidationError(
                "A Netskope tenant is required. Pass tenant='mycompany.goskope.com' "
                "or set the NETSKOPE_TENANT environment variable."
            )
        if not resolved_token:
            raise ValidationError(
                "An API token is required. Pass api_token='...' "
                "or set the NETSKOPE_API_TOKEN environment variable."
            )

        import warnings
        _known = (".goskope.com", ".netskope.com")
        if not any(resolved_tenant.endswith(d) for d in _known):
            warnings.warn(
                f"Tenant {resolved_tenant!r} is not a recognized Netskope domain",
                stacklevel=2,
            )

        return cls(
            tenant=resolved_tenant,
            api_token=resolved_token,
            timeout=timeout,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            retry_on_status=retry_on_status or _DEFAULT_RETRY_STATUSES,
        )
