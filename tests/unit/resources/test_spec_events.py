"""Wire and decode conformance for events, alerts, incidents, and datasearch.

Every test here cites the OpenAPI gateway contract it enforces. Paths are
relative to ``production/endpoints``: ``events/*.yaml`` is rooted at
``/api/v2/events``, ``incidents/*.yaml`` at ``/api/v2/incidents``, and
``ubadatasvc/ubadatasvc.yaml`` at ``/api/v2/ubadatasvc``.
"""

from __future__ import annotations

from typing import Any

import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.datasearch import DATASEARCH_TIMEOUT_DEFAULT, DatasearchWindow
from netskope.exceptions import APIError, NotFoundError, ResponseValidationError, ValidationError
from netskope.models.alerts import Alert
from netskope.models.events import ClientStatusEvent, NetworkEvent
from netskope.models.incidents import UserConfidenceIndex

BASE = "https://t.goskope.com"
ALERT_URL = f"{BASE}/api/v2/events/datasearch/alert"
NETWORK_URL = f"{BASE}/api/v2/events/datasearch/network"
INCIDENT_URL = f"{BASE}/api/v2/events/datasearch/incident"
AUDIT_URL = f"{BASE}/api/v2/events/data/audit"
INFRA_URL = f"{BASE}/api/v2/events/data/infrastructure"
METRICS_URL = f"{BASE}/api/v2/events/metrics/transactionevents"
FORENSICS_URL = f"{BASE}/api/v2/incidents/dlpincidents/1234/forensics"
UCI_URL = f"{BASE}/api/v2/ubadatasvc/user/uci"

EMPTY = {"result": [], "status": {"count": 0}}


# ---------------------------------------------------------------------------
# `timeout` is a required query parameter on every datasearch search
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda c: list(c.alerts.list()), id="alerts.list"),
        pytest.param(lambda c: c.alerts.list_page(), id="alerts.list_page"),
        pytest.param(lambda c: c.alerts.aggregate_page(group_by="app"), id="alerts.aggregate_page"),
        pytest.param(lambda c: list(c.events.list("alert")), id="events.list"),
        pytest.param(lambda c: c.events.list_page("alert"), id="events.list_page"),
    ],
)
@respx.mock
def test_datasearch_requests_carry_the_required_timeout(client: NetskopeClient, call: Any) -> None:
    """search_alert.yaml:313-319 marks `timeout` required with a default of 180."""
    route = respx.get(ALERT_URL).respond(200, json=EMPTY)
    call(client)
    assert route.calls.last.request.url.params["timeout"] == str(DATASEARCH_TIMEOUT_DEFAULT)


@respx.mock
def test_incident_datasearch_carries_the_required_timeout(client: NetskopeClient) -> None:
    """search_incident.yaml:459-465 marks `timeout` required on the incident search."""
    route = respx.get(INCIDENT_URL).respond(200, json=EMPTY)
    list(client.incidents.list())
    assert route.calls.last.request.url.params["timeout"] == "180"
    client.incidents.list_page(limit=1)
    assert route.calls.last.request.url.params["timeout"] == "180"


@respx.mock
def test_alert_lookup_and_scan_carry_the_timeout(client: NetskopeClient) -> None:
    """search_alert.yaml:313-319 applies to every GET /datasearch/alert, lookups included."""
    route = respx.get(ALERT_URL).respond(200, json={"result": [{"_id": "a1"}]})
    client.alerts.get("a1")
    assert route.calls.last.request.url.params["timeout"] == "180"
    list(client.alerts.scan_pages(window=DatasearchWindow(start_time=1, end_time=2), page_size=2))
    assert route.calls.last.request.url.params["timeout"] == "180"


@respx.mock
def test_a_caller_can_raise_or_omit_the_timeout(client: NetskopeClient) -> None:
    """search_alert.yaml:317-319 types `timeout` as an integer in seconds."""
    route = respx.get(ALERT_URL).respond(200, json=EMPTY)
    client.alerts.list_page(timeout=600)
    assert route.calls.last.request.url.params["timeout"] == "600"
    client.alerts.list_page(timeout=None)
    assert "timeout" not in route.calls.last.request.url.params


@pytest.mark.parametrize("timeout", [0, -1, True, "180"])
@respx.mock
def test_an_unusable_timeout_fails_before_http(client: NetskopeClient, timeout: Any) -> None:
    with pytest.raises(ValidationError):
        client.alerts.list_page(timeout=timeout)
    assert not respx.calls


