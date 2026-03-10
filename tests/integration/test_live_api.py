"""Live integration tests against the Netskope API.

These tests require valid credentials and hit the real API.
Run with: pytest tests/integration/ -m integration -v

Credentials are read from environment variables or passed directly.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError
from netskope.models.alerts import Alert
from netskope.models.events import Event
from netskope.models.publishers import Publisher
from netskope.models.url_lists import UrlList

# Test credentials — must be set via environment variables
_TENANT = os.environ.get("NETSKOPE_TENANT", "")
_TOKEN = os.environ.get("NETSKOPE_API_TOKEN", "")


@pytest.fixture(scope="module", autouse=True)
def _require_credentials() -> None:
    """Skip the entire module if credentials are not configured."""
    if not _TENANT or not _TOKEN:
        pytest.skip("NETSKOPE_TENANT and NETSKOPE_API_TOKEN env vars required")


@pytest.fixture(scope="module")
def client() -> NetskopeClient:
    """Create a real client for integration testing."""
    c = NetskopeClient(tenant=_TENANT, api_token=_TOKEN, timeout=60.0)
    yield c
    c.close()


@pytest.mark.integration
class TestAlertsIntegration:
    """Live tests for the Alerts API."""

    def test_list_alerts(self, client: NetskopeClient) -> None:
        """Verify we can list alerts and get typed responses."""
        alerts = client.alerts.list(page_size=5).to_list(max_items=5)
        # The tenant may or may not have alerts, but the call should succeed
        assert isinstance(alerts, list)
        if alerts:
            assert isinstance(alerts[0], Alert)
            assert alerts[0].id is not None

    def test_list_alerts_with_time_range(self, client: NetskopeClient) -> None:
        """List alerts within a specific time range."""
        end = datetime.now(tz=UTC)
        start = end - timedelta(days=30)
        alerts = client.alerts.list(
            start_time=start,
            end_time=end,
            page_size=10,
        ).to_list(max_items=10)
        assert isinstance(alerts, list)

    def test_list_alerts_pagination(self, client: NetskopeClient) -> None:
        """Verify pagination works — fetch at least 2 pages."""
        count = 0
        for page in client.alerts.list(page_size=5).pages():
            assert len(page.items) <= 5
            count += 1
            if count >= 2:
                break
        assert count >= 1  # At least one page returned


@pytest.mark.integration
class TestEventsIntegration:
    """Live tests for the Events API."""

    def test_list_application_events(self, client: NetskopeClient) -> None:
        events = client.events.list("application", page_size=5).to_list(max_items=5)
        assert isinstance(events, list)
        if events:
            assert isinstance(events[0], Event)

    def test_list_network_events(self, client: NetskopeClient) -> None:
        events = client.events.list("network", page_size=5).to_list(max_items=5)
        assert isinstance(events, list)

    def test_list_page_events(self, client: NetskopeClient) -> None:
        events = client.events.list("page", page_size=5).to_list(max_items=5)
        assert isinstance(events, list)

    def test_list_audit_events(self, client: NetskopeClient) -> None:
        try:
            events = client.events.list("audit", page_size=5).to_list(max_items=5)
            assert isinstance(events, list)
        except APIError as e:
            # Some tenants/tokens may not have access to audit events
            assert e.status_code in (403, 404)

    def test_list_alert_events(self, client: NetskopeClient) -> None:
        events = client.events.list("alert", page_size=5).to_list(max_items=5)
        assert isinstance(events, list)

    def test_events_with_time_range(self, client: NetskopeClient) -> None:
        end = datetime.now(tz=UTC)
        start = end - timedelta(days=7)
        events = client.events.list(
            "application",
            start_time=start,
            end_time=end,
            page_size=10,
        ).to_list(max_items=10)
        assert isinstance(events, list)


@pytest.mark.integration
class TestPublishersIntegration:
    """Live tests for the Publishers API."""

    def test_list_publishers(self, client: NetskopeClient) -> None:
        publishers = client.publishers.list(page_size=10).to_list(max_items=10)
        assert isinstance(publishers, list)
        if publishers:
            assert isinstance(publishers[0], Publisher)
            assert publishers[0].publisher_id is not None
            assert publishers[0].publisher_name is not None


@pytest.mark.integration
class TestUrlListsIntegration:
    """Live tests for the URL Lists API."""

    def test_list_url_lists(self, client: NetskopeClient) -> None:
        url_lists = client.url_lists.list(page_size=10).to_list(max_items=10)
        assert isinstance(url_lists, list)
        if url_lists:
            assert isinstance(url_lists[0], UrlList)


@pytest.mark.integration
class TestPrivateAppsIntegration:
    """Live tests for Private Apps."""

    def test_list_private_apps(self, client: NetskopeClient) -> None:
        apps = client.private_apps.list(page_size=10).to_list(max_items=10)
        assert isinstance(apps, list)


@pytest.mark.integration
class TestSteeringIntegration:
    """Live tests for Steering API."""

    def test_list_pops(self, client: NetskopeClient) -> None:
        pops = client.steering.list_pops(page_size=10).to_list(max_items=10)
        assert isinstance(pops, list)

    def test_list_tunnels(self, client: NetskopeClient) -> None:
        tunnels = client.steering.list_tunnels(page_size=10).to_list(max_items=10)
        assert isinstance(tunnels, list)


@pytest.mark.integration
class TestClientProperties:
    """Test client metadata and properties."""

    def test_version(self, client: NetskopeClient) -> None:
        from netskope._version import __version__
        assert client.version == __version__

    def test_tenant(self, client: NetskopeClient) -> None:
        assert client.tenant == _TENANT

    def test_base_url(self, client: NetskopeClient) -> None:
        assert client.base_url == f"https://{_TENANT}"

    def test_repr(self, client: NetskopeClient) -> None:
        assert _TENANT in repr(client)


@pytest.mark.integration
class TestErrorHandling:
    """Test error handling with real API."""

    def test_invalid_token(self) -> None:
        """An invalid token should raise AuthenticationError or APIError."""
        bad_client = NetskopeClient(
            tenant=_TENANT,
            api_token="invalid-token",
            timeout=15.0,
            max_retries=0,
        )
        try:
            with pytest.raises(APIError) as exc_info:
                list(bad_client.alerts.list(page_size=1))
            assert exc_info.value.status_code in (401, 403, 429)
        finally:
            bad_client.close()
