"""Shared request rules, acknowledgments, and admin records.

The administrative surface lives in ``platform/ms-platform.yaml``; the admin
user models here follow its ``SCIMUserDTO`` (:533-565) rather than the
core SCIM user the provisioning API returns.
"""

from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from netskope.models.common import NetskopeModel
from netskope.models.scim import ScimUser


class AdminRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        populate_by_name=True,
        revalidate_instances="always",
    )

    @model_validator(mode="after")
    def _omit_nulls(self) -> Self:
        if any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Omit optional fields instead of supplying null.")
        return self


class OperationStatus(NetskopeModel):
    """A write acknowledgment, without implying a follow-up detail read."""

    status: str | None = None


_NETSKOPE_USER_URN = "urn:ietf:params:scim:schemas:netskope:2.0:User"


class AdminRole(NetskopeModel):
    """The role an admin holds (``RoleDTO``, ms-platform.yaml:336-345)."""

    value: int | None = None
    display: str | None = None


class AdminApiAccessToken(NetskopeModel):
    """A service account's API token metadata (``TokenDetailsDTO``, :1229-1243).

    ``value`` is only populated when the platform returns the secret itself.
    """

    expires_on: datetime | None = Field(None, alias="expiresOn")
    issued_on: datetime | None = Field(None, alias="issuedOn")
    value: str | None = None


class AdminUserMetadata(NetskopeModel):
    """Admin record timestamps and self link (``SCIMUserMetadataDTO``, :566-581)."""

    created: datetime | None = None
    last_modified: datetime | None = Field(None, alias="lastModified")
    location: str | None = None


class AdminUserExtension(NetskopeModel):
    """The netskope SCIM extension (``NetskopeUserResponseSchemaDTO``, :182-229).

    Everything that distinguishes an admin from a provisioned user lives here:
    the role, whether the record is a person or a service account, and who
    provisioned it.
    """

    record_type: str | None = Field(None, alias="recordType")
    """``USER`` or ``SERVICE_ACCOUNT``."""

    provisioned_by: str | None = Field(None, alias="provisionedBy")
    """``LOCAL``, ``SCIM``, or ``SAML``."""

    role: AdminRole | None = None
    last_login: datetime | None = Field(None, alias="lastLogin")
    auth_type: str | None = Field(None, alias="authType")
    is_locked: bool | None = Field(None, alias="isLocked")
    is_verified: bool | None = Field(None, alias="isVerified")
    api_access_token: AdminApiAccessToken | None = Field(None, alias="apiAccessToken")


class AdminUser(ScimUser):
    """An administrator of the tenant (``SCIMUserDTO``, ms-platform.yaml:533-565).

    ``GET /api/v2/platform/administration/scim/Users`` returns a narrower
    record than the provisioning API: ``schemas``, ``id``, ``userName``,
    ``active``, ``externalId``, ``metadata``, and the netskope extension.  The
    ``display_name``, ``emails``, ``name``, and ``groups`` fields inherited
    from :class:`~netskope.models.scim.ScimUser` are never populated for an
    admin.

    Example::

        for admin in client.rbac.admins.list():
            print(f"{admin.user_name} {admin.record_type} {admin.role}")
    """

    metadata: AdminUserMetadata | None = None
    netskope_user: AdminUserExtension | None = Field(None, alias=_NETSKOPE_USER_URN)

    @property
    def record_type(self) -> str | None:
        """``USER`` or ``SERVICE_ACCOUNT``, from the netskope extension."""
        return None if self.netskope_user is None else self.netskope_user.record_type

    @property
    def provisioned_by(self) -> str | None:
        """``LOCAL``, ``SCIM``, or ``SAML``, from the netskope extension."""
        return None if self.netskope_user is None else self.netskope_user.provisioned_by

    @property
    def role(self) -> AdminRole | None:
        """The admin's role, from the netskope extension."""
        return None if self.netskope_user is None else self.netskope_user.role
