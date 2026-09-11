"""Models for the Netskope API Token Management API (``/api/v2/auth/tokens``)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from netskope.models.administration import AdminRequest
from netskope.models.common import NetskopeModel


class ApiTokenGrant(AdminRequest):
    """An endpoint permission, explicitly read-only or read/write."""

    endpoint: str = Field(min_length=1)
    permissions: Literal["r", "rw"]


class ApiTokenWrite(AdminRequest):
    """Complete token metadata required for create and ordinary PATCH.

    Expiration is explicit Unix-epoch seconds. Grants replace the complete
    scope list; partial metadata updates and empty grant clearing are not
    inferred by this contract.
    """

    name: str = Field(min_length=1)
    expires: int = Field(ge=0)
    endpoints: list[ApiTokenGrant] = Field(min_length=1)


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
