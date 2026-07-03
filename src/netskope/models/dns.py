"""Models for the Netskope DNS Security profiles API."""

from __future__ import annotations

from netskope.models.common import NetskopeModel


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
