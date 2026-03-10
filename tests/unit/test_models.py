"""Tests for Pydantic models."""

from __future__ import annotations

from datetime import datetime

import pytest

from netskope.models.alerts import Alert
from netskope.models.events import Event, EventType, NetworkEvent, PageEvent
from netskope.models.incidents import Incident, UserConfidenceIndex
from netskope.models.infrastructure import IPSecTunnel, Pop
from netskope.models.private_apps import PrivateApp
from netskope.models.publishers import Publisher
from netskope.models.scim import ScimGroup, ScimUser
from netskope.models.url_lists import UrlList


class TestAlert:
    """Tests for the Alert model."""

    def test_parse_from_api(self) -> None:
        data = {
            "_id": "abc123",
            "alert_name": "DLP Alert",
            "alert_type": "DLP",
            "severity_level": "high",
            "user": "alice@example.com",
            "app": "Slack",
            "activity": "Upload",
            "timestamp": 1709913600,
        }
        alert = Alert.model_validate(data)
        assert alert.id == "abc123"
        assert alert.alert_name == "DLP Alert"
        assert alert.severity == "high"
        assert alert.user == "alice@example.com"
        assert alert.timestamp is not None

    def test_extra_fields_allowed(self) -> None:
        data = {"_id": "x", "unknown_field": "value"}
        alert = Alert.model_validate(data)
        assert alert.id == "x"

    def test_frozen(self) -> None:
        from pydantic import ValidationError as PydanticValidationError

        alert = Alert.model_validate({"_id": "x"})
        with pytest.raises(PydanticValidationError):
            alert.id = "y"  # type: ignore[misc]

    def test_serialization(self) -> None:
        alert = Alert.model_validate({"_id": "abc", "alert_name": "Test"})
        d = alert.model_dump()
        assert isinstance(d, dict)
        assert d["id"] == "abc"
        json_str = alert.model_dump_json()
        assert "abc" in json_str


class TestEvent:
    def test_generic_event(self) -> None:
        event = Event.model_validate({
            "_id": "evt1",
            "user": "bob@example.com",
            "app": "Gmail",
            "activity": "Download",
        })
        assert event.user == "bob@example.com"

    def test_network_event(self) -> None:
        data = {
            "_id": "net1",
            "src_ip": "10.0.0.1",
            "dst_ip": "192.168.1.1",
            "src_port": 443,
            "protocol": "TCP",
        }
        event = NetworkEvent.model_validate(data)
        assert event.src_ip == "10.0.0.1"
        assert event.src_port == 443

    def test_page_event(self) -> None:
        data = {"_id": "pg1", "url": "https://example.com", "domain": "example.com"}
        event = PageEvent.model_validate(data)
        assert event.url == "https://example.com"


class TestEventType:
    def test_enum_values(self) -> None:
        assert EventType.ALERT == "alert"
        assert EventType.NETWORK == "network"
        assert EventType.APPLICATION == "application"


class TestUrlList:
    def test_parse(self) -> None:
        data = {
            "id": 42,
            "name": "Blocklist",
            "type": "exact",
            "urls": ["bad.com", "evil.org"],
            "pending": False,
        }
        url_list = UrlList.model_validate(data)
        assert url_list.id == 42
        assert url_list.name == "Blocklist"
        assert len(url_list.urls) == 2

    def test_empty_urls_default(self) -> None:
        url_list = UrlList.model_validate({"id": 1, "name": "Empty"})
        assert url_list.urls == []


class TestPublisher:
    def test_parse(self) -> None:
        data = {
            "publisher_id": 10,
            "publisher_name": "AWS-East",
            "status": "connected",
            "apps_count": 5,
        }
        pub = Publisher.model_validate(data)
        assert pub.publisher_id == 10
        assert pub.publisher_name == "AWS-East"
        assert pub.status == "connected"


class TestPrivateApp:
    def test_parse(self) -> None:
        data = {
            "app_id": 100,
            "app_name": "Dashboard",
            "host": "10.0.0.5",
            "port": "443",
            "protocols": ["TCP"],
        }
        app = PrivateApp.model_validate(data)
        assert app.app_name == "Dashboard"
        assert app.host == "10.0.0.5"


class TestScimUser:
    def test_parse(self) -> None:
        data = {
            "id": "user-1",
            "userName": "alice@example.com",
            "displayName": "Alice",
            "active": True,
            "emails": [{"value": "alice@example.com", "primary": True}],
        }
        user = ScimUser.model_validate(data)
        assert user.user_name == "alice@example.com"
        assert user.display_name == "Alice"
        assert user.active is True
        assert len(user.emails) == 1


class TestScimGroup:
    def test_parse(self) -> None:
        data = {
            "id": "grp-1",
            "displayName": "Engineering",
            "members": [{"value": "user-1", "display": "Alice"}],
        }
        group = ScimGroup.model_validate(data)
        assert group.display_name == "Engineering"
        assert len(group.members) == 1


class TestIncident:
    def test_parse(self) -> None:
        data = {
            "_id": "inc-1",
            "incident_id": "INC-001",
            "severity_level": "critical",
            "status": "open",
            "user": "bob@example.com",
        }
        incident = Incident.model_validate(data)
        assert incident.incident_id == "INC-001"
        assert incident.severity == "critical"


class TestTimestampMixin:
    def test_epoch_to_datetime(self) -> None:
        alert = Alert.model_validate({"timestamp": 1709913600})
        assert isinstance(alert.timestamp, datetime)

    def test_none_stays_none(self) -> None:
        alert = Alert.model_validate({})
        assert alert.timestamp is None


class TestInfrastructure:
    def test_pop(self) -> None:
        pop = Pop.model_validate({"name": "US-East", "region": "us-east-1"})
        assert pop.name == "US-East"

    def test_tunnel(self) -> None:
        tunnel = IPSecTunnel.model_validate({
            "id": 1,
            "name": "HQ-Tunnel",
            "status": "up",
        })
        assert tunnel.name == "HQ-Tunnel"


class TestUserConfidenceIndex:
    def test_parse(self) -> None:
        uci = UserConfidenceIndex.model_validate({
            "user": "alice@example.com",
            "score": 75.5,
            "severity": "medium",
        })
        assert uci.score == 75.5
        assert uci.severity == "medium"
