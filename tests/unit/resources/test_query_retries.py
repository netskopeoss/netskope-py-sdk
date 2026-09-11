"""Resource operations choose retries according to their API semantics."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import APIError, TimeoutError

_BASE = "https://t.goskope.com"

# The minimum an app probe needs (AppProbeUpdateCreateCommon, demconfig.yaml:2666-2707).
_PROBE_ARGS = {
    "app_name": "Slack",
    "frequency": 5,
    "entity": {"user": ["user1"]},
    "os": ["windows"],
    "device_classification": ["managed"],
}


@pytest.fixture
def retry_client() -> Iterator[NetskopeClient]:
    with NetskopeClient(
        tenant="t.goskope.com", api_token="tok", max_retries=2, backoff_factor=0
    ) as client:
        yield client


@pytest.fixture
async def async_retry_client() -> AsyncIterator[AsyncNetskopeClient]:
    async with AsyncNetskopeClient(
        tenant="t.goskope.com", api_token="tok", max_retries=2, backoff_factor=0
    ) as client:
        yield client


def _assert_same_query_retried(route: respx.Route) -> None:
    assert route.call_count == 2
    first, second = (call.request for call in route.calls)
    assert first.url == second.url
    assert first.content == second.content
    for request in (first, second):
        assert "retry_safe" not in request.url.params
        if request.content:
            assert "retry_safe" not in json.loads(request.content)


@respx.mock
def test_user_lookup_retries_without_changing_filter(retry_client: NetskopeClient) -> None:
    route = respx.post(f"{_BASE}/api/v2/users/getusers").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json={"data": [{"id": "alice@example.com"}]}),
        ]
    )

    user = retry_client.users.get("alice@example.com")

    assert user is not None and user.id == "alice@example.com"
    _assert_same_query_retried(route)
    assert json.loads(route.calls[0].request.content)["query"]["filter"] == {
        "and": [{"emails": {"eq": "alice@example.com"}}]
    }


@respx.mock
def test_dem_query_retries_preserving_url_and_body_filters(retry_client: NetskopeClient) -> None:
    route = respx.post(f"{_BASE}/api/v2/dem/query/getentities").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"data": []})]
    )

    assert retry_client.dem.query.get_entities(
        start_time=1_700_000_000,
        end_time=1_700_003_600,
        user="alice@example.com",
        limit=10,
        offset=20,
        sort_order="desc",
    ) == {"data": []}

    _assert_same_query_retried(route)
    assert dict(route.calls[0].request.url.params) == {
        "limit": "10",
        "offset": "20",
        "sortorder": "desc",
    }
    assert json.loads(route.calls[0].request.content)["user"] == "alice@example.com"


@respx.mock
@pytest.mark.parametrize("filter_expr", [None, "active"])
def test_inventory_query_retries_with_or_without_body(
    retry_client: NetskopeClient, filter_expr: str | None
) -> None:
    route = respx.post(f"{_BASE}/api/v2/spm/inventory/getresources").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"data": []})]
    )

    assert retry_client.spm.inventory(filter=filter_expr) == {"data": []}

    _assert_same_query_retried(route)
    body = json.loads(route.calls[0].request.content)
    assert body["group_by"] == "resource_name"
    assert body.get("ngl_query") == filter_expr


@respx.mock
async def test_async_tag_query_retries(async_retry_client: AsyncNetskopeClient) -> None:
    route = respx.post(f"{_BASE}/api/v2/devices/device/tags/gettags").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"data": []})]
    )

    assert await async_retry_client.devices.tags.list(name="Managed", limit=10) == []

    _assert_same_query_retried(route)


@respx.mock
async def test_async_dem_query_retries(async_retry_client: AsyncNetskopeClient) -> None:
    route = respx.post(f"{_BASE}/api/v2/dem/query/getentities").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"data": []})]
    )

    assert await async_retry_client.dem.query.get_entities(
        start_time=1_700_000_000, end_time=1_700_003_600, limit=10, offset=20
    ) == {"data": []}

    _assert_same_query_retried(route)
    assert dict(route.calls[0].request.url.params) == {"limit": "10", "offset": "20"}


@respx.mock
@pytest.mark.parametrize(
    "operation, path, body",
    [
        pytest.param(
            lambda client: client.incidents.with_response.get_uci("alice", from_time=0),
            "/api/v2/ubadatasvc/user/uci",
            {"userId": "alice", "score": 1.0},
            id="uci",
        ),
        pytest.param(
            lambda client: client.incidents.with_response.get_anomalies(["alice"]),
            "/api/v2/incidents/users/getanomalies",
            {"results": []},
            id="anomalies",
        ),
        pytest.param(
            lambda client: client.dem.query.with_response.get_data(
                "ux_score", ["user"], begin=1_000_000, end=2_000_000
            ),
            "/api/v2/dem/query/getdata",
            {"data": []},
            id="dem-getdata",
        ),
    ],
)
def test_read_only_posts_opt_into_replay(
    retry_client: NetskopeClient,
    operation: Callable[[NetskopeClient], object],
    path: str,
    body: dict[str, object],
) -> None:
    route = respx.post(f"{_BASE}{path}").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=body)]
    )

    operation(retry_client)

    _assert_same_query_retried(route)


@respx.mock
@pytest.mark.parametrize(
    "operation, path, body",
    [
        pytest.param(
            lambda client: client.incidents.with_response.list_notes("134"),
            "/api/v2/incidents/dlpincidents/134/notes",
            {"data": []},
            id="incident-notes",
        ),
        pytest.param(
            lambda client: client.dem.apps.with_response.list(),
            "/api/v2/dem/apps",
            {"apps": []},
            id="dem-apps",
        ),
    ],
)
def test_response_helper_gets_keep_their_method_default(
    retry_client: NetskopeClient,
    operation: Callable[[NetskopeClient], object],
    path: str,
    body: dict[str, object],
) -> None:
    route = respx.get(f"{_BASE}{path}").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=body)]
    )

    operation(retry_client)

    _assert_same_query_retried(route)


@respx.mock
@pytest.mark.parametrize(
    "operation, path",
    [
        pytest.param(
            lambda client: client.incidents.with_response.add_note("134", "note"),
            "/api/v2/incidents/dlpincidents/134/notes",
            id="add-note",
        ),
        pytest.param(
            lambda client: client.dem.probes.with_response.create("Probe", **_PROBE_ARGS),
            "/api/v2/dem/appprobes",
            id="typed-create-probe",
        ),
    ],
)
def test_writes_through_response_helpers_are_not_replayed(
    retry_client: NetskopeClient,
    operation: Callable[[NetskopeClient], object],
    path: str,
) -> None:
    route = respx.post(f"{_BASE}{path}").mock(return_value=httpx.Response(503))

    with pytest.raises(APIError):
        operation(retry_client)

    assert route.call_count == 1


@respx.mock
async def test_async_response_helpers_split_reads_from_writes(
    async_retry_client: AsyncNetskopeClient,
) -> None:
    read = respx.post(f"{_BASE}/api/v2/ubadatasvc/user/uci").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"userId": "a", "score": 1.0})]
    )
    write = respx.post(f"{_BASE}/api/v2/dem/appprobes").mock(return_value=httpx.Response(503))

    await async_retry_client.incidents.with_response.get_uci("a", from_time=0)
    with pytest.raises(APIError):
        await async_retry_client.dem.probes.with_response.create("P", **_PROBE_ARGS)

    _assert_same_query_retried(read)
    assert write.call_count == 1


@respx.mock
@pytest.mark.parametrize(
    "operation, path",
    [
        pytest.param(
            lambda client: client.devices.tags.create("Managed"),
            "/api/v2/devices/device/tags",
            id="create-tag",
        ),
        pytest.param(
            lambda client: client.dem.probes.create("Probe", **_PROBE_ARGS),
            "/api/v2/dem/appprobes",
            id="create-probe",
        ),
        pytest.param(
            lambda client: client.private_apps.update_discovery_settings({"enabled": True}),
            "/api/v2/steering/apps/private/discoverysettings",
            id="update-discovery",
        ),
    ],
)
@pytest.mark.parametrize("failure", ["response", "timeout"])
def test_mutations_in_query_capable_resources_are_not_retried(
    retry_client: NetskopeClient,
    operation: Callable[[NetskopeClient], object],
    path: str,
    failure: str,
) -> None:
    route = respx.post(f"{_BASE}{path}")
    if failure == "timeout":
        route.mock(side_effect=httpx.ReadTimeout("The operation may already have completed"))
    else:
        route.mock(return_value=httpx.Response(503))

    with pytest.raises((APIError, TimeoutError)):
        operation(retry_client)

    assert route.call_count == 1
    assert "retry_safe" not in route.calls[0].request.url.params
    assert "retry_safe" not in json.loads(route.calls[0].request.content)


@respx.mock
@pytest.mark.parametrize(
    "operation, path",
    [
        pytest.param(
            lambda client: client.devices.tags.create("Managed"),
            "/api/v2/devices/device/tags",
            id="create-tag",
        ),
        pytest.param(
            lambda client: client.dem.probes.create("Probe", **_PROBE_ARGS),
            "/api/v2/dem/appprobes",
            id="create-probe",
        ),
    ],
)
async def test_async_mutations_in_query_capable_resources_are_not_retried(
    async_retry_client: AsyncNetskopeClient,
    operation: Callable[[AsyncNetskopeClient], Awaitable[object]],
    path: str,
) -> None:
    route = respx.post(f"{_BASE}{path}").mock(return_value=httpx.Response(503))

    with pytest.raises(APIError):
        await operation(async_retry_client)

    assert route.call_count == 1
    assert "retry_safe" not in route.calls[0].request.url.params
    assert "retry_safe" not in json.loads(route.calls[0].request.content)
