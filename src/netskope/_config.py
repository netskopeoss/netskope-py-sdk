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

# Environment variables checked (in order) for a CA bundle path.
_CA_BUNDLE_ENV_VARS = (
    "NETSKOPE_CA_BUNDLE",
    "REQUESTS_CA_BUNDLE",
    "SSL_CERT_FILE",
    "CURL_CA_BUNDLE",
)

# Well-known locations where the Netskope client installs its CA certificate.
_NETSKOPE_CA_CERT_PATHS = (
    "/Library/Application Support/Netskope/STAgent/data/nscacert.pem",
    "/Library/Application Support/Netskope/STAgent/data/nscacert_combined.pem",
    "/opt/netskope/stagent/nsca/nscacert.pem",
    "/opt/netskope/stagent/nsca/nscacert_combined.pem",
    r"C:\ProgramData\Netskope\STAgent\data\nscacert.pem",
    r"C:\ProgramData\Netskope\STAgent\data\nscacert_combined.pem",
)


def find_netskope_ca_cert() -> str | None:
    """Locate the Netskope client CA certificate on this machine, if present.

    Checks the well-known install locations used by the Netskope steering
    agent on macOS, Linux, and Windows. Useful when your traffic passes
    through Netskope SSL inspection and you need a CA bundle that trusts
    the re-signed certificates::

        from netskope import NetskopeClient, find_netskope_ca_cert

        client = NetskopeClient(verify=find_netskope_ca_cert() or True)

    Returns:
        The first existing certificate path, or ``None`` if none exist.
    """
    for path in _NETSKOPE_CA_CERT_PATHS:
        if os.path.isfile(path):
            return path
    return None


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
        verify: TLS verification setting. ``True`` (default) verifies against
            the system trust store, ``False`` disables verification, and a
            string is treated as the path to a custom CA bundle file (e.g. the
            Netskope client certificate — see :func:`find_netskope_ca_cert`).
            Falls back to the ``NETSKOPE_CA_BUNDLE``, ``REQUESTS_CA_BUNDLE``,
            ``SSL_CERT_FILE``, or ``CURL_CA_BUNDLE`` environment variables.

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
    verify: bool | str = True

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
        verify: bool | str = True,
    ) -> NetskopeConfig:
        """Build a config by merging explicit values with environment fallbacks.

        Args:
            allow_custom_tenant: If ``True``, skip domain validation for the
                tenant hostname.  Use this only when connecting to a known
                non-standard Netskope endpoint.
            verify: TLS verification: ``True``, ``False``, or a CA bundle
                path.  An explicit non-default value wins; otherwise the
                ``NETSKOPE_CA_BUNDLE``, ``REQUESTS_CA_BUNDLE``,
                ``SSL_CERT_FILE``, and ``CURL_CA_BUNDLE`` environment
                variables are consulted (first non-empty wins).

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

        # Resolve TLS verification: explicit non-default value wins, then the
        # CA-bundle environment variable chain, then the default (True).
        resolved_verify: bool | str = verify
        if resolved_verify is True:
            for env_var in _CA_BUNDLE_ENV_VARS:
                env_value = os.environ.get(env_var)
                if env_value:
                    resolved_verify = env_value
                    break

        if isinstance(resolved_verify, str) and not os.path.isfile(resolved_verify):
            raise ValidationError(
                f"CA bundle file not found: {resolved_verify!r}. "
                "Pass verify=<path> with a valid certificate bundle, or use "
                "netskope.find_netskope_ca_cert() to locate the Netskope client "
                "certificate if your traffic passes through Netskope SSL inspection."
            )

        return cls(
            tenant=resolved_tenant,
            api_token=SecretStr(resolved_token),
            timeout=timeout,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            retry_on_status=retry_on_status or _DEFAULT_RETRY_STATUSES,
            verify=resolved_verify,
        )
