"""Publisher-related accessors preserve the response while exposing typed results."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx
from pydantic import BaseModel

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ResponseValidationError
from netskope.models.infrastructure import LocalBroker, PublisherUpgradeProfile
from netskope.models.publishers import PublisherActionResult, PublisherApp, PublisherRelease
from netskope.response import ApiResponse
from tests.unit.resources.conftest import sent_json

_BASE = "https://t.goskope.com/api/v2/infrastructure"
_APP = {
    "app_id": "7",
    "app_name": "wiki",
    "host": "wiki.internal",
    "protocol": "tcp",
    "future": {"enabled": False},
}
_COLLECTIONS = [
    (
        "publishers",
        "list_apps",
        (42,),
        f"{_BASE}/publishers/42/apps",
        {"data": {"apps": [_APP]}, "status": "success"},
        PublisherApp,
    ),
    (
        "publishers",
        "list_releases",
        (),
        f"{_BASE}/publishers/releases",
        {"data": [{"version": "100", "name": "Latest", "is_recommended": True}]},
        PublisherRelease,
    ),
    (
        "npa.upgrade_profiles",
        "list",
        (),
        f"{_BASE}/publisherupgradeprofiles",
        {
            "data": {"upgrade_profiles": [{"external_id": 5, "name": "Weekly", "enabled": True}]},
            "total": 1,
        },
        PublisherUpgradeProfile,
    ),
    (
        "npa.local_brokers",
        "list",
        (),
        f"{_BASE}/lbrokers",
        {"data": [{"id": 10, "name": "datacenter", "city_name": "Cupertino"}], "total": 1},
        LocalBroker,
    ),
]


def _resource(client: NetskopeClient | AsyncNetskopeClient, name: str) -> Any:
    resource: Any = client
    for segment in name.split("."):
        resource = getattr(resource, segment)
    return resource


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(("namespace", "method", "args", "url", "body", "model"), _COLLECTIONS)
@respx.mock
async def test_collection_accessors_parse_once_and_preserve_envelopes(
    client: NetskopeClient,
    aclient: AsyncNetskopeClient,
    asynchronous: bool,
    namespace: str,
    method: str,
    args: tuple,
    url: str,
    body: dict,
    model: type[BaseModel],
) -> None:
    route = respx.get(url).mock(return_value=httpx.Response(200, json=body))
    resource = _resource(aclient if asynchronous else client, namespace)
    operation = getattr(resource.with_response, method)

    response = await operation(*args) if asynchronous else operation(*args)
    assert isinstance(response, ApiResponse)
    records = response.parse()

    assert len(records) == 1
    assert isinstance(records[0], model)
    assert response.parse() is records
    assert response.json() == body
    assert route.call_count == 1
    if isinstance(records[0], PublisherApp):
        assert records[0].app_id == 7
        assert records[0].model_extra == {"future": {"enabled": False}}
    elif isinstance(records[0], PublisherRelease):
        assert records[0].release_type == "Latest"


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(("namespace", "method", "args", "url", "_body", "_model"), _COLLECTIONS)
@respx.mock
async def test_malformed_collection_keeps_request_metadata_and_original_json(
    client: NetskopeClient,
    aclient: AsyncNetskopeClient,
    asynchronous: bool,
    namespace: str,
    method: str,
    args: tuple,
    url: str,
    _body: dict,
    _model: type[BaseModel],
) -> None:
    body = {"data": {"unexpected": "response-secret"}}
    route = respx.get(url).mock(
        return_value=httpx.Response(200, json=body, headers={"x-request-id": "malformed-42"})
    )
    resource = _resource(aclient if asynchronous else client, namespace)
    operation = getattr(resource.with_response, method)
    response = await operation(*args) if asynchronous else operation(*args)

    with pytest.raises(ResponseValidationError) as caught:
        response.parse()

    assert caught.value.request_method == "GET"
    assert caught.value.request_path == httpx.URL(url).path
    assert caught.value.request_id == "malformed-42"
    assert "response-secret" not in str(caught.value)
    assert response.json() == body
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_app_schema_failure_preserves_raw_data(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    body = {"data": {"apps": [{"app_id": {"secret": "response-secret"}}]}}
    route = respx.get(f"{_BASE}/publishers/42/apps").mock(
        return_value=httpx.Response(200, json=body)
    )
    response = (
        await aclient.publishers.with_response.list_apps(42)
        if asynchronous
        else client.publishers.with_response.list_apps(42)
    )
    with pytest.raises(ResponseValidationError) as caught:
        response.parse()
    assert caught.value.field_errors == ((("app_id",), "int_type"),)
    assert "response-secret" not in str(caught.value)
    assert response.json() == body
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_registration_token_accessor_returns_string_without_reissuing_post(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    body = {"data": {"token": "registration-secret"}, "status": "success"}
    route = respx.post(f"{_BASE}/publishers/42/registration_token").mock(
        return_value=httpx.Response(200, json=body)
    )
    response = (
        await aclient.publishers.with_response.create_registration_token(42)
        if asynchronous
        else client.publishers.with_response.create_registration_token(42)
    )
    assert response.parse() == "registration-secret"
    assert response.parse() == "registration-secret"
    assert response.json() == body
    assert "registration-secret" not in repr(response)
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_missing_token_is_reported_without_response_values(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    body = {"data": {"renamed_token": "registration-secret"}, "status": "success"}
    route = respx.post(f"{_BASE}/publishers/42/registration_token").mock(
        return_value=httpx.Response(200, json=body)
    )
    response = (
        await aclient.publishers.with_response.create_registration_token(42)
        if asynchronous
        else client.publishers.with_response.create_registration_token(42)
    )
    with pytest.raises(ResponseValidationError) as caught:
        response.parse()
    assert caught.value.request_path == "/api/v2/infrastructure/publishers/42/registration_token"
    assert "registration-secret" not in str(caught.value)
    assert response.json() == body
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_bulk_upgrade_accessor_types_acknowledgment_and_preserves_payload(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    body = {"status": "success", "message": "Upgrade requested", "total": 2, "future": {"job": 7}}
    route = respx.put(f"{_BASE}/publishers/bulk").mock(return_value=httpx.Response(200, json=body))
    response = (
        await aclient.publishers.with_response.bulk_upgrade([7, 8])
        if asynchronous
        else client.publishers.with_response.bulk_upgrade([7, 8])
    )
    result = response.parse()
    assert isinstance(result, PublisherActionResult)
    assert result.status == "success"
    assert result.message == "Upgrade requested"
    assert result.model_extra == {"total": 2, "future": {"job": 7}}
    assert response.json() == body
    assert sent_json(route) == {"publishers": {"apply": {"upgrade_request": True}, "id": [7, 8]}}
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_legacy_apps_and_bulk_methods_keep_raw_return_values(
    client: NetskopeClient, aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    apps_route = respx.get(f"{_BASE}/publishers/42/apps").mock(
        return_value=httpx.Response(200, json={"data": {"apps": [_APP]}})
    )
    acknowledgment = {"status": "success", "future": {"job": "7"}}
    bulk_route = respx.put(f"{_BASE}/publishers/bulk").mock(
        return_value=httpx.Response(200, json=acknowledgment)
    )
    if asynchronous:
        apps = await aclient.publishers.list_apps(42)
        result = await aclient.publishers.bulk_upgrade([7])
    else:
        apps = client.publishers.list_apps(42)
        result = client.publishers.bulk_upgrade([7])
    assert apps == [_APP]
    assert isinstance(apps[0]["app_id"], str)
    assert result == acknowledgment
    assert apps_route.call_count == 1
    assert bulk_route.call_count == 1
