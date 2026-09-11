"""Models for the Netskope SCIM (User/Group Provisioning) API."""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from netskope.models.common import NetskopeModel


class _ScimRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, revalidate_instances="always"
    )

    @model_validator(mode="after")
    def _omit_nulls(self) -> Self:
        if any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Omit optional SCIM fields instead of supplying null.")
        return self


class ScimUserCreate(_ScimRequest):
    """Provision one user with an explicit primary email and account state."""

    user_name: str = Field(min_length=1)
    email: str = Field(min_length=1)
    active: bool = True


class ScimUserPatch(_ScimRequest):
    """Replace named SCIM attributes, including tenant extension paths.

    JSON values retain their types. This model does not coerce a string such
    as ``"false"`` to an account-state boolean.
    """

    fields: dict[str, JsonValue] = Field(min_length=1)

    @field_validator("fields")
    @classmethod
    def _check_paths(cls, fields: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if any(not path.strip() for path in fields):
            raise ValueError("SCIM replacement paths cannot be blank.")
        return fields


class ScimGroupCreate(_ScimRequest):
    """Provision a group, optionally with explicit initial member IDs."""

    display_name: str = Field(min_length=1)
    member_ids: list[str] | None = None


class ScimGroupPatch(_ScimRequest):
    """Replace a name or the entire member list; an empty list clears it."""

    display_name: str | None = Field(None, min_length=1)
    member_ids: list[str] | None = None

    @model_validator(mode="after")
    def _require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Supply a display name or member list.")
        return self


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
    """Always empty against this API: neither ``GET /Users`` (scim-apis.yaml:1029-1189)
    nor ``GET /Users/{id}`` (:1711-1860) declares a ``groups`` property. Read group
    membership from ``client.scim.groups.get(gid, attributes="members")`` instead."""

    external_id: str | None = Field(None, alias="externalId")
    schemas: list[str] = Field(default_factory=list)


class ScimGroupMember(NetskopeModel):
    """A member reference inside a SCIM group."""

    value: str | None = None
    display: str | None = None


class ScimGroup(NetskopeModel):
    """A SCIM-provisioned group.

    ``members`` is empty unless the read asked for it: the group endpoints
    exclude members by default (scim-apis.yaml:462).

    Example::

        group = client.scim.groups.get("grp-1", attributes="members")
        print(f"{group.display_name}: {len(group.members)} members")
    """

    id: str | None = None
    display_name: str | None = Field(None, alias="displayName")
    members: list[ScimGroupMember] = Field(default_factory=list)
    schemas: list[str] = Field(default_factory=list)
    external_id: str | None = Field(None, alias="externalId")
