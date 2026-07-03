"""Models for the Netskope API Token Management API (``/api/v2/auth/tokens``)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from netskope.models.common import NetskopeModel


class TokenPermission(StrEnum):
    """Permission level an API token holds for an endpoint scope."""

    READ = "r"
    READ_WRITE = "rw"


class ApiTokenEndpoint(NetskopeModel):
    """A single endpoint scope granted to an API token.

    Example::

        ApiTokenEndpoint(endpoint="/api/v2/events", permissions="r")
    """

    endpoint: str
    permissions: str  # "r" or "rw"


class ApiToken(NetskopeModel):
    """A Netskope REST API v2 token.

    .. warning::
        The :attr:`token` secret is returned by the API exactly once — in the
        response to :meth:`~netskope.resources.tokens.TokensResource.create`
        (and to a ``reissue``).  Store it securely immediately; it cannot be
        retrieved again, and it is never printed by the SDK.  ``list``, ``get``,
        and plain updates return ``token=None``.

    Example::

        created = tokens.create(
            "ci-token", ["/api/v2/events"], expires=1767225600
        )
        secret = created.token  # present exactly once — store securely
    """

    id: str | None = None
    name: str | None = None
    expires: int | None = None
    """Expiry as seconds since the Unix epoch."""
    endpoints: list[ApiTokenEndpoint] = Field(default_factory=list)
    token: str | None = None
    """The token secret. Only present on create/reissue responses — see warning above."""
