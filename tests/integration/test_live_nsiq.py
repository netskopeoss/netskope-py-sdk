"""Live integration tests for the NSIQ (Netskope Intelligence) API.

These tests require valid credentials and hit the real API.
Run with: pytest tests/integration/ -m integration -v

Credentials come from environment variables only (see conftest.py).

READ-ONLY by design: only the URL-lookup endpoint is exercised.  The
re-categorization and false-positive endpoints deliberately create review
tickets, so they are never submitted from the test suite.

``client.nsiq`` is not yet wired onto the client, so the resource is
instantiated directly against the client's transport.
"""

from __future__ import annotations

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError
from netskope.resources.nsiq import NsiqResource

from .conftest import skip_if_unavailable


@pytest.mark.integration
class TestNsiqIntegration:
    """Live read smokes for the NSIQ API."""

    def test_url_lookup(self, client: NetskopeClient) -> None:
        """Look up a well-known URL; skip when NSIQ is unlicensed."""
        nsiq = NsiqResource(client._transport)
        try:
            data = nsiq.url_lookup(["https://www.google.com"])
        except APIError as e:
            skip_if_unavailable(e, "NSIQ url lookup")
        else:
            assert isinstance(data, dict)
