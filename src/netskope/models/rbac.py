"""Models for the Netskope RBAC (Role-Based Access Control) API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from netskope.models.common import NetskopeModel


class RbacRoleApiGroup(NetskopeModel):
    """Per-API-group permission entry on an RBAC role.

    Mirrors the gateway ``ApiGroupsDto`` schema: each entry grants a
    permission level (``none``, ``r``, ``rw``, ``rwa``) on one API group.
    """

    api_group_id: int | None = Field(None, alias="apiGroupId")
    api_group_name: str | None = Field(None, alias="apiGroupName")
    permission: str | None = None
    obfuscations: list[dict[str, Any]] = Field(default_factory=list)
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    obfuscation_scope: dict[str, Any] | None = Field(None, alias="obfuscationScope")


class RbacRoleScope(NetskopeModel):
    """A scope entry restricting the data an RBAC role can see."""

    scope_field_id: int | None = Field(None, alias="scopeFieldId")
    scope_field_name: str | None = Field(None, alias="scopeFieldName")
    scope_value: str | None = Field(None, alias="scopeValue")
    excluded: bool | None = None
    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")


class RbacRole(NetskopeModel):
    """An RBAC role.

    Covers both response shapes the API uses: the list endpoint returns
    ``RoleViewDto`` items (``roleId``, ``name``, ``type``, ``obfuscated``,
    ``scoped``, ``description``, audit fields) while the detail endpoint
    returns ``GetRoleResponseDTO`` (``roleId``, ``roleName``,
    ``roleDescription``, ``scopes``, ``ipAllowList``, ``apiGroups``).
    Fields absent from a given shape are simply ``None`` / empty.

    Example::

        for role in client.rbac.roles.list():
            print(f"{role.id}: {role.name}")
    """

    id: int | None = Field(None, alias="roleId")
    # The list endpoint uses "name"/"description"; the detail endpoint uses
    # "roleName"/"roleDescription".  populate_by_name accepts both.
    name: str | None = Field(None, alias="roleName")
    description: str | None = Field(None, alias="roleDescription")
    type: int | None = None  # 1 = predefined, 0 = custom
    obfuscated: bool | None = None
    scoped: bool | None = None
    last_edited: datetime | None = Field(None, alias="lastEdited")
    created_by: str | None = Field(None, alias="createdBy")
    updated_by: str | None = Field(None, alias="updatedBy")
    alias_name: str | None = Field(None, alias="aliasName")
    user_count: int | None = Field(None, alias="userCount")
    scopes: list[RbacRoleScope] = Field(default_factory=list)
    ip_allow_list: dict[str, Any] | None = Field(None, alias="ipAllowList")
    labels: dict[str, Any] | None = None
    api_groups: list[RbacRoleApiGroup] = Field(default_factory=list, alias="apiGroups")
    is_alias_name_taken: bool | None = Field(None, alias="isAliasNameTaken")
