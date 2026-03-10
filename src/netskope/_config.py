"""Configuration and credential resolution for the Netskope SDK.

Credentials are resolved in priority order (boto3-style credential chain):

1. Explicit constructor parameters
2. Environment variables (``NETSKOPE_TENANT``, ``NETSKOPE_API_TOKEN``)
3. No implicit file-based config (explicit is better than implicit)
"""

from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass, field

from pydantic import SecretStr

_DEFAULT_TIMEOUT = 30.0
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BACKOFF_FACTOR = 0.5
_DEFAULT_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_VALID_TENANT_DOMAINS = (".goskope.com", ".netskope.com", ".boomskope.com")
_IP_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")


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
    api_token: SecretStr
    timeout: float = _DEFAULT_TIMEOUT
    max_retries: int = _DEFAULT_MAX_RETRIES
    backoff_factor: float = _DEFAULT_BACKOFF_FACTOR
    retry_on_status: frozenset[int] = field(default=_DEFAULT_RETRY_STATUSES)

    def __repr__(self) -> str:
        return (
            f"NetskopeConfig(tenant={self.tenant!r}, api_token=SecretStr('**********'), "
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
        allow_custom_tenant: bool = False,
    ) -> NetskopeConfig:
        """Build a config by merging explicit values with environment fallbacks.

        Args:
            allow_custom_tenant: If ``True``, skip domain validation for the
                tenant hostname.  Use this only when connecting to a known
                non-standard Netskope endpoint.

        Raises:
            netskope.exceptions.ValidationError: If a required value is
                missing from all sources, or if the tenant hostname fails
                validation.
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

        # Normalize: strip whitespace, protocol prefix, and trailing slashes.
        resolved_tenant = (
            resolved_tenant.strip().removeprefix("https://").removeprefix("http://").rstrip("/")
        )
        host = resolved_tenant

        # Block IP addresses (prevents SSRF to metadata services, RFC 1918, etc.)
        if _IP_RE.match(host):
            try:
                addr = ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                if addr.is_private or addr.is_loopback or addr.is_link_local:
                    raise ValidationError(
                        f"Tenant must be a hostname, not a private/link-local IP address: {host!r}"
                    )
                raise ValidationError(f"Tenant must be a hostname, not an IP address: {host!r}")

        # Require a recognized Netskope domain unless explicitly opted out.
        if not allow_custom_tenant and not any(host.endswith(d) for d in _VALID_TENANT_DOMAINS):
            raise ValidationError(
                f"Tenant {resolved_tenant!r} is not a recognized Netskope domain "
                f"(expected a hostname ending in {', '.join(_VALID_TENANT_DOMAINS)}). "
                "If this is intentional, pass allow_custom_tenant=True."
            )

        return cls(
            tenant=resolved_tenant,
            api_token=SecretStr(resolved_token),
            timeout=timeout,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            retry_on_status=retry_on_status or _DEFAULT_RETRY_STATUSES,
        )
