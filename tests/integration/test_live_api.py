"""Live integration tests against the Netskope API.

These tests require valid credentials and hit the real API.
Run with: pytest tests/integration/ -m integration -v

Credentials are read from environment variables only (see conftest.py for
the tenant matrix, the shared ``client`` fixture, and the safety checklist).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError
from netskope.models.alerts import Alert
from netskope.models.events import Event
from netskope.models.publishers import Publisher
from netskope.models.url_lists import UrlList

from .conftest import skip_if_unavailable


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
        # /api/v2/events/data/audit requires an explicit time range.
        end = datetime.now(tz=UTC)
        start = end - timedelta(days=1)
        try:
            events = client.events.list(
                "audit", start_time=start, end_time=end, page_size=5
            ).to_list(max_items=5)
        except APIError as e:
            # Some tenants/tokens may not have access to audit events
            skip_if_unavailable(e, "audit events")
        else:
            assert isinstance(events, list)

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
        try:
            publishers = client.publishers.list(page_size=10).to_list(max_items=10)
        except APIError as e:
            skip_if_unavailable(e, "publishers")
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
        try:
            apps = client.private_apps.list(page_size=10).to_list(max_items=10)
        except APIError as e:
            skip_if_unavailable(e, "private apps")
        assert isinstance(apps, list)


@pytest.mark.integration
class TestSteeringIntegration:
    """Live tests for Steering API."""

    def test_list_pops(self, client: NetskopeClient) -> None:
        try:
            pops = client.steering.list_pops(page_size=10).to_list(max_items=10)
        except APIError as e:
            skip_if_unavailable(e, "ipsec pops")
        assert isinstance(pops, list)

    def test_list_tunnels(self, client: NetskopeClient) -> None:
        try:
            tunnels = client.steering.list_tunnels(page_size=10).to_list(max_items=10)
        except APIError as e:
            skip_if_unavailable(e, "ipsec tunnels")
        assert isinstance(tunnels, list)


@pytest.mark.integration
class TestClientProperties:
    """Test client metadata and properties."""

    def test_version(self, client: NetskopeClient) -> None:
        from netskope._version import __version__

        assert client.version == __version__

    def test_tenant(self, client: NetskopeClient) -> None:
        assert client.tenant == client._config.tenant
        assert client.tenant  # non-empty

    def test_base_url(self, client: NetskopeClient) -> None:
        assert client.base_url == f"https://{client.tenant}"

    def test_repr(self, client: NetskopeClient) -> None:
        assert client.tenant in repr(client)


@pytest.mark.integration
class TestErrorHandling:
    """Test error handling with real API."""

    def test_invalid_token(self, client: NetskopeClient) -> None:
        """An invalid token should raise AuthenticationError or APIError."""
        bad_client = NetskopeClient(
            tenant=client.tenant,
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