@pytest.mark.parametrize(
    "url,call",
    [
        pytest.param(AUDIT_URL, lambda c: list(c.events.list("audit")), id="audit"),
        pytest.param(
            INFRA_URL, lambda c: list(c.events.list("infrastructure")), id="infrastructure"
        ),
    ],
)
@respx.mock
def test_the_data_endpoints_never_receive_a_timeout(
    client: NetskopeClient, url: str, call: Any
) -> None:
    """audit.yaml:12-72 and infrastructure.yaml:12-72 declare no `timeout` parameter."""
    route = respx.get(url).respond(200, json=EMPTY)
    call(client)
    assert "timeout" not in route.calls.last.request.url.params


@respx.mock
def test_transaction_metrics_sends_only_hours(client: NetskopeClient) -> None:
    """transaction_metrics.yaml:74-83 declares `hours` as the only parameter."""
    route = respx.get(METRICS_URL).respond(200, json={"result": {}})
    client.events.transaction_metrics(hours=48)
    assert dict(route.calls.last.request.url.params) == {"hours": "48"}


# ---------------------------------------------------------------------------
# Sort direction travels as `orderbys`, never `sortby`
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,call",
    [
        pytest.param(
            ALERT_URL, lambda c: list(c.alerts.list(order_by="timestamp")), id="alerts.list"
        ),
        pytest.param(
            ALERT_URL,
            lambda c: c.alerts.list_page(order_by="timestamp", descending=True),
            id="alerts.list_page",
        ),
        pytest.param(
            NETWORK_URL,
            lambda c: list(c.events.list("network", order_by="timestamp")),
            id="events.list",
        ),
        pytest.param(
            NETWORK_URL,
            lambda c: c.events.list_page("network", order_by="timestamp", descending=True),
            id="events.list_page",
        ),
        pytest.param(
            INCIDENT_URL,
            lambda c: c.incidents.list_page(order_by="timestamp", descending=True),
            id="incidents.list_page",
        ),
    ],
)
@respx.mock
def test_ordering_uses_orderbys_on_both_paths(client: NetskopeClient, url: str, call: Any) -> None:
    """search_alert.yaml:363-368 and search_network.yaml:269-274 name the parameter orderbys.

    The spec example `instance_id+desc,timestamp+desc` is `field desc`
    URL-encoded, so a space before the direction is the same wire value. No
    search_*.yaml declares a `sortby` parameter at all.
    """
    route = respx.get(url).respond(200, json=EMPTY)
    call(client)
    params = route.calls.last.request.url.params
    assert params["orderbys"] == "timestamp DESC"
    assert "sortby" not in params


# ---------------------------------------------------------------------------
# Record decoding
# ---------------------------------------------------------------------------


@respx.mock
def test_object_valued_other_categories_do_not_reject_the_page(client: NetskopeClient) -> None:
    """search_alert.yaml:168-171 types other_categories items as objects."""
    respx.get(ALERT_URL).respond(
        200,
        json={
            "result": [
                {"_id": "a1", "other_categories": [{"name": "Cloud Storage"}, "Webmail"]},
                {"_id": "a2", "other_categories": "Webmail"},
            ]
        },
    )
    alerts = client.alerts.list_page(limit=2).items
    assert alerts[0].other_categories == [{"name": "Cloud Storage"}, "Webmail"]
    assert alerts[1].other_categories == ["Webmail"]


def test_a_bare_alert_row_still_decodes_object_categories() -> None:
    """dataexport.yaml:255-257 leaves the item type open entirely."""
    alert = Alert.model_validate({"_id": "a1", "other_categories": [{"id": 7}]})
    assert alert.other_categories == [{"id": 7}]


@respx.mock
def test_network_rows_report_ip_protocol(client: NetskopeClient) -> None:
    """search_network.yaml:82-84 names the transport protocol field ip_protocol."""
    respx.get(NETWORK_URL).respond(
        200,
        json={
            "result": [
                {
                    "_id": "n1",
                    "ip_protocol": "UDP",
                    "srcip": "10.0.0.0",
                    "dstport": 53,
                    "timestamp": 1721669000,
                }
            ]
        },
    )
    event = client.events.list_page("network", limit=1).items[0]
    assert isinstance(event, NetworkEvent)
    assert event.protocol == "UDP"
    assert event.src_ip == "10.0.0.0" and event.dst_port == 53


def test_a_flat_protocol_key_is_still_accepted() -> None:
    """Tenants already returning the flat name must keep working."""
    assert NetworkEvent.model_validate({"_id": "n1", "protocol": "TCP"}).protocol == "TCP"


