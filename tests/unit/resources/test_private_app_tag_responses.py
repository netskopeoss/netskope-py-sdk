"""Private-app tag response accessors send canonical bodies and decode typed rows."""

from __future__ import annotations

import inspect

import pytest
import respx

from netskope.exceptions import NetskopeError, ValidationError
from tests.unit.resources.conftest import sent_json

TAGS = "https://t.goskope.com/api/v2/steering/apps/private/tags"

READS = [
    (
        f"{TAGS}/7",
        lambda tags: tags.get(7),
        {"data": {"tag_id": "7", "tag_name": "web", "future": [1]}},
        lambda parsed: parsed.tag_id == 7 and parsed.tag_name == "web",
    ),
]

WRITES = [
    (
        "POST",
        TAGS,
        lambda tags: tags.create(11, ["web", "prod"]),
        {"id": "11", "tags": [{"tag_name": "web"}, {"tag_name": "prod"}]},
        {"data": {"tags": [{"tag_id": 7, "tag_name": "web"}, {"tag_id": 8, "tag_name": "prod"}]}},
        lambda parsed: [tag.tag_name for tag in parsed] == ["web", "prod"],
    ),
    (
        "PUT",
        f"{TAGS}/7",
        lambda tags: tags.update(7, "renamed"),
        {"tag_name": "renamed"},
        {"data": {"tag_id": 7, "tag_name": "renamed"}},
        lambda parsed: parsed.tag_name == "renamed",
    ),
    (
        "PATCH",
        TAGS,
        lambda tags: tags.add([11, "12"], ["web"]),
        {"ids": ["11", "12"], "tags": [{"tag_name": "web"}]},
        {"data": {"private_apps": [{"app_id": 11}, {"app_id": 12}]}},
        lambda parsed: [app.app_id for app in parsed] == [11, 12],
    ),
    (
        "PUT",
        TAGS,
        lambda tags: tags.replace([11], ["web"]),
        {"ids": ["11"], "tags": [{"tag_name": "web"}]},
        {"data": {"private_apps": [{"app_id": 11}]}},
        lambda parsed: [app.app_id for app in parsed] == [11],
    ),
]


def tag_responses(sdk):
    return sdk.private_apps.tags.with_response


async def resolve(result):
    return await result if inspect.isawaitable(result) else result


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("url,invoke,body,check", READS)
@respx.mock
async def test_tag_reads(client, aclient, asynchronous, url, invoke, body, check):
    route = respx.get(url).respond(200, json=body)
    response = await resolve(invoke(tag_responses(aclient if asynchronous else client)))
    assert check(response.parse())
    assert response.json() == body
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("method,url,invoke,payload,body,check", WRITES)
@respx.mock
async def test_tag_writes(client, aclient, asynchronous, method, url, invoke, payload, body, check):
    route = respx.request(method, url).respond(200, json=body)
    response = await resolve(invoke(tag_responses(aclient if asynchronous else client)))
    assert check(response.parse())
    assert sent_json(route) == payload
    assert route.call_count == 1
    assert len(respx.calls) == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("method,url,invoke,payload,body,check", WRITES)
@respx.mock
async def test_tag_writes_do_not_retry_server_failures(
    client, aclient, asynchronous, method, url, invoke, payload, body, check
):
    route = respx.request(method, url).respond(503, json={"message": "unavailable"})
    with pytest.raises(NetskopeError):
        await resolve(invoke(tag_responses(aclient if asynchronous else client)))
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_empty_tag_identifiers_never_reach_http(client, aclient, asynchronous):
    with pytest.raises(ValidationError):
        await resolve(tag_responses(aclient if asynchronous else client).get_policy_in_use([]))
    assert len(respx.calls) == 0
