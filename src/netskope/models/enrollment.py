"""Models for the Netskope Client Enrollment API.

Enrollment token sets are used by the Netskope Client to authenticate
devices during initial registration.  The gateway response schema
(``TokenSetResponse``) identifies a token set by ``tsid`` and carries the
authentication/encryption tokens plus enforcement metadata.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from netskope.models.common import NetskopeModel


class EnrollmentTokenSet(NetskopeModel):
    """An enrollment token set (gateway ``TokenSetResponse``).

    Example::

        for token_set in enrollment.list_token_sets():
            print(f"{token_set.id}: enforced={token_set.enforce_status}")
    """

    id: int | None = Field(default=None, alias="tsid")
    """Token Set ID (API field ``tsid``)."""

    created_date: datetime | None = None
    """When the token set was created."""

    auth_token: str | None = None
    """Authentication token."""

    encrypt_token: str | None = None
    """Encryption token (may be an empty string when not generated)."""

    valid_till: datetime | None = None
    """Expiry of the token set; ``None`` means no expiry."""

    enforce_status: int | None = None
    """Enforcement status: ``0`` for Not Enforced, ``1`` for Enforced."""

    name: str | None = None
    """Display name, when the API echoes it back (not in the gateway schema)."""

    max_devices: int | None = None
    """Maximum devices allowed to enroll, when echoed back by the API."""
