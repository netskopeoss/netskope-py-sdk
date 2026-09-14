"""Private-app tag response accessors send canonical bodies and decode typed rows."""

from __future__ import annotations

import inspect
from typing import Any

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import NetskopeError, ValidationError
from netskope.models.private_apps import (
    PrivateApp,
    PrivateAppDiscoverySettings,
    PrivateAppMutationResult,
    PrivateAppPolicyUsage,
)
from tests.unit.resources.conftest import (
    CONTRACT_BASE,
    CONTRACT_TENANT,
    EXAMPLE_BASE,
    sent_json,
    sent_params,
)

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


# --- Gateway contract conformance -------------------------------------------------------------
#
# Folded in from the spec-conformance reviews: each test cites the
# production/endpoints file and line whose shape it pins.

_BASE = "https://t.goskope.com"
_APPS_URL = f"{_BASE}/api/v2/steering/apps/private"
_PUBLISHERS_URL = f"{_APPS_URL}/publishers"
_DISCOVERY_URL = f"{_APPS_URL}/discoverysettings"
_POLICY_IN_USE_URL = f"{_APPS_URL}/getpolicyinuse"
_APP = {
    "app_id": 42,
    "app_name": "internal-dashboard",
    "host": "10.0.0.5",
    "port": "443",
    "clientless_access": True,
}

_ACK = {"status": "success", "message": "2 private apps deleted"}
_DISCOVERY = {
    "data": {
        "id": 3,
        "settings": {"enabled": True},
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
    }
}


class TestPrivateAppResponsesSync:
    """client.private_apps.with_response — the methods C7 listed."""

    @respx.mock
    def test_bulk_delete_sends_string_ids_and_decodes_the_acknowledgment(
        self, client: NetskopeClient
    ) -> None:
        route = respx.delete(_APPS_URL).mock(return_value=httpx.Response(200, json=_ACK))
        response = client.private_apps.with_response.bulk_delete([123, 456])
        assert sent_json(route) == {"private_app_ids": ["123", "456"]}
        result = response.parse()
        assert isinstance(result, PrivateAppMutationResult)
        assert result.status == "success"

    @respx.mock
    def test_bulk_delete_decodes_an_empty_body_as_none(self, client: NetskopeClient) -> None:
        respx.delete(_APPS_URL).mock(return_value=httpx.Response(204))
        assert client.private_apps.with_response.bulk_delete([1]).parse() is None

    def test_bulk_delete_rejects_an_unusable_id_before_the_request(
        self, client: NetskopeClient
    ) -> None:
        with respx.mock:
            route = respx.route(host="t.goskope.com")
            with pytest.raises(ValidationError):
                client.private_apps.with_response.bulk_delete(["../1"])
            assert not route.called

    @respx.mock
    def test_remove_publishers_deletes_the_association(self, client: NetskopeClient) -> None:
        """The 200 is ``{data: [private_apps_response_item], status}`` (:167-178)."""
        body = {"data": [_APP, {**_APP, "app_id": 43, "app_name": "other"}], "status": "success"}
        route = respx.delete(_PUBLISHERS_URL).mock(return_value=httpx.Response(200, json=body))
        result = client.private_apps.with_response.remove_publishers([42], [7, 8]).parse()
        assert sent_json(route) == {
            "private_app_ids": ["42"],
            "publisher_ids": ["7", "8"],
        }
        assert result is not None
        assert [app.app_name for app in result] == ["internal-dashboard", "other"]

    @respx.mock
    def test_remove_publishers_decodes_an_empty_body_as_none(self, client: NetskopeClient) -> None:
        respx.delete(_PUBLISHERS_URL).mock(return_value=httpx.Response(204))
        assert client.private_apps.with_response.remove_publishers([42], [7]).parse() is None

    @respx.mock
    def test_get(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_APPS_URL}/42").mock(
            return_value=httpx.Response(200, json={"data": _APP})
        )
        app = client.private_apps.with_response.get(42).parse()
        assert route.calls.last.request.method == "GET"
        assert isinstance(app, PrivateApp)
        assert app.app_name == "internal-dashboard"

    @respx.mock
    def test_get_policy_in_use_posts_string_ids(self, client: NetskopeClient) -> None:
        route = respx.post(_POLICY_IN_USE_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": [{"app_id": "42", "num_in_use": 1, "policies": ["p1"]}],
                },
            )
        )
        usage = client.private_apps.with_response.get_policy_in_use([42]).parse()
        assert sent_json(route) == {"ids": ["42"]}
        assert isinstance(usage, PrivateAppPolicyUsage)
        assert isinstance(usage.data, list)
        assert usage.data[0].policies == ["p1"]

    @respx.mock
    def test_get_discovery_settings(self, client: NetskopeClient) -> None:
        route = respx.get(_DISCOVERY_URL).mock(return_value=httpx.Response(200, json=_DISCOVERY))
        settings = client.private_apps.with_response.get_discovery_settings().parse()
        assert route.call_count == 1
        assert isinstance(settings, PrivateAppDiscoverySettings)
        assert settings.id == 3

    @respx.mock
    def test_replace_publishers_uses_put(self, client: NetskopeClient) -> None:
        route = respx.put(_PUBLISHERS_URL).mock(
            return_value=httpx.Response(200, json={"data": {"private_apps": [_APP]}})
        )
        apps = client.private_apps.with_response.replace_publishers([42], [7]).parse()
        assert route.calls.last.request.method == "PUT"
        assert sent_json(route) == {"private_app_ids": ["42"], "publisher_ids": ["7"]}
        assert [app.app_id for app in apps] == [42]


