"""Tests for client.incidents with mocked HTTP."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.incidents import Incident, IncidentNote
from tests.unit.resources.conftest import sent_json

_BASE = "https://t.goskope.com"
_SEARCH_URL = f"{_BASE}/api/v2/events/datasearch/incident"
_UPDATE_URL = f"{_BASE}/api/v2/incidents/update"
_UCI_URL = f"{_BASE}/api/v2/ubadatasvc/user/uci"
_ANOMALIES_URL = f"{_BASE}/api/v2/incidents/users/getanomalies"
_DLP_URL = f"{_BASE}/api/v2/incidents/dlpincidents"

_NOTE = {
    "note_id": "604ce028-b104-4fe6-8d4e-6ed3c04c5378",
    "user": "analyst@example.com",
    "timestamp": 1700000000,
    "content": "Escalated to tier 2",
}


def _uci_window_ms() -> tuple[int, int]:
    """Return a tolerant (low, high) bound for the default 7-day UCI window."""
    now_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
    seven_days_ms = int(timedelta(days=7).total_seconds() * 1000)
    return now_ms - seven_days_ms - 60_000, now_ms - seven_days_ms + 60_000


class TestIncidentsResource:
    """Tests for client.incidents (sync)."""

    @respx.mock
    def test_list_returns_incidents(self, client: NetskopeClient) -> None:
        respx.get(_SEARCH_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "result": [
                        {"_id": "i1", "incident_id": "INC-1", "status": "open"},
                    ],
                    "status": {"total": 1},
                },
            )
        )
        incidents = list(client.incidents.list())
        assert len(incidents) == 1
        assert isinstance(incidents[0], Incident)
        assert incidents[0].incident_id == "INC-1"

    @respx.mock
    def test_update_sends_payload_wrapper(self, client: NetskopeClient) -> None:
        """update() must wrap the change in {"payload": [{...}]} with object_id."""
        route = respx.patch(_UPDATE_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        client.incidents.update(
            "INC-123",
            field="status",
            old_value="open",
            new_value="in_progress",
            user="analyst@example.com",
        )
        assert sent_json(route) == {
            "payload": [
                {
                    "object_id": "INC-123",
                    "field": "status",
                    "old_value": "open",
                    "new_value": "in_progress",
                    "user": "analyst@example.com",
                }
            ]
        }

    @respx.mock
    def test_update_invalid_field_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            client.incidents.update(
                "INC-123",
                field="priority",
                old_value="a",
                new_value="b",
                user="x@example.com",
            )
        assert len(respx.calls) == 0

    @respx.mock
    def test_get_uci_default_window(self, client: NetskopeClient) -> None:
        """get_uci() sends {"user", "fromTime"} with fromTime ~ now - 7d in ms."""
        route = respx.post(_UCI_URL).mock(
            return_value=httpx.Response(200, json={"data": {"score": 875.0}})
        )
        uci = client.incidents.get_uci("alice@example.com")
        assert uci.score == 875.0
        body = sent_json(route)
        assert set(body) == {"user", "fromTime"}
        assert body["user"] == "alice@example.com"
        low, high = _uci_window_ms()
        assert low <= body["fromTime"] <= high

    @respx.mock
    def test_get_uci_datetime_converted_to_epoch_ms(self, client: NetskopeClient) -> None:
        route = respx.post(_UCI_URL).mock(return_value=httpx.Response(200, json={"data": {}}))
        dt = datetime(2026, 1, 1, tzinfo=UTC)
        client.incidents.get_uci("alice@example.com", from_time=dt)
        assert sent_json(route)["fromTime"] == int(dt.timestamp() * 1000)

    @respx.mock
    def test_get_uci_int_passthrough(self, client: NetskopeClient) -> None:
        route = respx.post(_UCI_URL).mock(return_value=httpx.Response(200, json={"data": {}}))
        client.incidents.get_uci("alice@example.com", from_time=1700000000000)
        assert sent_json(route)["fromTime"] == 1700000000000

    @respx.mock
    def test_get_anomalies_default_body(self, client: NetskopeClient) -> None:
        route = respx.post(_ANOMALIES_URL).mock(
            return_value=httpx.Response(200, json={"data": [{"_id": "an1", "user": "a@ex.com"}]})
        )
        anomalies = client.incidents.get_anomalies(["a@ex.com"])
        assert len(anomalies) == 1
        assert anomalies[0].user == "a@ex.com"
        assert sent_json(route) == {
            "users": ["a@ex.com"],
            "timeframe": 30,
            "limit": 100,
            "offset": 0,
            "sortby": "time",
            "sortorder": "desc",
        }

    @respx.mock
    def test_get_anomalies_severity_str_normalized_to_list(self, client: NetskopeClient) -> None:
        route = respx.post(_ANOMALIES_URL).mock(return_value=httpx.Response(200, json={"data": []}))
        client.incidents.get_anomalies(["a@ex.com"], severity="High")
        assert sent_json(route)["severity_filter"] == ["High"]

    @respx.mock
    def test_get_anomalies_severity_list_passthrough(self, client: NetskopeClient) -> None:
        route = respx.post(_ANOMALIES_URL).mock(return_value=httpx.Response(200, json={"data": []}))
        client.incidents.get_anomalies(["a@ex.com"], severity=["High", "Critical"])
        assert sent_json(route)["severity_filter"] == ["High", "Critical"]

    @respx.mock
    @pytest.mark.parametrize(
        "kwargs",
        [
            {"severity": "high"},  # severities are capitalized
            {"severity": ["Critical", "bogus"]},
            {"timeframe": 0},
            {"timeframe": 91},
            {"limit": 0},
            {"limit": 10001},
            {"sort_order": "descending"},
        ],
    )
    def test_get_anomalies_validation_no_http(
        self, client: NetskopeClient, kwargs: dict[str, object]
    ) -> None:
        with pytest.raises(ValidationError):
            client.incidents.get_anomalies(["a@ex.com"], **kwargs)  # type: ignore[arg-type]
        assert len(respx.calls) == 0

    @respx.mock
    def test_get_forensics(self, client: NetskopeClient) -> None:
        respx.get(f"{_DLP_URL}/DLP-12345/forensics").mock(
            return_value=httpx.Response(200, json={"data": {"file_name": "secrets.txt"}})
        )
        body = client.incidents.get_forensics("DLP-12345")
        assert body["data"]["file_name"] == "secrets.txt"

    @respx.mock
    def test_list_notes(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_DLP_URL}/1343008090332508247/notes").mock(
            return_value=httpx.Response(200, json={"data": [_NOTE], "status": "success"})
        )
        notes = client.incidents.list_notes("1343008090332508247")
        assert route.calls.last.request.method == "GET"
        assert len(notes) == 1
        assert isinstance(notes[0], IncidentNote)
        assert notes[0].note_id == _NOTE["note_id"]
        assert notes[0].user == "analyst@example.com"
        assert notes[0].timestamp == 1700000000
        assert notes[0].content == "Escalated to tier 2"

    @respx.mock
    def test_add_note(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_DLP_URL}/1343008090332508247/notes").mock(
            return_value=httpx.Response(200, json={"data": _NOTE, "status": "success"})
        )
        note = client.incidents.add_note("1343008090332508247", "Escalated to tier 2")
        assert sent_json(route) == {"content": "Escalated to tier 2"}
        assert note.note_id == _NOTE["note_id"]
        assert note.content == "Escalated to tier 2"

    @respx.mock
    def test_add_note_content_length_no_http(self, client: NetskopeClient) -> None:
        """Content of 512 characters or more is rejected client-side."""
        with pytest.raises(ValidationError):
            client.incidents.add_note("1343008090332508247", "x" * 512)
        assert len(respx.calls) == 0
        # 511 characters is the maximum accepted.
        route = respx.post(f"{_DLP_URL}/1343008090332508247/notes").mock(
            return_value=httpx.Response(200, json={"data": _NOTE})
        )
        client.incidents.add_note("1343008090332508247", "x" * 511)
        assert route.call_count == 1

    @respx.mock
    def test_delete_note(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_DLP_URL}/1343008090332508247/notes/{_NOTE['note_id']}").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        result = client.incidents.delete_note("1343008090332508247", str(_NOTE["note_id"]))
        assert result is None
        assert route.call_count == 1

    @respx.mock
    def test_note_ids_are_quoted_in_path(self, client: NetskopeClient) -> None:
        """Path-delimiter characters in ids must be percent-encoded, not routed."""
        route = respx.get(url__regex=r".*/notes$").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        client.incidents.list_notes("a/b")
        raw_path = route.calls.last.request.url.raw_path
        assert raw_path == b"/api/v2/incidents/dlpincidents/a%2Fb/notes"

    @respx.mock
    def test_note_id_rejects_dot_segments(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            client.incidents.delete_note("1343008090332508247", "..")
        assert len(respx.calls) == 0


class TestAsyncIncidentsResource:
    """Tests for aclient.incidents (async)."""

    @respx.mock
    async def test_update_sends_payload_wrapper(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.patch(_UPDATE_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        await aclient.incidents.update(
            "INC-123",
            field="severity",
            old_value="medium",
            new_value="critical",
            user="analyst@example.com",
        )
        assert sent_json(route) == {
            "payload": [
                {
                    "object_id": "INC-123",
                    "field": "severity",
                    "old_value": "medium",
                    "new_value": "critical",
                    "user": "analyst@example.com",
                }
            ]
        }

    @respx.mock
    async def test_update_invalid_field_no_http(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError):
            await aclient.incidents.update(
                "INC-123", field="priority", old_value="a", new_value="b", user="x@example.com"
            )
        assert len(respx.calls) == 0

    @respx.mock
    async def test_get_uci_body(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_UCI_URL).mock(
            return_value=httpx.Response(200, json={"data": {"score": 500.0}})
        )
        uci = await aclient.incidents.get_uci("alice@example.com")
        assert uci.score == 500.0
        body = sent_json(route)
        assert set(body) == {"user", "fromTime"}
        low, high = _uci_window_ms()
        assert low <= body["fromTime"] <= high

    @respx.mock
    async def test_get_anomalies_body(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_ANOMALIES_URL).mock(return_value=httpx.Response(200, json={"data": []}))
        await aclient.incidents.get_anomalies(["a@ex.com"], severity="Low", timeframe=7)
        body = sent_json(route)
        assert body["timeframe"] == 7
        assert body["severity_filter"] == ["Low"]
        assert body["sortby"] == "time"
        assert body["sortorder"] == "desc"

    @respx.mock
    async def test_get_anomalies_validation_no_http(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError):
            await aclient.incidents.get_anomalies(["a@ex.com"], sort_order="up")
        assert len(respx.calls) == 0

    @respx.mock
    async def test_notes_roundtrip(self, aclient: AsyncNetskopeClient) -> None:
        list_route = respx.get(f"{_DLP_URL}/134/notes").mock(
            return_value=httpx.Response(200, json={"data": [_NOTE]})
        )
        add_route = respx.post(f"{_DLP_URL}/134/notes").mock(
            return_value=httpx.Response(200, json={"data": _NOTE})
        )
        delete_route = respx.delete(f"{_DLP_URL}/134/notes/{_NOTE['note_id']}").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        notes = await aclient.incidents.list_notes("134")
        assert notes[0].note_id == _NOTE["note_id"]
        note = await aclient.incidents.add_note("134", "Reviewed")
        assert sent_json(add_route) == {"content": "Reviewed"}
        assert note.content == "Escalated to tier 2"
        result = await aclient.incidents.delete_note("134", str(_NOTE["note_id"]))
        assert result is None
        assert list_route.call_count == 1
        assert delete_route.call_count == 1

    @respx.mock
    async def test_add_note_content_length_no_http(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError):
            await aclient.incidents.add_note("134", "x" * 600)
        assert len(respx.calls) == 0
