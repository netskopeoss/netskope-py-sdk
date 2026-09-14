"""Validated tag writes, original responses, and mutation retry safety."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx
from pydantic import ValidationError as PydanticValidationError

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import (
    APIError,
    ConnectionError,
    ResponseValidationError,
    TimeoutError,
    ValidationError,
)
from netskope.models.devices import DeviceTag, DeviceTagCreate, DeviceTagPatch

_PATH = "/api/v2/devices/device/tags"
_URL = f"https://t.goskope.com{_PATH}"
_TAG = {
    "id": "7",
    "name": "Production",
    "description": "Production devices",
    "future": {"code": "007"},
}


def test_request_models_preserve_omission_and_are_frozen() -> None:
    create = DeviceTagCreate(name="Production-1")
    patch = DeviceTagPatch(description="Updated description")
    assert create.model_dump(exclude_unset=True) == {"name": "Production-1"}
    assert patch.model_dump(exclude_unset=True) == {"description": "Updated description"}
    with pytest.raises(PydanticValidationError):
        create.name = "changed"  # type: ignore[misc]
    with pytest.raises(PydanticValidationError):
        patch.description = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("name", ["Production Server-1", "Production\tServer"])
def test_request_text_matches_pinned_schema(name: str) -> None:
    assert DeviceTagCreate(name=name).name == name


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (DeviceTagCreate, {"name": ""}),
        (DeviceTagCreate, {"name": "bad_name"}),
        (DeviceTagCreate, {"name": 42}),
        (DeviceTagCreate, {"name": True}),
        (DeviceTagCreate, {"name": None}),
        (DeviceTagCreate, {"name": "prod", "description": ""}),
        (DeviceTagCreate, {"name": "prod", "description": None}),
        (DeviceTagCreate, {"name": "prod", "type": "custom"}),
        (DeviceTagPatch, {}),
        (DeviceTagPatch, {"description": ""}),
        (DeviceTagPatch, {"description": None}),
        (DeviceTagPatch, {"name": None, "description": "new"}),
        (DeviceTagPatch, {"description": "bad_description"}),
        (DeviceTagPatch, {"description": 1}),
        (DeviceTagPatch, {"name": "prod", "type": "custom"}),
    ],
)
def test_request_models_reject_unsupported_values(
    model: type[DeviceTagCreate] | type[DeviceTagPatch], payload: dict[str, Any]
) -> None:
    with pytest.raises(PydanticValidationError):
        model.model_validate(payload)


@respx.mock
def test_create_is_one_write_with_original_response(client: NetskopeClient) -> None:
    body = {"success": True, "data": _TAG, "version": "v1"}
    route = respx.post(_URL).respond(201, json=body, headers={"x-request-id": "created-tag"})
    response = client.devices.tags.with_response.create(
        "Production", description="Production devices"
    )
    assert json.loads(route.calls.last.request.content) == {
        "name": "Production",
        "description": "Production devices",
    }
    assert not route.calls.last.request.url.params
    tag = response.parse()
    assert isinstance(tag, DeviceTag) and tag.id == 7
    assert response.parse() is tag
    assert tag.model_extra == {"future": {"code": "007"}}
    assert response.json() == body
    assert response.request_id == "created-tag"
    assert route.call_count == 1


@respx.mock
@pytest.mark.parametrize("body", [{"data": _TAG}, {"result": _TAG}, _TAG])
def test_existing_create_keeps_typed_return_for_supported_singletons(
    client: NetskopeClient, body: dict[str, Any]
) -> None:
    route = respx.post(_URL).respond(201, json=body)
    tag = client.devices.tags.create("Production", description=None)
    assert isinstance(tag, DeviceTag) and tag.id == 7
    assert json.loads(route.calls.last.request.content) == {"name": "Production"}
    assert route.call_count == 1


@respx.mock
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"name": "Renamed"}, {"name": "Renamed"}),
        ({"name": None, "description": "Updated"}, {"description": "Updated"}),
        (
            {"name": "Renamed", "description": "Updated"},
            {"name": "Renamed", "description": "Updated"},
        ),
    ],
)
def test_patch_sends_only_supplied_fields(
    client: NetskopeClient, kwargs: dict[str, Any], expected: dict[str, str]
) -> None:
    route = respx.patch(f"{_URL}/7").respond(200, json={"success": True, "data": _TAG})
    response = client.devices.tags.with_response.update("7", **kwargs)
    assert response.parse().id == 7
    assert response.json()["data"]["id"] == "7"
    assert json.loads(route.calls.last.request.content) == expected
    assert route.call_count == 1


@respx.mock
@pytest.mark.parametrize("operation", ["create", "update"])
@pytest.mark.parametrize("value", ["", "bad_name", 123, True])
def test_resource_validation_is_sdk_error_before_http(
    client: NetskopeClient, operation: str, value: Any
) -> None:
    with pytest.raises(ValidationError):
        if operation == "create":
            client.devices.tags.with_response.create(value)
        else:
            client.devices.tags.with_response.update(7, description=value)
    assert not respx.calls


@respx.mock
def test_empty_patch_and_bad_id_fail_before_http(client: NetskopeClient) -> None:
    with pytest.raises(ValidationError, match="Nothing to update"):
        client.devices.tags.with_response.update(7)
    with pytest.raises(ValidationError):
        client.devices.tags.with_response.update("not-an-id", name="Production")
    assert not respx.calls


@respx.mock
@pytest.mark.parametrize("operation", ["create", "update"])
@pytest.mark.parametrize(
    "body",
    [
        None,
        [],
        {},
        {"success": True},
        {"data": []},
        {"data": None},
        {"data": {"name": "prod"}},
        {"data": {"id": True}},
    ],
)
def test_malformed_write_response_remains_inspectable(
    client: NetskopeClient, operation: str, body: Any
) -> None:
    path = _PATH if operation == "create" else f"{_PATH}/7"
    method = "POST" if operation == "create" else "PATCH"
    route = respx.request(method, f"https://t.goskope.com{path}").respond(
        200, content=json.dumps(body), headers={"x-request-id": "bad-write-response"}
    )
    response = (
        client.devices.tags.with_response.create("prod")
        if operation == "create"
        else client.devices.tags.with_response.update(7, name="prod")
    )
    with pytest.raises(ResponseValidationError) as exc:
        response.parse()
    assert exc.value.request_method == method
    assert exc.value.request_path == path
    assert exc.value.request_id == "bad-write-response"
    assert response.json() == body
    assert route.call_count == 1


@respx.mock
def test_update_rejects_wrong_identity(client: NetskopeClient) -> None:
    route = respx.patch(f"{_URL}/8").respond(200, json={"data": _TAG})
    response = client.devices.tags.with_response.update(8, description="Updated")
    with pytest.raises(ResponseValidationError):
        response.parse()
    assert response.json()["data"]["id"] == "7"
    assert route.call_count == 1


@respx.mock
@pytest.mark.parametrize("operation", ["create", "update", "delete"])
@pytest.mark.parametrize("status", [429, 500])
def test_mutations_are_not_retried(client: NetskopeClient, operation: str, status: int) -> None:
    method = {"create": "POST", "update": "PATCH", "delete": "DELETE"}[operation]
    url = _URL if operation == "create" else f"{_URL}/7"
    route = respx.request(method, url).respond(status, json={"message": "Failed"})
    with pytest.raises(APIError):
        if operation == "create":
            client.devices.tags.create("prod")
        elif operation == "update":
            client.devices.tags.update(7, name="prod")
        else:
            client.devices.tags.delete(7)
    assert route.call_count == 1


@respx.mock
@pytest.mark.parametrize("error", [httpx.ReadTimeout, httpx.ConnectError])
def test_create_network_failures_are_not_replayed(
    client: NetskopeClient, error: type[httpx.RequestError]
) -> None:
    route = respx.post(_URL).mock(side_effect=error("Request interrupted"))
    with pytest.raises((ConnectionError, TimeoutError)):
        client.devices.tags.create("prod")
    assert route.call_count == 1


@respx.mock
async def test_async_create_update_and_omission(aclient: AsyncNetskopeClient) -> None:
    create = respx.post(_URL).respond(201, json={"data": _TAG})
    update = respx.patch(f"{_URL}/7").respond(200, json={"data": _TAG})
    response = await aclient.devices.tags.with_response.create("Production")
    assert response.parse().id == 7 and response.json()["data"]["id"] == "7"
    assert json.loads(create.calls.last.request.content) == {"name": "Production"}
    tag = await aclient.devices.tags.update(7, description="Updated")
    assert isinstance(tag, DeviceTag) and tag.id == 7
    assert json.loads(update.calls.last.request.content) == {"description": "Updated"}
    assert create.call_count == update.call_count == 1


@respx.mock
async def test_async_validation_and_malformed_response(aclient: AsyncNetskopeClient) -> None:
    with pytest.raises(ValidationError):
        await aclient.devices.tags.with_response.update(7, description="")
    assert not respx.calls
    route = respx.post(_URL).respond(201, json={"data": None})
    response = await aclient.devices.tags.with_response.create("prod")
    with pytest.raises(ResponseValidationError) as exc:
        response.parse()
    assert exc.value.request_path == _PATH
    assert response.json() == {"data": None}
    assert route.call_count == 1


@respx.mock
@pytest.mark.parametrize("operation", ["create", "update", "delete"])
@pytest.mark.parametrize("status", [429, 500])
async def test_async_mutations_are_not_retried(
    aclient: AsyncNetskopeClient, operation: str, status: int
) -> None:
    method = {"create": "POST", "update": "PATCH", "delete": "DELETE"}[operation]
    url = _URL if operation == "create" else f"{_URL}/7"
    route = respx.request(method, url).respond(status, json={"message": "Failed"})
    with pytest.raises(APIError):
        if operation == "create":
            await aclient.devices.tags.create("prod")
        elif operation == "update":
            await aclient.devices.tags.update(7, name="prod")
        else:
            await aclient.devices.tags.delete(7)
    assert route.call_count == 1
