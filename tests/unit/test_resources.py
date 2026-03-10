"""Tests for resource classes with mocked HTTP."""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import NetskopeClient
from netskope.exceptions import NotFoundError
from netskope.models.alerts import Alert
from netskope.models.publishers import Publisher
from netskope.models.url_lists import UrlList


class TestAlertsResource:
    """Tests for client.alerts."""

    @respx.mock
    def test_list_returns_alerts(self) -> None:
        respx.get("https://t.goskope.com/api/v2/events/datasearch/alert").mock(
            return_value=httpx.Response(
                200,
                json={
                    "result": [
                        {"_id": "a1", "alert_name": "Test Alert", "severity_level": "high"},
                        {"_id": "a2", "alert_name": "Alert 2", "severity_level": "low"},
                    ],
                    "status": {"total": 2},
                },
            )
        )
        client = NetskopeClient(tenant="t.goskope.com", api_token="tok")
        alerts = list(client.alerts.list())
        assert len(alerts) == 2
        assert isinstance(alerts[0], Alert)
        assert alerts[0].alert_name == "Test Alert"
        client.close()

    @respx.mock
    def test_list_with_query(self) -> None:
        route = respx.get("https://t.goskope.com/api/v2/events/datasearch/alert").mock(
            return_value=httpx.Response(200, json={"result": [], "status": {"total": 0}})
        )
        client = NetskopeClient(tenant="t.goskope.com", api_token="tok")
        list(client.alerts.list(query='severity eq "high"'))
        url = str(route.calls[0].request.url)
        assert "query=" in url
        client.close()

    @respx.mock
    def test_get_alert(self) -> None:
        respx.get("https://t.goskope.com/api/v2/events/datasearch/alert").mock(
            return_value=httpx.Response(
                200,
                json={
                    "result": [{"_id": "abc", "alert_name": "Found"}],
                },
            )
        )
        client = NetskopeClient(tenant="t.goskope.com", api_token="tok")
        alert = client.alerts.get("abc")
        assert alert.id == "abc"
        assert alert.alert_name == "Found"
        client.close()

    @respx.mock
    def test_get_alert_not_found(self) -> None:
        respx.get("https://t.goskope.com/api/v2/events/datasearch/alert").mock(
            return_value=httpx.Response(200, json={"result": []})
        )
        client = NetskopeClient(tenant="t.goskope.com", api_token="tok")
        with pytest.raises(NotFoundError):
            client.alerts.get("nonexistent")
        client.close()


class TestEventsResource:
    """Tests for client.events."""

    @respx.mock
    def test_list_application_events(self) -> None:
        respx.get("https://t.goskope.com/api/v2/events/datasearch/application").mock(
            return_value=httpx.Response(
                200,
                json={
                    "result": [{"_id": "e1", "user": "alice@ex.com", "app": "Slack"}],
                    "status": {"total": 1},
                },
            )
        )
        client = NetskopeClient(tenant="t.goskope.com", api_token="tok")
        events = list(client.events.list("application"))
        assert len(events) == 1
        assert events[0].app == "Slack"
        client.close()

    @respx.mock
    def test_list_network_events(self) -> None:
        respx.get("https://t.goskope.com/api/v2/events/datasearch/network").mock(
            return_value=httpx.Response(
                200,
                json={
                    "result": [{"_id": "n1", "src_ip": "10.0.0.1", "dst_ip": "8.8.8.8"}],
                    "status": {"total": 1},
                },
            )
        )
        client = NetskopeClient(tenant="t.goskope.com", api_token="tok")
        events = list(client.events.list("network"))
        assert len(events) == 1
        assert events[0].src_ip == "10.0.0.1"  # type: ignore[attr-defined]
        client.close()


class TestUrlListsResource:
    """Tests for client.url_lists."""

    @respx.mock
    def test_list(self) -> None:
        respx.get("https://t.goskope.com/api/v2/policy/urllist").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "urllists": [
                            {"id": 1, "name": "Block", "urls": ["bad.com"]},
                        ]
                    },
                    "status": {"total": 1},
                },
            )
        )
        client = NetskopeClient(tenant="t.goskope.com", api_token="tok")
        lists = list(client.url_lists.list())
        assert len(lists) == 1
        assert isinstance(lists[0], UrlList)
        assert lists[0].name == "Block"
        client.close()

    @respx.mock
    def test_create(self) -> None:
        respx.post("https://t.goskope.com/api/v2/policy/urllist").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {"id": 42, "name": "NewList", "urls": ["new.com"]},
                },
            )
        )
        client = NetskopeClient(tenant="t.goskope.com", api_token="tok")
        result = client.url_lists.create("NewList", ["new.com"])
        assert result.id == 42
        assert result.name == "NewList"
        client.close()

    @respx.mock
    def test_delete(self) -> None:
        respx.delete("https://t.goskope.com/api/v2/policy/urllist/42").mock(
            return_value=httpx.Response(200, json={})
        )
        client = NetskopeClient(tenant="t.goskope.com", api_token="tok")
        client.url_lists.delete(42)  # Should not raise
        client.close()

    @respx.mock
    def test_deploy(self) -> None:
        respx.post("https://t.goskope.com/api/v2/policy/deploy").mock(
            return_value=httpx.Response(200, json={"status": "deployed"})
        )
        client = NetskopeClient(tenant="t.goskope.com", api_token="tok")
        result = client.url_lists.deploy()
        assert result["status"] == "deployed"
        client.close()


class TestPublishersResource:
    """Tests for client.publishers."""

    @respx.mock
    def test_list(self) -> None:
        respx.get("https://t.goskope.com/api/v2/infrastructure/publishers").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "publishers": [
                            {"publisher_id": 1, "publisher_name": "Pub1", "status": "connected"},
                        ]
                    },
                    "status": {"total": 1},
                },
            )
        )
        client = NetskopeClient(tenant="t.goskope.com", api_token="tok")
        pubs = list(client.publishers.list())
        assert len(pubs) == 1
        assert isinstance(pubs[0], Publisher)
        assert pubs[0].publisher_name == "Pub1"
        client.close()

    @respx.mock
    def test_create(self) -> None:
        respx.post("https://t.goskope.com/api/v2/infrastructure/publishers").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {"publisher_id": 99, "publisher_name": "NewPub"},
                },
            )
        )
        client = NetskopeClient(tenant="t.goskope.com", api_token="tok")
        pub = client.publishers.create(name="NewPub")
        assert pub.publisher_id == 99
        client.close()
