"""Live integration tests for the IPS (Intrusion Prevention System) API.

These tests require valid credentials and hit the real API.
Run with: pytest tests/integration/ -m integration -v

Credentials come from environment variables only (see conftest.py).

``client.ips`` is not wired onto the client, so these tests drive the
resource directly via ``IpsResource(client._transport)``.  Every test is a
READ-ONLY smoke — nothing is added to the allowlist or otherwise mutated on
the live tenant.  Unlicensed/unavailable tenants skip rather than fail.
"""

from __future__ import annotations

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError
from netskope.resources.ips import IpsResource

from .conftest import skip_if_unavailable


@pytest.mark.integration
class TestIpsIntegration:
    """Live read-only smokes for the IPS API."""

    def test_status(self, client: NetskopeClient) -> None:
        """Fetch IPS feature status; skip when IPS is unlicensed."""
        ips = IpsResource(client._transport)
        try:
            body = ips.status()
        except APIError as e:
            skip_if_unavailable(e, "IPS status")
        else:
            assert isinstance(body, dict)

    def test_list_allowlist(self, client: NetskopeClient) -> None:
        """Fetch the IPS allowlist; skip when IPS is unavailable."""
        ips = IpsResource(client._transport)
        try:
            body = ips.list_allowlist()
        except APIError as e:
            skip_if_unavailable(e, "IPS allowlist")
        else:
            assert isinstance(body, dict)

    def test_list_signatures(self, client: NetskopeClient) -> None:
        """Fetch a page of IPS signature references; skip when unavailable."""
        ips = IpsResource(client._transport)
        try:
            body = ips.list_signatures(limit=5)
        except APIError as e:
            skip_if_unavailable(e, "IPS signature reference list")
        else:
            assert isinstance(body, dict)
