"""Tests for client.events with mocked HTTP."""

from __future__ import annotations

from typing import Any, ClassVar

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.datasearch import DATASEARCH_TIMEOUT_DEFAULT, DatasearchWindow
from netskope.exceptions import (
    APIError,
    NotFoundError,
    ResponseValidationError,
    ServerError,
    ValidationError,
)
from netskope.models.alerts import Alert
from netskope.models.events import ClientStatusEvent, Event, EventQueryCapabilities, NetworkEvent
from netskope.models.incidents import Incident
from tests.unit.resources.conftest import CONTRACT_BASE

_BASE = "https://t.goskope.com"
_APP_URL = f"{_BASE}/api/v2/events/datasearch/application"
_NETWORK_URL = f"{_BASE}/api/v2/events/datasearch/network"
_AUDIT_URL = f"{_BASE}/api/v2/events/data/audit"
_INFRA_URL = f"{_BASE}/api/v2/events/data/infrastructure"
_TRANSACTION_URL = f"{_BASE}/api/v2/events/metrics/transactionevents"

_EMPTY = {"result": [], "status": {"total": 0}}


class TestEventsResource:
    """Tests for client.events."""

    @respx.mock
    def test_list_application_events(self, client: NetskopeClient) -> None:
        respx.get(_APP_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "result": [{"_id": "e1", "user": "alice@ex.com", "app": "Slack"}],
                    "status": {"total": 1},
                },
            )
        )
        events = list(client.events.list("application"))
        assert len(events) == 1
        assert events[0].app == "Slack"

    @respx.mock
    def test_list_network_events(self, client: NetskopeClient) -> None:
        respx.get(_NETWORK_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "result": [{"_id": "n1", "src_ip": "10.0.0.1", "dst_ip": "8.8.8.8"}],
                    "status": {"total": 1},
                },
            )
        )
        events = list(client.events.list("network"))
        assert len(events) == 1
        assert events[0].src_ip == "10.0.0.1"  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Endpoint routing
    # ------------------------------------------------------------------

    @respx.mock
    def test_audit_routes_to_data_audit_with_a_query_clause(self, client: NetskopeClient) -> None:
        """audit.yaml:12-72 declares query, not type, and no timeout."""
        route = respx.get(_AUDIT_URL).mock(return_value=httpx.Response(200, json=_EMPTY))
        list(client.events.list("audit", audit_type="admin"))
        params = route.calls.last.request.url.params
        assert params["query"] == 'type eq "admin"'
        assert "type" not in params and "timeout" not in params

    @respx.mock
    def test_audit_accepts_a_query_and_combines_it_with_audit_type(
        self, client: NetskopeClient
    ) -> None:
        """audit.yaml:13-18 documents `query` as the audit filter."""
        route = respx.get(_AUDIT_URL).mock(return_value=httpx.Response(200, json=_EMPTY))
        list(client.events.list("audit", query='user eq "a@ex.com"', audit_type="admin"))
        assert (
            route.calls.last.request.url.params["query"]
            == '(user eq "a@ex.com") and type eq "admin"'
        )

    @respx.mock
    def test_audit_supports_insertion_time_bounds(self, client: NetskopeClient) -> None:
        """audit.yaml:51-72 declares insertionstarttime/insertionendtime."""
        route = respx.get(_AUDIT_URL).mock(return_value=httpx.Response(200, json=_EMPTY))
        list(client.events.list("audit", insertion_start_time=1, insertion_end_time=2))
        params = route.calls.last.request.url.params
        assert params["insertionstarttime"] == "1" and params["insertionendtime"] == "2"

    @respx.mock
    def test_insertion_bounds_rejected_for_datasearch_no_http(self, client: NetskopeClient) -> None:
        """search_network.yaml:218-279 declares no insertion-time parameters."""
        with pytest.raises(ValidationError, match="insertion-time"):
            client.events.list("network", insertion_start_time=1)
        assert len(respx.calls) == 0

    @respx.mock
    def test_infrastructure_routes_to_data_infrastructure(self, client: NetskopeClient) -> None:
        route = respx.get(_INFRA_URL).mock(return_value=httpx.Response(200, json=_EMPTY))
        list(client.events.list("infrastructure", query='status eq "down"'))
        assert route.called
        assert route.calls.last.request.url.path == "/api/v2/events/data/infrastructure"
        assert route.calls.last.request.url.params["query"] == 'status eq "down"'

    @respx.mock
    def test_transaction_is_not_a_record_endpoint_no_http(self, client: NetskopeClient) -> None:
        """transaction_metrics.yaml:65-90 returns one metrics object, not records."""
        with pytest.raises(ValidationError, match="transaction_metrics"):
            client.events.list("transaction")
        assert len(respx.calls) == 0

    @respx.mock
    def test_list_sends_groupbys_and_combined_orderbys(self, client: NetskopeClient) -> None:
        """search_app.yaml:382-399 names these groupbys and orderbys; no sortby exists."""
        route = respx.get(_APP_URL).mock(return_value=httpx.Response(200, json=_EMPTY))
        list(client.events.list("application", group_by="app", order_by="timestamp"))
        params = route.calls.last.request.url.params
        assert params["groupbys"] == "app"
        assert "groupby" not in params
        assert params["orderbys"] == "timestamp DESC"
        assert "sortby" not in params and "sortorder" not in params
        assert params["timeout"] == "180"

    @respx.mock
    def test_list_groupbys_joins_list_and_ascending_sort(self, client: NetskopeClient) -> None:
        route = respx.get(_APP_URL).mock(return_value=httpx.Response(200, json=_EMPTY))
        list(
            client.events.list(
                "application",
                group_by=["app", "user"],
                order_by="timestamp",
                descending=False,
            )
        )
        params = route.calls.last.request.url.params
        assert params["groupbys"] == "app,user"
        assert params["orderbys"] == "timestamp ASC"
        assert "sortby" not in params

    # ------------------------------------------------------------------
    # get()
    # ------------------------------------------------------------------

    @respx.mock
    def test_get_queries_by_id_with_limit_one(self, client: NetskopeClient) -> None:
        route = respx.get(_APP_URL).mock(
            return_value=httpx.Response(
                200, json={"result": [{"_id": "abc123", "user": "alice@ex.com"}]}
            )
        )
        event = client.events.get("abc123")
        assert event.id == "abc123"
        params = route.calls.last.request.url.params
        assert params["query"] == '_id eq "abc123"'
        assert params["limit"] == "1"

    @respx.mock
    def test_get_uses_type_specific_model(self, client: NetskopeClient) -> None:
        respx.get(_NETWORK_URL).mock(
            return_value=httpx.Response(
                200, json={"result": [{"_id": "beef01", "src_ip": "10.0.0.1"}]}
            )
        )
        event = client.events.get("beef01", event_type="network")
        assert isinstance(event, NetworkEvent)
        assert event.src_ip == "10.0.0.1"

    @respx.mock
    def test_get_uses_the_same_endpoint_as_list(self, client: NetskopeClient) -> None:
        """Infrastructure lookups query the data endpoint that list() uses."""
        route = respx.get(_INFRA_URL).mock(
            return_value=httpx.Response(200, json={"result": [{"_id": "beef01"}]})
        )
        assert client.events.get("beef01", event_type="infrastructure").id == "beef01"
        assert route.calls.last.request.url.path == "/api/v2/events/data/infrastructure"

    @respx.mock
    def test_get_rejects_non_hex_id_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            client.events.get("not-hex!")
        assert len(respx.calls) == 0

    @respx.mock
    def test_get_not_found(self, client: NetskopeClient) -> None:
        respx.get(_APP_URL).mock(return_value=httpx.Response(200, json={"result": []}))
        with pytest.raises(NotFoundError):
            client.events.get("deadbeef")

    @respx.mock
    def test_get_rejects_transaction_no_http(self, client: NetskopeClient) -> None:
        """transaction_metrics.yaml:74-83 takes only `hours`; there is no record to fetch."""
        with pytest.raises(ValidationError, match="transaction_metrics"):
            client.events.get("deadbeef", event_type="transaction")
        assert len(respx.calls) == 0

    @respx.mock
    def test_get_audit_looks_up_by_id_through_query(self, client: NetskopeClient) -> None:
        """audit.yaml:13-18 accepts a query, so `_id eq` resolves one audit row."""
        route = respx.get(_AUDIT_URL).mock(
            return_value=httpx.Response(200, json={"result": [{"_id": "beef01"}]})
        )
        assert client.events.get("beef01", event_type="audit").id == "beef01"
        params = route.calls.last.request.url.params
        assert params["query"] == '_id eq "beef01"' and "timeout" not in params