CLIENT_STATUS_ROW: dict[str, Any] = {
    "_id": "cs1",
    "client_version": "10.0.0.0",
    "device_id": "oDPehfjveUYNHCYAtz0KL",
    "host_info": {
        "device_make": "HP",
        "device_model": "HP ZBook 15 G3",
        "hostname": "ITE004433",
        "os": "Windows",
        "os_version": "10.0 (1909)",
    },
    "last_seen_device_event": {
        "actor": "User",
        "event": "Admin Enabled",
        "status": "Enabled",
        "timestamp": 17146156,
    },
}


@respx.mock
def test_client_status_reads_the_nested_host_and_event_fields(client: NetskopeClient) -> None:
    """search_clientstatus.yaml:81-121 nests host_info; :128-151 nests last_seen_device_event.

    ``hostname`` is at :90-92, ``os`` at :110-112, and ``status`` at :143-145.
    """
    respx.get(f"{BASE}/api/v2/events/datasearch/clientstatus").respond(
        200, json={"result": [CLIENT_STATUS_ROW]}
    )
    event = client.events.list_page("clientstatus", limit=1).items[0]
    assert isinstance(event, ClientStatusEvent)
    assert event.hostname == "ITE004433"
    assert event.os == "Windows"
    assert event.status == "Enabled"
    assert event.client_version == "10.0.0.0"


def test_flat_client_status_keys_are_still_accepted() -> None:
    """Tenants that flatten these fields keep decoding through the alias fallback."""
    event = ClientStatusEvent.model_validate(
        {"_id": "cs1", "hostname": "ITE004433", "os": "Windows", "status": "Enabled"}
    )
    assert (event.hostname, event.os, event.status) == ("ITE004433", "Windows", "Enabled")


# ---------------------------------------------------------------------------
# audit and infrastructure page limits
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("event_type", ["audit", "infrastructure"])
def test_the_data_endpoints_cap_a_page_at_five_thousand(
    client: NetskopeClient, event_type: str
) -> None:
    """audit.yaml:19-27 and infrastructure.yaml:19-27 declare maximum: 5000."""
    assert client.events.capabilities(event_type).page_limit == 5000
    with pytest.raises(ValidationError, match="5000"):
        client.events.list_page(event_type, limit=5001)


# ---------------------------------------------------------------------------
# UBA anomalies and the user confidence index
# ---------------------------------------------------------------------------


@respx.mock
async def test_async_anomalies_read_the_results_key(aclient: AsyncNetskopeClient) -> None:
    """uba.yaml:926-937 requires both `results` and `totalCount` on UserAnomalies."""
    respx.post(f"{BASE}/api/v2/incidents/users/getanomalies").respond(
        200,
        json={
            "results": [
                {
                    "anomalyId": "66c66dda184d542f2188282f",
                    "user": "demo@netskope.com",
                    "score": 25,
                    "windowId": 1661126400000,
                }
            ],
            "totalCount": 1,
        },
    )
    anomalies = await aclient.incidents.get_anomalies(["demo@netskope.com"])
    assert [anomaly.id for anomaly in anomalies] == ["66c66dda184d542f2188282f"]
    assert anomalies[0].window_id == 1661126400000


@respx.mock
def test_anomaly_sort_order_is_always_sent(client: NetskopeClient) -> None:
    """uba.yaml:2205-2216 defaults sortorder to asc; the SDK sends an explicit desc."""
    route = respx.post(f"{BASE}/api/v2/incidents/users/getanomalies").respond(
        200, json={"results": [], "totalCount": 0}
    )
    client.incidents.get_anomalies(["demo@netskope.com"])
    assert route.calls.last.request.url.params["sortorder"] == "desc"
    client.incidents.get_anomalies(["demo@netskope.com"], sort_order="asc")
    assert route.calls.last.request.url.params["sortorder"] == "asc"


@respx.mock
def test_uci_decodes_the_declared_time_series(client: NetskopeClient) -> None:
    """ubadatasvc.yaml:61-69 defines ConfidenceTimeSeries as confidences plus userId."""
    respx.post(UCI_URL).respond(
        200,
        json={
            "userId": "demo@netskope.com",
            "confidences": [
                {"start": 1661126400000, "confidenceScore": 950},
                {"confidenceScore": 900},
                {"start": 1661212800000},
            ],
        },
    )
    uci = client.incidents.with_response.get_uci("demo@netskope.com").parse()
    assert isinstance(uci, UserConfidenceIndex)
    assert uci.user_id == "demo@netskope.com"
    assert uci.confidences is not None
    assert [point.confidence_score for point in uci.confidences] == [950, 900, None]
    assert [point.start for point in uci.confidences] == [1661126400000, None, 1661212800000]


