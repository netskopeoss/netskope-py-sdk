"""Tests for Pydantic models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from netskope.models.alerts import Alert
from netskope.models.common import TimestampMixin
from netskope.models.events import Event, EventType, NetworkEvent, PageEvent
from netskope.models.incidents import (
    Anomaly,
    Incident,
    IncidentUpdateResult,
    UserConfidenceIndex,
)
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
        event = Event.model_validate(
            {
                "_id": "evt1",
                "user": "bob@example.com",
                "app": "Gmail",
                "activity": "Download",
            }
        )
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


_TIMESTAMPED = [Alert, Event, Incident, Anomaly]


class TestNumericWireShapes:
    """Datasearch returns several of these fields as numbers on some tenants."""

    @pytest.mark.parametrize("model", [Alert, Event, Incident])
    def test_numeric_severity_level_decodes(self, model: type[Any]) -> None:
        record = model.model_validate({"_id": "a1", "severity_level": 3})
        assert record.severity == 3

    @pytest.mark.parametrize("model", [Alert, Event, Incident])
    def test_string_severity_level_still_decodes(self, model: type[Any]) -> None:
        record = model.model_validate({"_id": "a1", "severity_level": "high"})
        assert record.severity == "high"

    def test_alert_accepts_numeric_ccl_and_site(self) -> None:
        alert = Alert.model_validate({"_id": "a1", "ccl": 4, "site": 12})
        assert alert.ccl == 4
        assert alert.site == 12

    def test_alert_accepts_one_other_category_as_a_bare_string(self) -> None:
        alert = Alert.model_validate({"_id": "a1", "other_categories": "Cloud Storage"})
        assert alert.other_categories == ["Cloud Storage"]

    def test_alert_reads_an_empty_other_categories_string_as_absent(self) -> None:
        assert Alert.model_validate({"_id": "a1", "other_categories": ""}).other_categories is None

    def test_alert_keeps_a_list_of_other_categories(self) -> None:
        alert = Alert.model_validate({"_id": "a1", "other_categories": ["a", "b"]})
        assert alert.other_categories == ["a", "b"]

    def test_incident_accepts_numeric_workflow_fields(self) -> None:
        incident = Incident.model_validate(
            {"_id": "i1", "status": 2, "assignee": 7, "dlp_profile": 1, "dlp_rule": 9}
        )
        assert (incident.status, incident.assignee) == (2, 7)
        assert (incident.dlp_profile, incident.dlp_rule) == (1, 9)

    def test_anomaly_accepts_numeric_severity(self) -> None:
        assert Anomaly.model_validate({"_id": "an1", "severity": 5}).severity == 5

    def test_a_whole_alert_row_with_numeric_fields_decodes(self) -> None:
        alert = Alert.model_validate(
            {
                "_id": "a1",
                "alert_name": "n1",
                "action": "block",
                "timestamp": 1700000000,
                "severity_level": 3,
            }
        )
        assert alert.id == "a1"
        assert alert.severity == 3


class TestTimestampMixin:
    def test_epoch_to_datetime(self) -> None:
        alert = Alert.model_validate({"timestamp": 1709913600})
        assert isinstance(alert.timestamp, datetime)

    def test_none_stays_none(self) -> None:
        alert = Alert.model_validate({})
        assert alert.timestamp is None

    @pytest.mark.parametrize("model", _TIMESTAMPED)
    def test_epoch_is_utc_aware(self, model: type[TimestampMixin]) -> None:
        record = model.model_validate({"timestamp": 1700000000})
        assert record.timestamp == datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)

    @pytest.mark.parametrize("model", _TIMESTAMPED)
    @pytest.mark.parametrize(
        "value",
        ["", "   ", "not-a-date", True, False, {"a": 1}, [1], 10**100, float("nan")],
        ids=["empty", "blank", "garbage", "true", "false", "dict", "list", "huge", "nan"],
    )
    def test_unreadable_values_are_absent_and_keep_the_record(
        self, model: type[TimestampMixin], value: Any
    ) -> None:
        record = model.model_validate({"_id": "x", "timestamp": value})
        assert record.timestamp is None

    @pytest.mark.parametrize("model", _TIMESTAMPED)
    def test_offset_datetime_string_keeps_its_offset(self, model: type[TimestampMixin]) -> None:
        record = model.model_validate({"timestamp": "2024-01-01T02:00:00+02:00"})
        assert record.timestamp == datetime(2024, 1, 1, tzinfo=UTC)

    @pytest.mark.parametrize("model", _TIMESTAMPED)
    @pytest.mark.parametrize("value", ["2024-01-01T00:00:00", "2024-01-01 00:00:00"])
    def test_datetime_string_without_an_offset_is_read_as_utc(
        self, model: type[TimestampMixin], value: str
    ) -> None:
        record = model.model_validate({"timestamp": value})
        assert record.timestamp == datetime(2024, 1, 1, tzinfo=UTC)
        assert isinstance(record.timestamp, datetime)
        assert record.timestamp.tzinfo is not None

    @pytest.mark.parametrize("model", _TIMESTAMPED)
    def test_naive_datetime_object_is_read_as_utc(self, model: type[TimestampMixin]) -> None:
        record = model.model_validate({"timestamp": datetime(2024, 1, 1)})
        assert record.timestamp == datetime(2024, 1, 1, tzinfo=UTC)

    def test_aware_datetime_object_keeps_its_offset(self) -> None:
        moment = datetime(2024, 1, 1, tzinfo=timezone(timedelta(hours=-5)))
        assert Alert.model_validate({"timestamp": moment}).timestamp == moment

    def test_numeric_string_epoch_still_parses(self) -> None:
        assert Alert.model_validate({"timestamp": "1700000000"}).timestamp == datetime(
            2023, 11, 14, 22, 13, 20, tzinfo=UTC
        )

    def test_epoch_and_string_rows_are_comparable(self) -> None:
        epoch_row = Alert.model_validate({"_id": "a", "timestamp": 1704067200})
        string_row = Alert.model_validate({"_id": "b", "timestamp": "2024-01-01 00:00:00"})
        assert epoch_row.timestamp == string_row.timestamp


class TestInfrastructure:
    def test_pop(self) -> None:
        pop = Pop.model_validate({"name": "US-East", "region": "us-east-1"})
        assert pop.name == "US-East"

    def test_tunnel(self) -> None:
        tunnel = IPSecTunnel.model_validate(
            {
                "id": 1,
                "name": "HQ-Tunnel",
                "status": "up",
            }
        )
        assert tunnel.name == "HQ-Tunnel"


class TestUserConfidenceIndex:
    def test_parse(self) -> None:
        uci = UserConfidenceIndex.model_validate(
            {
                "user": "alice@example.com",
                "score": 75.5,
                "severity": "medium",
            }
        )
        assert uci.score == 75.5
        assert uci.severity == "medium"


class TestIncidentUpdateResult:
    """`ok` is the acceptance flag; a reported count can still contradict it."""

    @pytest.mark.parametrize("count", [1, 3])
    def test_a_positive_count_is_accepted(self, count: int) -> None:
        result = IncidentUpdateResult.model_validate({"outcomes": [{"ok": 1, "result": count}]})
        assert result.accepted
        assert result.accepted_entries == count

    @pytest.mark.parametrize("count", [-1, -42])
    def test_a_negative_count_is_not_accepted(self, count: int) -> None:
        result = IncidentUpdateResult.model_validate({"outcomes": [{"ok": 1, "result": count}]})
        assert not result.accepted

    def test_a_zero_count_is_not_accepted(self) -> None:
        result = IncidentUpdateResult.model_validate({"outcomes": [{"ok": 1, "result": 0}]})
        assert not result.accepted

    def test_the_documented_success_body_is_accepted(self) -> None:
        """incident_update.yaml:8-14 and :69-75 document {ok: 1, result: <message>}."""
        result = IncidentUpdateResult.model_validate(
            {"outcomes": [{"ok": 1, "result": "Update Successful"}]}
        )
        assert result.accepted
        assert result.accepted_entries == 0

    def test_an_ok_flag_without_a_result_is_accepted(self) -> None:
        """incident_update.yaml:8-14 makes `result` optional; `ok` carries the outcome."""
        result = IncidentUpdateResult.model_validate({"outcomes": [{"ok": 1}]})
        assert result.accepted
        assert result.accepted_entries == 0

    def test_a_failed_ok_flag_is_not_accepted(self) -> None:
        """incident_update.yaml:15-21 gives the failure item the same {ok, result} shape."""
        result = IncidentUpdateResult.model_validate(
            {"outcomes": [{"ok": 1, "result": 2}, {"ok": 0, "result": "Update Failed"}]}
        )
        assert not result.accepted

    def test_one_negative_entry_withdraws_the_whole_claim(self) -> None:
        result = IncidentUpdateResult.model_validate(
            {"outcomes": [{"ok": 1, "result": 2}, {"ok": 1, "result": -1}]}
        )
        assert not result.accepted
