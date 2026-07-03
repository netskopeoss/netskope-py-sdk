"""Live integration tests for the Publishers API.

Read-only coverage per the safety checklist in ``tests/integration/conftest.py``:
no create/update/delete, no bulk upgrades, and no registration tokens are
exercised against live tenants.  Credentials come from environment variables
only (see the shared ``client`` fixture).

Run with: pytest tests/integration/test_live_publishers.py -m integration -v
"""

from __future__ import annotations

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError
from netskope.models.publishers import (
    Publisher,
    PublisherAlertsConfiguration,
    PublisherRelease,
)

from .conftest import skip_if_unavailable


@pytest.mark.integration
class TestPublishersIntegration:
    """Live, read-only tests for the Publishers API."""

    def test_list_publishers(self, client: NetskopeClient) -> None:
        """List publishers (capped at 10) and get typed responses."""
        try:
            publishers = client.publishers.list(page_size=10).to_list(max_items=10)
        except APIError as exc:
            skip_if_unavailable(exc, "Publishers API")
            return
        assert isinstance(publishers, list)
        assert len(publishers) <= 10
        if publishers:
            assert isinstance(publishers[0], Publisher)
            assert publishers[0].publisher_id is not None

    def test_list_releases(self, client: NetskopeClient) -> None:
        """List available publisher software releases."""
        try:
            releases = client.publishers.list_releases()
        except APIError as exc:
            skip_if_unavailable(exc, "Publisher releases API")
            return
        assert isinstance(releases, list)
        if releases:
            assert isinstance(releases[0], PublisherRelease)
            assert releases[0].version is not None

    def test_get_alerts_configuration(self, client: NetskopeClient) -> None:
        """Fetch the publisher alerts configuration (read-only)."""
        try:
            config = client.publishers.get_alerts_configuration()
        except APIError as exc:
            skip_if_unavailable(exc, "Publisher alerts configuration API")
            return
        assert isinstance(config, PublisherAlertsConfiguration)
        assert isinstance(config.admin_users, list)
        assert isinstance(config.event_types, list)