def test_a_confidence_point_needs_neither_field() -> None:
    """ubadatasvc.yaml:52-60 declares Confidence with no `required` list."""
    uci = UserConfidenceIndex.model_validate({"userId": "u", "confidences": [{}]})
    assert uci.confidences is not None
    assert uci.confidences[0].start is None
    assert uci.confidences[0].confidence_score is None


# ---------------------------------------------------------------------------
# Reported failures on HTTP 200
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("execution", ["Failed", "FAILED", "failed"])
@respx.mock
def test_a_failed_datasearch_execution_is_raised_in_any_casing(
    client: NetskopeClient, execution: str
) -> None:
    """search_alert.yaml:249-255 enums Success/Failed while its example reads SUCCESS."""
    respx.get(ALERT_URL).respond(
        200,
        json={
            "result": [],
            "status": {
                "count": 0,
                "execution": execution,
                "message": "Invalid query field",
                "status_code": 400,
            },
        },
    )
    with pytest.raises(APIError) as caught:
        client.alerts.list_page(limit=1)
    assert caught.value.status_code == 400
    assert "Invalid query field" in str(caught.value)
    assert "/api/v2/events/datasearch/alert" in str(caught.value)


@respx.mock
def test_forensics_reports_the_reason_from_data_error(client: NetskopeClient) -> None:
    """ims_forensics.yaml:60-94 returns the Error arm of `data` on HTTP 200 with status error."""
    respx.get(FORENSICS_URL).respond(
        200,
        json={
            "data": {"error": "Incident's Forensic File not found in destination."},
            "status": "error",
        },
    )
    with pytest.raises(NotFoundError) as caught:
        client.incidents.with_response.get_forensics("1234").parse()
    assert "not found in destination" in str(caught.value)


@respx.mock
def test_forensics_names_the_error_even_without_a_status_field(client: NetskopeClient) -> None:
    """ims_forensics.yaml:25-36 types `data` as oneOf[Forensics, Error]; `status` is optional."""
    respx.get(FORENSICS_URL).respond(
        200, json={"data": {"error": "Forensic File could not be retrieved."}}
    )
    with pytest.raises(ResponseValidationError) as caught:
        client.incidents.with_response.get_forensics("1234").parse()
    assert "could not be retrieved" in str(caught.value)


@respx.mock
def test_forensics_decodes_the_documented_success_body(client: NetskopeClient) -> None:
    """ims_forensics.yaml:80-86 shows the Success example verbatim."""
    respx.get(FORENSICS_URL).respond(
        200,
        json={
            "data": {
                "content": "sample file content",
                "meta": '{"meta":"data"}',
                "preview_image": "base64encoded Image Thumbnail File",
            },
            "status": "success",
        },
    )
    forensics = client.incidents.with_response.get_forensics("1234").parse()
    assert forensics.content == "sample file content"
    assert forensics.meta == '{"meta":"data"}'
    assert forensics.preview_image == "base64encoded Image Thumbnail File"


# ---------------------------------------------------------------------------
# Incident update acknowledgement
# ---------------------------------------------------------------------------


@respx.mock
def test_the_documented_update_envelope_reports_acceptance(client: NetskopeClient) -> None:
    """incident_update.yaml:69-75 wraps {ok, result} items in {"result": [...]}."""
    route = respx.patch(f"{BASE}/api/v2/incidents/update").respond(
        200, json={"result": [{"ok": 1, "result": "Update Successful"}]}
    )
    result = client.incidents.update_one(
        1234567890, field="status", new_value="in_progress", user="user@domain.com"
    )
    assert result.accepted
    assert result.accepted_entries == 0
    assert route.call_count == 1


@respx.mock
def test_transaction_metrics_decode_the_documented_result_object(client: NetskopeClient) -> None:
    """transaction_metrics.yaml:17-35 names both metric keys inside `result`."""
    respx.get(METRICS_URL).respond(
        200,
        json={
            "ok": 1,
            "result": {
                "subscription/backlog_message_count": {"0": {"1": 42}},
                "subscription/oldest_unacked_message_age": {"0": {"1": "1h 2m"}},
            },
        },
    )
    metrics = client.events.transaction_metrics()
    assert metrics.backlog_message_count == {"0": {"1": 42}}
    assert metrics.oldest_unacked_message_age == {"0": {"1": "1h 2m"}}


