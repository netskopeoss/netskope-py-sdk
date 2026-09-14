"""SPEC2 identity/events conformance: one test per accepted finding.

Every test pins a request or a decoded body against
``production/endpoints/<area>/*.yaml`` in the api-gateway-endpoints repo and
cites the lines it was read from.

The tenant is the synthetic ``example.goskope.coken`` behind
``allow_custom_tenant=True``, and every route is declared to respx with
``assert_all_mocked=True``, so no test can reach a real host.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.datasearch import DATASEARCH_TIMEOUT_DEFAULT
from netskope.exceptions import ResponseValidationError, ServerError, ValidationError
from netskope.models.administration import AdminRole
from netskope.models.alerts import Alert
from netskope.models.devices import DeviceTag
from netskope.models.events import ClientStatusEvent, Event, NetworkEvent
from netskope.models.incidents import Incident, IncidentUpdateOutcome
from netskope.models.rbac import (
    RbacRole,
    RbacRoleApiGroup,
    RbacRoleDetail,
    RbacRoleScope,
    RbacRoleSummary,
    RoleMutationReceipt,
)
from netskope.models.tokens import ApiToken
from tests.unit.resources.conftest import sent_json

_TENANT = "example.goskope.coken"
_BASE = f"https://{_TENANT}"

_ALERT_URL = f"{_BASE}/api/v2/events/datasearch/alert"
_APP_URL = f"{_BASE}/api/v2/events/datasearch/application"
_AUDIT_URL = f"{_BASE}/api/v2/events/data/audit"
_INFRA_URL = f"{_BASE}/api/v2/events/data/infrastructure"
_UPDATE_URL = f"{_BASE}/api/v2/incidents/update"
_GET_USERS_URL = f"{_BASE}/api/v2/users/getusers"
_GET_GROUPS_URL = f"{_BASE}/api/v2/users/getgroups"
_TOKENSET_URL = f"{_BASE}/api/v2/enrollment/tokenset"
_SCIM_USERS_URL = f"{_BASE}/api/v2/scim/Users"

_EMPTY = {"result": [], "status": {}}

# respx refuses any request that has no declared route.
mock = respx.mock(assert_all_mocked=True, assert_all_called=False)


@pytest.fixture
def client() -> Iterator[NetskopeClient]:
    with NetskopeClient(
        tenant=_TENANT, api_token="synthetic-token", allow_custom_tenant=True, max_retries=0
    ) as sync_client:
        yield sync_client


@pytest.fixture
async def aclient() -> AsyncIterator[AsyncNetskopeClient]:
    async with AsyncNetskopeClient(
        tenant=_TENANT, api_token="synthetic-token", allow_custom_tenant=True, max_retries=0
    ) as async_client:
        yield async_client


@pytest.fixture
def retrying_client() -> Iterator[NetskopeClient]:
    """A client whose retry budget is nonzero, so an opt-out is observable."""
    with NetskopeClient(
        tenant=_TENANT,
        api_token="synthetic-token",
        allow_custom_tenant=True,
        max_retries=2,
        backoff_factor=0.0,
    ) as sync_client:
        yield sync_client


@pytest.fixture
async def retrying_aclient() -> AsyncIterator[AsyncNetskopeClient]:
    async with AsyncNetskopeClient(
        tenant=_TENANT,
        api_token="synthetic-token",
        allow_custom_tenant=True,
        max_retries=2,
        backoff_factor=0.0,
    ) as async_client:
        yield async_client


# --- SPEC2-EV-1 ------------------------------------------------------------
# events/audit.yaml:12-72 declares only query/limit/offset/starttime/endtime/
# insertionstarttime/insertionendtime, and :19-27 bounds limit at
# maximum: 5000. events/infrastructure.yaml is identical (:19-27).


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
@mock
def test_legacy_list_applies_the_declared_capability_gate(
    client: NetskopeClient, event_type: str, kwargs: dict[str, object], message: str
) -> None:
    """The legacy iterator refuses what audit.yaml:12-72 does not declare."""
    with pytest.raises(ValidationError, match=message):
        client.events.list(event_type, **kwargs)
    assert not mock.calls


@pytest.mark.parametrize("event_type", ["audit", "infrastructure"])
@mock
async def test_async_legacy_list_applies_the_same_gate(
    aclient: AsyncNetskopeClient, event_type: str
) -> None:
    with pytest.raises(ValidationError, match="maximum limit of 5000"):
        aclient.events.list(event_type, page_size=10000)
    assert not mock.calls


@pytest.mark.parametrize("url,event_type", [(_AUDIT_URL, "audit"), (_INFRA_URL, "infrastructure")])
@mock
def test_legacy_list_still_accepts_the_declared_ceiling(
    client: NetskopeClient, url: str, event_type: str
) -> None:
    """audit.yaml:19-27 allows a limit of exactly 5000."""
    route = mock.get(url).respond(200, json=_EMPTY)
    list(client.events.list(event_type, page_size=5000))
    assert route.calls.last.request.url.params["limit"] == "5000"


@mock
def test_legacy_list_still_projects_on_a_datasearch_type(client: NetskopeClient) -> None:
    """search_app.yaml declares fields/groupbys/orderbys, so nothing is refused."""
    route = mock.get(_APP_URL).respond(200, json=_EMPTY)
    list(client.events.list("application", fields=["user"], order_by="timestamp"))
    params = route.calls.last.request.url.params
    assert params["fields"] == "user" and params["orderbys"] == "timestamp DESC"


# --- SPEC2-EV-2 ------------------------------------------------------------
# `type: number` admits a fraction, so a mapped number field must not be
# narrowed to int. Integral values keep decoding as int.


@pytest.mark.parametrize(
    "model,payload,attribute,expected",
    [
        # events/search_alert.yaml:48-50 (cci), :54-56 (count)
        (Alert, {"cci": 1.5}, "cci", 1.5),
        (Alert, {"count": 2.5}, "count", 2.5),
        # events/search_network.yaml:139-141, :73-75, :88-90
        (NetworkEvent, {"srcport": 1.5}, "src_port", 1.5),
        (NetworkEvent, {"dstport": 2.5}, "dst_port", 2.5),
        (NetworkEvent, {"numbytes": 3.5}, "num_bytes", 3.5),
        # rbac/ms-rbac.yaml:1621-1623 (roleId), :1651-1653 (userCount)
        (RbacRoleSummary, {"roleId": 1.5}, "id", 1.5),
        (RbacRoleSummary, {"userCount": 2.5}, "user_count", 2.5),
        (RbacRole, {"roleId": 1.5}, "id", 1.5),
        # rbac/ms-rbac.yaml:2439-2444 and :2529-2534
        (RoleMutationReceipt, {"roleId": 1.5}, "id", 1.5),
        # rbac/ms-rbac.yaml:2231-2233
        (RbacRoleDetail, {"roleId": 1.5}, "id", 1.5),
        # rbac/ms-rbac.yaml:2190-2192
        (RbacRoleApiGroup, {"apiGroupId": 1.5}, "api_group_id", 1.5),
        # rbac/ms-rbac.yaml:2040-2042
        (RbacRoleScope, {"scopeFieldId": 1.5}, "scope_field_id", 1.5),
        # auth/api-tokens.yaml:59-61
        (ApiToken, {"expires": 1.5}, "expires", 1.5),
        # devices/tag.yaml:738-741, :749-753, :754-758
        (DeviceTag, {"id": 1.5}, "id", 1.5),
        (DeviceTag, {"device_count": 2.5}, "device_count", 2.5),
        (DeviceTag, {"device_classification_count": 3.5}, "device_classification_count", 3.5),
        # platform/ms-platform.yaml:336-345, value at :338-339
        (AdminRole, {"value": 1.5}, "value", 1.5),
    ],
)
def test_a_declared_number_field_keeps_its_fraction(
    model: type, payload: dict[str, object], attribute: str, expected: float
) -> None:
    assert getattr(model.model_validate(payload), attribute) == expected


@pytest.mark.parametrize(
    "model,payload,attribute",
    [
        (Alert, {"cci": 89}, "cci"),
        (Alert, {"count": 1}, "count"),
        (NetworkEvent, {"srcport": 53}, "src_port"),
        (RbacRoleSummary, {"roleId": 7}, "id"),
        (ApiToken, {"expires": 2147384600}, "expires"),
        (DeviceTag, {"id": 1}, "id"),
        (AdminRole, {"value": 3}, "value"),
    ],
)
def test_an_integral_number_still_decodes_as_int(
    model: type, payload: dict[str, object], attribute: str
) -> None:
    value = getattr(model.model_validate(payload), attribute)
    assert isinstance(value, int) and not isinstance(value, bool)


def test_cci_no_longer_truncates_and_still_reads_the_legacy_shapes() -> None:
    """search_alert.yaml:48-50 types cci as a number; 1.5 is not 1."""
    assert Alert.model_validate({"cci": 1.5}).cci == 1.5
    assert Alert.model_validate({"cci": "8"}).cci == 8
    assert Alert.model_validate({"cci": ""}).cci is None
    assert Alert.model_validate({}).cci is None


@mock
def test_a_fractional_count_no_longer_rejects_the_whole_page(client: NetskopeClient) -> None:
    """One contract-legal fraction must not reject the page it sits in."""
    mock.get(_ALERT_URL).respond(
        200, json={"result": [{"_id": "a1", "count": 1.5}, {"_id": "a2", "count": 2}], "status": {}}
    )
    page = client.alerts.list_page(limit=5)
    assert [alert.count for alert in page.items] == [1.5, 2]


# --- SPEC2-EV-3 ------------------------------------------------------------


@pytest.mark.parametrize("model", [Alert, Event, NetworkEvent, Incident])
def test_the_declared_policy_field_populates_policy_name(model: type) -> None:
    """search_alert.yaml:175-177, search_app.yaml:169, search_network.yaml:94."""
    assert model.model_validate({"policy": "GDrive rule"}).policy_name == "GDrive rule"


@pytest.mark.parametrize("model", [Alert, Event, Incident])
def test_the_epdlp_spelling_still_wins(model: type) -> None:
    """search_epdlp.yaml:88 is the one schema that spells it policy_name."""
    assert model.model_validate({"policy_name": "epdlp rule"}).policy_name == "epdlp rule"


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


@mock
def test_a_client_status_page_decodes_the_nested_and_ts_fields(client: NetskopeClient) -> None:
    mock.get(f"{_BASE}/api/v2/events/datasearch/clientstatus").respond(
        200, json={"result": [{"ts": 1720398866, "host_info": {"hostname": "h"}}], "status": {}}
    )
    event = client.events.list_page("clientstatus", limit=1).items[0]
    assert isinstance(event, ClientStatusEvent)
    assert event.hostname == "h" and event.ts == 1720398866
    assert event.timestamp is None


# --- SPEC2-EV-4 ------------------------------------------------------------
# search_alert.yaml:340-345 defaults limit to 10000, so a one-record lookup
# states limit=1 and refuses a page that answers a different record.

_TWO_ROWS = {"result": [{"_id": "zzz"}, {"_id": "abc"}], "status": {}}
_WRONG_ROW = {"result": [{"_id": "zzz"}], "status": {}}


@mock
def test_alert_get_sends_limit_one(client: NetskopeClient) -> None:
    route = mock.get(_ALERT_URL).respond(200, json={"result": [{"_id": "abc"}], "status": {}})
    assert client.alerts.get("abc").id == "abc"
    params = route.calls.last.request.url.params
    assert params["limit"] == "1" and params["query"] == '_id eq "abc"'


@mock
async def test_async_alert_get_sends_limit_one(aclient: AsyncNetskopeClient) -> None:
    route = mock.get(_ALERT_URL).respond(200, json={"result": [{"_id": "abc"}], "status": {}})
    assert (await aclient.alerts.get("abc")).id == "abc"
    assert route.calls.last.request.url.params["limit"] == "1"


@pytest.mark.parametrize("body", [_TWO_ROWS, _WRONG_ROW], ids=["multiple", "wrong-id"])
@mock
def test_alert_get_surfaces_refuse_a_mismatched_lookup(
    client: NetskopeClient, body: dict[str, object]
) -> None:
    mock.get(_ALERT_URL).respond(200, json=body)
    with pytest.raises(ResponseValidationError):
        client.alerts.get("abc")
    with pytest.raises(ResponseValidationError):
        client.alerts.with_response.get("abc").parse()


@pytest.mark.parametrize("body", [_TWO_ROWS, _WRONG_ROW], ids=["multiple", "wrong-id"])
@mock
def test_event_get_surfaces_refuse_a_mismatched_lookup(
    client: NetskopeClient, body: dict[str, object]
) -> None:
    mock.get(_APP_URL).respond(200, json=body)
    with pytest.raises(ResponseValidationError):
        client.events.get("abc")
    with pytest.raises(ResponseValidationError):
        client.events.with_response.get("abc").parse()


@pytest.mark.parametrize("body", [_TWO_ROWS, _WRONG_ROW], ids=["multiple", "wrong-id"])
@mock
async def test_async_event_get_surfaces_refuse_a_mismatched_lookup(
    aclient: AsyncNetskopeClient, body: dict[str, object]
) -> None:
    mock.get(_APP_URL).respond(200, json=body)
    with pytest.raises(ResponseValidationError):
        await aclient.events.get("abc")
    with pytest.raises(ResponseValidationError):
        (await aclient.events.with_response.get("abc")).parse()


@mock
async def test_async_alert_get_surfaces_refuse_a_mismatched_lookup(
    aclient: AsyncNetskopeClient,
) -> None:
    mock.get(_ALERT_URL).respond(200, json=_TWO_ROWS)
    with pytest.raises(ResponseValidationError):
        await aclient.alerts.get("abc")
    with pytest.raises(ResponseValidationError):
        (await aclient.alerts.with_response.get("abc")).parse()


# --- SPEC2-EV-5 ------------------------------------------------------------
# incidents/incident_update.yaml:8-14 declares {ok: integer, result: string}
# with no required list and no bounds on ok.


def test_the_update_outcome_is_optional_and_unbounded() -> None:
    assert IncidentUpdateOutcome.model_validate({}).ok is None
    assert IncidentUpdateOutcome.model_validate({"ok": 2}).ok == 2
    assert IncidentUpdateOutcome.model_validate({"result": "Update Successful"}).ok is None


@pytest.mark.parametrize(
    "entry,accepted",
    [
        ({"ok": 1, "result": "Update Successful"}, True),
        ({"result": "Update Successful"}, False),
        ({"ok": 2, "result": "1"}, False),
        ({"ok": 0, "result": "0"}, False),
    ],
)
@mock
def test_a_contract_legal_update_ack_decodes(
    client: NetskopeClient, entry: dict[str, object], accepted: bool
) -> None:
    mock.patch(_UPDATE_URL).respond(200, json={"result": [entry]})
    result = client.incidents.update_one(1, field="status", new_value="x", user="u")
    assert result.accepted is accepted


@mock
def test_a_boolean_ok_flag_is_still_refused(client: NetskopeClient) -> None:
    """incident_update.yaml:10-11 types ok as an integer; JSON true is not one."""
    mock.patch(_UPDATE_URL).respond(200, json={"result": [{"ok": True, "result": 1}]})
    with pytest.raises(ResponseValidationError):
        client.incidents.update_one(1, field="status", new_value="x", user="u")


@pytest.mark.parametrize("body", [{}, {"result": []}, {"result": "garbage"}])
@mock
def test_a_body_that_reports_no_outcome_is_still_refused(
    client: NetskopeClient, body: dict[str, object]
) -> None:
    mock.patch(_UPDATE_URL).respond(200, json=body)
    with pytest.raises(ResponseValidationError):
        client.incidents.update_one(1, field="status", new_value="x", user="u")


# --- SPEC2-EV-6 ------------------------------------------------------------
# timeout is required: true with default: 180 on every /datasearch route
# except clientstatus (search_alert.yaml:312-319, search_app.yaml:343-350,
# search_network.yaml:218-225, search_page.yaml:283-290,
# search_incident.yaml:458-465, search_epdlp.yaml:173-180).


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda c: c.alerts.list_page(timeout=None), id="alerts.list_page"),
        pytest.param(lambda c: list(c.alerts.list(timeout=None)), id="alerts.list"),
        pytest.param(
            lambda c: c.alerts.with_response.aggregate_page(group_by="app", timeout=None),
            id="alerts.aggregate_page",
        ),
        pytest.param(lambda c: c.alerts.get("abc", timeout=None), id="alerts.get"),
        pytest.param(
            lambda c: c.alerts.with_response.list_page(timeout=None).parse(),
            id="alerts.with_response.list_page",
        ),
    ],
)
@mock
def test_timeout_none_sends_the_declared_default(client: NetskopeClient, call: object) -> None:
    route = mock.get(_ALERT_URL).respond(200, json={"result": [{"_id": "abc"}], "status": {}})
    call(client)
    assert route.calls.last.request.url.params["timeout"] == str(DATASEARCH_TIMEOUT_DEFAULT)


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda c: c.events.list_page("alert", timeout=None), id="events.list_page"),
        pytest.param(lambda c: list(c.events.list("alert", timeout=None)), id="events.list"),
        pytest.param(lambda c: c.events.get("abc", event_type="alert", timeout=None), id="get"),
    ],
)
@mock
def test_event_datasearch_timeout_none_sends_the_default(
    client: NetskopeClient, call: object
) -> None:
    route = mock.get(f"{_BASE}/api/v2/events/datasearch/alert").respond(
        200, json={"result": [{"_id": "abc"}], "status": {}}
    )
    call(client)
    assert route.calls.last.request.url.params["timeout"] == str(DATASEARCH_TIMEOUT_DEFAULT)


@mock
def test_incident_datasearch_timeout_none_sends_the_default(client: NetskopeClient) -> None:
    route = mock.get(f"{_BASE}/api/v2/events/datasearch/incident").respond(200, json=_EMPTY)
    client.incidents.list_page(timeout=None)
    assert route.calls.last.request.url.params["timeout"] == "180"


@pytest.mark.parametrize("url,event_type", [(_AUDIT_URL, "audit"), (_INFRA_URL, "infrastructure")])
@pytest.mark.parametrize("timeout", [None, 600])
@mock
def test_audit_and_infrastructure_never_carry_a_timeout(
    client: NetskopeClient, url: str, event_type: str, timeout: int | None
) -> None:
    """audit.yaml:12-72 and infrastructure.yaml:12-72 declare no timeout."""
    route = mock.get(url).respond(200, json=_EMPTY)
    client.events.list_page(event_type, limit=1, timeout=timeout)
    assert "timeout" not in route.calls.last.request.url.params


@pytest.mark.parametrize("timeout", [0, -1, True, "180"])
@mock
def test_an_unusable_timeout_still_fails_before_http(
    client: NetskopeClient, timeout: object
) -> None:
    with pytest.raises(ValidationError):
        client.alerts.list_page(timeout=timeout)
    assert not mock.calls


# --- SPEC2-ID-1 ------------------------------------------------------------
# users/usermanager.yaml:1190-1204; Pagination.limit is minimum 0/maximum
# 1000 and Pagination.offset is minimum 0, both required.


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda c: c.users.list(limit=5000), id="users.list-limit"),
        pytest.param(lambda c: c.users.list(offset=-1), id="users.list-offset"),
        pytest.param(lambda c: c.users.groups.list(limit=5000), id="groups.list"),
        pytest.param(lambda c: c.users.groups.members("G", limit=5000), id="groups.members"),
    ],
)
@mock
def test_legacy_user_paging_is_bounded_before_http(client: NetskopeClient, call: object) -> None:
    with pytest.raises(ValidationError, match=r"limit must be 0\.\.1000"):
        call(client)
    assert not mock.calls


@mock
async def test_async_legacy_user_paging_is_bounded_before_http(
    aclient: AsyncNetskopeClient,
) -> None:
    for call in (
        aclient.users.list(limit=5000),
        aclient.users.groups.list(limit=5000),
        aclient.users.groups.members("G", offset=-1),
    ):
        with pytest.raises(ValidationError):
            await call
    assert not mock.calls


@mock
def test_a_legal_legacy_page_still_reaches_the_wire(client: NetskopeClient) -> None:
    """usermanager.yaml:1190-1204 permits limit 1000 and offset 0."""
    users = mock.post(_GET_USERS_URL).respond(200, json={"data": [], "counts": {}})
    groups = mock.post(_GET_GROUPS_URL).respond(200, json={"data": [], "counts": {}})
    client.users.list(limit=1000, offset=0)
    client.users.groups.list(limit=0)
    assert sent_json(users) == {"query": {"paging": {"limit": 1000, "offset": 0}}}
    assert sent_json(groups) == {"query": {"paging": {"limit": 0, "offset": 0}}}


@mock
def test_a_legacy_filter_still_travels_with_the_paging_block(client: NetskopeClient) -> None:
    route = mock.post(_GET_USERS_URL).respond(200, json={"data": [], "counts": {}})
    client.users.get("alice@example.com")
    assert sent_json(route) == {
        "query": {
            "paging": {"limit": 1, "offset": 0},
            "filter": {"and": [{"emails": {"eq": "alice@example.com"}}]},
        }
    }


# --- SPEC2-ID-2 ------------------------------------------------------------
# enrollment-service-configuration.yaml:50-52 declares
# TokensetController_getTokenSets and :81 marks it access: rw, the same level
# as the sibling create POST at :47.


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda c: c.enrollment.list_token_sets(), id="legacy"),
        pytest.param(
            lambda c: c.enrollment.with_response.list_token_sets().parse(), id="with_response"
        ),
    ],
)
@mock
def test_the_tokenset_read_is_not_replayed(retrying_client: NetskopeClient, call: object) -> None:
    route = mock.get(_TOKENSET_URL).respond(500, json={"message": "boom"})
    with pytest.raises(ServerError):
        call(retrying_client)
    assert route.call_count == 1


@pytest.mark.parametrize("typed", [False, True], ids=["legacy", "with_response"])
@mock
async def test_the_async_tokenset_read_is_not_replayed(
    retrying_aclient: AsyncNetskopeClient, typed: bool
) -> None:
    route = mock.get(_TOKENSET_URL).respond(500, json={"message": "boom"})
    with pytest.raises(ServerError):
        if typed:
            (await retrying_aclient.enrollment.with_response.list_token_sets()).parse()
        else:
            await retrying_aclient.enrollment.list_token_sets()
    assert route.call_count == 1


@mock
def test_a_declared_read_operation_still_uses_the_retry_budget(
    retrying_client: NetskopeClient,
) -> None:
    """Control for the test above: audit.yaml:100-103 declares access: r."""
    route = mock.get(_AUDIT_URL).respond(500, json={"message": "boom"})
    with pytest.raises(ServerError):
        list(retrying_client.events.list("audit"))
    assert route.call_count == 3


@mock
def test_the_tokenset_read_still_decodes_its_bare_array(client: NetskopeClient) -> None:
    """TokenSetResponse (enrollment-service-configuration.yaml:744-773)."""
    mock.get(_TOKENSET_URL).respond(200, json=[{"tsid": 1, "enforce_status": 0}])
    token_sets = client.enrollment.list_token_sets()
    assert [token_set.id for token_set in token_sets] == [1]


# --- SPEC2-ID-3 ------------------------------------------------------------
# SCIM 2xx bodies are application/scim+json;charset=utf-8 (scim-apis.yaml:1029,
# :1260, :1711) while every documented SCIM error body is application/json and
# only that (:1195, :1218, :1228).

_SCIM_ACCEPT = "application/scim+json;charset=utf-8, application/json"


@mock
def test_scim_accept_lists_both_documented_media_types(client: NetskopeClient) -> None:
    route = mock.get(_SCIM_USERS_URL).respond(
        200, json={"Resources": [], "totalResults": 0, "startIndex": 1}
    )
    client.scim.users.list_page(count=1)
    assert route.calls.last.request.headers["Accept"] == _SCIM_ACCEPT


@mock
def test_scim_content_type_remains_the_bare_scim_type(client: NetskopeClient) -> None:
    route = mock.post(_SCIM_USERS_URL).respond(
        201, json={"id": "u1", "userName": "a@b.c", "active": True}
    )
    client.scim.users.create("a@b.c", email="a@b.c")
    headers = route.calls.last.request.headers
    assert headers["Content-Type"] == "application/scim+json;charset=utf-8"
    assert headers["Accept"] == _SCIM_ACCEPT


@mock
def test_the_platform_admin_scim_route_keeps_plain_json(client: NetskopeClient) -> None:
    """ms-platform.yaml's admin SCIM route is plain application/json."""
    route = mock.get(f"{_BASE}/api/v2/platform/administration/scim/Users").respond(
        200, json={"Resources": [], "totalResults": 0, "startIndex": 1}
    )
    client.rbac.admins.list_page(count=1)
    assert route.calls.last.request.headers["Accept"] == "application/json"
