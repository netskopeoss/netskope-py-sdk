"""Live integration tests for the DNS Security profiles API.

Follows the safety checklist in ``tests/integration/conftest.py``: test
objects use the ``sdk-inttest-`` prefix, every create has a guaranteed
delete, and unavailable APIs skip rather than fail.  Deploy endpoints are
never called — deploys are tenant-wide and excluded from the test suite.
"""

from __future__ import annotations

import contextlib

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError, NotFoundError
from netskope.models.dns import DnsInheritanceGroup, DnsProfile

from .conftest import skip_if_unavailable, unique_name


@pytest.mark.integration
class TestDnsProfilesIntegration:
    """Live tests for DNS Security profiles."""

    def test_list_profiles(self, client: NetskopeClient) -> None:
        """Read smoke: listing profiles succeeds and yields typed models."""
        try:
            profiles = client.dns.list(page_size=10).to_list(max_items=10)
        except APIError as e:
            skip_if_unavailable(e, "DNS profiles")
        else:
            assert isinstance(profiles, list)
            if profiles:
                assert isinstance(profiles[0], DnsProfile)

    def test_list_record_types(self, client: NetskopeClient) -> None:
        """Read smoke: record type reference data is retrievable."""
        try:
            body = client.dns.list_record_types(limit=10)
        except APIError as e:
            skip_if_unavailable(e, "DNS record types")
        else:
            assert isinstance(body, dict)

    def test_profile_write_cycle(self, client: NetskopeClient) -> None:
        """Create → get → update → delete a DNS profile."""
        name = unique_name("dnsprofile")
        try:
            created = client.dns.create(name)
        except APIError as e:
            skip_if_unavailable(e, "DNS profiles")
            return
        assert created.id is not None
        try:
            fetched = client.dns.get(created.id)
            assert fetched.id == created.id
            assert fetched.name == name

            updated = client.dns.update(created.id, description="sdk-inttest description")
            assert updated.id == created.id
        finally:
            with contextlib.suppress(NotFoundError):
                client.dns.delete(created.id)


@pytest.mark.integration
class TestDnsInheritanceGroupsIntegration:
    """Live tests for DNS inheritance groups."""

    def test_group_write_cycle(self, client: NetskopeClient) -> None:
        """Create → get → update → delete an inheritance group."""
        name = unique_name("dnsgroup")
        try:
            created = client.dns.inheritance_groups.create(name)
        except APIError as e:
            skip_if_unavailable(e, "DNS inheritance groups")
            return
        assert created.id is not None
        try:
            fetched = client.dns.inheritance_groups.get(created.id)
            assert isinstance(fetched, DnsInheritanceGroup)
            assert fetched.id == created.id
            assert fetched.name == name

            updated = client.dns.inheritance_groups.update(
                created.id, description="sdk-inttest description"
            )
            assert updated.id == created.id
        finally:
            with contextlib.suppress(NotFoundError):
                client.dns.inheritance_groups.delete(created.id)