class TestPrivateAppResponsesAsync:
    """The async mirrors of the same twelve methods."""

    @respx.mock
    async def test_bulk_delete(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete(_APPS_URL).mock(return_value=httpx.Response(200, json=_ACK))
        response = await aclient.private_apps.with_response.bulk_delete([123])
        assert sent_json(route) == {"private_app_ids": ["123"]}
        assert response.parse().status == "success"

    @respx.mock
    async def test_bulk_delete_decodes_an_empty_body_as_none(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        respx.delete(_APPS_URL).mock(return_value=httpx.Response(204))
        response = await aclient.private_apps.with_response.bulk_delete([1])
        assert response.parse() is None

    @respx.mock
    async def test_remove_publishers(self, aclient: AsyncNetskopeClient) -> None:
        body = {"data": [_APP], "status": "success"}
        route = respx.delete(_PUBLISHERS_URL).mock(return_value=httpx.Response(200, json=body))
        response = await aclient.private_apps.with_response.remove_publishers([42], [7, 8])
        assert sent_json(route) == {"private_app_ids": ["42"], "publisher_ids": ["7", "8"]}
        parsed = response.parse()
        assert parsed is not None
        assert [app.app_id for app in parsed] == [_APP["app_id"]]

    @respx.mock
    async def test_remove_publishers_decodes_an_empty_body_as_none(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        respx.delete(_PUBLISHERS_URL).mock(return_value=httpx.Response(204))
        response = await aclient.private_apps.with_response.remove_publishers([42], [7])
        assert response.parse() is None

    @respx.mock
    async def test_get(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_APPS_URL}/42").mock(return_value=httpx.Response(200, json={"data": _APP}))
        response = await aclient.private_apps.with_response.get(42)
        assert response.parse().host == "10.0.0.5"

    @respx.mock
    async def test_get_policy_in_use(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_POLICY_IN_USE_URL).mock(
            return_value=httpx.Response(200, json={"status": "success", "data": {"42": ["p1"]}})
        )
        response = await aclient.private_apps.with_response.get_policy_in_use([42])
        assert sent_json(route) == {"ids": ["42"]}
        assert response.parse().data == {"42": ["p1"]}

    @respx.mock
    async def test_get_discovery_settings(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_DISCOVERY_URL).mock(return_value=httpx.Response(200, json=_DISCOVERY))
        response = await aclient.private_apps.with_response.get_discovery_settings()
        settings = response.parse()
        assert settings.settings is not None
        assert settings.updated_at == "2026-01-02T00:00:00Z"

    @respx.mock
    async def test_replace_publishers(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.put(_PUBLISHERS_URL).mock(
            return_value=httpx.Response(200, json={"data": {"private_apps": [_APP]}})
        )
        response = await aclient.private_apps.with_response.replace_publishers([42], [7])
        assert route.calls.last.request.method == "PUT"
        assert [app.app_id for app in response.parse()] == [42]


_CONTRACT_APPS_URL = f"{CONTRACT_BASE}/api/v2/steering/apps/private"


@pytest.mark.parametrize(
    "path,invoke",
    [
        ("getpolicyinuse", lambda c: c.private_apps.get_policy_in_use([7])),
        ("tags/getpolicyinuse", lambda c: c.private_apps.tags.get_policy_in_use([7])),
        ("getpolicyinuse", lambda c: c.private_apps.with_response.get_policy_in_use([7])),
        (
            "tags/getpolicyinuse",
            lambda c: c.private_apps.tags.with_response.get_policy_in_use([7]),
        ),
    ],
)
@respx.mock
def test_policy_in_use_posts_are_not_retried(
    retrying_client: NetskopeClient, path: str, invoke: Any
) -> None:
    """A 503 is surfaced after exactly one attempt, not replayed."""
    route = respx.post(f"{_CONTRACT_APPS_URL}/{path}").mock(return_value=httpx.Response(503))
    with pytest.raises(Exception, match="5"):
        invoke(retrying_client)
    assert route.call_count == 1


@pytest.mark.parametrize(
    "path,invoke",
    [
        ("getpolicyinuse", lambda c: c.private_apps.get_policy_in_use([7])),
        ("tags/getpolicyinuse", lambda c: c.private_apps.tags.get_policy_in_use([7])),
        ("getpolicyinuse", lambda c: c.private_apps.with_response.get_policy_in_use([7])),
        (
            "tags/getpolicyinuse",
            lambda c: c.private_apps.tags.with_response.get_policy_in_use([7]),
        ),
    ],
)
@respx.mock
async def test_async_policy_in_use_posts_are_not_retried(path: str, invoke: Any) -> None:
    """The async mirrors of all four sites are equally unreplayable."""
    route = respx.post(f"{_CONTRACT_APPS_URL}/{path}").mock(return_value=httpx.Response(503))
    async with AsyncNetskopeClient(
        tenant=CONTRACT_TENANT,
        api_token="synthetic-token",
        allow_custom_tenant=True,
        max_retries=3,
        backoff_factor=0,
    ) as client:
        with pytest.raises(Exception, match="5"):
            await invoke(client)
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_remove_publishers_returns_the_declared_private_apps(
    contract_client: NetskopeClient, contract_aclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    """``DELETE /apps/private/publishers`` 200 is ``{data: [...], status}``.

    Spec: steering/npa_private_publisher.yaml:167-178, whose ``data`` items are
    ``private_apps_response_item``; byte-identical to the PATCH (:193-...) and
    PUT on the same path, which the SDK already decodes as ``list[PrivateApp]``.
    """
    body = {
        "data": [{"id": 2, "name": "private_app_name", "host": "abc.com"}],
        "status": "success",
    }
    route = respx.delete(f"{_CONTRACT_APPS_URL}/publishers").mock(
        return_value=httpx.Response(200, json=body)
    )
    accessor = (contract_aclient if asynchronous else contract_client).private_apps.with_response
    response = accessor.remove_publishers([2], [4, 5])
    if asynchronous:
        response = await response
    apps = response.parse()

    assert apps is not None
    assert all(isinstance(app, PrivateApp) for app in apps)
    assert [(app.app_id, app.app_name, app.host) for app in apps] == [
        (2, "private_app_name", "abc.com")
    ]
    assert sent_json(route) == {"private_app_ids": ["2"], "publisher_ids": ["4", "5"]}


_EXAMPLE_APPS_URL = f"{EXAMPLE_BASE}/api/v2/steering/apps/private"


@respx.mock
def test_private_app_filters_become_one_query_expression(example_client: NetskopeClient) -> None:
    """listNPAPrivateApps declares fields, query, offset and limit — nothing else.

    Spec: npa_apps_private.yaml:490-524 for the parameters, and
    npa_generic.yaml:495-504 for the columns and operators each filter renders
    as.  ``in_policy`` and ``reachable`` take ``yes``/``no`` there, while
    ``clientless_access`` takes ``true``/``false``.
    """
    route = respx.get(_EXAMPLE_APPS_URL).mock(
        return_value=httpx.Response(200, json={"data": {"private_apps": []}, "total": 0})
    )
    example_client.private_apps.with_response.list_page(
        app_name="testName", in_policy=True, clientless_access=True, limit=5, offset=0
    )

    assert sent_params(route) == {
        "query": "name sw testName and in_policy eq yes and clientless_access eq true",
        "limit": "5",
        "offset": "0",
    }
