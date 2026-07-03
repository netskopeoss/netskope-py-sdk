"""Models for the Netskope User Management (read) API.

These models cover the ``/api/v2/users/getusers`` and
``/api/v2/users/getgroups`` query endpoints, which return richer read-only
data than SCIM (group membership, user counts, provisioner info).  For
provisioning CRUD, see :mod:`netskope.models.scim`.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from netskope.models.common import NetskopeModel


class UmUserAccount(NetskopeModel):
    """A per-tenant account entry within a User Management user record."""

    scim_id: str | None = Field(None, alias="scimId")
    user_name: str | None = Field(None, alias="userName")
    active: bool | None = None
    deleted: bool | None = None
    parent_groups: list[str] = Field(default_factory=list, alias="parentGroups")
    ou: str | None = None
    provisioner: str | None = None


class UmUser(NetskopeModel):
    """A user returned by the User Management query API.

    Example::

        users = UsersResource(client._transport)
        for user in users.list(limit=50):
            print(f"{user.id}: {user.primary_email}")
    """

    id: str | None = None
    given_name: str | None = Field(None, alias="givenName")
    family_name: str | None = Field(None, alias="familyName")
    emails: list[dict[str, Any] | str] = Field(default_factory=list)
    accounts: list[UmUserAccount] = Field(default_factory=list)

    @property
    def primary_email(self) -> str | None:
        """The primary email address for this user.

        The API returns ``emails`` either as a list of dicts (with ``value``
        and ``primary`` keys) or as a list of plain strings.  Returns the
        first entry marked ``primary``, falling back to the first entry.
        """
        for email in self.emails:
            if isinstance(email, dict) and email.get("primary"):
                value = email.get("value")
                if isinstance(value, str):
                    return value
        for email in self.emails:
            if isinstance(email, str):
                return email
            value = email.get("value")
            if isinstance(value, str):
                return value
        return None


class UmGroup(NetskopeModel):
    """A group returned by the User Management query API."""

    id: str | None = None
    scim_id: str | None = Field(None, alias="scimId")
    display_name: str | None = Field(None, alias="displayName")
    user_count: int | None = Field(None, alias="userCount")
    provisioner: str | None = None
    deleted: bool | None = None
