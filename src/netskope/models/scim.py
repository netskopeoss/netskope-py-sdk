"""Models for the Netskope SCIM (User/Group Provisioning) API."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from netskope.models.common import NetskopeModel


class ScimEmail(NetskopeModel):
    """A SCIM email address entry."""

    value: str | None = None
    primary: bool | None = None
    type: str | None = None


class ScimUser(NetskopeModel):
    """A SCIM-provisioned user.

    Example::

        for user in client.scim.users.list():
            print(f"{user.user_name} active={user.active}")
    """

    id: str | None = None
    user_name: str | None = Field(None, alias="userName")
    display_name: str | None = Field(None, alias="displayName")
    active: bool | None = None
    emails: list[ScimEmail] = Field(default_factory=list)
    name: dict[str, Any] | None = None
    groups: list[dict[str, Any]] = Field(default_factory=list)
    external_id: str | None = Field(None, alias="externalId")
    schemas: list[str] = Field(default_factory=list)


class ScimGroupMember(NetskopeModel):
    """A member reference inside a SCIM group."""

    value: str | None = None
    display: str | None = None


class ScimGroup(NetskopeModel):
    """A SCIM-provisioned group.

    Example::

        for group in client.scim.groups.list():
            print(f"{group.display_name}: {len(group.members)} members")
    """

    id: str | None = None
    display_name: str | None = Field(None, alias="displayName")
    members: list[ScimGroupMember] = Field(default_factory=list)
    schemas: list[str] = Field(default_factory=list)
    external_id: str | None = Field(None, alias="externalId")
