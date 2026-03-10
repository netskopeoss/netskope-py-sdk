"""Netskope Python SDK — a modern, typed interface to the Netskope REST API v2.

Quick start::

    from netskope import NetskopeClient

    client = NetskopeClient(
        tenant="mycompany.goskope.com",
        api_token="your-api-token",
    )

    # List high-severity alerts
    for alert in client.alerts.list(query='severity eq "high"'):
        print(f"{alert.alert_name} — {alert.user}")

    # Manage URL lists
    client.url_lists.create("blocklist", ["malware.example.com"])
    client.url_lists.deploy()

    # SCIM user provisioning
    for user in client.scim.users.list():
        print(user.user_name)

For async usage::

    from netskope import AsyncNetskopeClient

    async with AsyncNetskopeClient(tenant="...", api_token="...") as client:
        async for alert in client.alerts.list():
            print(alert.alert_name)
"""

from netskope._client import AsyncNetskopeClient, NetskopeClient
from netskope._version import __version__
from netskope.exceptions import (
    APIError,
    AuthenticationError,
    ConflictError,
    ConnectionError,
    ForbiddenError,
    NetskopeError,
    NotFoundError,
    RateLimitError,
    ServerError,
    TimeoutError,
    ValidationError,
)

__all__ = [
    # Clients
    "NetskopeClient",
    "AsyncNetskopeClient",
    # Version
    "__version__",
    # Exceptions
    "NetskopeError",
    "APIError",
    "AuthenticationError",
    "ForbiddenError",
    "NotFoundError",
    "ConflictError",
    "RateLimitError",
    "ServerError",
    "ConnectionError",
    "TimeoutError",
    "ValidationError",
]