class TestAsyncEventsResource:
    """Tests for aclient.events."""

    @respx.mock
    async def test_get_queries_by_id(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_APP_URL).mock(
            return_value=httpx.Response(200, json={"result": [{"_id": "abc123"}]})
        )
        event = await aclient.events.get("abc123")
        assert event.id == "abc123"
        params = route.calls.last.request.url.params
        assert params["query"] == '_id eq "abc123"'
        assert params["limit"] == "1"

    @respx.mock
    async def test_get_rejects_non_hex_id_no_http(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError):
            await aclient.events.get("zzz")
        assert len(respx.calls) == 0

    @respx.mock
    async def test_get_not_found(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_APP_URL).mock(return_value=httpx.Response(200, json={"result": []}))
        with pytest.raises(NotFoundError):
            await aclient.events.get("deadbeef")

    @respx.mock
    async def test_audit_routing_and_query_clause(self, aclient: AsyncNetskopeClient) -> None:
        """audit.yaml:12-72: the audit type is a query clause, and no timeout is sent."""
        route = respx.get(_AUDIT_URL).mock(return_value=httpx.Response(200, json=_EMPTY))
        paginated = aclient.events.list("audit", audit_type="user")
        _ = [event async for event in paginated]
        params = route.calls.last.request.url.params
        assert params["query"] == 'type eq "user"'
        assert "type" not in params and "timeout" not in params

    @respx.mock
    async def test_audit_type_rejected_for_other_types_no_http(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with pytest.raises(ValidationError, match="audit_type"):
            aclient.events.list("network", audit_type="admin")
        assert len(respx.calls) == 0


_NUMERIC_CLIENT_STATUS = {
    "_id": "cs1",
    "device_id": 4815162342,
    "hostname": 900913,
    "client_version": 105,
    "os": 11,
    "status": 1,
}
_NUMERIC_INCIDENT = {
    "_id": "in1",
    "incident_id": 77,
    "status": 2,
    "assignee": 4242,
    "dlp_profile": 9,
    "dlp_rule": 31,
}


@pytest.mark.parametrize(
    ("event_type", "record"),
    [("clientstatus", _NUMERIC_CLIENT_STATUS), ("incident", _NUMERIC_INCIDENT)],
)
@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@respx.mock
async def test_numeric_record_fields_survive_the_typed_models(
    client: NetskopeClient,
    aclient: AsyncNetskopeClient,
    asynchronous: bool,
    event_type: str,
    record: dict,
) -> None:
    """Tenants report these fields as numbers; the value must reach the caller."""
    respx.get(f"{_BASE}/api/v2/events/datasearch/{event_type}").mock(
        return_value=httpx.Response(200, json={"result": [record], "status": {"total": 1}})
    )
    paginated = (aclient if asynchronous else client).events.list(event_type)
    events = [event async for event in paginated] if asynchronous else list(paginated)
    assert len(events) == 1
    for name, value in record.items():
        if name != "_id":
            assert getattr(events[0], name) == value


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@respx.mock
async def test_undecodable_record_raises_an_sdk_error(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    """A record the model rejects stays inside the NetskopeError hierarchy."""
    respx.get(f"{_BASE}/api/v2/events/datasearch/clientstatus").mock(
        return_value=httpx.Response(
            200,
            json={"result": [{"_id": "cs1", "hostname": {"secret": "value"}}]},
            headers={"x-request-id": "events-1"},
        )
    )
    paginated = (aclient if asynchronous else client).events.list("clientstatus")
    with pytest.raises(ResponseValidationError) as caught:
        if asynchronous:
            _ = [event async for event in paginated]
        else:
            list(paginated)
    assert caught.value.request_path == "/api/v2/events/datasearch/clientstatus"
    assert caught.value.request_id == "events-1"
    assert {error[0][0] for error in caught.value.field_errors} == {"hostname"}
    assert "secret" not in str(caught.value)


def test_event_capabilities_default_to_supporting_jql() -> None:
    """External constructors predate the jql field; audit is the only exception."""
    assert (
        EventQueryCapabilities(
            page_limit=100, scannable=False, projection=False, grouping=False, ordering=False
        ).jql
        is True
    )


@pytest.mark.parametrize("event_type", ["application", "infrastructure", "audit"])
def test_declared_capabilities_state_jql_support(client: NetskopeClient, event_type: str) -> None:
    """Every record endpoint declares `query`, audit included (audit.yaml:13-18)."""
    assert client.events.capabilities(event_type).jql is True


# --- Gateway contract conformance -------------------------------------------------------------
#
# Folded in from the spec-conformance reviews: each test cites the
# production/endpoints file and line whose shape it pins.

_ALERT_URL = f"{CONTRACT_BASE}/api/v2/events/datasearch/alert"
_CONTRACT_APP_URL = f"{CONTRACT_BASE}/api/v2/events/datasearch/application"
_CONTRACT_AUDIT_URL = f"{CONTRACT_BASE}/api/v2/events/data/audit"
_CONTRACT_INFRA_URL = f"{CONTRACT_BASE}/api/v2/events/data/infrastructure"
_EMPTY_RESULT = {"result": [], "status": {}}
_contract_mock = respx.mock(assert_all_mocked=True, assert_all_called=False)


@pytest.mark.parametrize("event_type", ["audit", "infrastructure"])
@pytest.mark.parametrize(
    "kwargs,message",
    [
        ({"fields": ["user"]}, "field projection"),
        ({"group_by": "app"}, "grouping"),
        ({"order_by": "timestamp"}, "ordering"),
        ({"page_size": 5001}, "maximum limit of 5000"),
    ],
)
@_contract_mock
def test_legacy_list_applies_the_declared_capability_gate(
    contract_client: NetskopeClient, event_type: str, kwargs: dict[str, object], message: str
) -> None:
    """The legacy iterator refuses what audit.yaml:12-72 does not declare."""
    with pytest.raises(ValidationError, match=message):
        contract_client.events.list(event_type, **kwargs)
    assert not _contract_mock.calls


@pytest.mark.parametrize("event_type", ["audit", "infrastructure"])
@_contract_mock
async def test_async_legacy_list_applies_the_same_gate(
    contract_aclient: AsyncNetskopeClient, event_type: str
) -> None:
    with pytest.raises(ValidationError, match="maximum limit of 5000"):
        contract_aclient.events.list(event_type, page_size=10000)
    assert not _contract_mock.calls


@pytest.mark.parametrize(
    "url,event_type", [(_CONTRACT_AUDIT_URL, "audit"), (_CONTRACT_INFRA_URL, "infrastructure")]
)
@_contract_mock
def test_legacy_list_still_accepts_the_declared_ceiling(
    contract_client: NetskopeClient, url: str, event_type: str
) -> None:
    """audit.yaml:19-27 allows a limit of exactly 5000."""
    route = _contract_mock.get(url).respond(200, json=_EMPTY_RESULT)
    list(contract_client.events.list(event_type, page_size=5000))
    assert route.calls.last.request.url.params["limit"] == "5000"


@_contract_mock
def test_legacy_list_still_projects_on_a_datasearch_type(contract_client: NetskopeClient) -> None:
    """search_app.yaml declares fields/groupbys/orderbys, so nothing is refused."""
    route = _contract_mock.get(_CONTRACT_APP_URL).respond(200, json=_EMPTY_RESULT)
    list(contract_client.events.list("application", fields=["user"], order_by="timestamp"))
    params = route.calls.last.request.url.params
    assert params["fields"] == "user" and params["orderbys"] == "timestamp DESC"


@_contract_mock
def test_a_fractional_count_no_longer_rejects_the_whole_page(
    contract_client: NetskopeClient,
) -> None:
    """One contract-legal fraction must not reject the page it sits in."""
    _contract_mock.get(_ALERT_URL).respond(
        200, json={"result": [{"_id": "a1", "count": 1.5}, {"_id": "a2", "count": 2}], "status": {}}
    )
    page = contract_client.alerts.list_page(limit=5)
    assert [alert.count for alert in page.items] == [1.5, 2]


@pytest.mark.parametrize("model", [Alert, Event, NetworkEvent, Incident])
def test_the_declared_policy_field_populates_policy_name(model: type) -> None:
    """search_alert.yaml:175-177, search_app.yaml:169, search_network.yaml:94."""
    assert model.model_validate({"policy": "GDrive rule"}).policy_name == "GDrive rule"


def test_the_incident_insertion_timestamp_populates() -> None:
    """search_incident.yaml:265-267 spells it ns_insertion_epoch_timestamp."""
    row = {"ns_insertion_epoch_timestamp": 1719475700}
    assert Event.model_validate(row).insertion_epoch_timestamp == 1719475700
    assert Event.model_validate({"insertion_epoch_timestamp": 42}).insertion_epoch_timestamp == 42


def test_client_status_keeps_ts_without_assuming_a_time_unit() -> None:
    """SPEC2-VERIFY-ID-4: search_clientstatus.yaml:157-159 gives ts no time unit."""
    event = ClientStatusEvent.model_validate({"ts": 1720398866})
    assert event.ts == 1720398866 and event.timestamp is None
    assert ClientStatusEvent.model_validate({"timestamp": 1720398866}).timestamp is not None


def test_last_event_timestamp_stays_a_raw_declared_number() -> None:
    """Its unit is unstated (search_clientstatus.yaml:125-127), so it is not a timestamp."""
    event = ClientStatusEvent.model_validate({"last_event_timestamp": 17146156})
    assert event.last_event_timestamp == 17146156
    assert event.timestamp is None


@_contract_mock
def test_a_client_status_page_decodes_the_nested_and_ts_fields(
    contract_client: NetskopeClient,
) -> None:
    _contract_mock.get(f"{CONTRACT_BASE}/api/v2/events/datasearch/clientstatus").respond(
        200, json={"result": [{"ts": 1720398866, "host_info": {"hostname": "h"}}], "status": {}}
    )
    event = contract_client.events.list_page("clientstatus", limit=1).items[0]
    assert isinstance(event, ClientStatusEvent)
    assert event.hostname == "h" and event.ts == 1720398866
    assert event.timestamp is None


@_contract_mock
def test_alert_get_sends_limit_one(contract_client: NetskopeClient) -> None:
    route = _contract_mock.get(_ALERT_URL).respond(
        200, json={"result": [{"_id": "abc"}], "status": {}}
    )
    assert contract_client.alerts.get("abc").id == "abc"
    params = route.calls.last.request.url.params
    assert params["limit"] == "1" and params["query"] == '_id eq "abc"'


@_contract_mock
async def test_async_alert_get_sends_limit_one(contract_aclient: AsyncNetskopeClient) -> None:
    route = _contract_mock.get(_ALERT_URL).respond(
        200, json={"result": [{"_id": "abc"}], "status": {}}
    )
    assert (await contract_aclient.alerts.get("abc")).id == "abc"
    assert route.calls.last.request.url.params["limit"] == "1"


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda c: c.events.list_page("alert", timeout=None), id="events.list_page"),
        pytest.param(lambda c: list(c.events.list("alert", timeout=None)), id="events.list"),
        pytest.param(lambda c: c.events.get("abc", event_type="alert", timeout=None), id="get"),
    ],
)
@_contract_mock
def test_event_datasearch_timeout_none_sends_the_default(
    contract_client: NetskopeClient, call: object
) -> None:
    route = _contract_mock.get(f"{CONTRACT_BASE}/api/v2/events/datasearch/alert").respond(
        200, json={"result": [{"_id": "abc"}], "status": {}}
    )
    call(contract_client)
    assert route.calls.last.request.url.params["timeout"] == str(DATASEARCH_TIMEOUT_DEFAULT)


