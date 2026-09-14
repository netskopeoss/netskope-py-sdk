"""Models for the Netskope DNS Security profiles API."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from netskope.models.administration import AdminRequest
from netskope.models.common import NetskopeModel


class DnsProfileCreate(AdminRequest):
    """Create a DNS profile with the gateway's string-valued logging mode."""

    name: str = Field(min_length=1)
    description: str | None = None
    log_traffic: Literal["Blocked DNS", "All DNS"] | None = None


class DnsProfilePatch(AdminRequest):
    """Change only supplied profile fields. Empty description clears it."""

    name: str | None = Field(None, min_length=1)
    description: str | None = None
    log_traffic: Literal["Blocked DNS", "All DNS"] | None = None

    @model_validator(mode="after")
    def _require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Supply at least one profile field.")
        return self


class DnsInheritanceGroupCreate(AdminRequest):
    name: str = Field(min_length=1)
    description: str | None = None


class DnsInheritanceGroupPatch(AdminRequest):
    name: str | None = Field(None, min_length=1)
    description: str | None = None

    @model_validator(mode="after")
    def _require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Supply at least one inheritance-group field.")
        return self


class DnsDeployment(AdminRequest):
    ids: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    change_note: str


class DnsInheritanceGroupDeployment(AdminRequest):
    ids: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    change_note: str | None = None


class DnsReference(NetskopeModel):
    """An identifier/name entry from a DNS reference collection.

    ``DNSTunnel`` (``profiles/dns.yaml:13-27``), ``DNSDomainCategory``
    (``:38-184``) and ``DNSRecordType`` (``:195-216``) each declare ``id`` and
    ``name`` as plain optional properties with no ``required`` block, so a
    record that omits one is a valid answer and must not reject its whole page.
    ``category_type`` (``:179-184``, enum ``Security`` / ``Business``) is
    declared by ``DNSDomainCategory`` only and is absent from the other two.
    """

    id: str | int | None = None
    name: str | None = None
    category_type: str | None = None


class DnsProfile(NetskopeModel):
    """A DNS Security profile.

    DNS profiles define the security posture for DNS traffic inspection —
    rules for blocking, allowing, or alerting on DNS queries to specific
    domain categories or record types.

    Note:
        The API returns ``id`` as a UUID string (e.g.
        ``"7b3b9c98-7718-11f1-..."``), and ``log_traffic`` as a string enum
        (``"Blocked DNS"`` or ``"All DNS"``) rather than a boolean; both
        raw forms are preserved.

    Example::

        for profile in client.dns.list():
            print(f"{profile.id}: {profile.name}")
    """

    id: str | int | None = None
    name: str | None = None
    description: str | None = None
    log_traffic: str | bool | None = None


class DnsInheritanceGroup(NetskopeModel):
    """A DNS Security inheritance group.

    Inheritance groups organize DNS profiles into hierarchical structures so
    child profiles can inherit settings from a parent group.

    Note:
        ``id`` is a UUID string in API responses.

    Example::

        for group in client.dns.inheritance_groups.list():
            print(f"{group.id}: {group.name}")
    """

    id: str | int | None = None
    name: str | None = None
    description: str | None = None
