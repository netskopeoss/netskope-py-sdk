"""Incident read decoding, canonical anomaly filters, and write safety."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
import respx

from netskope.exceptions import APIError, ResponseValidationError, ValidationError

BASE = "https://t.goskope.com"
ID = 1807262583165050077
UCI_ENTRIES = pytest.mark.parametrize("entry", ["typed", "plain"])


def uci_call(sdk, entry, username, from_time):
    """Invoke either UCI entry point; both build the same validated request."""
    resource = sdk.incidents
    if entry == "typed":
        return resource.with_response.get_uci(username, from_time=from_time)
    return resource.get_uci(username, from_time=from_time)


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("target", ["incident", "object"])
@respx.mock
async def test_explicit_update_targets_preserve_precision_and_one_write(
    client, aclient, asynchronous, target
):
    route = respx.patch(BASE + "/api/v2/incidents/update").respond(
        200, json={"result": [{"ok": 1, "result": "1", "future": True}]}
    )
    resource = (aclient if asynchronous else client).incidents.with_response
    options = {"field": "status", "new_value": "custom_status", "user": "analyst"}
    result = (
        resource.update_one(ID, **options)
        if target == "incident"
        else resource.update_object("object-a", old_value="new", **options)
    )
    if asynchronous:
        result = await result
    parsed = result.parse()
    assert parsed.accepted and parsed.accepted_entries == 1
    assert parsed.outcomes[0].model_extra == {"future": True}
    body = json.loads(route.calls.last.request.content)
    expected = {
        **options,
        **(
            {"incident_id": ID}
            if target == "incident"
            else {"object_id": "object-a", "old_value": "new"}
        ),
    }
    assert body == {"payload": [expected]}
    assert result.json()["result"][0]["result"] == "1"
    assert route.call_count == 1


@pytest.mark.parametrize(
    "method,args,kwargs",
    [
        ("update_one", ("123",), {"field": "status", "new_value": "new", "user": "a"}),
        ("update_one", (True,), {"field": "status", "new_value": "new", "user": "a"}),
        ("update_one", (123,), {"field": "other", "new_value": "new", "user": "a"}),
        (
            "update_object",
            ("object",),
            {"field": "status", "old_value": None, "new_value": "new", "user": "a"},
        ),
        ("add_note", ("id", "x" * 512), {}),
        ("get_anomalies", ([],), {}),
        ("get_anomalies", (["u"],), {"severity": "High"}),
        ("get_anomalies", (["u"],), {"offset": -1}),
    ],
)
@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_request_validation_precedes_http(
    client, aclient, asynchronous, method, args, kwargs
):
    resource = (aclient if asynchronous else client).incidents.with_response
    with pytest.raises(ValidationError):
        response = getattr(resource, method)(*args, **kwargs)
        if asynchronous:
            await response
    assert not respx.calls


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_anomalies_query_parameters_and_results_envelope(client, aclient, asynchronous):
    route = respx.post(BASE + "/api/v2/incidents/users/getanomalies").respond(
        200,
        json={
            "results": [{"anomalyId": "a", "time": "1700000000000", "score": "007", "user": "u"}],
            "totalCount": "1",
        },
    )
    resource = (aclient if asynchronous else client).incidents.with_response
    response = resource.get_anomalies(
        ["u"], timeframe=7, limit=5, offset=1, sort_by="severity", sort_order="asc"
    )
    if asynchronous:
        response = await response
    parsed = response.parse()[0]
    assert parsed.id == "a" and parsed.score == 7 and parsed.time == 1700000000000
    assert response.json()["results"][0]["score"] == "007"
    assert json.loads(route.calls.last.request.content) == {"users": ["u"], "timeframe": 7}
    assert dict(route.calls.last.request.url.params) == {
        "limit": "5",
        "offset": "1",
        "sortby": "severity",
        "sortorder": "asc",
    }


@UCI_ENTRIES
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    "from_time",
    [1700000000000, datetime.fromtimestamp(1700000000, tz=UTC)],
    ids=["epoch-milliseconds", "aware-datetime"],
)
@respx.mock
async def test_uci_is_a_millisecond_time_series(client, aclient, asynchronous, entry, from_time):
    payload = {"userId": "u", "confidences": [{"start": "1700000000000", "confidenceScore": "007"}]}
    route = respx.post(BASE + "/api/v2/ubadatasvc/user/uci").respond(200, json=payload)
    response = uci_call(aclient if asynchronous else client, entry, "u", from_time)
    if asynchronous:
        response = await response
    uci = response.parse() if entry == "typed" else response
    assert uci.confidences[0].confidence_score == 7
    if entry == "typed":
        assert response.json() == payload
    assert json.loads(route.calls.last.request.content) == {"user": "u", "fromTime": 1700000000000}


@UCI_ENTRIES
@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize(
    "username",
    ["alice", "alice@example.com", r"EXAMPLE\alice", "  alice@example.com  "],
    ids=["simple", "email", "domain-qualified", "surrounding-whitespace"],
)
@respx.mock
async def test_uci_preserves_username_and_epoch_zero(
    client, aclient, asynchronous, entry, username
):
    payload = {"userId": username, "confidences": [{"start": "0", "confidenceScore": "007"}]}
    route = respx.post(BASE + "/api/v2/ubadatasvc/user/uci").respond(200, json=payload)
    response = uci_call(aclient if asynchronous else client, entry, username, 0)
    if asynchronous:
        response = await response
    uci = response.parse() if entry == "typed" else response
    assert uci.user_id == username
    if entry == "typed":
        assert response.json() == payload
    assert json.loads(route.calls.last.request.content) == {"user": username, "fromTime": 0}
    assert not route.calls.last.request.url.params
    assert route.call_count == 1


@UCI_ENTRIES
@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize(
    "username",
    ["", " \t\r\n", None, 123, True, b"alice", ["alice"]],
    ids=["empty", "blank", "none", "integer", "boolean", "bytes", "list"],
)
@respx.mock
async def test_uci_rejects_blank_or_nonstring_usernames_before_http(
    client, aclient, asynchronous, entry, username
):
    sdk = aclient if asynchronous else client
    with pytest.raises(ValidationError, match="username"):
        response = uci_call(sdk, entry, username, 0)
        if asynchronous:
            await response
    assert not respx.calls


@UCI_ENTRIES
@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize(
    "from_time",
    [True, "1700000000000", 1.5, datetime(2024, 1, 1)],
    ids=["boolean", "string", "float", "naive-datetime"],
)
@respx.mock
async def test_uci_rejects_invalid_from_time_before_http(
    client, aclient, asynchronous, entry, from_time
):
    sdk = aclient if asynchronous else client
    with pytest.raises(ValidationError, match="from_time"):
        response = uci_call(sdk, entry, "alice", from_time)
        if asynchronous:
            await response
    assert not respx.calls


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_notes_forensics_and_empty_delete_parity(client, aclient, asynchronous):
    prefix = "/api/v2/incidents/dlpincidents/a%2Fb"
    forensics = respx.get(BASE + prefix + "/forensics").respond(
        200, json={"data": {"meta": "{}", "content": "sensitive"}, "status": "success"}
    )
    listing = respx.get(BASE + prefix + "/notes").respond(
        200, json={"data": [{"note_id": "n", "timestamp": "1000", "content": "text"}]}
    )
    adding = respx.post(BASE + prefix + "/notes").respond(
        200, json={"data": {"note_id": "n", "content": "text"}}
    )
    deletion = respx.delete(BASE + prefix + "/notes/n").respond(204)
    resource = (aclient if asynchronous else client).incidents.with_response
    responses = []
    for method, args in [
        ("get_forensics", ("a/b",)),
        ("list_notes", ("a/b",)),
        ("add_note", ("a/b", "text")),
        ("delete_note", ("a/b", "n")),
    ]:
        response = getattr(resource, method)(*args)
        responses.append(await response if asynchronous else response)
    assert responses[0].parse().content == "sensitive"
    assert responses[1].parse()[0].timestamp == 1000
    assert responses[2].parse().note_id == "n"
    assert responses[3].parse() is None
    assert json.loads(adding.calls.last.request.content) == {"content": "text"}
    assert all(route.call_count == 1 for route in (forensics, listing, adding, deletion))


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"result": []},
        {"result": "garbage"},
        {"result": [{"result": 1}]},
        {"result": [{"ok": True, "result": 1}]},
        {"result": [{"ok": 1, "result": 1.5}]},
    ],
)
@respx.mock
def test_malformed_success_retains_response_without_replay(client, payload):
    route = respx.patch(BASE + "/api/v2/incidents/update").respond(200, json=payload)
    response = client.incidents.with_response.update_one(
        ID, field="status", new_value="new", user="a"
    )
    with pytest.raises(ResponseValidationError) as caught:
        response.parse()
    assert caught.value.request_path == "/api/v2/incidents/update"
    assert response.json() == payload and route.call_count == 1


@respx.mock
def test_zero_acceptance_does_not_claim_a_change(client):
    respx.patch(BASE + "/api/v2/incidents/update").respond(200, json={"ok": 1, "result": "0"})
    result = client.incidents.update_one(ID, field="status", new_value="new", user="a")
    assert not result.accepted and result.accepted_entries == 0


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize(
    "payload,count,accepted",
    [
        ({"ok": 1, "result": "Update Successful"}, None, True),
        ({"ok": 1}, None, True),
        ({"ok": 1, "result": 3}, 3, True),
        ({"ok": 1, "result": "0"}, 0, False),
    ],
    ids=["message", "omitted", "count", "zero-count"],
)
@respx.mock
async def test_acceptance_follows_the_ok_flag(
    client, aclient, asynchronous, payload, count, accepted
):
    """incident_update.yaml:8-14 types result as a string, so ok carries the outcome.

    The documented success body is {"result": [{"ok": 1, "result": "Update
    Successful"}]} (incident_update.yaml:69-75): a message is an acknowledgement,
    not a refusal. A reported count of zero still contradicts acceptance.
    """
    route = respx.patch(BASE + "/api/v2/incidents/update").respond(200, json=payload)
    resource = (aclient if asynchronous else client).incidents
    result = resource.update_one(ID, field="status", new_value="new", user="a")
    if asynchronous:
        result = await result
    assert result.outcomes[0].ok == 1
    assert result.outcomes[0].count == count
    assert result.accepted is accepted
    assert result.accepted_entries == (count or 0)
    assert route.call_count == 1


@respx.mock
def test_a_failed_entry_withdraws_acceptance(client):
    """incident_update.yaml:83-89 wraps failure items in the same {result: [...]} envelope."""
    respx.patch(BASE + "/api/v2/incidents/update").respond(
        200, json={"result": [{"ok": 0, "result": "Update Failed"}]}
    )
    result = client.incidents.update_one(ID, field="status", new_value="new", user="a")
    assert not result.accepted and result.accepted_entries == 0


@respx.mock
def test_note_identity_is_not_replaced_by_an_extension_named_data(client):
    body = {
        "note_id": "001",
        "content": "note",
        "data": {"note_id": "extension", "content": "metadata"},
    }
    route = respx.post(BASE + "/api/v2/incidents/dlpincidents/123/notes").respond(200, json=body)
    response = client.incidents.with_response.add_note("123", "note")
    assert response.parse().note_id == "001"
    assert response.json() == body and route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("operation", ["update_one", "add_note", "delete_note"])
@respx.mock
async def test_writes_are_never_replayed(client, aclient, asynchronous, operation):
    path = (
        "/api/v2/incidents/update"
        if operation == "update_one"
        else "/api/v2/incidents/dlpincidents/a/notes"
    )
    method = "PATCH" if operation == "update_one" else "POST"
    if operation == "delete_note":
        method, path = "DELETE", path + "/n"
    route = respx.route(method=method, url=BASE + path).respond(503, json={"message": "temporary"})
    resource = (aclient if asynchronous else client).incidents.with_response
    args = (ID,) if operation == "update_one" else ("a", "n")
    kwargs = (
        {"field": "status", "new_value": "new", "user": "u"} if operation == "update_one" else {}
    )
    with pytest.raises(APIError):
        response = getattr(resource, operation)(*args, **kwargs)
        if asynchronous:
            await response
    assert route.call_count == 1


@respx.mock
def test_bounded_incident_page_and_legacy_update_remain_distinct(client):
    read = respx.get(BASE + "/api/v2/events/datasearch/incident").respond(
        200, json={"result": [{"_id": "a", "incident_id": ID}], "total": "10"}
    )
    page = client.incidents.list_page(
        fields=["incident_id"], order_by="timestamp", descending=True, limit=2
    )
    assert page.total == 10 and page.items[0].incident_id == ID
    assert read.calls.last.request.url.params["orderbys"] == "timestamp DESC"
    write = respx.patch(BASE + "/api/v2/incidents/update").respond(
        200, json={"ok": 1, "result": "1"}
    )
    assert isinstance(
        client.incidents.update(
            "legacy-object", field="status", old_value="new", new_value="closed", user="u"
        ),
        dict,
    )
    assert (
        json.loads(write.calls.last.request.content)["payload"][0]["object_id"] == "legacy-object"
    )