@_contract_mock
def test_incident_datasearch_timeout_none_sends_the_default(
    contract_client: NetskopeClient,
) -> None:
    route = _contract_mock.get(f"{CONTRACT_BASE}/api/v2/events/datasearch/incident").respond(
        200, json=_EMPTY_RESULT
    )
    contract_client.incidents.list_page(timeout=None)
    assert route.calls.last.request.url.params["timeout"] == "180"


@pytest.mark.parametrize(
    "url,event_type", [(_CONTRACT_AUDIT_URL, "audit"), (_CONTRACT_INFRA_URL, "infrastructure")]
)
@pytest.mark.parametrize("timeout", [None, 600])
@_contract_mock
def test_audit_and_infrastructure_never_carry_a_timeout(
    contract_client: NetskopeClient, url: str, event_type: str, timeout: int | None
) -> None:
    """audit.yaml:12-72 and infrastructure.yaml:12-72 declare no timeout."""
    route = _contract_mock.get(url).respond(200, json=_EMPTY_RESULT)
    contract_client.events.list_page(event_type, limit=1, timeout=timeout)
    assert "timeout" not in route.calls.last.request.url.params


@_contract_mock
def test_a_declared_read_operation_still_uses_the_retry_budget(
    retrying_client: NetskopeClient,
) -> None:
    """Control for the test above: audit.yaml:100-103 declares access: r."""
    route = _contract_mock.get(_CONTRACT_AUDIT_URL).respond(500, json={"message": "boom"})
    with pytest.raises(ServerError):
        list(retrying_client.events.list("audit"))
    assert route.call_count == 3


