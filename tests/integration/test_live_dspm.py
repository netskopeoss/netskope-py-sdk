"""Live integration tests for the DSPM (Data Security Posture Management) API.

These tests require valid credentials and hit the real API.
Run with: pytest tests/integration/ -m integration -v

Credentials come from environment variables only (see conftest.py).

READ-ONLY smokes only: this module never connects or scans datastores.  DSPM
is a separately licensed feature, so every call is wrapped in
``skip_if_unavailable`` — tenants without DSPM skip rather than fail.

DSPM is not yet wired onto the client, so the resource is built directly from
the client's transport.
"""

from __future__ import annotations

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError
from netskope.resources.dspm import DspmResource

from .conftest import skip_if_unavailable


@pytest.mark.integration
class TestDspmIntegration:
    """Live read-only smokes for the DSPM API."""

    def test_list_databases(self, client: NetskopeClient) -> None:
        """List databases; skip when DSPM is unlicensed/unavailable."""
        dspm = DspmResource(client._transport)
        try:
            data = dspm.list_resources("databases", limit=5)
        except APIError as e:
            skip_if_unavailable(e, "DSPM list_resources(databases)")
        else:
            assert isinstance(data, dict)

    def test_list_connected_datastores(self, client: NetskopeClient) -> None:
        """List connected datastores; skip when DSPM is unavailable."""
        dspm = DspmResource(client._transport)
        try:
            data = dspm.list_resources("connected_datastores", limit=5)
        except APIError as e:
            skip_if_unavailable(e, "DSPM list_resources(connected_datastores)")
        else:
            assert isinstance(data, dict)

    def test_analytics_summary(self, client: NetskopeClient) -> None:
        """Fetch a plausible analytics metric; skip when unavailable."""
        dspm = DspmResource(client._transport)
        try:
            data = dspm.analytics("summary")
        except APIError as e:
            skip_if_unavailable(e, "DSPM analytics(summary)")
        else:
            assert isinstance(data, dict)