@respx.mock
async def test_async_events_and_alerts_send_the_same_datasearch_parameters(
    aclient: AsyncNetskopeClient,
) -> None:
    """The async path must not drift from search_alert.yaml:313-368."""
    route = respx.get(ALERT_URL).respond(200, json=EMPTY)
    await aclient.alerts.list_page(order_by="timestamp", descending=False, limit=5)
    alert_params = dict(route.calls.last.request.url.params)
    await aclient.events.list_page("alert", order_by="timestamp", descending=False, limit=5)
    assert dict(route.calls.last.request.url.params) == alert_params
    assert alert_params == {"timeout": "180", "orderbys": "timestamp ASC", "limit": "5"}


@respx.mock
async def test_async_legacy_iterators_agree_on_the_wire(aclient: AsyncNetskopeClient) -> None:
    """Legacy alerts.list and events.list build one datasearch request shape."""
    route = respx.get(ALERT_URL).respond(200, json=EMPTY)
    _ = [alert async for alert in aclient.alerts.list(order_by="timestamp", page_size=25)]
    alert_params = dict(route.calls.last.request.url.params)
    _ = [event async for event in aclient.events.list("alert", order_by="timestamp", page_size=25)]
    assert dict(route.calls.last.request.url.params) == alert_params
    assert alert_params["timeout"] == "180"
    assert alert_params["orderbys"] == "timestamp DESC"


@respx.mock
def test_a_failed_execution_beside_the_envelope_is_also_raised(client: NetskopeClient) -> None:
    """search_clientstatus.yaml:204-210 declares the same Success/Failed enum."""
    respx.get(f"{BASE}/api/v2/events/datasearch/clientstatus").respond(
        200, json={"result": [], "execution": "Failed"}
    )
    with pytest.raises(APIError, match="execution=FAILED"):
        client.events.list_page("clientstatus", limit=1)


@respx.mock
def test_audit_type_with_a_quote_is_refused_before_http(client: NetskopeClient) -> None:
    """The audit filter becomes a JQL clause, so it must not carry a quote of its own."""
    with pytest.raises(ValidationError, match="double quote"):
        client.events.list_page("audit", audit_type='admin" or 1 eq 1 and "')
    assert not respx.calls


@respx.mock
def test_infrastructure_accepts_insertion_bounds(client: NetskopeClient) -> None:
    """infrastructure.yaml:51-72 declares insertionstarttime and insertionendtime."""
    route = respx.get(INFRA_URL).respond(200, json=EMPTY)
    client.events.list_page(
        "infrastructure", insertion_start_time=1700000000, insertion_end_time=1700003600
    )
    assert dict(route.calls.last.request.url.params) == {
        "insertionstarttime": "1700000000",
        "insertionendtime": "1700003600",
    }


@respx.mock
def test_transaction_is_rejected_on_every_record_entry_point(client: NetskopeClient) -> None:
    """transaction_metrics.yaml:65-90 answers with one metrics object, never records."""
    for call in (
        lambda: client.events.list("transaction"),
        lambda: client.events.list_page("transaction"),
        lambda: client.events.get("deadbeef", event_type="transaction"),
        lambda: client.events.capabilities("transaction"),
    ):
        with pytest.raises(ValidationError, match="transaction_metrics"):
            call()
    assert not respx.calls


@respx.mock
def test_a_page_of_spec_shaped_alert_rows_decodes(client: NetskopeClient) -> None:
    """search_alert.yaml:5-242 types the record fields returned by /datasearch/alert."""
    respx.get(ALERT_URL).respond(
        200,
        json={
            "result": [
                {
                    "_id": "1a2b3c",
                    "alert_name": "Login Failed",
                    "alert_type": "uba",
                    "app": "Box",
                    "cci": "42",
                    "ccl": "excellent",
                    "other_categories": [{"name": "Cloud Storage"}],
                    "severity_level": 3,
                    "site": 7,
                    "timestamp": 1721669000,
                    "usergroup": [{"name": "engineering"}],
                }
            ],
            "status": {"count": 1, "execution": "Success", "status_code": 200},
        },
    )
    alert = client.alerts.list_page(limit=1).items[0]
    assert alert.id == "1a2b3c"
    assert alert.cci == 42
    assert alert.severity == 3 and alert.site == 7
    assert alert.other_categories == [{"name": "Cloud Storage"}]
    assert alert.model_extra is not None and "usergroup" in alert.model_extra