ALERT_URL = f"{_BASE}/api/v2/events/datasearch/alert"
INCIDENT_URL = f"{_BASE}/api/v2/events/datasearch/incident"
EMPTY = {"result": [], "status": {"count": 0}}
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
def test_a_caller_can_raise_the_timeout_and_none_selects_the_default(
    client: NetskopeClient,
) -> None:
    """search_alert.yaml:312-319 marks `timeout` required with `default: 180`.

    ``None`` therefore selects the declared default; it cannot omit a required
    parameter.
    """
    route = respx.get(ALERT_URL).respond(200, json=EMPTY)
    client.alerts.list_page(timeout=600)
    assert route.calls.last.request.url.params["timeout"] == "600"
    client.alerts.list_page(timeout=None)
    assert route.calls.last.request.url.params["timeout"] == str(DATASEARCH_TIMEOUT_DEFAULT)


@pytest.mark.parametrize(
    "url,call",
    [
        pytest.param(_AUDIT_URL, lambda c: list(c.events.list("audit")), id="audit"),
        pytest.param(
            _INFRA_URL, lambda c: list(c.events.list("infrastructure")), id="infrastructure"
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
    route = respx.get(_TRANSACTION_URL).respond(200, json={"result": {}})
    client.events.transaction_metrics(hours=48)
    assert dict(route.calls.last.request.url.params) == {"hours": "48"}


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
            _NETWORK_URL,
            lambda c: list(c.events.list("network", order_by="timestamp")),
            id="events.list",
        ),
        pytest.param(
            _NETWORK_URL,
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


@respx.mock
def test_network_rows_report_ip_protocol(client: NetskopeClient) -> None:
    """search_network.yaml:82-84 names the transport protocol field ip_protocol."""
    respx.get(_NETWORK_URL).respond(
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


@respx.mock
def test_client_status_reads_the_nested_host_and_event_fields(client: NetskopeClient) -> None:
    """search_clientstatus.yaml:81-121 nests host_info; :128-151 nests last_seen_device_event.

    ``hostname`` is at :90-92, ``os`` at :110-112, and ``status`` at :143-145.
    """
    respx.get(f"{_BASE}/api/v2/events/datasearch/clientstatus").respond(
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


@pytest.mark.parametrize("event_type", ["audit", "infrastructure"])
def test_the_data_endpoints_cap_a_page_at_five_thousand(
    client: NetskopeClient, event_type: str
) -> None:
    """audit.yaml:19-27 and infrastructure.yaml:19-27 declare maximum: 5000."""
    assert client.events.capabilities(event_type).page_limit == 5000
    with pytest.raises(ValidationError, match="5000"):
        client.events.list_page(event_type, limit=5001)


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
def test_transaction_metrics_decode_the_documented_result_object(client: NetskopeClient) -> None:
    """transaction_metrics.yaml:17-35 names both metric keys inside `result`."""
    respx.get(_TRANSACTION_URL).respond(
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
    respx.get(f"{_BASE}/api/v2/events/datasearch/clientstatus").respond(
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
    route = respx.get(_INFRA_URL).respond(200, json=EMPTY)
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


class TestClientStatusKeepsItsNestedObjects:
    """Flattening a leaf must not discard the object it came from.

    ``NetskopeModel`` sets ``extra="allow"`` so an unmodelled key stays reachable
    (models/common.py). But when an ``AliasPath`` resolves, pydantic marks the
    *container* key as consumed, so ``host_info`` and ``last_seen_device_event``
    would vanish entirely along with every sibling key the SDK does not model.
    """

    _ROW: ClassVar[dict[str, Any]] = {
        "host_info": {
            "hostname": "laptop-1",
            "os": "macOS 15",
            "cpu": "m3",
            "device_model": "MacBookPro18,3",
        },
        "last_seen_device_event": {"status": "ok", "code": 7},
    }

    def test_the_flattened_leaves_are_still_reachable(self) -> None:
        event = ClientStatusEvent.model_validate(self._ROW)
        assert event.hostname == "laptop-1"
        assert event.os == "macOS 15"
        assert event.status == "ok"

    def test_the_container_and_its_unmodelled_siblings_survive(self) -> None:
        event = ClientStatusEvent.model_validate(self._ROW)
        assert event.host_info == self._ROW["host_info"]
        assert event.last_seen_device_event == self._ROW["last_seen_device_event"]
        assert event.host_info is not None
        assert event.host_info["cpu"] == "m3"
        assert event.last_seen_device_event is not None
        assert event.last_seen_device_event["code"] == 7

    def test_flat_rows_still_decode_and_carry_no_container(self) -> None:
        event = ClientStatusEvent.model_validate({"hostname": "h", "os": "linux", "status": "up"})
        assert (event.hostname, event.os, event.status) == ("h", "linux", "up")
        assert event.host_info is None
