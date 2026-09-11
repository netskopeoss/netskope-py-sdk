"""Models for the Netskope RBAC (Role-Based Access Control) API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from netskope.models.common import NetskopeModel


class _RoleRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        populate_by_name=True,
        revalidate_instances="always",
    )

    @model_validator(mode="after")
    def _reject_explicit_nulls(self) -> Self:
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null; omit it instead.")
        return self


class RoleScopeMatch(_RoleRequest):
    """Included or excluded scope values for one API-defined scope name."""

    included: list[str] | None = Field(None, alias="in")
    excluded: list[str] | None = Field(None, alias="!in")


class RoleConstraint(_RoleRequest):
    """Constraint settings on an API-group grant."""

    id: int = Field(alias="constraintId")
    values: list[str] = Field(alias="constraintValues")


class RoleObfuscation(_RoleRequest):
    """Obfuscation settings accepted with an API-group grant."""

    properties: list[str]
    enable_scope: bool = Field(alias="enableScope")
    scope: dict[str, RoleScopeMatch]


class ApiGroupGrant(_RoleRequest):
    """An explicit grant using the gateway's numeric API-group identifier.

    Permission values are ``none``, ``r``, ``rw``, and ``rwa``. This request
    type deliberately requires both the group ID and permission on patches.
    """

    api_group_id: int = Field(alias="apiGroupId")
    permission: Literal["none", "r", "rw", "rwa"]
    constraints: list[RoleConstraint] | None = None
    obfuscation: RoleObfuscation | None = None


class RoleIpAllowList(_RoleRequest):
    """IP allow-list input, whose entries are strings rather than detail objects."""

    enabled: bool = Field(alias="enableIpAllowList")
    ip_list: list[str] = Field(alias="ipList")


class RoleLabelAssignment(_RoleRequest):
    """A label permission accepted by role writes."""

    id: str
    permission: Literal["r", "rw"]


class RoleLabels(_RoleRequest):
    """Label assignments and optional read-all access."""

    assigned_labels: list[RoleLabelAssignment] = Field(alias="assignedLabels")
    read_all: bool | None = Field(None, alias="readAll")


class _RoleBody(_RoleRequest):
    scope: dict[str, RoleScopeMatch] | None = None
    ip_allow_list: RoleIpAllowList | None = Field(None, alias="ipAllowList")
    labels: RoleLabels | None = None

    @field_validator("name", check_fields=False)
    @classmethod
    def _nonempty_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("A role name cannot be blank.")
        return value

    @field_validator("api_groups", check_fields=False)
    @classmethod
    def _unique_groups(cls, value: list[ApiGroupGrant] | None) -> list[ApiGroupGrant] | None:
        if value is not None:
            ids = [grant.api_group_id for grant in value]
            if len(ids) != len(set(ids)):
                raise ValueError("API-group IDs must be unique within a request.")
        return value


class RoleCreate(_RoleBody):
    """A complete create request, using gateway aliases when serialized.

    The name, description, and grant list are required. An empty grant list
    is accepted for creation; unknown request fields and explicit nulls are not.
    """

    name: str = Field(alias="roleName")
    description: str = Field(alias="roleDescription")
    api_groups: list[ApiGroupGrant] = Field(alias="apiGroups")


class RolePatch(_RoleBody):
    """A partial role update. Only explicitly supplied fields are sent.

    Empty grant lists are rejected because their clearing semantics have not
    been verified. A grant with permission ``none`` remains valid.
    """

    name: str | None = Field(None, alias="roleName")
    description: str | None = Field(None, alias="roleDescription")
    api_groups: list[ApiGroupGrant] | None = Field(None, alias="apiGroups")

    @model_validator(mode="after")
    def _require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("A role patch requires at least one field.")
        if self.api_groups == []:
            raise ValueError("An empty apiGroups patch is not supported; clearing is unverified.")
        return self


class RoleMutationReceipt(NetskopeModel):
    """The write acknowledgment, not a complete role detail."""

    id: int = Field(alias="roleId")

    @field_validator("id", mode="before")
    @classmethod
    def _reject_boolean_id(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("A role identifier cannot be a boolean.")
        return value


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


class RbacRoleIpAddress(NetskopeModel):
    """An IP allow-list detail entry, including its API audit fields."""

    ip_address: str = Field(alias="ipAddress")
    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")


class RbacRoleIpAllowList(NetskopeModel):
    """IP restrictions returned in an RBAC role detail."""

    enabled: bool | None = Field(None, alias="enableIpAllowList")
    ip_list: list[str | RbacRoleIpAddress] = Field(default_factory=list, alias="ipList")


class RbacRoleSummary(NetskopeModel):
    """A role list record, retaining the list endpoint's field names."""

    id: int | None = Field(None, alias="roleId")
    name: str | None = None
    description: str | None = None
    type: int | None = None
    obfuscated: bool | None = None
    scoped: bool | None = None
    last_edited: datetime | None = Field(None, alias="lastEdited")
    created_by: str | None = Field(None, alias="createdBy")
    updated_by: str | None = Field(None, alias="updatedBy")
    alias_name: str | None = Field(None, alias="aliasName")
    user_count: int | None = Field(None, alias="userCount")


class RbacRoleDetail(NetskopeModel):
    """A role detail with typed API-group grants, scopes, and IP restrictions."""

    id: int | None = Field(None, alias="roleId")
    name: str | None = Field(None, alias="roleName")
    description: str | None = Field(None, alias="roleDescription")
    scopes: list[RbacRoleScope] = Field(default_factory=list)
    ip_allow_list: RbacRoleIpAllowList | None = Field(None, alias="ipAllowList")
    labels: dict[str, Any] | None = None
    api_groups: list[RbacRoleApiGroup] = Field(default_factory=list, alias="apiGroups")
    is_alias_name_taken: bool | None = Field(None, alias="isAliasNameTaken")

    @field_validator("id", mode="before")
    @classmethod
    def _reject_boolean_id(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("A role identifier cannot be a boolean.")
        return value


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
